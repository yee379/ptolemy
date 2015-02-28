from slac_utils.command import Daemon
import multiprocessing
import time
import logging
import random

class MyDaemon( Daemon ):
    def run(self, *args, **kwargs ):
        w = []
        while True:
            logging.info("main")
            time.sleep( 2 )

            if len(w) == 0:
                for x in xrange(0,2):
                    logging.info('spawning %s' % (x,))
                    this = Worker()
                    this.start()
                    w.append(this)
                    
class Worker( multiprocessing.Process ):
    
    def run(self):
        while 1:
            i = random.randrange(2)
            logging.info( '%s: sleeping %s' % (self,i) )
            time.sleep( i )
            
if __name__ == '__main__':
    d = MyDaemon()
    d.start( log_file='/tmp/log2' )