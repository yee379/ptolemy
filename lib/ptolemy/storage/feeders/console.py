from ptolemy.storage.feeders import Feeder
from ptolemy.storage.commands import StorageCommand
from slac_utils.command import DefaultList

class ConsoleStorer( Feeder ):
    """
    dumps the data out to screen
    """
    agent = 'console'
    def save( self, time, meta, context, data, time_delta ):
        # print( "+ %s meta=%s\tcontext=%s:\t%s" % (time, meta, context, data))
        print( "+ %s\tc=%s:\t%s" % (time, context, data))

class Console( StorageCommand ):
    """
    storage dumper to console
    """
    worker = ConsoleStorer
    
    @classmethod
    def create_parser( cls, parser, settings, parents=[] ):

        super( Console, cls ).create_parser( parser, settings, parents=parents )
        parser.add_argument( '-p', '--pool', help='pool name', default=settings.POOL )
        parser.add_argument( '-k', '--keys', help='key name', action='append', default=DefaultList(settings.KEYS) )

    def pre_run( self, *args, **kwargs ):
        # always run in foreground
        kwargs['foreground'] = True
        return args, kwargs