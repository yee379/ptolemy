from kombu.connection import BrokerConnection
from kombu.messaging import Exchange, Producer, Consumer
import kombu.messaging

from uuid import uuid1 as uuid
from itertools import count

from Queue import Queue as StandardQueue, Empty
from multiprocessing import Queue as MultiProcessingQueue

import socket
from time import sleep

import logging


class Queue( object ):
    """
    dumb class to spit out jobs to be done
    this instance just wraps around the python queue object
    """
    is_publisher = None
    is_consumer = None
    
    def __init__(self):
        self.is_publisher = False
        self.is_consumer = False
        self.q = MultiProcessingQueue()
    
    def initPublisher( self ):
        self.is_publisher = True
        pass
    
    def initConsumer( self ):
        self.is_consumer = True
        pass
    
    def put( self, item ):
        if self.is_publisher == False:
            self.initPublisher()
        # logging.warn("putting " + str(item) )
        self.q.put( item )

    def get( self, non_blocking=True ):
        if self.is_consumer == False:
            self.initConsumer()
        # logging.warn( "getting " + str(key) )
        try:
            return self.q.get( non_blocking )
        except Empty, e:
            pass
        return None

    def consume( self, callback, maintainence_callback=None, maintainence_period=5 ):
        """
        continuously get items from the queue and work on it
        """
        while True:
            logging.debug("consuming")
            item = self.q.get()
            logging.debug('got')
            callback( item, None )
            self.task_done()

    def qsize( self ):
        return self.q.qsize()
        
    def task_done( self ):
        pass


class KombuQueue( Queue ):

    end_marker = '===END==='

    def __init__( self, consumer=None, publisher=None, connection=None, channel=None ):
        if consumer == None and publisher == None:
            raise SyntaxError, 'kombu queue must have attached consumer or producer'
        self.consumer = consumer
        self.publisher = publisher
        self.is_publisher = False
        self.is_consumer = False
        # stupid kombu connection is required to drain queue
        self.connection = connection
        self.channel = channel
        self.continue_consuming = True

    def put( self, msg, key=None ):
        # logging.debug("putting " + str(msg) + ', with key=' + str(key))
        self.publisher.publish( msg, routing_key=key )

    def end( self, key=None ):
        self.put( self.end_marker, key=key )
    
    def get( self, non_blocking=False, until=None, wait_time=0.1 ):
        """ header/footer is to text around each item (for html generator etc), item """
        if until == None: until = self.end_marker
        for c in count():
            m = self.consumer.queues[0].get( non_blocking )
            if not m == None:
                if not m.payload == until:
                    yield m.payload
                else:
                    break
            else:
                # logging.debug("queue sleeping")
                sleep(wait_time)
        return

    def consume( self, callback ):
        logging.debug('consuming on ' + str(self.consumer) + ', with callback ' + str(callback))
        self.consumer.register_callback( callback )
        self.consumer.consume()
        while self.continue_consuming:
            logging.debug('consuming...')
            self.connection.drain_events()

    def qsize( self ):
        """
        consuming queue size only
        """
        q = self.consumer.queues[-1]
        logging.debug("determining qsize of " + str(q) + ' as ' + str(None))

        _, size, _ = q.queue_declare(passive=True)
        return size

class KombuQueueFactory(object):
    """
    bootstrap for kombuqueue
    """
    def __init__( self, 
            host=None, port=None, 
            virtual_host=None, 
            user=None, password=None,
            max_connections=0, max_channels=0 ):

        try:
            from django.conf import settings
        except:
            pass

        self.host = host or settings.BROKER_HOST
        self.port = port or settings.BROKER_PORT
        self.virtual_host = virtual_host or settings.BROKER_VHOST
        self.user = user or settings.BROKER_USER
        self.password = password or settings.BROKER_PASSWORD

        self.connection = BrokerConnection( hostname=self.host, port=self.port, virtual_host=self.virtual_host,
                    userid=self.user, password=self.password )
        logging.debug("kombu connection with " + str(self.connection))

        self.channel_pool = self.connection.ChannelPool(max_connections)
        self.connection_pool = self.connection.Pool(max_channels)

        self.exchanges = {}
    
    def _exchange( self,  name='', type='direct', durable=True, delivery_mode=1 ):
        if not name in self.exchanges:
            self.exchanges[name] = Exchange( name, type=type, durable=durable, delivery_mode=delivery_mode )
        return self.exchanges[name]
    
    def _queueName( self, qname, pool, key ):
        # we want pool members to load balance the workers, so if there is no pool defined
        # then we should generate a unique id
        name = qname + '.' + str(pool) + '.' + key
        return name
    
    def _consumer( self, exchange=None, queue_names=[], pool=None, key='#', channel=None, auto_delete=True ):
        # logging.debug('construct poll queue consumer')
        queues = []
        for qname in queue_names:
            name = self._queueName( qname, pool, key )
            # as we are typically sharing the queue between a bunch of workers (instantiated from teh manager)
            # an exclusive queue actually means an auto_delete queue as it's not in a pool
            q = kombu.messaging.Queue( name, exchange, key, auto_delete=auto_delete )
            logging.debug("created queue: " + str(q) + " del: " + str(auto_delete))
            queues.append(q)
        consumer = Consumer( channel, queues )
        consumer.declare()
        return consumer
    
    def _producer( self, exchange=None, channel=None ):
        # logging.debug('construct poll queue prod')
        publisher = Producer( channel, exchange=exchange )
        publisher.declare()
        return publisher
    
    def construct( self, 
            exchange_name='', queue_name='', type='direct', 
            pool=None, key='#', 
            connection=None, channel=None, auto_delete=True,
            consume=False, produce=False ):
        """
        pool is a unique string that faciliates the round-robin task sharing of the queue
        """
        ex = self._exchange( name=exchange_name, type=type, durable=True )
        consumer = None
        if consume: 
            qnames = []
            qnames.append( queue_name )
            if pool == None:
                pool = uuid()
            consumer = self._consumer( exchange=ex, queue_names=qnames, pool=pool, key=key, channel=channel, auto_delete=auto_delete )
        publisher = None
        if produce: publisher = self._producer( exchange=ex, channel=channel )
        return publisher, consumer

    def getConnection(self):
        return self.connection
        
    def getChannel(self,connection):
        return self.channel_pool.acquire()


