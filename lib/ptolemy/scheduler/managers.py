from slac_utils.managers import WorkerManager, Supervisor

from ptolemy.queues import QueueFactory
from ptolemy.scheduler.scheduler import YAMLScheduleParser, ScheduleParser
from ptolemy.scheduler.workers import create_task, routing_key

import memcache
from socket import gethostname

from datetime import timedelta
from time import time
from slac_utils.time import sleep, now
from slac_utils.hashing import ConsistentHashRing

import logging
import traceback

class BaseScheduleSupervisor( Supervisor ):
    """
    class to periodically publish messages into defined queues
    also can listen on queue and act on messages
    """
    queue_factory = QueueFactory
    monitor_period = 1.0

    schedule_parser = ScheduleParser
    
    proc_name = 'ptolemy scheduled'

    def __init__( self, *args, **kwargs ): # auto_delete=True, 
        super( BaseScheduleSupervisor, self ).__init__( *args, **kwargs )
        self.parser = self.schedule_parser( **kwargs )
        self.running = True

    def process_work_queue( self ):
        pass
        
    def wait( self, t ):
        """
        we wait for the next scheduled test
        if we have it configured, we also determine if there is anythign in the request queue
        """
        # self.logger.debug("waiting " + str(t) );
        if t > 0:
            # even though we are sleeping, we need to check the request queue in case omething comes in
            # so if we don't have a request queue, we sleep the full amount
            if self.work_queue == None:
                sleep(t)
                # Timer( wait_time, self.dummy, () ).start()
            # otherwise, we sleep and check the queue
            else:
                self.process_work_queue()
                s = self.monitor_period if t > self.monitor_period else t
                sleep( s )
            
    def peek(self):
        t, info = self.parser.peek()
        delta = t - time()
        # self.logger.debug("peek: now=" + str(now) + ", time=" + str(t) + ", delta=" + str(delta) + ", test: " + str(info))
        return delta, info

    def next(self):
        return self.parser.next()

    def publish( self, item, user=None, task_id=None ):
        context = self.message_context( item )
        msg = create_task( self.parser, item['node'], context=context, task_id=task_id, user=user )
        rk = routing_key( msg )

        logging.info('Scheduling %s' % (context,) )
        # if self.logging_queue and task_id:
        #     self.logging_queue.put( msg, key=task_id )

        # actually submit it!
        # logging.debug("%s -> %s" % (rk,msg,))
        # TODO: doesn't work if we have a routing key in!
        self.results_queue.put( msg )
    

    def message_context( self, item ):
        return { 'device': item['node'], 'spec': item['spec'] }

    def process_task( self, job ):

        self.running = True

        # instantiate the schedule
        self.parser.init_schedule()
    
        # determine initial time to wait
        delta = self.monitor_period
        try:
            delta, info = self.peek()
        except:
            pass
        finally:
            self.wait( delta )

        # run forever!
        while self.running:
            # get the next test
            try:
                delta, item = self.peek()
                # logging.debug("= peek %.2f %s" % (delta,item))
                if delta <= 0:
                    # run test, remove from queue and readd it with next time
                    # logging.info("- next %.4f %s" % (delta,item))
                    t, item = self.next()
                    # logging.info("+ next %s %s" % (t,item))
                    # create a message object for this
                    self.publish( item )
            except IndexError:
                logging.debug('schedule empty')
            except Exception, e:
                logging.error("%s: %s\n%s" % (type(e),e, traceback.format_exc()))
            finally:
                self.wait( delta )
                
    def reload(self, *args, **kwargs ):
        self.parser.reset_schedule()
        
    def run( self ):
        """
        this worker will listen on the work queue and '_run' forever for each task that comes in
        """
        self.done_tasks = 0
        try:
            self.setup( )
            self.working = True
            while self.working:
                logging.info( 'starting %s' % (self.__class__.__name__,) ) #+ ': pool=' + str(self.pool) + ", key=" + str(self.key) )
                try:
                    with self.work_queue:
                        with self.results_queue:
                            with self.logging_queue:
                                self.process_task( {} )
                except Exception, e:
                    logging.error('error (%s) %s: %s' %(type(e),e, traceback.format_exc() ) )
                    sleep(5)
            # self.cleanup()
            return
        except KeyboardInterrupt, e:
            logging.info("terminating...")
        
        except IOError, e:
            logging.error("Connection error %s: %s" % (self.work_queue,e,))
        
        except Exception, e:
            logging.error( "CONSUME ERROR with %s: (%s) %s\n%s" % (self.name, type(e), e, traceback.format_exc()) )



