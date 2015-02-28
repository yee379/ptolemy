
from django.http import HttpResponse

from ptolemy_py.ui.models_sql import Device, Entity, Port, Host, L1InterfaceArchive, Peer, PortWithPeer, HostsOnSubnet

from django.conf import settings

from re import match, search

import logging

from pydot import Node, Edge, Dot, Subgraph

#######################################################################
# Topology Views
#######################################################################

def _servers( f ):
    networks = {}
    # determine hosts on each vlan
    for i in HostsOnSubnet.objects.using('scs_lanmon').all():
        subnet = i.subnet_name
        if subnet == None:
            subnet = 'unknown'
        this_host = i.hostname
        device = i.device
        
        # try to reduce the hostname to something meaningful
        m = []
        if match( r'^(swh|rtr)g?\-', this_host ):
            continue
        elif m.append( match( r'(?P<host>([a-z]|\-)+)\d*', this_host ) ) or m[-1]:
            # this_host = m[-1].group( 'host' )
            pass

        if match( f, device ):
        
            # add to datastructure
            if not device in networks:
                networks[device] = {}
            if not subnet in networks[device]:
                networks[device][subnet] = {}
            if not this_host in networks[device][subnet]:
                networks[device][subnet][this_host] = 0
            networks[device][subnet][this_host] += 1

    # graphviz
    yield 'digraph g {\n'
    yield '  ranksep=0.2;\n'
    yield '  edge[dir=none];\n'
    yield '\n'
    
    for d in networks:
        
        yield ' "'+ str(d) + '" \t[shape=square];\n'

        for s in networks[d]:

            yield ' subgraph "cluster_' + str(s) + '" {\n'
            # yield '  label = "'+str(s)+'";\n'
            # yield '  labelloc = "left";\n'
            # yield '  "' + str(s) + '" [fillcolor="red"];\n'

            yield '  "'+str(s)+'" [shape=rectangle];\n'

            hosts = []
            links = []

            items = sorted(networks[d][s])

            yield '  node[shape=oval];\n'
            for h in items:
                i = '"' + str(h) + '"'
                yield '    ' + str(i) + ';\n';
                hosts.append( i )
                
            yield '  node[shape=none, width=0, height=0];\n'
            for h in items:
                l = '"' + str(s) +'_' + str(h) + '"'
                i = '"' + str(h) + '"'
                yield '    ' + str(l) + '\t[label=""];\n';
                links.append(l)
                yield '      ' + str(l) + ' -> ' + str(i) + ';\n'

            odd = []
            even = []
            for i in xrange(0,len(hosts)):
                if i % 2 == 1:
                    odd.append( hosts[i] )
                else:
                    even.append( hosts[i] )

            # yield '  { rank=same; ' + ' -> '.join([ i for i in links ]) + '; }\n'
            yield '  { rank=same; "' + str(s) + '" -> ' + ' -> '.join([ i for i in links ]) + '; }\n'

            yield '  { rank=min; ' + ' '.join([ str(i) for i in odd ]) + '; }\n'
            yield '  { rank=max; ' + ' '.join([ str(i) for i in even ]) + '; }\n'

            yield ' }\n'
            
            yield '"' + str(d) + '_' + str(s) + '" -> "' + str(s) + '" [style=invis];\n'


            yield '\n'
            

        last = None
        yield ' { rank=same;\n'
        for s in networks[d]:
            this = '"' + str(d) + '_' + str(s) + '"'
            yield '  ' + this + ' \t[style=invis];\n'
            if not last == None:
                yield '  ' + last + ' -> ' + this + ';\n'
            last = this
        yield '}\n\n'

        for s in networks[d]:
            yield '  "'+ str(d) +'" -> "' + str(d) + '_' + str(s) + '";\n'

            

        yield '\n'
        yield '}\n'

    return
    

def server_architecture( request):
    return HttpResponse( _servers( 'rtr-serv03' ) )