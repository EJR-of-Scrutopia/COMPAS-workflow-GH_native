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

# TNARegister - Rhino 8 Grasshopper Python 3 component.
#
# Inputs (Type hint / Access):
#   Geometry      Geometry   List   connect the faced Mesh directly (do not
#                                  explode it with Mesh Edges), OR provide all
#                                  planar Lines/Polylines; Flatten this input
#                                  to register the entire object once
#   AnalysisPlane Plane      Item   WorldXY if empty
#   WeldTol       float      Item
#   Precision     int        Item   optional decimal merge precision
#   Run           bool       Item
#
# Outputs:
#   Problem, PatternLines, RegisteredPoints, FacePolylines, SourceVertexKeys,
#   SourceEdges, SourceToForm, SourceEdgeToForm, Report
#
# Every connected item is registered as ONE TNA pattern. Meshes provide faces.
# Lines/Polylines must already be split at crossings and enclose multiple faces.

import sys

import Rhino
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


def _local_point(point, to_xy):
    copy = rg.Point3d(point)
    copy.Transform(to_xy)
    return [float(copy.X), float(copy.Y), float(copy.Z)]


def _world_point(coordinates, from_xy):
    point = rg.Point3d(*coordinates)
    point.Transform(from_xy)
    return point


def _curve_segments(value):
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
            "TNA line registration accepts straight Lines and Polylines only. "
            "Discretise curves intentionally and split every crossing."
        )
    raise TypeError("Every line-pattern item must be a Rhino Line or Polyline.")


def _mesh_vertices_faces(mesh, to_xy, vertex_offset):
    topology = mesh.TopologyVertices
    vertices = [
        _local_point(topology[index], to_xy)
        for index in range(topology.Count)
    ]
    faces = []
    for face_index in range(mesh.Faces.Count):
        face = mesh.Faces.GetFace(face_index)
        mesh_vertices = [face.A, face.B, face.C]
        if face.IsQuad:
            mesh_vertices.append(face.D)
        topology_vertices = [
            int(mesh.TopologyVertices.TopologyVertexIndex(index))
            for index in mesh_vertices
        ]
        clean = []
        for index in topology_vertices:
            if not clean or clean[-1] != index:
                clean.append(index)
        if len(clean) > 1 and clean[0] == clean[-1]:
            clean.pop()
        if len(set(clean)) < 3:
            raise ValueError(
                "Mesh face {} collapses below three topology vertices.".format(
                    face_index
                )
            )
        faces.append([vertex_offset + index for index in clean])
    return vertices, faces


def _plane_metadata(plane):
    return {
        "origin": [plane.OriginX, plane.OriginY, plane.OriginZ],
        "xaxis": [plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z],
        "yaxis": [plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z],
        "zaxis": [plane.ZAxis.X, plane.ZAxis.Y, plane.ZAxis.Z],
    }


Problem = None
PatternLines = []
RegisteredPoints = []
FacePolylines = []
SourceVertexKeys = []
SourceEdges = []
SourceToForm = []
SourceEdgeToForm = []
Report = "Set Run to True."


if Run:
    source = _items(Geometry)
    if not source:
        Report = "Connect all meshes or all lines/polylines for one TNA pattern."
    else:
        plane = _geo(AnalysisPlane) if AnalysisPlane is not None else rg.Plane.WorldXY
        if not isinstance(plane, rg.Plane) or not plane.IsValid:
            raise ValueError("AnalysisPlane must be a valid Rhino Plane.")
        to_xy = rg.Transform.PlaneToPlane(plane, rg.Plane.WorldXY)
        from_xy = rg.Transform.PlaneToPlane(rg.Plane.WorldXY, plane)

        document_tolerance = (
            Rhino.RhinoDoc.ActiveDoc.ModelAbsoluteTolerance
            if Rhino.RhinoDoc.ActiveDoc is not None
            else 1e-6
        )
        tolerance = float(WeldTol) if WeldTol is not None else document_tolerance
        precision = int(Precision) if Precision is not None else None

        geometry = [_geo(item) for item in source]
        meshes = [item for item in geometry if isinstance(item, rg.Mesh)]
        curves = [item for item in geometry if not isinstance(item, rg.Mesh)]
        if meshes and curves:
            raise ValueError(
                "Do not mix meshes and curves in one TNARegister input. Convert "
                "the complete pattern to one representation first."
            )

        metadata = {"analysis_plane": _plane_metadata(plane)}
        if meshes:
            vertices = []
            faces = []
            for mesh in meshes:
                local_vertices, local_faces = _mesh_vertices_faces(
                    mesh,
                    to_xy,
                    len(vertices),
                )
                vertices.extend(local_vertices)
                faces.extend(local_faces)
            Problem = tna.register_tna_pattern(
                vertices=vertices,
                faces=faces,
                tolerance=tolerance,
                precision=precision,
                metadata=metadata,
            )
        else:
            lines = []
            for item in curves:
                for segment in _curve_segments(item):
                    lines.append(
                        [
                            _local_point(segment.From, to_xy),
                            _local_point(segment.To, to_xy),
                        ]
                    )
            zvalues = [point[2] for line in lines for point in line]
            if zvalues and max(zvalues) - min(zvalues) > tolerance:
                raise ValueError(
                    "TNA linework must lie in AnalysisPlane. Project it or "
                    "choose the correct plane before registration."
                )
            Problem = tna.register_tna_pattern(
                lines=lines,
                tolerance=tolerance,
                precision=precision,
                metadata=metadata,
            )

        form = Problem.form
        form_points = {
            key: _world_point(form.vertex_coordinates(key), from_xy)
            for key in form.vertices()
        }
        PatternLines = [
            rg.Line(form_points[u], form_points[v]) for u, v in form.edges()
        ]
        RegisteredPoints = [form_points[key] for key in form.vertices()]
        FacePolylines = [
            rg.Polyline(
                [form_points[key] for key in form.face_vertices(face)]
                + [form_points[form.face_vertices(face)[0]]]
            )
            for face in form.faces()
        ]
        SourceVertexKeys = [str(key) for key in Problem.source_vertex_order]
        SourceEdges = [
            "{}:{}-{}".format(edge_id, edge[0], edge[1])
            for edge_id, edge in Problem.source_edges.items()
        ]
        SourceToForm = [
            "{}:{}".format(key, Problem.source_to_form[key])
            for key in Problem.source_vertex_order
        ]
        SourceEdgeToForm = [
            "{}:{}-{}".format(edge_id, edge[0], edge[1])
            for edge_id, edge in Problem.source_edge_to_form.items()
        ]
        diagnostics = Problem.diagnostics
        Report = (
            "TNA whole-pattern registration complete\n"
            "Source kind: {}\n"
            "Registered vertices/edges/faces: {}/{}/{}\n"
            "Source edges: {}  Components: {}\n"
            "All geometry was registered together; no per-line TNA solves."
        ).format(
            Problem.source_kind,
            form.number_of_vertices(),
            form.number_of_edges(),
            form.number_of_faces(),
            len(Problem.source_edges),
            diagnostics.get("component_count", 1),
        )
