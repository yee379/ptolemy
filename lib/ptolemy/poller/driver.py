from os import O_RDONLY
import sys
from copy import copy
import string
from re import match, search, sub, split, U, compile, IGNORECASE

import yaml
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader
    

import struct
from binascii import unhexlify
from ptolemy.poller.agent import *

from slac_utils.net import truncate_physical_port as truncate_physical_port_name, extract_physical_port
from collections import defaultdict

from pprint import pformat, pprint
import logging
import traceback


#######################################################################
# CUSTOM FUNCTIONS
#######################################################################


def _normalise_mac_address( v ):
    if v.startswith( '0x' ):
        v = v.replace( '0x', '')
    return v.lower().zfill(2)

def normalise_mac_address( v ):
    """
    create a standard mac address
    """
    if v == None:
        return None
    # TODO: handle xxxx.xxxx.xxxx input
    mac_addr = []
    c = 0
    this = []
    # logging.debug("convert: " + str(v))
    for d in sub( r'(\"|"\s|\:|\.)', ' ', v.lower().strip() ):
        # logging.debug("  %d: %s" % (c,d))
        if d == ' ':
            # logging.debug("    this: " + str(this))
            mac_addr.append( _normalise_mac_address( ''.join(this) ) )
            this = []            
        else:
            this.append(d)
        c = c + 1

    # format to cisco's standard mac address format
    mac_addr.append( _normalise_mac_address( ''.join(this) ) )

    # logging.debug("> " + str(mac_addr))
    if len(mac_addr) == 6:
        m = ''
        for i in xrange(0,len(mac_addr),2):
            m = m + mac_addr[i] + mac_addr[i+1]
            # logging.debug("  i: %d\t%s" %(i,m))
            if i % 2 == 0 and i < 4:
                m = m + '.'
        # logging.debug("return %s" % (m))
        return m
    return None

def normalise_ip_address( v ):
    """
    create an ip address
    """
    this = []
    if isinstance( v, list ):
        if len(v) == 4:
            for i in v:
                this.append( str(int(i, 16)) )
            # logging.debug("  IP: %s" % (this,))
    if len(this) == 4:
        return '.'.join(this)

    return None

def pretty_print_mac_address( v ):
    # logging.debug(" in: %s" %(v,))
    # return _pretty_print_mac_address( v.split('.') )
    c = 0
    a = []
    for i in split(r'(\.|\:)',v):
        if c % 2 == 0:
            a.append( i )
        c = c + 1
    return _pretty_print_mac_address( a )


def _pretty_print_mac_address( array ):
    # logging.debug("   > " + str(array))
    if len(array) == 6:
        m = ''
        for i in xrange(0,len(array),2):
            m = m + _normalise_mac_address(array[i]) + _normalise_mac_address(array[i+1])
            # logging.debug("  i: %d\t%s" %(i,m))
            if i % 2 == 0 and i < 4:
                m = m + '.'
        # logging.debug("return %s" % (m))
        return m
    return None

def binary_to_hex( v ):
    a = []
    for i in v:
        a.append( i.encode('hex') )
        # logging.debug("> i: %s\t-> s: %s (%s)" % (i,v))
    # logging.debug("  > %s" % (a,))
    return '.'.join( a )

def hex_to_integers( v ):
    if v == None:
        return None
    s = v.encode('hex')
    out = [ str(int( '0x' + str(s[x]) + str(s[x+1]), 0 ) ) for x in xrange(0, len(s), 2) ]
    return '.'.join( out )

def integers_to_hex( v ):
    return '.'.join( [ hex(int(i)) for i in v.split('.') ] )

def string_to_bits( v ):
    i = ['%08d'%int(bin(ord(i))[2:]) for i in v].pop(0)
    return i

def stringify( v ):
    try:
        return unicode(v).strip()
    except:
        pass
    return None

def lower( v ):
    return stringify( v ).lower()
    
def normalise_devicename( v, domain='slac.stanford.edu' ):
    # can't really have spaces in the names
    if ' ' in v:
        return v
    v = sub( r'\(\w+\)', '', lower(v) )
    if not '.' in v:
        v = '%s.%s' % (v,domain)
    return v

def printable( v ):
    """ removes non ascii chars from string """
    v = v.replace('\x00','')
    return filter(lambda x: x in string.printable, v)
    

HEXTAB = ("0000","0001","0010","0011","0100","0101","0110","0111","1000","1001","1010","1011","1100","1101","1110","1111");
IGNORE_VLANS = ( 1001,1002,1003,1004 )
def decode_vlanVlansOnPort( v ):
    """
    return array of vlan numbers from representation of vlanVlansOnPort
    first we convert the hex into raw bits
    then we iterate through all the bits to determine if it's true or false
    if true, then the relative position from the start is the vlan number
    """
    if v == None:
        return []
    a = ''
    for i in v:
        a = a + i.encode('hex')
    # logging.debug('  %s' % (a,))
    v = sub( '\W', '', a ).strip().lower()
    vlans = {}
    if not search( 'ffffffffffffffffffffffff', v ) or len(v) == 128:
        c = 0
        for i in v:
            x = int( '0x' + str(i), 16 )
            # logging.debug( " %s -> %s" % ( i, x ) )
            for j in str(HEXTAB[x]):
                # logging.debug( "    %s" % ( j, ))
                if int(j) == 1 and not c in IGNORE_VLANS:
                    vlans[c] = True
                c = c + 1
    array = sorted(vlans.keys())
    # logging.debug('    => %s (%s)' % (array, type(array)))
    return array

def replace_white_space( v ):
    if isinstance( v, str ):
        return v.replace( v, ' ', '_')
    return v

def merge_trunking_vlans( group_data ):
    """
    cisco's will keep the trunked vlans in different oids, so we merge them here
    """
    # logging.debug("MERGING TRUNKS on " + str(group_data))
    offset = 0
    this_data = {}
    for f in ( 'vlanTrunkPortVlansEnabled1k', 'vlanTrunkPortVlansEnabled2k', 'vlanTrunkPortVlansEnabled3k', 'vlanTrunkPortVlansEnabled4k'):
        if f in group_data:
            logging.debug("group data for " + str(f))
            for k,v in group_data[f].items():
                # logging.debug("  key: %s\t value: %s (%s)" % (k,v,type(v)))
                if isinstance( v, list ):
                    for n in v: # array
                        # logging.debug("    value: " + str(n) )
                        if not k in this_data:
                            this_data[k] = []
                        this_data[k].append( int(n) + offset )
        offset = offset + 1024
    # this_data[i].sort()
    return this_data

def determine_port_function( group_data ):
    """
    write out the function of the port (access/trunk etc)
    """
    this_data = {}
    # logging.error("DATA: %s" % (group_data,))
    for p in group_data['admin_status'].keys():
        if 'trunked_vlans' in group_data and p in group_data['trunked_vlans']:
            this_data[p] = 'trunk'
        elif 'native_vlan' in group_data and p in group_data['native_vlan']:
            this_data[p] = 'access'
        else:
            logging.debug('     could not determine port function %s' % (p,))
        #     this_data[p] = 'unknown'
    return this_data

def extract_l2vlan_trunking_vlans( group_data ):
    """
    exploit the fact that one commonly uses subinterfaces with teh same number
    as that of the vlan that the subinterface is on to extract trunking information
    """
    this_data = {}
    if 'type' in group_data:
        for k in sorted(group_data['type'].keys()):
            if group_data['type'][k] == 'l2vlan':
                # logging.debug("  K %s,\t %s" % (k,group_data['type'][k]) )
                m = match( r'^(?P<physical_interface>.*)\.(?P<vlan>\d+)$', k )
                if m:
                    g = m.groupdict()
                    # logging.debug("     %s" % (g))
                    if not g['physical_interface'] in this_data:
                        this_data[g['physical_interface']] = []
                    this_data[g['physical_interface']].append( int(g['vlan']) )
    else:
        raise RefNotFound, 'type variables are required for function extract_l2vlan_trunking_vlans'
    for v in this_data.keys():
        this_data[v] = sorted( this_data[v] )
    return this_data
    

