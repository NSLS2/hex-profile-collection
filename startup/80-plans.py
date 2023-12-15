def example_plan(motor, list_of_positions):

    for pos in list_of_positions:
        yield from mv(motor, pos)
        yield from count([germanium_detector])


def example_plan_2():
    yield from example_plan()


def acquire_germ_detector(count_time, detector=germ_detector, num=1):
    yield from bps.mv(detector.count_time, count_time)
    uid = (yield from bp.count([detector], num=num))
    return uid


def count_germ(count_time=1, num=10, detector=germ_detector_hdf5):
    yield from bps.mv(detector.count_time, count_time)
    uid = (yield from bp.count([detector], num=num))
    return uid


def sweep_motion(detector, count_time, motor, start, stop, max_moves=1000):
    init_pos = yield from bps.rd(motor)
    print(f"{init_pos = }")
    yield from bps.mv(motor, start)

    def check_if_done():
        status = detector.count.get(as_string=True)
        if status == "Done":
            return True
        else:
            return False

    @bpp.stage_decorator([detector])
    @bpp.run_decorator()
    def inner():
        yield from bps.mv(detector.count_time, count_time)
        yield from bps.trigger(detector, wait=False, group="germ")

        counter = 0
        while True:
            if counter % 2 == 0:
                target = stop
            else:
                target = start

            yield from bps.mv(motor, target)
            if check_if_done():
                break

            counter += 1
            if counter >= max_moves:
                break

        # TODO: fix the interrupt
        yield from bps.wait(group="germ")
        yield from bps.create(name="primary")
        reading = (yield from bps.read(detector))
        yield from bps.save()

        return reading

    def final_plan():
        yield from bps.mv(motor, init_pos)

    return (yield from bpp.finalize_wrapper(inner(), final_plan()))
