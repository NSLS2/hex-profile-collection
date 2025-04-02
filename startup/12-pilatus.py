# from ophyd_async.epics.adpilatus import PilatusDetector

# from ophyd_async.core import DeviceCollector

# pilatus_trigger_logic = StandardTriggerLogic()

# def create_pilatus():
#     with DeviceCollector():
#         pilatus_path_provider = ProposalNumYMDPathProvider(default_filename_provider)
#         pilatus = PilatusDetector("XF:27ID1-ES{Pilatus-Det:1}", pilatus_path_provider, name="pilatus_det")
#     return pilatus
# pilatus_det = create_pilatus()

# pilatus_flyer = StandardFlyer(
#     pilatus_trigger_logic, [], name="pilatus_flyer"
# )