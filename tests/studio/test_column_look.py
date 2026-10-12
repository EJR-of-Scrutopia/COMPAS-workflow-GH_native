"""The column as specced, in the steel chosen, page half (Param, 2026-10-12):
"i also would like the column to have a thickness and shape to have what we
have specced also. if we can choose different steel for that would be good
too", and, on the 2 sided prototype, "at this scale too the coloured dots and
the columns are way too big. maybe there can be a scale slider". Run under
node with the studio's own three.js."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_formwork_model import document

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

CATALOGUE = {
    "tubes": [{"key": "CHS-{:g}".format(d), "label": "CHS {:g}".format(d), "diameter_mm": d}
              for d in (21.3, 26.9, 33.7, 42.4, 48.3, 60.3, 76.1, 88.9)],
    "grades": [{"key": "S235", "label": "S235", "finish": None, "fy_mpa": 235.0, "e_mpa": 210000.0,
                "alpha": 0.21, "lambda0": 0.2},
               {"key": "S355", "label": "S355", "finish": None, "fy_mpa": 355.0, "e_mpa": 210000.0,
                "alpha": 0.21, "lambda0": 0.2},
               {"key": "1.4401", "label": "316 stainless", "finish": "stainless", "fy_mpa": 220.0,
                "e_mpa": 200000.0, "alpha": 0.49, "lambda0": 0.3}],
    "finishes": [{"key": "galvanised", "label": "galvanised",
                  "render": {"colour": "#8e9399", "metalness": 0.6, "roughness": 0.55}},
                 {"key": "painted", "label": "painted black",
                  "render": {"colour": "#2a2c30", "metalness": 0.15, "roughness": 0.6}},
                 {"key": "stainless", "label": "stainless",
                  "render": {"colour": "#cdd2d7", "metalness": 0.9, "roughness": 0.25}}],
    "spec": {"tube": "CHS-60.3", "grade": "S355", "finish": "galvanised", "wall": 3.2},
}

HARNESS = """
import * as THREE from %(three)r;
import * as m from %(model)r;
import * as c from %(column)r;
import { createFormworkView } from %(view)r;
const catalogue = %(catalogue)s;
const out = {};
// the tube a study starts at: the nearest to the one its export swept
out.nearest = [c.nearestTube(catalogue.tubes, 30), c.nearestTube(catalogue.tubes, 60),
               c.nearestTube(catalogue.tubes, 200), c.nearestTube(catalogue.tubes, null)];
out.fresh = c.columnChoice(null, catalogue, 30);
out.none = c.columnChoice(null, catalogue, null);
out.kept = c.columnChoice({ tube: "CHS-42.4", grade: "S235", finish: "painted" }, catalogue, 30);
out.stale = c.columnChoice({ tube: "CHS-999", grade: "S999", finish: "gold" }, catalogue, 60);
out.stainless = c.columnChoice({ tube: "CHS-26.9", grade: "1.4401", finish: "painted" }, catalogue, 30);
out.tube = c.columnTube(catalogue, out.stainless, 2.6);
out.look = c.columnLook(catalogue, out.kept, 3.2);
out.options = c.columnOptionsHtml(catalogue.tubes, "CHS-26.9");

// the run's trees judged again in the tube chosen, from its own member forces
const doc = %(doc)s;
const sim = m.readSim(doc);
out.readDefaults = [sim.trees.diameter, sim.trees.grade, sim.trees.steel];
const stainless = { diameter: 26.9, wall: 2.6, grade: "1.4401",
                    steel: { fy: 220, e: 200000, alpha: 0.49, lambda0: 0.3 } };
const judged = m.withTube(sim, stainless);
const capture = sim.captures[2];
const [p, q] = sim.trees.members[0];
const length = Math.hypot(capture.treeX[3 * q] - capture.treeX[3 * p],
  capture.treeX[3 * q + 1] - capture.treeX[3 * p + 1], capture.treeX[3 * q + 2] - capture.treeX[3 * p + 2]) * 1000;
