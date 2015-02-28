import argparse
from slac_utils.managers import Manager, FanOutManager
from slac_utils.command import Command, CommandDispatcher, ManagerDaemon, Settings, DefaultList

# from slac_utils.util import read_file_contents

from ptolemy.watcher.workers import Scanner, HostWatcher
# from ptolemy.storage.managers import StorageManager
from ptolemy.queues import QueueFactory

from ptolemy.scheduler.managers import BaseScheduleSupervisor
from ptolemy.scheduler.scheduler import ScheduleParser

from slac_utils.net import netmask_to_prefixlen
import ipaddress

from slac_utils.messages import Message
from slac_utils.time import now

import os
import pprint
import logging
import traceback


class ScannerdSchedule( ScheduleParser ):
    pass

class ScheduledScannerdSupervisor( BaseScheduleSupervisor ):
    """
    listens for new subnets and schedules them for scans every minute
    """
    schedule_parser = ScannerdSchedule
    monitor_period = 3
    
    min_prefix_len = 18
    max_prefix_len = 26
    subnets = []
    proc_name = 'ptolemy watcher scannerd supervisor'
    
    
    def __init__(self,*args,**kwargs):
        # logging.error("KWARGS: %s, %s" % (args, kwargs,))
        super( ScheduledScannerdSupervisor, self ).__init__(*args, **kwargs)

        # default schedule for all
        self.parser.settings['schedule']['default'] = {
          'scannerd': '54 +- 6'  
        }
        
        self.subnets = []
        for s in kwargs['subnets']:
            self.subnets.append( ipaddress.IPv4Network(s) )
        # set prefix sizes
        for i in ( 'min_prefix_len', 'max_prefix_len' ):
            if i in kwargs:
                setattr( self, i, kwargs[i] )

    def process_work_queue( self ):
        # do stuff regarding the request queue
        if not self.work_queue == None:
            # exits if nothing in queue
            for job in self.work_queue.get( non_blocking=True, prefetch_count=10 ):
                # logging.info("got! %s" % job)
                if 'data' in job:
                    for subnet in job['data']:

                        # convert watched subnets
                        if 'prefix' in subnet and 'netmask' in subnet:

                            prefix = subnet['prefix']
                            netmask = subnet['netmask']
                            prefix_len = netmask_to_prefixlen( netmask )
                            network = "%s/%s" % (prefix,prefix_len)
                            
                            # only bother with local subnets (ie those routed by us)
                            if 'local' in subnet and subnet['local'] == True:
                                
                                # only bother with those we haven't seen yet
                                # TODO: update so we can expire old subnets
                                if not network in self.parser.nodes:
                                
                                    try:
                                
                                        this = ipaddress.IPv4Network( "%s/%s" % ( prefix, prefix_len ))
                                        for s in self.subnets:
                                            if this[0] in s and prefix_len >= self.min_prefix_len and prefix_len <= self.max_prefix_len:
                                                logging.info("Queuing %s" % ( network, ))
                                                schedule = {
                                                    'scannerd': '54 +- 6'                                                
                                                }
                                                node = {
                                                    'name': network,
                                                    'schedule': schedule
                                                }
                                                # TODO: bah, this shoudl be in the parser
                                                self.parser.nodes[network] = { 'schedule': { 'ref': 'default' } }
                                                self.parser.add( node, 'scannerd', factor=1 )
                                                return None
                                                    
                                    except ValueError:
                                        # host bits of ip address
                                        pass
                                    except Exception, e:
                                        logging.error("%s %s\n%s" % (type(e),e, traceback.format_exc()))
    
    def message_context( self, item ):
        prefix, prefix_len = item['node'].split('/')
        return { 'prefix': prefix, 'prefix_len': prefix_len }


