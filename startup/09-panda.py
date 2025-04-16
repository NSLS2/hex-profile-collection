file_loading_timer.start_timer(__file__)

import asyncio
import datetime
import json
import time as ttime
import uuid
from enum import Enum
from pathlib import Path
from threading import Thread
from typing import AsyncGenerator, AsyncIterator, Dict, List, Optional

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky import RunEngine
from bluesky.utils import ProgressBarManager
from epics import caget, caput
from ophyd import Component as Cpt
from ophyd import Device, EpicsMotor, EpicsPathSignal, EpicsSignal, EpicsSignalWithRBV
from ophyd_async.core import (
    DEFAULT_TIMEOUT,
    DetectorTrigger,
    DetectorWriter,
    SignalRW,
    TriggerInfo,
)
from ophyd_async.core import AsyncStatus
from ophyd_async.core import StandardDetector
from ophyd_async.fastcs.panda import HDFPanda

# class HEXPandaHDFWriter(PandaHDFWriter):
#     async def open(self, *args, **kwargs):
#         desc = await super().open(*args, **kwargs)
#         # prefix = self._name_provider()
#         for key in desc:
#             if "-counter2-out-" in key:
#                 desc[key]["dtype_str"] = "<i4"
#             else:
#                 desc[key]["dtype_str"] = "<f8"
#         return desc


def connect_to_panda(panda_id):

    print(f"Connecting to Panda {panda_id}...")
    with init_devices():
        panda_path_provider = ProposalNumYMDPathProvider(default_filename_provider)
        panda = HDFPanda(
            f"XF:27ID1-ES{{PANDA:{panda_id}}}:",
            panda_path_provider,
            name=f"panda{panda_id}",
        )

    print("Done.")

    return panda


panda1 = connect_to_panda(1)

file_loading_timer.stop_timer(__file__)