def extract_dot1qVlanStaticEgressPorts( group_data ):
    """
    the oid dot1qVlanStaticEgressPorts provides the vlan number against the ifindex's
    for the ports that carry that vlan. this funcion remaps this.
    """
    this_data = {}
    if 'dot1qVlanStaticEgressPorts' in group_data and 'ifName' in group_data:
        for k,v in group_data['dot1qVlanStaticEgressPorts'].iteritems():
            logging.debug("remapping vlan %s on ports %s" % (k,v))
            for i in v:
                # determine phsyical
                i = str(i)
                if i in group_data['ifName']:
                    logging.debug("  port: %s -> %s" % (i,group_data['ifName'][i]))
                    if not group_data['ifName'][i] in this_data:
                        this_data[group_data['ifName'][i]] = []
                    this_data[group_data['ifName'][i]].append( int(k) )
                else:
                    logging.debug("  could not find %s" % (i,))
    else:
        raise RefNotFound, 'variable dot1qVlanStaticEgressPorts is required for function call'
    return this_data


LLDP_CAPABILITY = [ 'other', 'repeater', 'bridge', 'access_point', 'router', 'telephone', 'docsis', 'station' ]
def post_normalise_layer1_peer( g, d, data ):
    if g == 'neighbour':
        if 'peer_address_type' in d:
            if d['peer_address_type'] == 'networkAddress':
                d['peer_mac_address'] = normalise_mac_address( binary_to_hex( d['peer_physical_port'] ) )
                d['peer_ip_address'] = normalise_ip_address( binary_to_hex( d['peer_address'].split('.')[1:] ) )
                # logging.debug('  translating network addresses mac: %s->%s' % (d['peer_physical_port'],d['peer_mac_address']) )
                # , d['peer_address'].split('.')[1:], d['peer_ip_address']))
                del d['peer_physical_port']
                del d['peer_address']
            elif d['peer_address_type'] == 'macAddress':
                del d['peer_address']
            elif d['peer_address_type'] == 'ip' and 'peer_address' in d:
                d['peer_ip_address'] = d['peer_address']
                del d['peer_address']
        del d['peer_address_type']
        if 'peer_capabilities_lldp' in d:
            for x in xrange( 0, len(d['peer_capabilities_lldp']) ):
                if d['peer_capabilities_lldp'][x] == str(1):
                    c = 'capability_%s' % LLDP_CAPABILITY[x]
                    d[c] = True
            del d['peer_capabilities_lldp']
    yield g, d, data

def post_normalise_temperature( g, d, data ):
    if g == 'stats':
        delete = False
        if not 'sensor' in d:
            delete = True
        else:
            if not d['sensor'] == 'celsius':
                delete = True
            elif 'scale' in d:
                if d['scale'] == 'milli':
                    d['value'] = float( d['value'] / 1000. )
        if not delete:
            for n in ( 'scale', 'sensor' ):
                del d[n]
            yield g, d, data
    return

def tree(): return defaultdict(tree)
def dicts(t): return dict( (k, dicts(t[k])) for k in t )

def walk_to( node, tree, depth=0 ):
    pre = ' '*depth
    # logging.error("%swalk to %s" % (pre,node))
    for k in tree:
        # logging.error("%s k=%s" % (pre,k))
        if k == node:
            # logging.error("%s   found %s! %s" % (pre,node,tree[node]))
            return tree[node]
        else:
            w = walk_to( node, tree[k], depth=depth+1 )
            # logging.error("%s  w %s" %(pre,w))
            if w is not None:
                # logging.error("%s   out %s" % (pre,w))
                return w
    return None

def attach( node, parent, tree, add_if_orphan=True ):
    # logging.error("add %s at %s" % (node,parent))
    t = walk_to( parent, tree )
    if t == None:
        if add_if_orphan:
            tree[node]
        else:
            return False
    else:
        t[node]
    return True
    # logging.error("\n")

def regraft( node_to_remove, topology, items, parent_field='parent_index', inherit_fields=[] ):
    """ remove the node specified, moving it's children to directly connect to it's parent """
    # logging.error("  REGRAFT %s %s" % (type(node_to_remove),node_to_remove,))
    this = walk_to( node_to_remove, topology )
    # give the children this' values
    fields_to_inherit = {}
    for i in inherit_fields:
        if i in items[node_to_remove]:
            fields_to_inherit[i] = items[node_to_remove][i]
    # logging.error("   this: %s" % (this,))
    parent_id = items[node_to_remove][parent_field]
    # logging.error("   parent_id: %s" % (parent_id,))

    parent = walk_to( parent_id, topology )
    children_ids = []
    if this:
        children_ids = [ c for c in this ]
        logging.debug("   regrafting %s->%s will change %s" % (node_to_remove,parent_id,children_ids,) )
        for c in children_ids:
            # mod data
            if c in items:
                items[c][parent_field] = parent_id
                for i,v in fields_to_inherit.iteritems():
                    logging.debug("    %s inheriting %s->%s (was %s)" % (c,i,v,items[c][i]))
                    items[c][i] = v
                # mod tree
                if parent is not None:
                    parent[c] = this[c].copy()
                del this[c]
            
            else:
                logging.warn("    idx %s not found!" % (c,) )
    # remove this item
    if parent is not None:
        if node_to_remove in parent:
            del parent[node_to_remove]


def reattach_as( node, new_node, topology, items, parent_field='parent_index', index_field='physical_index' ):
    logging.debug("reattach as %s -> %s" % (node, new_node))
    parent = walk_to( items[node][parent_field], topology )
    if parent is not None:
        parent[new_node] = parent[node].copy()
        del parent[node]
    # reassign all children to point to new node
    this = walk_to( node, topology )
    # logging.error(" this: %s " % (this,))
    if this is not None:
        for c in this:
            items[c][parent_field] = new_node
    # remove data
    items[new_node] = items[node].copy()
    items[new_node][index_field] = new_node
    del items[node]
    logging.debug(" copying %s -> %s: %s" % (node,new_node,items[new_node]))

def build_tree( items, parent_field='parent_index', add_if_orphan=False, root_idx=0, iterations=2 ):
    """ from an anonhash, with each hash having a field called parent_field, build a tree of dependencies, if no_orphans is true, then try to ensure no stray branches exist (ie order or input matters for building tree) """
    # recreate tree
    topology = tree()
    strays = tree()
    for idx in numerise_keys( items ):
        d = items[idx]
        c = str(d[parent_field])
        force_add = add_if_orphan
        if d[parent_field] == root_idx:
            force_add = True
        # logging.info("IDX: %s \tparent=%s\t(force %s)\tD: %s" % (idx,c,force_add,d))
        added = attach( str(idx), c, topology, add_if_orphan=force_add )
        if added == False:
            # logging.info("  adding to strays")
            attach( str(idx), c, strays, add_if_orphan=True )
            
    # do first level only, for each stray branch, see if we can add it to the final tree
    while len(strays.keys()) and iterations > 0:
        for s in strays.keys():
            parent = items[s][parent_field]
            t = walk_to( str(parent), topology )
            # logging.info(" at %s who has parent %s: %s" % (s,parent,type(t)))
            if t is not None:
                # logging.info( "  moving %s to main topology" % (s,) )
                t[s] = strays[s]
                del strays[s]
        iterations = iterations - 1

    # logging.error("ORPHANS: %s" % (pformat(dicts(strays))))
    # logging.error("TOPOLOGY: %s" % (pformat(dicts(topology))))
    return topology

def numerise_keys( items ):
    idx = []
    idx2 = []
    for k in items.keys():
        try:
            idx.append(int(k))
        except:
            idx2.append(k)
    keys = [ str(i) for i in sorted(idx) + sorted(idx2) ]
    # logging.error("KEYS: %s" % (keys,))
    return keys

