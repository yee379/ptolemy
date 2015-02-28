#!/bin/env python

"""
simple script to test rabbitmq libraries and message filtering
"""
import sys
import logging


import ptolemy.queues
from slac_utils.managers import Worker, Supervisor, FanOutManager


class TestWorker( Worker ):
    def process_task( self, msg, stats={}, **kwargs ):
        # logging.error("--- %s" % (msg,))
        pass

class TestSupervisor( Supervisor ):
    def validate_task( self, job ):
        # logging.error("+++ %s "% job)
        return job

class TestManager( FanOutManager ):
    queue_factory = ptolemy.queues.QueueFactory
    worker = TestWorker
    supervisor = TestSupervisor
    
    work_queue_func = 'poll'
    results_queue_func = None
    
    
def just_worker( pool='default', keys=['#'] ):
    """
    initiate just a worker
    """
    # queue factory
    fac = ptolemy.queues.QueueFactory( host='net-amqp01.slac.stanford.edu', port=5672, virtual_host='/ptolemy', userid='ptolemy', password='ptolemy' )    
    # create worker to consume from queue
    w = TestWorker( fac, work_queue_func='poll', pool=pool, keys=keys )
    w.start()

def just_manager( pool='default', keys=['#'] ):
    """
    use manager
    """
    m = TestManager( host='net-amqp01.slac.stanford.edu', port=5672, virtual_host='/ptolemy', user='ptolemy', password='ptolemy' )
    m.start( pool=pool, keys=keys )
    
    
if __name__ == "__main__":
    
    logging.basicConfig( level=logging.DEBUG )
    
    keys = sys.argv
    keys.pop(0)
    logging.error("listening on %s" % (keys,))
    
    just_manager( keys=keys )
    
