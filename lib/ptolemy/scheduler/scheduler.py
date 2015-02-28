#
# a scheduler to put tests into an ampq for ptolemy-poll workers to conduct the tests
# reads in config files
#

import heapq
from ConfigParser import ConfigParser
import re
from random import uniform
import os

from slac_utils.time import utcfromtimestamp
import time
# from threading import Timer
from datetime import timedelta, datetime

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


import logging


class SchedulingException( Exception ):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class Schedule( object ):
    
    def __init__(self):
        self.heap = []
        
    def add( self, time, d ):
        heapq.heappush( self.heap, ( time, d ) )
        
    def pop( self ):
        time, d = heapq.heappop( self.heap )
        return time, d



class ScheduleParser( object ):
    
    delta_regex = re.compile( r'(\d+)(\s*(\+|\-|\+\-)\s*(\d+))?' )
    nodes = {}
    settings = {}
    latest_timestamp = None
    
    def __init__( self, *args, **kwargs ):
        self.schedule = Schedule()
        self.load()
        self.nodes = {}
        self.settings['schedule']  = {}

    def load( self ):
        pass
        
    def init_schedule( self ):
        pass
    def reset_schedule(self ):
        pass
    
    def getNodeInfo( self, node, fltr ):
        this = {}
        for s in node:
            # self.logger.debug("s: " + repr(s))
            m = self.regex[fltr].search( s )
            if not m == None:
                t = m.groups()
                if len(t) > 0:
                    # self.logger.debug("found: " + t[0] )
                    this[t[0]] = 1
        return this.keys()

    def _delta( self, s ):
        """
        determine the time delta for the next test
        input should be (\d+) (+|-|+-) (\d+)
        """
        # logging.warn("s '%s'" % (s,))
        m = self.delta_regex.search( str(s) ).groups()
        t = float(m[0])
        d = 0
        if m[3]:
            d = float(m[3])
        # logging.debug("t: %s, d: %s" %(t,d))
        return t, d

    def delta( self, s ):
        t, val = self._delta( s )
        # ignore if it's zero
        if t == 0:
            return None
        # deal with delta
        if val > 0:
            # self.logger.debug('2: ' + str(val) )
            d = uniform( -1 * val, val )
            t = t + d
        return t
    

    def getTimeDelta( self, node, spec ):
        if spec in node['schedule']:
            # logging.debug("NODE: %s %s" % (spec,node['schedule'][spec],))
            return node['schedule'][spec]
        return None


    def add( self, node_hash, spec, factor=0 ):
        """
        add the spec for node, if initial, then we do a full uniform random with the time from now to start scheduling immediately
        a node_hash is
        node = {
            'name': <str>
            'schedule': { 'spec': 'period +- dt' }
        }
        """
        if node_hash == None:
            return False
        
        i = self.getTimeDelta( node_hash, spec )
        if i:
            d = self.delta( i )
            if d == None:
                return False
                
            # allow randomisation
            if factor > 0:
                d = uniform( 0, factor*d )
            t = time.time() + d
            # logging.debug(" +%-3.1d (%s) %s:%s" %(d,t,node_hash['name'],spec) )
            self.schedule.add( t, { 'node': node_hash['name'], 'spec': spec } )
            return True
        return False
    
    def pop( self ):
        return self.schedule.pop()
        
    def peek( self ):
        # have a look at what the next item is and when, but put it back
        t, info = self.pop()
        self.schedule.add( t, info )
        return t, info
    
    def next(self):
        # get the next one
        t, info = self.schedule.pop()
        # self.logger.debug("got t: " + str(t) + ", info=" + str(info))
        # readd to queue
        this_node = self.getNode( info['node'] )
        # logging.debug("re-adding t: " + str(this_node) + ", info=" + str(info))
        self.add( this_node, info['spec'] )
        return t, info
    
    def getNode( self, name, report_errors=False ):
        # get the delta time
        if not name in self.nodes:
            # logging.debug( 'expired %s' % (name,))
            return None
            
        node = {
            'name': name,
        }
        for c in self.nodes[name]:
            # logging.debug( "c: %s" % (c,))
            if not c in node:
                node[c] = {}

            if 'ref' in self.nodes[name][c]:
                if not c in self.settings:
                    raise Exception, '%s %s not found' % (name,c)
                n = self.nodes[name][c]['ref']
                if not n in self.settings[c]:
                    if report_errors:
                        raise Exception, '%s ref %s not found in %s' % (c, n, name)
                node[c] = {}
                # logging.debug( "%s %s: %s" % (c, self.nodes[name][c]['ref'], self.settings[c][self.nodes[name][c]['ref']] ))
                # logging.debug("SETTINGS: %s %s: %s" % (c,n,self.settings[c][n],))
                try:
                    for k,v in self.settings[c][n].iteritems():
                        node[c][k] = v
                        # logging.debug(" + %s %s %s: %s" % (c,k, node, v))
                except Exception,e:
                    if report_errors:
                        raise e
            else:
                logging.error(" use defaults for " + name )

            # overload with personal values
            for k,v in self.nodes[name][c].iteritems():
                if not k == 'ref':
                    # logging.debug("node: %s, k: %s" % (node,k,))
                    node[c][k] = v

            # logging.debug("NODE: %s" % (node,))
        return node

    def get_options( self, node ):
        yield None, None
        
    
    def getSpecs( self, node ):
        return node['schedule'].keys()


