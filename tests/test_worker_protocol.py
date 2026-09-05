from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest

from ananke_equilibrium.codec import CodecError
from ananke_equilibrium.codec import decode_frame
from ananke_equilibrium.codec import encode_frame
from ananke_equilibrium.codec import read_frame
from ananke_equilibrium.codec import write_frame
from ananke_equilibrium.worker import dispatch
from ananke_equilibrium.worker import serve


def request(command, payload=None, request_id="request-1"):
    return {
        "v": 1,
        "type": "request",
        "id": request_id,
        "command": command,
        "payload": payload or {},
    }


class FakeDiagram:
    def __init__(
        self,
        vertices,
        edges,
        *,
        faces=(),
        edge_attributes=None,
        ordered_edges=None,
    ):
        self._vertices = dict(vertices)
        self._edges = tuple(tuple(edge) for edge in edges)
        self._faces = {
            key: tuple(cycle) for key, cycle in faces
        }
        self._edge_attributes = dict(edge_attributes or {})
        self._ordered_edges = (
            tuple(tuple(edge) for edge in ordered_edges)
            if ordered_edges is not None
            else None
        )

    def vertices(self):
        return iter(self._vertices)

    def vertex_coordinates(self, key):
        return self._vertices[key]

    def edges(self):
        return iter(self._edges)

    def edges_where(self, _conditions=None, **_kwargs):
        return iter(self._edges)

    def faces(self):
        return iter(self._faces)

    def face_vertices(self, key):
        return self._faces[key]

    def edge_attribute(self, edge, name):
        value = self._edge_attributes.get((tuple(edge), name))
        if value is None:
            value = self._edge_attributes.get(
                ((edge[1], edge[0]), name)
            )
        return value

    def ordered_edges(self, _form):
        if self._ordered_edges is None:
            return list(self._edges)
        return list(self._ordered_edges)


def tna_payload():
    vertices = [
        [float(x), float(y), 0.0]
        for y in range(3)
        for x in range(3)
    ]
    faces = [
        [0, 1, 4, 3],
        [1, 2, 5, 4],
        [3, 4, 7, 6],
        [4, 5, 8, 7],
    ]
    edges = []
    seen = set()
    for face in faces:
        for index, u in enumerate(face):
            v = face[(index + 1) % len(face)]
            edge = (min(u, v), max(u, v))
            if edge not in seen:
                seen.add(edge)
                edges.append(list(edge))
    return {
        "topology": {
            "kind": "faced",
            "vertices": vertices,
            "edges": edges,
            "faces": faces,
            "source_vertex_ids": [
                "grid-{}".format(index) for index in range(len(vertices))
            ],
            "length_unit": "m",
            "metadata": {
                "source": "test",
                "analysis_plane": [
                    [0, 0, 0],
                    [1, 0, 0],
                    [0, 1, 0],
                    [0, 0, 1],
                ],
            },
        },
        "supports": {
            "mode": "boundary",
        },
        "load_case": {
            "name": "dead",
            "distribution": "uniform_nodes",
            "base_vector": [0, 0, -1],
        },
        "control": {
            "height_control": {
                "mode": "zmax",
                "value": 1.0,
            },
            "settings": {
                "horizontal_alpha": 100.0,
                "horizontal_iterations": 100,
                "vertical_iterations": 100,
                "tolerance": 1.0e-3,
            },
        },
    }


