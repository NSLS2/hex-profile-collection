from ophyd.signal import EpicsSignalBase

EpicsSignalBase.set_defaults(timeout=10, connection_timeout=10)  # new style


import sys
import logging

import bluesky

import matplotlib
from IPython import get_ipython

import matplotlib.pyplot


# Import matplotlib and put it in interactive mode.
import matplotlib.pyplot as plt

plt.ion()
