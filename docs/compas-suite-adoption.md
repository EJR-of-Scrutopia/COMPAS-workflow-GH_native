# The COMPAS suite, and how it enters this plugin

This document reads the COMPAS architecture diagram against what is actually
installable in August 2026, then maps each family onto a concrete adoption step
for this project. Every version and dependency claim below was checked against
PyPI and against the installed COMPAS in this repository's environment, not
recalled from memory.

The short version: the diagram is accurate about the *shape* of the framework
and out of date about the *contents* of the core, because it predates COMPAS 2.

## 1. The diagram's five columns, corrected for COMPAS 2

The layered reading is right and worth stating plainly, because it is the
reason this plugin is built the way it is.

```text
External libraries  ->  COMPAS bindings  ->  COMPAS core  ->  COMPAS cad  ->  CAD software
   CGAL, Gmsh,          compas_cgal,          datastructures,   compas_rhino,     Rhino,
   libigl, OCC,         compas_gmsh,          geometry,         compas_ghpython,  Grasshopper,
   Triangle             compas_occ, ...       topology, ...     compas_blender    Blender
                                                   |
                                                   v
                                          COMPAS viz + extensions
```

The load-bearing idea is that **the core knows nothing about CAD**. Geometry
and datastructures are plain Python objects; `compas_rhino` and
`compas_ghpython` are adapters at the edge. That is precisely the discipline
this repository already enforces by keeping `src/tree_forest_compas/` and
`src/ananke_equilibrium/` free of Rhino imports. The project is not merely
compatible with the COMPAS architecture, it is built on the same principle.

### What changed since the slide was made

Checked directly against the installed `compas 2.15.1`:

| On the slide | Status in COMPAS 2.15.1 |
| --- | --- |
| `compas.artists` | **Gone.** Replaced by `compas.scene`. |
| `compas.numerical` | **Gone.** Split into `compas.linalg` and `compas.matrices`; the solvers moved out into `compas_fd`, `compas_dr` and friends. |
| `compas.robots` | **Gone.** Moved out to the standalone `compas_robots` package. |
| `compas.data`, `.datastructures`, `.files`, `.geometry`, `.plugins`, `.rpc`, `.topology` | Present and unchanged in role. |
| not shown | New: `compas.colors`, `compas.tolerance`, `compas.itertools`, `compas.linalg`, `compas.matrices`, `compas.scene`. |
| `compas_view2` | Superseded by `compas_viewer` 2.x. |

One of those survivors deserves attention. **`compas.rpc` is still there**, and
it is COMPAS's own answer to the problem this plugin solved with a bespoke
worker: running real CPython COMPAS outside the CAD process. The custom
protocol in `plugin/native_v02/Backend/` is not redundant, because a compiled
C# component wants an explicit versioned contract rather than a Python proxy,
but `compas.rpc` is the reference implementation worth reading before extending
the worker.

## 2. Verified inventory of the extension families

Latest versions and release dates from PyPI, with the declared COMPAS
dependency. This is the table that decides what you can actually adopt.

