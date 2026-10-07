# Vaulted: the cable net numbers and the mechanism chooser

Design specification, 7 October 2026. Branch `feature/studio-finish`.

Implements requirements 1 to 7 of the twelve set on 7 October. Requirements 8
to 12, the displays and the three exports, are a second spec and are listed in
section 12 so the seam between them is explicit.

Prior art this builds on, both in this repository:
`docs/superpowers/specs/2026-10-06-prescribed-length-staged-solve-design.md`
(the engine) and
`docs/superpowers/NEXT-2026-10-07-vaulted-solver-integration.md` (the workflow
as established by reading the real export).

## 1. The intent, written back

The engine that sizes the spooling machine exists and is tested, and it is
unreachable: it takes hand-written Python lists of points. The vault it is
meant to size lives in Vaulted, which already holds the geometry, the build
sequence and the weight of the skin. Nothing joins the two.

What this spec builds is that join, and it stops at the point where the
question "which motor, which gearbox, which reel, pulley or no pulley" has a
defended answer. It must say how much prestress the build will demand and what
ceiling the chosen parts impose, whether the arrangement fails and which part
fails first, how much rope goes through each drum, and it must let a person
move between named, purchasable configurations until one is satisfactory.

The success criterion is a purchase. When this is finished it should be
possible to open a study, try the parts already in the bill of materials, and
know whether they are adequate, without hand-editing a Python file and without
trusting a number whose provenance is not on screen.

## 2. Scope

**In.** The per-stage per-node load array. The staged cable net solve over a
real study. The demand document that solve writes. A catalogue of named parts
with their suppliers and prices. The prestress floor and ceiling. The pass or
fail verdict with the binding part named. Rope through the drum, drum wrap
capacity and carriage travel. An interface for choosing parts and comparing
configurations.

**Out.** The net coloured by tension and the numbers drawn on parts (spec two).
The component diagram, the spreadsheet and the data sheet (spec two). Any
change to the Grasshopper exporter. Any change to how the vault itself is
analysed: `solve_stage.py` and `solve_cra.py` are untouched.

**Global constraints.**

- The engine is newtons and millimetres throughout. Torque is newton
  millimetres, never newton metres.
- The Grasshopper contract is metres. Conversion happens once, at the adapter,
  and nowhere else.
- `src/tree_forest_compas` stays headless. It gains no knowledge of FastAPI, of
  the studio, or of file layout.
- No number reaches the screen without its provenance. Every catalogue figure
  carries its supplier, part number, the date it was seen and a confidence
  word, in the same vocabulary the bill of materials already uses: `confirmed`,
  `from price`, `approximate`, `estimate`, and here also `assumed` for a figure
  nobody published.
- `bench/studio/static/studio.js` is 18,597 lines and must not grow. New
  browser code is its own module, imported by `studio.js`, as `fields.js` and
  `live_graphs.js` already are.

## 3. The shape of it: two steps, because they cost different amounts

The expensive work is tied to the cut: tessellating, walking the courses,
weighing the placed skin, and solving the net at each stage. The cheap work is
asking what a given set of parts can hold.

```
step A, inside the staging run, minutes
  contract + cut + stage plan + resolved density + mechanism routing
    -> per stage, per node load, in newtons
    -> staged cable net solve
    -> cablenet-<...>.json            the DEMAND

step B, interactive, milliseconds
  demand + chosen parts
    -> prestress floor and ceiling, pass or fail, rope through each drum
```

Step B is cheap only because of the decomposition in section 5.6: every
mechanism check is a pure function of the worst cable tension and the
deviation, both of which the net produces without knowing anything about the
mechanism. So the net is walked once, in step A, and every candidate
configuration is then arithmetic.

Step A goes inside `run_staging` behind a flag, in the same manner as
`include_cra`, rather than becoming a second entry point. That module's own
docstring records why: a plan solved on one cut and matched against another
failed silently once already, and a separate entry point would rebuild the cut.

## 4. Files

**Created**

- `bench/studio/cablenet.py`: the adapter, the per-stage node loads, the staged
  run, and the demand document.
- `bench/studio/catalogue.py`: reads and validates `parts.json`, and builds a
  `Mechanism` from a chosen configuration.
- `bench/studio/parts.json`: the named parts, seeded from the bill of
  materials.
