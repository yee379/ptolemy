import argparse

import ptolemy
from ptolemy.storage.managers import StorageManagerFactory

from slac_utils.command import CommandDispatcher, Command, DefaultList, ManagerDaemon, Settings, load_conf
from slac_utils.klasses import inheritors

from slac_utils.string import camel_case_to_underscore

import yaml
import sys
import inspect
from os.path import dirname
from glob import iglob
import importlib

import logging


class StorageCommand( Command ):
    factory = StorageManagerFactory()
    worker = None
    proc_name = None 
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        manager = parser.add_argument_group( 'manager settings')
        manager.add_argument( '--output_format', help="serialisation format of messages", default='pickle' )

        worker = parser.add_argument_group( 'worker settings')
        worker.add_argument( '-p', '--pool',    help='pool name',  default=settings.POOL )
        worker.add_argument( '-k', '--keys',     help='key name',   action='append', default=settings.KEYS )
        worker.add_argument( '-w', '--min_workers', help='number of workers',   default=settings.WORKERS, type=int )

        # add defaults
        ampq = parser.add_argument_group('ampq options')
        ampq.add_argument( '--host',          help='ampq host',     default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port',     default=settings.BROKER_PORT, type=int )
        ampq.add_argument( '--vhost',         help='ampq vhost',    default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )
        
 
    def get_storage_daemon( self, worker, **kwargs ):
        # create a storage manager with the agent class
        class Storer( ManagerDaemon ):
            manager = self.factory.get( self.worker, manager_name=self.proc_name, **kwargs )
        return Storer
    def pre_run( self, *args, **kwargs ):
        return args, kwargs
    def run( self, *args, **kwargs ):
        # logging.info("RUN: %s" % (kwargs,))
        args, kwargs = self.pre_run( *args, **kwargs )
        daemon = self.get_storage_daemon( self.worker, **kwargs )()
        daemon.start( **kwargs )

class Stored( CommandDispatcher ):
    """
    backend storage daemons
    """
    commands = [ ]
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        # preload all known feeders
        from ptolemy.storage.feeders import Feeder
        # get path 
        d = dirname(inspect.getfile(Feeder)) 
        # logging.error("D: %s" % (d,))
        # determine what classes exist beneath
        module_prefix = 'ptolemy.storage.feeders.'
        for m in iglob( d + '/*.py' ):
            # logging.error(" M: %s" % (m,))
            n = m.replace( d, '' ).replace( '.py', '' ).replace('/','')
            try:
                fp = module_prefix + n
                i = importlib.import_module( fp )
                # check for storagecommand ancestor
            except Exception,e:
                logging.error("could not import %s: %s" % (m,e))
        # append storage commands for argparse
        cls.commands = [ ]
        for h in inheritors( StorageCommand ):
            # onlyl allow those in directory D
            if h.__module__.startswith( module_prefix ):
                # logging.error( 'PATH: %s' %( h.__module__ ) )
                cls.commands.append( h )

        # logging.error("COMMANDS: %s" % (cls.commands,))
        super( Stored, cls ).create_parser( parser, settings, parents=parents )
