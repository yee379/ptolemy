from netsnmp_types import *
from ctypes import *
import os

import logging

class OID(tuple):

    def __new__(cls, seq, length=None):
        """Note: length should only be used for sequence types that
        may not be able to report their length properly."""
        if isinstance(seq, OID):
            return seq
        elif isinstance(seq, basestring):
            try:
                seq = [int(v) for v in seq.strip('.').split('.')]
            except ValueError:
                seq = cls._parse_oid(seq)
        else:
            if length is not None:
                seq = [seq[i] for i in xrange(length)]
            try:
                seq = [int(v) for v in seq]
            except (ValueError, TypeError):
                raise Exception, 'could not translate %s to OID' % str(seq)

        self = super(OID, cls).__new__(cls, seq)
        self.raw = (oid * len(self))()
        for i, v in enumerate(self):
            self.raw[i] = v

        return self

    @classmethod
    def _parse_oid(cls, string):
        buf_len = c_size_t(MAX_OID_LEN)
        buf = (oid * MAX_OID_LEN)()
        if ':' in string:
            module, string = string.split(':', 1)
            if string.startswith(':'):
                string = string[1:]
            lib.netsnmp_read_module(module)
            if lib.which_module(module) == -1:
                raise Exception, "Cannot find module %s" % module
        else:
            module = "ANY"

        if lib.get_module_node(string, module, buf, byref(buf_len)) == 0:
            if module == "ANY":
                raise Exception, "Cannot translate name '%s' to OID" % string
            else:
                raise Exception, "Cannot find node %s in %s" % (string, module)
        return [buf[i] for i in xrange(buf_len.value)]

    def __str__(self):
        return ".%s" % ".".join(str(i) for i in self)

    def __repr__(self):
        return "<OID %r>" % list(self)

    def _tree(self):
        return lib.get_tree(self.raw, len(self), lib.get_tree_head())

    def hint(self):
        tree = self._tree()
        if tree:
            return tree.contents.hint
        return None

    def decode( self ):
        return _decode_oid( self )

def _decode_oid(oid):
    """ returns the nearest match name with iid """
    cbuff = create_string_buffer('', SPRINT_MAX_LEN )
    length = c_size_t(len(cbuff))
    n = lib.snprint_objid(cbuff, byref(length), oid.raw, len(oid))
    if n:
        m, f = cbuff[:n].split('::')
        f, tmp, iid = f.partition('.')
        # o = OID( _name_to_oid( s ) )
        return m, f, iid
    return None, None, None
    
def _name_to_oid( s ):
    """ convert a string to oid object """
    if isinstance( s, basestring ):
        if s[:2] == '.1': # 'iso' + s[2:]
            return map(int, filter (None, s.split ('.')))
        else:
            o = (c_long*MAX_OID_LEN)()
            l = c_size_t(len(o))
            r = lib.get_node( s, o, byref(l) )
            # logging.debug(" _name_to_oid: " + str(s) + ", r: " + str(r) + ", oid: " + str([ str(i) for i in oid]))
            return OID(o[:l.value]) if r else None
    return None

def _decode_objid(objid, var):
    length = var.val_len / sizeof(oid)
    return OID(var.val.objid, length)

def _decode_ip(objid, var):
    return '.'.join(map(str, var.val.bitstring[:4]))

def _decode_counter64(objid, var):
    int64 = var.val.counter64.contents
    return (int64.high << 32L) + int64.low

def _decode_raw_string(objid, var):
    return string_at(var.val.bitstring, var.val_len)

def _decode_string(objid, var):
    hint = objid.hint()
    if hint:
        buf_len = 260
        buf = create_string_buffer(buf_len)
        ret = lib.snprint_octet_string(buf, buf_len,
                byref(var), None, hint, None)
        if ret == -1:
            return _decode_raw_string(objid, var)
        else:
            return str(buf.value)
    else:
        return _decode_raw_string(objid, var)


class OIDException( Exception ):
    """ parent exception class"""
    def __str__(self):
        return self.__class__.__doc__