- `bench/studio/static/cablenet.js`: the chooser panel.
- `tests/studio/test_cablenet.py`, `tests/studio/test_catalogue.py`.
- `tests/test_capacity_curve.py`.

**Modified**

- `src/tree_forest_compas/capacity.py`: the sheave limit, and splitting the
  walk from the checks.
- `src/tree_forest_compas/trade_study.py`: `sweep` accepts a precomputed curve.
- `bench/studio/staging.py`: the `include_cablenet` flag and the call.
- `bench/studio/bundle.py`: `cablenet_path`, beside `staging_path`.
- `bench/studio/app.py`: three routes.
- `bench/studio/static/studio.js`: one import and one panel mount.
- `bench/studio/static/index.html`: the panel's markup.

## 5. Step A: the demand document

### 5.1 Units

The contract's vertices are metres. The engine refuses a geometry whose
greatest extent is under 50 mm, which is correct and which a metres geometry
trips. So the adapter multiplies every coordinate by 1000 exactly once, on the
way in, and divides by 1000 exactly once on anything geometric going back out.

Loads need no conversion. `geometry.face_area` returns square metres and the
weight expression below is already newtons.

The contract's own `equilibrium.loads` are not read. In the Armadillo style
export they are tributary areas with `factor 1`, summing to 125.4 square
metres, while `geometry.node_loads_newtons` multiplies them by 1000 as
kilonewtons. Reading them would produce a load one thousand times the area and
it would look like a plausible number. The loads are built from the mesh
instead, which is also the only way they can agree with the formwork curve
already on screen.

### 5.2 The per-stage per-node load

`stage_plan` already gives each stage the sorted list of faces placed up to and
including it, cumulatively. `formwork_curve` already weighs them. The node
loads are the same weights, distributed:

```
for each stage k:
    load[node] = (0, 0, 0) for every node
    for each face f placed at stage k:
        w = face_area(vertices, faces[f]) * thickness * density * GRAVITY
        for each corner node n of face f:
            load[n].z = load[n].z - w / (number of corners of f)
```

`density` is the value `resolve_density` already chose, so a vault wearing a
copper skin is pulled by a net that knows it is copper. `GRAVITY` is
`staging.GRAVITY`, 9.80665.

The split is equal between the face's corners. A corner-area-weighted split
would also preserve the total but would introduce a choice with no evidence
behind it, and the quantity that matters here is the total at each node, which
both preserve.

The net's own weight is then added to the same array, and kept as a separate
running total: 0.061 kg per metre for the 4 mm rope, by the catalogue, applied
as half of each member's weight to each of its two nodes. A stage with no skin
placed therefore still carries a load, which matters because
`hold_force_densities` refuses a stage with no load at all rather than
answering zero. The net's weight does not vary by stage, since the whole net is
hanging from the moment it is raised.

So each stage carries three sums, and the document records all three:

```
skin_load_sum_newtons  = the skin contribution alone, from the loop above
net_weight_newtons     = the rope's own weight, the same at every stage
node_load_sum_newtons  = skin_load_sum_newtons + net_weight_newtons
```

**The invariant that makes this trustworthy.** For every stage k:

```
skin_load_sum_newtons at stage k  ==  placed_weight_newtons at stage k
```

to within 1e-9 relative. That right-hand side is the number already drawn in
the formwork curve. If the two disagree, one of the readers is wrong and the
test says which stage. The sum is taken on the skin contribution alone and not
on the total, or the net's own weight would mask exactly the discrepancy the
check exists to find.

### 5.3 The net, the wires, and what is held

The problem handed to the engine has three kinds of edge:

1. **Net members.** `equilibrium.edges`, 2253 of them in the Armadillo style
   export. Real cables with manufactured rest lengths that never change.
2. **Wires.** One per spool. Each runs from a net node to a fixed point on the
   frame. Its rest length is what the drum commands. A wire needs no new
   physics: it is another cable, and the engine already solves it unchanged.
3. Nothing else. There are no struts.

Fixed nodes are the contract's `resolvedSupportNodeIds` (34 in that export)
plus one new fixed node per wire at its frame end.

