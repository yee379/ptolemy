
class Message( dict ):
    """
    object to pass around queues
    """
    def __getattr__(self, key): return self.get(key, None )
    
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    
