file_loading_timer.start_timer(__file__)


print(f"Loading file {__file__!r} ...")


import asyncio
from dataclasses import dataclass
from enum import Enum

from ophyd import EpicsSignalRO
from ophyd_async.core import (
    DEFAULT_TIMEOUT,
    DetectorControl,
    DetectorTrigger,
    DetectorWriter,
    DeviceCollector,
    HardwareTriggeredFlyable,
    ShapeProvider,
    SignalRW,
    TriggerInfo,
    TriggerLogic,
)
from ophyd_async.core.async_status import AsyncStatus
from ophyd_async.core.detector import StandardDetector
from ophyd_async.core.device import DeviceCollector
from ophyd_async.epics.areadetector.drivers.kinetix_driver import KinetixReadoutMode
from ophyd_async.epics.areadetector.kinetix import KinetixDetector

kinetix_trigger_logic = StandardTriggerLogic()


def connect_to_kinetix(kinetix_id):

    print(f"Connecting to kinetix {kinetix_id}...")
    with DeviceCollector():
        kinetix_path_provider = ProposalNumYMDPathProvder(default_filename_provider)
        kinetix = KinetixDetector(
            f"XF:27ID1-BI{{Kinetix-Det:{kinetix_id}}}",
            kinetix_path_provider,
            name=f"kinetix-det{kinetix_id}",
        )
        print_children(kinetix)

    print("Done.")

    return kinetix


kinetix1 = connect_to_kinetix(1)

sd.baseline.append(kinetix1.drv.acquire_time)
RE.preprocessors.append(sd)


# TODO: add as a new component into ophyd-async.
# kinetix_hdf_status = EpicsSignalRO(
#     "XF:27ID1-BI{Kinetix-Det:1}HDF1:WriteFile_RBV",
#     name="kinetix_hdf_status",
#     string=True,
# )


kinetix_flyer = HardwareTriggeredFlyable(
    kinetix_trigger_logic, [], name="kinetix_flyer"
)


def kinetix_stage(kinetix_detector):
    yield from bps.stage(kinetix_detector)
    yield from bps.sleep(5)


def inner_kinetix_collect(kinetix_detector):

    yield from bps.kickoff(kinetix_flyer)
    yield from bps.kickoff(kinetix_detector)

    yield from bps.complete(kinetix_flyer, wait=True, group="complete")
    yield from bps.complete(kinetix_detector, wait=True, group="complete")

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
            kinetix_detector,
            # stream=True,
            # return_payload=False,
            name=f"{kinetix_detector.name}_stream",
        )
        yield from bps.sleep(0.01)

    yield from bps.wait(group="complete")
    val = yield from bps.rd(kinetix_writer.hdf.num_captured)
    print(f"{val = }")


def kinetix_collect(kinetix_detector, num=10, exposure_time=0.1, software_trigger=True):

    kinetix_exp_setup = StandardTriggerSetup(
        num_images=num, exposure_time=exposure_time, software_trigger=software_trigger
    )

    yield from bps.open_run()

    yield from bps.stage_all(kinetix_detector, kinetix_flyer)

    yield from bps.prepare(kinetix_flyer, kinetix_exp_setup, wait=True)
    yield from bps.prepare(kinetix_detector, kinetix_flyer.trigger_info, wait=True)

    yield from inner_kinetix_collect()

    yield from bps.unstage_all(kinetix_flyer, kinetix_detector)

    yield from bps.close_run()


def _kinetix_collect_dark_flat(
    kinetix_detector, num=10, exposure_time=0.1, software_trigger=True
):

    kinetix_exp_setup = StandardTriggerSetup(
        num_images=num, exposure_time=exposure_time, software_trigger=software_trigger
    )

    yield from bps.open_run()

    yield from bps.stage_all(kinetix_detector, kinetix_flyer)

    yield from bps.prepare(kinetix_flyer, kinetix_exp_setup, wait=True)
    yield from bps.prepare(kinetix_detector, kinetix_flyer.trigger_info, wait=True)

    yield from inner_kinetix_collect()

    yield from bps.unstage_all(kinetix_flyer, kinetix_detector)

    yield from bps.close_run()


file_loading_timer.stop_timer(__file__)
