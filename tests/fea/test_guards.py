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

    Matches the call pattern .analyse_and_extract( rather than the bare
    word, so prose describing the defect cannot retrip this guard. That is
    what lets compat.py and results.py talk about the wrapper in their own
    docstrings (as "the double-extracting convenience wrapper") without
    being excluded from the scan: every file under src/ananke_fea is
    scanned, none excluded, and neither of them calls it.
    """

    import re
    from pathlib import Path

    pattern = re.compile(r"\.analyse_and_extract\s*\(")
    source = Path(__file__).resolve().parents[2] / "src" / "ananke_fea"
    offenders = [
        str(module.name)
        for module in source.rglob("*.py")
        if pattern.search(module.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_no_production_code_reads_the_garbage_stress_table():
    """extract_results pads the raw s.out rows into the DB table "s", which
    is meaningless for shells. Nothing of ours may read it: the honest
    route is the raw file via results._parse_resultants.

    Matches the attribute pattern stress_field.results rather than the bare
    words, so results.py's own docstring, which explains why
    stress_summary deliberately bypasses that attribute (calling it "the
    step's stress field attribute" instead of naming it), cannot retrip
    this guard. Every file under src/ananke_fea is scanned, none excluded.
    """

    import re
    from pathlib import Path

    pattern = re.compile(r"stress_field\.results")
    source = Path(__file__).resolve().parents[2] / "src" / "ananke_fea"
    offenders = [
        module.name
        for module in source.rglob("*.py")
        if pattern.search(module.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_fea_environment_pin_has_not_moved():
    """The backend imports BeamSection, which core removed after 664ec20.
    A moved pin fails at import in confusing ways; this fails plainly."""

    import json
    from importlib.metadata import distribution

    direct = json.loads(
        distribution("compas_fea2").read_text("direct_url.json") or "{}"
    )
    commit = direct.get("vcs_info", {}).get("commit_id", "")
    assert commit.startswith("664ec20"), (
        "compas_fea2 is installed from commit {!r}, not the 664ec20 pin".format(commit)
    )
