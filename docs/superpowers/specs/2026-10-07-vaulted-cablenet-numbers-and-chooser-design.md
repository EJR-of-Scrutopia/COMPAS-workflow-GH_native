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
with their suppliers and prices, covering three drive families and tiered
ladders for the parts that limit the machine. The prestress floor and ceiling.
The pass or fail verdict with the binding part named. Rope through the drum,
drum wrap capacity, carriage travel and rope speed. An interface for choosing
parts and comparing configurations.

Because the owner chose on 7 October to carry the alternating current drive as
a buildable option rather than a comparison, the catalogue also names the
companion parts that family requires, and the chooser refuses a motor paired
with a drive that cannot control it. Designing the encoder and the software
loop themselves is not in this spec; naming them as required, with the reason,
is.

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
- `bench/studio/catalogue.py`: reads and validates `parts.json`, refuses a
  configuration whose motor and drive families disagree, resolves the anchor
  chain at each wire's own angle, and builds a `Mechanism` from a chosen
  configuration.
- `bench/studio/parts.json`: the named parts across three drive families, with
  tiered ladders for the anchor chain, the rope and the sheave, seeded from the
  bill of materials and extended as section 6.2 sets out.
- `bench/studio/static/cablenet.js`: the chooser panel.
- `tests/studio/test_cablenet.py`, `tests/studio/test_catalogue.py`.
- `tests/test_capacity_curve.py`.

**Modified**

- `src/tree_forest_compas/capacity.py`: the sheave limit, and splitting the
  walk from the checks.
- `src/tree_forest_compas/trade_study.py`: `sweep` accepts a precomputed curve,
  and `resolution_at_the_net` accepts counts per revolution for a drive that
  does not microstep.
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

### 6.1 Three drive families, and why the family is a field

The catalogue cannot hold motors in one list, because "torque" does not mean
the same thing across the candidates. A stepper is quoted holding torque at
standstill; an induction motor is quoted continuous torque at rated speed. Put
them in one column and a 1 HP boat lift motor appears weaker than a 9 N m
stepper, which is true of the number and false of the machine.

So every motor entry carries a `family`, and the family decides how
`motor_torque` is derived, how it is derated, and where position comes from.

**Family A, closed-loop stepper.** What the rig is drawn with: NEMA 23 and
NEMA 34 closed loop, driven step and direction from the Octopus through a
CL57Y or CL86Y. `motor_torque` is the published holding torque. It is derated
by `torque_margin` 0.5, because holding torque falls away with speed and the
published figure is a standstill figure. Position comes from
`steps_per_revolution * microsteps`. It creeps naturally, which is what a net
being tensioned wants. It does not hold without power, so the ratchet and pawl
stay.

**Family B, three-phase AC with an inverter.** The buildable form of the winch
motor route. `motor_torque` comes from the power and the speed:

```
T [N mm] = 9550 * power_kw / rated_speed_rpm * 1000
```

**The rated speed must be the one for this supply.** A four-pole motor
synchronises at 1500 rpm on the United Kingdom's 50 Hz and runs near 1440 under
load, where the 1725 rpm quoted for boat lift motors is a 60 Hz figure. The
same motor therefore delivers about a fifth more torque here than its American
data sheet implies, and the rope moves a fifth slower, which is the better end
of both trades. The catalogue holds family B at 1440 rpm and family C at the
1725 rpm its parts are actually sold at, and the two must not be mixed.

So 0.75 kW at 1440 rpm is 4974 N mm, and 1.5 kW is 9948 N mm. It is derated by
`torque_margin` 0.8, a service factor against the continuous thermal rating
rather than a derate of a standstill figure; the breakdown torque of an
induction motor is well above rated, so starting is not what limits it.

Position does **not** come free. This family needs an inverter with a
single-phase input and a three-phase output, an incremental encoder on the
shaft, and a loop closed in software, because the Octopus cannot drive it with
step and direction. That is the real cost of this family and the catalogue
states it as a required companion part rather than leaving it to be discovered
during a build.

**Family C, single-phase capacitor motor, recorded and closed.** The boat lift
motors as actually sold: 1 to 2 HP, 115 or 230 V single phase, 1725 rpm, TENV,
in the NEMA 56C frame. They are in the catalogue and they are marked
unbuildable for this machine, with the reason attached, because an option that
is silently absent looks like an oversight and an option that is visibly closed
is an answer.