class KombuMultiConnectionFactory( KombuQueueFactory ):
    """
    something wrong with kombu with one conneciton and many channels, so in this we use one channel per connection
    """
    
    def getConnection(self):
        acq = None
        try:
            acq = self.connection_pool.acquire()
        except:
            raise Exception, "could not connect to queue at " + str(self.connection)
        return acq
    
    def getChannel(self, connection):
        return connection.channel()


class PtolemyQueueFactory( KombuMultiConnectionFactory ):
    """
    queues for ptolemy services
    """

    def poll_queue( self, pool=None, key='#', consume=False, produce=False, auto_delete=True ):
        """
        clients should never put things directly into the poll queue; they should go through poll_request_queue
        so that the scheduler may rate limit the requests
        """
        conn = self.getConnection()
        chan = self.getChannel( conn )
        if pool == None:
            pool = uuid()
        p, c = self.construct( exchange_name='ptolemy.poll', queue_name='task.poll', type='topic', 
                pool=pool, key=key, 
                connection=conn, channel=chan, auto_delete=auto_delete,
                consume=consume, produce=produce )
        return KombuQueue( consumer=c, publisher=p, connection=conn, channel=chan )

    def poll_request_queue( self, pool=None, key='#', consume=False, produce=False, auto_delete=True ):
        conn = self.getConnection()
        chan = self.getChannel( conn )
        p, c = self.construct( exchange_name='ptolemy.poll_request', queue_name='task.request', type='topic', 
                pool=pool, key=key, 
                connection=conn, channel=chan, auto_delete=auto_delete,
                consume=consume, produce=produce )
        return KombuQueue( consumer=c, publisher=p, connection=conn, channel=chan )    

    def store_queue( self, pool=None, key='#', consume=False, produce=False, auto_delete=True ):
        conn = self.getConnection()
        chan = self.getChannel( conn )
        p, c = self.construct( exchange_name='ptolemy.store', queue_name='task.store', type='topic', 
                pool=pool, key=key,
                connection=conn, channel=chan, auto_delete=auto_delete,
                consume=consume, produce=produce )
        return KombuQueue( consumer=c, publisher=p, connection=conn, channel=chan )

    def logging_queue( self, pool=None, key='#', consume=False, produce=False, auto_delete=True ):
        conn = self.getConnection()
        chan = self.getChannel( conn )
        p, c = self.construct( exchange_name='ptolemy.log', queue_name='log.item', type='topic', 
                pool=pool, key=key,
                connection=conn, channel=chan, auto_delete=auto_delete,
                consume=consume, produce=produce )
        return KombuQueue( consumer=c, publisher=p, connection=conn, channel=chan )


class ProvisionQueueFactory( KombuMultiConnectionFactory ):
    """
    queues for provision server
    """
    
    def provision_request_queue( self, pool=None, key='#', consume=False, produce=False, auto_delete=True ):
        conn = self.getConnection()
        chan = self.getChannel( conn )
        p, c = self.construct( exchange_name='provision.request', queue_name='provision.request', type='topic', 
                pool=pool, key=key, 
                connection=conn, channel=chan, auto_delete=auto_delete,
                consume=consume, produce=produce )
        return KombuQueue( consumer=c, publisher=p, connection=conn, channel=chan )

    def provision_response_queue( self, pool=None, key='#', consume=False, produce=False, auto_delete=True ):
        conn = self.getConnection()
        chan = self.getChannel( conn )
        p, c = self.construct( exchange_name='provision.response', queue_name='provision.response', type='topic', 
                pool=pool, key=key, 
                connection=conn, channel=chan, auto_delete=auto_delete,
                consume=consume, produce=produce )
        return KombuQueue( consumer=c, publisher=p, connection=conn, channel=chan )



class RPC( object ):
    """
    simple rpc object that enables communcation and processing of data
    """
    
    def __init__(self):
        self.cmd = Queue()
        self.result = Queue()
        logging.error("SELF: " + str(self))
    
    def __repr__(self):
        return ("<RPC Object, with cmd: " + str(self.cmd) + ", result: " + str(self.result))
    
    def close(self):
        pass
    
    def request( self, item ):
        self.cmd.put( item )
        logging.error("REQUESTING: " + str(item))
        return self.result.get()

    def wait(self):
        return self.cmd.get()

    def respond( self, item ):
        logging.error("RESPONDING: " + str(self.result))
        return self.result.put( item )
    
