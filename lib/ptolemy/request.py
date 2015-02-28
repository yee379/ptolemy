from slac_utils.request import Request
from ptolemy.queues import QueueFactory

class PollRequest( Request ):
    queue_factory = QueueFactory
    submission_queue = 'poll'
    result_queue = 'store'
    logging_queue = ''

