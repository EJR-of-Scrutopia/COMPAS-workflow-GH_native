from __future__ import annotations

import json
import math
from pathlib import Path

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]
TRIAL_2 = REPO / "bench" / "demo" / "upload from grasshopper" / "Trial 2-contract.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry
    import segmentation

    return geometry, segmentation


def ring_centroids():
    """36 centroids on two circles plus one at the centre: known rings."""

    points = []
    for radius, count in ((10.0, 24), (5.0, 12)):
        for i in range(count):
            angle = 2.0 * math.pi * i / count
            points.append([radius * math.cos(angle), radius * math.sin(angle), 0.0])
    points.append([0.0, 0.0, 0.0])
    return points


def test_every_face_is_assigned_exactly_once():
    _, seg = studio()
    points = ring_centroids()
    result = seg.segment_faces(points, rings=3)
    assert len(result["assignment"]) == len(points)
    assert all(len(pair) == 2 for pair in result["assignment"])


def test_outermost_is_ring_zero_and_innermost_is_the_last_ring():
    _, seg = studio()
    points = ring_centroids()
    result = seg.segment_faces(points, rings=3)
    assert result["assignment"][0][0] == 0          # on the 10.0 circle
    assert result["assignment"][-1][0] == 2         # the centre point


def test_wedge_counts_shrink_toward_the_crown():
    _, seg = studio()
    result = seg.segment_faces(ring_centroids(), rings=3)
    counts = result["wedge_counts"]
    assert len(counts) == 3
    assert counts[0] == 12
    assert counts[0] >= counts[1] >= counts[2] >= 1


def test_placement_order_is_rim_first_and_sweeps_by_angle():
    _, seg = studio()
    result = seg.segment_faces(ring_centroids(), rings=3)
    order = result["order"]
    rings_in_order = [pair[0] for pair in order]
    assert rings_in_order == sorted(rings_in_order)
    ring0 = [pair[1] for pair in order if pair[0] == 0]
    assert ring0 == sorted(ring0)


def test_order_only_contains_occupied_cells():
    _, seg = studio()
    result = seg.segment_faces(ring_centroids(), rings=3)
    occupied = {tuple(pair) for pair in result["assignment"]}
    assert {tuple(pair) for pair in result["order"]} == occupied


def test_determinism():
    _, seg = studio()
    points = ring_centroids()
    assert seg.segment_faces(points, rings=5) == seg.segment_faces(points, rings=5)


def test_segment_key_format():
    _, seg = studio()
    assert seg.segment_key(0, 11) == "r0w11"


def test_the_committed_parity_fixtures_still_hold():
    """The rule is pinned on the real export for the JS mirror to check against.

    If this fails after an intentional rule change, regenerate with:
    .venv\\Scripts\\python.exe tests/studio/make_fixtures.py
    and re-verify binning.js against the new fixtures by loading the studio.
    """

    geometry, seg = studio()
    contract = geometry.load_contract(TRIAL_2)
    arrays = geometry.mesh_arrays(contract)
    centroids = geometry.face_centroids(arrays["vertices"], arrays["faces"])
    for rings in (4, 8, 12):
        expected = json.loads(
            (FIXTURES / "trial-2-r{}.json".format(rings)).read_text(encoding="utf-8")
        )
        result = seg.segment_faces(centroids, rings=rings)
        assert result["assignment"] == expected["assignment"]
        assert result["wedge_counts"] == expected["wedge_counts"]
