file_loading_timer.start_timer(__file__)

# Number of encoder counts for an entire revolution
COUNTS_PER_REVOLUTION = 72000
DEG_PER_REVOLUTION = 360
COUNTS_PER_DEG = COUNTS_PER_REVOLUTION / DEG_PER_REVOLUTION
ZERO_OFFSET = 39660

KINETIX_MAX_FRAMERATES = {
    KinetixReadoutMode.sensitivity: 80,
    KinetixReadoutMode.speed: 250,
    KinetixReadoutMode.dynamic_range: 75
}


TOMO_ROTARY_STAGE_VELO_RESET_MAX = 30
TOMO_ROTARY_STAGE_VELO_SCAN_MAX= 60

def tomo_demo_async(num_images=1801, scan_time=20, start_deg=0, stop_deg=180, lead_angle=10, exposure_time=0.015, reset_speed=TOMO_ROTARY_STAGE_VELO_RESET_MAX):
    """Simple hardware triggered flyscan tomography

    Parameters
    ----------
    num_images : int
        number of camera images/angles
    scan_time : float
        time for the movement from 0 to 180 degrees, in seconds.
    start_deg : float
        starting point in degrees
    exposure_time : float
        exposure time to use on the camera, in seconds
    reset_speed : float
        speed of the rotary motor during reset movements, in deg/s
    """

    detectors = [panda_flyer, kinetix_flyer, panda_standard_det, kinetix_standard_det]

    panda1_pcomp_1 = dict(panda1_async.pcomp.children())["1"]

    mtr_reset_vel = reset_speed
    if mtr_reset_vel > TOMO_ROTARY_STAGE_VELO_RESET_MAX:
        mtr_reset_vel = TOMO_ROTARY_STAGE_VELO_RESET_MAX

    duration = scan_time
    rot_motor_vel = (stop_deg - start_deg) / scan_time
    if rot_motor_vel > TOMO_ROTARY_STAGE_VELO_SCAN_MAX:
        rot_motor_vel = TOMO_ROTARY_STAGE_VELO_SCAN_MAX
        duration = abs(stop_deg - start_deg) /rot_motor_vel

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
    
    step_width_counts = COUNTS_PER_REVOLUTION / ((DEG_PER_REVOLUTION / (stop_deg - start_deg)) * (num_images - 1))
    if int(step_width_counts) != round(step_width_counts, 5):
        raise ValueError(
            "The number of encoder counts per pulse is not an integer value!"
        )

    kinetix_exp_setup = KinetixTriggerSetup(
        num_images=num_images,
        exposure_time=exposure_time,
        software_trigger=False,
    )


    yield from bps.mv(
        tomo_rot_axis.velocity, reset_speed
    )  # Make it fast to move to the start position
    yield from bps.mv(tomo_rot_axis, start_deg - lead_angle)
    yield from bps.mv(
        tomo_rot_axis.velocity, rot_motor_vel
    )  # Set the velocity for the scan
    start_encoder = -1 * (start_deg * COUNTS_PER_DEG + ZERO_OFFSET)

    # Set up the pcomp block
    yield from bps.mv(panda1_pcomp_1.start, int(start_encoder))

    # Uncomment if using gate trigger mode on camera
    # yield from bps.mv(
    #    panda_pcomp_1.width, width_in_counts
    # )  # Width in encoder counts that the pulse will be high
    yield from bps.mv(panda1_pcomp_1.step, step_width_counts)
    yield from bps.mv(panda1_pcomp_1.pulses, num_images)


    # The setup below is happening in the VimbaController's arm method.
    # # Setup camera in trigger mode
    # yield from bps.mv(kinetix_async.trigger_mode, "On")
    # yield from bps.mv(kinetix_async.trigger_source, "Line1")
    # yield from bps.mv(kinetix_async.overlap, "Off")
    # yield from bps.mv(kinetix_async.expose_out_mode, "TriggerWidth")  # "Timed" or "TriggerWidth"

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

    # Move rotation axis to the stop position + the lead angle
    yield from bps.mv(tomo_rot_axis, start_deg + stop_deg + lead_angle)
    yield from bps.open_run()



    for flyer_or_det in detectors:
        yield from bps.kickoff(flyer_or_det)
        yield from bps.complete(flyer_or_det, wait=True, group="complete")

    # Manually incremenet the index as if a frame was taken
    # detector.writer.index += 1

    done = False
    while not done:
        try:
            yield from bps.wait(group="complete", timeout=0.5)
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
        yield from bps.collect(
            kinetix_standard_det,
            stream=True,
            return_payload=False,
            name=f"{kinetix_standard_det.name}_stream",
        )
        yield from bps.sleep(0.01)

    yield from bps.wait(group="complete")
    yield from bps.close_run()

    panda_val = yield from bps.rd(writer.hdf.num_captured)
    kinetix_val = yield from bps.rd(kinetix_writer.hdf.num_captured)
    print(f"{panda_val = }    {kinetix_val = }")

    yield from bps.unstage_all(*detectors)


    # Reset the velocity back to high.
    yield from bps.mv(tomo_rot_axis.velocity, reset_speed)


file_loading_timer.stop_timer(__file__)
