from slac_utils.managers import Worker
from ptolemy.storage.feeders import Feeder

from slac_utils.string import dict_to_kv
from slac_utils.util import arrayify
from slac_utils.net import netmask_to_prefixlen
from slac_utils.time import now, sleep, datetime_to_epoch
from datetime import timedelta

from slac_utils.messages import Message
from ptolemy.util.redis_mixins import ZStoreMixin

import ipaddress 
import subprocess
import traceback

try:
    from setproctitle import setproctitle
except:
    def setproctitle(blah):
        pass
from slac_utils.net import netmask_to_prefixlen
# import redis

from pprint import pformat
from re import sub
import logging



class SubnetScanner( object ):
    """
    Listen for subnet definitions from ptolemy and fping the hosts to gather statistics
    """
    agent = None
    data = []
    summary_data = {}
    
    def __init__(self, agent):
        self.agent = agent

        
    def do( self, prefix, prefix_len, mean=('loss',), median=('ipdv',), mins=('rtt',), maxs=() ):
        """
        run the scan and do some summarised statistics on the individual ping rtts
        """
        self.data = []
        self.summary_data = {}
        for t in mean:
            self.summary_data[t] = 0.
        for t in median:
            self.summary_data[t] = []
        for t in mins:
            self.summary_data[t] = None
        for t in maxs:
            self.summary_data[t] = None
            
        for i in self.agent.do( prefix, prefix_len ):
            self.data.append( i )

        # ignore the first and last values (network and broadcast addresses)
        if len(self.data) > 2:
            self.data.pop(-1)
            self.data.pop(0)
        self.summary_data['count'] = len(self.data)

        # if we only have a count of one item, it is most likely the svi
        # which is likely to have bad statistics anyway, so we ignore 
        # data analysis
        
        cn = 0
        if self.summary_data['count'] > 1:
            for i in self.data:
                # logging.info("+ i: %s " % (i,))
                for t in mean:
                    for n in arrayify( i, t ):
                        cn = cn + 1
                        self.summary_data[t] = self.summary_data[t] + n
                for t in median:
                    for n in arrayify( i, t ):
                        self.summary_data[t].append( n )
                for t in mins:
                    for n in arrayify( i, t ):
                        if self.summary_data[t] == None or n < self.summary_data[t]:
                            self.summary_data[t] = n
                for t in maxs:
                    for n in arrayify( i, t ):
                        if self.summary_data[t] == None or n > self.summary_data[t]:
                            self.summary_data[t] = n

        # summarise
        if self.summary_data['count'] == 0:
            self.summary_data['loss'] = 1.
        else:
            for t in mean:
                if cn > 0:
                    self.summary_data[t] = float(self.summary_data[t] / cn) 
            for t in median:
                if len(self.summary_data[t]) > 1:
                    try:
                        srtd = sorted(self.summary_data[t])
                        alen = len(srtd)
                        self.summary_data[t] = 0.5*( srtd[(alen-1)//2] + srtd[alen//2] )
                    except Exception,e:
                        logging.error("MEDIAN: %s - %s" % (e,self.summary_data[t],))
                        self.summary_data[t] = None
                else:
                    self.summary_data[t] = None
            
        for t in median + mean + mins + maxs:
            if ( isinstance( self.summary_data[t], list ) and len(self.summary_data[t]) == 0 ) \
                    or self.summary_data[t] == None:
                del self.summary_data[t]

        return self.summary_data
        
def normalise( i ):
    if i == '-':
        return None
    return float(i)

def ipdv( r1, r2 ):
    try:
        return r2 - r1
    except:
        return None
        
def loss( r1, r2 ):
    i = 0.
    for r in ( r1, r2 ):
        if r == None:
            i = i + 0.5
    return i

class FPing( object ):
    """
    wrapper around command line fping program 
    """
    path = None
    
    def __init__(self, binary='/usr/sbin/fping'):
        self.path = binary
        # check etc.
        
    def do( self, prefix, prefix_len ):
        arg = "-r 1 -C 3 -i 10 -t 100 -q -g %s/%s" % ( prefix,prefix_len )
        args = [ self.path ]
        for a in arg.split():
            args.append( a )
        # logging.debug("  running %s" % (" ".join(args)))
        process = subprocess.Popen( ' '.join(args), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        c = process.communicate("\n")
        return self.parse( c[1].split('\n') )
    
    def parse( self, output ):
        for o in output:
            try:
                # logging.debug("%s" % (o,))
                items = o.split()
                ip = items[0]
                r1 = normalise(items[-2])
                r2 = normalise(items[-1])
                this = {
                    'ipdv': ipdv( r1, r2 ),
                    'loss': loss( r1, r2 ),
                    'rtt': [ r1,r2 ],
                }
                for t in this:
                    if this[t] == None:
                        del this[t]
                # logging.debug( "  %s %s\t%s" % (r1, r2, this))
                yield this
            except:
                pass
        return


class Scanner( Worker ):

    scanner = None
    agent = 'fping'
    
    proc_name = 'ptolemy watcher scannerd'
    prefetch_tasks = 1
    
    def setup(self,**kwargs):
        logging.debug("scanner feeder....")
        Worker.setup(self,**kwargs)
        self.agent = FPing()
        self.scanner = SubnetScanner( self.agent )

    def process_task( self, this, stats={}, time_delta=timedelta(seconds=60), **kwargs ):

        setproctitle( "%s"%(self.proc_name))

        try:
            # if the request is too old (say >60s), then ignore it
            # logging.info("MSG: %s" % (this,))
            if this.timestamp < now() - time_delta:
                logging.warn('skipping old test')
                return None

            context = this['context']
            prefix = context['prefix']
            prefix_len = context['prefix_len']
            setproctitle( "%s %s/%s" % (self.proc_name, prefix, prefix_len ) )

            t = now()
            data = self.scanner.do( prefix, prefix_len )
            
            # ignore if we only have one host reporting (prob just the gw)? we don't want to show it as down
            key = 'network.kpi.subnet.prefix.%s.len.%s' % (prefix, prefix_len)
            logging.debug("  fping: %s %s\t%s" % (t,key,data))
            m = Message(
                context= { 'prefix': prefix, "prefix_len": prefix_len },
                meta={
                    'key':  key,
                    'type': 'task',
                    'spec': 'network.kpi',
                    'group': 'subnet',
                    'carbon_key': key,
                },
                data=data,
            )
            m.timestamp = datetime_to_epoch( t )
            m.type = 'task'
            # logging.error("MESSAGE: %s" % (m,))

            setproctitle( "%s"%(self.proc_name))

            return m

        except Exception,e:
            t = traceback.format_exc()
            logging.error("  error: %s\n%s" % (e,t))
            


class HostWatcher( Feeder, ZStoreMixin ):
    """
    Listens for arps and nds reported by ptolemy and compares the entries

    a) notify when new mac address is seen on network
        - do a zadd to mac_key, if it does not already exists, then it's a new mac address
    b) notify when a mac address leaves the network
        - periodically zremrange mac_key upto some time like now() - expire
    c) notify when a new arp tuple is seen on the network
        - do a zadd to arp_key, if it does not already exist, then it's a new arp tuple
    d) notify when a arp tuple leaves the network
        - periodically zremrange mac_key upto some time now() - expire
    TODO:
    e) notify if a mac address changes ip address
        - keep each mac address as key to a redis LIST of ip addresses - how to expire? 
    f) notify if an ip address changes mac address (possibly duplicate)
        - keep as redis hash keyed by ip address of mac address:timestamp? flaps?
    g) notify if a mac address is seen across multiple access ports...
    """
    proc_name = 'ptolemy watcher host'
    
    arp_key = 'pt:host:arps' # timestamp seen?
    mac_key = 'pt:host:macs' # zset of all seen mac addresses with timestamp as score

    expire_at = timedelta( minutes=20 )
    cache_spec = 'caching'
    cache_group = 'hosts'
    
    # setup a results queue
    results_queue_func = 'store'
    
    layer1_prefix = 'pt:layer1:'
    
    # don't output stats
    report_stats_locally = False
    
    def setup( self, **kwargs ):

        super( HostWatcher, self ).setup(**kwargs)
        
        if 'expire' in kwargs:
            self.expire_at = timedelta( seconds=kwargs['expire'] )
        if 'cache_spec' in kwargs:
            self.cache_spec = kwargs['cache_spec']
        if 'cache_group' in kwargs:
            self.cache_group = kwargs['cache_group']
        
        self.connect_redis( kwargs['cache_host'].pop(0) )
        
    def pre_bulk_process( self, time, meta, context, data ):
        self.these_macs = []
        self.these_arps = []
        self.these_ports = []
        if 'group' in meta and meta['group'] in ( 'arps', 'neighbour' ):
            return True
        return False
    
    def format_message( self, time, type, d, contexts=( 'mac_address', 'vlan' ), ignore=['status','type'], uplinks={}, bulk=True ):
        msg = Message( 
            meta={
                'task_id':  None,
                'type':     'task',
                'spec':     self.cache_spec,
                'group':    self.cache_group,
                'merge_context': True, # merge context from existing entries
                'merge_data': True, # merge data from existing entries
                'delayed_context': [ 'ip_address', ] # do not use ip address for lookups but consider it a context item
            },
            context={},
            data={},
        )
        msg._meta['key_name'] = [ 'mac_address', 'vlan' ]
        msg.timestamp = time
        msg._meta['key'] = '.spec.%s.group.%s.' % ( self.cache_spec, self.cache_group )

        # logging.warn(">> %s" % (pformat(d,width=300),) )

        # if it has an ip address, then it's an arp and the physical port locations are just wrong
        directly_connected = True
        if 'ip_address' in d:
            directly_connected = False

        # ignore physical_port and device; would this break the svi of switches for their management port
        # assume subinterfaces tell the real vlan, and strip off any non ints
        if not 'vlan' in d:
            try:
                v = str(d['physical_port'].split('.')[-1] )
                if v.upper().startswith( 'VL' ):
                    v = sub( "[^0-9]", "", v )
                d['vlan'] = int( v )
            except AttributeError:
                pass
            except Exception,e:
                pass

        try:
            d['physical_port'] = self.determine_physical_interface( d['physical_port'] )
        except:
            pass
        
        # if svi, then ignore data
        if 'physical_port' in d:
            p = str(d['physical_port']).upper()
            if p.startswith( 'VL' ):
                directly_connected = False
            # WARNING: hard code port channels to be directly connected for now
            # will need to await portchannel to cdp neighbour mappings to get this correct
            elif p.startswith( 'PO' ):
                directly_connected = False

        # do lookup via redis for physical port and wipe out the data if it's an uplink
        if 'device' in d:
            if 'physical_port' in d:
                key = '%s:%s' % ( d['device'], d['physical_port'] )
                if key in uplinks:
                    directly_connected = False
            else:
                # ensure that we have both device and port, otherwise a merge will be completely incorrect
                directly_connected = False
                
        # clear the data if not directly connected (ie only update the time stamps)
        more_ignore = []
        if not directly_connected:
            more_ignore = [ 'device', 'physical_port' ]
        
        # remove fluff
        for k in ignore + more_ignore:
            if k in d:
                del d[k]

        # logging.warn(" > %s" % (pformat(d,width=300),) )

        # fill in the msg contents
        for k,v in d.iteritems():
            if k in contexts:
                msg.context[k] = v
            else:
                msg.data[k] = v

        return '%s %s' % (dict_to_kv(msg.context),dict_to_kv(msg.data)), msg
        
    
    def determine_physical_interface( self, interface ):
        # strip out subinterfaces so we can do a good lookup for physical layer 1 peers
        v = interface
        try:
            if '.' in d['physical_port']:
                v = interface.split('.')[0]
        except Exception,e:
            pass
        return v
    
    def post_bulk_process( self, time, meta, context, data ):

        # retrieve all matching uplinks for these_ports
        uplinks = {}
        try:
            # logging.error("PORTS: %s" % (self.these_ports,))
            for p in self.these_ports:
                k = '%s%s'%(self.layer1_prefix,p)
                self.pipe.exists( k )
                # logging.error("  k: %s" % (k,))
            for i,v in enumerate(self.pipe.execute()):
                # logging.error("  FOUND: %s\t= %s" % (self.these_ports[i],v))
                if v:
                    uplinks[self.these_ports[i]] = v
        except:
            pass
    
        # logging.error("UPLINKS: %s" % (uplinks.keys(),))
        if len( self.these_macs ) or len( self.these_arps ):
            epoch = datetime_to_epoch(time)

            # logging.error("ARPS: %s" % (self.these_arps,))

            # try to dedup output; format_message returns a hash of the dict
            dups = {}
            # new mac addresesses seen
            for is_new,d in self.zstore_add( self.mac_key, epoch, self.these_macs, "${mac_address}" ):
                if is_new:
                    logging.info( 'new mac: %s' % (d,))
                # logging.info("     -m %s" % ( m, ) )
                h, m = self.format_message( epoch, 'mac', d, uplinks=uplinks )
                if not h in dups:
                    yield m
                else:
                    logging.debug("DUP MAC! c=%s,\td=%s" % (m['context'],m['data']))
                dups[h] = True
                
            # new arps
            dups = {}
            for is_new,d in self.zstore_add( self.arp_key, epoch, self.these_arps, "${mac_address}@${ip_address}" ):
                if is_new:
                    logging.info( 'new arp: %s' % (d,))
                h, m = self.format_message( epoch, 'arp', d, uplinks=uplinks )
                if not h in dups:
                    # logging.warn("     -a %s" % ( m, ) )
                    yield m
                else:
                    logging.debug("DUP ARP! c=%s,\td=%s" % (m['context'],m['data']))
                dups[h] = True

        # remove old entries
        old = int(datetime_to_epoch(time - self.expire_at))
        for i in self.zstore_expire( self.mac_key, old ):
            logging.info("expired mac: %s" % (i,))
        for i in self.zstore_expire( self.arp_key, old ):
            logging.info("expired arp: %s" % (i,))

        # logging.error("END")

    def save( self, time, meta, context, data, time_delta=None ):
        # logging.info("%s -> %s: %s" % (meta,context,data))
        combined = dict( context.items() + data.items() )
        if 'mac_address' in combined and combined['mac_address']:
            self.these_macs.append( combined )
            if 'ip_address' in combined and combined['ip_address']:
                self.these_arps.append( combined )
                
        # setup a bulk get for these physical ports to check if they are uplinks or no
        # remove subinterfaces
        try:
            port = self.determine_physical_interface( combined['physical_port'] )
            key = '%s:%s' % ( combined['device'].lower(), port) 
            if not key in self.these_ports:
                self.these_ports.append( key ) 
        except:
            pass