def post_normalise_entities( g, d, data ):
    """ filter and standardise entity output """

    topology = build_tree( data[g] )
    # logging.debug("BEFORE %s" % (pformat(dicts(topology))))

    remap = {
        # '1': 0    # always keep the root item at index 0 rather than 1 (incase of slots etc.)
    }
    
    chassis_ids = []
    possible_sw_revs = {}
    possible_models = {}
    
    logging.debug("initial scan of entities")
    for idx in numerise_keys( data[g] ):
        # deal with reindexing transcievers to something more useful (ie physical ports)
        # use fact that sensors of an sfp report the location
        this = data[g][idx]
        
        # logging.error("IDX: %s\t%s" % (idx,this))
        
        # make sure parent_id is a string
        this['parent_index'] = str(this['parent_index'])
        
        # cisco sup720's lie about modules being transceivers
        if 'description' in this and 'type' in this:
            if this['type'] == 'transceiver' and \
                ( search( r'Transceiver Port', this['description'] ) or ( 'serial' in this and this['serial'] == None ) ):
                logging.debug(" marked %s as container: %s" % (idx,this))
                this['type'] = 'container'
            # sup720's lie about transcievers being ports, also aristas 
            elif this['type'] == 'module' and \
                ( search( r'Transceiver', this['description'] ) or search( r'Xcvr', this['description'] ) ):
                logging.debug(" marked %s as transceiver: %s" % (idx,this))
                this['type'] = 'transceiver'
        
        if this['type'] == 'transceiver':
            # logging.error("transciever at %s: %s" % (idx,this))
            node = walk_to( idx, topology )
            physical_port = None
            # sensors, don't want
            for child_id in node:
                child = data[g][child_id]
                if 'description' in child:
                    physical_port = truncate_physical_port_name( child['description'] )
                data[g][child_id]['parent_index'] = physical_port
            # check itself for some description of physical port
            if not physical_port and 'description' in this:
                physical_port = extract_physical_port( this['description'] )
            # reindex
            if physical_port:
                # can be at start or at end of string
                p = extract_physical_port( physical_port )
                logging.debug("  identified transceiver at %s as %s (%s)" % (idx,p,physical_port))
                remap[idx] = p
            else:
                logging.debug("  could not determine physical port")
        
        # try to determine possible chassis's
        elif this['type'] == 'chassis':
            logging.debug(" found chassis at %s" % (idx,))
            chassis_ids.append( idx )
        
        # try to determine useable sw vers to put onto chassis'
        elif this['type'] == 'module' and 'description' in this and search( r'supervisor', this['description'], IGNORECASE ):
            if 'sw_rev' in this:
                if not this['sw_rev'] in possible_sw_revs:
                    possible_sw_revs[this['sw_rev']] = 0
                possible_sw_revs[this['sw_rev']] = possible_sw_revs[this['sw_rev']] + 1
            if not this['model'] in possible_models:
                possible_models[this['model']] = 0
            possible_models[this['model']] = possible_models[this['model']] + 1 
        
    logging.debug("NEED TO REMAP: %s" % (remap,))
    # delete any containers or useless entities and regraft tree
    # logging.error("KEYS: %s" % (data[g].keys(),))
    
    logging.debug("removing useless entities...")
    for idx in numerise_keys( data[g] ):
        this = data[g][idx]
        node = walk_to( idx, topology )
        
        # remove this item, regraft it's children onto this' parent
        if not this['parent_index'] == '0':
            if 'serial' in this and this['serial'] == None and not this['type'] == 'fan':
                # try to keep the relative id of the child against this' parents'
                # if it's a container, do not reassign the relative position
                f = []

                # deal with 6509 and n7k
                if 'Container of Container' in this['description'] or 'Container of Fan' in this['description'] or 'Bay' in this['description']:
                    # logging.debug('      1')
                    f = []
                elif 'Container of ' in this['description']:
                    # logging.debug('      3')
                    f = ['relative_position']
                elif not search( r'container', this['description'], IGNORECASE ):
                    # logging.debug('      4')
                    f = ['relative_position']

                logging.debug(" REMOVE %s: %s (inherit %s)" % (idx,this,f))
                regraft( idx, topology, data[g], inherit_fields=f )
                del data[g][idx]

        # remap items
        if idx in remap and idx in data[g]:
            logging.debug("reassigning %s to %s" % (idx,remap[idx]))
            reattach_as( idx, remap[idx], topology, data[g] )
            
        # if parent_id doesn't exist, set to first chassis
        # if not this['parent_id'] in data[g] and len(chassis_ids):
        #     logging.error("moving %s to top level chassis at %s" % (idx,chassis_ids))
        #     this['parent_id'] = chassis_ids[0]


    # set the chassis sw version for quick lookup
    if len(chassis_ids) == 1:
        c = chassis_ids.pop()
        # work it out from child modules...
        # logging.error("DESCR: %s" % data['info']['0']['string'])
        if 'sw_rev' in data[g][c] and not data[g][c]['sw_rev']:
            v = None
            if len(possible_sw_revs.keys()) == 1:
                v = possible_sw_revs.keys().pop()
            # try getting the chassis sw version from the sysDesc string
            elif 'info' in data and '0' in data['info'] and 'string' in data['info']['0']:
                m = search( r'version (?P<version>[a-zA-Z0-9\(\)\.]+)', data['info']['0']['string'], IGNORECASE )
                if m:
                    v = m.group('version')
            if v:
                logging.debug("setting chassis (%s) sw_rev as %s" % (c,v,))
                data[g][c]['sw_rev'] = v
        
        # if the model is blank for the chassis, determine from modules
        if 'model' in data[g][c] and data[g][c]['model'] == None or match( r'^\s+$', data[g][c]['model'] ):
            v = None
            if len(possible_models.keys()) == 1:
                v = possible_models.keys().pop()
            if v:
                logging.debug("setting chassis model (%s) as %s" % (c,v,))
                data[g][c]['model'] = v

    # many chassis... what to do?
    else:
        
        # nexus?
        for c in chassis_ids:
            # grab data from child modules of this chassis
            this = walk_to( c, topology )
            child_modules = []
            if this:
                for m in this:
                    if data[g][m]['type'] == 'module':
                        child_modules.append( m )
            if len(child_modules) == 1:
                m = child_modules.pop()
                # logging.error("PARENT: %s has child: %s" % (c,data[g][m]) )
                # copy contents to of module to parent
                for i in ( 'sw_rev', 'fw_rev' ):
                    if data[g][c][i] == None:
                        logging.debug('setting chassis %s to %s' % (i,data[g][m][i]))
                        data[g][c][i] = data[g][m][i]
            # rename stupid nexus 2k models from the descrition
            if c in data[g] and data[g][c]['model'].startswith( 'Fabric Extender Module' ):
                m = search( r'^Fex-\d+ (?P<model>\S+) Chassis', data[g][c]['description'] )
                if m:
                    v = m.group('model')
                    # replace start of string with model number
                    v = v.replace('Nexus','N2K-C')
                    logging.debug("setting chassis %s as model %s" % (c,v))
                    data[g][c]['model'] = v
            
    # recreate tree
    # topology = build_tree( data[g] )
    # logging.debug("ENTITY TOPOLOGY %s" % (pformat(dicts(topology))))
    
    for idx in data[g]:
        data[g][idx]['physical_index'] = idx
        yield g, data[g][idx], data


def _to_hex( v ):
    return hex( ord(v).replace('0x','') )

def decode_port_channels( value ):
    """
    pairs of hex-tuples. first is the number of members, subsequent pairs are the interfaces in
    (slot).(number) notation. all mod 128
    """
    value = binary_to_hex( value )
    logging.debug("      decode %s" % (value,))
    pattern = compile( r'(\w\w\.\w\w\.?)', U )
    count = 0
    members = []
    for i in pattern.finditer( value ):
        v = i.groups()[0].split('.')
        # get rid of last entry if not at end
        if len(v) == 3:
            v = v[:2]
        if count > 1:
            h = int( '0x%s%s' % (v[0],v[1]), 16 )
            logging.debug('          %s -> %s/%s' % (v,h/128,h%128) )
            members.append( '%s/%s' % (h/128,h%128) )
        count = count + 1
    
    return members




def quotify( value ):
    """
    just adds quotes around value as some key relations require this
    """
    return '"%s"' % value

def fqdn( s ):
    """ adds str to value """
    return '%s.%s' % ( s, 'slac.stanford.edu')


