# Structural verification of imported vault geometry

Date: 2026-08-04
Branch: `feature/vscode-design-bench`
Status: design approved, ready for planning

## Why

The bench can now take a vault out of Grasshopper, describe it, check its
global equilibrium, tessellate it into blocks, and show all of it. What it
cannot do is answer the question an engineer asks next: **does it stand up,
and what does it need.**

Thrust network analysis answers a narrower question than it appears to. It
finds a surface in compression under one load case. It says nothing about
bending, nothing about what happens when the load changes, nothing about
deflection, and nothing about buckling, which is how thin shells actually
fail. A funicular surface can be in perfect equilibrium and still be
unbuildable.

This strand adds the analysis that answers those questions, and sizes the
tension cables when the answer is that the shell alone will not do.

## What was verified before designing

Every claim here was run, not recalled.

| Check | Result |
| --- | --- |
| OpenSees executable | Runs a Tcl script and returns. Installed from the Berkeley download at `OpenSees3.8.0/bin/OpenSees.exe` |
| Backend registration | `compas_fea2.set_backend("compas_fea2_opensees")` gives `BACKEND = compas_fea2_opensees` |
| End-to-end solve | A nine-node cantilever returns a tip deflection **0.9998 of `PL^3/3EI`**, with reactions summing to the applied load |
| Buckling by eigenvalue | Class exists, **implementation is a stub**: `OpenseesBucklingAnalysis.jobdata()` emits the bare token `buckling`, which is not valid Tcl |
| Buckling by arc length | `OpenseesStaticRiksStep` is fully implemented, with `integrator ArcLength` and control parameters |
| Materials | `ElasticIsotropic`, `Concrete`, `ConcreteSmearedCrack`, `ConcreteDamagedPlasticity`, `Timber`, `Steel` all present |
| Elements | `ShellElement`, `TrussElement`, `BeamElement`, `SolidSection`, `ShellSection` all present |

### Nine API details that cost time to find

None of these are documented upstream. The first four each produce a run
that **reports success and returns zeros**, which is far more dangerous than
a crash.

1. **`Node.loads` does not exist at the pinned commit, and must be shimmed.**
   `model/nodes.py` sets `self._loads` but leaves the public `loads`
   property commented out, while `problem/steps/step.py:117` calls
   `node.loads`. Applying any load a combination recognises therefore raises
   `AttributeError: 'OpenseesNode' object has no attribute 'loads'`. One
   property closes it: `Node.loads = property(lambda self: self._loads)`.
2. **The load case name must be `DL`, `SDL` or `LL`.** `LoadCombination.ULS()`
   carries `{"DL": 1.35, "SDL": 1.35, "LL": 1.35}`, and
   `LoadCombination.node_load` skips every load field whose case is not a key
   of that dict, without warning. A load case named anything else is silently
   discarded, the generated Tcl carries no `pattern` block at all, and
   OpenSees happily solves an unloaded model and reports
   `Analysis completed!`. Note that ULS also multiplies by 1.35, so a
   closed-form check must include the factor.
3. **Field outputs must be requested explicitly**, with
   `step.add_output(DisplacementFieldResults)` and
   `step.add_output(ReactionFieldResults)`. Without them the only recorder
   emitted is a dummy reaction one, the results database is written at zero
   bytes, and reading any field raises
   `sqlite3.OperationalError: no such table: u`.
4. **Never use `problem.analyse_and_extract()`.** It runs extraction twice
   and inserts every row twice, so a nine-node model returns eighteen
   results and reactions sum to exactly double the applied load. `max()`
   survives this; every sum is wrong. Use `problem.analyse(path=...)`
   followed by `problem.extract_results()`, which gives nine rows and the
   correct total.
5. `compas_fea2.set_backend()` is required. Importing the backend leaves
   `BACKENDS` empty.
6. The `.env` needs five keys, not one: `EXE`, `VERBOSE`, `POINT_OVERLAP`,
   `GLOBAL_TOLERANCE`, `PRECISION`. `compas_fea2` reads the last four with no
   fallback and calls `.lower()` on them, so a missing key is an
   `AttributeError` at import.
