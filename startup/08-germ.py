file_loading_timer.start_timer(__file__)

import datetime
import os
import uuid
from collections import deque
from enum import Enum
from pathlib import Path

import h5py
import numpy as np
from event_model import compose_resource
from hextools.germ.ophyd import GeRMDetectorHDF5
from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, Kind, Signal
from ophyd.sim import new_uid
from ophyd.status import SubscriptionStatus
from PIL import Image

# TODO: add Tiff support in Caproto IOC.


class HEXGeRMDetectorHDF5(GeRMDetectorHDF5):
    """HEX-specific ophyd class for GeRM detector producing HDF5 files."""
    # threshold = Cpt(EpicsSignalRO, ".THRSH")  # the scan fails with this component enabled.

    def stage(self):
        self._root_dir = str(
            Path(
                "/nsls2/data/hex/proposals",
                RE.md["cycle"],
                # "commissioning",
                RE.md["data_session"],
                # "pass-314022",
                "assets",
                "GeRM",
            )
        )
        return super().stage()

    def stop(self, *, success=False):
        # TODO: see why it's not called by RE on RE.stop()
        ret = super().stop(success=success)
        print("\n!!! Should stop now !!!\n")
        self.count.put("Done")
        return ret


# Intialize the GeRM detector ophyd object
# germ_detector = HEXGeRMDetectorHDF5("XF:27ID1-ES{GeRM-Det:1}", name="GeRM", root_dir="/nsls2/data/hex/assets/germ/")
germ_detector = HEXGeRMDetectorHDF5(
    "XF:27ID1-ES{GeRM-Det:1}",
    name="GeRM",
    root_dir="PLACEHOLDER",
)
germ_detector.frame_shape.kind = Kind.omitted

file_loading_timer.stop_timer(__file__)
