file_loading_timer.start_timer(__file__)

import time as ttime
import os
from copy import deepcopy
import ophyd
from ophyd.areadetector import (PerkinElmerDetector, PerkinElmerDetectorCam,
                                ImagePlugin, TIFFPlugin, StatsPlugin, HDF5Plugin,
                                ProcessPlugin, ROIPlugin, TransformPlugin)
from ophyd.device import BlueskyInterface
from ophyd.areadetector.trigger_mixins import SingleTrigger, MultiTrigger
from ophyd.areadetector.filestore_mixins import (FileStoreIterativeWrite,
                                                 FileStoreHDF5IterativeWrite,
                                                 FileStoreTIFFSquashing,
                                                 FileStoreTIFF)
from ophyd import Signal, EpicsSignal, EpicsSignalRO, EpicsSignalWithRBV # Tim test
from ophyd import Component as Cpt
from ophyd import StatusBase
from ophyd.status import DeviceStatus
from nslsii.ad33 import SingleTriggerV33, StatsPluginV33
from pathlib import PurePath

from event_model import StreamRange, compose_stream_resource

from packaging.version import Version
# from distutils.version import LooseVersion



# from shutter import sh1


class HEXTIFFPlugin(TIFFPlugin, FileStoreTIFFSquashing,
                    FileStoreIterativeWrite):
    def describe(self):
        description = super().describe()
        description[f"{self.parent.name}_image"] = {
            "source": f"PV:{self.parent.prefix}",
            "dtype": "array",
            "shape": (2048, 2048),
            "dtype_numpy": "<u2",
            "external": "STREAM:"
        }
        return description
    
    def _generate_resource(self, resource_kwargs):
        fn = PurePath(self._fn).relative_to(self.reg_root)
        file_name = self.file_name.get()

        stream_resource, self._stream_datum_factory = compose_stream_resource(mimetype="multipart/related;type=image/tiff",
                                                                        uri=f"file://localhost/{fn}",
                                                                        data_key=f"{self.parent.name}_image",
                                                                        parameters={
                                                                            "chunk_shape": (1, 2048, 2048),
                                                                            "template": file_name + "_{:06d}.tiff"
                                                                        })
        self._asset_docs_cache.append(("stream_resource", stream_resource))


    def generate_datum(self, key, timestamp):
        "Generate a uid and cache it with its key for later insertion."


        frames_captured = self.num_captured.get()

        stream_datum = self._stream_datum_factory(StreamRange(start=frames_captured, stop=frames_captured + 1))

        self._asset_docs_cache.append(("stream_datum", stream_datum))
        return stream_datum["uid"]
    
    def update_read_write_paths(self):
        self._read_path_template = f'/nsls2/data/hex/proposals/{RE.md["cycle"]}/{RE.md["data_session"]}/assets/perkin-elmer/%Y/scan_{RE.md["scan_id"]:06}'
        self._write_path_template = f'Z:\\proposals\\{RE.md["cycle"]}\\{RE.md["data_session"]}\\assets\\perkin-elmer\\%Y\\scan_{RE.md["scan_id"]:06}\\'
        print(f"{self._read_path_template = }")
        print(f"{self._write_path_template = }")

    def stage(self):
        self.update_read_write_paths()

        super().stage()


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PEDetCamWithVersions(PerkinElmerDetectorCam):
    adcore_version = Cpt(EpicsSignalRO, 'ADCoreVersion_RBV')
    driver_version = Cpt(EpicsSignalRO, 'DriverVersion_RBV')



