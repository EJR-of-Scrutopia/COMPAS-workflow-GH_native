"""The Cable net tab's player buttons (his ask of 11 October 2026): the one
on the left goes back to the start, the one on the right on to the start of
the next scene (the raise, the finish, the hold, the jacking, each row of
tiles), not one capture."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

CAPTURES = [
    {"phase": "raise", "time": 30}, {"phase": "raise", "time": 32},
    {"phase": "finish", "time": 62}, {"phase": "finish", "time": 64},
    {"phase": "hold", "time": 90}, {"phase": "holds", "time": None},
    {"phase": "tiling", "row": "S1", "quarter": 1}, {"phase": "tiling", "row": "S1", "quarter": 2},
    {"phase": "tiling", "row": "S2", "quarter": 1}, {"phase": "tiling", "row": "S2", "quarter": 2},
    {"phase": "tiling", "row": "S4", "quarter": 1},
]

HARNESS = """
import * as m from %(module)r;
const captures = %(captures)s;
console.log(JSON.stringify({
  next: captures.map((_, i) => m.nextScene(captures, i)),
  none: [m.nextScene([], 0), m.nextScene(null, 0)],
}));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork_player") / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "formwork_model.js").resolve().as_uri(),
                                 "captures": json.dumps(CAPTURES)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_on_goes_to_the_first_capture_of_the_next_scene(out):
    # raise 0-1, finish 2-3, hold 4, the jacking 5, rows S1 6-7, S2 8-9, S4 10;
    # from the last scene, the last capture
    assert out["next"] == [2, 2, 4, 4, 5, 6, 8, 8, 10, 10, 10]
    assert out["none"] == [0, 0]


def test_the_buttons_go_to_the_start_and_on_a_scene():
    js = (STATIC / "formwork.js").read_text(encoding="utf-8")
    assert 'el.back.addEventListener("click", () => goTo(0));' in js
    assert "goTo(nextScene(tab.judged.captures, head.nearer))" in js
    assert "function step(" not in js
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert ('<button id="formwork-back" class="icon-act" type="button" title="Back to the start">'
            in html)
    assert '<button id="formwork-on" class="icon-act" type="button" title="On to the next scene">' in html
