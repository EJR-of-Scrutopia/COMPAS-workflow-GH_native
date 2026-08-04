from __future__ import annotations

import json

import pytest

from ananke_equilibrium.cli.study import factor_warnings
from ananke_equilibrium.cli.sweep import SweepError
from ananke_equilibrium.cli.sweep import deep_merge
from ananke_equilibrium.cli.sweep import format_sweep
from ananke_equilibrium.cli.sweep import load_cases


def test_deep_merge_recurses_into_nested_objects():
    base = {"load_case": {"name": "a", "vectors": [[0, 0, -1]]}, "keep": 1}
    patch = {"load_case": {"name": "b"}}
    merged = deep_merge(base, patch)
    assert merged["load_case"] == {"name": "b", "vectors": [[0, 0, -1]]}
    assert merged["keep"] == 1


def test_deep_merge_replaces_lists_wholesale():
    base = {"load_case": {"vectors": [[0, 0, -1], [0, 0, -2]]}}
    patch = {"load_case": {"vectors": [[0, 0, -9]]}}
    assert deep_merge(base, patch)["load_case"]["vectors"] == [[0, 0, -9]]


def test_deep_merge_does_not_mutate_the_base():
    base = {"load_case": {"name": "a"}}
    deep_merge(base, {"load_case": {"name": "b"}})
    assert base["load_case"]["name"] == "a"


def test_deep_merge_deep_copies_patched_values():
    patch = {"load_case": {"vectors": [[0, 0, -1]]}}
    merged = deep_merge({}, patch)
    merged["load_case"]["vectors"][0][2] = -99
    assert patch["load_case"]["vectors"][0][2] == -1


def write_cases(tmp_path, document):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_load_cases_reads_a_valid_file(tmp_path):
    path = write_cases(tmp_path, [{"name": "base", "patch": {}}])
    assert load_cases(path) == [{"name": "base", "patch": {}}]


def test_load_cases_rejects_an_empty_array(tmp_path):
    with pytest.raises(SweepError, match="non-empty"):
        load_cases(write_cases(tmp_path, []))


def test_load_cases_requires_a_name(tmp_path):
    with pytest.raises(SweepError, match="name"):
        load_cases(write_cases(tmp_path, [{"patch": {}}]))


def test_load_cases_rejects_a_missing_file(tmp_path):
    with pytest.raises(SweepError, match="does not exist"):
        load_cases(tmp_path / "absent.json")


def outcome(name, tension=0, residual=0.0, ok=True):
    return {
        "name": name,
        "ok": ok,
        "message": None if ok else "solve failed",
        "code": None,
        "result": None,
        "summary": {
            "geometry": {"rise": 3.0, "span_x": 10.0},
            "forces": {
                "min": -2.0,
                "max": -1.0,
                "compression": 60,
                "tension": tension,
            },
            "actions": {"residual_magnitude": residual},
        },
    }


def test_all_compression_is_reported_as_still_funicular():
    text = format_sweep([outcome("self weight"), outcome("snow")])
    assert "wholly in compression" in text
    assert "Tension appears" not in text


def test_tension_is_called_out_by_case_name():
    text = format_sweep([outcome("self weight"), outcome("snow", tension=4)])
    assert "Tension appears under: snow" in text
    assert "wholly in compression" not in text


def test_an_unbalanced_case_is_called_out():
    text = format_sweep([outcome("odd", residual=1.0)])
    assert "Global equilibrium residual exceeds" in text
    assert "odd" in text


def test_a_failed_case_does_not_hide_behind_a_blank_row():
    text = format_sweep([outcome("bad", ok=False)])
    assert "FAILED" in text


def test_factor_warning_fires_only_when_the_factor_would_be_ignored():
    assert factor_warnings({"load_case": {"factor": 1.0}}) == []
    assert factor_warnings({"load_case": {}}) == []
    assert factor_warnings({}) == []
    warnings = factor_warnings({"load_case": {"factor": 3.0}})
    assert len(warnings) == 1
    assert "does not apply it" in warnings[0]
