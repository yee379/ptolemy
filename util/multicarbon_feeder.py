#!/bin/env python

"""
test stupid carbon consistent hashing
"""

from ptolemy.storage.managers import MultiCarbonSupervisor
from slac_utils.messages import Message

import sys

if __name__ == '__main__':

    sup = MultiCarbonSupervisor( None, carbon_instances=[ 
        'net-graphite02.slac.stanford.edu:2004:a',
        'net-graphite02.slac.stanford.edu:2104:b',
        'net-graphite02.slac.stanford.edu:2204:c',
        'net-graphite02.slac.stanford.edu:2304:d',
        'net-graphite02.slac.stanford.edu:2404:e',
        'net-graphite02.slac.stanford.edu:2504:f',
        'net-graphite02.slac.stanford.edu:2604:g',
        'net-graphite02.slac.stanford.edu:2704:h',
        'net-graphite02.slac.stanford.edu:2804:i',
        'net-graphite02.slac.stanford.edu:2904:j',
        'net-graphite02.slac.stanford.edu:3004:k',
        'net-graphite02.slac.stanford.edu:3104:l',
        'net-graphite02.slac.stanford.edu:3204:m',
        'net-graphite02.slac.stanford.edu:3304:n',
        'net-graphite02.slac.stanford.edu:3404:o',
        'net-graphite02.slac.stanford.edu:3504:p',
        'net-graphite02.slac.stanford.edu:3604:q',
        'net-graphite02.slac.stanford.edu:3704:r',
        'net-graphite02.slac.stanford.edu:3804:s',
        'net-graphite02.slac.stanford.edu:3904:t',
        'net-graphite02.slac.stanford.edu:4004:u',
        'net-graphite02.slac.stanford.edu:4104:v',
        'net-graphite02.slac.stanford.edu:4204:w',
        'net-graphite02.slac.stanford.edu:4304:x',
    ], carbon_port_offset=4998 )

    k = sys.argv[1]
    h = sup.get_hash_key( k )
    print "KEY: %s -> %s" % (k,h,)