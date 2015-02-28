from slac_utils.command import Command, DefaultList

from slac_utils.managers import Manager
from slac_utils.command import ManagerDaemon
from ptolemy.storage.feeders import Feeder
from ptolemy.storage.managers import StorageManagerFactory

from ptolemy.analyse.alert import Email

from slac_utils.util import DictDiffer
from datetime import timedelta

from slac_utils.time import datetime_to_epoch, now

import redis

import logging


    
cache_key = 'pt:phones'
def phone_key( mac ):
    return 'pt:phones:%s' % mac

process_key = 'pt:phones:last_run'

def validate_message( meta ):
    if meta['spec'] == 'layer1_peer' and meta['group'] == 'neighbour':
        return True
    return False
    

class TelephoneWorker( Feeder ):
    """
    keep new phones found on network in a cache, deal with expiry of phones from network: when such events are found send emails(s) to interestered parties
    we use redis as a data store for the phones, as we wish to deal with expiry we have two options
    1) have each phone as a separate key as STRING or HASH and use EXPIRE to pubsub when phones go away
    2) keep everything in a ZSET and set the timestamp as the SCORE, periodically do a ZRANGE to determine what hasn't been seen in a while
    the former would require a separate process to subscribe for notifications, the latter is probably easier to understand. so we do options #2
    we'll use two datastructures
    - a sorted set with just the epoch time and mac address that it was seen
    - normal string get/sets with a dict of the last seen device and port it was on
    """
    
    agent = 'telephone'
    proc_name = 'ptolemy analyse telephones'
    delta = timedelta(minutes=20)
    # if the system has been down a while, we don't want to send a large number of alerts
    # so we keep a cache of when we last ran too
    alert = True
    dont_alert_until = None
    phone_not_moved = {}
    
    def setup( self, **kwargs ):
        super( TelephoneWorker, self ).setup(**kwargs)
        # keep the last known in memcache for stateful analysis
        # TODO: deal with multiple members
        for s in kwargs['cache_pool']:
            server, _tmp, port = s.partition(':')
            self.cache = redis.StrictRedis( host=server, port=int(port), db=0 )

        # prevent flood of emails when we haven't analysed anything in a while
        last_run = self.cache.get( process_key )
        n = now()
        logging.info("last time ran: %s" % (last_run,))
        if last_run and last_run < datetime_to_epoch(n - self.delta):
            self.dont_alert_until = n + self.delta
            logging.error("too much time has past, ignoring disconnection alerts until %s" % (self.dont_alert_until,))
        self.cache.set( process_key, datetime_to_epoch(n) )

        
    def send_email( self, msg, subj ):
        logging.info( '%s' % (msg,))
        try:
            e = Email( server=self.kwargs['email_server'], from_name=self.kwargs['email_from_name'], from_email=self.kwargs['email_from_address'], site_name=self.kwargs['email_server'] )
            e.send( self.kwargs['email_to'], msg, subject='%s%s' % (self.kwargs['email_subject_prepend'],subj) )
        except Exception,e:
            logging.error("could not send notification: %s %s" % (type(e),e))
            
            
    def pre_bulk_process( self, time, meta, context, deta ):
        # only bother with layer1_peers - requires phones to report lldp
        self.found = 0
        self.phone_not_moved = {}
        return validate_message( meta )
        
    def post_bulk_process( self, time, meta, context, data ):
        # load up oldest entries and notify that we haven't seen them in a while
        # hmm.. problem is that if we haven't ran for a while, the first switch that gets scanned
        # will result in all the other mac addresses which have expired to be notified... hmmm
        if self.found > 0:

            logging.debug("c=%s, found=%s" % (context,self.found))

            ok = True
            try:
                if datetime_to_epoch(now()) <= self.dont_alert_until:
                    ok = False
            except Exception,e:
                logging.error("could not parse time: %s %s " % (type(e),e))

            # logging.warn("PHONES NOT MOVED? %s" % (self.phone_not_moved, ))
            
            # logging.error("N: %s\t%s" % (self.dont_alert_until,ok))
            if ok:
                
                delta = datetime_to_epoch( time - self.delta )
                
                # we don't want to alert on other devices, however
                # there's no way of knowing otherwise that they're not around
                # logging.info("TIME: %s\t%s" % (time, datetime_to_epoch(time)))
                for this in self.cache.zrangebyscore( cache_key, 0, datetime_to_epoch(time), withscores=True ):

                    m = this[0]
                    if m:
                        score = this[1]

                        # only alert if some time has elapsed
                        # logging.debug("%s\ts=%s\tscore=%s/%s (%s)" % (m, context, score,delta, score<delta))
                        if score < delta:

                            k = phone_key( m )
                            last = self.cache.get( k )

                            msg = 'phone %s disconnected from %s (previously %.2fs ago)' % (m,last,delta-score)
                            subj = 'ip phone %s' % (m,)
                            if self.alert:
                                self.send_email( msg, subj )

                # remove entries from cache
                i = self.cache.zremrangebyscore( cache_key, 0, delta )
                if i > 0:
                    logging.debug("DELETED: %s" % (i,))
                # logging.debug("deleting: %s\tdeleted: %s" % (', '.join( [ i for i in self.cache.zrangebyscore( cache_key, 0, delta ) ] ), i )  )
            
    def save( self, time, meta, context, data, time_delta=None ):
        """
        use a sorted set
        """
        # print( "+ %s meta %s\tcontext %s:\t%s" % (time, meta, context, data))
        if 'capability_telephone' in data and data['capability_telephone'] and 'peer_mac_address' in data and data['peer_mac_address']:

            self.found = self.found + 1

            # get useful info
            m = data['peer_mac_address']
            current = {
                'switch':   context['device'],
                'port':     context['physical_port']
            }

            # useful variables
            t = int(datetime_to_epoch(time))
            k = phone_key(m)
            
            # we need to determine if this is a new entry or not
            seen = self.cache.zrank( cache_key, m )
            last = None
            try:
                v = eval( self.cache.get( k ) )
                if isinstance( v, dict ):
                    last = v
                # logging.warn("last: v %s l %s" % (v,last))
            except:
                pass
                
            # just add it, keys by the mac address, redis will update existing mac's with new timestamp
            self.cache.zadd( cache_key, t, m )
            self.cache.set( k, current )
            # logging.info( '(phone mac %s) %s: %s \t-> %s' % (m,k, last, current,) )

            # if changed, then notify
            msg = None
            subj = None
            
            if last:
                d = DictDiffer( last, current )
                if d.changed():
                    msg = 'phone %s moved from %s to %s' % (m, last, current)
                    subj = 'ip phone %s' % (m,)
                else:
                    self.phone_not_moved[m] = True

            else:
                msg = 'new phone %s at %s' % (m, current)
                subj = 'ip phone %s' % (m,)

            # send the email
            if msg and subj and self.alert:
                self.send_email( msg, subj )


