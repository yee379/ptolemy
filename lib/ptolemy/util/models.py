from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import multiprocessing
from subprocess import Popen, PIPE, STDOUT
from os import getpid

from time import sleep
from datetime import datetime
from random import randint
from uuid import uuid1 as uuid

import sys
import traceback
from optparse import make_option

# daemon stuff
import signal
import daemon
from lockfile import FileLock

import logging

from ptolemy_py.util.queues import PtolemyQueueFactory


class Process( multiprocessing.Process ):
    """
    abstraction of a process to have a work queue and results queue
    """

    work_queue = None
    results_queue = None
    working = False
    max_tasks = 0
    done_tasks = 0
    
    def __init__( self, work_queue=None, results_queue=None, max_tasks=0 ):

        self.work_queue = work_queue
        self.results_queue = results_queue

        self.working = False
        self.max_tasks = max_tasks

        multiprocessing.Process.__init__(self)

    def do( self, data, envelope ):
        # do something, and report back
        # logging.debug("do'ing")
        res = self.process( data )
        if not envelope == None:
            envelope.ack()
        # logging.info("RESULTS: " + str(self.results_queue))
        if not self.results_queue == None:
            self.report( res )
        self.done_tasks = self.done_tasks + 1
        # logging.debug('done ' + str(self.done_tasks) + ' of ' + str(self.max_tasks))
        if self.max_tasks > 0 and self.done_tasks > self.max_tasks:
            self.terminate()

    def process( self, item ):
        t = randint(0,10)
        logging.info("process: " + str(item) + ", sleeping " + str(t))
        time.sleep( t )
        return { 'result': 'slept ' + str(t) }

    def report( self, results ):
        # make into json or something
        # logging.info("do store: " + str(results))
        if not self.results_queue == None:
            self.results_queue.put( results )

    def run( self ):
        """
        this worker will listen on the work queue and 'do' forever
        """
        self.working = True
        task_number = 0
        # worker will block, will callback to do
        self.work_queue.consume( self.do )
    
    def terminate( self ):
        logging.debug('terminating ' + str(self.name) )
        super( Process, self ).terminate()
        
    def qsize(self):
        logging.debug('asking work queue size')
        return self.work_queue.qsize()

class LoggerAg( object ):
    logging_queue = None
    def __init__(self, logging_queue=None):
        self.queue = logging_queue
    
    def _message( self, loglevel, msg, extra ):
        m = { 'loglevel': loglevel, 'message': msg }
        for s in [ 'task_id', 'user', 'action', 'status' ]:
            if s in extra:
                m[s] = extra[s]
        return m
        
    def _routing_key( self, msg ):
        k = '#'
        if 'task_id' in msg:
            k = 'task_id.' + msg['task_id']
        # logging.error("KEY: " + str(k))
        return k
    
    def debug(self, msg, extra={} ):
        logging.debug(msg)
        if not self.queue == None:
            self.queue.put( self._message( 'debug', msg, extra ), key=self._routing_key(extra) )

    def info(self, msg, extra={} ):
        logging.info(msg)
        if not self.queue == None:
            self.queue.put( self._message( 'info', msg, extra ), key=self._routing_key(extra) )

    def warn(self, msg, extra={} ):
        logging.warn(msg)
        if not self.queue == None:
            self.queue.put( self._message( 'warn', msg, extra ), key=self._routing_key(extra) )

    def error(self, msg, extra={} ):
        logging.error(msg)
        if not self.queue == None:
            self.queue.put( self._message( 'error', msg, extra ), key=self._routing_key(extra) )