const n = capture.treeAxial[0];
const inner = 26.9 - 2 * 2.6;
const area = Math.PI / 4 * (26.9 ** 2 - inner ** 2);
const plastic = area * 220;
let expected = plastic;
if (n < 0) {
  const inertia = Math.PI / 64 * (26.9 ** 4 - inner ** 4);
  const slender = Math.sqrt(plastic / (Math.PI ** 2 * 200000 * inertia / length ** 2));
  const phi = 0.5 * (1 + 0.49 * (slender - 0.3) + slender ** 2);
  expected = Math.min(1, 1 / (phi + Math.sqrt(phi ** 2 - slender ** 2))) * plastic;
}
out.judged = [judged.captures[2].treeUtilisation[0], Math.abs(n) / expected, judged.trees.diameter,
              judged.trees.wall, judged.trees.grade, sim.trees.diameter];
out.wallStill = m.withWall(sim, 2.0).trees.diameter;
const named = m.readSim({ ...doc, trees: { ...doc.trees, diameter: 26.9, grade: "1.4401", fy: 220,
  e: 200000, alpha: 0.49, lambda0: 0.3 } });
out.readNamed = [named.trees.diameter, named.trees.grade, named.trees.steel];

// the view: the trees a round tube at the run's diameter and wall, the wall
// showing at the open ends; judged in another tube, the same parts redrawn
const radial = (geometry) => {
  const position = geometry.attributes.position;
  let low = Infinity, high = 0;
  for (let i = 0; i < position.count; i++) {
    const r = Math.hypot(position.getX(i), position.getZ(i));
    low = Math.min(low, r); high = Math.max(high, r);
  }
  return [low, high];
};
const view = createFormworkView(THREE);
view.build(sim);
const parts = view.parts();
out.built = radial(parts.trees.geometry);
view.rejudge(judged);
out.rejudged = [radial(parts.trees.geometry), view.parts() === parts];
// the marks at a quarter of their size, kept across a build
const size = (mesh) => { mesh.geometry.computeBoundingSphere(); return mesh.geometry.boundingSphere.radius; };
out.marksBefore = [size(parts.heads), size(parts.anchors), size(parts.ground), size(parts.rings)];
view.setMarks(0.25);
out.marksAfter = [size(view.parts().heads), size(view.parts().anchors), size(view.parts().ground),
                  size(view.parts().rings)];
