# Animate Rigid Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Animate's columns stand on their built feet from frame zero and rotate up as one body as the net rises; Time runs four phases; a Perimeter Lines output joins the tree outputs.

**Architecture:** Two pure functions on `MouldGeometry` carry the mechanism, `Phases` (time and pre-sag to sag, lift, phase word) and `LiveColumnNodes` (a block plus the live net to every column node's position: feet fixed, heads on their `HeadNode` vertex, forks at their built fraction along the live foot-to-main segment). Animate calls them and groups members with the existing `TreesByFoot`. The per-frame foot solve (`FootOnRail`), the aim-line fork (`ForkOnLine`), the downward resolution pass and the inline grouping are deleted.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8 (managed only in tests), the Rhino-free reflection smoke harness in `tests/native_smoke`.

**Spec:** `docs/superpowers/specs/2026-08-28-animate-rigid-columns-design.md`

## Global Constraints

- No em dashes anywhere, in code, comments, docs or commit messages.
- Full absolute Windows paths in any reply to Param.
- No Co-Authored-By or AI attribution in any commit.
- Commit locally after every task; never push.
- Every measured check runs in the smoke harness without launching Rhino. `Point3d`, `Vector3d.Length`, `DistanceTo` and operators are managed and fine; `Polyline.ToNurbsCurve` and `Mesh` are not and stay inside the component.
- Before every build and every commit, run the OneDrive clash check in the shared gate below.
- Animate's GUID `b1f4c7a2-5d63-4e19-9c88-3a7e6d0b52f4` never changes. Outputs 0 to 7 never move; Perimeter Lines is APPENDED at 8. Inputs are unchanged.
- No contract type changes. `MouldFrameDto.Phase` values become `reel`, `raise`, `finish`, `hold`.
- `plugin/native_v02/Components/DeliveryComponents.cs` is another session's uncommitted work: never staged. `git add` by explicit path only.
- The build must produce 0 warnings; a `<see cref>` to a deleted member is a warning.

---

## File structure

| Path (relative to `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`) | Responsibility |
| --- | --- |
| `plugin/native_v02/Components/MouldComponents.cs` (modify) | `MouldGeometry.Phases` and `LiveColumnNodes` added; Animate's phase block, column block, outputs and diagnostics rewritten; `FootOnRail` and `ForkOnLine` deleted. |
| `tests/native_smoke/Program.cs` (modify) | `ValidatePhases`, `ValidateLiveColumnNodes`. |
| `docs/component-taxonomy.md` (modify) | The Animate row. |

## The shared gate

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests" -Recurse -Filter "*Name clash*"
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve before building" }
dotnet build "$repo\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -v quiet --nologo
dotnet run --project "$repo\tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "$repo\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"
```

A passing gate ends with `Native component smoke test passed; Rhino was not launched.` and exit code 0, with 0 build warnings. Commit messages follow the repo's `type(scope): sentence` style. Every commit uses explicit file paths.

---

### Task 1: `Phases` and `LiveColumnNodes`, measured

**Files:**
- Modify: `plugin/native_v02/Components/MouldComponents.cs` (add both methods to `MouldGeometry`, directly after `MainBranch`, which ends just before the `ColumnsBlock` doc comment, about line 1960)
- Test: `tests/native_smoke/Program.cs` (new try blocks after the `ValidateOutputGrouping` block, about line 690; methods next to `ValidateColumnsBlock`)

**Interfaces:**
- Consumes: `MouldGeometry.TreeFromBlock`, `MouldGeometry.MainBranch`, `MouldGeometry.ColumnTree` (existing).
- Produces (Task 2 depends on these exact names):
  - `public static (double Sag, double Lift, string Phase) MouldGeometry.Phases(double time, double preSag)`, both arguments 0..1 and clamped.
  - `public static Point3d[] MouldGeometry.LiveColumnNodes(MouldColumnsDto block, Point3d[] live)`, one entry per `block.Nodes` in block order.

- [ ] **Step 1: Write the failing checks**

After the `ValidateOutputGrouping` try/catch block add:

```csharp
        try
        {
            ValidatePhases(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.Phases: reel 0 to 30 brings the sag to Pre-Sag "
                + "with the net still on the ground, raise 30 to 60 lifts it, "
                + "finish 60 to 90 reels the rest, hold 90 to 100 moves nothing; "
                + "sag and lift are continuous across every boundary.");
        }
        catch (Exception exception)
        {
            failures.Add($"MouldGeometry.Phases: {DescribeException(exception)}");
        }

        try
        {
            ValidateLiveColumnNodes(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.LiveColumnNodes: with the net at its solved "
                + "shape every column node is where it was built; with the net "
                + "flat on the ground every node lies on the ground and the fork "
                + "sits at its built fraction along the rail; halfway up the fork "
                + "keeps its fraction and trunk, fork and main head stay "
                + "collinear. Heads are found by HeadNode, not by plan matching.");
        }
        catch (Exception exception)
        {
            failures.Add($"MouldGeometry.LiveColumnNodes: {DescribeException(exception)}");
        }
```

Next to `ValidateColumnsBlock` add:

```csharp
    /// <summary>
    /// <c>MouldGeometry.Phases</c>: the four phases the spine spec bound from
    /// the seven-questions state machine, with the split Param chose (30, 30,
    /// 30, 10). Measured at every boundary because a discontinuity in sag or
    /// lift is a visible jump on the timeline slider.
    /// </summary>
    private static void ValidatePhases(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo phases = RequirePublicStatic(geometry, "Phases");

        (double Sag, double Lift, string Phase) At(double time, double pre)
        {
            object result = phases.Invoke(null, new object?[] { time, pre })!;
            Type type = result.GetType();
            return (
                (double)type.GetField("Item1")!.GetValue(result)!,
                (double)type.GetField("Item2")!.GetValue(result)!,
                (string)type.GetField("Item3")!.GetValue(result)!);
        }

        void Expect(double time, string phase, double sag, double lift)
        {
            (double s, double l, string p) = At(time, 0.4);
            if (p != phase)
                throw new InvalidOperationException($"Time {time} is '{phase}', got '{p}'.");
            if (Math.Abs(s - sag) > 1.0e-9 || Math.Abs(l - lift) > 1.0e-9)
                throw new InvalidOperationException($"Time {time} ({phase}) should give sag {sag}, lift {lift}; got sag {s:0.####}, lift {l:0.####}.");
        }

        Expect(0.0, "reel", 0.0, 0.0);
        Expect(0.15, "reel", 0.2, 0.0);
        Expect(0.3, "raise", 0.4, 0.0);
        Expect(0.45, "raise", 0.4, 0.5);
        Expect(0.6, "finish", 0.4, 1.0);
        Expect(0.75, "finish", 0.7, 1.0);
        Expect(0.9, "hold", 1.0, 1.0);
        Expect(1.0, "hold", 1.0, 1.0);

        // Continuity: just below each boundary matches the boundary.
        foreach (double boundary in new[] { 0.3, 0.6, 0.9 })
        {
            (double sBelow, double lBelow, _) = At(boundary - 1.0e-9, 0.4);
            (double sAt, double lAt, _) = At(boundary, 0.4);
            if (Math.Abs(sBelow - sAt) > 1.0e-6 || Math.Abs(lBelow - lAt) > 1.0e-6)
                throw new InvalidOperationException($"Sag or lift jumps at time {boundary}: {sBelow:0.######}/{lBelow:0.######} below, {sAt:0.######}/{lAt:0.######} at.");
        }
        // Out-of-range inputs clamp rather than throw.
        (double sOver, double lOver, string pOver) = At(1.5, 2.0);
        if (pOver != "hold" || Math.Abs(sOver - 1.0) > 1.0e-9 || Math.Abs(lOver - 1.0) > 1.0e-9)
            throw new InvalidOperationException("Time past 1 and Pre-Sag past 1 clamp to hold at full sag and lift.");
    }

    /// <summary>
    /// <c>MouldGeometry.LiveColumnNodes</c>: the rigid rotation. A tree's foot
    /// is where the block put it, its heads are on the live net by HeadNode,
    /// and its fork keeps the fraction it was built at along the live
    /// foot-to-main segment, so the whole tree turns about its foot as one
    /// body. Two trees share one foot here, and one of them forks.
    /// </summary>
    private static void ValidateLiveColumnNodes(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo liveNodes = RequirePublicStatic(geometry, "LiveColumnNodes");
        Type point3d = liveNodes.GetParameters()[1].ParameterType.GetElementType()!;
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");

        // Foot F at the origin; fork K at 0.65 of the way to main head M; a
        // branch head B off the fork; a second tree from the same foot to
        // head H. Net vertices 0, 1, 2 stand under M, B, H.
        double[][] built =
        {
            new[] { 0.0, 0.0, 0.0 },        // 0 F
            new[] { 0.65, 0.0, 1.3 },       // 1 K
            new[] { 1.0, 0.0, 2.0 },        // 2 M
            new[] { 2.0, 0.0, 1.5 },        // 3 B
            new[] { -1.0, 0.0, 2.0 },       // 4 H
        };
        Array nodes = Array.CreateInstance(point, built.Length);
        for (int i = 0; i < built.Length; i++)
            nodes.SetValue(Activator.CreateInstance(point, built[i][0], built[i][1], built[i][2]), i);
        Array members = Array.CreateInstance(edge, 4);
        members.SetValue(Activator.CreateInstance(edge, 0, 1), 0);
        members.SetValue(Activator.CreateInstance(edge, 1, 2), 1);
        members.SetValue(Activator.CreateInstance(edge, 1, 3), 2);
        members.SetValue(Activator.CreateInstance(edge, 0, 4), 3);
        object block = CreateInstance(columnsType);
        SetContractProperty(block, columnsType, "Nodes", nodes);
        SetContractProperty(block, columnsType, "Members", members);
        SetContractProperty(block, columnsType, "MemberForce", new[] { 3.0, 1.0, 1.0, 1.0 });
        SetContractProperty(block, columnsType, "Trees", new int[][] { new[] { 0, 1, 2, 3 } });
        SetContractProperty(block, columnsType, "Heads", new[] { 2, 3, 4 });
        SetContractProperty(block, columnsType, "Forks", new[] { 1 });
        SetContractProperty(block, columnsType, "Feet", new[] { 0 });
        SetContractProperty(block, columnsType, "HeadNode", new[] { 0, 1, 2 });

        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        double X(object p) => (double)point3d.GetProperty("X")!.GetValue(p)!;
        double Y(object p) => (double)point3d.GetProperty("Y")!.GetValue(p)!;
        double Z(object p) => (double)point3d.GetProperty("Z")!.GetValue(p)!;
        object[] Run(params object[] live)
        {
            Array array = Array.CreateInstance(point3d, live.Length);
            for (int i = 0; i < live.Length; i++)
                array.SetValue(live[i], i);
            return ((Array)liveNodes.Invoke(null, new object?[] { block, array })!).Cast<object>().ToArray();
        }
        void Near(object got, double x, double y, double z, string what)
        {
            if (Math.Abs(X(got) - x) > 1.0e-9 || Math.Abs(Y(got) - y) > 1.0e-9 || Math.Abs(Z(got) - z) > 1.0e-9)
                throw new InvalidOperationException($"{what} should be ({x}, {y}, {z}); got ({X(got):0.####}, {Y(got):0.####}, {Z(got):0.####}).");
        }

        // The solved net: every node where it was built.
        object[] final = Run(P(1.0, 0.0, 2.0), P(2.0, 0.0, 1.5), P(-1.0, 0.0, 2.0));
        if (final.Length != 5)
            throw new InvalidOperationException($"One position per block node; got {final.Length}.");
        for (int i = 0; i < built.Length; i++)
            Near(final[i], built[i][0], built[i][1], built[i][2], $"node {i} at the solved net");

        // Time zero: the net on the ground under its own plan. Every node on
        // the ground, the foot unmoved, the fork at its fraction along the
        // rail from the foot to the main head.
        object[] flat = Run(P(1.0, 0.0, 0.0), P(2.0, 0.0, 0.0), P(-1.0, 0.0, 0.0));
        Near(flat[0], 0.0, 0.0, 0.0, "the foot at time zero");
        Near(flat[2], 1.0, 0.0, 0.0, "the main head at time zero");
        Near(flat[3], 2.0, 0.0, 0.0, "the branch head at time zero");
        Near(flat[4], -1.0, 0.0, 0.0, "the second tree's head at time zero");
        Near(flat[1], 0.65, 0.0, 0.0, "the fork at time zero, on the rail at its built fraction");

        // Halfway: the fork keeps its fraction and stays on the line.
        object[] mid = Run(P(1.0, 0.0, 1.0), P(2.0, 0.0, 0.75), P(-1.0, 0.0, 1.0));
        Near(mid[1], 0.65, 0.0, 0.65, "the fork halfway up");
        double angle = AngleDeg(
            X(mid[1]) - X(mid[0]), Y(mid[1]) - Y(mid[0]), Z(mid[1]) - Z(mid[0]),
            X(mid[2]) - X(mid[1]), Y(mid[2]) - Y(mid[1]), Z(mid[2]) - Z(mid[1]));
        if (angle > 0.5)
            throw new InvalidOperationException($"Trunk, fork and main head must stay collinear; they kink by {angle:0.###} degrees halfway up.");
    }
```

`RequirePublicStatic`, `RequireContractType`, `CreateInstance`, `SetContractProperty` and `AngleDeg` all exist in the harness already (the last from sub-project 3).

- [ ] **Step 2: Run the gate to see both fail**

Expected: `MouldGeometry.Phases: ... Phases ... missing` and `MouldGeometry.LiveColumnNodes: ... LiveColumnNodes ... missing` (the exact wording is `RequirePublicStatic`'s).

- [ ] **Step 3: Add the two methods**

Directly after `MainBranch` in `MouldGeometry` add:

```csharp
        /// <summary>
        /// The four phases of the build on one Time slider, from the
        /// seven-questions state machine as the spine spec bound it: reel the
        /// net part way in while it is flat (0 to 30), raise it on the columns
        /// (30 to 60), reel the rest and tension both axes (60 to 90), then
        /// hold while load arrives (90 to 100). Sag and lift are continuous
        /// across every boundary so the slider never jumps.
        /// </summary>
        public static (double Sag, double Lift, string Phase) Phases(
            double time, double preSag)
        {
            time = Math.Min(Math.Max(time, 0.0), 1.0);
            double pre = Math.Min(Math.Max(preSag, 0.0), 1.0);
            if (time < 0.3)
                return (pre * (time / 0.3), 0.0, "reel");
            if (time < 0.6)
                return (pre, (time - 0.3) / 0.3, "raise");
            if (time < 0.9)
                return (pre + ((1.0 - pre) * ((time - 0.6) / 0.3)), 1.0, "finish");
            return (1.0, 1.0, "hold");
        }

        /// <summary>
        /// Every column node's position for one frame of the net.
        ///
        /// The tree turns about its foot as ONE BODY. The foot is fixed where
        /// the block put it, from frame zero. Each head is on the live net at
        /// the vertex HeadNode names for it, never found by matching plan
        /// coordinates. Each fork sits on the segment from its foot to its
        /// main head's live position at the fraction it was built at, the
        /// main head being the branch collinear with the trunk, which is the
        /// invariant Columns creates by putting the fork on that segment. So
        /// at time zero a trunk lies flat along the rail from its foot to its
        /// notch's drawn position, and rises with the notch, its length being
        /// what the ram delivers.
        ///
        /// A node nothing resolves (a head with no HeadNode, a fragment with
        /// no foot) keeps its built position rather than vanishing.
        /// </summary>
        public static Point3d[] LiveColumnNodes(
            MouldColumnsDto block, Point3d[] live)
        {
            ColumnTree tree = TreeFromBlock(block);
            int count = tree.Nodes.Count;
            var at = new Point3d[count];
            var known = new bool[count];

            foreach (int foot in tree.Feet)
            {
                at[foot] = tree.Nodes[foot];
                known[foot] = true;
            }
            for (int h = 0; h < block.Heads.Count && h < block.HeadNode.Count; h++)
            {
                int node = block.Heads[h];
                int vertex = block.HeadNode[h];
                if (node < 0 || node >= count || vertex < 0 || vertex >= live.Length)
                    continue;
                at[node] = live[vertex];
                known[node] = true;
            }

            // Forks, once their foot below and main head above are placed.
            for (int pass = 0; pass < count + 2; pass++)
            {
                bool moved = false;
                for (int v = 0; v < count; v++)
                {
                    if (known[v] || tree.Above[v].Count == 0)
                        continue;
                    int lower = -1;
                    foreach ((int lo, int up) in tree.Members)
                    {
                        if (up == v)
                        {
                            lower = lo;
                            break;
                        }
                    }
                    if (lower < 0 || !known[lower])
                        continue;
                    int main = MainBranch(tree, v);
                    if (!known[main])
                        continue;
                    double span = tree.Nodes[lower].DistanceTo(tree.Nodes[main]);
                    double fraction = span > 1.0e-12
                        ? tree.Nodes[lower].DistanceTo(tree.Nodes[v]) / span
                        : 1.0;
                    fraction = Math.Min(Math.Max(fraction, 0.0), 1.0);
                    at[v] = at[lower] + ((at[main] - at[lower]) * fraction);
                    known[v] = true;
                    moved = true;
                }
                if (!moved)
                    break;
            }

            for (int v = 0; v < count; v++)
            {
                if (!known[v])
                    at[v] = tree.Nodes[v];
            }
            return at;
        }
```

- [ ] **Step 4: Run the gate to see both pass, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/MouldComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(mould): Phases and LiveColumnNodes, the four-phase timeline and the rigid tree about a fixed foot, measured"
```

---

### Task 2: Animate rewired

**Files:**
- Modify: `plugin/native_v02/Components/MouldComponents.cs`: the Animate component (class doc comment about lines 85 to 117; `RegisterInputParams` Extension description about line 238; `RegisterOutputParams` about lines 254 to 330; the phase block about lines 469 to 494; the column block from the comment `// The columns, raised with the net, branches and all.` through the `animate.below_ground` entry, about lines 660 to 880; the outputs at the end of `SolveInstance`), and `MouldGeometry` (delete `ForkOnLine` and `FootOnRail`; fix the `MainBranch` doc comment's `<see cref="ForkOnLine"/>`).

Line numbers are as the file stands after Task 1; locate by content.

**Interfaces:**
- Consumes: `MouldGeometry.Phases`, `MouldGeometry.LiveColumnNodes` (Task 1); `MouldGeometry.TreeFromBlock`, `TreesByFoot`, `MainBranch`, `AimFrom`, `BarLoads`, `BarTransverse`, `OutputTree.Curves` (existing).
- Produces: nothing downstream.

- [ ] **Step 1: The phase block**

Replace the `if (time < 1.0 / 3.0) { ... } else if ... else { ... }` block that assigns `sag`, `lift` and `phase` with:

```csharp
                (double sag, double lift, string phaseWord) =
                    MouldGeometry.Phases(time, pre);
                string phase = phaseWord;
                string phaseDetail = phaseWord switch
                {
                    "reel" => $"reel: reeling flat on the ground, {sag * 100:0}% "
                        + $"of the final sag, heading for {pre * 100:0}%",
                    "raise" => $"raise: columns rotating up about their feet, "
                        + $"{lift * 100:0}% of the height, holding {pre * 100:0}% sag",
                    "finish" => "finish: tensioning both axes against the columns, "
                        + $"{sag * 100:0}% sag",
                    _ => "hold: the mould holds its shape while load arrives",
                };
```

and delete the three `double sag; double lift; string phase;` declarations above it. In the `entries` list change the `animate.phase` entry's message from `phase` to `phaseDetail`. `Frame.Phase = phase` stays and now carries the word.

- [ ] **Step 2: The column block**

Replace everything from the comment `// The columns, raised with the net, branches and all.` down to and including the `if (belowGround > 0) { ... }` block with:

```csharp
                // The columns, from frame zero. Every tree stands on the foot
                // Columns built for it and turns about it as ONE BODY: its
                // heads ride the live net, its fork keeps its built fraction
                // along the live foot-to-main segment. At time zero a trunk
                // lies flat along the rail from its foot to its notch's drawn
                // position; as the notch rises the trunk rotates up, and its
                // length is what the ram delivers. Nothing slides and nothing
                // is re-aimed: the trunk points where its foot and its notch
                // put it, and how far that is from the force path is reported.
                double extend = Math.Min(Math.Max(extendPct, 0.0), 95.0) / 100.0;
                var liveColumns = new List<Line>();
                var columnBranches = new List<List<Line>>();
                double shortest = double.MaxValue;
                double longest = 0.0;
                int ramViolations = 0;
                double worstRatio = 1.0;
                double worstAlign = 0.0;

                Point3d[]? liveColumnNodes = null;
                if (hasColumns)
                {
                    MouldGeometry.ColumnTree tree =
                        MouldGeometry.TreeFromBlock(columnsBlock!);
                    Point3d[] at = MouldGeometry.LiveColumnNodes(columnsBlock!, live);
                    liveColumnNodes = at;
                    var footSet = new HashSet<int>(tree.Feet);
                    var headVertex = new Dictionary<int, int>();
                    for (int h = 0; h < columnsBlock!.Heads.Count && h < columnsBlock.HeadNode.Count; h++)
                        headVertex[columnsBlock.Heads[h]] = columnsBlock.HeadNode[h];

                    foreach (List<int> group in MouldGeometry.TreesByFoot(tree))
                    {
                        var branch = new List<Line>();
                        foreach (int m in group)
                        {
                            (int lower, int upper) = tree.Members[m];
                            if (at[lower].DistanceTo(at[upper]) <= 1.0e-9)
                                continue;
                            var member = new Line(at[lower], at[upper]);
                            liveColumns.Add(member);
                            branch.Add(member);
                            double length = member.Length;
                            shortest = Math.Min(shortest, length);
                            longest = Math.Max(longest, length);

                            if (!footSet.Contains(lower))
                                continue;
                            // A trunk. The ram: this frame's length against
                            // the built one, inside the range the ram allows.
                            double builtLength = tree.Nodes[lower].DistanceTo(tree.Nodes[upper]);
                            if (builtLength > 1.0e-9)
                            {
                                double ratio = length / builtLength;
                                if (ratio < (1.0 - extend) - 1.0e-9 || ratio > 1.0 + 1.0e-9)
                                {
                                    ramViolations++;
                                    if (Math.Abs(ratio - 1.0) > Math.Abs(worstRatio - 1.0))
                                        worstRatio = ratio;
                                }
                            }
                            // Alignment: the trunk against the live thrust at
                            // its main notch.
                            int head = tree.Above[upper].Count == 0
                                ? upper
                                : MouldGeometry.MainBranch(tree, upper);
                            if (headVertex.TryGetValue(head, out int vertex) &&
                                liveAim.TryGetValue(vertex, out Vector3d aim))
                            {
                                Vector3d direction = at[upper] - at[lower];
                                worstAlign = Math.Max(
                                    worstAlign, ColumnPlacement.AngleBetween(direction, aim));
                            }
                        }
                        columnBranches.Add(branch);
                    }
                }

                if (liveColumns.Count > 0)
                {
                    entries.Add(ResultDiagnostics.Entry(S, "animate.columns", "info",
                        $"{liveColumns.Count} column members at this frame, "
                            + $"{shortest:0.###} to {longest:0.###} long. Every tree "
                            + "stands on its built foot from frame zero and turns "
                            + "about it as one body; its length is the ram.",
                        liveColumns.Count, unit: "members",
                        context: ResultDiagnostics.Context(
                            ("shortest", shortest.ToString("0.###", CultureInfo.InvariantCulture)),
                            ("longest", longest.ToString("0.###", CultureInfo.InvariantCulture)))));
                    entries.Add(ResultDiagnostics.Entry(S, "animate.column_alignment", "info",
                        $"trunks stand up to {worstAlign:0.#} degrees off the live "
                            + "thrust at their notch at this frame. Nothing is "
                            + "re-aimed: a trunk points where its foot and its notch "
                            + "put it.",
                        worstAlign, unit: "degrees"));
                    if (ramViolations > 0)
                    {
                        entries.Add(ResultDiagnostics.Entry(S, "animate.ram_range", "warning",
                            $"{ramViolations} trunk(s) need a length outside their ram's "
                                + $"range at this frame, the worst at {worstRatio * 100:0}% of "
                                + $"built length against a range of {(1.0 - extend) * 100:0}% "
                                + "to 100%. Raise Extension, or accept that the machine "
                                + "cannot follow this frame exactly.",
                            worstRatio, unit: "ratio",
                            context: ResultDiagnostics.Context(
                                ("violations", ramViolations.ToString(CultureInfo.InvariantCulture)),
                                ("extension", extendPct.ToString("0", CultureInfo.InvariantCulture)))));
                    }
                }
```

`ColumnPlacement.AngleBetween` is public static (sub-project 3). `liveAim` is the per-frame dictionary already computed above this block.

- [ ] **Step 3: Perimeter Lines**

In `RegisterOutputParams`, after the `Columns` output, append:

```csharp
            parameters.AddCurveParameter(
                "Perimeter Lines",
                "PRL",
                "The boundary of the net at this frame as CLOSED polylines, a "
                    + "TREE with one branch per boundary loop, the same loop as "
                    + "branch {i} of Perimeter Nodes. A net with a hole has one "
                    + "curve for the outside and one for the hole.",
                GH_ParamAccess.tree);
```

After `perimeterLoops` is computed (the `ConnectedGroups(perimeterIds, ...)` call), add:

```csharp
                // One closed curve per loop, branch {i} the same loop as
                // Perimeter Nodes branch {i}. A loop too short to close still
                // keeps its branch so the numbering holds.
                var perimeterCurves = new List<List<Curve>>();
                foreach (List<int> loop in perimeterLoops)
                {
                    var branch = new List<Curve>();
                    if (loop.Count >= 3)
                    {
                        var points = loop.Select(i => live[i]).ToList();
                        points.Add(points[0]);
                        var polyline = new Polyline(points);
                        if (polyline.IsValid)
                            branch.Add(polyline.ToNurbsCurve());
                    }
                    perimeterCurves.Add(branch);
                }
```

and after `data.SetDataTree(7, OutputTree.Lines(columnBranches));` add `data.SetDataTree(8, OutputTree.Curves(perimeterCurves));`.

- [ ] **Step 4: Descriptions and comments**

- Extension port description: replace its text with `"How much of a column's built length its ram can drive out, in percent. The feet are fixed, so this is a CHECK, not a driver: a trunk whose length at this frame falls below built x (100 - Extension)% or above built is reported by animate.ram_range."`.
- Columns output description: replace with `"The columns at THIS frame, from frame zero: every tree on its built foot, lying flat along its rail at time zero and turning up about the foot as the net rises, its length the ram's travel. A TREE with one branch per COLUMN TREE, that is per foot, each branch holding that tree's trunk and branches together. Empty unless the Result carries columns from Columns upstream."`.
- Time port description: replace `"Phase one reels ... against the bars."` with `"Four phases: reel (0 to 30) draws the net in on the ground, raise (30 to 60) rotates the columns up and lifts the bars, finish (60 to 90) reels the rest against the bars, hold (90 to 100) keeps the shape while load arrives."`.
- The class doc comment on the Animate component: where it describes the three phases and the sliding foot, rewrite those sentences to the four phases and the fixed foot; keep the `bare`/`relief` explanation and the frame formula as they are.
- Delete `MouldGeometry.ForkOnLine` and `MouldGeometry.FootOnRail` with their doc comments. In `MainBranch`'s doc comment replace `the invariant <see cref="ForkOnLine"/> creates by putting the fork on the main column's own line` with `the invariant Columns creates by putting the fork on the segment from the foot to the main notch`.

- [ ] **Step 5: Grep, gate, commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
rg -n "ForkOnLine|FootOnRail|below_ground|column_overrun|slide_remaining|NearestNodeInPlan\(" "$repo\plugin\native_v02" "$repo\tests\native_smoke"
```

Expected: `NearestNodeInPlan(` appears only inside `MouldGeometry` itself (its definition and `ColumnsBlock`'s HeadNode use); nothing else. Then run the gate: 0 warnings, 18 components, 12 parameters, all checks green. Commit:

```powershell
git -C $repo add "plugin/native_v02/Components/MouldComponents.cs"
git -C $repo commit -m "feat(animate): columns from frame zero on fixed feet turning as one body, four phases, Perimeter Lines; the sliding foot and the aim-line fork go"
```

---

### Task 3: The taxonomy row

**Files:**
- Modify: `docs/component-taxonomy.md` line 54 (the Animate row)

- [ ] **Step 1: Replace the row**

```markdown
| `03 Visualise` | **Animate** | Result `RES`, Time `T`, Pre-Sag `PS`, Extension `E` | Mesh `M`, Cables `C`, Principal Lines `PL`, Principal Nodes `PN`, Anchor Nodes `AN`, Perimeter Nodes `PRN`, Result `RES`, Columns `C`, Perimeter Lines `PRL` | Replay the reconfigurable mould building itself from one timeline slider. Everything is read from the solved Result: relaxing the free nodes with the bars and anchors pinned gives the `bare` surface (Schek's Theorem 1 minimum-way surface, so flat or saddled and never domed) which carries the height, the remainder to the Result is the relief the steppers reel which carries the sag, the ground is the level the anchors sit at, and the surface is rebuilt from the Result's own faces. A frame is `start + lift x (bare - start) + sag x relief`, with the plan drawing in by sag. `Time` 0-100 runs four phases: reel (0-30) draws the net in on the ground to `Pre-Sag`, raise (30-60) rotates the columns up about their feet and lifts the bars, finish (60-90) reels the rest and tensions both axes, hold (90-100) keeps the shape while load arrives. Columns exist from frame zero: every tree stands on the foot **Columns** built for it, lies flat along its rail at time zero, and turns about the foot as one body as its notches rise (heads by `HeadNode`, fork at its built fraction), its length being the ram; `Extension` is the ram's range and a trunk outside it is reported, not moved. `Perimeter Lines` gives one closed curve per boundary loop, branched as Perimeter Nodes. `Result` carries the frame in the Mould block (time, phase word, live net, live column nodes); wire it to **Monitor** and **Diagnose**. Mesh is empty for FD, which has no faces. |
```

- [ ] **Step 2: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "docs/component-taxonomy.md"
git -C $repo commit -m "docs(taxonomy): the Animate row says four phases, fixed feet, the rigid tree and Perimeter Lines"
```

---

## Self-review

Spec coverage: 2.1 (Task 1 `Phases`, Task 2 phase block), 2.2 (Task 1 `LiveColumnNodes`, Task 2 column block), 2.3 (Task 2 ram range), 2.4 (Task 2 alignment), 2.5 (Task 2 Perimeter Lines), 3 (Task 2 output 8, descriptions), 4 (Task 2 diagnostics), 5 (Tasks 1, 2, 3), 6 (Task 1 checks; the Animate output list is not pinned in the harness, so nothing to extend; parameter count untouched), 7 (no code).

Type consistency: `Phases(double, double)` returning `(double Sag, double Lift, string Phase)` read as Item1/Item2/Item3 in the check and deconstructed in Task 2; `LiveColumnNodes(MouldColumnsDto, Point3d[])` returning `Point3d[]` in Task 1 and Task 2; `TreesByFoot` returns member index lists, which Task 2 indexes into `tree.Members`.
