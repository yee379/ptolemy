import argparse

from slac_utils.command import Command, ManagerDaemon
from slac_utils.managers import Manager, Worker, WorkerManager

from slac_utils.messages import Message
# from ptolemy.queues import QueueFactory, PyAmqpLibQueue, Queue as StubQueue, END_MARKER
from slac_utils.queues import QueueFactory, Queue as StubQueue, END_MARKER, PyAmqpLibQueue

try:
    from setproctitle import setproctitle
except:
    def setproctitle(blah):
        pass

import sys
import logging
import traceback

from slac_utils.time import string_to_datetime

class PerfSONARWorkerManager( WorkerManager ):

    proc_name = 'ptolemy perfsonar'

    def __init__(self,*args,**kwargs):
        # logging.error("ARGS: %s, KWARGS: %s" % (args,kwargs,))
        # super(PerfSONARWorker,self).init(*args,**kwargs)
        self.kwargs = kwargs
        # input queue:
        self.work_queue = PyAmqpLibQueue( 
            host=kwargs['psnr_host'], virtual_host=kwargs['psnr_vhost'], 
            userid=kwargs['psnr_user'], password=kwargs['psnr_password'], 
            exchange_name='store', type='topic', format='json' )
        self.results_queue = PyAmqpLibQueue(
            host=kwargs['host'], virtual_host=kwargs['vhost'], 
            userid=kwargs['user'], password=kwargs['password'], 
            exchange_name='store', type='topic' )
        self.logging_queue = StubQueue()
        if self.proc_name:
            setproctitle( self.proc_name )

        self.prefetch_tasks = 100
    
    def start( self, *args, **kwargs ):
        try:
            with self.work_queue:
                with self.results_queue:
                    with self.logging_queue:
                        # logging.debug("consume from %s" % (self.work_queue) )
                        self.work_queue.consume( self.process_task, limit=0, prefetch=self.prefetch_tasks )
        except KeyboardInterrupt, e:
            logging.info("terminating...")
            sys.exit(0)
        except Exception, e:
            logging.error('consume error: %s\n%s' % (e,traceback.format_exc()))
    
    
    def process_task( self, msg, envelope ):

        self.work_queue.task_done( envelope )
        
        msg['source'] = msg['source'].lower()
        msg['target'] = msg['target'].lower()
        
        s = '.'.join( reversed(msg['source'].split('.')) )
        t = '.'.join( reversed(msg['target'].split('.')) )
        
        # reformat message suitable for storage
        m = Message( 
            meta={
                # 'key_names': [ 'source', 'source_ip', 'target', 'target_ip' ],
                'key':  "perfsonar.source.%s.target.%s.%s.stats." % ( s, t, msg['test'] ),
                'carbon_key': "network.kpi.wan.source.%s.target.%s.%s" % ( s, t, msg['test'] ),
                'spec': 'perfsonar',
                'group': msg['test'],
            },
            context={
                'source':  msg['source'],
                'source_ip':  msg['source_ip'],
                'target':  msg['target'],
                'target_ip':  msg['target_ip'],
            },
            data={}
        )
        m.timestamp = string_to_datetime( msg['end_time'], '%a %b %d %H:%M:%S %Z %Y' )
        m.type = 'task'
        
        try:
            if msg['test'] == 'owamp':
                m.data = {
                    'min':  msg['ow_min'],
                    'max':  msg['ow_max'],
                    'loss': msg['pkts_lost'] / msg['pkts_sent'],
                    'dup': msg['pkts_dup'] / msg['pkts_sent'],
                }
            elif msg['test'] == 'bwctl':
                m.data = {
                    'throughput':  msg['throughput'],
                    'duration':  msg['test_duration'],
                }
        
            logging.info("%s %s" % ( m['timestamp'], m['_meta']['key'] ) )
            self.results_queue.put( m, key=m['_meta']['key'] )
        except Exception,e:
            logging.warn("%s %s failed: %s" % ( m['timestamp'], m['_meta']['key'], e ))
            
        return

class PerfSONARDaemon( ManagerDaemon ):
    manager = PerfSONARWorkerManager
    proc_name = 'ptolemy perfsonar'
    

class PerfSONAR( Command ):
    """
    slurps perfsonar owamp and bwctl output from amqp and puts them into the ptolemy store queue
    """

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        parser.add_argument( '-w', '--min_workers', help='number of workers', default=1, type=int )
        
        manager = parser.add_argument_group( 'manager settings', 'manager configuration')
        manager.add_argument( '-p', '--pool',    help='pool name', default='perfsonar.default-pool' )
        manager.add_argument( '-k', '--keys',     help='key name', action='append', default=['#'] )

        ampq = parser.add_argument_group('reader ampq' )
        ampq.add_argument( '--psnr_host',          help='read queue host',     default=settings.PSNR_HOST )
        ampq.add_argument( '--psnr_port',          help='read queue port',     default=settings.PSNR_PORT )
        ampq.add_argument( '--psnr_vhost',         help='read queue vhost',    default=settings.PSNR_VHOST )
        ampq.add_argument( '--psnr_user',          help='read queue username', default=settings.PSNR_USER )
        ampq.add_argument( '--psnr_password',      help='read queue password', default=settings.PSNR_PASSWORD )

        ampq = parser.add_argument_group('storage ampq' )
        ampq.add_argument( '--host',          help='storage queue host',     default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='storage queue port',     default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='storage queue vhost',    default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='storage queue username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='storage queue password', default=settings.BROKER_PASSWORD )


    def run(self, *args, **kwargs ):
        
        daemon = PerfSONARDaemon()
        daemon.start( **kwargs )
