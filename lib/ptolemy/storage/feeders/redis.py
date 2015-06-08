
from ptolemy.queues import QueueFactory
from ptolemy.storage.feeders import Feeder
from ptolemy.storage.commands import StorageCommand, DefaultList

from slac_utils.time import utcfromtimestamp, sleep
from slac_utils.command import DefaultList
from slac_utils.string import dict_to_kv, flatten
from string import Template

from ptolemy.util.redis_mixins import ZStoreMixin

import traceback
import logging
from pprint import pformat

class RedisStorer( Feeder, ZStoreMixin ):
    """
    dumps each document into a redis database
    we use the context of each msg to become the key. we store the raw msg into
    a 
    """
    agent = 'redis'
    proc_name = 'ptolemy stored redis'
    
    post_msg_data = {}
    current_table_name = None
    storage_options = {}
    
    key_prepend = 'pt:store'
    
    def setup( self, **kwargs ):
        super( RedisStorer, self).setup(**kwargs) 
        logging.info("connecting to %s" % (kwargs,))
        self.connect_redis( kwargs['cache_host'].pop(0) )
        if 'storage_options' in kwargs:
            self.storage_options = kwargs['storage_options']
        # logging.error("STORAGE: %s" % (self.storage_options,))
        

    def get_key( self, ctx ):
        """ get a unique key from this ctx """
        return dict_to_kv(ctx,join_char=',',modifier='')

    def pre_msg_process( self, msg, envelope ):
        # basically a pre fetch for data
        logging.debug("="*80)
        # logging.warn("PRE MSG: %s" % (msg,))
        self.cache = {}
        self.count = 0
        return msg
        
    def pre_bulk_process( self, time, meta, context, data ):
        # get a unique key for this message (and ideally all subsequent 'same' messages)
        self.current_table_name = '%s:%s' % (meta['spec'],meta['group'])
        logging.debug("current table: %s" % (self.current_table_name,))
        if self.current_table_name in self.storage_options:
            self.key_template = Template( self.storage_options[self.current_table_name]['key'] )
            self.current_opts = self.storage_options[self.current_table_name]
            return True
        return False
        
    def post_bulk_process( self, time, meta, context, data ):
        # do some redis batch pipelines?
        self.pipe.execute()

        
    def post_msg_process( self ):
        # commit pipe
        logging.debug("count: %s" % (self.count,))
        yield None, None

    def save( self, time, meta, ctx, data, time_delta ):

        # method = self.current_opts['method'] if 'method' in self.current_opts else 'hmset'
        
        # reverse device
        if 'device' in ctx:
            ctx['device'] = '.'.join( reversed(ctx['device'].split('.')) )
        
        # sub key
        this_key = self.key_template.substitute( dict(ctx.items() + data.items()) )
        this_data = dict( {'updated_at': time }.items() + data.items() )

        full_key = '%s:%s' % (self.key_prepend,this_key)
        # k = '%s:%s:%s' % (self.key_prepend, self.current_table_name, self.get_key( ctx ) )
        self.pipe.hmset( full_key, this_data )
        if 'expire' in self.current_opts:
            logging.debug("expire in %s" % (self.current_opts['expire'],))
            self.pipe.expire( full_key, self.current_opts['expire'] )

        logging.debug("k=%s\tc=%s\td=%s" % (this_key,ctx,this_data))

        self.count = self.count + 1
        return None



class Redis( StorageCommand ):
    """
    redis storage daemon
    """
    worker = RedisStorer

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        super( Redis, cls ).create_parser( parser, settings, parents=parents )

        parser.add_argument( '-p', '--pool', help='pool name', default=settings.POOL )
        parser.add_argument( '-k', '--keys', help='key name', action='append', default=DefaultList(settings.KEYS) )

        parser.add_argument( '--cache_host', help='redis cluster members', default=DefaultList(settings.CACHE_HOST) )
        parser.add_argument( '--storage_options', help='store settings', default=settings.STORAGE_OPTIONS )