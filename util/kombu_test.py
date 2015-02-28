from django.core.management.base import BaseCommand, CommandError
from django.http import HttpRequest
from optparse import make_option

from django.conf import settings
from kombu.messaging import Exchange, Queue, Consumer
from kombu.connection import BrokerConnection
# from ptolemy_py.scheduler.queues import Connection
from multiprocessing import Process, Pool

from time import sleep

import sys
import traceback
import logging


logging.basicConfig( level=logging.DEBUG, format='%(levelname)-8s %(message)s' )

class worker( Process ):
    def __init__(self, consumer ):
        self.consumer = consumer
        super(worker,self).__init__()
    def run(self):
        logging.debug("running")
        self.consumer.register_callback(self.do)
        self.consumer.consume()
    def do(self, msg_data, msg):
        print "do something with " + str(msg_data)
        msg.ack()

class Command(BaseCommand):
    
    def handle(self, *args, **options):

        try:
            
            conn = BrokerConnection( host='sccs-ytl.slac.stanford.edu', port=5672, virtual_host='/ptolemy', userid='ptolemy', password='ptolemy')
            chan_pool = conn.ChannelPool(2)

            # channel_pool = c.ChannelPool(limit=None)
            ex = Exchange( 'ptolemy.poll', 'topic', durable=True )
            q = Queue( "q", exchange=ex, key='#' )
            
            workers = []
            for i in xrange(2):
                c = chan_pool.acquire()
                consumer = Consumer( c, q )
                w = worker( consumer=consumer )
                w.start()
                workers.append(w)

            while True:
                conn.drain_events()
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback, limit=3, file=sys.stdout)

        
        logging.info( "success!")
        sys.exit(0)

