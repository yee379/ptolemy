from slac_utils.queues import PyAmqpLibQueueFactory, PyAmqpLibQueue, PyAmqpLibMultiQueue

import logging


class QueueFactory( PyAmqpLibQueueFactory ):
    
    queue_options = {
        'host':   None,
        'port':   None,
        'virtual_host':  '/ptolemy/',

        'userid': None,
        'password': None,
    
        'exchange_name': 'ptolemy',
        'queue_name' : '',
        'pool': 'ptolemy',
        #        'queue_arguments': { 'x-ha-policy':'all' }  # only needed for rabbitmq < 3.0
    }


    def poll( self, **kwargs ):
        """
        queue for polling request
        """
        return self.get_queue( 'poll', 'topic', **kwargs )

    def supervised_poll( self, **kwargs ):
        """
        work queue for polling requests
        """
        return self.get_queue( 'supervised_poll', 'topic', **kwargs )

    def store( self, **kwargs ):
        """
        queue for storage requests
        """
        return self.get_queue( 'store', 'topic', **kwargs )

    def supervised( self, **kwargs ):
        """
        generic supervised queue
        """
        return self.get_queue( 'supervised', 'topic', **kwargs )
        
    def supervised_poll( self, **kwargs ):
        return self.get_queue( 'supervised_poll', 'topic', **kwargs )

    def log( self, **kwargs ):
        return self.get_queue( 'log', 'fanout', **kwargs )
        
    def supervised_store( self, **kwargs ):
        return self.get_queue( 'supervised_store', 'direct', **kwargs )

    def supervised_watcher( self, **kwargs ):
        return self.get_queue( 'supervised_watcher', 'direct', **kwargs )
        
    def watcher( self, **kwargs ):
        """
        multi queue that listens on both generic and own specific queue
        """
        return PyAmqpLibMultiQueue( 
            { 'exchange': 'poll', 'keys': (['#.spec.layer3.group.subnets.#']) },
            { 'exchange': 'watcher', 'keys': ( kwargs['keys'] ) },
            **dict( self.queue_options.items() + kwargs.items() )
        )
        
    def schedule( self, **kwargs ):
        return self.get_queue( 'schedule', 'direct', **kwargs )
        
    def capacity(self, **kwargs):
        """
        queue for capacity analysis
        """
        return self.get_queue( 'capacity', 'direct', **kwargs )
        
    def alert( self, **kwargs ):
        """
        queue for notification alerts
        """
        return self.get_queue( 'alert', 'direct', format='json', **kwargs )