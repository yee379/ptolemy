from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import argparse
from slac_utils.managers import CommandMixin

from ptolemy.property_control.property_control import Cando

from ptolemy.storage.workers import MongoStorer

from time import time
from datetime import datetime, timedelta
import logging


mode_map = {
    'feed_property_control': {
        'mongo_host': 'localhost',
        'mongo_port': 27017
    },
}

class Command( CommandMixin, BaseCommand ):
    """
    """
    parser = None
    cando = None

    def feed_property_control( self ):
        """
        feed pc data into mongo
        """
        # do not create true threaded worker
        feeder = MongoStorer( None, **mode_map['feed_property_control'] )
        now = int(time())
        for i in self.cando.get_devices():
            this = {
                'spec':     'property_control',
                'group':    'cando',
                'timestamp':    now,
                'first_seen':   i.date(),
                'pc_number':    i.pc_number,
                'serial':       i.serial,
                '_meta':    {
                    'key_name': [ 'pc_number', 'serial' ],    # allow indexing of the ip
                    'key':      '.property_control.cando.',
                },
                'data':     {
                    'model':        i.model,
                    'manufacturer': i.manufacturer,
                },
            }
            # logging.info("%s " % ( this ) )
            for i in feeder.process_task( this, time_delta=timedelta( days=3 ) ):
                pass
    
    def create_parser( self ):
        parser = argparse.ArgumentParser( description="property control management" )
        parser.add_argument('-v', '--verbose', help="verbosity", action='store_true', default=False )
        subparsers = parser.add_subparsers( help='sub command help')
        subparser = {}
        for i in mode_map:
            subparser[i] = subparsers.add_parser( i )
            subparser[i].set_defaults( FUNCTION=i )
        return parser
        
    def run( self, *args, **kwargs ):

        self.cando = Cando( 'cando' )
        # call mapped mode function
        return getattr( self, self.kwargs['FUNCTION'] )()