class DistributedScheduleManager( WorkerManager ):
    """
    a distributed supervisor that relies on memcached to determine states of other distributed supervisors
    each registered supervisor will connect to a work queue as well as their own specific work queue (routed)
    
    each loads own copy of what it thinks is the schedule locally
    based on timestamps on the files, the latest is placed into memcache for the others to pick up
    periodic polls and sighups will reassign the schedule
    
    each scheduler downloads the schedule periodically and will run a full schedule
    however, it will only publish a request to poll if the specific task matches its consistent hash ring
    regular checks on the status of the other schedulers through memcache and the consistent key ring will determine if a scheduler should publish or let someone else do it
    """
    monitor_period = 1.0

    schedule_parser = ScheduleParser
    
    proc_name = 'ptolemy scheduled'
    memcache_state_key = 'ptolemy.distributed.scheduler'
    memcache = None

    queue_factory = QueueFactory
    results_queue_func = 'poll'
    
    host_id = None
    last_update_time = None
    ring = None
    dead_time = 20;
    
    def __init__( self, *args, **kwargs ):
        
        super( DistributedScheduleManager, self ).__init__( *args, **kwargs )

        # distributd schedule
        self.memcache = memcache.Client( kwargs['memcache_pool'], debug=0 )
        self.host_id = gethostname()
        self.ring = ConsistentHashRing([])
        
        if len(kwargs['nodes']) == 0 or kwargs['snmp'] == None or kwargs['schedule'] == None:
            raise SyntaxError, 'no configuration files defined'
        self.parser = YAMLScheduleParser( node_confs=kwargs['nodes'], snmp_conf=kwargs['snmp'], schedule_conf=kwargs['schedule'] )
        self.running = True
        
    def reload(self):
        self.parser.reset_schedule()
        
    def peek(self):
        t, info = self.parser.peek()
        delta = t - time()
        # self.logger.debug("peek: now=" + str(now) + ", time=" + str(t) + ", delta=" + str(delta) + ", test: " + str(info))
        return delta, info

    def next(self):
        return self.parser.next()
    
    def update_ring( self, state_key='ptolemy.scheduled.state', period=timedelta(seconds=10) ):
        # only bother every period seconds
        n = now()
        # update now!
        if self.last_update_time == None:
            self.last_update_time = n - period
        
        if self.last_update_time <= n - period:
            # logging.info("updating ring")
            # get status of all scheduled's        
            states = self.memcache.get( state_key )
            logging.info("ring states: %s" % (states,) )
            if states == None:
                states = {}
            # assume one per host
            t = now()
            states[self.host_id] = t
            # buld ring
            for i in states:
                if t - states[i] <= timedelta( seconds=self.dead_time ):
                    if not i in self.ring.nodes:
                        logging.info(" adding %s to ring" % (i,))
                        self.ring.add_node( i )
                else:
                    self.ring.remove_node( i )
                    logging.info(" removing %s from ring" % (i,))
                    # do nott delete from state: others won't know about and so won't remove from ring
                    # del states[i]
            # update
            self.memcache.set( state_key, states )
            self.last_update_time = n
                
    def wait( self, t ):
        """
        we wait for the next scheduled test
        if we have it configured, we also determine if there is anything in the request queue
        """
        self.update_ring()
        if t > 0:
            sleep(t)
    
    def update_schedule( self, key='ptolemy.scheduled.schedule', period=timedelta( seconds=60 ) ):
        """
        problem: how to keep a consistent state of the parser schedule across scheduled instances?
        for now we just ignore it and always use a local schedule
        """
        self.parser.init_schedule()


    def message_context( self, item ):
        return { 'device': item['node'], 'spec': item['spec'] }

    def publish( self, item, user=None, task_id=None ):
        context = self.message_context( item )
        msg = create_task( self.parser, item['node'], context=context, task_id=task_id, user=user )
        rk = routing_key( msg )

        logging.info('Scheduling %s:%s' % (item['node'],item['spec']) )
        # if self.logging_queue and task_id:
        #     self.logging_queue.put( msg, key=task_id )

        # actually submit it!
        self.results_queue.put( msg, key=rk )

    def process_task( self, *args, **kwargs ):
        """
        the main thread is a loop around the schedule, peeking and sleeping until the next task to be schedule
        arrives.
        periodically, we must check memcache for state changes in the global schedule and act accordingly
        """

        # setup schedule
        self.update_schedule()
        
        # setup ring
        self.update_ring()
        
        # determine initial time to wait
        delta = self.monitor_period
        try:
            delta, info = self.peek()
        except:
            pass
        finally:
            self.wait( delta )

        # run forever!
        while self.running:
            # get the next test
            try:
                delta, item = self.peek()
                # logging.debug("= peek %.2f %s" % (delta,item))
                if delta <= 0:
                    # run test, remove from queue and readd it with next time
                    # logging.info("- next %.4f %s" % (delta,item))
                    t, item = self.next()
                    h = self.ring.get_node( "%s" % item )
                    if h == self.host_id:
                        # logging.info("+ publish (%s) %s %s" % (h,t,item))
                        self.publish( item )
            except IndexError:
                logging.debug('schedule empty')
                raise Exception, 'empty schedule'
            except Exception, e:
                logging.error("%s: %s\n%s" % (type(e),e, traceback.format_exc()))
                raise e
            finally:
                self.wait( delta )



class OnDemandScheduleManager( DistributedScheduleManager ):
    """
    just put the job into the queue
    """
    def start( self, *args, **kwargs ):
        self.setup( **kwargs )
        try:
            with self.work_queue:
                with self.results_queue:
                    with self.logging_queue:
                        self.loop_start( **kwargs )
                        self.process_task( *args, **kwargs )
                        self.loop_end( **kwargs )
        except Exception, e:
                logging.error('error (%s) %s: %s' %(type(e),e, traceback.format_exc() ) )


    def process_task( self, *args, **kwargs ):
        item = {
            'node': kwargs['node'],
            'spec': kwargs['spec'],
        }
        logging.error("schedule %s" % (item ))
        
        n = self.parser.getNode( item['node'] )
        if n and item['spec'] in n['schedule']:
            # logging.error("NODE: %s" % (n,))
            self.publish( item )
        else:
            logging.error("not registered")
            

    def queue( self, node, spec ):
        self.start( node=node, spec=spec )