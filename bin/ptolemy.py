#!/opt/ptolemy/bin/python

from __future__ import absolute_import

import sys
from os import path as path, environ
import argparse
import traceback

parent = lambda x: path.split(x)[0] if path.isdir(x) else split(path.dirname(x))[0]
app_path = path.dirname( path.realpath(__file__) )

# add ../lib to path; append to first so we dont' pick this up as ptolemy
lib_path = parent( app_path ) + '/lib/'
sys.path = [ lib_path ] + sys.path
# add conf path
conf_path = parent( app_path ) + '/etc/ptolemy/'

from slac_utils.command import execute_command

if __name__ == "__main__":

    CMD_MAP = {    
        'scheduled': {
            'klass': 'ptolemy.scheduler.commands.DistributedScheduled',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'scheduled.yaml' ],
        },
        'schedule': {
            'klass': 'ptolemy.scheduler.commands.Schedule',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'scheduled.yaml' ],
        },
        'polld': {
            'klass': 'ptolemy.poller.commands.Polld',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'polld.yaml' ],
        },
        'poll': {
            'klass': 'ptolemy.poller.commands.Poll',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'polld.yaml' ],
        },
        'polld-cache': {
            'klass': 'ptolemy.poller.commands.DriverCache',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'polld.yaml' ],
        },
        'stored': {
            'klass': 'ptolemy.storage.commands.Stored',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'stored.yaml' ],
        },
        # # 'storage-utils': {
        # #     'klass':    'ptolemy.storage.utils.Stored',
        # #     'conf':     conf_path + 'stored.yaml',
        # # },
        'perfsonar': {
            'klass': 'ptolemy.perfsonar.commands.PerfSONAR',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'perfsonar.yaml' ],
        },
        'watcher': {
            'klass': 'ptolemy.watcher.commands.Watcher',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'watcher.yaml' ],
        },
        'ipam': {
            'klass': 'ptolemy.ipam.commands.IPAM',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'ipam.yaml' ],
        },
        'analyse': {
            'klass': 'ptolemy.analyse.commands.Analyse',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'analyse.yaml' ],
        },
        'profile': {
            'klass': 'ptolemy.profiler.commands.Profiler',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'profiler.yaml' ],
        },
        'property': {
            'klass': 'ptolemy.property_control.commands.Property',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'property.yaml' ],
        },
        'alert': {
            'klass': 'ptolemy.alert.commands.Alert',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'alert.yaml' ],
        },
        'report': {
            'klass': 'ptolemy.report.commands.Report',
            'conf': [ conf_path + 'ptolemy.yaml', conf_path + 'report.yaml' ],
        },
    }

    parser = argparse.ArgumentParser( description='ptolemy monitoring infrastructure', conflict_handler='resolve' ) 
    # allow child commands to overwrite these options
    parser.add_argument( '-v', '--verbose',     help='verbose output',    action='store_true', default=False )
    parser.add_argument( '-V', '--errors_only',     help='non-verbose output',    dest='verbose', action='store_false', required=False )
    parser.add_argument( '-f', '--foreground',  help='run in foreground', action='store_true', default=False )
    
    daemon = parser.add_argument_group( 'daemon settings')
    daemon.add_argument( '--logfile',    help='log to a file',     default=None )
    daemon.add_argument( '--pidfile',    help='pid file',       default=None )
    daemon.add_argument( '--uid',     help='uid to run under',  default=None )
    daemon.add_argument( '--gid',     help='gid to run under',  default=None )
    # daemon.add_argument( '--umask',     help='umask of files',  default=None )

    # execute the command class
    try:
        execute_command( CMD_MAP, parser, *sys.argv )
        sys.exit(0)
        
    except Exception, e:
        print "Err: %s, %s" % (e,traceback.format_exc())
        sys.exit(128)
        