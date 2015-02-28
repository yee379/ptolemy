from collections import defaultdict
import logging
from pprint import pprint

def tree(): return defaultdict(tree)
def dicts(t): return {k: dicts(t[k]) for k in t}

def walk_to( node, tree, depth=0 ):
    pre = ' '*depth
    logging.error("%swalk to %s" % (pre,node))
    for k in tree:
        logging.error("%s k=%s" % (pre,k))
        if k == node:
            logging.error("%s   found %s! %s" % (pre,node,tree[node]))
            return tree[node]
        else:
            w = walk_to( node, tree[k], depth=depth+1 )
            logging.error("%s  w %s" %(pre,w))
            if w is not None:
                logging.error("%s   out %s" % (pre,w))
                return w
    return None

def attach( node, parent, tree ):
    logging.error("add %s at %s" % (node,parent))
    t = walk_to( parent, tree )
    if t == None:
        tree[node]
    else:
        t[node]
    logging.error("\n")

if __name__ == '__main__':

    # topology = tree()
    # topology['one']['two']
    # topology['two']['one']
    # topology['two']['three']
    # 
    # logging.error("%s" % (pprint(dicts(topology))))


    topology = tree()
    # attach( 'one', None, topology )
    # attach( 'two', None, topology )        
    # attach( 'three', 'one', topology )        
    # attach( 'four', 'three', topology )        
    # attach( 'five', 'four', topology )
    # attach( 'six', 'five', topology )        
    # attach( 'seven', 'six', topology )        
    # attach( 'eight', 'seven', topology )
    # attach( 'ten', 'seven', topology )        

    attach( '1', None, topology )
    attach( '10', '1', topology )
    attach( '11', '1', topology )
    attach( '12', '1', topology )
    attach( '2', None, topology )
    attach( '20', '2', topology )
    attach( '200', '20', topology )
    attach( '201', '20', topology )    
    attach( '301', '30', topology )    
    
    logging.error("%s" % (pprint(dicts(topology))))
