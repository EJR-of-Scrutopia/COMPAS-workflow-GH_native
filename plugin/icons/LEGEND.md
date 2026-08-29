# Component icon legend

These 24 × 24 RGBA PNG icons use short text labels so they remain legible in
the Grasshopper toolbar and on compact components. The fill colour identifies
the component category; the white letters identify the individual component.

## Category palette

| Category | Colour | Purpose |
| --- | --- | --- |
| 01 Inputs | `#126E82` teal | Topology, supports, and loads |
| 02 Form Finding | `#A9462E` orange | FD and TNA configuration and solvers |
| 03 Graphic Statics | `#2F7D6D` green | Reciprocal form, force, and thrust diagrams |
| 03 Diagnostics | `#765300` ochre | Validation and diagnostic results |
| 04 Visualisation | `#624494` violet | Diagram styling and preview payloads |
| 01 Model | `#126E82` teal | Native topology, support, load, and problem contracts |
| 05 Visualisation | `#624494` violet | Native result previews and diagram display |
| 90 Query | `#4E5968` slate | Backend inspection and result extraction |

## Component mapping

| Label | Component key | Component name | Icon file |
| --- | --- | --- | --- |
| NW | `network` | Network | `network.png` |
| SS | `support_set` | Support Set | `support_set.png` |
| LC | `load_case` | Load Case | `load_case.png` |
| FS | `fd_settings` | FD Settings | `fd_settings.png` |
| TC | `tna_control` | TNA Control | `tna_control.png` |
| FD | `fd_solve` | FD Solve | `fd_solve.png` |
| TN | `tna_solve` | TNA Solve | `tna_solve.png` |
| VA | `validate` | Validate | `validate.png` |
| DS | `diagram_style` | Diagram Style | `diagram_style.png` |
| PV | `preview_payload` | Preview Payload | `preview_payload.png` |
| EP | `equilibrium_problem` | Equilibrium Problem | `equilibrium_problem.png` |
| BH | `backend_health` | Backend Health | `backend_health.png` |
| RB | `result_breakdown` | Result Breakdown | `result_breakdown.png` |
| PV | `equilibrium_preview` | Equilibrium Preview | `equilibrium_preview.png` |
| TR | `tna_reciprocal` | TNA Reciprocal | `tna_reciprocal.png` |
| DD | `graphic_diagram_display` | Graphic Diagram Display | `graphic_diagram_display.png` |
| TG | `tna_geometry` | TNA Geometry | `tna_geometry.png` |
| TM | `tna_members` | TNA Members | `tna_members.png` |
| TA | `tna_actions` | TNA Actions | `tna_actions.png` |
| SK | `skin` | Skin | `skin.png` |

## Regeneration and validation

The generator has no third-party dependencies and bundles its own bitmap
glyphs, making the rendering independent of installed fonts:

```powershell
python plugin/icons/generate_icons.py
python plugin/icons/generate_icons.py --check
```

The generation command checks that every component in `plugin/components.toml`
has exactly one mapping and that its category agrees with the manifest. Both
commands validate that every image is a 24 × 24, 8-bit RGBA PNG.

`generate_icons.py` OWNS every file `icon-map.json` lists: a plain run
rewrites each one from that map's label and category fill. The mould family
(`stress_analysis`, `column_finder`, `mould_animate`, `diagnose`, `skin`) is
drawn flat rather than as a rounded badge and does not come from this
generator; `diagnose.png` and `skin.png` have scripts of their own beside it
(`make_diagnose_icon.py`, `make_skin_icon.py`). Those keys are therefore
deliberately absent from `icon-map.json`: listing one would hand its PNG to
two generators, and the next plain run would overwrite it.
