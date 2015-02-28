from ctypes import *

import logging


c_int_p = POINTER(c_int)
u_char_p = c_char_p
u_char_p = c_char_p
u_char = c_ubyte
u_int = c_uint

oid = c_long
fd_mask = c_ulong
fd_set_p = POINTER(fd_mask)

ASN_CONTEXT = (0x80)
ASN_CONSTRUCTOR = (0x20)
SNMP_MSG_GETBULK = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x5)
SNMP_MSG_GET = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x0)
SNMP_MSG_GETNEXT = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x1)

MAX_OID_LEN = 128

localname = []
paramname = []
authenticator = CFUNCTYPE(c_char_p, c_int_p, c_char_p, c_int)

class tree(Structure): pass
class netsnmp_session(Structure): pass
class netsnmp_transport(Structure): pass

class netsnmp_pdu(Structure): pass
class netsnmp_variable_list(Structure): pass

netsnmp_pdu_p = POINTER(netsnmp_pdu)

netsnmp_callback = CFUNCTYPE(c_int,
                             c_int, POINTER(netsnmp_session),
                             c_int, POINTER(netsnmp_pdu),
                             c_void_p)

netsnmp_session._fields_ = [
        ('version', c_long),
        ('retries', c_int),
        ('timeout', c_long),
        ('flags', c_ulong),
        ('subsession', POINTER(netsnmp_session)),
        ('next', POINTER(netsnmp_session)),
        ('peername', c_char_p),
        ('remote_port', c_ushort),
        ] + localname + [
        ('local_port', c_ushort),
        ('authenticator', authenticator),
        ('callback', netsnmp_callback),
        ('callback_magic', c_void_p),
        ('s_errno', c_int),
        ('s_snmp_errno', c_int),
        ('sessid', c_long),
        ('community', u_char_p),
        ('community_len', c_size_t),
        ('rcvMsgMaxSize', c_size_t),
        ('sndMsgMaxSize', c_size_t),

        ('isAuthoritative', u_char),
        ('contextEngineID', u_char_p),
        ('contextEngineIDLen', c_size_t),
        ('engineBoots', c_uint),
        ('engineTime', c_uint),
        ('contextName', c_char_p),
        ('contextNameLen', c_size_t),
        ('securityEngineID', u_char_p),
        ('securityEngineIDLen', c_size_t),
        ('securityName', c_char_p),
        ('securityNameLen', c_size_t),

        ('securityAuthProto', POINTER(oid)),
        ('securityAuthProtoLen', c_size_t),
        ('securityAuthKey', u_char * 32),
        ('securityAuthLocalKey', c_char_p),
        ('securityAuthLocalKeyLen', c_size_t),

        ('securityPrivProto', POINTER(oid)),
        ('securityPrivProtoLen', c_size_t),
        ('securityPrivKey', c_char * 32),
        ('securityPrivKeyLen', c_size_t),
        ('securityPrivLocalKey', c_char_p),
        ('securityPrivLocalKeyLen', c_size_t),

        ] + paramname + [

        ('securityModel', c_int),
        ('securityLevel', c_int),

        ('securityInfo', c_void_p),

        ('myvoid', c_void_p),
        ]

class counter64(Structure):
    _fields_ = [
        ('high', c_ulong),
        ('low', c_ulong),
        ]
        
class netsnmp_vardata(Union):
    _fields_ = [
        ('integer', POINTER(c_long)),
        ('uinteger', POINTER(c_ulong)),
        ('string', c_char_p),
        ('objid', POINTER(oid)),
        ('bitstring', POINTER(c_ubyte)),
        ('counter64', POINTER(counter64)),
        ('floatVal', POINTER(c_float)),
        ('doubleVal', POINTER(c_double)),
        ]
        
netsnmp_variable_list._fields_ = [
        ('next_variable', POINTER(netsnmp_variable_list)),
        ('name', POINTER(oid)),
        ('name_length', c_size_t),
        ('type', u_char),
        ('val', netsnmp_vardata),
        ('val_len', c_size_t),
        ('name_loc', oid * MAX_OID_LEN),
        ('buf', c_char * 40),
        ('data', c_void_p),
        ('dataFreeHook', CFUNCTYPE(c_void_p)),
        ('index', c_int),
        ]

netsnmp_pdu._fields_ = [
        ('version', c_long ),
        ('command', c_int ),
        ('reqid', c_long ),
        ('msgid', c_long ),
        ('transid', c_long ),
        ('sessid', c_long ),
        ('errstat', c_long ),   # (non_repeaters in GetBulk)
        ('errindex', c_long ),  # (max_repetitions in GetBulk)
        ('time', c_ulong ),
        ('flags', c_ulong ),
        ('securityModel', c_int ),
        ('securityLevel', c_int ),
        ('msgParseModel', c_int ),
        ('transport_data', c_void_p),
        ('transport_data_length', c_int ),
        ('tDomain', POINTER(oid)),
        ('tDomainLen', c_size_t ),
        ('variables', POINTER(netsnmp_variable_list)),
        ('community', c_char_p),
        ('community_len', c_size_t ),
        ('enterprise', POINTER(oid)),
        ('enterprise_length', c_size_t ),
        ('trap_type', c_long ),
        ('specific_type', c_long ),
        ('agent_addr', c_ubyte * 4),
        ('contextEngineID', c_char_p ),
        ('contextEngineIDLen', c_size_t ),
        ('contextName', c_char_p),
        ('contextNameLen', c_size_t ),
        ('securityEngineID', c_char_p),
        ('securityEngineIDLen', c_size_t ),
        ('securityName', c_char_p),
        ('securityNameLen', c_size_t ),
        ('priority', c_int ),
        ('range_subid', c_int ),
        ('securityStateRef', c_void_p),
        ]

