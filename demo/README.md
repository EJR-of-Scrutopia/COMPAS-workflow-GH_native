# Demo runbook

Seven scripts. Each prints its analysis to the terminal and then opens a
compas_viewer window. Close the window to end the script.

## Before you start

Open this folder in VS Code, then check the interpreter is the project's own:

```
.venv\Scripts\python.exe
```

Bottom-right of the VS Code status bar, or `Ctrl+Shift+P` then
`Python: Select Interpreter`.

Confirm the stack is live:

```powershell
.venv\Scripts\python.exe -m ananke_equilibrium.cli health
```

## Running a demo

Three ways, all equivalent. Use whichever reads best on the day.

1. **F5.** Open the script, press F5, pick its configuration from the list.
2. **Task.** `Ctrl+Shift+P`, `Tasks: Run Task`, pick the demo.
3. **Terminal.** `.venv\Scripts\python.exe demo\01_solve_pavilion.py`

To run a script without opening a window, set `ANANKE_DEMO_NO_SHOW=1`.

## The seven demos

### 1. Solve the pavilion

`demo/01_solve_pavilion.py`

Reads `studies/pavilion/problem.json`, solves the thrust network through the
same worker Grasshopper drives, and reports span, rise, member force range,
and a global equilibrium check.

The line to point at is the residual. It is the vector sum of every applied
load and every support reaction, and it comes out at zero to twelve decimal
places. The bench is not asserting that the solve worked, it is showing a
check you can dispute.

Then the viewer opens on the thrust surface and its network.

### 2. Form and force diagrams

`demo/02_diagrams.py`

Writes `demo/pavilion-diagrams.png`, then shows the vault, its form diagram,
and its reciprocal force diagram side by side in 3D.

The force diagram has one node per face of the form diagram and the same
edge count. That correspondence is what makes the pair reciprocal: every
edge length in the force diagram is a force magnitude in the form diagram.

### 3. Load cases

`demo/03_load_cases.py`

Seven load cases from `studies/pavilion/cases.json`, solved in one command,
compared in one table, and shown side by side in the viewer.

This is the argument for the bench. Read down the table:

- scaling the load scales the forces exactly, 1.5x and 3x;
- snow on the windward half and a point load at the crown both raise the
  peak compression without changing the shape;
- flattening the vault from 3 m to 1.5 m rise **raises** the thrust;
- steepening it to 5 m **lowers** the thrust.

The tension column stays at zero throughout, which is the statement that the
surface remains funicular across this range.

### 4. Masonry blocks

`demo/04_masonry_blocks.py`

Tessellates the thrust surface into 158 discrete blocks with 404 contact
interfaces, and shows the assembly against the translucent thrust surface.

Say plainly what this is: **geometry**. Blocks and interfaces, not stability.
Whether the assembly stands up, and what the falsework carries at each build
step, is coupled rigid-block analysis. That runs in a separate Python 3.10
environment built by `scripts/setup_cra_env.sh`, because `compas_cra` pins
`pyomo 6.4.2`, which cannot coexist with the NumPy 2 this project pins to
mirror Rhino 8.

### 5. A robot placing the vault

`demo/05_robot_placing.py`

Loads a UR5 from the compas_fab library (offline, with geometry, in under a
second), scales the tessellated vault down into the arm's reach, solves
closed-form inverse kinematics for all 28 block positions, and animates the
arm building it from springing to crown.

Say what it is: **analytical inverse kinematics**. Exact, instant, no solver,
no simulator, and no ROS anywhere. Eight arm postures come back per target
and the script picks the one nearest the current pose so the motion stays
continuous.

Say what it is not: no collision checking and no trajectory planning.
Reaching a frame and moving safely between frames are different questions,
and only the first is answered here. Collision checking is PyBullet;
planning around obstacles is ROS with MoveIt.

The robot is drawn by compas_robots' own `RobotModelObject` and moved with
`update_joints`, which is the pattern in the upstream compas_viewer robot
example. One detail: `scene.add(model, ...)` must be called **without** a
`name` keyword, because RobotModelObject passes its own name through to the
meshes it builds and a supplied one collides with it, raising
`MeshObject() got multiple values for keyword argument 'name'`.

### 6. The COMPAS masonry template gallery

`demo/06_masonry_gallery.py`

Builds the parametric masonry typologies that compas_dem ships: an arch (24
blocks), a barrel vault (58 blocks, 145 contacts) and a dome (240 blocks),
and shows them side by side.

It also prints what is **not** available in compas_dem 0.5.0: `WallTemplate`
raises, and cross vault, fan vault, pavilion vault, NURBS surface and stack
are all `NotImplementedError` stubs. Better to say so than to quietly show
three and imply seven.

### 7. COMPAS's own examples

`demo/07_compas_official.py`

Run with no argument for a menu of 32 unmodified example files taken from the
COMPAS repositories. Run one by name or number:

```powershell
.venv\Scripts\python.exe demo_compas_official.py dem_vault_cross
.venv\Scripts\python.exe demo_compas_official.py robot
```

These are richer than the demos above, and worth showing for two reasons.

**Real case-study geometry.** `dem_vault_cross` loads 184 individual
voussoirs from an OBJ and finds 488 contacts, with supports identified by
graph degree. `dem_armadillo`, `dem_dome` and `dem_wall` are the same idea.
None of it is parametric: it is measured geometry.

**A proper application, not a viewport.** These use `DEMViewer`, which adds a
COMPAS DEM menu with Show Blocks, Show Contacts and Show Interactions, a
sidebar object tree with per-object visibility checkboxes, object and camera
settings panels, four render modes and five view presets.

### 9. Structural verification

`demo/09_structural_verification.py`

