from ptolemy_py.ui.views import *
# from ptolemy_py.ui.models_sql import PortWithPeer

import logging


class JSONDeviceView( DeviceAllResultsView ):
    template_name = 'device.json'



class JSONDevicePortsView( DevicePortsView ):
    template_name = 'port.json'
    # model = PortWithPeer

class JSONIdlePortsView( IdlePortsSearchResultView ):
    template_name = 'unused-ports.json'


class JSONDeviceDelegateView( DelegateView ):
    template_dir = 'api'
    views = {
        'all': JSONDeviceView,
        'ports': JSONDevicePortsView,
        'unused-ports': JSONIdlePortsView,
    }




class JSONHostView( HostSearchResultsView ):
    template_name = 'host.json'

class JSONHostDelegateView( DelegateView ):
    template_dir = 'api'
    views = {
        'search': JSONHostView,
    }
    



class JSONPortView( PortSearchResultsView ):
    template_name = 'port.json'

class JSONPortDelegateView( DelegateView ):
    template_dir = 'api'
    views = {
        'search': JSONPortView,
    }
    
