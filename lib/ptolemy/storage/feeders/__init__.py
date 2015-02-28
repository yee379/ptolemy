from slac_utils.managers import Worker

import datetime
from slac_utils.time import utcfromtimestamp, sleep
from slac_utils.string import dict_to_kv

import gc
import sys
from ptolemy.queues import QueueFactory

import ipaddress 

import logging
from pprint import pformat
import traceback

from collections import Iterable

__all__ = [ 'Feeder' ]


class Store(object):
    """
    simple proxy to storage backends; use to broadcast storage items
    """
    def __init__(self, *args, **kwargs):
        # create the queue
        if not 'queue_factory' in kwargs:
            self.queue_factory_obj = QueueFactory( **kwargs )
        else:
            self.queue_factory_obj = kwargs['queue_factory']
        self.connection = self.queue_factory_obj.get_connection()
        self.queue = getattr( self.queue_factory_obj, 'store' )( connection=self.connection, exchange_name='store' )
        # self.__enter__()
    
    def __enter__(self):
        self.queue.__enter__()
    
    def __exit__(self, type, value, tb):
        self.queue.__exit__( type, value, tb )
    
    def __del__(self):
        self.__exit__( None, None, None )
    
    def put( self, msg, key=''):
        return self.process_task( msg, key=key )
    
    def process_task( self, msg, key='' ):
        """
        add the message item into the storage queues
        """
        if not msg == None:
            if key == '':
                if '_meta' in msg:
                    if 'key' in msg._meta:
                        key = msg._meta['key']
                    elif 'spec' in msg._meta and 'group' in msg._meta:
                        key = '.spec.%s.group.%s.' % (msg._meta['spec'],msg._meta['group'])
            # logging.error("PUTTING: %s %s" % (msg,key) )
            return self.queue.put( msg, key=key )

