from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

import ptolemy_py.ui.views_mobile

from ptolemy_py.ui.views_mobile import MobileDeviceDelegateView as DeviceView
from ptolemy_py.ui.views_mobile import MobileHostDelegateView as HostView
from ptolemy_py.ui.views_mobile import MobilePortDelegateView as PortView

from ptolemy_py.ui.views_mobile import MobileMenuView as MenuView
# from ptolemy_py.ui.views import *

urlpatterns = patterns('',

    # searching for devices
    (r'^device/search/(?P<field>\w+)/?$', DeviceView.as_view( use_view='search_summary') ),
    (r'^device/search/(?P<field>\w+)/(?P<value>(\w|-|\.|\(|\)|\s)+)/?$', DeviceView.as_view( use_view='search') ),
    (r'^device/search/?$', DeviceView.as_view( use_view='search_menu' ) ),

    # port lists
    (r'^device/id/(?P<id>\w+)/(?P<use_view>ports)/?$', DeviceView.as_view() ),
    (r'^device/id/(?P<id>\w+)/(?P<use_view>entities)/?$', DeviceView.as_view() ),

    # main menu
    (r'^device/?$', DeviceView.as_view() ),
    

    # searching for hosts
    (r'^host/search/(?P<field>\w+)/?$', HostView.as_view( use_view='search_summary') ),
    (r'^host/search/(?P<field>\w+)/(?P<value>(\w|-|\.|\(|\)|\s)+)/?$', HostView.as_view( use_view='search') ),    
    (r'^host/search/?$', HostView.as_view( use_view='search_menu') ),

    (r'^host/id/(?P<id>\w+)', HostView.as_view( use_view='detail') ),

    (r'^host/?', HostView.as_view() ),    
    

    # port
    (r'^port/id/(?P<id>\w+)?/edit/?$', PortView.as_view( use_view='edit' ) ),
    (r'^port/id/(?P<id>\w+)?(/info)?/?$', PortView.as_view( use_view='detail' ) ),    
    

    
    # (r'^port/id/(?P<port_id>\w+)?/edit/?$', ptolemy_py.ui.views_mobile.port, { 'edit': True } ),
    # (r'^port/id/(?P<port_id>\w+)?(/info)?/?$', ptolemy_py.ui.views_mobile.port ),    
    
    # (r'^entity/', ptolemy_py.ui.views_mobile.entity ),    


    # (r'^host/search/(?P<field>\w+)(/(?P<value>(\w|-)+))?/?', ptolemy_py.ui.views_mobile.host ),
    
    # provision
    # (r'^provision/poll/(?P<device>([a-zA-Z0-9]|\.|\-)+)/(?P<spec>([a-zA-Z])+)/?$', ptolemy_py.ui.views_mobile.provision_poll ),
    # (r'^provision/configure/(?P<device>([a-zA-Z0-9]|\.|\-)+)/(?P<port>.*)/?$', ptolemy_py.ui.views_mobile.provision_configure ),

    
    # main
    (r'^/?', MenuView.as_view() ),
)
