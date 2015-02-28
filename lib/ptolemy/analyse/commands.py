import argparse
from slac_utils.command import CommandDispatcher
from slac_utils.messages import Message

from ptolemy.analyse.telephones import Telephone
from ptolemy.analyse.capacity import Capacity
from ptolemy.analyse.layer1 import Layer1
from ptolemy.analyse.generic import Generic

import logging



class Analyse( CommandDispatcher ):
    """
    Ptolemy Live Network Analysis Tools
    """
    commands = [ Telephone, Capacity, Layer1, Generic ]