# Monitor, Deconstruct, Skin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Monitor carries every number as a tree aligned with a Deconstruct or Animate tree, Deconstruct carries geometry only, and a new Skin component carries the tessellation cells.

**Architecture:** A shared `ResultTables` static (members with ends, force, q, H and id in one fixed order; support node ids in strip order; reactions by node) is extracted from Deconstruct so Monitor enumerates members, supports and reactions in exactly Deconstruct's order and the trees align by construction. `MonitorMath` holds the pure arithmetic (tensioner axis, anchor split, deviation statistics, unstrained length). Skin receives Deconstruct's face-course code unchanged.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8, the Rhino-free reflection smoke harness in `tests/native_smoke`, Python 3 stdlib for the icon.

**Spec:** `docs/superpowers/specs/2026-08-28-monitor-deconstruct-skin-design.md`

## Global Constraints

- No em dashes anywhere, in code, comments, docs or commit messages.
- Full absolute Windows paths in any reply to Param.
- No Co-Authored-By or AI attribution in any commit.
- Commit locally after every task; never push.
- Every measured check runs in the smoke harness without launching Rhino; `MonitorMath` uses only `Point3d`, `Vector3d.Length`, operators.
- Before every build and every commit, run the OneDrive clash check in the shared gate below (ignore matches under `obj\`).
- GUIDs never change: Monitor `e8c216af-5b74-4d93-a027-9f61be40d5c3`, Deconstruct's existing GUID. Skin's GUID is `7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063`.
- No contract type changes.
- `plugin/native_v02/Components/DeliveryComponents.cs` is another session's uncommitted work: never staged. `git add` by explicit path only.
- The build must produce 0 warnings.
- Export, Animate, Columns, Diagnose are untouched.

---

## File structure

| Path (relative to `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`) | Responsibility |
| --- | --- |
| `plugin/native_v02/Components/SkinComponents.cs` (create) | The Skin component and the face-course helpers moved from Deconstruct. |
| `plugin/icons/skin.png`, `plugin/icons/make_skin_icon.py` (create) | Skin's 24x24 icon and its generator. |
| `plugin/native_v02/Components/VisualiseComponents.cs` (modify) | Deconstruct trimmed to geometry; `ResultTables` extracted; face helpers removed; `ThrustMesh` made internal. |
| `plugin/native_v02/Components/MonitorComponents.cs` (rewrite) | Monitor's new ports and solve; `MonitorMath`. |
| `tests/native_smoke/Program.cs` (modify) | `VisualiseContracts` entries for Deconstruct, Skin, Monitor; `ValidateMonitorMath`. |
| `docs/component-taxonomy.md` (modify) | Monitor, Deconstruct rows; Skin row. |

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

### Task 1: Skin

**Files:**
- Create: `plugin/native_v02/Components/SkinComponents.cs`
- Create: `plugin/icons/make_skin_icon.py`, `plugin/icons/skin.png`
- Modify: `plugin/native_v02/Components/VisualiseComponents.cs` (change `private static Mesh ThrustMesh(ResultDto result)` at about line 736 to `internal static`)
- Test: `tests/native_smoke/Program.cs` (`VisualiseContracts` gains the Skin entry)

**Interfaces:**
- Consumes: `DeconstructComponent.ThrustMesh(ResultDto)` (made internal here), `OutputTree.Curves`, `OutputTree.Integers`, `NativeComponentBase`, `ComponentCategories.Visualise`, `ResultParam`/`ResultGoo`.
- Produces: `SkinComponent` with inputs `Result`, `Course Height` and outputs `Face Polylines`, `Face Courses`. Task 2 deletes Deconstruct's copies of the helpers once this exists.

- [ ] **Step 1: Pin the ports**

In `VisualiseContracts` (Program.cs, about line 64) add:

```csharp
                ["Ananke.COMPAS.Native.Components.SkinComponent"] = (
                    new[] { "Result", "Course Height" },
                    new[] { "Face Polylines", "Face Courses" }),
```

- [ ] **Step 2: Run the gate to see nothing change**

The table is consulted only for types that exist, so the gate stays green; this step just proves the harness still builds. (The Skin entry starts biting in Step 5.)

- [ ] **Step 3: The icon**

Create `plugin/icons/make_skin_icon.py`, a copy of `make_diagnose_icon.py` with `FILL = (78, 89, 104, 255)` (the slate the mould family uses), glyphs `S` and `K`:

```python
GLYPHS = {
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
}
```

`blit("S", 5, 8)`, `blit("K", 13, 8)`, output `plugin/icons/skin.png`. Run it from the repo root with `python plugin/icons/make_skin_icon.py`; the csproj embeds every `..\icons\*.png` by glob, so nothing else registers it.

- [ ] **Step 4: The component**

Create `plugin/native_v02/Components/SkinComponents.cs`:

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Skin: the cells the surface is built from, one closed polyline per
    /// face of the thrust mesh, banded into courses by height. The
    /// ready-made Cells and Courses inputs for Export's Tessellation format.
    /// Moved here from Deconstruct, which is geometry only; the mechanism is
    /// unchanged.
    /// </summary>
    public sealed class SkinComponent : NativeComponentBase
    {
        public SkinComponent()
            : base(
                "Skin",
                "Skin",
                "One closed polyline per face of the thrust mesh, banded into "
                    + "courses by Course Height: the Cells and Courses for "
                    + "Export's Tessellation format.",
                ComponentCategories.Visualise,
                "skin")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "A solved TNA Result. FD carries no faces and gives nothing.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Course Height",
                "CH",
                "Band height in metres for the Face Courses output: faces are "
                    + "banded by centroid height from the lowest face upward, "
                    + "bottom row 0. Minimum 1 mm.",
                GH_ParamAccess.item,
                0.35);
            parameters[1].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddCurveParameter(
                "Face Polylines",
                "FP",
                "One closed polyline per Thrust Mesh face, as a TREE branched "
                    + "by COURSE (path = course, 0-up from the bottom): the "
                    + "ready-made Cells input for Export's Tessellation format. "
                    + "Empty for FD.",
                GH_ParamAccess.tree);
            parameters.AddIntegerParameter(
                "Face Courses",
                "FC",
                "The course per face, branched and ordered exactly as Face "
                    + "Polylines, so the pairing survives: the ready-made "
                    + "Courses input for Export's Tessellation format. Empty "
                    + "for FD.",
                GH_ParamAccess.tree);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }
            double courseHeight = 0.35;
            data.GetData(1, ref courseHeight);
            // Negated comparison, not "<= 0": NaN fails every comparison, so
            // "NaN <= 0" would sail past a positivity guard and floor every
            // face to course 0; a tiny positive would overflow the int cast
            // in FaceCourses. 1 mm is the sane floor for a physical course.
            if (!(courseHeight > 0.001))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Course Height must be at least 1 mm; using 0.35 m.");
                courseHeight = 0.35;
            }

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                bool isTna =
                    string.Equals(result.Solver, "tna", StringComparison.OrdinalIgnoreCase) &&
                    result.FormGraph is not null &&
                    result.ForceGraph is not null &&
                    result.Mappings is not null;
                Mesh mesh = isTna ? DeconstructComponent.ThrustMesh(result) : new Mesh();
                if (mesh.Faces.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        "No faces on this Result (FD carries none), so there are "
                            + "no cells.");
                }

                IReadOnlyList<PolylineCurve> facePolylines = FacePolylines(mesh);
                IReadOnlyList<int> faceCourses = FaceCourses(mesh, courseHeight);
                var faceByCourse = new List<List<Curve>>();
                var courseByCourse = new List<List<int>>();
                int courseCount = faceCourses.Count == 0 ? 0 : faceCourses.Max() + 1;
                for (int c = 0; c < courseCount; c++)
                {
                    faceByCourse.Add(new List<Curve>());
                    courseByCourse.Add(new List<int>());
                }
                for (int i = 0; i < facePolylines.Count; i++)
                {
                    int course = i < faceCourses.Count ? faceCourses[i] : 0;
                    if (course < 0 || course >= courseCount)
                        continue;
                    faceByCourse[course].Add(facePolylines[i]);
                    courseByCourse[course].Add(course);
                }
                data.SetDataTree(0, OutputTree.Curves(faceByCourse));
                data.SetDataTree(1, OutputTree.Integers(courseByCourse));
                Message = $"{facePolylines.Count} cells, {courseCount} courses";
            }
            catch (Exception error)
            {
                Message = "Invalid";
                ReportException("Skin failed", error);
            }
        }

        // FaceCorners, FacePolylines and FaceCourses: copied VERBATIM from
        // DeconstructComponent (VisualiseComponents.cs, about lines 650 to
        // 725 at the start of this plan), including their doc comments.
        // Task 2 deletes the originals.
    }
}
```

Copy the three private static methods `FaceCorners`, `FacePolylines`, `FaceCourses` from Deconstruct into the class body where the comment says.

- [ ] **Step 5: Make `ThrustMesh` internal, run the gate, commit**

In VisualiseComponents.cs change `private static Mesh ThrustMesh(ResultDto result)` to `internal static Mesh ThrustMesh(ResultDto result)`. Run the gate: 19 components, `PASS  Skin [...]`, icon 24x24. Commit:

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/SkinComponents.cs" "plugin/icons/skin.png" "plugin/icons/make_skin_icon.py" "plugin/native_v02/Components/VisualiseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(skin): the cells and courses leave Deconstruct for their own component"
```

---

### Task 2: Deconstruct is geometry only, and `ResultTables` is shared

**Files:**
- Modify: `plugin/native_v02/Components/VisualiseComponents.cs` (Deconstruct: `RegisterInputParams` about line 167, `RegisterOutputParams` 196 to 335, `SolveInstance` 337 to 645, the face helpers 650 to 725; add `ResultTables`)
- Test: `tests/native_smoke/Program.cs` (`VisualiseContracts` Deconstruct entry, lines 69 to 96)

**Interfaces:**
- Produces (Task 3 depends on these exact names):

```csharp
    /// <summary>
    /// The member, support and reaction tables of a Result in ONE fixed
    /// order, so every component that branches by member or by support
    /// strip reads the same rows. Deconstruct builds its geometry from
    /// them and Monitor its numbers, which is what makes their trees align
    /// item for item without either matching coordinates.
    /// </summary>
    internal static class ResultTables
    {
        /// <summary>One member: its equilibrium ends, signed force, q and H
        /// (NaN when the Result does not carry them), and its stable id.</summary>
        public readonly record struct MemberRow(int U, int V, double Force, double Q, double H, int Id, int EquilibriumEdgeId);

        public static bool IsTna(ResultDto result);
        /// <summary>TNA: edge states ordered by Id; FD: equilibrium edges in order.</summary>
        public static MemberRow[] Members(ResultDto result);
        /// <summary>Support node ids in the order Deconstruct's Node IDs use before stripping: TNA Mappings.Supports, FD ResolvedSupportNodeIds.</summary>
        public static int[] SupportNodes(ResultDto result);
        /// <summary>Reactions by node: TNA Mappings.Reactions, FD equilibrium.Reactions; zero-length vectors dropped.</summary>
        public static (int Node, Vector3d Vector)[] Reactions(ResultDto result);
    }
```

- [ ] **Step 1: Pin the trimmed port list**

Replace the Deconstruct entry in `VisualiseContracts` with:

```csharp
                ["Ananke.COMPAS.Native.Components.DeconstructComponent"] = (
                    new[] { "Result" },
                    new[]
                    {
                        "Thrust Mesh",
                        "Member Lines",
                        "Form Lines",
                        "Member IDs",
                        "Node IDs",
                        "Support Points",
                        "Load Points",
                        "Load Vectors",
                        "Reaction Points",
                        "Reaction Vectors",
                        "Columns",
                        "Heads",
                        "Feet"
                    }),
```

- [ ] **Step 2: Run the gate to see Deconstruct fail on the contract**

Expected: one failure naming `DeconstructComponent` with an input or output name mismatch.

- [ ] **Step 3: Extract `ResultTables`**

Add the class above (as a real implementation) to VisualiseComponents.cs, next to `DeconstructComponent`, built from the code Deconstruct's `SolveInstance` has today:

```csharp
    internal static class ResultTables
    {
        public readonly record struct MemberRow(
            int U, int V, double Force, double Q, double H, int Id, int EquilibriumEdgeId);

        public static bool IsTna(ResultDto result) =>
            string.Equals(result.Solver, "tna", StringComparison.OrdinalIgnoreCase) &&
            result.FormGraph is not null &&
            result.ForceGraph is not null &&
            result.Mappings is not null;

        public static MemberRow[] Members(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            if (IsTna(result))
            {
                return result.EdgeStates
                    .OrderBy(state => state.Id)
                    .Select(state =>
                    {
                        (int u, int v) = Ends(equilibrium, state.EquilibriumEdgeId);
                        return new MemberRow(
                            u, v, state.AxialForce, state.ForceDensity,
                            state.HorizontalForce, state.Id, state.EquilibriumEdgeId);
                    })
                    .ToArray();
            }
            var rows = new MemberRow[equilibrium.Edges.Count];
            for (int i = 0; i < rows.Length; i++)
            {
                (int u, int v) = Ends(equilibrium, i);
                double force = i < equilibrium.MemberForces.Count ? equilibrium.MemberForces[i] : 0.0;
                double q = i < equilibrium.ForceDensities.Count ? equilibrium.ForceDensities[i] : double.NaN;
                rows[i] = new MemberRow(u, v, force, q, double.NaN, i, i);
            }
            return rows;
        }

        public static int[] SupportNodes(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            return IsTna(result)
                ? result.Mappings!.Supports.Select(item => item.EquilibriumVertexId).ToArray()
                : equilibrium.ResolvedSupportNodeIds.ToArray();
        }

        public static (int Node, Vector3d Vector)[] Reactions(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            if (IsTna(result))
            {
                return result.Mappings!.Reactions
                    .Select(item => (item.EquilibriumVertexId,
                        new Vector3d(item.Reaction.X, item.Reaction.Y, item.Reaction.Z)))
                    .Where(item => item.Item2.SquareLength > 1.0e-24)
                    .ToArray();
            }
            return equilibrium.Reactions
                .Select(item => (item.NodeId,
                    new Vector3d(item.Vector.X, item.Vector.Y, item.Vector.Z)))
                .ToArray();
        }

        private static (int, int) Ends(EquilibriumResultDto equilibrium, int edgeId)
        {
            // Copy the body of DeconstructComponent.EquilibriumEnds here, or
            // call it if it is static and reachable; keep ONE implementation.
        }
    }
```

Resolve the `Ends` note by reading `DeconstructComponent.EquilibriumEnds` (search for it) and either moving it here (then Deconstruct calls `ResultTables`) or calling it; one copy only. Check the exact property names on `TnaEdgeStateDto` (`AxialForce`, `ForceDensity`, `HorizontalForce`, `Id`, `EquilibriumEdgeId`), `TnaMappingsDto.Supports[].EquilibriumVertexId`, `Mappings.Reactions[].Reaction`, `NodalVectorDto.NodeId/Vector` against the contracts before writing; the names above are read from Deconstruct's current code.

- [ ] **Step 4: Trim Deconstruct**

- `RegisterInputParams`: delete the Course Height parameter (Result stays alone).
- `RegisterOutputParams`: delete `q`, `H`, `F`, `Force State`, `Residuals`, `Face Polylines`, `Face Courses`. Order becomes exactly the pinned list.
- `SolveInstance`: delete the `courseHeight` read and its guard; build `memberIds` and `memberEnds` from `ResultTables.Members(result)` (`row.Id`, `(row.U, row.V)`), `nodeIds` from `ResultTables.SupportNodes(result)`, `reactions` from `ResultTables.Reactions(result)` (adding the point `Point(equilibrium.Vertices[node])`); delete the `q`, `h`, `f`, `forceStates`, `residuals` arrays and their `SetData` calls; delete the face-course block and its two `SetDataTree` calls; renumber the remaining `SetData` calls to 0 Thrust Mesh, 1 Member Lines, 2 Form Lines, 3 Member IDs, 4 Node IDs, 5 Support Points, 6 Load Points, 7 Load Vectors, 8 Reaction Points, 9 Reaction Vectors, 10 Columns, 11 Heads, 12 Feet. `memberLines`/`formLines`/`supportPoints`/`loads` keep their current construction (TNA via states, FD via equilibrium); verify that `ThrustLine(equilibrium, state)` uses the same ends `ResultTables` reports, so Member Lines and Monitor's numbers describe the same member.
- Delete `FaceCorners`, `FacePolylines`, `FaceCourses` and `ForceState` if nothing else calls them (grep). Keep `ThrustMesh` (internal, Skin uses it).
- Update the Deconstruct class doc comment and the `Member Lines` description's "Every member-aligned output below" sentence to say Monitor's number trees are aligned with it.

- [ ] **Step 5: Gate, commit**

Expected: 19 components, `PASS  Deconstruct`, `PASS  Deconstruct column trees` (the `ValidateDeconstructColumnTrees` check drives `ColumnTrees` directly and is unaffected). Commit:

```powershell
git -C $repo add "plugin/native_v02/Components/VisualiseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "refactor(deconstruct): geometry only; ResultTables gives every reader the same member, support and reaction order"
```

---

### Task 3: Monitor

**Files:**
- Rewrite: `plugin/native_v02/Components/MonitorComponents.cs` (keep the class name `StressAnalysisComponent`, the GUID, the icon name `stress_analysis`, `BarBending` unchanged)
- Test: `tests/native_smoke/Program.cs` (`VisualiseContracts` Monitor entry; `ValidateMonitorMath` with its try block after the `ValidateLiveColumnNodes` block)

**Interfaces:**
- Consumes: `ResultTables` (Task 2), `MouldGeometry.PrincipalRuns`, `MemberRunIndex`, `ValidEdges`, `BuildAdjacency`, `GroupingAdjacency`, `ConnectedGroups`, `BarLoads`, `BarTransverse`, `BeamSolver.Response`, `OutputTree.*`, `ResultDiagnostics`.
- Produces: `MonitorMath` (spec 2.4 names and signatures).

- [ ] **Step 1: Pin the ports and write the failing check**

Add to `VisualiseContracts`:

```csharp
                ["Ananke.COMPAS.Native.Components.StressAnalysisComponent"] = (
                    new[] { "Result", "EI", "EA", "Tolerance", "Cable Capacity", "Column Capacity" },
                    new[]
                    {
                        "Member Force", "Force Density", "Horizontal Force", "Slack",
                        "Spool Length", "Unstrained Length",
                        "Anchor Along", "Anchor Across",
                        "Tip Reaction", "Column Force", "Thrust", "Lean",
                        "Deviation", "Deviation Stats", "Reachable", "Unreachable",
                        "Bar Sag", "Residuals",
                        "Cable Utilisation", "Column Utilisation",
                        "Result"
                    }),
```

After the `ValidateLiveColumnNodes` try block add:

```csharp
        try
        {
            ValidateMonitorMath(plugin);
            Console.WriteLine(
                "PASS  MonitorMath: an anchor's reaction splits along its "
                + "tensioner axis and across it, the axis is the mean of the "
                + "cables leaving it, the deviation statistics are the RMS, the "
                + "worst and the 95th percentile of a hand-built field, and the "
                + "unstrained length divides by one plus force over EA.");
        }
        catch (Exception exception)
        {
            failures.Add($"MonitorMath: {DescribeException(exception)}");
        }
```

and the method next to `ValidateColumnAim`:

```csharp
    /// <summary>
    /// <c>MonitorMath</c>: the four pure rules Monitor's new outputs rest on,
    /// measured on hand-built inputs so a wrong sign or a wrong percentile
    /// rank cannot pass.
    /// </summary>
    private static void ValidateMonitorMath(Assembly plugin)
    {
        Type math = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MonitorMath", throwOnError: true)!;
        MethodInfo split = RequirePublicStatic(math, "AnchorSplit");
        MethodInfo axis = RequirePublicStatic(math, "TensionerAxis");
        MethodInfo stats = RequirePublicStatic(math, "DeviationStats");
        MethodInfo unstrained = RequirePublicStatic(math, "UnstrainedLength");
        Type vector3d = split.GetParameters()[0].ParameterType;
        Type point3d = axis.GetParameters()[1].ParameterType.GetElementType()!;

        object V(double x, double y, double z) => Activator.CreateInstance(vector3d, x, y, z)!;
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        double Get(object o, string name) => (double)o.GetType().GetProperty(name)!.GetValue(o)!;

        object parts = split.Invoke(null, new[] { V(3.0, 4.0, 0.0), V(1.0, 0.0, 0.0) })!;
        double along = (double)parts.GetType().GetField("Item1")!.GetValue(parts)!;
        double across = (double)parts.GetType().GetField("Item2")!.GetValue(parts)!;
        if (Math.Abs(along - 3.0) > 1.0e-9 || Math.Abs(across - 4.0) > 1.0e-9)
            throw new InvalidOperationException($"Reaction (3,4,0) on axis x splits into along 3, across 4; got {along}, {across}.");

        // Anchor 0 at the origin with cables to (1,0,0) and (0,1,0).
        Array nodes = Array.CreateInstance(point3d, 3);
        nodes.SetValue(P(0.0, 0.0, 0.0), 0);
        nodes.SetValue(P(1.0, 0.0, 0.0), 1);
        nodes.SetValue(P(0.0, 1.0, 0.0), 2);
        var neighbours = new List<int>[] { new() { 1, 2 }, new() { 0 }, new() { 0 } };
        object a = axis.Invoke(null, new object?[] { 0, nodes, neighbours })!;
        double r = 1.0 / Math.Sqrt(2.0);
        if (Math.Abs(Get(a, "X") - r) > 1.0e-9 || Math.Abs(Get(a, "Y") - r) > 1.0e-9 || Math.Abs(Get(a, "Z")) > 1.0e-9)
            throw new InvalidOperationException($"The tensioner axis is the unit mean of the cables leaving the anchor; got ({Get(a, "X"):0.###}, {Get(a, "Y"):0.###}, {Get(a, "Z"):0.###}).");
        object none = axis.Invoke(null, new object?[] { 1, nodes, new List<int>[] { new(), new(), new() } })!;
        if (Math.Abs(Get(none, "Z") - 1.0) > 1.0e-9)
            throw new InvalidOperationException("An anchor with no cable has a vertical axis.");

        object s = stats.Invoke(null, new object?[] { new List<double> { 1.0, -2.0, 3.0, -4.0, 5.0 } })!;
        double rms = (double)s.GetType().GetField("Item1")!.GetValue(s)!;
        double max = (double)s.GetType().GetField("Item2")!.GetValue(s)!;
        double p95 = (double)s.GetType().GetField("Item3")!.GetValue(s)!;
        if (Math.Abs(rms - Math.Sqrt(11.0)) > 1.0e-9 || Math.Abs(max - 5.0) > 1.0e-9 || Math.Abs(p95 - 5.0) > 1.0e-9)
            throw new InvalidOperationException($"Stats of (1,-2,3,-4,5) are RMS sqrt(11), max 5, p95 5; got {rms:0.####}, {max}, {p95}.");
        object empty = stats.Invoke(null, new object?[] { new List<double>() })!;
        if ((double)empty.GetType().GetField("Item1")!.GetValue(empty)! != 0.0)
            throw new InvalidOperationException("Stats of nothing are zero.");
        // Twenty values 1..20: the nearest-rank 95th percentile is the 19th, 19.
        object twenty = stats.Invoke(null, new object?[] { Enumerable.Range(1, 20).Select(i => (double)i).ToList() })!;
        double p95twenty = (double)twenty.GetType().GetField("Item3")!.GetValue(twenty)!;
        if (Math.Abs(p95twenty - 19.0) > 1.0e-9)
            throw new InvalidOperationException($"The nearest-rank 95th percentile of 1..20 is 19; got {p95twenty}.");

        double u = (double)unstrained.Invoke(null, new object?[] { 2.0, 100.0, 1000.0 })!;
        if (Math.Abs(u - (2.0 / 1.1)) > 1.0e-9)
            throw new InvalidOperationException($"Unstrained length of 2 under 100 N with EA 1000 is 2/1.1; got {u:0.######}.");
        double raw = (double)unstrained.Invoke(null, new object?[] { 2.0, 100.0, 0.0 })!;
        if (Math.Abs(raw - 2.0) > 1.0e-9)
            throw new InvalidOperationException("Without EA the strained length is returned.");
    }
```

- [ ] **Step 2: Run the gate to see it fail**

Expected: `MonitorMath: ... MonitorMath ... not found` and `StressAnalysisComponent` failing the contract on its second input name.

- [ ] **Step 3: Rewrite MonitorComponents.cs**

Keep the file header, namespace, class name, constructor (update the description to "Every number a Result and its frame carry, as trees aligned with Deconstruct's and Animate's, plus the machine's own readings: spool lengths, the anchors' pull along and across their tensioners, the tip reactions, the deviation to the solved shape and whether it is within tolerance. Demands only, unless a capacity is wired."), GUID and `BarBending` verbatim. Replace `RegisterInputParams`, `RegisterOutputParams`, `SolveInstance` and `Diagnostics`, and add `MonitorMath`:

```csharp
    /// <summary>The pure arithmetic under Monitor's readings.</summary>
    internal static class MonitorMath
    {
        /// <summary>
        /// A reaction split along the tensioner axis (signed, positive along
        /// the axis) and across it (the magnitude of the remainder). The
        /// across part is what the anchorage carries and the tensioner cannot.
        /// </summary>
        public static (double Along, double Across) AnchorSplit(Vector3d reaction, Vector3d axis)
        {
            double length = axis.Length;
            if (length <= 1.0e-12)
                return (0.0, reaction.Length);
            Vector3d unit = axis / length;
            double along = (reaction.X * unit.X) + (reaction.Y * unit.Y) + (reaction.Z * unit.Z);
            Vector3d rest = reaction - (unit * along);
            return (along, rest.Length);
        }

        /// <summary>
        /// The tensioner axis at an anchor: the unit mean direction of the
        /// members leaving it into the net. Vertical when it has none.
        /// </summary>
        public static Vector3d TensionerAxis(int anchor, Point3d[] v, List<int>[] neighbours)
        {
            var sum = Vector3d.Zero;
            if (anchor < 0 || anchor >= v.Length || anchor >= neighbours.Length)
                return Vector3d.ZAxis;
            foreach (int other in neighbours[anchor])
            {
                if (other < 0 || other >= v.Length)
                    continue;
                Vector3d d = v[other] - v[anchor];
                double length = d.Length;
                if (length > 1.0e-12)
                    sum += d / length;
            }
            double total = sum.Length;
            return total > 1.0e-12 ? sum / total : Vector3d.ZAxis;
        }

        /// <summary>
        /// RMS, worst absolute, and nearest-rank 95th percentile of the
        /// absolute values. Zeros on an empty field.
        /// </summary>
        public static (double Rms, double Max, double P95) DeviationStats(IReadOnlyList<double> values)
        {
            if (values.Count == 0)
                return (0.0, 0.0, 0.0);
            double sumSquares = 0.0;
            var absolute = new double[values.Count];
            for (int i = 0; i < values.Count; i++)
            {
                sumSquares += values[i] * values[i];
                absolute[i] = Math.Abs(values[i]);
            }
            Array.Sort(absolute);
            int rank = (int)Math.Ceiling(0.95 * absolute.Length);
            rank = Math.Min(Math.Max(rank, 1), absolute.Length);
            return (Math.Sqrt(sumSquares / values.Count), absolute[^1], absolute[rank - 1]);
        }

        /// <summary>The unstrained length of a member: strained over one plus
        /// force over EA; the strained length when EA is not positive.</summary>
        public static double UnstrainedLength(double strained, double force, double EA) =>
            EA > 0.0 ? strained / (1.0 + (force / EA)) : strained;
    }
```

Inputs per spec 2.1 (slots 2 to 5 `Optional = true`; EA and the capacities read with `GetData` into locals initialised to 0 and treated as unwired when not greater than 0). Outputs per spec 2.2, all `GH_ParamAccess.tree` except Result (item); the descriptions state the document 07 mapping for Slack, Tip Reaction, Deviation and Reachable (spec section 8, one sentence each).

`SolveInstance`, in order:
1. Validate; `equilibrium`; `block`, `frame`; `v` (frame or solved); `target` = solved vertices as Point3d; `n`.
2. `MemberRow[] members = ResultTables.Members(result)`; `edges = ValidEdges(equilibrium, n, out edgeSource)` for `BarBending` only; `runs = PrincipalRuns`; `principal` set; `memberBar = MemberRunIndex(members.Select(m => (m.U, m.V)).ToArray(), runs)`; the `ByBar` local copied from Deconstruct (one branch per bar, infill last).
3. Per member `i`: `length = v[U].DistanceTo(v[V])`; `force = row.Force`; `q = double.IsFinite(row.Q) ? row.Q : (length > 1e-12 ? force / length : 0.0)`; `h = double.IsFinite(row.H) ? row.H : force * Math.Sqrt(PlanDistanceSquared(v[U], v[V])) / Math.Max(length, 1e-12)`; `tension = string.Equals(equilibrium.SignConvention, "positive_compression", OrdinalIgnoreCase) ? force < -1e-9 : force > 1e-9`; `slack = !tension`; `cableUtil = cableCapacity > 0 ? Math.Abs(force) / cableCapacity : NaN` (only emitted when wired). Read `SignConvention`'s actual values off `EquilibriumResultDto` before writing the comparison and match them.
4. Spool: for each run, sum `v[run[k]].DistanceTo(v[run[k+1]])`; unstrained: look each consecutive pair up in a dictionary from `EdgeKey`-style packed `(min, max)` to member index; `UnstrainedLength(length, force, EA)` summed; Unstrained Length emitted only when EA > 0.
5. Anchors: `nodeIds = ResultTables.SupportNodes(result)`; `netEdges = ValidEdges(...)`; `grouping = GroupingAdjacency(result, netEdges, n)`; `strips = ConnectedGroups(nodeIds, grouping)` (exactly Deconstruct's calls); `adjacency = BuildAdjacency(n, netEdges)` for the axis; `reactionAt` from `ResultTables.Reactions(result)`; per strip per node: `axis = TensionerAxis(node, v, adjacency)`, `(along, across) = AnchorSplit(reaction or zero, axis)`; the stray-reaction branch Deconstruct appends is mirrored (an extra trailing branch with the same members) so branch counts match.
6. Columns: when `block` is not null: `cn = frame?.ColumnNodes ?? block.Nodes` as Point3d[]; groups = `block.Trees` when they cover every member index exactly once, else `MouldGeometry.TreesByFoot(MouldGeometry.TreeFromBlock(block))`; heads set from `block.Heads`; per group in order: per member index `m`: line `cn[U]` to `cn[V]`, `force = block.MemberForce[m]`, thrust `force * horizontal / length`, lean `Atan2(horizontal, |dz|)` in degrees, `columnUtil` when wired; Tip Reaction per head in the order Deconstruct's `ColumnTrees` emits heads (walk the group's members; an endpoint seen for the first time that is in the head set is the next head): the vector is `unit(cn[V] - cn[U]) * force` of the member whose upper end `V` is that head.
7. Deviation: `frame is null` gives zeros; else `(v[i].Z - target[i].Z) * 1000.0` per node; stats via `DeviationStats`; `reachable = every |d| <= tolerance`; `unreachable` = the node indices with `|d| > tolerance`, ascending.
8. Bar Sag: `held = anchors ∪ block.HeadNode`; `BarBending(runs, v, edges, edgeSource, equilibrium, held, stiffness)` as today; emit only the sag tree (the bar nodes are Animate's Principal Nodes).
9. Residuals: `equilibrium.Residuals` vectors as one branch.
10. Set every output by slot per spec 2.2; utilisation trees empty when the capacity is not wired; Result with `Diagnostics(...)` per spec 2.3 (keep the existing entries' texts, add `monitor.spool`, `monitor.anchor_split`, `monitor.deviation`, `monitor.reachability`, `monitor.utilisation`).

- [ ] **Step 4: Gate, commit**

Expected: 0 warnings, 19 components, `PASS  MonitorMath`, `PASS  Monitor [...StressAnalysisComponent]`. Commit:

```powershell
git -C $repo add "plugin/native_v02/Components/MonitorComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(monitor): every number as a tree aligned with Deconstruct, plus spool, anchor split, tip reactions, deviation, reachability and utilisation"
```

---

### Task 4: The taxonomy

**Files:**
- Modify: `docs/component-taxonomy.md` (Deconstruct row line 53, Monitor row line 56; insert a Skin row after Monitor)

- [ ] **Step 1: Rows**

Deconstruct row:

```markdown
| `03 Visualise` | **Deconstruct** | Result `RES` | Thrust Mesh `TM`, Member Lines `M`, Form Lines `FL`, Member IDs `MID`, Node IDs `NID`, Support Points `SP`, Load Points `LP`, Load Vectors `LV`, Reaction Points `RP`, Reaction Vectors `RV`, Columns `CO`, Heads `HD`, Feet `FT` | The GEOMETRY of one solved FD or TNA Result, and nothing else: member lines as a tree with one branch per principal line and the infill last, supports and reactions as one branch per connected strip walked end to end, the built column trees from the Mould block one branch per tree. Every number that used to sit here (q, H, F, force state, residuals) is on **Monitor**, branched and ordered identically, so Deconstruct's line at branch b item i and Monitor's number at branch b item i are the same member. The cells moved to **Skin**. Reciprocal-only streams (Thrust Mesh, Form Lines) come out empty for FD. |
```

Monitor row:

```markdown
| `03 Visualise` | **Monitor** | Result `RES`, EI `EI`, EA `EA` (optional), Tolerance `Tol`, Cable Capacity `CC` (optional), Column Capacity `CO` (optional) | Member Force `F`, Force Density `q`, Horizontal Force `H`, Slack `SL`, Spool Length `SP`, Unstrained Length `UL`, Anchor Along `AA`, Anchor Across `AX`, Tip Reaction `TR`, Column Force `CF`, Thrust `TH`, Lean `LN`, Deviation `DV`, Deviation Stats `DS`, Reachable `RC`, Unreachable `UN`, Bar Sag `BS`, Residuals `E`, Cable Utilisation `CU`, Column Utilisation `CLU`, Result `RES` | Every NUMBER a Result and its frame carry, as trees aligned item for item with **Deconstruct**'s geometry (member trees with Member Lines, anchor trees with Reaction Points, column trees with Columns and Heads) and with **Animate**'s Principal Nodes (Bar Sag). The machine's own readings from document 07: the spool length per principal line (strained; unstrained when EA is wired), each anchor's reaction split along its tensioner axis and across it (the across part is the anchorage's), the tip reaction under every head, the signed deviation of this frame from the solved shape with RMS, max and 95th percentile, and whether every node is within Tolerance with the set that is not. Slack marks a member whose force opposes the Result's sign convention. Utilisation is filled only against a capacity the author wires; otherwise every figure is a demand, not a verdict. The Karamba round trip is a manual one fed by Member Force and Column Force with the matching Deconstruct lines. `Result` passes through with Monitor's diagnostics. |
```

Skin row, inserted after Monitor:

```markdown
| `03 Visualise` | **Skin** | Result `RES`, Course Height `CH` | Face Polylines `FP`, Face Courses `FC` | The cells the surface is built from: one closed polyline per face of the thrust mesh, as a tree branched by course (faces banded by centroid height from the lowest, `Course Height` per band, bottom row 0), with the course per face branched identically. The ready-made Cells and Courses inputs for **Export**'s Tessellation format. Empty for FD, which carries no faces. |
```

- [ ] **Step 2: Commit**

```powershell
git -C $repo add "docs/component-taxonomy.md"
git -C $repo commit -m "docs(taxonomy): Deconstruct is geometry, Monitor is every number aligned with it, Skin is the cells"
```

---

## Self-review

Spec coverage: 2.1 and 2.2 (Task 3 ports and solve), 2.3 (Task 3 diagnostics), 2.4 (Task 3 `MonitorMath`), 3 (Task 2), 4 (Task 1), 5 (Task 4), 6 (Tasks 1 to 4), 7 (Task 3 check; contract entries in Tasks 1 to 3; 19 components by construction; no parameter type added so the persistent count stays 12), 8 (port descriptions in Task 3), 9 (no code).

Type consistency: `ResultTables.MemberRow(U, V, Force, Q, H, Id, EquilibriumEdgeId)` produced in Task 2 and consumed in Task 3; `MonitorMath.AnchorSplit(Vector3d, Vector3d)`, `TensionerAxis(int, Point3d[], List<int>[])`, `DeviationStats(IReadOnlyList<double>)`, `UnstrainedLength(double, double, double)` match spec 2.4 and the check; `DeconstructComponent.ThrustMesh` internal in Task 1, used by Skin.

Ordering: Task 1 copies the face helpers before Task 2 deletes them; Task 2 extracts `ResultTables` before Task 3 reads it.
