# Component Surface Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the twenty-component v0.2 Grasshopper surface with twelve components on one shared spine (Pattern, Supports, Loads) feeding two solvers (TNA, FD) that return one unified Result consumed by one Display, one Deconstruct, and one Export.

**Architecture:** The spine enriches one typed object per stage (PAT to SUP to PRB), solvers return a single `ResultDto` (today's `TnaResultDto` generalised, reciprocal block optional), and drawing lives only in Display, mirroring `compas.scene`. The Python solver core (`tree_forest_compas`) is untouched; the worker keeps its commands and gains `export.compas`.

**Tech Stack:** C# .NET 8 Grasshopper plugin (`plugin/native_v02/`), Python 3.9+ contracts/worker (`src/ananke_equilibrium/`), pytest, pinned COMPAS 2.15.1 environment in `.venv`.

**Spec:** `docs/superpowers/specs/2026-08-03-component-surface-redesign-design.md`

## Global Constraints

- Grasshopper canvas only. No Rhino-side plugin work, no Rhino Python environment changes.
- `src/tree_forest_compas/` is not modified.
- Python floor is 3.9 (Rhino 8 CPython target). No 3.10+ syntax in `src/`.
- All builds must finish with 0 warnings: `dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj`.
- Full pytest must stay green: `.venv/Scripts/python.exe -m pytest -q` (119 passed, 1 deliberate skip at time of writing).
- Port nicknames name the type: `PAT`, `SUP`, `PRB`, `RLX`, `RES`, `CTL`, `STY`. Full parameter names stay descriptive.
- Tab constants after this plan: `01 Model`, `02 Form Finding`, `03 Visualise`, `04 Masonry`, `05 Engineering`, `06 Fabrication`, `07 Delivery`, `90 System`.
- No em dashes in any prose or docs.
- Commit after every task (local only; never push).
- Run all commands from the repository root: `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`.

## New component GUIDs (fixed, use exactly these)

| Component | GUID |
| --- | --- |
| Pattern | `7c1a2e9b-4d3f-48a6-9b2e-51c8f0a7d310` |
| Supports | `b8e4f6c2-91a7-4b5d-8c3e-2f9d0a6b7e41` |
| Loads | `3f9b7d21-6c84-4e0a-b5d9-8a1c2e4f6072` |
| TNA Relax | `e5a0c8d4-2b7f-4963-a1e8-7d3b9f5c2084` |
| TNA Solve | `9d2f4b86-7e1a-4c50-b3f7-6a8e0c9d1235` |
| FD Solve | `4b8c6e0a-3d9f-47b2-95c1-e7a2d8f4b096` |
| Control | `a6d19e73-5f2b-4c8e-b0a4-9c3e7d1f5b28` |
| Display | `1e7b3a95-8c4d-4f26-a9b0-5d2c8e6f7143` |
| Style | `c3f8a2d6-4e9b-4071-8f5a-b1d7c9e3a250` |
| Deconstruct | `68d0b4f2-9a3e-4c17-85d6-f2b8a0c4e961` |
| Export | `f2a6c8e4-1b5d-49a3-b7e0-3c9f5d8a2617` |

`Backend Health` keeps its existing GUID `b0f27564-8304-4b4c-863f-871fc8682373`.

---

### Task 1: Unified Result envelope in the Python worker

**Files:**
- Modify: `src/ananke_equilibrium/codec.py` (add two wrapper functions near `encode_tna_result` / `encode_solved_case`)
- Modify: `src/ananke_equilibrium/worker.py` (the `tna.solve` and `fd.solve` branches of `dispatch`)
- Test: `tests/test_unified_result.py` (new)

**Interfaces:**
- Consumes: existing `encode_tna_result(...)` and `encode_solved_case(...)` in `codec.py` (read them first; reuse their outputs unchanged as the inner payload).
- Produces: `encode_result(solver: str, payload: dict) -> dict` in `codec.py`. The returned dict is the inner payload plus three keys: `"kind": "Result"`, `"solver": solver` (`"tna"` or `"fd"`), and `"resultSchema": "0.2"`. Every existing key of the inner payload is preserved at the top level. Worker `tna.solve` and `fd.solve` responses carry this envelope. Task 3's C# decoder relies on exactly these three key names.

- [ ] **Step 1: Read the two existing encoders**

Run: `grep -n "def encode_tna_result\|def encode_solved_case" src/ananke_equilibrium/codec.py`
Read both functions fully. Note the exact top-level keys each produces (the FD one will not have form/force graph keys; that is the point of the optional reciprocal).

- [ ] **Step 2: Write the failing test**

Create `tests/test_unified_result.py`:

```python
"""The worker returns one Result envelope from both solvers.

The C# side keys a single ResultDto off three fields: kind, solver, and
resultSchema. Everything else is the existing per-solver payload unchanged,
so old keys stay where the codecs already put them.
"""

from __future__ import annotations

import pytest

from ananke_equilibrium.codec import encode_result


def test_envelope_adds_exactly_three_keys():
    inner = {"a": 1, "nested": {"b": 2}}
    out = encode_result("tna", inner)

    assert out["kind"] == "Result"
    assert out["solver"] == "tna"
    assert out["resultSchema"] == "0.2"
    assert out["a"] == 1
    assert out["nested"] == {"b": 2}
    assert set(out) == {"kind", "solver", "resultSchema", "a", "nested"}


def test_envelope_rejects_unknown_solver():
    with pytest.raises(ValueError):
        encode_result("ags", {})


def test_envelope_does_not_mutate_the_inner_payload():
    inner = {"kind": "TnaResult"}
    encode_result("tna", inner)
    assert inner == {"kind": "TnaResult"}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_unified_result.py -q`
Expected: FAIL with `ImportError: cannot import name 'encode_result'`.

- [ ] **Step 4: Implement `encode_result` in codec.py**

Place next to the existing encoders:

```python
def encode_result(solver, payload):
    """Wrap a per-solver payload in the unified Result envelope.

    The inner payload is preserved key for key so existing decoders keep
    working; the envelope adds only the discriminator the single C#
    ResultDto needs. ``kind`` is overwritten deliberately: the object on
    the wire is a Result, whatever the solver called it internally.
    """
    if solver not in ("tna", "fd"):
        raise ValueError("solver must be 'tna' or 'fd', got {!r}".format(solver))
    out = dict(payload)
    out["kind"] = "Result"
    out["solver"] = solver
    out["resultSchema"] = "0.2"
    return out
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_unified_result.py -q`
Expected: 3 passed.

- [ ] **Step 6: Wrap the two dispatch branches**

In `worker.py`, find the `dispatch` branches for `"tna.solve"` and `"fd.solve"` (grep `"tna.solve"` and `"fd.solve"` inside `dispatch`). Wherever each currently returns `result_response(request_id, <encoded>)`, change the encoded value to `encode_result("tna", <encoded>)` or `encode_result("fd", <encoded>)` respectively. Import `encode_result` beside the other codec imports at the top of `worker.py`.

- [ ] **Step 7: Add a dispatch-level test to the same file**

Append to `tests/test_unified_result.py` (model the request helper on the existing one in `tests/test_worker_protocol.py`; copy its `request(...)` helper into this file rather than importing test internals):

```python
def request(command, request_id="t-1", payload=None):
    return {
        "protocolVersion": 1,
        "id": request_id,
        "command": command,
        "payload": payload or {},
    }


def test_tna_solve_dispatch_returns_result_kind():
    pytest.importorskip("compas_tna")
    from ananke_equilibrium.worker import dispatch

    # Reuse the known-good tna.solve payload from test_worker_protocol.py:
    # copy the smallest passing tna.solve request payload from that file
    # verbatim here (the 3x3 grid one). Then:
    response = dispatch(request("tna.solve", payload=PAYLOAD))
    assert response["result"]["kind"] == "Result"
    assert response["result"]["solver"] == "tna"
```

Copy the smallest working `tna.solve` payload from `tests/test_worker_protocol.py` into a module-level `PAYLOAD` constant. Do the same for an `fd.solve` variant asserting `solver == "fd"`.

- [ ] **Step 8: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: everything green. Existing worker-protocol tests that assert `kind == "TnaResult"` or `kind == "SolvedCase"` on solve responses will now fail; update those assertions to `"Result"` and add `solver` assertions. Do not weaken any other assertion.

- [ ] **Step 9: Commit**

```bash
git add src/ananke_equilibrium/codec.py src/ananke_equilibrium/worker.py tests/
git commit -m "Wrap both solver responses in one Result envelope"
```

---

### Task 2: `export.compas` worker command

**Files:**
- Modify: `src/ananke_equilibrium/worker.py` (`ALLOWED_COMMANDS`, new dispatch branch)
- Create: `src/ananke_equilibrium/gh/export.py`
- Test: `tests/test_export_compas.py` (new)

**Interfaces:**
- Consumes: the unified Result payload from Task 1 (a dict with `equilibrium`-style vertex/edge/face data; read `encode_tna_result` for the exact key names and use those).
- Produces: worker command `"export.compas"` taking `{"result": <Result payload>}` and returning `{"thrustMesh": str|None, "formDiagram": str|None, "forceDiagram": str|None, "compasVersion": str}` where each string is `compas.data` JSON (`json_dumps`) rebuildable via `json_loads`. Task 11 (Export component) calls this command.

- [ ] **Step 1: Establish the exact result keys**

Run: `grep -n "vertices\|faces\|edges" src/ananke_equilibrium/codec.py | head -30`
Note the key names `encode_tna_result` uses for thrust vertices, faces, and the form/force graphs. The extractor below must read those exact keys; adjust the names in the code to match what you find.

- [ ] **Step 2: Write the failing test**

Create `tests/test_export_compas.py`:

```python
"""export.compas turns a Result payload into native COMPAS JSON.

The output must rebuild into real COMPAS objects with json_loads, because
that is the entire point: another tool receives working datastructures,
not our schema.
"""

from __future__ import annotations

import pytest

compas = pytest.importorskip("compas")
from compas.data import json_loads

from ananke_equilibrium.gh.export import compas_export_payload


def _minimal_result():
    return {
        "kind": "Result",
        "solver": "fd",
        "resultSchema": "0.2",
        # Use the real key names found in Step 1. Shown here with the
        # names to replace:
        "equilibrium": {
            "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.5], [0.0, 1.0, 0.0]],
            "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
            "faces": [[0, 1, 2, 3]],
        },
    }


def test_thrust_mesh_round_trips_into_a_compas_mesh():
    payload = compas_export_payload(_minimal_result())

    assert payload["compasVersion"] == compas.__version__
    mesh = json_loads(payload["thrustMesh"])
    assert mesh.number_of_vertices() == 4
    assert mesh.number_of_faces() == 1


def test_fd_result_has_no_diagrams():
    payload = compas_export_payload(_minimal_result())
    assert payload["formDiagram"] is None
    assert payload["forceDiagram"] is None


def test_result_without_faces_has_no_mesh():
    result = _minimal_result()
    result["equilibrium"]["faces"] = []
    payload = compas_export_payload(result)
    assert payload["thrustMesh"] is None
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export_compas.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.gh.export'`.

- [ ] **Step 4: Implement `gh/export.py`**

```python
"""Native COMPAS JSON from a unified Result payload.

compas.data JSON is the interop currency of the whole COMPAS ecosystem;
emitting it means a receiving Python rebuilds real datastructures with
json_loads instead of parsing this plugin's schema.
"""

from __future__ import annotations

import compas
from compas.data import json_dumps
from compas.datastructures import Graph
from compas.datastructures import Mesh


def _graph_json(graph_payload):
    """One diagram graph payload to compas Graph JSON, or None."""
    if not graph_payload:
        return None
    graph = Graph()
    for vertex in graph_payload.get("vertices", ()):
        xyz = vertex["point"]
        graph.add_node(key=int(vertex["id"]), x=xyz["x"], y=xyz["y"], z=xyz["z"])
    for edge in graph_payload.get("edges", ()):
        graph.add_edge(int(edge["u"]), int(edge["v"]))
    return json_dumps(graph)


def compas_export_payload(result):
    """Build the export.compas response from a Result payload."""
    equilibrium = result.get("equilibrium") or {}
    vertices = equilibrium.get("vertices") or []
    faces = equilibrium.get("faces") or []

    thrust = None
    if vertices and faces:
        mesh = Mesh.from_vertices_and_faces(
            [list(map(float, xyz)) for xyz in vertices],
            [list(map(int, face)) for face in faces],
        )
        thrust = json_dumps(mesh)

    return {
        "thrustMesh": thrust,
        "formDiagram": _graph_json(result.get("formGraph")),
        "forceDiagram": _graph_json(result.get("forceGraph")),
        "compasVersion": compas.__version__,
    }
```

Adjust the key names (`equilibrium`, `vertices`, `faces`, `formGraph`, `forceGraph`, and the graph-vertex shape) to the exact names found in Step 1. The graph payload shape comes from `TnaDiagramGraphDto` serialisation: vertices have `id` and `point {x,y,z}`, edges have `u`/`v`; verify against one encoded result in the worker tests.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_export_compas.py -q`
Expected: 3 passed.

- [ ] **Step 6: Wire the worker command**

In `worker.py`: add `"export.compas"` to `ALLOWED_COMMANDS`; in `dispatch`, add:

```python
if command == "export.compas":
    from .gh.export import compas_export_payload
    result = payload.get("result")
    if not isinstance(result, dict) or result.get("kind") != "Result":
        raise ProtocolError("export.compas requires a Result payload.")
    return result_response(request_id, compas_export_payload(result))
```

Match the surrounding branches' style for `ProtocolError` construction (read one; it may take extra arguments).

- [ ] **Step 7: Dispatch test + full suite**

Append to `tests/test_export_compas.py` a dispatch test using the same `request` helper pattern as Task 1, asserting a valid response for a minimal Result and an error response for `{"result": {"kind": "Nope"}}`. Then run: `.venv/Scripts/python.exe -m pytest -q`. Expected: green. Note `tests/test_worker_protocol.py` has a test asserting the exact `ALLOWED_COMMANDS` set or the health `commands` list; update it to include `export.compas`.

- [ ] **Step 8: Commit**

```bash
git add src/ananke_equilibrium tests/
git commit -m "Add export.compas worker command producing native COMPAS JSON"
```

---

### Task 3: C# `ResultDto`, Goo, Param, and decoder

**Files:**
- Create: `plugin/native_v02/Contracts/ResultContracts.cs`
- Modify: `plugin/native_v02/Contracts/ContractCore.cs` (add `ContractKinds.Result`)
- Modify: `plugin/native_v02/Components/TnaWorkerResultCodec.cs` and `plugin/native_v02/Components/WorkerResultCodec.cs` (accept the envelope)
- Test: `tests/native_smoke/Program.cs` (extend)

**Interfaces:**
- Consumes: Task 1's envelope keys (`kind: "Result"`, `solver`, `resultSchema`) and every existing `TnaResultDto` member (see `plugin/native_v02/Contracts/TnaContracts.cs`).
- Produces: `ResultDto : ContractDto` with `string Solver`, plus all current `TnaResultDto` members where the reciprocal ones are nullable. `ResultGoo : ContractGoo<ResultDto>`, `ResultParam : ContractParam<ResultGoo>` with nickname `RES`. Tasks 8 through 12 consume these exact names.

- [ ] **Step 1: Read the current TnaResultDto and one Goo/Param pair**

Read `plugin/native_v02/Contracts/TnaContracts.cs` (record `TnaResultDto`) and the `TnaResultGoo`/`TnaResultParam` definitions in `ContractGoos.cs:421` / `ContractParams.cs:154` to copy their exact base-class usage and display-name conventions.

- [ ] **Step 2: Add the contract kind**

In `ContractCore.cs`, find the `ContractKinds` class (grep `class ContractKinds`) and add `public const string Result = "Result";` alongside the existing kinds.

- [ ] **Step 3: Create `ResultContracts.cs`**

Define `ResultDto` as a copy of `TnaResultDto`'s members with these changes: base kind `ContractKinds.Result`; new `public string Solver { get; init; } = "tna";` and `public string ResultSchema { get; init; } = "0.2";`; every TNA-only member (`FormGraph`, `ForceGraph`, `Mappings`, `EdgeStates`, `AnalysisPlane`, boundary/opening records if present) made nullable or defaulted empty; `Equilibrium` stays required. `ValidatePayload` rules: `Solver` must be `"tna"` or `"fd"`; `Equilibrium` must not be null; when `Solver == "tna"`, `FormGraph` and `ForceGraph` must not be null. Then `ResultGoo` and `ResultParam` copied from the TnaResult pair with `NickName = "RES"` and name `"Result"`.

- [ ] **Step 4: Teach the codecs the envelope**

In `TnaWorkerResultCodec.cs` (and `WorkerResultCodec.cs` for FD), find where the response JSON is deserialised to `TnaResultDto` / `EquilibriumResultDto`. Add deserialisation to `ResultDto` keyed on `kind == "Result"`: TNA responses map straight across (same member names); FD responses populate `Equilibrium` from the existing solved-case mapping and leave reciprocal members null with `Solver = "fd"`. Keep the old decode paths compiling for now; Tasks 8 to 10 switch the callers, Task 12 deletes the leftovers.

- [ ] **Step 5: Build**

Run: `dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -v minimal --nologo`
Expected: Build succeeded, 0 warnings.

- [ ] **Step 6: Extend the native smoke test**

Read `tests/native_smoke/Program.cs` and `tests/native_smoke/README.md` for how it exercises contracts. Add construction plus `Validate()` checks: a valid TNA `ResultDto` (with graphs), a valid FD one (without), and an invalid one (`Solver = "tna"`, no graphs) asserting validation errors are produced. Run per its README.

- [ ] **Step 7: Commit**

```bash
git add plugin/native_v02 tests/native_smoke
git commit -m "Add unified ResultDto with optional reciprocal block"
```

---

### Task 4: Spine contracts (`AnchoredPatternDto`, `ProblemDto`, `RelaxedDto`)

**Files:**
- Create: `plugin/native_v02/Contracts/SpineContracts.cs`
- Modify: `plugin/native_v02/Contracts/ContractCore.cs` (three new kinds)
- Test: `tests/native_smoke/Program.cs` (extend)

**Interfaces:**
- Consumes: `TnaPatternDto`, `LoadCaseDto`, `TnaPreparedDto` (all existing).
- Produces, consumed by Tasks 6 to 10 under exactly these names:

```csharp
public sealed record AnchoredPatternDto : ContractDto   // kind "AnchoredPattern"
{
    public TnaPatternDto? Pattern { get; init; }
    public IReadOnlyList<int> AnchorNodeIds { get; init; } = Array.Empty<int>();
    public double SnapTolerance { get; init; } = 1.0e-3;
}

public sealed record ProblemDto : ContractDto           // kind "Problem"
{
    public AnchoredPatternDto? Anchored { get; init; }
    public LoadCaseDto? Load { get; init; }
}

public sealed record RelaxedDto : ContractDto           // kind "Relaxed"
{
    public TnaPreparedDto? Prepared { get; init; }
    public ProblemDto? Problem { get; init; }
}
```

plus Goo/Param pairs `AnchoredPatternGoo/Param` (nickname `SUP`, name "Anchored Pattern"), `ProblemGoo/Param` (`PRB`, "Problem"), `RelaxedGoo/Param` (`RLX`, "Relaxed"). The existing `TnaPatternParam` keeps serving `PAT`; change its nickname to `PAT` where it is currently something else (check `ContractParams.cs` or `TnaWorkflowContracts.cs` for where `TnaPatternParam` lives and its current nickname).

- [ ] **Step 1: Locate `TnaPatternParam` and the prepared param**

Run: `grep -rn "class TnaPatternParam\|class TnaPreparedParam\|class TnaPatternGoo\|class TnaPreparedGoo" plugin/native_v02/`
Record where they live and their nicknames.

- [ ] **Step 2: Write the DTOs, kinds, validation**

Add kinds `AnchoredPattern`, `Problem`, `Relaxed` to `ContractKinds`. Validation: `AnchoredPatternDto` requires a valid `Pattern` and at least one anchor id, all ids within `Pattern.Topology` vertex count; `ProblemDto` requires valid `Anchored` and a `Load` whose `TopologyHash` matches `Anchored.Pattern.Topology.TopologyHash`; `RelaxedDto` requires both members valid. Copy the `ValidatePayload(List<string> errors)` pattern from `TnaControlDto` in `TnaContracts.cs:37`.

- [ ] **Step 3: Goo/Param pairs and PAT nickname**

Copy the Goo/Param shape found in Step 1. Set nicknames exactly `SUP`, `PRB`, `RLX`. Set `TnaPatternParam`'s nickname to `PAT`.

- [ ] **Step 4: Attach the Problem to the Result**

The spec's provenance rule says every output carries its inputs, so Deconstruct and Export work at any depth. Add to `ResultDto` (Task 3's file): `public ProblemDto? Problem { get; init; }`. It stays optional in validation (the worker does not send it; the solver components attach it client-side in Task 9).

- [ ] **Step 5: Build, smoke, commit**

Build (0 warnings), add smoke constructions of all three DTOs (valid and one invalid each) to `tests/native_smoke/Program.cs`, run it, then:

```bash
git add plugin/native_v02 tests/native_smoke
git commit -m "Add spine contracts: AnchoredPattern, Problem, Relaxed"
```

---

### Task 5: Checklist-mode value lists

**Files:**
- Modify: `plugin/native_v02/Components/NativeComponentBase.cs` (`ComponentValueListSpec`, `SuggestedValueListPlacement`)

**Interfaces:**
- Consumes: current `ComponentValueListSpec(int InputIndex, string Name, IReadOnlyList<(string Label, string Value)> Items, string DefaultValue)`.
- Produces: an added optional member `bool CheckList { get; init; } = false`. When true, placement sets `valueList.ListMode = GH_ValueListMode.CheckList` and selects every item whose value appears in the comma-separated `DefaultValue`. Task 9's Display Elements input relies on this.

- [ ] **Step 1: Extend the record and placement**

In `NativeComponentBase.cs`: add `bool CheckList = false` as a final optional positional/init member on `ComponentValueListSpec`. In `SuggestedValueListPlacement.Create`, replace the fixed `ListMode = GH_ValueListMode.DropDown` with `spec.CheckList ? GH_ValueListMode.CheckList : GH_ValueListMode.DropDown`, and replace the single-select block: when `CheckList`, split `spec.DefaultValue` on `,`, trim, and set `item.Selected = values.Contains(item value, OrdinalIgnoreCase)` for every item instead of `SelectItem`.

- [ ] **Step 2: Build and commit**

Build (0 warnings; existing callers compile unchanged because the member is optional), then:

```bash
git add plugin/native_v02/Components/NativeComponentBase.cs
git commit -m "Support checklist-mode suggested value lists"
```

---

### Task 6: Spine components file with Pattern and Supports

**Files:**
- Create: `plugin/native_v02/Components/SpineComponents.cs`
- Modify: `plugin/native_v02/Components/NativeComponentBase.cs` (tab constants)

**Interfaces:**
- Consumes: `GeometryTopologyBuilder` (registration logic), `TnaPatternDto`, `AnchoredPatternDto`, value-list base behaviour, existing preview base `NativePreviewComponentBase`.
- Produces: `PatternComponent` (name "Pattern", nickname "Pattern", GUID from the table, subcategory `ComponentCategories.Model`, output `TnaPatternParam` named "Pattern" nickname `PAT`) and `SupportsComponent` (name "Supports", inputs `PAT` + points/node-ids + snap tolerance, output `AnchoredPatternParam` `SUP`). Task 7 consumes `SUP`.

- [ ] **Step 1: Renumber the tab constants**

In `ComponentCategories` replace the block with:

```csharp
public const string Category = "Ananke COMPAS";
public const string Model = "01 Model";
public const string FormFinding = "02 Form Finding";
public const string Visualise = "03 Visualise";
public const string Masonry = "04 Masonry";
public const string Engineering = "05 Engineering";
public const string Fabrication = "06 Fabrication";
public const string Delivery = "07 Delivery";
public const string System = "90 System";
```

Old names `GraphicStatics`, `Visualisation`, `Query` are deleted; fix every compile error this causes by mapping `Visualisation -> Visualise` and `Query -> System` in the files that still reference them (they will be deleted in Task 12; a mechanical rename keeps the build green until then).

- [ ] **Step 2: Write `PatternComponent`**

Adapt `TnaPatternComponent` (`TnaWorkflowComponents.cs:26-293`): same inputs (Geometry list, Mode with the existing six-value list, Resolution, Weld Tolerance), same registration call into `GeometryTopologyBuilder.Build`, same light preview of pattern edges, same unit-warning behaviour. Changes only: class name `PatternComponent`, component name/nickname "Pattern", the new GUID, output parameter renamed "Pattern" nickname `PAT`, and drop the second `Topology` output (the pattern carries its topology; Deconstruct exposes data later). Keep the value list spec.

- [ ] **Step 3: Write `SupportsComponent`**

Adapt `TnaSupportsComponent` (`TnaWorkflowComponents.cs:295+`): inputs `PAT` (TnaPatternParam), anchor Points list, optional node id list, snap tolerance; snap logic unchanged. Output: an `AnchoredPatternDto { Pattern = source, AnchorNodeIds = snapped ids, SnapTolerance = tol }` through `AnchoredPatternParam` (`SUP`). Keep the anchor-dot preview and the existing both-ends-anchored warning text, appending one sentence: "Anchor only the true structural supports; intermediate boundary vertices should stay free so openings can sag."

- [ ] **Step 4: Build and commit**

Build (0 warnings).

```bash
git add plugin/native_v02
git commit -m "Add Pattern and Supports on the shared spine; renumber tabs"
```

---

### Task 7: Loads component

**Files:**
- Modify: `plugin/native_v02/Components/SpineComponents.cs`

**Interfaces:**
- Consumes: `AnchoredPatternDto` (`SUP`), `LoadCaseDto` (existing), `ProblemDto` from Task 4.
- Produces: `LoadsComponent`, GUID from the table, subcategory Model. Inputs: `SUP`; `Vector` (Vector3d, default `(0,0,-1)`); `NodeIDs` (int list, optional, empty = every node); `Factor` (number, default `1.0`). Output: `ProblemParam` (`PRB`). Task 8 and Task 10 consume `PRB`.

- [ ] **Step 1: Read how LoadCaseComponent builds a LoadCaseDto**

Read `InputComponents.cs:366-618` and record the exact `LoadCaseDto` member assignments for a uniform-nodes case and a node-id case (`Distribution`, `NodeIds`, `Vectors`, `TopologyHash`, `ForceUnit`, `Name`).

- [ ] **Step 2: Implement**

`SolveInstance`: read `SUP`; validate; build one `LoadCaseDto` with `Name = "load"`, `Distribution = "uniform_nodes"` when `NodeIDs` is empty else the node-id distribution found in Step 1, `Vectors` = the single vector times `Factor` (broadcast semantics exactly as `LoadCaseComponent` does for one vector), `TopologyHash` from `SUP.Pattern.Topology`, `ForceUnit = "kN"`. Output `new ProblemDto { Anchored = sup, Load = loadCase }` after `EnsureValid`.

- [ ] **Step 3: Build and commit**

```bash
git add plugin/native_v02/Components/SpineComponents.cs
git commit -m "Add Loads: one vector, optional nodes, one factor, out comes the Problem"
```

---

### Task 8: TNA Relax and Control

**Files:**
- Create: `plugin/native_v02/Components/SolverComponents.cs`
- Reference (adapt from): `plugin/native_v02/Components/TnaWorkflowComponents.cs` (`TnaRelaxBoundariesComponent`), `plugin/native_v02/Components/TnaComponents.cs` (`TnaControlComponent`), `plugin/native_v02/Components/TnaWorkflowWorkerCodec.cs`

**Interfaces:**
- Consumes: `ProblemDto` (`PRB`), `TnaControlDto`, the existing `tna.prepare` worker payload builder in `TnaWorkflowWorkerCodec.cs`.
- Produces: `TnaRelaxComponent` (inputs `PRB`, Force Density number default 1.0, Sag % number default 10; output `RelaxedParam` `RLX`; GUID from table; subcategory FormFinding) and `ControlComponent` (inputs Alpha 100, Horizontal Iterations 100, Vertical Iterations 100, Tolerance 1e-3; output `TnaControlParam` `CTL`; GUID from table; subcategory FormFinding). Task 9 consumes `RLX` and `CTL`.

- [ ] **Step 1: Write `ControlComponent`**

Adapt `TnaControlComponent` (`TnaComponents.cs:18-151`) dropping its Mode/Value inputs if present (Mode and Value live on TNA Solve): the component only bundles Alpha, HIter, VIter, Tolerance into a `TnaControlDto` (leave `HeightMode`/`HeightValue` at their defaults; TNA Solve overrides them). Name "Control", nickname "Control", output nickname `CTL`. Description must include: "Radial and other high-valence patterns need far more horizontal iterations than a quad grid; raise them until the reported reciprocity angle falls to near zero."

- [ ] **Step 2: Write `TnaRelaxComponent`**

Adapt `TnaRelaxBoundariesComponent` (`TnaWorkflowComponents.cs:548-955`): replace its pattern input with `PRB`; internally pass `prb.Anchored.Pattern` and `prb.Anchored.AnchorNodeIds` into the same worker `tna.prepare` call it makes today (follow its use of `TnaWorkflowWorkerCodec`); keep the sag/opening logic, diagnostics, and light preview unchanged. Output `new RelaxedDto { Prepared = <worker result>, Problem = prb }` through `RLX`. Keep the held-boundary warning verbatim.

- [ ] **Step 3: Build and commit**

```bash
git add plugin/native_v02/Components/SolverComponents.cs
git commit -m "Add TNA Relax consuming the Problem, and the shared Control"
```

---

### Task 9: TNA Solve and FD Solve returning the unified Result

**Files:**
- Modify: `plugin/native_v02/Components/SolverComponents.cs`
- Reference (adapt from): `TnaEquilibriumComponent` (`TnaWorkflowComponents.cs:957+`), `FDSolveComponent` (`FormFindingComponents.cs:19-269`), `WorkerPayloads.cs`

**Interfaces:**
- Consumes: `RelaxedDto`, `ProblemDto`, `TnaControlDto`, Task 3's `ResultDto` decode paths.
- Produces: `TnaSolveComponent2` named "TNA Solve" (inputs `RLX`, Mode text with the Crown Height / Force Scale value list, Value number default 5.0, optional `CTL`; output `ResultParam` `RES`; GUID from table) and `FdSolveComponent2` named "FD Solve" (inputs `PRB`, Force Density number-or-list default 1.0, optional `CTL`; output `RES`; GUID from table). Both subcategory FormFinding. Tasks 10 and 11 consume `RES`.

- [ ] **Step 1: TNA Solve**

Adapt `TnaEquilibriumComponent` wholesale (it is already task-capable with worker dispatch and the optional Control merge added in commit `5e59d14`): input 0 becomes `RelaxedParam`; the prepared state is `rlx.Prepared` and the load case is `rlx.Problem.Load` (drop the separate Load Case input and the default-load fallback; the Problem always carries a load). Decode the worker response into `ResultDto` (Task 3 codec) instead of `TnaResultDto`; set nothing else. Output `RES`.

- [ ] **Step 2: FD Solve**

Adapt `FDSolveComponent`: inputs `PRB`, ForceDensity, optional `CTL`. Build the worker `fd.solve` payload the way the current component does from an `EquilibriumProblemDto` (construct one internally from `prb.Anchored.Pattern.Topology`, a `SupportSetDto` built from `prb.Anchored.AnchorNodeIds`, and `prb.Load`; copy the member mapping from `EquilibriumProblemComponent`, `InputComponents.cs:620-727`). Decode the enveloped response into `ResultDto` with `Solver == "fd"`. Output `RES`.

- [ ] **Step 3: Build and commit**

```bash
git add plugin/native_v02/Components/SolverComponents.cs
git commit -m "TNA Solve and FD Solve return one unified Result"
```

---

### Task 10: Deconstruct and Style

**Files:**
- Create: `plugin/native_v02/Components/VisualiseComponents.cs`
- Reference (adapt from): `TnaQueryComponents.cs` (all three), `QueryComponents.cs` (`ResultBreakdownComponent`), `GraphicDiagramDisplayComponent.cs` (style presets)

**Interfaces:**
- Consumes: `ResultDto` (`RES`).
- Produces: `DeconstructComponent` (GUID from table, subcategory Visualise, input `RES`, outputs listed below) and `StyleComponent` (GUID from table, subcategory Visualise; inputs Preset text via value list from the presets found in `GraphicDiagramDisplayComponent`, Weight Scale number default 1.0, Vector Scale number default 0.0 meaning auto; output `StyleGoo` `STY`). New small `StyleDto : ContractDto` (kind "Style") with `string Preset`, `double WeightScale`, `double VectorScale` lives at the top of this file. Task 11 consumes `STY`.

- [ ] **Step 1: Deconstruct outputs**

One component, outputs in this order, adapted from the three TNA query components and `ResultBreakdownComponent` (their extraction code is the reference; copy the mesh/line reconstruction from `TnaGeometryComponent`, the aligned member table from `TnaMembersComponent`, the actions from `TnaActionsComponent`):

`Thrust Mesh` (Mesh), `Member Lines` (Line list), `Form Lines` (Line list, empty for FD), `q` (numbers), `H` (numbers, empty for FD), `F` (numbers), `Force State` (text), `Member IDs` (int), `Node IDs` (int), `Support Points` (Point3d), `Load Points` (Point3d), `Load Vectors` (Vector3d), `Reaction Points` (Point3d), `Reaction Vectors` (Vector3d), `Residuals` (Vector3d), `Diagnostics` (text lines), `Report` (text).

For FD results the reciprocal-only streams come out empty and the Report says "FD result: no reciprocal diagram." No errors for absence.

- [ ] **Step 2: Style**

Implement `StyleDto` plus its Goo/Param (`STY`) inline in this file, and `StyleComponent` bundling the three inputs. Preset names: read the preset list out of `GraphicDiagramDisplayComponent` and offer them as the value list.

- [ ] **Step 3: Build and commit**

```bash
git add plugin/native_v02
git commit -m "Add Deconstruct and Style for the unified Result"
```

---

### Task 11: Display and Export

**Files:**
- Modify: `plugin/native_v02/Components/VisualiseComponents.cs` (Display)
- Create: `plugin/native_v02/Components/DeliveryComponents.cs` (Export)
- Reference (adapt from): `TnaReciprocalComponent.cs` (diagram layout build), `GraphicDiagramDisplayComponent.cs` (styled drawing), `EquilibriumPreviewComponent` (`QueryComponents.cs:217+`, vector drawing), worker call pattern from `FDSolveComponent`

**Interfaces:**
- Consumes: `ResultDto` (`RES`), `StyleDto` (`STY`), checklist value lists (Task 5), worker command `export.compas` (Task 2).
- Produces: `DisplayComponent` (GUID from table, subcategory Visualise) and `ExportComponent` (GUID from table, subcategory Delivery). Final surface complete.

- [ ] **Step 1: Display inputs and outputs**

Inputs: `RES`; optional `STY`; `Elements` (text list, checklist value list with values `form,thrust,force,loads,reactions,residuals`, default `thrust,force`); `Metric` (text, drop-down `none,q,H,F`, default `none`); `Weight` (number, default 0 = from Style); `Vector Scale` (number, default 0 = auto); `Gap` (number, default 0.15, diagram offset ratio).

Outputs: `Thrust Mesh` (Mesh), `Form Lines`, `Thrust Lines`, `Force Lines`, `Load Lines`, `Reaction Lines` (Line lists), `Report` (text).

- [ ] **Step 2: Implement the pipeline**

Order of operations inside `SolveInstance` plus the preview overrides (base class `NativePreviewComponentBase`):

1. Build the diagram layout from the Result's reciprocal block by lifting the layout construction out of `TnaReciprocalComponent` (side-by-side placement, gap ratio). For FD results skip it and append "FD result: no reciprocal diagram" to the Report; the `force` element is simply absent.
2. Auto scales: `bbox` = bounding box of equilibrium vertices; `diag = bbox.Diagonal.Length`; `maxAction` = largest load/reaction magnitude; `autoVectorScale = maxAction > 1e-12 ? 0.15 * diag / maxAction : 1.0`. Explicit input (> 0) wins, then Style's value (> 0), then auto. Report states which was used and its value.
3. Elements filter selects which streams are built and drawn. Metric recolours member lines by the chosen quantity using the colour ramp already present in `GraphicDiagramDisplayComponent`; copy it.
4. Viewport drawing follows the `DrawViewportWires` pattern of `GraphicDiagramDisplayComponent` with the Style preset's weights times `Weight`.

- [ ] **Step 3: Export**

Inputs: `RES`; `Format` (text drop-down `Contract,COMPAS`, default `Contract`); `Path` (text, optional). Outputs: `JSON` (text), `Written` (text, file path or empty).

`Contract`: serialise the `ResultDto` with the same serializer options the codecs use (grep `JsonSerializer` in `plugin/native_v02/Components/*.cs` and reuse the shared options instance). `COMPAS`: dispatch `export.compas` through the worker exactly as `FDSolveComponent` dispatches solves, sending `{"result": <the raw result payload>}`; the raw payload must be retained on `ResultDto` or re-serialised from it (check how the codec stores the wire JSON; if it does not, serialise the DTO with the wire options, which round-trips because member names match). Concatenate the returned strings into one JSON object `{"thrustMesh": ..., "formDiagram": ..., "forceDiagram": ..., "compasVersion": ...}` for the `JSON` output. If `Path` is non-empty, `File.WriteAllText(path, json)` inside try/catch reporting failure as a runtime error message, and echo the path in `Written`.

- [ ] **Step 4: Build and commit**

```bash
git add plugin/native_v02
git commit -m "Add Display and Export; drawing lives in one place"
```

---

### Task 12: Delete the old surface, ledger the GUIDs, move Backend Health

**Files:**
- Delete: `plugin/native_v02/Components/InputComponents.cs`, `TnaComponents.cs`, `TnaQueryComponents.cs`, `TnaReciprocalComponent.cs`, `GraphicDiagramDisplayComponent.cs`, the `ResultBreakdownComponent` and `EquilibriumPreviewComponent` classes in `QueryComponents.cs`, the four old classes in `TnaWorkflowComponents.cs`, the old `FDSolveComponent` in `FormFindingComponents.cs`
- Modify: `FormFindingComponents.cs` (keep `BackendHealthComponent`, subcategory to `ComponentCategories.System`)
- Create: `docs/removed-guids.md`

**Interfaces:**
- Consumes: nothing new. Produces: a compiling plugin containing exactly the twelve new components plus Backend Health.

- [ ] **Step 1: Write the ledger first**

Create `docs/removed-guids.md` with the deletion date and this exact table (source: the pre-deletion inventory):

```markdown
# Removed component GUIDs

Deleted 2026-08-03 by decision in the component-surface redesign spec.
Saved definitions referencing these GUIDs lose those components on open.

| Component | GUID |
| --- | --- |
| Network | a9f470fc-e1a8-46c4-ba4c-d7fbe515b161 |
| Support Set | 73b719d9-9b24-4086-a023-a06313f4dd17 |
| Load Case | 1ba4e155-b5e5-4043-89b3-e062a8e72fb5 |
| Equilibrium Problem | 24868635-057b-4926-92d9-ec9a76bcf451 |
| FD Settings | 9de76173-8146-4b52-98d0-a0cc1c3d120a |
| FD Solve (v0.2) | cfcade39-f94d-4367-b9a8-9defedeff537 |
| TNA Control (v0.2) | 678439fc-d4d9-4734-9567-3f266d3e978b |
| TNA Solve (one-shot) | 8913cdd7-f563-4930-a310-fd62b3a31831 |
| TNA Pattern | 2fb2617f-d952-4f22-b7d5-0383c8cc203b |
| TNA Supports | fd767b85-9dc2-48a2-afdb-504f9db33640 |
| TNA Relax + Boundaries | 2f8fddfa-1e46-4546-afa7-c114db411b09 |
| TNA Equilibrium | 8dc94461-dcd8-4556-8ace-d201d2e1c6c3 |
| TNA Reciprocal | 30aa4b56-6d9e-47dd-8b15-94a56a046cf6 |
| Graphic Diagram Display | 0c17dc94-a6f0-48b0-98fa-ab6766c64912 |
| Equilibrium Preview | 471c5479-6c2c-479c-9372-3dc1fd31e85e |
| TNA Geometry | 3943da0e-bb1e-4375-9fa9-8b6e3019aacb |
| TNA Members | f543cb90-bef4-46ea-8510-7aa075c57279 |
| TNA Actions | 0ed716a8-744c-45dc-bc47-98b9e41d2f65 |
| Result Breakdown | c80b2201-c11b-4364-895e-5600ff6bcf01 |
```

- [ ] **Step 2: Delete and repair**

Delete the files and classes listed above. `BackendHealthComponent` moves to `ComponentCategories.System`. Any shared helpers the new components adapted from deleted files must have been copied, not referenced; the build finds every miss. Old DTOs referenced only by deleted components (`FDSettingsDto`, `EquilibriumProblemDto` if now unused, `GraphicDiagramDto` if Display absorbed the layout, plus their Goos/Params) are deleted too when nothing else references them; keep any the new code still uses.

- [ ] **Step 3: Icons**

Read how `PluginResources.Icon(iconName)` resolves names (grep `class PluginResources`) and `plugin/icons/icon-map.json`. Map the new icon names to existing art: Pattern -> `tna_pattern`, Supports -> `tna_supports`, Loads -> `load_case`, TNA Relax -> `tna_relax`, TNA Solve -> `tna_solve`, FD Solve -> `fd_solve`, Control -> `tna_control`, Display -> `graphic_diagram_display`, Style -> `diagram_style`, Deconstruct -> `result_breakdown`, Export -> `preview_payload`, Backend Health unchanged.

- [ ] **Step 4: Update the native smoke program**

Replace instantiations of deleted components with the twelve new ones; each constructs and reports its name, tab, and port nicknames so a port-registration regression fails off-canvas.

- [ ] **Step 5: Build, full pytest, commit**

Build (0 warnings), `.venv/Scripts/python.exe -m pytest -q` (green), then:

```bash
git add -A
git commit -m "Delete the v0.2 surface; twelve components and Backend Health remain"
```

---

### Task 13: Documentation and final verification

**Files:**
- Modify: `README.md` (component table and workflow diagram), `docs/component-taxonomy.md` (surface table, tab table)
- Test: full suite, build, smoke

- [ ] **Step 1: Rewrite the README component table**

Replace the twenty-component table with the twelve-component surface exactly as the spec's section 3 diagram, and replace the workflow diagram with:

```text
Geometry -> Pattern -> Supports -> Loads = Problem
Problem -> TNA Relax -> TNA Solve -> Result
Problem -> FD Solve ------------------> Result (same type)
Result -> Display / Deconstruct / Export
Control and Style feed the solvers and Display.
```

- [ ] **Step 2: Update component-taxonomy.md**

Surface table replaced with the twelve components; tab table updated to the renumbered sequence with `04 Masonry`, `05 Engineering`, `06 Fabrication` reserved and `07 Delivery` holding Export; note that capability flags and pyproject extras keep their existing names.

- [ ] **Step 3: Full verification**

Run all three and paste outputs into the commit message body:
- `.venv/Scripts/python.exe -m pytest -q`
- `dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -v minimal --nologo`
- the native smoke program per its README

- [ ] **Step 4: Commit**

```bash
git add README.md docs/
git commit -m "Document the twelve-component surface"
```

- [ ] **Step 5: Hand back for the manual canvas pass**

Not automatable: Param closes Rhino, runs `plugin\native_v02\Build-And-Install.ps1`, reopens, and walks the vault pattern end to end: Pattern, Supports (true anchors only), Loads, TNA Relax, Control with raised horizontal iterations, TNA Solve watching the reciprocity angle fall, Display with auto-scaled vectors, Deconstruct, Export in both formats. The redesign is done when that walk needs no reference to documentation.
