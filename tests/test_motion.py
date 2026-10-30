from aureum_island.island.motion import (
    FrameClock,
    close_curve,
    cubic_bezier,
    enter_curve,
    ramp,
    spring,
    spring_overshoot,
)


def test_spring_overshoots_a_little_and_settles():
    values = [spring(i / 400) for i in range(401)]
    assert values[0] == 0.0 and values[-1] == 1.0
    peak = max(values)
    assert 1.02 < peak < 1.035  # passa ~2,8% e volta
    assert abs(peak - 1 - spring_overshoot()) < 0.002
    assert spring(0.4) > 0.95  # chega ao tamanho cedo (~160 ms de 400)


def test_bezier_curves_are_monotonic_and_bounded():
    for curve in (close_curve, enter_curve, cubic_bezier(0.25, 0.1, 0.25, 1.0)):
        values = [curve(i / 100) for i in range(101)]
        assert values[0] == 0.0 and values[-1] == 1.0
        assert all(b >= a - 1e-9 for a, b in zip(values, values[1:], strict=False))
    assert abs(cubic_bezier(0, 0, 1, 1)(0.3) - 0.3) < 1e-3  # linear


def test_ramp():
    assert ramp(0.1, 0.2, 0.6) == 0.0
    assert abs(ramp(0.4, 0.2, 0.6) - 0.5) < 1e-9
    assert ramp(0.9, 0.2, 0.6) == 1.0


def test_frame_clock_runs_to_one_and_stops(qtbot):
    frames, done = [], []
    clock = FrameClock(60, frames.append, lambda: done.append(True))
    clock.start()
    assert frames == [0.0]
    qtbot.waitUntil(lambda: bool(done), timeout=1000)
    assert frames[-1] == 1.0
    assert not clock.running  # nenhum timer depois de terminar
    assert len(frames) > 3
