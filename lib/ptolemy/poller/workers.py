from ptolemy.poller.driver import YAMLDriver
from ptolemy.poller.agent import AgentTimeout, NetSNMP, Ping, NetConfig
from ptolemy.poller.driver import RefNotFound

from slac_utils.managers import Worker, TASK_RECEIVED, TASK_PROCESSING, TASK_COMPLETE, TASK_ERRORED, TASK_INFO
from slac_utils.timeout import timeout
from slac_utils.time import now
from slac_utils.messages import Message

from yaml import load

try:
    from setproctitle import setproctitle
except:
    def setproctitle(blah):
        pass

from copy import copy
from time import time
from datetime import datetime, timedelta
import signal
import sys
import traceback
from re import match, search
from types import ModuleType
from os.path import basename

from pprint import pformat
import logging
import random


AGENT_CLASSES = {
    'SNMP':         NetSNMP,
    'NetConfig':    NetConfig,
    'Ping':         Ping,
}


class TimedOut(Exception):
    pass

class NameResolutionError(Exception):
    pass
    
class Gatherer( object ):
    """
    wrapper around polling driver to facilitate data structure consistency for gathered data
    """
    agents = {}
    agent_kwargs = {
        'NetConfig': ( 'netconfig_config', )
    }
    
    schema = None
    schema_dir = None
    
    template = None
    
    
    def __init__( self, schema_dir=None, **kwargs ):
        
        # logging.error("GATHERER KWARGS: %s" % (kwargs,))
        self.schema_dir = schema_dir
        self.agents = {}
        for a in AGENT_CLASSES:
            if AGENT_CLASSES[a]:
                this_kwargs = {}
                if a in self.agent_kwargs:
                    for i in self.agent_kwargs[a]:
                        if i in kwargs:
                            this_kwargs[i] = kwargs[i]
                        else:
                            logging.error("agent kwargs %s not defined" % (i,))
                # logging.debug("initializing agent %s kwargs: %s" % (a,this_kwargs))
                self.agents[a] = AGENT_CLASSES[a]( **this_kwargs )
        
        # import external modules
        # sys.path.append( self.driver_dir )
        # import user_scripts


    def _fetch( self, host, this_driver, **kwargs ):

        try:

            opts = {}
            for k,v in kwargs.iteritems():
                opts[k] = v
    
            # deal with standard definitions first
            # logging.warn('+ %-35s --driver=%s' % (host,driver) )
            res = self.collect( host, this_driver, opts )
            logging.debug("collected: \n%s" %(pformat(res)) )
            res = self.process( res, this_driver )
            logging.debug("processed: \n%s" %(pformat(res)) )
            
            # keep an eye on any iterative polling we need to make (eg spanning tree on ciscos)
            # now deal with iterative definitions
            inside = 'iterative_groups'
            iter_meta = None
            if this_driver.groups( inside=inside ):
                iter_meta = { 'data': {} }
                iter_meta['group'], iter_meta['field'], iter_meta['var'] = self._get_iterative_meta( this_driver, inside=inside )
                # logging.debug("iterate %s" % (iter_meta,))

            keys = {}
            additional_keys = {}
            forced_keys = {}
            for g in res:
                # logging.debug("group: %s" % (g,))
                keys[g] = this_driver.key_name(g)
                additional_keys[g] = this_driver.additional_key_names( g )
                forced_keys[g] = this_driver.forced_key_names( g )

                # collect iter data if necessary
                if iter_meta:
                    if iter_meta['group'] == g:
                        iter_meta['data'] = res[g].copy()
                    # logging.debug("ITER: %s %s" % (g,iter_meta))

            # logging.error("post processed: \n%s" %(pformat(iter_meta)) )

            if iter_meta:
                iter_res = {}
                group_ignore = [ '__with__' ]
                failed = 0
                values = [ i for i in self._get_iterative_values( this_driver, iter_meta, inside=inside )]
                logging.debug('conducting iterative fetch on %s with values %s'%(iter_meta['var'],values))
                base_community = opts['snmp_community']
                for val in values:
                    try:
                        logging.debug("poll: iterating on %s=%s" % (iter_meta['var'], val))
                        # overwrite the snmp string
                        opts['snmp_community'] = base_community + '@' + str(val)
                        iter_res[val] = self.process( \
                            self.collect( host, this_driver, opts, inside=inside, ignore=group_ignore ), \
                            this_driver, \
                            inside=inside, ignore=group_ignore, parent_results=res )
                        # logging.error("post iter (%s) process: %s" % (val, iter_res[val],))
                    except AgentTimeout,e:
                        # some vlans don't return anything...
                        pass
                    except RefNotFound,e:
                        # if most failed, then assume the drivers bad and that we should skip this driver
                        failed = failed + 1
                        if failed == len(values):
                            raise RefNotFound( 'iterative polling failed' )
                        pass
                    except TimedOut,e:
                        raise e
                    except Exception,e:
                        # logging.error("FIXME! could not complete %s using %s iteration %s=%s due to (%s) %s\n%s" % (host, driver, var_name, val, type(e), e, traceback.format_exc() ) )
                        logging.error("    FIXME! iterative groups failed on a loop (%s) %s\n%s"%(type(e),e,traceback.format_exc()))

                # return results throw exception
                if len( iter_res.keys() ) == 0:
                    raise Exception, 'iterative groups polling failed'
                for val in iter_res.keys():
                    # logging.error("VAL %s " % (val,))
                    for g in iter_res[val].keys():
                        if not g in group_ignore:
                            this_g = "%s@%s=%s" % (g,iter_meta['var'],val)
                            keys[this_g] = this_driver.key_name(g, inside=inside)
                            additional_keys[this_g] = this_driver.additional_key_names( g, inside=inside )
                            # logging.error("ITER KEYS: %s: %s, %s" % (this_g,keys[this_g],additional_keys[this_g]))
                            res[this_g] = iter_res[val][g]

            # if self.schema_dir:
            #     self.validate( res, self.template )

        except Exception, e:
            s = str(e)
            if s == 'snmp_sess_synch_response (2): Unknown Error':
                # timeout of agent
                raise TimedOut('agent')
            elif s == '':
                # this /should/ be a name resolve error
                raise NameResolutionError(host)
            else:
                raise e
            
        # logging.error("RETURN: \n%s" %(pformat(res)) )
        return keys, additional_keys, forced_keys, res

    def fetch( self, host, driver, timeout=300, **kwargs ):
        """
        _fetch will return a pure dict representation of the data
        we need to provide arrays of dicts for each group
        """
        spec = driver.split('/')[-2]
        k = '%s:%s' % (host, spec)

        # load driver
        # logging.debug('initializing %s with driver %s' % (k, driver,))
        this_driver = None
        try:
            this_driver = YAMLDriver( driver )
        except Exception, e:
            logging.error("%s driver load error %s: %s" % (k, driver,e))
            raise e

        res = {}
        # create a timer in case of runaway jobs
        sig = None
        
        def _timeout_handler( *args ):
            raise TimedOut, 'timed out'
            
        try:
            if timeout and timeout > 0:
                signal.alarm(0)
                sig = signal.signal(signal.SIGALRM, _timeout_handler)
                # logging.debug("%s setting timeout: %s" % (k,timeout,))
                signal.alarm( int(timeout) )
                
            # logging.error("FETCH! %s %s" % (host, this_driver))
            keys, additional_keys, forced_keys, res_dict = self._fetch( host, this_driver, **kwargs )
            # logging.error("RES1 %s" % (res_dict,))
            res = this_driver.post_remap( res, res_dict, keys )
            # logging.error("RES2 %s" % (res,))
            
            logging.info("%s finished fetching data" % (k,))
            for g in res.keys():
                # remove the group?
                # logging.error("CLEAN %s"%g)
                r = this_driver.clean( g )
                if r == True:
                    del res[g]
                # tidy up key
                remove_key, field = this_driver._remove_key(g)
                # logging.error("KEY: %s %s" % (remove_key,field))
                if remove_key:
                    # logging.error("REMOVE %s %s" % (g,keys))
                    keys[g] = None
        except Exception, e:
            raise e
        finally:
            if sig:
                signal.signal(signal.SIGALRM, sig) 
            signal.alarm(0)

        # logging.info("%s fetch returning" % (k,))
        
        return keys, additional_keys, forced_keys, res
        
    
    # def validate( self, data, template ):
    #     """
    #     validate the returned data structure to that defined in the template
    #     """
    #     # load the yaml and convert to dict usable by voluptuous
    #     try:
    #         s = file( schema_file ,'r' )
    #     except IOError,e:
    #         m = search( '\](?P<msg>.*)\: ', str(e) )
    #         if m:
    #             err = m.group('msg')
    #             raise IOError, "could not open validation template '" + str(filepath) + "': " + str(err)
    #     template = load(s)


    def merge_options( self, agent_name, options, agent_options ):
        opts = {}
        for k,v in options.iteritems():
            a, tmp, i = k.partition('_')
            if a.lower() == agent_name.lower():
                opts[i.lower()] = v
        return dict( agent_options.items() + opts.items() )

    def _collect( self, agent_name, refs, host, driver, opts ):
        out = {}
        if len( refs ) > 0:
            logging.debug("fetching refs: %s using agent %s, opts: %s" %(refs, agent_name,opts) )
            with self.agents[agent_name] as agent:
                for f,i,v in agent.fetch( host, refs, **opts ):
                    yield f,i,v
        # force __exit__
        try:
            self.agents[agent_name].__exit__()
        except AssertionError,e:
            pass
        return
        
    def collect( self, host, driver, kwargs, inside='groups', ignore=[] ):
        out = {}
        for a, agent_opts in driver.agents():
            opts = self.merge_options( a, kwargs, agent_opts )
            logging.debug("collecting...")
            refs = driver.refs( a, inside=inside, ignore=ignore )
            for f,i,v in self._collect( a, refs, host, driver, opts ):
                # logging.debug("FIV %s %s %s"%(f,i,v))
                if not f in out:
                    out[f] = {}
                if not i in out[f]:
                    out[f][i] = {}
                out[f][i] = v
        # logging.debug("GOT: " + pformat(out))
        return out

    def _get_iterative_meta( self, driver, inside='iterative_groups', ctrl_stanza='__with__'):
        using = [ i for i in driver.defs( ctrl_stanza, inside=inside ) ].pop()
        var_name = using.keys().pop()
        ref_group, ref_field = using[var_name]['ref'].split('::')
        logging.debug("  iterate using variable %s from field %s" % ( var_name, ref_field) )
        return ref_group, ref_field, var_name

    def _get_iterative_values( self, driver, ref_meta, inside='iterative_groups', ctrl_stanza='__with__' ):
        ds = {
            ref_meta['field']: ref_meta['data']
        }
        for remap in driver.defs( ctrl_stanza, inside=inside ):
            # remove group from ref
            remap[ref_meta['var']]['ref'] = ref_meta['field']
            logging.debug("  processing iterative def ref %s" %(remap,))
            for f, item in remap.items():
                # logging.debug( " ds %s, item %s" % (ds, item))
                for i in driver.remap( ds, ref_meta['field'], item, remap ):
                    yield i
        return
        

    def process( self, result, driver, inside='groups', ignore=[], parent_results={} ):
        """ determine the data structure changes required to make the output 'conformant' """
    
        # process each item in each of the the groups
        wanted_fields = {}
        wanted_refs_count = {}    # check for other fields that require this ref, and clone datastructure if required
        wanted_refs = {}
        for g in driver.groups( inside=inside ):
            if g in ignore:
                continue
            logging.debug("processing group %s" %(g,) )
            for d in driver.defs(g, inside=inside ):
                for k,v in d.items():
                    wanted_fields[k] = True
                    if 'ref' in v:
                        if not v['ref'] in wanted_refs_count:
                            wanted_refs_count[v['ref']] = 0
                        wanted_refs_count[v['ref']] = wanted_refs_count[v['ref']] + 1
                        # logging.warn("  adding " + str(v['ref']) + " -> " + str(wanted_refs_count[v['ref']]))
                    if not k in wanted_fields:
                        wanted_fields[k] = 0

            # deal with when we want to reuse the same ref many times
            # logging.debug("  wanted refs: " + str(wanted_refs_count))
            for r in wanted_refs_count:
                if wanted_refs_count[r] > 1:
                    if not r in result:
                        raise RefNotFound, "could not copy %s (%s)" % (r,result.keys())
                    wanted_refs[r] = result[r].copy()
            
            # do the remap
            for remap in driver.defs( g, inside=inside ):
                logging.debug("  processing def " + str(remap))
                for f, item in remap.items():
                    # logging.debug("  >> %s (%s)" %( f,item ))
                    result = driver.remap( result, f, item, remap, parent_data=parent_results )
                    # logging.debug("   >> result: %s" % (result,))
 
                    # count down
                    # logging.debug("    item: %s" % (item,))
                    if 'ref' in item:
                        wanted_refs_count[item['ref']] = wanted_refs_count[item['ref']] - 1
                        # logging.debug("     ref: %s = %s" % (item['ref'], wanted_refs_count) ) #[item['ref']]))
                        if wanted_refs_count[item['ref']] > 0:
                            # logging.debug("      copying ")
                            for x,y in wanted_refs[item['ref']].items():
                                # logging.debug("        x: %s\t%s\n" % (x,y))
                                if not item['ref'] in result:
                                    result[item['ref']] = {}
                                result[item['ref']][x] = y

        # logging.warn("processing: \n%s" %(pformat(result)) )

        # clear
        del wanted_refs
        del wanted_refs_count

        # clean items (remove non-defined defs)
        diff = [ k for k in result.keys() if k not in wanted_fields ] 
        # logging.debug("  deleting: " + str(diff))
        for d in diff:
            del result[d]

        # reorangise data structure to be ordered by the group name
        new_result = {}
        for g in driver.groups( inside=inside ):
            defs = []
            for d in driver.defs( g, inside=inside ):
                for k,v in d.items():
                    defs.append( k )
            new_result[g] = {}
        
            for f,item in result.items():
                if f in defs:
                    for k,v in item.items():
                        # logging.debug(" g: %s, f: %s, k: %s, v: %s" % (g,f,k,v))
                        # organise so that the index is the field
                        if driver.process_group_by_key(g, inside=inside):
                            if not k in new_result[g]:
                                new_result[g][k] = {}
                            if v == 'None':
                                v = None
                            new_result[g][k][f] = v
                        # organise so that the field is the index
                        else:
                            if not f in new_result[g]:
                                new_result[g][f] = {}
                            new_result[g][f][k] = v
            
            # clean (delete) items marked as such
            for d in driver.defs( g, inside=inside ):
                for f,v in d.items():
                    if 'clean' in v:
                        if driver.process_group_by_key(g, inside=inside):
                            logging.debug('  removing by key %s %s %s' % (g,k,f) )
                            for k in new_result[g].keys():
                                if f in new_result[g][k]:
                                    del new_result[g][k][f]
                                if len(new_result[g][k].keys()) == 0:
                                    del new_result[g][k]
                        else:
                            logging.debug('  removing by field %s %s %s' % (g,f,k) )
                            del new_result[g][f]
            
        del result
        
        # logging.error('results:\n' + pformat( new_result ) )
        return new_result

