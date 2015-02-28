import argparse
from slac_utils.command import CommandDispatcher, Command
from ptolemy.ipam.commands import NetDBCommand
from slac_utils.messages import Message

# from ptolemy.ipam.ipam import NetDBCommand
#
# import logging
#
#
# class NetworkDevices( NetDBCommand ):
#     """
#     feeds into store queue all property control stuff from
#     """
#
#     def run( self, *args, **kwargs ):
#         feeder = self.get_mongodb( **kwargs )
#         cando = self.get_cando( **kwargs )
#
#         # kwargs: type='SWITCHING UNIT'
#         for i in cando.get_items( ):
#             this = Message(
#                 meta={
#                     'spec': 'property_control',
#                     'group': 'cando',
#                 },
#                 context={
#                     'pc_number':    i.pc_number,
#                     'serial':       i.serial,
#                 },
#                 data={
#                     'model':        i.model,
#                     'manufacturer': i.manufacturer,
#                 }
#
#             )
#             this.timestamp = i.date()
#             this.type = 'task'
#
#             if this.timestamp:
#                 logging.warn("feeding: %s" % (this,))
#                 for j in feeder.process_task( this, time_delta=None ):
#                     logging.warn("  done" )
#
#         return


class Property( CommandDispatcher ):
    """
    Property Control Integration Tools
    """
    # commands = [ NetworkDevices ]
    commands = []