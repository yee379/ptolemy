
# from django.test import TestCase
# import os
# 
# from poller.driver import Template, YAMLDriver
# 
# from poller.managers import DriverCache
# 
# from poller.workers import Gatherer
# 
# import re
# 
# import logging
# logging.basicConfig( level=logging.WARN, format='%(asctime)-8s %(message)s' )
# 
# 
# 
# 
# # class YAMLDriverTest(TestCase):
# #             
# #     def setUp(self):
# #         f = '/opt/ptolemy/etc/ptolemy/polld/drivers/performance-stats/generic.yaml'
# #         self.driver = YAMLDriver(f)
# #         self.assertEqual( type(self.driver).__name__, 'YAMLDriver' )
# # 
# #     def test_spec(self):
# #         self.assertEqual( self.driver.refs( 'SNMP' ), ['ifHCOutMulticastPkts', 'ifInDiscards', 'ifInErrors', 'ifHCOutOctets', 'ifHCInOctets', 'ifHCInBroadcastPkts', 'ifHCInMulticastPkts', 'ifConnectorPresent', 'ifHCOutBroadcastPkts', 'ifOutErrors', 'ifName', 'ifOperStatus', 'ifOutDiscards', 'ifHCOutUcastPkts', 'ifHCInUcastPkts', 'ifAdminStatus'] )
# #         self.assertEqual( self.driver.refs( 'NetConfig' ), [] )
# 
# 
# class DriverCacheTest(TestCase):
#     def test_set(self):
#         c = DriverCache()
#         d = 'driver.yaml'
#         c.set( 'host', 'spec', d )
#         self.assertEqual( d, c.get( 'host', 'spec' ) )
# 
#     def test_load(self):
#         f = '/tmp/test.cache'
#         with open(f, 'w') as a:
#             a.write( 'host1\tspec1\tdriver1' )
#         c = DriverCache( filepath=f )
#         c.load()
#         self.assertEqual( 'driver1', c.get('host1','spec1') )
#         
#     def test_save(self):
#         f = '/tmp/test.cache'
#         c = DriverCache( filepath=f )
#         c.set( 'host2', 'spec2', 'driver2' )
#         c.save()
#         d = DriverCache( filepath=f )
#         d.load()
#         self.assertEqual( c.get('host2','spec2'), d.get('host2','spec2') )
# 
# class TemplateTest(TestCase):
#     
#     def setUp(self):
#         f = '/opt/ptolemy/etc/ptolemy/polld/drivers/template.yaml'
#         self.template = Template(f)
#         self.assertEqual( type(self.template).__name__, 'Template')
#         # logging.debug("template: " + str(self.template))
#         
#     def test_specs(self):
#         self.assertEqual( self.template.specifications(), ['interface', 'performance', 'entity'] )
#     
#     def test_groups(self):
#         self.assertEqual( self.template.groups('interface'), ['port-settings', 'layer3-info', 'port-info', 'port-status', 'peer-info', 'vlan-info', 'portchannel-info'] )
#         
#     def test_defs(self):
#         self.assertEqual( self.template.defs('interface','port-info'), ['ifAlias', 'ifDescription', 'ifType', 'ifPort', 'ifPhysicalPort', 'ifPhysAddress'] )
# 
# 

