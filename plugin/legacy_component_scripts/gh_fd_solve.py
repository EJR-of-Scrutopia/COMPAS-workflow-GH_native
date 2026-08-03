#! python 3
# venv: catenary-compas-2026
# requirements: numpy==2.0.2
# requirements: scipy==1.13.1
# requirements: compas==2.15.1
# requirements: compas_fd==0.5.4
# requirements: compas_ags==1.3.3
# requirements: compas_tna==0.7.0
# requirements: compas_model==0.9.3
# requirements: compas_ifc==2.1.0

# FDWholeNetwork - Rhino 8 Grasshopper Python 3 component.
#
# Inputs (Type hint / Access):
#   Geometry       Geometry   List   Lines, LineCurves or Polylines; Flatten
#                                  this input to solve the entire network once
#   Supports       Point3d    List   empty = all degree-one registered vertices
#   LoadPoints     Point3d    List   positions at which LoadVectors are applied
#   LoadNodeIDs    int        List   optional alternative to LoadPoints; useful
#                                  for an integer moving-load position slider
#   LoadVectors    Vector3d   List   one vector (broadcast) or one per LoadPoint
#   ForceDensity   object     List   scalar, per input item, or per flat segment
#   WeldTol        float      Item
#   SnapTol        float      Item   maximum support/load point snap distance
#                                    (default 10 x WeldTol)
#   Run            bool       Item
#
# Outputs:
#   Problem, Session, RegisteredPoints, EquilibriumLines, MemberForces,
#   ForceDensities, SupportPoints, AppliedLoadNodeIDs, ResidualMagnitudes,
#   SourceEdges, Report
#
# All Geometry is flattened and welded into ONE registered COMPAS FD graph.

import importlib
import sys

import numpy as np
import Rhino
import Rhino.Geometry as rg


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tree_forest_compas import fd  # noqa: E402

importlib.reload(fd)


def _geo(value):
    return value.Value if hasattr(value, "Value") else value