class Telephone( Command ):
    """
    Monitors for and alerts on changes in the voip telephones on campus
    """
    
    @classmethod
    def create_parser( self, parser, settings, parents=[] ):

        parser.add_argument( '-p', '--pool', help='pool name', default=settings.POOL )
        parser.add_argument( '-k', '--keys', help='key name', action='append', default=DefaultList(settings.KEYS) )
        
        ampq = parser.add_argument_group('backend messenging settings')
        ampq.add_argument( '--host',          help='ampq host', default=settings.BROKER_HOST )
        ampq.add_argument( '--port',          help='ampq port', default=settings.BROKER_PORT )
        ampq.add_argument( '--vhost',         help='ampq vhost', default=settings.BROKER_VHOST )
        ampq.add_argument( '--user',          help='ampq username', default=settings.BROKER_USER )
        ampq.add_argument( '--password',      help='ampq password', default=settings.BROKER_PASSWORD )

        cache = parser.add_argument_group( 'cache settings')
        cache.add_argument( '--cache_pool', help='cache servers', default=DefaultList(settings.CACHE_POOL))
        
        alert = parser.add_argument_group( 'alert settings')
        alert.add_argument( '--email_server', help='email server name', default=settings.ALERT['EMAIL']['SERVER'] )
        alert.add_argument( '--email_from_name', help='email from name', default=settings.ALERT['EMAIL']['FROM_NAME'] )
        alert.add_argument( '--email_from_address', help='email from address', default=settings.ALERT['EMAIL']['FROM_EMAIL'] )
        alert.add_argument( '--email_subject_prepend', help='email subject', default=settings.ALERT['EMAIL']['SUBJECT_PREPEND'] )
        alert.add_argument( '--email_to', help='email targets', default=DefaultList(settings.ALERT['EMAIL']['TO']) )
    
    def run( self, *args, **kwargs ):

        analyse_manager = StorageManagerFactory().get( TelephoneWorker, **kwargs )
        analyse_manager.proc_name = 'ptolemy analyse telephone manager'
    
        class TelephoneDaemon( ManagerDaemon ):
            manager = analyse_manager
            proc_name = 'ptolemy analyse telephone'
            worker_kwargs = [ 'email_server', 'email_from_name', 'email_from_address', 'email_subject_prepend', 'email_to' ]

        daemon = TelephoneDaemon()
        daemon.start( **kwargs )


