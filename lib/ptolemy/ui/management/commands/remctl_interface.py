from sys import exit

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option

from ptolemy_py.util.remote import *

import logging


class Command( BaseCommand ):

    option_list = BaseCommand.option_list + (
        make_option('--args', dest='args',
            help='arguments'),
    )
    help = 'Ptolemy Netconfig Interface'
    args = '[--args=STRING]'
    
    def handle(self, *args, **options):

        args = str(options.get('args'))
        # logging.debug("command line params " + str(args) )

        nc = NetShow( server=settings.PROVISION_SERVER, port=settings.PROVISION_PORT, service=settings.PROVISION_SERVICE )
        nc.connect()
        cmds = [ 'port', 'swh-b050f3', 'Gi5/3' ]
        for i in nc.run( cmds ):
            print( i )
        nc.close()
        
        exit(0)