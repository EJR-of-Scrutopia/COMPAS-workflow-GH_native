# Principal Lines Input Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Principal lines enter the contract only through Pattern's Principal Lines input, Pattern says loudly when the curves it was given cannot be placed, and Pattern is the only component that previews the red bars.

**Architecture:** `PrincipalRunFinder` loses its anchor derivation and gains one pure `Outcome(supplied, unmatched, kept)` function that maps match counts to a severity and message. Pattern flattens `P`, throws (so emits nothing) on the error outcome, and shows the run count on its message line. Supports loses the Ribs port and the derive block. Eight components lose their red-bar preview fields; `TnaWorkflowPreview.ResultPrincipalLines` goes with them. The smoke harness pins all of it by reflection.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8 (managed only in tests), the Rhino-free reflection smoke harness in `tests/native_smoke`.

**Spec:** `docs/superpowers/specs/2026-08-28-principal-lines-input-only-design.md`

## Global Constraints

- No em dashes anywhere, in code, comments, docs or commit messages.
- Full absolute Windows paths in any reply to Param.
- No Co-Authored-By or AI attribution in any commit.
- Commit locally after every task; never push. Push only on Param's word.
- Rebuild and install as the final step with Rhino CLOSED, then tell Param to restart Rhino.
- Every measured check runs in the smoke harness without launching Rhino. Anything that P/Invokes `rhcommon_c` (`Curve.DivideByCount`, `Vector3d.Unitize`, mesh queries) cannot run there; `Point3d`, `Line`, `Vector3d.Length`, `DistanceTo` and operators are managed and fine.
- Before every build and every commit, run the OneDrive clash check in the shared gate below. A file named `... (# Name clash ... #).cs` in the source tree holds a NEWER edit than the real file and will also be compiled as a duplicate type; diff it, re-apply, move it out of the tree.
- Component GUIDs never change. Port order never changes; Supports' Ribs is the LAST input so removing it moves nothing.
- `ContractSchema.Current` and `ResultDto.ResultSchema` are untouched. No contract type changes in this plan.
- Another session holds an uncommitted edit to `plugin/native_v02/Components/DeliveryComponents.cs`. NEVER stage that file. `git add` by explicit path only; never `git add .` or `git add plugin`.
- Spec section 5 (columns, Animate, Monitor, Skin, Export, the worker) is OUT OF SCOPE.

---

## File structure

| Path (relative to `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`) | Responsibility |
| --- | --- |
| `plugin/native_v02/Components/PrincipalRunFinder.cs` (modify) | Matching drawn curves to vertex runs (`FromCurves`), the safety net (`Deduplicate`), and the new `Outcome` function. The anchor derivation is deleted. |
| `plugin/native_v02/Components/SpineComponents.cs` (modify) | Pattern: flatten `P`, outcome wiring, message line. Supports: Ribs port and derive block gone, preview without bars. Loads: preview without bars. |
| `plugin/native_v02/Components/SolverComponents.cs` (modify) | TNA Relax, TNA Solve, FD Solve previews without bars. |
| `plugin/native_v02/Components/VisualiseComponents.cs` (modify) | Display preview without bars. |
| `plugin/native_v02/Components/MouldComponents.cs` (modify) | Animate preview without bars; its no-runs message. |
| `plugin/native_v02/Components/ColumnFinderComponents.cs` (modify) | Columns preview without bars; its no-runs message; the `columns.principal_source` diagnostic. |
| `plugin/native_v02/Components/TnaWorkflowComponents.cs` (modify) | `TnaWorkflowPreview`: delete `ResultPrincipalLines`, rewrite the principal doc comment. |
| `tests/native_smoke/Program.cs` (modify) | Two table changes and three new checks. |
| `docs/component-taxonomy.md` (modify) | Pattern and Supports rows. |

## The shared gate

Every "run the gate" step below means this, from PowerShell. It refuses a OneDrive clash file first, builds the plugin, builds the harness, and runs the harness against the freshly built `.gha`.

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests" -Recurse -Filter "*Name clash*"
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve before building" }
dotnet build "$repo\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -v quiet --nologo
dotnet run --project "$repo\tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "$repo\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"
```

A passing gate ends with `Native component smoke test passed; Rhino was not launched.` and exit code 0. A failing gate lists `ERROR: N native component validation failures:` and exits 5. The harness catches every exception inside a check and reports it by name, so a check whose target does not exist yet fails with a named message rather than crashing. The build must produce 0 warnings; an unused `using` left behind by a deletion is a warning, remove it.

Commit messages follow the repo's `type(scope): sentence` style already in `git log`. Every commit uses explicit file paths.

---

### Task 1: PrincipalRunFinder loses the derivation and gains Outcome

**Files:**
- Modify: `plugin/native_v02/Components/PrincipalRunFinder.cs` (whole file; today 385 lines)
- Test: `tests/native_smoke/Program.cs` (add two checks after the `ValidateRunDeduplication` try block, which starts at line 534)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `public static List<List<int>> PrincipalRunFinder.FromCurves(IReadOnlyList<Curve> curves, IReadOnlyList<Point3d> vertices, IReadOnlyList<EdgeDto> edges, out double worstOffset, out double gauge, out int unmatched)` (one new `out int unmatched` parameter, the count of non-null curves that caught fewer than two nodes).
  - `internal sealed record PrincipalOutcome(string Severity, string Message)` in namespace `Ananke.COMPAS.Native.Components`, same file.
  - `public static PrincipalOutcome PrincipalRunFinder.Outcome(int supplied, int unmatched, int kept)`. Severity is one of `"none"`, `"remark"`, `"warning"`, `"error"`.
  - `DeriveFromAnchors` no longer exists. `Deduplicate` stays private static, unchanged.
- Task 2 wires `Outcome` into Pattern.

- [ ] **Step 1: Write the failing checks**

In `tests/native_smoke/Program.cs`, immediately after the `try { ValidateRunDeduplication(plugin); ... }` block (it ends at line 550 with `}`), add:

```csharp
        try
        {
            ValidateDerivationRemoved(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder: the anchor derivation is GONE. A "
                + "principal line is a decision Param draws into Pattern; "
                + "nothing in the plugin derives one from the anchors any more.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder derivation removed: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidatePrincipalOutcome(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder.Outcome: no curves is silence, a "
                + "dropped curve is a warning naming the count, two curves on "
                + "one run is a remark that says merged, and curves with NO "
                + "run at all is an error that says no Pattern is emitted.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder.Outcome: {DescribeException(exception)}");
        }
