"""The page's half of the wires drawn as the rope chosen (Param, 2026-10-12):
the controls are on the page, the studio reads the ropes and saves the
default, the mechanisms are asked for the study's rope, the net and the
machines' wires wear the rope's look, and his modelled cable mesh gives way
to wires lofted at the rope's size (his answer: "Redraw at the rope's
size"). Behaviour is checked on screen; these pin the wiring."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
JS = (STATIC / "studio.js").read_text(encoding="utf-8")


def _section(html, ident):
    start = html.index('<details id="{}">'.format(ident))
    return html[start:html.index("</details>", start)]


def test_the_default_wire_is_set_in_the_import_section():
    assert '<select id="default-rope">' in _section(HTML, "import-section")


def test_the_cable_net_tab_has_the_wire_and_its_size_on_screen():
    tab = _section(HTML, "formwork-section")
    assert '<select id="rope-select">' in tab
    assert re.search(r'<input id="wire-scale" type="range" min="1" max="10" step="0.5" value="1">', tab)


def test_the_studio_reads_the_ropes_saves_the_default_and_asks_for_the_studys_rope():
    assert 'from "./wire_look_model.js"' in JS
    assert 'fetch("/api/ropes")' in JS
    assert '"/api/ropes/default"' in JS and 'method: "PUT"' in JS
    assert "rope: () => studyRopeKey()" in JS


def test_the_net_and_the_machines_wires_wear_the_ropes_look():
    assert JS.count("applyLookTo(") >= 4
    assert "function applyWireLook()" in JS
    # the machines' wires no longer wear the black of the principal lines
    assert "wireMaterial.color.set(CABLE_BLACK)" not in JS


def test_his_modelled_cable_mesh_gives_way_to_wires_at_the_ropes_size():
    assert "for (const part of cableParts)" not in JS
    assert "cableParts.length ? null : loftWire(" not in JS
    assert "const routed = loftWire(" in JS
