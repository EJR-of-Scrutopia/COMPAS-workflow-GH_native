# Demo runbook

Six scripts. Each prints its analysis to the terminal and then opens a
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

## The six demos

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

One incompatibility worth knowing if anyone asks why the robot is drawn by
hand: `compas_robots` 1.0.1's own viewer object crashes against
`compas_viewer` 2.0.2 with `MeshObject() got multiple values for keyword
argument 'name'`. `demo/_robot.py` bypasses it by transforming the link
meshes directly.

### 6. The COMPAS masonry template gallery

`demo/06_masonry_gallery.py`

Builds the parametric masonry typologies that compas_dem ships: an arch (24
blocks), a barrel vault (58 blocks, 145 contacts) and a dome (240 blocks),
and shows them side by side.

It also prints what is **not** available in compas_dem 0.5.0: `WallTemplate`
raises, and cross vault, fan vault, pavilion vault, NURBS surface and stack
are all `NotImplementedError` stubs. Better to say so than to quietly show
three and imply seven.

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
| Deformation under load, FEA sense | `compas_fea2` registers no solver backend, and the OpenSees bridge is not published. It can express a model, not analyse one. |
| ROS robot placing blocks | Demo 5 does the placement with closed-form inverse kinematics and no ROS. What is missing is collision checking and trajectory planning, which are PyBullet and ROS with MoveIt respectively. |
| Cross, fan and pavilion vaults | `NotImplementedError` stubs in compas_dem 0.5.0. Demo 6 names them. |
