# VS Code design bench for COMPAS equilibrium workflows

Date: 2026-08-03
Branch: `feature/vscode-design-bench`
Status: design approved, ready for planning

## Why

The COMPAS numerics in this repository are already Rhino-free. `contracts.py`,
`codec.py`, the `gh/` adapters, and `worker.py` contain no Rhino or Grasshopper
imports, and `worker.dispatch()` is a pure function from request dictionary to
response dictionary. What does not exist is any way to reach that machinery
except by opening Rhino and placing components on a canvas.

That makes Grasshopper the only door to solvers that never needed it. This spec
builds the second door: a bench where a vault study is a JSON file, a solve is a
terminal command, and a result is something you can view, plot, diff, and commit.

The bench is a design tool, not a test harness. Faster plugin development is a
by-product, not the purpose.

## What was verified

Every environment claim below was checked against the repository's `.venv` or a
throwaway environment, not recalled. This section exists because two documented
claims turned out to be false, and the planning work depends on which.

### Working

| Check | Result |
| --- | --- |
| `compas_viewer` 2.0.2 resolution | Resolves cleanly; pulls PySide6 6.11.1, PyOpenGL 3.1.10, freetype-py 2.5.1; does **not** move `numpy`, `scipy`, or `compas` |
| `compas_dem` tessellation | `BlockModel.from_meshpattern(dome_mesh, 'Hex', tmin=0.15, tmax=0.25)` returns 114 blocks and serialises through `compas.data.json_dumps` |
| `compas_fea2` model expression | `Model()` constructs successfully with zero backends registered |
| IPOPT acquisition | `pip install idaes-pse` then `idaes get-extensions` delivers Ipopt 3.13.2 windows-x86_64, 67 binaries, executable verified |

### Broken, and documented as working

`docs/compas-suite-adoption.md` states that every family package "imports
cleanly", and `health_payload()` reports `masonry: true`. Both are false.
`health_payload()` reads distribution metadata via `importlib.metadata.version`
and never attempts an import, so a package that installs but cannot load reports
as present.

`compas_cra` 0.4.0 cannot import in this environment:

```text
compas_cra 0.4.0 requires: pyomo ==6.4.2
pyomo 6.4.2 -> pyomo/common/dependencies.py:659 -> np.float_
np.float_ removed in NumPy 2.0; this project pins numpy 2.0.2
import compas_cra.equilibrium  ->  AttributeError
```

`compas_dem.analysis.cra` imports `cra_penalty_solve` and `rbe_solve` from that
module, so `compas_dem.analysis` is down with it.

### The pyomo pin cannot be overridden

Tested by installing `compas_cra==0.4.0 --no-deps` and varying pyomo against a
three-block stack smoke solve:

| pyomo | Result |
| --- | --- |
| 6.4.2 (the pin) | `np.float_` under numpy 2; under numpy 1.26 on Python 3.12, fails in `component.py:471` with `TypeError: 'tuple' object does not support item assignment` (Python 3.11+ `__getstate__` returns a tuple) |
| 6.7.3 | Imports fail: `np.float_` |
| 6.8.0, 6.8.2, 6.9.0, 6.10.1 | Import cleanly; solve fails in `pyomo/repn/plugins/nl_writer.py` with `TypeError: Mapping.values() takes 1 positional argument but 2 were given` |

The window is empty. Everything at or below 6.7.3 fails to import under numpy 2,
and everything at or above 6.8.0 fails to solve against CRA's model construction.

`compas_cra` 0.4.0 therefore requires all four of: Python 3.10 or lower,
numpy below 2, pyomo exactly 6.4.2, and IPOPT on PATH. This project runs Python
3.12 with numpy 2.0.2 pinned to mirror the Rhino 8 `catenary-compas-2026`
environment. Three of the four conflict, and no Python 3.10 is installed on this
machine (the `Python310` entry on PATH is stale).

CRA staged stability is consequently a separate project with a separate
interpreter, not a command in this one.

### One Windows gotcha worth recording

The base interpreter is Microsoft Store Python, which virtualises `%LOCALAPPDATA%`
writes. `idaes get-extensions` therefore installs to:

```text
%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\Local\idaes\bin
```

while pyomo reports `SolverFactory('ipopt').available() == True` with an
`executable()` path of `%LOCALAPPDATA%\idaes\bin\ipopt.exe`, which does not
exist. The solver works, but only with that virtualised directory placed on PATH
explicitly. Trusting `available()` here produces a confident lie.

