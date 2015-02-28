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

def get_key( meta, context, key_prepend='' ):
    if 'carbon_key' in meta:
        return meta['carbon_key']
    # remap device to reverse notation
    device = ".".join( reversed( context['device'].split('.')) )
    # append other context items
    keys = []
    for k in sorted(context.keys()):
        if not k in ( 'device', ):
            keys.append( "%s" % (context[k],) )
    # key
    key = "%s%s.%s.%s.%s" % (key_prepend, device, meta['spec'], meta['group'], '.'.join(keys) )
    return key.replace('/','.')

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
    data_cache = []

    instances = []
    dbname = ''
    user = 'root'
    password = 'root'
     
    def setup(self,**kwargs):
        super( InfluxDbStorer, self).setup(**kwargs) 
        if len( self.instances ) == 0:
            raise Exception( 'need influx endpoints defined under influxdb_instances' )
        # logging.error("BLAH i=%s, c=%s, n=%s, u=%s, p=%s" % (self.instances,self.chunks,self.dbname,self.user,self.password))
    
    def get_instance_string(self):
        # 'http://172.23.52.10:8086/db/test_db/series?u=root&p=root'
        return 'http://%s/db/%s/series?u=%s&p=%s' % ( choice(self.instances), self.dbname, self.user, self.password )
        
    def save( self, time, meta, context, data, time_delta=None ):
        # logging.debug("> %s\t%s - %s\t%s\t%s" % (self.instances, meta, context, time, data))
        # reformat ata into influx format
        
        ts = { 'start': now() }
        
        this = {
            'name': get_key( meta, context ),
            'points': [ [ time*1000, ], ],
            'columns': [ 'time', ]
        }
        for k,v in data.iteritems():
            this['columns'].append( k )
            this['points'][0].append( float(v) )

        self.data_cache.append( this )

        if len( self.data_cache ) >= self.chunks:
            # logging.debug( "  - %s" % (encoded,))
            c = self.get_instance_string()
            # logging.info("sending %s to %s" % (len(self.cache),c))

            json = dumps( self.data_cache ) 

            ts['caching'] = now()

            resp = urlopen( c, json )
            code = resp.getcode()

            n = len(self.data_cache)

            if code == 200:
                self.data_cache = []
            else:
                logging.warn("  >: %s: %s" % (code,resp.read()))

            ts['sending'] = now()

            logging.info("%s sent %s datapoints (processing %.3fsec, sending %.3fsec)" % (c, n, delta(ts['start'],ts['caching']), delta(ts['caching'],ts['sending']) ) )

    
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
        