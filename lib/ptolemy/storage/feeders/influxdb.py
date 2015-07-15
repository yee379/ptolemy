from slac_utils.statistics_feeder import CarbonFeeder, MultiCarbonFeeder
from slac_utils.command import ManagerDaemon, CommandDaemon, DefaultList

from slac_utils.time import utcfromtimestamp, sleep, delta

from ptolemy.storage.feeders import Feeder
from ptolemy.storage.commands import StorageCommand

try:
    from setproctitle import setproctitle 
except:
    def setproctitle(blah):
        pass

from slac_utils.time import now

from json import dumps
from urllib2 import urlopen
from urllib import urlencode
import logging
from pprint import pformat
import traceback
from random import choice

def get_key( meta, context ):
    this = context.copy()
    this['group'] = meta['group']
    keys = []
    for k in sorted(this.keys()):
        keys.append( "%s=%s" % (k,this[k],) )
    # key, should probably try to merge in group into sorted list above
    return "%s,%s" % ( meta['spec'], ','.join(keys) )

def get_data( data ):
    # append other context items
    def parse(x):
        try:
            a = float(x)
            # b = int(a)
        except ValueError:
            return '"%s"' % x
        return a
        # if a == b:
        #     return b
        # else:
        #     return a
    out = []    
    for k,v in data.iteritems():
        out.append('%s=%s' % (k,parse(v)) )
    return ','.join(out)

def calc_time( ts ):
    return "%.3f" % float( (float(ts.microseconds) + float(ts.seconds*1000000))/1000000 )

class InfluxDbStorer( Feeder ):
    
    agent = 'influxdb'
    key_prepend = '.'

    proc_name = 'ptolemy stored influxdb'
    timestamp_to_datetime = False

    # prevent memory management
    memory_multiply_threshold = None

    # number of entries to send at once to server
    chunks = 100
    retry_chunks = 10
    current_chunks = chunks
    data_cache = []

    instances = []
    dbname = ''
    user = 'ptolemy'
    password = 'ptolemy'
     
    def setup(self,**kwargs):
        super( InfluxDbStorer, self).setup(**kwargs) 
        if len( self.instances ) == 0:
            raise Exception( 'need influx endpoints defined under influxdb_instances' )
        # logging.error("BLAH i=%s, c=%s, n=%s, u=%s, p=%s" % (self.instances,self.chunks,self.dbname,self.user,self.password))
    
        
    def save( self, time, meta, context, data, time_delta=None ):
        # logging.debug("> %s\t%s - %s\t%s\t%s" % (self.instances, meta, context, time, data))
        ts = { 'start': now() }
        
        # reformat ata into influx format
        this = '%s %s %s' % (get_key(meta,context),get_data(data),int(time))
        logging.debug("+ %s" % (this,))
        self.data_cache.append( this )

        if len( self.data_cache ) >= self.current_chunks:
            # logging.debug( "  - %s" % (encoded,))
            server = choice(self.instances)
            c = 'http://%s/write?db=%s&u=%s&p=%s&precision=%s' % ( server, self.dbname, self.user, self.password, 's' )
            # logging.info("sending %s to %s" % (len(self.data_cache),c))

            ts['caching'] = now()

            resp = urlopen( c, '\n'.join(self.data_cache) )
            code = resp.getcode()
            code = 200

            n = len(self.data_cache)

            if code == 200:
                self.data_cache = []
                self.current_chunks = self.chunks
            else:
                logging.warn("  >: %s: %s" % (code,resp.read()))
                self.current_chunks = self.chunks + self.retry_chunks

            ts['sending'] = now()

            logging.info("%s sent %s datapoints (processing %.3fsec, sending %.3fsec)" % (server, n, delta(ts['start'],ts['caching']), delta(ts['caching'],ts['sending']) ) )

    
class Influxdb( StorageCommand ):
    """
    influxdb storage daemon
    """
    worker = InfluxDbStorer

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        super( Influxdb, cls ).create_parser( parser, settings, parents=parents )

        parser.add_argument( '-p', '--pool', help='pool name', default=settings.POOL )
        parser.add_argument( '-k', '--keys', help='key name', action='append', default=DefaultList(settings.KEYS) )

        influx = parser.add_argument_group( 'influxdb settings')
        influx.add_argument( '-i', '--influxdb_instances', help='influxdb instance endpoints', action="append", default=settings.INFLUXDB_INSTANCES )
        influx.add_argument( '-n', '--influxdb_dbname', help='influxdb dbname', default=settings.INFLUXDB_DBNAME )
        influx.add_argument( '-u', '--influxdb_user', help='influxdb username', default=settings.INFLUXDB_USER )
        influx.add_argument( '-P', '--influxdb_password', help='influxdb password', default=settings.INFLUXDB_PASSWORD )
        influx.add_argument( '-c', '--influxdb_chunks', help='influxdb chunk threshold', type=int, default=settings.INFLUXDB_CHUNKS )
        