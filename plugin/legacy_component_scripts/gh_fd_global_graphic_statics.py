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

# FDGlobalGraphicStatics - Rhino 8 Grasshopper Python 3 component.
#
# This component turns ONE solved planar COMPAS FD network into the connected
# graphic-statics drawing shown in classical references. It stitches shared
# member-force sides; it does not lay independent joint triangles beside one
# another.
#
# Inputs (Type hint / Access):
#   Session        object     Item   FDSession from FDWholeNetwork
#   DiagramPlane   Plane      Item   planar system orientation; empty = infer
#   StartNode      int        Item   optional first terminal of a chain
#   QNodeID        int        Item   optional load node to highlight only
#   ForceOrigin    Point3d    Item   empty = automatically placed beside form
#   ForceScale     float      Item   display-only model units per force unit
#   Tolerance      float      Item   relative planarity/closure tolerance
#   Clockwise      bool       Item   force-cell winding; default True
#   Run            bool       Item
#
# Outputs:
#   GraphicSession, FormLines, ForceMemberLines, ForceLoadLines,
#   ForceLoadStartPoints, ForceLoadVectors, ForceReactionLines,
#   ForceReactionStartPoints, ForceReactionVectors, ForceCells,
#   BoundaryLines, BoundaryKinds,
#   OuterEnvelope, Pole, LoadLinePoints, LoadLineSegments, QSegment,
#   ChainNodeIDs, ChainEdgeIDs, MemberIDs, LoadNodeIDs, ReactionNodeIDs,
#   ClosureErrors, StitchError, PlanarityErrors, ForceDimension,
#   FitsOuterEnvelope, DiagramPlaneOut, Report
#
# Routing:
#   serial FD cable/arch -> one pole fan + load line + detected outer triangle
#   acyclic planar tree -> connected shared-edge reciprocal cells
#   cyclic canopy/truss  -> AGSGraphicStatics
#   faced mesh/pattern   -> TNAVisualize

import importlib
import sys

import Rhino.Geometry as rg
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tree_forest_compas import graphic_statics  # noqa: E402

importlib.reload(graphic_statics)


def _geo(value):
    return value.Value if hasattr(value, "Value") else value


def _point(value):
    return rg.Point3d(float(value[0]), float(value[1]), float(value[2]))


def _vector(value):
    return rg.Vector3d(float(value[0]), float(value[1]), float(value[2]))


GraphicSession = None
FormLines = []
ForceMemberLines = []
ForceLoadLines = []
ForceLoadStartPoints = []
ForceLoadVectors = []
ForceReactionLines = []
ForceReactionStartPoints = []
ForceReactionVectors = []
ForceCells = DataTree[object]()
BoundaryLines = []
BoundaryKinds = []
OuterEnvelope = []
Pole = None
LoadLinePoints = []
LoadLineSegments = []
QSegment = None
ChainNodeIDs = []
ChainEdgeIDs = []
MemberIDs = []
LoadNodeIDs = []
ReactionNodeIDs = []
ClosureErrors = []
StitchError = 0.0
PlanarityErrors = []
ForceDimension = 0
FitsOuterEnvelope = False
DiagramPlaneOut = None
Report = "Set Run to True."


