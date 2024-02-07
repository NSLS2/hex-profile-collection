file_loading_timer.start_timer(__file__)

import datetime
import uuid
from collections import deque
from pathlib import Path

import numpy as np
from event_model import compose_resource
from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, Kind, Signal
from ophyd.sim import new_uid
from ophyd.status import SubscriptionStatus
from PIL import Image

from enum import Enum


class AcqStatuses(Enum):
    """Enum class for acquisition statuses."""

    IDLE = "Done"
    ACQUIRING = "Count"


class StageStates(Enum):
    """Enum class for stage states."""

    UNSTAGED = "unstaged"
    STAGED = "staged"


class ExternalFileReference(Signal):
    """
    A pure software Signal that describe()s an image in an external file.
    """

    def describe(self):
        resource_document_data = super().describe()
        resource_document_data[self.name].update(
            {
                "external": "FILESTORE:",
                "dtype": "array",
            }
        )
        return resource_document_data


class GeRMMiniClassForCaprotoIOC(Device):
    """Minimal GeRM detector ophyd class used in caproto IOC."""

    count = Cpt(EpicsSignal, ".CNT", kind=Kind.omitted, string=True)
    mca = Cpt(EpicsSignal, ".MCA", kind=Kind.omitted)
    number_of_channels = Cpt(EpicsSignal, ".NELM", kind=Kind.config)
    energy = Cpt(EpicsSignal, ".SPCTX", kind=Kind.omitted)


class GeRMDetectorBase(GeRMMiniClassForCaprotoIOC):
    """The base ophyd class for GeRM detector."""

    gain = Cpt(EpicsSignal, ".GAIN", kind=Kind.config)
    shaping_time = Cpt(EpicsSignal, ".SHPT", kind=Kind.config)
    count_time = Cpt(EpicsSignal, ".TP", kind=Kind.config)
    auto_time = Cpt(EpicsSignal, ".TP1", kind=Kind.config)
    run_num = Cpt(EpicsSignal, ".RUNNO", kind=Kind.omitted)
    fast_data_filename = Cpt(EpicsSignal, ".FNAM", string=True, kind=Kind.config)
    operating_mode = Cpt(EpicsSignal, ".MODE", kind=Kind.omitted)
    single_auto_toggle = Cpt(EpicsSignal, ".CONT", kind=Kind.omitted)
    gmon = Cpt(EpicsSignal, ".GMON", kind=Kind.omitted)
    ip_addr = Cpt(EpicsSignal, ".IPADDR", string=True, kind=Kind.omitted)
    temp_1 = Cpt(EpicsSignal, ":Temp1", kind=Kind.omitted)
    temp_2 = Cpt(EpicsSignal, ":Temp2", kind=Kind.omitted)
    fpga_cpu_temp = Cpt(EpicsSignal, ":ztmp", kind=Kind.omitted)
    calibration_file = Cpt(EpicsSignal, ".CALF", kind=Kind.omitted)
    multi_file_supression = Cpt(EpicsSignal, ".MFS", kind=Kind.omitted)
    tdc = Cpt(EpicsSignal, ".TDC", kind=Kind.omitted)
    leakage_pulse = Cpt(EpicsSignal, ".LOAO", kind=Kind.omitted)
    internal_leak_curr = Cpt(EpicsSignal, ".EBLK", kind=Kind.omitted)
    pileup_rejection = Cpt(EpicsSignal, ".PUEN", kind=Kind.omitted)
    test_pulse_aplitude = Cpt(EpicsSignal, ".TPAMP", kind=Kind.omitted)
    channel = Cpt(EpicsSignal, ".MONCH", kind=Kind.omitted)
    tdc_slope = Cpt(EpicsSignal, ".TDS", kind=Kind.omitted)
    test_pulse_freq = Cpt(EpicsSignal, ".TPFRQ", kind=Kind.omitted)
    tdc_mode = Cpt(EpicsSignal, ".TDM", kind=Kind.omitted)
    test_pulce_enable = Cpt(EpicsSignal, ".TPENB", kind=Kind.omitted)
    test_pulse_count = Cpt(EpicsSignal, ".TPCNT", kind=Kind.omitted)
    input_polarity = Cpt(EpicsSignal, ".POL", kind=Kind.omitted)
    voltage = Cpt(EpicsSignal, ":HV_RBV", kind=Kind.config)
    current = Cpt(EpicsSignal, ":HV_CUR", kind=Kind.omitted)
    peltier_2 = Cpt(EpicsSignal, ":P2", kind=Kind.omitted)
    peliter_2_current = Cpt(EpicsSignal, ":P2_CUR", kind=Kind.omitted)
    peltier_1 = Cpt(EpicsSignal, ":P1", kind=Kind.omitted)
    peltier_1_current = Cpt(EpicsSignal, ":P1_CUR", kind=Kind.omitted)
    hv_bias = Cpt(EpicsSignal, ":HV", kind=Kind.config)
    ring_hi = Cpt(EpicsSignal, ":DRFTHI", kind=Kind.omitted)
    ring_lo = Cpt(EpicsSignal, ":DRFTLO", kind=Kind.omitted)
    channel_enabled = Cpt(EpicsSignal, ".TSEN", kind=Kind.omitted)

    image = Cpt(ExternalFileReference, kind=Kind.normal)

    # Caproto IOC components:
    write_dir = Cpt(
        EpicsSignal,
        ":write_dir",
        kind=Kind.config,
        string=True,
    )
    file_name_prefix = Cpt(
        EpicsSignal,
        ":file_name_prefix",
        kind=Kind.config,
        string=True,
    )
    frame_num = Cpt(EpicsSignal, ":frame_num", kind=Kind.omitted)
    frame_shape = Cpt(EpicsSignal, ":frame_shape", kind=Kind.config)
    ioc_stage = Cpt(EpicsSignal, ":stage", kind=Kind.omitted)

    def __init__(self, *args, root_dir=None, **kwargs):
        super().__init__(*args, **kwargs)
        if root_dir is None:
            msg = "The 'root_dir' kwarg cannot be None"
            raise RuntimeError(msg)
        self._root_dir = root_dir
        self._resource_document, self._datum_factory = None, None
        self._asset_docs_cache = deque()

    def collect_asset_docs(self):
        """The method to collect resource/datum documents."""
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        yield from items

    def unstage(self):
        super().unstage()
        self._resource_document = None
        self._datum_factory = None

    def get_current_image(self):
        """The function to return a current image from detector's MCA."""
        # This is the reshaping we want
        # This doesn't trigger the detector
        raw_data = self.mca.get()
        return np.reshape(raw_data, self.frame_shape)


