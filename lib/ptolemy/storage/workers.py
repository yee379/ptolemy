from slac_utils.managers import Worker
from slac_utils.statistics_feeder import CarbonFeeder, MultiCarbonFeeder

import datetime
# from time import sleep
from slac_utils.time import utcfromtimestamp, sleep

import gc

import sys
from ptolemy.queues import QueueFactory
# from pymongo import Connection
# from pymongo.objectid import ObjectId
# from bson.dbref import DBRef

try:
    import psycopg2
    import psycopg2.extras
except:
    pass
    
try:
    import pynsca
except:
    pass
    
import ipaddress 

import traceback

import logging
from pprint import pformat
        
class Store(object):
    """
    simple proxy to storage backends; use to broadcast storage items
    """
    def __init__(self, *args, **kwargs):
        # create the queue
        self.queue_factory_obj = QueueFactory( **kwargs )
        self.connection = self.queue_factory_obj.get_connection()
        self.queue = getattr( self.queue_factory_obj, 'store' )( connection=self.connection, exchange_name='store' )
        self.queue.__enter__()
        
    def __del__(self):
        self.queue.__exit__()
        
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
            # logging.error("KEY: %s" % (key,))
            self.queue.put( msg, key=key )

class Feeder( Worker ):
    """
    generic storer that gets parameters from __init__(**kwargs) and only picks up the ones beginning with the same as agent name
    """
    action = 'storing'
    agent = 'generic'
    
    stats_feeder = None
    stats_preamble = 'ptolemy_internals.polld'
    
    proc_name = 'ptolemy stored'
    
    timestamp_to_datetime = True
    
    def setup( self, **kwargs ):
        logging.debug("feeder %s setup: %s" % (self.agent,kwargs,))
        super( Feeder, self ).setup( **kwargs )
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
        
    def extract( self, this, timestamp_to_datetime=True ):
        # query key for lookup
        for i in ( 'group', 'spec' ):
            if not i in this._meta:
                logging.error("Invalid metadata for storage: does not contain key '%s'" % (i,) ) 
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
        if 'carbon_key' in this['_meta']:
            meta['carbon_key'] = this._meta['carbon_key']

        
        if not 'timestamp' in this:
            logging.error("no timestamp in task")
            raise 'No timestamp found'
        timestamp = this['timestamp']
        if timestamp_to_datetime and not isinstance( timestamp, datetime.datetime ):
            timestamp = utcfromtimestamp( timestamp )

        for i in ( '_meta', 'context', 'timestamp' ):
            del this[i]
        # logging.error("DONE: %s %s %s %s" % (timestamp,meta,kwargs,this) )
        return timestamp, meta, kwargs, this

    def pre_bulk_process( self, time, meta, context, data ):
        return True
        
    def post_bulk_process( self, time, meta, context, data ):
        pass

    # arps need at least 15 minutes for some reason
    def process_task( self, this, stats={}, time_delta=None, **kwargs ):

        # logging.error("+STORER: %s" % (this) )
        # logging.debug("processing key: %s" % (this['_meta']['key'],))
        # make sure it's valid (each will have a 'data)
        if not 'data' in this or not '_meta' in this:
            raise SyntaxError, 'invalid storage item: ' + pformat(this)

        # overwrite the time_delta if instructed to in the dataset
        if '_meta' in this and 'archive_after' in this['_meta'] and not this['_meta']['archive_after'] == None:
            time_delta = this['_meta']['archive_after']
            logging.warn("set time delta to %s" % (time_delta,))

        time, meta, context, this = self.extract( this, self.timestamp_to_datetime )
        # logging.error(">> %s %s %s %s %s" % (time, meta, context, type(this.data), this.data ))

        if self.pre_bulk_process( time, meta, context, this ):

            t = type(this.data)
            if t == list:
                template = {}
                for k,v in this.iteritems():
                    if not k in ( 'data', 'type' ):
                        template[k] = v
                for i in this.data:
                    try:
                        one = template.copy()
                        this_context = context.copy()
                        for k,v in i.iteritems():
                            one[k] = v
                        # logging.debug(">> %s %s" % (meta, this_context,))
                        yield self._process_task( time, meta, this_context, one, time_delta )
                    except UserWarning,e:
                        logging.warn('%s' % (e,))
                    except Exception,e:
                        logging.error("ERROR: <%s> %s: %s %s\n%s" % (type(e),e,context,meta,traceback.format_exc()))

            # if it's just a dict, the we flatten the doc and just store it
            elif t == dict:
                yield self._process_task( time, meta, context, this.data, time_delta )
    
            else:
                logging.error("unknown data type %s" % (this['data']))
                
        # else:
        #     logging.debug('failed pre_bulk_process: %s' % (meta,))

        self.post_bulk_process( time, meta, context, this )
        # logging.info("-STORER: %s " % ({},) )
        
        return

    def _process_task( self, time, meta, context, item, time_delta ):
        # logging.info("_PROCESS_TASK %s %s" % (meta,context))
        # process single datum
        if isinstance( item, dict ):
            # look for key names in the data
            for k in meta['key_name']:
                if k in item:
                    context[k] = item[k]
                    del item[k]
            # logging.debug(">>> %s %s %s %s %s" % (time, meta, context, type(item), item))
            return self.save( time, meta, context, item, time_delta )
    
        logging.error("unknown data type for %s" % (item,))
        return None

    def save( self, time, meta, context, data, time_delta=None ):
        raise NotImplementedError, 'not implemented save()'
    