def fake_tna_backend(**kwargs):
    topology = kwargs["topology"]
    form_edges = ((1, 4), (3, 4), (4, 5), (4, 7))
    force_edges = ((10, 11), (11, 12), (12, 13), (13, 10))
    form = FakeDiagram(
        {
            1: (1.0, 0.0, 0.0),
            3: (0.0, 1.0, 0.0),
            4: (1.0, 1.0, 1.0),
            5: (2.0, 1.0, 0.0),
            7: (1.0, 2.0, 0.0),
        },
        form_edges,
        faces=(
            (20, (1, 4, 3)),
            (21, (1, 5, 4)),
            (22, (3, 4, 7)),
            (23, (4, 5, 7)),
        ),
        edge_attributes={
            (edge, "_a"): 179.75 for edge in form_edges
        },
    )
    force = FakeDiagram(
        {
            10: (0.0, 0.0, 0.0),
            11: (1.0, 0.0, 0.0),
            12: (1.0, 1.0, 0.0),
            13: (0.0, 1.0, 0.0),
        },
        force_edges,
        faces=((4, (10, 11, 12, 13)),),
        ordered_edges=force_edges,
    )
    source_edges = {
        index: tuple(edge)
        for index, edge in enumerate(topology.edges)
    }
    active_by_source = {
        tuple(sorted(edge)): index
        for index, edge in source_edges.items()
        if tuple(sorted(edge)) in {
            tuple(sorted(item)) for item in form_edges
        }
    }
    source_edge_to_form = {
        source_id: (
            tuple(edge)
            if tuple(sorted(edge)) in active_by_source
            else None
        )
        for source_id, edge in source_edges.items()
    }
    form_edge_to_sources = {
        tuple(sorted(edge)): (active_by_source[tuple(sorted(edge))],)
        for edge in form_edges
    }
    return SimpleNamespace(
        form=form,
        force=force,
        source_kind="vertices_faces",
        source_vertex_order=tuple(range(len(topology.vertices))),
        source_vertices={
            index: point for index, point in enumerate(topology.vertices)
        },
        source_to_form={
            index: index if index in (1, 3, 4, 5, 7) else None
            for index in range(len(topology.vertices))
        },
        form_to_sources={
            index: (index,) for index in (1, 3, 4, 5, 7)
        },
        source_edges=source_edges,
        source_edge_to_form=source_edge_to_form,
        form_edge_to_sources=form_edge_to_sources,
        endpoint_to_source={},
        support_keys=(1, 3, 5, 7),
        support_form_keys=(1, 3, 5, 7),
        source_nodal_pz={
            index: -1.0 for index in range(len(topology.vertices))
        },
        form_nodal_pz={
            index: -1.0 for index in (1, 3, 4, 5, 7)
        },
        effective_form_loads={
            index: (0.0, 0.0, -1.0)
            for index in (1, 3, 4, 5, 7)
        },
        edge_q={edge: -0.25 for edge in form_edges},
        edge_forces={edge: -0.3535533905932738 for edge in form_edges},
        support_reactions={
            index: (0.0, 0.0, 1.25) for index in (1, 3, 5, 7)
        },
        support_reactions_by_form={
            index: (0.0, 0.0, 1.25) for index in (1, 3, 5, 7)
        },
        diagnostics={
            "status": "solved",
            "vertical_scale": -0.25,
            "max_free_residual": 1.0e-12,
            "global_force_error_norm": 0.0,
            "max_reciprocal_angle_deviation": 179.75,
        },
        metadata={
            "analysis_plane": topology.metadata["analysis_plane"],
            "solve": {"vertical_mode": "zmax"},
        },
        report="Injected worker TNA solve complete.",
    )


def test_frame_roundtrip_uses_big_endian_length_prefix():
    message = request("system.health", request_id="health-1")

    frame = encode_frame(message)
    assert int.from_bytes(frame[:4], byteorder="big", signed=False) == len(frame) - 4
    assert decode_frame(frame) == message

    stream = BytesIO()
    write_frame(stream, message)
    stream.seek(0)
    assert read_frame(stream) == message
    assert read_frame(stream) is None


def test_frame_codec_rejects_non_finite_json():
    with pytest.raises(CodecError, match="Non-finite"):
        encode_frame({"value": float("nan")})


def test_health_dispatch_reports_runtime_and_optional_capabilities():
    response = dispatch(request("system.health"))

    assert response["type"] == "result"
    assert response["id"] == "request-1"
    health = response["result"]
    assert health["status"] == "ok"
    assert health["worker"]["protocol_version"] == 1
    assert health["python"]["version"]
    assert "compas_fd" in health["packages"]
    assert "fd.solve" in health["capabilities"]
    assert "system.health" in health["capabilities"]["commands"]
    assert "tna.solve" in health["capabilities"]["commands"]


