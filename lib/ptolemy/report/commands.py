import argparse

try:
    import psycopg2
    import psycopg2.extras
except:
    pass

from slac_utils.messages import Message
from slac_utils.command import Command, CommandDispatcher
#from slac_utils.time import datetime
import logging
import datetime


class PostgresCommand( Command ):

    @classmethod
    def create_parser( self, parser, settings, parents=[] ):

        db = parser.add_argument_group( 'db settings' )
        db.add_argument( '--db_host', help='db host', default=settings.POSTGRES_HOST )
        db.add_argument( '--db_port', help='db host', default=settings.POSTGRES_PORT, type=int )
        db.add_argument( '--db_name', help='db db name', default=settings.POSTGRES_DATABASE )
        db.add_argument( '--db_username', help='db user name', default=settings.POSTGRES_USERNAME )
        db.add_argument( '--db_password', help='db pass', default=settings.POSTGRES_PASSWORD )

        # add defaults
        ampq = parser.add_argument_group('ampq options')
        ampq.add_argument( '--host',          help='ampq host',     default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port',     default=settings.BROKER_PORT, type=int )
        ampq.add_argument( '--vhost',         help='ampq vhost',    default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )
        
    def connect( self, db_host='localhost', db_port=5432, db_name='default', db_username='default', db_password='default', **kwargs ):
        self.db = psycopg2.connect(
            host = db_host,
            database = db_name,
            user = db_username,
            password = db_password,
        )
        # enable hstore
        # psycopg2.extras.register_hstore(self.db)
        logging.info("success connecting to postgres at %s: %s" % (db_host,db_port) )
        return self.db.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        

    def pre_run( self, *args, **kwargs ):
        logging.debug("connecting to database")
        self.cur = self.connect( **kwargs )
        return args, kwargs

    def run( self, *args, **kwargs ):
        base = datetime.datetime.today()
        res = {}
        for t in [ base - datetime.timedelta(days=x) for x in range(0,60) ]:
            d = "%s" % t.strftime('%Y-%m-%d')
            logging.debug( d )
            v = self._run( d )
            res[d] = v
            print( '%s\t%s' % (d,v) )
        # logging.error("%s" % res )
        # for k in sorted( res)
        
        
class UniqueIpAddresses( PostgresCommand ):
    """
    number of ip addresses seen on date
    """

    def _run( self, date ):
        stmt = "select count(distinct(context->'ip_address')) from arps__arps where '%s' between created_at and updated_at;" % date
        logging.debug("RUN: %s" % stmt)
        self.cur.execute( stmt )
        return self.cur.fetchall().pop()['count']

class UniqueMacAddresses( PostgresCommand ):
    """
    number of unique mac addresses seen on day
    """

    def _run( self, date ):
        stmt = "select count(distinct(context->'mac_address')) from spanning_tree__neighbour where '%s' between created_at and updated_at;" % date
        logging.debug("RUN: %s" % stmt)
        self.cur.execute( stmt )
        return self.cur.fetchall().pop()['count']

class Report( CommandDispatcher ):
    """
    report details
    """
    commands = [ UniqueIpAddresses, UniqueMacAddresses ]