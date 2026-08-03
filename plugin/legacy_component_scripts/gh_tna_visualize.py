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

# TNAVisualize - Rhino 8 Grasshopper Python 3 component.
#
# Inputs:
#   Session      object    Item   solved TNASession
#   ForceOrigin  Point3d   Item   empty = automatically placed beside form
#   ForceScale   float     Item   model units per horizontal-force unit
#   VectorScale  float     Item   model units per load/reaction unit
#   Run          bool      Item
#
# Outputs:
#   FormLines, ThrustLines, ForceLines, MemberForces, HorizontalForces,
#   ForceDensities, ForceNormalised, ForceColours, LoadPoints, LoadVectors,
#   ReactionPoints, ReactionVectors, ResidualPoints, ResidualVectors,
#   FormEdges, ForceEdges, FormToForceMappings, SourceEdgeMappings,
#   SourceToForceMappings, Report

import sys
from System.Drawing import Color

import numpy as np
import Rhino.Geometry as rg


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _analysis_plane(session):
    data = session.metadata.get("analysis_plane", {})
    if not data:
        return rg.Plane.WorldXY
    return rg.Plane(
        rg.Point3d(*data["origin"]),
        rg.Vector3d(*data["xaxis"]),
        rg.Vector3d(*data["yaxis"]),
    )


def _world_point(coordinates, from_xy):
    point = rg.Point3d(*coordinates)
    point.Transform(from_xy)
    return point


def _edge_key(edge):
    u, v = int(edge[0]), int(edge[1])
    return (u, v) if u < v else (v, u)


def _colour(force, maximum):
    amount = min(1.0, abs(float(force)) / maximum) if maximum > 0.0 else 0.0
    pale = np.array([225.0, 225.0, 225.0])
    target = (
        np.array([225.0, 55.0, 45.0])
        if force > 0.0
        else np.array([45.0, 105.0, 220.0])
    )
    rgb = pale + amount * (target - pale)
    return Color.FromArgb(255, int(rgb[0]), int(rgb[1]), int(rgb[2]))


FormLines = []
ThrustLines = []
ForceLines = []
MemberForces = []
HorizontalForces = []
ForceDensities = []
ForceNormalised = []
ForceColours = []
LoadPoints = []
LoadVectors = []
ReactionPoints = []
ReactionVectors = []
ResidualPoints = []
ResidualVectors = []
FormEdges = []
ForceEdges = []
FormToForceMappings = []
SourceEdgeMappings = []
SourceToForceMappings = []
Report = "Set Run to True."


