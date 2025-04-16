file_loading_timer.start_timer(__file__)


print(f"Loading file {__file__!r} ...")


import asyncio
from dataclasses import dataclass
from enum import Enum

from ophyd import EpicsSignalRO
from ophyd_async.core import (
    DEFAULT_TIMEOUT,
    DetectorTrigger,
    DetectorWriter,
    SignalRW,
    TriggerInfo,
)
from ophyd_async.epics.adkinetix import KinetixDetector
from ophyd_async.epics.adcore import ADHDFWriter


class HEXADHDFWriter(ADHDFWriter):

    async def begin_capture(self):
        await super().begin_capture()
        await self.fileio.swmr_mode.set(False)


class HEXKinetixDetector(KinetixDetector):
    """Override base StandardDetector unstage class to reset into continuous mode after scan/abort"""

    @AsyncStatus.wrap
    async def unstage(self) -> None:
        # Stop data writing.
        await asyncio.gather(self._writer.close(), self._controller.disarm())

        # Set to continuous internal trigger, and start acquiring
        await self.driver.trigger_mode.set("Internal")
        await self.driver.image_mode.set("Continuous")
        await self._controller.arm()


def connect_to_kinetix(kinetix_id):

    print(f"Connecting to kinetix {kinetix_id}...")
    with init_devices():
        kinetix_path_provider = ProposalNumYMDPathProvider(default_filename_provider)
        kinetix = HEXKinetixDetector(
            f"XF:27ID1-BI{{Kinetix-Det:{kinetix_id}}}",
            kinetix_path_provider,
            name=f"kinetix-det{kinetix_id}",
            writer_cls=HEXADHDFWriter,
        )

    print("Done.")

    return kinetix

try:
    kinetix1 = connect_to_kinetix(1)
except Exception as e:
    print(f"Kinetix 1 is unavailable...")

try:
    kinetix3 = connect_to_kinetix(3)
except Exception as e:
    print(f"Kinetix 3 is unavailable...")


file_loading_timer.stop_timer(__file__)
