from django.views.generic import TemplateView
from ptolemy_py.ui.views import *
from django.utils.datastructures import SortedDict

from django.template import Context, Template, loader

# superset the json api's for exhibit
from ptolemy_py.ui.views_api import *
from django.utils.decorators import classonlymethod

from texttable import Texttable

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
        ( 'software_version', { 'label': 'sw_version(s)'} ),
        ( 'category', {} ),
        ( 'kind', {} ),
        ( 'serial', {} ),
        ( 'vlan', { 'label': 'vlans' } ),
        # ( 'building', {} ),
        ( 'location', {} ),
        ( 'last_seen', {} ),
        ( 'uptime', { 'label': 'uptime' } )
    ])

}


class Table( Texttable ):
    """
    inherited texttable to allow tsv and csv outputs
    """
    TABLE = 0
    CSV = 1
    TSV = 2
    
    def draw(self, format=None):

        if format == None:
            format = self.TABLE

        if not self._header and not self._rows:
            return
        self._compute_cols_width()
        self._check_align()
        out = ""
        if format == self.TABLE and self._has_border():
            out += self._hline()
        if self._header:
            out += self._draw_line(self._header, isheader=True, format=format )
            if self._has_header():
                if format == self.TABLE:
                    out += self._hline_header()
                else:
                    out += "\n"
        length = 0
        for row in self._rows:
            length += 1
            out += self._draw_line(row, format=format )
            if format == self.TABLE:
                if self._has_hlines() and length < len(self._rows):
                    out += self._hline()
            else:
                out += "\n"
        if format == self.TABLE and self._has_border():
            out += self._hline()
        return out[:-1]

    def _draw_line(self, line, isheader=False, format=None ):
        if format == self.TABLE:
            line = self._splitit(line, isheader)
            space = " "
            out  = ""
            for i in range(len(line[0])):
                if self._has_border():
                    out += "%s " % self._char_vert
                length = 0
                for cell, width, align in zip(line, self._width, self._align):
                    length += 1
                    cell_line = cell[i]
                    fill = width - len(cell_line)
                    if isheader:
                        align = "c"
                    if align == "r":
                        out += "%s " % (fill * space + cell_line)
                    elif align == "c":
                        out += "%s " % (fill/2 * space + cell_line \
                                + (fill/2 + fill%2) * space)
                    else:
                        out += "%s " % (cell_line + fill * space)
                    if length < len(line):
                        out += "%s " % [space, self._char_vert][self._has_vlines()]
                out += "%s\n" % ['', self._char_vert][self._has_border()]
            return out

        out = ""
        delim = " "
        if format == self.CSV:
            delim = ','
        elif format == self.TSV:
            delim = "\t"
        if isheader:
            out += '# '
        for i in xrange(len(line)):
            out += str(line[i]) 
            if i < len(line) - 1:
                out += delim
        return out

    
# exhibit basically returns exactly the same view each time, but with a differing json call
class TableMixin( object ):
    db_name = 'scs_lanmon'

    # where to point for the api calls for teh json data
    facets = SortedDict([]) # key = facet name, value = selected items within facet
    columns = SortedDict([])
    sort_column = 0
    
    mapping = {
        'fields': { 'field': None, 'default': None },
        'header': { 'field': 'label', 'default': None },
        'type': { 'field': 'type', 'default': 'a' },
        'halign': { 'field': 'halign', 'default': 'l' },
        'valign': { 'field': 'valign', 'default': 'm' },
    }
    
    
    def parse_meta( self, columns ):
        meta = {}
        cols = []
        for i in columns:
            if i in self.columns:
                for m, data in self.mapping.items():
                    v = self.mapping[m]['default']
                    if v == None:
                        v = i
                    f = self.mapping[m]['field']
                    
                    if f in self.columns[i]:
                        v = self.columns[i][f]
                    
                    if not m in meta:
                        meta[m] = []
                    meta[m].append( v )
                    
                    # add colum
            cols.append( i )
                    
        # logging.error( str(meta) )
        return meta, cols
    
    # def parse_filters(self, **kwargs):
    #     return **kwargs
    
    def render(self, filter, width=132, columns=[], format=None ):
        """
        format may be table, tsv, csv
        """
        if len(columns) == 0:
            for c in self.columns:
                columns.append(c)

        meta, cols = self.parse_meta( columns )

        table = Table( max_width=width )
        table.header( meta['header'] )
        table.set_cols_dtype( meta['type'] )
        table.set_cols_align( meta['halign'] )
        table.set_cols_valign( meta['valign'] )

        # logging.error("KWARGS: " + str(filter))
        # self.kwargs = self.parse_filters( **kwargs )
        self.kwargs = filter

        for i in self.get_queryset( ):
            this = []
            for c in cols:
                this.append( getattr(i,c) )
            # print str(this)
            table.add_row( this )
        
        if format == 'tsv':
            format = Table.TSV
        elif format == 'csv':
            format = Table.CSV
            
        print table.draw( format=format )
        
        
class CmdLineDeviceView( DeviceSearchResultsView, TableMixin ):
    facets = standard_facets['device']
    columns = standard_columns['device']

    
class CmdLineDevicePortsView( TableMixin ):
    facets = standard_facets['port']
    columns = standard_columns['port']
    sort_column = 1

class CmdLineIdlePortsView( TableMixin ):
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


class CmdLineHostSearchView( TableMixin ):
    facets = standard_facets['host']
    columns = standard_columns['host']
    

class CmdLinePortSearchView( TableMixin ):
    facets = standard_facets['port']
    columns = standard_columns['port']
    