class Poller( Worker ):
    """
    worker to poll a device
    """
    action = 'polling'
    gatherer = None
    proc_name = 'ptolemy polld'
    prefetch_tasks = 1 # only take one job at once

    def  (self, *args, **kwargs):
        super( Poller, self ).setup( *args, **kwargs )
        self.gatherer = Gatherer( **kwargs )
    
    def process_task( self, job, stats={} ):
        # don't bother with 'old' tasks
        # logging.error("PROCESS: %s" % (job,) )
        if 'timestamp' in job:
            t = 60
            if now() - job.timestamp > timedelta( seconds=t ):
                raise Exception, 'old test (>%ss)' % (t,)
            # logging.error( 'task %s %s -> %s' % (job.timestamp, t, t - job.timestamp))
        if 'spec' in job.context and 'device' in job.context:
            s = '%s %s:%s' % (self.proc_name, job.context['device'], job.context['spec']) 
            try:
                if 'driver' in job.data:
                    s = '%s with %s' % (s, basename(job.data['driver']))
            except:
                pass
            setproctitle(s)
            return poll( job, self.gatherer, self.logger )

    def post_task( self, job ):
        setproctitle( self.proc_name )

def format_msg( task_id, time, spec, group, device, data, keys=[], forced_keys=[] ):
    # logging.warn( 'KEYS: %s, FORCED: %s' % (keys,forced_keys))
    msg = Message( 
        meta={
            'task_id':  task_id,
            'type':     'task',
            'spec':     spec,
            'group':    group,
        },
        context={
            'device':   device,
        },
        data=data,
    )
    msg.timestamp = time
    msg._meta['key_name'] = keys
    
    # create routing key
    parts = []
    # logging.error('JOB: %s' % (job,))
    parts.append( 'spec.%s' % (spec,) )
    parts.append( 'group.%s' % (group,) )
    parts.append( "device.%s" % (".".join(reversed( device.split('.'))),) )
    parts.append( 'task_id.%s' % (task_id,))

    msg._meta['key'] = '.%s.' % ( '.'.join(parts), )
    
    if group in forced_keys and forced_keys[group]:
        for k in forced_keys[group]:
            msg['context'][k] = None
    
    return msg

