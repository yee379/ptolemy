
import unittest
import logging

import ptolemy.storage.feeders.postgres
from ptolemy.queues import QueueFactory
import psycopg2

from datetime import datetime

from copy import deepcopy
from hashlib import md5


def modulo( string, number ):
    m = md5()
    m.update( string )
    v = long(m.hexdigest(),16) % number
    return v


class PostgresHashingTest( unittest.TestCase ):
    
    def setUp( self ):
        self.feeder = ptolemy.storage.feeders.postgres.PostgresStorer( 'blah' )
        self.feeder._setup( \
            partitions=[ { 'spec': 'caching', 'group': 'hosts', 'field': 'mac_address', 'modulo': 128 } ], \
            pre_msg_process=[ { 'spec': 'caching', 'group': 'hosts', 'fields': ['mac_address','vlan'], 'fields_missing_ok': True }  ],
            post_msg_process=[ { 'spec': 'caching', 'group': 'hosts' }, ] )


    def test_input(self):
        msg = {'_meta': {'delayed_context': ['ip_address'],
                'group': 'hosts',
                'key': '.spec.caching.group.hosts.',
                'key_name': ['mac_address', 'vlan'],
                'merge_context': True,
                'merge_data': True,
                'spec': 'caching',
                'task_id': None,
                'type': 'task' },
            'context': {'mac_address': 'd4be.d951.2cd0', 'vlan': 32},
            'data': {'device': 'swh-ssrlb137ej5.slac.stanford.edu', 'physical_port': 'Gi1/0/20'},
            'timestamp': datetime.now() }
            
        self.assertEqual( self.feeder._table_name( msg['_meta']['spec'], msg['_meta']['group'] ), 'caching__hosts' )

        table, parent = self.feeder.table_name( msg['_meta']['spec'], msg['_meta']['group'], msg['context'], msg['data'] )
        self.assertEqual( parent, 'caching__hosts' )
        
        # work out hash
        h = modulo( msg['context']['mac_address'], 128 )
        # h = 15
        self.assertEqual( table, 'caching__hosts__mac_address%s' % (h,) )

        # try built in
        queries, tree = self.feeder.hash_pre_msg_process( [ msg, ], parent )
        logging.error("CTXS %s" % (queries,))
        logging.error("TREE %s" % (tree,))

        self.assertEqual( queries.keys().pop(0), table )


class PostgresCachingTest( unittest.TestCase ):
    
    @classmethod
    def test_01_create_feeder(self):
        queue_factory = QueueFactory( host=[ 'net-amqp02.slac.stanford.edu:5672', ], vhost='/ptolemy', user='ptolemy', password='ptolemy' )
        self.feeder = ptolemy.storage.feeders.postgres.PostgresStorer( queue_factory, work_queue_func='store' )        
        self.feeder.setup( postgres_username='ptolemy', postgres_password='ptolemy', postgres_database='ptolemy_production', postgres_host='net-graphite01', postgres_port=5432, \
            partitions=[ { 'spec': 'caching', 'group': 'hosts', 'field': 'mac_address', 'modulo': 128 } ], \
            pre_msg_process=[ { 'spec': 'caching', 'group': 'hosts', 'fields': ['mac_address','vlan'], 'fields_missing_ok': True }  ],
        post_msg_process=[ { 'spec': 'caching', 'group': 'hosts' }, ] )

    def test_02_connect(self):
        self.feeder.connect()
        self.assertTrue( isinstance( self.feeder.cur, psycopg2.extras.RealDictCursor ) )
    
    def test_03_pre_msg( self ):
        # t = 1421914870.0
        t = datetime.now()
        msgs = [
            {'_meta': {'delayed_context': ['ip_address'],
                'group': 'hosts',
                'key': '.spec.caching.group.hosts.',
                'key_name': ['mac_address', 'vlan'],
                'merge_context': True,
                'merge_data': True,
                'spec': 'caching',
                'task_id': None,
                'type': 'task' },
            'context': {'mac_address': 'd4be.d951.2cd0', 'vlan': 32},
            'data': {'device': 'swh-ssrlb137ej5.slac.stanford.edu', 'physical_port': 'Gi1/0/20'},
            'timestamp': t },
        ]
        # msgs = [
        #     {'_meta': {'delayed_context': ['ip_address'],
        #                'group': 'hosts',
        #                'key': '.spec.caching.group.hosts.',
        #                'key_name': ['mac_address', 'vlan'],
        #                'merge_context': True,
        #                'merge_data': True,
        #                'spec': 'caching',
        #                'task_id': None,
        #                'type': 'task'},
        #      'context': {'mac_address': '0013.8081.87c0'},
        #      'data': {'ip_address': '134.79.253.74'},
        #      'timestamp': t },
        # ]

        m = msgs[0]

        h = modulo( m['context']['mac_address'], 128 )
        # logging.error("H: %s" % (h,))

        # logging.error("THIS: %s" % (msgs,))
        self.feeder.pre_msg_process( msgs, None )
        cache_before = deepcopy( self.feeder.cache )
        # logging.error("CACHE: %s" % (self.feeder.cache.keys(),))

        # pre bulk
        self.feeder.pre_bulk_process( t, m['_meta'], m['context'], m['data'] )
        # logging.error("H2: %s" % (self.feeder.table,))
        self.assertTrue( self.feeder.table.endswith(str(h)) )
        
        # should not fetch and add to the cache
        cache_after = deepcopy( self.feeder.cache )
        logging.error("CACHE2: %s" % (self.feeder.cache.keys(),))
        self.assertEquals( cache_before, cache_after )
        
        self.feeder.save( t, m['_meta'], m['context'], m['data'], 0 )


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
