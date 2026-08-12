"""A Grasshopper authored tessellation is a first class generator.

Every rule the schema states is enforced here, and every rejection names
the offending cell, because an author fixing a pattern in Grasshopper
needs to know which polygon to look at.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import tessellation
    return tessellation


def document(cells=None, **overrides):
    base = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": cells if cells is not None else [
            {"key": "a", "course": 0,
             "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {"key": "b", "course": 1,
             "outline": [[0, 1], [1, 1], [1, 2], [0, 2]]},
        ],
        "provenance": {"source": "Grasshopper", "author": "test"},
    }
    base.update(overrides)
    return base


def flat(x, y):
    return 0.0


def test_a_valid_document_is_accepted():
    t = studio()
    tess = t.from_document(document(), flat)
    assert tess["source"] == "imported"
    assert tess["pattern"] == "authored"
    assert len(tess["cells"]) == 2
    assert tess["provenance"]["author"] == "test"
    assert "coverage_holes" in tess["report"]
    assert "broken_boundary" in tess["report"]


def test_a_duplicate_key_is_rejected_by_name():
    t = studio()
    cells = [
        {"key": "same", "course": 0, "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
        {"key": "same", "course": 1, "outline": [[0, 1], [1, 1], [1, 2], [0, 2]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "same" in str(error.value)


def test_overlapping_cells_are_rejected_by_name():
    t = studio()
    cells = [
        {"key": "low", "course": 0, "outline": [[0, 0], [2, 0], [2, 2], [0, 2]]},
        {"key": "over", "course": 1, "outline": [[1, 1], [3, 1], [3, 3], [1, 3]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    message = str(error.value)
    assert "low" in message and "over" in message


def test_an_unknown_units_value_is_rejected_rather_than_guessed():
    t = studio()
    with pytest.raises(ValueError) as error:
        t.from_document(document(units="mm"), flat)
    assert "mm" in str(error.value)


def test_a_self_intersecting_outline_is_rejected_by_name():
    t = studio()
    cells = [{"key": "bowtie", "course": 0,
              "outline": [[0, 0], [1, 1], [1, 0], [0, 1]]}]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "bowtie" in str(error.value)


def test_a_supplied_z_is_measured_against_the_surface_not_used():
    t = studio()
    cells = [
        {"key": "a", "course": 0,
         "outline": [[0, 0, 0.5], [1, 0, 0.5], [1, 1, 0.5], [0, 1, 0.5]]},
    ]
    tess = t.from_document(document(cells), flat)
    assert tess["z_offset_max"] == pytest.approx(0.5)
    # The geometry is the plan only: z never reaches the point table.
    assert all(len(p) == 2 for p in tess["points"])


def test_a_missing_course_is_filled_in_and_disclosed():
    t = studio()
    cells = [{"key": "a", "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    tess = t.from_document(document(cells), flat)
    assert tess["cells"][0]["course"] == 0
    assert tess["courses_inferred"] is True


def test_the_contract_wins_over_the_sidecar(tmp_path):
    t = studio()
    sidecar = tmp_path / "x-tessellation.json"
    sidecar.write_text(json.dumps(document(pattern="sidecar")), encoding="utf-8")
    found = t.read_tessellation({"tessellation": document(pattern="contract")}, sidecar)
    assert found["pattern"] == "contract"
    found = t.read_tessellation({}, sidecar)
    assert found["pattern"] == "sidecar"
    assert t.read_tessellation({}, tmp_path / "missing.json") is None
