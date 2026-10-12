"""The column as specced, in the steel chosen, wired into the page (Param,
2026-10-12). His answers: a round tube at the chosen size with its wall
showing; Tube, Steel and Finish chosen in the Cable net tab and kept per
study, starting at the tube nearest the one the export swept; the run judging
the trees in that tube; and, on the 3 m prototype, "the coloured dots and the
columns are way too big. maybe there can be a scale slider"."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def _function(js, signature):
    start = js.index(signature)
    depth = 0
    for i in range(js.index("{", start), len(js)):
        depth += {"{": 1, "}": -1}.get(js[i], 0)
        if depth == 0:
            return js[start:i + 1]
    raise AssertionError(signature)


def test_tube_steel_and_finish_sit_in_the_mechanism_pop_up_and_marks_in_the_tab():
    # his word on seeing them squeezed into the panel (2026-10-12): "i think we
    # can put these in the mechanism drop down. make sure the drop down can
    # actually show the information inside"
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    start = html.index('<div id="mech-choose" class="mech-tab">')
    pane = html[start:html.index('<div id="mech-cost"', start)]
    for select, name in (("column-tube", "Tube"), ("column-grade", "Steel"),
                         ("column-finish", "Finish")):
        assert html.count('id="{}"'.format(select)) == 1, select
        assert ('<label class="mechanism-line" title="Column {}"><span>{}</span> '
                '<select id="{}"></select></label>').format(
                    {"Tube": "tube", "Steel": "steel", "Finish": "finish"}[name], name, select) in pane
    assert pane.index("mechanism-have") < pane.index("column-tube")
    # every dropdown in the pop-up takes the row's width, so its text shows
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "#mech-choose .mechanism-line select { flex: 1; min-width: 0; }" in css
    assert ('<input id="formwork-marks" type="range" min="0.1" max="2" step="0.05" value="1">'
            in html)
    assert '<b id="formwork-marks-value">1</b><em>x</em>' in html


def test_the_studio_keeps_each_studys_column_and_draws_every_column_in_it():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'from "./column_look_model.js";' in js
    assert 'import { tubeGeometry } from "./tube_geometry.js";' in js
    assert 'const COLUMN_PREFIX = "vaulted-column:";' in js
    assert 'fetch("/api/column-steel")' in _function(js, "async function loadColumnSteel()")
    choice = _function(js, "function studyColumn()")
    assert "columnChoice(stored, columnState.catalogue, exportColumnDiameterMm())" in choice
    assert "state.columnRadius * 2000" in _function(js, "function exportColumnDiameterMm()")
    # the act's members and the exported columns, both the tube chosen
    act = _function(js, "function rebuildFormworkObjects()")
    assert "columnTubeGeometry()" in act
    assert "applyLookTo(barMaterial, columnRender());" in act
    assert "new THREE.CylinderGeometry(radius, radius, 1, 8, 1, true)" not in act
    assert "columnMeshFor(columnDocument)" in _function(js, "function addColumnSolid(group, columnDocument)")
    solid = _function(js, "function columnMeshFor(columnDocument)")
    assert "columnTubeGeometry()" in solid
    assert "writeInstancedSegments(" in solid
    assert "columnGeometryFrom(columnDocument)" in solid, "a solid with no members still draws"
    # a choice redraws the columns, the act's by their geometry and finish
    # alone (a full rebuild would build the machine again on every Wall drag),
    # and judges the run again in it
    apply = _function(js, "function applyColumnLook()")
    assert "restyleActColumns();" in apply
    assert "redrawColumnSolids();" in apply
    restyle = _function(js, "function restyleActColumns()")
    assert "bars.geometry = columnTubeGeometry();" in restyle
    assert "applyLookTo(bars.material, columnRender());" in restyle
    # a study's load paints its column and draws it
    assert "paintColumnSelects();\n    applyColumnLook();" in js
    assert "formworkTab.columnChanged();" in apply
    mount = js[js.index("formworkTab = mountFormwork({"):]
    assert "column: () => currentColumnTube()," in mount[:mount.index("});")]
    for select in ("column-tube", "column-grade", "column-finish"):
        assert 'document.getElementById("{}").addEventListener("change"'.format(select) in js
    assert 'document.getElementById("formwork-wall").addEventListener("input", applyColumnLook);' in js


def test_the_tab_judges_and_runs_in_the_tube_chosen_and_sizes_its_marks():
    js = (STATIC / "formwork.js").read_text(encoding="utf-8")
    assert "export function mountFormwork({ studyName, studyOptions, mechanism, view, hooks, column" in js
    judge = _function(js, "function judge()")
    assert "withTube(tab.sim, tube)" in judge
    run = _function(js, "async function startRun()")
    assert "tube: tube.key, grade: tube.grade" in run
    assert "columnChanged: () => {" in js
    assert 'const MARKS_PREFIX = "vaulted-marks:";' in js
    assert "view.setMarks(" in js
    assert re.search(r"el\.marks\.addEventListener\(\"input\"", js)