class YAMLScheduleParser( ScheduleParser ):

    snmp_conf = None
    schedule_conf = None
    node_confs = []
    
    nodes = {}    
    
    def __init__( self, node_confs=[], snmp_conf=None, schedule_conf=None, **kwargs ):
        self.snmp_conf = snmp_conf
        self.schedule_conf = schedule_conf
        self.node_confs = node_confs
        # logging.debug("SNMP: %s, SCHED: %s, NODE: %s" % (self.snmp_conf,self.schedule_conf,self.node_confs))
        self.nodes = {}

        # heapq
        self.schedule = Schedule()

        # initate!
        self.load()
    
    def get_modtime( self, file ):
        # (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime) = stat(file)
        # return time.ctime( mtime )
        return os.path.getmtime(file)
        
    def set_latest_timestamp( self, this ):
        this = utcfromtimestamp( float(this) )
        if self.latest_timestamp == None:
            self.latest_timestamp = this
        elif self.latest_timestamp < this:
            self.latest_timestamp = this
        # logging.debug("latest timestamp: %s" % (self.latest_timestamp))
        
    def load( self ):
        
        # we flatten the nodes as we handle all node schedules
        logging.debug("loading %s, %s" % (self.snmp_conf, self.schedule_conf) )
        
        # read in the schedule config
        self.settings = {
            'schedule': {},
            'snmp': {}
        }
        if self.schedule_conf:
            self.set_latest_timestamp( self.get_modtime( self.schedule_conf ) )
            self.settings['schedule'] = load( file(self.schedule_conf,'r'), Loader=Loader )
        self.set_latest_timestamp( self.get_modtime(self.snmp_conf) )
        self.settings['snmp'] = load( file(self.snmp_conf,'r'), Loader=Loader )
            
        self.nodes = {}    
        for f in self.node_confs:
            logging.debug('loading node file ' + str(f))
            self.set_latest_timestamp( self.get_modtime( f ) )
            this = load( file(f,'r'), Loader=Loader )
            # logging.info("%s" % ( this, ) )
            # pick up the defaults for this set
            settings = {
                'schedule': {},
                'snmp': {}
            }

            if not this == None:
                if 'hosts' in this:
                    for i in ( 'schedule', 'snmp'):
                        settings[i]['ref'] = 'default'
                    if 'settings' in this:
                        for i in ( 'schedule', 'snmp' ):
                            if i in this['settings']:
                                settings[i]['ref'] = this['settings'][i]

                    if this['hosts']:
                        for n in this['hosts']:
                            # inherit the settings
                            if this['hosts'][n] == None:
                                this['hosts'][n] = settings.copy()
                            else:
                                for i in ( 'schedule', 'snmp' ):
                                    if not i in this['hosts'][n]:
                                        this['hosts'][n][i] = {}
                                    this['hosts'][n][i]['ref'] = settings[i]['ref']
                            
                            self.nodes[n] = this['hosts'][n]
                            # logging.debug("%s\t%s" % (n,self.nodes[n],))
                
            else:
                logging.error('no hosts defined in ' + f)
                # raise Exception, 'no hosts defined in ' + f
                
    def init_schedule(self):
        """
        instantiate the heapq
        """
        # self.logger.debug('initiating schedule items ' + str(self.nodes))
        for n in self.nodes:
            # self.logger.debug('section: ' + str(n))
            node = self.getNode( n )
            for s in self.getSpecs( node ):
                self.add( node, s, factor=3 )
        return True
    
    def reset_schedule(self):
        current = {} # nest name, spec
        # see what we currently have
        for n in self.nodes:
            if not n in current:
                current[n] = {}
            node = self.getNode( n )
            for s in self.getSpecs( node ):
                current[n][s] = True
        # load the new ones
        self.load()
        # add new items
        for n in self.nodes:
            node = self.getNode( n )
            for s in self.getSpecs( node ):
                add = False
                if not n in current:
                    add = True
                elif not s in current[n]:
                    add = True
                if add:
                    logging.info("adding %s:%s" % (n,s,))
                    self.add( node, s )
                                    
        # removed items will just expire at next iteration

    
    def get_options( self, node ):
        if node == None:
            return
        for k,v in node.iteritems():
            if not k in ( 'schedule', 'name' ):
                yield k,v
        return