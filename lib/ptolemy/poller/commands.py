import argparse

from slac_utils.command import Command, ManagerDaemon, DefaultList
from ptolemy.poller.managers import PollManager

from slac_utils.util import read_file_contents
from slac_utils.messages import Message
from ptolemy.poller.workers import Gatherer, poll

from datetime import datetime

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import memcache

import logging
from slac_utils.logger import init_loggers

import pprint

class PollerDaemon( ManagerDaemon ):
    manager = PollManager
    proc_name = 'ptolemy polld manager'

class Polld( Command ):
    """
    distributed polling daemon
    """

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        
        manager = parser.add_argument_group( 'manager settings')
        manager.add_argument( '-p', '--pool',    help='pool name',  default='default' )
        manager.add_argument( '-k', '--keys',     help='key name',   action='append' )
        manager.add_argument( '-w', '--min_workers', help='number of workers',   type=int,   default=settings.WORKERS )
        manager.add_argument( '-W', '--max_workers', help='number of workers',   type=int,   default=settings.WORKERS )

        supervisor = parser.add_argument_group( 'polling settings')
        # supervisor.add_argument( '-c', '--driver_cache',    help='driver cache file',   default=settings.DRIVER_CACHE )
        supervisor.add_argument( '-D', '--driver_dir',      help='driver cache directory',   default=settings.DRIVER_DIR )
        supervisor.add_argument( '-l', '--driver_priorities', help='driver priorities',   default=settings.DRIVER_PRIORITIES )
        supervisor.add_argument( '-F', '--forced_drivers', help='forced drivers',   default=settings.FORCED_DRIVERS )

        memcache = parser.add_argument_group( 'memcache settings')
        memcache.add_argument( '-m', '--memcache_pool', help='memcache servers', default=DefaultList(settings.MEMCACHE_POOL))

        # statistics = parser.add_argument_group( 'statistics settings', 'statistics logging configuration')
        # statistics.add_argument( '--stats_host',    help='statistics server',   default=settings.STATS_HOST )
        # statistics.add_argument( '--stats_port',    help='statistics port',   default=settings.STATS_PORT )

        ampq = parser.add_argument_group('backend messenging settings')
        ampq.add_argument( '--host',          help='ampq host', default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port', default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='ampq vhost', default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )

        poll = parser.add_argument_group('polling settings')
        poll.add_argument( '--received_throttle_time', help='do not poll if received less than this in sec', default=settings.RECEIVED_THROTTLE_TIME )
        poll.add_argument( '--complete_throttle_time', help='do not poll if received less than this much after the last has completed', default=settings.COMPLETE_THROTTLE_TIME )
        poll.add_argument( '--failed_throttle_time',  help='if the last poll failed, do not do it again until after this', default=settings.FAILED_THROTTLE_TIME )
        poll.add_argument( '--invalid_time_multiplier', help='invalidate poll if its been running for this times the frequency of the test', default=settings.INVALID_TIME_MULTIPLIER )
        poll.add_argument( '--reprobe_period',      help='automatically reprobe drivers after this time', default=settings.REPROBE_PERIOD )
        poll.add_argument( '--reprobe_spread',      help='variation of reprobe period', default=settings.REPROBE_SPREAD )        

        agent = parser.add_argument_group('agent settings')
        agent.add_argument( '--netconfig_config', help='location of netconfig configuration file', default=settings.NETCONFIG_CONFIG )

        return parser
        
    def run( self, *args, **kwargs ):

        if not 'keys' in kwargs:
            kwargs['keys'] = ['#']
        
        p = PollerDaemon()
        p.start( **kwargs )
        
class Poll( Command ):
    """
    command line polling
    """
    
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):        

        poll = parser.add_argument_group( 'poll settings' )
        poll.add_argument( 'host', help='device to poll' )
        poll.add_argument( '-d', '--driver', help='force use of driver', default=None )
        poll.add_argument( '--driver_path', help='force the use of driver to use', default=None )
        poll.add_argument( '--probe', help='force a probe for compatible driver', action='store_true', default=False )
        poll.add_argument( '-D', '--driver_dir',      help='driver cache directory',   default=settings.DRIVER_DIR )
        poll.add_argument( '-l', '--driver_priorities', help='driver priorities',   default=settings.DRIVER_PRIORITIES )
        poll.add_argument( '-t', '--timeout', help='poller timeout',   default=300 )

        conf = parser.add_argument_group( 'configuration' )
        # conf.add_argument( '--driver_dir', help='directory of drivers', default='/opt/ptolemy/etc/ptolemy/polld/drivers/' )
        # conf.add_argument( '--mib_dir', help='directory of mibs', default='/opt/ptolemy/etc/ptolemy/polld/snmp_mibs/' )
        conf.add_argument( '-c', '--community', help='snmp community', default='/opt/etc/snmp.community.read' )
        # conf.add_argument( '--timeout', help='hard timeout', default=0, type=int )

        poll.add_argument( '-w', '--write', help='write driver details to cache', default=False, action='store_true' )


        agent = parser.add_argument_group('agent settings')
        agent.add_argument( '--netconfig_config', help='location of netconfig configuration file', default=settings.NETCONFIG_CONFIG )

        # copy settings to later user
        self.settings = settings

        return parser


    def run( self, *args, **kwargs ):

        init_loggers( None, verbose=kwargs['verbose'], log_format='%(module)s %(lineno)d\t%(levelname)s\t%(message)s' )

        # logging.error("KWARGS: %s" % kwargs )
        # load driver priorities
        driver_dir = kwargs['driver_dir']
        drivers = load( file(kwargs['driver_priorities'],'r'), Loader=Loader )

        g = Gatherer( **kwargs )

        if ':' in kwargs['host']:
            kwargs['host'], _tmp, kwargs['probe'] = kwargs['host'].partition(':')

        job = Message(
            meta={},
            context={
                'device': kwargs['host'],
            },
            data={
                'snmp_community': read_file_contents( kwargs['community'] ),
            }
        )
        
        if 'timeout' in kwargs:
            job._meta['frequency'] = kwargs['timeout']
        
        if 'driver_path' in kwargs and kwargs['driver_path']:
            job.context['spec'] = None
            job.data['driver'] = kwargs['driver_path']
        elif 'driver' in kwargs and kwargs['driver']:
            job.context['spec'] = kwargs['probe']
            job.data['driver'] = '%s/%s/%s' % (kwargs['driver_dir'],job.context['spec'],kwargs['driver'])
            f = open( job.data['driver'], 'r' )
            f.close()
        elif 'probe' in kwargs and kwargs['probe']:
            job.context['spec'] = kwargs['probe']
            # logging.error("JOB: %s" % (drivers,))        
            these_drivers = []
            if job.context['spec'] in drivers:
                for d in drivers[job.context['spec']]:
                    these_drivers.append( driver_dir + '/' + job.context['spec'] + '/' + d )
                job.data['probe_with_drivers'] = these_drivers
            logging.info("probing with %s" % ( [ i.split('/')[-1] for i in these_drivers ], ))
        else:
            raise SyntaxError, 'must specify spec to poll or driver to use'

        # logging.info("JOB: %s" % (job,))

        # do it
        for i in poll( job, g ):
            print "%s" % (pprint.pformat(i),)
            

        