## Decisions

| Question | Decision |
| --- | --- |
| Purpose | A design bench. Studies get run here, not just replayed. |
| Authoring surface | The JSON file is the study. Hand-edited, schema-validated, diffable. |
| Solver reach | The CLI is a file-shaped adapter over `worker.dispatch()`, in-process. |
| Geometry source | Exported from Grasshopper, via worker-side capture. |
| Viewing | Split by job: `compas_viewer` for 3D, matplotlib for 2D diagrams. |
| Solver families | FD, TNA, graphic statics, DEM tessellation, FEA model export. |
| CRA staged stability | Out. Its own project, recipe recorded above. |
| FEA analysis | Out. Model expression and export only. |

## Architecture

### 1. Study directory and problem file

A study is a directory. The hand-edited file is `problem.json`:

```json
{
  "$schema": "../../.vscode/ananke-problem.schema.json",
  "study": "vault-a",
  "command": "tna.solve",
  "payload": {
    "topology":  { "...": "machine-written, bulky" },
    "supports":  { "mode": "explicit", "nodes": [0, 4, 20, 24] },
    "load_case": { "distribution": "uniform_nodes", "vectors": [[0, 0, -1]] },
    "settings":  { "...": "the tuned quantities" }
  }
}
```

The `payload` block is byte-identical to what the C# components already send.
`decode_fd_payload` requires exactly `{topology, supports, load_case, settings}`
and rejects unknown fields, so the study wrapper adds only `study` and
`command`, and the CLI reconstitutes the `{v, type, id, command, payload}`
envelope. A captured canvas solve is a valid study file with no translation step.

`"topology": {"$ref": "topology.json"}` is supported so the vertex array can live
in a sibling file that capture writes and hand-editing never touches. Resolution
is relative to the problem file.

Results are written to `results/result.json`, overwritten on each run so `git
diff` reports what changed between solves. `--archive` writes an additional
timestamped copy.

### 2. The CLI

A `[project.scripts]` entry point named `ananke`, implemented in a new
`src/ananke_equilibrium/cli/` package.

| Command | Behaviour |
| --- | --- |
| `ananke solve <problem.json>` | Build envelope, call `dispatch()`, write result. Exit 0 on a `result` response, exit 1 on an `error` response with the protocol message on stderr. |
| `ananke check <problem.json>` | Decode and validate only. No solve. Fast enough to bind to file save. |
| `ananke plot <result.json>` | Headless 2D diagrams to PNG or SVG. |
| `ananke view <result.json>` | Interactive 3D through `compas_viewer`. |
| `ananke health` | `health_payload()` rendered as a table. |

`solve` dispatches on the problem file's `command` field, so FD, TNA prepare, TNA
solve, and DEM tessellation share one command with no per-solver CLI surface.

Calling `dispatch()` rather than reimplementing the decode-solve-encode sandwich
means parity with Grasshopper is structural rather than asserted. It also keeps
everything in one process, so a breakpoint set in `solve_tna` is reached by
pressing F5 on a problem file.

### 3. Viewing

`ananke plot` uses matplotlib, already installed, and needs no new dependency.
`encode_tna_result` emits `form_graph` and `force_graph` as vertices carrying
`[x, y, z]` points and edges carrying `u`/`v` indices, so the reciprocal pair
draws directly from the result file: form and force side by side, members
coloured by force state. These are the committable, diffable artefacts.

Graphic statics in this spec means exactly that: plotting the reciprocal form and
force diagrams that `tna.solve` already produces. It does not mean a new solver.
A generic `ags.solve` worker command is out of scope, and the `ags.solve`
capability flag continues to describe the installed package rather than an
implemented command.

`ananke view` uses `compas_viewer` behind an opt-in `viz` extra. The bridge
already exists: `compas_export_payload()` in `gh/export.py` returns
`json_dumps(Mesh)` and `json_dumps(Graph)`, so viewing is `json_loads` into a
`compas.scene.Scene` plus load and reaction vectors.

The `viz` extra is opt-in because PySide6 is large and Rhino never imports it.
An environment guard test asserts that `numpy`, `scipy`, and `compas` still match
the declared pins, so installing the viewer can never quietly drift the
environment away from what Rhino runs.

### 4. Capture: getting problems out of Grasshopper