The wires come from the study's mechanism document, `bench.mechanism/1`. Each
wire carries the frame point it is anchored to and a `net_vertex` naming the
equilibrium vertex it pulls. That was ruled on 7 October: the mapping lives in
the mechanism document and re-exporting when trying a different routing is
accepted. The mechanism document's own components, its motors and reels, are
deliberately ignored, because choosing them is what step B does.

`mechanism.py` validates the schema and the scale and hands the document
through verbatim, by design, so it is `cablenet.py` that reads the wires and
`cablenet.py` that refuses a document whose wires do not carry a `net_vertex`,
naming the wire.

### 5.4 The design point, and the net's manufactured rest lengths

The target shape is the contract's equilibrium geometry: the funicular form the
finished vault takes. It is the same at every stage, because holding it is the
whole point.

That form is funicular for the **full** skin load and for no other. So the
design point is the last stage, and it is where the net is dimensioned:

```
hold_force_densities(target, all_edges, fixed, loads = full skin + net weight)
    -> a tension per member
rest_length_for(ea, tension, length)  per member
    -> the net's manufactured rest lengths
```

Those are the lengths the net is made to. They are an output of step A and they
belong in the demand document, because they are a thing somebody has to cut.

`hold_force_densities` returns one member of a family when the net is
redundant, and says so. With 2253 edges against 2301 equilibrium equations this
net is not redundant but over-determined, so the solve is a non-negative least
squares fit and its residual is the quantity that matters. The residual is
recorded in the demand document, and a residual above the solver's own
tolerance is reported rather than absorbed: it means the exported geometry is
not exactly funicular for the load it is being given, which is a fact about the
export and should be read as one.

### 5.5 Walking the stages

At every stage before the last, the load is partial and the funicular form is
**not** exactly holdable by a tension-only net. This is the central physical
difficulty and the spec does not pretend otherwise. There are seven wires
against roughly 2300 degrees of freedom: the shape cannot be held exactly, only
held close.

So the per-stage question is not "what tension holds it" but "with the net's
manufactured rest lengths fixed and the wires commanded, where does the net
actually sit, and is that close enough". Close enough is the falsework
acceptance line, which is the whole reason that module exists.

Per stage, in order:

1. Solve forward at the current wire commands:
   `solve_prescribed_lengths(problem, fixed, rest_lengths, ea, loads)`.
2. Measure the deviation from the target.
3. Correct the wires:
   `correction_for(problem, fixed, rest_lengths, ea, loads, measured, target)`.
   It reports `reachable` and `residual_after`, the deviation it cannot remove,
   which is the honest answer for an under-actuated net.
4. Apply the correction to the wire rest lengths. The net members are not
   corrected: their rest lengths are manufactured and the correction must not
   be allowed to move them. `correction_for` is given the full rest length
   vector and its commands for net members are discarded, with a test pinning
   that they are.
5. Record the stage as a `Stage(name, kind, rest_lengths, loads)`.

The first stage is `kind="raise"`, which carries no conformance verdict because
there is no target to conform to while the net is being lifted. Later stages
are `kind="tile"`. `run_stages` then solves the sequence and returns the
register rows, and `write_register` writes them.

The register is one row per edge per stage. On the Armadillo style export with
twenty courses that is roughly 45,000 rows, and the file is written to disk and
read back by route, never held open in the browser. Spec two decides whether
the display needs a more compact form.

**The acceptance line.** `acceptance_line(rib, areal_load)` needs a rib, and a
rib is something a person designs, not something to infer from geometry.
`parts.json` therefore carries named falsework entries with all five `Rib`
fields, defaulting to the briefed plywood rib (span 2000, spacing 400, depth
100, width 18, E 9000), and `acceptance_source` records the entry verbatim so
no acceptance figure is ever anonymous.

One refusal guards the obvious error: if the rib's span is less than half the
study's greatest anchor-to-anchor distance, the run refuses and names both
numbers. A 2000 mm rib against a 15,900 mm vault is describing a different
building, and that acceptance line would pass everything.

### 5.6 The tension curve, and why the chooser is cheap

Read `capacity.py:_checks` and the decomposition falls out. Every check it
makes is a function of exactly two quantities, the worst cable tension and the
deviation, and of the mechanism's own scalars:

