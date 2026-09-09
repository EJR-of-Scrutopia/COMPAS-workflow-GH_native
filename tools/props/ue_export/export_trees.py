"""Batch-export every StaticMesh under the given content roots to GLB.

Runs inside UnrealEditor-Cmd via -ExecutePythonScript. Writes one .glb per
mesh with baked materials, plus a JSON report of everything it saw --
including asset classes it skipped, so procedural assets show their hand.

Configured by environment variables so one script serves both projects:
  VAULTED_EXPORT_ROOTS   comma-separated content paths (/Game/...)
  VAULTED_EXPORT_OUT     output directory
"""
import json
import os
import traceback

import unreal

# Roots arrive WITHOUT the leading slash (Git Bash rewrites /Game/... into
# its own install path when it exports the variable) and are restored here.
ROOTS = ["/" + r.strip().lstrip("/") for r in os.environ.get(
    "VAULTED_EXPORT_ROOTS", "Game/EuropeanBeech").split(",") if r.strip()]
OUT = os.environ.get("VAULTED_EXPORT_OUT", r"C:\ue_export_out")
# A forced LOD sidesteps both the LOD-probe API (unreliable across
# versions) and the downstream simplifier (which eats branches): the
# authored LOD is the artist's own decimation.
FORCE_LOD = os.environ.get("VAULTED_FORCE_LOD")
ONLY = {n.strip() for n in os.environ.get(
    "VAULTED_ONLY", "").split(",") if n.strip()}
# The most detail the studio's vegetation budget keeps; an authored LOD at
# or under this passes through the pipeline unsimplified.
TRIANGLE_CEILING = 260000

os.makedirs(OUT, exist_ok=True)
report = {"roots": ROOTS, "exported": [], "skipped": [], "errors": []}

registry = unreal.AssetRegistryHelpers.get_asset_registry()
# A commandlet's registry can still be scanning: make it certain.
try:
    registry.scan_paths_synchronous(ROOTS, force_rescan=True)
except Exception:
    pass
try:
    registry.wait_for_completion()
except Exception:
    pass

try:
    mesh_tools = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
except Exception:
    mesh_tools = None


def triangle_count(mesh, lod):
    for call in ("get_number_triangles",):
        try:
            return mesh_tools.get_number_triangles(mesh, lod)
        except Exception:
            pass
    return None


def pick_lod(mesh):
    """The most detailed authored LOD that fits the ceiling."""
    try:
        lods = mesh_tools.get_lod_count(mesh) if mesh_tools else 1
    except Exception:
        lods = 1
    counts = []
    for index in range(lods):
        counts.append(triangle_count(mesh, index))
    for index, count in enumerate(counts):
        if count is None or count <= TRIANGLE_CEILING:
            return index, counts
    return max(0, lods - 1), counts


def export_options(lod):
    options = unreal.GLTFExportOptions()
    wanted = {
        "default_level_of_detail": lod,
        "export_uniform_scale": 0.01,          # centimetres to metres
        "export_preview_mesh": False,
        "export_vertex_colors": False,
        "export_level_sequences": False,
        "export_animation_sequences": False,
        "texture_image_format": unreal.GLTFTextureImageFormat.PNG,
    }
    # Bake material inputs so the layered Megascans materials become plain
    # textures; enum names shifted across versions, so try the variants.
    for name, value in wanted.items():
        try:
            options.set_editor_property(name, value)
        except Exception as error:
            report["errors"].append({"option": name, "error": str(error)})
    for bake_name in ("USE_MESH_DATA", "SIMPLE"):
        try:
            options.set_editor_property(
                "bake_material_inputs",
                getattr(unreal.GLTFMaterialBakeMode, bake_name))
            break
        except Exception:
            continue
    for size_name in ("POT_2048", "POT_1024"):
        try:
            options.set_editor_property(
                "default_material_bake_size",
                getattr(unreal.GLTFMaterialBakeSize, size_name))
            break
        except Exception:
            continue
    return options


for root in ROOTS:
    assets = registry.get_assets_by_path(unreal.Name(root), recursive=True)
    for data in assets:
        try:
            klass = str(data.asset_class_path.asset_name)
        except Exception:
            klass = str(data.asset_class)
        name = str(data.asset_name)
        if klass != "StaticMesh":
            report["skipped"].append({"asset": name, "class": klass,
                                      "path": str(data.package_name)})
            continue
        if ONLY and name not in ONLY:
            continue
        try:
            mesh = data.get_asset()
            if FORCE_LOD is not None:
                lod, counts = int(FORCE_LOD), []
            else:
                lod, counts = pick_lod(mesh)
            target = os.path.join(OUT, name + ".glb")
            options = export_options(lod)
            ok = unreal.GLTFExporter.export_to_gltf(
                mesh, target, options, set())
            size = os.path.getsize(target) if os.path.isfile(target) else 0
            report["exported"].append({
                "asset": name, "lod": lod, "lodTriangles": counts,
                "ok": bool(ok), "bytes": size})
            unreal.log("VAULTED exported {} lod {} ok {}".format(name, lod, ok))
        except Exception:
            report["errors"].append({"asset": name,
                                     "trace": traceback.format_exc()})

with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=1)
unreal.log("VAULTED export finished: {} exported, {} skipped, {} errors".format(
    len(report["exported"]), len(report["skipped"]), len(report["errors"])))
