from ptolemy.poller.agent import NetSNMP
import multiprocessing
import slac_utils.manager
from ptolemy.queues import QueueFactory
from ptolemy.poller.workers import Gatherer

import logging

def fetch(host):
    c = open('/opt/etc/snmp.community.read' ).read().strip()
    agent = NetSNMP( host, community=c )
    with agent:
        for f,i,v in agent.fetch( [ 'ifAlias' ] ):
            print str(h) + "\t" + str(f) + "\t" + str(i) + "\t" + str(v)
            

class Fetcher(multiprocessing.Process):
    host = None
    agent = None
    def __init__(self,host,**kwargs):
        multiprocessing.Process.__init__(self)
        self.host = host
        self.c = open('/opt/etc/snmp.community.read' ).read().strip()
        self.agent = NetSNMP( host, community=self.c, max_tasks=3 )

    def run(self):
        with self.agent as agent:
            for f,i,v in agent.fetch( [ 'ifAlias' ] ):
                print str(self.host) + ":\t" + str(f) + "\t" + str(i) + "\t" + str(v)

class AgentProcess( slac_utils.manager.Process ):
    agent = None
    def __init__(self,*args,**kwargs):
        super( AgentProcess, self ).__init__(*args,**kwargs)
        self.c = open('/opt/etc/snmp.community.read' ).read().strip()

    def process( self, job, stats={} ):
        host = job['device']
        print "processing: " + str(job)
        self.agent = NetSNMP( job['device'], community=self.c )
        out = { host: {}, 'task_id': job['task_id'] }
        with self.agent as agent:
            for f,i,v in agent.fetch( [ 'sysName','ifAlias' ] ):
                # print str(self.host) + "\t" + str(f) + "\t" + str(i) + "\t" + str(v)
                if not f in out[host]:
                    out[host][f] = {}
                out[host][f][str(i)] = str(v)
        return out


class AgentWorker( slac_utils.manager.Worker ):
    agent = None
    def __init__(self, queue_obj, *args,**kwargs):
        super( AgentWorker, self ).__init__(queue_obj, **kwargs )
        self.c = open('/opt/etc/snmp.community.read' ).read().strip()
        
    def process_task(self, job, stats={} ):
        host = job['device']
        print "working: " + str(job)
        self.agent = NetSNMP( job['device'], community=self.c )
        out = { host: {}, 'task_id': job['task_id'] }
        with self.agent as agent:
            for f,i,v in agent.fetch( ['ifHCOutMulticastPkts', 'ifInDiscards', 'ifInErrors', 'ifHCOutOctets', 'ifHCInOctets', 'ifHCInBroadcastPkts', 'ifHCInMulticastPkts', 'ifConnectorPresent', 'ifHCOutBroadcastPkts', 'ifOutErrors', 'ifName', 'ifOperStatus', 'ifOutDiscards', 'ifHCOutUcastPkts', 'ifHCInUcastPkts', 'ifAdminStatus'] ):
                # print str(self.host) + "\t" + str(f) + "\t" + str(i) + "\t" + str(v)
                if not f in out[host]:
                    out[host][f] = {}
                out[host][f][str(i)] = str(v)
        return out
        
class GathererWorker( AgentWorker ):
    def __init__(self, queue_obj, *args,**kwargs):
        super( GathererWorker, self ).__init__(queue_obj, **kwargs )
        # self.c = open('/opt/etc/snmp.community.read' ).read().strip()
        self.gatherer = Gatherer()
        
    def process_task( self, job, stats={} ):
        return self.gatherer.fetch( job['device'], 'port_stats/generic.yaml' )


def poll_def( hosts ):    
    # using functions
    processes = []
    for h in hosts:
        p = Process( target=fetch, args=( h, ) )
        p.start()
        processes.append(p)
    
    for p in processes:
        p.join()
        p.terminate()
    
def poll_process( hosts ):
    processes = []
    for h in hosts:
        p = Fetcher( h )
        p.start()
        processes.append(p)
        
    for p in processes:
        p.join()
        p.terminate()

def poll_process( queue_obj ):
    processes = []
    for i in xrange( 0, 4 ):
        p = AgentProcess( work_queue=queue_obj.poll_queue(consume=True), results_queue=queue_obj.store_queue(produce=True) )
        p.start()
        processes.append( p )
    for p in processes:
        p.join()
        
def poll_worker( queue_obj ):
    processes = []
    for i in xrange( 0, 4 ):
        p = AgentWorker( queue_obj, work_queue_func='poll_queue', results_queue_func='store_queue' )
        p.start()
        processes.append( p )
    for p in processes:
        p.join()
    
def poll_gatherer( queue_obj ):
    processes = []
    for i in xrange( 0, 4 ):
        p = GathererWorker( queue_obj, work_queue_func='poll_queue', results_queue_func='store_queue' )
        p.start()
        processes.append( p )
    for p in processes:
        p.join()
    
    
if __name__ == '__main__':
    
    logging.basicConfig( level=logging.DEBUG )
    
    hosts = ( 'swh-b050f1', 'swh-b028', 'swh-b901f1', 'rtr-serv03' )

    queue_obj = QueueFactory( host='localhost', port=5672, virtual_host='/ptolemy', user='ptolemy', password='ptolemy' )

    # poll_process( queue_obj )
    # poll_worker( queue_obj )
    poll_gatherer( queue_obj )