from slac_utils.managers import FanOutManager, Supervisor
from slac_utils.statistics_feeder import CarbonFeeder, MultiCarbonFeeder
from slac_utils.command import ManagerDaemon, CommandDaemon

from slac_utils.time import utcfromtimestamp, sleep
from slac_utils.hashing import ConsistentHashRing

# from slac_utils.logger import init_loggers

from slac_utils.messages import Message
from ptolemy.queues import QueueFactory
from ptolemy.storage.feeders import Feeder
from ptolemy.storage.commands import StorageCommand
from slac_utils.command import DefaultList
try:
    from setproctitle import setproctitle 
except:
    def setproctitle(blah):
        pass
        
import logging
from pprint import pformat
import traceback

import gc

def get_carbon_key( meta, context, key_prepend='' ):
    if 'carbon_key' in meta:
        return meta['carbon_key']
    # remap device to reverse notation
    device = ".".join( reversed( context['device'].split('.')) )
    # append other context items
    context_keys = []
    for k in sorted(context.keys()):
        if not k in ( 'device', ):
            context_keys.append( "%s" % (context[k],) )
    # key
    carbon_key = "%s%s.%s.%s.%s" % (key_prepend, device, meta['spec'], meta['group'], '.'.join(context_keys) )
    # logging.error("-carbon %s" % (carbon_key,))
    return carbon_key.replace('/','.')

class CarbonStorer( Feeder ):
    
    agent = 'carbon'    
    key_prepend = '.'

    feeder = None    

    proc_name = 'ptolemy stored carbon'

    timestamp_to_datetime = False

    # prevent memory management
    memory_multiply_threshold = None

    def setup(self,**kwargs):
        super( CarbonStorer, self).setup(**kwargs) 
        if 'key_prepend' in kwargs:
            self.key_prepend = kwargs['key_prepend']
        # logging.error("STORE: %s (%s:%s)" % (kwargs,self.host,self.port))
        if not 'connect' in kwargs:
            kwargs['connect'] = True
        if not kwargs['connect'] == False:
            self.feeder = CarbonFeeder( host=self.host, port=self.port )
            self.proc_name = "%s %s:%s" % (self.proc_name, self.host, self.port)
        
    def __exit__(self,*args,**kwargs):
        if self.feeder:
            self.feeder.__exit__(*args,**kwargs)
    
    def get_key( self, meta, context ):
        return get_carbon_key( meta, context, key_prepend=self.key_prepend )
    
    def save( self, time, meta, context, data, time_delta=None ):
        carbon_key = self.get_key( meta, context )
        # logging.debug("= %s" % (carbon_key,))
        try:
            if self.feeder:
                # logging.debug("> %s:%s\t %s\t%s\t%s" % (self.host,self.port, time, carbon_key, data))
                self.feeder.send( time, carbon_key, data )
            # sys.stdout.write('i')
        except Exception,e:
            logging.error("Error: could not send " + str(e))
        return


class MultiCarbonStorer( CarbonStorer ):
    """
    given a array of the carbon instances, will use consistent hashing to determine where to send it
    """
    agent = 'multicarbon'    
    proc_name = 'ptolemy stored multicarbon'

    def setup(self,**kwargs):
        super( CarbonStorer, self).setup(**kwargs) 
        self.feeder = MultiCarbonFeeder( instances=self.instances )