def _items(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _segments(value):
    geometry = _geo(value)
    if isinstance(geometry, rg.Line):
        return list(geometry.GetSegments()) if hasattr(geometry, "GetSegments") else [geometry]
    if isinstance(geometry, rg.Polyline):
        return list(geometry.GetSegments())
    if isinstance(geometry, rg.LineCurve):
        return [geometry.Line]
    if isinstance(geometry, rg.Curve):
        success, polyline = geometry.TryGetPolyline()
        if success:
            return list(polyline.GetSegments())
        raise TypeError(
            "FDWholeNetwork accepts straight Lines and Polylines. Discretise "
            "curved members intentionally before solving."
        )
    raise TypeError("Every Geometry item must be a Rhino Line or Polyline.")


def _xyz(point):
    point = _geo(point)
    return [float(point.X), float(point.Y), float(point.Z)]


def _vector(vector):
    vector = _geo(vector)
    return [float(vector.X), float(vector.Y), float(vector.Z)]


def _nearest(vertices, point):
    delta = vertices - np.asarray(point, dtype=float)
    distances2 = np.sum(delta * delta, axis=1)
    index = int(np.argmin(distances2))
    return index, float(np.sqrt(distances2[index]))


Problem = None
Session = None
RegisteredPoints = []
EquilibriumLines = []
MemberForces = []
ForceDensities = []
SupportPoints = []
AppliedLoadNodeIDs = []
ResidualMagnitudes = []
SourceEdges = []
Report = "Set Run to True."


if Run:
    geometry_items = _items(Geometry)
    if not geometry_items:
        Report = "Connect the complete line/polyline network."
    else:
        document_tolerance = (
            Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
            if Rhino.RhinoDoc.ActiveDoc is not None
            else 1e-6
        )
        tolerance = float(WeldTol) if WeldTol is not None else document_tolerance
        snap_input = globals().get("SnapTol")
        snap_tolerance = (
            float(snap_input) if snap_input is not None else 10.0 * tolerance
        )
        if not np.isfinite(snap_tolerance) or snap_tolerance <= 0.0:
            raise ValueError("SnapTol must be finite and positive.")

        lines = []
        owners = []
        for owner, item in enumerate(geometry_items):
            for segment in _segments(item):
                lines.append([_xyz(segment.From), _xyz(segment.To)])
                owners.append(owner)

        Problem = fd.register_fd_network(lines, tolerance=tolerance)
        vertices = np.asarray(Problem.source_vertices, dtype=float)

        degree = np.zeros(len(vertices), dtype=int)
        for u, v in Problem.source_edges:
            degree[int(u)] += 1
            degree[int(v)] += 1

        support_snap = []
        support_input = _items(Supports)
        if support_input:
            fixed = []
            for point_index, point in enumerate(support_input):
                index, distance = _nearest(vertices, _xyz(point))
                if distance > snap_tolerance:
                    raise ValueError(
                        "Supports[{}] is {:.6g} from its nearest registered "
                        "node, beyond SnapTol {:.6g}.".format(
                            point_index, distance, snap_tolerance
                        )
                    )
                fixed.append(index)
                support_snap.append(distance)
            fixed = sorted(set(fixed))
        else:
            fixed = np.where(degree == 1)[0].tolist()
        if not fixed:
            raise ValueError(
                "No supports were found. Connect Supports or provide a graph "
                "with degree-one terminal vertices."
            )

        loads = np.zeros((len(vertices), 3), dtype=float)
        load_points = _items(LoadPoints)
        load_node_ids = [
            int(value) for value in _items(globals().get("LoadNodeIDs"))
        ]
        load_vectors = _items(LoadVectors)
        load_snap = []
        if load_points and load_node_ids:
            raise ValueError(
                "Use either LoadPoints or LoadNodeIDs, not both in one solve."
            )
        load_targets = load_node_ids if load_node_ids else load_points
        if load_vectors and not load_targets:
            raise ValueError(
                "LoadVectors are connected but LoadPoints/LoadNodeIDs are empty."
            )
        if load_targets:
            if not load_vectors:
                raise ValueError(
                    "LoadPoints/LoadNodeIDs are connected but LoadVectors are empty."
                )
            if len(load_vectors) == 1:
                load_vectors = load_vectors * len(load_targets)
            if len(load_vectors) != len(load_targets):
                raise ValueError(
                    "LoadVectors must contain one item or one vector per load target."
                )
            if load_node_ids:
                for item_index, (index, vector) in enumerate(
                    zip(load_node_ids, load_vectors)
                ):
                    if index < 0 or index >= len(vertices):
                        raise ValueError(
                            "LoadNodeIDs[{}]={} is outside 0..{}.".format(
                                item_index, index, len(vertices) - 1
                            )
                        )
                    loads[index] += np.asarray(_vector(vector), dtype=float)
                    AppliedLoadNodeIDs.append(index)
            else:
                for point_index, (point, vector) in enumerate(
                    zip(load_points, load_vectors)
                ):
                    index, distance = _nearest(vertices, _xyz(point))
                    if distance > snap_tolerance:
                        raise ValueError(
                            "LoadPoints[{}] is {:.6g} from its nearest registered "
                            "node, beyond SnapTol {:.6g}.".format(
                                point_index, distance, snap_tolerance
                            )
                        )
                    loads[index] += np.asarray(_vector(vector), dtype=float)
                    load_snap.append(distance)
                    AppliedLoadNodeIDs.append(index)

        q_input = _items(ForceDensity)
        if not q_input:
            q = 1.0
        elif len(q_input) == 1:
            q = float(q_input[0])
        elif len(q_input) == len(lines):
            q = [float(value) for value in q_input]
        elif len(q_input) == len(geometry_items):
            q = [float(q_input[owner]) for owner in owners]
        else:
            raise ValueError(
                "ForceDensity must be scalar, per input geometry item, or per "
                "flattened segment ({} values).".format(len(lines))
            )

        Session = fd.solve_fd_problem(
            Problem,
            fixed=fixed,
            forcedensities=q,
            loads=loads,
        )

        registered = [rg.Point3d(*coordinates) for coordinates in Problem.source_vertices]
        equilibrium = [
            rg.Point3d(*coordinates) for coordinates in Session.equilibrium_vertices
        ]
        RegisteredPoints = registered
        EquilibriumLines = [
            rg.Line(equilibrium[u], equilibrium[v])
            for u, v in Session.source_edges
        ]
        MemberForces = [float(value) for value in Session.member_forces]
        ForceDensities = [float(value) for value in Session.force_densities]
        SupportPoints = [equilibrium[index] for index in Session.fixed]
        ResidualMagnitudes = [
            float(np.linalg.norm(value)) for value in Session.residuals
        ]
        SourceEdges = [int(value) for edge in Session.source_edges for value in edge]

        snap_values = support_snap + load_snap
        maximum_snap = max(snap_values) if snap_values else 0.0
        Report = (
            Session.report
            + "\nInput geometry items: {}  Flattened segments: {}"
            + "\nMaximum support/load snap: {:.6g} (SnapTol {:.6g})"
            + "\nApplied load records/nodes: {} / {}"
        ).format(
            len(geometry_items),
            len(lines),
            maximum_snap,
            snap_tolerance,
            len(AppliedLoadNodeIDs),
            len(set(AppliedLoadNodeIDs)),
        )
