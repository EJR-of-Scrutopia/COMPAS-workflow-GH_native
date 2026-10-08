"""Inventory-only: list every asset (name, class, path) under the roots.
No subsystems, no get_asset(), nothing that can detonate on Nanite."""
import json
import os

import unreal

ROOTS = ["/" + r.strip().lstrip("/") for r in os.environ.get(
    "VAULTED_EXPORT_ROOTS", "Game").split(",") if r.strip()]
OUT = os.environ.get("VAULTED_EXPORT_OUT", r"C:\ue_export_out")
os.makedirs(OUT, exist_ok=True)

registry = unreal.AssetRegistryHelpers.get_asset_registry()
try:
    registry.scan_paths_synchronous(ROOTS, force_rescan=True)
except Exception:
    pass
try:
    registry.wait_for_completion()
except Exception:
    pass

rows = []
for root in ROOTS:
    for data in registry.get_assets_by_path(unreal.Name(root), recursive=True):
        try:
            klass = str(data.asset_class_path.asset_name)
        except Exception:
            klass = str(data.asset_class)
        rows.append({"name": str(data.asset_name), "class": klass,
                     "path": str(data.package_name)})

with open(os.path.join(OUT, "inventory.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=1)
unreal.log("VAULTED inventory: {} assets".format(len(rows)))
