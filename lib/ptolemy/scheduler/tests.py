"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from scheduler import Schedule, ScheduleParser, Scheduler
# from util import Queue, KombuQueue

# from Queue import Empty

from models import Message, PollObject

import logging
logging.basicConfig( level=logging.DEBUG )

class ScheduleTest(TestCase):

    def setUp(self):
        self.sched = Schedule()
        
    
    def test_instantiation(self):
        self.assertEqual( type(self.sched).__name__, 'Schedule' )
    
    def test_add_pop(self):
        self.sched.add( '1.5', { 'a': 'C', 'b': 'D' } )
        self.sched.add( '1.0', { 'a': 'A', 'b': 'B' } )
        self.sched.add( '1.9', { 'a': 'E', 'b': 'F' } )
        for i in xrange(0,3):
            t, d = self.sched.pop()
            logging.debug("t: " + str(t) + ", d: " + str(d) )


class ScheduleParserTest(TestCase):
    
    parser = None
    
    def setUp(self):
        d = '/afs/slac.stanford.edu/package/netmon/lanmon/ptolemy_py/etc/'
        self.parser = ScheduleParser( node_confs=[ d + 'nodes-campus.conf' ], snmp_conf=d+'snmp.conf', schedule_conf=d+'schedule.conf' )
        self.assertEqual( type(self.parser).__name__, 'ScheduleParser' )
        
    # def test_instantiation(self):
        

    def test_delta_single(self):
        t = self.parser.delta( '500' )
        self.assertEqual( t, float('500') )
        

    def test_delta_tuple(self):
        t = self.parser.delta( '500 +- 4' )
        mn = 496
        mx = 504
        # logging.debug("t: " + str(t))
        self.assertEqual( t > mn and t < mx , True )
    
    def test_delta_tuple_loop(self):
        for i in xrange(0,100):
            self.test_delta_tuple()
            
    def test_getNode_good(self):
        n = self.parser.getNode('swh-b050f1.slac.stanford.edu')
        # logging.debug("node: " + str(n) + ", " + str(type(n)))
        self.assertEqual( type(n).__name__, 'dict')
        
    def test_getSpecs(self):
        n = self.parser.getNode('swh-b050f1.slac.stanford.edu')
        l = self.parser.getSpecs( n )
        self.assertEqual( l, [ 'environment', 'performance', 'spanningtree', 'entity' ] )
        
    def test_getSnmp(self):
        n = self.parser.getNode('swh-b050f1.slac.stanford.edu')
        l = self.parser.getSnmp( n )
        self.assertEqual( l, [ 'retries', 'community', 'version', 'timeout', 'community_path', 'port' ] )
        
    def test_initSchedule(self):
        self.parser.initSchedule()
        
    def test_pop( self ):
        self.parser.initSchedule()
        for i in xrange(0,5):
            this, that = self.parser.next()
            logging.debug("THIS: "+ str(this) + ", THAT: " + str(that))
            


class ScheduleManagerTest(TestCase):

    manager = None
    def setUp( self ):
        d = '/afs/slac.stanford.edu/package/netmon/lanmon/ptolemy_py/etc/'
        self.manager = ScheduleManager( node_confs=[ d + 'nodes-campus.conf' ], snmp_conf=d+'snmp.conf', schedule_conf=d+'schedule.conf' )

    def test_init(self):
        self.assertEqual( type(self.manager).__name__, 'ScheduleManager' )

    def test_start( self ):
        self.manager.start()

# 
# 
# class PikaTest( TestCase ):
# 
#     def test_init(self):
#         params = pika.ConnectionParameters('127.0.0.1')
#         self.connection = pika.AsyncoreConnection(  )
#         self.channel = self.connection.channel()
#         exchange_name='blah'
#         self.channel.exchange_declare( exchange=exchange_name, type="fanout", durable=False, auto_delete=False )



class QueueTest( TestCase ):
    
    def test_init( self ):
        q = Queue()
        self.assertEqual( type(q).__name__, 'Queue')
        
    def test_putget( self ):
        q = Queue()
        i = {'message':'hello there'}
        q.put( i )
        m = q.get()
        self.assertEqual( m, i )
        
        
class KombuQueueTest( TestCase ):
    
    def test_init( self ):
        q = KombuQueue()
        self.assertEqual( type(q).__name__, 'KombuQueue' )
        
    def test_putget( self ):
        q = KombuQueue()
        i = { 'message': 'hello world' }
        q.put( i )
        m = q.get()
        self.assertEqual( m, i )
        
    # def test_empty( self ):
    #     q = KombuQueue()
    #     while True:
    #         try:
    #             m = q.get()
    #         except Empty, e:
    #             # good
    #             self.assertEqual( 1, 1 )
    
    
class MessageTest(TestCase):
    def test_set(self):
        m = Message()
        t = 'hello'
        m.device = t
        self.failUnlessEqual( m.device, t )
        
class PollObjectTest(TestCase):
    def setUp(self):
        self.m = PollObject()
        self.failUnlessEqual( type(self.m).__name__, 'PollObject' )
        
    def test_new(self):
        t = 'this'
        m = PollObject( device=t )
        self.failUnlessEqual( m.device, t )
        
