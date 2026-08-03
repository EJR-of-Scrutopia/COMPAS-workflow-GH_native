# Component surface redesign: one spine, two solvers, one display

Status: agreed in discussion 2026-08-03, awaiting spec review.
Scope: the Grasshopper canvas surface only. No Rhino-side plugin work, no
Rhino toolbar, no changes to the Rhino Python environment. The worker
protocol changes only where the unified result type requires it.

## 1. Why

Field testing the v0.2 surface against a real vault pattern surfaced the
problems all at once:

- Two parallel stacks register geometry, bind supports, and take loads
  (`Network`/`Support Set`/`Load Case`/`Equilibrium Problem` beside
  `TNA Pattern`/`TNA Supports`), so every job on the canvas has two names
  and neither is obviously the right one.
- Eight components touch display and query. Nothing draws until the right
  one is found and wired, and then everything draws at once with vectors
  scaled for no particular model.
- Load definition takes ten inputs to say "1 kN downwards".
- Almost every port is nicknamed `P`, so the data flow is only legible to
  someone who already knows it.
- `TNA Reciprocal` is a required wiring step whose purpose is invisible on
  the canvas.
- Solver settings (`TNA Control`) could not even reach the staged solver
  until 2026-08-03 (`5e59d14`); the settings component fed only the legacy
  one-shot path.

The decisions below were agreed: one shared spine with solvers branching
off it; one Display plus one Deconstruct; light previews on stages with the
full picture on Display; redundant components deleted outright.

## 2. Grounding in COMPAS's own architecture

The redesign copies three structural ideas straight from COMPAS, so the
plugin gets more COMPAS-shaped as it gets simpler:

**One datastructure, many algorithms.** COMPAS centres on shared
datastructures (`Mesh`, `Graph`) that many algorithms consume. The spine is
exactly that: one registered `Problem` that FD, TNA, and later AGS all
solve. The current design where each solver builds its own input is the
anti-pattern COMPAS exists to avoid.

**Scene separated from data.** COMPAS 2 draws through `compas.scene`
(SceneObjects wrap datastructures for a CAD context) rather than through
methods on the data itself. Display and Deconstruct mirror this: results
hold no drawing, drawing holds no solving.

**JSON as the interop currency.** Every COMPAS object round-trips through
`compas.data` JSON, which is how COMPAS moves between Rhino, Blender, the
viewer, and other software. The worker protocol already speaks JSON-safe
contracts end to end, so exposing that as a canvas output costs almost
nothing and buys the interop route Param asked for.

Family names for tabs also come from COMPAS's own taxonomy (Form Finding,
Masonry, Engineering, Fabrication), so a tab answers "which package family
backs this" without a lookup.

## 3. The surface

Twelve components replace twenty. Every stage takes one primary typed
object and returns it enriched, so the wire is the workflow.

```text
01 Model
  Pattern      Geometry, Mode, Tol            -> PAT  registered pattern
  Supports     PAT, Points, Tol               -> SUP  anchored pattern
  Loads        SUP, Vector, NodeIDs, Factor   -> PRB  problem

02 Form Finding
  TNA Relax    PRB, ForceDensity, Sag%        -> RLX  relaxed state
  TNA Solve    RLX, Mode, Value, CTL          -> RES  result
  FD Solve     PRB, ForceDensity, CTL         -> RES  result (same type)
  Control      Alpha, HIter, VIter, Tol       -> CTL  solver settings

03 Visualise
  Display      RES, STY, Elements, Metric,
               Weight, VectorScale, Gap       -> viewport + ThrustMesh,
                                                 Form/Force/Load/Reaction
                                                 lines, Report
  Style        Preset, LineWeights, Colours   -> STY  display preset
  Deconstruct  RES                            -> every data stream

07 Delivery
  Export       RES or any typed object,
               Format (contract | compas),
               Path (optional)                -> JSON text, written file path

90 System
  Backend Health                              -> ready, packages,
                                                 capabilities, report
```