class DriverCache( Command ):
    """
    query polld distributed cache entries
    """
    
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):    

        parser.add_argument( '-m', '--memcache_pool', help='memcache servers', default=DefaultList(settings.MEMCACHE_POOL))
        parser.add_argument( '-p', '--prefix', help='key prefix', default='ptolemy:polld:')
        subparsers = parser.add_subparsers()
        
        # A list command
        # TBD
        list = subparsers.add_parser('list', help='List contents', parents=parents, conflict_handler='resolve' )
        list.set_defaults(method='list')

        # get
        get = subparsers.add_parser('get', help='Get contents', parents=parents, conflict_handler='resolve')
        get.add_argument( 'key', help='cache key' )
        get.set_defaults(method='get')

        # set
        set = subparsers.add_parser('set', help='Set contents', parents=parents, conflict_handler='resolve')
        set.add_argument( 'key', help='cache key' )
        set.add_argument( '--force_driver', required=False )
        set.set_defaults(method='set')
        
        # delete
        delete = subparsers.add_parser('delete', help='Delete cache item', parents=parents, conflict_handler='resolve')
        delete.add_argument( 'key', help='cache key')
        delete.set_defaults(method='delete')


    def run( self, *args, **kwargs ):

        from pprint import pformat

        # logging.error("KWARGS: %s" % pformat(kwargs))
        mc = memcache.Client( kwargs['memcache_pool'], debug=0 )
        
        p = kwargs['prefix']
        k = p + kwargs['key']
        
        if kwargs['method'] == 'get':
            d = mc.get( k )
        
        elif kwargs['method'] == 'set':
            d = mc.get( k )
            for i in ( 'force_driver', ):
                if i in kwargs:
                    d[i] = kwargs[i]
            mc.set( k, d )
            d = mc.get( k )
        
        elif kwargs['method'] == 'delete':
            d = mc.get( k )
            mc.delete( k )
        
        if d:
            for k,v in d.iteritems():
                if isinstance( v, datetime ):
                    d[k] = str(v)
            print("%s" % (pformat(d),))
    