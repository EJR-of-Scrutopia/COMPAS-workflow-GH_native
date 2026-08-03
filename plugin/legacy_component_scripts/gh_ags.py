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

# AGSGraphicStatics - Rhino 8 Grasshopper Python 3 component.
#
# This is a thin adapter around ``tree_forest_compas.ags``. It registers every
# connected line/polyline segment as ONE planar form graph and solves one
# reciprocal force diagram. It does not solve each input curve independently.
#
# Inputs (Type hint / Access):
#   Geometry       Geometry   List   complete planar line/polyline system,
#                                  including its external load/reaction edges;
#                                  Flatten this input for one global solve
#   DiagramPlane   Plane      Item   plane containing Geometry; WorldXY if empty
#   ReferenceEdge int        Item   source segment index (default 0)
#   ReferenceForce float     Item   signed known force (default -1; negative
#                                  compression in the chosen convention)
#   IndependentEdges int     List   optional complete independent-edge set;
#                                  replaces ReferenceEdge when connected
#   IndependentForces float  List   one signed force per IndependentEdge
#   LoadEdges      int       List   optional external source-edge role labels
#   ReactionEdges  int       List   optional external source-edge role labels
#   ForceOrigin    Point3d    Item   display origin for the force diagram
#   ForceScale     float      Item   display-only scale (default 1)
#   Run            bool       Item
#
# Outputs:
#   Session, FormLines, ForceLines, ForceInternalLines, ForceExternalLines,
#   ForceLoadLines, ForceReactionLines, ForceVertices, ForceFaces, ForceRoles,
#   SourceForces, SourceRoles, ForceMagnitudes, ReciprocityErrors,
#   SourceToFormEdge, SourceToForceEdge, Nullity, Mechanisms, Report
#
# Important: crossings must already be split. AGS is a two-dimensional method;
# transform a spatial slice/joint into DiagramPlane before using this component.

import importlib
import sys

import Rhino.Geometry as rg


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tree_forest_compas import ags  # noqa: E402

importlib.reload(ags)


def _geo(value):
    return value.Value if hasattr(value, "Value") else value


