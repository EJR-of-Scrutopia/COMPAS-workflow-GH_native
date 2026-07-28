# Native Grasshopper / COMPAS worker architecture

Status: accepted for the v0.2 development milestone.

## Boundary

The Grasshopper plugin is a compiled .NET 8 component library. Its public
components derive from `GH_Component` or `GH_TaskCapableComponent<T>`.
They do not derive from Rhino Script components and do not embed one Python
script per component.

COMPAS remains the numerical source of truth. It runs in one persistent,
hidden CPython worker process owned by the plugin. Native v0.2 loads its FD
adapter when the worker starts; the adapter imports `compas_fd` lazily when
`fd.solve` is requested. Health reporting can detect installed `compas_tna`,
`compas_ags`, `compas_model`, `compas_fea2`, and `compas_ifc` distributions
without importing them; no command for those packages is implemented in this
milestone.

RhinoCommon, Grasshopper objects, document object IDs, and live Python or
COMPAS objects never cross the process boundary.

## Transport

The plugin launches:

```text
python -m ananke_equilibrium.worker
```

Standard input and output are reserved for protocol frames. Each frame is:

```text
4-byte unsigned big-endian byte count
UTF-8 JSON payload of exactly that byte count
```

The maximum frame size is 32 MiB. Diagnostic output and Python tracebacks go
to standard error and therefore cannot corrupt protocol output.

Every request has this envelope:

```json
{
  "v": 1,
  "type": "request",
  "id": "request UUID",
  "command": "fd.solve",
  "payload": {}
}
```

Every terminal response echoes `v`, `id`, and one of these types:

- `result`: successful payload in `result`
- `error`: structured `code`, `message`, and optional `details`
- `cancelled`: the request did not produce a result

Progress notifications use `type: "event"` and are non-terminal.

The v1 allowlist starts with:

- `system.hello`
- `system.health`
- `system.shutdown`
- `fd.solve`

Commands for TNA, AGS, structural modelling, FEA, and IFC are additive. The
worker never exposes arbitrary module imports, function calls, or `eval`.

Protocol and snapshot schemas are versioned independently. Native plugin v0.2
requires protocol v1 and explicitly accepts worker snapshot schema v0.1; both
the startup handshake and every FD result are rejected if those versions do
not match.

## Data contracts

All public values are versioned JSON snapshots. Each Grasshopper Goo stores:

- contract kind
- schema version
- immutable JSON data
- a topology binding hash where relevant
- unit metadata and sign convention where relevant
- package and solver provenance for calculated results

The first native contract family is:

- `Topology`
- `SupportSet`
- `LoadCase`
- `EquilibriumProblem`
- `FDSettings`
- `EquilibriumResult`
- `Diagnostic`

The current FD command returns a complete stable snapshot and then discards
the live backend session. Sessions are never pickled into a Grasshopper
definition. A saved result contains enough stable input, source-member
mapping, and result data to display it after the worker exits. Opaque
worker-side references are a future option only for operations that genuinely
need a live COMPAS session.

Current native registration and targeting rules are explicit:

- `Network.Geometry` is flattened before lines, polyline segments, or mesh
  edges are welded into one topology.
- Vertex IDs and source-segment IDs are deterministic for the exact flattened
  input order, segmentation, and weld tolerance; they are not promised to
  survive a reordering of source geometry.
- Coincident registered edges are represented once and retain their
  contributing source-segment IDs as a `|`-joined provenance value.
- Support and load point targets are snapped to the nearest topology vertex in
  the C# layer, using their requested tolerance or the topology's recorded weld
  tolerance. Only resolved zero-based node IDs cross to Python.
- The result decoder checks worker edge count and ordering against the
  registered topology before reattaching member source IDs.
- The worker returns the resolved fixed node IDs with the solved snapshot, so
  automatic terminal or boundary supports remain explicit downstream even
  when a support reaction is zero.
- v0.2 rejects unimplemented modes instead of coercing them: support modes are
  `explicit`, `terminals`, or `boundary`; load distributions are `point`,
  `uniform_nodes`, or `custom`; FD uses the fixed `positive_tension` sign
  convention.

## Grasshopper lifecycle

Solver components use Grasshopper's task-capable two-pass solve pattern.
Inputs are duplicated and converted to immutable DTOs before background work
starts. The background task communicates only with the worker. Grasshopper
outputs and Rhino viewport state are updated on Grasshopper's solve thread.

Grasshopper's task-capable solve lifecycle owns delivery of each result.
Cancellation is cooperative first; if numerical code cannot stop within the
configured grace period, the plugin terminates and restarts the worker.

The principal workflow is deliberately bundle-first:

```text
Topology + SupportSet + LoadCase
              |
       EquilibriumProblem
              |
      FDSettings -> FD Solve
              |
      EquilibriumResult
```

Runtime messages replace repeated `Status` outputs. Long aligned lists are
available through explicit query components rather than every solver output.

## Environment

During v0.2 development the installer resolves the existing
`catenary-compas-2026` Rhino CPython package environment and writes its exact
interpreter and package paths to `backend.json` beside the installed plugin.
The runtime never relies on `PATH` or on an unresolved environment glob.

A later distribution milestone may provision a plugin-managed pinned Python
environment without changing the transport or component contracts.

## Migration

The script-backed v0.1 plugin is preserved by Git tag
`prototype-script-backed-v0.1.0`.

Native v0.2 components are tested with development GUIDs until their worker
results match the Python adapters. An existing public component GUID is reused
only if ports, access modes, defaults, persistence, and semantics remain
compatible. Otherwise the old component becomes Legacy and an explicit
Grasshopper upgrade object performs migration.

The script-backed v0.1 and native v0.2 components deliberately have different
GUIDs. There is no automatic v0.1-to-v0.2 document migration in this milestone:
keep the tagged prototype to open an old definition, then rebuild its wiring
with the native bundle components.