class MultiCarbonSupervisor( CarbonStorer, Supervisor ):
    """
    A supervisor that calculates the appropriate hash for each type of message that comes in
    this hash is set as the routing key to find the appropriate worker
    """

    action = 'storing'
    key_prepend = 'ptolemy.'
    ring = None

    proc_name = 'ptolemy stored carbon supervisor'

    def setup( self, **kwargs):
        # logging.warn("KWARGS: %s" % (kwargs,))
        super( MultiCarbonSupervisor, self).setup( connect=False, **kwargs )
        self.ring = ConsistentHashRing([])
        self.instance_ports = {}
        self.port_offset = int(kwargs['carbon_port_offset']) if 'carbon_port_offset' in kwargs else 0
        for i in kwargs['carbon_instances']:
            # logging.error("I: %s" % (i,))
            s,p,n = i.split(':')
            self.add_instance( s,p,n )
        # logging.info("finished setup")

    def add_instance(self,server,port,instance):
        if (server, instance) in self.instance_ports:
          raise Exception("destination instance (%s, %s) already configured" % (server, instance))
        self.instance_ports[ (server, instance) ] = str(int(port) + self.port_offset)
        # logging.error("SERVER %s:%s %s" % (server,int(port)+self.port_offset,instance))
        self.ring.add_node( (server, instance) )

    def get_hash_key(self,key):
        (s, i) = self.ring.get_node(key)
        p = self.instance_ports[ (s, i) ]
        return ':'.join( (s, p, i) )

    def process_task( self, this, stats={}, time_delta=None ):
        """
        we need to examine each entry and construct the full hash key for each metric
        in 'this'. we then have to construct a new Message to send to the correct
        carbon worker (using the key in [_meta][key])
        we try to limit the number of messages sent by grouping them first before sending to the worker
        """
        this_context = this.context.copy()
        # logging.info("PROCESS_TASK %s" % this)
        messages = {} # keyed by worker name
        gc.disable()
        for t,m,c,item in super( MultiCarbonSupervisor, self ).process_task( this, stats, time_delta ):
            # logging.debug(" > t: %s\tm: %s\tc: %s\tdata: %s" % (t,m,c,item) )
            for k,v in item.iteritems():
                meta = m.copy()
                context = c.copy()
                key = self.get_key( meta,context ) + '.' + k
                h = self.get_hash_key( key )
                # logging.debug("  %s \t-> %s" % (key,h,))
                if not h in messages:
                    messages[h] = Message(
                        meta=m,
                        context=this_context,
                        data=[],
                    )
                    messages[h]['timestamp'] = t
                # add this data to the message
                partial = {}
                partial[k] = v
                for x in m['key_name']:
                    if x in context:
                        partial[x] = context[x]
                messages[h]['data'].append(partial)

        gc.enable()
        for h in messages:
            # logging.warn("%s sending %s\t%s" % (h, len(messages[h]['data']), messages[h]['data'] ) )
            messages[h]._meta['type'] = 'task'
            messages[h].type = 'task'

            # dont' forget to reset the meta.key to point to relevant consistent hashed carbon worker 
            a = h.split(':')
            messages[h]._meta['key'] = "%s:%s:%s" % (a[0],int(a[1])-self.port_offset,a[2])

            # logging.debug("hashed %s\tto %s" % (messages[h]._meta['key'], h) )
            yield messages[h]
        # sys.stdout.write('u')
        return 
            
    def _process_task( self, time, meta, context, item, time_delta=None ):
        # process single datum
        if not isinstance( item, dict ):
            raise SyntaxError, 'dict required'
        # look for key names in the data
        for k in meta['key_name']:
            if k in item:
                context[k] = item[k]
                del item[k]
        return time, meta, context, item