class ConsoleStorer( Feeder ):
    """
    dumps the data out to screen
    """
    agent = 'console'
    def save( self, time, meta, context, data, time_delta ):
        print( "+ %s meta=%s\tcontext=%s:\t%s" % (time, meta, context, data))



def get_carbon_key( meta, context, key_prepend='' ):
    if 'carbon_key' in meta:
        return meta['carbon_key']
    # remap device to reverse notation
    device = ".".join( reversed( context['device'].split('.')) )
    # append other context items
    context_keys = []
    for k in sorted(context.keys()):
        if not k in ( 'device', ):
            context_keys.append( "%s" % (context[k],) )
    # key
    carbon_key = "%s%s.%s.%s.%s" % (key_prepend, device, meta['spec'], meta['group'], '.'.join(context_keys) )
    # logging.error("-carbon %s" % (carbon_key,))
    return carbon_key.replace('/','.')

class CarbonStorer( Feeder ):
    
    agent = 'carbon'    
    key_prepend = '.'

    feeder = None    

    proc_name = 'ptolemy stored carbon'

    timestamp_to_datetime = False

    def setup(self,**kwargs):
        super( CarbonStorer, self).setup(**kwargs) 
        if 'key_prepend' in kwargs:
            self.key_prepend = kwargs['key_prepend']
        # logging.error("STORE: %s (%s:%s)" % (kwargs,self.host,self.port))
        if not 'connect' in kwargs:
            kwargs['connect'] = True
        if not kwargs['connect'] == False:
            self.feeder = CarbonFeeder( host=self.host, port=self.port )
            self.proc_name = "%s %s:%s" % (self.proc_name, self.host, self.port)
        
    def __exit__(self,*args,**kwargs):
        if self.feeder:
            self.feeder.__exit__(*args,**kwargs)
    
    def get_key( self, meta, context ):
        return get_carbon_key( meta, context, key_prepend=self.key_prepend )
    
    def save( self, time, meta, context, data, time_delta=None ):
        carbon_key = self.get_key( meta, context )
        # logging.debug("= %s" % (carbon_key,))
        try:
            if self.feeder:
                # logging.debug("> %s:%s\t %s\t%s\t%s" % (self.host,self.port, time, carbon_key, data))
                self.feeder.send( time, carbon_key, data )
            # sys.stdout.write('i')
        except Exception,e:
            logging.error("Error: could not send " + str(e))
        return


class MultiCarbonStorer( CarbonStorer ):
    """
    given a array of the carbon instances, will use consistent hashing to determine where to send it
    """
    agent = 'multicarbon'    
    proc_name = 'ptolemy stored multicarbon'

    def setup(self,**kwargs):
        super( CarbonStorer, self).setup(**kwargs) 
        self.feeder = MultiCarbonFeeder( instances=self.instances )


