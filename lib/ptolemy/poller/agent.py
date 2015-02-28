from ctypes import *
from netconfig import NewNetConfig as NetConfigAgent, config_file

import subprocess
import struct
import os

from re import match, search

import logging

class AgentTimeout( Exception ):
    pass

class Agent( object ):
    """
    Generic Agent to collect information
    """
    def __enter__(self):
        return self
        
    def __exit__(self, *args, **kwargs):
        pass

    def fetch( self, host, vars=[], **kargs ):
        """
        generator returning 3-tuple of field, index, and value
        """
        yield 'field', 'iid', 'value'
        return



USM_LENGTH_OID_TRANSFORM = 10

SNMP_CALLBACK_LIBRARY = 0
SNMP_CALLBACK_LOGGING = 4

NETSNMP_CALLBACK_OP_RECEIVED_MESSAGE = 1
NETSNMP_CALLBACK_OP_TIMED_OUT = 2
NETSNMP_CALLBACK_OP_SEND_FAILED = 3
NETSNMP_CALLBACK_OP_CONNECT = 4
NETSNMP_CALLBACK_OP_DISCONNECT = 5

NULL = None
MIN_OID_LEN = 2
MAX_OID_LEN = 128
MAX_NAME_LEN = MAX_OID_LEN
ASN_BOOLEAN = (0x01)
ASN_INTEGER = (0x02)
ASN_BIT_STR = (0x03)
ASN_OCTET_STR = (0x04)
ASN_NULL = (0x05)
ASN_OBJECT_ID = (0x06)
ASN_SEQUENCE = (0x10)
ASN_SET = (0x11)
ASN_UNIVERSAL = (0x00)
ASN_APPLICATION = (0x40)
ASN_CONTEXT = (0x80)
ASN_PRIVATE = (0xC0)
ASN_PRIMITIVE = (0x00)
ASN_CONSTRUCTOR = (0x20)
ASN_LONG_LEN = (0x80)
ASN_EXTENSION_ID = (0x1F)
ASN_BIT8 = (0x80)
ASN_OPAQUE_TAG1 = (ASN_CONTEXT | ASN_EXTENSION_ID)
ASN_OPAQUE_TAG2 = (0x30)
ASN_OPAQUE_TAG2U = (0x2f)
ASN_APP_OPAQUE = (ASN_APPLICATION | 4)
ASN_APP_COUNTER64 = (ASN_APPLICATION | 6)
ASN_APP_FLOAT = (ASN_APPLICATION | 8)
ASN_APP_DOUBLE = (ASN_APPLICATION | 9)
ASN_APP_I64 = (ASN_APPLICATION | 10)
ASN_APP_U64 = (ASN_APPLICATION | 11)
ASN_APP_UNION = (ASN_PRIVATE | 1)
ASN_OPAQUE_COUNTER64 = (ASN_OPAQUE_TAG2 + ASN_APP_COUNTER64)
ASN_OPAQUE_COUNTER64_MX_BER_LEN = 12
ASN_OPAQUE_FLOAT = (ASN_OPAQUE_TAG2 + ASN_APP_FLOAT)
ASN_OPAQUE_FLOAT_BER_LEN = 7
ASN_OPAQUE_DOUBLE = (ASN_OPAQUE_TAG2 + ASN_APP_DOUBLE)
ASN_OPAQUE_DOUBLE_BER_LEN = 11
ASN_OPAQUE_I64 = (ASN_OPAQUE_TAG2 + ASN_APP_I64)
ASN_OPAQUE_I64_MX_BER_LEN = 11
ASN_OPAQUE_U64 = (ASN_OPAQUE_TAG2 + ASN_APP_U64)
ASN_OPAQUE_U64_MX_BER_LEN = 12
ASN_PRIV_INCL_RANGE = (ASN_PRIVATE | 2)
ASN_PRIV_EXCL_RANGE = (ASN_PRIVATE | 3)
ASN_PRIV_DELEGATED = (ASN_PRIVATE | 5)
ASN_PRIV_IMPLIED_OCTET_STR = (ASN_PRIVATE | ASN_OCTET_STR)
ASN_PRIV_IMPLIED_OBJECT_ID = (ASN_PRIVATE | ASN_OBJECT_ID)
ASN_PRIV_RETRY = (ASN_PRIVATE | 7)

