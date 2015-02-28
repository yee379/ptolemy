
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
    
    print_stats_fields = ( 'bulk_updated', 'updated', 'inserted', 'deleted', 'archived', 'pre_cached', 'bulk_cached', 'pre_msg_process_time', 'main_loop_time', 'post_msg_process_time', 'total_time' )
    report_stats_locally = True
    
    def flatten( self, a, b ):
        # hstore can only store text values
        d = {}
        for k,v in dict( a.items() + b.items() ).iteritems():
            d[k] = str(v)
        return d
    
    def _setup( self, **kwargs ):
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
                'fields_required': d['fields_required'] if 'fields_required' in d else [],
                'optional': d['optional_fields'] if 'optional_fields' in d else [],
            }
        logging.debug("post tables: %s" % (self.pre_msg_process_tables,))
        
        self.post_msg_data = {}
        self.post_msg_process_tables = []
        for d in kwargs['post_msg_process']:
            n = self._table_name( d['spec'], d['group'] )
            self.post_msg_process_tables.append(n)
        logging.debug("pre tables: %s" % (self.post_msg_process_tables,))
        
    
    def setup( self, **kwargs ):
        super( PostgresStorer, self).setup(**kwargs) 
        # logging.debug("attempting connection to postgres db %s:%s %s (%s/%s)"%(self.host, self.port, self.database, self.username, self.password) )
        # logging.info("connecting to %s" % (kwargs,))
        self.connect()
        # keep cache of tables
        self._setup( **kwargs )
        
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
                inherited_from = name
                v = context[self.partitions[name]]
                # logging.info("partitioning %s on field %s, value %s" % (name, self.partitions[name], v) )
                # check to see if we need to do a modulo on the value
                if name in self.partitions_modulo:
                    m = md5()
                    m.update( v )
                    v = long(m.hexdigest(),16) % self.partitions_modulo[name]
                    # logging.info("  modulo! %s, len %s -> %s" % (name,self.partitions_modulo[name],v))
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
                        logging.error(" %s: %s -> %s" % (s, name, inherited_from) )
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
            stmt = "CREATE TABLE %s () INHERITS (%s)" % (name,inherited_from)
            try:
                logging.debug("CREATE PARTITION: %s" % (stmt,))
                self.cur.execute( stmt )
                self.known_tables[name] = {}
            except psycopg2.ProgrammingError,e:
                # its fine if the table already exists
                if not str(e).endswith( ' already exists\n'):
                    logging.error("ERR: %s %s" % (type(e),e))
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
        # only return most recent answer?
        if recent:
            stmt = stmt + ' ORDER BY created_at DESC LIMIT 1 '
        stmt = stmt + ';'
        logging.debug(" %s" % (stmt,))
        self.cur.execute( stmt )
        return self.cur.fetchall()

    def insert( self, table, time, context, data ):
        self.stats['inserted'] = self.stats['inserted'] + 1
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
    
    def hash_pre_msg_process( self, msgs, current_table ):
        """ scan through all of the messages and determine a concise query string to use to bulk fetch data """
        self.context_fields = self.pre_msg_process_tables[current_table]['fields']
        self.context_fields_missing_ok = self.pre_msg_process_tables[current_table]['missing_ok']
        # if we know that the table is partitioned, then lets ensure we query on partitions if possible
        ctxs = {}
        mappings = {}
        seen = {}
        dups = {}
        
        for m in msgs:

            this_table_name, parent_table_name = self.table_name( m['_meta']['spec'],m['_meta']['group'], m['context'], m['data'] )
            if not this_table_name.startswith( current_table ): 
                raise Exception('non identical spec/groups in long message: %s / %s' % (current_table, this_table_name))
            if 'context' in m:
                if not this_table_name in ctxs:
                    ctxs[this_table_name] = []
                    
                # build a tree for value lookups
                if not this_table_name in mappings:
                    mappings[this_table_name] = {}
                here = mappings[this_table_name]

                this = {}
                full_this = {}
                # just keep a tree of values, with each level being the context field in order
                for f in self.context_fields:

                    ok = False
                    if f in m['context']:
                        ok = True
                    elif not self.context_fields_missing_ok and f in self.pre_msg_process_tables[current_table]['fields_required']:
                        raise Exception( 'field %s is required in pre_msg_processing' % (f,))
                    elif self.context_fields_missing_ok:
                        ok = False

                    if f in m['context']:
                        
                        v = str(m['context'][f])
                        # logging.error("F: %s\tV: %s" % (f,v))
                        if not v in here:
                            here[v] = {}
                        here = here[v]

                        # logging.error("  add %s\tto %s? %s\t%s" % (f,this_table_name,ok,v))
                        if ok:
                            this[f] = v
                
                # dedup to reduce queried args, and keep a count of overlaps (eg ips on same mac addreses)
                key = dict_to_kv( this, keys=self.context_fields, missing_ok=self.context_fields_missing_ok )
                if not key in seen:
                    seen[key] = []
                # hmm.... in case there are duplicates, lets merge the context and data and obtain uniques for later lookup
                combined = dict( m['context'].items() + m['data'].items() )
                h = dict_to_kv( combined )
                if not h in dups:
                    seen[key].append( combined )
                    if len(seen[key]) == 1:
                        ctxs[this_table_name].append( this )
                dups[h] = True
                    
        return ctxs, seen, mappings
        
        
    def pre_msg_process( self, msg, envelope ):
        # basically a pre fetch for data
        
        # logging.warn("="*80)
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
        self.dups = {}

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
            try:
                ctxs, self.msg_contexts, self.tree = self.hash_pre_msg_process( msg, self.current_table_name )
                self.stats['messages'] = len(msg)
                
                for table in ctxs:
                
                    # do the caching
                    if len( ctxs[table] ):
                        # logging.error("QUERY table: %s, CTX: %s, TREE: %s" % (table,ctxs[table],self.tree[table]))

                        # so if we're doing a merge on the context, we don't know the cache key
                        # so we have to iterate through our ctxs and see if any of them match
                        for d in self.query( table, ctxs[table], operation='OR' ):

                            ptr = self.tree[table]
                            # construct the key with something we know will match later, trawl the tree
                            # logging.error("   GOT: %s" % (d['context'],))
                            found_fields = []
                            for f in self.context_fields:
                                if f in d['context']:
                                    # logging.error(" field %s in %s\tat %s" % (f,d,ptr))
                                    # search tree
                                    v = str(d['context'][f])
                                    # logging.error("    PTR1: %s\t%s\t%s" % (f,ptr,v))
                                    if v in ptr:
                                        found_fields.append( f )
                                        ptr = ptr[v]
                                        # logging.error("    PTR2: %s\t%s" % (f,ptr,))

                            # logging.error("FOUND FIELDS: %s" % (found_fields,))
                            key = dict_to_kv( d['context'], keys=found_fields )
                            # logging.error("   - key=%s\tc=%s,\tfields=%s->%s" % (key,d['context'],self.context_fields,found_fields) )
                            if not key in self.cache:
                                self.cache[key] = []
                            self.cache[key].append( d )
                            self.stats['pre_cached'] = self.stats['pre_cached'] + 1

                            # add a long key into cache too to exact match
                            # logging.error("D: %s %s" % (d['context'],d['data']))
                            full_key = dict_to_kv( d['context'] )
                            if not full_key == key:
                                # logging.error("FULL KEY: %s\t%s" % (full_key,d))
                                if not full_key in self.cache:
                                    self.cache[full_key] = []
                                self.cache[full_key].append( d )

                            self.pre_msg_queried = True
                        # logging.warn("-"*80)
            except Exception,e:
                logging.warning("%s %s" % (type(e),e))
                self.db.rollback()
                self.cache = {}
                self.pre_msg_queried = None
        # for k,v in self.cache.iteritems():
            # logging.error(" cached %s\t%s" % (k,len(v)))
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
        self.dups = {}
        
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
                stmt = 'DELETE FROM %s WHERE id in (%s)' % ( table, ','.join( [ str(i) for i in ids ] ) )
                logging.info(" %s" % stmt)
                self.cur.execute( stmt )
            except Exception,e:
                logging.error("ERR bulk delete: %s %s" % (type(e),e))
                raise e
                
    def _save( self, doc, time, meta, context, data, time_delta ):

        # see if there are any differences in the this set
        diff = self.different( doc, context, data, partial=False )
        logging.debug("doc (%s): c=%s\td=%s" % (diff,doc['context'],doc['data']) )

        # if we have a 'ignore_data', then we don't care if d is True, so force - ensure we don't overwrite the created_at time
        update_created_at = True
        if 'ignore_data' in meta and meta['ignore_data']:
            update_created_at = False
            diff = None
            
        if 'merge_context' in meta and meta['merge_context']:
            new_context = self.flatten( doc['context'], context )
            # if new context has more fields, assume it's the same then
            diff = False if len(new_context) >= len(context) else None
            logging.debug(" contexts (%s) c=%s\t-> c=%s" % (diff,context,new_context))
            context = new_context
        
        if 'merge_data' in meta and meta['merge_data']:
            # check to see if the kv are same for keys that are common; always assume data is smaller
            # set d := None if there is a difference so that we do a full update
            # for k,v in data.iteritems():
            #     if not k in docs[0]['data'] or not docs[0]['data'][k] == data[k]:
            #         d = None                
            # if d == None:
            # check to see if the merge set would be different from what we have
            this_data = self.flatten( doc['data'], data )
            if cmp( this_data, doc['data'] ) == 0:
                # no need to do full merge
                diff = False
            else:
                # need to update what's in the db
                diff = None
                logging.debug(" merging data d=%s\t+ %s" % (doc['data'],data))
                data = self.flatten( doc['data'], data )
            update_created_at = False

        # actually do somethign now
        if diff == True:
            # 1b) if there are differences in the data, then archive the current and update links
            # logging.error("THAT %s" % (context,))
            self.stats['archived'] = self.stats['archived'] + 1
            self.archive_and_update( meta['spec'], meta['group'], doc, time, context, data )

        elif diff == False:
            # 2) check timestamps, if too long, then archive the old one
            if not time_delta == None and doc['updated_at'] + time_delta < time:
                logging.warn("old data %s\t%s: %s " % (time_delta, doc['updated_at']+time_delta-time, context ))
            # 1a) if no difference from the stored doc, then just update the time stamps
            self.stats['bulk_updated'] = self.stats['bulk_updated'] + 1
            self.update_ids.append( doc['id'] )

        elif diff == None:
            # minor updates
            self.stats['updated'] = self.stats['updated'] + 1
            # self.update_item( meta['spec'], meta['group'], docs[0], time, context, data, update_created_at=update_created_at )
            self.update_item( self.table, doc, time, context, data, update_created_at=update_created_at )

        else:
            logging.error("difference value unknown! %s" % (diff,))


    def is_skip_save( self, time, meta, context, data, time_delta ):
        # skip subnets that we don't care about as defined in configuration files
        skip = False
        if ( meta['spec'] == 'layer3' and meta['group'] == 'subnets' ):
            if 'prefix' in context and 'netmask' in context:
                this = ipaddress.IPv4Network( "%s/%s" % ( context['prefix'], context['netmask'] ))

                for s in self.subnets:
                    if this.overlaps( s ):
                        skip = True
                        break
        return skip

    def save( self, time, meta, ctx, data, time_delta ):
        """ do something with this single datum """

        # flatten the document
        context = self.flatten( {}, ctx )
        data = self.flatten( {}, data )

        # ignore dups
        combined_key = dict_to_kv( dict( context.items() + data.items() ) )
        if combined_key in self.dups:
            # logging.error("DUPLICATE! %s" % (combined_key,) )
            return
        self.dups[combined_key] = True
        
        # logging.warn("SAVE >>> %s: %s %s" % (time,context,data))
            
        # skip subnets that we don't care about as defined in configuration files
        if self.is_skip_save( time, meta, context, data, time_delta ):
            s = 'skipping %s %s: subnet %s' % (meta['spec'],meta['group'],this)
            raise UserWarning, s

        # 0) do we currently have the item in our db/cache? (see pre_process for cache entries)
        
        # deal with delayed_contexts where we may only have a paritial entry
        # this will throw an exception if the context doesn't have all necessary fields
        # eg with vlans on caching__hosts
        key = dict_to_kv( context, keys=self.context_fields, missing_ok=self.context_fields_missing_ok )
        # logging.warn("SAVE KEY: %s" % (key,) )
        docs = self.cache[key] if key in self.cache else []

        # merge in keys for delayed contexts (ie put fields back into the context )
        if 'delayed_context' in meta and len( meta['delayed_context'] ):
            for c in meta['delayed_context']:
                # logging.error("DELAYED field=%s:\tc=%s\td=%s" % (c,context,data))
                if c in data.keys():
                    context[c] = data[c]
                    del data[c]
            # logging.error("DELAYED2: %s %s" % (context,data))

        # TODO: check that only one matching document is found, if more, then merge the documents 
        # together, taking into account the last_seen and first_seens and if history exists

        no_docs = len(docs)
        no_msgs = len(self.msg_contexts[key])

        # if no_docs > 1 or no_msgs > 1:
        #     logging.error(" context: %s\t key: %s\tindb: %s\tctxs: (%s) %s" % (context,key,no_docs,no_msgs,self.msg_contexts[key]) )
            
        # 1) one cache hit is good
        if no_docs == 1:
            
            # 1a) one new or existing record to update
            if no_msgs <= 1:

                self._save( docs[0], time, meta, ctx, data, time_delta )

                # TODO: deal with fact that the doc could be old and that we should archive it regardless

            # 1b) hmm... we have multiple msgs, will need a new entry for each
            else:
                
                logging.error("1>> SAVE: c=%s\td=%s" % (context,data))
                logging.error(  " #1b) MULTI MSGS doc: c=%s\td=%s" % (docs[0]['context'],docs[0]['data']))
                # for m in self.msg_contexts[key]:
                    # logging.error("    msg: %s" % (m,))
                # search cache for more specific entry?
                this_key = dict_to_kv( context )
                if this_key in self.cache and len(self.cache[this_key]) == 1:
                    # logging.error("      %s\t(%s)\t%s" % (this_key, len(self.cache[k]),self.cache[k]))
                    logging.error("    GOT IT with %s" % (this_key,))
                    self._save( self.cache[this_key][0], time, meta, context, data, time_delta )
                else:
                    # for m in self.msg_contexts[key]:
                    #     logging.error("    msg: %s" % (m,))
                    # if we have a merge, then consider when this context has less keys than what's int he cache
                    logging.error("      doc ctx: %s,\tcontext %s" % (docs[0]['context'], context))
                    if 'merge_context' in meta and meta['merge_context'] and len(context) < len(docs[0]['context']):

                        
                        logging.error("    MERGE UPDATE all records?")
                        
                    else:
                        # TODO: insert?
                        logging.warn("INSERTING: key=%s\ttable=%s\tc=%s " % (key,self.table,context))
                        self.insert( self.table, time, context, data )

                    # logging.error("      %s\t(%s)\t%s" % (this_key, len(self.cache[k]),self.cache[k]))

                    
                # TODO: insert this context, data
                # we have one doc, need to replicate for each message?
                # do an exact match on doc['context'] and context vars

        # 2) just insert the new document
        elif no_docs == 0:

            logging.warn("INSERTING: key=%s\ttable=%s\tc=%s " % (key,self.table,context))
            self.insert( self.table, time, context, data )
        
        # 3)  if there are multiple matches of docs, lets see if we can mege them together
        elif no_docs > 1:
                        
            def mark_newest_for_deletion( array ):
                t = None
                oldest = None
                if len(array) > 1:
                    for i in array:
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

            # def build( ctx, keys=[] ):
            #     found_fields = []
            #     for f in self.context_fields:
            #         if f in ctx:
            #             v = str(ctx[f])
            #             found_fields.append( f )
            #     return dict_to_kv( ctx, keys=found_fields )
            def merge_docs( array, keys=[] ):
                these = {}
                for a in array:
                    # k = build( a['context'], keys=keys )
                    k = dict_to_kv( a['context'], keys=keys )
                    if not k in these:
                        these[k] = []
                    these[k].append( a )
                return these

            # determine unique matches based on the fields of the dict
            this_cache = merge_docs( docs, keys=context.keys() )

            no_this_cache = len(this_cache)
            no_cache_hits = 0
            this_key = dict_to_kv( context )
            if this_key in self.cache:
                no_cache_hits = len(self.cache[this_key])
                        
            # 3a) if there's only one unique message, then merge if they have the same (sub)set of key/value pairs
            if no_msgs == 1:
                        
                logging.error("3>> SAVE: c=%s\td=%s" % (context,data))

                logging.error(" = %s\tno_this_cache: %s\tno_cache_hits: %s" % (this_key,len(this_cache),no_cache_hits))

                if no_this_cache == 1:

                    logging.error(" #3a) msg: c=%s\td=%s" % (context,data) )
                    if this_key in self.cache:
                        logging.error("    GOT IT with key %s" % (this_key,))
                        self._save( self.cache[this_key][0], time, meta, context, data, time_delta )
                        
                    else:

                        # what to do? add new one?
                        logging.error("    WHAT TO UPDATE ON DB?")

                    logging.error("  MERGE INTO ONE?")
                    # iterate thorugh all items for this key and see if the records should be related
                    # or not. we do this via 

                    # c={'vlan': '1922', 'mac_address': '34e6.d729.d645'}, d={}
                    # c={'vlan': '1922', 'ip_address': '134.79.224.175', 'mac_address': '34e6.d729.d645'}, d={'device': 'swh-b267.slac.stanford.edu', 'physical_port': 'Fa1/0/42'}
                    for i in self.cache[key]:
                        logging.error("    %s:\tc=%s, d=%s" % (i['id'],i['context'],i['data']))

                    
                # single cache entry
                elif no_this_cache == 0:

                    for k,v in this_cache.iteritems():
                        logging.error("    %s\t(%s)" % (k,len(v)))
                        for w in v:
                            logging.error("      %s: c=%s\td=%s" % (w['id'],w['context'],w['data']))

                    logging.error(" #3b) msg: c=%s\td=%s" % (context,data) )
                    logging.error("  NO HITS")
                    # insert?
                    
                # multiple cache entries
                else:

                    logging.error(" #3c) msg: c=%s\td=%s" % (context,data) )
                    logging.error("  too many different docs (%s)..." % (len(this_cache),))
                    # try an exact match
                    if this_key in self.cache:
                        if len(self.cache[this_key]) == 1:
                            logging.error("    GOT IT with key %s" % (this_key,))
                            self._save( self.cache[this_key][0], time, meta, context, data, time_delta )
                        else:
                            for k,v in this_cache.iteritems():
                                logging.error("    %s\t(%s)" % (k,len(v)))
                                for w in v:
                                    logging.error("      %s: c=%s\td=%s" % (w['id'],w['context'],w['data']))
                            logging.error("    DON'T GOT IT")
                            
                    elif this_key in this_cache and len(this_cache[this_key]) == 1:
                        logging.error("    GOT IT with key %s" % (this_key,))
                        self._save( this_cache[this_key][0], time, meta, context, data, time_delta )
                        
                    else:

                        logging.warn("INSERTING: key=%s\ttable=%s\tc=%s " % (key,self.table,context))
                        self.insert( self.table, time, context, data )
                        # update all near matches?
                    # dunno what to do...
                    
                    # TODO: merge a series of docs into teh same one?
                    

                # # get oldest
                # distinct = {}
                # for i in docs:
                #     # take a hash of the context to get uniques
                #     h = dict_to_kv( i['context'] )
                #     if not h in distinct:
                #         distinct[h] = []
                #     distinct[h].append(i)
                #
                # for h in distinct:
                #     mark_newest_for_deletion( distinct[h] )
                #
                # # if we're doing merge contexts, then we should do so if we have multiple's left
                # if 'merge_context' in meta and meta['merge_context']:
                #     for h in distinct:
                #         if len(distinct[h]) > 1:
                #             logging.error("SHOULD PROBABLY TRY TO MERGE %s:" % (h,))
                #             for item in distinct[h]:
                #                 logging.error("  c=%s\td=%s\tid=%s" % (item['context'],item['data'],item['id'] ))
                #             mark_newest_for_deletion( distinct[h] )
                #
                #     # TODO iterate though all docs and see if there's any to merge, eg missing fields which otherwise would make the records for hte same thing
                #     # logging.error("distinct multiples: \n%s" % (pformat(distinct,width=230),) )

            elif no_msgs > 1:
                
                logging.error(  " #4) MANY MANY DOCS: %s\tMSGS: %s:\tc=%s\td=%s" % (no_docs,no_msgs,context,data))

                if this_key in self.cache and len(self.cache[this_key]) == 1:
                    logging.error("    GOT IT with key %s" % (this_key,))
                    self._save( this_cache[this_key][0], time, meta, context, data, time_delta )
                else:
                    logging.warn("INSERTING: key=%s\ttable=%s\tc=%s " % (key,self.table,context))
                    self.insert( self.table, time, context, data )
                    # for i in docs:
                    #     logging.error("   %s:\tc=%s\td=%s" % (i['id'],i['context'],i['data']) )
                    

            elif no_msgs == 0:
                # not possible
                logging.error("ERROR")


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
    
