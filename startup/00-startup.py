# Begin loading HEX Profile Collection

print("Loading NSLS-II HEX profile collection...")

import asyncio
import datetime
import logging
import os
import subprocess
import time as ttime
import warnings
from pathlib import Path

import bluesky.plan_stubs as bps
import epicscorelibs.path.pyepics
import matplotlib.pyplot as plt
import nslsii
import ophyd.signal
import redis
from bluesky.callbacks.broker import post_run, verify_files_saved
from bluesky.callbacks.tiled_writer import TiledWriter
from bluesky.run_engine import RunEngine, call_in_bluesky_event_loop
from databroker.v0 import Broker
from IPython import get_ipython
from IPython.terminal.prompts import Prompts, Token
from nslsii import configure_base, configure_kafka_publisher
from nslsii.re_subs import BlueskyDocJSONWriter, BlueskyDocStreamPrinter
from ophyd.signal import EpicsSignalBase
from redis_json_dict import RedisJSONDict
from tiled.client import from_uri

try:
    from bluesky_queueserver import is_re_worker_active
except ImportError:
    # TODO: delete this when 'bluesky_queueserver' is distributed as part of collection environment
    def is_re_worker_active():
        return False


# RUNNING_IN_NSLS2_CI = os.environ["NSLS2_PROFILE_CI"] == "YES"
# RUNNING_IN_NSLS2_CI = os.environ["NSLS2_PROFILE_CI"] == False
RUNNING_IN_NSLS2_CI = False

# warnings.filterwarnings("ignore")

plt.ion()


class ProposalIDPrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [
            (
                Token.Prompt,
                f"{RE.md.get('data_session', 'N/A')} [",
            ),
            (Token.PromptNum, str(self.shell.execution_count)),
            (Token.Prompt, "]: "),
        ]


if not is_re_worker_active():
    ip = get_ipython()
    ip.prompts = ProposalIDPrompt(ip)


class FileLoadingTimer:

    def __init__(self):
        self.start_time = 0
        self.loading = False

    def start_timer(self, filename):
        if self.loading:
            raise Exception("File already loading!")

        print(f"Loading {filename}...")
        self.start_time = ttime.time()
        self.loading = True

    def stop_timer(self, filename):

        elapsed = ttime.time() - self.start_time
        print(f"Done loading {filename} in {elapsed:.6f} seconds.")
        self.loading = False


EpicsSignalBase.set_defaults(timeout=10, connection_timeout=10)

# The call below creates 'RE' and 'db' objects in the IPython user namespace.
# configure_base(get_ipython().user_ns,
#                "hex",
#                publish_documents_with_kafka=True,
#                pbar=True)

# configure_base(
#     get_ipython().user_ns,
#     Broker.named("temp"),
#     pbar=True,
#     bec=True,
#     magics=True,
#     mpl=True,
#     epics_context=False,
#     publish_documents_with_kafka=False,
# )

# event_loop = asyncio.get_event_loop()
# RE = RunEngine(loop=event_loop)
RE = RunEngine()
# RE.subscribe(bec)
# RE.preprocessors.append(sd)

tiled_writing_client = from_uri(
    "https://tiled.nsls2.bnl.gov/api/v1/metadata/hex/raw",
    api_key=os.environ["TILED_BLUESKY_WRITING_API_KEY_HEX"],
)


tw = TiledWriter(tiled_writing_client)
RE.subscribe(tw)

c = None
if not is_re_worker_active():
    c = tiled_reading_client = from_uri(
        "https://tiled.nsls2.bnl.gov/api/v1/metadata/hex/raw",
        include_data_sources=True,
        # username=None
    )


def logout():
    """
    Logout of tiled and reset the default username.
    This is needed to switch between different users.
    """

    if c is None:
        raise RuntimeError("Tiled reading client not initialized!")
    c.logout()


jw = BlueskyDocJSONWriter()
RE.subscribe(jw)

configure_kafka_publisher(RE, beamline_name="hex")

# This is needed for ophyd-async to enable 'await <>' instead of 'asyncio.run(<>)':
if not is_re_worker_active():
    get_ipython().run_line_magic("autoawait", "call_in_bluesky_event_loop")

# PandA does not produce any data for plots for now.
# bec.disable_plots()
# bec.disable_table()
# bec.disable_baseline()

# runengine_metadata_dir = Path("/nsls2/data/hex/shared/config/runengine-metadata")

# TODO: Revert back to real redis
# RE.md = {"data_session": "pass-318988", "cycle": "2026-1", "tiled_access_tags": ["pass-318988"]}
RE.md = RedisJSONDict(redis.Redis("info.hex.nsls2.bnl.gov", 6379), prefix="")


# Set some metadata that never changes.
RE.md["facility"] = "NSLS-II"
RE.md["group"] = "HEX"
RE.md["beamline_id"] = "27-ID-1"


from ophyd_async.core import config_ophyd_async_logging

config_ophyd_async_logging()


def reset_scan_id(scan_id=0):
    """A fake plan to reset the scan_id via qserver."""
    yield from bps.null()
    print(f"Scan_id before: {RE.md['scan_id']}")
    RE.md["scan_id"] = scan_id
    print(f"Scan_id after: {RE.md['scan_id']}")


file_loading_timer = FileLoadingTimer()
