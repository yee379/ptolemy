#!/bin/env python

# script to take in some input and dump it into mongo db

from ptolemy.storage.workers import MongoStorer
import fileinput
import logging
from datetime import datetime, timedelta
from time import time

logging.basicConfig( level=logging.DEBUG )

FEEDER = MongoStorer( None, mongo_host='localhost', mongo_port=27017 )

headers = []

now = int(time())

for i in fileinput.input():
    a = [ l.strip() for l in i.split('|') ] 
    this = {
        'spec':     'asset',
        'group':    'lifecycle',
        'timestamp': now,
        '_meta': {
          'key_name':   [ 'model' ],
          'key':        'asset.lifecycle',
        },
        'data': {
        }
    }
    # populate headers
    if len(headers) == 0:
        for n in xrange(0,len(a)):
            headers.append( a[n] )
        logging.info("found headers: %s" % headers )
    else:
        for n in xrange(0,len(a)):
            if a[n] == 'NULL':
                a[n] = None
            
            if headers[n] == 'type':
                a[n] = a[n].lower()
            elif headers[n] in ( 'end_of_sale', 'end_of_support' ) and not a[n] == None:
                a[n] = datetime.strptime( a[n],'%Y-%m-%d')
            elif headers[n] in ( 'list_price', ) and not a[n] == None:
                a[n] = float( a[n] )
            
            if not headers[n] == '':
                this[headers[n]] = a[n]
            
        logging.info("%s" % this)
        for i in FEEDER.process_task( this, time_delta=timedelta( days=3 ) ):
            pass
        
    