```
rope tension        worst            vs rope_mbl / safety_factor
anchor              worst            vs anchor_wll
spool rope tension  worst / AMA      vs spool_rope_mbl / safety_factor
motor torque        worst / AMA * r  vs motor_torque * ratio * eff * margin
deviation           deviation        vs acceptance
```

Neither `worst` nor `deviation` depends on anything about the mechanism. The
reeving, the drum, the gearbox and the motor enter only through arithmetic
after the net has been solved. So the net is walked once, at increasing load
factors, and the result is stored:

```
curve = [ (factor, worst_tension, deviation) for each of the walk's steps ]
```

Every candidate configuration is then evaluated against the stored curve
without touching the solver. This is the caching item LEFTOVERS flagged, solved
properly rather than by memoising a dictionary: the walk and the checks are
genuinely different things and separating them is correct independently of
speed.

The walk is run at the worst stage, the one whose maximum wire tension is
highest, since that is the stage that sizes the machine. Which stage that is is
recorded in the demand document by name.

### 5.7 The demand document

Written by `bundle.cablenet_path(...)`, beside `staging_path`, with the same
cache key so a density override earns its own slot.

```
{
  "schema": "bench.cablenet/1",
  "units": "N, mm",
  "study": "<export name>",
  "geometry_scale_applied": 1000.0,
  "density": <the resolved density>,
  "thickness": <metres, as the studio holds it>,
  "net": {
    "vertices": [[x, y, z], ...],          mm
    "edges": [[u, v], ...],
    "fixed": [ids],
    "manufactured_rest_lengths": [...],    mm
    "design_point_residual": <float>,
    "ea_newtons": <float>,
    "ea_provenance": "<catalogue entry and confidence>"
  },
  "wires": [
    {"name": "...", "net_vertex": <id>, "frame_point": [x, y, z]}, ...
  ],
  "stages": [
    {"stage": 1, "name": "...", "kind": "raise",
     "placed_weight_newtons": <float>,
     "skin_load_sum_newtons": <float>,
     "net_weight_newtons": <float>,
     "node_load_sum_newtons": <float>,
     "wire_rest_lengths": [...], "wire_reel_commands": [...],
     "wire_tensions": [...], "worst_net_tension": <float>,
     "deviation": <float or null>, "reachable": <bool>,
     "residual_after": <float>}, ...
  ],
  "sizing_stage": "<name of the worst stage>",
  "curve": [{"factor": f, "worst_tension": t, "deviation": d}, ...],
  "acceptance": <float>,
  "acceptance_source": "<the falsework entry, verbatim>",
  "register_path": "<relative path to the register file>"
}
```

`placed_weight_newtons` and `skin_load_sum_newtons` are both written so the
invariant of section 5.2 is checkable from the file alone, by anyone, without
re-running anything. Writing only their difference, or only one of them, would
make the check depend on trusting the code that wrote the file.

`curve` is stored as objects for the benefit of anyone reading the file, while
`capacity_from_curve` takes the engine's own tuples of
`(factor, worst_tension, deviation)`. `cablenet.py` converts between the two,
and that is the only place the two forms meet.

## 6. Step B: the catalogue and the chooser

### 6.1 The catalogue

`bench/studio/parts.json`, seeded from
`...\PHD robotics\AI\tasks\T1_spooling_machine\spooling-machine-BOM.xlsx`.
Every entry carries `supplier`, `part_number`, `unit_price`, `vat`,
`price_seen`, `confidence` and `source_url`, copied from that sheet, plus the
engineering figures below. Entries are grouped by kind.

**motor** (`motor_torque` in N mm)

| id | model | torque | note |
| --- | --- | --- | --- |
| `34HS46` | 34HS46-6004D-E1000 | 9000 | NEMA 34 closed loop, 6.0 A, 1000 PPR |
| `34HS39` | 34HS39 | 6500 | same family, less torque |
| `34HS31` | 34HS31 | 4300 | same family, least torque |
| `23HS45` | 23HS45-4204D-E1000 | 3000 | NEMA 23, the seven-spool candidate |

**gearbox** (`gear_ratio`, `gear_efficiency`)

| id | model | ratio | efficiency |
| --- | --- | --- | --- |
| `EG23-G20` | EG23-G20-D8 | 20 | 0.94, assumed |
| `EG34-G100` | EG34 family | 100 | 0.90, assumed, two stages |
| `direct` | no gearbox | 1 | 1.00 |

