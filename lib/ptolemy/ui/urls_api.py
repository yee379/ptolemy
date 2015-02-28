from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from ptolemy_py.ui.views_api import JSONDeviceDelegateView as DeviceView
from ptolemy_py.ui.views_api import JSONHostDelegateView as HostView
from ptolemy_py.ui.views_api import JSONPortDelegateView as PortView

from ptolemy_py.ui.views import ProvisionShowPortView, ProvisionEditPortView

import ptolemy_py.ui.views_api

urlpatterns = patterns('',

    # device list
    (r'^device/?$', DeviceView.as_view( use_view='all') ),
    (r'^device/id/(?P<id>\w+)/ports/unused/?$', DeviceView.as_view( use_view='unused-ports') ),
    (r'^device/id/(?P<id>\w+)/(?P<use_view>ports)/?$', DeviceView.as_view() ),

    # host search
    (r'^host/(?P<use_view>search)/(?P<field>\w+)/(?P<value>(\w|-|\.|:|\s)+)/?$', HostView.as_view() ),

    # port search
    (r'^port/(?P<use_view>search)/(?P<field>\w+)/(?P<value>(\w|-|\.|:|\s)+)/?$', PortView.as_view() ),

    # update
    (r'^port/id/(?P<id>\d+)/update/?$', ProvisionShowPortView.as_view() ),

    # edit
    (r'^port/id/(?P<id>\d+)/edit/?$', ProvisionEditPortView.as_view() ),
    

)
