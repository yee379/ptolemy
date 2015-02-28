###
# script to query for all access ports of a specific type (farm in this case)
# then query graphite/carbon for throughput information for each and do a sum
# better suited to map reduce, but given backend probably isn't worth while
###
from urllib2 import urlopen
import json

import logging

PTOLEMY_WEB='http://network.slac.stanford.edu'

def get_access_ports( group='scientific computing' ):
    group = group.replace(' ', '%20')
    r = urlopen( '%s/api/ports/type.json?group=%s' % (PTOLEMY_WEB,group))
    return json.load(r)   
    
def get_traffic( device, physical_port, frm, to, summary='1h', metric='port.util.out' ):
    physical_port = physical_port.replace('/','.')
    url = '%s/stats.raw/%s/%s/%s?from=%s&until=%s&summarize=%s,avg' % (PTOLEMY_WEB,metric,device,physical_port,frm,to,summary)
    r = urlopen( url ).read().strip()
    _pre, _tmp, _data = r.partition('|')
    _pre = _pre.split(',')
    # logging.error("pre: %s" % (_pre[0],_pre[1],_pre[2],))
    data = []
    for i in _data.split(','):
        v = 0.0
        try:
            v = float(i)
        except:
            pass
        data.append(v)
    # logging.error("URL %s -> %s: %s" % (url,r,data))
    # data array, start, end, step (epoch)
    return data, int(_pre[1]), int(_pre[2]), int(_pre[3])
    
if __name__ == "__main__":

    group='scientific computing'
    start='20131110'
    end='20131118'

    data = []
    s = None
    e = None
    step = None

    ports = get_access_ports( group=group )
    # logging.error("number of ports: %s" % (len(ports),))
    for n,p in enumerate(ports):
        try:
            d, s, e, step = get_traffic( p['device'], p['physical_port'], start, end, summary='1min' )
            # logging.error( "P: %s \t-> %s" % (p,d))
            for i,v in enumerate(d):
                try:
                    data[i] = data[i] + v
                except:
                    data.append(v) # hmmm

            # logging.error("%s\t%s" % (p,data))
            logging.error('%s/%s %s' % (n,len(ports),len(data)))
        except Exception,e:
            logging.error("Err: %s: %s" % (p,e))

    for d in data:
        print("%s\t%s" % (s,d,))
        s = s + step
