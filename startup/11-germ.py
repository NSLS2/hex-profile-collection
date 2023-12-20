file_loading_timer.start_timer(__file__)

import os
import datetime
import h5py
import uuid
from PIL import Image
import tifffile
import numpy as np
import itertools


from event_model import compose_resource
from collections import deque
from ophyd import Signal, Device, EpicsSignal, Component as Cpt, Kind
from ophyd.status import SubscriptionStatus
from area_detector_handlers import HandlerBase
from ophyd.sim import NullStatus, new_uid
from pathlib import Path

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
    count = Cpt(EpicsSignal, ".CNT", kind=Kind.omitted, string=True)
    mca = Cpt(EpicsSignal, ".MCA", kind=Kind.omitted)
    number_of_channels = Cpt(EpicsSignal, ".NELM", kind=Kind.config)
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
            if old_value == "Count" and value == "Done":
                return True

            return False

        status = SubscriptionStatus(self.count, run=False, callback=is_done)

        self.count.put("Count")
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


class GeRMDetectorHDF5(GeRMDetector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        height = int(self.number_of_channels.get())
        width = len(self.energy.get())
        self._frame_shape = (height, width)

    def stage(self):
        super().stage()

        # Clear asset docs cache which may have some documents from the previous failed run.
        self._asset_docs_cache.clear()

        date = datetime.datetime.now()
        self._assets_dir = date.strftime("%Y/%m/%d")
        data_file = f"{new_uid()}.h5"

        self._resource_document, self._datum_factory, _ = compose_resource(
            start={"uid": "needed for compose_resource() but will be discarded"},
            spec="AD_HDF5_GERM",
            root=ROOT_DIR,
            resource_path=str(Path(self._assets_dir) / Path(data_file)),
            resource_kwargs={},
        )

        self._data_file = str(
            Path(self._resource_document["root"])
            / Path(self._resource_document["resource_path"])
        )

        # now discard the start uid, a real one will be added later
        self._resource_document.pop("run_start")
        self._asset_docs_cache.append(("resource", self._resource_document))

        self._h5file_desc = h5py.File(self._data_file, "x")
        group = self._h5file_desc.create_group("/entry")
        self._dataset = group.create_dataset("data/data",
                                             data=np.full(fill_value=np.nan,
                                                          shape=(1, *self._frame_shape)),
                                             maxshape=(None, *self._frame_shape),
                                             chunks=(1, *self._frame_shape),
                                             dtype="float32")
        # add group to track motors
        # current method of getting motors is using caget
        #   should find a better way to do this
        # Should this be tracked through the bluesky plan?
        # Then how would we add this metadata to the hdf5 file?
        self._counter = itertools.count()

    # def stage(self):
    #     # TODO: Open and set up hdf5 file
    #     # # self.count_time.set()  # bluesky plan arg
    #     # hdf_file_path = output_folder + "/" + file_name + ".hdf"
    #     # # depth = len(list_pos)  # bluesky plan
    #     # dataset_shape = (depth, height, width)
    #     # # metadata_group = ["entry/static_motors/" + group for group in group_names]
    #     # # metadata_list.append({"command_used" : ' '.join(sys.argv)})
    #     # # metadata_group.append("entry/information")
    #     # # if user_input != "":
    #     # #     metadata_list.append({"scan_description" : user_input})
    #     # #     metadata_group.append("entry/information")
    #     # self.writer = HDF5Writer(hdf_file_path, dataset_shape, overwrite=True)
    #     ...

    def trigger(self):
        # Write image to open hdf5 file
        # deco.move_motor(moto_pv_name, pos)  # do in bluesky plan
        def is_done(value, old_value, **kwargs):
            if old_value == "Count" and value == "Done":
                data = self.get_current_image()

                self._dataset.resize((self.current_frame + 1, *self._frame_shape))
                self._dataset[self.current_frame, :, :] = data

                return True

            return False

        status = SubscriptionStatus(self.count, run=False, callback=is_done)

        self.current_frame = next(self._counter)
        self.count.put("Count")

        datum_document = self._datum_factory(datum_kwargs={"frame": self.current_frame})
        self._asset_docs_cache.append(("datum", datum_document))

        self.image.put(datum_document["datum_id"])

        return status

    def describe(self):
        res = super().describe()
        res[self.image.name].update(dict(shape=self._frame_shape))
        return res

    def unstage(self):
        super().unstage()
        # del self._dataset
        self._h5file_desc.close()
        self._resource_document = None
        self._datum_factory = None


class HDF5Writer:
    def __init__(self, output_path, dataset_shape, data_type="float32",
                 group_name="entry", overwrite=False):
        self.output_path = output_path
        self.current_index = 0

        if overwrite:
            if os.path.exists(self.output_path):
                os.remove(self.output_path)
        else:
            if os.path.exists(self.output_path):
                raise ValueError("File exists! Please provide a new name!!!")

        self.make_folder()
        # Open hdf stream
        self.h5_file = h5py.File(self.output_path, 'a')  # open in append mode
        self.entry_grp = self.h5_file.require_group(group_name)
        self.data_grp = self.entry_grp.require_group("data")

        # Create a 3D dataset for storing images
        if "images" not in self.data_grp:
            self.dataset = self.data_grp.create_dataset("images",
                                                        dataset_shape,
                                                        dtype=data_type)
        else:
            self.dataset = self.data_grp["images"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.h5_file:
            self.h5_file.close()

    def make_folder(self):
        dir_name = os.path.dirname(self.output_path)
        os.makedirs(dir_name, exist_ok=True)

    def get_dtype(self, value):
        if isinstance(value, str):
            return h5py.special_dtype(vlen=str)
        elif isinstance(value, float):
            return np.float32
        elif isinstance(value, int):
            return np.int32
        else:
            return type(value)

    def save_data(self, image, scan_params=None, metadata=None,
                  metadata_group=None):
        try:
            self.dataset[self.current_index] = image
            if scan_params is not None:
                if "scanning_parameters" not in self.entry_grp:
                    self.scan_params_grp = self.entry_grp.require_group(
                        "scanning_parameters")
                for key, value in scan_params.items():
                    param_dataset_name = f"{key}_values"
                    if param_dataset_name not in self.scan_params_grp:
                        dtype = self.get_dtype(value)
                        param_dset = self.scan_params_grp.create_dataset(
                            param_dataset_name, (self.dataset.shape[0],),
                            dtype=dtype)
                    else:
                        param_dset = self.scan_params_grp[param_dataset_name]
                    param_dset[self.current_index] = value
            if metadata and metadata_group:
                if len(metadata) != len(metadata_group):
                    raise ValueError("Length of metadata list must match the "
                                     "length of metadata_group list")
                for idx, meta in enumerate(metadata):
                    current_metadata_grp = self.h5_file.require_group(
                        metadata_group[idx])
                    for key, value in meta.items():
                        if key not in current_metadata_grp:
                            dtype = self.get_dtype(value)
                            current_metadata_grp.create_dataset(key,
                                                                data=value,
                                                                dtype=dtype)
            self.current_index += 1
        except Exception as e:
            raise ValueError("Failed to save data due to: {}".format(e))

    def close(self):
        if self.h5_file:
            self.h5_file.close()

# Intialize the GeRM detector ophyd object
germ_detector = GeRMDetector("XF:27ID1-ES{GeRM-Det:1}", name="GeRM")
germ_detector_hdf5 = GeRMDetectorHDF5("XF:27ID1-ES{GeRM-Det:1}", name="GeRM")


class AreaDetectorTiffHandlerGERM(HandlerBase):
    specs = {"AD_TIFF_GERM"}

    def __init__(self, fpath):
        self._path = os.path.join(fpath, "")

    def __call__(self):
        ret = []
        with tifffile.TiffFile(self._path) as tif:
            ret.append(tif.asarray())
        return np.array(ret)


class AreaDetectorHDF5HandlerGERM(HandlerBase):
    specs = {"AD_HDF5_GERM"}
    def __init__(self, filename):
        self._name = filename

    def __call__(self, frame):
        with h5py.File(self._name, "r") as f:
            entry = f["/entry/data/data"]
            return entry[frame, :]


db.reg.register_handler("AD_TIFF_GERM", AreaDetectorTiffHandlerGERM, overwrite=True)
db.reg.register_handler("AD_HDF5_GERM", AreaDetectorHDF5HandlerGERM, overwrite=True)


# TODO: rework the exported based on Tiled.
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
                nx_filepath = f"{os.path.splitext(h5_filepath)[0]}.nxs"
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


GERM_DETECTOR_KEYS = [
    "count_time",
    "gain",
    "shaping_time",
    "hv_bias",
    "voltage",
]

def get_detector_parameters(det=germ_detector_hdf5, keys=GERM_DETECTOR_KEYS):
    group_key = f"{det.name.lower()}_detector"
    detector_metadata = {group_key : {}}
    for key in keys:
        obj = getattr(det, key)
        as_string = True if obj.enum_strs else False
        detector_metadata[group_key][key] = obj.get(as_string=as_string)
    return detector_metadata


RE.subscribe(nx_export_callback, name="stop")


file_loading_timer.stop_timer(__file__)
