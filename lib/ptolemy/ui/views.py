from django.shortcuts import get_object_or_404

from django.views.generic.base import View
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.detail import SingleObjectMixin

from django import http
from django.http import HttpResponse

from ptolemy_py.ui.models_sql import Device, Entity, Port, Host, L1InterfaceArchive, Peer, PortWithPeer, HostsOnSubnet
from django.db.models import Count

from ptolemy_py.util.remote import *
from django.conf import settings

import os
from time import sleep

from django.utils import simplejson as json

import logging

mimetype_map = {
    'html': 'text/html',
    'xml':  'application/xml',
    'tsv':  'text/plain',
    'csv':  'text/plain',
    'exhibit': 'application/json',
}


def parse_location( string ):
    """
    given a location string, will spit out the components
    """
    location = {}
    for p in string.split(','):
        this = p.split('=')
        if len(this) > 1:
            location[this[0].strip()] = this[1].strip()
    # logging.error("location: " + str(location))
    return location
    

class MenuView( TemplateView ):
    template_name = 'index.html'



#######################################################################
# Helper Views
#######################################################################

class DelegateView( View ):
    """
    Base view to determine what view should be shown based upon input parameters
    """
    template_dir = ''
    views = {
        'id': None,
        'search': None,
        'search_menu': None,
        None: MenuView
    }
    
    use_view = None # hack to get view as initkwargs
    db_name = 'scs_lanmon'

    def delegate( self, view, request, *args, **kwargs ):
        """
        given the view, use the delegate_map to determine the type of (new View) object to return
        """
        logging.error("Delegate use_view=" + str(view) + " in " + str(self.views))
        if view in self.views and not self.views[view] == None:
            logging.error("  delegating to " + str(self.views[view]))
            cls = self.views[view]()
            # reassign templates
            if self.template_dir:
                cls.template_name = self.template_dir + '/' + cls.template_name
            # set the db_name
            cls.db_name = self.db_name
            return cls.dispatch( request, *args, **kwargs )

        return HttpResponse('fail')

    def dispatch( self, request, *args, **kwargs ):
        """
        collect the input parameters and store
        if there is a 'type' on the input, then store that and delegate to a new view class
        """
        self.request = request
        self.args = args
        self.kwargs = kwargs
        # logging.warn("KWARGS: " + str(self.kwargs))
        if 'use_view' in self.kwargs and self.use_view == None:
            self.use_view = self.kwargs['use_view']
        return self.delegate( self.use_view, request, *args, **kwargs )




class SearchSummaryView( ListView ):
    """
    return items matching the field provided; do some special stuff for locations and cat'd fields
    """
    template_name = 'fields.html'
    object_type = None
    context_object_name = 'items'
    model = None
    split_objects = ( )

    def get_queryset(self):
        f = str(self.kwargs['field']).lower()
        if f == 'building': f = 'location'
        return self.model.objects.using(self.db_name).values(f, 'id').annotate( num_field=Count(f) ).distinct(f)

    def get_context_data( self, **kwargs ):
        field = str(self.kwargs['field']).lower()
        f = field
        # deal with db inconsistences
        if f == 'building': f = 'location'
        these = {}
        for i in self.object_list:
            if f in i and not i[f] == None:
                if f in self.split_objects:
                    for j in i[f].split(','):
                        if not j in these: these[j] = 0
                        these[j] = these[j] + i['num_field']
                # elif f in ('name'):
                #     these[i[f]] = i
                else:
                    j = i[f]
                    if not j in these: these[j] = 0
                    these[j] = these[j] + i['num_field']

        if field == 'building':
            buildings = {}
            for l in these:
                loc = parse_location( l )
                b = 'unknown'
                if field in loc: b = loc[field]
                if not b in buildings: buildings[b] = these[l]
                buildings[b] = buildings[b] + these[l]
            these = buildings

        d = super( ListView, self ).get_context_data(**kwargs)

        d[self.context_object_name] = []
        for n in sorted(these.iterkeys()):
            i = { 'name': n, 'count': these[n] }
            # logging.error("I " + str(i))
            d[self.context_object_name].append( i )

        # add in headers
        if self.object_type == None or self.object_type == '':
            self.object_type = type(self.model).__name__
        d['meta'] = { 'item_type': self.object_type, 'field': field }
        return d