The efficiencies are marked `assumed`: StepperOnline publish no figure. They
are the only engineering numbers in the catalogue that no supplier stated, and
the interface shows the confidence word beside them.

**drum** (`drum_radius`, plus `width_mm` and `groove_pitch_mm`)

| id | description | radius | width | groove |
| --- | --- | --- | --- | --- |
| `drum-72` | the briefed drum, 72 dia winding surface | 36 | 150 | 4 |

**rope** (`rope_mbl`, `mass_per_metre_kg`, `ea_newtons`, `diameter_mm`)

| id | spec | MBL | kg/m | diameter |
| --- | --- | --- | --- | --- |
| `rope-4mm-7x19` | 4 mm 7x19 AISI 316 | 9091 | 0.061 | 4 |

MBL is the supplier's 927 kg converted at 9.80665. `ea_newtons` is 450000,
confidence `assumed`: a 7x19 rope's effective modulus is well below solid
steel's because of the lay, roughly 70 to 90 GPa over a metallic area near 5.65
square millimetres. This is the single most consequential assumed number in the
catalogue, because the rest lengths scale with it, and it is listed in section
13 as a thing to measure.

**sheave** (`sheave_swl`, `diameter_mm`, `sheave_efficiency`)

| id | model | SWL | diameter | efficiency |
| --- | --- | --- | --- | --- |
| `WZ-11-K` | GPS Lifting WZ 11 K | 1226 | 120 | 0.98, assumed |

SWL is the supplier's 125 kg at 180 degrees, converted.

**anchor chain**: an ordered list of the parts in the load path at the wall,
each with its own working load limit. The default chain is the eye bolt DIN 580
M12 A4 at 3334 N and the turnbuckle DIN 1480 M10 A4 at 1471 N.

**rail** (`stroke_mm`)

| id | model | stroke |
| --- | --- | --- |
| `MGN15H-300` | MGN15H, 300 mm rail | 300 |

**falsework**: named `Rib` entries, as section 5.5.

### 6.2 From chosen parts to a `Mechanism`

A configuration is a set of catalogue ids plus the pulley choice. The pulley
choice sets `reeve_factor`: 1 for no pulley, 2 for the moving block the rig is
drawn with. `catalogue.mechanism_for(configuration)` returns a `Mechanism`, and
two of its fields are computed rather than looked up:

```
anchor_wll      = min(working load limit of every part in the anchor chain)
spool_rope_mbl  = the spool rope's MBL, which is the same rope unless a
                  different one is named
```

**The binding anchor is the turnbuckle, not the eye bolt.** The eye bolt is
3334 N and the turnbuckle is 1471 N, so the chain's limit is 1471 N, less than
half the figure that has been used in the worked runs so far. Computing it from
the chain rather than accepting a typed number is the point: the weakest part
in a load path is not the part a person thinks of first.

`torque_margin` stays 0.5 and `safety_factor` stays 5.0, the engine's defaults,
and both are shown on screen beside the verdict rather than buried.

### 6.3 The prestress floor

The floor at a stage is the greatest wire tension that stage demands, which
step A already solved and stored in `stages[k].wire_tensions`. Requirement 1's
headline figure is the maximum across every stage:

```
prestress_floor = max over stages of max over wires of wire_tension
```

It is a property of the vault and the skin, not of the parts, so it does not
move when the configuration changes. That is worth stating on screen, because
it is the number that says whether the whole idea is feasible before any part
is chosen.

### 6.4 The ceiling

The ceiling is the greatest cable tension the chosen parts permit, and it is
the smallest of the limits the mechanism imposes:

```
ceiling = min(
    rope_mbl / safety_factor,
    anchor_wll,
    spool_rope_mbl * AMA / safety_factor,
    sheave_swl * AMA / reeve_factor,
    motor_torque * gear_ratio * gear_efficiency * torque_margin * AMA
        / drum_radius
)
AMA = (1 - eta**n) / (1 - eta),  n = reeve_factor, eta = sheave_efficiency
AMA = n when eta == 1
```

Each term is the inverse of the matching check in `_checks`, so the ceiling and
the pass or fail verdict can never disagree. The interface names which term won
and shows all five, because knowing the ceiling is 1471 N is less useful than
knowing it is the turnbuckle.

