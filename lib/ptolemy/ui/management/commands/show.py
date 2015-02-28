from sys import exit

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option

from ptolemy_py.ui.views_cmdline import *

import os

import logging


class Command( BaseCommand ):

    option_list = BaseCommand.option_list + (
        make_option('--category', dest='category', help='filter by category'),
        make_option('--kind', dest='kind', help='filter by kind'),
        make_option('--name', dest='name', help='filter by name'),
        make_option('--software_version', dest='software_version', help='filter by software_version'),
        make_option('--vlan', dest='vlan', help='filter by vlan'),

        make_option('--model', dest='model', help='filter by model'),
        make_option('--vendor', dest='vendor', help='filter by vendor'),
        make_option('--serial', dest='serial', help='filter by serial number'),
        make_option('--location', dest='location', help='filter by location'),

        make_option('--building', dest='building', help='filter by building'),

        make_option('--width', dest='columns', help='output width in characters'),
        make_option('--format', dest='format', help='output format'),
        make_option('--orderby', dest='orderby', help='output sorting column'),

    )
    help = "ptolemy.py show displays lan monitoring information on command line.\n"
    help += "\n"
    help += "  where fields are:\n"
    help += "    name\n"
    help += "    software_version\n"
    help += "    location\n"
    help += "    model\n"
    help += "    last_seen\n"
    help += "    uptime\n"
    help += "    vendor\n"
    help += "    category\n"
    help += "    kind\n"
    help += "    vlan\n"
    help += "    serial\n"

    args = 'devices|ports [field1, field2...]'
    
    def parse_filters(self, cls, kwargs):
        this = { 'filters': {} }
        for k in kwargs:
            if not kwargs[k] == None:
                if k in cls.columns:
                    this['filters'][k] = kwargs[k]
        # logging.error("THIS: " + str(this))
        return this
    
    def handle(self, *args, **kwargs):

        a = []
        mode = None
        for i in xrange( len(args)):
            if i == 0:
                mode = args[i]
                continue
            a.append( args[i] )
        logging.debug("args (" + str(mode) + ") " + str(a) + ": " + str(kwargs))

        order = kwargs.get('orderby')

        # terminal size
        r, c = None, None
        if kwargs.get('columns'):
            c = kwargs.get('columns')
        else:
            try:
                term = os.popen('stty size', 'r').read()
                r, c = term.split()
            except Exception, e:
                pass

        # determine what to show
        if mode == 'devices':
            d = CmdLineDeviceView()
            if not order == None:
                d.order_by = order
            filters = self.parse_filters( d, kwargs )
            args = {
                'columns': a, 
                'format': kwargs.get('format'),
            }
            if not c == None:
                args['width'] = int(c)
            print d.render( filters,**args )

        else:
            raise NotImplementedError
        
        exit(0)