SNMP_MAX_LEN = 1500
SNMP_MIN_MAX_LEN = 484
SNMP_VERSION_1 = 0
SNMP_VERSION_2c = 1
SNMP_VERSION_2u = 2
SNMP_VERSION_3 = 3
SNMP_VERSION_sec = 128
SNMP_VERSION_2p = 129
SNMP_VERSION_2star = 130
SNMP_MSG_GET = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x0)
SNMP_MSG_GETNEXT = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x1)
SNMP_MSG_RESPONSE = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x2)
SNMP_MSG_SET = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x3)
SNMP_MSG_TRAP = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x4)
SNMP_MSG_GETBULK = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x5)
SNMP_MSG_INFORM = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x6)
SNMP_MSG_TRAP2 = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x7)
SNMP_MSG_REPORT = (ASN_CONTEXT | ASN_CONSTRUCTOR | 0x8)

SNMP_NOSUCHOBJECT = (ASN_CONTEXT | ASN_PRIMITIVE | 0x0)
SNMP_NOSUCHINSTANCE = (ASN_CONTEXT | ASN_PRIMITIVE | 0x1)
SNMP_ENDOFMIBVIEW = (ASN_CONTEXT | ASN_PRIMITIVE | 0x2)
SNMP_ERR_NOERROR = (0)
SNMP_ERR_TOOBIG = (1)
SNMP_ERR_NOSUCHNAME = (2)
SNMP_ERR_BADVALUE = (3)
SNMP_ERR_READONLY = (4)
SNMP_ERR_GENERR = (5)
SNMP_ERR_NOACCESS = (6)
SNMP_ERR_WRONGTYPE = (7)
SNMP_ERR_WRONGLENGTH = (8)
SNMP_ERR_WRONGENCODING = (9)
SNMP_ERR_WRONGVALUE = (10)
SNMP_ERR_NOCREATION = (11)
SNMP_ERR_INCONSISTENTVALUE = (12)
SNMP_ERR_RESOURCEUNAVAILABLE = (13)
SNMP_ERR_COMMITFAILED = (14)
SNMP_ERR_UNDOFAILED = (15)
SNMP_ERR_AUTHORIZATIONERROR = (16)
SNMP_ERR_NOTWRITABLE = (17)
SNMP_ERR_INCONSISTENTNAME = (18)
MAX_SNMP_ERR = 18

UCD_MSG_FLAG_RESPONSE_PDU = 0x100
UCD_MSG_FLAG_EXPECT_RESPONSE = 0x200
UCD_MSG_FLAG_FORCE_PDU_COPY = 0x400
UCD_MSG_FLAG_ALWAYS_IN_VIEW = 0x800
UCD_MSG_FLAG_PDU_TIMEOUT = 0x1000
UCD_MSG_FLAG_ONE_PASS_ONLY = 0x2000
UCD_MSG_FLAG_TUNNELED = 0x4000

SNMPADMINLENGTH = 255
USM_AUTH_KU_LEN = 32
USM_PRIV_KU_LEN = 32

SNMP_MAX_MSG_SIZE = 1472
SNMP_MAX_MSG_V3_HDRS = (4+3+4+7+7+3+7+16)
SNMP_MAX_ENG_SIZE = 32
SNMP_MAX_SEC_NAME_SIZE = 256
SNMP_MAX_CONTEXT_SIZE = 256
SNMP_SEC_PARAM_BUF_SIZE = 256
SNMPV3_IGNORE_UNAUTH_REPORTS = 0
SNMP_SESS_NONAUTHORITATIVE = 0
SNMP_SESS_AUTHORITATIVE = 1
SNMP_SESS_UNKNOWNAUTH = 2

COMMUNITY_MAX_LEN = 256
SPRINT_MAX_LEN = 2560

ASN_IPADDRESS = (ASN_APPLICATION | 0)
ASN_COUNTER = (ASN_APPLICATION | 1)
ASN_GAUGE = (ASN_APPLICATION | 2)
ASN_UNSIGNED = (ASN_APPLICATION | 2)
ASN_TIMETICKS = (ASN_APPLICATION | 3)
ASN_OPAQUE = (ASN_APPLICATION | 4)
ASN_NSAP = (ASN_APPLICATION | 5)
ASN_COUNTER64 = (ASN_APPLICATION | 6)
ASN_UINTEGER = (ASN_APPLICATION | 7)
ASN_FLOAT = (ASN_APPLICATION | 8)
ASN_DOUBLE = (ASN_APPLICATION | 9)
ASN_INTEGER64 = (ASN_APPLICATION | 10)
ASN_UNSIGNED64 = (ASN_APPLICATION | 11)

