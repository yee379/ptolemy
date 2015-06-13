
from ptolemy.queues import QueueFactory
from ptolemy.storage.feeders import Feeder
from ptolemy.storage.commands import StorageCommand, DefaultList

from slac_utils.time import utcfromtimestamp, sleep
from slac_utils.command import DefaultList
from slac_utils.string import dict_to_kv

from hashlib import md5

try:
    import psycopg2
    import psycopg2.extras
except:
    pass

import ipaddress 

import traceback
import logging
from pprint import pformat

class PostgresStorer( Feeder ):
    """
    dumps each document into a postgres hstore database
    """
    agent = 'postgres'
    proc_name = 'ptolemy stored postgres'
    
    history_collection_append = '_history'
    
    known_tables = {}
    current_table_name = None
    update_ids = []
    delete_ids = []
    partitions = {}
    partitions_modulo = {}
    
    post_msg_process_tables = []
    post_msg_data = {}
    
    cur = None
    db = None
    
    print_stats_fields = ( 'updated', 'bulk_updated', 'inserted', 'deleted', 'archived', 'pre_cached', 'bulk_cached', 'pre_msg_process_time', 'main_loop_time', 'post_msg_process_time', 'total_time' )
    
    def flatten( self, a, b ):
        # hstore can only store text values
        d = {}
        for k,v in dict( a.items() + b.items() ).iteritems():
            d[k] = str(v)
        return d
    
    def setup( self, **kwargs ):
        super( PostgresStorer, self).setup(**kwargs) 
        # logging.debug("attempting connection to postgres db %s:%s %s (%s/%s)"%(self.host, self.port, self.database, self.username, self.password) )
        # logging.info("connecting to %s" % (kwargs,))
        self.connect()
        # keep cache of tables
        self.known_tables = {}
        self.update_ids = []
        self.delete_ids = []
        # initialise subnets
        self.subnets = []
        if 'subnets' in kwargs:
            for s in kwargs['subnets']:
                self.subnets.append( ipaddress.IPv4Network(s) )
            logging.debug("subnets: %s" % (self.subnets))

        # partitioning
        self.partitions = {}
        self.partitions_modulo = {}
        self.md5 = md5()
        if 'partitions' in kwargs:
            for d in kwargs['partitions']:
                try:
                    key = '%s__%s'%(d['spec'],d['group'])
                    self.partitions[key] = d['field']
                    if 'modulo' in d:
                        self.partitions_modulo[key] = int(d['modulo'])
                except:
                    raise Exception( 'partition %s not defined correctly' % (d,))
        logging.debug("partitions: %s" % (self.partitions,))
        
        # processing of large workflows (multi msg sets, aka prefetching)
        self.pre_msg_process_tables = {}
        for d in kwargs['pre_msg_process']:
            n = self._table_name( d['spec'], d['group'] )
            self.pre_msg_process_tables[n] = { 
                'fields': d['fields'],
                'missing_ok': d['fields_missing_ok'] if 'fields_missing_ok' in d else False,
            }
        logging.debug("post tables: %s" % (self.pre_msg_process_tables,))
        
        self.post_msg_data = {}
        self.post_msg_process_tables = []
        for d in kwargs['post_msg_process']:
            n = self._table_name( d['spec'], d['group'] )
            self.post_msg_process_tables.append(n)
        logging.debug("pre tables: %s" % (self.post_msg_process_tables,))
        
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
    
    def _table_name( self, spec, group ):
        return '%s__%s' % (spec, group)
        
    def table_name( self, spec, group, context, data ):
        name = self._table_name(spec, group)
        # logging.debug("NAME: %s (%s)" % (name,context))
        inherited_from = None
        if name in self.partitions:
            if self.partitions[name] in context:
                # determine the key to partition on and use this as the table name
                # logging.info("partition! %s -> %s = %s (%s)" % (name, self.partitions[name], context[self.partitions[name]], context) )
                inherited_from = name
                v = context[self.partitions[name]]
                # check to see if we need to do a modulo on the value
                if name in self.partitions_modulo:
                    self.md5.update( v )
                    v = long(self.md5.hexdigest(),16) % self.partitions_modulo[name]
                name = "%s__%s%s" % (name,self.partitions[name],v)
            elif not context == {}:
                # the context does not contain the relevant fields for the table as it's inherited and split
                # so lets check the data dict to see if we have it there
                # TODO: fix if more than one valid value in data set....
                vals = {}
                # logging.error("DATA: %s" % data)
                for d in data:
                    # logging.error("D: %s %s" % (self.partitions[name],d) )
                    if self.partitions[name] in d:
                        vals[d[self.partitions[name]]] = True
                    else:
                        s = 'partition for %s has incorrect context: %s does not exist (allowed %s)' % (name,self.partitions[name],context.keys())
                        logging.debug(" %s: %s -> %s" % (s, name, inherited_from) )
                        raise UserWarning, s

                # logging.error("VALS: %s %s" % (vals,len(vals)) )
                if len(vals) == 1:
                    v = vals.keys().pop()
                    name = "%s__%s%s" % (name,self.partitions[name],v)
                    # logging.error("NAME: %s %s" % (name, inherited_from))
                else:
                    raise Exception( 'could not determine partition value %s: %s' % (vals,data))
        return name, inherited_from
        
    def ensure_table( self, spec, group, context={}, data=None, archive=False ):
        """
        if archive, then the archive table will use the id column as basically a FK for the item it is referencing.
        """
        name, inherited_from = self.table_name( spec, group, context, data )
        # logging.error("ENSURE: %s (inherited from %s)" % (name,inherited_from))
        if archive:
            name = name + self.history_collection_append
        
        # create the master table
        this_table = inherited_from
        if this_table == None:
            this_table = name
        
        if not this_table in self.known_tables:

            # check
            try:
                # this is ~15x faster than creating the table if it already exists
                stmt = "SELECT '%s'::regclass;" % (this_table)
                logging.debug("ENSURE: %s" % (stmt,))
                self.cur.execute( stmt )
                self.known_tables[this_table] = {}
            except:
                # manually create
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
        if inherited_from and not name in self.known_tables:

            try:
                
                stmt = "SELECT '%s'::regclass;" % (name,)
                logging.debug('ENSURE %s' % (stmt,))
                self.cur.execute( stmt )
                self.known_tables[name] = {}

            except:

                stmt = "CREATE TABLE %s () INHERITS (%s)" % (name,inherited_from)
                try:
                    logging.debug("CREATE PARTITION: %s" % (stmt,))
                    self.cur.execute( stmt )
                    self.known_tables[name] = {}
                except psycopg2.ProgrammingError,e:
                    # its fine if the table already exists
                    if not str(e).endswith( ' already exists\n'):
                        logging.debug("ERR: %s %s" % (type(e),e))
                        raise e
                    if not name in self.known_tables:
                        self.known_tables[name] = {}
                except psycopg2.InternalError,e:
                    # hmmm.... why does it return this sometimes?
                    # ?? current transaction is aborted, commands ignored until end of transaction block
                    logging.debug("ERROR: %s %s" % (type(e),e))
                self.db.commit()

        # logging.warn("END ENSURE %s" % (name,))
        return name
    
    def ensure_indexes( self, table, context ):
        """
        using our cache, create the indexes on the server if we don't already know about it
        """
        # ptolemy_production=> CREATE INDEX port__status_device_index ON ports__status((context->'device')) WHERE ((context->'device') IS NOT NULL);
        # ptolemy_production=> CREATE INDEX port__status_physical_port_index ON ports__status((context->'physical_port')) WHERE ((context->'physical_port') IS NOT NULL);
        # logging.error("ENSURE IDX")
        if table in self.known_tables:
            for k in context:
                try:
                    if not k in self.known_tables[table]:
                        # query the db
                        name = table + "_" + k + "_index"
                        stmt = "SELECT indexname FROM pg_indexes WHERE indexname='%s'" % name
                        self.cur.execute( stmt )
                        # create since we don't appear to have it
                        if len( [i for i in self.cur.fetchall()] ) == 0:
                            field = "(context->'"+k+"')"
                            stmt = "CREATE INDEX %s ON %s(%s) WHERE (%s IS NOT NULL);" % (name, table, field, field )
                            logging.info( ' INDEX: %s' % (stmt,))
                            self.cur.execute( stmt )
                        # else:
                        #     logging.debug("  index %s already exists" % (name,))
                except Exception,e:
                    if not str(e).endswith( ' already exists\n'):
                        raise e
                # accept
                self.db.commit()
                # cache the fact we know of this key
                self.known_tables[table][k] = True

        # logging.error("END ENSURE IDX")
    
    def _query_constructor( self, anon_hash, field='context', operation='AND' ):
        items = []
        for kwargs in anon_hash:
            kv = []
            for k,v in kwargs.iteritems():
                kv.append( "%s->'%s'='%s'" % (field,k,v))
            items.append( '(' + ' AND '.join(kv) + ')' )
        op_string = ' %s ' % (operation,)
        return op_string.join(items)
    
    def query( self, table, array_of_contexts, field='context', recent=False, operation='AND' ):
        """
        retrieve the item from db with all fields in the context matching
        """
        stmt = "SELECT * FROM %s WHERE " % (table,)
        stmt = stmt + self._query_constructor( array_of_contexts, field=field, operation=operation )
        if recent:
            stmt = stmt + ' ORDER BY created_at DESC LIMIT 1 '
        stmt = stmt + ';'
        logging.debug(" %s" % (stmt,))
        self.cur.execute( stmt )
        return self.cur.fetchall()

    def insert( self, table, time, context, data ):
        stmt = self.cur.mogrify("INSERT INTO "+table+"(created_at,updated_at,context,data) VALUES (%s,%s,%s,%s);", (time,time,context,data) )
        logging.debug(" INSERT: (%s) %s" % (table,stmt,))
        self.cur.execute( stmt )

    def different( self, row, context, data, partial=False ):
        """
        determines if the contents of row is different, we have 3 states:
        True: there is a major difference where a lot of data has changed
        False: the data is all the same
        None: there are new updates that should be applied, but it is not major
        if partial is true, then don't worry if data only has a small subset of the data in row
        """
        # logging.error("  ROW: %s" % (row,))
        # logging.error("  NEW: %s %s" % (context,data,))
        different = False
        for k,v in data.iteritems():
            # logging.error("   k: %s %s" % (k,v))
            if k in row['data'] and row['data'][k] == v:
                pass
            # ignore if we add more data into the database
            elif not k in row['data']:
                different = None
            else:
                different = True
                break
                
        # if there are more fields in row than in data, then there is a change - unless partial is True
        if different == False and partial == False:
            if len(row['data'].keys()) > len(data.keys()):
                different = True
                # logging.debug("  DIFFERENT: %s (%s / %s)" % (different,row['data'].keys(),data.keys()))
                
        return different
        
    def archive_and_update( self, spec, group, row, time, context, data ):
        # ensure we have the archive table
        arch = self.ensure_table( spec, group, archive=True )
        # copy the item into the archive; use the current timestamp to indicate time range
        try:
            # logging.debug("+ ARCHIVE2 %s" % (context,))
            stmt = self.cur.mogrify("INSERT INTO "+arch+"(id,created_at,updated_at,context,data) VALUES (%s,%s,%s,%s,%s);", (row['id'],row['created_at'],time,context,data) )
            logging.debug(" %s" % (stmt,))
            self.cur.execute( stmt )
        except Exception,e:
            logging.error("Error: %s" %e)
        # update table with new info
        # self.update_item( spec, group, row, time, context, data )
        self.update_item( self.table, row, time, context, data )

    def update_item( self, table, row, time, context, data, update_created_at=True ):
        # table = self.ensure_table( spec, group )
        stmt = self.cur.mogrify("UPDATE " + table + " SET updated_at=%s,created_at=%s,context=%s,data=%s WHERE id=%s;", (time,time,context,data,row['id'] ) )
        if not update_created_at:
            stmt = self.cur.mogrify("UPDATE " + table + " SET updated_at=%s,context=%s,data=%s WHERE id=%s;", (time,context,data,row['id'] ) )
        # logging.info("c=%s, doc=%s" % (context,row['context']))
        # logging.info("d=%s, doc=%s" % (data,row['data']))
        logging.debug(" (full) %s" % (stmt,))
        self.cur.execute( stmt )
        
    def pre_msg_process( self, msg, envelope ):
        # basically a pre fetch for data
        
        logging.debug("="*80)
        # logging.warn("PRE MSG: %s" % (pformat(msg,width=250),))
        self.update_ids = []
        self.delete_ids = []
        self.context_fields = []
        self.context_fields_missing_ok = False
        self.cache = {}
        self.pre_msg_queried = False
        self.stats = {
            'pre_cached': 0,
            'bulk_cached': 0,
            'inserted': 0,
            'updated': 0,
            'bulk_updated': 0,
            'archived': 0,
            'messages': 0,
            'deleted': 0,
        }

        # try to work out if i can reduce the number of queries to fill the cache here
        # we do this by iterating through all the msgs and constructing a singel query string
        # instead of doing a query per message.
        
        # this only works of course, when there is more than one message in the input, 
        # otherwise, it's simpler to use pre_bulk_processing
        
        # important: this assumes that all messages in msg are of the same spec and group; use first as example
        m = msg[0]
        self.current_table_name = self._table_name( m['_meta']['spec'],m['_meta']['group'] )
        # logging.error("CUR: %s, PRE %s" % (self.current_table_name, self.pre_msg_process_tables))
        if self.current_table_name in self.pre_msg_process_tables:
            self.context_fields = self.pre_msg_process_tables[self.current_table_name]['fields']
            self.context_fields_missing_ok = self.pre_msg_process_tables[self.current_table_name]['missing_ok']
            ctxs = []
            for m in msg:
                okay = []
                this_table_name = self._table_name( m['_meta']['spec'],m['_meta']['group'] )
                if not this_table_name == self.current_table_name:
                    raise Exception('non identical spec/groups in long message: %s / %s' % (self.current_table_name, this_table_name))
                if 'context' in m:
                    for f in self.context_fields:
                        okay.append( True if f in m['context'] else False )
                if not False in okay:
                    # logging.warn("+++ %s" % m['context'] )
                    this = {}
                    for f in self.context_fields:
                        this[f] = m['context'][f]
                    ctxs.append( this )
            self.stats['messages'] = len(msg)
            # actually do the query
            if len( ctxs ):
                try:
                    for d in self.query( self.current_table_name, ctxs, operation='OR' ):
                        key = dict_to_kv( d['context'], keys=self.context_fields, missing_ok=self.context_fields_missing_ok )
                        # logging.warn("- %s\tc=%s, d=%s" % (key,d['context'],d['data']) )
                        if not key in self.cache:
                            self.cache[key] = []
                        self.cache[key].append( d )
                        self.stats['pre_cached'] = self.stats['pre_cached'] + 1
                        self.pre_msg_queried = True
                    # logging.warn("-"*80)
                except Exception,e:
                    self.db.rollback()
                    self.cache = {}
                    self.pre_msg_queried = None
        return msg
        
    def pre_bulk_process( self, time, meta, context, data ):
        """
        do a bulk fetch for all of the data pertinent to this context/data and cache for lookups
        """
        # we put the result of the bulk lookup into self.cache[key]
        # logging.error("+++pre bulk process: m=%s, c=%s d=%s" % (meta, context, data) )
        
        # self.cache = {} # moved to pre_msg_process

        self.delayed_context = meta['delayed_context'] if 'delayed_context' in meta and len(meta['delayed_context']) else []
        # set this for mass bulk procesing (post msg if needed)
        self.post_msg_processing = True if self._table_name(meta['spec'],meta['group']) in self.post_msg_process_tables else False
        
        # get the table
        self.table = self.ensure_table( meta['spec'], meta['group'], context=context, data=data )
        self.ensure_indexes( self.table, context )

        context = self.flatten( {}, context )
        
        # if we have 'just_insert' == True in meta, then we the message wants to be inserted
        # without updating any previous doc, so we don't bother looking up
        if 'just_insert' in meta and meta['just_insert'] == True:
            return True
                
        # some tables want to just update the last entry as the context may match many documents (like on an alert table where each row represents an alert). in this case, we would have an 'update_recent' in meta
        recent = False
        kwargs = context
        if 'update_recent' in meta and meta['update_recent'] == True:
            # logging.warn("UPDATE RECENT %s" % context )
            recent = True
        else:
            if 'device' in kwargs:
                kwargs = { 'device': context['device'] }
        for c in self.delayed_context:
            if c in kwargs:
                del kwargs[c]

        # if there's something already in the cache, then assume that that pre_msg_process did it and we don't
        # have to do a lookup again here 
        
        # TODO: have issue of caching__hosts where what is stored may not have all of the context fields we care for, eg arps without vlans (p2p links etc)
        if not self.pre_msg_queried:
            for i in self.query( self.table, [ kwargs, ], recent=recent ):
                key = dict_to_kv( i['context'], keys=self.context_fields, missing_ok=self.context_fields_missing_ok )
                # logging.warn("  key: %s" % (key,))
                if not key in self.cache:
                    self.cache[key] = []
                self.cache[key].append( i )
                self.stats['bulk_cached'] = self.stats['bulk_cached'] + 1
        
        # if 'update_recent' in meta and meta['update_recent'] == True:
        # if meta['spec'] == 'entity' and meta['group'] == 'info':
            # logging.error("%s\t%s CACHE: %s" % (context,kwargs,self.cache,))
        
        # important! otherwise ignore this message
        return True

    def post_bulk_process( self, time, meta, context, data ):
        if len(self.update_ids):
            if not self.post_msg_processing:
                self.bulk_update( self.table, time, self.update_ids )
            else:
                # index by the table and time for each id to update
                if not self.table in self.post_msg_data:
                    self.post_msg_data[self.table] = {}
                if not time in self.post_msg_data[self.table]:
                    self.post_msg_data[self.table][time] = []
                for i in self.update_ids:
                    self.post_msg_data[self.table][time].append( i )
        # clean up
        self.table = None
        self.update_ids = []

    def post_msg_process( self ):
        # logging.error("POST BULK PROCESS: %s" % (self.post_msg_data,))
        # did_something = False
        
        if len(self.delete_ids):
            self.bulk_delete( self.current_table_name, self.delete_ids )
            self.delete_ids = []
        
        for table, d in self.post_msg_data.iteritems():
            for time in d:
                # logging.error("   TABLE: %s, TIME: %s\t%s" % (table,time,d[time]))
                self.bulk_update( table, time, d[time] )
                # did_something = True
        # if did_something:
        self.db.commit()
        # logging.info("stats: %s" % (self.stats,))
        yield None, None

    def bulk_update( self, table, time, ids ):
        # logging.warn("    BULK UPDATE: %s\t%s" % (table,ids,))
        if len(ids):
            try:
                stmt = self.cur.mogrify('UPDATE ' + table + ' SET updated_at=%s WHERE id IN (' + ','.join( [ str(i) for i in ids] ) + ');', (time,) )
                logging.debug(" (bulk) %s" % (stmt,))
                self.cur.execute( stmt )
            except Exception,e:
                logging.error("ERR bulk update: %s %s" % (type(e),e))
                raise e
    
    def bulk_delete( self, table, ids ):
        if len(ids):
            try:
                self.stats['deleted'] = self.stats['deleted'] + len(ids)
                # big hack
                t = table
                if '@' in table:
                    t = t.split('@').pop(0)
                stmt = 'DELETE FROM %s WHERE id in (%s)' % ( t, ','.join( [ str(i) for i in ids ] ) )
                logging.info(" %s" % stmt)
                self.cur.execute( stmt )
            except Exception,e:
                logging.error("ERR bulk delete: %s %s" % (type(e),e))
                raise e

    def save( self, time, meta, ctx, data, time_delta ):
        """ do something with this single datum """
        # logging.error(">>> SAVE: %s %s" % (ctx,data))
        # flatten the document
        context = self.flatten( {}, ctx )
        data = self.flatten( {}, data )

        # logging.warn("SAVE >>> %s: %s %s" % (time,ctx,data))
        # skip subnets that we don't care about as defined in configuration files
        if ( meta['spec'] == 'layer3' and meta['group'] == 'subnets' ):
            if 'prefix' in context and 'netmask' in context:
                this = ipaddress.IPv4Network( "%s/%s" % ( context['prefix'], context['netmask'] ))
                ok = False
                for s in self.subnets:
                    if this.overlaps( s ):
                        ok = True
                        break
                if not ok:
                    s = 'skipping %s %s: subnet %s' % (meta['spec'],meta['group'],this)
                    # logging.error(s)
                    raise UserWarning, s
            else:
                raise SyntaxError, 'invalid context for %s %s: %s' % (meta['spec'], meta['group'], context)
                                
        # 0) do we currently have the item in our db/cache (see pre_process for cache entries)?
        
        # deal with delayed_contexts where we may only have a paritial entry
        # this will throw an exception if the context doesn't have all necessary fields
        # eg with vlans on caching__hosts
        key = dict_to_kv( context, keys=self.context_fields, missing_ok=self.context_fields_missing_ok )
        # logging.warn("KEY: %s" % (key,) )
        docs = self.cache[key] if key in self.cache else []

        # merge in keys for delayed contexts
        if 'delayed_context' in meta and len( meta['delayed_context'] ):
            for c in meta['delayed_context']:
                # logging.error("DELAYED1 %s: %s %s" % (c,context,data))
                if c in data.keys():
                    context[c] = data[c]
                    del data[c]
            # logging.error("DELAYED2 (d=%s): %s %s" % (d,context,data))

        # TODO: check that only one matching document is found, if more, then merge the documents 
        # together, taking into account the last_seen and first_seens and if history exists

        # logging.debug("  DOCS: %s" % (len(docs),) )
        # 1) if we already have a document, then we need to update it
        if len(docs) == 1:

            # see if there are any differences in the this set
            d = self.different( docs[0], context, data, partial=False )
            logging.debug("doc (%s): c=%s\td=%s" % (d,docs[0]['context'],docs[0]['data']) )

            # if we have a 'ignore_data', then we don't care if d is True, so force - ensure we don't overwrite the created_at time
            update_created_at = True
            if 'ignore_data' in meta and meta['ignore_data']:
                update_created_at = False
                d = None
                
            if 'merge_context' in meta and meta['merge_context']:
                new_context = self.flatten( docs[0]['context'], context )
                # if new context has more fields, assume it's the same then
                d = False if len(new_context) >= len(context) else None
                logging.debug(" contexts (%s) c=%s\t-> c=%s" % (d,context,new_context))
                context = new_context
             
            if 'merge_data' in meta and meta['merge_data']:
                # fastpath: if data is empty, then force a post batch update
                if data == {}:
                    logging.debug( ' data empty')
                else:
                    # check to see if the kv are same for keys that are common; always assume data is smaller
                    for k,v in data.iteritems():
                        if not k in docs[0]['data'] or not docs[0]['data'][k] == data[k]:
                            # tehre's a difference, so update item
                            d = None
                    new_data = self.flatten( docs[0]['data'], data )
                    logging.debug(" data (%s) d=%s\t-> d=%s" % (d,docs[0]['data'],data))
                    data = new_data
                    
            if d == True:
                # 1b) if there are differences in the data, then archive the current and update links
                # logging.error("THAT %s" % (context,))
                self.stats['archived'] = self.stats['archived'] + 1
                self.archive_and_update( meta['spec'], meta['group'], docs[0], time, context, data )

            elif d == False:
                # 2) check timestamps, if too long, then archive the old one
                if not time_delta == None and docs[0]['updated_at'] + time_delta < time:
                    logging.warn("old data %s\t%s: %s " % (time_delta, docs[0]['updated_at']+time_delta-time, context ))
                # 1a) if no difference from the stored doc, then just update the time stamps
                self.stats['bulk_updated'] = self.stats['bulk_updated'] + 1
                self.update_ids.append( docs[0]['id'] )

            elif d == None:
                # minor updates
                self.stats['updated'] = self.stats['updated'] + 1
                # self.update_item( meta['spec'], meta['group'], docs[0], time, context, data, update_created_at=update_created_at )
                self.update_item( self.table, docs[0], time, context, data, update_created_at=update_created_at )
 
            else:
                
                logging.error("difference value unknown! %s" % (d,))
                
            # TODO: deal with fact that the doc could be old and that we should archive it regardless
                    
        elif len(docs) > 1:
            
            # get oldest
            t = None
            oldest = None
            for i in docs:
                if t == None:
                    t = i['created_at']
                    oldest = i['id']
                if i['created_at'] < t:
                    t = i['created_at']
                    oldest = i['id']
                if not i['id'] in self.delete_ids:
                    self.delete_ids.append( i['id'] )
                # logging.warn("- %s" % (i,))
            self.delete_ids.remove( oldest )
            # do a post_msg_process to delete in bulk
            
        # 2) just insert the new document
        else:
            logging.warn("INSERTING: key=%s\tc=%s " % (key,context))
            self.stats['inserted'] = self.stats['inserted'] + 1
            self.insert( self.table, time, context, data )
        
        return None
        

