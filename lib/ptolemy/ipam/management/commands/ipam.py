from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import argparse
from slac_utils.managers import CommandMixin
from slac_utils.messages import Message

from ptolemy.ipam.ipam import Cando
from ptolemy.ipam.util import Categoriser

from ptolemy.storage.workers import MongoStorer

import os, errno
from time import time
from datetime import datetime, timedelta
import logging

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

mode_map = {
    'dump_network_devices': {},
    'update_network_devices': {
        'directory': settings.IPAM_DEVICES_DIRECTORY,
    },
    'feed_subnets': {
        'mongo_host': 'localhost',
        'mongo_port': 27017
    },
    'feed_hosts': {
        'mongo_host': 'localhost',
        'mongo_port': 27017
    },
}

class Command( CommandMixin, BaseCommand ):
    """
    """
    parser = None
    cando = None


    def feed_subnets( self ):
        feeder = MongoStorer( None, **mode_map['feed_subnets'] )
        now = int(time())
        for s in self.cando.get_subnets():
            this = Message(
                meta={
                    'spec': 'ipam',
                    'group': 'subnets',
                },
                context={
                    'prefix':   s.prefix,
                    'netmask':  s.netmask,
                    'prefix_len':   s.prefix_len(),
                },
                data={
                    'name': s.name,
                    'default_gateway': s.default_gateway,
                    'description':  s.description,
                }
                
            )
            this.timestamp = now
            this.type = 'task'

            # logging.error("THIS: %s" % (this,))
            for i in feeder.process_task( this, time_delta=timedelta( days=90 ) ):
                logging.info("%s" % (i,) )


    def get_host( self, host ):
        d = self.cando.get_device( host )
        logging.error("d: " + str(d))
        return d
    
    def get_network_devices( self ):
        cat = Categoriser( type_file=settings.IPAM_TYPES,
                    group_file=settings.IPAM_GROUPS,
                    category_file=settings.IPAM_CATEGORIES )

        for d in self.cando.get_network_devices():
            # categorise
            t, g, c = cat.get( d['hostname'] )
            yield {
                'hostname':     d['hostname'],
                'ip_address':   d['ip_address'],
                'type':  t,
                'groups':       g,
                'categories':     c,
            }
        
        return
        # f = open( '/tmp/devices' )
        # for l in f.readlines():
        #     devices[ l.strip() ] = True
    
    def dump_network_devices( self ):
        for this in self.get_network_devices():
            print '+ %-40s\t%-20s\t%-40s\t%-20s' % ( this['hostname'], this['device_type'], this['groups'], this['categories'] )
        return
    
    def update_network_devices( self ):
        # write each category file for list of devies
        dir = mode_map['update_network_devices']['directory']
        try:
            os.makedirs( dir )
        except Exception, e:
            if e.errno == errno.EEXIST and os.path.isdir(dir):
                pass
            else:
                raise e

        items = {}
        for this in self.get_network_devices():
            if len(this['categories']) > 0:
                k = this['categories'].pop()
                if not k in items:
                    items[k] = {}
                items[k][this['hostname']] = this
    
        # dataformat
        # settings:
        #   snmp: <str>
        #   schedule: <str>
        #   group: wireless
        # hosts:
        #   host1: {}
        #   host2: {}
        
        for c in items:

            f = dir + '/' + c + '.yaml'
            # read in the existing file
            current = {
                'settings': {
                    'snmp': 'default',
                    'schedule': 'default'
                },
                'hosts': {}
            }
            try:
                current = load( file(f,'r'), Loader=Loader )
                # logging.info("%s" % (current,))
            except Exception, e:
                pass

            current_hosts = {}
            
            # keep existin host customisations
            if 'hosts' in current and len( current['hosts'] ) > 0:
                current_hosts = current['hosts'].copy()

            # update list of hosts, keep customisations
            for d in sorted(items[c]):
                # ignore terminal servers
                this = items[c][d]
                n = this['hostname']
                if not 'terminal' in this['type']:
                    current['hosts'][n] = None
                    if n in current_hosts:
                        if current_hosts[n]:
                            current['hosts'][n] = current_hosts[n]

            # differences
            added = set( sorted(current['hosts'].keys()) ) - set( sorted(current_hosts.keys()) )
            removed = set( sorted(current_hosts.keys()) ) - set( sorted(current['hosts'].keys()) )
            if len(added) or len(removed):
                logging.error("%s: " % (c,))
                if len(added):
                    logging.info("  added:")
                    for i in added:
                        logging.info("    %s" % (i,))
                if len(removed):
                    logging.info("  removed:")
                    for i in removed:
                        logging.info("    %s" % (i,))
            
            # write the yaml file out
            # dump( current, file(f,'w') )
            dump( current, file(f,'w'), Dumper=Dumper, default_flow_style=False )
    
    def feed_hosts( self ):
        """
        feed dns data into mongo for hostname and user lookups
        """
        # do not create true threaded worker
        feeder = MongoStorer( None, **mode_map['feed_hosts'] )
        now = int(time())
        for h in self.cando.get_all_hosts():
            # hard code fqdn
            this = Message(
                context={
                    'ip_address':   h.ip_address,
                },
                meta={
                    'key_name': [ 'ip_address', 'hostname' ],
                    'key':      '.dns.cando.',
                    'spec':     'dns',
                    'group':    'cando',
                },
                data={
                    'hostname': "%s.slac.stanford.edu" % h.hostname.lower(),
                },
            )
            this.timestamp = now
            this.type = 'task'
            
            for i in feeder.process_task( this, time_delta=timedelta( days=90 ) ):
                logging.info("%s" % ( i, ) )
    
    def create_parser( self ):
        parser = argparse.ArgumentParser( description="ipam management" )
        # parser.add_argument( 'ipam', help='IPAM utilities' )
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