def test_unknown_command_returns_structured_error_and_echoes_id():
    response = dispatch(request("python.eval", {"source": "2 + 2"}, "unsafe-1"))

    assert response["type"] == "error"
    assert response["id"] == "unsafe-1"
    assert response["error"]["code"] == "unknown_command"
    assert "not allowed" in response["error"]["message"]
    assert "python.eval" not in response["error"]["details"]["allowed_commands"]


def test_fd_solve_decodes_contracts_and_encodes_stable_snapshot():
    payload = {
        "topology": {
            "kind": "line",
            "vertices": [[0, 0, 0], [1, -1, 0], [2, 0, 0]],
            "edges": [[0, 1], [1, 2]],
            "length_unit": "m",
            "metadata": {"source": "test"},
        },
        "supports": {
            "mode": "explicit",
            "node_ids": [0, 2],
        },
        "load_case": {
            "name": "dead",
            "distribution": "point",
            "node_ids": [1],
            "vectors": [[0, -1, 0]],
        },
        "settings": {
            "force_densities": 10.0,
            "sign_convention": "positive_tension",
        },
    }
    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            equilibrium_vertices=((0, 0, 0), (1, -1, 0), (2, 0, 0)),
            source_edges=((0, 1), (1, 2)),
            member_forces=(10.0, 10.0),
            force_densities=(10.0, 10.0),
            support_reactions=((0, 0.5, 0), (0, 0, 0), (0, 0.5, 0)),
            residuals=((0, 0, 0), (0, 1e-12, 0), (0, 0, 0)),
            fixed=(0, 2),
            loads=((0, 0, 0), (0, -1, 0), (0, 0, 0)),
            report="Injected worker FD solve complete.",
        )

    response = dispatch(
        request("fd.solve", payload, "fd-1"),
        fd_backend=backend,
    )

    assert response["type"] == "result", response
    assert response["id"] == "fd-1"
    assert calls
    assert calls[0]["topology"].topology_hash
    assert calls[0]["supports"].topology_hash == calls[0]["topology"].topology_hash
    assert calls[0]["load_case"].topology_hash == calls[0]["topology"].topology_hash

    solved = response["result"]
    assert solved["solver"] == "fd"
    assert solved["member_forces"] == [10.0, 10.0]
    assert solved["config"]["force_densities"] == 10.0
    assert solved["topology"]["metadata"]["source"] == "test"
    assert solved["provenance"]["protocol_version"] == 1
    assert solved["mappings"]["resolved_support_ids"] == [0, 2]
    assert "session" not in solved

    # The resulting response itself remains valid framed JSON.
    assert decode_frame(encode_frame(response)) == response


def test_tna_solve_persists_reciprocal_graphs_and_stable_mappings():
    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return fake_tna_backend(**kwargs)

    response = dispatch(
        request("tna.solve", tna_payload(), "tna-1"),
        tna_backend=backend,
    )

    assert response["type"] == "result", response
    assert response["id"] == "tna-1"
    assert calls
    assert calls[0]["topology"].kind == "faced"
    assert calls[0]["height_control"].mode == "zmax"
    assert calls[0]["config"].horizontal_alpha == pytest.approx(100.0)

    result = response["result"]
    assert result["kind"] == "Result"
    assert result["solver"] == "tna"
    assert result["equilibrium"]["solver"] == "tna"
    assert "session" not in result["equilibrium"]
    assert len(result["form_graph"]["vertices"]) == 5
    assert len(result["form_graph"]["edges"]) == 4
    assert result["form_graph"]["vertices"][0]["source_vertex_ids"] == [
        "grid-1"
    ]
    assert len(result["force_graph"]["vertices"]) == 4
    assert len(result["force_graph"]["edges"]) == 4
    assert result["horizontal_scale"] == pytest.approx(-0.25)
    assert result["analysis_plane"]["zaxis"] == [0.0, 0.0, 1.0]

    first = result["edge_states"][0]
    assert first["form_edge_id"] == 0
    assert first["force_edge_id"] == 0
    assert first["equilibrium_edge_id"] == 0
    assert first["q"] == pytest.approx(-0.25)
    assert first["horizontal_force"] == pytest.approx(-0.25)
    assert first["axial_force"] == pytest.approx(-0.3535533905932738)
    assert first["force_state"] == "compression"
    assert first["reciprocity_error_degrees"] == pytest.approx(0.25)
    assert first["source_edge_ids"]

    mappings = result["mappings"]
    assert len(mappings["source_vertex_to_form_vertex"]) == 9
    assert any(
        item["form_edge_id"] is None
        for item in mappings["source_edge_to_form_edge"]
    )
    assert len(mappings["form_edge_to_force_edge"]) == 4
    assert len(mappings["form_edge_to_equilibrium_edge"]) == 4
    assert len(mappings["supports"]) == 4
    assert len(mappings["loads"]) == 5
    assert mappings["supports"] == mappings["reactions"]
    assert mappings["supports"][0]["source_vertex_id"] == "grid-1"

    # The complete reciprocal snapshot itself must remain finite framed JSON.
    assert decode_frame(encode_frame(response)) == response


