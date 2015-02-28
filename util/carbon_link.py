import os, sys
sys.path.append('/opt/graphite/webapp')
os.environ['DJANGO_SETTINGS_MODULE'] = 'graphite.settings'

from graphite.carbonlink import CarbonLinkPool

# export PYTHONPATH=/opt/graphite/webapp/:/opt/graphite/webapp/graphite
# export DJANGO_SETTINGS_MODULE=graphite.settings


# net-graphite02.slac.stanford.edu
if __name__ == '__main__':
    hosts = [ "net-graphite02.slac.stanford.edu:7002:a", "net-graphite02.slac.stanford.edu:7102:b", "net-graphite02.slac.stanford.edu:7202:c", "net-graphite02.slac.stanford.edu:7302:d", "net-graphite02.slac.stanford.edu:7402:e", "net-graphite02.slac.stanford.edu:7502:f", "net-graphite02.slac.stanford.edu:7602:g", "net-graphite02.slac.stanford.edu:7702:h", "net-graphite02.slac.stanford.edu:7802:i", "net-graphite02.slac.stanford.edu:7902:j", "net-graphite02.slac.stanford.edu:8002:k", "net-graphite02.slac.stanford.edu:8102:l", "net-graphite02.slac.stanford.edu:8202:m", "net-graphite02.slac.stanford.edu:8302:n", "net-graphite02.slac.stanford.edu:8402:o", "net-graphite02.slac.stanford.edu:8502:p", "net-graphite02.slac.stanford.edu:8602:q", "net-graphite02.slac.stanford.edu:8702:r", "net-graphite02.slac.stanford.edu:8802:s", "net-graphite02.slac.stanford.edu:8902:t", "net-graphite02.slac.stanford.edu:9002:u", "net-graphite02.slac.stanford.edu:9102:v", "net-graphite02.slac.stanford.edu:9202:w", "net-graphite02.slac.stanford.edu:9302:x" ]
    
    k = sys.argv[1]

    # i = int(sys.argv[2])

    instances = []
    for i in hosts:
        j = i.split(':')
        instances.append( (j[0],int(j[1]), j[2]))
    c = CarbonLinkPool(instances, 10)
    d = c.query(k)
    print "auto: %s" % (d,)

    for i in xrange(0,len(hosts)):
        h = hosts[i].split(':')
        print "%s" % (h,)
        instances = []
        instances.append( (h[0], int(h[1]), h[2]) )
    
        c = CarbonLinkPool(instances, 10)
        x = c.query(k)
        if len(x):
            print " %s %s = %s" % (h,i,x,)