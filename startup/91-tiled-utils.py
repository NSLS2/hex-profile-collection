from tiled.queries import Key
import os

def find_bsrun_for_file(fpath: str):
    # ts = datetime(2025, 7, 31, 16, 20, 59).timestamp()   # File creation timestamp
    ts = os.path.getmtime(fpath)  # File creation timestamp
    run = tiled_reading_client.search(Key('start.time') < ts).values().last()
    return run