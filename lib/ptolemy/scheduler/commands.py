import argparse

from slac_utils.command import Command, ManagerDaemon
from ptolemy.scheduler.managers import DistributedScheduleManager, OnDemandScheduleManager

from ptolemy.scheduler.scheduler import YAMLScheduleParser as ScheduleParser
# from ptolemy.scheduler.workers import submit
from ptolemy.queues import QueueFactory

# from slac_utils.time import now
from ptolemy.request import PollRequest
from ptolemy.scheduler.workers import create_task

from slac_utils.logger import init_loggers
import logging



class ScheduleBase( Command ):

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):

        manager = parser.add_argument_group( 'on-demand scheduler settings')
        manager.add_argument( '-p', '--pool',    help='pool name', default='default-pool' )
        manager.add_argument( '-k', '--key',     help='key name' )
        manager.add_argument( '--memcache_pool',  help='memcache servers', default=settings.MEMCACHE_POOL )

        ampq = parser.add_argument_group('ampq options', 'options on connecting to backend messenging service')
        ampq.add_argument( '--host',          help='ampq host', default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port', default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='ampq vhost', default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )
        
        scheduling = parser.add_argument_group( 'scheduling options', 'options for what to schedule' )
        scheduling.add_argument( '--nodes',      help='configured nodes to schedule', default=settings.NODES )
        scheduling.add_argument( '--snmp',       help='snmp profiles file', default=settings.SNMP_SETTINGS )
        scheduling.add_argument( '--schedule',   help='schedule profile file', default=settings.SCHEDULE )
        #scheduling.add_argument( '--provision_only',   help='only provide provision support', default=False, action='store_true' )

class DistributedSchedulerdDaemon( ManagerDaemon ):
    manager = DistributedScheduleManager
    proc_name = 'ptolemy scheduled'

class DistributedScheduled( ScheduleBase ):
    """
    distributed scheduling daemon 
    """
    def run(self, *args, **kwargs ):
        scheduler = DistributedSchedulerdDaemon()
        scheduler.start( *args, **kwargs )




class Schedule( ScheduleBase ):
    """
    on-demand schedule
    """
    
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        super( Schedule, self ).create_parser( parser, settings, parents=parents )
        
        poll = parser.add_argument_group( 'poll' )
        poll.add_argument( 'node', help='node to poll' )
        poll.add_argument( '--spec', help='spec to poll', default=None )

    
    def run(self, *args, **opts ):
        scheduler = OnDemandScheduleManager( *args, **opts )
        if opts['spec'] == None:
            if not ':' in opts['node']:
                raise Exception( 'need specification' )
            opts['node'], opts['spec'] = opts['node'].split(':')
        # scheduler.start( *args, **opts )
        scheduler.queue( opts['node'], opts['spec'] )
        
        
        