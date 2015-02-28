import argparse
import traceback
import smtplib
import logging
import redis
from re import compile
import hashlib
from datetime import datetime

from slac_utils.command import CommandDispatcher, Command, CommandDaemon, ManagerDaemon
from slac_utils.messages import Message
from slac_utils.managers import Manager, Worker, WorkerManager
from slac_utils.time import sleep, now_as_epoch
from ptolemy.queues import QueueFactory
# from slac_utils.queues import Queue as StubQueue
from ptolemy.storage.feeders import Store
from slac_utils.string import dict_to_kv

REGEX_TYPE = type(compile(''))


def cache_key( method, name, context, condition, notification_to ):
    """ get redis key for parameters """
    ctx = []
    for k in sorted(context.keys()):
        ctx.append( "%s"%context[k] )
    ctx = ':'.join(ctx)
    c = abs( hash("%s" % condition) ) % ( 10**4 )
    t = abs( hash('%s-%s' % (method,notification_to) ) ) % ( 10**2 )
    return 'pt:a:%s:%s:%s:%s' % (ctx,c,name,t,)

class AlertWorkerManager( WorkerManager ):

    proc_name = 'ptolemy alert'
    work_queue_func = 'alert'
    queue_factory = QueueFactory
    
    prefetch_tasks = 1
    
    def start( self, *args, **options ):
        options = dict( self.kwargs.items() + options.items() )
        self.setup( **options )
        
        # keep things in redis to prevent spamming updates
        server, _tmp, port = options['cache'].pop(0).partition(':')
        self.cache = redis.StrictRedis( host=server, port=int(port), db=0 )
        
        # storage queue alerts
        # self.queue = getattr( self.queue_factory_obj, 'store' )( auto_delete=True )
        self.store_queue = Store( dict( options.items() + { 'queue_factory': self.queue_factory_obj }.items() ) )
        logging.debug("  storage : %s" % (self.store_queue))

        self.working = True
        while self.working:
            logging.info( 'starting %s' % (self.__class__.__name__,) )
            try:
                with self.work_queue:
                    with self.store_queue:
                        self.work_queue.consume( self.process_task, limit=0, prefetch=self.prefetch_tasks )
            except Exception, e:
                logging.error('error (%s) %s: %s' %(type(e),e, traceback.format_exc() ) )
                sleep(5)
        return
    
    def match_ignore( self, metric, context, ignore=[] ):
        """ determine if the dict message context matches any defined ignores """
        if metric in ignore:
            for d in ignore[metric]:
                # logging.debug("  d: %s" % (d,))
                matched = True
                for k,v in d.iteritems():
                    if k in context:
                        r = compile(d[k])
                        if not r.match(context[k]):
                            matched = False
                            continue
                if matched:
                    return True
        return False
    
    def match_context( self, name, context, message_context ):
        """ determine if the message matches the stanza's context """
        # logging.debug(" - %s"%(name,))
        for k,v in context.iteritems():
            # match against the context to determine if this alert matches
            results = []
            # match against array?
            arr = []
            if isinstance( v, list ):
                arr = v
            else:
                arr.append( v )
            this = message_context[k] if k in message_context else None
            # logging.debug("   %s: %s -> %s" % (k,this,arr) )

            for a in arr:
                r = False
                if isinstance(a,str):
                    a = compile( a )
                if isinstance( a, REGEX_TYPE ):
                    if a.match( this ):
                        r = True
                elif v == this:
                    r = True
                results.append( r )

            # logging.debug("    this; %s res: %s" % (this,results,))

            # don't bother doing more if one fails
            if not True in results:
                return False
        return True

    def match_condition( self, name, conditions, data ):
        """ determine if the data contents matches the supplied stanza """
        # logging.debug('   condition: %s, on %s' % (conditions,'-') )
        for c in conditions:
            try:
                if not c == True:
                    # run an eval... bad bad bad, but how else?
                    cmd = c % data
                    logging.debug("   %-40s %30s  -->  %s" % (name,c,cmd,))
                    if not eval( cmd ):
                        return False
            except Exception,e:
                logging.warn("   Err: %s %s\n%s" % (type(e),e,traceback.format_exc()))
                return None
        return True

    
    def alert( self, method, t_now, name, alert_options, global_options, context, conditions, data ):
        """ send the alert via method taking into consideration limit definitions in the alert frequency """
        k = cache_key(method,name,context,conditions,alert_options['to'] if 'to' in alert_options else '-')
        logging.info("  ! alert: method %s item %s (key %s)" % (method,name,k))
        # look up key in redis, value is timestamp at which first alert was sent
        temper = False
        limit = float(alert_options['limit']) if 'limit' in alert_options else None
        if limit:
            try:
                t = self.cache.get(k)
                left = float(t) + limit
                logging.debug('    time %s, %s + %s (%s) > %s ' % (type(t),t,limit,left,t_now))
                if left > t_now:
                    temper = left - t_now
            except:
                pass
                # logging.warn("    cache time format error")
        if temper == False:
            # globals()[method]( alert_options, global_options, context, data, obj=self )
            getattr(self, method)( alert_options, global_options, context.copy(), conditions, data, t_now )
            # logging.debug("    sent!")
            if limit:
                # add key to cache with expiry of limit
                self.cache.setex( k, int(limit), t_now )
            
        else:
            logging.debug("    alert limit reached, resuming in %4ds" % (temper,))
        
    def email( self, stanza, opts, context, conditions, data, t_now ):
        """ alert via email """
        # header
        subj = stanza['subject'] % context
        pre = [
            'From: ' + opts['email_from_name'],
            'Subject: ' + opts['email_subject_prepend'] + subj,
            ''
        ]
        body = stanza['content'] % dict( data.items() + context.items() )
        s = smtplib.SMTP( opts['email_server'] )
        return s.sendmail( opts['email_from_address'], stanza['to'], '\n'.join(pre) + body )

    def store( self, stanza, opts, context, conditions, data, t_now ):
        """ insert into the ptolemy storage queue with the group as the metric name """
        g = context['metric'].replace('.','_')
        del context['metric']
        meta = dict( {
                'type':     'task',
                'spec':     'alert',
                'group':    g,
        }.items() + stanza.items() )
        msg = Message( 
            meta=meta,
            context=context,
            data=data,
        )
        msg.timestamp = t_now
        # logging.warn("MSG: %s" % (msg,))
        return self.store_queue.put( msg )
        
    def file( self, stanza, opts, context, conditions, data, t_now ):
        """ write output to file """
        fn = stanza['path']
        with open( fn, 'a' ) as f:
            f.write( '%s %s %s\n' % (t_now,dict_to_kv(context),conditions))
        
        
    def process_task( self, msg, envelope ):
        """ check alert against configuration stanzas to determine who to alert """
        logging.debug("+ %s" % (msg['context'],))
        t_now = now_as_epoch()

        try:
            # process ignore list
            if not self.match_ignore( msg['context']['metric'], msg['context'], ignore=self.kwargs['ignore'] ):

                # iterate through alert stanzas and determine if this alert message matches
                for a in self.kwargs['alerts']:
                    for name, alert in a.iteritems():
                        if self.match_context( name, alert['context'], msg['context'] ):
                            # logging.debug("    passed context" )
                            m = self.match_condition( name, alert['condition'], msg['data'] )
                            if m:
                                # alert each mechanism
                                for alert_with in alert['alert_with']:
                                    # logging.debug('  ! sending alert for %s' % name)
                                    for method, opts in alert_with.iteritems():
                                        try:
                                            # for each method, keep cached when it was last sent
                                            self.alert( method, t_now, name, opts, self.kwargs, msg['context'], alert['condition'], msg['data'] )
                                        except Exception,e:
                                            logging.warn('could not send alert %s: %s\n%s' % (type(e),e, traceback.format_exc()))

            else:
                logging.debug(" - ignoring")

        finally:
            self.work_queue.task_done( envelope )

        return


