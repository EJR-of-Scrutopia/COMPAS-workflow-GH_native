"""The real-study script's reading and drawing, on the toy's capture document
(spec 2026-10-09 section 7)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")
pytest.importorskip("matplotlib")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "scripts"))
sys.path.insert(0, str(REPO / "bench" / "studio"))

import formwork_real  # noqa: E402
import solve_formwork  # noqa: E402
from test_solve_formwork import _request  # noqa: E402


def test_the_script_reads_and_draws_a_capture_document(tmp_path):
    document = solve_formwork.solve(_request())
    lines = formwork_real.summary_lines(document)
    assert lines[0].startswith("7 captures in ") and lines[0].endswith(": 2.3 mm")
    assert [line.split()[0] for line in lines[4:]] == ["raise", "finish", "hold"] + ["tiling"] * 4
    written = formwork_real.render(document, tmp_path)
    assert [path.name for path in written] == [
        "end-of-raise-tension.png", "end-of-raise-deviation.png",
        "last-course-tension.png", "last-course-deviation.png", "sequence.png"]
    assert all(path.stat().st_size > 10000 for path in written)
