file_loading_timer.start_timer(__file__)


print(f"Loading file {__file__!r} ...")


import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from enum import Enum

from ophyd import EpicsSignalRO
from ophyd_async.core import (
    DEFAULT_TIMEOUT,
    AsyncStatus,
    DetectorTrigger,
    SignalRW,
    TriggerInfo,
    init_devices,
    observe_value,
    wait_for_value,
    SignalR,
    PathProvider,
    NotConnectedError
)
from typing import Annotated as A
from ophyd_async.epics.core import stop_busy_record, PvSuffix
from ophyd_async.epics.adcore import (
    ADAcquireLogic,
    ADBaseDataType,
    ADBaseIO,
    ADHDFDataLogic,
    ADMultipartDataLogic,
    ADWriterFactory,
    AreaDetector,
    NDPluginBaseIO,
)
from ophyd_async.epics.core import PvSuffix, epics_signal_rw_rbv
from ophyd_async.epics.adkinetix import KinetixDetector
from bluesky.protocols import StreamAsset


# class NDFileHDF5IOWithQueueFree(NDFileHDFIO):
#     queue_free: A[SignalR[int], PvSuffix("QueueFree")]


# class HEXADHDFWriter(ADHDFWriter):

#     async def _begin_capture(self, name: str):
#         await super()._begin_capture(name)
#         await self.fileio.swmr_mode.set(False)

#     async def collect_stream_docs(
#         self, name: str, indices_written: int
#     ) -> AsyncIterator[StreamAsset]:
#         # TODO: fail if we get dropped frames
#         if self._composer is None:
#             msg = f"open() not called on {self}"
#             raise RuntimeError(msg)
#         # TODO: Re-enable flush now once we figure out why it occasionally locks the HDF plugin
#         # await self.fileio.flush_now.set(True)
#         # await wait_for_value(self.fileio.flush_now, False, timeout=DEFAULT_TIMEOUT)
#         for doc in self._composer.make_stream_docs(indices_written):
#             yield doc


#     @classmethod
#     def with_io(
#         cls: type['HEXADHDFWriter'],
#         prefix: str,
#         path_provider: PathProvider,
#         dataset_source: NDArrayBaseIO | None = None,
#         fileio_suffix: str | None = None,
#         plugins: dict[str, NDPluginBaseIO] | None = None,
#     ) -> 'HEXADHDFWriter':

#         fileio = NDFileHDF5IOWithQueueFree(prefix + (fileio_suffix or cls.default_suffix))
#         dataset_describer = ADBaseDatasetDescriber(dataset_source or fileio)

#         writer = cls(fileio, path_provider, dataset_describer, plugins=plugins)
#         return writer

#     async def observe_indices_written(
#         self, timeout: float
#     ) -> AsyncGenerator[int, None]:
#         """Wait until a specific index is ready to be collected."""
#         while self._capture_status is not None:
#             try:
#                 async for num_captured in observe_value(self.fileio.num_captured, timeout):
#                     print(f"Observed num_captured: {num_captured}")
#                     yield num_captured // self._exposures_per_event
#             except TimeoutError as e:
#                 if self._capture_status is None:
#                     break
#                 queue_size, queue_free = await asyncio.gather(
#                     self.fileio.queue_size.get_value(),
#                     self.fileio.queue_free.get_value(),
#                 )
#                 if queue_size != queue_free:
#                     print(f"Queue size: {queue_size}, Queue free: {queue_free}")
#                 else:
#                     raise TimeoutError(str(e)) from e

class HEXKinetixDetector(KinetixDetector):
    """Override base StandardDetector unstage class to reset into continuous mode after scan/abort"""

    @AsyncStatus.wrap
    async def unstage(self) -> None:
        # Stop data writing.
        super().unstage()

        # # Set to continuous internal trigger, and start acquiring
        # await self.driver.trigger_mode.set("Internal")
        # await self.driver.image_mode.set("Continuous")
        # await self.driver.acquire.set(True)


def connect_to_kinetix(kinetix_id):

    print(f"Connecting to kinetix {kinetix_id}...")
    with init_devices(mock=RUNNING_IN_NSLS2_CI, timeout=1):
        kinetix_path_provider = NSLS2PathProvider(RE.md, default_filename_provider)
        kinetix = HEXKinetixDetector(
            f"XF:27ID1-BI{{Kinetix-Det:{kinetix_id}}}",
            ADWriterFactory.hdf(kinetix_path_provider),
            name=f"kinetix-det{kinetix_id}",
        )

    print("Done.")

    return kinetix


try:
    kinetix1 = connect_to_kinetix(1)
except NotConnectedError as e:
    print(f"Kinetix 1 is unavailable...")

try:
    kinetix3 = connect_to_kinetix(3)
except NotConnectedError as e:
    print(f"Kinetix 3 is unavailable...")


file_loading_timer.stop_timer(__file__)