```

Then add the two check methods next to `ValidateRunDeduplication` (after its closing brace, before `ValidateSharedFoot`):

```csharp
    /// <summary>
    /// The anchor derivation is deleted, and stays deleted. A principal line
    /// is a decision the author draws into Pattern. When Supports derived
    /// lines whenever Pattern carried none, a definition that forgot its
    /// curves quietly got bars it never asked for, which is a second author
    /// of one fact. This pins the deletion so it cannot creep back under
    /// another refactor.
    /// </summary>
    private static void ValidateDerivationRemoved(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static | BindingFlags.Instance;
        if (finder.GetMethods(Any).Any(m => m.Name == "DeriveFromAnchors"))
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.DeriveFromAnchors still exists. Principal "
                + "lines are input only; nothing derives them from anchors.");
        }
        if (finder.GetMethod("FromCurves", Any) is null)
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.FromCurves is missing; it is the one way in.");
        }
        if (finder.GetMethod("Deduplicate", Any) is null)
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.Deduplicate is missing; it is the safety net "
                + "for two curves snapping to one run.");
        }
    }

    /// <summary>
    /// <c>PrincipalRunFinder.Outcome</c>: what Pattern says about the curves
    /// it was handed, as one pure function of three counts, so the error path
    /// is measured rather than trusted. The error case matters most: curves
    /// wired and none placed used to fall through silently to no runs, and the
    /// first sign was Columns with nothing to stand under.
    /// </summary>
    private static void ValidatePrincipalOutcome(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        MethodInfo outcome = finder.GetMethod(
            "Outcome", BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "PrincipalRunFinder.Outcome(int, int, int) is missing.");

        (string Severity, string Message) Run(int supplied, int unmatched, int kept)
        {
            object result = outcome.Invoke(
                null, new object?[] { supplied, unmatched, kept })!;
            Type type = result.GetType();
            string severity = (string)type.GetProperty("Severity")!
                .GetValue(result)!;
            string message = (string)type.GetProperty("Message")!
                .GetValue(result)!;
            return (severity, message);
        }

        void Expect(
            (int, int, int) counts, string severity, string contains)
        {
            (int supplied, int unmatched, int kept) = counts;
            (string got, string message) = Run(supplied, unmatched, kept);
            if (got != severity)
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) should be "
                    + $"'{severity}'; it was '{got}' with message '{message}'.");
            }
            if (contains.Length > 0 &&
                !message.Contains(contains, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) message should "
                    + $"contain '{contains}'; it was '{message}'.");
            }
            if (contains.Length == 0 && message.Length != 0)
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) should carry no "
                    + $"message; it was '{message}'.");
            }
        }

        Expect((0, 0, 0), "none", "");
        Expect((2, 0, 2), "none", "");
        Expect((3, 1, 2), "warning", "1 of 3");
        Expect((3, 0, 2), "remark", "merged");
        Expect((2, 2, 0), "error", "No Pattern");
        Expect((2, 0, 0), "error", "No Pattern");
    }