The tab sequence is deliberately renumbered and compacted from the current
constants (which read 04/06/07/08 with gaps): `03 Graphic Statics`
disappears because its display half folds into Display and a future AGS
solver belongs in `02 Form Finding`, which is where COMPAS classifies
`compas_ags` anyway; `05 Visualisation` becomes `03 Visualise`; the
reserved families close up to `04 Masonry` (compas_dem, compas_assembly,
compas_cra), `05 Engineering` (compas_fea2 plus a backend), and
`06 Fabrication` (compas_fab, compas_robots), with Delivery at `07`.
Subcategory strings are display grouping only, so renumbering breaks
nothing. The tab-family-capability-extra alignment from the taxonomy
document survives unchanged; `pyproject.toml` extras keep their names.

### Port naming rule

The all-`P` problem is solved by one rule: **a nickname names the type, not
the word "input"**. `PAT`, `SUP`, `PRB`, `RLX`, `RES`, `CTL`, `STY` appear
on exactly the ports that carry those types, on both sides of every wire.
A wire is then self-describing: `SUP -> SUP` connects, `PAT -> RES` visibly
does not. Full names stay descriptive ("Anchored Pattern", not "P").

### Loads, cut to the basic case

Inputs: the anchored pattern, one load vector defaulting to `(0, 0, -1)`,
optional node IDs to restrict it, and a factor. Units are metadata carried
on the Pattern from registration, not re-stated per component. Named load
cases, distributions, and combination logic return later as a separate
component when there is a reason; the contract keeps the fields so nothing
is repainted then.

### Solvers

`TNA Relax` keeps the boundary-sag stage as its own component because it is
a design decision with its own feedback (openings found, sag achieved), not
a solver setting. `TNA Solve` carries Mode and Value on the component
because target height or force scale is a design decision; everything
numerical (alpha, iterations, tolerance) lives on `Control`, shared by both
solvers. The one-shot `TNA Solve` compatibility macro is deleted with the
rest.

Both solvers return the **same Result type**. FD results simply have no
reciprocal block; Display greys the force-diagram element and says why
rather than erroring.

### Display

One component draws everything, from either solver:

- `Elements` multi-select: form, thrust, force diagram, loads, reactions,
  residuals. Value list offered at the socket, QS style.
- `Metric` colours members by q, F, H, or none.
- Thrust is output as a **real shaded mesh**, not wireframe, alongside the
  line streams for drawing operations.
- Vector and weight scales **auto-fit to the model's bounding box** so
  arrows start proportionate; explicit values override.
- Stages draw a light hint of their own state (pattern edges, anchor dots,
  relaxed boundary) so progress is visible before Display is wired;
  Display draws the full styled picture. Preview toggles respect
  Grasshopper's own per-component preview switch.

`Deconstruct` emits the data: thrust mesh, member lines, q/H/F aligned
lists, force states, node and edge IDs, supports, loads, reactions,
residuals, diagnostics. It replaces `TNA Geometry`, `TNA Members`,
`TNA Actions`, and `Result Breakdown` in one component with grouped,
properly named outputs.

**Display is a renderer registry, not one picture.** Each COMPAS method has
a canonical diagram language (FD a force-scaled network with action
vectors, TNA plan form plus reciprocal force diagram plus lifted thrust,
AGS a side-by-side reciprocal pair, 3GS polyhedral cells), and the
legibility of a result lives in that language. Display therefore renders
per diagram kind carried by the Result, exactly as `compas.scene` keys one
SceneObject per data type, and it never homogenises methods into one
generic drawing. When a future solver arrives, its Result carries its
diagram kinds and Display gains a renderer for them; the component count
stays one while the representations stay method-true. The packages' own
Rhino scene objects cannot be reused directly because COMPAS objects live
in the worker process, which is the same trade RhinoVault makes with its
own display conduits.

### Export

The contracts crossing the worker boundary are already JSON. `Export`
serialises any typed object two ways: `contract` (this plugin's versioned
schema, stable for round-tripping between definitions and external tools)
and `compas` (native `compas.data` JSON of the form and force diagrams and
thrust mesh, produced by a small new worker command, rebuildable into real
COMPAS objects in any Python). With a path supplied it writes the file;
otherwise it just emits text. This is the interop output and the first
resident of `07 Delivery`.

## 4. Lessons taken from QS Intelligence

- **Value lists at the socket**, populated, token-only rows. Already ported
  at the base-class level; every new enum input uses it.
- **Quiet canvas.** Drawing belongs to specific components and nothing
  forces it. Solvers compute; Display shows.
