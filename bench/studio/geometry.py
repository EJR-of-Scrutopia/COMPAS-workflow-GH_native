"""Read a Grasshopper contract export with nothing but the standard library.

The studio may not import ananke_fea (see tests/studio/test_studio_guard.py),
so the three small pieces it needs from that world are duplicated here on
purpose: the kN conversion, the slug rule, and the export-pair listing. Each
copy is pinned by its own tests; if one changes, its test says so.

Geometry facts this module relies on (verified against Trial 2):
- equilibrium.vertices carry the true 3D thrust surface in metres, in node
  id order (id 0 is index 0).
- formGraph.faces[i]["vertices"] index directly into equilibrium.vertices.
  formGraph's own vertex z is the flat form diagram and is never read.
  These two are ASSUMPTIONS about ids matching array positions, and
  check_index_spaces now refuses an export that breaks them rather than
  letting it draw and solve a surface built from the wrong vertices.
- equilibrium.edges are {u, v} node id pairs.
- Forces are kilonewtons; they become newtons here, exactly once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

KN_TO_N = 1000.0


def slugify(name: str) -> str:
    """The study folder rule demo 09 uses: lower case, spaces to hyphens."""

    return name.lower().replace(" ", "-")


def load_contract(path) -> Dict[str, Any]:
    """The stored contract, or a ValueError NAMING the file.

    A contract torn by a killed process mid-store used to raise the bare
    JSONDecodeError, which reaches the client as a 400 reading
    "Expecting value: line 1 column 415" and names nothing: the study
    tile still listed, the run still accepted, and nothing anywhere
    pointed at the file on disk as the thing to replace.
    """

    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            "{} is not valid JSON ({}). The stored file is damaged, most "
            "likely a write that was interrupted; re-upload this export "
            "from Grasshopper.".format(path.name, error)
        ) from error


# The four names the studio writes into the upload folder itself. A file
# ending in one of these belongs to a study; anything else in the folder is
# a candidate study of its own.
# The four the studio has always written, and the three the exporter is
# moving to (the plugin session's REPLY to R-010 and R-011, 2026-09-03,
# settled by Param: form, skin, formwork). Both sets resolve side by side,
# because his existing studies must keep opening on the day the exporter
# changes over.
KIND_SUFFIXES = (
    "-contract.json", "-compas.json", "-tessellation.json", "-frames.json",
    "-form.json", "-skin.json", "-formwork.json", "-mechanism.json")

# The two spellings of the document that carries the form, newest first, so
# a study written both ways lands on the newer one.
CONTRACT_SUFFIXES = ("-form.json", "-contract.json")


def export_name_from_contract(path) -> str:
    """The export a contract file belongs to.

    ONE rule for naming a study, because there were two and they
    disagreed. The suffix is MATCHED, never assumed: a caller that
    subtracts the length of the old "-contract.json" from a name that
    ends in the new "-form.json" eats the four-character difference in
    silence, and takes real letters of the study's name with it.

    That is what reached Param. His "2 Sided Vault" arrived at the cut as
    "2 Sided V", so the run went looking for the skin of a study nobody
    has and reported that he had never authored one -- while the same
    study, named correctly by available_exports, was on screen wearing
    its authored cut of 215 pieces. The name is recovered here now, once,
    and both callers use it.
    """

    name = Path(path).name
    for suffix in CONTRACT_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    # A file dropped in under its own name is a study too (see
    # available_exports), and its stem is the whole name.
    return Path(path).stem

# Verdicts for the loose scan below, keyed by path, size and mtime. The
# browser polls the study list every two seconds and a contract runs to
# megabytes, so each file is read once and re-read only when it changes.
_LOOKS_LIKE_CONTRACT: Dict[Any, bool] = {}


def reads_like_a_contract(path) -> bool:
    """True when this file carries the two blocks a study is built from."""

    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return False
    key = (str(path), stat.st_size, stat.st_mtime)
    verdict = _LOOKS_LIKE_CONTRACT.get(key)
    if verdict is None:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            verdict = False
        else:
            verdict = (
                isinstance(document, Mapping)
                and isinstance(document.get("equilibrium"), Mapping)
                and isinstance(document.get("formGraph"), Mapping)
            )
        # A scan cache, not a store: a long session in a busy folder is
        # capped rather than allowed to grow with every rewrite.
        if len(_LOOKS_LIKE_CONTRACT) > 256:
            _LOOKS_LIKE_CONTRACT.clear()
        _LOOKS_LIKE_CONTRACT[key] = verdict
    return verdict


def available_exports(directory) -> Dict[str, Dict[str, Path]]:
    """Map export name to its files, for every contract in the folder.

    A contract is enough. The compas half used to be required, and it is a
    passenger: nothing in the studio parses it, it is carried through to
    the stage plan as a path and no further, and Round trip check ships one
    whose every field is null and opens exactly like the others. Requiring
    it hid whole studies from the list over a file that says nothing.

    A JSON that carries no kind suffix counts as a contract when it reads
    like one, so a file dropped into the folder under its own name is
    offered as a study rather than ignored. Suffixed files are matched
    first, so a study never appears twice.
    """

    directory = Path(directory)
    pairs: Dict[str, Dict[str, Path]] = {}
    # -form.json is the new name for what -contract.json holds, and it is
    # read first so a study that has both lands on the newer document.
    for suffix in CONTRACT_SUFFIXES:
        for contract in sorted(directory.glob("*" + suffix)):
            name = export_name_from_contract(contract)
            if name in pairs:
                continue
            entry: Dict[str, Path] = {"contract": contract}
            geometry = directory / (name + "-compas.json")
            if geometry.is_file():
                entry["geometry"] = geometry
            pairs[name] = entry
    for path in sorted(directory.glob("*.json")):
        if any(path.name.endswith(suffix) for suffix in KIND_SUFFIXES):
            continue
        if path.stem in pairs:
            continue
        if reads_like_a_contract(path):
            pairs[path.stem] = {"contract": path}
    return pairs


def _equilibrium(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    block = contract.get("equilibrium")
    if not isinstance(block, Mapping):
        raise ValueError("this file has no equilibrium block; is it Contract mode?")
    return block


def check_index_spaces(contract: Mapping[str, Any]) -> None:
    """Refuse a contract whose ids do not line up with array positions.

    The module docstring's second and third facts are ASSUMPTIONS, not
    guarantees. formGraph.faces carry FORM vertex ids, and form vertices
    and equilibrium vertices are two index spaces joined by
    mappings.sourceVertexToFormVertex; the exporter's own plugin readers
    sort by id rather than trusting array position, in both
    MouldComponents and SkinPatterns, which is as clear a statement as
    the contract makes that position is not the key.

    The two spaces are the identity on every export in existence
    (measured 2026-09-09: 2 Sided Vault 441, Aramdillo style 801, Column
    diagnosis 661, Round trip check 441, all identity, all face ids
    0..n-1 in array order). So this is a no-op today, and the studio goes
    on indexing by position, which it must: the stage plan names placed
    faces by position and solve_stage looks them up the same way, so
    changing one reader alone would put the cut and the analysis on
    different meshes.

    What this refuses is the day that stops being true. A permuted vertex
    space would draw a scrambled vault and solve a vault nobody designed,
    and the numbers would still look like numbers. Named here instead, at
    the one door every reader comes through.
    """

    equilibrium = _equilibrium(contract)
    count = len(equilibrium.get("vertices", []))

    mappings = contract.get("mappings") or {}
    for entry in mappings.get("sourceVertexToFormVertex") or []:
        form_id = entry.get("formVertexId")
        equilibrium_id = entry.get("equilibriumVertexId")
        if form_id is None or equilibrium_id is None:
            continue
        if int(form_id) != int(equilibrium_id):
            raise ValueError(
                "this export's form and equilibrium vertices are different "
                "index spaces (form vertex {} is equilibrium vertex {}), and "
                "the studio indexes faces into equilibrium.vertices directly. "
                "Reading it would draw and solve the wrong "
                "surface.".format(form_id, equilibrium_id))

    # A face's own id is DELIBERATELY not compared with its array
    # position, and this is the one clause that was here and was wrong.
    #
    # Nothing in the studio or in ananke_fea ever reads face["id"]: the
    # cut binding joins cells to faces geometrically (point_in_ring), and
    # the stage plan then names faces by position in a numbering that is
    # entirely the studio's own. A face id that disagrees with its
    # position is therefore ignored data, not a hazard, and the
    # exporter's readers sort by id precisely because out-of-order faces
    # are ordinary input to them.
    #
    # Refusing them would have failed a study the plugin reads correctly,
    # and blamed his file for a limit of this reader -- which is the same
    # sentence that started all of this: "Upload one from the Skin
    # component", said of a study whose skin was already on disk.
    for position, face in enumerate(contract.get("formGraph", {}).get("faces") or []):
        for index in face.get("vertices", []):
            if not 0 <= int(index) < count:
                raise ValueError(
                    "face {} names vertex {}, which is outside this export's "
                    "{} equilibrium vertices".format(position, index, count))


def mesh_arrays(contract: Mapping[str, Any]) -> Dict[str, list]:
    """Vertices, quad faces, and edges as plain lists for JSON shipping."""

    check_index_spaces(contract)
    equilibrium = _equilibrium(contract)
    vertices = [
        [float(v["x"]), float(v["y"]), float(v["z"])]
        for v in equilibrium.get("vertices", [])
    ]
    form = contract.get("formGraph") or {}
    faces = [
        [int(i) for i in face["vertices"]]
        for face in form.get("faces", [])
    ]
    edges = [
        [int(e["u"]), int(e["v"])]
        for e in equilibrium.get("edges", [])
    ]
    if not faces:
        raise ValueError("this contract has no formGraph faces to build a surface from")
    return {"vertices": vertices, "faces": faces, "edges": edges}


def support_ids(contract: Mapping[str, Any]) -> List[int]:
    return [int(i) for i in _equilibrium(contract).get("resolvedSupportNodeIds", [])]


def node_loads_newtons(contract: Mapping[str, Any]) -> Dict[int, List[float]]:
    """Applied load per node id, converted from kilonewtons exactly once."""

    return _vector_map_newtons(contract, "loads")


def support_reactions_newtons(contract: Mapping[str, Any]) -> Dict[int, List[float]]:
    """TNA reaction per support node id, in newtons."""

    return _vector_map_newtons(contract, "reactions")


def _vector_map_newtons(
    contract: Mapping[str, Any], key: str
) -> Dict[int, List[float]]:
    loads: Dict[int, List[float]] = {}
    for entry in _equilibrium(contract).get(key, []):
        vector = entry.get("vector")
        if vector is None:
            raise ValueError(
                "node {!r} has no {} vector; a missing vector must not "
                "silently become zero".format(entry.get("nodeId"), key)
            )
        loads[int(entry["nodeId"])] = [
            float(vector.get("x", 0.0)) * KN_TO_N,
            float(vector.get("y", 0.0)) * KN_TO_N,
            float(vector.get("z", 0.0)) * KN_TO_N,
        ]
    return loads


def member_forces_newtons(contract: Mapping[str, Any]) -> List[float]:
    """Axial force per member, in newtons, tension positive, one per edge.

    Mirrors src/ananke_fea/mesh.py:member_forces -- the kN to N conversion
    happens exactly once, here. Returns [] when the contract carries no
    equilibrium.memberForces. Raises ValueError naming the mismatch when
    memberForces is present but its count differs from a non-empty
    equilibrium.edges list (edges is the order buildWiresAndNodes builds
    wire instances in, so the two must line up one-to-one).
    """

    equilibrium = _equilibrium(contract)
    forces = equilibrium.get("memberForces", [])
    if not forces:
        return []
    edges = equilibrium.get("edges", [])
    if edges and len(forces) != len(edges):
        raise ValueError(
            "equilibrium.memberForces has {} entries but equilibrium.edges "
            "has {}; they must be one-to-one".format(len(forces), len(edges))
        )
    return [float(value) * KN_TO_N for value in forces]


def face_centroids(vertices: List[list], faces: List[list]) -> List[List[float]]:
    out = []
    for face in faces:
        xs = [vertices[i] for i in face]
        n = float(len(face))
        out.append([
            sum(p[0] for p in xs) / n,
            sum(p[1] for p in xs) / n,
            sum(p[2] for p in xs) / n,
        ])
    return out


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def face_area(vertices: List[list], face: List[int]) -> float:
    """Area of a (possibly warped) quad or triangle: fan of triangles."""

    base = vertices[face[0]]
    total = 0.0
    for i in range(1, len(face) - 1):
        p, q = vertices[face[i]], vertices[face[i + 1]]
        u = (p[0] - base[0], p[1] - base[1], p[2] - base[2])
        v = (q[0] - base[0], q[1] - base[1], q[2] - base[2])
        c = _cross(u, v)
        total += 0.5 * (c[0] ** 2 + c[1] ** 2 + c[2] ** 2) ** 0.5
    return total
