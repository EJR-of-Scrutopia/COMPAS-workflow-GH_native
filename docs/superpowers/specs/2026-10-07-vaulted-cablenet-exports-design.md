# Vaulted: the cable net exports

Design specification, 7 October 2026. Branch `feature/studio-finish`.

Implements requirements 10, 11 and 12 of the twelve set on 7 October, plus the
chosen-folder button asked for after the first spec shipped. It is the second
and final spec of that pair; the first is
`docs/superpowers/specs/2026-10-07-vaulted-cablenet-numbers-and-chooser-design.md`
and everything here reads what that one produces.

## 1. The intent, written back

The numbers exist and can be explored on screen. Nothing leaves the machine.
What is missing is the ability to hand the answer to somebody: to a supervisor
as an argument, to a workshop as a parts list, and to the thesis as a figure.

So this spec produces three files from one action, written together into a
folder the owner chooses once and the studio remembers. The success criterion is
that a person who was not in the room can read the data sheet, open the
spreadsheet, look at the diagram, and reach the same conclusion the panel
reached, without being told anything else.

A second criterion matters as much and is easier to lose: the three must agree
with each other and with the panel. Three documents that disagree are worse than
one, because the reader cannot tell which is wrong.

## 2. Scope

**In.** The spreadsheet, the component diagram and the data sheet. The folder
picker and its remembered default. The routes that write and download them. The
button on the cable net panel.

**Out.** Any change to how a number is computed. If an export disagrees with the
panel, the export is wrong and is fixed here; the engine is not touched. No new
analysis, no new checks, no change to `parts.json` figures.

## 3. Global constraints

- **The exports read; they never compute.** Every figure comes from the demand
  document, from `catalogue.ceiling_for`, `catalogue.price_of`,
  `catalogue.drum_and_travel` and `catalogue.rope_speed`, or from `parts.json`.
  Nothing is recalculated in a second place, because a second implementation is
  how a diagram comes to contradict a verdict.
- No number without provenance. Supplier, part number, price, date seen and
  confidence word travel with every priced line, in the bill of materials'
  vocabulary: `confirmed`, `from price`, `approximate`, `estimate`, `assumed`.
- A total with an unpriced line is a floor and says so. This is already how
  `price_of` reports and how the owner's own bill of materials reads.
- `bench/studio/**` must not import numpy, scipy, compas or a solver stack;
  `tests/studio/test_studio_guard.py` enforces it. The export code is arithmetic
  on already-computed numbers and needs none of them.
- Newtons and millimetres, as everywhere. Prices in pounds.
- `bench/studio/static/studio.js` gains nothing. The button belongs to
  `cablenet.js`.

## 4. What the exports read

**The demand document**, written by `solve_cablenet.py` to the path
`bundle.cablenet_path(...)` and served by
`GET /api/studies/{export}/cablenet`. Verified field names, as the code writes
them today:

```
schema, units, geometry_scale_applied, prestress, ea_newtons,
study, density, thickness, sizing_stage, acceptance, acceptance_source,
net: { vertices, edges, fixed, net_edge_count, manufactured_rest_lengths,
       node_of, ea_provenance },
stages: [ { stage, name, kind, placed_weight_newtons, skin_load_sum_newtons,
            net_weight_newtons, node_load_sum_newtons, wire_rest_lengths,
            wire_reel_commands, wire_tensions, worst_net_tension,
            deviation, reachable, residual_after } ],
wires: [ { name, net_vertex, frame_point } ]
```

**The scored row**, from `POST /api/studies/{export}/cablenet/configurations`:

```
configuration, ceiling, binding, passes, passes_note, margin,
price: { pounds, unpriced, is_floor },
rope_speed_mm_s, rope_path: { rope_wound_mm, turns_at_drum,
  drum_capacity_wraps, drum_capacity_mm, drum_fits, carriage_travel_mm,
  rail_stroke_mm, rail_fits, sheave_over_rope_diameter },
refused
```

**The catalogue**, `catalogue.load_parts()`, for each chosen part's provenance
and for the individual ceiling terms via `ceiling_terms`.

## 5. The spreadsheet

`<study>-cablenet.xlsx`. Five sheets, in this order, because that is the order a
reader needs them.

**Read this.** The legend, modelled on the owner's own bill of materials: what
each confidence word means, that rows without a price make every total a floor
rather than a forecast, that VAT is not normalised between suppliers, that
delivery is excluded, and the date the figures were taken. Also the units: that
forces are newtons, lengths millimetres, torque newton millimetres.

