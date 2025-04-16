file_loading_timer.start_timer(__file__)

# Number of encoder counts for an entire revolution
COUNTS_PER_REVOLUTION = 72000
DEG_PER_REVOLUTION = 360
COUNTS_PER_DEG = COUNTS_PER_REVOLUTION / DEG_PER_REVOLUTION
ZERO_OFFSET = 39660

from ophyd_async.epics.adkinetix import KinetixReadoutMode

DETECTOR_MAX_FRAMERATES = {
    KinetixReadoutMode.SENSITIVITY: 80,
    KinetixReadoutMode.SPEED: 250,
    KinetixReadoutMode.DYNAMIC_RANGE: 75,
}


TOMO_ROTARY_STAGE_VELO_RESET_MAX = 30
TOMO_ROTARY_STAGE_VELO_SCAN_MAX = 60


# def close_shutter():
#     """Close the shutter after the scan."""
#     yield from bps.mv(ph_shutter, "Close")
#     yield from bps.sleep(2)


def post_tomo_fly_cleanup():
    """Cleanup to perform at the end of every flyscan"""

    yield from close_ph_shutter()
    
    # Reset the velocity back to high.
    yield from bps.abs_set(tomo_rot_axis.velocity, TOMO_ROTARY_STAGE_VELO_RESET_MAX)


def software_flyscan(detectors: list[StandardDetector], num_images: int, exposure_time: float, stream_name: str):

    yield from bps.stage_all(*detectors)

    trigger_info = TriggerInfo(
        number_of_triggers=num_images,
        trigger=DetectorTrigger.INTERNAL,
        livetime=exposure_time,
    )
    for det in detectors:
        yield from bps.prepare(det, trigger_info, wait=True)

    yield from bps.declare_stream(*detectors, name=stream_name)

    yield from bps.kickoff_all(*detectors, wait=True)
    yield from bps.complete_all(*detectors, wait=True)
    for det in detectors:
        yield from bps.collect(det, name=stream_name)

    yield from bps.unstage_all(*detectors)


@bpp.finalize_decorator(post_tomo_fly_cleanup)
def tomo_dark_flat(
    exposure_time,
    offset,
    detectors=None,
    dark_images=20,
    flat_images=50,
    use_shutter=True,
    md=None,
):

    if detectors is None:
        detectors = [kinetix1]

    if use_shutter:
        if (yield from bps.rd(fe_shutter_status)) != 1:
            raise RuntimeError(f"Front-end shutter is closed. Reopen it!")

    _md = md or {}
    _md.update({"tomo_scanning_mode": ScanType.tomo_dark_flat.value})

    dark_flat_start_uuid = yield from bps.open_run(md=_md)

    print(f"\n=============================\n\nCollecting dark and flat images with scan number {RE.md['scan_id']}...")

    #### DARKS ####

    # Collect dark frames:
    if use_shutter:
        yield from close_ph_shutter()

    for detector in detectors:
        detector._writer._path_provider._filename_provider.set_frame_type(
            TomoFrameType.dark
        )

    yield from software_flyscan(
        detectors,
        dark_images,
        exposure_time,
        "dark"
    )

    #### FLATS ####

    # Move sample out of the way:
    yield from bps.movr(sample_tower.axis_x1, offset)

    # Collect flat images:
    if use_shutter:
        yield from open_ph_shutter()

    for detector in detectors:
        detector._writer._path_provider._filename_provider.set_frame_type(
            TomoFrameType.flat
        )

    yield from software_flyscan(
        detectors,
        flat_images,
        exposure_time,
        "flat"
    )

    yield from bps.close_run()

    # Move sample back:
    yield from bps.movr(sample_tower.axis_x1, -offset)

    # Keep track of current dark/flat scan id here
    RE.md['current_dark_flat_scan_num'] = RE.md['scan_id']
    RE.md['current_dark_flat_scan_uid'] = dark_flat_start_uuid

    print("====================================================\n\n")
    print(f"Completed collection of dark and flat images with scan number: {RE.md['scan_id']}.")
    print("====================================================\n\n")


def home_rotation_stage():

    print("Starting homing routine for TOMO rotation stage...")
    yield from bps.mv(tomo_rotary_stage.home, 1)
    print("Moving rotation axis back to zero degree position...")
    yield from bps.mv(tomo_rot_axis, 0)