class Worker( Process ):
    """
    worker thread that also adds information on statistics and logging
    """
    action = 'Doing'
    logging_queue = None
    
    def __init__( self, work_queue=None, results_queue=None, logging_queue=None, max_tasks=0 ):
        super( Worker, self ).__init__( work_queue=work_queue, results_queue=results_queue, max_tasks=max_tasks )
        self.logger = LoggerAg( logging_queue=logging_queue )
    
    def _process( self, msg, stats={} ):
        raise NotImplementedError, '_process() to be implemented by subclass'
    
    def process( self, msg ):
        
        # check the input
        logging.warn("processing data: " + str(msg) )
        try:
            i = iter( msg )
        except TypeError, e:
            raise TypeError, 'unknown message type recieved'
        
        # add action
        msg['action'] = self.action
        # msg['status'] = 0
                    
        # time it just incase
        t = datetime.now()
        stats = {}
        item = msg['device'] + ' for ' + msg['spec']
        if 'user' in msg:
            item = 'user ' + msg['user'] + '; ' + item
        logging.info( self.action + " " + item, msg )

        # do something!
        msg = self._process( msg, stats=stats )
        t = datetime.now() - t
        stats['total_time'] = "%.6f" % float( (float(t.microseconds) + float(t.seconds*1000000))/1000000 )

        # format output
        s = self.action.lower() + " " + item
        e = "Error " + s  + ": "
        # logging.error("MSG: " + str(msg))
        if 'error' in msg:
            if len(msg['error']):
                x = e + ', '.join(msg['error']) + " (" + self._printStatistics(stats) + ")"
                self.logger.error( x, msg )
        elif 'result' in msg and not 'result' == None:
            if not msg['result'] == None:
                msg['status'] = msg['status'] + 1
                x = "Finished " + s + " (" + self._printStatistics(stats) + ")"
                self.logger.info( x, msg )
        else:
            x = e + ' Null output' 
            self.logger.error( x, msg )

        return msg

    def _printStatistics( self, s ):
        out = []
        for i in s:
            if i.endswith( '_time' ):
                j = i.replace('_time','')
                # logging.info(str(i) + ", " + str(j) + ", " + str(s))
                out.append( "%s %.2fsec" % ( str(j), float(s[i]) ) )
        return ', '.join(out)

    def _reportKey( self, msg ):
        parts = []
        for n in ( 'group', 'spec', 'user', 'task_id' ): #'device',
            if n in msg:
                this = msg[n]
                # if n == 'device': 
                #     device_parts = reversed( msg['device'].split('.'))
                #     this = ".".join(device_parts)
                parts.append( n + '.' + this )
        k = '.' + '.'.join(parts) + '.'
        # logging.info("  routing key: " + k )
        return k

        parts = reversed( msg['device'].split('.'))
        routing_key = msg['group'] + '.' + msg['spec'] + '.' + ".".join(parts)
        return str(routing_key)
    
    def _parseStatistics( self, line, d={} ):
        for f in line.split(r' '):
            # logging.info("got " + str(f) )
            g = f.split('=')
            if len(g) == 2:
                # logging.info("  parsed " + str(g))
                d[g[0]] = g[1]
        return d


class CommandLineWorker( Worker ):
    
    def _process(self, msg, stats={} ):
        raise NotImplementedError, '_process() to be subclassed'
        return self._execute( cmd, msg )
    
    def _execute( self, cmd, msg, stats={}, stdin=None ):
        # logging.info("CMD: " + str(cmd) )
        p = Popen( cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE )

        out, err = p.communicate( stdin )
        p.wait()

        # parse output
        # logging.warn("STDOUT: " + str(out) )
        msg['result'] = self._stdoutFilter( out )
        if msg['result'] == '':
            del msg['result']
        
        # logging.warn("STDERR: " + str(err) )
        for e in err.split("\n"):
            e = e.rstrip()
            if e.startswith( 'Statistics: '):
                msg['statistics'] = self._parseStatistics( e, stats )
            else:
                if not e == '':
                    if not 'error' in msg or msg['error'] == None:
                        msg['error'] = []
                    msg['error'].append( e )
        return msg
    
    def _stdoutFilter( self, i ):
        return i
        