def _bsn_data( data ):
    bsn = {}
    if 'bsn' in data:
        for k in data['bsn']:
            for i,j in data['bsn'][k].iteritems():
                serial = data['bsn'][k]['bsn_serial']
                s = i.replace('bsn_','')
                if s in ( 'serial', 'index' ):
                    next
                if not serial in bsn:
                    bsn[serial] = {}
                # bah!
                if s == 'device':
                    j = "%s.slac.stanford.edu" % (j,)
                bsn[serial][s] = j
    return bsn


def post_merge_wireless_info_bsn( g, d, data ):
    """ generate a new info for each access point too """
    # yield the controller
    if 'info' in data:
        # logging.error("%s" % (data['info'],))
        for k in data['info']:
            # logging.error("K: %s" % (k,))
            yield g, data['info'][k], data
    # yield each ap
    for k,d in _bsn_data( data ).iteritems():
        d['name'] = d['device']
        del d['serial']
        yield g, d, data

def post_merge_wireless_meta_bsn( g, d, data ):
    """
    merge two separate groups given a common key
    """
    # create lookup of serials to bsn info
    bsn = _bsn_data( data )
    # merge into the data
    if 'meta' in data:
        for k in data['meta']:
            d = data['meta'][k]
            if 'serial' in d and d['serial'] in bsn:
                d['device'] = bsn[d['serial']]['device']
            # logging.error("G: %s, D: %s" % (g,d,))
            
            # add index
            d['physical_index'] = k
            if not int(k) == 1:
                d['physical_index'] = 0
            yield g, d, data


def post_merge_wireless_apname_on_radio( g, d, data ):
    """ for each radio, determine the name by index lookup """
    aps = {}
    for k in data['ap_name']['device']:
        aps[k] = data['ap_name']['device'][k]
    # logging.error("APS: %s" % (aps,))
    # f = None
    # for j in ( 'neighbour', 'status', 'radio_stats' ):
    #     if j in data:
    #         f = j
    # logging.error("F: %s: %s" % (f,data))
    # if f:
    for k in data[g]:
        # logging.error("K: %s" % (k,))
        if k in aps:
            x = k
        else:
            m = search( r'^(?P<key>.*)\.\d$', k )
            if m:
                x = m.groupdict()['key']
        if x in aps:
            d = data[g][k]
            d['device'] = aps[x]
            yield g, d, data

def post_merge_wireless_apname_on_mac_address( g, d, data ):
    """ join data based on the mac address """
    macs = {}
    for k in data['ap_name']['ap_mac_address']:
        m = data['ap_name']['ap_mac_address'][k]
        macs[m] = data['ap_name']['device'][k]

    for k in data[g]:
        m = data[g][k]['on_mac_address']
        if m in macs:
            d = data[g][k]
            d['device'] = macs[m]
            del d['on_mac_address']
            yield g, d, data

def post_reindex_wireless_on_serial( g, d, data ):
    """ stupid wlc controllers keep on changing the physical_index, let's use the serial instead """
    
    keys = [ k for k in data[g] ]

    for k in keys:
        s = data[g][k]['serial']
        d = data[g][k]
        if int(k) == 1: # leave the controller alone
            d['physical_index'] = 1
        else:
            d['physical_index'] = 0
            del data[g][k]
            data[g][s] = d
        yield g, d, data


def post_fan_physical_index_lookup( g,d,data):
    """ using a reference to another item, repalce current index """
    logging.debug("  post key sub lookup %s" % (d,))
    
    keys = {}
    for k,v in data['entity_map'].iteritems():
        if v['entPhysicalClass']:
            keys['%s'%v['entPhysicalParentRelPos']] = v['index']
            
    logging.debug("  mapping: %s -> %s: %s" % (d['physical_index'], keys,d['physical_index'] in keys))
    if d['physical_index'] in keys:
        d['physical_index'] = keys[d['physical_index']]
        # logging.error(" OUT: %s" % d)
        yield g, d, data
    else:
        yield None, None, data

#######################################################################
# END CUSTOM FUNCTIONS
#######################################################################



class RefNotFound( Exception ):
    pass

class Template( object ):
    """
    yaml object to help determine if drivers are compatable
    """
    conf = None
    
    mapping = {}
    data = {}
    agents = []

    def __init__(self, filepath):
        s = file(template_file, 'r')
        self.conf = self.load( s )

    def __repr__(self):
        return str(self.conf)

    def specifications(self):
        return self.conf.keys()
        
    def groups(self, spec):
        if spec in self.conf:
            return self.conf[spec].keys()
        raise Exception, 'no spec ' + str(spec)
            
    def index(self, spec, group ):
        if spec in self.conf and group in self.conf[spec] and 'index' in self.conf[spec][group]:
            return self.conf[spec][group]['index']
        raise Exception, 'no index'
        
    def defs( self, spec, group ):
        if spec in self.conf and group in self.conf[spec] and 'def' in self.conf[spec][group]:
            return self.conf[spec][group]['def']
        raise Exception, 'no defs'





def _process_by_field_rename( data, name, definition, **kwargs ):
    """
    just change the data keys to variable name
    """
    frm = definition['ref']
    # logging.error("    changing field name from '" + str(frm) + "' to '" + str(name) + "'" )
    needed = True
    if not frm in data:
        if 'required' in definition and definition['required'] == False:
            needed = False
        logging.debug( '   field ' + str(frm) + ' -> ' + str(name) + ' is not within dataset, required ' + str(needed) )
        if needed:
            raise RefNotFound, 'required variable ' + str(frm) + ' is not in data'
    else:
        # convert
        this = {}
        for i in data[frm]:
            this[i] = data[frm][i]
        del data[frm]
        data[name] = {}
        for i in this:
            data[name][i] = this[i]

    return data


def _process_by_key_remap( data, name, definition, **kwargs ):
    """
    for each key in the field, use the defined map to determine the new key
    """
    ref = definition['ref']
    # logging.debug("   REF %s, DATA: %s" % (ref,data) )
    if not ref in data:
        raise RefNotFound, 'request remapping using ref %s (not in data)' % (ref,)
    logging.debug("    changing keys using %s on name %s" % (ref,name ) )    
    this = {}
    for k,v in data[name].items():
        k = str(k)
        if k in data[ref]:
            this[data[ref][k]] = v
            logging.debug( "       changed %s\t-> %s" % (k,data[ref][k]) )
        else:
            logging.debug( "       key %s does not exist for lookup: %s" % (k,ref) )
            
    # clear old
    data[name] = {}
    for k,v in this.items():
        data[name][k] = v

    # logging.debug("key remap: " + str(data))
    return data


