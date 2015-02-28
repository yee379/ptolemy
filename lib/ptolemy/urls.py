from django.conf.urls.defaults import *
from django.conf import settings

import ptolemy_py.provision.urls

import ptolemy_py.ui.urls_api
import ptolemy_py.ui.views_topology


urlpatterns = patterns('',

    # uris for ui
    (r'^api/', include('ptolemy_py.ui.urls_api')),

    # dangerous; users to request that something is actually done in the backend
    (r'^provision/', include('ptolemy_py.provision.urls')),
    
    # web display frontends
    (r'^exhibit/', include('ptolemy_py.ui.urls_exhibit')),
    (r'^mobile/', include('ptolemy_py.ui.urls_mobile')),

    # topology stuff
    (r'^topology/', ptolemy_py.ui.views_topology.server_architecture ),


)