class SearchResultsView( ListView ):
    template_name = None
    match_filtes = {}
    model = None
    order_by = None
    select_related = None
    
    def get_queryset(self):
        if self.model == None:
            raise Exception, "SearchResultsView requires 'model' definition"
            
        this = {}
        # pull in post args
        try:
            for k,v in self.request.POST.items():
                this[k] = v
        except Exception, e:
            pass
        # pull in from args
        if 'field' in self.kwargs and 'value' in self.kwargs:
            this[self.kwargs['field']] = self.kwargs['value']

        if 'filters' in self.kwargs:
            for k,v in self.kwargs['filters'].items():
                this[k] = v

        # logging.debug("FILTER: " + str(this))

        # create the query object
        qs = self.model.objects.using(self.db_name)

        if not self.select_related == None:
            qs = qs.select_related( self.select_related )

        # filter somewhat
        if len( this.keys() ) > 0:
            search = {}
            for k,v in this.items():
                # logging.warn("K: " + str(k) + ", V: " + str(v) + ", match: " + str(self.match_filters))

                m = 'exact'

                # reassign fields if a def exists
                if k in self.match_filters:
                    # logging.debug(" " + str(k) + " is in match_filters")

                    if 'select_related' in self.match_filters[k]:
                        for a in self.match_filters[k]['select_related']:
                            qs = qs.select_related( a )

                    if 'order_by' in self.match_filters[k]:
                        self.order_by = self.match_filters[k]['order_by']

                    # if self.kwargs['field'] in self.match_filters:
                    if 'filter' in self.match_filters[k]:
                        m = self.match_filters[k]['filter']
                    if 'field' in self.match_filters[k]:
                        k = self.match_filters[k]['field']

                search[k + '__' + m] = v
                # logging.debug(" -> " + str(search))

            logging.info("searching " + str(self.model) + " with " + str(search))
            qs = qs.filter( **search )            

        else:
            logging.warn("doing full " + str(self.model) + " object retrieval")
            qs = qs.all()

        if self.order_by:
            qs = qs.order_by(self.order_by)

        # logging.error("QS: " + str(qs.query))
        return qs

    def get_context_data(self, **kwargs):
        d = super(SearchResultsView,self).get_context_data(**kwargs)
        d['meta'] = { 'item_type': str(self.context_object_name), 'field': str(self.kwargs['field']), 'value': str(self.kwargs['value']) }
        logging.error("D: " + str(d))
        return d



#######################################################################
# Device Views
#######################################################################

class DeviceSearchMenuView( TemplateView ):
    """
    search menu for devices
    """
    template_name = 'device-menu.html'
    def get_context_data( self, **kwargs ):
        d = super( DeviceSearchMenuView, self ).get_context_data(**kwargs)
        d['items'] = ( 'category', 'kind', 'vendor', 'model', 'vlan', 'building' )
        return d


class DeviceSearchSummaryView( SearchSummaryView ):
    model = Device
    object_type = 'Device'
    split_objects = ( 'vlan', 'model' )


class DeviceAllResultsView( ListView ):
    model = Device
    context_object_name = 'devices'
    template_name = None
    def get_queryset( self, **kwargs ):
        return self.model.objects.using(self.db_name).all()

class DeviceSearchResultsView( SearchResultsView ):
    """
    search results for devices
    """
    template_name = 'device.html'
    context_object_name = 'devices'
    model = Device
    match_filters = {
        'vlan': { 'filter': 'exact', 'order_by': 'vlan' },
        'building': { 'field': 'location', 'filter': 'icontains' },
        'location': { 'field': 'location', 'filter': 'icontains' },
        'model': { 'field': 'model', 'filter': 'icontains' },
        'software_version': { 'field': 'software_version', 'filter': 'icontains' },
        'name': { 'filter': 'icontains' }
    }
    order_by = 'name'


class DevicePortsView( ListView ):
    template_name = 'device-ports.html'
    model = PortWithPeer
    context_object_name = 'ports'
    def get_queryset(self):
        # TODO: wrong idi
        if not 'id' in self.kwargs:
            raise Exception
        id = self.kwargs['id']
        return self.model.objects.using(self.db_name).filter( device_id=id ).order_by('if_index')

    def get_context_data(self, **kwargs):        
        this = super(DevicePortsView,self).get_context_data(**kwargs)
        id = self.kwargs['id']
        this['Device'] = Device.objects.using(self.db_name).get( pk=id )
        return this

# class SingleDeviceMixin( SingleObjectMixin ):
#     pk_url_kwarg = 'id'
#     def get_object(self, queryset=None):
#         return Device.objects.using(self.db_name).filter(id=self.pk_url_kwarg)
# 
# 
# class DevicePortListView( DevicePortsView, SingleDeviceMixin ):
#     template_name = 'device-ports.html'
#     def get_context_data(self, **kwargs):
#         c = super( SingleDeviceMixin, self ).get_context_data(**kwargs)
#         # d = super( PortsView, self ).get_context_data(**kwargs)
#         


#######################################################################
# Host Views
#######################################################################


class HostSearchMenuView( TemplateView ):
    """
    search menu for devices
    """
    template_name = 'host-menu.html'
    def get_context_data( self, **kwargs ):
        d = super( HostSearchMenuView, self ).get_context_data(**kwargs)
        # d['items'] = ( 'hostname', 'ip_address', 'mac_address' )
        return d