netsnmp_transport._fields_ = [
    ('domain', POINTER(oid)),
    ('domain_length', c_int),
    ('local', u_char_p),
    ('local_length', c_int),
    ('remote', u_char_p),
    ('remote_length', c_int),
    ('sock', c_int),
    ('flags', u_int),
    ('data', c_void_p),
    ('data_length', c_int),
    ('msgMaxSize', c_size_t),
    ('f_recv', c_void_p),
    ('f_send', c_void_p),
    ('f_close', c_void_p),
    ('f_accept',  c_void_p),
    ('f_fmtaddr', c_void_p),
]

def _to_oid(l):
    if l:
        r = (c_long * len(l))()
        logging.debug("_to_oid: " + str(l))
        for i, v in enumerate(l):
            r[i] = v
        return r
    return None
            
def _mkname( s ):
    """ module and oid """
    oid = _name_to_oid(s)
    return _oid_to_name( oid )

def _name_to_oid( s ):
    if isinstance( s, basestring ):
        if s[:2] == '.1': # 'iso' + s[2:]
            return map(int, filter (None, s.split ('.')))
        else:
            oid = (c_long*MAX_OID_LEN)()
            l = c_size_t(len(oid))
            r = lib.get_node( s, oid, byref(l) )
            # logging.debug(" _name_to_oid: " + str(s) + ", r: " + str(r) + ", oid: " + str([ str(i) for i in oid]))
            return oid[:l.value] if r else None
    return None

def _oid_to_name( o):
    if o and not isinstance (o, basestring):
        cbuff = create_string_buffer('', 2560) # SPRINT_MAX_LEN = 2560
        length = c_size_t(len(cbuff))
        an_oid = (c_long * len(o))()
        for i, v in enumerate(o):
            an_oid[i] = v
        r = self.lib.snprint_objid(cbuff, byref(length), an_oid, len (an_oid))
        if r:
            r = cbuff[:r]
        else:
            r = ''
    else:
        r = o
    return r

def _oid_to_n( oid ):
    s = ''
    for n in oid:
        s = s + '.' + str(n)
    return s




netsnmp_lib_map = {
    'snmp_open':        ( [ POINTER(netsnmp_session) ], c_void_p ),
    'snmp_close':       ( [ POINTER(netsnmp_session) ], c_void_p ),
    'snmp_sess_open':   ( [ POINTER(netsnmp_session) ], c_void_p ),
    'snmp_sess_close':  ( [c_void_p], c_int ),
    'snmp_sess_init':   ( [ POINTER(netsnmp_session) ], c_void_p ),
    'snmp_sess_session': ( [c_void_p], c_int ),
    'snmp_sess_timeout': ( [c_void_p], None ),
    'snmp_sess_send':   ( [c_void_p, POINTER(netsnmp_pdu)], c_int ),
    'snmp_sess_read':   ( [c_void_p, fd_set_p], c_int ),
    'netsnmp_init_mib': ( [], None ),
    'netsnmp_read_module': ( [c_char_p], POINTER(tree) ),
    'snmp_pdu_create':  ( [c_int], POINTER(netsnmp_pdu) ),
    'snmp_add_null_var':    ( [POINTER(netsnmp_pdu), POINTER(oid), c_size_t], POINTER(netsnmp_variable_list) ),
    'snmp_free_pdu':    ( [POINTER(netsnmp_pdu)], None ),
    'get_node':  ( [c_char_p, POINTER(oid), POINTER(c_size_t)], c_int ),
    'get_module_node':  ( [c_char_p, c_char_p, POINTER(oid), POINTER(c_size_t)], c_int ),
}
    
    
lib = None
try:
    lib = CDLL( 'libnetsnmp.so', RTLD_GLOBAL )
except OSError:
    from ctypes.util import find_library
    lib = CDLL( find_library('netsnmp'), RTLD_GLOBAL )

# register arg and returns 
for k,v in netsnmp_lib_map.iteritems():
    f = getattr( lib, k )
    f.argtypes = v[0]
    f.restype = v[1]




if __name__ == "__main__":

    sessp = None   # single session api pointer
    session = None # session struct
    session_template = netsnmp_session()
    
    lib.netsnmp_init_mib()
    
    logging.basicConfig( level=logging.DEBUG )

    lib.snmp_sess_init(byref(session_template))

    logging.debug("setting options")
    kwargs = {
        'peername': 'swh-b050f1',
        # 'remote_port':  161,
        'version':  1,
        'community':    'public',
        'timeout':  int(3*1e6),
    }
    kwargs['community_len'] = len(kwargs['community'])
    for k,v in kwargs.iteritems():
        setattr(session_template, k,v)
    
    logging.debug("opening")
    sessp = lib.snmp_sess_open(byref(session_template))
    if not sessp:
        raise Exception, 'could not open net-snmp'
    logging.debug("opened session " + str(session_template) + " pointer " + str(sessp))
    session = lib.snmp_sess_session(sessp)
    logging.debug("session: " + str(session))
    
    assert sessp
    lib.snmp_sess_close( sessp )


    logging.debug("end")
