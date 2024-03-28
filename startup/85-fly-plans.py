file_loading_timer.start_timer(__file__)

# Number of encoder counts for an entire revolution
COUNTS_PER_REVOLUTION = 72000
DEG_PER_REVOLUTION = 360
COUNTS_PER_DEG = COUNTS_PER_REVOLUTION / DEG_PER_REVOLUTION
ZERO_OFFSET = 39660

TOMO_ROTARY_STAGE_FAST_VELO = 30


def tomo_demo_async(num_images=1801, scan_time=20, start_deg=0, exposure_time=0.015):

    panda1_pcomp_1 = dict(panda1_async.pcomp.children())["1"]

    step_width_counts = COUNTS_PER_REVOLUTION / (2 * (num_images - 1))
    if int(step_width_counts) != round(step_width_counts, 5):
        raise ValueError(
            "The number of encoder counts per pulse is not an integer value!"
        )

    step_time = scan_time / num_images
    camera_exposure_time = step_time / 2
    if exposure_time is not None:
        if exposure_time > step_time:
            raise RuntimeError(
                f"Your configured exposure time is longer than the step size {step_time}"
            )
    camera_exposure_time = exposure_time

    kinetix_exp_setup = KinetixTriggerSetup(
        num_images=num_images,
        exposure_time=camera_exposure_time,
        software_trigger=False,
    )

    yield from bps.mv(
        tomo_rot_axis.velocity, TOMO_ROTARY_STAGE_FAST_VELO
    )  # Make it fast to move to the start position
    yield from bps.mv(tomo_rot_axis, start_deg - 20)
    yield from bps.mv(
        tomo_rot_axis.velocity, 180 / scan_time
    )  # Set the velocity for the scan
    start_encoder = -1 * (start_deg * COUNTS_PER_DEG + ZERO_OFFSET)

    width_in_counts = (180 / scan_time) * COUNTS_PER_DEG * exposure_time
    if width_in_counts > step_width_counts:
        raise RuntimeError(
            f"Your specified exposure time of {exposure_time}s is too long! Calculated width: {width_in_counts}, Step size: {step_width_counts}"
        )
    print(f"Exposing camera for {width_in_counts} counts")

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
    yield from bps.stage_all(kinetix_standard_det, kinetix_flyer)
    assert kinetix_flyer._trigger_logic.state == KinetixTriggerState.stopping
    yield from bps.prepare(kinetix_flyer, kinetix_exp_setup, wait=True)
    yield from bps.prepare(kinetix_standard_det, kinetix_flyer.trigger_info, wait=True)

    yield from bps.stage_all(panda_standard_det, panda_flyer)
    assert panda_flyer._trigger_logic.state == KinetixTriggerState.stopping
    yield from bps.prepare(panda_flyer, num_images, wait=True)
    yield from bps.prepare(panda_standard_det, panda_flyer.trigger_info, wait=True)

    yield from bps.mv(tomo_rot_axis, start_deg + DEG_PER_REVOLUTION / 2 + 5)

    detector = panda_standard_det
    # detector.controller.disarm.assert_called_once  # type: ignore

    yield from bps.open_run()

    yield from bps.kickoff(panda_flyer)
    yield from bps.kickoff(detector)

    yield from bps.complete(panda_flyer, wait=True, group="complete")
    yield from bps.complete(detector, wait=True, group="complete")

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
            detector,
            stream=True,
            return_payload=False,
            name=f"{detector.name}_stream",
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

    # TODO: use AsyncStatus to wait for a 'Done' writing signal
    while (yield from bps.rd(kinetix_hdf_status)) != "Done":
        yield from bps.sleep(1)

    yield from bps.unstage_all(panda_flyer, detector)
    yield from bps.unstage_all(kinetix_flyer, kinetix_standard_det)

    # Reset the velocity back to high.
    yield from bps.mv(tomo_rot_axis.velocity, TOMO_ROTARY_STAGE_FAST_VELO)


file_loading_timer.stop_timer(__file__)