# in order to put in documents in a meaningful fashion, we need to determine the fields that should be used as
# a reference to what has changed since the last document. we do this by defining the excluded fields
class MongoStorer( Feeder ):
    """
    dumps each document into mongodb
    """
    agent = 'mongo'
    proc_name = 'ptolemy stored mongo'
    
    db_name = 'ptolemy_production'
    history_collection_append = '_history'
    
    conn = None
    db = None
    
    def setup( self, **kwargs ):
        super( MongoStorer, self).setup( **kwargs) 
        logging.debug("attempting connection to mongodb db %s"%(self.db_name))
        self.conn = Connection( self.host, self.port )
        self.db = self.conn[self.db_name]
        logging.debug("success connecting to mongodb at " + str(self.host) + ":" + str(self.port) )
        # try connecting to something to make sure FH is up
        self.db['system']
            
            
    def save( self, time, meta, context, data, time_delta ):
        # logging.info( ">>> MONGO: time: %s meta: %s, context: %s, data: %s" % (time, meta, context, data))        
        # store the document under collection_name (spec and group_name)
        collection_name = meta['spec'] + '__' + meta['group']
        collection = self.db[collection_name]
        # create indexes
        #     collection.ensure_index( i )
        archive_name = collection_name + self.history_collection_append

        # flatten the document
        context = self.flatten( {}, context )
        logging.debug("context: %s" % (context,))
        for k,v in context.iteritems():
            data[k] = v
        data['last_seen'] = time

        # 0) do we currently have the item in our db?
        # TODO: check that only one matching document is found, if more, then merge the documents 
        # together, taking into account the last_seen and first_seens and if history exists
        docs = []
        for d in collection.find( context ):
            gc.disable()
            docs.append( d )
            gc.enable()
        doc = None
        if len(docs) == 0:
            pass
        elif len(docs) == 1:
            doc = docs[0]
        else:
            logging.warn("duplicates found: %s\t%s \t%s" % (collection_name, context, len(docs)))
            doc = {}
            for d in docs:
                logging.debug("  d: %s" % (d,))
                for k,v in d.iteritems():
                    if not k in ( 'last_seen', 'first_seen' ):
                        doc[k] = v
                    elif k == 'last_seen':
                        if not k in doc or ( k in doc and doc[k] < v ):
                            doc[k] = v
                    elif k == 'first_seen':
                        if not k in doc or ( k in doc and doc[k] > v ):
                            doc[k] = v
                collection.remove( d )
            logging.debug("reduced to %s"%(doc,))

        # 1) if we already have a document, then we need to update it
        if doc:
            logging.debug("  updating doc: " + str(doc))
            # see if there are any differences in the this set
            different = False
            for k,v in data.iteritems():
                if not k in ( 'last_seen' ):
                    if not k in doc or not doc[k] == v:
                        # logging.debug("    %s: %s->%s" % (k,doc[k],v))
                        different = True

            # if collection_name == 'entity__entities':
            #     if different:
            #         logging.info("DIFFERENT: %s %s" % (len(data),len(doc)))
            #         for k,v in data.iteritems():
            #             logging.info("  %s:\t%s (%s)\t%s (%s)\t%s" % (k,data[k],type(data[k]),doc[k], type(doc[k]),data[k] == doc[k]) )

            # TODO: deal with fact that the doc could be old and that we should archive it regardless
            if not time_delta == None and doc['last_seen'] + time_delta < data['last_seen']:
                different = None

            # 1a) if no difference from the stored doc, then just update the time stamps
            if different == False:

                collection.update( doc, { '$set': { 'last_seen': data['last_seen'] } })
                logging.debug("  updated timestamps to " + str(data['last_seen']))
                sys.stdout.write('u')
                
            # 1b) if tehre are difference in the data, then archive the current and update links
            else:
                # we move the doc to the archive collection and put it into the archive
                collection.remove( { '_id': doc['_id'], '$atomic': True } )
                archive = self.db[archive_name]
                doc = archive.insert( doc )

                # we keep a linked list so we can easily trawl through history
                data['first_seen'] = data['last_seen']  # same timestamp
                data['_previous'] = DBRef( archive_name, doc )  # ref to archive doc

                logging.debug("  inserting updated " + pformat(data) )
                collection.insert( self.flatten( data, context ) )
                if different == True:
                    sys.stdout.write('a')
                else:
                    sys.stdout.write('t')
        
        # 2) just insert the new document
        else:
            if not 'first_seen' in data:
                data['first_seen'] = data['last_seen']  # same timestamp
            doc = self.flatten( data, context )
            logging.debug("  inserting new %s" % (doc))
            collection.insert( doc )
            sys.stdout.write('i')

        # done
        return data

        