class WatcherScannerdManager( FanOutManager ):
    worker = Scanner
    queue_factory = QueueFactory
    supervisor = ScheduledScannerdSupervisor
    
    # listen for subnets on store, submit jobs to supervised_watcher and get them to dump results back into store
    work_queue_func = 'store'
    supervisor_queue_func = 'supervised_watcher'
    results_queue_func = 'store'

    proc_name = 'ptolemy watcher scannerd manager'
    min_workers = 64
    max_tasks_per_worker = 1024

    # what initialisation keys for workers
    supervisor_kwargs = [ 'subnets', 'min_prefix_len', 'max_prefix_len' ]
    
class WatcherScannerdDaemon( ManagerDaemon ):
    manager = WatcherScannerdManager
    proc_name = 'ptolemy watcher scannerd'

class Base( Command ):
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        ampq = parser.add_argument_group('ampq options', 'options on connecting to backend messenging service')
        ampq.add_argument( '--host',          help='ampq host',     default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port',     default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='ampq vhost',    default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )

        manager = parser.add_argument_group( 'manager settings', 'manager configuration')
        manager.add_argument( '-p', '--pool',    help='pool name', default='watcher.scannerd.default' )
        manager.add_argument( '-k', '--keys',     help='key name', action='append', default=['#.spec.layer3.group.subnets.#'] )
        
    def run(self, *args, **kwargs ):
        raise NotImplementedError, 'run()'

class Scannerd( Base ):
    """
    scanner deamon to issue fpings to prime arp/nd caches, also report on statistics
    """
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        # parent
        Base.create_parser( parser, settings )
        parser.add_argument( '-w', '--min_workers', help='number of workers', default=settings.WORKERS, type=int )

        scan = parser.add_argument_group( 'scanning settings', 'scanning configuration')        
        scan.add_argument( '-s', '--subnets', help='subnets to monitor', action="append", default=settings.SUBNETS )
        scan.add_argument( '-l', '--min_prefix_len', help='minimum prefix length to test', default=settings.MIN_PREFIX_LEN )
        scan.add_argument( '-L', '--max_prefix_len', help='maximum prefix length to test', default=settings.MAX_PREFIX_LEN )

    def run(self, *args, **kwargs ):
        daemon = WatcherScannerdDaemon()
        daemon.start( **kwargs )



class HostManager( Manager ):
    worker = HostWatcher
    queue_factory = QueueFactory

    work_queue_func = 'store'
    results_queue_func = 'store'

    proc_name = 'ptolemy watcher host manager'
    worker_kwargs = [ 'cache_host', 'cache_spec', 'cache_group', 'bulk' ]

class HostDaemon( ManagerDaemon ):
    manager = HostManager
    proc_name = 'ptolemy watcher host daemon'

class Hosts( Base ):
    """
    alerts when a host (by ip or mac address) is seen or leaves the network
    """
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):

        Base.create_parser( parser, settings )

        parser.add_argument( '--cache_host', help='redis cluster members', default=DefaultList(settings.CACHE_HOST) )

        parser.add_argument( '-w', '--min_workers', help='number of workers', default=1, type=int )

        manager = parser.add_argument_group( 'manager settings', 'manager configuration')
        manager.add_argument( '-p', '--pool',    help='pool name', default='watcher.host' )
        manager.add_argument( '-k', '--keys',     help='key name', action='append', default=['#.spanning_tree.#','#.arps.#'] )

        expire = parser.add_argument_group( 'expiration settings', 'cache configuration')
        expire.add_argument( '--expire',     help='expire after n seconds', type=int, default=1200 )

        cache = parser.add_argument_group( 'cache settings', 'cache configuration')
        cache.add_argument( '--store_cache',     help='dump cache to queue', default=True )
        cache.add_argument( '--cache_spec',     help='group name for cache spec', default='caching' )
        cache.add_argument( '--cache_group',     help='group name for cache spec', default='hosts' )
        cache.add_argument( '--bulk',     help='batch results', default=True )


    def run(self, *args, **kwargs ):
        daemon = HostDaemon()
        daemon.start( **kwargs )

    

class Watcher( CommandDispatcher ):
    """
    Network Security Monitoring Tools
    """
    commands = [ Scannerd, Hosts ]
    
                
        
        
        
