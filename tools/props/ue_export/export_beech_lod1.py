"""Export the six big beeches at their authored LOD1 by raising min_lod.

default_level_of_detail on GLTFExportOptions is ignored for direct asset
export (measured: LOD0's millions of triangles came out regardless), but
the exporter honours the mesh's own minimum LOD: raise min_lod to 1,
export, put it back.
"""
import json
import os

import unreal

OUT = os.environ.get("VAULTED_EXPORT_OUT", r"C:\ue_export_out")
NAMES = [n.strip() for n in os.environ.get("VAULTED_ONLY", "").split(",")
         if n.strip()]
os.makedirs(OUT, exist_ok=True)
report = []

registry = unreal.AssetRegistryHelpers.get_asset_registry()
try:
    registry.scan_paths_synchronous(["/Game/EuropeanBeech"], force_rescan=True)
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


for data in registry.get_assets_by_path(
        unreal.Name("/Game/EuropeanBeech"), recursive=True):
    name = str(data.asset_name)
    if name not in NAMES:
        continue
    mesh = data.get_asset()
    # Overwrite LOD0 with the mesh's own authored LOD1, in memory only:
    # nothing saves, so the project keeps its original.
    try:
        unreal.EditorStaticMeshLibrary.set_lod_from_static_mesh(
            mesh, 0, mesh, 1, True)
    except Exception as error:
        report.append({"asset": name, "lodSwapError": str(error)})
    target = os.path.join(OUT, name + ".glb")
    ok = unreal.GLTFExporter.export_to_gltf(mesh, target, options(), set())
    size = os.path.getsize(target) if os.path.isfile(target) else 0
    report.append({"asset": name, "ok": bool(ok), "bytes": size})
    unreal.log("VAULTED lod1 {} ok {} {} bytes".format(name, ok, size))

with open(os.path.join(OUT, "report-lod1.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=1)
unreal.log("VAULTED lod1 pass done")