- **Vocabulary follows the source.** Element and metric lists are offered
  from the component's own vocabulary, not typed from memory.
- **Distinct nicknames make flow legible.** Their components read as
  sentences on the canvas; the type-nickname rule above is the same idea.

## 5. Removed components

Deleted outright, per decision (chosen over the versioning policy's
legacy-hide; the plugin is pre-release with one user):

`Network`, `Support Set`, `Load Case`, `Equilibrium Problem`,
`FD Settings`, `TNA Pattern`, `TNA Supports`, `TNA Relax + Boundaries`,
`TNA Equilibrium`, `TNA Control`, `TNA Solve` (one-shot),
`TNA Reciprocal`, `Graphic Diagram Display`, `Diagram Style`,
`Equilibrium Preview`, `TNA Geometry`, `TNA Members`, `TNA Actions`,
`Result Breakdown`.

**Accepted consequence:** every saved definition using them loses those
components on open. Definitions worth keeping should be saved off before
the cutover. GUIDs of deleted components are recorded in the manifest for
the archaeology case. `Backend Health` survives unchanged. The
`plugin/legacy_component_scripts/` folder (pasteable Python components) is
untouched; it is reference material, not part of the compiled plugin.

## 6. How later families connect

The enriched-object chain is the connection ideal for everything that
follows. Each future family consumes a typed object from an earlier stage
and returns its own:

```text
RES -> Tessellate (04)      -> BLK blocks + interfaces   [compas_dem]
BLK -> Assembly (04)        -> ASM contact assembly      [compas_assembly]
ASM -> Stability (04)       -> stage-k equilibrium,
                               formwork reaction history [compas_cra]
ASM -> Sequence (06)        -> ordered placement targets
Seq -> IK (06)              -> joint configurations      [compas_fab]
RES/ASM -> Model, IFC (07)  -> compas_model / compas_ifc objects
```

The rules that make this composable, and which every new component must
follow:

1. One primary typed input, one primary typed output. Settings objects are
   the only fan-in.
2. The output carries its inputs' provenance (the Result keeps its Problem;
   the Assembly keeps its Result), so Deconstruct and Export work at any
   depth without re-wiring upstream.
3. A family's components appear only when its capability flag is true, and
   fail with the missing-package message otherwise. Backend Health stays
   the single explainer.
4. Solved quantities are demands, never capacities; no downstream family
   turns an equilibrium result into a verified structure by relabelling.

## 7. Contracts and worker

- New `PatternDto`, `AnchoredPatternDto`, `ProblemDto` wrap the existing
  topology/support/load payloads rather than reinventing them.
- `TnaResultDto` and `EquilibriumResultDto` merge into one `ResultDto`
  with an optional reciprocal block. This is the one genuinely breaking
  contract change, and it is what makes single Display/Deconstruct
  possible.
- Worker commands keep their shape: `tna.prepare` backs TNA Relax,
  `tna.solve` and `fd.solve` back the solvers and now return the unified
  result. One new command, `export.compas`, produces native COMPAS JSON
  for Export.
- Python solver core (`tree_forest_compas`) is untouched.

## 8. Testing

- Contract round-trip tests for the new DTOs and the unified Result.
- Worker tests: each command against the unified result schema, plus
  `export.compas` output rebuilding into COMPAS objects in the test
  environment.
- The capability-family and value-list behaviours keep their existing
  tests.
- C# builds clean with zero warnings; the native smoke project exercises
  component instantiation so port registrations are checked off-canvas.
- Manual canvas pass on the vault pattern that drove this redesign:
  register, anchor, load, relax, solve at raised iterations, Display with
  auto-scaled vectors, Deconstruct, Export both formats.

## 9. Risks and mitigations

- **Deleting breaks saved files.** Accepted by decision; mitigation is
  saving off definitions before cutover and recording old GUIDs.
- **Unified Result hides solver differences.** Mitigated by the optional
  reciprocal block being explicit, and Display saying "no force diagram in
  an FD result" instead of drawing nothing silently.
- **Auto-fit scales surprise power users.** Explicit scale inputs always
  override; the report states the fitted factor.
- **Radial convergence remains slow.** Not a surface problem; the Control
  wiring fix plus the reciprocity-angle diagnostic are the instrument.
  Display's report surfaces both numbers so non-convergence is visible at
  the point of looking.