def poll( job, gatherer, logger=logging ):
    
    o = job.data
        
    # determine the driver to use
    drivers = []
    if not 'driver' in job.data and 'probe_with_drivers' in job.data:
        drivers = job.data['probe_with_drivers']
    elif 'driver' in job.data:
        drivers.append( job.data['driver'] )
        del o['driver']
    else:
        raise Exception, 'no driver defined for job'
    
    # set timeout
    # really? why 450?
    timeout = 900
    if 'frequency' in job._meta and job._meta['frequency'] > 0:
        # logging.error("TIMEOUT: %s" % (job._meta))
        timeout = min( int(job._meta['frequency']), timeout )

    #if search( r'ssrl', job.context['device'] ):
    # raise Exception, 'skipping'
    
    # attempt each driver listed
    while len(drivers) > 0:

        t = int(time())
        # work on the next driver
        d = drivers.pop(0)

        try:

            # logging.debug("starting poll: %s:%s, with %s, timeout %s (%s)" % (job.context['device'],job.context['spec'], d, timeout, o))
            keys, additional_keys, forced_keys, data = gatherer.fetch( job.context['device'], d, timeout=timeout, **o )

            # notify upstream that this succeeded
            job._meta['state'] = TASK_INFO
            job.data['driver'] = d
            if not isinstance( logger, ModuleType ):
                logger.info( 'success with driver %s' % (d,), job )
                
            for g in data.keys():
                # logging.warn("g: %s, keys: %s, additional_keys: %s, forced: %s" % (g,keys, additional_keys,forced_keys))
                i = None
                if 'task_id' in job._meta:
                    i = job._meta['task_id']
                # map the key backwards
                this_g = g
                if not g in keys:
                    this_g, tmp, i = g.partition('@')
                this_keys = additional_keys[this_g]
                # logging.error("HERE %s this_keys %s" % (keys[this_g],this_keys))
                add = []
                if keys[this_g]:
                    add = [ keys[this_g] ]
                if this_keys == None:
                    this_keys = add
                elif not keys[this_g] in this_keys:
                    this_keys = add + this_keys
                # logging.warn("KEYS: %s:%s %s = %s" % (job.context['device'],job.context['spec'],g,this_keys))
                yield format_msg( i, t, job.context['spec'], g, job.context['device'], data[g], keys=this_keys, forced_keys=forced_keys )
            data = {}
            return
            
        except TimedOut,e:
            # if a driver is timing out, then check to see if we are probing (len(drivers)), and report as appropriate
            # this allows more efficient drivers with lower priorities to take precedence (eg CLI)
            if len(drivers) == 0:
                raise TimedOut( 'timed out' ) #job.context['device'] )
        
        except NameResolutionError, e:
            raise e
        
        except Exception,e:
            if isinstance( logger, ModuleType ):
                logging.warn("%s:%s driver %s failed (left %d): %s %s" % (job.context['device'],job.context['spec'],d.split('/')[-1],len(drivers),type(e),e))
                # logging.warn("TYPE: %s %s " % (type(e),e))
    
    raise Exception, 'no suitable driver found'

