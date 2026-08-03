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

# TNASolve - Rhino 8 Grasshopper Python 3 component.
#
# Inputs (Type hint / Access):
#   Problem          object    Item   TNAProblem from TNARegister
#   SupportPoints    Point3d   List   empty = every boundary node
#   LoadPoints       Point3d   List   optional source-node locations
#   Pz               object    List   scalar, per LoadPoint, or source-aligned
#   VerticalMode     str       Item   "zmax" (default) or "q"
#   ZMax             float     Item   required/derived in zmax mode
#   QScale           float     Item   default -1 in q mode
#   Density          float     Item   must remain 0 in compas_tna 0.7 adapter;
#                                    add self-weight as explicit negative Pz
#   HorizontalAlpha  float     Item   0..100, default 100
#   HorizontalIter   int       Item   default 100
#   VerticalIter     int       Item   default 100
#   SolveTolerance   float     Item   default 1e-3
#   SnapTol          float     Item   maximum support/load point snap distance
#                                    (default 10 x registration WeldTol)
#   Run               bool      Item
#
# Outputs:
#   Session, ThrustLines, MemberForces, ForceDensities, SupportPointsOut,
#   Reactions, SourceToForm, SourceEdgeToForm, Diagnostics, Report

import sys

import numpy as np
import Rhino.Geometry as rg


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tree_forest_compas import tna  # noqa: E402


def _geo(value):
    return value.Value if hasattr(value, "Value") else value