@bpp.finalize_decorator(post_tomo_fly_cleanup)
def tomo_flyscan(
    exposure_time,
    num_images,
    panda=None,
    detectors=None,
    time_trigger=True,
    start_deg=0,
    stop_deg=180,
    lead_angle=10,
    reset_speed=TOMO_ROTARY_STAGE_VELO_RESET_MAX,
    use_shutter=True,
    sample_name=None,
):
    """Simple hardware triggered flyscan tomography

    Parameters
    ----------
    exposure_time : float
        exposure time to use on the camera, in seconds
    num_images : int
        total number of camera images to collect during the scan
    start_deg : float (optional)
        starting point in degrees
    stop_deg : float (optional)
        stopping point in degrees
    lead_angle : float (optional)
        the angle in degrees to be used to move motor to -lead_angle before 'start_deg' and +lead_angle after 'stop_deg'
    reset_speed : float
        speed of the rotary motor during reset movements, in deg/s
    use_shutter : bool
        whether to use/check the shutter during the scan
    """


    overhead = 0.005
    if panda is None:
        panda = panda1

    if detectors is None:
        detectors = [kinetix1]

    if use_shutter:
        if (yield from bps.rd(fe_shutter_status)) != 1:
            raise RuntimeError(f"\n    Front-end shutter is closed. Reopen it!\n")

        yield from open_ph_shutter()

    all_detectors = [panda] + detectors

    panda_pcomp = panda.pcomp[1]
    panda_pulser = panda.pulse[1]

    mtr_reset_vel = reset_speed
    if mtr_reset_vel > TOMO_ROTARY_STAGE_VELO_RESET_MAX:
        mtr_reset_vel = TOMO_ROTARY_STAGE_VELO_RESET_MAX

    scan_time = (num_images - 1) * (exposure_time + overhead)
    rot_motor_vel = (stop_deg - start_deg) / scan_time
    if rot_motor_vel > TOMO_ROTARY_STAGE_VELO_SCAN_MAX:
        rot_motor_vel = TOMO_ROTARY_STAGE_VELO_SCAN_MAX
        scan_time = abs(stop_deg - start_deg) / rot_motor_vel

    step_time = scan_time / (num_images - 1)

    framerate = 1 / step_time

    for kinetix_det in detectors:
        det_readout_mode = yield from bps.rd(kinetix_det.driver.readout_port_idx)
        if framerate > DETECTOR_MAX_FRAMERATES[det_readout_mode]:
            step_time = 1 / DETECTOR_MAX_FRAMERATES[det_readout_mode]

    if exposure_time is not None:
        if exposure_time > step_time:
            raise RuntimeError(
                f"Your configured exposure time is longer than the time per step {step_time} seconds!"
            )

    # step_width_counts = COUNTS_PER_REVOLUTION / (
    #    (DEG_PER_REVOLUTION / (stop_deg - start_deg)) * (num_images - 1)
    # )
    # if int(step_width_counts) != round(step_width_counts, 5):
    #    raise ValueError(
    #        "The number of encoder counts per pulse is not an integer value!"
    #    )

    det_trigger_info = TriggerInfo(
        number_of_triggers=num_images,
        trigger=DetectorTrigger.EDGE_TRIGGER,
        livetime=exposure_time,
        deadtime=0.001,
    )

    panda_trigger_info = TriggerInfo(
        number_of_triggers=num_images,
        trigger=DetectorTrigger.CONSTANT_GATE,
        livetime=exposure_time,
        deadtime=0.0001,
    )

    # Make it fast to move to the start position:
    yield from bps.mv(tomo_rot_axis.velocity, reset_speed)
    yield from bps.mv(tomo_rot_axis, start_deg - lead_angle)
    # Set the velocity for the scan:
    yield from bps.mv(tomo_rot_axis.velocity, rot_motor_vel)
    start_encoder = start_deg * COUNTS_PER_DEG - ZERO_OFFSET

    # Set up the pcomp block
    yield from bps.mv(panda_pcomp.start, int(start_encoder))

    # Uncomment if using gate trigger mode on camera
    yield from bps.mv(
        panda_pcomp.width, 3  # step_width_counts - 1
    )  # Width in encoder counts that the pulse will be high
    # yield from bps.mv(panda1_pcomp_1.step, step_width_counts)
    if time_trigger:
        yield from bps.mv(
            panda_pcomp.pulses, 1,
            panda_pulser.pulses, num_images,
            panda_pulser.step, step_time,
            panda_pulser.width, exposure_time / 5,
        )
    else:
        yield from bps.mv(panda_pcomp.pulses, num_images)

    # Set dataset name of calc 2 to "Angle"
    yield from bps.mv(panda.calc[2].out_dataset, "Angle")

    _md = {    
        "detectors": [det.name for det in detectors],
        "num_points": num_images,
        "plan_name": "tomo_flyscan",
        "hints": {},
    }
    _md.update({"tomo_scanning_mode": ScanType.tomo_flyscan.value})
    yield from bps.open_run(md=_md)

    print(f"Executing tomography scan with number number: {RE.md['scan_id']}...\n")

    for det in detectors:
        det._writer._path_provider._filename_provider.set_frame_type(
            TomoFrameType.proj
        )
        if hasattr(det.fileio, "queue_size"):
            yield from bps.mv(det.fileio.queue_size, num_images * 2)

    # Stage All!
    yield from bps.stage_all(*all_detectors)

    for det in detectors:
        yield from bps.prepare(
            det, det_trigger_info, wait=True
        )

    yield from bps.prepare(
        panda, panda_trigger_info, wait=True
    )

    yield from bps.declare_stream(*all_detectors, name="tomo")

    yield from bps.kickoff_all(*all_detectors, wait=True)

    # Move rotation axis to the stop position + the lead angle:
    movement_status = tomo_rot_axis.set(stop_deg + lead_angle, wait=False)

    print("Completing...")
    yield from bps.collect_while_completing(all_detectors, all_detectors, flush_period=1, stream_name="tomo")
    yield from bps.unstage_all(*all_detectors)

    # Make sure rotation movement is done
    movement_status.wait()

    yield from bps.close_run()
    
    print("====================================================")
    print("====================================================\n\n")
    print(f"Completed tomography scan with scan number: {RE.md['scan_id']}.\n")
    print("====================================================")
    print("====================================================\n\n")


    # Print out number of points captured by each detector
    captured = {}
    captured[panda.name] = yield from bps.rd(panda.data.num_captured)
    for det in detectors:
        captured[det.name] = yield from bps.rd(det.fileio.num_captured)
    
    print("Number frames captured:\n")
    for cap in captured.keys():
        print(f"    {cap:15}: {captured[cap]}")



