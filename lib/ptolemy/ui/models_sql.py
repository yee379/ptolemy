from django.db import models

import logging


class Device( models.Model ):

    class Meta:
        db_table = 'node_entities_aggregate'
        managed = False

    id = models.IntegerField( primary_key=True, db_column='node_id' )
    name = models.CharField(max_length=127, db_column='node' )
    software_version = models.CharField(max_length=127)
    serial = models.CharField(max_length=127)
    model = models.CharField(max_length=127)
    location = models.CharField(max_length=127)
    vendor = models.CharField(max_length=127)
    vlan = models.CharField(max_length=255)
    kind = models.CharField(max_length=127)
    category = models.CharField(max_length=127)
    uptime = models.CharField(max_length=64)
    last_seen = models.DateTimeField()
    # 
    # def vlans(self):
    #     return self.vlan.split(',')

    def _locations( self ):
        self._loc = {}
        for i in self.location.split(','):
            j = i.strip()
            # logging.error("J: " + str(len(j)) + ", " + str(j))
            l = j.split('=')
            # logging.error("  L: " + str(len(l)) + ", " + str(l))
            if len(l) == 2:
                self._loc[l[0]] = l[1]
        return self._loc
        
    def building( self ):
        loc = self._locations()
        # logging.error("BUILDING " + str(loc))
        if 'building' in loc:
            return loc['building']
        return None
        
    def __str__(self):
        return self.name + ', serial ' + self.serial
        

class Entity( models.Model ):
    
    id = models.IntegerField( primary_key=True, db_column='_id' )
    # device_name = models.CharField(max_length=127, db_column='node' )
    device = models.ForeignKey(Device, db_column='node_id' )

    type = models.CharField(max_length=127, db_column='type' )
    vendor = models.CharField(max_length=127)
    model = models.CharField(max_length=127)
    description = models.CharField(max_length=255)

    admin_status = models.CharField(max_length=255)
    operational_status = models.CharField(max_length=255)

    serial = models.CharField(max_length=127)

    # slot_number = models.IntegerField(max_length=11)
    hardware_version = models.CharField(max_length=255)
    software_version = models.CharField(max_length=255)
    firmware_version = models.CharField(max_length=255)

    number_of_ports = models.IntegerField(max_length=11)

    last_seen = models.DateTimeField()
    class Meta:
        db_table = 'entities_on_node'
        managed = False


class StatusMixin(object):
    def status(self):
        if self.operational_status == 1 and self.admin_status == 1:
            return 'connected'
        elif self.operational_status == 0 and self.admin_status == 1:
            return 'notconnected'
        return 'disabled'

class AutoNegMixin(object):
    def autoneg(self):
        if self.speed_admin == 'auto' or self.duplex_admin == 'auto':
            return True
        return False

def numeric_compare(x,y):
    return int(x) - int(y)

class VlanMixin(object):
    def vlans(self):
        return sorted( self.vlan.split(','), cmp=numeric_compare )


class PortStrMixin(object):
    def __str__(self):
        return self.physical_port + ", " + str(self.admin_status) + ", " + str(self.alias) + ", " + str(self.vlan)


class Subnet( models.Model ):
    class Meta:
        db_table = 'l3_subnet'
        managed = False
    id = models.IntegerField(max_length=20, db_column='_id', primary_key=True)
    prefix = models.CharField(max_length=127)
    prefix_length = models.IntegerField(max_length=11)
    name = models.CharField(max_length=255)



class Port( models.Model, StatusMixin, AutoNegMixin, PortStrMixin, VlanMixin ):
    class Meta:
        db_table = 'Port'
        managed = False
    id = models.IntegerField(max_length=20, db_column='_id', primary_key=True)
    # l2_id = models.IntegerField(max_length=11)

    # Device = models.ForeignKey( Device, db_column='node_id' )
    device_id = models.IntegerField(max_length=20, db_column='node_id')
    physical_port = models.CharField(max_length=255)
    if_index = models.IntegerField(max_length=11)

    alias = models.CharField(max_length=255, db_column='alias')

    admin_status = models.IntegerField(max_length=1)
    operational_status = models.IntegerField(max_length=1)

    vlan = models.CharField(max_length=255,db_column='vlans')

    speed = models.IntegerField(max_length=11)
    speed_admin = models.CharField(max_length=255)
    duplex = models.CharField(max_length=255)
    duplex_admin = models.CharField(max_length=255)
    
    is_port_fast = models.IntegerField(max_length=1, db_column='is_port_fast')
    is_virtual = models.IntegerField(max_length=1, db_column='is_virtual')
    is_trunking = models.IntegerField(max_length=1, db_column='is_trunking')
    
    last_seen = models.DateTimeField()