class Feeder( Worker ):
    """
    generic storer that gets parameters from __init__(**kwargs) and only picks up the ones beginning with the same as agent name
    """
    action = 'storing'
    agent = 'generic'
    
    stats_feeder = None
    stats_preamble = 'ptolemy_internals.polld'
    
    proc_name = 'ptolemy stored'
    prefetch_tasks = None
        
    timestamp_to_datetime = True
    
    # for certain types of processing (like bulk updates) when there are multiple datums within a message (ie an array), it may be prudent to do bulk updates on the entire msg, rather than on per datum. 
    # populate post_msg_data with our dataset to process at the end in this case
    post_msg_data = {}
    
    def setup( self, **kwargs ):
        super( Feeder, self ).setup( **kwargs )
        self.post_msg_data = {}
        # logging.error("feeder %s kwargs: %s" % (self.agent,kwargs,))
        for k,v in kwargs.iteritems():
            # logging.warn(" k: %s, v: %s" % (k,v))
            if k.startswith( self.agent + '_' ):
                i = k.replace( self.agent + '_', '' )
                # logging.warn("  feeder options: %s = %s" %(i,kwargs[k]) )
                setattr( self, i, kwargs[k] )

    def statistics_key( self, job ):
        s = []
        for i in ( 'device', 'group', 'index' ):
            v = job[i]
            if i == 'device':
                v = reversed( v.split('.') )
            s.append(v)
        return self.preamble + '.' + '.'.join(s)
        
    def flatten( self, a, b):
        for k,v in b.iteritems():
            try:
                v = int(v)
            except:
                v = str(v)
            a[str(k)] = v
        return a
        
    def _extract( self, this, timestamp_to_datetime=True, additional_meta=() ):
        # query key for lookup
        for i in ( 'group', 'spec' ):
            if not i in this._meta:
                logging.error("Invalid metadata for storage: does not contain key %s" % (i,) ) 
                raise AssertionError, 'no %s defined' % i
 
        # logging.info("EXTRACT: %s" % (pformat(this)))
        # find searchable fields for storage (pk's, field lookups etc.)
        kwargs = {}
        if 'device' in this.context:
            kwargs['device'] = this.context['device']
            del this.context['device']

        indexes = []

        # if we have a context then use that
        if 'context' in this:
            for k,v in this.context.iteritems():
                kwargs[k] = v
            # overload with data field
            indexes = kwargs.keys()

        if 'key_name' in this._meta:
            k = this._meta['key_name']
            if isinstance( k, list ):
                for i in k:
                    if not i in indexes:
                        indexes.append( i )
                        if i in this:
                            kwargs[i] = this[i]
                            del this[i]
            else:
                if not k in indexes:
                    indexes.append( k )
                    if k in this:
                        kwargs[k] = this[k]
                        del this[k]
        #     if not isinstance( k, list ):
        #         k = [ k ]
        #     for i in k:
        #         if not i in indexes:
        #             indexes.append( i )
        #             if i in this:
        #                 kwargs[i] = this[i]
        #                 del this[i]
        # 
        # logging.info("%s INDEX: %s %s" % (this._meta['group'],this._meta['key_name'], indexes,))

        # deal with iterative group messages where the group key/value has been overloaded to
        # contain subgroup information regarding this message. it is in the form
        #   <group>@<key>=<value>
        # so we split it up so that key/value become higher level on our store
        if '@' in this._meta['group']:
            # logging.error("FOUND @")
            try:
                g, _tmp, d = this._meta['group'].partition( '@' )
                k,v = d.split('=')
                try:
                    v = int(v)
                except:
                    pass
                # add to doc
                this[k] = v
                this._meta['group'] = g
                # add to search
                kwargs[k] = v
                # add to index
                indexes.append(k)
            except:
                # sys.stdout.write('!')
                raise Exception, 'iterative group message is not of required format: %s' % (this['group'])

        meta = {
            'group':    this._meta['group'],
            'spec':     this._meta['spec'],
            'key_name': indexes,
        }
        for m in additional_meta:
            if m in this['_meta']:
                meta[m] = this._meta[m]
        # logging.warn("META: %s -> %s" % (this._meta,meta))
        
        if not 'timestamp' in this:
            logging.error("no timestamp in task")
            raise 'No timestamp found'
        timestamp = this['timestamp']
        if timestamp_to_datetime and not isinstance( timestamp, datetime.datetime ):
            timestamp = utcfromtimestamp( timestamp )

        for i in ( '_meta', 'context', 'timestamp' ):
            del this[i]
        # logging.error("DONE: %s %s %s %s" % (timestamp,meta,kwargs,this) )
        return timestamp, meta, kwargs, this['data']

    def extract_context( self, context, item ):
        """
        construct the context and items by moving known keys from data to context
        """
        this_context = context.copy()
        # logging.error("KEY: (%s/%s) %s \t -> %s" % (len(context.keys()),len(keys), context.keys(),keys) )
        for k in context.keys():
            if k in item:
                this_context[k] = item[k]
                del item[k]
        return dict_to_kv( this_context ), this_context, item

    def extract( self, this, timestamp_to_datetime=True, additional_meta=('carbon_key','just_insert','update_recent','ignore_data','merge_data','merge_context','delayed_context') ):
        # carbon_key: use this as the carbon key for data storage in cardon
        # just_insert: do not do a lookup of exiting context
        # update_recent: only update the latest matched context
        # ignore_data: ignore the contents of data - why? hows this different from just_insert?
        # merge_context: merge the context with the one stored
        # merge_data: do not replace data, but merge the contents
        # delayed_context: do not use this for lookup (must be in data) but merge it in after
        t, m, context, this = self._extract( this, timestamp_to_datetime=timestamp_to_datetime, additional_meta=additional_meta )
        # logging.debug("CTX CONTEXT: %s\t KEYS (%s)" % (context,m['key_name']))

        # force into array
        if isinstance( this, dict ):
            this = [ this ]
        elif not isinstance( this, list ):
            logging.error("unknown type for %s" % (type(this)) )
            raise Exception( 'dunno what to do with type %s' % (type(this),) )

        new_contexts = {}
        for i in this:
            c, ctx, i = self.extract_context( context, i )
            # logging.warn("  CTX> context %s\t: c %s\tctx %s\ti %s" % (context,c, ctx, i))
            if not c in new_contexts:
                new_contexts[c] = { 'ctx': ctx, 'data': [] }
            new_contexts[c]['data'].append(i)
        for c in new_contexts:
            # logging.error("EXTRACT %s: %s\t%s" % (c,new_contexts[c]['ctx'],'') ) 
            yield t, m, new_contexts[c]['ctx'], new_contexts[c]['data']

        #     # merge in contexts from data if they exist
        #     c, ctx, i = self.extract_context( context, this )
        #     yield t, m, ctx, i


    def pre_bulk_process( self, time, meta, context, data ):
        return True
        
    def post_bulk_process( self, time, meta, context, data ):
        pass

    # arps need at least 15 minutes for some reason
    def process_task( self, msg, stats={}, time_delta=None, **kwargs ):

        # logging.warn(">>> STORER: %s\t%s" % (msg['_meta'],msg['context'],) )
        # logging.warn("MSG: %s" % (msg,))
        # logging.debug("processing key: %s" % (this['_meta']['key'],))
        # make sure it's valid (each will have a 'data)
        if not 'data' in msg or not '_meta' in msg:
            raise SyntaxError, 'invalid storage item: ' + pformat(msg)

        # overwrite the time_delta if instructed to in the dataset
        if '_meta' in msg and 'archive_after' in msg['_meta'] and not msg['_meta']['archive_after'] == None:
            time_delta = msg['_meta']['archive_after']
            logging.warn("set time delta to %s" % (time_delta,))

        for time, meta, context, this in self.extract( msg, self.timestamp_to_datetime ):

            try:

                if self.pre_bulk_process( time, meta, context, this ):

                    # convert to list for processing
                    if isinstance( this, dict ):
                        this = [ this, ]

                    if not isinstance( this, list ):
                        raise Exception('unsupported type %s' % (type(this),) )

                    for i in this:
                        try:
                            yield self._process_task( time, meta, context.copy(), i, time_delta )
                        except UserWarning,e:
                            # logging.warn('user warning: %s' % (e,))
                            pass
                        except Exception,e:
                            logging.error("ERROR: <%s> %s: m=%s c=%s d=%s\n%s" % (type(e),e,meta,context,i,traceback.format_exc()))
                
                out = self.post_bulk_process( time, meta, context, this )

                if isinstance( out, Iterable ):
                    for o in out:
                        yield o
                elif out:
                    yield out

            except Exception, e:
                t = traceback.format_exc()
                logging.warn("TRACE: %s" % t)
                logging.warn("WARN: %s %s: m=%s, c=%s, d=%s" % (type(e),e,meta, context, this) )
                pass
                
        # logging.info("-STORER: %s " % ({},) )
        return

    def _process_task( self, time, meta, ctx, item, time_delta ):
        # logging.info("_PROCESS_TASK %s %s item: %s" % (meta,context,item))
        # process single datum
        if isinstance( item, dict ):
            # look for key names in the data
            for k in meta['key_name']:
                if k in item:
                    ctx[k] = item[k]
                    del item[k]
            # logging.debug(">>> %s %s %s %s %s" % (time, meta, ctx, type(item), item))
            # logging.error("CTX: %s" % (time,))
            return self.save( time, meta, ctx, item, time_delta )
    
        logging.error("unknown data type for %s" % (item,))
        return None

    def save( self, time, meta, context, data, time_delta=None ):
        raise NotImplementedError, 'not implemented save()'
    


