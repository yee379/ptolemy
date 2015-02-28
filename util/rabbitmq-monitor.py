#!/bin/env python

"""
simple script to grab values from rabbitmq via command line and dump summary queue stats out to the ptolemy storage queue
"""

from slac_utils.managers import WorkerManager
from slac_utils.command import Command, ManagerDaemon
from slac_utils.messages import Message

import argparse

import logging

CMD="/usr/sbin/rabbitmqctl  -p /ptolemy list_queues name messages messages_ready messages_unacknowledged"

class RabbitMQManager( WorkerManager ):
    proc_name = 'ptolemy rabbitmq-monitor'
  
    def process_task( self ):
        print "%s" % (CMD,)
        time.sleep( 60 )
        
class RabbitMQDaemon( ManagerDaemon ):
    manager = RabbitMQManager
    proc_name = 'ptolemy rabbitmq-monitor'
    

class RabbitMQMonitor( Command ):
    """
    puts rabbitmq statistics into ptolemy storage queues
    """

    def create_parser( self, parser, settings ):
        if not parser:
            parser = argparse.ArgumentParser( description='ptolemy perfsonar')
            
        parser.add_argument( '-v', '--verbose', help='verbosity', action='store_true', default=True )
        parser.add_argument( '-f', '--foreground', help='verbosity', action='store_true', default=True )

        manager = parser.add_argument_group( 'manager settings', 'manager configuration')
        manager.add_argument( '-p', '--pool',    help='pool name', default='perfsonar.default-pool' )
        manager.add_argument( '-k', '--keys',     help='key name', action='append', default=['#'] )

        ampq = parser.add_argument_group('storage ampq' )
        ampq.add_argument( '--host',          help='storage queue host',     default='net-lanmon01.slac.stanford.edu' )
        ampq.add_argument( '--port',          help='storage queue port',     default=5672 )
        ampq.add_argument( '--vhost',         help='storage queue vhost',    default='/ptolemy' )
        ampq.add_argument( '--user',          help='storage queue username', default='ptolemy' )
        ampq.add_argument( '--password',      help='storage queue password', default='ptolemy' )
        
        return parser


    def run(self, *args, **kwargs ):
        
        daemon = RabbitMQDaemon()
        daemon.start( **kwargs )

if __name__ == "main":
    
    r = RabbitMQMonitor()
    o = vars( r.create_parser( None ).parse_args() )
    print "%s" % (o,)
    r.run( **o )
    
    
        