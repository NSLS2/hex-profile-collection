file_loading_timer.start_timer(__file__)

import os
import datetime
import uuid
from PIL import Image
import tifffile
import numpy as np

from event_model import compose_resource
from collections import deque
from ophyd import Signal, Device, EpicsSignal, Component as Cpt, Kind
from ophyd.status import SubscriptionStatus
from area_detector_handlers import HandlerBase


ROOT_DIR = "/nsls2/data/hex/proposals/commissioning/pass-312143/temp"


class ExternalFileReference(Signal):
    """
    A pure software Signal that describe()s an image in an external file.
    """

    def describe(self):
        resource_document_data = super().describe()
        resource_document_data[self.name].update(
            dict(
                external="FILESTORE:",
                dtype="array",
            )
        )
        return resource_document_data


class GeRMDetector(Device):
    count = Cpt(EpicsSignal, ".CNT", kind=Kind.omitted)
    mca = Cpt(EpicsSignal, ".MCA", kind=Kind.hinted)
    number_of_channels = Cpt(EpicsSignal, ".NELM", kind=Kind.config)
    gain = Cpt(EpicsSignal, ".GAIN", kind=Kind.config)
    shaping_time = Cpt(EpicsSignal, ".SHPT", kind=Kind.config)
    count_time = Cpt(EpicsSignal, ".TP", kind=Kind.config)
    auto_time = Cpt(EpicsSignal, ".TP1", kind=Kind.config)
    run_num = Cpt(EpicsSignal, ".RUNNO", kind=Kind.omitted)
    fast_data_filename = Cpt(EpicsSignal, ".FNAM", string=True)
    operating_mode = Cpt(EpicsSignal, ".MODE", kind=Kind.omitted)
    single_auto_toggle = Cpt(EpicsSignal, ".CONT", kind=Kind.omitted)
    gmon = Cpt(EpicsSignal, ".GMON", kind=Kind.omitted)
    ip_addr = Cpt(EpicsSignal, ".IPADDR", string=True)
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
    voltage = Cpt(EpicsSignal, ":HV_RBV", kind=Kind.omitted)
    current = Cpt(EpicsSignal, ":HV_CUR", kind=Kind.omitted)
    peltier_2 = Cpt(EpicsSignal, ":P2", kind=Kind.omitted)
    peliter_2_current = Cpt(EpicsSignal, ":P2_CUR", kind=Kind.omitted)
    peltier_1 = Cpt(EpicsSignal, ":P1", kind=Kind.omitted)
    peltier_1_current = Cpt(EpicsSignal, ":P1_CUR", kind=Kind.omitted)
    hv_bias = Cpt(EpicsSignal, ":HV", kind=Kind.omitted)
    ring_hi = Cpt(EpicsSignal, ":DRFTHI", kind=Kind.omitted)
    ring_lo = Cpt(EpicsSignal, ":DRFTLO", kind=Kind.omitted)
    channel_enabled = Cpt(EpicsSignal, ".TSEN", kind=Kind.omitted)
    energy = Cpt(EpicsSignal, ".SPCTX", kind=Kind.omitted)

    image = Cpt(ExternalFileReference, kind=Kind.normal)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resource_document, self._datum_factory = None, None
        self._asset_docs_cache = deque()

    def describe(self):
        desc = super().describe()
        return desc

    def trigger(self):
        def is_done(value, old_value, **kwargs):
            if old_value == 1 and value == 0:
                return True

            return False

        status = SubscriptionStatus(self.count, run=False, callback=is_done)

        self.count.put(1)
        status.wait()

        # Read the image array:
        img = self.get_current_image()

        # Save TIFF files:
        root_dir = ROOT_DIR
        date = datetime.datetime.now()
        assets_dir = date.strftime("%Y/%m/%d")
        file_name = f"{uuid.uuid4()}.tiff"
        file_path = os.path.join(root_dir, assets_dir, file_name)
        self.save_image(file_path=file_path, mat=img)

        # Create resource/datum docs:
        self._resource_document, self._datum_factory, _ = compose_resource(
            start={"uid": "needed for compose_resource() but will be discarded"},
            spec="AD_TIFF_GERM",  # TODO: convert to use standard AD_TIFF.
            root=root_dir,
            resource_path=os.path.join(assets_dir, file_name),
            resource_kwargs={},
        )

        self._resource_document.pop("run_start")
        self._asset_docs_cache.append(("resource", self._resource_document))

        datum_document = self._datum_factory(datum_kwargs={})
        self._asset_docs_cache.append(("datum", datum_document))

        self.image.put(datum_document["datum_id"])

        return status

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item

    def unstage(self):
        super().unstage()
        self._resource_document = None
        self._datum_factory = None

    def get_current_image(self):
        # This is the reshaping we want
        # This doesn't trigger the detector
        data = self.mca.get()
        height = int(self.number_of_channels.get())
        width = len(self.energy.get())
        data = np.reshape(data, (height, width))
        return data

    def save_image(self, file_path, mat, overwrite=True):
        image = Image.fromarray(mat)
        if not overwrite:
            file_path = self._make_file_name(file_path)
        try:
            image.save(file_path)
        except IOError:
            raise ValueError("Couldn't write to file {}".format(file_path))
        return file_path

    def _make_file_name(self, file_path):
        file_base, file_ext = os.path.splitext(file_path)
        if os.path.isfile(file_path):
            nfile = 0
            check = True
            while check:
                name_add = "0000" + str(nfile)
                file_path = file_base + "_" + name_add[-4:] + file_ext
                if os.path.isfile(file_path):
                    nfile = nfile + 1
                else:
                    check = False
        return file_path

    # def write_mca_hdf5(self):
    #     mca = self.mca.get()
    #     print(mca)


# Intialize the GeRM detector ophyd object
germ_detector = GeRMDetector("XF:27ID1-ES{GeRM-Det:1}", name="GeRM")


class AreaDetectorTiffHandlerHEX(HandlerBase):
    specs = {"AD_TIFF_GERM"}

    def __init__(self, fpath):
        self._path = os.path.join(fpath, "")

    def __call__(self):
        ret = []
        with tifffile.TiffFile(self._path) as tif:
            ret.append(tif.asarray())
        return np.array(ret)


db.reg.register_handler("AD_TIFF_GERM", AreaDetectorTiffHandlerHEX)


file_loading_timer.stop_timer(__file__)
