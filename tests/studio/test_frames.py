"""bench.frames/1: the reader's validation and pairing gates.

The writer side is specified in FRAMES-WRITER-SPEC-2026-09-03.md (the
contract between the two live sessions; its section 6 lists the six
guarantees the reader may and should enforce). The toy fixture below is
the spec's own section 7 file, which deliberately omits the 60 and 90
phase boundaries: the spec instructs that "the reader's validator should
flag their absence, and the test for the validator can use exactly this
file to prove it". So it does.

Pairing (guarantees 4 and 5) is a separate gate returning a reason
string rather than raising, because R-004 in
REQUESTS-for-plugin-session.md records the agreed behaviour: a frames
file that disagrees with the CURRENT contract is an unpaired leftover
(formwork act absent, one disclosed reason), never an error that blocks
the study.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import frames

    return frames


def spec_toy_fixture():
    """Section 7 of the writer spec, verbatim in structure."""

    return {
        "schema": "bench.frames/1",
        "units": "m",
        "study": "fixture",
        "vertexCount": 3,
        "columnNodeCount": 2,
        "frames": [
            {"time": 0.0, "phase": "reel",
             "vertices": [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
             "columnNodes": [[0.5, 0, 0], [0.5, 0, 0]]},
            {"time": 30.0, "phase": "raise",
             "vertices": [[0, 0, 0], [1, 0, 0.4], [2, 0, 0]],
             "columnNodes": [[0.5, 0, 0], [0.5, 0, 0.2]]},
            {"time": 100.0, "phase": "hold",
             "vertices": [[0, 0, 0], [1, 0, 1], [2, 0, 0]],
             "columnNodes": [[0.5, 0, 0], [0.5, 0, 0.5]]},
        ],
    }


def complete_fixture():
    """The toy fixture with the missing 60 and 90 boundaries filled in."""

    document = spec_toy_fixture()
    document["frames"].insert(2, {
        "time": 60.0, "phase": "finish",
        "vertices": [[0, 0, 0], [1, 0, 0.7], [2, 0, 0]],
        "columnNodes": [[0.5, 0, 0], [0.5, 0, 0.35]],
    })
    document["frames"].insert(3, {
        "time": 90.0, "phase": "hold",
        "vertices": [[0, 0, 0], [1, 0, 0.95], [2, 0, 0]],
        "columnNodes": [[0.5, 0, 0], [0.5, 0, 0.475]],
    })
    return document


def matching_contract():
    """A contract whose equilibrium.vertices equal the complete fixture's
    time-100 frame, in the {x, y, z} dict shape real contracts carry."""

    return {
        "equilibrium": {
            "vertices": [
                {"x": 0.0, "y": 0.0, "z": 0.0},
                {"x": 1.0, "y": 0.0, "z": 1.0},
                {"x": 2.0, "y": 0.0, "z": 0.0},
            ],
        },
    }


def test_the_spec_toy_fixture_is_flagged_for_its_missing_boundaries():
    f = studio()
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(spec_toy_fixture())
    message = str(caught.value)
    assert "60" in message and "90" in message, message


def test_a_complete_document_validates_and_comes_back_normalised():
    f = studio()
    document = f.validate_frames_document(complete_fixture())
    times = [frame["time"] for frame in document["frames"]]
    assert times == [0.0, 30.0, 60.0, 90.0, 100.0]
    assert document["vertexCount"] == 3
    assert document["columnNodeCount"] == 2


def test_schema_prefix_and_version_are_both_enforced():
    f = studio()
    wrong = complete_fixture()
    wrong["schema"] = "bench.tessellation/1"
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(wrong)
    assert "bench.tessellation/1" in str(caught.value)

    future = complete_fixture()
    future["schema"] = "bench.frames/2"
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(future)
    assert "bench.frames/2" in str(caught.value)


def test_units_other_than_metres_are_refused_naming_the_value():
    f = studio()
    document = complete_fixture()
    document["units"] = "mm"
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(document)
    assert "mm" in str(caught.value)


def test_times_must_be_strictly_ascending():
    f = studio()
    document = complete_fixture()
    document["frames"][1]["time"] = 0.0
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(document)
    assert "ascending" in str(caught.value).lower()


def test_the_ends_of_the_timeline_must_be_present():
    f = studio()
    document = complete_fixture()
    document["frames"][0]["time"] = 1.0
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(document)
    assert "0" in str(caught.value)


def test_every_frame_is_shape_checked_against_the_declared_counts():
    f = studio()
    document = complete_fixture()
    document["frames"][2]["vertices"] = document["frames"][2]["vertices"][:2]
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(document)
    assert "vertexCount" in str(caught.value)

    document = complete_fixture()
    document["frames"][1]["columnNodes"] = []
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(document)
    assert "columnNodeCount" in str(caught.value)


def test_non_finite_coordinates_are_refused():
    f = studio()
    document = complete_fixture()
    document["frames"][1]["vertices"][1][2] = float("nan")
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(document)
    assert "finite" in str(caught.value).lower()


def test_phase_labels_come_from_the_four_words():
    f = studio()
    document = complete_fixture()
    document["frames"][1]["phase"] = "levitate"
    with pytest.raises(ValueError) as caught:
        f.validate_frames_document(document)
    assert "levitate" in str(caught.value)


def test_pairing_accepts_a_contract_the_frames_were_written_for():
    f = studio()
    document = f.validate_frames_document(complete_fixture())
    assert f.pairing_error(document, matching_contract()) is None


def test_pairing_refuses_a_set_mixed_from_two_solves():
    f = studio()
    document = f.validate_frames_document(complete_fixture())
    contract = matching_contract()
    contract["equilibrium"]["vertices"].append({"x": 9.0, "y": 9.0, "z": 9.0})
    reason = f.pairing_error(document, contract)
    assert reason is not None
    assert "3" in reason and "4" in reason, reason


def test_pairing_refuses_a_stale_frames_file_by_the_time_100_check():
    f = studio()
    document = f.validate_frames_document(complete_fixture())
    contract = matching_contract()
    contract["equilibrium"]["vertices"][1]["z"] = 1.5
    reason = f.pairing_error(document, contract)
    assert reason is not None
    assert "100" in reason, reason
