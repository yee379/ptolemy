from ptolemy_py.ui.views import *
import ptolemy_py.provision.views

import logging


class MobileMenuView( MenuView ):
    template_name = 'mobile/index.html'


class MobileDeviceDelegateView( DelegateView ):
    template_dir = 'mobile'
    views = {
        'search': DeviceSearchResultsView,
        'search_summary': DeviceSearchSummaryView, 
        'search_menu': DeviceSearchMenuView,
        'ports': DevicePortsView,
    }

class MobileHostDelegateView( DelegateView ):
    template_dir = 'mobile'
    views = {
        'search_menu': HostSearchMenuView,    
        'search_summary': HostSearchSummaryView,
        'search': HostSearchResultsView,
        'detail': HostDetailView,
    }


class MobilePortDelegateView( DelegateView ):
    template_dir = 'mobile'
    views = {
        'detail': PortDetailView,
    }



# provision results

header = """
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, minimum-scale=1, maximum-scale=1">
    <title>Provision Response</title>
    <link rel="stylesheet" href="/css/jquery.mobile-1.0b1.min.css" type="text/css">
    <link rel="stylesheet" href="/css/jqm-docs.css" type="text/css">
  </head>
  <body>
    <ul>
"""

footer = """
    </ul>
  </body>
</html>
"""
def provision_poll( request, device=None, spec='spanningtree', format=None ):
    if format == None: format = 'html'
    info = ptolemy_py.provision.views.poll( request, device=device, spec=spec )
    return HttpResponse( info.get( header=header, footer=footer, item='<li>' ) )

def provision_configure( request, device=None, port=None, format=None ):
    if format == None: format = 'html'
    port = port.replace( '_', '/' )
    info = ptolemy_py.provision.views.configure( request, device=device, port=port )
    if info == None:
        return HttpResponse( header )
    return HttpResponse( info.get( header=header, footer=footer, item='<li>' ) )
    
