# Studio Wave 4a: CRA Feasibility

The studio's staged runs answer how the shell deforms and what it carries
(FEA), but not the masonry question: does the assembly of discrete cast
pieces stand as rigid blocks, without tension, with real friction at the
joints, or does it slide or hinge apart? Coupled Rigid-block Analysis
answers that. This wave adds a per-study stands verdict and a per-stage
verdict beside every struck-now FEA solve, using compas_cra 0.4.0 in the
`.venv-cra` environment (Python 3.10, compas 2.15.1, pyomo), shelled from
the server exactly the way `solve_stage.py` is shelled to `.venv-fea`.

Decisions taken with Param on 2026-08-10: blocks are the studio's own
ring/wedge segments; CRA runs inside the existing staged run; friction is
fixed per material with stated provenance; the verdict shows as a badge
plus a HUD line plus the integrity pulse requiring both FEA and CRA to
pass.

## Global constraints (as every wave)

- No em dashes anywhere: code, comments, UI copy, commits, docs.
- The server never imports compas, numpy, scipy, compas_fea2 or ananke_fea
  outside the named solver scripts; `solve_cra.py` joins `solve_stage.py`
  in the guard test's exemption list, and `blocks.py` must be stdlib only.
- Metres and Newtons server-side; the UI formats.
- Python is canonical for anything mirrored in JS.
- Honest failures: a solver that did not run or did not converge reports
  itself as such; the UI never invents a verdict.

## Prerequisite: the IPOPT solver binary

compas_cra drives pyomo's `ipopt` solver. `.venv-cra` has compas_cra,
compas_assembly and pyomo installed, but IPOPT itself was never installed
(`SolverFactory("ipopt").available()` is False today), so nothing solves.

Setup, first task of the plan:

- Download the current 3.14.x win64 binary release of Ipopt from the
  COIN-OR GitHub releases page (github.com/coin-or/Ipopt/releases, the
  `win64` zip asset, about 15 MB).
