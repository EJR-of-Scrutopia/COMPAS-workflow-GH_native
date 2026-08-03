#! python 3
# venv: catenary-compas-2026

"""Report why a Rhino mesh cannot become a TNA pattern, and where.

Paste into a Rhino 8 Grasshopper Python 3 component.

Inputs (Type hint / Access):
    Mesh      Mesh    Item   the pattern mesh, exactly as fed to TNA Pattern
    WeldTol   float   Item   the same tolerance TNA Pattern uses (default 1e-6)

Outputs:
    Ok            True when the mesh can register as a TNA pattern
    Report        human-readable summary
    DefectPoints  Point3d list, one per offending edge midpoint, for baking
    DefectLines   Line list of the offending edges, so they can be isolated
    Naked         naked (boundary) edge count, for context

This deliberately duplicates no solver logic: it calls the same
``describe_mesh_defects`` the registrar uses, so what it reports is exactly what
the registrar would reject.
"""

import sys

import Rhino.Geometry as rg


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tree_forest_compas.tna import describe_mesh_defects  # noqa: E402


def _geo(value):
    return value.Value if hasattr(value, "Value") else value


Ok = False
Report = "Connect a Mesh."
DefectPoints = []
DefectLines = []
Naked = 0


def _weld(mesh, tolerance):
    """Merge coincident vertices exactly as ``_merge_source_points`` does.

    This is the same first-seen-wins linear scan the registrar performs, kept
    deliberately identical rather than optimised. A faster spatial hash would
    merge a slightly different set of near-tolerance points, and a diagnostic
    that disagrees with the thing it is diagnosing is worse than a slow one.
    """
    canonical = []
    remap = []
    squared = float(tolerance) ** 2
    for index in range(mesh.Vertices.Count):
        point = mesh.Vertices[index]
        xyz = (float(point.X), float(point.Y), float(point.Z))
        found = None
        for candidate, other in enumerate(canonical):
            delta = sum((xyz[axis] - other[axis]) ** 2 for axis in range(3))
            if delta <= squared:
                found = candidate
                break
        if found is None:
            found = len(canonical)
            canonical.append(xyz)
        remap.append(found)
    return canonical, remap


if Mesh is not None:
    mesh = _geo(Mesh)
    tolerance = float(WeldTol) if WeldTol else 1.0e-6

    vertices, remap = _weld(mesh, tolerance)

    faces = []
    for index in range(mesh.Faces.Count):
        face = mesh.Faces[index]
        if face.IsQuad:
            cycle = [face.A, face.B, face.C, face.D]
        else:
            cycle = [face.A, face.B, face.C]
        merged = []
        for corner in cycle:
            mapped = remap[corner]
            if not merged or merged[-1] != mapped:
                merged.append(mapped)
        if len(merged) > 1 and merged[0] == merged[-1]:
            merged.pop()
        if len(set(merged)) >= 3:
            faces.append(merged)

    defects = describe_mesh_defects(vertices, faces, limit=10)

    # Recompute the offending edges so they can be drawn, not just described.
    halfedges = {}
    edges = {}
    for face_index, face in enumerate(faces):
        for position, u in enumerate(face):
            v = face[(position + 1) % len(face)]
            if u == v:
                continue
            halfedges.setdefault((u, v), []).append(face_index)
            edges.setdefault((min(u, v), max(u, v)), []).append(face_index)

    bad = set()
    for (u, v), owners in halfedges.items():
        if len(owners) > 1:
            bad.add((min(u, v), max(u, v)))
    for edge, owners in edges.items():
        if len(owners) > 2:
            bad.add(edge)

    for u, v in sorted(bad):
        a = rg.Point3d(*vertices[u])
        b = rg.Point3d(*vertices[v])
        DefectLines.append(rg.Line(a, b))
        DefectPoints.append(rg.Point3d((a.X + b.X) / 2.0, (a.Y + b.Y) / 2.0, (a.Z + b.Z) / 2.0))

    Naked = sum(1 for owners in edges.values() if len(owners) == 1)
    Ok = not defects

    # Rhino's own validity is a different and stricter question than COMPAS's.
    # A mesh Rhino calls invalid can still register here, so report its reason
    # rather than leaving "Invalid Mesh" on a panel with no explanation.
    rhino_valid = True
    rhino_log = ""
    try:
        rhino_valid, rhino_log = mesh.IsValidWithLog()
    except Exception:
        try:
            rhino_valid = bool(mesh.IsValid)
        except Exception:
            rhino_valid = True

    triangles = sum(1 for index in range(mesh.Faces.Count) if mesh.Faces[index].IsTriangle)
    quads = mesh.Faces.Count - triangles

    lines = [
        "Mesh diagnosis for TNA registration",
        "Weld tolerance:      {:g}".format(tolerance),
        "Rhino vertices:      {}".format(mesh.Vertices.Count),
        "After welding:       {}".format(len(vertices)),
        "Merged away:         {}".format(mesh.Vertices.Count - len(vertices)),
        "Rhino faces:         {}  ({} tri, {} quad)".format(
            mesh.Faces.Count, triangles, quads
        ),
        "Usable faces:        {}".format(len(faces)),
        "Edges:               {}".format(len(edges)),
        "Naked (boundary):    {}".format(Naked),
        "Defective edges:     {}".format(len(bad)),
        "Rhino says valid:    {}".format(rhino_valid),
        "",
    ]
    if not rhino_valid and rhino_log:
        lines.append("Rhino's own validity complaint (a stricter, separate check):")
        lines.extend("  " + part for part in str(rhino_log).strip().splitlines())
        lines.append("")
    # Mixed triangles and quads are fine for TNA. A single very high valence
    # vertex is not a registration problem either, but it makes the horizontal
    # solve converge far more slowly, so it is worth knowing about.
    valence = {}
    for edge in edges:
        valence[edge[0]] = valence.get(edge[0], 0) + 1
        valence[edge[1]] = valence.get(edge[1], 0) + 1
    if valence:
        worst = max(valence.values())
        lines.append("Highest vertex valence: {}".format(worst))
        if worst >= 12:
            lines.append(
                "  A vertex joining {} edges is legal but slows horizontal TNA "
                "convergence sharply. Expect to raise Horizontal Iterations "
                "well above the default 100 and watch the reported "
                "reciprocity angle fall.".format(worst)
            )
        lines.append("")
    if defects:
        lines.append("REGISTRATION WILL FAIL. Causes:")
        lines.extend("  " + message for message in defects)
        lines.append("")
        lines.append(
            "DefectLines shows every offending edge. Bake it, then isolate "
            "those edges in Rhino to find the region at fault."
        )
        if mesh.Vertices.Count != len(vertices):
            lines.append(
                "Welding merged {} vertices. If the defects sit where two "
                "surfaces meet, the weld created them: try a smaller "
                "tolerance.".format(mesh.Vertices.Count - len(vertices))
            )
    else:
        lines.append("No blocking defect. This mesh can register as a TNA pattern.")

    Report = "\n".join(lines)
