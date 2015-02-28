from django.test import TestCase

from ptolemy_py.storage.storing import StorageManager, PerlPtolemyStorer
from ptolemy_py.storage.storing import Storer

from ptolemy_py.scheduler.models import PollObject

import time

import logging
logging.basicConfig( level=logging.DEBUG )

class StorageManagerTest(TestCase):
    
    def test_init(self):
        man = StorageManager()
        
    def test_start(self):
        man = StorageManager()
        man.start()
        man.terminate()
        self.assertEqual( True, True )

    def test_add_item(self):
        man = StorageManager()
        # q = KombuPollResultsQueue()
        man.start()
        q.put( {'test': 'hello world'} )
        time.sleep(30)
        
class PerlPtolemyStorerTest( TestCase ):
    
    def setUp( self ):
        self.storer = PerlPtolemyStorer()
        self.failUnlessEqual( type(self.storer).__name__, 'PerlPtolemyStorer')
        
    def test_single( self ):
        msg = PollObject( device='test', spec='test2', result={ 'this': 'test' } )
        o = self.storer.process( msg )
        logging.debug("OUT: " + str(o) )
        self.failUnlessEqual( 'result' in o, True )