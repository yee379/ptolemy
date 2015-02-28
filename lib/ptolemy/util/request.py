from uuid import uuid1 as uuid
from os import environ
from getpass import getuser

from ptolemy_py.util.queues import ProvisionQueueFactory as QueueFactory

from netconfig import util

import sys, signal
from socket import getfqdn

import logging

class TaskRequest(dict):
    """
    object used to request that somethign get's done by provision
    """
    context_fields = [ 'device' ]
    action_fields = []
    
    def __getattr__(self, key): return self.get(key, None )
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    
    type = None
    
    def __init__(self, item, type=None, options={} ):
        if not type == None:
            self.type = type
            
        if 'task_id' in item: self.task_id = item['task_id']
        else: self.task_id = str(uuid())

        if 'user' in item: self.user = item['user']
        else: self.user = self.getUser()  # deal with remctl

        if 'context' in item: self.context = item['context']
        else: self.setContext( item )
        if not len(self.context.keys()) == len(self.context_fields):
            raise Exception, 'could not define all context fields for task request'

        if 'action' in item: self.action = item['action']
        else: self.setAction( item )
        if len(self.action) == 0:
            raise Exception, 'could not define any actions for task request'

        self.options = options

    def getUser(self):
        user = None
        if 'REMOTE_USER' in environ: user = environ['REMOTE_USER']
        else: 
            dn = str(getfqdn()).split('.')
            user = getuser() + '@' + '.'.join(dn[1:]).upper()
        return user
    def uuid(self):
        return self.task_id
    def setContext(self, item):
        this = {}
        for i in self.context_fields:
            if i in item:
                logging.debug( ' ' + str(i) + ' adding context')
                this[i] = item[i]
            else:
                logging.debug( ' ' + str(i) + ' ignoring context')
        logging.debug('setting context ' + str(this) + " from " + str(item) )
        self.context = this
        return self.context
    def setAction(self, item ):
        this = {}
        # logging.error("ACTION FIELDS: " + str(self.action_fields))
        # logging.error("CONTEXT FIELDS: " + str(self.context_fields))
        for i in item:
            if not i in self.context_fields and i in self.action_fields:
                logging.debug(" adding action " + str(i))
                this[i] = item[i]
            else:
                logging.debug(" ignoring action " + str(i) )
                raise Exception, 'internal error: unsupported action ' + str(i) + ' for request type ' + str(self.__name__)
        logging.debug("setting actions: " + str(this))
        self.action = this
        return self.action
        
        
class PortRequest(TaskRequest):
    context_fields = [ 'device', 'interface' ]
    action_fields = [ 'port.type', 'port.status', 'port.vlan', 'port.state', 'port.protocol', 'port.speed', 'port.duplex', 'port.autoneg', 'port.alias', 'port.subnet', 'port.vlan_name' ]
    type = 'port'
    
class ShowRequest(TaskRequest):
    context_fields = [ 'device', 'interface' ]
    action_fields = [ 'port.info', 'port.transceiver', 'port.spanningtree' ]
    type = 'show'
    
# class Entity( dict ):
#     def __getattr__(self, key): return self.get(key, None )
#         __setattr__ = dict.__setitem__
#         __delattr__ = dict.__delitem__

class settings( object ):
    PROVISION_HOST = 'net-lanmon01.slac.stanford.edu'
    PROVISION_PORT = 5672
    PROVISION_VHOST = '/provision'
    PROVISION_USER = 'provision'
    PROVISION_PASSWORD = 'provision'

class Requestor(object):

    arguments = {
        '-h'        : 'help',
        '--help'    : 'help',
        '-v'        : 'verbose',
        '--verbose' : 'verbose',
    }
    
    request_timeout = 5
    request_object = TaskRequest
    
    def __init__(self, settings ):
        # parse arguments
        self.args, self.options = util.parseArgs( self.arguments )

        if self.options.has_key( 'verbose' ) and self.options['verbose'] == 1:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO, format='%(message)s')
    
        if self.options.has_key( 'help' ) and self.options['help'] == 1:
            self.usage()
            sys.exit(1)

        self.f = QueueFactory( host=settings.PROVISION_HOST, port=settings.PROVISION_PORT, 
                virtual_host=settings.PROVISION_VHOST, user=settings.PROVISION_USER, password=settings.PROVISION_PASSWORD )
        self.q = self.f.provision_request_queue( produce=True )

        self.jobs = []
        self.results = []

        self.parse()

    def usage(self, error=None ):
        raise NotImplementedError

    def parse(self):
        """
        create the requests and append to jobs queue
        """
        for a in self.args:
            req = self.request_object( a )
            self.jobs.append( req )
    
    def submit( self, request ):
        r = self.f.provision_response_queue( consume=True, key=request.uuid() )
        self.q.put( request )
        self.results.append( r )
    
    def run( self ):
        """
        create requests from the parsed jobs and submit
        """
        if len(self.jobs) == 0:
            raise Exception, 'no jobs defined'
        for item in self.jobs:
            self.submit( item )
    
    def report(self):
        # see if we get a response soon
        def timeout_handler(signum,frame):
            logging.error("Error: Response timeout")
            sys.exit(1)
        signal.signal( signal.SIGALRM, timeout_handler )
        signal.alarm(self.request_timeout)
        for r in self.results:
            for i in r.get():
                signal.alarm(0) # cancel
                l = i['level']
                if l == 'data':
                    yield( i['message'] )
                else:
                    m = str(i['message'])                    
                    if l == 'debug': logging.debug( m )
                    elif l == 'info': logging.info( m )
                    elif l == 'error': logging.error( m )
        return
        
        sys.exit(0)