```

- [ ] **Step 2: Run the gate to see the new checks fail**

Run the gate. Expected: build passes (nothing in the plugin changed yet), harness reports two failures: `PrincipalRunFinder derivation removed: ... DeriveFromAnchors still exists` and `PrincipalRunFinder.Outcome: ... Outcome(int, int, int) is missing`.

- [ ] **Step 3: Rewrite PrincipalRunFinder.cs**

Replace the whole file with this. It keeps `Deduplicate` and `FromCurves` byte-for-byte in logic, deletes `DeriveFromAnchors`, `Adjacency`, `Strips`, `Order`, `StartsAlong`, `WalkAcross` and `Plan`, adds the `unmatched` out parameter, and adds `Outcome`.

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// What Pattern has to say about the principal lines it was handed, as a
    /// severity and a message. Produced by
    /// <see cref="PrincipalRunFinder.Outcome"/> from three counts so the
    /// words can be checked without a canvas.
    /// </summary>
    internal sealed record PrincipalOutcome(string Severity, string Message);

    /// <summary>
    /// Resolving the principal lines, the notched bars a reconfigurable mould
    /// holds rigid, into runs of vertex indices on the pattern.
    ///
    /// ONE way in. An author draws the bars as curves over the pattern and
    /// each is matched to the run of pattern vertices lying along it.
    /// Matching is done in plan, so a bar drawn flat still finds its nodes.
    /// A principal line is a decision, and nothing here makes it for the
    /// author: the derivation from the anchors that used to stand in when no
    /// curves were drawn is gone, because a definition that forgot its curves
    /// quietly got bars it never asked for.
    ///
    /// Resolved here, on the pattern, because this is the one place where the
    /// curves and the geometry still agree. Downstream the surface rises and
    /// the curves do not follow it.
    /// </summary>
    internal static class PrincipalRunFinder
    {
        /// <summary>
        /// One bar, however many times it was traced.
        ///
        /// Two curves laid near the same run of nodes both snap to it. The
        /// duplicate is invisible in the viewport, because the second bar
        /// draws exactly on top of the first, and it is ruinous downstream:
        /// each bar is given its OWN full set of columns, each mirrored about
        /// its own slightly different midpoint, so the columns land on one
        /// line at two offset spacings and read as hopelessly lopsided.
        ///
        /// Matched on WHAT THEY ARE MADE OF, not on where they stop. Endpoints
        /// were tried and could not catch it: two traces of one line rarely
        /// finish on exactly the same node. Two runs sharing more than half
        /// their nodes are one bar, and the longer trace is the one kept.
        /// </summary>
        private static List<List<int>> Deduplicate(List<List<int>> runs)
        {
            var kept = new List<List<int>>();
            var keptNodes = new List<HashSet<int>>();
            foreach (List<int> run in runs.OrderByDescending(r => r.Count))
            {
                var nodes = new HashSet<int>(run);
                bool duplicate = false;
                for (int i = 0; i < keptNodes.Count; i++)
                {
                    int shared = nodes.Count(keptNodes[i].Contains);
                    if (2 * shared > Math.Min(nodes.Count, keptNodes[i].Count))
                    {
                        duplicate = true;
                        break;
                    }
                }
                if (duplicate)
                    continue;
                keptNodes.Add(nodes);
                kept.Add(run);
            }
            return kept;
        }

        /// <summary>
        /// Runs matched from drawn curves. Matching is in plan, so a bar drawn
        /// on the flat pattern still finds its nodes on a surface that rises.
        ///
        /// <paramref name="worstOffset"/> and <paramref name="gauge"/> come
        /// back so the caller can tell the author when a line was drawn where
        /// no run of nodes goes: the offset is how far the furthest matched bar
        /// sits from the curve that asked for it, the gauge the mesh's own
        /// median edge length to measure that against.
        /// <paramref name="unmatched"/> is how many curves caught fewer than
        /// two nodes and were dropped, so the caller can tell a DROPPED curve
        /// from two curves MERGED onto one run by <see cref="Deduplicate"/>.
        /// </summary>
        public static List<List<int>> FromCurves(
            IReadOnlyList<Curve> curves,
            IReadOnlyList<Point3d> vertices,
            IReadOnlyList<EdgeDto> edges,
            out double worstOffset,
            out double gauge,
            out int unmatched)
        {
            worstOffset = 0.0;
            gauge = 0.0;
            unmatched = 0;
            var runs = new List<List<int>>();
            if (curves.Count == 0 || vertices.Count == 0)
                return runs;

            Point3d[] nodes = vertices.ToArray();
            (int, int)[] pairs = edges
                .Where(e => e.U != e.V &&
                    e.U >= 0 && e.U < nodes.Length &&
                    e.V >= 0 && e.V < nodes.Length)
                .Select(e => (e.U, e.V))
                .ToArray();
            if (pairs.Length == 0)
            {
                unmatched = curves.Count(c => c is not null);
                return runs;
            }

            gauge = MouldGeometry.MedianEdgeLength(nodes, pairs);
            foreach (Curve curve in curves)
            {
                if (curve is null)
                    continue;
                List<int> run = MouldGeometry.SnapCurveToNodes(
                    curve, nodes, pairs, out double offset);
                if (run.Count < 2)
                {
                    unmatched++;
                    continue;
                }
                runs.Add(run);
                worstOffset = Math.Max(worstOffset, offset);
            }
            return Deduplicate(runs);
        }

        /// <summary>
        /// What Pattern says about the curves it was handed, from three
        /// counts: how many curves were supplied, how many caught fewer than
        /// two nodes, and how many runs survived deduplication.
        ///
        /// No curves is silence, because the FD path never draws any. Curves
        /// with no run at all is an ERROR, and Pattern emits nothing on it: a
        /// pattern whose bars were asked for and could not be placed is not
        /// the pattern that was asked for, and a grey chain is louder than a
        /// red badge on one component. A dropped curve is a warning. Two
        /// curves that snapped to one run is a remark, because the author
        /// should know the safety net fired, and before this it was reported
        /// as a drop, which it is not.
        /// </summary>
        public static PrincipalOutcome Outcome(int supplied, int unmatched, int kept)
        {
            if (supplied <= 0)
                return new PrincipalOutcome("none", string.Empty);
            if (kept <= 0)
            {
                return new PrincipalOutcome(
                    "error",
                    $"{supplied} principal line(s) were wired into Pattern and "
                    + "none of them lie over a run of pattern nodes in plan. A "
                    + "bar can only stand on nodes: draw each line through at "
                    + "least two connected pattern nodes. No Pattern is emitted "
                    + "until one does.");
            }
            if (unmatched > 0)
            {
                return new PrincipalOutcome(
                    "warning",
                    $"{unmatched} of {supplied} principal lines caught fewer "
                    + "than two pattern vertices and were dropped. They must "
                    + "lie over the pattern in plan.");
            }
            int merged = supplied - kept;
            if (merged > 0)
            {
                return new PrincipalOutcome(
                    "remark",
                    $"{supplied} principal lines snapped to {kept} distinct "
                    + $"run(s) of nodes; {merged} duplicate(s) merged into the "
                    + "bar they share. Two curves on one run of nodes are one "
                    + "bar.");
            }
            return new PrincipalOutcome("none", string.Empty);
        }
    }
}
```