def _items(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _polyline_segments(value):
    geometry = _geo(value)
    if isinstance(geometry, rg.Line):
        return [geometry]
    if isinstance(geometry, rg.Polyline):
        return list(geometry.GetSegments())
    if isinstance(geometry, rg.LineCurve):
        return [geometry.Line]
    if isinstance(geometry, rg.Curve):
        success, polyline = geometry.TryGetPolyline()
        if success:
            return list(polyline.GetSegments())
        raise TypeError(
            "AGS accepts straight Lines and Polylines. Convert curved geometry "
            "to an intentional straight-edge discretisation first."
        )
    raise TypeError("Every Geometry item must be a Rhino Line or Polyline.")


def _point_coordinates(point, to_xy):
    copy = rg.Point3d(point)
    copy.Transform(to_xy)
    return [float(copy.X), float(copy.Y), float(copy.Z)]


def _rhino_point(xyz, from_xy):
    point = rg.Point3d(float(xyz[0]), float(xyz[1]), float(xyz[2]))
    point.Transform(from_xy)
    return point


Session = None
FormLines = []
ForceLines = []
ForceInternalLines = []
ForceExternalLines = []
ForceLoadLines = []
ForceReactionLines = []
ForceVertices = []
ForceFaces = []
ForceRoles = []
SourceForces = []
SourceRoles = []
ForceMagnitudes = []
ReciprocityErrors = []
SourceToFormEdge = []
SourceToForceEdge = []
Nullity = 0
Mechanisms = 0
Report = "Set Run to True."


if Run:
    source_geometry = _items(Geometry)
    if not source_geometry:
        Report = "Connect the complete planar line/polyline system."
    else:
        plane = _geo(DiagramPlane) if DiagramPlane is not None else rg.Plane.WorldXY
        if not isinstance(plane, rg.Plane) or not plane.IsValid:
            raise ValueError("DiagramPlane must be a valid Rhino Plane.")

        to_xy = rg.Transform.PlaneToPlane(plane, rg.Plane.WorldXY)
        from_xy = rg.Transform.PlaneToPlane(rg.Plane.WorldXY, plane)

        source_lines = []
        for item in source_geometry:
            for segment in _polyline_segments(item):
                source_lines.append(
                    [
                        _point_coordinates(segment.From, to_xy),
                        _point_coordinates(segment.To, to_xy),
                    ]
                )

        reference_edge = int(ReferenceEdge) if ReferenceEdge is not None else 0
        reference_force = (
            float(ReferenceForce) if ReferenceForce is not None else -1.0
        )
        independent_edges_input = _items(globals().get("IndependentEdges"))
        independent_forces_input = _items(globals().get("IndependentForces"))
        independent_edges = (
            [int(value) for value in independent_edges_input]
            if independent_edges_input
            else None
        )
        independent_forces = (
            [float(value) for value in independent_forces_input]
            if independent_forces_input
            else None
        )
        load_edges = [
            int(value) for value in _items(globals().get("LoadEdges"))
        ]
        reaction_edges = [
            int(value) for value in _items(globals().get("ReactionEdges"))
        ]
        force_scale = float(ForceScale) if ForceScale is not None else 1.0
        if force_scale <= 0.0:
            raise ValueError("ForceScale must be positive.")

        Session = ags.solve_planar_graphic_statics(
            source_lines,
            reference_source_edge=reference_edge,
            reference_force=reference_force,
            independent_source_edges=independent_edges,
            independent_forces=independent_forces,
            load_source_edges=load_edges,
            reaction_source_edges=reaction_edges,
        )

        # Form geometry is emitted in COMPAS form-edge order. SourceForces is
        # separately aligned with the flattened input segment order.
        for u, v in Session.form_edges:
            a = _rhino_point(Session.form.vertex_coordinates(u), from_xy)
            b = _rhino_point(Session.form.vertex_coordinates(v), from_xy)
            FormLines.append(rg.Line(a, b))

        if ForceOrigin is None:
            form_points = [
                _rhino_point(Session.form.vertex_coordinates(key), from_xy)
                for key in Session.form.vertices()
            ]
            box = rg.BoundingBox(form_points)
            display_origin = box.Max + plane.XAxis * max(
                box.Diagonal.Length * 0.15, 1.0
            )
        else:
            display_origin = rg.Point3d(_geo(ForceOrigin))

        force_xyz = {
            key: Session.force.vertex_coordinates(key)
            for key in Session.force.vertices()
        }
        if force_xyz:
            cx = sum(value[0] for value in force_xyz.values()) / len(force_xyz)
            cy = sum(value[1] for value in force_xyz.values()) / len(force_xyz)
        else:
            cx = cy = 0.0

        def force_point(key):
            x, y, _ = force_xyz[key]
            return (
                display_origin
                + plane.XAxis * ((float(x) - cx) * force_scale)
                + plane.YAxis * ((float(y) - cy) * force_scale)
            )

        force_points = {
            key: force_point(key) for key in Session.force.vertices()
        }
        ForceVertices = [force_points[key] for key in Session.force.vertices()]
        for face in Session.force.faces():
            keys = Session.force.face_vertices(face)
            if len(keys) >= 3:
                points = [force_points[key] for key in keys]
                ForceFaces.append(rg.PolylineCurve(points + [points[0]]))

        for (u, v), role in zip(Session.force_edges, Session.form_edge_roles):
            line = rg.Line(force_points[u], force_points[v])
            ForceLines.append(line)
            ForceRoles.append(role)
            if role == "member":
                ForceInternalLines.append(line)
            else:
                ForceExternalLines.append(line)
            if role == "load":
                ForceLoadLines.append(line)
            elif role == "reaction":
                ForceReactionLines.append(line)

        SourceForces = [float(value) for value in Session.source_forces]
        SourceRoles = list(Session.source_roles)
        ForceMagnitudes = [abs(float(value)) for value in Session.member_forces]
        ReciprocityErrors = [
            abs(float(value)) for value in Session.angle_deviations
        ]
        SourceToFormEdge = [
            "{}-{}".format(edge[0], edge[1])
            for edge in Session.source_edge_to_form_edge
        ]
        SourceToForceEdge = [
            "{}-{}".format(edge[0], edge[1])
            for edge in Session.source_edge_to_force_edge
        ]
        Nullity = int(Session.nullity)
        Mechanisms = int(Session.mechanisms)
        Report = (
            Session.report
            + "\nOne connected system was registered from {} input item(s) "
            "and {} straight segment(s)."
            + "\nForceLines is one connected reciprocal. ForceExternalLines "
            "is its external-force polygon; roles are explicit only when "
            "LoadEdges/ReactionEdges are supplied."
        ).format(len(source_geometry), len(source_lines))
