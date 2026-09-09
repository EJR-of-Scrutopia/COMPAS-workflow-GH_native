"""Megaplants via the LEVEL exporter path: spawn each skeletal tree as an
actor and export the selection. Direct asset export of these Nanite
assembly skeletal meshes crashes the glTF exporter; the level path runs a
different converter. One species variant first would be prudent, but the
whole capped list costs the same run and each export is wrapped so one
failure cannot take the batch down (a native crash still can -- the
report file is written incrementally so a crash names its culprit)."""
import json
import os
import re
import traceback
from collections import defaultdict

import unreal

OUT = os.environ.get("VAULTED_EXPORT_OUT", r"C:\ue_export_out")
PER_SPECIES = int(os.environ.get("VAULTED_PER_SPECIES", "2"))
os.makedirs(OUT, exist_ok=True)
report = {"exported": [], "errors": []}
REPORT_PATH = os.path.join(OUT, "report-actor.json")


def flush():
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1)


registry = unreal.AssetRegistryHelpers.get_asset_registry()
try:
    registry.scan_paths_synchronous(["/Game/Megaplant_Library"],
                                    force_rescan=True)
    registry.wait_for_completion()
except Exception:
    pass

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
        continue
    species[str(data.package_name).split("/")[2]].append(data)

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


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
    return opts


world = unreal.EditorLevelLibrary.get_editor_world()
for folder, rows in sorted(species.items()):
    rows.sort(key=lambda d: str(d.asset_name))
    for data in rows[:PER_SPECIES]:
        name = str(data.asset_name)
        report["errors"].append({"asset": name, "note": "attempting"})
        flush()                      # a native crash names its culprit
        actor = None
        try:
            mesh = data.get_asset()
            actor = subsystem.spawn_actor_from_object(
                mesh, unreal.Vector(0, 0, 0))
            target = os.path.join(OUT, name + ".glb")
            ok = unreal.GLTFExporter.export_to_gltf(
                world, target, options(), {actor})
            size = os.path.getsize(target) if os.path.isfile(target) else 0
            report["errors"].pop()   # attempt survived
            report["exported"].append({"asset": name, "ok": bool(ok),
                                       "bytes": size})
            unreal.log("VAULTED actor {} ok {} {} bytes".format(
                name, ok, size))
        except Exception:
            report["errors"][-1] = {"asset": name,
                                    "trace": traceback.format_exc()}
        finally:
            if actor:
                try:
                    subsystem.destroy_actor(actor)
                except Exception:
                    pass
        flush()

flush()
unreal.log("VAULTED actor pass done: {} exported".format(
    len(report["exported"])))
