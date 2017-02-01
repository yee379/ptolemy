from slac_utils.managers import Worker, Manager, FanOutManager, Supervisor, TASK_RECEIVED, TASK_PROCESSING, TASK_COMPLETE, TASK_WARNING, TASK_ERRORED, TASK_INFO

from ptolemy.queues import QueueFactory
from ptolemy.poller.workers import Poller as PollerWorker, TimedOut
from slac_utils.util import read_file_contents

# from slac_utils.statistics_feeder import CarbonFeeder

try:
    from setproctitle import setproctitle
except:
    def setproctitle(blah):
        pass
        
import collections
from copy import copy
from datetime import datetime, timedelta

# from fcntl import flock, LOCK_EX, LOCK_UN, LOCK_NB, LOCK_SH
from re import match

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
    
try:
    import memcache
except:
    pass
    
from random import uniform

import logging
import traceback


def driver_key( job ):
    return "%s:%s" % (job.context['device'],job.context['spec'])

def memcache_key( driver_key ):
    return 'ptolemy:polld:' + str(driver_key)
    

def initial_state( ):
    # cache struct for test state
    return {
        'recvd': None,
        'started': None,
        'complete': None,
        'next_probe': None,
        'last_failed': None,
        'last_successful_driver': None, # base driver name
        'force_driver': None
    }

