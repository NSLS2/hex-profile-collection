file_loading_timer.start_timer(__file__)


import ophyd
from ophyd.areadetector import (AreaDetector, 
                                ImagePlugin,
                                TIFFPlugin, 
                                StatsPlugin, 
                                ProcessPlugin, 
                                ROIPlugin, 
                                TransformPlugin,
                                OverlayPlugin,
                                CamBase)

from ophyd.areadetector.filestore_mixins import (FileStoreTIFFIterativeWrite,
                                                 FileStoreHDF5IterativeWrite,
                                                 FileStoreTIFFSquashing,
                                                 FileStoreIterativeWrite,
                                                 FileStoreTIFF,
                                                 FileStoreBase
                                                 )


from ophyd import Component as Cpt, Kind
from ophyd.status import SubscriptionStatus

from bluesky import RunEngine
from bluesky.plans import count

from ophyd import Signal, EpicsSignal, EpicsSignalRO
from nslsii.ad33 import SingleTriggerV33, StatsPluginV33
from ophyd.areadetector import (EpicsSignalWithRBV as SignalWithRBV)

from ophyd.device import BlueskyInterface, Device
from ophyd.device import DeviceStatus


# TODO: uncomment once the databroker/mongo server is available, and remove the RE instantiation calls in 02-bluesky.py.
# nslsii.configure_base(get_ipython().user_ns, "hex")
RE = RunEngine({})

from bluesky.callbacks.best_effort import BestEffortCallback
import bluesky.plans as bp

bec = BestEffortCallback()
RE.subscribe(bec)

file_loading_timer.stop_timer(__file__)