class PortWithPeer( models.Model, StatusMixin, AutoNegMixin, PortStrMixin, VlanMixin ):
    class Meta:
        db_table = 'PortWithPeer'
        managed = False
    id = models.IntegerField(max_length=20, db_column='_id', primary_key=True)
    # l2_id = models.IntegerField(max_length=11)

    # Device = models.ForeignKey( Device, db_column='node_id' )
    device_id = models.IntegerField(max_length=20, db_column='node_id')
    physical_port = models.CharField(max_length=255)
    if_index = models.IntegerField(max_length=11)

    alias = models.CharField(max_length=255, db_column='alias')

    admin_status = models.IntegerField(max_length=1)
    operational_status = models.IntegerField(max_length=1)

    hostname = models.CharField(max_length=255, db_column='hostname')
    mac_address  = models.CharField(max_length=255, db_column='mac_address' )
    ip_address = models.CharField(max_length=255, db_column='ip_address')

    vlan = models.CharField(max_length=255,db_column='vlans')

    speed = models.IntegerField(max_length=11)
    speed_admin = models.CharField(max_length=255)
    duplex = models.CharField(max_length=255)
    duplex_admin = models.CharField(max_length=255)
    
    is_port_fast = models.IntegerField(max_length=1, db_column='is_port_fast')
    is_virtual = models.IntegerField(max_length=1, db_column='is_virtual')
    is_trunking = models.IntegerField(max_length=1, db_column='is_trunking')
    
    last_seen = models.DateTimeField()


class Host( models.Model ):
    class Meta:
        db_table = 'Host'
        managed = False
    id = models.IntegerField(max_length=20, db_column='_id', primary_key=True)

    hostname = models.CharField(max_length=255, db_column='hostname')
    mac_address  = models.CharField(max_length=255, db_column='mac_address' )
    ip_address = models.CharField(max_length=255, db_column='ip_address')
    
    user = models.CharField( max_length=255, db_column='user')
    admin = models.CharField( max_length=255, db_column='administrator')

    Device = models.ForeignKey( Device, db_column='node_id')
    Port = models.ForeignKey( Port, db_column='l1_interface_id' )
    Subnet = models.ForeignKey(Subnet, db_column='subnet')

    last_seen = models.DateTimeField()


class Peer( models.Model ):
    class Meta:
        db_table = 'Peer'
        managed = False
    id = models.IntegerField(max_length=20, db_column='_id', primary_key=True)
    src = models.ForeignKey(Device, db_column='src_node_id', related_name="src" )
    src_port_id = models.IntegerField(max_length=20, db_column='src_l1_interface_id')
    src_port = models.ForeignKey(Port, db_column='src_l1_interface_id', related_name="src_port" )
    dst = models.ForeignKey(Device, db_column='dst_node_id', related_name="dst" )
    dst_port_id = models.IntegerField(max_length=20, db_column='dst_l1_interface_id')
    dst_port = models.ForeignKey(Port, db_column='dst_l1_interface_id', related_name="dst_port" )

    last_seen = models.DateTimeField(db_column='src_last_seen')

class L1InterfaceArchive( models.Model ):
    class Meta:
        db_table = 'arch_l1_interface'
        managed = False
        
    id = models.IntegerField(max_length=20, db_column='_id', primary_key=True)
    operational_status = models.IntegerField(max_length=1)
    last_seen = models.DateTimeField()





class HostsOnSubnet( models.Model ):
    class Meta:
        db_table = 'hosts_on_subnet'
        managed = False
    # id = models.IntegerField(max_length=20, primary_key=True)
    device = models.CharField( max_length=127, db_column='device' )
    subnet_name = models.CharField( max_length=255, db_column='subnet_name')
    vlan = models.IntegerField( max_length=11, db_column='vlan')
    hostname = models.CharField( max_length=255, db_column='hostname', primary_key=True)
    ip_address = models.CharField( max_length=255, db_column='ip_address')
    admin_status = models.IntegerField(max_length=1, db_column='adm_status')
    op_status = models.IntegerField(max_length=1, db_column='op_status')