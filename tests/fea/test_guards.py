"""Guards for the ways this package can silently produce zeros.

Each of these corresponds to a failure that reports success. They are worth
more than most of the feature tests, because a crash gets investigated and a
plausible zero gets presented.
"""

from __future__ import annotations

import pytest

from ananke_fea.analyses import COMBINATION_FACTORS, LOAD_CASE
from ananke_fea.compat import analyse, apply_patches, require_backend


def test_the_load_case_is_one_the_combination_recognises():
    """A load case ULS does not know is dropped without warning, and the
    model then solves with no load at all."""

    require_backend()
    from compas_fea2.problem import LoadCombination

    assert LOAD_CASE in LoadCombination.ULS().factors
    assert LOAD_CASE in LoadCombination.SLS().factors


def test_the_uls_factor_matches_what_the_library_applies():
    require_backend()
    from compas_fea2.problem import LoadCombination

    assert COMBINATION_FACTORS["ULS"] == LoadCombination.ULS().factors[LOAD_CASE]
    assert COMBINATION_FACTORS["SLS"] == LoadCombination.SLS().factors[LOAD_CASE]


def test_the_node_loads_shim_is_still_needed_and_still_works():
    """If a future bump restores the property upstream, this tells us the
    shim can go rather than leaving it to rot."""

    require_backend()
    apply_patches()
    from compas_fea2.model import Node

    assert isinstance(Node.loads, property)


def test_the_stress_jobdata_patch_is_still_needed_and_still_applied():
    """The upstream stub returns the bare token "S". If a future pin fixes
    it, this says the patch can go; until then it must be applied."""

    require_backend()
    apply_patches()
    from compas_fea2_opensees.results.fields import OpenseesStressFieldResults

    assert getattr(
        OpenseesStressFieldResults.jobdata, "_ananke_patch", False
    ), "the stress jobdata patch is no longer applied"


def test_analyse_refuses_a_directory_that_would_make_it_prompt(tmp_path):
    """compas_fea2 calls input() on an existing output directory, which
    hangs a non-interactive run forever."""

    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "leftover.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        analyse(object(), busy)


def test_analyse_and_extract_is_not_used_anywhere():
    """It double-inserts every result row, so every sum comes out doubled.

    compat.py and results.py are excluded from the scan: both name
    analyse_and_extract only in prose, to document why they avoid it
    (compat.py's module docstring explains the double-insert bug;
    results.py's explains why it goes through compat.analyse instead).
    Neither calls it.
    """

    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "src" / "ananke_fea"
    documenting_only = {"compat.py", "results.py"}
    offenders = [
        str(module.name)
        for module in source.rglob("*.py")
        if "analyse_and_extract" in module.read_text(encoding="utf-8")
        and module.name not in documenting_only
    ]
    assert offenders == []


def test_no_production_code_reads_the_garbage_stress_table():
    """extract_results pads the raw s.out rows into the DB table "s", which
    is meaningless for shells. Nothing of ours may read it: the honest
    route is the raw file via results._parse_resultants.

    results.py itself is excluded from the scan: its stress_summary
    docstring names step.stress_field.results only to explain why the
    function deliberately bypasses it, not because it reads it.
    """

    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "src" / "ananke_fea"
    offenders = [
        module.name
        for module in source.rglob("*.py")
        if "stress_field.results" in module.read_text(encoding="utf-8")
        and module.name != "results.py"
    ]
    assert offenders == []
