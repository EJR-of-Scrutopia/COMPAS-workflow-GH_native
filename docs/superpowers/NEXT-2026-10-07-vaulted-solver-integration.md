# Vaulted and the staged solve: what to build next

Written 7 October 2026, immediately before a conversation compaction, so it is
deliberately self-contained. It records what was established about the workflow,
what the candidate asked for, and what is already there to build on. Nothing
here has been designed or planned yet: the next session should brainstorm it
properly before writing code.

## 1. Where the engine is

Committed on `feature/studio-finish`, pushed to `origin/feature/studio-finish`.
Nineteen commits of solver plus one fix, suite 1097 passed and 5 skipped.

| Module | What it answers |
| --- | --- |
| `src/tree_forest_compas/rest_length.py` | the elastic relation between a reeled length and a force |
| `src/tree_forest_compas/prescribed.py` | given rest lengths, where the net sits and what each cable carries; and the reverse, plus the reel command between two states |
| `src/tree_forest_compas/hold.py` | given a target shape and a load, the tension that holds it; and the correction to reel from measured marker positions, with the residual it cannot remove |
| `src/tree_forest_compas/falsework.py` | what the timber falsework this machine replaces would itself deflect, which is the acceptance line |
| `src/tree_forest_compas/staged_solve.py` | walks a build sequence and produces the register rows |
| `src/tree_forest_compas/register.py` | the one file a staged run writes |
| `src/tree_forest_compas/capacity.py` | what a given mechanism can hold and which constraint stops it first |
| `src/tree_forest_compas/trade_study.py` | sweeps the mechanism choices and reports three fronts |
| `scripts/trade_study.py` | the command line over the sweep |

Everything is newtons and millimetres. What the branch leaves open is in
`docs/superpowers/LEFTOVERS-2026-10-06-prescribed-length-staged-solve.md`, which
also lists the follow-on work and three unverified figures to settle before
anything is ordered.

Two worked runs were done by hand this session and both behaved. The second is
the one that matters: you give the shape you want and the load on it, and the
solver returns the tension needed and the rest length to reel each cable to,
verified by commanding those lengths and landing on the asked-for geometry to
three decimal places. You never supply a "before" shape; the machine's before is
simply where its drums already are.

## 2. The workflow, as established by reading the actual files

The Grasshopper export writes four files per study into
`bench/demo/upload from grasshopper/`: `-compas.json`, `-contract.json`,
`-frames.json` and `-tessellation.json`.

`-contract.json` is the one the engine needs, and it already carries almost
everything. Checked against "Aramdillo style":

- `equilibrium.vertices`, 801 nodes with x, y, z
- `equilibrium.edges`, 2253 edges as u and v
- `problem.anchored.anchorNodeIds`, 34 anchors
- `equilibrium.loads`, one vector per node
- `equilibrium.forceDensities` and `memberForces`, plus reactions and residuals
- `mappings` tying source, form, force and equilibrium ids together

Three conversions the adapter must make, each silent if missed:

1. **The geometry is in metres.** That file spans 15.9 m with a 3.5 m rise. The
   engine is millimetres and its own guard refuses a geometry that small,
   correctly.
2. **The loads are tributary areas, not forces.** `problem.load` says
   `distribution: tributary_area`, `baseVector (0,0,-1)`, `factor 1`, and the
   per-node values sum to 125.4, which is the surface area in square metres.
   Multiplying by the real areal load from T3 turns them into newtons. This is
   the clean seam where the tile density enters.
3. **The exported force densities are negative: it is a compression thrust
   network**, the finished vault, not the cable net. The engine is tension only
   by design. The adapter must take the geometry and the loads and let the
   engine compute the net's own tension state. Same surface, opposite force.

**The cable-to-node mapping stays in the mechanism document.** Ruled by the
candidate on 7 October: each wire in `bench.mechanism/1` carries a `net_vertex`
naming the vertex it pulls, and re-exporting it when trying a different
mechanism is accepted. The alternatives considered and rejected were a separate
small export from Grasshopper, and choosing the nodes inside Vaulted.

**A wire needs no new physics.** It is another cable: one end at a net vertex,
the other at a fixed point on the frame, with a rest length the drum commands.
So the model is the net's own members with fixed rest lengths, plus one edge per
wire whose rest length is commanded, plus the anchors. The engine already solves
that unchanged.

