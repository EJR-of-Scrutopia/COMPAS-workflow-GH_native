"""The seam between a Grasshopper study and the staged cable net engine.

This module needs no solver: the engine runs in solve_cablenet.py, a
subprocess under the main .venv, and this file only builds its request and
reads its answer back.

Everything the engine sees is newtons and millimetres. Everything the contract
carries is metres. The conversion happens in solve_cablenet.build_problem and nowhere else.

The loads here are built from the MESH, never from the contract's own
equilibrium.loads. In the exports that exist those are tributary AREAS with a
factor of one, while geometry.node_loads_newtons multiplies them by a thousand
as kilonewtons, so reading them would give a load a thousand times the area and
it would look like a number. Building them from the mesh is also the only way
they can agree with the formwork curve already on screen, which is what the
invariant in the tests checks.
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, NamedTuple

import geometry
import staging


class CableNetError(RuntimeError):
    """Raised when a study cannot be turned into a cable net problem."""


# The engine needs the array stack and compas_fd together, and only the main venv
# has them: .venv-fea and .venv-cra lack compas_fd.
CABLENET_PYTHON = staging.REPO / ".venv" / "Scripts" / "python.exe"
SOLVE_CABLENET = Path(__file__).resolve().parent / "solve_cablenet.py"


def _subprocess_runner(python_exe: Path) -> Callable[[dict], dict]:
    def run(request: dict) -> dict:
        with tempfile.TemporaryDirectory(prefix="ananke_cablenet_") as tmp:
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            completed = subprocess.run(
                [str(python_exe), str(SOLVE_CABLENET), str(request_path),
                 str(out_path)],
                capture_output=True, text=True,
            )
            if completed.returncode != 0 or not out_path.is_file():
                raise CableNetError(
                    "solve_cablenet exited {}: {}".format(
                        completed.returncode, completed.stderr.strip()[-2000:]
                    )
                )
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run


def stage_node_loads(vertices, faces, plan, thickness, density,
                     gravity=staging.GRAVITY):
    """Per stage, the downward load at every node from the faces placed by then.

    vertices and faces are the contract's own arrays in METRES, as
    geometry.mesh_arrays returns them: face_area is an area in square metres and
    the weight below is already newtons, so only coordinates ever need scaling.

    A face's weight is shared equally between its corners. A corner-area
    weighting would also preserve the total, which is the quantity that matters,
    and would add a choice with no evidence behind it.
    """

    out = []
    for entry in plan:
        loads = [[0.0, 0.0, 0.0] for _ in vertices]
        for index in entry["faces"]:
            face = faces[index]
            weight = (
                geometry.face_area(vertices, face) * thickness * density * gravity
            )
            share = weight / float(len(face))
            for node in face:
                loads[node][2] -= share
        out.append(loads)
    return out


def net_weight_loads(vertices, edges, mass_per_metre, gravity=staging.GRAVITY):
    """The rope's own weight, half of each member at each of its ends.

    The whole net hangs from the moment it is raised, so this does not vary by
    stage. It matters because hold and capacity both refuse a stage with no load
    at all rather than answering zero.
    """

    loads = [[0.0, 0.0, 0.0] for _ in vertices]
    for u, v in edges:
        a, b = vertices[int(u)], vertices[int(v)]
        length = math.sqrt(
            (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
        )
        half = length * float(mass_per_metre) * gravity / 2.0
        loads[int(u)][2] -= half
        loads[int(v)][2] -= half
    return loads


class Wire(NamedTuple):
    """One spooled cable: the net node it holds, and the machine point it runs to.

    frame_point is the point on the MACHINE the wire is fixed to, in world
    millimetres. The name is kept from the older shape; it is the drum end of
    the wire's route, not a point on a frame.
    """

    name: str
    net_vertex: int
    frame_point: list                 # millimetres, world space
    machine_wire: object = None       # index of the wire on its machine
    reeve_factor: object = None
    permanence: object = None


def frame_to_world(frame, local):
    """Map a point from a machine instance's local space into world space.

    frame is {origin, xAxis, yAxis, zAxis}: the instance's own axes written in
    world coordinates. The point is local[0] along xAxis, local[1] along yAxis
    and local[2] along zAxis, from origin:

        world = origin + x * xAxis + y * yAxis + z * zAxis

    The axes are the COLUMNS of the rotation. Reading them as rows is the
    transpose, which is the identity for the first instance and so passes any
    check made on it alone; on the real export it puts a rotated instance's
    drums about 14 m out.
    """

    try:
        origin, ax, ay, az = (
            [float(c) for c in frame[key]]
            for key in ("origin", "xAxis", "yAxis", "zAxis")
        )
        x, y, z = (float(c) for c in local)
        if not (len(origin) == len(ax) == len(ay) == len(az) == 3):
            raise ValueError("an axis is not a 3-vector")
    except (KeyError, TypeError, ValueError) as error:
        raise CableNetError(
            "An instance frame needs origin, xAxis, yAxis and zAxis, each "
            "three numbers ({}).".format(error)
        )
    return [origin[k] + x * ax[k] + y * ay[k] + z * az[k] for k in range(3)]


def wires_from_mechanism(document, vertex_count, supports):
    """The wires a study's mechanism document declares, in millimetres.

    mechanism.py validates the schema and the scale and hands the document
    through verbatim by design, so the wire keys are read and checked here. The
    document's components, its motors and reels, are deliberately ignored:
    choosing those is what the chooser does.

    The wires are at the top level of the document, beside mechanism, instances
    and anchors. Each carries id, net_vertex, machine_wire, path, permanence,
    reeveFactor and route. The route is in its machine's LOCAL space and runs
    from the net end (first) to the machine end (last); the instance named by
    path[0] (side, mechanism) carries the frame that takes it into world space.
    The document's own units are checked: metres at a scale of 1 are converted
    to millimetres here, anything else is refused.

    supports are the form document's resolvedSupportNodeIds. On this machine the
    wires ARE the supports: those nodes are held by the machine and not by the
    ground, so every wire must sit on one. The older nested shape
    document["mechanism"]["wires"] with a frame_point is still read, because it
    costs nothing; there the wire's point is already world metres.
    """

    document = document or {}
    raw = document.get("wires")
    nested = False
    if not raw:
        raw = (document.get("mechanism") or {}).get("wires")
        nested = bool(raw)
    if not raw:
        raise CableNetError(
            "This study's mechanism document declares no wires. It needs a "
            "top-level 'wires' list, one entry per spool, each naming the "
            "net_vertex it holds and the route it runs, and then exporting "
            "again."
        )
    scale = 1.0 if nested else float(document.get("lengthUnitToMetres", 1.0))
    if (not nested and document.get("units", "m") != "m") or scale != 1.0:
        raise CableNetError(
            "This mechanism document is in {!r} with lengthUnitToMetres {}; "
            "only metres at a scale of 1 are read, and anything else would "
            "move every drum by the wrong factor.".format(
                document.get("units"), scale)
        )
    frames = {}
    for instance in document.get("instances") or []:
        frames[(instance.get("side"), instance.get("mechanism"))] = (
            instance.get("frame"))

    held = set(int(index) for index in supports)
    wires = []
    for position, entry in enumerate(raw):
        name = str(entry.get("id") or entry.get("name")
                   or "wire {}".format(position + 1))
        if "net_vertex" not in entry:
            raise CableNetError(
                "Wire {!r} carries no net_vertex, so nothing says which node it "
                "holds.".format(name)
            )
        node = int(entry["net_vertex"])
        if not 0 <= node < int(vertex_count):
            raise CableNetError(
                "Wire {!r} holds net_vertex {}, which is outside this study's "
                "0 to {}.".format(name, node, int(vertex_count) - 1)
            )
        if node not in held:
            raise CableNetError(
                "Wire {!r} holds net_vertex {}, which is NOT a support node. "
                "On this machine the wires ARE the supports: every support "
                "node is held by a wire rather than by the ground, so a wire "
                "belongs on a node in resolvedSupportNodeIds. A wire on any "
                "other node would be pulling a free node, which the exporter "
                "does not produce; the numbering of this export and of the "
                "form document has gone out of step.".format(name, node)
            )
        if nested:
            point = entry.get("frame_point") or {}
            try:
                machine = [float(point[k]) * 1000.0 for k in "xyz"]
            except (KeyError, TypeError, ValueError):
                raise CableNetError(
                    "Wire {!r} has no usable frame_point; it needs x, y and z "
                    "in metres.".format(name)
                )
        else:
            route = entry.get("route") or []
            try:
                local = route[-1]["origin"]
            except (IndexError, KeyError, TypeError):
                raise CableNetError(
                    "Wire {!r} has no route, so nothing says where the machine "
                    "end is.".format(name)
                )
            try:
                key = (entry["path"][0]["side"], entry["path"][0]["mechanism"])
            except (IndexError, KeyError, TypeError):
                raise CableNetError(
                    "Wire {!r} names no path[0] with a side and a mechanism, so "
                    "its instance cannot be found.".format(name)
                )
            if frames.get(key) is None:
                raise CableNetError(
                    "Wire {!r} runs on side {} mechanism {}, and the document "
                    "has no instance with a frame for it.".format(name, *key)
                )
            machine = [c * 1000.0 for c in frame_to_world(frames[key], local)]
        wires.append(Wire(
            name=name, net_vertex=node, frame_point=machine,
            machine_wire=entry.get("machine_wire"),
            reeve_factor=entry.get("reeveFactor"),
            permanence=entry.get("permanence"),
        ))
    return wires


def run_cablenet(contract, arrays, plan, thickness, density, out_path,
                 mechanism_document, ea, prestress, acceptance,
                 acceptance_source, mass_per_metre, runner=None, python_exe=None,
                 falsework=None, study=None, ea_provenance=None):
    """Everything step A does, from a contract to a written demand document.

    The engine runs in solve_cablenet.py under a solver interpreter, never in
    this process. runner, when given, replaces the subprocess: it takes the
    request dict and returns the demand document. python_exe overrides the
    interpreter the default runner starts.

    falsework, when given, is the KEY of a parts.json falsework entry. The
    acceptance line is then computed in the engine process, where the geometry
    is, from that rib and this skin, and acceptance and acceptance_source are
    ignored (pass None). prestress is an input: a starting point for the cut
    rule, not a value derived from anything.
    """

    if falsework is not None and not (acceptance is None and acceptance_source is None):
        raise CableNetError(
            "This run names the falsework entry {!r} AND an explicit acceptance "
            "line. The falsework computes the acceptance from that rib and this "
            "skin, so the explicit one would be discarded without saying so, and "
            "the figure on screen would not be the figure that was asked for. "
            "Give one or the other.".format(falsework)
        )

    vertices = arrays["vertices"]
    edges = [tuple(edge) for edge in arrays["edges"]]
    anchors = geometry.support_ids(contract)
    wires = wires_from_mechanism(mechanism_document, len(vertices), anchors)

    loads_by_stage = stage_node_loads(
        vertices, arrays["faces"], plan, thickness, density
    )
    net_weight = net_weight_loads(vertices, edges, mass_per_metre)
    # The weight each stage places, summed straight from face areas and NOT from
    # loads_by_stage, so the demand document can show the two agree (section
    # 5.2) without the reader trusting the code that distributed the loads.
    placed_weights = [
        sum(geometry.face_area(vertices, arrays["faces"][i])
            for i in entry["faces"]) * thickness * density * staging.GRAVITY
        for entry in plan
    ]
    request = {
        "study": None if study is None else str(study),
        "ea_provenance": None if ea_provenance is None else str(ea_provenance),
        "placed_weights": [float(w) for w in placed_weights],
        "vertices": [[float(c) for c in point] for point in vertices],
        "edges": [[int(u), int(v)] for u, v in edges],
        "anchors": [int(a) for a in anchors],
        "wires": [
            {"name": w.name, "net_vertex": w.net_vertex,
             "frame_point": list(w.frame_point),
             "machine_wire": w.machine_wire, "reeve_factor": w.reeve_factor,
             "permanence": w.permanence}
            for w in wires
        ],
        "loads_by_stage": loads_by_stage,
        "net_weight": net_weight,
        "ea": float(ea),
        "prestress": float(prestress),
        "acceptance": None if falsework else float(acceptance),
        "acceptance_source": None if falsework else str(acceptance_source),
        "falsework": falsework,
        "thickness": float(thickness),
        "density": float(density),
        "stage_names": {
            str(i): "S{}".format(entry["stage"]) for i, entry in enumerate(plan)
        },
    }
    if runner is None:
        runner = _subprocess_runner(python_exe or CABLENET_PYTHON)
    document = runner(request)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, allow_nan=False), encoding="utf-8")
    return {"path": str(out_path), "stages": len(document["stages"])}