def done_callback(value, old_value, **kwargs):
    """The callback function used by ophyd's SubscriptionStatus."""
    # pylint: disable=unused-argument
    if old_value == AcqStatuses.ACQUIRING.value and value == AcqStatuses.IDLE.value:
        return True
    return False


# TODO: add Tiff support in Caproto IOC.

class GeRMDetectorHDF5(GeRMDetectorBase):
    """The ophyd class for GeRM detector producing HDF5 files."""

    def stage(self):
        super().stage()

        # Clear asset docs cache which may have some documents from the previous failed run.
        self._asset_docs_cache.clear()

        date = datetime.datetime.now()
        # TODO: parametrize templating on both ophyd and caproto sides.
        assets_dir = date.strftime("%Y/%m/%d")
        data_file_no_ext = f"{new_uid()}"
        data_file_with_ext = f"{data_file_no_ext}.h5"

        self._resource_document, self._datum_factory, _ = compose_resource(
            start={"uid": "needed for compose_resource() but will be discarded"},
            spec="AD_HDF5_GERM",
            root=self._root_dir,
            resource_path=str(Path(assets_dir) / Path(data_file_with_ext)),
            resource_kwargs={},
        )

        # now discard the start uid, a real one will be added later
        self._resource_document.pop("run_start")
        self._asset_docs_cache.append(("resource", self._resource_document))

        # Update caproto IOC parameters:
        self.write_dir.put(self._root_dir)
        self.file_name_prefix.put(data_file_no_ext)
        self.ioc_stage.put(StageStates.STAGED.value)

    def describe(self):
        res = super().describe()
        res[self.image.name].update({"shape": self.frame_shape.get().tolist(), "dtype_str": "<f4"})
        return res

    def trigger(self):
        status = SubscriptionStatus(self.count, run=False, callback=done_callback)

        # Reuse the counter from the caproto IOC
        current_frame = self.frame_num.get()
        self.count.put(AcqStatuses.ACQUIRING.value)

        datum_document = self._datum_factory(datum_kwargs={"frame": current_frame})
        self._asset_docs_cache.append(("datum", datum_document))

        self.image.put(datum_document["datum_id"])

        return status

    def stop(self, *, success=False):
        # TODO: see why it's not called by RE on RE.stop()
        ret = super().stop(success=success)
        print("\n!!! Should stop now !!!\n")
        self.count.put("Done")
        return ret

    def unstage(self):
        self.ioc_stage.put(StageStates.UNSTAGED.value)
        super().unstage()