class PollerSupervisor( Supervisor ):
    """
    The Poller Supervisor does a couple of things:
    1) analyses incoming poll requests to check for validity and deconstruct the request to minimise the work the workers have to do
    2) keeps a driver cache and does lookups for which drivers suit the request
    as this is a supervisor class, we monitor for jobs in our work_queue, and spit out valid jobs
    to our results_queue. polling workers (managed by the parent manager instance) feed from our 
    results_queue. logging messages for updates etc. from the workers come back into our work_queue
    marked as a 'log' rather than a 'task'.
    To synchronise between supervisors, we use memcached to store the states of each test using a simple dict:
    {
        'recvd':    datetime, # when the poll request was recvd
        'start':    datetime, # start-time of the poll request
        'complete':     datetime, # last timestamp of when the request was completed
        'next_probe':   datetime, # timestamp of when it should next be probed
        'last_failed':  datetime, # timestamp of when it last failed polling
        'last_successful_driver':   str, # last known good driver (to synchronise drivers)
    }
    """

    action = 'polling'
    # prefetch_tasks = 1000 # TODO: is this causing memcache items not to be updated in time?

    options_cache = None

    driver_dir = '/opt/ptolemy/etc/ptolemy/polld/drivers/'

    # priority list of drivers keyed by spec
    driver_priorities = None
    forced_drivers = None
    
    # thresholds for test reprobing and validation
    received_throttle_time = timedelta( seconds=30 )
    complete_throttle_time = timedelta( seconds=15 )
    failed_throttle_time = timedelta( seconds=3600 )
    invalid_time_multiplier = timedelta( seconds=120 )
    reprobe_period = 5400 # every 1.5h
    reprobe_spread = 0.2
    
    proc_name = 'ptolemy polld supervisor'
    
    def __init__(self,*args,**kwargs):

        super( PollerSupervisor, self ).__init__(*args,**kwargs)
        self.options_cache = {}
        
        # set driver directory
        for a in ( 'driver_dir', ):
            setattr( self, a, kwargs[a] )
        # set configuration files
        for y in ( 'driver_priorities', 'forced_drivers' ):
            logging.info("loading %s from %s" % (y,kwargs[y]))
            setattr( self, y, load( file( kwargs[y], 'r' ), Loader=Loader ) )
            # logging.error( '%s: %s ' % (y, getattr(self,y)) )
        # logging.warn("FORCED DRIVERS: %s" % (self.forced_drivers,))
            
        # start mc
        self.init_state( **kwargs )
        
        for i in ( 'received_throttle_time', 'complete_throttle_time', 'failed_throttle_time' ):
            if i in kwargs:
                setattr( self, i, timedelta( seconds=float(kwargs[i]) ) )
                # logging.error("SUP KWARGS: %s -> %s" % (i, getattr(self, i)))
        for i in ( 'invalid_time_multiplier', 'reprobe_period', 'reprobe_spread' ):
            if i in kwargs:
                setattr( self, i, float(kwargs[i]) )
                # logging.error("SUP KWARGS: %s -> %s" % (i, getattr(self, i)))

    def process_invalid_task(self, job, exception):
        logging.warn( "%s" % (exception,) ) # job) )

    def _get_driver_path( self, spec, driver ):
        return str(self.driver_dir) + str(spec) + '/' + str(driver)

    def _strip_driver_path( self, driver, spec ):
        return driver.replace( self.driver_dir + spec + '/', '' )

    def init_state(self,**kwargs):
        self.memcache = memcache.Client( kwargs['memcache_pool'], debug=0 )
        # self.memcache = {}
        
    def get_state(self, k):
        K = memcache_key( k )
        return self.memcache.get( K )
        # if K in self.memcache:
        #     return self.memcache[K]
        # return None

    def commit_state(self, k, state ):
        K = memcache_key( k )
        self.memcache.set( K, state )
        # self.memcache[K] = state

    def validate_task(self,job):
        """
        determine the driver to use for this job, add to job['driver']
        if we don't know, then we supply a list of possible drivers that the worker should try in order job['probe_with_drivers']
        """
        
        # logging.info('JOB %s' % (job,))
        if not 'device' in job.context or not 'spec' in job.context:
            raise Exception, 'invalid job'

        # logging.info('%s recvd' % (k,))
        now = datetime.now()

        # deconstruct passwords etc.
        if isinstance( job.data, dict ):
            for i,v in job.data.iteritems():
                if str(v).startswith('file'):
                    if v in self.options_cache:
                        v = self.options_cache[v]
                    else:
                        m = match( r'^file://(?P<filepath>.*)$', str(v) )
                        if m:
                            f = m.group( 'filepath' )
                            v = read_file_contents( f )
                            self.options_cache[v] = v
                job.data[i] = v

        # local keys for lookup
        k = driver_key( job )

        # check to see if we have something in our cache
        state = self.get_state( k )
        reprobe = False
        
        # don't prevent polls by too frequent requests etc. if False
        update_recvd = True

        if not state:
            state = initial_state( )
                    
        try:
            
            # do checks to make sure we're good, throw exceptions for invalid tests
            # 1e) if we've always had problems with this test, wait until the next reprobe time
            if not state['complete'] == None and state['last_successful_driver'] == None:
                # if it's past a reprobe point, then allow to test
                # logging.info("MAN %s - %s > %s = %s" % (k,state['next_probe'],now, state['next_probe']>now))
                if 'next_probe' in state:
                    if not state['next_probe'] == None:
                        if state['next_probe'] > now:
                            raise Exception, 'skipping %s cannot be polled effectively' % (k)                
            # 1c) if the last 'complete' time is not that long ago
            if not state['complete'] == None:
                if now - state['complete'] < self.complete_throttle_time:
                    update_recvd = False
                    raise Exception, 'skipping %s completed less than %s ago (%s)' % (k,self.complete_throttle_time, now - state['complete'])        
                
            # 1a) if we recvd recently, we ignore this test
            if not state['recvd'] == None and ( now - state['recvd'] < self.received_throttle_time ):
                update_recvd = False
                raise Exception, 'skipping %s requested too frequently (last %s)' % (k,now-state['recvd'])

            # 1b) if test is still active, ie we have a 'start' time (we must ensure that the 'start' is nullified on completing)
            if not state['started'] == None:

                t = 60
                if 'frequency' in job._meta:
                    t = job._meta['frequency'] * self.invalid_time_multiplier

                if now - state['started'] > timedelta( seconds=t ):
                    logging.warn("previous %s test invalidated (%s), freq %s" % (k,str(state['started']).split('.')[0],t))
                    state['started'] = None

                if state['started']:
                    # raise Exception, 'skipping %s: being polled (started %s ago)' % (k, str(now - state['started']).split('.')[0] )
                    logging.warn( 'skipping %s being polled (started %s ago)' % (k, str(now - state['started']).split('.')[0] ) )

        except Exception, e:
            
            raise e
        
        finally:

            # don't forget to update the recv time
            if update_recvd:
                state['recvd'] = now

            # determine if we need to reprobe now, and schedule the next
            if ( 'next_probe' in state and ( state['next_probe'] == None or state['next_probe'] < now ) ) or not 'next_probe' in state:
                reprobe = True
                d = self.reprobe_spread*self.reprobe_period
                s = self.reprobe_period + uniform( -1*d, d )
                state['next_probe'] = now + timedelta( seconds=s )
                # logging.warn("NEXT %s %s (now %s +- %s = %s)" % (k,state['next_probe'],now,d,s))

            # set the forced driver from mem
            if k in self.forced_drivers:
                state['force_driver'] = self.forced_drivers[k]

            # update our cache
            self.commit_state( k, state )

        # queue the test!

        # check to make sure that we are ok with reprobe
        if 'last_successful_driver' in state and state['last_successful_driver'] == None:
            reprobe = True
        if k in self.forced_drivers or ( 'force_driver' in state and state['force_driver'] ):
            reprobe = False
        
        # deal with reprobing but providing 'probe_with_drivers' instead of 'driver' in the job
        # logging.error("HERE: %s (%s) = %s" % (k, reprobe, k in self.forced_drivers ))

        if reprobe:

            if job.context['spec'] in self.driver_priorities:
                job.data['probe_with_drivers'] = []
                for d in self.driver_priorities[job.context['spec']]:
                    job.data['probe_with_drivers'].append( self._get_driver_path( job.context['spec'], d ) )
                logging.info( "probing %s using %s" % (k,[ d.split('/')[-1] for d in job.data['probe_with_drivers'] ]) )
                return job

            else:
                raise Exception, 'spec %s has not been registered' % (job.content['spec'])

        else:
            
            driver = state['last_successful_driver']
            # override with forced driver if exists
            if 'force_driver' in state and state['force_driver']:
                driver = state['force_driver']
                
            job.data['driver'] = self._get_driver_path( job.context['spec'], driver )
            # logging.info( "manager %s using %s %s" % (k,job.data['driver'].split('/')[-1],state) )
            return job
            
        raise Exception, '%s internal logic error' % (k,)


    def process_log(self,job):
        """ need to monitor for probe attempts and remove the entry if successful """

        now = datetime.now()

        # call parent to unlock
        super(PollerSupervisor,self).process_log(job)
        
        # keep a global lock on the job to prevent hammering the system
        k = driver_key( job )
        
        if not 'state' in job._meta:
            raise Exception, 'invalid log entry: %s' % (job)

        # retrieve memcache item
        state = self.get_state( k )
        if not state:
            logging.error('%s did not exist in state cache' % (k,))
            state = initial_state( now )

        try:

            s = job._meta['state']

            # 1) recvd notice that the test has been recvd and is processing
            if s in ( TASK_RECEIVED, TASK_PROCESSING ):

                if s in ( TASK_PROCESSING, ):
                    state['started'] = now
                ago = None
                m = ''
                if state['recvd']:
                    ago = state['started'] - state['recvd']
                    if ago > timedelta( seconds=60 ):
                        m = ', delayed %s' % (str(ago).split('.')[0],)
                logging.info('%s %s%s' % (self.action,k,m))
            
            # 2) recvd notice that the test has been completed 
            elif s in ( TASK_COMPLETE, TASK_WARNING, TASK_ERRORED ):
                
                if s in ( TASK_COMPLETE, TASK_ERRORED ):
                    state['started'] = None
                    state['complete'] = now

                for d in job.data:
                    
                    if d == 'no suitable driver found':
                        state['last_failed'] = now
                        state['last_successful_driver'] = None
                    elif d == 'timed out':
                        state['last_timed_out'] = now
                    
                    if s == TASK_COMPLETE:
                        logging.info("%s %s %s" % (self.action,k,d))
                    elif s == TASK_WARNING:
                        logging.warn("%s %s %s" % (self.action,k,d))
                    elif s == TASK_ERRORED:
                        state['last_failed'] = now
                        logging.error("%s %s %s" % (self.action,k,d))
                    
            elif s in ( TASK_INFO, ):
                report = False
                for d in job.data:
                    m = match( r'success with driver (?P<driver>.*)$', d )
                    if m:
                        driver = m.group( 'driver' )
                        base_driver = self._strip_driver_path( driver, job.context['spec'] )
                        state['last_successful_driver'] = base_driver
                    else:
                        logging.warn("!! %s %s" % (k,job['message']) )

            # hmmm
            else:
                m =  "unknown state %s" % (job,)
                logging.error( m )
                raise Exception, m

        except Exception,e:
            
            # logging.error("LOG: error %s" % (e,))
            raise e
            
        finally:
            # commit our updates for this state - dunno why its not always synchronous...
            self.commit_state( k, state )

        # if 'stack_trace' in job['_meta'] and job['_meta']['stack_trace']:
        #     t = '\n%s' % (job['_meta']['stack_trace'],)
        
        # update statistics
        # self.process_stats(job)

        return

    def statistics_key( self, job ):
        a = []
        for i in ( 'spec', 'device' ):
            if i in job.context:
                v = job.context[i]
                if i == 'device':
                    v = '.'.join( reversed( v.split('.') ) )
                a.append( v )
        return self.stats_preamble + '.' + '.'.join(a)


class PollManager( FanOutManager ):
    worker = PollerWorker
    supervisor = PollerSupervisor
    queue_factory = QueueFactory
    
    work_queue_func = 'poll'
    supervisor_queue_func = 'supervised_poll'
    results_queue_func = 'store'
    logging_queue_func = 'poll' # to give to supervisor

    # kwargs for supervisor creation
    min_supervisors = 2
    supervisor_kwargs = [ 'driver_dir', 'driver_priorities', 'forced_drivers', 'memcache_pool', 'received_throttle_time', 'complete_throttle_time', 'failed_throttle_time', 'invalid_time_multiplier', 'reprobe_period', 'reprobe_spread' ]
    # max_tasks_per_supervisor = 500
    
    proc_name = 'ptolemy polld manager'
    max_tasks_per_worker = 1024

    worker_kwargs = [ 'netconfig_config', ]