class ContinuousAcquisitionTrigger(BlueskyInterface):
    """
    This trigger mixin class records images when it is triggered.

    It expects the detector to *already* be acquiring, continously.
    """
    def __init__(self, *args, plugin_name="tiff", image_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._plugin = getattr(self, plugin_name)
        if image_name is None:
            image_name = '_'.join([self.name, 'image'])
        self._plugin.stage_sigs[self._plugin.auto_save] = 'No'
        self.cam.stage_sigs[self.cam.image_mode] = 'Continuous'
        self._plugin.stage_sigs[self._plugin.file_write_mode] = 'Capture'
        self._image_name = image_name
        self._status = None
        self._num_captured_signal = self._plugin.num_captured
        self._num_captured_signal.subscribe(self._num_captured_changed)
        self._save_started = False

    def stage(self):
        if self.cam.acquire.get() != 1:
            raise RuntimeError("The ContinuousAcquisitionTrigger expects "
                               "the detector to already be acquiring.")
        return super().stage()
        # put logic to look up proper dark frame
        # die if none is found

    def trigger(self):
        "Trigger one acquisition."
        if not self._staged:
            raise RuntimeError("This detector is not ready to trigger."
                               "Call the stage() method before triggering.")
        self._save_started = False
        self._status = DeviceStatus(self)
        self._desired_number_of_sets = self.number_of_sets.get()
        self._plugin.num_capture.put(self._desired_number_of_sets)
        # self.dispatch(self._image_name, ttime.time())
        self._plugin.generate_datum(self._image_name, ttime.time())
        # reset the proc buffer, this needs to be generalized
        self.proc.reset_filter.put(1)
        self._plugin.capture.put(1)  # Now the TIFF plugin is capturing.
        return self._status

    def _num_captured_changed(self, value=None, old_value=None, **kwargs):
        "This is called when the 'acquire' signal changes."
        if self._status is None:
            return
        if value == self._desired_number_of_sets:
            # This is run on a thread, so exceptions might pass silently.
            # Print and reraise so they are at least noticed.
            try:
                self.tiff.write_file.put(1)
            except Exception as e:
                print(e)
                raise
            self._save_started = True
        if value == 0 and self._save_started:
            self._status._finished()
            self._status = None
            self._save_started = False


class HEXPerkinElmer(ContinuousAcquisitionTrigger, PerkinElmerDetector):
    image = Cpt(ImagePlugin, 'image1:')
    cam = Cpt(PEDetCamWithVersions, 'cam1:')
    _default_configuration_attrs = (PerkinElmerDetector._default_configuration_attrs +
        ('images_per_set', 'number_of_sets'))
    tiff = Cpt(HEXTIFFPlugin, 'TIFF1:',
               write_path_template='/nsls2/data/hex/proposals/',
               read_path_template='/a/b/c/d',
               cam_name='cam',  # used to configure "tiff squashing"
               proc_name='proc',  # ditto
               read_attrs=[],
               root='/nsls2/data/hex/proposals/')


    proc = Cpt(ProcessPlugin, 'Proc1:')

    # These attributes together replace `num_images`. They control
    # summing images before they are stored by the detector (a.k.a. "tiff
    # squashing").
    images_per_set = Cpt(Signal, value=1, add_prefix=())
    number_of_sets = Cpt(Signal, value=1, add_prefix=())
    # sample_to_detector_distance measured in millimeters
    #sample_to_detector_distance = Cpt(Signal, value=300.0, add_prefix=(), kind="config")

    #pixel_size = Cpt(Signal, value=.0002, kind='config')
    #stats1 = Cpt(StatsPluginV33, 'Stats1:')
    #stats2 = Cpt(StatsPluginV33, 'Stats2:')
    #stats3 = Cpt(StatsPluginV33, 'Stats3:')
    #stats4 = Cpt(StatsPluginV33, 'Stats4:')
    #stats5 = Cpt(StatsPluginV33, 'Stats5:')

    #trans1 = Cpt(TransformPlugin, 'Trans1:')

    #roi1 = Cpt(ROIPlugin, 'ROI1:')
    #roi2 = Cpt(ROIPlugin, 'ROI2:')
    #roi3 = Cpt(ROIPlugin, 'ROI3:')
    #roi4 = Cpt(ROIPlugin, 'ROI4:')





try:
    # PE1 detector configurations:
    pe1_pv_prefix = 'XF:27ID1-ES{PE-Det:1}'
    pe1 = HEXPerkinElmer(pe1_pv_prefix, name='pe1',
                     read_attrs=['tiff'])
except:
    print("Perkin Elmer not connected...")

file_loading_timer.stop_timer(__file__)