def _process_by_value_remap( data, name, definition, parent_data={}, **kwargs ):
    """
    take the values for the definition and change to what's defined
    """
    logging.debug("    changing value using defn %s" %(definition,) )

    # ignore the type of the value
    if 'dict' in definition:
        mapping = definition['dict']
        for k,v in data[name].items():
            # incase it's an integer
            v = str(v)
            try:
                v = int(v)
            except:
                pass
            found = False

            if v in mapping:
                data[name][k] = mapping[v]
                found = True
            else:
                # logging.debug("     regexp value remap")
                for i,j in mapping.iteritems():
                    # logging.debug("      search for '%s' in '%s' -> replace with '%s'" % (data[name][k],i,j))
                    if search( '%s'%i, '%s'%data[name][k] ):
                        data[name][k] = j
                        found = True
                        break
            if not found and 'other' in mapping:
                # determine if special value 'other' is defined
                logging.debug("      not found, using 'other' value %s" % (mapping['other'],))
                data[name][k] = mapping['other']
                found = True
            if not found:
                logging.debug("    value '%s' not defined in remap %s" % (v,definition))
                
    elif 'ref' in definition:
        r = definition['ref']
        if r in data:
            
            for k,v in data[name].iteritems():
                v = str(v)
                # logging.debug("k:%s\tv:\t%s" % (k,v) )
                if v in data[r]:
                    data[name][k] = data[r][v]
                    # logging.debug( " (%s->%s) %s %s -> %s" % (name,r,k, v,data[r][v]) )
                else:
                    logging.debug("      could not remap value %s using ref %s" % (v,r))
                # logging.debug( "  -> %s" % (data[r][v]))
        else:
            raise RefNotFound, 'request value remapping using ref %s (not in data)' % (r,)

    elif 'parent_ref' in definition:
        # in an iterative poll, it's not worth polling the same data for every iteration, so we can reference a group and field where it has already been polled
        p, tmp, r = definition['parent_ref'].partition('::')
        logging.debug("    replace with parent %s field %s" % (p,r))
        if p in parent_data and r in parent_data[p]:
            for k,v in data[name].iteritems():
                v = str(v)
                if v in parent_data[p][r]:
                    data[name][k] = parent_data[p][r][v]
                    logging.debug( " (%s->%s) %s %s -> %s" % (name,r, k,v, parent_data[p][r][v]) )
                else:
                    logging.debug("      could not remap value %s using parent %s ref %s" % (v,p,r))
        else:
            raise RefNotFound, 'request value remapping using parent %s ref %s (not in data)' % (r,r,)
            
    elif 'set' in definition:
        s = definition['set']
        for k,v in data[name].iteritems():
            data[name][k] = s
            
    elif 'prefix' in definition:
        s = definition['prefix']
        for k,v in data[name].iteritems():
            data[name][k] = '%s%s' % (s,v)
            logging.debug('     prefix\'d to %s' % (data[name][k]))
        
    else:
        raise Exception, 'unknown mapping type %s' % (definition,)

    return data


def _unescape_regex( regexp ):
    return sub(r'\\\\', r'\\', regexp )


def _process_regexp( item, regexp ):
    try:
        m = match( _unescape_regex( regexp ), item )
        if m:
            return m.groupdict()
    except Exception, e:
        logging.debug("     could not key_regexp " + str(regexp) + " on '" + str(item) + "': error=" + str(e))
    return None

    
def _process_by_regexp( data, name, definition, **kwargs ):
    y = definition.keys().pop()
    logging.debug("    changing " + str(y) + " on " + str(name) + " using regexp " + str(definition) )
    if y in ( 'key', 'value' ):
        for k,v in data[name].items():
            if y == 'key':
                logging.debug('     attempting regexp %s on %s' % (definition[y],k))
                d = _process_regexp( k, definition[y] )
                if d:
                    if 'key' in d:
                        new_key = d['key']
                        logging.debug("      replacing key from key '%s'\t-> '%s'" % (k,new_key) )
                        del data[name][k]
                        data[name][new_key] = v
                    elif 'value' in d:
                        v = d['value']
                        logging.debug("      replacing value from key '%s'\t-> '%s'" % (k,v) )
                        data[name][k] = v
                else:
                    logging.debug("      regexp on key %s failed" % (k,) )
                    
            elif y == 'value':
                d = _process_regexp( v, definition[y] )
                if d:
                    if 'key' in d:
                        new_key = d['key']
                        logging.debug("      replacing key from value %s\t-> %s" % (v,new_key) )
                        del data[name][k]
                        data[name][new_key] = v
                    elif 'value' in d:
                        new_value = d['value']
                        logging.debug("      replacing value from value '%s'\t-> '%s'" %(v,new_value) )
                        data[name][k] = new_value
                else:
                    logging.debug("      regexp on value %s failed" % (v,) )

    else:
        raise Exception, 'must define what to operate regexp on by key or value'
    return data
    
def _process_by_extract_from_key( data, name, definition, **kwargs ):
    """
    given data[name][key] = value,
    extract data from the key such that we can get
      data[name][key_bit] = [ { key_otherbit: value }, ... ]
    where key_bit and key_otherbit were once part of the key
    """
    logging.debug("    extracting dict with %s on %s " %(definition,name) )
    # logging.debug("  DATA: %s" % (pformat(data,)))
    if 'regexp' in definition:
        for k,v in data[name].items():
            r = _unescape_regex( definition['regexp'] )
            m = match( r, k )
            # logging.debug("MATCH " + str(r) + " on " + str(k) + ': ' + str(m))
            if m:
                d = m.groupdict()
                key = k
                if 'key' in d:
                    key = d['key']
                    del d['key']
                for i,j in d.iteritems():
                    logging.debug("DICT: %s=%s \tindex=%s" % (i,j,k) )
                    if not i in data:
                        data[i] = {}
                    data[i][key] = j
    logging.debug("extract result: %s" % (pformat(data)) )
    return data

def _process_by_post_extract( g, d, data, defn ):
    """
    given the spec, 
    """
    logging.debug("    post extracting" )
    for k, regex in defn.iteritems():
        if k in d:
            logging.debug("     k=%s regex=%s on v=%s" % ( k,regex,d[k] ) )
            if d[k]:
                m = search( regex, d[k] )
                if m:
                    # delete the key unless it's defined in the extraction
                    delete = True
                    for i,j in m.groupdict().iteritems():
                        d[i] = j
                        if i == k:
                            delete = False
                    if delete:
                        del d[k]
    logging.debug( "     >: %s" % (d,))
    yield g, d, data

def _process_by_post_key_sub( g, d, data, defn ):
    """
    given the data, will substitute the value of the key with the value of the defn
    """
    logging.debug("  post post_key_sub %s %s" % (defn,{}))
    for frm, to in defn.iteritems():
        if ':' in to:
            grp, _tmp, ref = to.partition(':')
        else:
            grp = g
            ref = to
        logging.debug("   frm: %s, grp: %s, ref %s: %s on %s " %(frm,grp,ref,d,{}))
        if frm in d and ref in data[grp] and d[frm] in data[grp][ref]:
            d[frm] = data[grp][ref][d[frm]]
        # logging.error("D: %s" % (d,))
    yield g,d,data


def _process_by_merge_defs( data, name, definition, **kwargs ):
    logging.debug("    merging %s %s" %(name,definition) )
    # logging.debug("      on data %s" % (data,))
    this = {}
    for k, fields in definition.iteritems():
        logging.debug("        k: %s, fields: %s" % (k, fields,))
        delete = []
        if k in data:
            for i,j in data[k].iteritems():
                logging.debug("          analysing %s: %s" % (i,j,))
                add = True
                if len(fields):
                    if j in fields:
                        add = False
                elif j == None:
                    add = False
            
                if add:
                    if not k in this:
                        this[k] = {}
                    this[k][i] = j
                    logging.debug("            set %s: %s %s"%(k,i,j,))

                # remove original entry
                delete.append(i)

            # delete
            # for d in delete:
            #     del data[k][d]

    # merge entries
    f = this.keys()
    if len(f) == 1:
        data[name] = this[f[0]]
        logging.debug("      out: %s"%(this[f[0]],))

    else:
        # deal with nested structure
        logging.debug("  merged: %s"% (this,))
        for k in this.keys():
            logging.debug("  after %s"%(k,))
            for i in this[k].keys():
                logging.debug("  key %s"%(i,))
                logging.debug("    out: i: %s, %s"%(i,this[k][i],))
                # pivot
                if not name in data:
                    data[name] = {}
                data[name][i] = this[k][i]

        # raise Exception, "Deal with multiple entries for merge_defs %s" % (this,)
    return data

