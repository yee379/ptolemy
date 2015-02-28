from django.db import models

# Create your models here.
from django.db import models


#######################################################################
# network devices
#######################################################################


class Node(models.Model):
    _id = models.AutoField(primary_key=True)
    hardware_id = models.ForeignKey(Hardware, null=True, blank=True)
    location_id = models.ForeignKey(Location, null=True, blank=True)
    name = models.CharField(db_index=True, max_length=127)
    software_version = models.TextField(blank=True)
    serial = models.TextField(db_index=True, blank=True,null=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=127, blank=True)
    category = models.CharField(max_length=127, blank=True)
    uptime = models.CharField(max_length=127, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'node'

class Location(models.Model):
    _id = models.AutoField(primary_key=True)
    description = models.CharField(db_index=True, max_length=127)
    class Meta:
        db_table = u'location'



#######################################################################
# entities
#######################################################################

class Entity(models.Model):
    _id = models.AutoField(primary_key=True)
    hardware_id = models.ForeignKey( Hardware, to_field='_id' )
    serial = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    operational_status = models.CharField(max_length=255, blank=True)
    admin_status = models.CharField(max_length=255, blank=True)
    hardware_version = models.CharField(max_length=255, blank=True)
    firmware_version = models.CharField(max_length=255, blank=True)
    software_version = models.CharField(max_length=255, blank=True)
    last_seen = models.DateTimeField()
    number_of_ports = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'entity'

class Entity2Node(models.Model):
    node_id = models.ForeignKey( Node )
    entity_id = models.ForeignKey( Entity )
    slot_number = models.IntegerField(null=True, blank=True)
    entity_index = models.IntegerField(unique=True, max_length=24)
    parent_entity_index = models.IntegerField(max_length=24, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'entity2node'

class Hardware(models.Model):
    _id = models.AutoField(primary_key=True)
    model = models.CharField(db_index=True,unique=True, max_length=127)
    hardware_type_id = models.ForeignKey(HardwareType, unique=True, null=True, blank=True)
    sysobjectid = models.CharField(max_length=127, db_column='sysObjectID', blank=True) # Field name made lowercase.
    vendor = models.CharField( max_length=127)
    bulletin_no = models.CharField(max_length=127, blank=True)
    end_of_sale = models.DateField(null=True, blank=True)
    end_of_support = models.DateField(null=True, blank=True)
    list_price = models.DecimalField(null=True, max_digits=12, decimal_places=2, blank=True)
    replacement_hardware_id = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'hardware'

class HardwareType(models.Model):
    _id = models.AutoField(primary_key=True)
    name = models.TextField(db_index=True)
    class Meta:
        db_table = u'hardware_type'


class NodeModule(models.Model):
    _id = models.AutoField(unique=True)
    node_id = models.ForeignKey(Node)
    operational_status = models.CharField(max_length=255, blank=True)
    admin_status = models.CharField(max_length=255, blank=True)
    hardware_id = models.ForeignKey(Hardware,null=True, blank=True)
    entity_index = models.CharField(max_length=24, blank=True)
    parent_entity_index = models.CharField(max_length=24, blank=True)
    description = models.CharField(max_length=255, blank=True)
    serial = models.CharField(unique=True, max_length=127, blank=True)
    hardware_version = models.CharField(max_length=255, blank=True)
    firmware_version = models.CharField(max_length=255, blank=True)
    software_version = models.CharField(max_length=255, blank=True)
    slot_number = models.IntegerField(null=True, blank=True)
    number_of_ports = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'node_module'



#######################################################################
# Layer 1
#######################################################################

class L1Interface(models.Model):
    _id = models.AutoField(primary_key=True)
    if_index = models.IntegerField(unique=True)
    port_index = models.CharField(max_length=255, blank=True)
    physical_port = models.CharField(max_length=64, blank=True)
    is_virtual = models.NullBooleanField(null=True, blank=True)
    descriptor = models.CharField(max_length=255, blank=True)
    alias = models.CharField(db_index=True, max_length=255, blank=True)
    node_id = models.ForeignKey(Node)
    entity_id = models.ForeignKey(Entity, null=True, blank=True)
    module_entity_id = models.IntegerField(null=True, blank=True)
    l1_technology_id = models.ForeignKey(L1Technology, null=True, blank=True)
    admin_status = models.IntegerField(null=True, blank=True)
    operational_status = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'l1_interface'

class L1Interface2Link(models.Model):
    last_seen = models.DateTimeField()
    interface_id = models.ForeignKey(L1Interface2Link, primary_key=True)
    link_id = models.IntegerField(L1Link,primary_key=True)
    class Meta:
        db_table = u'l1_interface2link'

class L1Link(models.Model):
    _id = models.AutoField(primary_key=True)
    last_seen = models.DateTimeField()
    description = models.CharField(max_length=255, blank=True)
    class Meta:
        db_table = u'l1_link'

class L1Technology(models.Model):
    _id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=127)
    class Meta:
        db_table = u'l1_technology'
        
        


#######################################################################
# Layer 2
#######################################################################



class L2Interface(models.Model):
    _id = models.AutoField(primary_key=True)
    mac_address = models.CharField(max_length=127)
    node_id = models.ForeignKey(Node, null=True, blank=True)
    etherchannel_id = models.IntegerField(null=True, blank=True)
    l1_interface_id = models.ForeignKey(L1Interface, null=True, blank=True)
    speed = models.PositiveIntegerField(null=True, blank=True)
    duplex = models.CharField(max_length=255, blank=True)
    speed_admin = models.CharField(max_length=255, blank=True)
    duplex_admin = models.CharField(max_length=255, blank=True)
    is_port_fast = models.NullBooleanField(null=True, blank=True)
    is_trunking = models.NullBooleanField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'l2_interface'

class L2Interface2Vlan(models.Model):
    vlan_id = models.ForeignKey(L2Vlan, primary_key=True)
    interface_id = models.ForeignKey(L1Interface,primary_key=True)
    is_tagged = models.NullBooleanField(null=True, blank=True)
    spanning_tree_state = models.CharField(max_length=30, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'l2_interface2vlan'

class L2Peer(models.Model):
    _id = models.AutoField(primary_key=True)
    l2_interface_id = models.ForeignKey(L2Interface2Vlan,null=True, blank=True)
    peer_mac_address = models.CharField(db_index=True,max_length=127)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'l2_peer'

class L2Vlan(models.Model):
    _id = models.AutoField(primary_key=True)
    number = models.IntegerField()
    name = models.CharField(max_length=255, blank=True)
    vtp_domain = models.CharField(max_length=127)
    class Meta:
        db_table = u'l2_vlan'


class Node2Vlan(models.Model):
    node_id = models.ForeignKey(Node, primary_key=True)
    vlan_id = models.ForeignKey(L2Vlan, primary_key=True)
    priority = models.IntegerField(null=True, blank=True)
    designated_root = models.IntegerField(null=True, blank=True)
    root_port = models.IntegerField(null=True, blank=True)
    root_cost = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'node2vlan'


class NodesOnVlan(models.Model):
    node = models.ForeignKey(Node)
    vlan = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'nodes_on_vlan'



#######################################################################
# Layer 3
#######################################################################



class L3Host(models.Model):
    _id = models.AutoField(primary_key=True)
    subnet_id = models.ForeignKey(L3Subnet)
    host_ip_address = models.CharField(db_index=True,max_length=127)
    l2_peer_id = models.ForeignKey(L2Peer, null=True, blank=True)
    last_seen = models.DateTimeField()
    router_node_id = models.ForeignKey(Node,null=True, blank=True)
    class Meta:
        db_table = u'l3_host'

class L3Interface(models.Model):
    _id = models.AutoField(primary_key=True)
    ip_address = models.CharField(db_index=True,max_length=127)
    subnet_id = models.ForeignKey(L3Subnet)
    is_routing = models.NullBooleanField(null=True, blank=True)
    l2_interface_id = models.ForeignKey(L2Interface,null=True, blank=True)
    node_id = models.ForeignKey(Node)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'l3_interface'

class L3Subnet(models.Model):
    _id = models.AutoField(primary_key=True)
    prefix = models.CharField(max_length=127)
    prefix_length = models.IntegerField()
    name = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    class Meta:
        db_table = u'l3_subnet'



#######################################################################
# External db's
#######################################################################


class Dns(models.Model):
    _id = models.AutoField(primary_key=True)
    hostname = models.CharField(max_length=255, blank=True)
    ip_address = models.CharField(max_length=127)
    mac_address = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=255, blank=True)
    department = models.CharField(max_length=255, blank=True)
    building = models.CharField(max_length=255, blank=True)
    room = models.CharField(max_length=255, blank=True)
    user = models.CharField(max_length=255, blank=True)
    email = models.CharField(max_length=255, blank=True)
    administrator = models.CharField(max_length=255, blank=True)
    class Meta:
        db_table = u'dns'





#######################################################################
# Contracts
#######################################################################

class Smartnet(models.Model):
    serial = models.CharField(max_length=127, primary_key=True)
    year = models.IntegerField(primary_key=True)
    on_smartnet = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(null=True, max_digits=10, decimal_places=2, blank=True)
    guessname = models.CharField(max_length=255, blank=True)
    class Meta:
        db_table = u'smartnet'

class SmartnetBak(models.Model):
    serial = models.CharField(max_length=127, primary_key=True)
    year = models.IntegerField(primary_key=True)
    on_smartnet = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(null=True, max_digits=10, decimal_places=2, blank=True)
    class Meta:
        db_table = u'smartnet_bak'



#######################################################################
# TODO
#######################################################################


class AdminsOnNode(models.Model):

    hostname = models.CharField(max_length=255, blank=True)
    ip_address = models.CharField(max_length=127, blank=True)
    mac_address = models.CharField(max_length=255, blank=True)
    administrator = models.CharField(max_length=255, blank=True)
    user = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=255, blank=True)
    building = models.CharField(max_length=255, blank=True)
    room = models.CharField(max_length=255, blank=True)
    node = models.CharField(max_length=127)
    physical_port = models.CharField(max_length=255, blank=True)
    vlan = models.TextField(blank=True)
    alias = models.CharField(max_length=255, blank=True)
    descriptor = models.CharField(max_length=255, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    is_trunking = models.IntegerField(null=True, blank=True)
    speed = models.CharField(max_length=255, blank=True)
    duplex = models.CharField(max_length=255, blank=True)
    new_ip_address = models.CharField(max_length=127, blank=True)
    new_subnet = models.CharField(max_length=127, blank=True)
    new_gateway = models.CharField(max_length=127, blank=True)
    new_vlan = models.CharField(max_length=127, blank=True)
    complete = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'admins_on_node'

class AliasMacAddresses(models.Model):
    device = models.CharField(max_length=127)
    physical_port = models.CharField(max_length=255, blank=True)
    peer_mac_address = models.CharField(max_length=127, blank=True)
    alias = models.CharField(max_length=255, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = u'alias_mac_addresses'

class ArchEntity(models.Model):
    _id = models.BigIntegerField()
    hardware_id = models.IntegerField()
    serial = models.CharField(max_length=127, blank=True)
    description = models.CharField(max_length=255, blank=True)
    operational_status = models.CharField(max_length=255, blank=True)
    admin_status = models.CharField(max_length=255, blank=True)
    hardware_version = models.CharField(max_length=255, blank=True)
    firmware_version = models.CharField(max_length=255, blank=True)
    software_version = models.CharField(max_length=255, blank=True)
    last_seen = models.DateTimeField()
    number_of_ports = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'arch_entity'

class ArchEntity2Node(models.Model):
    node_id = models.IntegerField()
    entity_id = models.IntegerField()
    slot_number = models.IntegerField(null=True, blank=True)
    entity_index = models.CharField(max_length=24)
    parent_entity_index = models.CharField(max_length=24, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_entity2node'

class ArchL1Interface(models.Model):
    _id = models.BigIntegerField()
    if_index = models.IntegerField()
    port_index = models.CharField(max_length=255, blank=True)
    physical_port = models.CharField(max_length=255, blank=True)
    is_virtual = models.IntegerField(null=True, blank=True)
    descriptor = models.CharField(max_length=255, blank=True)
    alias = models.CharField(max_length=255, blank=True)
    node_id = models.IntegerField()
    entity_id = models.IntegerField(null=True, blank=True)
    module_entity_id = models.IntegerField(null=True, blank=True)
    l1_technology_id = models.IntegerField(null=True, blank=True)
    admin_status = models.IntegerField(null=True, blank=True)
    operational_status = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_l1_interface'

class ArchL1Interface2Link(models.Model):
    last_seen = models.DateTimeField()
    interface_id = models.IntegerField(null=True, blank=True)
    link_id = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'arch_l1_interface2link'

class ArchL1Link(models.Model):
    _id = models.BigIntegerField()
    last_seen = models.DateTimeField()
    description = models.CharField(max_length=255, blank=True)
    class Meta:
        db_table = u'arch_l1_link'

class ArchL2Interface(models.Model):
    _id = models.BigIntegerField()
    mac_address = models.CharField(max_length=127)
    node_id = models.IntegerField(null=True, blank=True)
    etherchannel_id = models.IntegerField(null=True, blank=True)
    l1_interface_id = models.IntegerField(null=True, blank=True)
    speed = models.IntegerField(null=True, blank=True)
    duplex = models.CharField(max_length=255, blank=True)
    speed_admin = models.CharField(max_length=255, blank=True)
    duplex_admin = models.CharField(max_length=255, blank=True)
    is_port_fast = models.IntegerField(null=True, blank=True)
    is_trunking = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_l2_interface'

class ArchL2Interface2Vlan(models.Model):
    vlan_id = models.IntegerField()
    interface_id = models.IntegerField()
    is_tagged = models.IntegerField(null=True, blank=True)
    spanning_tree_state = models.CharField(max_length=30, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_l2_interface2vlan'

class ArchL2Peer(models.Model):
    _id = models.BigIntegerField()
    l2_interface_id = models.IntegerField(null=True, blank=True)
    peer_mac_address = models.CharField(max_length=127)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_l2_peer'

class ArchL3Host(models.Model):
    _id = models.BigIntegerField()
    subnet_id = models.IntegerField()
    host_ip_address = models.CharField(max_length=127)
    l2_peer_id = models.IntegerField()
    last_seen = models.DateTimeField()
    router_node_id = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'arch_l3_host'

class ArchL3Interface(models.Model):
    _id = models.BigIntegerField()
    ip_address = models.CharField(max_length=127)
    subnet_id = models.IntegerField()
    is_routing = models.IntegerField(null=True, blank=True)
    l2_interface_id = models.IntegerField(null=True, blank=True)
    node_id = models.IntegerField()
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_l3_interface'

class ArchNode(models.Model):
    _id = models.BigIntegerField()
    hardware_id = models.IntegerField(null=True, blank=True)
    location_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=127)
    software_version = models.TextField(blank=True)
    serial = models.TextField(blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=127, blank=True)
    type = models.CharField(max_length=127, blank=True)
    uptime = models.CharField(max_length=127, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_node'

class ArchNode2Vlan(models.Model):
    node_id = models.IntegerField()
    vlan_id = models.IntegerField()
    priority = models.IntegerField(null=True, blank=True)
    designated_root = models.IntegerField(null=True, blank=True)
    root_port = models.IntegerField(null=True, blank=True)
    root_cost = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_node2vlan'

class ArchNodeModule(models.Model):
    _id = models.BigIntegerField()
    node_id = models.IntegerField()
    operational_status = models.CharField(max_length=255, blank=True)
    admin_status = models.CharField(max_length=255, blank=True)
    hardware_id = models.IntegerField(null=True, blank=True)
    entity_index = models.CharField(max_length=24, blank=True)
    parent_entity_index = models.CharField(max_length=24, blank=True)
    description = models.CharField(max_length=255, blank=True)
    serial = models.CharField(max_length=127, blank=True)
    hardware_version = models.CharField(max_length=255, blank=True)
    firmware_version = models.CharField(max_length=255, blank=True)
    software_version = models.CharField(max_length=255, blank=True)
    slot_number = models.IntegerField(null=True, blank=True)
    number_of_ports = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'arch_node_module'





class InactivePorts(models.Model):
    node = models.CharField(max_length=127, blank=True)
    physical_port = models.CharField(max_length=255, blank=True)
    if_index = models.IntegerField(null=True, blank=True)
    slot_number = models.IntegerField(null=True, blank=True)
    module_id = models.IntegerField(null=True, blank=True)
    admin_status = models.IntegerField(null=True, blank=True)
    operational_status = models.IntegerField(null=True, blank=True)
    alias = models.CharField(max_length=255, blank=True)
    descriptor = models.CharField(max_length=255, blank=True)
    vlan = models.TextField(blank=True)
    speed = models.IntegerField(null=True, blank=True)
    speed_admin = models.CharField(max_length=255, blank=True)
    duplex = models.CharField(max_length=255, blank=True)
    duplex_admin = models.CharField(max_length=255, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'inactive_ports'


        


class MergeL1Interface(models.Model):
    _id = models.BigIntegerField()
    if_index = models.IntegerField()
    port_index = models.CharField(max_length=255, blank=True)
    physical_port = models.CharField(max_length=255, blank=True)
    is_virtual = models.IntegerField(null=True, blank=True)
    descriptor = models.CharField(max_length=255, blank=True)
    alias = models.CharField(max_length=255, blank=True)
    node_id = models.IntegerField()
    entity_id = models.IntegerField(null=True, blank=True)
    module_entity_id = models.IntegerField(null=True, blank=True)
    l1_technology_id = models.IntegerField(null=True, blank=True)
    admin_status = models.IntegerField(null=True, blank=True)
    operational_status = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'merge_l1_interface'

class MergeL2Interface(models.Model):
    _id = models.BigIntegerField()
    mac_address = models.CharField(max_length=127)
    node_id = models.IntegerField(null=True, blank=True)
    etherchannel_id = models.IntegerField(null=True, blank=True)
    l1_interface_id = models.IntegerField(null=True, blank=True)
    speed = models.IntegerField(null=True, blank=True)
    duplex = models.CharField(max_length=255, blank=True)
    speed_admin = models.CharField(max_length=255, blank=True)
    duplex_admin = models.CharField(max_length=255, blank=True)
    is_port_fast = models.IntegerField(null=True, blank=True)
    is_trunking = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'merge_l2_interface'

class MergeL2Interface2Vlan(models.Model):
    vlan_id = models.IntegerField()
    interface_id = models.IntegerField()
    is_tagged = models.IntegerField(null=True, blank=True)
    spanning_tree_state = models.CharField(max_length=30, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'merge_l2_interface2vlan'

class MergeL2Peer(models.Model):
    _id = models.BigIntegerField()
    l2_interface_id = models.IntegerField(null=True, blank=True)
    peer_mac_address = models.CharField(max_length=127)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'merge_l2_peer'

class MergeL3Host(models.Model):
    _id = models.BigIntegerField()
    subnet_id = models.IntegerField()
    host_ip_address = models.CharField(max_length=127)
    l2_peer_id = models.IntegerField()
    last_seen = models.DateTimeField()
    router_node_id = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'merge_l3_host'

class MergeNode(models.Model):
    _id = models.BigIntegerField()
    hardware_id = models.IntegerField(null=True, blank=True)
    location_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=127)
    software_version = models.TextField(blank=True)
    serial = models.TextField(blank=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=127, blank=True)
    category = models.CharField(max_length=127, blank=True)
    uptime = models.CharField(max_length=127, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'merge_node'

class MergeNodeModule(models.Model):
    _id = models.BigIntegerField()
    node_id = models.IntegerField()
    operational_status = models.CharField(max_length=255, blank=True)
    admin_status = models.CharField(max_length=255, blank=True)
    hardware_id = models.IntegerField(null=True, blank=True)
    entity_index = models.CharField(max_length=24, blank=True)
    parent_entity_index = models.CharField(max_length=24, blank=True)
    description = models.CharField(max_length=255, blank=True)
    serial = models.CharField(max_length=127, blank=True)
    hardware_version = models.CharField(max_length=255, blank=True)
    firmware_version = models.CharField(max_length=255, blank=True)
    software_version = models.CharField(max_length=255, blank=True)
    slot_number = models.IntegerField(null=True, blank=True)
    number_of_ports = models.IntegerField(null=True, blank=True)
    last_seen = models.DateTimeField()
    class Meta:
        db_table = u'merge_node_module'