class HostSearchResultsView( SearchResultsView ):
    """
    search results for host
    """
    template_name = 'host-field.html'
    context_object_name = 'hosts'
    model = Host
    select_related = 'Port'
    match_filters = {
        'vlan': { 'filter': 'exact' },
        'hostname': { 'filter': 'istartswith' },
        'ip_address': { 'filter': 'exact' },
        'mac_address': { 'filter': 'exact' },
        'user': { 'filter': 'icontains' },
        'tap': { 'filter': 'icontains' },
        'admin': { 'filter': 'icontains' },
        'building': { 'field': 'device__location', 'filter': 'icontains', 'select_related': ['device'] },
    }

class HostSearchSummaryView( SearchSummaryView ):
    model = Host
    object_type = 'Host'
    paginate_by = 256

    def get_queryset(self):
        f = str(self.kwargs['field']).lower()
        if f == 'building':
            self.model = Device
            f = 'location'
        return self.model.objects.using(self.db_name).values(f, 'id').annotate( num_field=Count(f) ).distinct(f)
    
        
class HostDetailView( DetailView ):
    template_name = 'host-detail.html'
    template_name_field = 'host'
    def get_object(self):
        return Host.objects.using(self.db_name).select_related('device').select_related('port').get( id=self.kwargs['id'] )
        
        
#######################################################################
# Port Views
#######################################################################

class PortSearchResultsView( SearchResultsView ):
    template_name = 'port-field.html'
    model = Port
    select_related = 'device'
    match_filters = {
        'device': { 'filter': 'startswith', 'field': 'device__name' },
        'vlan': { 'fiter': 'exact' },
    }

class PortDetailView( DetailView ):
    template_name = 'port-detail.html'
    context_object_name = 'port'
    template_name_field = 'port'
    def get_object(self):
        this = Port.objects.using(self.db_name).select_related('device').get( id=self.kwargs['id'] )
        try:
            this.Host = Host.objects.using(self.db_name).get( Port=this.id )
        except Exception, e:
            try:
                this.Host = None
                this.Peer = Peer.objects.using(self.db_name).get( src_port=this.id )
            except Exception, e:
                this.Peer = None
                logging.error("ERROR WITH Peer fetch: " + str(e))
        return this


class IdlePortsSearchResultView( ListView ):
    template_name = 'unused-ports.html'
    model = None
    order_by = None
    select_related = None
    
    def get_queryset(self, *args, **kwargs):
        # create the query object
        qs = Port.objects.using(self.db_name)
        if not self.select_related == None:
            qs = qs.select_related( self.select_related )
        # logging.error("ID:" + str(self.kwargs))
        qs = qs.filter( device=self.kwargs['id'], operational_status=0, is_virtual=0 );
        final = []
        for i in qs:
            # logging.error( "HERE: " + str(i) )
            try:
                p = L1InterfaceArchive.objects.using(self.db_name).filter( id=i.id, operational_status=1 ).latest( 'last_seen' )
                i.last_seen = p.last_seen
            except Exception, e:
                # logging.error("GOT EXCEPTION " + str(e))
                i.last_seen = '! Never'
                pass
            final.append(i)
        return final
        
        
#######################################################################
# Delegation (remctl) Views
#######################################################################

class ProvisionView( View ):
    pass

class StreamingResponse( object ):
    preamble = None
    prefix = ''
    postamble = None
    def __init__(self, generator ):
        self.gen = generator
    def get(self):
        if self.preamble:
            yield self.preamble
        for this in self.gen.run():
            yield self.prefix + str(this)
        if self.postamble:
            yield self.postamble
        return

class Dummy(object):
    i = 0
    t = 2
    def run(self):
        while True:
            yield self.i
            self.i = self.i + 1
            sleep( self.t )
    def close(self):
        pass
        
        
class ProvisionNetView( ProvisionView ):
    args = []
    nc = None   # netconfig remctl object

    remctl_class = None
    
    def create_args( self, request, *args, **kwargs ):
        pass
        
    def get( self, request, *args, **kwargs ):

        self.args = self.create_args( request, *args, **kwargs )
        
        self.nc = self.remctl_class( settings.PROVISION_SERVER, settings.PROVISION_PORT, settings.PROVISION_SERVICE )
        self.nc.args = [ 'swh-b050f3', 'Gi5/3' ]
        self.nc.connect()
        # create a streaming response
        # self.nc = Dummy()
        gen = StreamingResponse( self.nc )
        if request.is_ajax():
            # json
            # ret = { 'some_key': 'some_value '}
            return HttpResponse( json.dumps(ret), mimetype='application/javascript')

        gen.preamble = "<html></body><h1>Response Output</h1><ul>"
        gen.prefix = "<li>"
        gen.postamble = "</ul></body></html>"
        return HttpResponse( gen.get() )
            
    def __del__( self ):
        # super( ProvisionNetView, self ).__del__()
        self.nc.close()


class ProvisionShowPortView( ProvisionNetView ):
    args = [ 'swh-b050f3', 'Gi5/3' ]
    remctl_class = NetShow
    
class ProvisionEditPortView( ProvisionNetView ):
    args = [ ]
    remctl_class = NetEdit
    def create_args( self, request, *args, **kwargs ):
        args = []
        for k in kwargs:
            args[k] = kwargs[k]
        return args
        