def test_the_load_case_wire_carries_the_selfweight_thickness_and_density():
    """Rule 2.4(a) of the 2026-09-04 design crosses the worker boundary.

    The native Loads component sends the self-weight's thickness and
    density as fields of their own; the decoder allowlists them by name,
    so a field it does not know about is refused rather than ignored, and
    a load case that carries neither is the load case every canvas sent
    before they existed: thickness 1.0, density 1.0.
    """

    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return fake_tna_backend(**kwargs)

    payload = tna_payload()
    payload["load_case"] = {
        "name": "dead",
        "distribution": "self_weight",
        "base_vector": [0, 0, -1],
        "thickness": 0.2,
        "density": 24.0,
        "node_ids": [4],
        "vectors": [[0, 0, -3.0]],
    }
    response = dispatch(
        request("tna.solve", payload, "tna-selfweight"),
        tna_backend=backend,
    )

    assert response["type"] == "result", response
    assert calls
    load_case = calls[0]["load_case"]
    assert load_case.thickness == pytest.approx(0.2)
    assert load_case.density == pytest.approx(24.0)
    # Both halves of rule 2.4(b)'s load case survive the wire together.
    assert load_case.base_vector == (0.0, 0.0, -1.0)
    assert load_case.node_ids == (4,)
    assert load_case.vectors == ((0.0, 0.0, -3.0),)

    # Absent, and explicitly null, both read as one.
    for value in ({}, {"thickness": None, "density": None}):
        bare = tna_payload()
        bare["load_case"] = dict(
            {
                "name": "dead",
                "distribution": "tributary_area",
                "base_vector": [0, 0, -1],
            },
            **value,
        )
        calls.clear()
        assert dispatch(
            request("tna.solve", bare, "tna-bare"),
            tna_backend=backend,
        )["type"] == "result"
        assert calls[0]["load_case"].thickness == 1.0
        assert calls[0]["load_case"].density == 1.0


def test_the_load_case_wire_refuses_a_signed_selfweight_density():
    """The density is a magnitude and the base vector is the direction.
    A negative density would flip a vault's weight upward while every
    arrow on the canvas still pointed down, so it is refused at the
    boundary rather than solved."""

    payload = tna_payload()
    payload["load_case"] = {
        "name": "dead",
        "distribution": "self_weight",
        "base_vector": [0, 0, -1],
        "density": -24.0,
    }
    called = []

    response = dispatch(
        request("tna.solve", payload, "tna-signed-density"),
        tna_backend=lambda **kwargs: called.append(kwargs),
    )

    assert response["type"] == "error", response
    assert "density cannot be negative" in response["error"]["message"]
    assert not called


def test_tna_solve_rejects_line_topology_before_backend_call():
    payload = tna_payload()
    payload["topology"]["kind"] = "line"
    payload["topology"]["faces"] = []
    called = []

    response = dispatch(
        request("tna.solve", payload, "bad-tna"),
        tna_backend=lambda **kwargs: called.append(kwargs),
    )

    assert response["type"] == "error"
    assert response["id"] == "bad-tna"
    assert response["error"]["code"] == "invalid_payload"
    assert "faced topology" in response["error"]["message"]
    assert not called


