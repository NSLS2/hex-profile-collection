file_loading_timer.start_timer(__file__)

from ophyd_async.epics import advimba

try:
    with init_devices():
        vimba_path_provider = ProposalNumYMDPathProvider(default_filename_provider)
        smpl_align_cam = advimba.VimbaDetector(
            "XF:27ID1-ES{Sample-Cam:1}",
            vimba_path_provider,
            name=f"smpl_align_cam",
        )
except Exception as e:
    print(f"Sample alignment camera is unavailable...")


print(f"Loading file {__file__!r} ...")

file_loading_timer.stop_timer(__file__)