if Run:
    if Session is None:
        Report = "Connect an FDSession from FDWholeNetwork."
    else:
        plane_input = globals().get("DiagramPlane")
        if plane_input is None:
            plane_x = None
            plane_y = None
        else:
            plane = _geo(plane_input)
            if not isinstance(plane, rg.Plane) or not plane.IsValid:
                raise ValueError("DiagramPlane must be a valid Rhino Plane.")
            plane_x = [float(plane.XAxis.X), float(plane.XAxis.Y), float(plane.XAxis.Z)]
            plane_y = [float(plane.YAxis.X), float(plane.YAxis.Y), float(plane.YAxis.Z)]

        start_input = globals().get("StartNode")
        start_node = int(start_input) if start_input is not None else None
        tolerance_input = globals().get("Tolerance")
        tolerance = float(tolerance_input) if tolerance_input is not None else 1e-6
        clockwise_input = globals().get("Clockwise")
        clockwise = bool(clockwise_input) if clockwise_input is not None else True

        GraphicSession = graphic_statics.stitch_fd_force_diagram(
            Session,
            plane_xaxis=plane_x,
            plane_yaxis=plane_y,
            start_node=start_node,
            tolerance=tolerance,
            clockwise=clockwise,
        )

        form_points = [_point(value) for value in Session.equilibrium_vertices]
        FormLines = [
            rg.Line(form_points[u], form_points[v])
            for u, v in Session.source_edges
        ]

        force_scale_input = globals().get("ForceScale")
        force_scale = (
            float(force_scale_input) if force_scale_input is not None else 1.0
        )
        if force_scale <= 0.0:
            raise ValueError("ForceScale must be positive.")

        force_origin_input = globals().get("ForceOrigin")
        if force_origin_input is None:
            box = rg.BoundingBox(form_points)
            margin = max(box.Diagonal.Length * 0.15, 1.0)
            display_origin = box.Max + _vector(GraphicSession.plane_xaxis) * margin
        else:
            display_origin = rg.Point3d(_geo(force_origin_input))

        def display_point(value):
            return display_origin + _vector(value) * force_scale

        def display_line(start, end):
            return rg.Line(display_point(start), display_point(end))

        ForceMemberLines = [
            display_line(start, end)
            for start, end in GraphicSession.member_lines
        ]
        MemberIDs = list(range(len(ForceMemberLines)))

        for side in GraphicSession.load_lines:
            line = display_line(side.start, side.end)
            ForceLoadLines.append(line)
            ForceLoadStartPoints.append(line.From)
            ForceLoadVectors.append(line.Direction)
            LoadNodeIDs.append(int(side.node))
        for side in GraphicSession.reaction_lines:
            line = display_line(side.start, side.end)
            ForceReactionLines.append(line)
            ForceReactionStartPoints.append(line.From)
            ForceReactionVectors.append(line.Direction)
            ReactionNodeIDs.append(int(side.node))

        for cell in GraphicSession.cells:
            path = GH_Path(int(cell.node))
            for side in cell.sides:
                ForceCells.Add(display_line(side.start, side.end), path)

        for loop in GraphicSession.boundary_loops:
            for side in loop.sides:
                BoundaryLines.append(display_line(side.start, side.end))
                BoundaryKinds.append(side.kind)

        if len(GraphicSession.boundary_loops) == 1:
            envelope = GraphicSession.boundary_loops[0].simplified_points
            OuterEnvelope = [
                display_line(a, b) for a, b in zip(envelope[:-1], envelope[1:])
            ]

        if GraphicSession.pole is not None:
            Pole = display_point(GraphicSession.pole)
        if GraphicSession.chain_path and len(GraphicSession.boundary_loops) == 1:
            ordered_load_sides = [
                side
                for side in GraphicSession.boundary_loops[0].sides
                if side.kind == "load"
            ]
            if ordered_load_sides:
                LoadLinePoints = [
                    display_point(ordered_load_sides[0].start)
                ] + [
                    display_point(side.end) for side in ordered_load_sides
                ]
                LoadLineSegments = [
                    display_line(side.start, side.end)
                    for side in ordered_load_sides
                ]

        q_node_input = globals().get("QNodeID")
        if q_node_input is not None:
            q_node = int(q_node_input)
            selected = [
                side for side in GraphicSession.load_lines if side.node == q_node
            ]
            if selected:
                QSegment = display_line(selected[0].start, selected[0].end)

        ChainNodeIDs = [int(value) for value in GraphicSession.chain_path]
        ChainEdgeIDs = [int(value) for value in GraphicSession.chain_edges]
        ClosureErrors = [
            float(cell.closure_error) for cell in GraphicSession.cells
        ]
        StitchError = float(GraphicSession.max_glue_error)
        PlanarityErrors = [
            float(GraphicSession.form_planarity_error),
            float(GraphicSession.force_planarity_error),
        ]
        ForceDimension = int(GraphicSession.force_dimension)
        FitsOuterEnvelope = bool(GraphicSession.fits_outer_envelope)
        DiagramPlaneOut = rg.Plane(
            display_origin,
            _vector(GraphicSession.plane_xaxis),
            _vector(GraphicSession.plane_yaxis),
        )

        mode = (
            "serial pole/load-line fan"
            if GraphicSession.chain_path
            else "stitched acyclic reciprocal cells"
        )
        Report = (
            GraphicSession.report
            + "\nGrasshopper display mode: {}"
            + "\nForceScale {:.6g} is display-only."
            + "\nOuterEnvelope is simplified from the real external-force "
            "boundary; it is never fitted around unrelated geometry."
        ).format(mode, force_scale)
        if q_node_input is not None and QSegment is None:
            Report += "\nQNodeID {} has no non-zero applied load.".format(
                int(q_node_input)
            )
