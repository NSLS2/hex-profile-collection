file_loading_timer.start_timer(__file__)

# Number of encoder counts for an entire revolution
COUNTS_PER_REVOLUTION = 72000
DEG_PER_REVOLUTION = 360
COUNTS_PER_DEG = COUNTS_PER_REVOLUTION / DEG_PER_REVOLUTION
ZERO_OFFSET = 39660

KINETIX_MAX_FRAMERATES = {
    KinetixReadoutMode.sensitivity: 80,
    KinetixReadoutMode.speed: 250,
    KinetixReadoutMode.dynamic_range: 75,
}


TOMO_ROTARY_STAGE_VELO_RESET_MAX = 30
TOMO_ROTARY_STAGE_VELO_SCAN_MAX = 60


def close_shutter():
    """Close the shutter after the scan."""
    yield from bps.mv(ph_shutter, "Close")


@bpp.finalize_decorator(close_shutter)
def take_dark_flat(exposure_time, offset, dark_images=20, flat_images=50):
    if (yield from bps.rd(fe_shutter_status)) != 1:
        raise RuntimeError(f"Front-end shutter is closed. Reopen it!")

    # Collect dark frames:
    yield from bps.mv(ph_shutter, "Close")
    yield from kinetix_collect(num=dark_images, exposure_time=exposure_time)

    # Move sample out of the way:
    yield from bps.movr(sample_tower.axis_x1, offset)

    # Collect flat images:
    yield from bps.mv(ph_shutter, "Open")
    yield from bps.sleep(2)
    uid_flat = yield from kinetix_collect(num=flat_images, exposure_time=exposure_time)

    # Move sample back:
    yield from bps.movr(sample_tower.axis_x1, -offset)
    # yield from bps.mv(ph_shutter, "Close")


