
from time import sleep
import random
import logging
import slac_utils.logger

import multiprocessing


class Worker( multiprocessing.Process ):
    
    def run(self):
        # logger = logging.getLogger('')
        # print "LOGGER: %s" % (logger,)
        while 1:
            i = random.randrange(2)
            print "going.."
            logging.info( 'hello %s: sleeping %s' % (self,i) )
            sleep( i )


if __name__ == '__main__':
    
    h = slac_utils.logger.MultiProcessingHandler( '/tmp/test2.log', 'a' )
    # h = logging.FileHandler('/tmp/test2.log')
    h.setFormatter( logging.Formatter('%(message)s') )

    LOG = logging.getLogger('')
    LOG.setLevel( logging.DEBUG )
    LOG.addHandler(h)

    w = []
    LOG.debug('starting...')
    for x in xrange(0,2):
        this = Worker()
        LOG.warn("writing...")
        this.start()
        w.append( this )
        
    