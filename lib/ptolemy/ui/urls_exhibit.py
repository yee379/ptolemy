from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()


from ptolemy_py.ui.views_exhibit import ExhibitDeviceDelegateView as DeviceView
from ptolemy_py.ui.views_exhibit import ExhibitHostDelegateView as HostView
from ptolemy_py.ui.views_exhibit import ExhibitPortDelegateView as PortView

from ptolemy_py.ui.views_exhibit import ExhibitMenuView as MenuView

from ptolemy_py.ui.views_exhibit import ExhibitJSONDeviceDelegateView as JSONDeviceView
from ptolemy_py.ui.views_exhibit import ExhibitJSONHostDelegateView as JSONHostView
from ptolemy_py.ui.views_exhibit import ExhibitJSONPortDelegateView as JSONPortView


urlpatterns = patterns('',

    # searching for devices
    (r'^device/search/(?P<field>\w+)/?$', DeviceView.as_view( use_view='search_summary') ),
    (r'^device/search/(?P<field>\w+)/(?P<value>.*)/?$', DeviceView.as_view( use_view='search') ),
    (r'^device/search/?$', DeviceView.as_view( use_view='search_menu' ) ),

    # port lists
    (r'^device/id/(?P<id>\w+)/ports/unused/?$', DeviceView.as_view( use_view="unused-ports") ),
    (r'^device/id/(?P<id>\w+)/(?P<use_view>ports)/?$', DeviceView.as_view() ),
    (r'^device/id/(?P<id>\w+)/(?P<use_view>entities)/?$', DeviceView.as_view() ),
    (r'^device/?$', DeviceView.as_view() ),

    # searching for hosts
    (r'^host/search/(?P<field>\w+)/?$', HostView.as_view( use_view='search_summary') ),
    (r'^host/search/(?P<field>\w+)(/(?P<value>(\w|-|\.|\:)+))/?$', HostView.as_view( use_view='search') ),    
    (r'^host/search/?$', HostView.as_view( use_view='search_menu') ),
    (r'^host/id/(?P<id>\w+)', HostView.as_view( use_view='detail') ),
    (r'^host/?', HostView.as_view() ),    
    
    # main menu
    (r'^$', MenuView.as_view() ),

    # api port
    (r'^api/port/search/(?P<field>\w+)(/(?P<value>(\w|-)+))/?$', JSONPortView.as_view( use_view='search') ),    
    (r'^api/port/id/(?P<id>\w+)?/edit/?$', JSONPortView.as_view( use_view='edit' ) ),
    (r'^api/port/id/(?P<id>\w+)?(/info)?/?$', JSONPortView.as_view( use_view='detail' ) ),    
    (r'^api/port/(?P<use_view>search)/(?P<field>\w+)/(?P<value>(\w|-|\.|:|\s)+)/?$', JSONPortView.as_view() ),
    
    # api device list
    (r'^api/device/?$', JSONDeviceView.as_view( use_view='all') ),
    (r'^api/device/id/(?P<id>\w+)/ports/unused/?$', JSONDeviceView.as_view( use_view='unused-ports') ),
    (r'^api/device/id/(?P<id>\w+)/(?P<use_view>ports)/?$', JSONDeviceView.as_view() ),

    # api host search
    (r'^api/host/(?P<use_view>search)/(?P<field>\w+)/(?P<value>(\w|-|\.|:|\s)+)/?$', JSONHostView.as_view() ),

)
