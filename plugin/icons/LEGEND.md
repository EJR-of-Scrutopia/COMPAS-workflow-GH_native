# Component icon legend

These 24 x 24 RGBA PNG icons use short text labels so they remain legible in
the Grasshopper toolbar and on compact components. The fill colour is the
panel the component sits under; the white letters name the component.

One generator draws every one of them. `generate_icons.py` reads
`icon-map.json` and rewrites each file from that map's label and category
fill, and the smoke harness checks the map back against the assembly: every
component's key has exactly one entry, its category is the panel the
component actually registers under, and the badge's own pixels carry that
category's fill.

## Panels

| Panel | Colour | Holds |
| --- | --- | --- |
| 01 Model | `#126E82` teal | Pattern, Supports, Loads |
| 02 Solve | `#A9462E` orange | TNA Relax, TNA Solve, TNA Solve Algebraic, FD Solve |
| 03 Mould | `#2855AF` blue | Columns, Animate |
| 04 Read | `#2F7D6D` green | Deconstruct, Forces, Fit, Supports, Diagnose, Frame, Style, Display |
| 05 Deliver | `#765300` ochre | Export, Import Pieces, Skin |
| 90 System | `#4E5968` slate | Backend Health |

## The twenty-one components

| Label | Component key | Component | Panel |
| --- | --- | --- | --- |
| PA | `tna_pattern` | Pattern | 01 Model |
| SU | `tna_supports` | Supports | 01 Model |
| LO | `load_case` | Loads | 01 Model |
| RX | `tna_relax` | TNA Relax | 02 Solve |
| TS | `tna_solve` | TNA Solve | 02 Solve |
| TA | `tna_solve_algebraic` | TNA Solve Algebraic | 02 Solve |
| FD | `fd_solve` | FD Solve | 02 Solve |
| CO | `column_finder` | Columns | 03 Mould |
| AN | `mould_animate` | Animate | 03 Mould |
| DE | `result_breakdown` | Deconstruct | 04 Read |
| FO | `forces` | Forces | 04 Read |
| FI | `fit` | Fit | 04 Read |
| SP | `supports` | Supports | 04 Read |
| DG | `diagnose` | Diagnose | 04 Read |
| FR | `frame` | Frame | 04 Read |
| ST | `diagram_style` | Style | 04 Read |
| DI | `graphic_diagram_display` | Display | 04 Read |
| EX | `export` | Export | 05 Deliver |
| IP | `import_pieces` | Import Pieces | 05 Deliver |
| SK | `skin` | Skin | 05 Deliver |
| BH | `backend_health` | Backend Health | 90 System |

Four keys (`load_case`, `tna_solve`, `fd_solve`, `diagram_style`) are also in
the legacy `components` list, because the script-backed v0.1 plugin under
`plugin/native` loads those same files by those same names. One PNG, and the
native entry owns its pixels: it is generated last, and the panel colour is
the one that has to be right on the toolbar being built.

## The legacy v0.1 set

`icon-map.json` also carries the ten `components` entries of the
script-backed plugin, checked against `plugin/components.toml` exactly as
before: the same keys, the same subcategories, the categories `01 Inputs`,
`02 Form Finding`, `03 Diagnostics` and `04 Visualisation`. Nothing in this
plugin reads them.

## Regeneration and validation

The generator has no third-party dependencies and bundles its own bitmap
glyphs, making the rendering independent of installed fonts:

```powershell
python plugin/icons/generate_icons.py
python plugin/icons/generate_icons.py --check
```

A plain run rewrites every file the map lists. Both commands validate that
every image is a 24 x 24, 8-bit RGBA PNG, that every label is two or three
letters the bundled alphabet holds, and that the legacy list still covers
`plugin/components.toml`.

`--check` then re-renders every icon the map lists IN MEMORY and refuses any
file whose bytes differ, so a stale badge carrying the wrong letters or the
wrong panel fill cannot pass it. A header check alone could not say that: the
letters are the only thing telling one badge from another inside a panel, and
every badge in a panel shares its fill. The comparison follows the same
native-last rule the generator writes by: a key in both lists names ONE file,
the native entry owns its pixels, and that is the entry compared. The legacy
entry for such a key is stepped over rather than measured against a render it
did not make, and the closing line counts the files compared and the legacy
entries skipped, so it never claims to have checked a label nothing looked at.
The four shared keys are therefore checked once each, on the native side; a
typo in one of their legacy labels changes no pixel and raises nothing.