Runs in `.venv-fea`, a third project environment beside `.venv` and
`.venv-cra`: `compas_fea2` is pinned to a mid-2025 commit because the
OpenSees backend it targets was last pushed before the core removed
`BeamSection`, and that pin should not leak into the Rhino-mirroring main
environment. Build it with `bash scripts/setup_fea_env.sh`. Like every other
demo here, the play button hands the script to the right interpreter
automatically if a different one is selected; from `.venv` you will see
`Switching from ... to ...\.venv-fea\Scripts\python.exe` before it runs.

The export to analyse is chosen at runtime, never hard-coded. With no
argument, the export with the smallest equilibrium residual is picked (of
the three shipped in `upload from grasshopper/`, that is currently the
algebraic TNA solve, closing to 0.03 kN); name one explicitly to override:

```powershell
.venv-fea\Scripts\python.exe demo\09_structural_verification.py "Trial 2"
```

Seven sections: reads the export; solves a pin-jointed truss of the thrust
network under the same loads and cross-checks both the global reaction and
every member's axial force against what TNA already reported; solves the
shell under its design load and reports peak deflection and stress
utilisation; sweeps two load factors to find where the shell goes into
tension; sizes a cable if it does; traces the load path by arc length
(`StaticRiksStep` cannot be constructed at this pin, so this reports why
rather than inventing a collapse factor); and writes everything to
`studies/<export-name>/fea-verification.json`.

Each full-mesh shell solve took under two seconds in testing, well under the
brief's original estimate, so the shell sections plus the sweep and the cable
sizing run in single-digit seconds. **The bar cross-check does not
currently complete on the real vault.** Every shipped export is a pure
quad-grid thrust network with no diagonal members at all, and a pin-jointed
truss built from a quad grid is a mechanism: each of its 2400 quad panels can
rack freely, which is invisible on the tiny triangulated fixture the unit
tests use but shows up at full scale as OpenSees' Newton iteration diverging
rather than converging (residual norm rising past 4x10^9 in ten iterations,
confirmed by running the generated `.tcl` directly). This surfaced for the
first time when the demo was run end to end, exactly the risk the plan for
this piece flagged in advance. It is a limitation of `build_bar_model` in
`ananke_fea.bars`, not of this script, and it is open rather than patched
around.

### Every working example has its own clickable file

`demo/compas_examples/` holds **24 files, one per example that runs here**.
Open any of them and press play. Each is a wrapper: the example itself stays
unmodified in `upstream/`, and the wrapper only points the interpreter and
working directory at it, because these examples load data by paths relative
to their own repository.

The masonry case studies are the ones to show:

| File | What it is |
| --- | --- |
| `dem_vault_cross.py` | 184 voussoirs from an OBJ, 488 contacts |
| `dem_armadillo.py` | The armadillo vault, a large freeform assembly |
| `dem_dome.py` | A masonry dome from measured geometry |
| `dem_vault_barrel.py` | A barrel vault with its interfaces |
| `dem_arch.py`, `dem_stack.py`, `dem_wall.py` | Smaller assemblies |

The `viewer_*.py` files demonstrate the viewer itself: `viewer_treeform.py`
for the scene tree, `viewer_sidedock.py` for the side panel,
`viewer_dynamic_scene.py` for animation, `viewer_camera.py` for view presets.

**Eight of the 32 do not run here**, and the reasons are worth knowing:
`robot`, `model`, `test_ui`, `scene` and `nurbscurve` need an older
compas_viewer API or an uninstalled plugin; `dem_new_features` and
`dem_new_features_RBE` hit the same pyomo 6.4.2 against NumPy 2 wall as
compas_cra; and `extract_robot_package_from_ros` needs a live ROS
connection. They are listed by `demo/07_compas_official.py` rather than
hidden.

## Bringing your own pavilion from Grasshopper

Build the vault on the canvas, run it through
`TNA Pattern -> TNA Supports -> TNA Relax + Boundaries -> TNA Equilibrium`,
then drop an **Export** component on the result:

- **Mode `Contract`** with a `Path` set writes the whole solved result as
  portable JSON. This is the one to use for analysis here: it carries the
  equilibrium state, both diagrams, and the per-edge forces.
- **Mode `COMPAS`** writes `compas.data` geometry instead. Good for viewing,
  but it drops the forces.

Then, in this folder:

```powershell
.venv\Scripts\python.exe -m ananke_equilibrium.cli describe path\to\export.json
.venv\Scripts\python.exe -m ananke_equilibrium.cli plot     path\to\export.json
.venv\Scripts\python.exe -m ananke_equilibrium.cli view     path\to\export.json
```

The Contract export is camelCase because it is serialised by C#, and the
worker's own output is snake_case. The reader treats them as the same thing,
so either file works in any of those commands.

## One trap worth knowing

`load_case.factor` in a hand-written study file **is not applied**. The
worker stores it and no solver reads it. The Grasshopper Loads component
avoids the problem by multiplying the vector itself and sending a factor of
1.0, so canvas work is unaffected. `check` and `solve` now warn if a study
file sets it. Multiply the vectors instead.

## What is not in these demos, and why

| Asked for | State |
| --- | --- |
| Formwork load at build step k | The CRA environment is built and solves. Wiring the tessellated blocks into it is the next piece of work, not a finished demo. |
| Deformation under load, FEA sense | Demo 9 does this now, in `.venv-fea` against a pinned OpenSees backend. What is not finished is its own bar cross-check on the real vault; see demo 9's entry above. |
| ROS robot placing blocks | Demo 5 does the placement with closed-form inverse kinematics and no ROS. What is missing is collision checking and trajectory planning, which are PyBullet and ROS with MoveIt respectively. |
| Cross, fan and pavilion vaults | `NotImplementedError` stubs in compas_dem 0.5.0. Demo 6 names them. |