- [ ] **Step 4: Fix the one caller of FromCurves**

`plugin/native_v02/Components/SpineComponents.cs` line 203 calls `FromCurves` with two `out` arguments. Add the third so the build passes; Task 2 replaces this block properly, so for now the minimal edit is:

```csharp
            List<List<int>> principalRuns = PrincipalRunFinder.FromCurves(
                principalCurves,
                patternVertices,
                patternEdges,
                out double principalOffset,
                out double principalGauge,
                out int _);
```

- [ ] **Step 5: Delete Supports' derive block, which no longer compiles**

Supports called `DeriveFromAnchors` at line 495 of `SpineComponents.cs`, so the build is broken until that block goes. In the Supports class `SolveInstance`:
- Delete the comment beginning `// Derive the principal lines from the anchors, unless the` (lines 487 to 491) and the whole `TnaPatternDto patternForAnchors = source; if (topology.PrincipalRuns.Count == 0 && ribs > 0) { ... }` block (lines 492 to 513).
- Replace `Pattern = patternForAnchors,` with `Pattern = source,`.
- Delete the comment beginning `// The annotated topology, not the one that arrived:` (lines 523 to 525) and replace `SetPreview(patternForAnchors.Topology ?? topology, nodeIds);` with `SetPreview(topology, nodeIds);`.
- Replace the four-line `int runCount = ...; Message = runCount > 0 ? ... : ...;` with `Message = $"{nodeIds.Length} explicit anchors";`.

Leave the `ribs` read (`int ribs = 1; data.GetData(3, ref ribs);`) and the Ribs port in place; Task 3 removes the port. A local that is assigned through `ref` and never read is not a compiler warning.

- [ ] **Step 6: Run the gate to see it pass**

Run the gate. Expected: build 0 warnings (`System`, `System.Collections.Generic`, `System.Linq`, the Contracts namespace and `Rhino.Geometry` are all still used in PrincipalRunFinder.cs), harness passes including `PASS  PrincipalRunFinder: the anchor derivation is GONE` and `PASS  PrincipalRunFinder.Outcome`, and `ValidateRunDeduplication` still passes.

- [ ] **Step 7: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/PrincipalRunFinder.cs" "plugin/native_v02/Components/SpineComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "refactor(principal): one way in, the anchor derivation goes and Outcome names what Pattern says"
```

---

### Task 2: Pattern flattens P, throws on none matched, shows the run count

**Files:**
- Modify: `plugin/native_v02/Components/SpineComponents.cs` (Pattern: `RegisterInputParams` lines 95 to 106, the principal block lines 200 to 218, the message line 277 to 279)
- Test: `tests/native_smoke/Program.cs` (`FlattenedInputs` table at lines 26 to 27)

**Interfaces:**
- Consumes: `PrincipalRunFinder.FromCurves(..., out int unmatched)` and `PrincipalRunFinder.Outcome(int, int, int)` returning `PrincipalOutcome(string Severity, string Message)` from Task 1.
- Produces: nothing downstream depends on it.

- [ ] **Step 1: Pin the flatten in the harness**

In `tests/native_smoke/Program.cs` change the Pattern entry of `FlattenedInputs`:

```csharp
            ["Ananke.COMPAS.Native.Components.PatternComponent"] =
                new[] { 0, 4 },
```

- [ ] **Step 2: Run the gate to see it fail**

Expected: one failure, `Ananke.COMPAS.Native.Components.PatternComponent: constructor failed: Input 4 must flatten bundle collection trees; mapping was 'None'.`

- [ ] **Step 3: Flatten P and rewrite its description**

Replace lines 95 to 105 of `SpineComponents.cs` (the `AddCurveParameter` for Principal Lines and the `Optional` line) with:

```csharp
        parameters.AddCurveParameter(
            "Principal Lines",
            "P",
            "Optional. The notched bars a reconfigurable mould holds rigid, " +
            "drawn as curves over this pattern. They are matched HERE, in " +
            "plan, to runs of pattern vertices and carried downstream as " +
            "indices, because once the surface rises the curves no longer sit " +
            "on it and cannot find their own nodes. This is the ONLY way a " +
            "principal line enters the chain: nothing derives one for you. " +
            "Wired curves that match no run of nodes are an error and no " +
            "Pattern is emitted.",
            GH_ParamAccess.list);
        parameters[4].Optional = true;
        parameters[4].DataMapping = GH_DataMapping.Flatten;