**Worked, on the parts the bill of materials actually lists.** Computed with
the figures in section 6.1, the briefed 36 mm drum, the EG23-G20 at 20 to 1 and
0.94, `torque_margin` 0.5, `safety_factor` 5.0 and `sheave_efficiency` 0.98.
All values in newtons of cable tension.

| motor | pulley | rope | anchor | spool rope | motor torque | sheave | ceiling | bound by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 34HS46, 9 N m | no | 1818 | 1471 | 1818 | 2350 | n/a | **1471** | anchor |
| 34HS46, 9 N m | yes | 1818 | 1471 | 3600 | 4653 | 1214 | **1214** | sheave |
| 34HS31, 4.3 N m | no | 1818 | 1471 | 1818 | 1123 | n/a | **1123** | motor torque |
| 34HS31, 4.3 N m | yes | 1818 | 1471 | 3600 | 2223 | 1214 | **1214** | sheave |
| 23HS45, 3 N m | no | 1818 | 1471 | 1818 | 783 | n/a | **783** | motor torque |
| 23HS45, 3 N m | yes | 1818 | 1471 | 3600 | 1551 | 1214 | **1214** | sheave |

Three things follow, and they are the reason this spec exists rather than a
larger motor being ordered.

The motor is not the constraint. With the 9 N m motor the torque term is 2350 N
against a ceiling of 1471 N set by a turnbuckle costing 3.79, and the machine
cannot be made stronger by buying a bigger motor.

**Adding the pulley makes the strong configuration worse.** With the 9 N m
motor the ceiling falls from 1471 N to 1214 N, because the moving block roughly
doubles the force through a sheave rated 1226 N while relieving a motor that
was never short of torque. The pulley earns its place only with a small motor:
it lifts the NEMA 23 from 783 N to 1214 N.

There is a hard ceiling of about 1.2 to 1.5 kN per cable that no motor choice
moves, set by the turnbuckle without a pulley and the sheave with one. If the
demand exceeds that, the answer is a heavier turnbuckle and a heavier sheave,
or more wires, and no amount of motor will do.

These six rows are exact and are used as the test fixture for section 6.4, so
an implementation that gets the mechanical advantage or the sheave resultant
wrong fails against published numbers rather than against my arithmetic.

### 6.5 Fails or not

```
fails  when  prestress_floor > ceiling
```

and the binding part is the term that set the ceiling. Where the limit comes
from the net rather than the parts, the deviation exceeding the acceptance
line, `capacity_from_curve` reports `deviation` as the binding name, as it does
today.

### 6.6 Rope through the drum, and what the catalogue now affords

Requirement 3 is answered per wire per stage by `reel_command`, which the
register already carries, plus three derived figures the catalogue now makes
possible:

```
turns at the drum   = reel_command / (2 * pi * drum_radius)
rope on the drum    = cumulative rope wound, from the raise onwards
drum capacity       = floor(width_mm / groove_pitch_mm) * 2 * pi * drum_radius
carriage travel     = cumulative rope taken in / reeve_factor
```

For the briefed drum that capacity is 37 wraps, which is 8369 mm of rope in a
single layer. Exceeding it means a second layer, which changes the effective
radius and invalidates the torque figure, so it is a hard check and not a
warning.

Carriage travel is checked against the chosen rail's stroke. The MGN15H-300
gives 300 mm. This is expected to fail on a real vault and that failure is
useful: it is the check that says the rig as drawn cannot reach, and it has
been invisible until now.

The sheave diameter over the rope diameter, 120 over 4, is 30, and this is
**reported as a number without a verdict**. The governing minimum would come
from ISO 4308-1, which is among the three unverified figures LEFTOVERS lists,
and a pass or fail against an unconfirmed limit would be worse than no verdict
at all.

The fleet angle is not checked. It needs the distance from the drum to the
first sheave, which is a layout dimension the catalogue does not hold.

### 6.7 Moving between configurations

The chooser scores a list of configurations at once and returns a row for each:
the parts, pass or fail, the ceiling and which part set it, the margin as
`ceiling / prestress_floor`, the resolution at the net from
`resolution_at_the_net`, the drum and travel checks, and the total price of the
priced lines.

