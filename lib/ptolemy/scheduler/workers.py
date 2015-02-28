
from slac_utils.messages import Message
from slac_utils.request import Task
from slac_utils.time import now as now

from uuid import uuid1 as uuid

import logging

def routing_key( msg ):
    parts = []
    for n in ( 'spec', 'group', 'device', 'prefix', 'prefix_len', 'user' ):
        if n in msg.context:
            this = msg.context[n]
            if n == 'device': 
                device_parts = reversed( this.split('.') )
                this = ".".join(device_parts)
            parts.append( n + '.' + this )
    parts.append( 'task_id' + '.' + msg._meta['task_id'] )
    return '.%s.' % '.'.join(parts)


# def create_task( parser, node, spec, task_id=None, user=None ):
def create_task( parser, node, context={}, task_id=None, user=None ):

    # add a task id?
    if task_id == None:
        task_id = str(uuid())

    meta = { 'task_id': task_id, 'user': user }
    
    n = None
    freq = None
    try:
        # get the node
        n = parser.getNode( node )
    except Exception, e:
        raise Exception, 'device %s is not configured for polling' % ( node, )

    try:
        # determine frequency of test, add to meta data for use
        # TODO: hmmm.... what if we don't have spec?
        t,d = parser._delta( parser.getTimeDelta( n, context['spec'] ) )
        meta['frequency'] = t+d
    except:
        pass

    if n and 'group' in n: context['group'] = n['group']

    data = {}
    for k,v in parser.get_options( n ):
        if v:
            for i,j in v.iteritems():
                key = "%s_%s" % (k,i)
                data[key] = j

    msg = Task( 
        meta = meta,
        context = context,
        data = data
    )
    msg.timestamp = now()
    
    # logging.info('msg: ' + str(msg))
    return msg
#     
# def submit( parser, node, spec, queue, task_id=None, user=None, logging_queue=None ):
#     """
#     given the schedule parser, submit the item into the queue, log if supplied
#     """
#     
#     msg = create_task( parser, node, spec, task_id=task_id, user=user )
#     rk = routing_key( msg )
# 
#     logging.info('Scheduling %s:%s' % (node,spec) )
#     if logging_queue and 'task_id' in msg._meta:
#         logging_queue.put( msg, key=msg._meta['task_id'] )
# 
#     # actually submit it!
#     queue.put( msg, key=rk )
#     # logging.warn("+ %s:%s (%s):\t%s" % ( node, spec, rk, msg) )
#     