7. Nodal loads are `step.add_uniform_node_load(...)`, not `add_node_pattern`.
   A step also needs `step.combination`, or the job writer raises
   `AttributeError: 'NoneType' object has no attribute 'node_load'`.
8. `problem.analyse(path=...)` calls `input()` if the output directory
   already exists, which hangs a non-interactive run. Always analyse into a
   fresh directory.
9. **Node tags are not insertion order.** `Part` stores nodes in a set, so
   the first node added came out as tag 0 at x=1.5 while the node at the
   origin became tag 1. Map results back by node identity, never by index.
   `step.get_total_reaction()` is separately broken: it reads
   `self.steps_order` on a step, which does not exist.

`StaticRiksStep` imports from `compas_fea2.problem.steps`, not from
`compas_fea2.problem`, which does not re-export it.

### The imported geometry, and its residual

The current export is a three-legged vault, roughly 15.0 m by 20.3 m with a
7.0 m rise, 2521 vertices, 2400 faces, 4800 members, all in compression.

Its TNA solve does not close horizontally:

| | Trial 1 | Trial 2 |
| --- | --- | --- |
| `horizontal_iterations_run` | 600 | 2600 |
| `max_reciprocal_angle_deviation` | 4.81 deg | 3.02 deg |
| `global_force_error_norm` | 3.558 | 2.406 |

The residual tracks the reciprocal angle deviation almost linearly, and the
acceptance gate `horizontal_accept_degrees` is 5 in both. Closing it needs a
tighter gate, not only more iterations. That is being addressed separately.

**This matters here in exactly one place.** The shell model builds its own
loads and boundary conditions and is unaffected. The bar cross-check compares
FEA axial forces against TNA member forces, so its tolerance must accommodate
the TNA residual of the file under test. The check reads the residual from
the file's own `global_force_error_norm` diagnostic and sets its tolerance
from that, rather than hard-coding a number that a better solve would make
wrong.

## Decisions

| Question | Decision |
| --- | --- |
| Model type | Shell primary, with a bar network cross-check |
| Checks | Tension onset, stress utilisation, deflection, buckling |
| Buckling method | Arc-length collapse (`StaticRiksStep`), not eigenvalue |
| Materials | `ElasticIsotropic` first, for concrete and timber both |
| Cable sizing | Provisional, from the tension demand |
| Environment | Separate `.venv-fea`, exchanging JSON with the main bench |

## Architecture

### 1. A third environment, and why it cannot be merged

`compas_fea2` is pinned to commit `664ec20` (2026-06-16) because the OpenSees
backend was last pushed 2025-06-17 and imports `BeamSection`, which the core
removed on 2025-07-30. The main bench pins `numpy 2.0.2`, `scipy 1.13.1` and
`compas 2.15.1` to mirror the Rhino 8 environment. Pinning a mid-2025
compas_fea2 commit is not something that environment should inherit.

So the FEA work runs in `.venv-fea`, following the pattern already
established for coupled rigid-block analysis in `.venv-cra`. A new package
`src/ananke_fea/` imports only in that environment. `demo/_bootstrap.py`
gains `ensure_fea_venv`, matching the existing `ensure_cra_venv`.

Nothing in `src/ananke_equilibrium/` imports `compas_fea2`. The two sides
exchange COMPAS JSON on disk.

### 2. Modules

| Module | Responsibility |
| --- | --- |
| `ananke_fea/mesh.py` | Read a thrust surface from either export mode; remesh to an analysis target edge length |
| `ananke_fea/materials.py` | Named material and section presets for concrete and timber, with their sources |
| `ananke_fea/model.py` | Build a shell model: elements, thickness, material, boundary conditions from exported support node IDs |
| `ananke_fea/bars.py` | Build the truss model from the exported thrust members, for the cross-check |
| `ananke_fea/analyses.py` | The four analyses, each taking a built model and returning a result contract |
| `ananke_fea/results.py` | Extract displacements and stresses; write a JSON the main bench can read |
| `ananke_fea/cables.py` | Size a cable from a tension demand |

Each is independently testable. `model.py` and `bars.py` produce models
without solving; `analyses.py` solves without knowing how the model was
built; `results.py` reads results without knowing which analysis produced
them.

### 3. The pipeline

