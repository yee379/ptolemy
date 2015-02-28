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


def rate( latest, oldest, capacity=None ):
    # logging.debug("l%s o%s c%s" % (latest,oldest,capacity))
    if latest and oldest and capacity:
        try:
            bits = ( latest[1] - oldest[1] ) * 8. 
            secs = latest[0] - oldest[0]
            return "%0.6f" % (bits/(capacity*secs),)
        except Exception, e:
            # logging.error("ERR: %s %s" % (type(e),e))
            pass
    return None
    
    
# def is_virtual( key ):
#     return search( r'(vl|nu|stack|span|po|Do|(Fa|Gi)0\.\d+|Lo0|CPP|EO0)', key, IGNORECASE )
    
class CapacityWorker( Feeder ):
    """
    keep a history of packet counters in redis and do analysis
    there are two types of data we want
    1) the (fixed) capacity of the port (eg 1000mbps)
        use standard redis string with an int
        we also filter out non-physical ports (as they lie sometimes about throughput)
    2) a window of counter values with timestamps
        use redis Z store, with a score on the epoch time and a tuple (time,counter)
        we can then do a zrangebyscore to get the latest values
        
    each new message executes:
    1) pre_bulk_process)
      - setup the variables to use
    2) save loop)
      - commit each data point
    3) post_bulk_process)
      - do the analysis
      - write rank tables
      - send alerts
    """
    proc_name = 'ptolemy analyse capacity worker'
    # garbage_collect_freq = 1000
    prefix = 'pt:cap:'
    key_prefix = prefix + '{device}:{physical_port}'
    top_score_key_prefix = prefix + '{time}'
    
    top_on_device_key_prefix = prefix + '{device}:{time}'
    top_uplinks_key_prefix = prefix + 'uplinks:{time}'
    
    ranges = ( 1,5,15,30,60 )
    
    alert_queue = None
    
    
    def key_to_hash( self, key ):
        a = key.replace( self.prefix, '' ).split(':')
        h = {}
        h['device'] = a.pop(0)
        h['physical_port'] = a.pop(0)
        try:
            h['direction'] = a.pop(0)
        except:
            pass
        return h
    
    def setup( self, **kwargs ):
        super( CapacityWorker, self ).setup(**kwargs)
        # keep the last known in redis for stateful analysis
        server, _tmp, port = kwargs['cache'].pop(0).partition(':')
        self.redis = redis.StrictRedis( host=server, port=int(port), db=0 )
        # reduce pingpongs
        self.pipe = self.redis.pipeline()    
        # alert queue
        self.alert_queue = getattr( self.queue_factory_obj, 'alert' )( connection=self.connection, pool='default', keys=['#',] )
    
    def save_speed_meta( self, time, key, data ):
        # pick only real ports (as virtual ports don't always make sense for capacity)
        if ( 'physical' in data and data['physical'] ) and 'speed' in data:
            self.pipe.set( "%s:cap" % (key,), data['speed'])

    def save_layer1_meta( self, time, key, data ):
        # determine if the port is connected to another switch
        # logging.error("LAYER1 %s\t%s" % (key,data))
        self.pipe.set( '%s:peer'%(key,), True )
        # self.pipe.set( self.peer_prefix.format( device=))
        
    def save_data( self, time, key, data ):
        """
        commit the data into redis
        """
        if 'octets_in' in data and 'octets_out' in data:
            t = int(datetime_to_epoch(time))
            for d in ( 'in', 'out' ):
                self.pipe.zadd( "%s:%s" % (key,d), t, int(data['octets_%s'%d]) )
        
    def analyse( self, data, capacity ):
        """
        determine the average throughputs for ranges
        """
        # logging.debug("      analyse: %s %s" % (data,capacity))
        score = {
            'raw': []
        }
        recent = None
        at = {}
        for i in self.ranges:
            at[i] = None

        for x in data:
            i = ( x[1], int(x[0]) )
            # keep raw values too
            score['raw'].append(i)
            # logging.debug("    i: %s -> t%s v%s" % (i,i[0],i[1]))
            if recent == None:
                recent = i
            for t in self.ranges:
                # logging.info("AT: %s %s " % (t,at[t]))
                if at[t] == None and i[0] < self.ago[t] and i[0] > self.ago[t] - 60:
                    at[t] = i
            # don't bother with the rest, we have all we need
            ok = False
            for t in self.ranges:
                if at[t]:
                    ok = ok and True
            if ok:
                break
    
        # add summaries
        for i in self.ranges:
            score[i] = rate( recent,at[i],capacity )
        
        # logging.info("  %14s\t %s" % ( capacity, ' \t '.join( [ "%s: %s" % (i,score[i]) for i in score.keys() ] ) ) )    
        return score

            
    def pre_bulk_process( self, time, meta, context, data ):
        # cache the time
        self.now = datetime_to_epoch( now() )
        self.ago = {}
        for i in self.ranges:
            self.ago[i] = self.now - ( i * 60 )
        # logging.debug("+ %s / %s" % (meta['spec'], context)) 
        self.post_capacities = []
        self.post_analyse = []
        return True
    
    
    def get_capacities( self, keys ):
        """ given list of keys, determine the capacity of each port """
        capacity = {}
        if len( keys ):
            # get all capacities for this message's interfaces
            for k in keys:
                self.pipe.get("%s:cap" % (k,))
            try:
                for i,c in enumerate(self.pipe.execute()):
                    k = keys[i]
                    try:
                        capacity[k] = float(c) * 1000000.
                    except Exception,e:
                        pass
            except Exception,e:
                logging.error("  error: %s %s\n%s" % (type(e),e,traceback.format_exc()))
        return capacity
    
    def get_layer1_peers( self, keys ):
        """ given a list of keys, determine if the port is connected to another switch """
        peers = {}
        if len( keys ):
            for k in keys:
                self.pipe.get("%s:peer"%(k,))
            try:
                for i,c in enumerate(self.pipe.execute()):
                    k = keys[i]
                    if c:
                        peers[k] = True
                        # logging.error("PEER %s\t%s" % (k,c))
                    else:
                        peers[k] = False
            except Exception,e:
                logging.error("  error: %s %s\n%s" % (type(e),e,traceback.format_exc()))
        return peers
    
    def get_utilisations( self, keys, capacities ):
        scores = {}
        # if len( capacities.keys() ):
        # logging.debug(" analyse %s" % (len(keys),))
        for k in keys:
            self.pipe.zrevrange( k, 0, -1, withscores=True )
        for i, data in enumerate(self.pipe.execute()):
            # get the original name
            key = keys[i]
            k = key.replace(':out','').replace(':in','')
            if not k in capacities:
                continue
            else:
                scores[key] = self.analyse(data,capacities[k])
        return scores

    def format_utilisation( self, key, scores, capacity ):
        s = key
        c = []
        if s.endswith('in'):
            s = key + ' '
        for t in sorted(scores.keys()):
            try:
                v = "%.6f" % float(scores[t])
            except:
                v = '-       '
            c.append( "%s: %s" % (t, v) )
        return " %60s\t (%8s)\t-> %s" % (s, int(capacity/1000000), ' \t '.join(c) )

    
    def rank_utilisations( self, scores, remove_older_than=120, peers={} ):
        """ update the utilisation scoreboards """

        # logging.debug( ' scores: %s' % (scores,))
        # logging.debug( ' peers: %s' % (peers,))
        
        other_scoreboards = {}
        
        for k in scores.keys():
            
            d = self.key_to_hash(k)
            
            for t in self.ranges:

                # no need to remove as zadd deals with existing entries

                if not scores[k][t] == None:

                    # global scoreboard of all ports
                    score_key = self.top_score_key_prefix.format( time=t )
                    self.pipe.zadd( score_key, float(scores[k][t]), k )
                    other_scoreboards[score_key] = True

                    # uplinks scoreboard
                    peer_key = self.key_prefix.format( device=d['device'], physical_port=d['physical_port'] )
                    uplinks_key = self.top_uplinks_key_prefix.format( time=t )
                    if peer_key in peers and peers[peer_key]:
                        # logging.debug("PEER: %s / %s" % (peer_key,uplinks_key))
                        self.pipe.zadd( uplinks_key, float(scores[k][t]), k )
                    other_scoreboards[uplinks_key] = True

                    # local scoreboard of device
                    device_key = self.top_on_device_key_prefix.format( device=d['device'], time=t )
                    # logging.debug("device: %s" % (device_key,))
                    self.pipe.zadd( device_key, float(scores[k][t]), k )   
                    other_scoreboards[device_key] = True
                    
        self.pipe.execute()

        # remove old entries
        for k in self.post_analyse: # + other_scoreboards.keys():
            # logging.debug(" zremrange: %s" % (k,))
            self.pipe.zremrangebyscore( k, 0, self.ago[self.ranges[-1]] - remove_older_than )
        
        return self.pipe.execute()
    
    
    def process_alert( self, key, score, peers={}, low_pass_value=0.5 ):
        """
        send an alert out
        """
        alert = False
        for t in self.ranges:
        # for t,v in score.iteritems():
            if score[t]:
                score[t] = float(score[t])
                if score[t] > low_pass_value:
                    alert = True
        try:
            if alert:
                # logging.warn( " ! %60s\t %s " % (key,score) )
                logging.warn( " ! %60s" % (key,) )
                has_peer = None
                k = key.replace(':in','').replace(':out','')
                if k in peers:
                    has_peer = peers[k]
                # logging.error("KEY: %s \t %s" % (k, k in peers and peers[k]))
                # format a message
                a = key.split(':')
                c = {
                    'device': a[2],
                    'physical_port': a[3],
                    'direction': a[4],
                    'has_peer': has_peer,
                    'metric': 'capacity.utilisation'
                }
                msg = Task( context=c, data=score )
                # logging.debug('sending alert: %s' % (msg,))
                self.alert_queue.put( msg )
        except Exception, e:
            logging.error("Err %s %s" % (type(e),e))
            
    
    def post_bulk_process( self, *args, **kwargs ):
        """
        we try to use the pipeline as much as possible
        so we sacrifice more local loops for ping/pong reduction
        """
        # flush all writes from save()
        self.pipe.execute()

        # determine capacities of all of the ports
        capacity = self.get_capacities( self.post_capacities )

        # analyse all data but only if we have capacities to match against
        scores = self.get_utilisations( self.post_analyse, capacity )

        # get peering info
        peers = self.get_layer1_peers( self.post_capacities )
        # logging.error("PEER: %s" % (peers,))

        # update ranks
        self.rank_utilisations( scores, peers=peers )
        
        # end!
        self.pipe.reset()

        # alert
        for k,data in scores.iteritems():
            # logging.debug("process alert: %s %s" % (k,data),)
            self.process_alert( k, data, peers=peers )

    
    def save( self, time, meta, context, data, time_delta=None ):
        """
        proxy request to appropriate function
        """
        try:
            
            k = self.key_prefix.format( **context )

            # deal with the packet counters
            if meta['spec'] == 'port_stats':

                # add new data, probably more efficient just to add the unwanted (non-physical) data 
                self.save_data( time, k, data )
                self.post_capacities.append(k)
                for d in ( 'in', 'out' ):
                    this = "%s:%s"%(k,d)
                    self.post_analyse.append( this )
                    # logging.debug(' add: %s -> %s' % (k,this,))
            
            # deal with meta data for the links
            elif meta['spec'] == 'ports':
            
                self.save_speed_meta( time, k, data )
                
            # deal with cdp neigh to determine if uplink
            elif meta['spec'] == 'layer1_peer': # and meta['group'] == 'neighbour':
                
                self.save_layer1_meta( time, k, data )
        
        except KeyError, e:
            pass
        except Exception, e:
            logging.error("(%s) %s: %s %s %s" % (meta,context,type(e),e,traceback.format_exc()))

    
class Capacity( StorageCommand ):
    """
    Monitors and alerts on port capacities
    """
    worker = CapacityWorker
    proc_name = 'ptolemy analyse capacity manager'
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        manager = parser.add_argument_group( 'manager settings')
        manager.add_argument( '--output_format', help="serialisation format of messages", default='pickle' )

        worker = parser.add_argument_group( 'worker settings')
        manager.add_argument( '-p', '--pool',    help='pool name',  default=settings.POOL )
        manager.add_argument( '-k', '--keys',     help='key name',   action='append', default=settings.KEYS )
        worker.add_argument( '-w', '--min_workers', help='number of workers',   default=settings.WORKERS, type=int )

        # add defaults
        ampq = parser.add_argument_group('ampq options')
        ampq.add_argument( '--host',          help='ampq host',     default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port',     default=settings.BROKER_PORT, type=int )
        ampq.add_argument( '--vhost',         help='ampq vhost',    default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )

        redis = parser.add_argument_group( 'cache settings')
        redis.add_argument( '--cache', help='redis server(s)', default=DefaultList(settings.CACHE_HOST))

    