The default list is the cross product of the catalogue's motors, gearboxes and
the two pulley choices, which is 4 x 3 x 2, twenty-four rows, every one
evaluated against the stored curve by arithmetic. `trade_study.fronts` then
marks the best on each of its three axes, accuracy, simplicity and margin, so
the three recommendations already implemented are visible without a second
mechanism for the same thing.

Rows whose price is a floor rather than a forecast are marked as such, because
the bill of materials has unpriced lines and a total that hides them would be a
lie by omission.

## 7. Changes to the engine

Both changes are to `src/tree_forest_compas/capacity.py` and both must leave
every existing test passing unchanged.

### 7.1 The sheave limit

`Mechanism` gains `sheave_swl: object = None`, defaulting to `None` meaning no
limit, so every existing caller and every existing test is unaffected.

`_checks` gains one clause, placed after the spool rope check and before the
torque check, since it concerns the same rope path:

```
sheave load = worst cable tension * reeve_factor / AMA          (approximately
              the resultant on the moving block)
refuse when sheave load > sheave_swl
```

For a single fall there is no moving block and the check does not apply.

This is the clause that makes requirement 5 answerable. Today the engine has no
sheave limit, so adding a pulley appears to be a free gain in motor capability.
It is not: the moving block roughly doubles the force through the sheave while
dividing the force at the drum, and the WZ 11 K at 1226 N is the lowest limit
in the whole mechanism once a pulley is fitted. The pulley helps the motor and
hurts the sheave, and until this clause exists the chooser cannot say so.

### 7.2 Splitting the walk from the checks

Two new public functions, with `capacity_of` refactored to call them so there
is exactly one implementation of the checks:

```
tension_curve(problem, fixed, rest_lengths, ea, load_pattern,
              steps=40, max_factor=20.0)
    -> tuple of (factor, worst_tension, deviation)

capacity_from_curve(mechanism, curve, acceptance)
    -> Capacity
```

`capacity_of(...)` becomes `capacity_from_curve(mechanism,
tension_curve(...), acceptance)` and keeps its signature and its behaviour
exactly. The refactor is behaviour-preserving and the existing capacity tests
are the proof.

`trade_study.sweep` gains an optional `curve=` argument. When given, it skips
the solve entirely and evaluates every grid combination against the curve. When
not given it behaves as it does today. The sweep's header records which path
was taken, because a reader of the file is entitled to know whether the rows
came from twenty-four solves or one.

## 8. The interface

One new panel, `bench/studio/static/cablenet.js`, imported by `studio.js` the
way `live_graphs.js` already is, with its markup in `index.html`.

It shows, in this order:

1. **The demand.** The prestress floor in newtons, the sizing stage by name,
   and the acceptance line with its source. These do not move when parts
   change.
2. **The parts.** One selector per kind, each option showing the part number,
   the price and the confidence word. The pulley choice is a toggle, labelled
   with what it does to both the motor and the sheave.
3. **The verdict.** Pass or fail, the ceiling, the part that set it, and the
   five ceiling terms listed so the margin on each is visible.
4. **The rope.** Turns, rope on the drum against the drum's capacity, and
   carriage travel against the rail's stroke, per wire.
5. **The configurations.** The scored table, with the three fronts marked.

The written interface standard in `project_vaulted_interface_language` applies
and is enforced by the existing tests: plain words, no jargon the vault itself
does not use, and no abbreviation that is not expanded somewhere on the panel.

## 9. Routes

```
GET  /api/catalogue
     the parts, grouped by kind, with provenance

GET  /api/studies/{export}/cablenet
     the demand document, or 404 with a message saying to run the study
     with the cable net phase enabled

POST /api/studies/{export}/cablenet/configurations
     body: a list of configurations
     returns: one scored row per configuration, plus the fronts
```

The run route `POST /api/runs` gains a `cablenet` boolean, defaulting to false,
and the run's `phase` gains the value `cablenet` so the existing progress
display reports it without change.

## 10. Refusals

Each of these refuses with a message that names the thing and what to do, in
the manner `geometry.load_contract` already sets. None of them is a 500.

- A mechanism document whose wires carry no `net_vertex`, naming the wire.
- A `net_vertex` outside the contract's vertex range, naming the id and the
  range.
