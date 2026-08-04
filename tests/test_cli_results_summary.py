from __future__ import annotations

import json

import pytest

from ananke_equilibrium.cli.results import ResultError
from ananke_equilibrium.cli.results import diagram
from ananke_equilibrium.cli.results import force_states
from ananke_equilibrium.cli.results import is_compas_mode
from ananke_equilibrium.cli.results import load_result
from ananke_equilibrium.cli.results import loads
from ananke_equilibrium.cli.results import member_forces
from ananke_equilibrium.cli.results import reactions
from ananke_equilibrium.cli.results import solver_name
from ananke_equilibrium.cli.results import thrust_faces
from ananke_equilibrium.cli.results import thrust_vertices
from ananke_equilibrium.cli.summary import format_summary
from ananke_equilibrium.cli.summary import is_balanced
from ananke_equilibrium.cli.summary import summarise


# A two-bay arch: three supports, two loaded nodes, all members compressed.
# Loads and reactions cancel exactly, so it is in global equilibrium.
SNAKE = {
    "kind": "Result",
    "solver": "tna",
    "resultSchema": "0.2",
    "equilibrium": {
        "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 1.0], [2.0, 0.0, 0.0]],
        "member_forces": [-2.0, -3.0],
        "loads": [[0.0, 0.0, 0.0], [0.0, 0.0, -4.0], [0.0, 0.0, 0.0]],
        "reactions": [[0.0, 0.0, 2.0], [0.0, 0.0, 2.0]],
    },
    "edge_states": [
        {"form_edge_id": 0, "axial_force": -2.0, "force_state": "compression"},
        {"form_edge_id": 1, "axial_force": -3.0, "force_state": "compression"},
    ],
    "form_graph": {
        "vertices": [
            {"id": 0, "point": [0.0, 0.0, 0.0]},
            {"id": 1, "point": [1.0, 0.0, 0.0]},
            {"id": 2, "point": [2.0, 0.0, 0.0]},
        ],
        "edges": [{"u": 0, "v": 1}, {"u": 1, "v": 2}],
        "faces": [{"vertices": [0, 1, 2]}],
    },
    "force_graph": {
        "vertices": [
            {"id": 0, "point": [0.0, 0.0, 0.0]},
            {"id": 1, "point": [0.5, 0.0, 0.0]},
        ],
        "edges": [{"u": 0, "v": 1}],
    },
}


def to_camel(value):
    """Re-key a payload the way the C# Export component's camelCase does."""

    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            parts = key.split("_")
            camel = parts[0] + "".join(p.title() for p in parts[1:])
            out[camel] = to_camel(item)
        return out
    if isinstance(value, list):
        return [to_camel(item) for item in value]
    return value


CAMEL = to_camel(SNAKE)
COMPAS_MODE = {
    "thrustMesh": "{}",
    "formDiagram": "{}",
    "forceDiagram": None,
    "compasVersion": "2.15.1",
}


def test_camel_fixture_really_is_renamed():
    # Guards the test itself: if to_camel silently did nothing, every
    # camelCase assertion below would pass for the wrong reason.
    assert "formGraph" in CAMEL
    assert "form_graph" not in CAMEL
    assert "memberForces" in CAMEL["equilibrium"]


@pytest.mark.parametrize("payload", [SNAKE, CAMEL], ids=["snake", "camel"])
def test_reader_is_indifferent_to_key_style(payload):
    assert solver_name(payload) == "tna"
    assert thrust_vertices(payload) == [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 1.0],
        [2.0, 0.0, 0.0],
    ]
    assert thrust_faces(payload) == [[0, 1, 2]]
    assert member_forces(payload) == [-2.0, -3.0]
    assert loads(payload) == [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, -4.0],
        [0.0, 0.0, 0.0],
    ]
    assert [record["vector"] for record in reactions(payload)] == [
        [0.0, 0.0, 2.0],
        [0.0, 0.0, 2.0],
    ]
    assert force_states(payload) == ["compression", "compression"]
    assert len(diagram(payload, "form_graph")["edges"]) == 2


def test_snake_and_camel_summarise_identically():
    assert summarise(SNAKE) == summarise(CAMEL)


def test_member_forces_fall_back_to_edge_states():
    payload = json.loads(json.dumps(SNAKE))
    del payload["equilibrium"]["member_forces"]
    assert member_forces(payload) == [-2.0, -3.0]


def test_compas_mode_export_is_recognised():
    assert is_compas_mode(COMPAS_MODE) is True
    assert is_compas_mode(SNAKE) is False


def test_diagram_rejects_an_unknown_name():
    with pytest.raises(ResultError, match="form_graph"):
        diagram(SNAKE, "nonsense")


def test_load_result_rejects_a_missing_file(tmp_path):
    with pytest.raises(ResultError, match="does not exist"):
        load_result(tmp_path / "absent.json")


def test_summary_reports_geometry_and_forces():
    summary = summarise(SNAKE)
    assert summary["geometry"]["vertices"] == 3
    assert summary["geometry"]["span_x"] == 2.0
    assert summary["geometry"]["rise"] == 1.0
    assert summary["forces"]["compression"] == 2
    assert summary["forces"]["tension"] == 0
    assert summary["forces"]["min"] == -3.0


def test_balanced_result_is_reported_balanced():
    summary = summarise(SNAKE)
    assert summary["actions"]["residual"] == [0.0, 0.0, 0.0]
    assert is_balanced(summary) is True
    assert "BALANCED" in format_summary(summary)


def test_unbalanced_result_is_caught():
    payload = json.loads(json.dumps(SNAKE))
    payload["equilibrium"]["reactions"] = [[0.0, 0.0, 2.0], [0.0, 0.0, 1.0]]
    summary = summarise(payload)
    assert summary["actions"]["residual_magnitude"] == pytest.approx(1.0)
    assert is_balanced(summary) is False
    assert "NOT BALANCED" in format_summary(summary)


def test_describe_command_exits_zero_on_a_balanced_result(tmp_path, capsys):
    from ananke_equilibrium.cli.main import main

    path = tmp_path / "result.json"
    path.write_text(json.dumps(SNAKE), encoding="utf-8")
    assert main(["describe", str(path)]) == 0
    assert "BALANCED" in capsys.readouterr().out


def test_describe_strict_exits_one_on_an_unbalanced_result(tmp_path):
    from ananke_equilibrium.cli.main import main

    payload = json.loads(json.dumps(SNAKE))
    payload["equilibrium"]["reactions"] = [[0.0, 0.0, 2.0]]
    path = tmp_path / "result.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["describe", str(path), "--strict"]) == 1
    assert main(["describe", str(path)]) == 0


def test_plot_writes_an_image(tmp_path):
    from ananke_equilibrium.cli.plot import plot_result

    out = plot_result(SNAKE, tmp_path / "diagrams.png")
    assert out.is_file()
    assert out.stat().st_size > 0


def test_plot_rejects_a_result_without_diagrams(tmp_path):
    from ananke_equilibrium.cli.plot import plot_result

    with pytest.raises(ResultError, match="no reciprocal diagrams"):
        plot_result({"kind": "Result", "vertices": []}, tmp_path / "x.png")