```text
Grasshopper export (COMPAS mode: thrust mesh; Contract mode: forces, supports)
    |
    +-- mesh.py       remesh to analysis density
    +-- model.py      ShellElements + thickness + material + BCs
    |                     |
    |                     +-- analyses.py  static, sweep, Riks
    |                     +-- results.py   displacements, stresses -> JSON
    |                                          |
    |                                          +-- cables.py  size where tension
    |
    +-- bars.py       TrussElements from the 4800 thrust members
                          |
                          +-- cross-check: FEA axial vs TNA member forces
```

The cross-check is the reason to build the bar model at all. If a truss model
of the thrust network, solved under the same loads, reproduces the TNA member
forces within the file's own residual, the FEA setup is trustworthy and the
shell result can be believed. If it does not, the fault is in the model
setup, not the vault. Without that check the shell numbers are unfalsifiable.

### 4. The four analyses

**Stress utilisation.** One static solve. Principal stresses per element
against the material's design strength, reported as a utilisation with the
peak and its location.

**Deflection.** From the same solve. Displacement field, peak magnitude, and
the governing span-over-deflection ratio.

**Tension onset.** A sweep of static solves over a rising load factor. For
each, whether any element reaches positive principal stress, and where. The
output is the factor at which tension first appears and the extent of the
tension region. This is the direct answer to whether cables are needed.

**Buckling.** `StaticRiksStep` arc-length, traced to the limit point, giving
a geometric-nonlinear collapse load factor. Arc-length needs per-model tuning
and can fail to converge. When it does not converge the analysis reports that
plainly and returns no collapse load. It does not report the last converged
increment as though it were the answer.

### 5. Materials

`ElasticIsotropic` for both concrete and timber to begin with, because a
linear elastic run is the one that can be checked by hand. Presets carry
their source and the assumptions behind them.

`ConcreteSmearedCrack` and `ConcreteDamagedPlasticity` are deliberately not
used yet. They change what "tension" means in the tension-onset check, and
they need calibration this project does not have. Adopting them without that
calibration would produce numbers that look more authoritative and are less
trustworthy.

Timber is orthotropic in reality. Modelling it as isotropic is conservative
in some directions and unconservative in others, and the preset says so.

### 6. Cable sizing

Where the tension-onset sweep finds tension, sum the tension resultant along
the affected edge or region, then report the required steel area for a given
grade and the equivalent diameter.

This is provisional sizing from a demand, in the same discipline as the
concrete sizing already in demo 8. It is not a verification: no anchorage, no
fatigue, no relaxation, no prestress losses, no connection design.

### 7. Results, and getting them back

`results.py` writes one JSON per analysis into the study directory, in a
shape the main bench's reader already understands: displacement and stress
fields keyed by node and element id, plus a summary block. The main bench can
then view and plot them without importing `compas_fea2`.

## Testing

| Test | Asserts |
| --- | --- |
| Cantilever closed form | Tip deflection matches `PL^3 / 3EI` within tolerance |
| Bar cross-check | Truss axial forces match TNA member forces within the file's own residual |
| Tension fixture | A shape known to require tension reports tension |
| Compression fixture | The funicular under its design load reports none |
| Riks non-convergence | A model that cannot converge reports that, and returns no collapse load |
| Environment guard | The FEA environment's pins have not moved |
| No cross-import | `src/ananke_equilibrium/` never imports `compas_fea2` |

The cantilever test is the one that proves the whole chain end to end against
an answer that is known independently of any of this code.

## Out of scope

Cracking and plasticity material models. Orthotropic timber. Dynamic and
seismic analysis. Staged construction. Connection design. Reinforcement
detailing. Code compliance checking of any kind. The tessellation UI, robotic
placement, and alternative fabrication methods, which are their own strands.

## Risks

**Arc-length convergence** is the only item with genuinely unknown size. If
buckling will not converge on this geometry, the other three checks still
ship and the buckling analysis reports its failure honestly.

**Mesh density** trades accuracy against solve time, and 2400 faces is
already substantial. The remesh target is a parameter, and the first task
should establish what density solves in reasonable time before the rest is
built on an assumption.

**Nothing here verifies a structure.** Every output is a demand or a
prediction from a model with stated assumptions. A vault that passes all four
checks is a vault worth engineering properly, not a vault that has been
engineered.