```

- [ ] **Step 4: Wire Outcome into the solve**

Replace lines 200 to 218 (from the comment `// Only the explicit curves are resolved here.` through the closing brace of the `if (principalCurves.Count > 0 && ...)` warning block) with:

```csharp
            // The curves are the only way in. What Pattern says about them
            // is one pure function of three counts, so the error path is
            // measured in the harness rather than trusted: curves wired and
            // none placed is an error and NO pattern leaves this component,
            // because a pattern whose bars could not be placed is not the
            // pattern that was asked for.
            List<List<int>> principalRuns = PrincipalRunFinder.FromCurves(
                principalCurves,
                patternVertices,
                patternEdges,
                out double principalOffset,
                out double principalGauge,
                out int unmatchedCurves);
            PrincipalOutcome outcome = PrincipalRunFinder.Outcome(
                principalCurves.Count, unmatchedCurves, principalRuns.Count);
            switch (outcome.Severity)
            {
                case "error":
                    throw new InvalidOperationException(outcome.Message);
                case "warning":
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning, outcome.Message);
                    break;
                case "remark":
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark, outcome.Message);
                    break;
            }
```

The `catch (Exception error)` at the end of `SolveInstance` already sets `Message = "Invalid"` and calls `ReportException("Pattern failed", error)`, which adds the Error runtime message; nothing is `SetData` before the throw, so the error case emits nothing. Leave the existing offset remark block (the `if (principalRuns.Count > 0 && principalGauge > 0.0 && principalOffset > 0.25 * principalGauge)` block) exactly as it is; it follows immediately.

- [ ] **Step 5: Show the run count on the message line**

Replace the `Message = ...` assignment just after `SetTopologyPreview(topology);` (lines 277 to 279 today) with:

```csharp
            int runCount = topology.PrincipalRuns.Count;
            string runNote = runCount switch
            {
                0 => string.Empty,
                1 => ", 1 principal line",
                _ => $", {runCount} principal lines"
            };
            Message =
                $"{DisplayMode(mode)} - {topology.Vertices.Count}V/" +
                $"{topology.Edges.Count}E{runNote}";
```

- [ ] **Step 6: Run the gate to see it pass**

Expected: pass, including `PASS  Pattern [Ananke.COMPAS.Native.Components.PatternComponent]` with input 4 flattened.

- [ ] **Step 7: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/SpineComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(pattern): P flattens, curves that place no bar are an error with no output, the message line counts the lines"
```

---

### Task 3: Supports loses Ribs; Supports and Loads stop painting the bars

**Files:**
- Modify: `plugin/native_v02/Components/SpineComponents.cs` (Supports class from line 359; Loads class from line 630)
- Test: `tests/native_smoke/Program.cs` (`SpineComponentContracts` Supports entry, line 121)

**Interfaces:**
- Consumes: Task 1 already deleted the derive block and set `Pattern = source`.
- Produces: Supports has three inputs `PAT`, `A`, `Tol`.

- [ ] **Step 1: Pin the port list in the harness**

Change line 121 of `tests/native_smoke/Program.cs`:

```csharp
                    new[] { "PAT", "A", "Tol" },
```

- [ ] **Step 2: Run the gate to see it fail**

Expected: one failure naming `SupportsComponent` with an input nickname mismatch (four found, three expected).

- [ ] **Step 3: Remove the Ribs port and its read**

In the Supports class:
- Delete the `parameters.AddIntegerParameter("Ribs", "RB", ...)` call and the line `parameters[3].Optional = true;`. Keep `parameters[2].Optional = true;`.
- Delete `int ribs = 1;` and `data.GetData(3, ref ribs);` from `SolveInstance`.
- Delete the field `private readonly List<Line> _previewPrincipal = new();`, the `_previewPrincipal.Clear();` line in `BeforeSolveInstance`, the `foreach (Line bar in _previewPrincipal) { ... }` loop in `DrawVisibleViewportWires`, and the two lines `_previewPrincipal.Clear();` and `_previewPrincipal.AddRange(TnaWorkflowPreview.TopologyPrincipalLines(topology));` in `SetPreview`.

After this, Supports' `SetPreview` is:

```csharp
    private void SetPreview(
        TopologyDto topology,
        IReadOnlyList<int> nodeIds)
    {
        _previewEdges.Clear();
        _previewEdges.AddRange(TnaWorkflowPreview.TopologyLines(topology));
        _previewSupports.Clear();
        _previewSupports.AddRange(
            nodeIds.Select(id => TnaWorkflowPreview.Point(topology.Vertices[id])));
        _clippingBox = TnaWorkflowPreview.Box(
            _previewEdges,
            _previewSupports);
    }
```

and its `RegisterInputParams` ends:

```csharp
        parameters.AddNumberParameter(
            "Snap Tolerance",
            "Tol",
            "Optional maximum anchor-to-node snapping distance. Empty uses " +
            "the Pattern weld tolerance.",
            GH_ParamAccess.item);
        parameters[2].Optional = true;
    }
```

- [ ] **Step 4: Loads stops painting the bars**

In the Loads class:
- Delete the field `private readonly List<Line> _previewPrincipal = new();`.
- Delete `_previewPrincipal.Clear();` from `BeforeSolveInstance`.
- In `DrawVisibleViewportWires`, delete the four-line comment beginning `// The bars are drawn here even though the net is not` and the `foreach (Line bar in _previewPrincipal) { ... }` loop, leaving only the arrows loop:

```csharp
    protected override void DrawVisibleViewportWires(IGH_PreviewArgs args)
    {
        foreach (Line arrow in _previewArrows)
            args.Display.DrawArrow(arrow, Color.FromArgb(238, 135, 35));
    }
```

- In `SetPreview`, delete `_previewPrincipal.Clear();` and the `_previewPrincipal.AddRange(TnaWorkflowPreview.TopologyPrincipalLines(topology));` statement.

- [ ] **Step 5: Run the gate to see it pass**

Expected: pass with 0 build warnings and `PASS  Supports [...]`.

- [ ] **Step 6: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/SpineComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "refactor(supports): the Ribs port goes and neither Supports nor Loads paints the bars"
```

---

### Task 4: Pattern is the only preview owner

**Files:**
- Modify: `plugin/native_v02/Components/SolverComponents.cs` (TNA Relax lines 37, 115, 300 to 306, 471, 474 to 489, 528; TNA Solve lines 569, 695, 720 to 726, 826 to 828; FD Solve lines 1073, 1153, 1165 to 1171, 1278 to 1280)
- Modify: `plugin/native_v02/Components/VisualiseComponents.cs` (Display lines 1539 to 1552)
- Modify: `plugin/native_v02/Components/MouldComponents.cs` (Animate lines 142, 159, 198 to 204, 909 to 915)
- Modify: `plugin/native_v02/Components/ColumnFinderComponents.cs` (Columns lines 108, 122, 164 to 170, 747 to 753, and the doc comment at 132 to 133)
- Modify: `plugin/native_v02/Components/TnaWorkflowComponents.cs` (`TnaWorkflowPreview` lines 243 to 257 doc comment, 294 to 309 `ResultPrincipalLines`)
- Test: `tests/native_smoke/Program.cs` (new check `ValidatePrincipalPreviewOwner`)

Line numbers are as the files stand at the start of this plan; Tasks 1 to 3 do not touch these files except SpineComponents.cs. Locate by content, not by number.

**Interfaces:**
- Consumes: nothing.
- Produces: `TnaWorkflowPreview.ResultPrincipalLines` no longer exists; this task's own check asserts it.

- [ ] **Step 1: Write the failing check**

In `tests/native_smoke/Program.cs`, after the `ValidatePrincipalOutcome` try block added in Task 1, add:

```csharp
        try
        {
            ValidatePrincipalPreviewOwner(plugin, componentTypes);
            Console.WriteLine(
                "PASS  Preview ownership: Pattern is the ONLY component holding "
                + "a principal-line preview, and the Result-side helper that "
                + "fed the others is gone. Nine components painted the same "
                + "red bars, and with a solver's preview underneath each bar "
                + "drew twice; one owner, one drawing.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Principal preview owner: {DescribeException(exception)}");
        }
```

and the method, next to `ValidateDerivationRemoved`:

```csharp
    /// <summary>
    /// Pattern is the only component that previews principal runs. Every
    /// other component used to hold a <c>List&lt;Line&gt;</c> of red bars and
    /// paint it over its own preview, so two components on one canvas showed
    /// each bar twice: the "dual lining" that read as a doubled principal
    /// line. The rule is mechanical: an instance field of type List of Line
    /// whose name contains "Principal" exists on PatternComponent and on no
    /// other component, and the helper that read runs off a Result for the
    /// others, <c>TnaWorkflowPreview.ResultPrincipalLines</c>, is gone.
    /// </summary>
    private static void ValidatePrincipalPreviewOwner(
        Assembly plugin,
        Type[] componentTypes)
    {
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static | BindingFlags.Instance;
        Type preview = plugin.GetType(
            "Ananke.COMPAS.Native.Components.TnaWorkflowPreview",
            throwOnError: true)!;
        if (preview.GetMethods(Any).Any(m => m.Name == "ResultPrincipalLines"))
        {
            throw new InvalidOperationException(
                "TnaWorkflowPreview.ResultPrincipalLines still exists. Pattern is "
                + "the only component that previews principal runs, and it reads "
                + "a topology, not a Result.");
        }

        const BindingFlags Fields = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Instance | BindingFlags.DeclaredOnly;
        var owners = new List<string>();
        foreach (Type componentType in componentTypes)
        {
            for (Type? at = componentType; at is not null; at = at.BaseType)
            {
                foreach (FieldInfo field in at.GetFields(Fields))
                {
                    if (!field.Name.Contains(
                            "Principal", StringComparison.OrdinalIgnoreCase))
                        continue;
                    Type type = field.FieldType;
                    bool listOfLine = type.IsGenericType
                        && type.GetGenericTypeDefinition() == typeof(List<>)
                        && type.GetGenericArguments()[0].Name == "Line";
                    if (listOfLine)
                        owners.Add(componentType.FullName ?? componentType.Name);
                }
            }
        }

        const string Pattern = "Ananke.COMPAS.Native.Components.PatternComponent";
        if (!owners.Contains(Pattern))
        {
            throw new InvalidOperationException(
                "PatternComponent holds no principal-line preview field; it is "
                + "the one component that must.");
        }
        string[] others = owners.Where(o => o != Pattern).Distinct().ToArray();
        if (others.Length > 0)
        {
            throw new InvalidOperationException(
                "Only Pattern previews principal runs; these still hold a "
                + $"principal preview field: {string.Join(", ", others)}.");
        }
    }
