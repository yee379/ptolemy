from slac_utils.managers import FanOutManager, Manager, Worker, Supervisor
from slac_utils.command import ManagerDaemon, DefaultList
from ptolemy.storage.commands import StorageCommand
from ptolemy.storage.feeders import Feeder
from slac_utils.time import datetime_to_epoch, now
from ptolemy.util.redis_mixins import ZStoreMixin

import traceback

from string import Template
import logging
from math import floor


class Layer1Worker( Feeder, ZStoreMixin ):
    """
    simply monitor for peer to peer connections and keep a cache in redis
    also monitor port channels an determine if the physical ports are associated with 
    
    """
    proc_name = 'ptolemy analyse layer1 worker'
    
    key_template = Template('pt:layer1:${device}:${physical_port}')
    value_template = Template("${peer_device}:${peer_physical_port}")
    this_time = None
    
    def setup( self, **kwargs ):
        super( Layer1Worker, self ).setup(**kwargs)
        self.connect_redis( kwargs['cache_pool'].pop(0) )
        
    def pre_bulk_process( self, time, meta, context, data ):
        # logging.error("META: %s \t  %s -> %s" % (meta,context,data))
        self.this_time = datetime_to_epoch(time)
        if meta['spec'] == 'layer1_peer' and meta['group'] == 'neighbour':
            return True
        elif meta['spec'] == 'port_channel' and meta['group'] == 'members':
            return True
        return False
    
    def post_bulk_process( self, *args, **kwargs ):
        self.pipe.execute()

    def save( self, time, meta, context, data, time_delta=None, expiration=1200 ):
        # save layer1 p2p connections to other network devices (excluding phones)
        if meta['spec'] == 'layer1_peer' and not 'capability_telephone' in data:
            key = self.key_template.substitute(context)
            data['peer_device'] = data['peer_device'].lower()
            # TODO: HA! hard coding stuff is fun.. until i forget about it...
            if not '.' in data['peer_device']:
                data['peer_device'] = data['peer_device'] + '.slac.stanford.edu'
            value = self.value_template.substitute(data)
            logging.info("%s\t -> %s" % (key,value))
            self.pipe.setex( key, expiration, value )
        
        # save port channel peering information
        elif meta['spec'] == 'port_channel':
            # context contains host and physical port, data contains the po
            # we will need to do a lookup on the layer1_peer to determine
            # if this physical port is directly connected to another switch
            is_uplink = self.redis.get( self.key_template.substitute( context ) )
            # logging.error(" is_uplink: %s" % (is_uplink,))
            if is_uplink:
                key = self.key_template.substitute( { 'device': context['device'], 'physical_port': data['port-channel'] } )
                # logging.error(" is uplink: %s" % (is_uplink,))
                d, p = is_uplink.split(':')
                value = self.value_template.substitute( { 'peer_device': d, 'peer_physical_port': 'unk' } )
                # logging.error(" set %s\t%s" % (key,value))
                # how to determien the peering Po number?
                logging.info("%s\t -> %s *" % (key,value))
                self.pipe.setex( key, expiration, value )
        
class Layer1Manager( Manager ):
    worker = Layer1Worker
    proc_name = 'ptolemy analyse layer1 manager'

class Daemon( ManagerDaemon ):
    manager = Layer1Manager
    proc_name = 'ptolemy analyse layer1 daemon'
    worker_kwargs = ['cache_pool'] 


    
class Layer1( StorageCommand ):
    """
    Monitors and alerts on point to point linls
    """
    worker = Layer1Worker
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        super( Layer1, cls ).create_parser( parser, settings, parents=parents )

        redis = parser.add_argument_group( 'cache settings')
        redis.add_argument( '--cache_pool', help='redis server(s)', default=DefaultList(settings.CACHE_POOL))

        manager = parser.add_argument_group( 'manager settings', 'manager configuration')
        manager.add_argument( '-p', '--pool',    help='pool name', default='analyse.layer1' )
        manager.add_argument( '-k', '--keys',     help='key name', action='append', default=settings.KEYS )
