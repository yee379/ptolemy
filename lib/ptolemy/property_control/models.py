from django.db import models

from datetime import datetime, date, time


# select doe,mfg_ser from dpf_lookup where mfg_ser='"+serial+"'"
# select d.device_name, p.property_control_num, p.hardware_serial_num 
#     from devices d, hardware_purchases p, hardware_configuration d2p 
#     where d.device_id=d2p.device_id and d2p.hardware_id=p.hardware_id and d.device_name like '"+host+"%'";
# select d.device_name, p.property_control_num, p.hardware_serial_num 
#     from devices d, hardware_purchases p, hardware_configuration d2p 
#     where d.device_id=d2p.device_id and d2p.hardware_id=p.hardware_id and (p.property_control_num like '"+host+"%' OR p.hardware_serial_num like '"+host+"%')";


class Item(models.Model):
    class Meta:
        db_table = u'DPF_LOOKUP'
        managed = False

    pc_number = models.CharField( primary_key=True, max_length=22, db_column='doe' )
    type = models.CharField( max_length=30, db_column='ITEM_NAME' )
    manufacturer = models.CharField( max_length=30, db_column='MFGR' )
    model = models.CharField( max_length=30, db_column='MODEL' )
    serial = models.CharField(max_length=40, db_column='mfg_ser')
    _date = models.CharField( max_length=5, db_column='DATE_RECVD' )
    contact = models.CharField( max_length=30, db_column='CONTACT' )
    group = models.CharField( max_length=10, db_column='USING_GROUP' )

    def date(self):
        m, _tmp, y = self._date.partition('/')
        m = int(m)
        y = int(y)
        if y > 70:
            y = 1900 + y
        else:
            y = 2000 + y
        return datetime.combine( date( y, m, 1 ), time() )

    def __str__(self):
        return '<Item %s: %s %s\t%s\t%s>' % ( self.pc_number, self.manufacturer, self.model, self.serial, self.date() )

    
class Device( models.Model ):
    class Meta:
        db_table = u'DEVICES'
        managed = False
        
    id = models.IntegerField( primary_key=True, max_length=6, db_column='device_id' )
    name = models.CharField( max_length=40, db_column='device_name' )

    def __str__(self):
        return '<Device id=%s name=%s>' % ( self.id, self.name  )

class Product( models.Model ):
    class Meta:
        db_table = u'HARDWARE_PRODUCT_TYPES'
        managed = False
    
    id = models.IntegerField( primary_key=True, max_length=6, db_column="hardware_prod_id" )
    type = models.CharField( max_length=10, db_column='device_type' )
    
    def __str__(self):
        return '<Product id=%s type=%s>' % ( self.id, self.type )


class Purchase( models.Model ):
    class Meta:
        db_table = u'HARDWARE_PURCHASES'
        managed = False

    number = models.CharField( primary_key=True, max_length=8, db_column='property_control_num')
    serial = models.CharField( max_length=30, db_column='hardware_serial_num')
    # hw = models.IntegerField( max_length=6, db_column='hardware_id' )
    product = models.ForeignKey( Product, max_length=6, db_column='hardware_prod_id' )
    date = models.DateField( db_column='upd_date' )

    def __str__(self):
        return '<Purchase pc_number=%s\tserial=%s\tproduct=%s\tdate=%s>' % ( self.number, self.serial, self.product, self.date )


class Property(models.Model):

    class Meta:
        db_table = u'HARDWARE_CONFIGURATION'
        managed = False
    device = models.ForeignKey( Device, db_column='device_id' )
    item = models.ForeignKey( Purchase, db_column='hardware_id' )
    first_seen = models.DateField( db_column='date_assigned' )
    id = models.IntegerField( primary_key=True, max_length=6, db_column='person_id' )

    def __str__(self):
        return '<Property device=%s item=%s>' % ( self.device, self.purchase )

# 
# 
# OWNER                TABLE_NAME
# ------------------------------ ------------------------------
# NETGROUP             ASK_4MAIL
# NETGROUP             ASK_4MAIL_TEMP
# NETGROUP             AT_NODE
# NETGROUP             AT_ZONES
# NETGROUP             BIT_NODE
# NETGROUP             BOOTP_PORTS
# NETGROUP             BRIDGE_DUMP_INFO
# NETGROUP             BUILDINGS
# NETGROUP             CABLES
# NETGROUP             CABLE_TYPES
# NETGROUP             CATALYST_CONFIG
# NETGROUP             CISCO_DUMP_INFO
# NETGROUP             CONNECTORS
# NETGROUP             CONNECTOR_TYPES
# NETGROUP             CONN_TO_TAP
# NETGROUP             CONTRACTS
# NETGROUP             DEC_NODE
# NETGROUP             DEC_NODES_CHECKOFF
# NETGROUP             DEC_NODE_HISTORY
# NETGROUP             DEVICES
# NETGROUP             DEVICES_HISTORY
# NETGROUP             DEVICE_CHARACTERISTICS
# NETGROUP             DEVICE_CONTRACTS
# NETGROUP             DEVICE_DNET_LINK
# NETGROUP             DEVICE_HARDWARE_PORT_MAP
# NETGROUP             DEVICE_MANAGERS
# NETGROUP             DEVICE_MODELS
# NETGROUP             DEVICE_OPSYS
# NETGROUP             DEVICE_PORT
# NETGROUP             DEVICE_RTR_INFO
# NETGROUP             DEVICE_TO_TAP
# NETGROUP             DEVICE_TYPES
# NETGROUP             DEV_MAIL
# NETGROUP             DPF_LOOKUP
# NETGROUP             ENET_ADDR_PORTS
# NETGROUP             EXT_ATOM
# NETGROUP             GIGASWITCH_PORT_MAPPING
# NETGROUP             HARDWARE_CLASS
# NETGROUP             HARDWARE_CONFIGURATION
# NETGROUP             HARDWARE_EXPERTS
# NETGROUP             HARDWARE_PORT
# NETGROUP             HARDWARE_PRODUCTS
 # Name                       Null?    Type
 # ----------------------------------------- -------- ----------------------------
 # HARDWARE_PROD_ID               NOT NULL NUMBER(6)
 # HARDWARE_PROD                   NOT NULL VARCHAR2(40)
 # HARDWARE_CLASS                     NUMBER(6)
 # UPD_DATE                   NOT NULL DATE
 # UPD_USER                   NOT NULL VARCHAR2(20)
 # HARDWARE_PART                        VARCHAR2(30)