**Chosen.** The configuration and its verdict. One row per ceiling term, each
with the term's name, the part that supplies it, the tension it permits in
newtons, and a mark against the one that binds. Then the verdict: the prestress
the build demands, the ceiling, whether it holds, the margin, and separately
whether the net stays within the acceptance line, with the worst residual and
the stage it occurs at. The two halves of the verdict are shown as two rows,
never merged, because a configuration can pass one and fail the other.

**Parts.** One row per chosen part, with kind, catalogue id, model, supplier,
part number, unit price, VAT basis, date seen, confidence and source URL. A
total row that is explicitly labelled a floor when any line is unpriced, naming
how many lines and which.

**Stages.** One row per stage per wire: stage, name, kind, wire name, the net
vertex it pulls, rest length, reel command, tension. Plus per stage, once: the
placed weight, the skin load sum, the deviation, whether it was reachable and
the residual after correction. The register is the long form of this and stays
on disk; this sheet is the readable form.

**Ladder.** The upgrade ladder: for each rung, the parts that differ, the
ceiling, the binding part and the price. This is the sheet that answers "what
should I change next", and the first spec showed that the answer is usually not
the motor.

### The dependency, and what happens without it

`openpyxl` is in none of this repository's environments, though it is what wrote
the owner's bill of materials under another interpreter. It is added as an
optional extra, `exports`, in `pyproject.toml`.

When it is present the workbook is written as above. When it is absent the
spreadsheet degrades to one CSV per sheet, named
`<study>-cablenet-<sheet>.csv`, and the response says plainly that the workbook
was not written, names the extra to install, and lists the files that were. The
other two exports are unaffected either way.

CSV is a fallback and not the plan: it loses the sheet structure and the shading
that marks an unpriced line. The degradation exists so that a studio without the
extra still exports something true, not so that the extra is optional in
practice.

## 6. The component diagram

`<study>-cablenet.svg`. Written as text with no library.

It draws the load path in the order the force travels, which is also the order
`ceiling_terms` checks it:

```
wall anchor -> turnbuckle -> net cable -> [moving block] -> drum
  -> gearbox -> motor
```

Each element is a box carrying the part's name, its catalogue id, and the cable
tension it permits in newtons. The binding element is marked distinctly and
labelled with the ceiling. Elements that do not apply to the configuration, the
moving block when the reeving is one fall, are omitted rather than drawn greyed,
because a diagram of a machine should show the machine.

Below the path, a second band shows the net schematically: the anchor count, the
wire count, and each wire's net vertex, with the sizing stage named. This is not
a geometric drawing of the vault and must not pretend to be; it is a wiring
diagram of what pulls what.

**The invariant that keeps it honest:** the element the diagram marks as binding
is `catalogue.ceiling_for(...)`'s second return value, and the tension it prints
beside each element is the matching entry of `ceiling_terms`. Both come from the
same call that produced the panel's verdict. A test asserts the marked element
and the verdict's binding part are the same string. The diagram cannot drift
from the answer because it is not allowed its own arithmetic.

Styling follows the owner's locked KiCad convention, since these figures sit
beside those: dark grey strokes at double width, Liberation Sans, tight spacing.

## 7. The data sheet

`<study>-cablenet.md`. Written for a supervisor and for the thesis, which the
owner ruled on 7 October, so it argues rather than tabulates.

Sections, in order:

1. **What this machine replaces.** The timber falsework, the rib it is taken
   from, its span and section, and the deflection that becomes the acceptance
   line, with `acceptance_source` quoted verbatim.
2. **What the vault demands.** The prestress floor, the stage that sizes it, the
   skin and its density, and the total placed weight. Where the number came from.
3. **What was chosen.** The configuration, part by part, with supplier and price.
4. **Whether it holds.** Both halves: the tension verdict with the binding part
   and the margin, and the shape verdict with the worst residual against the
   acceptance line. If either fails, that is the section's first sentence.
5. **The load path.** Every ceiling term in newtons with the part that sets it,
   so the reader can see how far each is from binding rather than only which one
   won.
6. **The assumptions, listed as assumptions.** The rope's EA and that the
   manufactured lengths scale with it; the gearbox efficiencies; the flat torque
   derate and the motor speed the chosen rope speed demands; the anchor angle,
   which is assumed off-axis because the bolt's orientation is not in the
   export; the uniform prestress of the cut rule.
7. **What is not checked.** The sheave diameter ratio is reported without a
   verdict because the governing standard is unconfirmed; the fleet angle needs
   a layout dimension nobody records; nothing dynamic is modelled; the capacity
   walk is static.

Section 6 and section 7 are not optional and not an appendix. A data sheet that
presents assumed numbers as measured ones would mislead exactly the reader it is
written for.

## 8. Where the files go