The reason is that a capacitor-run single-phase motor cannot be speed
controlled by an inverter. Its run capacitor is sized for one frequency, so
away from it the motor loses torque and heats, and an inverter has no third
winding to work with. The motor is therefore a fixed-speed on and off device.
That is entirely adequate for a boat lift, which goes up and comes down, and
no use for holding a net within millimetres while courses are laid.

Note also that NEMA 56C is an AC frame and not a larger stepper: 5/8 inch
shaft, 4.5 inch pilot, 5.875 inch bolt circle. It shares nothing with the
NEMA 34 stepper frame but the naming convention.

### 6.2 The catalogue

`bench/studio/parts.json`, seeded from
`...\PHD robotics\AI\tasks\T1_spooling_machine\spooling-machine-BOM.xlsx` for
everything already sourced, and extended with the ladders below. Every entry
carries `supplier`, `part_number`, `unit_price`, `vat`, `price_seen`,
`confidence` and `source_url`, in the bill of materials' own vocabulary, with
`assumed` added for a figure no supplier published.

**motor**: `family`, `motor_torque` in N mm, `torque_basis`,
`torque_margin`, and for families B and C `power_kw` and `rated_speed_rpm`.

| id | family | model | torque | basis |
| --- | --- | --- | --- | --- |
| `23HS45` | A | 23HS45-4204D-E1000 | 3000 | holding |
| `34HS31` | A | 34HS31 | 4300 | holding |
| `34HS39` | A | 34HS39 | 6500 | holding |
| `34HS46` | A | 34HS46-6004D-E1000 | 9000 | holding |
| `34HS-12` | A | NEMA 34 closed loop, 12 N m | 12000 | holding |
| `ac-0r75-3ph` | B | 0.75 kW three phase, 4 pole, 1440 rpm | 4974 | continuous |
| `ac-1r1-3ph` | B | 1.1 kW three phase, 4 pole, 1440 rpm | 7295 | continuous |
| `ac-1r5-3ph` | B | 1.5 kW three phase, 4 pole, 1440 rpm | 9948 | continuous |
| `boatlift-1hp` | C | 1 HP 56C boat hoist duty, single phase | 4130 | continuous |
| `boatlift-2hp` | C | 2 HP 56C boat hoist duty, single phase | 8260 | continuous |

The family B and C torques are computed from power and speed by the expression
in section 6.1, not quoted by a supplier, so they carry confidence `assumed`
until a nameplate is read.

**drive electronics**, one required per motor family, and the chooser refuses a
configuration that pairs a motor with the wrong one.

| id | for family | part | note |
| --- | --- | --- | --- |
| `CL57Y` | A | StepperOnline CL57Y, 24 to 50 V, 7 A | owned; 50 V ceiling limits a NEMA 34 at speed |
| `CL86Y` | A | StepperOnline CL86Y, 30 to 110 V, 8.5 A | the standard pairing for a NEMA 34 |
| `vfd-1ph-in` | B | inverter, single-phase in, three-phase out | plus an encoder and a software loop |
| `none` | C | direct on line, fixed speed | why family C is closed |

**gearbox**: `gear_ratio` and `gear_efficiency`, with the efficiency a function
of the ratio for worms rather than one figure.

| id | kind | ratio | efficiency |
| --- | --- | --- | --- |
| `direct` | none | 1 | 1.00 |
| `EG23-G20` | planetary | 20 | 0.94, assumed |
| `EG34-G100` | planetary | 100 | 0.90, assumed |
| `worm-7r5` | worm | 7.5 | 0.90, assumed |
| `worm-10` | worm | 10 | 0.88, assumed |
| `worm-20` | worm | 20 | 0.80, assumed |
| `worm-30` | worm | 30 | 0.72, assumed |
| `worm-50` | worm | 50 | 0.60, assumed |
| `worm-100` | worm | 100 | 0.45, assumed |

Worm reducers in the NEMA 56C input flange are offered from 7.5 to 1 up to 100
to 1, and their suppliers quote efficiency falling with ratio across a band of
roughly 45 to 93 per cent. The figures above interpolate that band and are
marked assumed; each must be replaced with the chosen gearbox's own published
figure before anything is ordered, because the torque term scales with it.