def _items(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _analysis_plane(problem):
    data = problem.metadata.get("analysis_plane", {})
    if not data:
        return rg.Plane.WorldXY
    return rg.Plane(
        rg.Point3d(*data["origin"]),
        rg.Vector3d(*data["xaxis"]),
        rg.Vector3d(*data["yaxis"]),
    )


def _local_coordinates(point, to_xy):
    point = rg.Point3d(_geo(point))
    point.Transform(to_xy)
    return np.array([point.X, point.Y, point.Z], dtype=float)


def _world_point(coordinates, from_xy):
    point = rg.Point3d(*coordinates)
    point.Transform(from_xy)
    return point


def _nearest_source(problem, local_point):
    keys = list(problem.source_vertex_order)
    coordinates = np.asarray([problem.source_vertices[key] for key in keys])
    delta = coordinates - local_point
    distances2 = np.sum(delta * delta, axis=1)
    index = int(np.argmin(distances2))
    return keys[index], float(np.sqrt(distances2[index]))


Session = None
ThrustLines = []
MemberForces = []
ForceDensities = []
SupportPointsOut = []
Reactions = []
SourceToForm = []
SourceEdgeToForm = []
Diagnostics = []
Report = "Set Run to True."


if Run:
    if Problem is None:
        Report = "Connect a TNAProblem from TNARegister."
    else:
        plane = _analysis_plane(Problem)
        to_xy = rg.Transform.PlaneToPlane(plane, rg.Plane.WorldXY)
        from_xy = rg.Transform.PlaneToPlane(rg.Plane.WorldXY, plane)
        registration_tolerance = float(
            Problem.diagnostics.get("tolerance", 1e-6) or 1e-6
        )
        snap_input = globals().get("SnapTol")
        snap_tolerance = (
            float(snap_input)
            if snap_input is not None
            else 10.0 * registration_tolerance
        )
        if not np.isfinite(snap_tolerance) or snap_tolerance <= 0.0:
            raise ValueError("SnapTol must be finite and positive.")

        support_input = _items(SupportPoints)
        snap_distances = []
        if support_input:
            support_keys = []
            for point_index, point in enumerate(support_input):
                key, distance = _nearest_source(
                    Problem,
                    _local_coordinates(point, to_xy),
                )
                if distance > snap_tolerance:
                    raise ValueError(
                        "SupportPoints[{}] is {:.6g} from its nearest registered "
                        "node, beyond SnapTol {:.6g}.".format(
                            point_index, distance, snap_tolerance
                        )
                    )
                support_keys.append(key)
                snap_distances.append(distance)
            support_keys = list(dict.fromkeys(support_keys))
            support_mode = "keys"
        else:
            support_keys = None
            support_mode = "boundary"

        pz_input = _items(Pz)
        load_points = _items(LoadPoints)
        if load_points and not pz_input:
            pz_input = [-1.0]

        if not pz_input:
            pz = -1.0
        elif load_points:
            if len(pz_input) == 1:
                pz_input = pz_input * len(load_points)
            if len(pz_input) != len(load_points):
                raise ValueError(
                    "With LoadPoints, Pz must contain one value or one value per point."
                )
            pz = {}
            for point_index, (point, value) in enumerate(
                zip(load_points, pz_input)
            ):
                key, distance = _nearest_source(
                    Problem,
                    _local_coordinates(point, to_xy),
                )
                if distance > snap_tolerance:
                    raise ValueError(
                        "LoadPoints[{}] is {:.6g} from its nearest registered "
                        "node, beyond SnapTol {:.6g}.".format(
                            point_index, distance, snap_tolerance
                        )
                    )
                pz[key] = pz.get(key, 0.0) + float(value)
                snap_distances.append(distance)
        elif len(pz_input) == 1:
            pz = float(pz_input[0])
        elif len(pz_input) == len(Problem.source_vertex_order):
            pz = [float(value) for value in pz_input]
        else:
            raise ValueError(
                "Pz must be scalar, aligned with LoadPoints, or aligned with "
                "the {} registered source vertices.".format(
                    len(Problem.source_vertex_order)
                )
            )

        mode = str(VerticalMode or "zmax").strip().lower()
        zmax = float(ZMax) if ZMax is not None else None
        q_scale = float(QScale) if QScale is not None else -1.0
        density = float(Density) if Density is not None else 0.0
        alpha = (
            float(HorizontalAlpha) if HorizontalAlpha is not None else 100.0
        )
        horizontal_kmax = (
            int(HorizontalIter) if HorizontalIter is not None else 100
        )
        vertical_kmax = int(VerticalIter) if VerticalIter is not None else 100
        solve_tolerance = (
            float(SolveTolerance) if SolveTolerance is not None else 1e-3
        )

        Session = tna.solve_tna_problem(
            Problem,
            support_mode=support_mode,
            support_keys=support_keys,
            pz=pz,
            vertical_mode=mode,
            zmax=zmax,
            q_scale=q_scale,
            density=density,
            horizontal_alpha=alpha,
            horizontal_kmax=horizontal_kmax,
            vertical_kmax=vertical_kmax,
            vertical_tolerance=solve_tolerance,
        )

        form = Session.form
        form_points = {
            key: _world_point(form.vertex_coordinates(key), from_xy)
            for key in form.vertices()
        }
        active_edges = list(form.edges_where({"_is_edge": True}))
        ThrustLines = [
            rg.Line(form_points[u], form_points[v]) for u, v in active_edges
        ]

        def edge_key(edge):
            u, v = int(edge[0]), int(edge[1])
            return (u, v) if u < v else (v, u)

        MemberForces = [
            float(Session.edge_forces[edge_key(edge)]) for edge in active_edges
        ]
        ForceDensities = [
            float(Session.edge_q[edge_key(edge)]) for edge in active_edges
        ]
        SupportPointsOut = [
            form_points[key] for key in Session.support_form_keys
        ]
        Reactions = []
        for key in Session.support_form_keys:
            local = Session.support_reactions_by_form[key]
            Reactions.append(
                plane.XAxis * local[0]
                + plane.YAxis * local[1]
                + plane.ZAxis * local[2]
            )
        SourceToForm = [
            "{}:{}".format(key, Session.source_to_form[key])
            for key in Session.source_vertex_order
        ]
        SourceEdgeToForm = [
            "{}:{}".format(edge_id, Session.source_edge_to_form[edge_id])
            for edge_id in sorted(Session.source_edges)
        ]
        Diagnostics = [
            "{}={}".format(key, value)
            for key, value in sorted(Session.diagnostics.items())
        ]

        maximum_snap = max(snap_distances) if snap_distances else 0.0
        removed_vertices = len(Session.diagnostics.get("removed_source_keys", ()))
        removed_edges = len(
            Session.diagnostics.get("removed_source_edge_ids", ())
        )
        Report = (
            "COMPAS TNA whole-pattern solve complete\n"
            "Active vertices/edges: {}/{}\n"
            "Supports: {}  Removed boundary vertices/edges: {}/{}\n"
            "Solved height range: {:.6g} to {:.6g}\n"
            "Max free residual: {:.3e}\n"
            "Global force error: {:.3e}\n"
            "Max reciprocal angle error: {:.3e} deg\n"
            "Compression/tension edges: {}/{}\n"
            "Pz/reaction components use AnalysisPlane XYZ\n"
            "Maximum support/load snap: {:.6g} (SnapTol {:.6g})"
        ).format(
            Session.diagnostics["active_vertex_count"],
            Session.diagnostics["active_edge_count"],
            Session.diagnostics["support_count"],
            removed_vertices,
            removed_edges,
            Session.diagnostics["zmin_solved"],
            Session.diagnostics["zmax_solved"],
            Session.diagnostics["max_free_residual"],
            Session.diagnostics["global_force_error_norm"],
            Session.diagnostics["max_reciprocal_angle_deviation"],
            Session.diagnostics["compression_edge_count"],
            Session.diagnostics["tension_edge_count"],
            maximum_snap,
            snap_tolerance,
        )
