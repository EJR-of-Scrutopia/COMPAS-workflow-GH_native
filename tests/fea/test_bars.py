from __future__ import annotations

from pathlib import Path

import pytest

from ananke_fea import mesh as reader
from ananke_fea.analyses import run_static
from ananke_fea.bars import build_bar_model, cross_check, member_axial_forces
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS

UPLOAD = Path(__file__).resolve().parents[2] / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"

pytestmark = pytest.mark.skipif(
    not CONTRACT.is_file(), reason="the Trial 2 export is not present"
)


@pytest.fixture(scope="module")
def contract():
    return reader.load_contract(CONTRACT)


def test_every_vertex_and_edge_is_built(contract):
    require_backend()
    apply_patches()
    built = build_bar_model(contract, PRESETS["concrete"], 0.09)
    assert len(built.nodes) == 2521
    assert len(list(built.part.elements)) == 4800


def test_supports_come_from_the_resolved_list(contract):
    built = build_bar_model(contract, PRESETS["concrete"], 0.09)
    assert len(built.supports) == 123


def test_the_tolerance_defaults_to_the_files_own_residual(contract):
    """A hard-coded tolerance would be wrong the moment the solve improves."""

    outcome = type("Outcome", (), {"step": None, "combination_factor": 1.0})()
    checked = cross_check(contract, outcome, tolerance=None, reactions=(0.0, 0.0, 0.0))
    assert checked["residual_from_file"] == pytest.approx(2406.0, rel=0.05)
    assert checked["tolerance"] >= checked["residual_from_file"]


def test_agreement_is_reported_against_that_tolerance(contract):
    outcome = type("Outcome", (), {"step": None, "combination_factor": 1.0})()
    applied = reader.applied_total(contract)
    exact = cross_check(contract, outcome, reactions=(0.0, 0.0, applied))
    assert exact["agrees"] is True

    way_off = cross_check(contract, outcome, reactions=(0.0, 0.0, applied * 2))
    assert way_off["agrees"] is False


@pytest.fixture(scope="module")
def solved_tripod():
    """Three bars from a triangle of supports to one apex, solved.

    By statics the vertical load splits into three equal members at
    N = P / (3 cos b), b measured from vertical. This is chosen over a
    two-bar planar triangle: a frame confined to a single plane leaves the
    apex with zero stiffness normal to that plane, because both bar
    directions have a zero component out of it, which is a translational
    mechanism unrelated to what build_bar_model's beams are for. Three
    non-coplanar bars give the apex real translational stiffness in all
    three axes, and because build_bar_model now uses BeamElement, the apex
    also gets its rotations stiffened by the beams themselves; nothing is
    restrained on top of that.

    The load is 1000 kN, not a more modest 1 kN. Checked directly against
    the raw OpenSees output, the extraction pipeline that lands displacement
    values in the results database rounds to 6 decimal places, not 6
    significant figures: a true apex displacement of -0.0000028 m came back
    from the database as exactly -0.000003, a 6% error. At 1000 kN the same
    model deflects in the low millimetres, where 6 decimal places of
    absolute precision is far more digits than this test's rel=1e-3 needs.
    """

    require_backend()
    apply_patches()

    contract = {
        "equilibrium": {
            "vertices": [
                {"x": 1.0, "y": 0.0, "z": 0.0},
                {"x": -0.5, "y": 0.8660254037844386, "z": 0.0},
                {"x": -0.5, "y": -0.8660254037844386, "z": 0.0},
                {"x": 0.0, "y": 0.0, "z": 2.0},
            ],
            "edges": [
                {"u": 0, "v": 3},
                {"u": 1, "v": 3},
                {"u": 2, "v": 3},
            ],
            "memberForces": [
                -372.67799624996496,
                -372.67799624996496,
                -372.67799624996496,
            ],
            "loads": [
                {"nodeId": 3, "vector": {"x": 0.0, "y": 0.0, "z": -1000.0}},
            ],
            "reactions": [],
            "resolvedSupportNodeIds": [0, 1, 2],
            "diagnostics": [
                {"code": "global_force_error_norm", "value": 0.1},
            ],
        }
    }
    built = build_bar_model(contract, PRESETS["concrete"], 0.01)
    outcome = run_static(
        built, reader.node_loads(contract), combination="SLS", name="tripod"
    )
    return contract, built, outcome


def test_the_tripod_matches_statics(solved_tripod):
    contract, built, outcome = solved_tripod
    forces = member_axial_forces(
        built, contract, outcome, area=0.01, modulus=PRESETS["concrete"].modulus
    )
    expected = reader.member_forces(contract)
    assert len(forces) == len(expected)
    for got, want in zip(forces, expected):
        assert got == pytest.approx(want, rel=1e-3)


def test_cross_check_accepts_matching_member_forces(solved_tripod):
    contract, built, outcome = solved_tripod
    forces = member_axial_forces(
        built, contract, outcome, area=0.01, modulus=PRESETS["concrete"].modulus
    )
    checked = cross_check(contract, outcome, axial_forces=forces)
    assert checked["members_agree"] is True
    assert checked["member_count"] == 3
    # The tripod is statically determinate, so the strict form must hold
    # too: this is the fixture that proves strict_agrees is reachable at
    # all, not just a fallback name for when it is not.
    assert checked["strict_agrees"] is True


def test_cross_check_rejects_wrong_member_forces(solved_tripod):
    contract, built, outcome = solved_tripod
    wrong = [f * 3.0 for f in reader.member_forces(contract)]
    checked = cross_check(contract, outcome, axial_forces=wrong)
    assert checked["members_agree"] is False


def test_cross_check_splits_reaction_and_member_verdicts(solved_tripod):
    """No solving: a statically indeterminate network can legitimately
    disagree with TNA member by member while the wiring is still correct,
    so reactions_agree must be able to carry agrees even when
    strict_agrees cannot."""

    contract, _, _ = solved_tripod
    outcome = type("Outcome", (), {"step": None, "combination_factor": 1.0})()
    applied = reader.applied_total(contract)
    wrong = [force * 3.0 for force in reader.member_forces(contract)]

    checked = cross_check(
        contract, outcome, reactions=(0.0, 0.0, applied), axial_forces=wrong
    )
    assert checked["reactions_agree"] is True
    assert checked["members_agree"] is False
    assert checked["strict_agrees"] is False
    assert checked["agrees"] is True
    assert checked["member_note"]


def test_cross_check_rejects_a_length_mismatch(solved_tripod):
    """zip would silently truncate; this must fail loudly instead."""

    contract, built, outcome = solved_tripod
    with pytest.raises(ValueError, match="axial_forces has 2 members"):
        cross_check(contract, outcome, axial_forces=[0.0, 0.0])


def test_member_scaling_holds_at_uls(solved_tripod):
    """At ULS the FEA forces carry 1.35 and the TNA forces do not. A flipped
    scaling direction is invisible at SLS and off by 1.82x here, so this is
    the test that pins the direction."""

    contract, _, _ = solved_tripod
    built = build_bar_model(contract, PRESETS["concrete"], 0.01)
    outcome = run_static(
        built, reader.node_loads(contract), combination="ULS", name="tripod_uls"
    )
    forces = member_axial_forces(
        built, contract, outcome, area=0.01, modulus=PRESETS["concrete"].modulus
    )
    for got, want in zip(forces, reader.member_forces(contract)):
        assert got == pytest.approx(want * 1.35, rel=1e-3)

    checked = cross_check(contract, outcome, axial_forces=forces)
    assert checked["members_agree"] is True
    assert checked["strict_agrees"] is True
