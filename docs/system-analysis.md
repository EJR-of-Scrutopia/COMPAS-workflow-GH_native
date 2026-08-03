# System analysis: what this project is, and why it is shaped this way

This document is the orientation read. It covers the layered architecture as
actually built, the design intent behind the separation of layers, the role
graphic statics plays as a design-finding mechanism rather than a drawing
style, and where the project sits inside the wider COMPAS ecosystem.

It is written against the code in this repository, not against an aspiration.
Where something is roadmap rather than built, it says so.

## 1. The two lineages in this repository

The project has two generations of the same idea, and both are here on purpose.

**The script layer** (`plugin/legacy_component_scripts/`, `src/tree_forest_compas/`).
Eight Grasshopper Python 3 components pasted into Rhino 8, each importing a
Rhino-free solver core. This is the working prototype: it is what established
the workflow, and the TNA path in it still runs.

**The native layer** (`plugin/native_v02/`, `src/ananke_equilibrium/`).
Compiled C#/.NET 8 Grasshopper components talking to one persistent hidden
CPython worker over versioned JSON contracts. RhinoCommon, Grasshopper, live
Python objects and live COMPAS objects never cross the process boundary.

The native layer is the direction of travel. The script layer is retained
because saved Grasshopper definitions still resolve against it, and because the
solver core underneath both is the same tested code.

The single most important structural decision is that **the solver core has no
Rhino imports at all**. `src/tree_forest_compas/{tna,fd,ags,graphic_statics,
structural}.py` are pure Python plus numpy plus COMPAS. That is what makes the
core testable headlessly (96 tests run in about one second with no Rhino in
sight), reusable from a worker process, and portable to a different CAD front
end later.

## 2. Design intent: the layers refuse to lie to each other

The `WORKFLOW.md` opening line states the governing rule: "a clustering or
Steiner operation is not silently treated as structural equilibrium, and an
equilibrium result is not silently treated as a verified building model."

Almost every unusual decision in this codebase follows from that one sentence.

- `CarriedVerticalLoad` was renamed from `FBR` precisely because the old name
  implied solved force. It is a tributary quantity, design metadata, and the
  code says so in several places.
- Degree-three 120 degree claims must come from the Steiner angle output, not
  from tributary load values, because a weighted Fermat problem does not in
  general give three equal angles.
- Self-weight through the `density` parameter is *refused* rather than
  approximated. In compas_tna 0.7.0 the `LoadUpdater` adds positive self-weight
  to `pz` while `FormDiagram.vertex_selfweight` reports it with the opposite
  sign, and the final effective load array is never written back to the form.
  Rather than ship a silently wrong signed load field, the adapter requires
  `Density=0` and makes you discretise self-weight into explicit negative nodal
  `Pz`. This is a good instinct and worth keeping.
- Unimplemented pattern modes (`Surface`, `Grid`, `Triangulation`, `Skeleton`)
  appear in the value list and *fail with an actionable error* instead of
  generating substitute geometry.
- `Backend Health` reporting that a package is installed is explicitly not a
  claim that the corresponding workflow exists or has been verified.

The same discipline separates the two downstream contracts. `StructuralBundle`
is the small active-topology contract: solved coordinates, active connectivity,
signed axial forces, supports, units. `StructuralAnalysisCase` is the
provenance object, and it additionally preserves every source vertex and member
mapping including the ones TNA boundary conditioning *removed*. A source edge
mapped to `None` is not a solved member, and the case records that rather than
quietly dropping it.

This matters more than it first appears. TNA's `update_boundaries()` genuinely
deletes registered vertices and edges. In the boundary-supported four by four
grid, four source vertices and sixteen source edges disappear. A workflow that
did not track that would hand IFC a member list that silently disagrees with the
model the designer drew.

## 3. Graphic statics as a design-finding mechanism

The reason graphic statics is load-bearing here, rather than decorative, is
that the force diagram is an *input surface* for design, not a report.

In a reciprocal pair, form and force are dual. Every edge in the form diagram
has a corresponding edge in the force diagram, parallel to it, whose length is
the magnitude of the force in that member. Change the force diagram and the
form must change to stay in equilibrium. That is the design-finding move: you
manipulate forces directly and read back the geometry that carries them, rather
than drawing geometry and asking afterwards what it costs.

TNA is the three-dimensional case of this. The horizontal projection of a
thrust network and its force diagram are a reciprocal planar pair; the vertical
solve then lifts the network to a height that satisfies vertical equilibrium.
So the plan topology encodes the possible force paths, and the designer's real
decision is the pattern, not the surface. `WORKFLOW.md` is blunt about this:
"TNA does not infer the best structural segmentation from an arbitrary surface.
The pattern encodes the possible force paths, so topology remains a design
decision." Subdividing a line only for visual smoothness adds variables without
improving force flow.

### The four views are not interchangeable