def test_solver_stdout_cannot_corrupt_framed_worker_response(capsys):
    payload = {
        "topology": {
            "kind": "line",
            "vertices": [[0, 0, 0], [1, -1, 0], [2, 0, 0]],
            "edges": [[0, 1], [1, 2]],
        },
        "supports": {"mode": "explicit", "node_ids": [0, 2]},
        "load_case": {
            "name": "dead",
            "distribution": "point",
            "node_ids": [1],
            "vectors": [[0, -1, 0]],
        },
        "settings": {
            "force_densities": 10.0,
            "sign_convention": "positive_tension",
        },
    }

    def noisy_backend(**_kwargs):
        print("backend progress that must not enter the protocol")
        return SimpleNamespace(
            equilibrium_vertices=((0, 0, 0), (1, -1, 0), (2, 0, 0)),
            source_edges=((0, 1), (1, 2)),
            member_forces=(10.0, 10.0),
            force_densities=(10.0, 10.0),
            support_reactions=((0, 0.5, 0), (0, 0, 0), (0, 0.5, 0)),
            residuals=((0, 0, 0), (0, 0, 0), (0, 0, 0)),
            fixed=(0, 2),
            loads=((0, 0, 0), (0, -1, 0), (0, 0, 0)),
            report="Noisy backend solve complete.",
        )

    source = BytesIO()
    write_frame(source, request("fd.solve", payload, "noisy-fd"))
    write_frame(source, request("system.shutdown", request_id="stop"))
    source.seek(0)
    target = BytesIO()

    assert serve(source, target, fd_backend=noisy_backend) == 0
    target.seek(0)
    solve_response = read_frame(target)
    shutdown_response = read_frame(target)
    assert solve_response["id"] == "noisy-fd"
    assert solve_response["type"] == "result"
    assert shutdown_response["id"] == "stop"
    assert read_frame(target) is None
    assert "backend progress" in capsys.readouterr().err


def prepared_stage_payload():
    """The smallest prepared stage the equilibrate codec will accept.

    Handmade rather than solved, so the protocol pins below measure the
    boundary alone and need no numerical backend.
    """
    return {
        "schema_version": "0.1",
        "kind": "tna_prepared",
        "topology": {
            "kind": "faced",
            "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
            "faces": [[0, 1, 2, 3]],
            "source_vertex_ids": ["a", "b", "c", "d"],
            "length_unit": "m",
            "metadata": {},
        },
        "support_set": {"mode": "explicit", "node_ids": [0, 2]},
        "config": {
            "force_density": 1.0,
            "relax": True,
            "boundary_sag": 0.1,
            "sag_iterations": 10,
            "sag_tolerance": 0.01,
            "fixed_node_ids": [],
            "metadata": {},
        },
        "pattern": {
            "kind": "faced",
            "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
            "faces": [[0, 1, 2, 3]],
            "edge_force_densities": [1.0, 1.0, 1.0, 1.0],
            "fixed_node_ids": [],
        },
        "form_graph": {
            "vertices": [
                {
                    "id": index,
                    "key": index,
                    "point": [float(index), 0.0, 0.0],
                    "source_vertex_ids": [name],
                }
                for index, name in enumerate("abcd")
            ],
            "edges": [],
            "faces": [],
        },
        "force_graph": {"vertices": [], "edges": [], "faces": []},
        "boundary_segments": [],
        "diagnostics": [],
        "diagnostic_metrics": {"boundary_support_count": 2},
        "mappings": {"support_node_ids": [0, 2]},
        "report": "prepared",
        "metadata": {},
        "provenance": {"worker": "test"},
    }


