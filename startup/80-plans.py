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
