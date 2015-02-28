import re
try:
    from lxml import etree
except:
    pass
import logging

class RackWiseData( object ):

    book = None
    none_string = '-'

    function_map = {
        'host': { 'sheet': 'Equipment', 'search_field': 'Name' },
        'rack': { 'sheet': 'Equipment', 'search_field': 'Region', 'match_fields': { 'Region Type': 'RACK' } },
        'pc_number': { 'sheet': 'Equipment', 'search_field': 'Asset ID' },
    }
    
    def __init__(self, file ):
        self.book = file
    
    def _parse( self, worksheet ):

        headers = []
        n = 0
        try:
            for ev, el in etree.iterparse( self.book ):
                if el.tag.endswith( 'Worksheet' ) \
                    and el.get('{urn:schemas-microsoft-com:office:spreadsheet}Name') == worksheet:
                    logging.debug("found worksheet " + str(worksheet))
                    for ev, d in etree.iterwalk( el ):
                        if d.tag.endswith( 'Row' ):
                            logging.debug('N='+str(n))
                            data = {}
                            count = 0
                            for ev, c in etree.iterwalk( d ):
                                if c.tag.endswith( 'Cell' ):
                                    # stupid xml with skipped cols
                                    skip = c.get('{urn:schemas-microsoft-com:office:spreadsheet}Index')
                                    if skip:
                                        # logging.debug(" skip " + str(skip))
                                        count = int(skip)-1
                                    v = None
                                    if n > 0:
                                        v = headers[count]
                                    for ev, i in etree.iterwalk( c ):
                                        if i.tag.endswith( 'Data' ):
                                            # headers
                                            if n == 0:
                                                headers.append( i.text )
                                            else:
                                                logging.debug( '  ' + str(v) + "\t" + str(i.text))
                                                x = i.text
                                                if x == None:
                                                    x = self.none_string
                                                data[v] = x
                                    count = count + 1
                            if len(data.keys()):
                                yield data
                            n = n + 1
        except:
            pass
        return

    def parse( self, worksheet, **kwargs ):
        # map kwargs
        field = None
        regex = None
        for k,v in kwargs.iteritems():
            # TODO support more than one pair
            field = k
            regex = v
        for item in self._parse( worksheet=worksheet ):
            if regex == None:
                yield item
            if field in item and not item[field] == None:
                if regex.search( item[field] ):
                    yield item
        return

    def get( self, type, regex=None ):
        if type in self.function_map:
            m = self.function_map[type]
            matches = {}
            if 'match_fields' in m:
                matches = m['match_fields']
            for item in self.parse( m['sheet'], m['search_field'], regex=regex ):
                ok = True
                for k,v in matches.iteritems():
                    if not item[k] == v:
                        ok = False
                        continue
                if ok:
                    yield item
        return

    def __iter__(self):
        for item in self.parse( 'Equipment' ):
            yield item
        return