| Family | Package | Latest | Released | COMPAS dep | Verdict |
| --- | --- | --- | --- | --- | --- |
| Form finding | `compas_fd` | 0.5.4 | 2024-11 | >=3.9 | **In use** |
| Form finding | `compas_tna` | 0.7.0 | 2025-09 | >=3.9 | **In use** |
| Form finding | `compas_ags` | 1.3.3 | 2024-11 | >=3.9 | **In use** |
| Form finding | `compas_dr` | 0.3.1 | 2024-05 | >=3.9 | Safe to add |
| Form finding | `compas_cem` | 0.8.6 | 2025-02 | **`compas==1.17.10`** | **Blocked**, see below |
| Form finding | `compas_3gs` | 0.6.0 | **2021-12** | COMPAS 1.x era | **Dormant**, see below |
| Masonry | `compas_dem` | 0.5.0 | 2026-05 | >=2.4 | **Current DEM package** |
| Masonry | `compas_cra` | 0.4.0 | 2024-03 | >=2.0 | Safe to add |
| Masonry | `compas_assembly` | 0.7.1 | 2024-05 | >=2.0 | Safe to add |
| Masonry | `compas_tno` | 0.3.0 | 2025-09 | uses `compas_tna` | Safe to add |
| Masonry | `compas_rbe` | 0.1.2rc0 | 2021-05 | 1.x era | **Superseded** by `compas_cra` |
| Fabrication | `compas_fab` | **2.0.1** | 2026-06 | >=2.3,<3 | **Safe to add, COMPAS 2 native** |
| Fabrication | `compas_robots` | 1.0.1 | 2026-05 | >=3.9 | Pulled in by `compas_fab` |
| Fabrication | `compas_timber` | 2.2.0 | 2026-07 | >=3.9 | Safe to add |
| Fabrication | `compas_slicer` | 0.7.0 | 2024-03 | >=3.8 | Safe to add |
| Fabrication | `compas_rrc` | 2.0.0 | 2024-03 | ABB control | Only with ABB hardware |
| Engineering | `compas_fea2` | 0.2.1 | 2024-05 | >=2.0 | Needs a solver backend |
| Data modelling | `compas_ifc` | 2.1.0 | 2026-07 | >=3.9 | **Already an extra** |
| Data modelling | `compas_lca` | 1.0.2 | 2026-07 | **Python >=3.11** | Blocked by the 3.9 floor |
| Model | `compas_model` | 0.9.3 | 2026-05 | >=3.9 | **Already an extra** |
| Bindings | `compas_cgal` | 0.10.0 | 2026-07 | >=3.9 | Pulled in by `compas_dem` |
| Bindings | `compas_libigl` | 0.7.6 | 2025-09 | >=3.9 | Pulled in by `compas_dem` |
| Bindings | `compas_gmsh` | 0.4.6 | 2026-03 | >=3.9 | Pulled in by `compas_fea2` |
| Bindings | `compas_occ` | conda only | | | Not on PyPI |
| Patterns | `compas_skeleton` | 2.0.1 | 2025-02 | >=3.9 | Safe to add |
| Patterns | `compas_singular` | conda only | | | Not on PyPI |

### Two corrections that change the plan

**`compas_3gs` is not the answer I suggested it was.** I previously named it as
the route to a spatial reciprocal for branching tree columns. Its last release
is December 2021, it declares `requires_python >=2.7`, and it depends on
`compas_skeleton >=1.1.0` from the COMPAS 1.x line. It will not run against
`compas 2.15.1`. Treat 3D graphic statics as a research port, not an install.
The routing already implemented in this repository (3D FD vectors and local
cells for diagnosis, planar AGS for intentional slices, FEA for the full
spatial system) remains the correct answer, and now for a firmer reason.

**`compas_cem` hard-pins `compas==1.17.10`.** Combinatorial Equilibrium
Modelling is genuinely interesting for mixed tension and compression networks,
but that pin means it can never share an environment with this project. If you
want it, it is a separate conda environment and a file-based exchange, not an
extra.

## 3. Where the empty slots are right now

The worker reports its own capability set. Running `health_payload()` against
the current environment gives:

```text
compas 2.15.1  compas_fd 0.5.4  compas_tna 0.7.0  compas_ags 1.3.3
compas_model: null   compas_fea2: null   compas_ifc: null

fd.solve  true    tna.prepare true    tna.solve true    ags.solve true
model     false   fea         false   ifc       false
```

So three declared extras (`model`, `fea`, `ifc`) are wired in code and simply
not installed in the development environment. That is the honest starting
point: the contracts exist, the capability flags exist, the packages do not.

## 4. The masonry vault on formwork, end to end

This is the pipeline you actually asked about, and it is worth being precise
because it contains two different problems that are easy to conflate.

**Robot inverse kinematics** answers "what joint angles put the gripper here".
That is `compas_fab`.

**The formwork load question** answers "what does the falsework carry at build
step k". That is a staged equilibrium problem, and it is *not* IK. It is where
`compas_dem` and `compas_cra` live.

They meet at the build sequence, which is the shared spine.

### Why the staged question matters structurally

A masonry vault is funicular only when it is complete. Until the last block
closes the arch, the partial assembly cannot carry itself, and the difference
between what the partial vault can resolve and what gravity demands is exactly
the load the formwork takes. A TNA solve gives you the *final* state. It says
nothing about step k.