def _process_by_function( data, name, definition, **kwargs ):
    """
    allow user to run a function on the value, key or entire group 
    """
    # import user functions?
    y = definition.keys().pop()
    if not y in definition:
        raise Exception, '      function call not defined'
    func = definition[y]
    logging.debug("    processing function on %s with %s" % (y,definition) )
    if y in ( 'key', 'value' ):
        by_key = True if y == 'key' else False
        for k,v in data[name].items():
            try:
                if by_key:
                    j = globals()[func]( k )
                    if not j == k:
                        data[name][j] = v
                        logging.debug("      converted %s %s\t-> %s" % (y,k,j) )
                        del data[name][k]
                else:
                    # logging.debug("      calling function on %s" % (v) )
                    this = globals()[func]( v )
                    # logging.debug("        got %s for %s %s" % (this,name,k) )
                    data[name][k] = this
                    logging.debug("      converted %s %s to %s" % (y,v,data[name][k]))
            except Exception, e:
                logging.warn('      could not execute function %s on %s %s: (%s) %s' % (func,y,k if y == 'key' else v,type(e),e))
                
    elif y == 'delete':
        
        logging.debug("       deleting %s" % (definition[y]))
        grp, _tmp, ref = definition[y].partition(':')
        if grp in data and ref in data[grp]:
            del data[grp][ref]
    
    elif y == 'delete_key':
    
        logging.debug("       deleting key %s" % (definition[y]))
        grp, _tmp, ref = definition[y].partition(':')
        if grp in data:
            for k in data[grp]:
                if ref in data[grp][k]:
                    del data[grp][k][ref]
    
    
    elif y == 'delete_entry_unless':

        ref, _tmp, val = definition[y].partition('==')
        grp, _tmp, var = ref.partition(':')
        
        logging.debug("       deleting entries unless (%s) %s == %s: %s" % (grp,var,val,{}))
        if grp in data:
            # logging.debug("has grp %s" %(grp,pformat(data)) )
            for k in data[grp].keys():
                delete = False
                if not var in data[grp][k]:
                    logging.debug("         deleting (no key) %s" % (data[grp][k],))
                    delete = True
                elif not data[grp][k][var] == val:
                    logging.debug("         deleting (inequal) %s" % (data[grp][k],))
                    delete = True
                if delete:
                    del data[grp][k]
    
    elif y == 'group':
        try:
            data[name] = globals()[func]( data )
        except Exception, e:
            t = traceback.format_exc()
            logging.warn('      could not run function %s on group: (%s) %s\n%s' % (func,type(e),e,t) )

    elif y == 'dataset':
        try:
            data = globals()[func]( data )
        except Exception, e:
            t = traceback.format_exc()
            logging.warn('      could not run function %s on dataset: (%s) %s\n%s' % (func,type(e),e,t) )

    else:
        logging.warn("       unknown function call %s" % y )


    return data    
    
    
def _process_by_post_null( g, d, data, defn ):
    """
    null function
    """
    yield g, d, data
    
def _process_by_post_function( g, d, data, defn ):
    """ call the function defined, we can call it on the entire data structure, or per group item """
    x = defn.keys()[0]
    func = defn[x]
    # logging.debug("# x: %s, func: %s" % (x,func))
    try:
        for g, d, data in globals()[func]( g, d, data ):
            yield g, d, data

    except Exception, e:
        t = traceback.format_exc()
        logging.warn('      could not run function %s on dataset: (%s) %s\n%s' % (func,type(e),e,t) )
    return
    
    
    
def _process_by_swap_index_with_field( data, name, definition, **kwargs ):
    """
    operate on the entire group and take a field's value and use that as the index
    with the existing index, take in a field name to use to put into datastructure after
    """
    logging.debug("    processing swap index %s with field %s" %(name,definition) )
    if 'field' in definition:
        f = definition['field']
        # logging.error("GOT: %s, %s"%(f,data) )
        if name in data:
            this = {}
            logging.debug(">>> %s"%(data[name]))
            try:
                pass
                # this[name] = data[name]
            except Exception, e:
                logging.warn( '      could not swap index %s with field %s' % (name,f) )
    return data

def _process_by_set_value_as_key( data, name, definition, **kwargs ):
    logging.debug("    processing set value to equal index %s %s, %s" %(name,definition, data) )
    if name in data:
        for k,v in data[name].items():
            data[name][k] = k
            logging.debug("      setting %s %s as %s"%(name,k,k))
    else:
        logging.warn( '      name %s not in data %s' % (name,data) )
    return data

def _process_by_swap_key_values( data, name, definition ):
    """ exchange the key with the values """
    raise NotImplementedError, 'doesnt work'
    temp = {}
    for k,v in data[name].iteritems():
        temp[v] = k
    data[name] = temp
    logging.error("SWAPPED: %s" % (temp,))
    return data

def _process_by_value_math( data, name, definition, **kwargs ):
    logging.debug("    processing value math with " + str(definition) )
    func = definition.keys().pop()
    if func == None:
        logging.warn('      no math defined on map: ' + str(definition))
        return data
    
    value = definition[func]
    for k,v in data[name].items():
        try:
            if func == 'divide_by':
                data[name][k] = float(v) / float(value)
            elif func == 'multiply_by':
                data[name][k] = float(v) * float(value)
            else:
                logging.warn('      math function ' + str(func) + ' not understood: ' + str(definition))
                
        except Exception, e:
            logging.warn('      could not perform math using ' + str(func) + ' on ' + str(value) + " on group: " + str(e))
    return data


def _process_by_to_array( data, name, definition, **kwargs ):
    logging.debug("    converting to array with %s by %s" % ( name, definition) )
    # logging.debug("DATA: " + str(data[name]))
    return [ k for k,v in data[name].iteritems() ]


def _process_by_filter( data, name, definition, **kwargs ):
    logging.debug("    processing filter with " + str(definition) )
    if 'key' or 'value' in definition:
        y = definition.keys().pop()
        mapping = definition[y]
        for k,v in data[name].items():
            # incase it's an integer
            i = str(k) if y == 'key' else str(v)
            try:
                i = int(i)
            except:
                pass
            # logging.debug('  i:\t' + str(i) + '\t('+str(type(i))+'),\t' + str(mapping))
            if i in mapping:
                if not mapping[i]:
                    logging.debug("      removing %s, %s" % ( k, v ) )
                    del data[name][k]
            # see if other is defined
            elif 'other' in mapping:
                # logging.debug('     other: ' + str(mapping['other']))
                if not mapping['other']:
                    logging.debug("      removing %s, %s" % ( k, v ) )
                    del data[name][k]
    else:
        raise Exception, 'filter must be defined by key or value dict'
    return data



def _process_by_post_new_group_from_field( g, d, data, defn ):
    if 'field' in defn:
        f = defn['field']
        logging.debug("  new group from %s: %s -> %s" % (defn,f,d))
        if f in d:
            new_g = "%s@%s=%s" % (g,f,d[f])
            # logging.debug( ' new: %s' % (new_g,))
            del d[f]
            # logging.debug( '   d: %s' % (d,))
            yield new_g, d, data
    return

def _process_by_default_value( g, d, data, defn ):
    """
    looks at the dict and if the key of defn isn't there, will set a default value for it based on v
    """
    for k,v in defn.iteritems():
        if not k in d:
            logging.debug("     setting default value for %s: %s" % (k,v)) 
            d[k] = v
    yield g, d, data

def _process_by_post_rename_key( g, d, data, defn ):
    """
    renames the key name for the set given
    """
    logging.debug("    post key rename %s" % (defn,) )
    for k, v in defn.iteritems():
        if k in d:
            logging.debug("     renaming key %s: %s" % (k,v))
            value = d[k]
            d[v] = value
            del d[k]
    yield g, d, data

def _process_by_post_remove( g, d, data, defn ):
    """
    removes the entry if the field defined matches
    """
    logging.debug("    post removing %s" % (defn,) )
    for k, v in defn.iteritems():
        if k in d and d[k] == v:
            logging.debug( "     skipping %s >: %s" % (d[k],d,))
            yield None, None, data
        elif v == None or not k in d:
            if not k in d:
                logging.debug("    removing empty")
                yield None, None, data
    yield g, d, data

def _process_by_post_clean( g, d, data, defn ):
    """
    removes the field if the field defined matches
    """
    logging.debug("    post removing field %s" % (defn,) )
    # delete d[]
    for i in defn:
        if i in d:
            del d[i]
    yield g, d, data
    
def _process_by_post_merge( g, d, data, defn ):
    """
    given other groups, merges them into this group g
    takes care of prefix of group names
    """
    logging.debug("    post merge: %s " % (defn))
    for k,s in defn.iteritems():
        if k in data:
            logging.debug("     merging %s" % k)
            this = {}
            for i,d in data[k].iteritems():
                logging.debug("      got %s %s" % (i,d))
                for u,v in d.iteritems():
                    w = u.replace(s,'')
                    this[w] = v
                logging.debug("      yield %s" % this)
                yield g, this.copy(), data

