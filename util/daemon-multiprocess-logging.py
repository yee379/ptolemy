
import time
import random
import logging
from logging.handlers import TimedRotatingFileHandler

from daemon import DaemonContext

import multiprocessing
import threading


class MultiProcessingLogHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self)

        self._handler = TimedRotatingFileHandler(*args, **kwargs)
        self.queue = multiprocessing.Queue(-1)

        self.stream = self._handler.stream

        t = threading.Thread(target=self.receive)
        t.daemon = True
        t.start()

    def setFormatter(self, fmt):
        logging.Handler.setFormatter(self, fmt)
        self._handler.setFormatter(fmt)

    def receive(self):
        while True:
            try:
                record = self.queue.get()
                self._handler.emit(record)
            except (KeyboardInterrupt, SystemExit):
                raise
            except EOFError:
                break
            except:
                traceback.print_exc(file=sys.stderr)

    def send(self, s):
        self.queue.put_nowait(s)

    def _format_record(self, record):
        # ensure that exc_info and args
        # have been stringified.  Removes any chance of
        # unpickleable things inside and possibly reduces
        # message size sent over the pipe
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        if record.exc_info:
            dummy = self.format(record)
            record.exc_info = None

        return record

    def emit(self, record):
        try:
            s = self._format_record(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        self._handler.close()
        logging.Handler.close(self)


class MyDaemon( DaemonContext ):

    def start( self, *args, **options ):

        with self as s:

            # init logger
            ch = MultiProcessingLogHandler('/tmp/log', when='midnight', backupCount=7 )
            ch.setFormatter( logging.Formatter('%(asctime)s %(levelname)s\t%(message)s') )

            LOG = logging.getLogger('')
            LOG.setLevel( logging.DEBUG )
            LOG.addHandler(ch)

            LOG.warn("STARTING")

            w = []
            while True:

                logging.info("main thread %s" % (s,))
                time.sleep( 2 )

                # initiate only once
                if len(w) == 0:
                    for x in xrange(0,2):
                        logging.info('spawning %s' % (x,))
                        this = Worker()
                        this.start()
                        w.append( this )


class Worker( multiprocessing.Process ):
    
    def run(self):
        while 1:
            i = random.randrange(2)
            logging.info( '%s: sleeping %s' % (self,i) )
            time.sleep( i )


if __name__ == '__main__':
    
    d = MyDaemon()
    d.start()
        
    