That gap is the whole reason discrete element analysis exists in this suite.
TNA treats the vault as a continuous network of forces. `compas_cra` treats it
as actual blocks with actual interfaces, and solves for stability including
friction and the possibility of sliding, which a thrust network cannot express.

### The pipeline

```text
1  TNA form finding                     this plugin, built
   thrust network for the complete vault
                 |
                 v
2  Tessellation into blocks             compas_dem (pulls compas_cgal,
   intrados/extrados offsets,           compas_libigl, compas_model)
   interface geometry
                 |
                 v
3  Assembly with interfaces             compas_assembly
   blocks, contact frames, adjacency
                 |
                 v
4  Staged stability + friction          compas_cra
   for each build step k:                 - is the partial assembly stable?
     solve equilibrium of blocks 1..k     - what are the interface forces?
     the unresolved residual is the       - where does it want to slide?
     formwork reaction at step k
                 |
                 +--> formwork design load history   (the answer you want)
                 |
                 v
5  Placement sequence -> robot poses    compas_fab
   target frame per block                 - analytical IK: closed form, no setup
                 |                         - PyBullet: numerical IK + collision
                 v                         - ROS 2 + MoveIt 2 via rosbridge
6  Execution                            compas_rrc (ABB) or ROS driver
```

Step 4 is the one that produces the number you are after. The formwork reaction
at each stage is a first-class structural result, not a by-product, and it is
often the governing load case for the falsework even though the finished vault
never sees it.

### The ROS answer, specifically

`compas_fab` 2.0.1 is COMPAS 2 native and offers five planning backends, in
increasing order of setup cost:

1. **Analytical IK.** Closed-form, pure Python, no installation beyond
   `compas_fab` itself. Covers UR, Stäubli and ABB kinematic families. This is
   the on-ramp, and for placing blocks on a known vault it may be all you need.
2. **Analytical IK plus PyBullet** for collision checking.
3. **PyBullet** for numerical IK, collision checking and local planning.
4. **ROS 1 with MoveIt 1** over rosbridge, legacy.
5. **ROS 2 with MoveIt 2** over rosbridge, the current standard.

The usual deployment for 4 and 5 is ROS in Docker containers, reached over
`roslibpy`, so Rhino and Grasshopper on Windows drive a planning stack that
genuinely runs on Linux. Given the Docker infrastructure already in use on this
machine, that route is closer to hand than it looks.

Start at level 1. Do not stand up ROS to answer a question closed-form IK can
answer.

## 5. Adoption sequence for this plugin

Ordered by value per unit of risk, and expressed as changes to
`pyproject.toml` extras plus worker capability flags, which is the pattern the
project already uses.

**First, close the declared gaps.** `compas_model` and `compas_ifc` are already
extras with contracts written and capability flags wired. Installing them turns
three `false` flags into `true` with no new architecture. This is the cheapest
real progress available.

**Second, add the masonry extra.** A new `masonry` extra pulling `compas_dem`,
`compas_assembly` and `compas_cra`. `compas_dem` transitively brings
`compas_cgal` and `compas_libigl`, which also unlocks the meshing and boolean
operations the tessellation step needs. New worker commands would follow the
existing shape: `dem.tessellate`, `assembly.build`, `cra.solve_stage`.

**Third, add the fabrication extra.** `compas_fab` plus `compas_robots`,
starting with analytical IK only and no ROS dependency. A `fab.ik` worker
command taking target frames and returning joint configurations fits the
existing contract style exactly.

**Fourth, and only when a solver is chosen,** `compas_fea2` in its own
environment. The existing documentation is already correct that this needs a
dedicated conda environment and a backend (Abaqus, ANSYS, SOFiSTiK or
OpenSees), and that installing it into the Rhino environment is a mistake.

**Deliberately not adopted:** `compas_3gs` and `compas_cem` for the version
reasons above, `compas_lca` until the Python floor moves off 3.9, and
`compas_rrc` until there is ABB hardware to talk to.

## 6. What this does not change

The design rule stated in the README still governs every one of these
additions. A discrete element stability result is not a verified structural
model, an IK solution is not a collision-free trajectory, and an IFC export
does not turn any of it into a checked building. Each package that comes in
should arrive with its own capability flag, its own diagnostics, and its own
honest statement of what it has not proven. The value of this suite is that it
makes those boundaries explicit rather than dissolving them.
