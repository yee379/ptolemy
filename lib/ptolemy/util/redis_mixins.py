from string import Template
import redis


class ZStoreMixin( object ):
    """
    simple mixin to provide a time based scoreboard for entries
    
    synopsis: connect() to the redis instance. then add() the anon array of items 
    """
    
    
    def connect_redis( self, string ):
        
        server, _tmp, port = string.partition(':')
        # logging.error("SERVER: %s" % (server,))
        self.redis = redis.StrictRedis( host=server, port=int(port), db=0 )
        # reduce pingpongs
        self.pipe = self.redis.pipeline()
        
    def zstore_add( self, key, epoch, anon_array, key_format ):
        t = Template(key_format)
        # logging.error("TEMPLATE: %s" % t)
        for d in anon_array:
            v = t.substitute(d)
            # logging.error("v: %s " % (v,))
            self.pipe.zadd( key, epoch, v )
        for i,v in enumerate(self.pipe.execute()):
            # if v == 1, then it's a new entry, otherwise if v == 0, it already existed
            d = anon_array[i]
            yield True if v == 1 else False, d
        return
    
    def zstore_expire( self, key, until ):
        for i in self.redis.zrangebyscore( key, 0, until ):
            self.pipe.zrem( key, i )
            yield i
        self.pipe.execute()
        return
        
