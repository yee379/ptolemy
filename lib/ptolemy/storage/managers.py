from uuid import uuid1 as uuid

from ptolemy.queues import QueueFactory
from slac_utils.managers import Manager
from slac_utils.messages import Message

from slac_utils.queues import END_MARKER

import gc

import logging
import sys

class StorageManager( Manager ):
    worker = None
    queue_factory = QueueFactory
                
    work_queue_func = 'store'
    results_queue_func = None
    logging_queue_func = None
                
    proc_name = 'ptolemy stored manager'
    min_workers = 1

    # generate unique id for this pool
    uuid = uuid()

    def reload(self,*args,**kwargs):
        self.working = False

    def create_worker(self,job,**options):
        # merge options
        options['work_queue_func'] = self.work_queue_func
        options['results_queue_func'] = self.results_queue_func
        options['logging_queue_func'] = self.logging_queue_func
        options['max_tasks'] = self.max_tasks_per_worker

        # stats
        # options['stats_host'] = kwargs['stats_host']
        # options['stats_port'] = kwargs['stats_port']
                    
        # ensure we don't steal messages from someone else, so we create unique pools for this task
        if 'pool' in options:
          self.uuid = options['pool']
        name = self.__class__.__name__
        options['pool'] = "%s.%s" % (name,self.uuid)
                    
        # logging.error("OPTIONS: " + str(options))
        return self.worker( self.queue_factory_obj, **options )


class StorageManagerFactory( object ):
    
    
    def get( self, agent, manager_name=None, **kwargs ):
        
        # logging.error("KWARGS: %s" % kwargs )
        class StorageManager( Manager ):
            worker = agent
            queue_factory = QueueFactory
            work_queue_func = 'store'
            results_queue_func = None
            logging_queue_func = None
            
            # logging.error("AGENT: %s " % (agent,))
            proc_name = manager_name if manager_name else 'ptolemy stored %s manager' % ( agent.__name__.replace('Storer','').lower(), )
            if not 'min_workers' in kwargs:
                kwargs['min_workers'] = 1
            min_workers = kwargs['min_workers']

            # generate unique id for this pool
            uuid = uuid()

            def create_worker(self,job,**kwargs):
                # logging.error("FACT KWARGS: %s" % (kwargs,))
                # override default options if we have input
                options = kwargs.copy()
                
                # sort the keys so they are same across different instances
                options['keys'].sort()
                
                # add queues etc.
                options['work_queue_func'] = self.work_queue_func
                options['results_queue_func'] = self.results_queue_func
                options['logging_queue_func'] = self.logging_queue_func
                options['max_tasks'] = self.max_tasks_per_worker
                # stats
                # options['stats_host'] = kwargs['stats_host']
                # options['stats_port'] = kwargs['stats_port']
                    
                # ensure we don't steal messages from someone else, so we create unique pools for this task
                if 'pool' in options:
                  self.uuid = options['pool']
                options['pool'] = "%s" % (self.uuid,)
                    
                # logging.error("    OPTIONS: " + str(options))
                return self.worker( self.queue_factory_obj, **options )
                
        return StorageManager



