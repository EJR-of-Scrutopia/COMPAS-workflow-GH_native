# Component icon legend

These 24 × 24 RGBA PNG icons use short text labels so they remain legible in
the Grasshopper toolbar and on compact components. The fill colour identifies
the component category; the white letters identify the individual component.

## Category palette

| Category | Colour | Purpose |
| --- | --- | --- |
| 01 Inputs | `#126E82` teal | Topology, supports, and loads |
| 02 Form Finding | `#A9462E` orange | FD and TNA configuration and solvers |
| 03 Diagnostics | `#765300` ochre | Validation and diagnostic results |
| 04 Visualisation | `#624494` violet | Diagram styling and preview payloads |

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
