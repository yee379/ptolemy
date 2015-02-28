import redis
from re import match, search, IGNORECASE

import traceback

import logging
from math import floor

from slac_utils.managers import FanOutManager, Manager, Worker, Supervisor
from slac_utils.command import ManagerDaemon, DefaultList
from slac_utils.time import datetime_to_epoch, now
from ptolemy.storage.commands import StorageCommand
from ptolemy.storage.feeders import Feeder
from slac_utils.request import Task
from slac_utils.string import dict_to_kv


class Float(object):
    v = None
    def __init__(cls,f):
        cls.v = float(f)
    def __gt__(cls,o):
        return cls.v > o
    def __ge__(cls,o):
        return cls.v >= o
    def __lt__(cls,o):
        return cls.v < o
    def __le__(cls,o):
        return cls.v <= o
    

class AnalyseWorker( Feeder ):
    """
    An analyse worker listens for new data from the queue. it's function is to match these incoming
    data and determine if there is some anomalous that has occured. for example
    - determine how many uplinks a switch has, and monitor the operational status of each of these ports - if any of operational status is down, then alert
    - determine the modules (fru-able) that are a switch. monitor the operational status of the modules and alert if any go down
    as we need to compare against history, we use redis as a quick store for previous data rather than an expensive fetch to a backend db.
    """
    proc_name = 'ptolemy analyse generic worker'

    prefix = 'pt:ana:'
    alert_queue = None
    
    analyse = None
    
    def to_amqp_key( self, spec='#', group='#', **kwargs ):
        return '#.%s.group.%s.#' % (spec, group)
    
    def setup( self, **kwargs ):
        
        self.analyse = kwargs['analyse']

        # work out keys to monitor from config
        keys = {}
        for n in self.analyse:
            # logging.debug(" N: %s" % (n,))
            for w in self.analyse[n]:
                a = self.analyse[n][w]
                k = self.to_amqp_key( **a )
                logging.debug("stanza %s -> queue %s" % (a,k))
                if not k in keys:
                    keys[k] = True
        self.keys = [ k for k in sorted(keys) ]
        # logging.error("KEYS %s" % (self.keys,))        
        super( AnalyseWorker, self ).setup(**kwargs)

        # keep the last known in redis for stateful analysis
        server, _tmp, port = kwargs['cache'].pop(0).partition(':')
        self.redis = redis.StrictRedis( host=server, port=int(port), db=0 )
        # reduce pingpongs
        self.pipe = self.redis.pipeline()    

        # alert queue
        self.alert_queue = getattr( self.queue_factory_obj, 'alert' )( connection=self.connection, pool='default', keys=['#',] )
    
    
    def process_alert( self, metric, context, data ):
        """
        send an alert out
        """
        try:
            logging.warn( " ! %33s\t%75s\t%s->%s\t%s->%s " % (metric,dict_to_kv(context),data['last_state'],data['state'],data['last_value'],data['value']) )
            # format a message
            c = context.copy()
            m = metric
            if ':' in metric:
                m, other = metric.split(':')
            c['metric'] = m
            msg = Task( context=c, data=data )
            # TODO: Set timestamp from original message
            # logging.warn('sending alert: %s' % (msg,))
            self.alert_queue.put( msg )
        except Exception, e:
            logging.error("Err %s %s" % (type(e),e))
            

    def find( self, meta ):
        """ returns list of matching analyse directives for this """
        matches = {}
        for name in self.analyse:
            # logging.debug("name: %s" % (name,))
            for w in ( 'what', 'when' ):
                if self.analyse[name][w]['spec'] == meta['spec'] and self.analyse[name][w]['group'] == meta['group']:
                    if not w in matches:
                        matches[w] = {}
                    matches[w][name] = True
        # logging.debug("  %s" % (matches,))
        what = [ n for n in matches['what'] ] if 'what' in matches else []
        when = [ n for n in matches['when'] ] if 'when' in matches else []
        return what, when

    def get_key( self, name, context ):
        """ returns string repr of context """
        k = dict_to_kv(context).replace(' ',',').replace("'",'')
        # logging.error("K: %s %s" % (name, k,))
        return 'pt:ana-g:%s:%s' % (name, k )
    
    def process_what( self, w, context, data, expire_seconds=10800 ):
        """
        update the redis cache with this context if we have a directive that matches
        use key pt:ana-g:<what>:<context> = <value>|None
        add an expiry on the item - 30 mins?
        """
        d = self.analyse[w]['what']['field']
        merged = dict( data.items() + context.items() )

        # if not w in ( 'ap.down', 'devices.unreachable', 'uplinks.down' ):
            # logging.info("MERGED: %s %s \t %s" % (w,d['name'],merged,))

        if not d['name'] in merged:
            # raise SyntaxError("field %s not in data" % (d['name'],))
            return 
        
        if 'regex' in d:
            # if not w in ( 'ap.down', 'devices.unreachable', 'uplinks.down' ):
            # logging.info("+ what: %s regex: search( '%s' on '%s')" % (w,d['regex'],merged[d['name']]))
            # deal with teh fact that as things change, it may no longer match, so we explicitly delete the entry too
            k = self.get_key( w, context )
            if merged[d['name']] and search( d['regex'], str(merged[d['name']]) ):
                # set a key in redis for lookups, expire if not seen in a while
                # contention issue if parallel threads operate on same key?
                self.redis.setnx( k, (None,None) )
                self.redis.expire( k, expire_seconds )
                # logging.error("WHAT NX: %s, EX: %s \t%s" % (nx,ex,k))
            else:
                # logging.error("WHAT DEL: %s" % (k,))
                self.redis.delete( k )
        else:
            raise SyntaxError, 'unknown field directive %s' % (d,)
        
        
    def process_when( self, w, context, data, expire_seconds=10800 ):
        """
        if a key exists in redis for this item, then we want to do some simple comparisions
        against it's last known value which is stored in redis under the same key
        """
        d = self.analyse[w]['when']['field']
        
        # match to see if we have this under meta
        k = self.get_key(w, context)
        last_state = None
        last_value = None
        state = False # match against where condition
        value = data[d['name']]
        try:
            last_state, last_value = eval( self.redis.get(k) )
            logging.debug( "found %s/%s\t%s" % (last_state,last_value,k))
        except:
            pass
        ex = self.redis.exists(k)
        if ex:
            
            # TODO deal with numbers of d['eq']
            if 'eq' in d:
                if str(value) == str(d['eq']):
                    state = True
            elif 'ne' in d:
                if str(value) != str(d['ne']):
                    state = True
            elif 'ge' in d:
                if float(value) >= d['ge']:
                    state = True
            elif 'gt' in d:
                if float(value) > d['gt']:
                    state = True
            elif 'le' in d:
                if float(value) >= d['le']:
                    state = True
            elif 'lt' in d:
                if float(value) < d['lt']:
                    state = True
            elif 'inside' in d or 'outside' in d:
                x = 'inside' if 'inside' in d else 'outside'
                l,h = d[x].split(',')
                l = float(l)
                h = float(h)
                v = float(value)
                if x == 'inside':
                    if not v > l and v < h:
                        state = True
                elif x == 'outside':
                    if v < l or v > h:
                        state = True
                # logging.error("RANGE %s\t%s\t %s - %s - %s" % ( alert,k,l,v,h,))
                
            # else:
            #     for c in ( 'gt', 'ge', 'lt', 'le' ):
            #         f = Float(v)
            #         if c in d:
            #             found = True
            #             if getattr(f, '__%s__'%c)( float(d[c]) ):
            #                 alert = True
            #             break
                
            else:
                raise SyntaxError, 'unknown field directive %s' % (d,)
                                
            # update cache
            r = self.redis.set(k,(state,value))
            self.redis.expire( k, expire_seconds )
        
            # alert if the where condition is met or if the state has changed since the last value
            # logging.debug("  => %s(%s)\t %s(%s)" % (value, state, last_value, last_state ) )
            if state or ( not last_state == None and not state == last_state ):
                return { 'value': value, 'last_value': last_value, 'state': state, 'last_state': last_state }

        return None
    
    def save( self, time, meta, context, data, time_delta=None ):
        """
        analyse each incoming monitoring message
        we basically trawl through the analyse stanza and determine the meta and data elements to be considered
        to minimise the amount of real data to analyse, we only consider those which match the 'what' contexts - to implement this we keep a local variable what_to_analyse
        """
        try:

            # logging.error("META: %s, CONTEXT: %s, DATA: %s" % (meta, context,data))
            what, when = self.find( meta )
            
            # setup meta data
            for w in what:
                try:
                    self.process_what( w, context, data )
                except Exception,e:
                    logging.error("Err (what): %s for %s %s\n%s" % (e,meta,context, traceback.format_exc()) )

            # if not meta['spec'] in ( 'transceiver', ):
            #     logging.info("meta: %s, what: %s, when: %s" % (meta,what,when))

            # monitor the real data
            for w in when:
                for name, stanza in self.analyse.iteritems():
                    if w == name:
                        # logging.info("W: %s\t%s" % (w,name))
                        try:
                            this_data = self.process_when( w, context, data )
                            # add the condition to this_data
                            if not this_data == None:
                                this_data['condition'] = stanza
                                self.process_alert( name, context, this_data )
                        except Exception,e:
                            logging.error("Err (where): %s for %s %s\n%s" % (e,meta,context,traceback.format_exc()))

            
        except Exception, e:
            logging.error("%s, %s %s" % (context,type(e),e))

    
class Generic( StorageCommand ):
    """
    Monitors and alerts on port capacities
    """
    worker = AnalyseWorker
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        manager = parser.add_argument_group( 'manager settings')
        manager.add_argument( '-p', '--pool',    help='pool name',  default=settings.POOL )
        manager.add_argument( '-k', '--keys',     help='key name',   action='append', default=[] )
        manager.add_argument( '-w', '--min_workers', help='number of workers',   default=settings.WORKERS, type=int )

        # add defaults
        ampq = parser.add_argument_group('ampq options')
        ampq.add_argument( '--host',          help='ampq host',     default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port',     default=settings.BROKER_PORT, type=int )
        ampq.add_argument( '--vhost',         help='ampq vhost',    default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )
        
        analyse = parser.add_argument_group('analysis options')
        analyse.add_argument( '--analyse',      help='analyse data', default=settings.ANALYSE )
        
        redis = parser.add_argument_group( 'cache settings')
        redis.add_argument( '--cache', help='redis server(s)', default=DefaultList(settings.CACHE_HOST))