PROCESS_BY_MAP = {
    'key_sub':      _process_by_key_remap,
    'value_sub':    _process_by_value_remap,
    'regexp':       _process_by_regexp,
    'extract_from_key': _process_by_extract_from_key,
    'function':     _process_by_function,
    'value_math':   _process_by_value_math,
    'to_array':     _process_by_to_array,
    'filter':       _process_by_filter,
    # 'swap_index_with_field':    _process_by_swap_index_with_field,
    'set_value_as_key': _process_by_set_value_as_key,
    'swap_keys_and_values': _process_by_swap_key_values,
    
    # post
    'merge_defs':   _process_by_merge_defs,
    
}


PROCESS_BY_POST_MAP = {
    'post_new_group_from_field': _process_by_post_new_group_from_field,
    'post_key_sub': _process_by_post_key_sub,
    'post_function': _process_by_post_function,
    'post_null':    _process_by_post_null,
    'post_extract': _process_by_post_extract,
    'post_default_value':   _process_by_default_value,
    'post_key_rename': _process_by_post_rename_key,
    'post_remove':  _process_by_post_remove,
    'post_clean':   _process_by_post_clean,
    'post_merge':   _process_by_post_merge,
    # 'post_filter':  _process_by_post_filter,
}

class Driver( object ):
    """
    abstract class for definition of a driver that determines how and what to poll
    """
    name = None
    
    agent_settings = None
    mapping_defs = None
    groups_defs = None
    iterative_groups_defs = None
    post_defs = None
    
    def __init__(self, filepath):
        self.name = filepath
        conf = self.load( self.name )
        self.agent_settings, self.mapping_defs, self.groups_defs, self.iterative_groups_defs = self.process( conf )
    
    def load( self, file ):
        # initiate the driver from a file
        pass
    
    def specification(self):
        # what this driver is for
        return self.conf.specification

    def _groups_defs( self, inside='groups' ):
        g = self.groups_defs
        if inside == 'iterative_groups':
            g = self.iterative_groups_defs
        # logging.debug("_groups_defs: %s: %s" % (inside,g))
        return g

    def groups(self, inside='groups'):
        return self._groups_defs( inside=inside ).keys()

    def agents( self ):
        for a in self.agent_settings.keys():
            yield a, self.agent_settings[a]
        return


    def __refs( self, j, refs ):
        # logging.debug("  map definition instance = " + str(type(j)))
        if isinstance( j, list ):
            for o in j:
                # logging.debug("    o=%s" % (o,))
                # for x,y in o.items():
                #     if 'ref' in y:
                #         refs[y['ref']] = True
                refs = self.__refs( o, refs )
        elif isinstance( j, dict ):
            for x,y in j.items():
                if 'ref' in y:
                    refs[y['ref']] = True
        return refs

    def _refs( self, r ):
        refs = {}
        logging.debug("  _refs: %s" % (r,))
        for k,v in r.items():
            # logging.debug(" this one: " + str(v))
            if 'ref' in v:
                refs[v['ref']] = True
            if 'map' in v:
                # logging.error("MAP: %s" % (v['map']))
                for j in v['map']:
                    refs = self.__refs( j, refs )
                    # if isinstance( j, list ):
                    #     for o in j:
                    #         logging.debug("    o=%s" % (o,))
                    #         for x,y in o.items():
                    #             if 'ref' in y:
                    #                 refs[y['ref']] = True
                    # elif isinstance( j, dict ):
                    #     for x,y in j.items():
                    #         if 'ref' in y:
                    #             refs[y['ref']] = True
                    # else:
                    #     raise Exception, 'unknown map ' + str(v['map']) 
        # logging.debug("  r: %s" % (refs.keys(),))
        return refs.keys()

    def refs( self, agent, inside='groups', ignore=[] ):
        """ the agent based variables required for collection """
        refs = {}
        g = self._groups_defs( inside=inside )
        for i in g:
            if i in ignore:
                continue
            if 'defs' in g[i]:
                for r in g[i]['defs']:
                    # allow subarrays to ease configuration syntax
                    for x in self._refs( r ):
                        refs[x] = True
        return refs.keys()
        
    def defs( self, group, inside='groups' ):
        """ a list of items to collect and process """
        g = self._groups_defs( inside=inside )
        if group in g:
            for i in g[group]['defs']:
                yield i
        return
    
    def key_name( self, group, inside='groups' ):
        """ the name for the index used to relate all items together """
        return self._get( 'key_name', group, inside=inside, default='index' )

    def remove_key( self, group, inside='groups' ):
        """ remove the index used to gather the data (eg index 0 stuff) """
        return self._get( 'remove_key', group, inside=inside, default=False )

    def additional_key_names( self, group, inside='groups' ):
        """ what other fields in each dataset should be used as keys/context items """
        return self._get( 'additional_key_names', group, inside=inside, default=None )

    def forced_key_names( self, group, inside='groups' ):
        """ force keys into the context """
        return self._get( 'forced_key_names', group, inside=inside, default=None )

    def clean( self, group, inside='groups' ):
        """ should the group be deleted after use/before export """
        return self._get( 'clean', group, inside=inside, default=False )

    def _get( self, item, group, inside='groups', default=None ):
        g = self._groups_defs( inside=inside )
        if group in g and item in g[group]:
            return g[group][item]
        return default
    
    def post( self, group ):
        """ instructions for post processing the entire dataset """
        g = self.groups_defs
        if group in g and 'post' in g[group]:
            return g[group]['post']
        return None
    
    def _remap( self, i, result, field, parent_data={} ):
        logging.debug("  map on %s: %s"%(field,i))
        if isinstance( i, list ):
            for j in i:
                result = self._remap( j, result, field )
        elif isinstance( i, dict ):
            for k,v in i.items():
                if k in PROCESS_BY_MAP:
                    # logging.error("INPUT %s: %s" % (v,pformat(result),))
                    result = PROCESS_BY_MAP[k]( result, field, v, parent_data=parent_data )
                    # logging.error("FIELD: %s\n%s" % (field,pformat(result)))
                else:
                    raise Exception, "unknown/unregistered map %s" % (k,)
        # logging.debug("  result: %s"%(pformat(result)))
        return result
    
    def _post_remap( self, defn, result, field ):
        logging.debug("  post remap on %s: %s" % (field,defn))
        if isinstance( defn, list ):
            for d in defn:
                result = self._post_remap( defn, result, field )
        elif isinstance( defn, dict ):
            for k,v in i.item():
                if k in POST_PROCESS_MAP:
                    pass
            
    def remap( self, result, field, item, defn, parent_data={} ):
        """ do the work of taking each defn from each def and work the data to suit """
        # check for null entries and report if the field is required
        if 'ref' in item:
            # logging.debug("        remap 0 %s (within results %s) %s" % (item['ref'], result, item['ref'] in result))
            logging.debug("        remap 0 %s (within results) %s" % (item['ref'], item['ref'] in result))
            tally = False
            if item['ref'] in result:
                # logging.debug("  within")
                for k,v in result[item['ref']].iteritems():
                    # logging.debug("    %s %s -> %s" % (item['ref'],k,v))
                    # why does it matter that the value is not None?
                    if not v == None:
                        tally = True
                    # else:
                    #     logging.error("remap() tally had null value for %s" % (item['ref']))
                        # tally = True
                        # logging.error("TALLY OK")
            if not tally:
                # logging.error("NOT TALLY %s" % (item))
                if not 'required' in item or ( 'required' in item and item['required'] ):
                    raise RefNotFound, "field '%s' not in dataset" % (field,)

        # logging.debug("HERE 1 %s" % (item))
        # do field renaming
        if 'ref' in item and not item['ref'] == field:
            result = _process_by_field_rename( result, field, item )

        # logging.debug("HERE 2 %s" % (item))
        if 'map' in item:
            try:
                for i in item['map']:
                    if isinstance( i, list ):
                        for x in i:
                            result = self._remap( x, result, field, parent_data=parent_data )
                    else:
                        result = self._remap( i, result, field, parent_data=parent_data )
            # don't worry if it's a not required def
            except KeyError,e:
                if 'required' in defn[field] and not defn[field]['required']:
                    logging.debug("      remapping failed, but field not required... ignoring")
                    pass
        
        return result
    
    def _remove_key( self, g ):
        remove_key = self.remove_key(g)
        key_name = self.key_name(g)
        this_g, tmp, field = g.partition('@')
        if field:
            remove_key = self.remove_key(this_g,inside='iterative_groups')
            key_name = self.key_name(this_g,inside='iterative_groups')
        return remove_key, key_name
    
    def post_remap( self, results, data, keys ):
        """ 
        after merging the data, do something else with it
        we have two distinct methods of working on the data, that of the entire dataset at once
        or per item with in the group. we can only work on the entire data set for function calls
        so we scan for that independently
        """
        for g in data.keys():
            defn = self.post( g )
            remove_key, key_name = self._remove_key(g)
            try:
                
                # always add the null call if nothing defined
                if not defn:
                    defn = {
                        'map': [ { 'post_null': None } ]
                    }

                # introspect if function call for dataset
                work_on_dataset = False
                for m in defn['map']:
                    n = m.keys()[0]
                    # logging.error("M: %s N %s" % (m,n))
                    if n == 'post_function':
                        if len(m[n].keys()) > 1:
                            raise NotImplementedError, 'post function with chained maps'
                        if m[n].keys()[0] == 'dataset':
                            work_on_dataset = True
                    elif n == 'post_merge':
                        work_on_dataset = True

                logging.debug("post remap on group %s using %s with remove key %s (work? %s)" % (g,defn,remove_key, work_on_dataset))
                
                if work_on_dataset:
                    
                    this_g = g
                    for this_g, d, data in PROCESS_BY_POST_MAP[n]( g, {}, data, m[n] ):
                        # logging.error(" G: %s->%s, D: %s, key_name: %s" % (g,this_g,d,key_name))
                        if remove_key and key_name in d:
                            del d[key_name]
                        if not this_g in results:
                            results[this_g] = []
                        results[this_g].append(d)
                    
                else:
                
                    # logging.debug("DATA: keys %s, g %s \t %s" % (keys,g,data))
                
                    for k in data[g].keys():
                    
                        # create a dict
                        d = data[g][k]
                        if not keys[g] in d:
                            d[keys[g]] = k
                        # logging.debug("   1 g: %s, k: %s, D: %s" % (g,k,d))

                        # before adding, call the post function(s)
                        this_g = g
                        # if any POST function returns none, then do not add to result set
                        for m in defn['map']:
                            n = m.keys()[0]
                            # logging.debug("    # M: %s, N: %s" % (m,n))
                            if d:
                                for this_g, d, data in PROCESS_BY_POST_MAP[n]( g, d, data, m[n] ):
                                    if d == None:
                                        break
                        # logging.debug("   2 g: %s, k: %s, D: %s" % (g,k,d))

                        if d:
                            # remove key?
                            if remove_key:
                                del d[key_name]

                            if not this_g in results:
                                results[this_g] = []                        
                            results[this_g].append(d)

                        # if isinstance( d, list ):
                        #     for x in d:
                        #         result = self._post_remap( x, result, defn )
                        # else:
                        #     result = self._post_remap( d, result, defn )

            except Exception,e:
                raise e
        # logging.debug("RESULTS: %s"%results)
        return results
    
    def process_group_by_key(self, group, inside='groups'):
        g = self.groups_defs
        if inside == 'iterative_groups':
            g = self.iterative_groups_defs
        return g[group]['group_by_key']


