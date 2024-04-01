# Begin loading HEX Profile Collection

print("Loading NSLS-II HEX profile collection...")

import asyncio
import datetime
import logging
import os
import subprocess
import time
import warnings
from pathlib import Path

import epicscorelibs.path.pyepics
import matplotlib.pyplot as plt
import nslsii
import ophyd.signal
from bluesky.callbacks.broker import post_run, verify_files_saved
from bluesky.callbacks.tiled_writer import TiledWriter
from bluesky.run_engine import RunEngine, call_in_bluesky_event_loop
from bluesky.utils import PersistentDict
from databroker.v0 import Broker
from IPython import get_ipython
from nslsii import configure_base, configure_kafka_publisher
from ophyd.signal import EpicsSignalBase
from tiled.client import from_uri

plt.ion()


class FileLoadingTimer:

    def __init__(self):
        self.start_time = 0
        self.loading = False

    def start_timer(self, filename):
        if self.loading:
            raise Exception("File already loading!")

        print(f"Loading {filename}...")
        self.start_time = time.time()
        self.loading = True

    def stop_timer(self, filename):

        elapsed = time.time() - self.start_time
        print(f"Done loading {filename} in {elapsed} seconds.")
        self.loading = False


EpicsSignalBase.set_defaults(timeout=10, connection_timeout=10)

# The call below creates 'RE' and 'db' objects in the IPython user namespace.
# configure_base(get_ipython().user_ns,
#                "hex",
#                publish_documents_with_kafka=True,
#                pbar=True)

configure_base(
    get_ipython().user_ns,
    Broker.named("temp"),
    pbar=True,
    bec=True,
    magics=True,
    mpl=True,
    epics_context=False,
    publish_documents_with_kafka=False,
)


event_loop = asyncio.get_event_loop()
RE = RunEngine(loop=event_loop)
RE.subscribe(bec)

tiled_client = from_uri("http://localhost:8000", api_key=os.getenv("TILED_API_KEY", ""))
tw = TiledWriter(tiled_client)
RE.subscribe(tw)

configure_kafka_publisher(RE, beamline_name="hex")

# This is needed for ophyd-async to enable 'await <>' instead of 'asyncio.run(<>)':
get_ipython().run_line_magic("autoawait", "call_in_bluesky_event_loop")

# PandA does not produce any data for plots for now.
bec.disable_plots()
bec.disable_table()

runengine_metadata_dir = Path("/nsls2/data/hex/shared/config/runengine-metadata")

# PersistentDict will create the directory if it does not exist
RE.md = PersistentDict(runengine_metadata_dir)


# Optional: set any metadata that rarely changes.
RE.md["facility"] = "NSLS-II"
RE.md["group"] = "HEX"
RE.md["beamline_id"] = "27-ID-1"


def warmup_hdf5_plugins(detectors):
    """
    Warm-up the hdf5 plugins.
    This is necessary for when the corresponding IOC restarts we have to trigger one image
    for the hdf5 plugin to work correctly, else we get file writing errors.
    Parameter:
    ----------
    detectors: list
    """
    for det in detectors:
        _array_size = det.hdf5.array_size.get()
        if 0 in [_array_size.height, _array_size.width] and hasattr(det, "hdf5"):
            print(
                f"\n  Warming up HDF5 plugin for {det.name} as the array_size={_array_size}..."
            )
            det.hdf5.warmup()
            print(
                f"  Warming up HDF5 plugin for {det.name} is done. array_size={det.hdf5.array_size.get()}\n"
            )
        else:
            print(
                f"\n  Warming up of the HDF5 plugin is not needed for {det.name} as the array_size={_array_size}."
            )


def show_env():
    # this is not guaranteed to work as you can start IPython without hacking
    # the path via activate
    proc = subprocess.Popen(["conda", "list"], stdout=subprocess.PIPE)
    out, err = proc.communicate()
    a = out.decode("utf-8")
    b = a.split("\n")
    print(b[0].split("/")[-1][:-1])


file_loading_timer = FileLoadingTimer()