if Run:
    if Session is None:
        Report = "Connect a solved TNASession."
    else:
        force_scale = float(ForceScale) if ForceScale is not None else 1.0
        vector_scale = float(VectorScale) if VectorScale is not None else 1.0
        if force_scale <= 0.0 or vector_scale <= 0.0:
            raise ValueError("ForceScale and VectorScale must be positive.")

        plane = _analysis_plane(Session)
        from_xy = rg.Transform.PlaneToPlane(rg.Plane.WorldXY, plane)
        form = Session.form
        force = Session.force
        active_edges = list(form.edges_where({"_is_edge": True}))
        ordered_force_edges = list(force.ordered_edges(form))

        thrust_points = {
            key: _world_point(form.vertex_coordinates(key), from_xy)
            for key in form.vertices()
        }
        plan_points = {}
        for key in form.vertices():
            x, y, _ = form.vertex_coordinates(key)
            plan_points[key] = _world_point([x, y, 0.0], from_xy)

        FormLines = [
            rg.Line(plan_points[u], plan_points[v]) for u, v in active_edges
        ]
        ThrustLines = [
            rg.Line(thrust_points[u], thrust_points[v]) for u, v in active_edges
        ]
        MemberForces = [
            float(Session.edge_forces[_edge_key(edge)]) for edge in active_edges
        ]
        ForceDensities = [
            float(Session.edge_q[_edge_key(edge)]) for edge in active_edges
        ]
        HorizontalForces = [
            ForceDensities[index]
            * FormLines[index].Length
            for index in range(len(active_edges))
        ]
        maximum_force = max((abs(value) for value in MemberForces), default=0.0)
        ForceNormalised = [
            abs(value) / maximum_force if maximum_force > 0.0 else 0.0
            for value in MemberForces
        ]
        ForceColours = [_colour(value, maximum_force) for value in MemberForces]
        FormEdges = ["{}-{}".format(u, v) for u, v in active_edges]
        ForceEdges = ["{}-{}".format(u, v) for u, v in ordered_force_edges]
        FormToForceMappings = [
            "{}-{} -> {}-{}".format(
                form_edge[0],
                form_edge[1],
                force_edge[0],
                force_edge[1],
            )
            for form_edge, force_edge in zip(active_edges, ordered_force_edges)
        ]

        for key in form.vertices():
            load = Session.effective_form_loads.get(
                int(key), (0.0, 0.0, 0.0)
            )
            if np.linalg.norm(load) > 1e-12:
                LoadPoints.append(thrust_points[key])
                LoadVectors.append(
                    (
                        plane.XAxis * load[0]
                        + plane.YAxis * load[1]
                        + plane.ZAxis * load[2]
                    )
                    * vector_scale
                )

        support_set = set(Session.support_form_keys)
        for key in Session.support_form_keys:
            local = Session.support_reactions_by_form[key]
            world = (
                plane.XAxis * local[0]
                + plane.YAxis * local[1]
                + plane.ZAxis * local[2]
            )
            ReactionPoints.append(thrust_points[key])
            ReactionVectors.append(world * vector_scale)

        for key in form.vertices():
            if key in support_set:
                continue
            residual = form.vertex_attributes(key, ["_rx", "_ry", "_rz"])
            if residual is None:
                continue
            local = [float(value or 0.0) for value in residual]
            if np.linalg.norm(local) <= 1e-12:
                continue
            world = (
                plane.XAxis * local[0]
                + plane.YAxis * local[1]
                + plane.ZAxis * local[2]
            )
            ResidualPoints.append(thrust_points[key])
            ResidualVectors.append(world * vector_scale)

        force_xyz = {
            key: force.vertex_coordinates(key) for key in force.vertices()
        }
        if force_xyz:
            cx = sum(value[0] for value in force_xyz.values()) / len(force_xyz)
            cy = sum(value[1] for value in force_xyz.values()) / len(force_xyz)
        else:
            cx = cy = 0.0
        if ForceOrigin is None:
            box = rg.BoundingBox(list(plan_points.values()))
            origin = box.Max + plane.XAxis * max(box.Diagonal.Length * 0.15, 1.0)
        else:
            value = ForceOrigin.Value if hasattr(ForceOrigin, "Value") else ForceOrigin
            origin = rg.Point3d(value)

        # The reciprocal is created before the vertical scale is applied. Scale
        # its lengths by |vertical_scale| so displayed lengths represent solved
        # horizontal-force magnitudes, then apply the user's display scale.
        physical_scale = abs(float(Session.diagnostics["vertical_scale"]))
        diagram_scale = physical_scale * force_scale

        def force_point(key):
            x, y, _ = force_xyz[key]
            return (
                origin
                + plane.XAxis * ((float(x) - cx) * diagram_scale)
                + plane.YAxis * ((float(y) - cy) * diagram_scale)
            )

        ForceLines = [
            rg.Line(force_point(u), force_point(v))
            for u, v in ordered_force_edges
        ]
        SourceEdgeMappings = [
            "{}:{}".format(edge_id, Session.source_edge_to_form[edge_id])
            for edge_id in sorted(Session.source_edges)
        ]
        active_to_force = {
            _edge_key(form_edge): force_edge
            for form_edge, force_edge in zip(active_edges, ordered_force_edges)
        }
        SourceToForceMappings = []
        for edge_id in sorted(Session.source_edges):
            form_edge = Session.source_edge_to_form[edge_id]
            if form_edge is None:
                SourceToForceMappings.append(
                    "{}: removed during boundary conditioning".format(edge_id)
                )
            else:
                force_edge = active_to_force.get(_edge_key(form_edge))
                SourceToForceMappings.append(
                    "{}: {} -> {}".format(edge_id, form_edge, force_edge)
                )
        Report = (
            "TNA visualisation ready\n"
            "Active form/thrust members: {}\n"
            "Reciprocal force edges: {}\n"
            "Blue=compression, red=tension\n"
            "MemberForces are total axial forces; reciprocal edge lengths show "
            "horizontal force.\n"
            "Physical reciprocal scale: {:.6g}; display scale: {:.6g}\n"
            "Maximum free residual: {:.3e}; global force error: {:.3e}"
        ).format(
            len(active_edges),
            len(ordered_force_edges),
            physical_scale,
            force_scale,
            Session.diagnostics["max_free_residual"],
            Session.diagnostics["global_force_error_norm"],
        )
