from __future__ import annotations

import subprocess
import sys


def test_the_checks_module_is_standard_library_only():
    # bench/studio imports this module; the studio guard forbids numpy there,
    # and a transitive import would pass the guard's regex while coupling the
    # server to the solver stack all the same. So it is checked at runtime.
    script = (
        "import sys\n"
        "import tree_forest_compas.mechanism as m\n"
        "m.capacity_from_curve\n"
        "bad = [n for n in ('numpy', 'scipy', 'compas', 'compas_fd') if n in sys.modules]\n"
        "assert not bad, bad\n"
        "print('clean')\n"
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "clean"


def test_capacity_still_exports_the_same_objects():
    from tree_forest_compas import capacity, mechanism
    assert capacity.capacity_from_curve is mechanism.capacity_from_curve
    assert capacity.CurvePoint is mechanism.CurvePoint
    assert capacity.TensionCurve is mechanism.TensionCurve
    assert capacity.Capacity is mechanism.Capacity


def _mechanism(**kwargs):
    from tree_forest_compas.mechanism import Mechanism
    base = dict(
        drum_radius=36.0, reeve_factor=1, gear_ratio=20.0, motor_torque=1.0e7,
        gear_efficiency=0.94, rope_mbl=1.0e6, anchor_wll=1000.0,
    )
    base.update(kwargs)
    return Mechanism(**base)


def _curve(tension_per_factor, deviation, steps=20, max_factor=10.0):
    from tree_forest_compas.mechanism import CurvePoint, TensionCurve
    points = tuple(
        CurvePoint(factor=max_factor * k / steps,
                   worst_tension=tension_per_factor * max_factor * k / steps,
                   deviation=deviation)
        for k in range(1, steps + 1)
    )
    return TensionCurve(points, steps, max_factor)


def test_a_synthetic_curve_binds_on_the_anchor_at_the_right_rung():
    from tree_forest_compas.mechanism import capacity_from_curve
    # 300 N per unit factor against a 1000 N anchor: 3.0 passes (900), 3.5
    # breaches (1050)
    result = capacity_from_curve(_mechanism(), _curve(300.0, 0.0), acceptance=50.0)
    assert result.binding == "anchor"
    assert result.limit_factor == 3.0
    assert result.breaching_factor == 3.5
    assert "1050" in result.detail


def test_no_acceptance_line_skips_the_deviation_check():
    from tree_forest_compas.mechanism import capacity_from_curve, checks
    huge = _curve(1.0, deviation=1.0e9)
    result = capacity_from_curve(_mechanism(), huge, acceptance=None)
    assert result.binding == "none"
    assert checks(_mechanism(), 10.0, 1.0e9, None) == (None, "")
    assert checks(_mechanism(), 10.0, 1.0e9, 50.0)[0] == "deviation"