class Manager( object ):
    """
    dyanamically handles a pool of Process objects based on the work queue size
    is itself a multiprocessing.Process object
    """
    queue_factory = None
    work_queue = None
    results_queue = None
    logging_queue = None

    worker = None
    workers = []
    max_tasks_per_child = 0
    min_workers = 0
    max_workers = 0

    working = False
    monitor_period = 1
    new_child_at = 5

    def __init__( self, 
            pool=None, key='#', auto_delete_queue=True,
            max_tasks_per_child=0, min_children=0, max_children=0,
            monitor_period=1, new_child_at=5 ):

        # work_queue=None, results_queue=None,
        # self.work_queue = work_queue
        # self.results_queue = results_queue
        
        # routing key for queue that workers should be listening on
        self.pool = pool
        self.key = key
        self.auto_delete_queue = auto_delete_queue
        
        self.max_tasks_per_child = max_tasks_per_child
        self.min_workers = min_children
        self.max_workers = max_children
        
        self.monitor_period = monitor_period
        self.new_child_at = new_child_at
        
        # self.queue_factory = queue_factory
        
        # signal.signal( signal.SIGINT, self.terminate_workers )
        # signal.signal( signal.SIGHUP, self.restart_workers )
        
    
    def setup( self, queue_factory ):
        self.queue_factory = queue_factory
    
    
    def start( self ):
        # TODO: do not block?
        logging.info('Starting ' + str(type(self).__name__) + ': pool=' + str(self.pool) + ", key=" + str(self.key) + ', with ' + str(self.min_workers) + ' to ' + str(self.max_workers) + ' workers')
        self.working = True
        for i in xrange(self.min_workers):
            self.create_worker()

        while self.working:
            try:

                c = len( self.workers )
                
                # logging.debug("workers=" + str(c) + ", sleeping " + str(self.monitor_period))
                sleep( self.monitor_period )
                
                for n, p in enumerate( self.workers ):
                    if not p.is_alive():
                        logging.warn( 'reaping worker ' + str(p) + ', n=' + str(n) )
                        p.terminate()
                        self.workers.pop( n )
                
                # too few workers, create more
                if not self.min_workers == 0:                    
                    needed_workers = self.min_workers - c
                    if self.max_workers > 0 and c > self.max_workers: needed_workers = 0
                    # logging.info("workers: " + str(c) + ", min/max=" + str(self.min_workers) + "/" + str(self.max_workers) + ", needed: " + str(needed_workers) )
                    if needed_workers > 0:
                        for i in xrange( needed_workers ):
                            # logging.info("creating new worker")
                            self.create_worker()
                # else:
                #     # create at least one worker
                #     self.init_worker()
                        
                # determine length of queue by asking random worker
                # n = randint(0,c-1)
                # logging.debug("n: " + str(n))
                # q = self.workers[n].qsize()
                # logging.debug("workers: " + str(c) + ", qsize: " + str(q) )
                # # if too many, then start new child upto max_children
                # if not q == None:
                #     if q >= self.new_child_at and c < self.max_workers:
                #         self.init_worker()
                #     # if queue is zero, then terminate a random child
                #     elif q == 0:
                #         p = self.workers.pop( n )
                #         logging.debug("terminating worker " + str(p) + ", n=" + str(n))
                #         p.terminate()
                
            except Exception, e:
                logging.error('error ' + str(type(e)) + ":" + str(e))

    def terminate(self):
        self.terminate_workers()
        return

    def create_worker( self ):
        raise NotImplementedError, 'create_worker() to be subclassed'
        
    def terminate_workers( self ):
        for w in self.workers:
            w.terminate()

    def restart_workers( self ):
        self.terminate_workers()
        for i in xrange(self.min_workers):
            self.create_worker()
            
            
            
class Daemon( BaseCommand ):
    """
    wrapper for creating daemons out of Managers
    """
    option_list = BaseCommand.option_list + (
        make_option('-p', '--pool', dest='pool',
            help='what pool to become a member of'),
        make_option('-k', '--key', default='#', dest='key',
            help='what to listen for'),
        make_option('-w', '--workers', default=settings.WORKERS, dest='workers',
            help='how many concurrent worker threads to use'),
        make_option('-f', '--foreground', action="store_true", dest='foreground',
            help='run in the foreground (do not daemonise)'),
        make_option( '--verbose', action="store_true", dest='verbose',
            help='debug output'),

    )
    help = 'daemon class'
    args = '[--pool=STR --key=STR --workers=INT]'

    manager = None

    working_dir = None
    lock_file = None
    daemonise = False

    # def __init__(self, *args, **kwargs ):
    #     super(Daemon,self).__init__( *args, **kwargs )
    
    def terminate(self):
        self.manager.terminate()
    
    def reload( self ):
        pass
    
    def run( self, *args, **options ):
        pool = str(options.get('pool'))
        auto_delete_consumer_queue = False
        if pool == 'None':
            auto_delete_consumer_queue = True
            pool = uuid()
        key = str(options.get('key'))
        workers = int(options.get('workers'))
        self.manager = self.manager( min_children=workers, pool=pool, key=key, auto_delete_queue=auto_delete_consumer_queue )
        qf = PtolemyQueueFactory()
        if 'queue_factory' in options:
            qf = options['queue_factory']
        self.manager.setup( queue_factory=qf )
        self.manager.start()
        
    def handle(self, *args, **options):

        # daemonise?
        if options.get('foreground'): self.daemonise = False
        else: self.daemonise = True
        
        # setup logging
        v = options.get('verbose')
        try:
            if self.daemonise:
                # pid = daemon.pidlockfile.TimeoutPIDLockFile( self.lock_file, 10 )
                # print current pid
                print getpid()
                
                # get all open files for logging for daemonising
                logs = []
                for a in logging.root.handlers:
                    logs.append( a.stream )
                
                context = daemon.DaemonContext( 
                    files_preserve=logs, # hack to enable file logging
                )
                context.signal_map = {
                        signal.SIGTERM: self.terminate,
                        signal.SIGHUP: self.reload,
                    }

                with context:
                    self.run( *args, **options )
            else:
                self.run( *args, **options )
        
        except KeyboardInterrupt, e:
            logging.info('ctrl-c received')
            self.terminate()
        except:
            traceback.print_exc()

        sys.exit(0)
