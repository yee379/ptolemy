
import unittest
import logging

import ptolemy.ipam


class CategoriserTest(unittest.TestCase):
    def setUp(self):
        self.cat = Categoriser( type_file='etc/ptolemy/ipam/types.conf',
                        group_file='etc/ptolemy/ipam/groups.conf',
                        category_file='etc/ptolemy/ipam/categories.conf' )
        self.assertEqual( type(self.cat), Categoriser )

    def test_type(self):
        t = self.cat.types
        self.assertEqual( self.cat.match( t, 'rtr-farm21.slac.stanford.edu', 'name' ), 'router' )
        self.assertEqual( self.cat.match( t, 'swh-b050f3.slac.stanford.edu', 'name' ), 'switch' )
        self.assertEqual( self.cat.match( t, 'ap-b049r250.slac.stanford.edu', 'name' ), 'wireless' )
        self.assertEqual( self.cat.match( t, 'rtr-lbserv03-01.slac.stanford.edu', 'name' ), 'load_balancer' )        
        self.assertEqual( self.cat.match( t, 'rtr-fwfsys1.slac.stanford.edu', 'name' ), 'firewall' )        
        self.assertEqual( self.cat.match( t, 'swh-devctl1as22.slac.stanford.edu', 'name' ), 'switch' )
        
    def test_group(self):
        """ a group is an actual department that cares about these devices """
        t = self.cat.groups
        self.assertEqual( self.cat.match( t, 'rtr-farm21.slac.stanford.edu', 'name' ), 'farm' )
        self.assertEqual( self.cat.match( t, 'swh-b050f3.slac.stanford.edu', 'name' ), 'campus' )
        self.assertEqual( self.cat.match( t, 'ap-b049r250.slac.stanford.edu', 'name' ), 'campus' )
        self.assertEqual( self.cat.match( t, 'rtr-lbserv03-01.slac.stanford.edu', 'name' ), 'infrastructure' )
        self.assertEqual( self.cat.match( t, 'rtr-fwfsys1.slac.stanford.edu', 'name' ), 'business' )
        self.assertEqual( self.cat.match( t, 'swh-devctl1as22.slac.stanford.edu', 'name' ), 'farm' )
        
    def test_category(self):
        """ category is a logical grouping used by net management"""
        t = self.cat.categories
        self.assertEqual( self.cat.match( t, 'rtr-farm21.slac.stanford.edu', 'name' ), 'infrastructure' )
        self.assertEqual( self.cat.match( t, 'swh-b050f3.slac.stanford.edu', 'name' ), 'infrastructure' )
        self.assertEqual( self.cat.match( t, 'ap-b049r250.slac.stanford.edu', 'name' ), 'infrastructure' )
        self.assertEqual( self.cat.match( t, 'rtr-lbserv03-01.slac.stanford.edu', 'name' ), 'infrastructure' )
        self.assertEqual( self.cat.match( t, 'rtr-fwfsys1.slac.stanford.edu', 'name' ), 'infrastructure' )
        self.assertEqual( self.cat.match( t, 'swh-devctl1as22.slac.stanford.edu', 'name' ), 'management' )


class DevicesListTest( unittest.TestCase ):
    def setUp(self):
        pass
        
    def test_get(self):
        pass


if __name__ == '__main__':
    log_level = logging.DEBUG
    log_format = '%(asctime)-8s %(process)-5d %(message)s'
    logging.basicConfig( level=log_level, format=log_format )
    unittest.main()