"""Independent, lazily loaded COMPAS workflows for the tree-forest project.

Keeping imports lazy is important: a dedicated FEA/IFC environment can use the
neutral structural handoff without also installing TNA, AGS and FD.
"""

import importlib


_EXPORTS = {
    "TNAError": (".tna", "TNAError"),
    "TNAInputError": (".tna", "TNAInputError"),
    "TNAProblem": (".tna", "TNAProblem"),
    "TNASession": (".tna", "TNASession"),
    "TNASolveError": (".tna", "TNASolveError"),
    "TNATopologyError": (".tna", "TNATopologyError"),
    "register_tna_pattern": (".tna", "register_tna_pattern"),
    "solve_tna_pattern": (".tna", "solve_tna_pattern"),
    "solve_tna_problem": (".tna", "solve_tna_problem"),
    "AGSRegistrationError": (".ags", "AGSRegistrationError"),
    "AGSResult": (".ags", "AGSResult"),
    "solve_planar_graphic_statics": (".ags", "solve_planar_graphic_statics"),
    "FDInputError": (".fd", "FDInputError"),
    "FDProblem": (".fd", "FDProblem"),
    "FDSession": (".fd", "FDSession"),
    "FDSolveError": (".fd", "FDSolveError"),
    "JointForcePolygon": (".fd", "JointForcePolygon"),
    "joint_force_polygons": (".fd", "joint_force_polygons"),
    "register_fd_network": (".fd", "register_fd_network"),
    "solve_fd_network": (".fd", "solve_fd_network"),
    "solve_fd_problem": (".fd", "solve_fd_problem"),
    "BoundaryLoop": (".graphic_statics", "BoundaryLoop"),
    "ForceCell": (".graphic_statics", "ForceCell"),
    "ForceSide": (".graphic_statics", "ForceSide"),
    "GraphicStaticsError": (".graphic_statics", "GraphicStaticsError"),
    "StitchedForceDiagram": (
        ".graphic_statics",
        "StitchedForceDiagram",
    ),
    "funicular_force_diagram": (
        ".graphic_statics",
        "funicular_force_diagram",
    ),
    "stitch_fd_force_diagram": (
        ".graphic_statics",
        "stitch_fd_force_diagram",
    ),
    "MissingAnalysisBackendError": (
        ".structural",
        "MissingAnalysisBackendError",
    ),
    "NodalVector": (".structural", "NodalVector"),
    "SourceMemberMapping": (".structural", "SourceMemberMapping"),
    "SourceVertexMapping": (".structural", "SourceVertexMapping"),
    "StructuralAnalysisCase": (".structural", "StructuralAnalysisCase"),
    "StructuralBundle": (".structural", "StructuralBundle"),
    "StructuralHandoffError": (".structural", "StructuralHandoffError"),
    "analysis_case_from_fd_session": (
        ".structural",
        "analysis_case_from_fd_session",
    ),
    "analysis_case_from_tna_session": (
        ".structural",
        "analysis_case_from_tna_session",
    ),
    "assess_fea_readiness": (".structural", "assess_fea_readiness"),
    "build_compas_model": (".structural", "build_compas_model"),
    "build_ifc_model": (".structural", "build_ifc_model"),
    "compas_fea2_status": (".structural", "compas_fea2_status"),
    "make_ifc_formulation": (".structural", "make_ifc_formulation"),
    "make_structural_bundle": (".structural", "make_structural_bundle"),
    "structural_bundle_from_fd_session": (
        ".structural",
        "structural_bundle_from_fd_session",
    ),
    "structural_bundle_from_tna_session": (
        ".structural",
        "structural_bundle_from_tna_session",
    ),
    "tna": (".tna", None),
    "ags": (".ags", None),
    "fd": (".fd", None),
    "graphic_statics": (".graphic_statics", None),
    "structural": (".structural", None),
}


def __getattr__(name):
    """Load a requested workflow without importing unrelated dependencies."""

    if name not in _EXPORTS:
        raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
    module_name, attribute = _EXPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