- A wire whose `net_vertex` is an anchor, since commanding a fixed node does
  nothing and silently achieving nothing is the worst outcome.
- A study with no mechanism document at all.
- A rib whose span is under half the study's greatest anchor-to-anchor
  distance, naming both.
- A configuration naming a catalogue id that does not exist, naming the id.
- The design point hold solve failing, carrying the engine's own message
  through, since `HoldError` already says whether the geometry needed a strut
  or had no load.
- The engine's millimetre guard tripping, which means the conversion was
  skipped, and the message should say so rather than repeating the engine's
  more general wording.

## 11. Testing

**The invariant.** For a real study, every stage's per-node load sum equals
that stage's `placed_weight_newtons` to 1e-9 relative. This is the one test
that catches a wrong density, a wrong thickness, a dropped face and a double
count, all four, and it compares against a number already on screen.

**Units.** A contract in metres is read as millimetres: a 15.9 m study arrives
at the engine with a greatest extent of 15,900 and is not refused. A test
asserts the scale factor was applied exactly once by checking a known
anchor-to-anchor distance.

**The anchor chain.** A chain of the eye bolt and the turnbuckle yields 1471 N,
not 3334 N. Reversing the order of the chain yields the same answer.

**The sheave clause.** A mechanism with a sheave and two falls is limited by it
at a tension where the same mechanism with one fall is not. A mechanism with
`sheave_swl=None` behaves exactly as it does today, pinned against the existing
expected values.

**The ceiling, against the worked table.** All six rows of section 6.4, each
asserting both the ceiling to the nearest newton and the name of the binding
part. The row that matters most is the 9 N m motor with the pulley: it must
return 1214 N bound by the sheave, lower than the same motor without the
pulley. An implementation that treats reeving as a free gain passes every other
test and fails this one.

**The refactor.** `capacity_from_curve` applied to `tension_curve`'s output
returns a `Capacity` identical in every field to what `capacity_of` returns for
the same inputs, across the cases the existing capacity tests already cover.

**The correction does not move the net.** After `correction_for`, every net
member's rest length is unchanged to the last bit, and only wire rest lengths
have moved.

**Falsework span.** A 2000 mm rib against a study whose anchors span 15,900 mm
refuses, and the message carries both numbers.

**End to end.** One run on the Aramdillo style export produces a demand
document that round-trips through `json.loads`, with no NaN, and with
`skin_load_sum_newtons` matching the staging document's own
`placed_weight_newtons` for every stage.

Tests needing scipy carry `pytest.importorskip("scipy")`, since scipy is in the
`equilibrium` extra and not in `dev`, as `tests/test_hold.py` already does.
Tests needing fastapi carry the same guard for the same reason.

## 12. What spec two covers

Requirements 8 to 12, which are all downstream of the register and the chosen
configuration, and none of which changes a number:

8. The net coloured by tension, per stage, in the existing 3D view.
9. The readout as numbers on the parts of the machine, in `mechanism.js`.
10. The component diagram.
11. The spreadsheet.
12. The data sheet, which was ruled on 7 October to be for the thesis and the
    supervisor: the argument rather than a table to work from, the falsework
    being replaced, its deflection as the acceptance line, the load path, and
    every number with its source.

## 13. Open items this spec does not settle

1. **The rope's EA.** 450000 N is assumed from a lay factor and a modulus band,
   not measured and not published. The manufactured rest lengths scale with it.
   It should be measured on a sample, or a figure obtained from GS Products,
   before any net is cut. Everything else in this spec tolerates it being
   wrong; the cut lengths do not.
2. **The gearbox efficiencies**, 0.94 and 0.90, are assumed for the same
   reason, and they move the torque ceiling directly.
3. **ISO 4308-1's minimum D over d**, which is why the sheave ratio is reported
   without a verdict. One of the three unverified figures LEFTOVERS lists; the
   other two, the ACI 347 and BS 5975 deflection limits, bear on the acceptance
   line and are unchanged by this spec.
4. **The fleet angle**, which needs a layout dimension the catalogue does not
   carry.
5. **Whether the seven wires are enough.** Section 5.5 expects a residual
   deviation the wires cannot remove. If that residual exceeds the acceptance
   line on a real study, the answer is more wires or a different routing, and
   that is a design finding this spec is built to surface rather than one it
   can pre-empt.