```

`FieldInfo` is in `System.Reflection`, which `Program.cs` already imports (it uses `MethodInfo` and `BindingFlags`).

- [ ] **Step 2: Run the gate to see it fail**

Expected: `Principal preview owner: ... these still hold a principal preview field: ...ColumnFinderComponent, ...AnimateComponent, ...FdSolveComponent, ...TnaRelaxComponent, ...TnaSolveComponent` (names as the assembly has them; Supports and Loads were cleared in Task 3; Display keeps no field, it adds to a shared `_preview` list, so it does not appear here and is covered by the `ResultPrincipalLines` deletion below).

- [ ] **Step 3: TNA Relax**

In `SolverComponents.cs`, class `TnaRelaxComponent`:
- Delete the field `private readonly List<Line> _principalPreview = new();`.
- Delete `_principalPreview.Clear();` from `BeforeSolveInstance`.
- Delete the `foreach (Line bar in _principalPreview) { ... }` loop from the draw method.
- In `BuildPreparedPreview`, delete `_principalPreview.Clear();`, the comment beginning `// The runs come from the LOCAL problem` through the closing brace of `if (sourceTopology is not null && ...) { _principalPreview.AddRange(...); }`, and the `TopologyDto? sourceTopology = problem?.Anchored?.Pattern?.Topology;` declaration if nothing else in the method reads it (nothing does). Change `.Concat(_principalPreview)` in the `_clippingBox` expression to nothing, so it reads:

```csharp
        _clippingBox = TnaWorkflowPreview.Box(
            _formPreview
                .Concat(_forcePreview)
                .Concat(_boundaryPreview),
            _supportPreview);
```

If the `problem` parameter of `BuildPreparedPreview` is then unused, keep the parameter (removing it changes the call site for no gain) but do not leave a compiler warning; an unused parameter is not a warning in C#.

- [ ] **Step 4: TNA Solve and FD Solve**

Class `TnaSolveComponent`: delete the field `_previewPrincipal`, its `Clear()` in `BeforeSolveInstance`, the `foreach (Line bar in _previewPrincipal)` loop in `DrawViewportWires`, and the two statements `_previewPrincipal.Clear(); _previewPrincipal.AddRange(TnaWorkflowPreview.ResultPrincipalLines(result.Result));` in the result handler.

Class `FdSolveComponent`: the same four deletions.

- [ ] **Step 5: Display**

In `VisualiseComponents.cs`, delete the block from the comment `// The notched bars, over the thrust network they belong to.` through the closing brace of `if (elements.Contains("thrust")) { _preview.AddRange(TnaWorkflowPreview.ResultPrincipalLines(result)...); }`.

- [ ] **Step 6: Animate and Columns**

`MouldComponents.cs`, Animate: delete the field `_previewPrincipal`, its `Clear()` in `BeforeSolveInstance`, the `foreach (Line bar in _previewPrincipal)` loop in `DrawViewportWires`, and in the solve the block:

```csharp
                _previewPrincipal.Clear();
                foreach (List<int> run in bars)
                {
                    for (int k = 0; k + 1 < run.Count; k++)
                        _previewPrincipal.Add(
                            new Line(live[run[k]], live[run[k + 1]]));
                }
```

`ColumnFinderComponents.cs`, Columns: the same four deletions (the solve block there iterates `foreach (List<int> bar in bars)` over `nodes`). Also amend the `DrawViewportMeshes` doc comment sentence `On top of that goes the one thing only this component knows, the columns, and the bars they hold.` to `On top of that goes the one thing only this component knows, the columns. The bars are Pattern's to draw.`

- [ ] **Step 7: Delete ResultPrincipalLines and rewrite the doc comment**

In `TnaWorkflowComponents.cs`, `TnaWorkflowPreview`: delete the `ResultPrincipalLines` method and its doc comment (from `/// <summary>` `The runs a solved Result carries` through the method's closing brace). Replace the doc comment above `PrincipalColour` with:

```csharp
    /// <summary>
    /// The principal lines: the notched bars a reconfigurable mould holds
    /// rigid along the net.
    ///
    /// Red, at the same weight as the network they lie on, so the only
    /// distinction is colour. That is deliberate: a bar is a member of the
    /// net, not a highlight laid over it, and drawing it heavier would say
    /// otherwise.
    ///
    /// PATTERN ALONE draws them, from the vertex runs it resolved from the
    /// curves drawn into it. Every other stage used to paint the same runs
    /// over its own preview, and with a solver's preview underneath each bar
    /// showed twice. One owner, one drawing. A pattern that carries no runs
    /// draws nothing rather than guessing.
    /// </summary>
```

If `ResultDto` or `EquilibriumResultDto` is now referenced nowhere else in that file, the `using Ananke.COMPAS.Native.Contracts;` stays because `TopologyDto` and `Point3Dto` are still used; verify with the 0-warning build.

- [ ] **Step 8: Run the gate to see it pass**

Expected: pass, 0 warnings, `PASS  Preview ownership`.

- [ ] **Step 9: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/SolverComponents.cs" "plugin/native_v02/Components/VisualiseComponents.cs" "plugin/native_v02/Components/MouldComponents.cs" "plugin/native_v02/Components/ColumnFinderComponents.cs" "plugin/native_v02/Components/TnaWorkflowComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "refactor(preview): Pattern alone draws the principal lines; eight red copies and the Result helper go"
```

---

### Task 5: Every message points at Pattern, and the taxonomy says so

**Files:**
- Modify: `plugin/native_v02/Components/ColumnFinderComponents.cs` (the no-runs warning at lines 377 to 381; the `columns.principal_source` entry at 1213 to 1216)
- Modify: `plugin/native_v02/Components/MouldComponents.cs` (the comment at 434 to 438 and the no-runs warning at 444 to 448)
- Modify: `docs/component-taxonomy.md` (Pattern row line 44, Supports row line 45)

**Interfaces:** none.

- [ ] **Step 1: Columns' messages**

Replace the warning text in the `if (bars.Count == 0)` block:

```csharp
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines. Draw Principal "
                            + "Lines into Pattern upstream; nothing derives them.");