**Worm reducers are not self-locking and must not be treated as the fail-safe
hold.** Their own suppliers state they are "not to be considered fail safe or
self-locking devices". The ratchet and pawl remain in the design for every
family.

**anchor chain**: an ordered list of the parts in the load path at the wall,
each with an axial and an angled working load limit. DIN 580 A4 eye bolts, in
kilograms, axial and at up to 45 degrees:

| id | size | axial | at 45 degrees | axial N | angled N |
| --- | --- | --- | --- | --- | --- |
| `eye-M12` | M12 | 340 | 240 | 3334 | 2354 |
| `eye-M16` | M16 | 700 | 500 | 6865 | 4903 |
| `eye-M20` | M20 | 1200 | 860 | 11768 | 8434 |
| `eye-M24` | M24 | 1800 | 1290 | 17652 | 12651 |

**The angled rating is the one that applies.** A wire runs from a net node to a
frame point and almost never pulls along the eye bolt's axis, and off axis the
rating drops by about 30 per cent. The angle is not assumed: the mechanism
document gives both ends of every wire, so `catalogue.py` computes the angle
between the wire and the eye bolt's axis and takes the matching rating, using
the angled figure for anything over 5 degrees and refusing anything over 45,
which is outside the published table.

Turnbuckles are tiered by **configuration as well as size**, because the
configuration matters as much as the thread. The rig's current part is a
DIN 1480 hook and hook M10 in A4, which its supplier rates at 150 kg, 1471 N,
and that is the single lowest limit in the whole machine. Published tables for
eye and eye and for stub end at the same thread are far higher, by a factor
approaching three. The hook is the weak element, so moving to a stub-end
turnbuckle may buy more than moving up two thread sizes.

The ladder is therefore populated from each supplier's own page for the exact
configuration and material, never from a generic DIN 1480 table, and section 13
records that this ladder is not yet confirmed. The generic tables found so far
disagree with each other and with the supplier by enough that quoting them
would be worse than leaving the rung empty.

**rope**: `rope_mbl`, `mass_per_metre_kg`, `ea_newtons`, `diameter_mm`. 7x19
AISI 316, with the MBL band published sources give for each diameter:

| id | diameter | MBL band, kN | catalogue MBL, N | kg/m |
| --- | --- | --- | --- | --- |
| `rope-4mm` | 4 | 8.3 to 9.1 | 9091 | 0.061 |
| `rope-5mm` | 5 | 13.0 to 14.2 | 13000 | 0.093 |
| `rope-6mm` | 6 | 18.8 to 20.5 | 18800 | 0.134 |
| `rope-8mm` | 8 | 33.3 to 36.4 | 33300 | 0.238 |

The 4 mm entry is GS Products' own 927 kg converted, which sits inside the
band, and the rest take the bottom of the band until the supplier's own page
for that diameter is read. Taking the bottom is the safe direction and the
spread is recorded so nobody mistakes it for precision.

`ea_newtons` is 450000, confidence `assumed`: a 7x19 rope's effective modulus
is well below solid steel's because of the lay, roughly 70 to 90 GPa over a
metallic area near 5.65 square millimetres. This is the single most
consequential assumed number in the catalogue, because the manufactured net
lengths scale with it. Section 13 carries it.

**sheave**: `sheave_swl`, `diameter_mm`, `sheave_efficiency`. The rig's WZ 11 K
is 125 kg at 180 degrees, 1226 N, 120 mm, and it is the binding part in any
reeved arrangement. Heavier rungs come from the same supplier's range and are
sourced with the turnbuckle ladder.

**drum**: `drum_radius`, `width_mm`, `groove_pitch_mm`. The briefed drum is 72
diameter winding surface, so radius 36, 150 wide, grooved at 4.

**rail**: `stroke_mm`. The MGN15H-300 gives 300.

**falsework**: named `Rib` entries, as section 5.5.

### 6.3 From chosen parts to a `Mechanism`

A configuration names a motor, a drive, a gearbox, a drum, a rope, an anchor
chain, a sheave where one is fitted, a rail and a falsework entry, plus the
pulley choice. The pulley choice sets `reeve_factor`: 1 for no pulley, 2 for
the moving block the rig is drawn with.