# FIRST_PASS = 1
# LAST_PASS = 2
LOG_EMERG = 0
LOG_ALERT = 1
LOG_CRIT = 2
LOG_ERR = 3
LOG_WARNING = 4
LOG_NOTICE = 5
LOG_INFO = 6
LOG_DEBUG = 7
DEFAULT_LOG_ID = "net-snmp"
NETSNMP_LOGHANDLER_STDOUT = 1
NETSNMP_LOGHANDLER_STDERR = 2
NETSNMP_LOGHANDLER_FILE = 3
NETSNMP_LOGHANDLER_SYSLOG = 4
NETSNMP_LOGHANDLER_CALLBACK = 5
NETSNMP_LOGHANDLER_NONE = 6

LOG_PRIORITY_MAP = {
    LOG_EMERG     : 'error',
    LOG_ALERT     : 'error',
    LOG_CRIT      : 'error',
    LOG_ERR       : 'error',
    LOG_WARNING   : 'warn',
    LOG_NOTICE    : 'info',
    LOG_INFO      : 'info',
    LOG_DEBUG     : 'debug',
}

class netsnmp_log_message(Structure): 
        pass
netsnmp_log_message._fields_ = [
        ('priority', c_int),
        ('msg', c_char_p),
]
netsnmp_log_message_p = POINTER(netsnmp_log_message)
log_callback = CFUNCTYPE(
        c_int, c_int,
        netsnmp_log_message_p,
        c_void_p
)

# Provide the standard timeval struct
class timeval(Structure):
    _fields_ = [
        ('tv_sec', c_long),
        ('tv_usec', c_long),
        ]

# The normal fd_set types and sizes
fd_mask = c_ulong
fd_set_p = POINTER(fd_mask)

FD_SETSIZE = 1024
NFDBITS = 8 * sizeof(fd_mask)