# Intialize the GeRM detector ophyd object
germ_detector = GeRMDetectorHDF5("XF:27ID1-ES{GeRM-Det:1}", name="GeRM", root_dir="/nsls2/data/hex/assets/germ/")


# No need for the handlers if used with Tiled.
import os
import h5py
from area_detector_handlers import HandlerBase

class AreaDetectorHDF5HandlerGERM(HandlerBase):
    specs = {"AD_HDF5_GERM"}
    def __init__(self, filename):
        self._name = filename

    def __call__(self, frame):
        with h5py.File(self._name, "r") as f:
            entry = f["/entry/data/data"]
            return entry[frame, :]


db.reg.register_handler("AD_HDF5_GERM", AreaDetectorHDF5HandlerGERM, overwrite=True)


# TODO: rework the exported based on Tiled.
# TODO 2: add motor positions.
def nx_export_callback(name, doc):
    print(f"Exporting the nx file at {datetime.datetime.now().isoformat()}")
    if name == "stop":
        run_start = doc["run_start"]
        # TODO: rewrite with SingleRunCache.
        hdr = db[run_start]
        for nn, dd in hdr.documents():
            if nn == "resource" and dd["spec"] == "AD_HDF5_GERM":
                resource_root = dd["root"]
                resource_path = dd["resource_path"]
                h5_filepath = os.path.join(resource_root, resource_path)
                # nx_filepath = f"{os.path.splitext(h5_filepath)[0]}.nxs"
                nx_filepath = os.path.join(
                    "/tmp",
                    f"{os.path.basename(os.path.splitext(h5_filepath)[0])}.nxs",
                )
                print(f"{nx_filepath = }")
                # TODO 1: prepare metadata
                # TODO 2: save .nxs file

                def get_dtype(value):
                    if isinstance(value, str):
                        return h5py.special_dtype(vlen=str)
                    elif isinstance(value, float):
                        return np.float32
                    elif isinstance(value, int):
                        return np.int32
                    else:
                        return type(value)

                with h5py.File(nx_filepath, 'w') as h5_file:
                    entry_grp = h5_file.require_group("entry")
                    data_grp = entry_grp.require_group("data")

                    meta_dict = get_detector_parameters()
                    for k, v in meta_dict.items():
                        meta = v
                        break
                    current_metadata_grp = h5_file.require_group("entry/instrument/detector")  # TODO: fix the location later.
                    for key, value in meta.items():
                        if key not in current_metadata_grp:
                            dtype = get_dtype(value)
                            current_metadata_grp.create_dataset(key, data=value, dtype=dtype)

                    # External link
                    data_grp["data"] = h5py.ExternalLink(h5_filepath, "entry/data/data")


# TODO: add detector params into exported .h5 via caproto IOC.
GERM_DETECTOR_KEYS = [
    "count_time",
    "gain",
    "shaping_time",
    "hv_bias",
    "voltage",
]

def get_detector_parameters(det=germ_detector, keys=GERM_DETECTOR_KEYS):
    group_key = f"{det.name.lower()}_detector"
    detector_metadata = {group_key : {}}
    for key in keys:
        obj = getattr(det, key)
        as_string = True if obj.enum_strs else False
        detector_metadata[group_key][key] = obj.get(as_string=as_string)
    return detector_metadata


# RE.subscribe(nx_export_callback, name="stop")


file_loading_timer.stop_timer(__file__)
