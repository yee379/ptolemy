import logging 
# from ptolemy_py.util.queues import KombuQueueFactory as QueueFactory
from ptolemy_py.util.queues import KombuMultiConnectionFactory as QueueFactory

class QueueHandler( logging.Handler ):
    """
    simple wrapper for logging handler to provided queue object; use the routing key for pub/sub
    """
    queue = None
    
    def __init__( self, queue=None ):
        if queue == None:
            f = QueueFactory()
            queue = f.logging_queue
            pass
        self.queue = queue
        logging.Handler.__init__(self)
    
    def _routingKey(self, r):
        return r.levelname.lower() + '.' + r.name
    
    def emit(self, record):
        # determine routing key
        self.queue.put( { 'date': record.asctime, 
                    'level': record.levelname, 
                    'message': record.message, 
                    'function': record.funcName, 
                    'name': record.name, 
                    'lineno': record.lineno }, key=self._routingKey(record) )
        