`catalogue.mechanism_for(configuration, wire_angles)` returns a `Mechanism`.
Five of its fields are computed rather than looked up:

```
motor_torque    = holding torque            for family A
                = 9550 * kw / rpm * 1000    for families B and C
torque_margin   = 0.5 for family A, 0.8 for families B and C
gear_efficiency = the gearbox's figure AT THE CHOSEN RATIO
anchor_wll      = min over the chain of the rating at that wire's own angle
spool_rope_mbl  = the spool rope's MBL, the same rope unless another is named
```

**The binding anchor is the turnbuckle, not the eye bolt.** The eye bolt is
3334 N axially and 2354 N at an angle; the hook and hook turnbuckle is 1471 N.
So the chain's limit is 1471 N, well under half the figure the worked runs have
been using. Computing it from a named chain rather than accepting a typed
number is the whole point: the weakest part in a load path is not the part a
person thinks of first, and here it costs 3.79.

`safety_factor` stays 5.0, the engine's default, and is shown on screen beside
the verdict rather than buried.

### 6.4 Rope speed, which only families B and C make urgent

The engine models no speed at all, and for family A it does not need to: a
stepper is commanded as fast or as slow as wanted. For a motor with a rated
speed, the rope speed is a consequence of the choice rather than a setting:

```
rope speed [mm/s] = rated_speed_rpm / gear_ratio / 60 * 2 * pi * drum_radius
```

At 1440 rpm on the briefed drum that is 271 mm/s through a 20 to 1 worm,
109 mm/s at 50 to 1 and 54 mm/s at 100 to 1. A net being held to within
millimetres while tiles are laid wants to creep, so these are fast, and the
inverter is what makes them usable. The same motors on a 60 Hz supply would be
a fifth faster again, which is the other half of why the supply frequency has
to be stated rather than inherited from a data sheet.

It is reported as a column with no pass or fail, because the acceptable rate of
movement has not been set. Section 13 carries it as an open item: given a
figure, it becomes a check like any other.

### 6.5 The prestress floor

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

### 6.6 The ceiling

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
the figures in section 6.2, the briefed 36 mm drum, the EG23-G20 at 20 to 1 and
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

**And across the whole widened catalogue**, direct drive, no pulley, with the
worm efficiency taken at each ratio and the family's own `torque_margin`:

| drive | ratio | motor torque term | ceiling | bound by |
| --- | --- | --- | --- | --- |
| stepper NEMA 23, 3 N m | 20:1 planetary | 783 | **783** | motor torque |
| stepper NEMA 34, 4.3 N m | 20:1 planetary | 1123 | **1123** | motor torque |
| stepper NEMA 34, 9 N m | 20:1 planetary | 2350 | **1471** | turnbuckle |
| stepper NEMA 34, 12 N m | 50:1 planetary | 7500 | **1471** | turnbuckle |
| AC 0.75 kW, 1440 rpm | 20:1 worm | 1769 | **1471** | turnbuckle |
| AC 0.75 kW, 1440 rpm | 50:1 worm | 3316 | **1471** | turnbuckle |
| AC 0.75 kW, 1440 rpm | 100:1 worm | 4974 | **1471** | turnbuckle |
| AC 1.5 kW, 1440 rpm | 100:1 worm | 9948 | **1471** | turnbuckle |

Four things follow, and they are the reason this spec exists rather than a
larger motor being ordered.

**The motor is not the constraint, and a bigger one buys nothing.** Every row
from the 9 N m stepper upward returns 1471 N, and on a 50 Hz supply that is
every alternating current option in the catalogue without exception, including
the smallest at the lowest ratio. The 1.5 kW motor through a 100 to 1 worm
produces 9948 N of capability and still delivers 1471 N, because a turnbuckle
costing 3.79 is in the way. Widening the motor list without widening
the rope path would produce a chooser whose rows all read the same, correctly
and uselessly. That is why section 6.2 tiers the anchor chain, the rope and the
sheave as well.

**Adding the pulley makes the strong configuration worse.** With the 9 N m
motor the ceiling falls from 1471 N to 1214 N, because the moving block roughly
doubles the force through a sheave rated 1226 N while relieving a motor that
was never short of torque. The pulley earns its place only with a small motor:
it lifts the NEMA 23 from 783 N to 1214 N.