- Extract `ipopt.exe` and the DLLs beside it into `.venv-cra\Scripts\`.
  The venv is git-ignored: nothing lands in the repository and nothing
  changes what Param pushes.
- `solve_cra.py` prepends its own interpreter's Scripts directory to PATH
  before creating the solver, so the binary is found without machine-wide
  configuration.
- Record the exact release URL, asset name and extraction steps in
  `docs/BENCH.md` so the environment is reproducible.
- Prove the install by solving one small upstream compas_cra sample (the
  cube example) in `.venv-cra` before anything builds on it.

## Block model: bench/studio/blocks.py

New pure module, stdlib only, imported by staging. It turns the study's
segmentation into closed rigid-block meshes:

- Input: the analysis mesh (contract vertices and quad faces), the
  segment assignment from `segmentation.segment_faces`, the thickness in
  metres, and the support vertex ids from `geometry.support_ids`.
- Blocks are built on the analysis mesh, not the render mesh: it is the
  canonical surface, the solve is four times smaller, and adjacent blocks
  still share wall vertices exactly. The on-screen render mesh is a linear
  subdivision of the same surface, so the shapes agree to within the
  subdivision's rounding; the spec accepts that difference.
- Per segment: a closed quad mesh with a welded vertex list. Top vertices
  are the segment's analysis vertices offset +n * t/2 along area-weighted
  full-mesh vertex normals, bottom vertices offset -n * t/2, top faces in
  original winding, bottom faces reversed, and one wall quad per perimeter
  edge (an edge used by exactly one of the segment's faces). The offset
  and boundary maths mirror fields.js's `vertexNormals`,
  `segmentBoundaryEdges` and `extrudeSegment`; a node parity test feeds
  the same toy mesh to both sides and compares offset positions.
- A block is a support block when any of its faces contains a support
  vertex id.
- Output shape per block:
  `{"vertices": [[x, y, z], ...], "faces": [[i, ...], ...], "is_support": bool, "ring": r, "wedge": w}`.

## Solver script: bench/studio/solve_cra.py

CLI `python solve_cra.py <request.json> <out.json>`, runs only in
`.venv-cra`, named exemption in the studio guard test.

Request:

```json
{
  "blocks": [{"vertices": [], "faces": [], "is_support": false, "ring": 0, "wedge": 0}],
  "density": 2400.0,
  "mu": 0.6
}
```

Behaviour: build compas Meshes, assemble a `CRA_Assembly`, mark supports,
detect interfaces with `assembly_interfaces_numpy`, run `cra_solve` with
the given mu and density, self-weight only. The export's node loads stay
the FEA's business; the Data panel says so in the CRA section. The
verdict is scale-invariant in the weights (uniform scaling does not change
rigid-block feasibility), so the density is passed for completeness, not
calibration.

Response, always exit 0:

```json
{
  "stands": true,
  "status": "optimal",
  "message": "",
  "blocks": 25,
  "interfaces": 48,
  "mu": 0.6
}
```

- `stands` true: the solver found an equilibrium (status optimal).
- `stands` false: the solver proved infeasibility (the assembly cannot
  stand as rigid friction blocks).
- `stands` null: the solver did not run or crashed (IPOPT missing, pyomo
  error); `message` carries the reason, including a pointer to the
  BENCH.md setup when IPOPT is absent.
- Zero detected interfaces on a multi-block assembly is an error, not a
  verdict: `stands` null with a message, because a meaningless "stands"
  from unconnected blocks is worse than no answer.

## Staging integration

`staging.run_staging` gains a CRA step after each stage's FEA solve:

- The stage's placed rings (0..k) select the blocks; the request is
  written; a second subprocess runner, same shape as the existing
  `_subprocess_runner` but targeting `.venv-cra\Scripts\python.exe
  solve_cra.py`, executes it. Both runners stay injectable for tests.
- Each stage entry in the staging JSON gains a `"cra"` key holding the
  response verbatim. The staging document gains `"cra_mu"` at the top
  level recording what friction the run used; the UI reports the recorded
  value, never the current constant, so a later constant change cannot
  make an old cache lie.
- The final stage's CRA verdict is the whole-study verdict; no separate
  whole-vault solve exists.
- Progress messages extend the existing on_stage strings so the run
  status line shows CRA progress per stage.
- Runtime expectation, stated for honesty (measured on the real Trial 2
  export, not estimated): interface detection alone runs around half a
  minute per stage. The nonlinear IPOPT solve that follows has no such
  ceiling: it can take many minutes, or run past the 600 s subprocess
  timeout on larger stages, in which case the verdict is an honest null
  rather than a hang. Cached like everything else in the staging file.

Friction lives beside the densities:

```python
FRICTION = {
    "concrete": 0.6, "concrete-c50": 0.6,
    "concrete-sprayed": 0.6, "timber": 0.4,
}
```

Provenance, quoted in the Data panel: 0.6 is the EN 1992-1-1 clause 6.2.5
coefficient for a smooth precast concrete joint; 0.4 is a literature value
for dry timber-on-timber contact, stated as a literature value because
Eurocode 5 does not give one. A literal test pins the dict.

## UI

- Badge: a chip element near the legend showing the whole-study verdict
  from the loaded bundle's staging: green "CRA: stands (mu 0.60)", red
  "CRA: does not stand", grey "no CRA run yet" when staging or the cra key
  is absent, grey with the message when `stands` is null. Hidden only when
  no bundle is loaded.
- HUD: the stage block gains one line for the current stage: "CRA: stands"
  or "CRA: does not stand" or "CRA: not run (<message>)".
- Integrity pulse: green only when the current stage's FEA solve converged
  AND its CRA verdict is `stands` true; red otherwise. A missing CRA entry
  (old cache) counts as not-passing for the pulse but the HUD line says
  "CRA: not run" so the red is explainable.
- Data panel: a CRA section with the final verdict, the recorded mu and
  its provenance sentence, and block and interface counts.

## Testing

- `tests/studio/test_blocks.py` (main venv): closed prisms (every edge
  shared by exactly two faces), vertex and face counts for a toy
  two-segment mesh, offset positions, winding, support marking, ring and
  wedge tags.
- Node parity: feed the same toy mesh to fields.js (`vertexNormals`,
  `extrudeSegment`) and `blocks.py`, compare offset vertex positions;
  skips cleanly without node, like tests/studio/test_fields.py.
- `tests/studio/test_staging.py` extensions with a fake CRA runner: stage
  entries carry `cra`, the document carries `cra_mu`, progress strings
  include CRA, the FRICTION literal pin.
- `tests/cra/test_solve_cra.py`, run with `.venv-cra`: a two-block stack
  that stands (verdict true), a request with IPOPT removed from PATH
  (verdict null with the setup pointer), zero-interface rejection.
  Skipif-guarded on IPOPT availability so the suite degrades honestly on
  a machine without the binary.
- Static pins in tests/studio/test_static.py: badge element ids, the HUD
  CRA line, the pulse condition referencing both verdicts, the Data panel
  CRA section.
- Guard test: `solve_cra.py` joins the exemption list; `blocks.py` must
  import cleanly in the main venv with no third-party imports.

## Out of scope

- A friction slider (fixed per material now; the cache records mu so a
  slider can come later without lying about old runs).
- External loads in the CRA model (self-weight only, stated in the UI).
- The hex masonry tessellation from demo 04 (the studio's segments are
  the blocks).
- Penalty-solve diagnostics (how badly it fails); stands or not is the
  wave's contract.
- The rest of wave 4: mould clustering, concrete vs timber A/B, robot
  choreography. Each gets its own spec.

## Engineering pass, 2026-08-10

The first real staged run showed the wave was honest but inert: warped wall
quads cost 16 of 17 joints, and the solve did not finish. Measured fixes,
recorded in .superpowers/sdd/2026-08-10-studio-cra-feasibility/cra-diagnostics.md:

- Wall faces are planar triangle pairs split on a shared-edge diagonal, so
  both blocks of a joint present matching coplanar faces. Detection then
  recovers every detectable joint at a tight fixed tmax of 1e-6. Note that
  compas_cra skips pairs where both blocks are supports, so the detectable
  joint count sits below the geometric one.
- The solver is cra_penalty_solve, not cra_solve: about a second against
  21 s at 8 blocks, and decisive where the plain form only reaches
  maxIterations. Upstream makes the same switch for its larger examples.
- The CRA model is coarsened by merging neighbouring wedges until it fits
  CRA_BLOCK_BUDGET (8 blocks), because both solvers blow a 300 s cap at 10.
  Rings are never merged, so stages stay whole. The document records
  cra_wedge_factor and the Data panel says when the verdict describes a
  coarser assembly than the drawing. A coarser model is optimistic on two
  counts: fewer joints means fewer ways to hinge, and a merged piece counts
  as supported if any of its merged wedges touches a support vertex. Both
  sources of optimism are disclosed in the Data panel so the verdict is
  labelled rather than quietly substituted.
- When a stage has more occupied rings than CRA_BLOCK_BUDGET, wedge merging
  cannot reduce the block count below one per ring, so the stage cannot be
  made affordable. Such stages get an honest null verdict with a message
  directing the user to lower the ring count, rather than hanging on a 300 s
  timeout that would reach the same null.
