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
    DetectorControl,
    DetectorTrigger,
    DetectorWriter,
    HardwareTriggeredFlyable,
    SignalRW,
    TriggerInfo,
    TriggerLogic,
)
from ophyd_async.core.async_status import AsyncStatus
from ophyd_async.core.detector import StandardDetector
from ophyd_async.core.device import DeviceCollector
from ophyd_async.panda import HDFPanda

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


panda_trigger_logic = StandardTriggerLogic(trigger_mode=DetectorTrigger.constant_gate)
panda_flyer = HardwareTriggeredFlyable(panda_trigger_logic, [], name="panda_flyer")


def connect_to_panda(panda_id):

    print(f"Connecting to Panda {panda_id}...")
    with DeviceCollector():
        panda_path_provider = ProposalNumYMDPathProvder(default_filename_provider)
        panda = HDFPanda(
            f"XF:27ID1-ES{{PANDA:{panda_id}}}:",
            panda_path_provider,
            name=f"panda{panda_id}",
        )
        # print_children(panda)

    print("Done.")

    return panda


panda1 = connect_to_panda(1)


def panda_fly(panda, num=724):
    yield from bps.stage_all(panda, panda_flyer)
    yield from bps.prepare(panda_flyer, num, wait=True)
    yield from bps.prepare(
        panda, panda_flyer.trigger_logic.trigger_info(num), wait=True
    )

    detector = panda
    # detector.controller.disarm.assert_called_once  # type: ignore

    yield from bps.open_run()

    yield from bps.kickoff(panda_flyer)
    yield from bps.kickoff(detector)

    yield from bps.complete(panda_flyer, wait=True, group="complete")
    yield from bps.complete(detector, wait=True, group="complete")

    # Manually incremenet the index as if a frame was taken
    # detector.writer.index += 1

    done = False
    while not done:
        try:
            yield from bps.wait(group="complete", timeout=0.5)
        except TimeoutError:
            pass
        else:
            done = True
        yield from bps.collect(
            panda,
            # stream=False,
            # return_payload=False,
            name="main_stream",
        )
        yield from bps.sleep(0.01)
    yield from bps.wait(group="complete")
    val = yield from bps.rd(panda.data.num_captured)
    print(f"{val = }")
    yield from bps.close_run()

    yield from bps.unstage_all(panda_flyer, panda)


file_loading_timer.stop_timer(__file__)