class MultiCarbonManager( FanOutManager ):
    """
    spawns of supervisor(s) and workers to handle messages destined for carbon/graphite storage.
    each worker is assigned a specific hash key to listen on messages from. it is up to the supervisors
    to determine the appropriate hash key (and hence queue) to send it to the appropriate worker
    """
    
    worker = CarbonStorer
    supervisor = MultiCarbonSupervisor
    queue_factory = QueueFactory
    
    work_queue_func = 'store'
    supervisor_queue_func = 'supervised_store'
    results_queue_func = None
    logging_queue_func = None
    
    supervisor_kwargs = [ 'carbon_instances', 'carbon_port_offset' ]
    min_supervisors = 6
    workers_per_shard = 1
    
    proc_name = 'ptolemy stored carbon manager'

    def start( self, *args, **options ):

        # use hash for workers
        self.workers = {} # key'd by carbon_instance, then an array upto workers_per_shard
        options = dict( self.kwargs.items() + options.items() )
        self.setup( **options )

        logging.info( 'Starting %s: pool=%s, keys=%s, with %s to %s workers' % (self.__class__.__name__, self.pool, self.keys, self.min_workers, self.max_workers) )

        for i in options['carbon_instances']:
            self.workers[i] = []
            for n in xrange(self.workers_per_shard):
                self.workers[i].append( None )

        self.working = True
        while self.working:
                        
            try:
                
                self.loop_start( **options )
                for i in options['carbon_instances']:
                    
                    # use c to determine how many workers we need to spin up, use bool to specify current state
                    for n in xrange(self.workers_per_shard):
                        if not self.workers[i][n] == None:
                            state = False
                            try:
                                if isinstance( self.workers[i][n], CarbonStorer ):
                                    state = self.workers[i][n].is_alive()
                            except:
                                pass
                            finally:
                                if not state:
                                    self.workers[i][n] = False

                    for n, w in enumerate(self.workers[i]):
                        # logging.error("I: %s\tN: %s W: %s"  % (i,n,str(w),))
                        if w in ( False, None ):
                            try:
                                logging.info("starting %s, member %s" % (i,n))
                                h,p,a = i.split(':')
                                opts = {
                                    'work_queue_func':  self.supervisor_queue_func,
                                    'work_exchange_name': 'multi_carbon_manager',
                                    'results_queue_func': None,
                                    'logging_queue_func': None,
                                    'max_tasks':         self.max_tasks_per_worker,
                                    'carbon_host':      h,
                                    'carbon_port':      int(p),
                                    'key_prepend':      'ptolemy.',
                                    'keys':             ( i, ),
                                    'pool':             options['pool'],
                                }
                                for k in self.worker_kwargs:
                                    opts[k] = kwargs[k]
                                opts['exchange_name'] = self.supervisor_exchange_name

                                # start the worker!
                                logging.debug("starting worker: %s"%(opts,))
                                self.workers[i][n] = self.worker( self.queue_factory_obj, **opts )
                                self.workers[i][n].start()

                                if self.proc_name:
                                    setproctitle( self.proc_name )

                            except Exception,e:
                                logging.error("Error starting worker: %s %s"%(type(e),e))

                self.loop_end( **options )
                sleep( self.monitor_period )
                
            except Exception, e:
                logging.error('Fatal Error: %s %s\n%s' % (type(e), str(e), traceback.format_exc()) )
                self.working = False

            if self.proc_name:
                setproctitle( self.proc_name )

        
        # clean up workers
        # self.cleanup()
        return
    
    
    def terminate_workers( self ):
        # q = getattr( self.queue_factory_obj, ''
        # self.supervisor_obj
        for i in self.workers:
            if self.workers[i]:
                self.workers[i].terminate()
        for i in self.workers:
            logging.info("awaiting worker termination %s"%(i,))
            if self.workers[i]:
                self.workers[i].join()
        #     # send poison pill to worker
        #     self.( END_MARKER, key=i )
        logging.info("done")

    
class Carbon( StorageCommand ):
    """
    graphite carbon storage daemon
    """
    worker = MultiCarbonManager

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        super( Carbon, cls ).create_parser( parser, settings, parents=parents )

        parser.add_argument( '-p', '--pool', help='pool name', default=settings.POOL )
        parser.add_argument( '-k', '--keys', help='key name', action='append', default=DefaultList(settings.KEYS) )

        carbon = parser.add_argument_group( 'carbon settings')
        # carbon.add_argument( '-d', '--carbon_destination', help='carbon host',   default=settings.CARBON_DESTINATION )
        carbon.add_argument( '-i', '--carbon_instances', help='carbon instances', action="append", default=settings.CARBON_INSTANCES )
        carbon.add_argument( '--carbon_key_prepend', help='carbon key prepend',   default=settings.CARBON_KEY_PREPEND )
        carbon.add_argument( '--carbon_port_offset', help='carbonlink port offset',   default=settings.CARBON_PORT_OFFSET )

    def get_storage_daemon( self, worker, **kwargs ):
        # create a storage manager with the agent class
        class Storer( CommandDaemon ):
            manager = MultiCarbonManager
            proc_name = 'ptolemy stored carbon manager'
        return Storer
    
    def pre_run( self, *args, **kwargs ):
        # init_loggers( verbose=True )
        if 'carbon_destination' in kwargs and kwargs['carbon_destination']:
            for i in xrange(0,len(kwargs['carbon_instances'])):
                kwargs['carbon_instances'][i] = kwargs['carbon_instances'][i] % (kwargs['carbon_destination'],)
        return args, kwargs