This is the part most easily got wrong, and the codebase is careful about it:

1. **FD local cells** (`FDVisualize`). Independent nodal closure polygons. A
   diagnostic, one per joint. A loaded degree-two catenary node necessarily
   gives a triangle: two member forces and one load.
2. **FD stitched reciprocal** (`FDGlobalGraphicStatics`). One global diagram
   for a connected planar *acyclic* FD graph, built by cyclically ordering each
   nodal cell and gluing the two equal and opposite copies of every shared
   member side. A serial chain specialises to the classical common pole and
   cumulative load line.
3. **AGS reciprocal**. The mesh dual of a complete planar form graph, which is
   the right general representation once the topology has cycles (a canopy or
   truss).
4. **TNA reciprocal**. The global horizontal force diagram dual to a faced
   compression pattern.

`graphic_statics.py` enforces the boundaries rather than blurring them: cyclic
networks are rejected with a routing message to AGS, disconnected trees are
declared separate equilibrium systems needing separate diagrams, and networks
that do not lie in the chosen plane are refused outright.

Two refusals in particular show the intent:

- **The triangle is detected, never fitted.** Under parallel loads the exact
  external-force boundary of a serial chain simplifies to the familiar left
  reaction, total load, right reaction triangle. The code detects that from the
  boundary loop and checks the load line actually fits inside it. It does not
  draw a triangle around unrelated local polygons to make the picture look
  canonical.
- **Degeneracy is reported, not hidden.** A bare binary tree with one root
  reaction and parallel vertical tip loads has a degenerate pin-jointed
  solution: the terminal members must align with their loads and the reciprocal
  collapses toward a line. The code computes the force-space dimension and warns
  when it drops below two, then tells you what is actually needed (a crown or
  canopy chord, another reaction path, or a bending analysis). It does not
  invent the canopy silently.

And the honest limit, stated in `WORKFLOW.md`: a spatial tree has no directly
drawable two-dimensional reciprocal without choosing a real plane, slice or
projection whose equilibrium stays in that plane. Never discard out-of-plane
components merely to get a clean drawing.

## 4. The wider COMPAS ecosystem

COMPAS is a Python framework for computational research in architecture,
engineering and digital fabrication. The core gives datastructures (mesh, graph,
volmesh), geometry, linear algebra and serialisation, plus CAD integration for
Rhino/Grasshopper and Blender. Everything else is an extension package with its
own release cycle, which is why the pinning discipline in this repository
matters so much.

**Form finding and graphic statics** (mostly Block Research Group at ETH
Zurich, which is the lineage this project draws on):

| Package | Role |
| --- | --- |
| `compas_tna` | Thrust Network Analysis: funicular compression networks under vertical loads. Used here. |
| `compas_ags` | Algebraic graphic statics for 2D structures. Used here. |
| `compas_fd` | Force density method, constrained form finding. Used here. |
| `compas_dr` | Dynamic relaxation, an alternative constrained form finder. |
| `compas_3gs` | Three-dimensional graphic statics. Conceptually the home for the spatial reciprocal this project declines to fake, but dormant since December 2021 and still on the COMPAS 1.x line. See [the suite adoption map](compas-suite-adoption.md). |
| `compas_tno` | Thrust network *optimisation*: admissible thrust networks in vaulted masonry. |
| `compas_bender` | Form finding including bending, not just axial action. |
| `compas-RV` / `compas-RV3` | RhinoVault: the Rhino plugin form of the TNA workflow. This repository's boundary-opening relaxation is adapted from compas-RV's Pattern workflow, credited in `THIRD_PARTY_NOTICES.md`. |
| `compas-FoFin` | Rhino plugin for tension-only, compression-only and mixed form finding. |
| `compas-Masonry` | Equilibrium and stability assessment of masonry block models. |

**Analysis and verification:**

- `compas_fea2` is the finite element layer, deliberately split into a frontend
  (model definition, results) and swappable backends. It supports Abaqus,
  ANSYS, SOFiSTiK and OpenSees through separate backend packages. It needs at
  least one of those installed to do anything, which is exactly why this
  repository keeps it out of the Rhino environment and reports the boundary
  instead of faking results.

**Fabrication and robotics:**

- `compas_fab` is the robotic fabrication package, and it is the answer to the
  "can COMPAS bring in ROS" question. It provides interfaces to robotics
  libraries and tooling, most importantly **ROS (Robot Operating System)** as a
  backend, plus motion planning through MoveIt and OMPL, kinematic solvers, and
  execution with feedback loops, all reachable from inside the parametric
  design environment. The usual deployment is ROS running in Docker containers
  that COMPAS talks to over `roslibpy`, so Rhino/Grasshopper on Windows can
  drive a planning stack that genuinely lives on Linux.
- `compas_xr` covers extended reality workflows for collaborative assembly,
  including an on-site visualiser for robotic assembly.

