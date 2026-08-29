# Export Live Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export writes everything a Result can be (contract, COMPAS, tessellation when cells are wired, a columns mesh when the Mould block carries columns) in one component, and with Live on pushes that set to the studio on every solve, debounced, retrying a 409.

**Architecture:** Two new files hold the pure parts: `ExportPayloads.cs` (`ExportPlan.Kinds`, `ColumnsMesh.Build` and its JSON) and `LiveUploader.cs` (the uploader with its pure rules `RetryDelay`, `RouteFor`, `Outcome`, `SetKey`). Export keeps its contract, COMPAS and tessellation code and gains a plan loop, the columns payload, the Live wiring and two more outputs.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8, `System.Net.Http` (in the BCL), the Rhino-free reflection smoke harness.

**Spec:** `docs/superpowers/specs/2026-08-28-export-live-design.md`

## Global Constraints

- No em dashes anywhere, in code, comments, docs or commit messages.
- Full absolute Windows paths in any reply to Param.
- No Co-Authored-By or AI attribution in any commit.
- Commit locally after every task; never push.
- Every measured check runs in the smoke harness without launching Rhino and without network access; `ColumnsMesh` uses only `Point3d`/`Vector3d` arithmetic (write your own cross product; do not call `Vector3d.CrossProduct` or `Unitize`).
- Before every build and every commit, run the OneDrive clash check in the shared gate below (ignore matches under `obj\`).
- Export's GUID `f2a6c8e4-1b5d-49a3-b7e0-3c9f5d8a2617` never changes. Slot 0 (Result) never moves.
- No contract type changes. Component count stays 19; persistent parameter count stays 12.
- The uploader never touches Grasshopper objects off the UI thread.
- `plugin/native_v02/Components/DeliveryComponents.cs` is now ours (the foreign edit was committed as 0767636 on this branch); the other session is told in the report.

---

## File structure

| Path (relative to `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`) | Responsibility |
| --- | --- |
| `plugin/native_v02/Components/ExportPayloads.cs` (create) | `ExportPlan`, `ColumnsMesh`. |
| `plugin/native_v02/Components/LiveUploader.cs` (create) | `LiveUploader`: debounce, send, retry, outcome. |
| `plugin/native_v02/Components/DeliveryComponents.cs` (modify) | Export's ports, plan loop, writes, Live wiring, outputs. |
| `tests/native_smoke/Program.cs` (modify) | Three new checks; Export pinned; Cells and Courses flattened. |
| `docs/component-taxonomy.md` (modify) | The Export row. |

## The shared gate

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests" -Recurse -Filter "*Name clash*" | Where-Object { $_.FullName -notmatch '\\obj\\' }
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve before building" }
dotnet build "$repo\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -v quiet --nologo
dotnet run --project "$repo\tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "$repo\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"
```

A passing gate ends with `Native component smoke test passed; Rhino was not launched.`, exit code 0, 0 build warnings. Commit messages follow `type(scope): sentence`. Every commit uses explicit file paths.

---

### Task 1: The pure parts, measured

**Files:**
- Create: `plugin/native_v02/Components/ExportPayloads.cs`, `plugin/native_v02/Components/LiveUploader.cs`
- Test: `tests/native_smoke/Program.cs` (three try blocks after the `ValidateParameterMismatch` block; methods next to `ValidateExportTessellationJsonOptions`)

**Interfaces (Task 2 depends on these exact names):**
- `internal static class ExportPlan { public static string[] Kinds(bool hasCells, bool hasColumns); }`
- `internal static class ColumnsMesh { public static (double[][] Vertices, int[][] Faces) Build(IReadOnlyList<(Point3d From, Point3d To, double Force)> members, double radius, int sides = 6); public static string Json(IReadOnlyList<(Point3d From, Point3d To, double Force)> members, double radius, string forceUnit, double unitFactor); }`
- `internal sealed class LiveUploader : IDisposable` with `const int DebounceMilliseconds = 500`; `public sealed record Pending(string Studio, string Name, IReadOnlyList<(string Kind, string Json)> Payloads)`; `public LiveUploader(Action onOutcome)`; `public void Enqueue(Pending set)`; `public string LastOutcome { get; }`; `public static int? RetryDelay(int attempt)`; `public static string RouteFor(string kind, string name, string studio)`; `public static string Outcome(int status, int attempt)`; `public static string SetKey(IReadOnlyList<(string Kind, string Json)> payloads)`.

- [ ] **Step 1: Write the failing checks**

After the `ValidateParameterMismatch` try block add three try blocks calling `ValidateExportPlan(plugin)`, `ValidateColumnsMesh(plugin)`, `ValidateLiveUploader(plugin)` with PASS lines: "PASS  ExportPlan: contract and compas always, tessellation with cells, columns with a block, in that order."; "PASS  ColumnsMesh: one member is a closed prism of six quads and eight cap triangles at the radius asked, a zero-length member is nothing, two members index cleanly."; "PASS  LiveUploader: the retry schedule is 2, 4, 8 seconds then deferred, the routes are the studio's, a 2xx is stored, a 409 retries until the schedule runs out, anything else is refused, and an identical set keys the same."; each catch adds `failures.Add($"<name>: {DescribeException(exception)}")`.

Methods:

```csharp
    private static void ValidateExportPlan(Assembly plugin)
    {
        Type plan = plugin.GetType("Ananke.COMPAS.Native.Components.ExportPlan", throwOnError: true)!;
        MethodInfo kinds = RequirePublicStatic(plan, "Kinds");
        string Show(bool cells, bool columns) =>
            string.Join(",", (string[])kinds.Invoke(null, new object?[] { cells, columns })!);
        if (Show(false, false) != "contract,compas") throw new InvalidOperationException($"No cells, no columns: contract,compas; got {Show(false, false)}.");
        if (Show(true, false) != "contract,compas,tessellation") throw new InvalidOperationException($"Cells add tessellation; got {Show(true, false)}.");
        if (Show(false, true) != "contract,compas,columns") throw new InvalidOperationException($"Columns add columns; got {Show(false, true)}.");
        if (Show(true, true) != "contract,compas,tessellation,columns") throw new InvalidOperationException($"All four in order; got {Show(true, true)}.");
    }

    private static void ValidateColumnsMesh(Assembly plugin)
    {
        Type mesh = plugin.GetType("Ananke.COMPAS.Native.Components.ColumnsMesh", throwOnError: true)!;
        MethodInfo build = RequirePublicStatic(mesh, "Build");
        Type memberList = build.GetParameters()[0].ParameterType;   // IReadOnlyList<(Point3d, Point3d, double)>
        Type tuple = memberList.GetGenericArguments()[0];
        Type point3d = tuple.GetGenericArguments()[0];
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        object Member(double x0, double y0, double z0, double x1, double y1, double z1, double f) =>
            Activator.CreateInstance(tuple, P(x0, y0, z0), P(x1, y1, z1), f)!;
        object ListOf(params object[] members)
        {
            var list = (System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(tuple))!;
            foreach (object m in members) list.Add(m);
            return list;
        }
        (double[][] V, int[][] F) Run(object members, double radius)
        {
            object result = build.Invoke(null, new object?[] { members, radius, 6 })!;
            Type t = result.GetType();
            return ((double[][])t.GetField("Item1")!.GetValue(result)!, (int[][])t.GetField("Item2")!.GetValue(result)!);
        }

        (double[][] v, int[][] f) = Run(ListOf(Member(0, 0, 0, 0, 0, 2, 5.0)), 0.1);
        if (v.Length != 12) throw new InvalidOperationException($"A six-sided prism has 12 vertices; got {v.Length}.");
        if (f.Count(x => x.Length == 4) != 6 || f.Count(x => x.Length == 3) != 8)
            throw new InvalidOperationException($"Six side quads and eight cap triangles; got {f.Count(x => x.Length == 4)} quads and {f.Count(x => x.Length == 3)} triangles.");
        foreach (double[] p in v)
        {
            double r = Math.Sqrt((p[0] * p[0]) + (p[1] * p[1]));
            if (Math.Abs(r - 0.1) > 1.0e-9) throw new InvalidOperationException($"Every vertex sits at the radius; one is at {r:0.######}.");
            if (Math.Abs(p[2]) > 1.0e-9 && Math.Abs(p[2] - 2.0) > 1.0e-9) throw new InvalidOperationException($"Cap vertices sit at the member's ends; one is at z {p[2]:0.######}.");
        }
        foreach (int[] face in f)
            foreach (int i in face)
                if (i < 0 || i >= v.Length) throw new InvalidOperationException("A face indexes outside the vertices.");
        (double[][] none, int[][] noneF) = Run(ListOf(Member(1, 1, 1, 1, 1, 1, 1.0)), 0.1);
        if (none.Length != 0 || noneF.Length != 0) throw new InvalidOperationException("A zero-length member draws nothing.");
        (double[][] two, int[][] twoF) = Run(ListOf(Member(0, 0, 0, 0, 0, 2, 1.0), Member(1, 0, 0, 3, 0, 0, 1.0)), 0.1);
        if (two.Length != 24) throw new InvalidOperationException($"Two members give 24 vertices; got {two.Length}.");
        if (twoF.SelectMany(x => x).Any(i => i < 0 || i >= 24)) throw new InvalidOperationException("Two members' faces index within 24 vertices.");
    }

    private static void ValidateLiveUploader(Assembly plugin)
    {
        Type uploader = plugin.GetType("Ananke.COMPAS.Native.Components.LiveUploader", throwOnError: true)!;
        MethodInfo delay = RequirePublicStatic(uploader, "RetryDelay");
        MethodInfo route = RequirePublicStatic(uploader, "RouteFor");
        MethodInfo outcome = RequirePublicStatic(uploader, "Outcome");
        MethodInfo key = RequirePublicStatic(uploader, "SetKey");
        int? Delay(int attempt) => (int?)delay.Invoke(null, new object?[] { attempt });
        if (Delay(0) != 2000 || Delay(1) != 4000 || Delay(2) != 8000 || Delay(3) is not null)
            throw new InvalidOperationException("The retry schedule is 2000, 4000, 8000 then null.");
        string Route(string kind, string name, string studio) => (string)route.Invoke(null, new object?[] { kind, name, studio })!;
        if (Route("contract", "arch", "http://127.0.0.1:8600") != "http://127.0.0.1:8600/api/uploads/exports/arch/contract")
            throw new InvalidOperationException($"Contract route wrong: {Route("contract", "arch", "http://127.0.0.1:8600")}.");
        if (Route("tessellation", "arch", "http://127.0.0.1:8600/") != "http://127.0.0.1:8600/api/uploads/exports/arch/tessellation")
            throw new InvalidOperationException("A trailing slash on Studio is tolerated.");
        if (Route("columns", "arch", "http://127.0.0.1:8600") != "http://127.0.0.1:8600/api/uploads/columns/arch-columns.json")
            throw new InvalidOperationException($"Columns route wrong: {Route("columns", "arch", "http://127.0.0.1:8600")}.");
        string Verdict(int status, int attempt) => (string)outcome.Invoke(null, new object?[] { status, attempt })!;
        if (Verdict(200, 0) != "stored" || Verdict(204, 5) != "stored") throw new InvalidOperationException("2xx is stored.");
        if (Verdict(409, 0) != "retry" || Verdict(409, 2) != "retry") throw new InvalidOperationException("409 retries while the schedule has entries.");
        if (Verdict(409, 3) != "deferred") throw new InvalidOperationException("409 after the schedule is deferred.");
        if (Verdict(400, 0) != "refused" || Verdict(500, 0) != "refused") throw new InvalidOperationException("Anything else is refused.");
        var a = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"b\":2}") };
        var b = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"b\":2}") };
        var c = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"b\":3}") };
        string ka = (string)key.Invoke(null, new object?[] { a })!;
        string kb = (string)key.Invoke(null, new object?[] { b })!;
        string kc = (string)key.Invoke(null, new object?[] { c })!;
        if (ka != kb) throw new InvalidOperationException("Equal sets key the same.");
        if (ka == kc) throw new InvalidOperationException("A set differing in one byte keys differently.");
    }
```

- [ ] **Step 2: Run the gate to see the three fail by name**

- [ ] **Step 3: `ExportPayloads.cs`**

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Text.Json;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// What a Result can be exported as. Every Result is a contract and a
/// COMPAS document; with cells wired it is also a tessellation sidecar,
/// and with columns in its Mould block a columns mesh. Export writes what
/// the Result can be rather than asking which one.
/// </summary>
internal static class ExportPlan
{
    public static string[] Kinds(bool hasCells, bool hasColumns)
    {
        var kinds = new List<string> { "contract", "compas" };
        if (hasCells)
            kinds.Add("tessellation");
        if (hasColumns)
            kinds.Add("columns");
        return kinds.ToArray();
    }
}

/// <summary>
/// The columns as a mesh the studio renders today: one closed prism per
/// member, six side quads and two triangle-fanned caps, at the radius
/// asked. The members themselves travel beside the mesh so a later
/// studio can draw them in its own material from lines and a radius.
/// Pure arithmetic: the harness builds it without Rhino.
/// </summary>
internal static class ColumnsMesh
{
    public static (double[][] Vertices, int[][] Faces) Build(
        IReadOnlyList<(Point3d From, Point3d To, double Force)> members,
        double radius,
        int sides = 6)
    {
        sides = Math.Max(sides, 3);
        radius = Math.Max(radius, 1.0e-9);
        var vertices = new List<double[]>();
        var faces = new List<int[]>();
        foreach ((Point3d from, Point3d to, double _) in members)
        {
            Vector3d axis = to - from;
            double length = axis.Length;
            if (length <= 1.0e-9)
                continue;
            axis = axis / length;
            Vector3d helper = Math.Abs(axis.Z) < 0.9 ? Vector3d.ZAxis : Vector3d.XAxis;
            Vector3d u = Cross(axis, helper);
            u = u / u.Length;
            Vector3d v = Cross(axis, u);
            int baseIndex = vertices.Count;
            for (int end = 0; end < 2; end++)
            {
                Point3d centre = end == 0 ? from : to;
                for (int s = 0; s < sides; s++)
                {
                    double a = 2.0 * Math.PI * s / sides;
                    Point3d p = centre + (u * (radius * Math.Cos(a))) + (v * (radius * Math.Sin(a)));
                    vertices.Add(new[] { p.X, p.Y, p.Z });
                }
            }
            for (int s = 0; s < sides; s++)
            {
                int n = (s + 1) % sides;
                faces.Add(new[] { baseIndex + s, baseIndex + n, baseIndex + sides + n, baseIndex + sides + s });
            }
            for (int s = 1; s + 1 < sides; s++)
            {
                faces.Add(new[] { baseIndex, baseIndex + s + 1, baseIndex + s });
                faces.Add(new[] { baseIndex + sides, baseIndex + sides + s, baseIndex + sides + s + 1 });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    public static string Json(
        IReadOnlyList<(Point3d From, Point3d To, double Force)> members,
        double radius,
        string forceUnit,
        double unitFactor)
    {
        (double[][] vertices, int[][] faces) = Build(members, radius);
        var memberPayloads = new List<Dictionary<string, object?>>(members.Count);
        foreach ((Point3d from, Point3d to, double force) in members)
        {
            memberPayloads.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["from"] = new[] { from.X, from.Y, from.Z },
                ["to"] = new[] { to.X, to.Y, to.Z },
                ["force"] = force,
            });
        }
        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = "bench.columns/1",
            ["lengthUnitToMetres"] = unitFactor,
            ["forceUnit"] = forceUnit,
            ["radius"] = radius,
            ["vertices"] = vertices,
            ["faces"] = faces,
            ["members"] = memberPayloads,
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    private static Vector3d Cross(Vector3d a, Vector3d b) => new(
        (a.Y * b.Z) - (a.Z * b.Y),
        (a.Z * b.X) - (a.X * b.Z),
        (a.X * b.Y) - (a.Y * b.X));
}
```

- [ ] **Step 4: `LiveUploader.cs`**

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Pushes an export set to the studio, off the UI thread.
///
/// Debounced: a solve enqueues a set and the send waits half a second
/// after the LAST enqueue, so a slider scrub sends only the final state.
/// A 409 means the studio has a run in flight for that study; the send
/// waits and retries on a short schedule, then gives up for this set and
/// says so. A set identical to the last one sent is skipped, which is
/// what lets the component expire itself to show an outcome without
/// sending again. Nothing here touches a Grasshopper object; the
/// outcome lands in a field and the owner is told through a callback it
/// marshals to the UI thread itself.
/// </summary>
internal sealed class LiveUploader : IDisposable
{
    public const int DebounceMilliseconds = 500;

    private static readonly HttpClient Client = new()
    {
        Timeout = TimeSpan.FromSeconds(30),
    };

    public sealed record Pending(
        string Studio,
        string Name,
        IReadOnlyList<(string Kind, string Json)> Payloads);

    private readonly object _gate = new();
    private readonly Action _onOutcome;
    private Timer? _timer;
    private Pending? _pending;
    private string? _lastSentKey;
    private string _lastOutcome = "idle";
    private bool _disposed;

    public LiveUploader(Action onOutcome)
    {
        _onOutcome = onOutcome;
    }

    public string LastOutcome
    {
        get
        {
            lock (_gate)
                return _lastOutcome;
        }
    }

    public static int? RetryDelay(int attempt) => attempt switch
    {
        0 => 2000,
        1 => 4000,
        2 => 8000,
        _ => null,
    };

    public static string RouteFor(string kind, string name, string studio)
    {
        string root = studio.Trim().TrimEnd('/');
        return kind == "columns"
            ? $"{root}/api/uploads/columns/{name}-columns.json"
            : $"{root}/api/uploads/exports/{name}/{kind}";
    }

    public static string Outcome(int status, int attempt)
    {
        if (status >= 200 && status < 300)
            return "stored";
        if (status == 409)
            return RetryDelay(attempt) is null ? "deferred" : "retry";
        return "refused";
    }

    public static string SetKey(IReadOnlyList<(string Kind, string Json)> payloads)
    {
        using var sha = SHA256.Create();
        var builder = new StringBuilder();
        foreach ((string kind, string json) in payloads)
        {
            builder.Append(kind).Append('\u001f').Append(json).Append('\u001e');
        }
        byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(builder.ToString()));
        return Convert.ToHexString(hash);
    }

    public void Enqueue(Pending set)
    {
        lock (_gate)
        {
            if (_disposed)
                return;
            _pending = set;
            _timer?.Dispose();
            _timer = new Timer(_ => Fire(), null, DebounceMilliseconds, Timeout.Infinite);
        }
    }

    private void Fire()
    {
        Pending? set;
        lock (_gate)
        {
            set = _pending;
            _pending = null;
        }
        if (set is null)
            return;
        string key = SetKey(set.Payloads);
        lock (_gate)
        {
            if (key == _lastSentKey)
                return;
        }
        _ = Task.Run(() => SendAsync(set, key));
    }

    private async Task SendAsync(Pending set, string key)
    {
        var lines = new List<string>();
        foreach ((string kind, string json) in set.Payloads)
        {
            string route = RouteFor(kind, set.Name, set.Studio);
            string line = kind + ": ";
            for (int attempt = 0; ; attempt++)
            {
                try
                {
                    using var content = new StringContent(json, Encoding.UTF8, "application/json");
                    using HttpResponseMessage response =
                        await Client.PutAsync(route, content).ConfigureAwait(false);
                    int status = (int)response.StatusCode;
                    string verdict = Outcome(status, attempt);
                    if (verdict == "retry")
                    {
                        await Task.Delay(RetryDelay(attempt)!.Value).ConfigureAwait(false);
                        continue;
                    }
                    string body = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                    line += verdict switch
                    {
                        "stored" => "stored",
                        "deferred" => $"deferred, 409 after {attempt} retries {Short(body)}",
                        _ => $"refused {status} {Short(body)}",
                    };
                }
                catch (Exception error)
                {
                    line += "failed: " + error.GetBaseException().Message;
                }
                break;
            }
            lines.Add(line);
        }
        lock (_gate)
        {
            _lastSentKey = key;
            _lastOutcome = string.Join(Environment.NewLine, lines);
        }
        _onOutcome();
    }

    private static string Short(string body)
    {
        string trimmed = body.Trim();
        return trimmed.Length <= 120 ? trimmed : trimmed[..120] + "...";
    }

    public void Dispose()
    {
        lock (_gate)
        {
            _disposed = true;
            _timer?.Dispose();
            _timer = null;
            _pending = null;
        }
    }
}
```

- [ ] **Step 5: Run the gate to see the three pass, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ExportPayloads.cs" "plugin/native_v02/Components/LiveUploader.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(export): the plan, the columns prism and the uploader's rules, measured"
```

---

### Task 2: Export rewired

**Files:**
- Modify: `plugin/native_v02/Components/DeliveryComponents.cs` (Export's `ValueLists`, constructor description, `RegisterInputParams`, `RegisterOutputParams`, `SolveInstance`, `TryReadInputs`, `ComputeAsync`, `ResolveWritePath`; keep `PrepareTessellationCells`, `HasNegativeCourse`, `BuildCompasJsonAsync`, `BuildCompasJson`, `BuildTessellationJson`, `ScaleOutline`, `ResolveUnitFactor`, `CloneResult`, `OptionalString`, `RequiredString`, `TessellationCell`, `ExportComponentTaskResult` as they are or minimally extended)
- Test: `tests/native_smoke/Program.cs` (`VisualiseContracts` gains Export; `FlattenedInputs` gains `["Ananke.COMPAS.Native.Components.ExportComponent"] = new[] { 4, 5 }`)

**Interfaces:**
- Consumes: Task 1's `ExportPlan.Kinds`, `ColumnsMesh.Json`, `LiveUploader` (its `Pending`, `Enqueue`, `LastOutcome`, `Dispose`).

- [ ] **Step 1: Pin the ports and the flatten**

Add to `VisualiseContracts`:

```csharp
                ["Ananke.COMPAS.Native.Components.ExportComponent"] = (
                    new[] { "Result", "Path", "Write", "Name", "Cells", "Courses", "Live", "Studio", "Column Radius" },
                    new[] { "Contract JSON", "COMPAS JSON", "Tessellation JSON", "Columns JSON", "Written", "Uploaded" }),
```

and to `FlattenedInputs`: `["Ananke.COMPAS.Native.Components.ExportComponent"] = new[] { 4, 5 },`. Run the gate: Export fails both.

- [ ] **Step 2: Ports**

Delete the `ValueLists` array and the `SuggestedValueLists` override (no Format list any more). `RegisterInputParams` in the spec's order: Result (as now); Path (as now, text, optional; description "A folder, or a file whose folder is used, for the Write trigger; missing folders are created."); Write (as now); Name (description: "The study name. Files are <Name>-<kind>.json under Path and the studio's export name is <Name>; blank uses ananke-export."); Cells (as now, plus `parameters[4].DataMapping = GH_DataMapping.Flatten;` and "Wire Skin's Face Polylines straight in; the tree is flattened here."); Courses (as now, `parameters[5].DataMapping = GH_DataMapping.Flatten;`); Live (boolean, default false, "Push the set to the studio on every solve, debounced half a second, retrying a 409 while the studio has a run in flight. Failures are warnings; the files and outputs stand."); Studio (text, default `http://127.0.0.1:8600`, "The studio's base URL."); Column Radius (number, default 0.05, "Radius of the prism each column member is drawn as in the columns mesh, in document units."). Mark 1, 3, 4, 5, 7, 8 optional. `RegisterOutputParams`: Contract JSON `CJ`, COMPAS JSON `MJ`, Tessellation JSON `TJ`, Columns JSON `KJ`, Written `W`, Uploaded `U`, all text items. Update the constructor description to "Write everything a solved Result can be, contract and COMPAS always, a tessellation sidecar when cells are wired, a columns mesh when the Result carries columns, and push the set live to the studio."

- [ ] **Step 3: The solve**

Extend `ExportComponentTaskResult` to carry the set: replace `string? Json` with `IReadOnlyList<(string Kind, string Json)>? Payloads` (keep `Warning`, `Error`, `Elapsed`). `TryReadInputs` reads the nine inputs into a small record `ExportInputs(ResultDto Result, string Path, bool Write, string Name, IReadOnlyList<TessellationCell>? Cells, string? CellWarning, bool Live, string Studio, double Radius)`; validation as today for Write and cells (cells are validated whenever wired, tessellation is produced when they are); a non-finite or non-positive Radius falls back to 0.05 with a Warning; a blank Studio falls back to the default with a Warning when Live is true.

`ComputeAsync(ResultDto result, IReadOnlyList<TessellationCell>? cells, string? cellWarning, double unitFactor, double radius, CancellationToken)`: build `kinds = ExportPlan.Kinds(cells is not null && cells.Count > 0, result.Mould?.Columns is { } block && block.Members.Count > 0)` and, for each kind, the JSON: contract via `ContractJson.Serialize`, compas via `BuildCompasJsonAsync` (its warning joins), tessellation via `BuildTessellationJson` (with the unit note as today), columns via `ColumnsMesh.Json(members, radius, forceUnit, unitFactor)` where members are `(nodes[U], nodes[V], MemberForce[m])` from the block and `forceUnit` is the trimmed `equilibrium.ForceUnit` (default kN). Return the payload list.

Post phase: as today, then for the writes: with Write and a Path, resolve the folder as `ResolveWritePath` does today for the folder part (a file path's directory), write `<folder>/<name>-<kind>.json` for every payload, collect the paths into `Written` (one per line) and latch them. Set outputs 0 to 3 by kind (empty string when absent), 4 Written, 5 Uploaded (`_uploader.LastOutcome`, or "Live is off" when Live is false). Live: when Live is true, `_uploader.Enqueue(new LiveUploader.Pending(studio, name, payloads))`. The uploader is a field created in the constructor with `onOutcome: () => RhinoApp.InvokeOnUiThread(new Action(() => ExpireSolution(true)))`; override `RemovedFromDocument(GH_Document document)` to `_uploader.Dispose()` then call base. `Message`: the payload count and the last outcome's first line.

- [ ] **Step 4: Gate, commit**

Expected: 0 warnings, 19 components, `PASS  Export`, the two existing Export checks still passing (`HasNegativeCourse` and `BuildTessellationJson` keep their names and signatures). Commit:

```powershell
git -C $repo add "plugin/native_v02/Components/DeliveryComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(export): one component writes everything a Result can be and pushes it live"
```

---

### Task 3: The taxonomy row

**Files:**
- Modify: `docs/component-taxonomy.md` (the Export row, line 58)

- [ ] **Step 1: Replace the row**

```markdown
| `07 Delivery` | **Export** | Result `RES`, Path `P` (optional), Write `W`, Name `N` (optional), Cells `C` (optional, flattened), Courses `CO` (optional, flattened), Live `L`, Studio `S`, Column Radius `R` | Contract JSON `CJ`, COMPAS JSON `MJ`, Tessellation JSON `TJ`, Columns JSON `KJ`, Written `W`, Uploaded `U` | Write everything a solved Result can be, in one component: the portable Contract JSON and the native COMPAS document always, the `bench.tessellation/1` sidecar when **Skin**'s cells are wired, and a `bench.columns/1` mesh (a prism per member at `Column Radius`, with the members beside it) when the Result's Mould block carries columns. `Write` puts the set under `Path` as `<Name>-<kind>.json`; `Written` lists what was written. `Live` pushes the same set to the studio at `Studio` on every solve, debounced half a second so a scrub sends only the final state, retrying a 409 (a run in flight for that study) after 2, 4 and 8 seconds and then deferring; an identical set is not sent twice; `Uploaded` says what happened per kind, and a failure is a warning, never an error. The studio-side tasks this feeds are in `docs/studio-tasks-2026-08-28.md`. |
```

- [ ] **Step 2: Commit**

```powershell
git -C $repo add "docs/component-taxonomy.md"
git -C $repo commit -m "docs(taxonomy): Export writes the whole set and pushes it live"
```

---

## Self-review

Spec coverage: 2 (Task 2 ports, flatten pinned), 3 (Task 1 plan and prism, Task 2 loop and columns payload), 4 (Task 1 uploader, Task 2 wiring and expire), 5 (files across tasks; the studio task doc is already written and committed with the spec), 6 (the doc), 8 (Task 1 checks, Task 2 pins), 9 (no code).

Type consistency: `ExportPlan.Kinds(bool, bool)`, `ColumnsMesh.Build(IReadOnlyList<(Point3d, Point3d, double)>, double, int)` and `Json(...)`, `LiveUploader.Pending(string, string, IReadOnlyList<(string, string)>)`, `RetryDelay(int) -> int?`, `RouteFor(string, string, string)`, `Outcome(int, int)`, `SetKey(IReadOnlyList<(string, string)>)` match between Task 1, its checks and Task 2.

Known risk: `RhinoApp.InvokeOnUiThread` and `ExpireSolution` are UI-thread calls that the harness cannot exercise; the content-hash skip is what makes the expire safe, and it is measured.
