from math import log
# import cx_Oracle
from yaml import load
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from slac_utils.net import valid_netmask_or_prefixlen, prefixlen_to_netmask, network_address, netmask_to_prefixlen, to_network, sort_networks, to_network_from_list


import logging

class Infrastructure( object ):
    
    def __init__( self, **kwargs ):
        pass
    
    def get_network_devices(self,*args,**kwargs):
        """
        retrieves a list of all network devices
        """
        raise NotImplementedError
     
    def get_subnets(self,*args,**kwargs):
        """
        retrieves a list of all subnets
        """
        raise NotImplementedError

    def get_hosts(self,*args,**kwargs):
        """
        retrieves a list of all hosts ip/dns pairs
        """
        raise NotImplementedError


class NetDB( Infrastructure ):
    
    def __init__(self,nodes=None,subnets=None):
        self.nodes = open( nodes, 'r' )
        self.subnets = open( subnets, 'r' )
    
    def get_network_devices( self, default_domain_name='slac.stanford.edu', filter=['ap-','swh-','rtr-']  ):

        # the generic algorithm is that the node name has to match the interface name provided
        # that both startswith any in the filter list
        for key,d in load( self.nodes, Loader=Loader ).iteritems():
            # logging.error("D: %s\t%s" % (key,d))
            # grab first part of name from key
            node_name = key.split('.').pop(0).lower()
            is_network_device = [ True for b in filter if node_name.startswith(b) ]
            if True in is_network_device:
                for i in d['interfaces']:
                    if i['name'].lower() == node_name:
                        this = {
                            'hostname': "%s.%s" % (node_name.lower(),default_domain_name),
                            'ip_address': None,
                        }
                        yield this
        return
        
    def get_subnets( self ):
        for k,d in load( self.subnets, Loader=Loader ).iteritems():
            d['prefix_len'] = netmask_to_prefixlen( d['netmask'] )
            yield d

    def get_hosts( self ):
        """ return all hosts registered """
        for k,d in load( self.nodes, Loader=Loader ).iteritems():
            # logging.warn( "%s" % (d,) )
            for i in d['interfaces']:
                this = {}
                if 'ipnum' in i:
                    for j in i['ipnum']:
                        this['ip_address'] = j
                    if 'name' in i and 'domain' in i:
                        this['hostname'] = '%s.%s' % ( i['name'].lower(), i['domain'].lower() )
                    if 'ethernet' in i:
                        this['mac_address'] = '%s' % i['ethernet']
                    yield this
    