class YAMLDriver( Driver ):
    
    def load( self, filepath ):
        conf = {}
        with open( filepath ,'r' ) as f:
            # logging.error("F: %s" % (f,))
            conf = yaml.load( f, Loader=Loader )
            # logging.error("C: %s" % (conf,))
        return conf

    def group_defaults( self, conf, definition, group ):
        if group in conf[definition]:
            if 'defaults' in conf[definition][group]:
                return conf[definition][group]['defaults']
        return {}
    
    def get_defaults( self, conf, definition, group ):
        # propogate global and local
        defaults = {}
        # get global
        if 'defaults' in conf:
            defaults = conf['defaults'].copy()
        # logging.debug("global defaults: " + str(defaults))
        # get local
        local_defaults = self.group_defaults( conf, definition, group )
        # logging.debug("local defaults for " + str(group) + ": " + str(local_defaults) )
        for k,v in local_defaults.items():
            defaults[k] = v
        return defaults

    def definition_stanza( self, stanza, defaults={} ):
        # determines all the defaults for this stanza
        logging.debug("  stanza: " + str(stanza) + " with defaults " + str(defaults))
        this = defaults.copy()
        for k,v in stanza.items():
            # logging.debug("  s: " + str(s) + " => " + str(stanza[s]) )
            for i,j in stanza[k].items():
                this[i] = j
        out = { k: this }
        # logging.debug("    -> " + str(out))
        agent = this['agent']
        return out, agent
        
    def _process( self, conf, field='definition', agents={} ):
        
        # defined in groups
        groups = {}
        if field in conf:
            logging.debug("getting def's for " + str(field))
            for g in conf[field]:
                groups[g] = { 'defaults': self.get_defaults( conf, field, g ), 'defs': [], 'group_by_key': False }
                # logging.debug("defaults: " + str(groups[g]['defaults']))
                if 'group_by_key' in conf[field][g] and conf[field][g]['group_by_key'] == True:
                    groups[g]['group_by_key'] = conf[field][g]['group_by_key']

                if 'key_name' in conf[field][g]:
                    groups[g]['key_name'] = conf[field][g]['key_name']
                if 'additional_key_names' in conf[field][g]:
                    groups[g]['additional_key_names'] = conf[field][g]['additional_key_names']
                if 'forced_key_names' in conf[field][g]:
                    groups[g]['forced_key_names'] = conf[field][g]['forced_key_names']

                if 'clean' in conf[field][g]:
                    groups[g]['clean'] = conf[field][g]['clean']
                if 'remove_key' in conf[field][g]:
                    groups[g]['remove_key'] = conf[field][g]['remove_key']

                # local for def's
                def_defaults = groups[g]['defaults'].copy()
                if 'settings' in def_defaults:
                    del def_defaults['settings']
                # determine full def
                if 'defs' in conf[field][g]:
                    if  not isinstance( conf[field][g]['defs'], list ):
                        raise Exception, 'defs must be defined as a list in driver %s group %s' % (self.name,g)
                    for s in conf[field][g]['defs']:
                        this, agent = self.definition_stanza( s, defaults=def_defaults )
                        # add agents
                        if not agent in agents:
                            agents[agent] = {}
                        # append to groups
                        groups[g]['defs'].append( this )
                elif not 'post' in conf[field][g]:
                    raise Exception, 'no useable stanzas found in driver %s for group %s' %(self.name,g)
                    
                # groups
                if 'post' in conf[field][g]:
                    # logging.error("FOUND: %s" % (conf[field][g]['post']))
                    groups[g]['post'] = conf[field][g]['post']
        # logging.debug("group: %s" % (groups))
        return groups, agents
        
    def process( self, conf ):
        """
        return the refs for the agent (ie the options to provide to the polling agents)
        """
        # ref's may be contained within the group:definition or within the mapping or group:mapping
        # we search through all to determine what ref's are defined
        agents = {}
        
        # defaults
        if 'defaults' in conf:
            if 'settings' in conf['defaults']:
                for a in conf['defaults']['settings']:
                    agents[a] = conf['defaults']['settings'][a]
        
        # global mappings
        # logging.debug("getting mapping's")
        mapping = {}
        if 'mapping' in conf:
            mapping = conf['mapping']
        # logging.debug( "mapping: " + str(mapping) )
        
        groups, agents = self._process( conf, field='definition', agents=agents )
        # logging.error("GROUPS: " + str(groups))
        if len(groups.keys()) == 0:
            raise Exception, 'no definitions found'
        iterative_groups, agents = self._process( conf, field='iterative_definition', agents=agents )
                
        return agents, mapping, groups, iterative_groups
