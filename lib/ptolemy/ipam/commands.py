import argparse
from slac_utils.command import CommandDispatcher, Command
from slac_utils.messages import Message

from ptolemy.ipam.ipam import NetDB
from ptolemy.ipam.util import Categoriser

from ptolemy.storage.feeders import Store
from ptolemy.ipam.rackwise import RackWiseData

import os, errno
from time import time
from datetime import datetime, timedelta
import logging

from re import compile, search

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import urllib2
import json


class NetDBCommand( Command ):
    """
    base updating command
    """
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):

        ampq = parser.add_argument_group('backend messenging settings')
        ampq.add_argument( '--host',          help='ampq host', default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port', default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='ampq vhost', default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )
        
        netdb = parser.add_argument_group('netdb settings')
        netdb.add_argument( '--netdb_nodes',      help='netdb yaml file', default=settings.NETDB_NODES )
        netdb.add_argument( '--netdb_subnets',      help='netdb yaml file', default=settings.NETDB_SUBNETS )
        
    def get_store( self, **kwargs ):
        return Store( **kwargs )
        
    def get_db( self, **kwargs ):
        return NetDB( nodes=kwargs['netdb_nodes'], subnets=kwargs['netdb_subnets'] )


class NetworkDevices( NetDBCommand ):
    """
    updates the list registered network devices from cando
    """

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        super( NetworkDevices, self ).create_parser( parser, settings, parents=parents )

        subparser = parser.add_argument_group('categorisation settings')
        subparser.add_argument('--types', help='type definitions', default=settings.IPAM_TYPES )
        subparser.add_argument('--groups', help='group definitions', default=settings.IPAM_GROUPS )
        subparser.add_argument('--categories', help='group definitions', default=settings.IPAM_CATEGORIES )

        parser.add_argument('--directory', help='directory to update yaml files', default=settings.IPAM_DEVICES_DIRECTORY )
        parser.add_argument('--exclude_devices', help='hosts to exclude', default=settings.EXCLUDE_DEVICES )
        
        parser.add_argument('--no_update', help='do not update db', default=False, action='store_true' )

    def _run( self, cat, **kwargs ):
        db = self.get_db( **kwargs )
        for d in db.get_network_devices():
            # categorise
            t, g, c = cat.get( d['hostname'] )
            yield {
                'hostname':     d['hostname'],
                'ip_address':   d['ip_address'],
                'type':         t,
                'groups':       g,
                'categories':   c,
            }
        return

    def update_store( self, this ):
        # logging.error("THIS: %s" % (this,))
        msg = Message(
            meta={
                'spec': 'ipam',
                'group': 'devices',
                'archive_after': None,
            },
            context={
                'device':   this['hostname'],
            },
            data={
            }
        )

        for i in ( 'type', 'groups', 'categories' ):
            v = ''
            if len( this[i] ) == 1:
                v = this[i][0]
            else:
                v = ','.join(this[i])
            msg['data'][i] = v

        msg.timestamp = int(time())
        msg.type = 'task'

        logging.info("adding: %s" % (msg,))
        self.feeder.process_task( msg )


    def run( self, *args, **kwargs ):
        # write each category file for list of devices
        # also update the storage ipam dbs'
        
        self.feeder = Store( **kwargs )
        cat = Categoriser( type_file=kwargs['types'],
                    group_file=kwargs['groups'],
                    category_file=kwargs['categories'] )
        dir = kwargs['directory']
        try:
            os.makedirs( dir )
        except Exception, e:
            if e.errno == errno.EEXIST and os.path.isdir(dir):
                pass
            else:
                raise e

        items = {}
        for this in self._run( cat, **kwargs ):
            
            ok = True
            for r in kwargs['exclude_devices']:
                if search( r, this['hostname'] ):
                    ok = False
                    break
            
            if ok:
                # send updates to feeder
                if not kwargs['no_update']:
                    self.update_store(this)
                else:
                    print '+ %-40s\t%-20s\t%-40s\t%-20s' % ( this['hostname'], this['type'], this['groups'], this['categories'] )

                # create lists for file diffs
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
        
        if not kwargs['no_update']:
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
                added = set( sorted(current['hosts'].keys()) ) - set( sorted(current_hosts.keys()) )

                # remove hosts no longer in use
                removed = set( sorted(current_hosts.keys()) ) - set( sorted(items[c].keys()) )
                # logging.error("REMOVED: %s" % (removed,))
                for r in removed:
                    del current['hosts'][r]
            
                # differences
                if len(added) or len(removed):
                    print("%s: " % (c,))
                    if len(added):
                        print("  added:")
                        for i in added:
                            print("    %s" % (i,))
                    if len(removed):
                        print("  removed:")
                        for i in removed:
                            print("    %s" % (i,))
            
                # write the yaml file out
                dump( current, file(f,'w'), Dumper=Dumper, default_flow_style=False )


class NetworkDevicesFeedback( NetworkDevices ):
    """
    Query the database via rest and reinject device types, categories and groups
    This is mainly for the stupid AP's which aren't registered in IPAM, so queries may fail
    unless we reinject the values as the rails view for devices will give correct values
    """

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        super( NetworkDevicesFeedback, self ).create_parser( parser, settings, parents=parents )

        parser.add_argument('--json_url', help='URI endpoint to fetch json list of devicse', default='http://network.slac.stanford.edu/devices.json' )

    def _run( self, cat, **kwargs ):
        response = urllib2.urlopen(kwargs['json_url'])
        data = json.load(response)
        for d in data:
            # categorise
            t, g, c = cat.get( d['device'] )
            yield {
                'hostname':     d['device'],
                'ip_address':   None,
                'type':         t,
                'groups':       g,
                'categories':   c,
            }
        return
    

        
class Subnets( NetDBCommand ):
    """
    Updates ptolemy's list of registered subnets
    """
    subnet_map = None

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        super( Subnets, self ).create_parser( parser, settings )
        
        subnet = parser.add_argument_group('subnet configurations' )
        subnet.add_argument( '--subnet_map_file', help="subnet mapping file", default=settings.SUBNET_MAP_FILE )

    def get_subnet_map( self, filename ):
        return load( open(filename,'r') )

    def map_subnet( self, name ):
        types = []
        seen = {}
        for item in self.subnet_map:
            for k,a in item.iteritems():
                # logging.error("  K: %s I: %s" % (k,i,))
                for i in a:
                    if search( i, name ):
                        if not k in seen:
                            types.append( k )
                        seen[k] = True
        return types
        
    def run( self, *args, **kwargs ):
        # create a generic storer feeder object and push each subnet into it
        feeder = self.get_store( **kwargs )
        db = self.get_db( **kwargs )
        self.subnet_map = self.get_subnet_map( kwargs['subnet_map_file'] )
        # logging.error("MAP %s" % (self.subnet_map,))
        
        now = int(time())
        for s in db.get_subnets():
            
            types = self.map_subnet(s['name'])
            logging.debug("%s\t-> %s" % (s,types))
            
            this = Message(
                meta={
                    'spec': 'ipam',
                    'group': 'subnets',
                    'archive_after': None,
                },
                context={
                    'prefix':   s['prefix'],
                    'netmask':  s['netmask'],
                    'prefix_len':   s['prefix_len']
                },
                data={
                    'name': s['name'],
                    'default_gateway': s['router'],
                    'description':  s['comments'],
                    'types': ','.join(types),
                }
                
            )
            if s['vlan']:
                this['data']['vlan'] = int(s['vlan'])


            this.timestamp = now
            this.type = 'task'

            # logging.error("THIS: %s" % (this,))
            feeder.process_task( this )
            # print("%s" % (this,) )
    
class Hosts( NetDBCommand ):
    """
    Update ptolemy's host information from cando
    """
    
    def run( self, *args, **kwargs ):
        """
        feed dns data into storage queue for hostname and user lookups
        """
        # do not create true threaded worker
        feeder = self.get_store( **kwargs )
        db = self.get_db( **kwargs )

        now = int(time())
        for h in db.get_hosts():
            # hard code fqdn
            if 'ip_address' in h and 'hostname' in h:
                this = Message(
                    meta={
                        'key_name': [ 'ip_address', 'hostname' ],
                        # 'key':      '.dns.cando.',
                        'spec':     'ipam',
                        'group':    'dns',
                        'archive_after': None,
                    },
                    context={
                        'ip_address':   h['ip_address'],
                    },
                    data={
                        # TODO: domain name?!
                        'hostname': h['hostname']
                    },
                )
                this.timestamp = now
                this.type = 'task'
            
                feeder.process_task( this )
                # print("%s" % ( this, ) )
    
    
# class QueryHost( DjangoCommand ):
#     """
#     Retrieves information about a host from cando
#     """
#     @classmethod
#     def create_parser( self, parser, settings, parents=[] ):
#         parser.add_argument( 'host', help='hostname' )
#
#     def run( self, *args, **kwargs ):
#         if 'host' in kwargs:
#             cando = Cando( CANDO_DB_NAME )
#             d = cando.get_device( kwargs['host'] )
#             print "%s" % (d,)


class Rackwise( NetDBCommand ):
    """
    Update's ptolemy with information from rackwise
    """

    field_pattern = compile('[\W_]+')

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):
        super( Rackwise, self ).create_parser( parser, settings )
        parser.add_argument( 'rackwise_spreadsheets', help='rackwise excel spreadsheets', nargs='+' )
    
    def rackwise2message( self, item, site=None ):

        # build context
        context_fields = ( 'Asset ID', 'Name', 'Serial Number' )
        # logging.error("%s" % (item,))
        c = {}
        d = {}
        for f in item:
            e = self.field_pattern.sub( '', f )
            if f in context_fields:
                c[e] = item[f]
            else:
                d[e] = item[f].replace('\n', '; ')

        # add site
        d['Site'] = site

        this = Message(
            meta={
                'spec':     'ipam',
                'group':    'rackwise',
                'archive_after':    None,
            },
            context=c,
            data=d,
        )
        this.type = 'task'
        return this
    
    def run( self, *args, **kwargs ):
        now = datetime.now()
        feeder = self.get_store( **kwargs )
        for f in kwargs['rackwise_spreadsheets']:
            for i in RackWiseData( f ):
                # create the message
                m = self.rackwise2message( i, site=os.path.splitext( os.path.basename(f) )[0] )
                m.timestamp = now
                # logging.warn("%s" % (m,))
                feeder.process_task( m )
                print "%s" % (m,)

# class PropertyControl( UpdaterCommand ):
#     """
#     populates stores of all property control information
#     """
#
#     def pc2message( self, item ):
#         this = Message(
#             meta={
#                 'spec':     'ipam',
#                 'group':    'property_control',
#                 'archive_after':    None,
#             },
#             context={
#                 'pc_number': item.pc_number,
#                 'serial':   item.serial,
#             },
#             data={
#                 'type': item.type,
#                 'model': item.model,
#                 'contact':  item.contact,
#                 'group':    item.group,
#             },
#         )
#         this.type = 'task'
#         this.timestamp = item.date()
#         return this
#
#     def run( self, *args, **kwargs ):
#         feeder = self.get_store( **kwargs )
#         cando = self.get_cando( **kwargs )
#         for i in cando.get_items():
#             t = self.pc2message( i )
#             print("%s" % (t,))
#             feeder.process_task( t )
        

class IPAM( CommandDispatcher ):
    """
    IP Address Management Integration Tools
    """
    commands = [ NetworkDevices, NetworkDevicesFeedback, Subnets, Hosts ]