## 3. What Vaulted already has, and should not be rebuilt

- `bench/studio/staging.py`, `stage_plan`: one stage per course, rim to crown,
  cumulative, walking the courses actually present in the cut. That is the
  tile-ring time axis the engine needs, already written and already careful
  about sparse course numbering.
- `bench/studio/solve_stage.py`: a staged solve reporting `self_weight_newtons`
  against a resolved density, with displacements, stresses and peak tension and
  compression. So the weight of the placed skin at each stage is already a
  number the app computes.
- The live graphs, the share-of-placed-weight model and the prestress dial.

What that existing solve answers is whether the vault stands once struck. What
it does not answer, and what the new engine can, is what the net must do to hold
the shape while the courses are being laid.

## 4. The one piece of data that does not exist yet

**The load at each net node, at each stage.** The contract gives tributary areas
for the whole net at once; the staging plan gives which faces are placed at each
stage; nobody produces the product. That single array is what the engine eats,
and everything below comes out of it. It is a mapping rather than new physics,
since the tessellation already knows which faces belong to which course and the
contract already knows each node's tributary area.

Build this first. Nothing else can be tested without it.

## 5. What the candidate asked for, 7 October

In his words, reordered only to group them:

**Numbers the system must report**

1. The maximum prestress that will be required given the load, **and a ceiling**.
2. Whether it fails or not.
3. How much wire has to be extended or reeled through.

**Choices the system must let him make**

4. Select between different motors.
5. Select pulley or no pulley, so he knows whether the motors can handle it.
6. Select the reel size.
7. A way to move through different configurations and settle on one he is happy
   with.

**What he must be able to see**

8. The net coloured by tension, visually.
9. The readout as numbers on the parts of the system themselves.

**What must come out at the end**

10. A diagram of the components.
11. A spreadsheet.
12. A data sheet.

### How that maps onto what exists

| Asked for | State |
| --- | --- |
| prestress required, and a ceiling | the floor and ceiling were specified but are among the register columns the plan omitted; see LEFTOVERS item 3. The ceiling logic exists inside `capacity.py` as the rope, anchor and torque limits |
| fails or not | `capacity_of` returns the binding constraint by name; the register carries `within_acceptance` |
| wire to extend or reel through | `reel_command` per stage per cable exists; turns at the drum is a missing register column |
| choose motors, pulley, reel size | `Mechanism` plus `sweep` and `fronts` already sweep exactly these |
| moving through configurations | the sweep produces the feasible set with three fronts; the chooser over it is new |
| net coloured by tension | new display, but the per-stage tensions come straight from the register |
| numbers on the parts | new display |
| component diagram, spreadsheet, data sheet | all new, and all downstream of the register plus the chosen mechanism |

Three of the twelve are already computed, four are a thin layer over the sweep,
and five are genuinely new work in the app.

## 6. Open questions for the next session

1. Which display comes first. He named the net coloured by tension and the
   numbers on the parts; the deviation view and the graph over the build were
   also offered and not ruled on.
2. Whether the configuration chooser drives a live sweep or reads a sweep run
   earlier. A sweep currently re-solves every grid row, about half a second each,
   which LEFTOVERS flags as worth caching before any interactive use.
3. What the data sheet is for: a supervisor, a supplier, or the thesis. That
   decides its shape more than anything else.
4. The prestress ceiling needs the rope, the anchor and the motor to be chosen,
   so the ceiling and the chooser are the same feature seen from two ends.

## 7. Suggested order

1. The per-stage per-node load array, in the studio, from the tessellation and
   the contract. Nothing works without it.
2. A studio runner that calls `run_stages` and writes the register, driven by the
   existing `stage_plan`.
3. The register gains the columns the spec asked for and the plan omitted: turns
   at the drum, lead tension, drum torque, motor torque, the prestress floor and
   ceiling, the slack flag, and the per-node block.
4. The net coloured by tension, and the numbers on the parts.
5. The configuration chooser over the sweep, with caching.
6. The three exports: diagram, spreadsheet, data sheet.

Steps 1 to 3 are the data formation he asked for first. Steps 4 to 6 are what he
sees and takes away.
