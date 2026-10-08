"""Export the tree_assets project's usable models to GLB.

The Megaplant library assembles its trees as SKELETAL meshes (SK_*); the
static meshes beside them are loose branch parts. So: skeletal meshes for
the trees (bind pose IS the tree, the ingest strips the skin), capped at
four healthy variants per species, plus the handful of true static
meshes elsewhere (Megascans clusters, the high-poly tree). No LOD-probe
subsystems anywhere: a Nanite mesh detonates them on 5.7.
"""
import json
import os
import re
import traceback
from collections import defaultdict

import unreal

OUT = os.environ.get("VAULTED_EXPORT_OUT", r"C:\ue_export_out")
PER_SPECIES = int(os.environ.get("VAULTED_PER_SPECIES", "4"))
os.makedirs(OUT, exist_ok=True)
report = {"exported": [], "skipped": [], "errors": []}

registry = unreal.AssetRegistryHelpers.get_asset_registry()
try:
    registry.scan_paths_synchronous(
        ["/Game/Megaplant_Library", "/Game/Fab/Megascans",
         "/Game/HighPoly_Tree_Model"], force_rescan=True)
    registry.wait_for_completion()
except Exception:
    pass


def options():
    opts = unreal.GLTFExportOptions()
    for name, value in {
        "export_uniform_scale": 0.01,
        "export_preview_mesh": False,
        "export_vertex_colors": False,
        "export_level_sequences": False,
        "export_animation_sequences": False,
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
    for size in ("POT_2048", "POT_1024"):
        try:
            opts.set_editor_property("default_material_bake_size",
                getattr(unreal.GLTFMaterialBakeSize, size))
            break
        except Exception:
            continue
    return opts


def export(asset_data, name):
    try:
        asset = asset_data.get_asset()
        target = os.path.join(OUT, name + ".glb")
        ok = unreal.GLTFExporter.export_to_gltf(asset, target, options(), set())
        size = os.path.getsize(target) if os.path.isfile(target) else 0
        report["exported"].append({"asset": name, "ok": bool(ok), "bytes": size})
        unreal.log("VAULTED exported {} ok {} {} bytes".format(name, ok, size))
    except Exception:
        report["errors"].append({"asset": name, "trace": traceback.format_exc()})


# 1. Megaplant skeletal trees, curated: healthy variants only, a cap per
# species, dead ones excluded (their bare silhouettes never read well at
# vault scale and the studio already has dead trunks).
species = defaultdict(list)
for data in registry.get_assets_by_path(
        unreal.Name("/Game/Megaplant_Library"), recursive=True):
    try:
        klass = str(data.asset_class_path.asset_name)
    except Exception:
        klass = str(data.asset_class)
    name = str(data.asset_name)
    if klass != "SkeletalMesh" or not name.startswith("SK_"):
        continue
    if re.search(r"dead|decay|sparse", name, re.I):
        report["skipped"].append({"asset": name, "why": "dead/decaying"})
        continue
    folder = str(data.package_name).split("/")[2]
    species[folder].append(data)

for folder, rows in sorted(species.items()):
    rows.sort(key=lambda d: str(d.asset_name))
    for data in rows[:PER_SPECIES]:
        export(data, str(data.asset_name))
    for data in rows[PER_SPECIES:]:
        report["skipped"].append({"asset": str(data.asset_name),
                                  "why": "over per-species cap"})

# 2. True static meshes: Megascans clusters and the high-poly tree.
for root in ("/Game/Fab/Megascans", "/Game/HighPoly_Tree_Model"):
    for data in registry.get_assets_by_path(unreal.Name(root), recursive=True):
        try:
            klass = str(data.asset_class_path.asset_name)
        except Exception:
            klass = str(data.asset_class)
        if klass != "StaticMesh":
            continue
        export(data, str(data.asset_name))

with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=1)
unreal.log("VAULTED megaplants finished: {} exported, {} errors".format(
    len(report["exported"]), len(report["errors"])))