class NoSuchObject( OIDException ):
    """ No such object """

class NoSuchInstance( OIDException ):
    """ No such instance"""

class EndOfMibView( OIDException ):
    """ No more mib """

class OIDValueError( OIDException ):
    """ unparseable value """
    
_decoder = {
    ASN_OCTET_STR:    _decode_string,
    ASN_BOOLEAN:      lambda id, var: var.val.integer.contents.value,
    ASN_INTEGER:      lambda id, var: var.val.integer.contents.value,
    ASN_NULL:         lambda id, var: None,
    ASN_OBJECT_ID:    _decode_objid,
    ASN_BIT_STR:      _decode_raw_string,
    ASN_IPADDRESS:    _decode_ip,
    ASN_COUNTER:      lambda id, var: var.val.uinteger.contents.value,
    ASN_GAUGE:        lambda id, var: var.val.uinteger.contents.value,
    ASN_TIMETICKS:    lambda id, var: var.val.uinteger.contents.value,
    ASN_COUNTER64:    _decode_counter64,
    ASN_APP_FLOAT:    lambda id, var: var.val.float.contents.value,
    ASN_APP_DOUBLE:   lambda id, var: var.val.double.contents.value,

    # Errors
    SNMP_NOSUCHOBJECT:    lambda id, var: NoSuchObject(),
    SNMP_NOSUCHINSTANCE:  lambda id, var: NoSuchInstance(),
    SNMP_ENDOFMIBVIEW:    lambda id, var: EndOfMibView(),
}

def _decode_variable(objid, var):
    if var.type not in _decoder:
        raise Exception("SNMP data type %d not implemented" % var.type)
    return _decoder[var.type](objid, var)


