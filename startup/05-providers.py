file_loading_timer.start_timer(__file__)


# TODO: use the ophyd-async version once released.
# https://github.com/bluesky/ophyd-async/pull/245
# class UUIDDirectoryProvider(DirectoryProvider):
#     def __init__(self, directory_path, resource_dir="."):
#         self._directory_path = directory_path
#         self._resource_dir = resource_dir

#     def __call__(self):
#         return DirectoryInfo(
#             root=Path(self._directory_path),
#             resource_dir=Path(self._resource_dir),
#             prefix=str(uuid.uuid4()),
#         )

import dataclasses
import uuid

from ophyd_async.core._providers import UUIDFilenameProvider, YMDPathProvider


class ProposalNumYMDPathProvder(YMDPathProvider):

    def __init__(
        self, filename_provider, use_default=False, root=HEX_PROPOSAL_DIR_ROOT, **kwargs
    ):

        self._use_default = use_default
        super().__init__(filename_provider, root, **kwargs)

    def __call__(self, device_name=None):
        # self._directory_path is /nsls2/data/hex/proposals
        # This never changes.
        # RE.md['cycle'] -> 2024-2
        # RE.md['proposal'] -> 'pass-123456'
        proposal_assets = (
            self._directory_path / RE.md["cycle"] / RE.md["data_session"] / "assets"
        )
        if not self._use_default:
            path_info = super().__call__(device_name=device_name)
        else:
            path_info = super().__call__(device_name="default")

        filename = path_info.filename
        if isinstance(self._filename_provider, ScanIDFilenameProvider):
            filename = self._filename_provider(device_name=device_name)

        print(f"{path_info = }:\n  {proposal_assets = }\n  {filename = }")
        return dataclasses.replace(path_info, root=proposal_assets, filename=filename)


# class ScanIDDirectoryProvider(UUIDDirectoryProvider):
#     def __init__(self, *args, frame_type: FrameType = FrameType.scan, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._frame_type = frame_type

#     def __call__(self):
#         resource_dir = Path(f"scan_{RE.md['scan_id']:05d}_dark_flat")
#         prefix = f"{self._frame_type.value}_{uuid.uuid4()}"

#         if self._frame_type == FrameType.scan:
#             resource_dir = Path(f"scan_{RE.md['scan_id']:05d}")
#             prefix = f"{uuid.uuid4()}"

#         proposal_assets = Path(self._directory_path, RE.md["cycle"], RE.md["proposal"], "assets")
#         return DirectoryInfo(
#             root=proposal_assets,
#             resource_dir=resource_dir,
#             prefix=prefix,
#         )


class ScanIDFilenameProvider(UUIDFilenameProvider):
    def __init__(
        self,
        *args,
        device_name=None,
        frame_type: TomoFrameType = TomoFrameType.proj,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._frame_type = frame_type
        self._uuid_for_scan = None

    def set_frame_type(self, new_frame_type: TomoFrameType):
        self._frame_type = new_frame_type

    def __call__(self, device_name=None):
        if self._uuid_for_scan is None:
            self._uuid_for_scan = self._uuid_call_func(
                *self._uuid_call_args
            )  # Generate a new UUID

        if device_name is None or not device_name.startswith("panda"):
            filename = f"{self._frame_type.value}_{self._uuid_for_scan}"
        else:
            filename = f"{device_name}_{self._uuid_for_scan}"

        # If we are generating a name for projections, then replace
        if self._frame_type == TomoFrameType.proj and (
            device_name is None or not device_name.startswith("panda")
        ):
            self._uuid_for_scan = None

        return filename


default_filename_provider = ScanIDFilenameProvider(uuid.uuid4)

file_loading_timer.stop_timer(__file__)