```

Replace the `columns.principal_source` entry:

```csharp
            d.Add(ResultDiagnostics.Entry(S, "columns.principal_source", "info",
                "principal lines came from the contract, resolved upstream by "
                    + "Pattern from the curves drawn into it; nothing was "
                    + "re-matched here.",
                bars.Count, unit: "bars"));
```

- [ ] **Step 2: Animate's message and comment**

Replace the comment that begins `// The principal lines this Result carries, resolved upstream by` (the lines mentioning `from the anchors or by Pattern from drawn curves`) so it reads:

```csharp
                // The principal lines this Result carries, resolved upstream
                // by Pattern from the curves drawn into it. Nothing is snapped
                // here, which is why there is no curve input: indices survive
                // a surface that rises and curves do not.
```

Replace the warning text:

```csharp
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines, so nothing is "
                            + "held and there is nothing to lift. Draw Principal "
                            + "Lines into Pattern upstream.");
```

- [ ] **Step 3: Grep for stragglers**

Run from the repo root:

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
rg -n "Ribs|DeriveFromAnchors|ResultPrincipalLines|from the anchors" "$repo\plugin\native_v02" "$repo\tests\native_smoke" "$repo\docs\component-taxonomy.md"
```

Expected: no output, apart from `VisualiseComponents.cs` line 483's comment if it still says `resolved upstream by` followed by Supports; if it does, rewrite that comment to `resolved upstream by Pattern from the curves drawn into it`. Historical specs and plans under `docs/superpowers` are left as written.

- [ ] **Step 4: Taxonomy rows**

In `docs/component-taxonomy.md` replace the Pattern row with:

```markdown
| `01 Model` | **Pattern** | Geometry `G`, Mode `M`, Resolution `R`, Weld Tolerance `Tol`, Principal Lines `P` (optional, flattened) | Pattern `PAT` | Register a stable Rhino mesh or already-split planar line pattern as the shared spine's source geometry. Surface, Grid, Triangulation, and Skeleton modes fail explicitly until their generators exist. `Principal Lines` are the notched bars of the reconfigurable mould, drawn as curves over the pattern and matched here, in plan, to runs of pattern vertices carried downstream as indices; this is the only way a principal line enters the chain. Curves that place no bar are an error and no Pattern is emitted; a dropped curve is a warning; two curves on one run are merged with a remark. Pattern is the only component that previews the bars, in red at the net's own weight; the message line counts them. |
```

and the Supports row with:

```markdown
| `01 Model` | **Supports** | Pattern `PAT`, Anchor Points `A`, Snap Tolerance `Tol` (optional) | Anchored Pattern `SUP` | Snap explicit structural anchors to a registered Pattern; intermediate boundary vertices stay free for relaxation. Carries the Pattern's principal runs through unchanged and derives none. |
```

- [ ] **Step 5: Run the gate**

Expected: pass, 0 warnings.

- [ ] **Step 6: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnFinderComponents.cs" "plugin/native_v02/Components/MouldComponents.cs" "plugin/native_v02/Components/VisualiseComponents.cs" "docs/component-taxonomy.md"
git -C $repo commit -m "docs(principal): every message and the taxonomy point at Pattern as the one source of principal lines"
```

If `VisualiseComponents.cs` was not changed in Step 3, omit it from the `git add`.

---

## Self-review

Spec coverage: decision 1 (Task 1), 2 (Task 2), 3 (Tasks 1 and 2), 4 (Task 2), 5 (Tasks 1 and 3), 6 (Tasks 3 and 4), 7 (Task 5), 8 (no task changes GUIDs, ports beyond Ribs, or contracts). Testing section: `SpineComponentContracts` (Task 3), `FlattenedInputs` (Task 2), `ValidateDerivationRemoved` and `ValidatePrincipalOutcome` (Task 1), `ValidatePrincipalPreviewOwner` (Task 4). Canvas section needs no code.

Type consistency: `FromCurves(..., out double worstOffset, out double gauge, out int unmatched)` in Task 1 and Task 2; `Outcome(int supplied, int unmatched, int kept)` returning `PrincipalOutcome(string Severity, string Message)` in Task 1, Task 2 and the harness; `ValidatePrincipalPreviewOwner(Assembly plugin, Type[] componentTypes)` takes the array declared at line 238 of `Program.cs`.

Every task's gate is fully green at its commit. Task 1 removes the derivation and, because Supports' call to it would not compile, deletes Supports' derive block in the same task; the Ribs port itself goes in Task 3.
