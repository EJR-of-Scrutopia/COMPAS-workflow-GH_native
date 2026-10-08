"""Statics only from tree_assets: Megascans clusters + the high-poly
tree. No subsystems, no skeletals, incremental report so a native crash
names its culprit."""
import json
import os
import traceback

import unreal

OUT = os.environ.get("VAULTED_EXPORT_OUT", r"C:\ue_export_out")
os.makedirs(OUT, exist_ok=True)
report = {"exported": [], "errors": []}
REPORT_PATH = os.path.join(OUT, "report-statics.json")


def flush():
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)


registry = unreal.AssetRegistryHelpers.get_asset_registry()
try:
    registry.scan_paths_synchronous(
        ["/Game/Fab/Megascans", "/Game/HighPoly_Tree_Model"],
        force_rescan=True)
    registry.wait_for_completion()
except Exception:
    pass


def options():
    opts = unreal.GLTFExportOptions()
    for name, value in {
        "export_uniform_scale": 0.01,
        "export_preview_mesh": False,
        "export_vertex_colors": False,
        "texture_image_format": unreal.GLTFTextureImageFormat.PNG,
    }.items():
        try:
            opts.set_editor_property(name, value)
        except Exception:
            pass
    for bake in ("USE_MESH_DATA", "SIMPLE"):
        try:
            opts.set_editor_property("bake_material_inputs",
                getattr(unreal.GLTFMaterialBakeMode, bake))
            break
        except Exception:
            continue
    return opts


for root in ("/Game/Fab/Megascans", "/Game/HighPoly_Tree_Model"):
    for data in registry.get_assets_by_path(unreal.Name(root), recursive=True):
        try:
            klass = str(data.asset_class_path.asset_name)
        except Exception:
            klass = str(data.asset_class)
        if klass != "StaticMesh":
            continue
        name = str(data.asset_name)
        report["errors"].append({"asset": name, "note": "attempting"})
        flush()
        try:
            mesh = data.get_asset()
            target = os.path.join(OUT, name + ".glb")
            ok = unreal.GLTFExporter.export_to_gltf(
                mesh, target, options(), set())
            size = os.path.getsize(target) if os.path.isfile(target) else 0
            report["errors"].pop()
            report["exported"].append({"asset": name, "ok": bool(ok),
                                       "bytes": size})
            unreal.log("VAULTED static {} ok {} {}".format(name, ok, size))
        except Exception:
            report["errors"][-1] = {"asset": name,
                                    "trace": traceback.format_exc()}
        flush()

flush()
unreal.log("VAULTED statics done: {}".format(len(report["exported"])))