# 
# # class CiscoSRouterLayer1Test( DriverTest ):
# #     def test1(self):
# #         return self.do( 'rtr-mcccore1.slac.stanford.edu', 'layer1/cisco_srouter.yaml' )
# #         
# # class CiscoSRouterLayer2Test( DriverTest ):
# #     def test1(self):
# #         return self.do( 'rtr-mcccore1.slac.stanford.edu', 'layer2/cisco_srouter.yaml' )
# #         
# # class CiscoSRouterLayer3Test( DriverTest ):
# #     def test1(self):
# #         return self.do( 'rtr-mcccore1.slac.stanford.edu', 'layer3/cisco_srouter.yaml' )
# 
# 
# 
# class DriverSuiteTest( TestCase ):
#     tests = {
#         'system':   [
#             ( 'swh-farm02a.slac.stanford.edu',      'cisco_5000.yaml' ),
#             ( 'rtr-lbepn3-01.slac.stanford.edu',    'f5_big_ip.yaml'),
#             ( 'rtr-fwvpn1.slac.stanford.edu',       'cisco_5000.yaml' ),
#             ( 'swh-b050f3.slac.stanford.edu',       'cisco_generic.yaml' ),
#             ( 'swh-ibfarm03.slac.stanford.edu',     'cisco_topspin.yaml' ),
#             
#         ],
#         'entity': [
#             ( 'swh-b106.slac.stanford.edu',         'cisco_ios_switch.yaml' ),
#             ( 'rtr-netmgmt.slac.stanford.edu',      'cisco_ios_router.yaml' ),
#             ( 'rtr-fwepn3-01.slac.stanford.edu',    'cisco_asa.yaml'),
#         ],
#         'port_stats': [
#             ( 'rtr-fwpbx01.slac.stanford.edu',      'generic.yaml' ),
#             
#         ],
#         'layer1_peer': [
#             ( 'swh-b050f3.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'rtr-serv03.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'swh-b041f1.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'rtr-block.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'swh-devctl2ah07.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'swh-farmorange1.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'swh-li25-bp02.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'swh-lebcore1b.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'swh-ibfarm08.slac.stanford.edu',       'topspin_sfs7000d.yaml' ),
#             ( 'swh-farm02a.slac.stanford.edu',       'dell_8024f.yaml' ),
#             ( 'rtr-serv01-01.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'rtr-farmorange.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'rtr-visitor1.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'rtr-fac1.slac.stanford.edu',       'cisco_cdp.yaml' ),
#             ( 'rtr-fwpbx01.slac.stanford.edu',       None ),
#             
#         ]
#         'ports': [
#             ( 'swh-b050f3.slac.stanford.edu',       'cisco_ios_switch.yaml' ),
#             ( 'rtr-serv03.slac.stanford.edu',       'cisco_ios_switch.yaml' ),
#             ( 'swh-b041f1.slac.stanford.edu',       'cisco_ios_4000.yaml' ),
#             ( 'rtr-block.slac.stanford.edu',       'cisco_hybrid_router.yaml' ),
#             ( 'swh-devctl2ah07.slac.stanford.edu',       'cisco_router.yaml' ),
#             ( 'swh-farmorange1.slac.stanford.edu',       'cisco_ios_switch.yaml' ),
#             ( 'swh-li25-bp02.slac.stanford.edu',       'cisco_ios_switch.yaml' ),
#             ( 'swh-lebcore1b.slac.stanford.edu',       'cisco_router.yaml' ),
#             ( 'swh-ibfarm08.slac.stanford.edu',       'topspin_sfs7000d.yaml' ),
#             ( 'swh-farm02a.slac.stanford.edu',       'dell_8024f.yaml' ),
#             ( 'rtr-serv01-01.slac.stanford.edu',       'cisco_ios_4000.yaml' ),
#             ( 'rtr-farmorange.slac.stanford.edu',       'cisco_ios_4000.yaml' ),
#             ( 'rtr-visitor1.slac.stanford.edu',       'cisco_hybrid_router.yaml' ),
#             ( 'rtr-fac1.slac.stanford.edu',       'cisco_hybrid_router.yaml' ),
#             ( 'rtr-fwpbx01.slac.stanford.edu',       'cisco_router.yaml' ),
#     
#         ],
#     }
# 
# 
#     options = {
#         'snmp_community':    'file:///opt/etc/snmp.community.read',
#         'snmp_mib_dirs':      [ '/opt/ptolemy/etc/ptolemy/polld/snmp_mibs/' ]
#     }
#     g = None
# 
#     def setUp( self ):
#         self.g = Gatherer( mib_dirs=self.options['snmp.mib_dirs'] )
# 
#     def do( self, device, driver ):
#         kwargs = {
#             'options': self.options
#         }
#         return self.g.fetch( device, driver, kwargs )
# 
#     def test(self):
#         for spec in self.tests:
#             pass
# 
#     def test_spec( self, spec ):
#         for test in self.tests[spec]:
#             device = test[0]
#             driver = str(spec) + '/' + str(test[1])
#             g = Gatherer( driver_dir='/opt/ptolemy/etc/ptolemy/polld/drivers/', 
#                     mib_dirs=self.options['snmp.mib_dirs'] )
#             self.do( device, driver )
#             



import unittest
import logging

import ptolemy.poller.agent