class AlertDaemon( ManagerDaemon ):
    manager = AlertWorkerManager
    proc_name = 'ptolemy alert'

class Alert( Command ):
    """ 
    Listens for alerts from ptolemy and sends notifications via email
    """
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        
        ampq = parser.add_argument_group('backend messenging settings')
        ampq.add_argument( '--host',          help='ampq host', default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port', default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='ampq vhost', default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )
        
        redis = parser.add_argument_group('cache server settings')
        redis.add_argument( '--cache', help='cache servers', default=settings.CACHE_HOST )
        
        manager = parser.add_argument_group( 'manager settings')
        manager.add_argument( '-p', '--pool',    help='pool name',  default='default' )
        manager.add_argument( '-k', '--keys',     help='key name',   action='append' )
        manager.add_argument( '-w', '--min_workers', help='number of workers',   type=int,   default=settings.WORKERS )
        manager.add_argument( '-W', '--max_workers', help='number of workers',   type=int,   default=settings.WORKERS )
        
        # logging.error("SETTINGS: %s" % settings )
        alert = parser.add_argument_group( 'alert settings')
        alert.add_argument( '--alerts', help='alert configuration', default=settings['ALERTS'] )
        alert.add_argument( '--ignore', help='ignore configuration', default=settings['IGNORE'] )

        email = parser.add_argument_group( 'email settings')
        email.add_argument( '--email_server', help='server name', default=settings['EMAIL_SERVER'] )
        email.add_argument( '--email_from_name', help='from name', default=settings['EMAIL_FROM_NAME'] )
        email.add_argument( '--email_from_address', help='from address', default=settings['EMAIL_FROM_EMAIL'] )
        email.add_argument( '--email_subject_prepend', help='subject prepend', default=settings['EMAIL_SUBJECT_PREPEND'] )
        
    def run(self, *args, **kwargs ):
        scheduler = AlertDaemon()
        scheduler.start( *args, **kwargs )