**A chosen folder, remembered.** A new setting `cablenet_exports_folder`, in the
same `settings.json` as the six that exist, restored by `apply_saved_folders`
at startup. The routes mirror the established shape exactly:

```
GET  /api/cablenet/exports/folder          the folder in use
POST /api/cablenet/exports/folder          validate, use and remember a path
POST /api/cablenet/exports/folder/browse   open the native dialog, return a
                                           path WITHOUT setting it
```

The browse route returns the chosen path and does not apply it; the caller posts
it back, so validation and remembering live in one place rather than two. That
is how `/api/folder` is written and the reason is in its own docstring.

Files are delivered with the existing `deliver_output`, which never writes over
an existing file: a second export in the same second becomes `-2`, not a silent
replacement. Where no folder has been chosen, exports go to the studio's default
output folder, as recordings do.

**And downloadable.** `GET /api/studies/{export}/cablenet/exports/{kind}` with
`kind` in `spreadsheet`, `diagram`, `datasheet`, returning the file for the
browser to download, for when the studio is being used over the tailnet rather
than at the machine.

**The button.** One Export button on the cable net panel, beside the verdict,
with the current folder shown next to it and a Choose folder button. After a
successful export the panel lists the files written, with their full paths, so
the owner can find them without hunting.

## 9. Refusals

Each names the thing and what to do, and none is a 500.

- **No demand document.** The exports have nothing to describe. The message says
  to run the study with the cable net phase enabled, the same wording the demand
  route already uses.
- **A configuration the catalogue refuses**, for example a family mismatch or a
  reeving with no sheave named. Refuse to export: a document describing a
  machine that cannot be built is worse than no document.
- **A configuration that FAILS is exported, deliberately.** A failing analysis is
  a result and often the one worth sending. The documents lead with the failure
  rather than burying it, and the spreadsheet's Chosen sheet and the data sheet's
  section 4 both state it first.
- **An unwritable folder.** Name the folder and the operating system's reason.
  `deliver_output` currently falls back to returning the source path on `OSError`;
  for exports that silence is wrong, so the route reports the failure.
- **`openpyxl` absent** is not a refusal but a stated degradation, as section 5
  sets out.

## 10. Testing

**The three agree.** One run produces all three from one scored row. A test
asserts that the binding part named in the spreadsheet's Chosen sheet, the
element marked in the SVG, and the part named in the data sheet's section 4 are
the same string, and that the ceiling printed in each is the same number. This
is the test that would have caught the class of defect the first spec's final
review found three of.

**The diagram has no arithmetic of its own.** A test patches `ceiling_terms` to
return altered values and asserts the diagram's printed tensions follow, proving
it reads rather than recomputes.

**A floor stays a floor.** With an unpriced part in the configuration, the
spreadsheet's total row is marked a floor and names the count, and the data
sheet says so in words.

**Both halves of the verdict survive.** A configuration whose parts carry the
tension but whose net misses the acceptance line must produce documents that say
it does not hold, and must say which half failed. A test builds exactly that
case, because it is the case the panel got wrong before the final review.

**The folder is remembered.** Setting it writes `settings.json`; a fresh
`apply_saved_folders` restores it; an export with none set goes to the default.

**The workbook opens.** An opt-in test opens the written `.xlsx` in a hidden
Excel through COM and reads a known cell back, skipped where Excel is absent.
Python can confirm the file is a valid zip of XML and cannot confirm Excel will
open it, which is the failure that matters.

**CSV fallback.** With `openpyxl` made unimportable, the export still writes the
CSV set and the response names the extra to install.

## 11. Out of scope, and why

The register, which `write_register` already produces, is not re-exported here.
It is the long machine-readable form and already lands on disk; the Stages sheet
is its readable summary. Making a second copy of it inside the workbook would
duplicate the one artifact that is already canonical.

No PDF. The data sheet is Markdown because that is the format this project keeps
its documents in and it pastes into the thesis. A PDF would need a browser or a
type-setting dependency, and the headless browser on this machine is a local
convenience rather than something the repository should rely on.

## 12. Open items

1. **The exports cannot run until a mechanism document carries `net_vertex` per
   wire.** That is the same precondition the first spec records, and it is the
   one thing blocking an end-to-end run on a real study.
2. **The spreadsheet's styling is asserted loosely.** A test can check a cell's
   value; checking that a row is shaded the way the owner's bill of materials
   shades an unpriced line is not worth the machinery, so it is checked by eye
   once and then trusted.
3. **The diagram's layout is fixed rather than computed.** A configuration with
   an unusually long part name may overflow its box. The elements are few and
   known, so this is a cosmetic risk accepted rather than solved with a layout
   engine.
