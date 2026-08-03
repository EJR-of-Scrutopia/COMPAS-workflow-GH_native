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

# StructuralHandoff - Rhino 8 Grasshopper Python 3 component.
#
# Inputs:
#   Session       object   Item   solved TNASession or FDSession
#   LengthUnit    str      Item   "m" default
#   ForceUnit     str      Item   "kN" default
#   LoadCase      str      Item   "equilibrium" default
#   MemberRoles   object   List   optional source-ID mapping or active alignment
#   Width         float    Item   explicit compas_model preview width
#   Depth         float    Item   explicit preview depth; Width if empty
#   BuildModel    bool     Item   create in-memory compas_model preview
#   BuildIFC      bool     Item   create in-memory compas_ifc BIM
#   IFCBodies     bool     Item   add explicit rectangular bodies to IFC
#   Run           bool     Item
#
# Outputs:
#   SourceSession, AnalysisCase, SourceMappings, Bundle, ModelHandoff, CompasModel,
#   IFCFormulation, IFCModelHandoff, IFCModel, MemberLines, AxialForces,
#   ForceStates, SupportPoints, FEAAvailable, FEAMissing, Report
#
# No IFC file is written. Review IFCFormulation before explicitly saving IFCModel.
# This component does not claim that form-finding is a full structural analysis.

import importlib
import sys

import Rhino.Geometry as rg


SRC_DIR = r"C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src"
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tree_forest_compas import structural  # noqa: E402

importlib.reload(structural)


SourceSession = None
AnalysisCase = None
SourceMappings = []
Bundle = None
ModelHandoff = None
CompasModel = None
IFCFormulation = None
IFCModelHandoff = None
IFCModel = None
MemberLines = []
AxialForces = []
ForceStates = []
SupportPoints = []
FEAAvailable = False
FEAMissing = []
Report = "Set Run to True."


if Run:
    if Session is None:
        Report = "Connect a solved TNASession or FDSession."
    else:
        SourceSession = Session
        length_unit = str(LengthUnit or "m")
        force_unit = str(ForceUnit or "kN")
        load_case = str(globals().get("LoadCase", None) or "equilibrium")
        role_input = globals().get("MemberRoles", None)
        if isinstance(role_input, (list, tuple)):
            if not role_input:
                role_input = None
            elif len(role_input) == 1:
                role_input = role_input[0]

        if hasattr(Session, "edge_forces") and hasattr(Session, "form"):
            AnalysisCase = structural.analysis_case_from_tna_session(
                Session,
                load_case=load_case,
                member_roles=role_input,
                length_unit=length_unit,
                force_unit=force_unit,
            )
        elif hasattr(Session, "member_forces") and hasattr(
            Session, "equilibrium_vertices"
        ):
            AnalysisCase = structural.analysis_case_from_fd_session(
                Session,
                load_case=load_case,
                member_roles=role_input,
                length_unit=length_unit,
                force_unit=force_unit,
            )
        else:
            raise TypeError(
                "Session is neither the TNASession nor FDSession contract."
            )
        Bundle = AnalysisCase.bundle
        SourceMappings = [
            "{}:{} -> {} -> {} [{}; {}]".format(
                mapping.source_id,
                mapping.source_edge,
                mapping.solver_edge,
                mapping.bundle_member_index,
                mapping.status,
                mapping.role,
            )
            for mapping in AnalysisCase.source_member_mappings
        ]

        width = float(Width) if Width is not None else 0.1
        depth = float(Depth) if Depth is not None else width
        if BuildModel:
            ModelHandoff = structural.build_compas_model(
                Bundle,
                width=width,
                depth=depth,
            )
            CompasModel = ModelHandoff.model

        IFCFormulation = structural.make_ifc_formulation(Bundle)
        if BuildIFC:
            body_section = (width, depth) if IFCBodies else None
            IFCModelHandoff = structural.build_ifc_model(
                IFCFormulation,
                body_section=body_section,
            )
            IFCModel = IFCModelHandoff.model

        MemberLines = [
            rg.Line(rg.Point3d(*member.start), rg.Point3d(*member.end))
            for member in Bundle.members
        ]
        AxialForces = [float(member.axial_force) for member in Bundle.members]
        ForceStates = [member.force_state for member in Bundle.members]
        node_by_key = {node.key: node for node in Bundle.nodes}
        SupportPoints = [
            rg.Point3d(*node_by_key[key].xyz) for key in Bundle.support_keys
        ]

        readiness = structural.assess_fea_readiness(AnalysisCase)
        FEAAvailable = bool(readiness.backend.available)
        FEAMissing = list(readiness.missing_inputs)
        reports = [
            AnalysisCase.report,
            Bundle.report,
            IFCFormulation.report,
            readiness.report,
        ]
        if ModelHandoff is not None:
            reports.append(ModelHandoff.report)
        if IFCModelHandoff is not None:
            reports.append(IFCModelHandoff.report)
        Report = "\n\n".join(reports)
