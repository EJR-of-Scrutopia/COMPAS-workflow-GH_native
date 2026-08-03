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

# FDVisualize - Rhino 8 Grasshopper Python 3 component.
#
# Inputs:
#   Session        object     Item   FDSession from FDWholeNetwork
#   JointIDs       int        List   empty = all non-support nodes
#   DiagramOrigin  Point3d    Item   empty = automatically placed beside form
#   LayoutVector   Vector3d   Item   direction between local polygons
#   DiagramSpacing float      Item
#   ForceScale     float      Item   model units per force unit
#   VectorScale    float      Item   model units per load/reaction unit
#   Run            bool       Item
#
# Outputs:
#   FormLines, MemberForces, ForceDensities, ForceNormalised, ForceColours,
#   LoadPoints, LoadVectors, ReactionPoints, ReactionVectors,
#   ForceMemberLines, ForceLoadLines, ForceReactionLines, ClosureErrors, Report
#
# ForceMember/Load/Reaction outputs are DataTrees with one branch per joint.
# A degree-two loaded node produces a triangle because it has exactly two member
# vectors plus one external load vector. These are local polygons, not TNA/AGS.

import importlib
import sys
from System.Drawing import Color

import numpy as np
import Rhino.Geometry as rg
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tree_forest_compas import fd  # noqa: E402

importlib.reload(fd)


def _geo(value):
    return value.Value if hasattr(value, "Value") else value


def _point(values):
    return rg.Point3d(float(values[0]), float(values[1]), float(values[2]))


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
MemberForces = []
ForceDensities = []
ForceNormalised = []
ForceColours = []
LoadPoints = []
LoadVectors = []
ReactionPoints = []
ReactionVectors = []
ForceMemberLines = DataTree[object]()
ForceLoadLines = DataTree[object]()
ForceReactionLines = DataTree[object]()
ClosureErrors = []
Report = "Set Run to True."


if Run:
    if Session is None:
        Report = "Connect an FDSession from FDWholeNetwork."
    else:
        xyz = np.asarray(Session.equilibrium_vertices, dtype=float)
        points = [_point(value) for value in xyz]
        FormLines = [
            rg.Line(points[u], points[v]) for u, v in Session.source_edges
        ]
        MemberForces = [float(value) for value in Session.member_forces]
        ForceDensities = [float(value) for value in Session.force_densities]
        maximum_force = max((abs(value) for value in MemberForces), default=0.0)
        ForceNormalised = [
            abs(value) / maximum_force if maximum_force > 0.0 else 0.0
            for value in MemberForces
        ]
        ForceColours = [_colour(value, maximum_force) for value in MemberForces]

        vector_scale = float(VectorScale) if VectorScale is not None else 1.0
        if vector_scale <= 0.0:
            raise ValueError("VectorScale must be positive.")
        for index, vector in enumerate(Session.loads):
            if np.linalg.norm(vector) > 1e-12:
                LoadPoints.append(points[index])
                LoadVectors.append(rg.Vector3d(*vector) * vector_scale)
        for index in Session.fixed:
            vector = Session.support_reactions[index]
            if np.linalg.norm(vector) > 1e-12:
                ReactionPoints.append(points[index])
                ReactionVectors.append(rg.Vector3d(*vector) * vector_scale)

        requested = [int(value) for value in JointIDs] if JointIDs else []
        selected = (
            requested
            if requested
            else [
                index
                for index in range(len(points))
                if index not in set(Session.fixed)
            ]
        )
        force_scale = float(ForceScale) if ForceScale is not None else 1.0
        spacing = float(DiagramSpacing) if DiagramSpacing is not None else 2.0
        if force_scale <= 0.0 or spacing <= 0.0:
            raise ValueError("ForceScale and DiagramSpacing must be positive.")

        if DiagramOrigin is None:
            box = rg.BoundingBox(points)
            base = box.Max + rg.Vector3d(max(box.Diagonal.Length * 0.15, 1.0), 0, 0)
        else:
            base = rg.Point3d(_geo(DiagramOrigin))

        if LayoutVector is None:
            layout = rg.Vector3d(0.0, -1.0, 0.0)
        else:
            layout = rg.Vector3d(_geo(LayoutVector))
        if not layout.Unitize():
            layout = rg.Vector3d(0.0, -1.0, 0.0)

        polygons = fd.joint_force_polygons(
            Session,
            nodes=selected,
            scale=force_scale,
        )
        for branch_index, polygon in enumerate(polygons):
            path = GH_Path(int(polygon.node))
            origin = base + layout * (branch_index * spacing)
            polygon_points = [
                origin + rg.Vector3d(*coordinates)
                for coordinates in polygon.points
            ]
            degree = len(polygon.member_vectors)
            for index in range(degree):
                ForceMemberLines.Add(
                    rg.Line(polygon_points[index], polygon_points[index + 1]),
                    path,
                )
            if np.linalg.norm(polygon.load_vector) > 1e-12:
                ForceLoadLines.Add(
                    rg.Line(
                        polygon_points[degree],
                        polygon_points[degree + 1],
                    ),
                    path,
                )
            if np.linalg.norm(polygon.reaction_vector) > 1e-12:
                ForceReactionLines.Add(
                    rg.Line(
                        polygon_points[degree + 1],
                        polygon_points[degree + 2],
                    ),
                    path,
                )
            ClosureErrors.append(float(polygon.closure_error))

        Report = (
            Session.report
            + "\nLocal joint force polygons: {}"
            + "\nMaximum polygon closure error: {:.3e}"
            + "\nDegree-two loaded joints appear as triangles by definition; "
            "these are local equilibrium polygons, not a global reciprocal."
            + "\nConnect the same Session to FDGlobalGraphicStatics for the "
            "stitched pole/load-line or tree-cell diagram."
        ).format(
            len(polygons),
            max(ClosureErrors) if ClosureErrors else 0.0,
        )