class Postgres( StorageCommand ):
    """
    postgres storage daemon
    """
    worker = PostgresStorer

    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):
        super( Postgres, cls ).create_parser( parser, settings, parents=parents )

        parser.add_argument( '-p', '--pool', help='pool name', default=settings.POOL )
        parser.add_argument( '-k', '--keys', help='key name', action='append', default=DefaultList(settings.KEYS) )

        p = parser.add_argument_group( 'postgres settings')
        p.add_argument( '--postgres_database', help='postgres database', default=settings.POSTGRES_DATABASE )
        p.add_argument( '--postgres_host', help='postgres host',   default=settings.POSTGRES_HOST )
        p.add_argument( '--postgres_port', help='postgres instances', default=settings.POSTGRES_PORT )
        p.add_argument( '--postgres_username', help='postgres username', default=settings.POSTGRES_USERNAME )
        p.add_argument( '--postgres_password', help='postgres password', default=settings.POSTGRES_PASSWORD )
        p.add_argument( '--subnets', help='site subnets', default=DefaultList(settings.LAYER3_SUBNETS) )
        p.add_argument( '--partitions', help='table partitions', default=DefaultList(settings.PARTITIONS) )
        p.add_argument( '--pre_msg_process', help='mass bulk updates', default=DefaultList(settings.PRE_MSG_PROCESS) )
        p.add_argument( '--post_msg_process', help='mass bulk updates', default=DefaultList(settings.POST_MSG_PROCESS) )
    