**Geometry and interoperability kernels:**

- `compas_occ` (OpenCascade: NURBS and B-rep), `compas_cgal` (CGAL: booleans,
  remeshing, slicing), `compas_libigl`, `compas_gmsh` (meshing),
  `compas_viewer` (standalone PyOpenGL/PySide6 viewer), `compas_plotter`.
- `compas_ifc` for IFC read and write, and `compas_model` for the physical
  element, material and section representation. Both are already wired into
  `structural.py` here as an explicitly reviewable formulation that never
  auto-saves a file.

The strategic point for this project: COMPAS is the interoperability substrate.
The same registered topology can go to a force density solve, a thrust network
solve, a graphic statics study, an FEA backend, an IFC export, or a robot
motion planner, because they all speak COMPAS datastructures. That is the whole
argument for keeping the core Rhino-free and contract-driven, and this
repository is already built that way.

## 5. Where this plugin sits

Built and working: the FD path end to end; the staged TNA path
(`TNA Pattern` to `TNA Supports` to `TNA Relax + Boundaries` to
`TNA Equilibrium`); the TNA reciprocal and its styled display; the query
components; the neutral structural handoff with its IFC formulation.

Explicitly roadmap, and flagged as such rather than half-implemented: generic
AGS on the native canvas, spatial/3D graphic statics, directional dashed
load-line and pole constructions, column and branch placement, Steiner
relaxation, and the `compas_model`/FEA/IFC stages as native components.

The honest gap worth naming is the spatial reciprocal that a branching tree
column actually wants. `compas_3gs` is conceptually its home, but its last
release is December 2021 and it belongs to the COMPAS 1.x line, so it is a
research port rather than an install. The routing already implemented here is
therefore the right answer for now: 3D FD vectors and local cells for
diagnosis, planar AGS for intentional slices, and FEA for the complete spatial
system. See [the suite adoption map](compas-suite-adoption.md) for the verified
version position of every package considered.

## 6. The recurring TNA message, diagnosed

The symptom: TNA runs, computes, produces plausible geometry, and still prints
something alarming.

The cause, confirmed against `compas_tna` 0.7.0 source. `horizontal_nodal`
stores a form/force edge direction difference in the `_a` edge attribute, and
the upstream code carries this comment:

```python
# angle deviations
# note that this does not account for flipped edges!
a = [angle_vectors_xy(uv[i], _uv[i], deg=True) for i in range(len(edges))]
```

Form and force edges are unoriented lines, so reciprocity holds when they are
parallel *or* antiparallel. A perfectly reciprocal but flipped edge is recorded
as 180 degrees. The legacy solver core reported `max(abs(_a))` directly, so
`gh_tna_solve.py` printed `Max reciprocal angle error: 1.800e+02 deg` on solves
that were fine.

Measured on a four by four corner-supported grid, the raw maximum was exactly
180 degrees while the true reciprocity error was 27.25 degrees.

The fix applied is a fold into 0 to 90 degrees, matching the convention the
native layer already uses in `ananke_equilibrium/codec.py` and
`ananke_equilibrium/gh/validate.py`, which both carried the correct handling and
an explanatory comment. Only the legacy core was reporting raw. The raw value is
now also preserved as `max_raw_form_force_angle` for traceability.

### The second finding, which is about your model rather than the code

Once the false alarm is removed, a real signal appears underneath it. On the
corner-supported grid the reciprocal has genuinely not converged at the default
100 horizontal iterations (27.25 degrees of deviation, free-node residual 15.7).

Raising iterations converges the reciprocal to 0 degrees, but it does *not*
produce a valid solve. It reveals that the configuration is ill-posed: the
support reactions then carry a net horizontal thrust of 0.5 against a total
applied load of 1.0, and the free-node residual settles at 3.0 rather than zero.

The same pattern with a **fully supported rim** is exact at the default 100
iterations: global force error 1.8e-16, residual 6.1e-16, reciprocity 0
degrees. Iteration count is irrelevant there.

The conclusion is that iterations were never the real problem. Corner supports
with an unsupported sagging boundary are the problem, and that is exactly the
case the staged workflow exists to handle. `TNA Relax + Boundaries` targets an
exact rise/span ratio for every eligible support-to-support opening before the
equilibrium solve. The one-shot legacy `TNA Solve` has no such stage, which is
why it returns plausible geometry for a configuration that is not in horizontal
equilibrium.

Practical guidance:

- If you use the legacy one-shot path with corner supports, watch the reported
  reciprocity error and the free-node residual. They are now truthful.
- Prefer the staged native path for any pattern whose boundary is not fully
  held.
- A fully supported rim converges immediately and is the right sanity check
  when you suspect the solver rather than the model.

The shipped iteration default is deliberately left at 100. Raising it would
change results for existing definitions without fixing anything real.