class NetSNMP(object):

    default_options = {
        'community': 'public',
        'timeout': 3,
        'retries': 2,
        'version': '2c',
        'port': 161,
        'mib_dir': [],
        'mibs': [],
    }

    max_repeaters = 100

    def __init__(self, host, options={} ):
        self.sessp = None   # single session api pointer
        self.session = None # session struct
        self.session_template = netsnmp_session()
        self._requests = {}

        if 'mib_dirs' in options:
            if len( options['mib_dirs'] ) == 1:
                self.add_mibdir( options['mib_dirs'] )
            else:
                for d in options['mib_dirs']:
                    self.add_mibdir( d )

        # initilise mibs
        lib.init_mib()
        logging.debug("using mib_dirs: " + str(self.get_mibdirs()))

        # load mibs
        if 'mibs' in options:
            for m in options['mibs']:
                self.add_mib_module( m )

        # Initialize session to default values
        lib.snmp_sess_init(byref(self.session_template))

        kwargs = {}
        kwargs['peername'] = host
        for k,v in self.default_options.iteritems():
            kwargs[k] = v
            if k in options:
                kwargs[k] = options[k]
            if k == 'version':
                if kwargs[k] in ( 1, '1' ):
                    kwargs[k] = SNMP_VERSION_1
                elif kwargs[k] in ( 2, '2', '2c' ):
                    kwargs[k] = SNMP_VERSION_2c
            elif k == 'community':
                kwargs['community_len'] = len(kwargs[k])
            elif k == 'timeout':
                kwargs[k] = int(kwargs[k] * 1e6)

        for k,v in kwargs.iteritems():
            setattr(self.session_template, k,v)


    def __enter__(self):
        self.sessp = lib.snmp_sess_open(byref(self.session_template))
        if not self.sessp:
            raise SnmpError('snmp_sess_open')
        self.session = lib.snmp_sess_session(self.sessp)
        return self

    def __exit__(self, *args):
        assert self.sessp
        lib.snmp_sess_close(self.sessp)
        self.sessp = None
        self.session = None
        self._session_callback = None
        self._requests.clear()


    def get_mibdirs(self):
        return lib.netsnmp_get_mib_directory().split(':')

    def add_mibdir( self, path ):
        cur = self.get_mibdirs()
        # don't bother if we already have it
        if not path in cur:            
            dirs = ":".join(cur)
            if len(path) > 0:
                 dirs = dirs + ':' + ":".join(path)
            lib.netsnmp_ds_set_string(
                    NETSNMP_DS_LIBRARY_ID,
                    NETSNMP_DS_LIB_MIBDIRS,
                    dirs
            )
        return True
    
    def add_mib_module(self, module):
        logging.debug('  reading mib: ' + str(module))
        lib.netsnmp_read_module(module)
        if lib.which_module(module) == -1:
            raise Exception, "Cannot find module %s" % module

    # def add_mib_module(self, module):
    #     logging.debug('  reading mib: ' + str(module))
    #     mibs = []
    #     if 'MIBS' in os.environ:
    #         mibs = os.environ['MIBS'].split(':')
    #     mibs.append( module )
    #     os.environ['MIBS'] = ':'.join(mibs) 

    def fetch( self, oids, method='bulkwalk' ):
        m = 'fetch_by_' + str(method)
        try:
            f = getattr(self, m)
            return f( oids )
        except:
            raise Exception, 'unknown fetch method ' + str(method) 

    def fetch_by_bulkwalk( self, oids ):
        assert self.sessp
        
        for name in oids:

            this_f = name
            this_oid = OID(name)
            m, wanted_f, iid = this_oid.decode()
            if iid == '':
                iid = 0

            while this_f == name:

                logging.debug("fetch_by_bulkwalk: " + str(name) +  ", iid: " + str(iid) + " (oid: " + str(this_oid) + ")")

                req = lib.snmp_pdu_create(SNMP_MSG_GETBULK)
                lib.snmp_add_null_var(req, this_oid.raw, len(this_oid))
                req.contents.errstat = 0
                req.contents.errindex = self.max_repeaters
        
                response = POINTER(netsnmp_pdu)()
                if lib.snmp_sess_synch_response(self.sessp, req, byref(response)):
                    raise Exception, "could not sess_sync"

                # spit out only wanted oids
                for o,v in self._parse(response.contents):
                    # if seq(o) is the same as seq(this_oid)
                    m, this_f, iid = o.decode()
                    if this_f == wanted_f:
                        # logging.debug("  got: " +str(o) +"\t" + str(f) + '\t' + str(iid))
                        this_oid = o    # set up for next poll sequence from this field
                        yield this_f,iid,v
            
                lib.snmp_free_pdu(response)

        return
        

    def _parse( self, pdu ):

        err_index = None
        if pdu.errstat != SNMP_ERR_NOERROR:
            err_index = pdu.errindex

        var = pdu.variables
        index = 1
        while var:
            var = var.contents
            o = OID(var.name, var.name_length)

            if err_index is None:
                yield o, _decode_variable(o, var)
            
            elif err_index == index:
                logging.error("ERROR: ("+str(index)+")" + str(pdu.errstat))
                break
            else:
                logging.error("ERROR: "+ str(_decode_error(pdu.errstat)) )

            var = var.next_variable
            index += 1

        return


if __name__ == '__main__':
    logging.basicConfig( level=logging.DEBUG )

    # o = OID('sysDescr')
    # module, field, iid = o.decode()
    
    c = open('/opt/etc/snmp.community.read' ).read().strip()
    # s = NetSNMP( 'rtr-core1', options={ 'community': c, 'version': '2c' } )
    # 
    # with s as agent:
    #     for f,i,v in agent.fetch( [ 'ifAlias', 'sysName', 'sysLocation' ] ):
    #         print str(f) + "\t" + str(i) + "\t" + str(v)

    s = NetSNMP( 'rtr-core1', options={ 'community': c, 'mib_dirs': [ '/opt/ptolemy/etc/ptolemy/polld/snmp_mibs/' ], 'mibs': ['CISCO-MEMORY-POOL-MIB'] } )
    with s as agent:
        for f,i,v in agent.fetch( [ 'ciscoMemoryPoolUsed' ] ):
            print str(f) + "\t" + str(i) + "\t" + str(v)