@bpp.finalize_decorator(close_shutter)
def tomo_flyscan(
    exposure_time,
    num_images,
    scan_time=30,
    start_deg=0,
    stop_deg=180,
    lead_angle=10,
    reset_speed=TOMO_ROTARY_STAGE_VELO_RESET_MAX,
    use_shutter=True,
):
    """Simple hardware triggered flyscan tomography

    Parameters
    ----------
    exposure_time : float
        exposure time to use on the camera, in seconds
    num_images : int
        total number of camera images to collect during the scan
    scan_time : float (optional)
        time for the movement from start_deg to stop_deg degrees, in seconds.
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

    if use_shutter:
        if (yield from bps.rd(fe_shutter_status)) != 1:
            raise RuntimeError(f"\n    Front-end shutter is closed. Reopen it!\n")

        yield from bps.mv(ph_shutter, "Open")
        yield from bps.sleep(2)

    panda_detectors = [panda_flyer, panda_standard_det]
    kinetix_detectors = [kinetix_flyer, kinetix_standard_det]

    detectors = panda_detectors + kinetix_detectors

    panda1_pcomp_1 = dict(panda1_async.pcomp.children())["1"]

    mtr_reset_vel = reset_speed
    if mtr_reset_vel > TOMO_ROTARY_STAGE_VELO_RESET_MAX:
        mtr_reset_vel = TOMO_ROTARY_STAGE_VELO_RESET_MAX

    duration = scan_time
    rot_motor_vel = (stop_deg - start_deg) / scan_time
    if rot_motor_vel > TOMO_ROTARY_STAGE_VELO_SCAN_MAX:
        rot_motor_vel = TOMO_ROTARY_STAGE_VELO_SCAN_MAX
        duration = abs(stop_deg - start_deg) / rot_motor_vel

    step_time = duration / (num_images - 1)

    framerate = 1 / step_time

    kinetix_mode = yield from bps.rd(kinetix_async.readout_mode)
    if framerate > KINETIX_MAX_FRAMERATES[kinetix_mode]:
        step_time = 1 / KINETIX_MAX_FRAMERATES[kinetix_mode]

    if exposure_time is not None:
        if exposure_time > step_time:
            raise RuntimeError(
                f"Your configured exposure time is longer than the time per step {step_time} seconds!"
            )

    step_width_counts = COUNTS_PER_REVOLUTION / (
        (DEG_PER_REVOLUTION / (stop_deg - start_deg)) * (num_images - 1)
    )
    if int(step_width_counts) != round(step_width_counts, 5):
        raise ValueError(
            "The number of encoder counts per pulse is not an integer value!"
        )

    kinetix_exp_setup = KinetixTriggerSetup(
        num_images=num_images,
        exposure_time=exposure_time,
        software_trigger=False,
    )

    # Make it fast to move to the start position:
    yield from bps.mv(tomo_rot_axis.velocity, reset_speed)
    yield from bps.mv(tomo_rot_axis, start_deg - lead_angle)
    # Set the velocity for the scan:
    yield from bps.mv(tomo_rot_axis.velocity, rot_motor_vel)
    start_encoder = start_deg * COUNTS_PER_DEG - ZERO_OFFSET

    # Set up the pcomp block
    yield from bps.mv(panda1_pcomp_1.start, int(start_encoder))

    # Uncomment if using gate trigger mode on camera
    # yield from bps.mv(
    #    panda_pcomp_1.width, width_in_counts
    # )  # Width in encoder counts that the pulse will be high
    yield from bps.mv(panda1_pcomp_1.step, step_width_counts)
    yield from bps.mv(panda1_pcomp_1.pulses, num_images)

    # Stage All!
    yield from bps.stage_all(*detectors)

    # Set HDF plugin numcapture to num_images
    yield from bps.mv(kinetix_writer.hdf.num_capture, num_images)

    assert kinetix_flyer._trigger_logic.state == KinetixTriggerState.stopping
    yield from bps.prepare(kinetix_flyer, kinetix_exp_setup, wait=True)
    yield from bps.prepare(kinetix_standard_det, kinetix_flyer.trigger_info, wait=True)

    assert panda_flyer._trigger_logic.state == KinetixTriggerState.stopping
    yield from bps.prepare(panda_flyer, num_images, wait=True)
    yield from bps.prepare(panda_standard_det, panda_flyer.trigger_info, wait=True)

    # Move rotation axis to the stop position + the lead angle:
    yield from bps.mv(tomo_rot_axis, stop_deg + lead_angle)

    yield from bps.open_run()

    for flyer_or_det in detectors:
        yield from bps.kickoff(flyer_or_det)

    for flyer_or_det in panda_detectors:
        yield from bps.complete(flyer_or_det, wait=True, group="complete_panda")

    for flyer_or_det in kinetix_detectors:
        yield from bps.complete(flyer_or_det, wait=True, group="complete_kinetix")

    # Wait for completion of the PandA HDF5 file saving.
    done = False
    while not done:
        try:
            yield from bps.wait(group="complete_panda", timeout=0.5)
        except TimeoutError:
            pass
        else:
            done = True
        yield from bps.collect(
            panda_standard_det,
            stream=True,
            return_payload=False,
            name=f"{panda_standard_det.name}_stream",
        )

    yield from bps.unstage_all(*panda_detectors)

    if use_shutter:
        yield from close_shutter()

    # Wait for completion of the AD HDF5 file saving.
    done = False
    while not done:
        try:
            yield from bps.wait(group="complete_kinetix", timeout=0.5)
        except TimeoutError:
            pass
        else:
            done = True
        yield from bps.collect(
            kinetix_standard_det,
            stream=True,
            return_payload=False,
            name=f"{kinetix_standard_det.name}_stream",
        )
        yield from bps.sleep(0.01)

    yield from bps.close_run()

    panda_val = yield from bps.rd(writer.hdf.num_captured)
    kinetix_val = yield from bps.rd(kinetix_writer.hdf.num_captured)
    print(f"{panda_val = }    {kinetix_val = }")

    yield from bps.unstage_all(*kinetix_detectors)

    # Reset the velocity back to high.
    yield from bps.mv(tomo_rot_axis.velocity, reset_speed)


file_loading_timer.stop_timer(__file__)
