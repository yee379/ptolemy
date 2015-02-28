from django.views.generic import TemplateView
from ptolemy_py.ui.views import *
from django.utils.datastructures import SortedDict

# superset the json api's for exhibit
from ptolemy_py.ui.views_api import *


import logging



standard_facets = {
    'port': SortedDict([
        ( 'device', [] ),
        ( 'vlan', [] ),
        ( 'slot', [] ),
        ( 'status', [] ),
        ( 'autoneg', [] ),
        ( 'speed', [] ),
        ( 'duplex', [] ),
        ( 'portfast', [] )
    ]),
    'host': SortedDict([
        ( 'connected_to', [] ),
        ( 'status', [] ),
        ( 'vlan', [] ),
        ( 'autoneg', [] ),
        ( 'speed', [] ),
        ( 'duplex', [] ),
        ( 'admin', [] ),
        ( 'user', [] )
    ]),
    'device': SortedDict([
        ( 'category', [] ),
        ( 'kind', [] ),
        ( 'vlan', [] ),
        ( 'vendor', [] ),
        ( 'model', [] ),
        ( 'sw_version', [] ),
        ( 'building', [] )
    ]),
}

standard_columns = {
    'port': SortedDict([
        ( 'port_edit_url', { 'label': 'edit', 'type': 'a' } ),
        ( 'device', { }),
        ( 'port', {} ),
        ( 'alias', { 'editable': True } ),
        ( 'status', { 'editable': True, 'editable_values': [ 'enable', 'disable' ] } ),
        ( 'vlan', { 'label': 'vlans', 'editable': True } ),
        ( 'speed', { 'editable': True, 'editable_values': [ '10', '100', '1000' ] } ),
        ( 'duplex', { 'editable': True, 'editable_values': [ 'auto', 'fixed' ] } ),
        ( 'autoneg', { 'editable': True, 'editable_values': [ 'auto', 'fixed' ] } ),
        ( 'peer', {} ),
        ( 'last_seen', {} ),
    ]),
    'host': SortedDict([
        ( 'hostname', {} ),
        ( 'ip_address', {} ),
        ( 'mac_address',  {} ),
        ( 'connected_to', {} ),
        ( 'port', { 'label': 'port' } ),
        ( 'tap', {} ),
        ( 'status', {} ),
        ( 'vlan', {} ),
        ( 'speed', {} ),
        ( 'duplex', {} ),
        ( 'autoneg', {} ),
        ( 'user', {} ),
        ( 'admin', {} ),
    ]),
    'device': SortedDict([
        ( 'name', { 'label': 'device' }),
        ( 'vendor', {} ),
        ( 'model',  { 'label': 'model(s)'} ),
        ( 'sw_version', { 'label': 'sw_version(s)'} ),
        ( 'vlan', { 'label': 'vlans' } ),
        ( 'location', {} ),
        ( 'ports_url', { 'label': 'ports', 'type': 'a' } ),
        ( 'last_seen', {} ),
        ( 'uptime', { 'label': 'uptime' } )
    ])

}



class ExhibitMenuView( MenuView ):
    template_name = 'exhibit/index.html'
    
    
# exhibit basically returns exactly the same view each time, but with a differing json call
class ExhibitTableView( TemplateView ):
    template_dir = 'exhibit'
    template_name = 'table.html'
    # where to point for the api calls for teh json data
    json_href_prefix = 'exhibit/api' 
    json_href = None

    facets = SortedDict([]) # key = facet name, value = selected items within facet
    columns = SortedDict([])
    sort_column = 0
    
    def dispatch(self, *args, **kwargs):
        # look into the args and populate the json_href with appropriate fields
        # logging.error("KWARGS: " + str(kwargs))
        return super(ExhibitTableView, self).dispatch(*args, **kwargs)
    
    # exhibit_json = None
    def get_context_data(self, **kwargs):
        d = super( ExhibitTableView, self ).get_context_data(**kwargs)
        
        # filter the facets based on get items
        for k,v in self.request.GET.items():
            # logging.error("GET: " + str(k) + ", " + str(v))
            if k.startswith( '.' ):
                i = k.replace( '.', '' )
                if i in self.facets:
                    self.facets[i].append( v )
        
        # determien the appropriate href based on one's own view
        href = self.request.path.replace( '/'+self.template_dir+'/', '/'+self.json_href_prefix+'/')
        d['json_href'] = href
        
        # work out the facet and table columns        
        cl = []
        for i in self.columns:
            # c.append( str(i) )
            x = i
            if 'label' in self.columns[i]:
                x = self.columns[i]['label']
            else:
                self.columns[i]['label'] = i
            cl.append( x )
        d['exhibit'] = {
            'facets': self.facets,
            'columns': self.columns,
            'columnLabels': cl,
            'sort_column': self.sort_column,
        }
        return d

class ExhibitDeviceView( ExhibitTableView ):
    facets = standard_facets['device']
    columns = standard_columns['device']

    
class ExhibitDevicePortsView( ExhibitTableView ):
    facets = standard_facets['port']
    columns = standard_columns['port']
    sort_column = 1

class ExhibitIdlePortsView( ExhibitTableView ):
    facets = SortedDict([
        ( 'device', [] ),
        ( 'status', [] ),
        ( 'autoneg', [] ),
        ( 'speed', [] ),
        ( 'duplex', [] ),
    ])
    columns = SortedDict([
        ( 'last_active', {} ),

        ( 'device', { }),
        ( 'port', {} ),
        ( 'alias', {} ),
        ( 'status', {} ),
        # ( 'vlan', { 'label': 'vlans' } ),
        ( 'speed', {} ),
        ( 'duplex', {} ),
        ( 'autoneg', {} ),
        # ( 'peer', { 'label': 'last peer'} ),
    ])

class ExhibitDeviceDelegateView( DelegateView ):
    template_dir = 'exhibit'
    views = {
        'search': DeviceSearchResultsView,
        'ports': ExhibitDevicePortsView, 
        'unused-ports': ExhibitIdlePortsView,
        None: ExhibitDeviceView,
    }

class ExhibitHostSearchView( ExhibitTableView ):
    facets = standard_facets['host']
    columns = standard_columns['host']
    
class ExhibitHostDelegateView( DelegateView ):
    template_dir = 'exhibit'
    views = {
        'search_menu': HostSearchMenuView,
        'search': ExhibitHostSearchView,
    }


class ExhibitPortSearchView( ExhibitTableView ):
    facets = standard_facets['port']
    columns = standard_columns['port']
    

class ExhibitPortDelegateView( DelegateView ):
    template_dir = 'exhibit'
    views = {
        'search': ExhibitPortSearchView,
    }


#######################################################################
# json interfaces
#######################################################################

class ExhibitJSONDeviceDelegateView( JSONDeviceDelegateView ):
    template_dir = 'exhibit/api'
    
class ExhibitJSONHostDelegateView( JSONHostDelegateView ):
    template_dir = 'exhibit/api'
    
class ExhibitJSONPortDelegateView( JSONPortDelegateView ):
    template_dir = 'template/api'
    
