import argparse

from slac_utils.command import CommandDispatcher, Command, ManagerDaemon
from slac_utils.managers import WorkerManager
from slac_utils.messages import Message
from ptolemy.queues import QueueFactory

try:
    import psycopg2
    import psycopg2.extras
except:
    pass

import logging
from slac_utils.logger import init_loggers
from slac_utils import time
import subprocess, os, sys
from re import search


class Base( Command ):

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        parser.add_argument( '-i', '--interval',     help='monitor interval', default=60 )

        ampq = parser.add_argument_group('ampq options', 'options on connecting to backend messenging service')
        ampq.add_argument( '--host',          help='ampq host', default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port', default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='ampq vhost', default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )





class CommandLineManager( WorkerManager ):
    proc_name = 'ptolemy profile commandline'
    queue_factory = QueueFactory
    monitor_period = 60
    def __init__( self, pool=None, key='#', auto_delete=True, **kwargs ):
        super( CommandLineManager, self ).__init__( pool=pool, key=key, auto_delete=auto_delete, 
            work_queue_func=None, results_queue_func='store', **kwargs )
        if 'interval' in kwargs:
            self.monitor_period = kwargs['interval']
    def run_command( self, command ):
        logging.info("running: %s" % (self.CMD,))
        p = subprocess.Popen( command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        for i in p.stdout:
            yield i
        return
    def process_task( self, *args, **kwargs ):
        self.now = time.now()
        # logging.error( "%s: %s" % (self.now, self.CMD) )
        for i in self.parse( self.run_command( self.CMD.split() ) ):
            # logging.info("%s" % (i,))
            key=None
            if '_meta' in i and 'key' in i._meta:
                key = i._meta['key']
            logging.debug("ENQUEUE: %s\t%s" % (key,i) )
            self.results_queue.put( i, key='.'+key )
        time.sleep(self.monitor_period)
        return

###############################################################################
# RabbitMQ Monitoring
###############################################################################

class RabbitMQProfiler( CommandLineManager ):
    """
    list all queues in /ptolemy vhost and determine some stats
    """
    CMD="/usr/sbin/rabbitmqctl  -p /ptolemy list_queues name messages messages_ready messages_unacknowledged consumers"
    def parse( self, generator ):
        for i in generator:
            # supervised_store@carbon.default.[net-store01.slac.stanford.edu:2804:i]
            m = search( r'^(?P<queue>.*)\s+(?P<messages>\d+)\s+(?P<ready>\d+)\s+(?P<processing>\d+)\s+(?P<consumers>\d+)', i )
            if m:
                d = m.groupdict()

                if ':' in d['queue']:
                    # instance may come out as '#', ignore in this case, want
                    v = d['queue'].split(':')[-1][0]
                    if v == '#':
                        pass
                    else:
                        d['instance'] = v
                        
                d['queue'] = d['queue'].split('.[')[0].replace('#','all')
                # contruct routing and carbon keys
                k = 'profiler.rabbitmq.%s' % d['queue']
                if 'instance' in d:
                    k = '%s.%s' % (k, d['instance'])
                k = k + '.stats.'
                msg = Message( 
                    meta    = { 
                        'type': 'task',
                        'key':  k,
                        'spec':     'profiler',
                        'group':    'rabbitmq',
                        'carbon_key':   k,
                    },
                    context = {
                        'queue': d['queue'],
                    },
                    data = {
                        'queued': int(d['ready']),
                        'processing': int(d['processing']),
                        'consumers': int(d['consumers']),
                    }
                )
                if 'instance' in d:
                    msg.context['instance'] = d['instance']
                    
                # msg._meta['task_id'] = item['task_id'] if 'task_id' in item else str(uuid())
                msg.timestamp = self.now
                # logging.info("%s: %s" % (a[0],msg))
                yield msg
        return

class RabbitMQDaemon( ManagerDaemon ):
    manager = RabbitMQProfiler
    proc_name = 'ptolemy profile rabbitmq'
    
class RabbitMQ( Base ):
    """
    monitor rabbitmq performance
    """
    def run( self, *args, **kwargs ):
        d = RabbitMQDaemon()
        d.start( **kwargs )

###############################################################################
# PostGres Monitoring
###############################################################################

class PostgresProfiler( WorkerManager ):
    """
    Monitors the number of rows from each table
    """
    proc_name = 'ptolemy profile postgres'
    queue_factory = QueueFactory
    monitor_period = 60
    def __init__( self, pool=None, key='#', auto_delete=True, **kwargs ):
        super( PostgresProfiler, self ).__init__( pool=pool, key=key, auto_delete=auto_delete, 
            work_queue_func=None, results_queue_func='store', **kwargs )
        if 'interval' in kwargs:
            self.monitor_period = kwargs['interval']
        # connect to postgres
        self.db = psycopg2.connect(
            host = kwargs['postgres_host'],
            database = kwargs['postgres_database'],
            user = kwargs['postgres_username'],
            password = kwargs['postgres_password'],
        )
        self.cur = self.db.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        
    def process_task( self, *args, **kwargs ):
        self.now = time.now()
        # run command
        # taken from http://stackoverflow.com/questions/2596670/how-do-you-find-the-row-count-for-all-your-tables-in-postgres
        self.cur.execute("""
            SELECT 
              nspname AS schemaname,relname,reltuples,relpages
            FROM pg_class C
            LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)
            WHERE 
              nspname NOT IN ('pg_catalog', 'information_schema') AND
              relkind='r'
        """)
        for i in self.cur.fetchall():
            # logging.error("I: %s" % (i,))
            k = 'profiler.postgres.%s.%s.stats.' % (i['schemaname'], i['relname'])
            msg = Message( 
                meta    = { 
                    'type': 'task',
                    'key':  k,
                    'spec':     'profiler',
                    'group':    'postgres',
                    'carbon_key':   k,
                },
                context = {
                    'schema': i['schemaname'],
                    'table': i['relname'],
                },
                data = {
                    'rows': int(i['reltuples']),
                    'pages': int(i['relpages']),
                }
            )
            msg.timestamp = time.now()
            logging.debug("ENQUEUE: %s\t%s" % (k,msg) )
            self.results_queue.put( msg, key='.'+k )
        time.sleep(self.monitor_period)
        return
        
class PostgresDaemon( ManagerDaemon ):
    manager = PostgresProfiler
    proc_name = 'ptolemy profile postgres'
    
class Postgres( Base ):
    """
    monitor postgres performance
    """
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        super( Postgres, cls ).create_parser( parser, settings, parents=parents )
        p = parser.add_argument_group( 'postgres database to monitor')
        p.add_argument( '--postgres_database', help='postgres database', default=settings.POSTGRES_DATABASE )
        p.add_argument( '--postgres_host', help='postgres host',   default=settings.POSTGRES_HOST )
        p.add_argument( '--postgres_port', help='postgres instances', default=settings.POSTGRES_PORT )
        p.add_argument( '--postgres_username', help='postgres username', default=settings.POSTGRES_USERNAME )
        p.add_argument( '--postgres_password', help='postgres password', default=settings.POSTGRES_PASSWORD )

    def run( self, *args, **kwargs ):
        d = PostgresDaemon()
        d.start( **kwargs )
    
        
        
        
###############################################################################
# Command Dispatch
###############################################################################


class Profiler( CommandDispatcher ):
    """
    monitors a ptolemy subsystem and puts the related statistics into it's storage queue
    """
    commands = [ RabbitMQ, Postgres ]