fd_set = fd_mask * (FD_SETSIZE // NFDBITS)

oid = c_long
u_char_p = c_char_p
u_char = c_ubyte
c_int_p = POINTER(c_int)

class tree(Structure): pass
class enum_list(Structure): pass
class netsnmp_session(Structure): pass
class netsnmp_transport(Structure): pass
class netsnmp_pdu(Structure): pass
class netsnmp_variable_list(Structure): pass

lib_ctype_registration = {

    # ( ARG, RES )

    # net-snmp/pdu_api.h
    'snmp_pdu_create':  ( [c_int],                  POINTER(netsnmp_pdu) ),
    'snmp_free_pdu':    ( [POINTER(netsnmp_pdu)],   None ),
    
    # net-snmp/varbind_api.h
    'snmp_add_null_var':  ( [POINTER(netsnmp_pdu), POINTER(oid), c_size_t],   POINTER(netsnmp_variable_list) ),

    # net-snmp/session_api.h
    'snmp_sess_open':       ( [POINTER(netsnmp_session)],   c_void_p ),
    'snmp_sess_close':      ( [c_void_p],                   c_int ),
    'snmp_sess_session':    ( [c_void_p],                   POINTER(netsnmp_session) ),
    'snmp_sess_transport':  ( [c_void_p],                   POINTER(netsnmp_transport) ),
    'snmp_sess_select_info': ( [c_void_p, c_int_p, fd_set_p, POINTER(timeval), c_int_p],    c_int ),
    'snmp_sess_timeout':    ( [c_void_p],                   None ),
    'snmp_sess_send':       ( [c_void_p, POINTER(netsnmp_pdu)],     c_int ),
    'snmp_sess_read':       ( [c_void_p, fd_set_p],         c_int ),
    'snmp_errstring':       ( [c_int],                      c_char_p ),
    
    
    # net-snmp/mib_api.h
    'netsnmp_init_mib':     ( [],                           None ),
    'init_mib_internals':   ( [],                           None ),
    'netsnmp_read_module':  ( [c_char_p],                   POINTER(tree) ),
    'get_module_node':      ( [c_char_p, c_char_p, POINTER(oid), POINTER(c_size_t)], c_int ),
    'netsnmp_get_mib_directory': ( [],                      c_char_p ),
    'shutdown_mib':         ( [],                           None ),
    
    # net-snmp/library/parse.h
    'which_module':         ( [c_char_p],                   c_int ),

    # net-snmp/library/mib.h
    'get_tree_head':        ( [],                           POINTER(tree) ),
    'get_tree':             ( [POINTER(oid), c_size_t, POINTER(tree)],  POINTER(tree) ),
    'snprint_octet_string': ( [
            c_char_p,   # buf
            c_size_t,   # buf_len
            POINTER(netsnmp_variable_list),
            c_void_p,   # enum_list
            c_char_p,   # hint
            c_char_p,   # units
            ],
        c_int ),

}

NETSNMP_DS_LIBRARY_ID = 0
NETSNMP_DS_LIB_MIBDIRS = 11

## Data structures and other random types ##

reference = [('reference', c_char_p)]
tree._fields_ = [
    ('child_list', POINTER(tree)),
    ('next_peer', POINTER(tree)),
    ('next', POINTER(tree)),
    ('parent', POINTER(tree)),
    ('label', c_char_p),
    ('subid', c_int),
    ('modid', c_int),
    ('number_modules', c_int),
    ('module_list', c_int_p),
    ('tc_index', c_int),
    ('type', c_int),
    ('access', c_int),
    ('status', c_int),
    ('enums', POINTER(enum_list)),
    ('ranges', c_void_p),
    ('indexes', c_void_p),
    ('arguments', c_char_p),
    ('varbinds', c_void_p),
    ('hint', c_char_p),
    ('units', c_char_p),
    ('printomat', c_void_p),
    ('printer', c_void_p),
    ('description', c_char_p),
    ] + reference + [
    ('reported', c_int),
    ('defaultValue', c_char_p),
    ]

enum_list._fields_ = [
        ('next', POINTER(enum_list)),
        ('value', c_int),
        ('label', c_char_p),
        ]

authenticator = CFUNCTYPE(c_char_p, c_int_p, c_char_p, c_int)

# Event callback
netsnmp_callback = CFUNCTYPE(c_int,
                             c_int, POINTER(netsnmp_session),
                             c_int, POINTER(netsnmp_pdu),
                             c_void_p)

localname = [('localname', c_char_p)]
paramname = [('paramName', c_char_p)]
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
        ('securityAuthKey', u_char * USM_AUTH_KU_LEN),
        ('securityAuthKeyLen', c_size_t),
        ('securityAuthLocalKey', c_char_p),
        ('securityAuthLocalKeyLen', c_size_t),

        ('securityPrivProto', POINTER(oid)),
        ('securityPrivProtoLen', c_size_t),
        ('securityPrivKey', c_char * USM_PRIV_KU_LEN),
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

tmStateRef = [('tmStateRef', c_void_p)]

netsnmp_transport._fields_ = [
        ('domain', POINTER(oid)),
        ('domain_length', c_int),
        ('local', u_char_p),
        ('local_length', c_int),
        ('remote', u_char_p),
        ('remote_length', c_int),
        ('sock', c_int),
        ('flags', c_uint),
        ('data', c_void_p),
        ('data_length', c_int),
        ('msgMaxSize', c_size_t),
        ] + tmStateRef + [
        ('f_recv', c_void_p),
        ('f_send', c_void_p),
        ('f_close', c_void_p),
        ('f_accept',  c_void_p),
        ('f_fmtaddr', c_void_p),
]


NAME_CACHE = {}


class OID(tuple):
    lib = None
    def __new__(cls, netsnmplib, seq, length=None ):
        # print "%s %s"  % ( netsnmplib, seq )
        if isinstance(seq, OID):
            return seq
        elif isinstance(seq, basestring):
            try:
                seq = [int(v) for v in seq.strip('.').split('.')]
            except ValueError:
                buf_len = c_size_t(MAX_OID_LEN)
                buf = (oid * MAX_OID_LEN)()
                if ':' in seq:
                    module, seq = seq.split(':', 1)
                    if seq.startswith(':'):
                        seq = string[1:]
                    netsnmplib.netsnmp_read_module(module)
                    if netsnmplib.which_module(module) == -1:
                        # raise Exception, "Cannot find module %s" % module
                        # logging.error('could not find module %s, trying with all'%(module,))
                        module = "ANY"
                else:
                    module = "ANY"
                if netsnmplib.get_module_node(seq, module, buf, byref(buf_len)) == 0:
                    if module == "ANY":
                        raise Exception, "Cannot translate name '%s' to OID" % seq
                    else:
                        raise Exception, "Cannot find node %s in %s" % (seq, module)
                seq = [buf[i] for i in xrange(buf_len.value)]
        else:
            if length is not None:
                seq = [seq[i] for i in xrange(length)]
            try:
                seq = [int(v) for v in seq]
            except (ValueError, TypeError):
                raise Exception, 'could not translate %s to OID' % str(seq)

        self = super(OID, cls).__new__( cls, seq)
        self.raw = (oid * len(self))()
        self.lib = netsnmplib
        for i, v in enumerate(self):
            self.raw[i] = v

        return self

    def __str__(self):
        return ".%s" % ".".join(str(i) for i in self)

    def __repr__(self):
        return "<OID %r>" % list(self)

    def _tree(self):
        return self.lib.get_tree(self.raw, len(self), self.lib.get_tree_head())

    def hint(self):
        tree = self._tree()
        if tree:
            # logging.debug("hint: %s" % (tree.contents.hint))
            return tree.contents.hint
        return None

    def decode( self ):
        """ returns the nearest match name with iid """
        cbuff = create_string_buffer('', SPRINT_MAX_LEN )
        length = c_size_t(len(cbuff))
        try:
            n = self.lib.snprint_objid(cbuff, byref(length), self.raw, len(self))
            if n:
                # logging.debug("    raw1> %s" % (cbuff[:n],))
                m, f = cbuff[:n].split('::')
                # logging.debug("    raw2> %s\t%s" % (m,f))
                f, tmp, iid = f.partition('.')
                # logging.debug("    out> %s\t%s\t%s" % (m,f,iid))
                # deal with non-numbers in the iid
                if iid.startswith("'"):
                    # FIXME: can't seem to be able to translate the raw bytes from teh iid into something useable
                    # ie,
                    # for i in iid[1:-1]:
                    #     v = '%x' % (struct.unpack('B',i))
                    # so we do this the long way, and determinen the f's oid and do a replace to determine the oid
                    o = self.name_to_oid( f )
                    iid = str(self).replace( str(o)+'.','' )
                    # logging.debug("    oid for %s: %s\t-> %s" % (o, self, iid) )
                return m, f, iid
        except Exception,e:
            logging.debug("  error decoding oid %s:\t%s" % (cbuff[:n],e,))
        return None, None, None

    def enums(self):
        """
        Used for converting integers to more useful string values.
        """
        tree = self._tree()
        mapping = {}
        enum = tree.contents.enums
        # logging.debug("    tree: %s\t%s" % (tree, tree.contents.enums) )
        while enum:
            # logging.debug("        enum: %s\t%s" % (enum.contents.label, enum.contents.value))
            mapping[enum.contents.value] = enum.contents.label
            enum = enum.contents.next
        # logging.debug("      out: %s" % (mapping))
        return mapping

    def name_to_oid( self, s ):
        """ convert a string to oid object """
        if isinstance( s, basestring ):
            if s in NAME_CACHE:
                return NAME_CACHE[s]
            if s[:2] == '.1': # 'iso' + s[2:]
                return map(int, filter (None, s.split ('.')))
            else:
                o = (c_long*MAX_OID_LEN)()
                l = c_size_t(len(o))
                r = self.lib.get_node( s, o, byref(l) )
                # logging.debug(" _name_to_oid: " + str(s) + ", r: " + str(r) + ", oid: " + str([ str(i) for i in oid]))
                NAME_CACHE[s] = OID(self.lib,o[:l.value]) if r else None
                return NAME_CACHE[s]
        return None


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



def _decode_objid(lib, objid, var):
    length = var.val_len / sizeof(oid)
    o = OID(lib, var.val.objid, length=length)
    e = o.enums()
    # logging.debug(" decoding objid %s, var %s (%s): %s" % (objid, var.val.objid, o, e) )
    return o
    
def _decode_ip(lib, objid, var):
    return '.'.join(map(str, var.val.bitstring[:4]))

def _decode_counter64(lib, objid, var):
    int64 = var.val.counter64.contents
    return (int64.high << 32L) + int64.low

def _decode_raw_string(lib, objid, var):
    # logging.debug(" decoding raw string")
    return string_at(var.val.bitstring, var.val_len)

def _decode_string(lib, objid, var):
    hint = objid.hint()
    # logging.debug(" decoding string: " + str(hint))
    if hint:
        buf_len = 260
        buf = create_string_buffer(buf_len)
        ret = lib.snprint_octet_string(buf, buf_len, byref(var), None, hint, None)
        # logging.debug( "  buf: %s (%d), var: %s, ret=%d" % (buf.value, buf_len, var, ret))
        if ret == -1:
            return _decode_raw_string(lib, objid, var)
        else:
            return str(buf.value)
    else:
        return _decode_raw_string(lib, objid, var)
    


_decoder = {
    ASN_OCTET_STR:    _decode_string,
    ASN_BOOLEAN:      lambda lib, id, var: var.val.integer.contents.value,
    ASN_INTEGER:      lambda lib, id, var: var.val.integer.contents.value,
    ASN_NULL:         lambda lib, id, var: None,
    ASN_OBJECT_ID:    _decode_objid,
    ASN_BIT_STR:      _decode_raw_string,
    ASN_IPADDRESS:    _decode_ip,
    ASN_COUNTER:      lambda lib, id, var: var.val.uinteger.contents.value,
    ASN_GAUGE:        lambda lib, id, var: var.val.uinteger.contents.value,
    ASN_TIMETICKS:    lambda lib, id, var: var.val.uinteger.contents.value,
    ASN_COUNTER64:    _decode_counter64,
    ASN_APP_FLOAT:    lambda lib, id, var: var.val.float.contents.value,
    ASN_APP_DOUBLE:   lambda lib, id, var: var.val.double.contents.value,

    # Errors
    SNMP_NOSUCHOBJECT:    lambda lib, id, var: NoSuchObject(),
    SNMP_NOSUCHINSTANCE:  lambda lib, id, var: NoSuchInstance(),
    SNMP_ENDOFMIBVIEW:    lambda lib, id, var: EndOfMibView(),
}


# keep a cache of enums

def _decode_variable(lib, objid, var):
    if var.type not in _decoder:
        raise Exception("decoding of vartype %d not implemented" % var.type)
    # logging.debug(" decoding " + str(var.type))
    return _decoder[var.type](lib, objid, var)
    

# caches for various frequently used lookups
OID_CACHE = {}
MAPPING_ENUM_CACHE = {}

class NetSNMP( Agent ):

    default_options = {
        'community': 'public',
        'timeout': 5,
        'retries': 2,
        'version': '2c',
        'port': 161,
        'mib_dir': [],
        'mibs': [],
    }

    lib = None

    max_repeaters = 100
    _netsnmp_logger_callback = None
    last_err = ''

    def __init__(self, **options ):
        self.sessp = None   # single session api pointer
        self.session = None # session struct

        self.lib = self.init_netsnmp()
        self._init_netsnmp()
        
        # TODO: netsnmp log handling doesn't seem to work; can't get paste log_callback with > 72 multiprocess instances
        # logging.warn("+ agent init")
        # register log handler callbacks
        # self._netsnmp_logger_callback = log_callback(self._netsnmp_logger)
        # logging.warn("+ agent log callback")
        # self.lib.snmp_register_callback(
        #         SNMP_CALLBACK_LIBRARY,
        #         SNMP_CALLBACK_LOGGING,
        #         self._netsnmp_logger_callback,
        #         0
        # )
        # self._log_handler = self.lib.netsnmp_register_loghandler( NETSNMP_LOGHANDLER_CALLBACK, LOG_WARNING )

        # logging.warn("+ agent add mibdir")
        self.add_mibdir( '/opt/ptolemy/etc/ptolemy/polld/snmp_mibs/' )
        # if 'mib_dirs' in options:
        #         if isinstance( options['mib_dirs'], list ):
        #             for d in options['mib_dirs']:
        #                 self.add_mibdir( d )
    
        # initilise mibs
        self.lib.init_mib()

    ## Set library arg and return types ##
    def init_netsnmp(self):
        lib = None
        try:
            lib = CDLL("libnetsnmp.so", RTLD_GLOBAL)
        except OSError:
            from ctypes.util import find_library
            lib = CDLL(find_library("netsnmp"), RTLD_GLOBAL)
        except Exception,e:
            raise Exception, 'could not initiate net-snmp'
        return lib

    def _init_netsnmp(self):
        # net-snmp/version.h
        self.lib.netsnmp_get_version.argtypes = []
        self.lib.netsnmp_get_version.restype = c_char_p
        lib_version = self.lib.netsnmp_get_version()
        lib_version_info = tuple(int(x) for x in lib_version.split('.'))
        if lib_version_info < (5,5):
            raise ImportError("netsnmp version 5.5 or greater is required")

        # register all ctypes for netsnmp
        for k,v in lib_ctype_registration.iteritems():
            f = getattr( self.lib, k )
            f.argtypes = v[0]
            f.restype = v[1]

        # This removes the STRING: prefix when using snprint_octet_string
        self.lib.netsnmp_ds_set_boolean(0, 13, 1)
        
    # add all mibs
    def get_mibdirs(self):
        return self.lib.netsnmp_get_mib_directory().split(':')

    def add_mibdir( self,path ):
        cur = self.get_mibdirs()
        # logging.debug("current: " + str(cur) + ", new '" + str(path) + "'")
        # don't bother if we already have it
        if not path in cur:
            dirs = ":".join(cur) + ':' + str(path)
            self.lib.netsnmp_ds_set_string(
                    NETSNMP_DS_LIBRARY_ID,
                    NETSNMP_DS_LIB_MIBDIRS,
                    dirs
            )
            return True
        return False

    def add_mib_module(self,module):
        # logging.debug('  reading mib: ' + str(module))
        self.lib.netsnmp_read_module(module)
        if self.lib.which_module(module) == -1:
            raise Exception, "Cannot find module %s" % module

    def __del__(self):
        # if we try to clean up, it prevents other processes from starting
        # self.lib.shutdown_mib()
        s = ' ' * 255
        cbuff = create_string_buffer(s, len(s))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.lib.snmp_sess_close(self.sessp)
        self.sessp = None
        self.session = None
        # self._session_callback = None

    def _netsnmp_logger( self, a, b, msg ):
        msg = cast( msg, netsnmp_log_message_p )
        priority = LOG_PRIORITY_MAP[ msg.contents.priority ]
        self.last_err = msg.contents.msg.strip()
        f = getattr( logging, priority )
        f( self.last_err )
        # important! callback require int return
        return 0

    def get_error(self, session):
        errno = None
        if hasattr(session, 'contents'):
            if bool(session):
                errno = session.contents.s_snmp_errno
            else:
                errno = session.s_snmp_errno
            if session is not None:
                r = self.lib.snmp_api_errstring(errno)
        if errno is None:
            errno = c_int.in_dll(self.lib, 'snmp_errno').value
            r = self.lib.snmp_errstring(errno)
        return r

    def get_session( self, host, **options ):
        # Initialize session to default values
        session_template = netsnmp_session()
        self.lib.snmp_sess_init(byref(session_template))

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

        # logging.error("SNMP: timeout=%s, retries=%s" % (kwargs['timeout'],kwargs['retries']))
        for k,v in kwargs.iteritems():
            setattr(session_template, k,v)
        return session_template

    def fetch( self, host, oids, method='bulkwalk', **kwargs ):
        self.sessp = self.lib.snmp_sess_open(byref(self.get_session( host, **kwargs )))
        if not self.sessp:
            raise Exception, '%s' % (self.last_err,)
        self.session = self.lib.snmp_sess_session(self.sessp)

        # this may be bad: netsnmp mib handling isn't thread safe?
        if 'mibs' in kwargs and isinstance( kwargs['mibs'], list ):
            for m in kwargs['mibs']:
                self.add_mib_module( m )
    
        m = 'fetch_by_' + str(method)
        try:
            f = getattr(self, m)
            return f( oids )
        except AttributeError:
            raise Exception, 'unknown fetch method ' + str(method)


    def fetch_by_bulkwalk( self, oids, close_match=False ):
        """
        do a bulk fetch for each oid defined
        """
        for name in oids:

            this_f = name
            this_oid = OID(self.lib,name)
            m, wanted_f, iid = this_oid.decode()
            if iid == '':
                iid = 0

            while this_f == name:

                # logging.warn("  fetch_by_bulkwalk: %s, iid: %s (oid: %s)" % (name, iid, this_oid))
                req = self.lib.snmp_pdu_create(SNMP_MSG_GETBULK)
                req.contents.errstat = 0
                req.contents.errindex = self.max_repeaters
                self.lib.snmp_add_null_var(req, this_oid.raw, len(this_oid))

                # logging.error("    %r: %s" % (self.sessp,self.sessp))
                response = POINTER(netsnmp_pdu)()
                r = self.lib.snmp_sess_synch_response(self.sessp, req, byref(response))
                if r:
                    err = self.get_error(self.sessp)
                    # logging.error("  SNMP ERROR: %s %s" % (r, err))
                    raise Exception, "snmp_sess_synch_response (%s): %s" % ( r,err )

                # spit out only wanted oids
                for o,v in self._parse(response.contents):
                    m, this_f, iid = o.decode()
                    # logging.debug("  looking for %s: %s\t%s\t%s" % (wanted_f,m,this_f,iid) )
                    ok = this_f == wanted_f
                    if not ok and close_match:
                        if this_f.startswith( wanted_f ):
                            ok = True
                    # if this_f == wanted_f:
                    if ok:
                        if not this_f in MAPPING_ENUM_CACHE:
                            MAPPING_ENUM_CACHE[this_f] = o.enums()
                        if v in MAPPING_ENUM_CACHE[this_f]:
                            v = MAPPING_ENUM_CACHE[this_f][v]
                        this_oid = o    # set up for next poll sequence from this field
                        if v == '':
                            v = None
                        logging.debug("  got: %s\t%s\t(%s)\t%s" % (this_f,iid,o,v) )
                        if close_match and not this_f == wanted_f:
                            this_f = wanted_f
                        yield this_f,iid,v
            
                self.lib.snmp_free_pdu(response)

        return
        

    def _parse( self, pdu ):
        err_index = None
        if pdu.errstat != SNMP_ERR_NOERROR:
            err_index = pdu.errindex
        var = pdu.variables
        while var:
            var = var.contents
            o = OID(self.lib, var.name, length=var.name_length)
            # logging.debug(" var %r (%s)\toid: %r" % (var.name,var.name_length,o) )
            if err_index is None:
                yield o, _decode_variable(self.lib, o, var)
            var = var.next_variable

        return



class NetConfig( Agent ):
    """
    Agent class to interact with netconfig
    """
    
    proxy = None
    
    def __init__(self, netconfig_config=None, **kwargs ):
        logging.debug('setup netconfig worker %s' %(kwargs,))
        if not 'netconfig_config':
            raise SyntaxError, 'netconfig configuration file not defined'
        self.netconfig_config = netconfig_config
        self.proxy = None
        self.kwargs = kwargs
        
    def __enter__(self):
        # connect to host
        c = config_file( self.netconfig_config )
        logging.debug('net-config: %s' % (c,))
        self.nc = NetConfigAgent( c )
        return self
        
    def __exit__(self, *args, **kwargs):
        # disconnect from host
        if self.proxy:
            self.proxy.disconnect()
        self.proxy = None
        
    def fetch( self, host, varlist, **kwargs ):
        self.proxy = self.nc.get( host )
        # logging.error("NETCONFIG FETCH %s %s" % (host,varlist))
        if self.proxy.connect():
            # no term buffer
            self.proxy.prompt.terminal_buffer(0)
            for var in varlist:
                try:
                    # logging.debug( "kwargs: %s" % (kwargs,) )
                    c = self.proxy.get_component( var )
                    for i,v in c():
                        yield var,i,v
                except Exception,e:
                    raise Exception, 'net-config error: (%s) %s' % ( type(e),e )
        return


class CommandLine( Agent ):
    """ generically, runs a command line """
    
    host = None
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args, **kwargs):
        return

    def fetch( self, host, varlist=[], **kwargs ):
        data = self.run( host, varlist, **kwargs)
        for var in varlist:
            if var in data:
                yield var,self.__class__.__name__,data[var]
        return

    def commandline( self, host, varlist=[], **kwargs ):
        raise NotImplementedError

    def run( self, host, varlist=[], **kwargs ):
        cmdline = self.commandline( host, varlist, **kwargs )
        # logging.info("running command: %s"%(cmdline,))
        cmd = subprocess.Popen( cmdline,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT )
        out, error = cmd.communicate()
        if not out == None:
            out = out.split('\n')
        if not error == None:
            error = error.split('\n')
        # logging.info("got: %s, %s"%(out,error))
        data = {}
        for k,v in self.parse( out, error ):
            data[k] = v
        return data
        
    def parse( self, output, error ):
        for o in output:
            for r in self.match:
                m = search( self.match[r], o )
                # logging.info("match: %s %s = %s" % (r,o,m) )
                if m:
                    for k,v in m.groupdict().iteritems():
                        # logging.debug("  yielding: %s %s" % (k, v))
                        yield k, v
        return

class Ping( CommandLine ):
    """
    Agent class to ping a given host
    """
    match = {
        'linux-loss': r'(?P<sent>\d+) packets transmitted, (?P<received>\d+) received, (?P<loss>\d+)\% packet loss,',
        'linux-rtt': r' min/avg/max/mdev = (?P<min_rtt>\d+.\d+)/(?P<avg_rtt>\d+.\d+)/(?P<max_rtt>\d+.\d+)/(?P<stddev>\d+.\d+) ms',
    }
    
    def commandline( self, host, varlist, **kwargs ):
        # logging.error("IN: %s, %s, %s" % (host, varlist, kwargs))
        return "ping -c 3 -i 0.2 -w 2 %s " % host


class NMap( CommandLine ):
    """
    run a nmap single port scan
    """
    match = {
        'port': r'^(?P<port>\d+)/(?P<protocol>\w+) (?P<state>\w+) (?P<service>.*)\s*$',
        'latency': r'^Host is up \((?P<rtt>\d+.\d+)s latency\)',
        'time': r' scanned in (?P<duration>\d+.\d+) seconds',
    }
    
    def commandline( self, host, varlist, **kwargs ):
        return "nmap -sT -p %s %s " % ( kwargs['port'], host )
    