There is a hard ceiling of about 1.2 to 1.5 kN per cable that no motor or
gearbox choice moves, set by the hook and hook turnbuckle without a pulley and
by the sheave with one. If the demand from step A exceeds it, the answer is a
stub-end or larger turnbuckle and a heavier sheave, or more wires. No motor
will do it.

**Where the families genuinely differ is not torque.** It is positioning and
speed. Family A creeps and holds by holding current; family B needs an
inverter, an encoder and a software loop to do either, and runs at 54 to 271
mm/s of rope depending on the ratio. The chooser must therefore show the rope
speed and the required companion drive beside the ceiling, or family B looks
like a cheap way to buy torque that nothing needs.

These fourteen rows are exact and are used as the test fixture for section 6.6,
so an implementation that gets the mechanical advantage, the sheave resultant
or the family torque derivation wrong fails against published numbers rather
than against my arithmetic.

### 6.7 Fails or not

```
fails  when  prestress_floor > ceiling
```

and the binding part is the term that set the ceiling. Where the limit comes
from the net rather than the parts, the deviation exceeding the acceptance
line, `capacity_from_curve` reports `deviation` as the binding name, as it does
today.

### 6.8 Rope through the drum, and what the catalogue now affords

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

### 6.9 Moving between configurations

The chooser scores a list of configurations at once and returns a row for each:
the parts, the family, pass or fail, the ceiling and which part set it, the
margin as `ceiling / prestress_floor`, the resolution at the net from
`resolution_at_the_net`, the rope speed, the drum and travel checks, the
companion drive the family requires, and the total price of the priced lines.

The widened catalogue makes the full cross product large: ten motors, nine
gearboxes, two pulley choices, four ropes, four eye bolts and the turnbuckle
rungs multiply into the thousands. That is affordable only because of section
5.6: a row is arithmetic against the stored curve, microseconds each, so even
several thousand rows cost less than one solve. Had the sweep kept re-solving
the net, this widening would have been impossible rather than merely slow,
which is worth recording as the reason that refactor is in this spec and not
deferred.

Two things keep the table legible rather than vast. Configurations whose
motor and drive families disagree are never generated. And the rope path is
swept as whole named chains rather than as independent parts, since mixing an
M24 eye bolt with a 4 mm rope describes nothing anybody would build.

`trade_study.fronts` then marks the best on each of its three axes, accuracy,
simplicity and margin, so the three recommendations already implemented are
visible without a second mechanism for the same thing.

Rows whose price is a floor rather than a forecast are marked as such, because
the bill of materials has unpriced lines and a total that hides them would be a
lie by omission. Family B rows carry the inverter and the encoder in their
total, or they would undercut family A on price by omitting what they need.

## 7. Changes to the engine

Three changes, two to `src/tree_forest_compas/capacity.py` and one to
`src/tree_forest_compas/trade_study.py`. Every one must leave the existing
tests passing unchanged, and each is additive with a default that reproduces
today's behaviour exactly.

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
came from thousands of solves or one.

### 7.3 Resolution for a drive that has no microsteps

`resolution_at_the_net` multiplies `steps_per_revolution` by `microsteps`,
which describes a stepper and nothing else. A family B drive positions from an
encoder, so the quantity it needs is counts per revolution of the motor shaft,
however they arise.

The function gains an optional `counts_per_revolution=` argument. When given it
is used directly; when not, it falls back to
`steps_per_revolution * microsteps`, which is what every present caller does,
so the default is today's behaviour. `DRIVE_FIELDS` gains the new name so the
sweep can grid over it.

This is a one-line generalisation and it matters because without it the
accuracy front is meaningless for family B: every alternating current row would
be scored as though it microstepped.

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
- A configuration pairing a motor with a drive for a different family, naming
  both and saying which drives suit that motor. A CL57Y cannot run a
  three-phase motor and an inverter cannot run a stepper.
- A family C motor in any configuration, with the capacitor explanation from
  section 6.1 carried through, since the option is closed rather than missing.
- A wire whose angle to its eye bolt's axis exceeds 45 degrees, which is
  outside the published rating table. Guessing past the end of a load table is
  how a termination fails.
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