# NETGROUP             HARDWARE_PRODUCT_TYPES
 # Name                       Null?    Type
 # ----------------------------------------- -------- ----------------------------
 # HARDWARE_PROD_ID               NOT NULL NUMBER(6)
 # DEVICE_TYPE                   NOT NULL VARCHAR2(10)
# NETGROUP             HARDWARE_PURCHASES
# NETGROUP             HARDWARE_PURCHASES_DEC
# NETGROUP             HARDWARE_TAGS
# NETGROUP             HOME_PHONE_CONFIG
# NETGROUP             INSTITUTIONS
# NETGROUP             INTL_PHONE
# NETGROUP             IPHOST_CHARACTERISTICS
# NETGROUP             IP_ACCESS_TYPE
# NETGROUP             IP_ALIASES
# NETGROUP             IP_CAPABILITY_CLASSES
# NETGROUP             IP_DOMAINS
# NETGROUP             IP_MX_HOSTS
# NETGROUP             IP_NAMESERVERS
# NETGROUP             IP_NODE
# NETGROUP             IP_NODES_CHECKOFF
# NETGROUP             IP_NODE_HISTORY
# NETGROUP             IP_NODE_HISTORY_OLD
# NETGROUP             IP_NODE_OLD
# NETGROUP             IP_SERVICES
# NETGROUP             IP_SOURCE_OF_AUTHORITY
# NETGROUP             IP_SUBNETS
# NETGROUP             IP_WELL_KNOWN_SERVICES
# NETGROUP             ISDN_DEVICES
# NETGROUP             MAILLIST
# NETGROUP             MAIL_SYSTEM
# NETGROUP             MSU_NODES
# NETGROUP             MSU_TOPOLOGY
# NETGROUP             NETS
# NETGROUP             NETWORK_SERVERS
# NETGROUP             NETWORK_SERVICES
# NETGROUP             NETWORK_TAPS
# NETGROUP             NETWORK_TOPOLOGY
# NETGROUP             NET_TYPES
# NETGROUP             NT_DOMAINS
# NETGROUP             NT_NODE_DOMAINS
# NETGROUP             PAGER_ACTIONS
# NETGROUP             PAGER_CONFIG
# NETGROUP             PERSON_ALL_LIST_OLD
# NETGROUP             PERSON_LIST
# NETGROUP             PERSON_NAMES
# NETGROUP             PING_GROUP
# NETGROUP             PING_GROUP_ASSOC
# NETGROUP             PORT_TYPE
# NETGROUP             ROUTER_CONFIG
# NETGROUP             SEGMENTS
# NETGROUP             SEGMENT_CONFIGURATION
# NETGROUP             SEGMENT_TYPES
# NETGROUP             SERVERS_SERVICES
# NETGROUP             SLAC_DIVISIONS
# NETGROUP             SOFTWARE_ACCOUNTS_CHARGED
# NETGROUP             SOFTWARE_CHARGEBACKS
# NETGROUP             SOFTWARE_CLASS
# NETGROUP             SOFTWARE_CONFIGURATION
# NETGROUP             SOFTWARE_CONTRACTS
# NETGROUP             SOFTWARE_EXPERTS
# NETGROUP             SOFTWARE_PRODUCTS
# NETGROUP             SOFTWARE_PRODUCT_TYPES
# NETGROUP             SOFTWARE_PURCHASES
# NETGROUP             SOFTWARE_REQUESTOR
# NETGROUP             SOFTWARE_SUPPORT
# NETGROUP             SWITCH_SEEN
# NETGROUP             TC_BRIDGED_DN
# NETGROUP             TC_COMMON
# NETGROUP             TC_DN_TN
# NETGROUP             TC_LUV
# NETGROUP             TELECOM_STATS
# NETGROUP             TRANSCEIVERS
# NETGROUP             TRANSCEIVER_TYPES
# NETGROUP             VENDOR
# NETGROUP             XCVR_CONFIGURATION
# NETGROUP             SPAM_BLOCK
# NETGROUP             DEVICE_PCNUMBERS