view.build(sim);
out.marksRebuilt = size(view.parts().heads);
view.clear();
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("column_look") / "harness.mjs"
    script.write_text(HARNESS % {
        "three": (STATIC / "vendor" / "three.module.js").resolve().as_uri(),
        "model": (STATIC / "formwork_model.js").resolve().as_uri(),
        "column": (STATIC / "column_look_model.js").resolve().as_uri(),
        "view": (STATIC / "formwork_view.js").resolve().as_uri(),
        "catalogue": json.dumps(CATALOGUE), "doc": json.dumps(document())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_study_starts_at_the_tube_nearest_its_export_in_the_spec_steel(out):
    # the 2 sided prototype sweeps its props 30 mm across, the 5 sided form 60
    assert out["nearest"] == ["CHS-26.9", "CHS-60.3", "CHS-88.9", None]
    assert out["fresh"] == {"tube": "CHS-26.9", "grade": "S355", "finish": "galvanised"}
    # an export that sweeps none starts at the spec's own tube
    assert out["none"] == {"tube": "CHS-60.3", "grade": "S355", "finish": "galvanised"}


def test_a_choice_is_kept_and_one_the_catalogue_no_longer_holds_falls_back(out):
    assert out["kept"] == {"tube": "CHS-42.4", "grade": "S235", "finish": "painted"}
    assert out["stale"] == {"tube": "CHS-60.3", "grade": "S355", "finish": "galvanised"}
    # stainless wears its own finish whatever was picked before
    assert out["stainless"] == {"tube": "CHS-26.9", "grade": "1.4401", "finish": "stainless"}


def test_the_tube_and_the_look_are_read_from_the_choice(out):
    assert out["tube"] == {"key": "CHS-26.9", "diameter": 26.9, "wall": 2.6, "grade": "1.4401",
                           "steel": {"fy": 220.0, "e": 200000.0, "alpha": 0.49, "lambda0": 0.3}}
    look = out["look"]
    assert look["outer"] == pytest.approx(0.0212) and look["inner"] == pytest.approx(0.018)
    assert look["render"] == CATALOGUE["finishes"][1]["render"]
    assert 'value="CHS-26.9" selected' in out["options"] and ">CHS 88.9<" in out["options"]


def test_the_runs_trees_are_judged_again_in_the_tube_and_steel_chosen(out):
    utilisation, expected, diameter, wall, grade, untouched = out["judged"]
    assert utilisation == pytest.approx(expected, rel=1.0e-5)
    assert (diameter, wall, grade) == (26.9, 2.6, "1.4401")
    assert untouched == 60.3, "the run read is left as it is"
    assert out["wallStill"] == 60.3
    # a run made before the steel was chosen is the spec's S355
    assert out["readDefaults"] == [60.3, "S355",
                                   {"fy": 355, "e": 210000, "alpha": 0.21, "lambda0": 0.2}]
    assert out["readNamed"] == [26.9, "1.4401",
                                {"fy": 220, "e": 200000, "alpha": 0.49, "lambda0": 0.3}]


def test_the_view_draws_the_trees_as_the_tube_with_its_wall(out):
    low, high = out["built"]
    assert high == pytest.approx(0.03015, rel=1.0e-4)
    assert low == pytest.approx(0.02695, rel=1.0e-4), "hollow: the wall shows at its open ends"
    (low, high), same = out["rejudged"]
    assert high == pytest.approx(0.01345, rel=1.0e-4) and low == pytest.approx(0.01085, rel=1.0e-4)
    assert same, "judged in another tube, the same parts are redrawn, not built again"


def test_the_marks_size_scales_every_mark_and_is_kept_across_a_build(out):
    for before, after in zip(out["marksBefore"], out["marksAfter"]):
        assert after == pytest.approx(0.25 * before, rel=1.0e-4)
    assert out["marksRebuilt"] == pytest.approx(out["marksAfter"][0], rel=1.0e-4)


WINDING = """
import * as THREE from %(three)r;
import { tubeGeometry } from %(tube)r;
const out = [];
for (const [outer, inner] of [[0.03, 0.027], [0.03, 0]]) {
  const g = tubeGeometry(THREE, outer, inner, 12);
  const p = g.attributes.position, n = g.attributes.normal, idx = g.index.array;
  const v = (k) => new THREE.Vector3(p.getX(k), p.getY(k), p.getZ(k));
  let against = 0;
  for (let f = 0; f < idx.length; f += 3) {
    const [a, b, c] = [idx[f], idx[f + 1], idx[f + 2]];
    const face = v(b).sub(v(a)).cross(v(c).sub(v(a)));
    const normal = new THREE.Vector3(n.getX(a) + n.getX(b) + n.getX(c),
      n.getY(a) + n.getY(b) + n.getY(c), n.getZ(a) + n.getZ(b) + n.getZ(c));
    if (face.dot(normal) <= 0) against += 1;
  }
  g.computeBoundingBox();
  out.push([idx.length / 3, against, g.boundingBox.min.y, g.boundingBox.max.y]);
}
console.log(JSON.stringify(out));
"""


def test_every_face_of_the_tube_looks_the_way_its_normals_say(tmp_path):
    # the outer face out, the inner face in, the cut ends up and down: a face
    # wound against its normals is culled, and the wall shows as a hole
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path / "winding.mjs"
    script.write_text(WINDING % {
        "three": (STATIC / "vendor" / "three.module.js").resolve().as_uri(),
        "tube": (STATIC / "tube_geometry.js").resolve().as_uri()}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    hollow, solid = json.loads(result.stdout)
    assert hollow == [96, 0, 0, 1] and solid == [48, 0, 0, 1]