def fake_equilibrate(prepared, move, watched, **_kwargs):
    from ananke_equilibrium.gh import ComponentResult
    from ananke_equilibrium.gh import ComponentStatus

    moved = {} if move == 0.0 else {1: (1.5, 0.25)}
    return ComponentResult(
        value={
            "moved_points": moved,
            "diagnostics": {
                "horizontal_move": move,
                "horizontal_watched_node_count": len(watched),
            },
            "report": "moved {}".format(move),
        },
        status=ComponentStatus("ok", "TNA Horizontal complete."),
    )


def test_tna_equilibrate_is_a_named_command_with_its_own_capability():
    health = dispatch(request("system.health"))["result"]
    assert "tna.equilibrate" in health["capabilities"]["commands"]
    assert "tna.equilibrate" in health["capabilities"]
    hello = dispatch(request("system.hello"))["result"]
    assert "tna.equilibrate" in hello["commands"]


def test_tna_equilibrate_moves_only_the_plan_and_stays_framed_json():
    payload = {
        "prepared": prepared_stage_payload(),
        "move": 60.0,
        "watched_node_ids": [1, 3],
    }
    response = dispatch(
        request("tna.equilibrate", payload, "equilibrate-1"),
        tna_equilibrate_solver=fake_equilibrate,
    )

    assert response["type"] == "result", response
    assert response["id"] == "equilibrate-1"
    moved = response["result"]
    assert moved["kind"] == "tna_prepared"
    # Only the plan moved, and z came off the incoming vertex rather than
    # the station, which never touches a height.
    assert moved["pattern"]["vertices"] == [
        [0.0, 0.0, 0.0],
        [1.5, 0.25, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
    ]
    assert moved["pattern"]["edges"] == payload["prepared"]["pattern"]["edges"]
    assert moved["topology"] == payload["prepared"]["topology"]
    assert moved["force_graph"] == payload["prepared"]["force_graph"]
    # The form graph follows the plan by its source vertex ID, so the RLX
    # that leaves does not carry a drawing of the plan that arrived.
    assert moved["form_graph"]["vertices"][1]["point"] == [1.5, 0.25, 0.0]
    assert moved["form_graph"]["vertices"][0]["point"] == [0.0, 0.0, 0.0]
    # The prepare stage's own metrics survive beside the station's.
    metrics = moved["diagnostic_metrics"]
    assert metrics["boundary_support_count"] == 2
    assert metrics["horizontal_move"] == 60.0
    assert metrics["horizontal_watched_node_count"] == 2
    assert moved["report"] == "moved 60.0"
    assert moved["provenance"]["horizontal_station"] == "tna.equilibrate"
    assert moved["provenance"]["worker"] == "ananke-equilibrium-worker"

    assert decode_frame(encode_frame(response)) == response


def test_tna_equilibrate_pins_its_payload_fields_and_its_move_range():
    prepared = prepared_stage_payload()
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        return fake_equilibrate(*args, **kwargs)

    unknown = dispatch(
        request(
            "tna.equilibrate",
            {"prepared": prepared, "move": 10.0, "iterations": 500},
            "unknown-field",
        ),
        tna_equilibrate_solver=spy,
    )
    assert unknown["type"] == "error", unknown
    assert unknown["error"]["code"] == "invalid_payload"
    assert "iterations" in unknown["error"]["message"]

    missing = dispatch(
        request("tna.equilibrate", {"move": 10.0}, "missing-prepared"),
        tna_equilibrate_solver=spy,
    )
    assert missing["type"] == "error", missing
    assert "prepared" in missing["error"]["message"]

    for move in (-1.0, 100.5, float("inf")):
        refused = dispatch(
            request(
                "tna.equilibrate",
                {"prepared": prepared, "move": move},
                "bad-move",
            ),
            tna_equilibrate_solver=spy,
        )
        assert refused["type"] == "error", (move, refused)
        assert "between 0 and 100" in refused["error"]["message"]

    assert not calls

    # An absent Move is the default the ruling gives the component.
    default = dispatch(
        request("tna.equilibrate", {"prepared": prepared}, "default-move"),
        tna_equilibrate_solver=spy,
    )
    assert default["type"] == "result", default
    assert calls and calls[0][1] == 100.0
    assert calls[0][2] == ()
