file_loading_timer.start_timer(__file__)


import asyncio
from dataclasses import dataclass
from enum import Enum

from ophyd import EpicsSignalRO
from ophyd_async.core import (
    DEFAULT_TIMEOUT,
    DetectorTrigger,
    DetectorWriter,
    init_devices,
    SignalRW,
    TriggerInfo,
)
from ophyd_async.core import AsyncStatus
from ophyd_async.core import StandardDetector

HEX_PROPOSAL_DIR_ROOT = "/nsls2/data/hex/proposals"


class ScanType(Enum):
    tomo_dark_flat = "tomo_dark_flat"
    tomo_flyscan = "tomo_flyscan"
    edxd = "edxd"


class TomoFrameType(Enum):
    dark = "dark"
    flat = "flat"
    proj = "proj"


async def print_children(device):
    for name, obj in dict(device.children()).items():
        print(f"{name}: {await obj.read()}")


file_loading_timer.stop_timer(__file__)