class NSCAStorer( Feeder ):
    """
    pushes simple checks to nagios via nsca
    """
    agent = 'nsca'
    conn = None
    
    proc_name = 'ptolemy stored nsca'
    
    value_map = {
        'ping': {
            100.:    pynsca.UNREACHABLE,
            0.:      pynsca.UP,
            'other':    pynsca.WARNING,
        }
    }
    
    def setup( self, **kwargs ):
        super( NSCAStorer, self).setup(*args,**kwargs) 
        logging.info("attempting connection to nsca %s:%s"%(self.host,self.port))
        self.conn = pynsca.NSCANotifier( self.host, monitoring_port=self.port ) #, encryption_mode=1, password=None )
            
    def remap_state( self, service, value ):
        if service in self.value_map:
            if value in self.value_map[service]:
                return self.value_map[service][value]
            else:
                return self.value_map[service]['other']
        return None
    
    def save( self, time, meta, context, data, time_delta ):
        logging.info("request %s %s %s" % (meta, context, data) )

        try:
            host = context['device']        
            service = 'undefined'
            state = pynsca.UNKNOWN

            if 'tool' in context:
                service = context['tool'].lower()

            if service == 'ping':
                state = self.remap_state( service, float(data['loss']) )
                service = '' # identify as a host

            else:
                raise NotImplementedError, 'unknown service ' + service

            msg = str(data)
            logging.info("  state: %s, msg %s"%(state,msg))
            self.conn.svc_result( host, service, state, msg )
            logging.info("  sent host: %s\tservice: %s\tstate: %s\tmsg: %s" % (host, service, state, msg ))

        except Exception,e:
            logging.error("save error %s %s: %s %s %s"%(type(e),e,meta,context,data))

        # done
        return None