def tomo_loop(
        number_of_repetitions,
        exposure_time,
        dark_flat_offset,
        num_projections,
        pause_time,
        panda=None,
        detectors=None,
        skip_tomo_num=-1,
        time_trigger=True,
        start_deg=0,
        stop_deg=180,
        lead_angle=10,
        reset_speed=TOMO_ROTARY_STAGE_VELO_RESET_MAX,
        use_shutter=True,
        num_flat_images = 50,
        num_dark_images = 20,
    ):

    scan_countdown = skip_tomo_num
    
    yield from tomo_dark_flat(exposure_time, dark_flat_offset, detectors=detectors, use_shutter=use_shutter, dark_images=num_dark_images, flat_images=num_flat_images)

    for i in range(number_of_repetitions):

        print(f"Executing tomo flyscan iteration #{i+1}...")
        
        yield from tomo_flyscan(
            exposure_time,
            num_projections,
            panda=panda,
            detectors=detectors,
            time_trigger=time_trigger,
            start_deg=start_deg,
            stop_deg=stop_deg,
            lead_angle=lead_angle,
            reset_speed=reset_speed,
            use_shutter=use_shutter,
        )

        # Sleep to wait for file saving to complete
        yield from bps.sleep(pause_time)

        if skip_tomo_num > 0:
            scan_countdown -= 1

            if scan_countdown == 0:
                print("Taking dark, flat...")
                yield from tomo_dark_flat(exposure_time, dark_flat_offset, detectors=detectors, use_shutter=use_shutter, dark_images=num_dark_images, flat_images=num_flat_images)
                scan_countdown = skip_tomo_num        


    yield from tomo_dark_flat(exposure_time, dark_flat_offset, detectors=detectors, use_shutter=use_shutter, dark_images=num_dark_images, flat_images=num_flat_images)



def tomo_y_scan_loop(
        exposure_time,
        dark_flat_offset,
        num_projections,
        y_motion_start,
        y_motion_stop,
        y_motion_step,
        panda=None,
        detectors=None,
        skip_tomo_num=-1,
        time_trigger=True,
        start_deg=0,
        stop_deg=180,
        lead_angle=10,
        reset_speed=TOMO_ROTARY_STAGE_VELO_RESET_MAX,
        use_shutter=True,
        num_flat_images = 50,
        num_dark_images = 20,
    ):

    scan_countdown = skip_tomo_num

    pre_scan_position = sample_tower.vertical_y.user_readback.get()

    yield from bps.mv(sample_tower.vertical_y, y_motion_start)

    yield from tomo_dark_flat(exposure_time, dark_flat_offset, detectors=detectors, use_shutter=use_shutter, dark_images=num_dark_images, flat_images=num_flat_images)

    num_steps = int(abs(y_motion_start - y_motion_stop) / abs(y_motion_step))
    last_step = abs(y_motion_start - y_motion_stop) % abs(y_motion_step)
    print(f"Your last step will be {last_step}, since the y_step did not divide evenly.")

    if y_motion_start > y_motion_stop:
        direction = -1
    else:
        direction = 1

    for i in range(num_steps):

        print(f"Executing tomo flyscan iteration #{i+1}...")
        
        yield from tomo_flyscan(
            exposure_time,
            num_projections,
            panda=panda,
            detectors=detectors,
            time_trigger=time_trigger,
            start_deg=start_deg,
            stop_deg=stop_deg,
            lead_angle=lead_angle,
            reset_speed=reset_speed,
            use_shutter=use_shutter,
        )

        # Sleep to wait for file saving to complete
        yield from bps.movr(sample_tower.vertical_y, abs(y_motion_step) * direction)

        if skip_tomo_num > 0:
            scan_countdown -= 1

            if scan_countdown == 0:
                print("Taking dark, flat...")
                yield from tomo_dark_flat(exposure_time, dark_flat_offset, detectors=detectors, use_shutter=use_shutter, dark_images=num_dark_images, flat_images=num_flat_images)
                scan_countdown = skip_tomo_num        


    yield from tomo_dark_flat(exposure_time, dark_flat_offset, detectors=detectors, use_shutter=use_shutter, dark_images=num_dark_images, flat_images=num_flat_images)

    yield from bps.mv(sample_tower.vertical_y, pre_scan_position)

file_loading_timer.stop_timer(__file__)
