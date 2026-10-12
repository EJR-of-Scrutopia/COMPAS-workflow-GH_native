"""The formwork engine's own process and its capture document (spec 2026-10-09
sections 4.3, 4.5 and 7)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

import solve_formwork  # noqa: E402


FACES = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]


def _request():
    # the sequence tests' toy as the studio sends it, in millimetres and
    # newtons: a 3 x 3 net, its corners on wires, one tree lifting the centre
    # 400 mm, the edge midpoints hanging 250 mm in and 50 mm up, and one row of
    # skin going on a quarter at a time
    design = [[i * 1000.0, j * 1000.0, 0.0] for j in range(3) for i in range(3)]
    design[4][2] = 400.0
    for node, (dx, dy) in ((1, (0.0, 250.0)), (3, (250.0, 0.0)), (5, (-250.0, 0.0)),
                           (7, (0.0, -250.0))):
        design[node] = [design[node][0] + dx, design[node][1] + dy, 50.0]
    flat = [[x, y, 0.0] for x, y, _ in design]
    edges = ([[j * 3 + i, j * 3 + i + 1] for j in range(3) for i in range(2)]
             + [[j * 3 + i, (j + 1) * 3 + i] for j in range(2) for i in range(3)])
    out = {0: (-1.0, -1.0), 2: (1.0, -1.0), 6: (-1.0, 1.0), 8: (1.0, 1.0)}
    rim = [{"node": node, "name": "w{}".format(node), "anchor": design[node],
            "into": [x / 2.0 ** 0.5, y / 2.0 ** 0.5, 0.0], "stiffness": 50.0}
           for node, (x, y) in out.items()]

    def trees(z):
        return [[1000.0, 1000.0, 0.0], [1000.0, 1000.0, z]]

    return {
        "study": "Tiny", "units": "mm, N",
        "design": design, "edges": edges, "ea": 1.0e5, "prestress": 50.0,
        "weight": [[0.0, 0.0, -0.5]] * 9,
        "rim": rim, "machines": [[0, 2, 6, 8]], "wires_per_motor": 1,
        "heads": [[4, 1]], "tree_members": [[0, 1]], "tree_feet": [0],
        "frames": [{"time": 30.0, "phase": "raise", "net": flat, "trees": trees(0.0)},
                   {"time": 60.0, "phase": "finish", "net": design, "trees": trees(400.0)},
                   {"time": 100.0, "phase": "hold", "net": design, "trees": trees(400.0)}],
        "rows": [{"name": "S1", "quarters": [{"nodes": [1, 3, 5, 7][:q], "z": [-20.0] * q,
                                              "faces": [q - 1]}
                                             for q in range(1, 5)]}],
        "faces": FACES,
        "wall": 3.2, "options": {"prestress": 50.0}, "note": None, "assumptions": ["a toy"],
    }


def test_an_array_survives_the_trip_through_the_document():
    values = np.array([[1.5, -2.25, 3.0], [1.0e5, 0.0, -7.125]])
    entry = solve_formwork.pack(values)
    assert entry["shape"] == [2, 3] and isinstance(entry["f32"], str)
    assert np.array_equal(solve_formwork.unpack(entry), values.astype(np.float32))


def test_the_document_carries_every_capture_with_its_arrays_in_shape():
    document = solve_formwork.solve(_request())
    json.dumps(document, allow_nan=False)                  # nothing a browser cannot read
    assert document["schema"] == "bench.formwork-sim/1" and document["units"] == "mm, N"
    captures = document["captures"]
    assert [c["phase"] for c in captures] == ["raise", "finish", "hold"] + ["tiling"] * 4
    assert [(c["row"], c["quarter"]) for c in captures[3:]] == [("S1", q) for q in (1, 2, 3, 4)]
    shapes = {"x": (9, 3), "tension": (12,), "deviation": (9,), "head_push": (1, 3),
              "anchor_force": (4, 3), "wire_tension": (4,), "reel": (4,), "let_out": (4,),
              "tree_x": (2, 3), "tree_axial": (1,), "tree_utilisation": (1,)}
    for c in captures:
        for field, shape in shapes.items():
            assert solve_formwork.unpack(c[field]).shape == shape, field
    hold = captures[2]
    assert solve_formwork.unpack(hold["x"])[4] == pytest.approx([1000.0, 1000.0, 400.0])
    assert document["rim"]["nodes"] == [0, 2, 6, 8] and document["rim"]["motors"] is None
    assert document["trees"]["thinnest_wall"] == 2.3
    summary = document["summary"]
    assert summary["captures"] == 7
    assert summary["raise_deviation_max_mm"] == pytest.approx(
        float(solve_formwork.unpack(hold["deviation"]).max()), rel=1.0e-6)


def test_the_document_carries_the_faces_the_skin_goes_on_and_the_grounds_nodes():
    # what the Formwork tab draws the skin and the ground contacts from (spec
    # 2026-10-10 formwork tab, section 4)
    document = solve_formwork.solve(_request())
    assert document["net"]["faces"] == FACES
    captures = document["captures"]
    assert [c["added_faces"] for c in captures] == [None] * 3 + [[0], [1], [2], [3]]
    assert captures[0]["ground"] == [1, 3, 5, 7]
    assert all(isinstance(c["ground"], list) for c in captures)
    # an older request, with no faces: none written, the ground still is
    older = _request()
    del older["faces"]
    for row in older["rows"]:
        for quarter in row["quarters"]:
            del quarter["faces"]
    document = solve_formwork.solve(older)
    assert document["net"]["faces"] is None
    assert all(c["added_faces"] is None for c in document["captures"])
    assert document["captures"][0]["ground"] == [1, 3, 5, 7]


def test_the_document_carries_the_holds_and_what_each_pushes():
    # spec 2026-10-10 formwork holds, section 3: the held nodes, each hold's
    # push in every capture, the capture after the jacking, and the worst
    # deviation the search judges by (that capture and every tiling capture)
    request = _request()
    request["holds"] = [1, 3, 5, 7]
    document = solve_formwork.solve(request)
    assert document["net"]["holds"] == [1, 3, 5, 7]
    captures = document["captures"]
    assert [c["phase"] for c in captures] == ["raise", "finish", "hold", "holds"] + ["tiling"] * 4
    assert captures[3]["time"] == 100.0 and captures[3]["added_faces"] is None
    for c in captures:
        assert solve_formwork.unpack(c["hold_push"]).shape == (4, 3)
    judged = max(float(solve_formwork.unpack(c["deviation"]).max()) for c in captures[3:])
    assert document["summary"]["holds_deviation_max_mm"] == pytest.approx(judged, rel=1.0e-6)
    # a run with no holds names none and judges nothing
    plain = solve_formwork.solve(_request())
    assert plain["net"]["holds"] == []
    assert solve_formwork.unpack(plain["captures"][0]["hold_push"]).shape == (0, 3)
    assert plain["summary"]["holds_deviation_max_mm"] is None


def test_the_entry_runs_as_its_own_process_reporting_progress(tmp_path):
    (tmp_path / "request.json").write_text(json.dumps(_request()), encoding="utf-8")
    done = subprocess.run([sys.executable, str(STUDIO / "solve_formwork.py"),
                           str(tmp_path / "request.json"), str(tmp_path / "out.json")],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    lines = [line for line in done.stdout.splitlines() if line.startswith("progress ")]
    assert [line.split()[1:3] for line in lines] == [[str(k), "7"] for k in range(1, 8)]
    # and each capture's figures, as JSON, for the answer as the run goes
    # (his choice of 11 October 2026)
    figures = [line.split(None, 2) for line in done.stdout.splitlines()
               if line.startswith("figures ")]
    assert [int(parts[1]) for parts in figures] == list(range(1, 8))
    assert {"wire", "offset_max", "offset_mean", "tree_utilisation", "tree_newtons",
            "tendons"} <= set(json.loads(figures[-1][2]))
    document = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert len(document["captures"]) == 7


def test_the_entry_refuses_with_the_reason_and_writes_nothing(tmp_path):
    request = _request()
    request["frames"] = []
    (tmp_path / "request.json").write_text(json.dumps(request), encoding="utf-8")
    done = subprocess.run([sys.executable, str(STUDIO / "solve_formwork.py"),
                           str(tmp_path / "request.json"), str(tmp_path / "out.json")],
                          capture_output=True, text=True)
    assert done.returncode == 1
    assert "no frames" in done.stderr
    assert not (tmp_path / "out.json").exists()


# spec 2026-10-11 one Cable net tab, sections 6 and 7: each node's side in the
# toy, its four corners a side each
SIDES = [0, 0, 1, 0, 0, 1, 2, 2, 3]


def test_a_holds_run_from_the_saved_state_is_the_full_run_and_says_so(tmp_path):
    state = tmp_path / "state.json.gz"
    base = solve_formwork.solve({**_request(), "sides": SIDES, "state_out": str(state)})
    assert state.is_file() and base["resumed"] is False
    asked = {**_request(), "sides": SIDES, "holds_per_side": 1}
    again = solve_formwork.solve({**asked, "state_in": str(state)})
    full = solve_formwork.solve(asked)
    assert again["resumed"] is True and full["resumed"] is False
    assert again["captures"] == full["captures"] and again["summary"] == full["summary"]
    assert again["net"] == full["net"]
    held = full["net"]["holds"]
    assert len(held) == 3 and full["net"]["holds_per_side"] == 1
    assert full["net"]["hold_sides"] == [SIDES[node] for node in held]


def test_a_state_for_another_request_or_none_readable_is_a_full_run(tmp_path):
    state = tmp_path / "state.json.gz"
    solve_formwork.solve({**_request(), "sides": SIDES, "state_out": str(state)})
    other = {**_request(), "sides": SIDES, "holds_per_side": 1, "prestress": 60.0}
    full = solve_formwork.solve(other)
    for path in (state, tmp_path / "none.json.gz"):
        again = solve_formwork.solve({**other, "state_in": str(path)})
        assert again["resumed"] is False and again["captures"] == full["captures"]
    state.write_bytes(b"not a state")
    assert solve_formwork.solve({**other, "state_in": str(state)})["resumed"] is False


TENDON_LINES = [{"head": 0, "side": side, "path": [4, node]}
                for side, node in ((0, 1), (0, 3), (1, 5), (2, 7))]


def test_the_document_carries_the_pull_each_tendons_line_and_its_tension(tmp_path):
    document = solve_formwork.solve({**_request(), "tendons": TENDON_LINES, "tendon_pull": 50.0})
    tendons = document["tendons"]
    assert tendons["pull_n"] == 50.0
    assert [line["path"] for line in tendons["lines"]] == [[4, 1], [4, 3], [4, 5], [4, 7]]
    assert [line["side"] for line in tendons["lines"]] == [0, 0, 1, 2]
    assert tendons["lines"][0]["head"] == 0
    # each line pulls once it is off the ground: from the hold on, all four
    for c in document["captures"]:
        pulls = solve_formwork.unpack(c["tendon_tension"]).tolist()
        assert len(pulls) == 4 and set(pulls) <= {0.0, 50.0}
        if c["phase"] not in ("raise", "finish"):
            assert pulls == [50.0] * 4
    assert document["summary"]["tendon_pull_n"] == 50.0
    # no pull is no tendons
    for asked in ({**_request(), "tendons": TENDON_LINES}, _request()):
        plain = solve_formwork.solve(asked)
        assert plain["tendons"] is None and plain["summary"]["tendon_pull_n"] is None
        assert solve_formwork.unpack(plain["captures"][0]["tendon_tension"]).shape == (0,)
    # and a state at the hold with tendons is a full run's to the bit
    state = tmp_path / "state.json.gz"
    pulled = {**_request(), "tendons": TENDON_LINES, "tendon_pull": 50.0, "sides": SIDES}
    solve_formwork.solve({**pulled, "state_out": str(state)})
    asked = {**pulled, "holds_per_side": 1}
    again = solve_formwork.solve({**asked, "state_in": str(state)})
    assert again["resumed"] is True
    assert again["captures"] == solve_formwork.solve(asked)["captures"]


def test_the_document_says_which_tube_and_steel_the_trees_were_judged_in():
    # Param, 2026-10-12: the column's tube and steel are chosen; a request
    # with none is the 60.3 S355 tube the trees were always judged in
    plain = solve_formwork.solve(_request())["trees"]
    assert plain["diameter"] == 60.3 and plain["grade"] == "S355"
    assert (plain["fy"], plain["e"], plain["alpha"], plain["lambda0"]) == (355.0, 210000.0, 0.21, 0.2)
    tube = {"diameter": 26.9, "grade": "1.4401", "fy": 220.0, "e": 200000.0,
            "alpha": 0.49, "lambda0": 0.3}
    chosen = solve_formwork.solve(dict(_request(), tube=tube))["trees"]
    assert {key: chosen[key] for key in tube} == tube
    assert chosen["wall"] == 3.2
