from __future__ import annotations

import json

import pytest

from ananke_equilibrium.cli.study import StudyError
from ananke_equilibrium.cli.study import build_request
from ananke_equilibrium.cli.study import load_study


TOPOLOGY = {
    "kind": "line",
    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
    "edges": [[0, 1], [1, 2]],
}
STUDY = {
    "study": "arch",
    "command": "fd.solve",
    "payload": {
        "topology": TOPOLOGY,
        "supports": {"mode": "explicit", "node_ids": [0, 2]},
        "load_case": {
            "name": "gravity",
            "distribution": "point",
            "node_ids": [1],
            "vectors": [[0.0, 0.0, -1.0]],
        },
        "settings": {"force_densities": 1.0},
    },
}


def write(tmp_path, document, name="problem.json"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_load_study_returns_the_document(tmp_path):
    path = write(tmp_path, STUDY)
    study = load_study(path)
    assert study["command"] == "fd.solve"
    assert study["payload"]["topology"]["kind"] == "line"


def test_load_study_resolves_a_topology_ref(tmp_path):
    (tmp_path / "topology.json").write_text(json.dumps(TOPOLOGY), encoding="utf-8")
    document = json.loads(json.dumps(STUDY))
    document["payload"]["topology"] = {"$ref": "topology.json"}
    path = write(tmp_path, document)
    study = load_study(path)
    assert study["payload"]["topology"]["edges"] == [[0, 1], [1, 2]]


def test_load_study_rejects_a_ref_outside_the_study_directory(tmp_path):
    document = json.loads(json.dumps(STUDY))
    document["payload"]["topology"] = {"$ref": "../escape.json"}
    path = write(tmp_path, document)
    with pytest.raises(StudyError, match="outside"):
        load_study(path)


def test_load_study_requires_a_command(tmp_path):
    document = json.loads(json.dumps(STUDY))
    del document["command"]
    path = write(tmp_path, document)
    with pytest.raises(StudyError, match="command"):
        load_study(path)


def test_build_request_produces_the_worker_envelope():
    request = build_request(STUDY)
    assert request["v"] == 1
    assert request["type"] == "request"
    assert request["id"] == "arch"
    assert request["command"] == "fd.solve"
    assert request["payload"] == STUDY["payload"]


def test_build_request_ignores_study_only_keys():
    document = dict(STUDY)
    document["$schema"] = "../../.vscode/ananke-problem.schema.json"
    request = build_request(document)
    assert set(request) == {"v", "type", "id", "command", "payload"}