**The ceiling, against the worked tables.** All fourteen rows of section 6.6,
each asserting both the ceiling to the nearest newton and the name of the
binding part. Two rows matter most. The 9 N m motor with the pulley must return
1214 N bound by the sheave, lower than the same motor without it, so an
implementation that treats reeving as a free gain passes every other test and
fails this one. And the 1.5 kW motor through a 100 to 1 worm must return 1471 N
bound by the turnbuckle despite a motor term of 9948 N, which is the assertion
that the chain limit is being computed rather than the motor believed.

**The family torque derivation, at the right speed for the family.** From
`9550 * kw / rpm * 1000`: 0.75 kW at 1440 rpm gives 4974 N mm and 1.5 kW gives
9948 N mm for family B, while 1 HP at 1725 rpm gives 4130 N mm and 2 HP gives
8260 N mm for family C. A test asserts both bases, since using one speed for
both families is the mistake this is here to catch and it would pass any test
that checked only the arithmetic.

A family A motor's torque is taken as published with no such conversion, and a
test asserts that a stepper entry is never put through the power expression.

**The derating by family.** The same shaft torque yields different ceilings
under family A and family B, 0.5 against 0.8, and a test pins both so the
margins cannot be quietly unified.

**The worm efficiency follows the ratio.** A 100 to 1 worm is evaluated at 0.45
and a 20 to 1 at 0.80, not both at one figure, and a test asserts the ratio
selects the efficiency.

**The angled anchor rating.** A wire at 30 degrees to an M12 eye bolt's axis is
rated 2354 N, not 3334 N; the same wire at 2 degrees takes the axial figure;
and at 50 degrees it refuses. The chain limit with the hook and hook turnbuckle
present is 1471 N in all three cases, which is the point: the test must assert
the angle changed the eye bolt's own term and not merely the answer.

**Family mismatch.** A stepper with an inverter and a three-phase motor with a
CL57Y both refuse, naming the families.

**Resolution without microsteps.** `resolution_at_the_net` with
`counts_per_revolution` given returns the same value as the equivalent
`steps_per_revolution` and `microsteps` pair, and omitting it reproduces every
existing expected value unchanged.

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
2. **The turnbuckle ladder.** This is now the most important open item, because
   the turnbuckle is the binding part in almost every configuration, so the
   whole ceiling moves with it. The rig's part is rated 150 kg by its own
   supplier. Generic DIN 1480 tables found so far give figures up to three
   times higher for eye and eye and stub-end at the same thread, and they
   disagree with each other and with the supplier by too much to quote. Each
   rung must come from a supplier's own page for the exact configuration and
   material before the chooser's answers mean anything above 1471 N. Note that
   configuration may matter more than size: the hook is the weak element.
3. **The gearbox efficiencies.** The planetary figures, 0.94 and 0.90, and the
   whole worm ladder from 0.90 down to 0.45, are interpolated from a published
   band rather than taken from a model's datasheet. They move the torque
   ceiling directly, though as section 6.6 shows the torque ceiling is not what
   binds today.
4. **The family B nameplate torques**, computed from power and a nominal
   1440 rpm rather than read off a motor. The expression is standard and the
   speed is right for a four-pole machine on 50 Hz, but real full-load speeds
   vary by a few per cent between models and a nameplate should replace the
   figure. A motor's actual slip is the whole difference here.
5. **The encoder and the software loop for family B.** This spec names them as
   required companion parts and does not design them. Closing a position loop
   around an inverter is its own piece of work and it is not something the
   Octopus does with step and direction.
6. **The acceptable rate of movement at the net**, which is what would turn
   rope speed from a reported column into a check. Section 6.4 has the
   expression ready for a figure.
7. **ISO 4308-1's minimum D over d**, which is why the sheave ratio is reported
   without a verdict. One of the three unverified figures LEFTOVERS lists; the
   other two, the ACI 347 and BS 5975 deflection limits, bear on the acceptance
   line and are unchanged by this spec.
8. **The fleet angle**, which needs a layout dimension the catalogue does not
   carry.
9. **Whether the seven wires are enough.** Section 5.5 expects a residual
   deviation the wires cannot remove. If that residual exceeds the acceptance
   line on a real study, the answer is more wires or a different routing, and
   that is a design finding this spec is built to surface rather than one it
   can pre-empt.
