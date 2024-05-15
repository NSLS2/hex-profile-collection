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
    DirectoryInfo,
    DirectoryProvider,
    HardwareTriggeredFlyable,
    SignalRW,
    TriggerInfo,
    TriggerLogic,
)
from ophyd_async.core.async_status import AsyncStatus
from ophyd_async.core.detector import StandardDetector
from ophyd_async.core.device import DeviceCollector
from ophyd_async.panda.panda import PandA
from ophyd_async.panda.panda_controller import PandaPcapController
from ophyd_async.panda.writers import PandaHDFWriter


# TODO: use the ophyd-async version once released.
# https://github.com/bluesky/ophyd-async/pull/245
class UUIDDirectoryProvider(DirectoryProvider):
    def __init__(self, directory_path, resource_dir="."):
        self._directory_path = directory_path
        self._resource_dir = resource_dir

    def __call__(self):
        return DirectoryInfo(
            root=Path(self._directory_path),
            resource_dir=Path(self._resource_dir),
            prefix=str(uuid.uuid4()),
        )


async def print_children(device):
    for name, obj in dict(device.children()).items():
        print(f"{name}: {await obj.read()}")


class HEXPandaHDFWriter(PandaHDFWriter):
    async def open(self, *args, **kwargs):
        desc = await super().open(*args, **kwargs)
        # prefix = self._name_provider()
        for key in desc:
            if "-counter2-out-" in key:
                desc[key]["dtype_str"] = "<i4"
            else:
                desc[key]["dtype_str"] = "<f8"
        return desc


class FrameType(Enum):
    dark = "dark"
    flat = "flat"
    scan = "scan"


class ScanIDDirectoryProvider(UUIDDirectoryProvider):
    def __init__(self, *args, frame_type: FrameType = FrameType.scan, **kwargs):
        super().__init__(*args, **kwargs)
        self._frame_type = frame_type

    def __call__(self):
        resource_dir = Path(f"scan_{RE.md['scan_id']:05d}_dark_flat")
        prefix = f"{self._frame_type.value}_{uuid.uuid4()}"

        if self._frame_type == FrameType.scan:
            resource_dir = Path(f"scan_{RE.md['scan_id']:05d}")
            prefix = f"{uuid.uuid4()}"

        return DirectoryInfo(
            root=Path(self._directory_path),
            resource_dir=resource_dir,
            prefix=prefix,
        )


def instantiate_panda_async():
    with DeviceCollector():
        panda1_async = PandA("XF:27ID1-ES{PANDA:1}:", name="panda1_async")

    with DeviceCollector():
        # dir_prov = UUIDDirectoryProvider("/nsls2/data/hex/proposals/commissioning/pass-315051/tomography/bluesky_test/panda")
        dir_prov = ScanIDDirectoryProvider(PROPOSAL_DIR)
        writer = HEXPandaHDFWriter(
            "XF:27ID1-ES{PANDA:1}",
            dir_prov,
            lambda: "hex-panda1",
            panda_device=panda1_async,
        )
        print_children(panda1_async)

    return panda1_async, writer


panda1_async, writer = instantiate_panda_async()


class PandATriggerState(str, Enum):
    null = "null"
    preparing = "preparing"
    starting = "starting"
    stopping = "stopping"


class PandATriggerLogic(TriggerLogic[int]):
    def __init__(self):
        self.state = PandATriggerState.null

    def trigger_info(self, value: int) -> TriggerInfo:
        return TriggerInfo(
            num=value, trigger=DetectorTrigger.constant_gate, deadtime=0.1, livetime=0.1
        )

    async def prepare(self, value: int):
        self.state = PandATriggerState.preparing
        return value

    async def start(self):
        self.state = PandATriggerState.starting

    async def stop(self):
        self.state = PandATriggerState.stopping


panda_trigger_logic = PandATriggerLogic()
pcap_controller = PandaPcapController(panda1_async.pcap)

panda_standard_det = StandardDetector(
    pcap_controller, writer, name="panda_standard_det"
)


panda_flyer = HardwareTriggeredFlyable(panda_trigger_logic, [], name="panda_flyer")


def panda_fly(panda_standard_det, num=724):
    yield from bps.stage_all(panda_standard_det, panda_flyer)
    yield from bps.prepare(panda_flyer, num, wait=True)
    yield from bps.prepare(panda_standard_det, panda_flyer.trigger_info, wait=True)

    detector = panda_standard_det
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
            panda_standard_det,
            stream=True,
            return_payload=False,
            name="main_stream",
        )
        yield from bps.sleep(0.01)
    yield from bps.wait(group="complete")
    val = yield from bps.rd(writer.hdf.num_captured)
    print(f"{val = }")
    yield from bps.close_run()

    yield from bps.unstage_all(panda_flyer, panda_standard_det)


class JSONLWriter:
    def __init__(self, filepath):
        self.file = open(filepath, "w")

    def __call__(self, name, doc):
        json.dump({"name": name, "doc": doc}, self.file)
        self.file.write("\n")
        if name == "stop":
            self.file.close()


def now():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


jlw = JSONLWriter(f"/tmp/export-docs-{now()}.json")


file_loading_timer.stop_timer(__file__)