The worker reads an `ANANKE_CAPTURE_DIR` environment variable at startup. When
set, every solve request that arrives is written to that directory as a study
file in the shape above. Rhino's environment is inherited by the worker process
it spawns, so this is one environment variable and a Rhino restart.

No C# changes are required, and nothing needs coordinating with concurrent
component work. Capture is inert unless the variable is set. Requests larger than
`codec.MAX_FRAME_BYTES` cannot reach the worker in the first place, so that value
is the natural cap; capture skips anything above it and writes a warning to
stderr rather than silently producing very large files.

### 5. DEM tessellation, and two honesty fixes

A new worker command `dem.tessellate` takes a solved TNA result plus tessellation
settings (one of the 18 pattern names `compas_libigl` accepts, plus `tmin` and
`tmax`) and returns a `BlockModel` as COMPAS JSON with a block and interface
summary. Placing it in the worker rather than the CLI means Grasshopper gains it
at the same time.

`health_payload()` changes from a metadata check to an import check, so a package
that installs but cannot load reports as unavailable. `masonry` splits into
`masonry.tessellate` (true) and `masonry.stability` (false, carrying its reason).
`docs/compas-suite-adoption.md` is corrected.

`compute_contacts()` returned zero contacts on the dome fixture during
verification. The implementation must reach non-zero contacts on a committed
fixture or report honestly why it cannot. A tessellation that produces no
interfaces is a picture, not a model.

### 6. FEA model export

A `fea.model` worker command builds a `compas_fea2` `Model` from a solved result
and returns it as COMPAS JSON, matching the format `export.compas` already uses.
Solver input decks are not produced, because writing one is a backend
responsibility and no backend is registered. The capability flag continues to
report `fea: false` and `fea.model: true`, because expressing a model and
analysing one are different claims and the second is not available.

Restraint degrees of freedom are not inferred from form-finding supports. The
command carries the support node IDs through as geometry and metadata only,
leaving restraint definition to whoever later attaches a backend. This follows
the design rule already stated in the README.

This exists so that the later OpenSees project is a backend registration rather
than a rewrite.

### 7. The VS Code layer

The centrepiece is a JSON Schema generated from `contracts.py` and wired through
`.vscode/settings.json`'s `json.schemas` map. Hand-editing `problem.json` then
gets completion and inline validation on support modes, load distributions, unit
strings, force-density fields, and the command allowlist. It is generated rather
than written, with a test asserting it matches the contracts, because a
hand-maintained schema drifts from the code it describes.

Alongside it:

- `tasks.json`: solve, check, plot, view, health, and tests, against the active file.
- `launch.json`: debug the CLI on the current problem file; attach to the worker.
- `extensions.json`: recommended extensions.
- `settings.json`: interpreter selection and pytest configuration.

## Testing

Added to the existing pytest suite:

| Test | Asserts |
| --- | --- |
| CLI round trip | A golden problem fixture solves to an expected result |
| Parity | CLI output and a direct `dispatch()` call return identical results |
| Schema sync | The generated JSON Schema matches `contracts.py` |
| Environment guard | `numpy`, `scipy`, `compas` still match declared pins |
| Capture | A captured file is a valid study file and re-solves |
| Tessellation | A dome fixture yields blocks and non-zero contacts |
| Health honesty | Capability flags follow imports, not distribution metadata |

## Out of scope

CRA staged stability. FEA analysis. Mesh-file importers (OBJ, PLY). Pattern
generators (grid, surface, triangulation, skeleton). The `tree_forest` pipeline.
Parameter sweeps. Result diffing beyond what `git diff` provides.

## Follow-on projects

**CRA staged stability.** A Python 3.10 environment with numpy 1.26, pyomo 6.4.2,
`compas_cra` 0.4.0, and IPOPT on PATH, exchanging block models as COMPAS JSON
with the main environment. This is the same answer `docs/compas-suite-adoption.md`
already gives for `compas_cem`, and it answers the formwork load question.

**OpenSees FEA backend.** Installing `compas_fea2_opensees` from source against
`openseespy` 3.8.0.0 to register a backend. Unbounded until attempted.

## Risks

The contact-tolerance work in section 5 is the only item with genuinely unknown
size. If non-zero contacts prove hard to reach on a real thrust mesh, the
tessellation command still ships with an honest diagnostic, and interface
detection becomes its own investigation.

`compas_viewer` was verified to resolve, but not yet verified to render a scene
on this machine's graphics stack. The plotter path carries no such risk, which is
part of why the split exists.
