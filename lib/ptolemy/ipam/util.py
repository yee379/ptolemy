from ConfigParser import ConfigParser, NoOptionError
import re

import logging

class Categoriser( object ):
    """
    object that takes in some fields and determines relevant mappings to appropriate devices
    """
    def __init__(self, type_file=None, group_file=None, category_file=None ):
        self.types = ConfigParser()
        self.groups = ConfigParser()
        self.categories = ConfigParser()
        self.types.read( type_file )
        self.groups.read( group_file )
        self.categories.read( category_file )
    
    def match( self, config_parser, name, field='name' ):
        matched = {}
        for t in config_parser.sections():
            # logging.warn("section " + str(t))
            try:
                for i in config_parser.get( t, field ).split(','):
                    # logging.warn("  comparing against: " + str(i) )
                    if re.search( i.strip(), name ):
                        matched[t] = 1
            except NoOptionError, e:
                pass

        # logging.warn("" + str(name) + ", matched " + str(matched) )
        # TODO: support more than one match?
        res = matched.keys()
        return res
        # if len(res) == 1:
        #     return res[-1]
        # return None
    
    def get( self, name ):
        """
        iterates through type, group and category and spits out the string that matches for each
        """
        # self.groups, self.categories 
        # for i in ( self.types ):
        t = self.match( self.types, name, 'name' )
        g = self.match( self.groups, name, 'name' )
        # remove common elements
        c = list( set(self.match( self.categories, name, 'name' )) ^ set(self.match( self.categories, name, 'exclude' ) ) )
        if len(c) == 0:
            c.append( 'other' )
        return t, g, c