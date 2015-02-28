from ptolemy.property_control.models import *
from django.db.models import Q, F

import logging

        
class Cando( object ):
    
    def __init__(self, database):
        self.db = database
    
    def get_devices( self ):
        """ return all serial numbers """
        # qs = Q( product__type="PC" ) | Q( product__type="MAC" ) | Q( product__type="AMIGA" ) | Q( product__type="NEXT" ) | Q( product__type="VAX" ) | \
        #          Q( product__type__contains="-WKS" ) | Q( product__type__contains="-SRVR" ) | \
        #          Q( product__type__contains="-XTERM" ) | Q( product__type="INTERGRAPH" ) | \
        #          Q( product__type="FDDIMETER" ) | Q( product__type__contains="XCVR" ) | Q( product__type="ETHERMETER") | Q( product__type="REPEATER" ) | \
        #          Q( product__type="PRINTER" )
        for o in Item.objects.using(self.db).select_related().filter( type="SWITCHING UNIT" ):
            yield o

    # def get_serial_number( self, sn ):
        