class PostgresStorer( Feeder ):
    """
    dumps each document into a postgres hstore database
    """
    agent = 'postgres'
    proc_name = 'ptolemy stored postgres'
    
    history_collection_append = '_history'
    
    known_tables = {}
    update_ids = []
    partitions = {}
    
    cur = None
    db = None
    
    def flatten( self, a, b ):
        # hstore can only store text values
        for k,v in b.iteritems():
            a[k] = str(v)
        return a
    
    def setup( self, **kwargs ):
        super( PostgresStorer, self).setup(**kwargs) 
        # logging.debug("attempting connection to postgres db %s:%s %s (%s/%s)"%(self.host, self.port, self.database, self.username, self.password) )
        logging.info("connecting to %s" % (kwargs,))
        self.connect()
        # keep cache of tables
        self.known_tables = {}
        self.update_ids = []
        # initialise subnets
        self.subnets = []
        for s in kwargs['subnets']:
            self.subnets.append( ipaddress.IPv4Network(s) )
        logging.debug("subnets: %s" % (self.subnets))

        # partitioning
        self.partitions = {}
        if 'partitions' in kwargs:
           for i in kwargs['partitions']:
               k,_tmp,v = i.partition(':')
               if k and v:
                   self.partitions[k] = v
        logging.debug("partitions: %s" % (self.partitions,))
        
    def connect( self ):
        self.db = psycopg2.connect(
            host = self.host,
            database = self.database,
            user = self.username,
            password = self.password,
        )
        # enable hstore
        psycopg2.extras.register_hstore(self.db)
        logging.info("success connecting to postgres at " + str(self.host) + ":" + str(self.port) )
        self.cur = self.db.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
    
    def table_name( self, spec, group, context ):
        name = '%s__%s' % (spec, group)
        # logging.debug("NAME: %s (%s)" % (name,self.partitions))
        inherited_from = None
        if name in self.partitions:
            if self.partitions[name] in context:
                # determine the key to partition on and use this as the table name
                # logging.info("partition! %s -> %s = %s (%s)" % (name, self.partitions[name], context[self.partitions[name]], context) )
                inherited_from = name
                name = "%s__%s%s" % (name,self.partitions[name],context[self.partitions[name]])
            else:
                raise UserWarning, 'partition for %s has incorrect context: %s does not exist (allowed %s)' % (name,self.partition[name],context.keys())
        return name, inherited_from
        
    def ensure_table( self, spec, group, context={}, archive=False ):
        """
        if archive, then the archive table will use the id column as basically a FK for the item it is referencing.
        """
        name, inherited_from = self.table_name( spec, group, context )
        # logging.warn("ENSURE: %s (inherited from %s)" % (name,inherited_from))
        if archive:
            name = name + self.history_collection_append
        
        # create the master table
        this_table = inherited_from
        if this_table == None:
            this_table = name
        
        if not this_table in self.known_tables:

            pk = 'SERIAL'
            if archive:
                pk = 'INT'
            stmt = "CREATE TABLE %s ( id %s, created_at TIMESTAMP WITH TIME ZONE NOT NULL, updated_at TIMESTAMP WITH TIME ZONE NOT NULL, context HSTORE DEFAULT hstore(array[]::varchar[]), data HSTORE DEFAULT HSTORE(array[]::varchar[]) );" % (this_table,pk)
            try:
                logging.debug("CREATE: %s" % (stmt,))
                self.cur.execute( stmt )
                self.known_tables[this_table] = {}
                # TODO: Create indexes
            except psycopg2.ProgrammingError,e:
                # its fine if the table already exists
                if not str(e).endswith( ' already exists\n'):
                    raise e
                if not name in self.known_tables:
                    self.known_tables[this_table] = {}
            # accept error
            self.db.commit()

        # if we have a parition, then create the partition 
        if inherited_from:
            stmt = "CREATE TABLE %s () INHERITS (%s)" % (name,inherited_from)
            try:
                logging.debug("CREATE PART: %s" % (stmt,))
                self.cur.execute( stmt )
                self.known_tables[name] = {}
            except psycopg2.ProgrammingError,e:
                # its fine if the table already exists
                if not str(e).endswith( ' already exists\n'):
                    logging.error("ERR: %s %s" % (type(e),e))
                    raise e
                if not name in self.known_tables:
                    self.known_tables[inherited_table] = {}
            self.db.commit()

        return name
    
    def ensure_indexes( self, table, context ):
        """
        using our cache, create the indexes on the server if we don't already know about it
        """
        # ptolemy_production=> CREATE INDEX port__status_device_index ON ports__status((context->'device')) WHERE ((context->'device') IS NOT NULL);
        # ptolemy_production=> CREATE INDEX port__status_physical_port_index ON ports__status((context->'physical_port')) WHERE ((context->'physical_port') IS NOT NULL);
        if table in self.known_tables:
            for k in context:
                try:
                    if not k in self.known_tables[table]:
                        name = table + "_" + k + "_index"
                        field = "(context->'"+k+"')"
                        stmt = "CREATE INDEX %s ON %s(%s) WHERE (%s IS NOT NULL);" % (name, table, field, field )
                        logging.info( ' INDEX: %s' % (stmt,))
                        self.cur.execute( stmt )
                except Exception,e:
                    if not str(e).endswith( ' already exists\n'):
                        raise e
                # accept
                self.db.commit()
                # cache the fact we know of this key
                self.known_tables[table][k] = True
        
    def query( self, table, context, field='context' ):
        """
        retrieve the item from db with all fields in the context matching
        """
        stmt = "SELECT * FROM %s WHERE " % (table,)
        kv = []
        for k,v in context.iteritems():
            kv.append( "%s->'%s'='%s'" % ('context',k,v))
        stmt = stmt + ' AND '.join(kv) + ';'
        logging.debug("QUERY: %s" % (stmt,))
        self.cur.execute( stmt )
        return self.cur.fetchall()

    def insert( self, table, time, context, data ):
        stmt = self.cur.mogrify("INSERT INTO "+table+"(created_at,updated_at,context,data) VALUES (%s,%s,%s,%s);", (time,time,context,data) )
        logging.debug(" INSERT: (%s) %s" % (table,stmt,))
        self.cur.execute( stmt )

    def different( self, row, table, context, data ):
        """
        determines if the contents of row is different
        """
        # logging.error("  ROW: %s" % (row,))
        # logging.error("  NEW: %s %s" % (context,data,))
        different = False
        for k,v in data.iteritems():
            # logging.error("   k: %s %s" % (k,v))
            if k in row['data'] and row['data'][k] == v:
                pass
            else:
                different = True
                break
        # logging.error("  DIFFERENT: %s" % (different,))
        return different
            
    def update_timestamps( self, row, table, time ):
        stmt = self.cur.mogrify("UPDATE " + table + " SET updated_at=%s WHERE id=%s;", (time, row['id'] ) )
        # logging.debug("UPDATE: %s" % (stmt,))
        self.cur.execute( stmt )
        
    def archive_and_update( self, spec, group, row, time, context, data ):
        # ensure we have the archive table
        arch = self.ensure_table( spec, group, archive=True )
        # copy the item into the archive; use the current timestamp to indicate time range
        stmt = self.cur.mogrify("INSERT INTO "+arch+"(id,created_at,updated_at,context,data) VALUES (%s,%s,%s,%s,%s);", (row['id'],row['created_at'],time,context,data) )
        logging.debug(" INSERT: %s" % ('',) ) #(stmt,))
        self.cur.execute( stmt )
        # update table with new info
        table = self.ensure_table( spec, group )
        stmt = self.cur.mogrify("UPDATE " + table + " SET updated_at=%s,created_at=%s,context=%s,data=%s WHERE id=%s;", (time,time,context,data,row['id'] ) )
        logging.debug(" UPDATE: (%s) %s" % (table,stmt,))
        self.cur.execute( stmt )
        
    def _context_key( self, context ):
        idx = []
        for k in sorted( context.keys() ):
            idx.append( "%s=%s" % (k,context[k]) )
        return ','.join(idx)
    
    def pre_bulk_process( self, time, meta, context, data ):
        """
        do a bulk fetch for all of the data pertinent to this context/data and cache for lookups
        """
        self.cache = {}
        self.table = None
        self.update_ids = []
        
        # get the table
        self.table = self.ensure_table( meta['spec'], meta['group'], context=context )
        self.ensure_indexes( self.table, context )

        context = self.flatten( {}, context )
        
        # query for all docs - how to determine the limited context? assume just device
        # if it exists in the context
        kwargs = context
        if 'device' in kwargs:
            kwargs = { 'device': context['device'] }
        for i in self.query( self.table, kwargs ):
            key = self._context_key( i['context'] )
            # logging.warn("  key: %s" % (key,))
            if not key in self.cache:
                self.cache[key] = []
            self.cache[key].append( i )
        
        # important! otherwise ignore this message
        return True
        
    def post_bulk_process( self, time, meta, context, data ):
        self.bulk_update( self.table, time, self.update_ids )
        self.db.commit()
        self.table = None
        self.update_ids = []

    def bulk_update( self, table, time, ids ):
        if len(ids):
            idx = []
            for i in ids:
                idx.append( 'id=%s' % (i,) )
            stmt = self.cur.mogrify("UPDATE " + table + " SET updated_at=%s WHERE " + ' OR '.join(idx) + ";", (time,) )
            logging.debug("UPDATE (%s): %s" % (time, stmt,))
            self.cur.execute( stmt )
        
    def save( self, time, meta, context, data, time_delta ):

        # flatten the document
        context = self.flatten( {}, context )
        data = self.flatten( {}, data )
        
        # logging.debug("> %s: %s %s" % (time,context,data))
        # skip anything not defined as ours
        if ( meta['spec'] == 'layer3' and meta['group'] == 'subnets' ):
            if 'prefix' in context and 'netmask' in context:
                this = ipaddress.IPv4Network( "%s/%s" % ( context['prefix'], context['netmask'] ))
                ok = False
                for s in self.subnets:
                    if this.overlaps( s ):
                        ok = True
                if not ok:
                    s = 'skipping %s %s: subnet %s' % (meta['spec'],meta['group'],this)
                    # logging.error(s)
                    raise UserWarning, s
            else:
                raise SyntaxError, 'invalid context for %s %s: %s' % (meta['spec'], meta['group'], context)

        # 0) do we currently have the item in our db?
        key = self._context_key( context )
        docs = []
        if key in self.cache:
            docs = self.cache[key]
            
        # logging.debug("  DOCS: %s" % (len(docs),) )
            
        # TODO: check that only one matching document is found, if more, then merge the documents 
        # together, taking into account the last_seen and first_seens and if history exists

        # 1) if we already have a document, then we need to update it
        if len(docs) == 1:

            # see if there are any differences in the this set
            if self.different( docs[0], self.table, context, data ):
                # 1b) if tehre are difference in the data, then archive the current and update links
                self.archive_and_update( meta['spec'], meta['group'], docs[0], time, context, data )

            else:

                # 2) check timestamps, if too long, then archive the old one
                if not time_delta == None and docs[0]['updated_at'] + time_delta < time:
                    logging.warn("old data %s\t%s: %s " % (time_delta, docs[0]['updated_at']+time_delta-time, context ))

                # 1a) if no difference from the stored doc, then just update the time stamps
                self.update_ids.append( docs[0]['id'] )

            # TODO: deal with fact that the doc could be old and that we should archive it regardless

        elif len(docs) > 1:
            
            # get oldest
            t = None
            ids = [ i['id'] for i in docs ]
            table = "%s__%s" % ( meta['spec'], meta['group'] )
            logging.error("DUPLICATES FOUND (%s) %s %s: DELETE FROM %s WHERE %s" % (table, context, data, table, ids ))


        # 2) just insert the new document
        else:
            self.insert( self.table, time, context, data )

        return data



class RRDStorer( Feeder ):
    pass
    