class PingAgentTest( unittest.TestCase ):
    def setUp( self ):
        self.agent = ptolemy.poller.agent.Ping()
    def do( self, host ):
        d = {}
        for k,n,v in self.agent.fetch( host, [ 'sent', 'received', 'loss', 'min_rtt', 'max_rtt', 'avg_rtt', 'stdev' ] ):
            d[k] = v
        return d
    def test_good(self):
        d = self.do( 'rtr-core1.slac.stanford.edu' )
        # logging.error("D: %s" % (d,))
        self.assertTrue( int(d['loss']) < 100 )
    def test_bad(self):
        d = self.do( 'sccs-ytl.slac.stanford.edu' )
        self.assertTrue( int(d['loss']) == 0 )
    # def test_bad2(self):
    #     d = self.do( 'swh-ssrlb137ee1.slac.stanford.edu' )
    #     logging.error("D: %s" % (d,))
    #     self.assertTrue( int(d['loss']) > 0 )

c = open('/opt/etc/snmp.community.read' ).read().strip()

class NetSNMPAgentTest( unittest.TestCase ):

    mib_dirs = [ '/opt/ptolemy/etc/ptolemy/polld/snmp_mibs/' ]

    def setUp(self):
        self.agent = ptolemy.poller.agent.NetSNMP()

    # def test_set_mibdir(self):
    #     m = 'test_dir'
    #     # agent = NetSNMP( 'swh-b050f3', options={ 'community': c, 'mib_dirs': [ m ] } )
    #     d = agent.get_mibdirs()
    #     self.assertTrue( m in d, 'set mibdir' )

    def test_read_module(self):
        agent = ptolemy.poller.agent.NetSNMP()
        d = agent.get_mibdirs()
        self.assertTrue( self.mib_dirs[0] in d, 'mib dir not okay')

    def bulkwalk( self, host, options={}, oids=[] ):
        with self.agent as a:
            got_something = False
            for f,i,v in a.fetch( host, oids, **options ):
                logging.error(">> f: " + str(f) + ", i: " + str(i) + ", v: " + str(v))
                self.assertTrue( f in oids, 'could not fetch ' + str(oids) )
                got_something = True
            if not got_something:
                self.fail('no data from query for %s' % (oids,))

    def test_uptime(self):
        self.bulkwalk( 'swh-b050f3', options={ 'community': c }, oids=['sysUpTime',] )


    def test_bulkwalk(self):
        self.bulkwalk( 'swh-b050f3', options={ 'community': c }, oids=['ifHCInUcastPkts','ifHCOutUcastPkts'] )

    def test_bulkwalk2(self):
        self.bulkwalk( 'swh-b050f3', options={ 'community': c, 'mib_dirs': self.mib_dirs, 'mibs': [ 'CISCO-MEMORY-POOL-MIB' ] }, oids=[ 'ciscoMemoryPoolUsed' ] )

    def test_bulkwalk3(self):
        self.bulkwalk( 'swh-b050f3', options={ 'community': c, 'mib_dirs': self.mib_dirs, 'mibs': ['ENTITY-MIB'] }, oids=[ 'entPhysicalVendorType' ] )

    def test_bulkwalk4(self):
        self.bulkwalk( 'swh-b050f3', options={ 'community': c, 'mib_dirs': self.mib_dirs, 'mibs': ['ENTITY-MIB'] }, oids=[ 'entPhysicalVendorType', 'sysName' ] )

#     def test_enum(self):
#         # n = '.1.3.6.1.2.1.17.1.4.1.3.5'
#         add_mib_module( 'Q-BRIDGE-MIB' )
#         add_mib_module( 'CISCO-VTP-MIB' )
#         n = 'dot1dTpFdbStatus'
#         o = OID( n )
#         logging.debug("OID: %s gives %r" % (n,o) )
#         self.assertTrue( isinstance(o, OID) )
#         m,f,iid = o.decode()
#         logging.debug(" m: %s\tf: %s\tiid: %s" % (m,f,iid) )
#         self.assertEquals( m, 'BRIDGE-MIB' )
#         self.assertEquals( f, 'dot1dTpFdbStatus' )
#         # self.assertEquals( iid, '1' )
#         
#         enums = o.enums()
#         logging.debug(" enums: " + str(enums))
#         
#   #       # get the value
#   #         with self.agent as a:
#   #             for f,i,v in a.fetch( 'swh-b050f3', [ 'dot1dTpFdbStatus', ], community=c+'@230' ):
#   #                 logging.warn("  f: %s\tk: %s\tv: %s" % (f,i,v))
# 
# 

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
