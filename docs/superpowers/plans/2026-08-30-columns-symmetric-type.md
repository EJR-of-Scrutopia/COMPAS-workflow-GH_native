# Columns Stand Symmetric And Uniform, And Type Gathers Them: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The columns of a span come out mirrored about its midpoint and identical to every other span that holds the same notches; a shared foot never refuses a level, it peels the trunks that cannot reach it; feet merge only where a mirrored pair meets; every level is judged and none is refused; and slot 2 is Type, not Ground, in every port, message, tooltip and diagnostic.

**Architecture:** Four changes inside the existing engine `ColumnPlacement` and its component. `Symmetrise` runs once inside `Place`, after the trees are built and before any level, and rewrites `Tree.Resultant` from the mirror rule of spec 3.4 while keeping the original in `Tree.RawResultant`. `BuildLevel` decides a band per MIRROR PAIR, gains the Type N peel (`Level.Peeled`), and hands `MergeFeet` the mirror pairing so only a mirrored pair can merge, the rest being counted in `Level.FeetClose`. `Refuse` goes: `Level.Feasible` becomes `Collisions == 0`, `Level.Rule` names the worst measure, `Place` builds level N alone when N is asked and all five for Auto. `ColumnsComponent` renames slot 2 and writes the diagnostics of spec section 4. `MouldContracts` is not edited, and `GroundAsked` and `GroundPlaced` keep their wire names.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8 (managed only in tests), the Rhino-free reflection smoke harness in `tests/native_smoke`.

**Spec:** `docs/superpowers/specs/2026-08-30-columns-symmetric-type-design.md` (binding), which amends sections 2, 3.4, 3.5, 3.7 and 4 of `docs/superpowers/specs/2026-08-28-columns-two-sliders-design.md`. Everything in that spec not amended stands.

## Global Constraints

Spec section 10, verbatim:

- No em dashes anywhere.
- Full absolute Windows paths in any reply.
- No Co-Authored-By or AI attribution.
- Commit locally after every task; push only on Param's word.
- Rebuild and install as the final step with Rhino closed and tell Param to restart Rhino.
- Every measured check runs in the smoke harness without launching Rhino.
- Check for OneDrive name-clash files before every build and commit.
- git add by explicit path only.

And, binding for this plan:

- The harness command is the shared gate below. A passing gate prints `0 warnings` from the build, `Components discovered: 19`, `Parameters discovered: 12`, a `PASS` line for every check with no `FAIL`, and ends with `Native component smoke test passed; Rhino was not launched.` at exit code 0.
- Component GUID `c47a1e93-8b25-4d60-a1f7-6e29b3c05d84` never changes; slot 2 keeps its slot and its values, so a saved wire survives.
- `plugin/native_v02/Contracts/MouldContracts.cs` is NOT edited. `GroundAsked` and `GroundPlaced` keep their wire names, and so do `Placement.GroundAsked`, `Placement.GroundPlaced`, `Level.Ground` and `ColumnPlacement.MaxGround`, which are what fill them.
- `MouldGeometry.AimFrom`, `MouldGeometry.LeanFromVertical`, `MouldGeometry.BarLoads`, `MouldGeometry.BarTransverse` and the 60 degree cap are read only. Nothing in this plan changes them.
- Members leave the engine LOWER END FIRST and a fork is one node shared exactly; Animate depends on both.
- Anything that P/Invokes `rhcommon_c` (`Vector3d.Unitize`, `Curve`, `Mesh` queries) cannot run in the harness. `Point3d`, `Vector3d`, `Vector3d.ZAxis`, `Length`, `DistanceTo` and the operators are managed and fine. `ColumnPlacement.cs` must not touch `Mesh` or `Curve` at all.
- Spec section 9 (Animate, the Frame component, Deconstruct, Monitor, the RES-first port order, Export, Display, panels and icons) is OUT OF SCOPE.

---

## File structure

| Path (relative to `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`) | Responsibility |
| --- | --- |
| `plugin/native_v02/Components/ColumnPlacement.cs` (modify) | `PlumbDegrees`, `Tree.RawResultant`, `Placement.Partner/AsymmetryRemoved/Families/CentreTrees`, `Symmetrise`, the Type N peel, the one-case merge, `Level.Peeled`, `Level.FeetClose`, judged-not-refused, Auto's preference. |
| `plugin/native_v02/Components/ColumnsComponent.cs` (modify) | Slot 2 is Type `T`, the value list, every message and tooltip, the diagnostics of spec section 4. |
| `plugin/native_v02/Components/DiagnoseComponents.cs` (read only) | Verified to hold no read of `columns.ground`; nothing to rename. |
| `tests/native_smoke/Program.cs` (modify) | The six new cases of spec section 6, the two rewritten ones, the Columns pin in `SpineComponentContracts`, the `PASS` line. |
| `docs/component-taxonomy.md` (modify) | The Columns row, line 55. |

## The shared gate

Every "run the gate" step means this, from PowerShell. It refuses a OneDrive clash file first, builds the plugin, then builds and runs the harness against the freshly built `.gha`.

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests","$repo\docs" -Recurse -Filter "*Name clash*"
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve before building" }
dotnet build "$repo\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -v quiet --nologo
dotnet run --project "$repo\tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "$repo\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"
```

Expected on a passing gate: `0 warnings`, `Components discovered: 19`, `Parameters discovered: 12`, every line `PASS`, and `Native component smoke test passed; Rhino was not launched.` Commit messages follow the repo's `type(scope): sentence` style. Every `git add` names explicit paths.

---

### Task 1: The resultants are mirrored before a foot is placed

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`AlignmentDegrees` at line 43; `Tree` at lines 68 to 82; `Placement` at 113 to 123; `Place` at 205 to 297; a new `Symmetrise` between `Group` (ends 186) and the `Entry` banner at 188)
- Modify: `tests/native_smoke/Program.cs` (`ValidateColumnPlacement`, the local helpers ending at line 3316; the new cases are inserted at 3317, before the fork case at 3318)

**Interfaces:**
- Consumes: `MouldGeometry.AimFrom(Vector3d pulled) -> Vector3d`, `ColumnPlacement.AngleBetween(Vector3d a, Vector3d b) -> double` (public static, degrees), `Rhino.Geometry.Vector3d.ZAxis`.
- Produces (Tasks 2, 3 and 4 depend on these exact names):
  - `public const double PlumbDegrees = 2.0;`
  - `Tree.RawResultant` (public `Vector3d` field).
  - `Placement.Partner` (public `int[]`: the mirror partner per tree index, itself for a centre tree, `-1` for the ring tree), `Placement.AsymmetryRemoved` (public `double`, degrees), `Placement.Families` (public `int`), `Placement.CentreTrees` (public `int`).
  - `public static double Symmetrise(Placement placement, Point3d[] nodes, int[][] bars)`, called once from `Place`.

- [ ] **Step 1: Write the two failing cases**

In `tests/native_smoke/Program.cs`, insert at line 3317 (after `double Z(object p) => ...` and before the `// ---- Fork on the segment` comment) the three local helpers and the two cases:

```csharp

        // A parabolic arch whose across pulls are mirrored in SHAPE, carrying
        // the two asymmetries a solved net always has. `bend` is the mirrored
        // part (positive leans the pulls outward from the midpoint), `skew` a
        // common along-chord tilt on every notch, `flank` a scale on the left
        // half alone. Neither asymmetry survives the mirror rule of spec 3.4,
        // and both move the feet today.
        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) SkewArch(
            int count, double width, double rise, double bend, double skew, double flank)
        {
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            double middle = (count - 1) / 2.0;
            for (int i = 0; i < count; i++)
            {
                double s = (double)i / (count - 1);
                nodes.SetValue(P(width * s, 0.0, rise * 4.0 * s * (1.0 - s)), i);
                double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                double scale = i < middle ? flank : 1.0;
                acrossBar.SetValue(V(scale * ((side * bend) + skew), 0.0, -scale), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }

        (int Lower, int Upper)[] MembersOf(object level) =>
            ((IEnumerable)Get<object>(level, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!,
                    (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();

        // Which node each tree stands on: the lower end of the first member
        // of that tree that leaves a foot.
        int[] FootOfTree(object level, int treeCount)
        {
            (int Lower, int Upper)[] members = MembersOf(level);
            var feet = ((IEnumerable)Get<object>(level, "Feet")).Cast<int>().ToHashSet();
            int[] memberTree = ((IEnumerable)Get<object>(level, "MemberTree")).Cast<int>().ToArray();
            int[] byTree = Enumerable.Repeat(-1, treeCount).ToArray();
            for (int m = 0; m < members.Length; m++)
            {
                int t = memberTree[m];
                if (byTree[t] < 0 && feet.Contains(members[m].Lower))
                    byTree[t] = members[m].Lower;
            }
            return byTree;
        }

        // ---- Mirrored feet (spec 6). Eleven notches, span ten, rise 2.5:
        // the across pulls mirrored in shape and leaning outward, the LEFT
        // flank scaled by 1.1, and every notch skewed one degree along the
        // chord. Spec 3.4 mirrors the resultants about the span's midpoint
        // before a single foot is placed, so the scale and the skew both go:
        // the along-chord parts of a pair are made equal and opposite, its
        // across and down parts equal, and the centre tree stands plumb.
        {
            const double skew = 0.0174550649282176;   // tan(1 degree)
            var arch = SkewArch(11, 10.0, 2.5, bend: 0.25, skew: skew, flank: 1.1);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int m = trees.Length;
            if (m != 9)
                throw new InvalidOperationException($"Eleven notches anchored at both ends hold nine trees at Branching 1; got {m}.");
            int[] footNode = FootOfTree(built, m);
            const double midpoint = 5.0;
            for (int i = 0; i < m / 2; i++)
            {
                double left = X(nodes[footNode[i]]);
                double right = X(nodes[footNode[m - 1 - i]]);
                if (Math.Abs((left + right) - (2.0 * midpoint)) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Trees {i} and {m - 1 - i} are a mirrored pair and their feet straddle the span's midpoint: "
                        + $"{left:0.#########} and {right:0.#########} sum to {left + right:0.#########}, not {2.0 * midpoint:0.#}. "
                        + "The feet are following each tree's RAW resultant, which the along-chord skew tilts the same way on both flanks.");
                }
            }
            double centre = X(nodes[footNode[m / 2]]);
            if (Math.Abs(centre - midpoint) > 1.0e-9)
                throw new InvalidOperationException($"The centre tree stands outside the pairing and its foot is ON the midpoint; it is at {centre:0.#########}.");
            int[] memberTree = ((IEnumerable)Get<object>(built, "MemberTree")).Cast<int>().ToArray();
            (int Lower, int Upper)[] members = MembersOf(built);
            for (int k = 0; k < members.Length; k++)
            {
                if (memberTree[k] != m / 2)
                    continue;
                object a = nodes[members[k].Lower];
                object b = nodes[members[k].Upper];
                double lean = AngleDeg(
                    X(b) - X(a), Y(b) - Y(a), Z(b) - Z(a), 0.0, 0.0, 1.0);
                if (lean > 1.0e-9)
                    throw new InvalidOperationException($"The centre tree's along-chord pull is mirrored away, so its member stands vertical; it leans {lean:0.######} degrees.");
            }
            double moved = Get<double>(placed, "AsymmetryRemoved");
            if (moved <= 0.0)
                throw new InvalidOperationException($"Symmetrise reports the largest angle it moved an aim through, and on an arch this lopsided that is more than nothing; it reported {moved:0.######}.");
        }

        // ---- One family (spec 6). The same arch three times, offset in Y by
        // 0, 1 and 2, the second's pulls scaled by 1.05, the third traced
        // BACKWARDS. A family is every span with the same free-notch count
        // (Branching is one slider, so the tree count and layout follow);
        // each span is read in the frame of the family's first span, a span
        // whose chord points the other way being read reversed, and each
        // takes the family's mean. Every principal line of a family therefore
        // carries the same columns in its own frame.
        {
            const double skew = 0.0174550649282176;
            const int count = 11;
            Array nodes = Array.CreateInstance(point3d, 3 * count);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 3);
            var bars = new int[3][];
            var anchors = new List<int>();
            double middle = (count - 1) / 2.0;
            for (int b = 0; b < 3; b++)
            {
                Array acrossBar = Array.CreateInstance(vector3d, count);
                var bar = new int[count];
                for (int i = 0; i < count; i++)
                {
                    double s = (double)i / (count - 1);
                    int node = (b * count) + i;
                    nodes.SetValue(P(10.0 * s, b, 2.5 * 4.0 * s * (1.0 - s)), node);
                    double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                    double flank = i < middle ? 1.1 : 1.0;
                    double scale = flank * (b == 1 ? 1.05 : 1.0);
                    // Bar 2 is traced from its far end: bar position k holds
                    // the node at count-1-k, and the pull at that POSITION is
                    // the pull that node carries.
                    int position = b == 2 ? count - 1 - i : i;
                    bar[position] = node;
                    acrossBar.SetValue(V(scale * ((side * 0.25) + skew), 0.0, -scale), position);
                }
                bars[b] = bar;
                across.SetValue(acrossBar, b);
                anchors.Add(b * count);
                anchors.Add((b * count) + count - 1);
            }
            var family = (nodes, bars, anchors.ToArray(), across, Array.Empty<(int, int)>());
            object placed = Run(family, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 3)
                throw new InvalidOperationException($"Three bars anchored at both ends give three spans; got {spans.Length}.");
            int[] footNode = FootOfTree(built, trees.Length);
            var offsets = new List<(double Along, double Across)>[spans.Length];
            for (int s = 0; s < spans.Length; s++)
            {
                object span = spans[s];
                int[] bar = bars[Get<int>(span, "Bar")];
                object first = nodes.GetValue(bar[Get<int>(span, "First")])!;
                object last = nodes.GetValue(bar[Get<int>(span, "Last")])!;
                double cx = X(last) - X(first);
                double cy = Y(last) - Y(first);
                double length = Math.Sqrt((cx * cx) + (cy * cy));
                cx /= length;
                cy /= length;
                double midX = 0.5 * (X(first) + X(last));
                double midY = 0.5 * (Y(first) + Y(last));
                offsets[s] = new List<(double Along, double Across)>();
                for (int t = 0; t < trees.Length; t++)
                {
                    if (Get<int>(trees[t], "Span") != s)
                        continue;
                    object foot = levelNodes[footNode[t]];
                    double dx = X(foot) - midX;
                    double dy = Y(foot) - midY;
                    offsets[s].Add(((dx * cx) + (dy * cy), (dx * -cy) + (dy * cx)));
                }
            }
            for (int s = 1; s < spans.Length; s++)
            {
                if (offsets[s].Count != offsets[0].Count)
                    throw new InvalidOperationException($"Every span of a family holds the same trees; span {s} holds {offsets[s].Count} against {offsets[0].Count}.");
                for (int i = 0; i < offsets[0].Count; i++)
                {
                    if (Math.Abs(offsets[s][i].Along - offsets[0][i].Along) > 1.0e-9 ||
                        Math.Abs(offsets[s][i].Across - offsets[0][i].Across) > 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"Foot {i} of span {s}, read in its OWN frame, stands where foot {i} of the family's first span stands: "
                            + $"({offsets[s][i].Along:0.#########}, {offsets[s][i].Across:0.#########}) against ({offsets[0][i].Along:0.#########}, {offsets[0][i].Across:0.#########}). "
                            + "A span traced backwards is being read in the world's frame, not the family's.");
                    }
                }
            }
        }
```

- [ ] **Step 2: Run the gate and name the failure**

Run the gate. Expected: the build is clean and the harness reports

`FAIL  ColumnPlacement: Trees 0 and 8 are a mirrored pair and their feet straddle the span's midpoint: 0.790750000 and 9.240750000 sum to 10.031500000, not 10. ...`

because today every tree aims from its OWN raw resultant: the one degree along-chord skew tilts the left flank's aim and the right flank's aim the same way in the world, so both feet slide the same way and a mirrored pair no longer straddles the midpoint. The one-family case fails next, for the same reason read across bars: the third bar is traced backwards, so the same physical skew reads with the opposite sign in its own frame and its feet land 2 x tan(1 degree) x notch height away from the first bar's.

- [ ] **Step 3: Write `Symmetrise`**

In `plugin/native_v02/Components/ColumnPlacement.cs`, after the `AlignmentDegrees` constant (line 43) and before `ClearanceFraction`, add:

```csharp
        /// <summary>
        /// How close to vertical an aim has to be to BE vertical. A degree of
        /// residual lean out of a solved net is noise, not a thrust line, and
        /// a column that follows it stands crooked for no reason.
        /// </summary>
        public const double PlumbDegrees = 2.0;
```

In `Tree` (line 68), after `public Vector3d Resultant;` and its comment, add:

```csharp
            /// <summary>
            /// The resultant as the net handed it over, before the mirror
            /// rule of spec 3.4. The diagnostics measure how far the
            /// symmetrised aim moved from this one.
            /// </summary>
            public Vector3d RawResultant;
```

In `Placement` (line 113), after `public double Clearance;`, add:

```csharp
            /// <summary>
            /// The mirror partner of each tree: the tree it pairs with about
            /// its span's midpoint, ITSELF for the centre tree of an odd
            /// count, -1 for the ring tree, which has no partner.
            /// </summary>
            public int[] Partner = Array.Empty<int>();
            /// <summary>The largest angle Symmetrise moved an aim through, in degrees.</summary>
            public double AsymmetryRemoved;
            /// <summary>How many families the spans fell into.</summary>
            public int Families;
            /// <summary>Trees that are their own mirror partner.</summary>
            public int CentreTrees;
```

Between `Group` (which ends at line 186) and the `// Entry` banner (line 188), add the method:

```csharp
        // ------------------------------------------------------------------
        // Symmetry

        /// <summary>
        /// Mirror every span's resultants about its own midpoint, share them
        /// across every span that holds the same notches, and report the
        /// largest angle an aim moved through.
        ///
        /// The GROUPING of spec 3.3 was already mirrored about the span's
        /// midpoint; the FEET were not, because each tree aimed from its own
        /// resultant and a solved net's forces are never mirrored to the last
        /// digit and differ from bar to bar. That is what came back off
        /// Param's review arch as columns that did not match across a span, a
        /// centre column leaning, and neighbouring principal lines
        /// disagreeing with one another.
        ///
        /// So each resultant is read in its span's frame as (along, across,
        /// down): along the chord from the span's first node to its last,
        /// across it in plan, and down. Tree i and tree m-1-i are a mirrored
        /// pair, so their along parts are made equal and opposite and their
        /// across and down parts equal; the centre tree of an odd count is
        /// its own partner and its along part is zero. Then every span with
        /// the same free-notch count (a FAMILY, since Branching is one
        /// slider) is read in the frame of the family's first span, a span
        /// whose chord points against that one being read REVERSED with its
        /// index mirrored and its along and across parts negated, and each
        /// takes the family's mean. An aim within PlumbDegrees of vertical is
        /// vertical.
        ///
        /// Tree.Load is deliberately NOT averaged. The forces a tree reports
        /// are its own; only WHERE IT STANDS is shared.
        /// </summary>
        public static double Symmetrise(Placement placement, Point3d[] nodes, int[][] bars)
        {
            List<Tree> trees = placement.Trees;
            int count = trees.Count;
            placement.Partner = new int[count];
            for (int t = 0; t < count; t++)
            {
                placement.Partner[t] = -1;
                trees[t].RawResultant = trees[t].Resultant;
            }
            placement.Families = 0;
            placement.CentreTrees = 0;
            if (count == 0)
                return 0.0;

            // Span frames, and each span's trees in grouping order: they are
            // added to Trees span by span, group by group, so insertion order
            // IS grouping order.
            int spanCount = placement.Spans.Count;
            var chord = new Vector3d[spanCount];
            var normal = new Vector3d[spanCount];
            var order = new List<int>[spanCount];
            for (int s = 0; s < spanCount; s++)
            {
                Span span = placement.Spans[s];
                int[] bar = bars[span.Bar];
                Point3d first = nodes[bar[span.First]];
                Point3d last = nodes[bar[span.Last]];
                double dx = last.X - first.X;
                double dy = last.Y - first.Y;
                double length = Math.Sqrt((dx * dx) + (dy * dy));
                if (length <= 1.0e-12)
                {
                    dx = 1.0;
                    dy = 0.0;
                    length = 1.0;
                }
                chord[s] = new Vector3d(dx / length, dy / length, 0.0);
                normal[s] = new Vector3d(-chord[s].Y, chord[s].X, 0.0);
                order[s] = new List<int>();
            }
            for (int t = 0; t < count; t++)
            {
                Tree tree = trees[t];
                if (tree.Ring || tree.Span < 0 || tree.Span >= spanCount)
                    continue;
                order[tree.Span].Add(t);
            }

            var along = new double[count];
            var across = new double[count];
            var down = new double[count];
            for (int t = 0; t < count; t++)
            {
                Tree tree = trees[t];
                if (tree.Ring || tree.Span < 0 || tree.Span >= spanCount)
                    continue;
                int s = tree.Span;
                Vector3d r = tree.Resultant;
                along[t] = (r.X * chord[s].X) + (r.Y * chord[s].Y);
                across[t] = (r.X * normal[s].X) + (r.Y * normal[s].Y);
                down[t] = r.Z;
            }

            // Mirror pairs, per span.
            for (int s = 0; s < spanCount; s++)
            {
                List<int> ids = order[s];
                int m = ids.Count;
                for (int i = 0; i < m - 1 - i; i++)
                {
                    int low = ids[i];
                    int high = ids[m - 1 - i];
                    placement.Partner[low] = high;
                    placement.Partner[high] = low;
                    double half = 0.5 * (along[low] - along[high]);
                    along[low] = half;
                    along[high] = -half;
                    double side = 0.5 * (across[low] + across[high]);
                    across[low] = side;
                    across[high] = side;
                    double weight = 0.5 * (down[low] + down[high]);
                    down[low] = weight;
                    down[high] = weight;
                }
                if ((m % 2) == 1)
                {
                    int centre = ids[m / 2];
                    placement.Partner[centre] = centre;
                    along[centre] = 0.0;
                    placement.CentreTrees++;
                }
            }

            // Families: the spans that hold the same free notches, hence the
            // same trees in the same layout at this Branching.
            var families = new Dictionary<int, List<int>>();
            for (int s = 0; s < spanCount; s++)
            {
                if (order[s].Count == 0)
                    continue;
                int notches = order[s].Sum(t => trees[t].Nodes.Length);
                if (!families.TryGetValue(notches, out List<int>? list))
                {
                    list = new List<int>();
                    families[notches] = list;
                }
                list.Add(s);
            }
            placement.Families = families.Count;
            foreach (List<int> family in families.Values)
            {
                int lead = family[0];
                int m = order[lead].Count;
                if (family.Any(s => order[s].Count != m))
                    continue;
                var reversed = new bool[family.Count];
                var meanAlong = new double[m];
                var meanAcross = new double[m];
                var meanDown = new double[m];
                for (int k = 0; k < family.Count; k++)
                {
                    int s = family[k];
                    reversed[k] =
                        ((chord[s].X * chord[lead].X) + (chord[s].Y * chord[lead].Y)) < 0.0;
                    for (int i = 0; i < m; i++)
                    {
                        int t = order[s][i];
                        int index = reversed[k] ? m - 1 - i : i;
                        double sign = reversed[k] ? -1.0 : 1.0;
                        meanAlong[index] += sign * along[t];
                        meanAcross[index] += sign * across[t];
                        meanDown[index] += down[t];
                    }
                }
                for (int i = 0; i < m; i++)
                {
                    meanAlong[i] /= family.Count;
                    meanAcross[i] /= family.Count;
                    meanDown[i] /= family.Count;
                }
                for (int k = 0; k < family.Count; k++)
                {
                    int s = family[k];
                    for (int i = 0; i < m; i++)
                    {
                        int t = order[s][i];
                        int index = reversed[k] ? m - 1 - i : i;
                        double sign = reversed[k] ? -1.0 : 1.0;
                        along[t] = sign * meanAlong[index];
                        across[t] = sign * meanAcross[index];
                        down[t] = meanDown[index];
                    }
                }
            }

            // Back into each span's own frame, with the dead band, and the
            // angle every aim moved through.
            double moved = 0.0;
            for (int t = 0; t < count; t++)
            {
                Tree tree = trees[t];
                if (tree.Ring || tree.Span < 0 || tree.Span >= spanCount)
                    continue;
                int s = tree.Span;
                var rebuilt = new Vector3d(
                    (along[t] * chord[s].X) + (across[t] * normal[s].X),
                    (along[t] * chord[s].Y) + (across[t] * normal[s].Y),
                    down[t]);
                if (AngleBetween(MouldGeometry.AimFrom(rebuilt), Vector3d.ZAxis) <= PlumbDegrees)
                    rebuilt = new Vector3d(0.0, 0.0, down[t]);
                tree.Resultant = rebuilt;
                moved = Math.Max(moved, AngleBetween(
                    MouldGeometry.AimFrom(tree.RawResultant),
                    MouldGeometry.AimFrom(tree.Resultant)));
            }
            return moved;
        }
```

In `Place`, immediately after the `foreach (Span span in placement.Spans)` loop closes (line 262, the `}` before `if (groundAsked >= 0)`), add:

```csharp

            // Spec 3.4: the resultants are mirrored about each span's
            // midpoint and shared across each family BEFORE a single foot is
            // placed. The ring tree keeps its own; it has no mirror partner
            // and no family, and its foot is fixed by 3.2 anyway.
            placement.AsymmetryRemoved = Symmetrise(placement, nodes, bars);
```

- [ ] **Step 4: Run the gate green**

Run the gate. Expected: `0 warnings`, `Components discovered: 19`, `Parameters discovered: 12`, `PASS  ColumnPlacement`, exit 0. The nine older cases in `ValidateColumnPlacement` are untouched by this task: every one of them pulls its notches straight down, so `along` and `across` are already zero and the mirror rule returns the same vectors it was given.

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): mirror every span's resultants about its midpoint and share them across each family"
```

---

### Task 2: The feet, peeled and merged in one case only

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`Level` at lines 85 to 111; the foot section of `BuildLevel` at 490 to 569; `MergeFeet` at 749 to 808)
- Modify: `tests/native_smoke/Program.cs` (three new cases inserted after the Task 1 cases; the wide-arch case at lines 3406 to 3420 rewritten in place)

**Interfaces:**
- Consumes: `Placement.Partner` (Task 1, which decides both the band pairing and the merge pairing), `MouldGeometry.LeanFromVertical(Point3d foot, Point3d top) -> double`, `MouldGeometry.MaxLeanDegrees` (60.0), `MouldGeometry.PlanDistanceSquared(Point3d a, Point3d b) -> double`.
- Produces: `Level.Peeled` (public `int`), `Level.FeetClose` (public `int`), and two new private statics:
  `static int BandIndex(Point3d[] nodes, Placement placement, int[][] bars, Tree tree, int level)` and
  `static int[] MergeFeet(Placement placement, Point3d[] foot, Point3d[] nodes, int[][] bars, double clearance, List<Point3d> levelNodes, out int merged, out int close)`.

- [ ] **Step 1: Write the four failing cases and rewrite the refused one**

In `tests/native_smoke/Program.cs`, add these four cases after the one-family case of Task 1:

```csharp

        // ---- Type 1 is PLACED, not refused (spec 3.5 and 3.7). The wide
        // arch, rise 2.5 on a span of ten: the flank trunks to a single
        // central foot would lean 77 and 62 degrees, past the 60 degree cap,
        // so those four trees step off onto their own feet and the level
        // stands. It used to be refused whole and fall back to Type 0, which
        // is what made the slider look dead.
        {
            var wide = Arch(11, 10.0, 2.5, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 1);
            if (Get<int>(placed, "GroundAsked") != 1 || Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"Type 1 asked is Type 1 placed; asked {Get<int>(placed, "GroundAsked")}, placed {Get<int>(placed, "GroundPlaced")}.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            if (tried.Length != 1)
                throw new InvalidOperationException($"Type N asked builds level N alone; {tried.Length} levels were built.");
            if (tried.Any(t => Get<string>(t, "Rule") == "lean"))
                throw new InvalidOperationException("No level can name lean any more: the peel holds every trunk inside the cap.");
            object built = Get<object>(placed, "Built");
            if (Get<int>(built, "Peeled") != 4)
                throw new InvalidOperationException($"The two trunks on each flank lean 77 and 62 degrees to the central foot and peel; {Get<int>(built, "Peeled")} peeled.");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 5)
                throw new InvalidOperationException($"One band foot and four peeled feet is five; {feet.Length} built.");
            foreach ((int lower, int upper) in MembersOf(built))
            {
                if (!feet.Contains(lower))
                    continue;
                double lean = AngleDeg(
                    X(nodes[upper]) - X(nodes[lower]), Y(nodes[upper]) - Y(nodes[lower]), Z(nodes[upper]) - Z(nodes[lower]),
                    0.0, 0.0, 1.0);
                if (lean > maxLean + 1.0e-9)
                    throw new InvalidOperationException($"Every trunk stands inside the {maxLean:0} degree cap once the peel has run; one leans {lean:0.###}.");
            }
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int[] footNode = FootOfTree(built, trees.Length);
            int shared = footNode[4];
            if (Math.Abs(X(nodes[shared]) - 5.0) > 1.0e-9)
                throw new InvalidOperationException($"The band's foot stands on the plan centre of the main notches it carries, x = 5; it is at {X(nodes[shared]):0.#########}.");
            for (int t = 2; t <= 6; t++)
            {
                if (footNode[t] != shared)
                    throw new InvalidOperationException($"The five centre trees share the band foot; tree {t} stands on node {footNode[t]} against {shared}.");
            }
        }

        // ---- Type 2 on the same wide arch (spec 3.5, amended): the band is
        // decided PER MIRROR PAIR, so a pair lands in mirrored bands wherever
        // the boundaries fall. The centre notch of a uniform arch projects
        // EXACTLY onto the mirror plane, which at an even Type is a band
        // boundary: reading its own projection put it in the upper band, so
        // the two bands held four trees and five and their feet came out at
        // 2.5 and 7, unmirrored on a symmetric arch. It has no central band
        // to take, so it stands on its own Type 0 foot, which is on the
        // midpoint, and the two bands come out at 2.5 and 7.5.
        {
            var wide = Arch(11, 10.0, 2.5, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 2);
            if (Get<int>(placed, "GroundPlaced") != 2)
                throw new InvalidOperationException($"Type 2 asked is Type 2 placed; it placed {Get<int>(placed, "GroundPlaced")}.");
            object built = Get<object>(placed, "Built");
            if (Get<int>(built, "Peeled") != 0)
                throw new InvalidOperationException($"Every trunk reaches its band foot here, the outermost leaning 59 degrees; {Get<int>(built, "Peeled")} peeled, so a band foot is in the wrong place.");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int m = trees.Length;
            int[] footNode = FootOfTree(built, m);
            for (int i = 0; i < m / 2; i++)
            {
                double left = X(nodes[footNode[i]]);
                double right = X(nodes[footNode[m - 1 - i]]);
                if (Math.Abs((left + right) - 10.0) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Trees {i} and {m - 1 - i} are a mirrored pair, so their BANDS are mirrored and their feet straddle the midpoint: "
                        + $"{left:0.#########} and {right:0.#########} sum to {left + right:0.#########}, not 10. "
                        + "A band read from each tree's own projection puts the centre notch, which sits exactly on the boundary, in the upper band.");
                }
            }
            double centre = X(nodes[footNode[m / 2]]);
            if (Math.Abs(centre - 5.0) > 1.0e-9)
                throw new InvalidOperationException($"At an EVEN Type the centre tree has no central band and stands on its own foot, on the midpoint; it stands at {centre:0.#########}.");
            if (footNode[m / 2] == footNode[0] || footNode[m / 2] == footNode[m - 1])
                throw new InvalidOperationException("At an even Type the centre tree stands on its OWN foot, not on either band's.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 3)
                throw new InvalidOperationException($"Two band feet at 2.5 and 7.5 and the centre tree's own at 5 is three; {feet.Length} built.");
        }

        // ---- Neighbours stay apart (spec 3.5). A narrow bay, span four,
        // seven notches, the across pulls leaning INWARD hard enough that the
        // two feet either side of the centre land a fortieth of a unit from
        // it, inside a clearance of a thirtieth. Neither is a mirrored pair
        // with it, so nothing merges: five trees keep five feet and the close
        // pairs are counted instead. Welding them is what turned leaning
        // neighbours into accidental V's and X's on the review arch.
        {
            var bay = SkewArch(7, 4.0, 2.5, bend: -0.28875, skew: 0.0, flank: 1.0);
            object placed = Run(bay, Array.Empty<int[]>(), 2.0 / 3.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (trees.Length != 5)
                throw new InvalidOperationException($"Seven notches anchored at both ends hold five trees at Branching 1; got {trees.Length}.");
            if (feet.Length != trees.Length)
                throw new InvalidOperationException($"No two of these feet are a mirrored pair inside the clearance, so every tree keeps its own foot; {feet.Length} feet under {trees.Length} trees.");
            if (Get<int>(built, "FeetMerged") != 0)
                throw new InvalidOperationException($"Nothing merges here; {Get<int>(built, "FeetMerged")} merges reported.");
            if (Get<int>(built, "FeetClose") < 1)
                throw new InvalidOperationException("Feet that stand within the clearance and stay two are counted, so the author can raise Type or space the lines; none was.");
        }

        // ---- The centre pair merges (spec 3.5). Ten notches, an even count,
        // so there is no centre tree and the two innermost trees ARE a
        // mirrored pair; their inward-leaning feet fall a thirtieth apart,
        // inside the clearance, and they stand on ONE foot at the span's
        // chord midpoint. Node 4 is nudged two hundredths off the mirror so
        // that the pair's own plan centre (4.49) is not the midpoint (4.5):
        // welding a pair wherever its feet happen to meet is what the old
        // rule did, and on a solved net that is never quite the middle.
        {
            var arch = SkewArch(10, 9.0, 2.5, bend: -0.2, skew: 0.0, flank: 1.0);
            object node4 = arch.Nodes.GetValue(4)!;
            arch.Nodes.SetValue(P(3.98, 0.0, Z(node4)), 4);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            if (trees.Length != 8)
                throw new InvalidOperationException($"Ten notches anchored at both ends hold eight trees at Branching 1; got {trees.Length}.");
            if (Get<int>(built, "FeetMerged") != 1)
                throw new InvalidOperationException($"Exactly one mirrored pair lies inside the clearance here; {Get<int>(built, "FeetMerged")} merges reported.");
            int[] footNode = FootOfTree(built, trees.Length);
            if (footNode[3] != footNode[4])
                throw new InvalidOperationException("The innermost mirrored pair stands on ONE foot.");
            if (Math.Abs(X(nodes[footNode[3]]) - 4.5) > 1.0e-9)
                throw new InvalidOperationException($"A merged pair stands on its span's chord midpoint, x = 4.5, not on wherever its two feet happened to meet; it stands at {X(nodes[footNode[3]]):0.#########}.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 7)
                throw new InvalidOperationException($"Eight trees on seven feet once the pair has merged; {feet.Length} built.");
        }
```

Then replace the whole `// ---- The wide arch refuses one central foot.` case (lines 3406 to 3420) with:

```csharp
        // ---- The shallow arch twelve wide, which USED to refuse Type 1 on
        // lean and fall back to Type 0. Three trunks on each flank pass the
        // cap to a foot at the span's centre and peel onto their own feet;
        // the level itself stands, and nothing names lean.
        {
            var wide = Arch(13, 12.0, 2.0, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 1);
            int asked = Get<int>(placed, "GroundAsked");
            int got = Get<int>(placed, "GroundPlaced");
            if (asked != 1 || got != 1)
                throw new InvalidOperationException($"A level is never refused now: Type 1 asked is Type 1 placed; asked {asked}, placed {got}.");
            object built = Get<object>(placed, "Built");
            if (Get<int>(built, "Peeled") != 6)
                throw new InvalidOperationException($"The three trunks on each flank lean 83, 74 and 63 degrees to the central foot and peel; {Get<int>(built, "Peeled")} peeled.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            object first = tried[0];
            if (Get<int>(first, "Ground") != 1 || Get<string>(first, "Rule") == "lean")
                throw new InvalidOperationException($"The level built is level 1 and it names no lean; it names '{Get<string>(first, "Rule")}'.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 7)
                throw new InvalidOperationException($"Six peeled feet and one band foot is seven; {feet.Length} built.");
        }
```

- [ ] **Step 2: Run the gate and name the failure**

Run the gate. Expected: the build is clean and the harness reports

`FAIL  ColumnPlacement: Type 1 asked is Type 1 placed; asked 1, placed 0.`

because today a trunk past the 60 degree cap refuses the whole level and `Place` drops to the next one down. Behind it wait four more: Type 2 on the same arch reports `placed 0` too, and once the peel is in but the band is still read from each tree's own projection it comes back with the centre notch in the upper band, feet at 2.5 and 7 and one trunk peeled; the narrow bay comes back with three feet, not five, because today every pair of feet inside the clearance is welded whatever put them there; the centre pair stands at 4.49, its own plan centre, not on the span's midpoint; and the twelve-wide arch still reports `placed 0`.

- [ ] **Step 3: Write the peel and the one-case merge**

In `plugin/native_v02/Components/ColumnPlacement.cs`, in `Level` (line 85), after `public int FeetMerged;` add:

```csharp
            /// <summary>Trunks that stepped off a shared foot onto their own.</summary>
            public int Peeled;
            /// <summary>Pairs of feet inside the clearance that stayed two.</summary>
            public int FeetClose;
```

Replace the whole foot section of `BuildLevel`, from `if (level == 0)` (line 490) through the two lines that record the merge (`int[] footIndex = MergeFeet(...)` and `result.FeetMerged = merged;`, lines 566 and 567), with:

```csharp
            // Every tree's OWN foot, where the ray from its main notch along
            // the aim meets the ground: what Type 0 stands on, and what a
            // peeled trunk falls back to.
            var own = new Point3d[trees.Count];
            for (int t = 0; t < trees.Count; t++)
            {
                if (trees[t].FixedFoot is Point3d fixedFoot)
                {
                    own[t] = fixedFoot;
                    continue;
                }
                Point3d ownMain = nodes[trees[t].Nodes[0]];
                double ownRise = Math.Max(ownMain.Z - ground, 0.0);
                double ownAlong = ownRise / Math.Max(aim[t].Z, 1.0e-9);
                own[t] = new Point3d(
                    ownMain.X - (aim[t].X * ownAlong),
                    ownMain.Y - (aim[t].Y * ownAlong),
                    ground);
            }

            if (level == 0)
            {
                // Each tree stands on its own foot, on the line of the force
                // it carries. AimFrom caps the lean, so this is never refused.
                for (int t = 0; t < trees.Count; t++)
                    foot[t] = own[t];
            }
            else
            {
                // N bands per span about its own midpoint. The band is
                // decided PER MIRROR PAIR (spec 3.5): the pair member on the
                // first half of the chord takes the band its main notch
                // projects into, and its partner takes the MIRRORED band,
                // level-1-band, so a pair lands in mirrored bands wherever
                // the boundaries fall. Reading every tree's own projection
                // put a main notch sitting exactly ON a boundary, which is
                // where the centre notch of a uniform arch sits at an even
                // Type, into the upper band: the two central bands then held
                // different trees and their feet came out unmirrored on a
                // symmetric arch. A centre tree is its own partner: at an ODD
                // Type it takes the central band; at an EVEN Type the mirror
                // plane IS a boundary and there is no central band to take,
                // so it stands on its Type 0 foot, which is on that plane
                // already.
                var band = new int[trees.Count];
                for (int t = 0; t < trees.Count; t++)
                    band[t] = -1;
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null || band[t] >= 0)
                        continue;
                    int partner = t < placement.Partner.Length ? placement.Partner[t] : -1;
                    if (partner == t)
                    {
                        if ((level % 2) == 1)
                            band[t] = level / 2;
                        continue;
                    }
                    bool paired = partner >= 0 && partner < trees.Count;
                    // A span's trees are added in grouping order, so the
                    // LOWER index of a pair is the one on the first half of
                    // the chord.
                    int first = paired ? Math.Min(t, partner) : t;
                    int mirrored = paired ? Math.Max(t, partner) : -1;
                    int chosen = BandIndex(nodes, placement, bars, trees[first], level);
                    band[first] = chosen;
                    if (mirrored >= 0)
                        band[mirrored] = level - 1 - chosen;
                }

                // A band's foot is the plan centre (midpoint of the extremes)
                // of the main notches it carries, at ground level.
                var bandMains = new Dictionary<(int Span, int Band), List<int>>();
                for (int t = 0; t < trees.Count; t++)
                {
                    Tree tree = trees[t];
                    if (tree.FixedFoot is Point3d fixedFoot)
                    {
                        foot[t] = fixedFoot;
                        continue;
                    }
                    if (band[t] < 0)
                    {
                        // The centre tree at an even Type: no band, its own
                        // foot, which stands on the mirror plane.
                        foot[t] = own[t];
                        continue;
                    }
                    if (!bandMains.TryGetValue((tree.Span, band[t]), out List<int>? list))
                    {
                        list = new List<int>();
                        bandMains[(tree.Span, band[t])] = list;
                    }
                    list.Add(t);
                }
                foreach (List<int> members in bandMains.Values)
                {
                    double minX = double.MaxValue, maxX = double.MinValue;
                    double minY = double.MaxValue, maxY = double.MinValue;
                    foreach (int t in members)
                    {
                        Point3d main = nodes[trees[t].Nodes[0]];
                        minX = Math.Min(minX, main.X);
                        maxX = Math.Max(maxX, main.X);
                        minY = Math.Min(minY, main.Y);
                        maxY = Math.Max(maxY, main.Y);
                    }
                    var centre = new Point3d(0.5 * (minX + maxX), 0.5 * (minY + maxY), ground);
                    foreach (int t in members)
                        foot[t] = centre;
                }

                // The PEEL (spec 3.5). A trunk runs from its foot to a fork
                // that lies on the segment to its main notch, so the trunk's
                // lean IS that segment's lean and no fork can change it. Past
                // the cap the TREE steps off the shared foot onto its own,
                // rather than the level being refused: on any wide span the
                // flank trunks always pass the cap, so Type 1 fell back to
                // Type 0 whole and the slider looked dead. A band whose trees
                // all peel simply builds no foot, because nothing stands on
                // it.
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null)
                        continue;
                    double lean = MouldGeometry.LeanFromVertical(
                        foot[t], nodes[trees[t].Nodes[0]]);
                    if (lean <= MouldGeometry.MaxLeanDegrees + 1.0e-9)
                        continue;
                    foot[t] = own[t];
                    result.Peeled++;
                }
            }

            int[] footIndex = MergeFeet(
                placement, foot, nodes, bars, clearance, result.Nodes,
                out int merged, out int close);
            result.FeetMerged = merged;
            result.FeetClose = close;
```

Add the band helper immediately before `MergeFeet` (that is, after `AddMember` ends at line 747):

```csharp
        /// <summary>
        /// The band a main notch projects into: the chord from the span's
        /// first node to its last is cut into <paramref name="level"/> equal
        /// bands and the notch's parameter along it says which. Only the
        /// FIRST-HALF member of a mirror pair is read this way; its partner
        /// takes the mirrored band, and a centre tree takes the central band
        /// or none (spec 3.5).
        /// </summary>
        private static int BandIndex(
            Point3d[] nodes, Placement placement, int[][] bars, Tree tree, int level)
        {
            Span span = placement.Spans[tree.Span];
            int[] bar = bars[span.Bar];
            Point3d a = nodes[bar[span.First]];
            Point3d b = nodes[bar[span.Last]];
            double cx = b.X - a.X;
            double cy = b.Y - a.Y;
            double chord = (cx * cx) + (cy * cy);
            Point3d main = nodes[tree.Nodes[0]];
            double s = chord > 1.0e-18
                ? (((main.X - a.X) * cx) + ((main.Y - a.Y) * cy)) / chord
                : 0.5;
            return Math.Min(Math.Max((int)Math.Floor(s * level), 0), level - 1);
        }
```

Then replace `MergeFeet` entire (lines 749 to 808, doc comment included) with:

```csharp
        /// <summary>
        /// Where the feet become NODES, and the one case in which two of them
        /// become one.
        ///
        /// Feet at the SAME point are one node whatever put them there: two
        /// trees in one band, every tree of a span at Type 1, or two spans
        /// whose bands meet at a crossing. That is WELDING, and it is not a
        /// merge and is not counted.
        ///
        /// Beyond that only a MIRRORED PAIR merges (spec 3.5): when its two
        /// feet lie within the clearance of each other the pair stands on one
        /// foot at its span's chord midpoint, which is where its own symmetry
        /// says it belongs and not wherever two solved-net forces happened to
        /// aim it. Any other two feet inside the clearance stay two and are
        /// counted in FeetClose. Merging those was what turned leaning
        /// neighbours into accidental V's and X's on Param's review arch: two
        /// trees that lean toward one another are not one tree, and the ring
        /// tree's foot, fixed by 3.2, never merges at all.
        /// </summary>
        private static int[] MergeFeet(
            Placement placement,
            Point3d[] foot,
            Point3d[] nodes,
            int[][] bars,
            double clearance,
            List<Point3d> levelNodes,
            out int merged,
            out int close)
        {
            int n = foot.Length;
            merged = 0;
            double squared = clearance * clearance;
            const double weldSquared = 1.0e-18;

            for (int t = 0; t < n; t++)
            {
                int partner = t < placement.Partner.Length ? placement.Partner[t] : -1;
                // -1 is the ring tree, t is a centre tree standing alone, and
                // anything below t was handled when its partner came round.
                if (partner <= t || partner >= n)
                    continue;
                if (placement.Trees[t].FixedFoot is not null ||
                    placement.Trees[partner].FixedFoot is not null)
                    continue;
                double gap = MouldGeometry.PlanDistanceSquared(foot[t], foot[partner]);
                if (gap <= weldSquared || gap > squared)
                    continue;
                Span span = placement.Spans[placement.Trees[t].Span];
                int[] bar = bars[span.Bar];
                Point3d first = nodes[bar[span.First]];
                Point3d last = nodes[bar[span.Last]];
                var middle = new Point3d(
                    0.5 * (first.X + last.X), 0.5 * (first.Y + last.Y), foot[t].Z);
                foot[t] = middle;
                foot[partner] = middle;
                merged++;
            }

            var footIndex = new int[n];
            for (int t = 0; t < n; t++)
            {
                footIndex[t] = -1;
                for (int u = 0; u < t; u++)
                {
                    if (MouldGeometry.PlanDistanceSquared(foot[t], foot[u]) <= weldSquared &&
                        Math.Abs(foot[t].Z - foot[u].Z) <= 1.0e-9)
                    {
                        footIndex[t] = footIndex[u];
                        break;
                    }
                }
                if (footIndex[t] < 0)
                {
                    levelNodes.Add(foot[t]);
                    footIndex[t] = levelNodes.Count - 1;
                }
            }

            // What stands close but apart, counted once per pair of feet.
            // The feet are the only nodes in the level so far, which is why
            // this runs here and not after the members are built.
            close = 0;
            for (int i = 0; i < levelNodes.Count; i++)
            {
                for (int j = i + 1; j < levelNodes.Count; j++)
                {
                    if (MouldGeometry.PlanDistanceSquared(levelNodes[i], levelNodes[j]) <= squared)
                        close++;
                }
            }
            return footIndex;
        }
```

- [ ] **Step 4: Run the gate green**

Run the gate. Expected: `0 warnings`, `Components discovered: 19`, `PASS  ColumnPlacement`, exit 0. Every Type 1 in the older cases is untouched by the band rule (at Type 1 both members of a pair, and any centre tree, take band 0 whichever way it is read), and two older cases depend on the weld and must still pass: the crossing, where the two spans' band feet are both computed as exactly `(0, 0)` and so weld to one node (`Ground 1 on a cross merges the two midpoint feet into one`), and the centred foot at 9 and 8 notches, where one band holds every tree and no trunk reaches the cap, so nothing peels.

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): a trunk past the cap peels onto its own foot, and only a mirrored pair merges"
```

---

### Task 3: Judged, never refused

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`Level.Feasible` doc at lines 88 to 92; `Place`'s level selection at 264 to 295; `BuildLevel`'s verdict at 695 to 711; `Refuse` at 714 to 719, deleted)
- Modify: `tests/native_smoke/Program.cs` (the `alignmentCap` lookup near line 3245; the Auto case at 3622 to 3679 adjusted; a new Auto case appended after it; the `PASS ColumnPlacement` text at 601 to 619)

**Interfaces:**
- Consumes: `Level.Collisions`, `Level.WorstLean`, `Level.WorstAlignment`, `Level.LoadPath` (all existing public fields), `ColumnPlacement.AlignmentDegrees` (30.0), `MouldGeometry.MaxLeanDegrees` (60.0).
- Produces: `Level.Feasible` now means `Collisions == 0`; `Level.Rule` is one of `"collision"`, `"lean"`, `"alignment"`, `"none"` and `Level.Value` the measure it names; `Place` builds level `min(groundAsked, MaxGround)` alone when `groundAsked >= 0` and all five levels for Auto. `Refuse` no longer exists.

- [ ] **Step 1: Write the failing case and adjust the old one**

In `tests/native_smoke/Program.cs`, after `double maxLean = (double)geometry.GetField("MaxLeanDegrees")!.GetValue(null)!;` (about line 3245) add:

```csharp
        double alignmentCap = (double)engine.GetField("AlignmentDegrees")!.GetValue(null)!;
```

In the existing Auto case (`// ---- Auto picks the shorter load path where both are feasible.`, line 3622), replace the two `Feasible` assertions and the whole tail from `if (Get<int>(placed, "GroundPlaced") != 1)` to the end of the case with the block below, and add the `AutoWinner` local function immediately before the case:

```csharp
        // Spec 3.7's Auto rule, recomputed by the check from what the engine
        // recorded: the shortest load path among the levels with NO
        // collision, ties to the higher level; and when every level collides,
        // the shortest of them all.
        int AutoWinner(object[] levels)
        {
            object? best = null;
            object? bestAny = null;
            foreach (object level in levels.OrderByDescending(l => Get<int>(l, "Ground")))
            {
                if (bestAny is null || Get<double>(level, "LoadPath") < Get<double>(bestAny, "LoadPath"))
                    bestAny = level;
                if (Get<int>(level, "Collisions") == 0 &&
                    (best is null || Get<double>(level, "LoadPath") < Get<double>(best, "LoadPath")))
                    best = level;
            }
            return Get<int>(best ?? bestAny!, "Ground");
        }
```

That case's opening comment now ends on two claims that are no longer true, that levels 2, 3 and 4 are refused and that the refusal is what keeps the tie rule off level 1. Replace its last clause, `so they are refused and cannot take the tie-to-the-higher-level rule off 1.`, with:

```csharp
            // the 30-degree cap, so alignment is the worst measure each of
            // them names. Nothing is refused any more, and Auto weighs all
            // five levels by load path.
```

The two `Feasible` assertions become:

```csharp
            if (!Get<bool>(one, "Feasible"))
                throw new InvalidOperationException($"Feasible now means no collision, and Type 1 has none here; it reports {Get<int>(one, "Collisions")}.");
            if (!Get<bool>(zero, "Feasible"))
                throw new InvalidOperationException($"Feasible now means no collision, and Type 0 has none here; it reports {Get<int>(zero, "Collisions")}.");
```

and the tail becomes:

```csharp
            // Levels 2, 3 and 4 hand every tree its own plumb foot under a
            // tilted aim, 35 degrees off the thrust the foot is asked for.
            // That USED to refuse them. Spec 3.7 judges and never refuses:
            // they stand, alignment is named as the worst measure, and Auto
            // weighs them by load path like any other level.
            foreach (int level in new[] { 2, 3, 4 })
            {
                object judged = AtLevel(level);
                if (!Get<bool>(judged, "Feasible"))
                    throw new InvalidOperationException($"Level {level} has no collision here, so it is feasible; it came back refused on {Get<string>(judged, "Rule")}.");
                if (Get<string>(judged, "Rule") != "alignment")
                    throw new InvalidOperationException($"Level {level} stands a plumb trunk under a tilted aim, so alignment is the worst measure it names; it names '{Get<string>(judged, "Rule")}'.");
                if (Get<double>(judged, "Value") <= alignmentCap)
                    throw new InvalidOperationException($"The named alignment is the measured angle, past the {alignmentCap:0} degree bound; it is {Get<double>(judged, "Value"):0.###}.");
            }
            int winner = AutoWinner(tried);
            if (Get<int>(placed, "GroundPlaced") != winner)
                throw new InvalidOperationException($"Auto places the shortest load path among the levels with no collision, ties to the higher; that is {winner} and it placed {Get<int>(placed, "GroundPlaced")}.");
        }

        // ---- Auto prefers the level that does not collide (spec 3.7). The
        // rise-five arch eight wide at a clearance of 1.2 (a median plan edge
        // of 24 gives ClearanceFraction 0.05 that) stands its seven Type 0
        // feet one unit apart, so every neighbouring pair of members is
        // inside the clearance and Type 0 collides six times. Type 1 gathers
        // all seven onto one foot, where every member shares an end and
        // nothing can collide. Type 0 still carries the SHORTEST load path,
        // being plumb throughout, so an Auto that only minimised the load
        // path would take it.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 24.0, 1, -1);
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            if (tried.Length != 5)
                throw new InvalidOperationException($"Auto builds all five levels; it built {tried.Length}.");
            object AtLevel(int level) =>
                tried.FirstOrDefault(t => Get<int>(t, "Ground") == level)
                ?? throw new InvalidOperationException($"Auto must build every level; {level} is missing.");
            object zero = AtLevel(0);
            object one = AtLevel(1);
            if (Get<int>(zero, "Collisions") == 0)
                throw new InvalidOperationException("This fixture wants Type 0 to collide: seven plumb members a unit apart inside a clearance of 1.2.");
            if (Get<bool>(zero, "Feasible"))
                throw new InvalidOperationException("Feasible means no collision, and Type 0 collides here.");
            if (Get<string>(zero, "Rule") != "collision")
                throw new InvalidOperationException($"A colliding level names the collision as its worst measure; it names '{Get<string>(zero, "Rule")}'.");
            if (Get<int>(one, "Collisions") != 0)
                throw new InvalidOperationException($"Type 1 gathers every tree onto one foot, where every member shares an end; it reports {Get<int>(one, "Collisions")} collisions.");
            if (tried.Any(t => Get<double>(t, "LoadPath") < Get<double>(zero, "LoadPath")))
                throw new InvalidOperationException("Type 0 carries the shortest load path here, or the preference for a collision-free level is not being tested at all.");
            int winner = AutoWinner(tried);
            if (winner == 0)
                throw new InvalidOperationException("The recomputed winner is a collision-free level, and Type 0 is not one.");
            if (Get<int>(placed, "GroundPlaced") != winner)
                throw new InvalidOperationException($"Auto places the shortest load path among the levels with no collision, ties to the higher; that is {winner} and it placed {Get<int>(placed, "GroundPlaced")}.");
        }
```

- [ ] **Step 2: Run the gate and name the failure**

Run the gate. Expected: the build is clean and the harness reports

`FAIL  ColumnPlacement: Level 2 has no collision here, so it is feasible; it came back refused on alignment.`

because today a level whose worst per-foot alignment passes 30 degrees is REFUSED, `Feasible` means "nothing refused it" rather than "nothing collides", and Auto scores only the levels that survived. The new Auto case fails behind it with `Auto places the shortest load path among the levels with no collision, ties to the higher; that is 1 and it placed 0`, because today every level of that fixture is refused on its collision and Auto falls back to level 0, the one that collides most.

- [ ] **Step 3: Judge instead of refusing**

In `plugin/native_v02/Components/ColumnPlacement.cs`, replace the `Feasible`, `Rule` and `Value` declarations in `Level` (lines 88 to 92) with:

```csharp
            /// <summary>No member collides. Auto reads this and nothing else.</summary>
            public bool Feasible = true;
            /// <summary>collision, lean, alignment, or none: the worst measure.</summary>
            public string Rule = "none";
            /// <summary>The measure Rule names.</summary>
            public double Value;
```

Replace the verdict at the end of `BuildLevel` (lines 695 to 711, from `if (level > 0)` through the closing brace of the `else if` block, leaving `return result;`) with:

```csharp
            // Judged, never refused (spec 3.7). Every level is BUILDABLE: the
            // aim caps the lean at Type 0 and the peel caps it at Type N, and
            // an alignment past the bound is a foundation taking thrust, not
            // an impossibility. So Feasible carries the one thing that is a
            // fault, a collision, and Auto reads it; Rule and Value name the
            // worst measure for the author, in the order they matter. A level
            // that used to be refused is now placed and reported.
            result.Feasible = result.Collisions == 0;
            if (result.Collisions > 0)
            {
                result.Rule = "collision";
                result.Value = result.Collisions;
            }
            else if (worstLean > MouldGeometry.MaxLeanDegrees + 1.0e-9)
            {
                result.Rule = "lean";
                result.Value = worstLean;
            }
            else if (worstAlign > AlignmentDegrees + 1.0e-9)
            {
                result.Rule = "alignment";
                result.Value = worstAlign;
            }
            else
            {
                result.Rule = "none";
                result.Value = 0.0;
            }
            return result;
```

Delete `Refuse` entire (lines 714 to 719).

Replace the level selection in `Place` (lines 264 to 295, from `if (groundAsked >= 0)` through the closing brace of the `else` block) with:

```csharp
            if (groundAsked >= 0)
            {
                // Type N asked is Type N built: nothing refuses a level any
                // more, so there is nothing to fall back to and GroundPlaced
                // always equals GroundAsked.
                int level = Math.Min(groundAsked, MaxGround);
                Level built = BuildLevel(nodes, placement, bars, anchorSet, ground, level, clearance);
                placement.Tried.Add(built);
                placement.Built = built;
                placement.GroundPlaced = level;
            }
            else
            {
                // Auto: build all five and prefer the shortest load path
                // among those with NO COLLISION. Descending, so a tie goes to
                // the higher level. When every level collides the shortest of
                // them is placed anyway, because a Result with no columns
                // breaks the chain.
                Level? best = null;
                Level? bestAny = null;
                for (int level = MaxGround; level >= 0; level--)
                {
                    Level built = BuildLevel(nodes, placement, bars, anchorSet, ground, level, clearance);
                    placement.Tried.Add(built);
                    if (bestAny is null || built.LoadPath < bestAny.LoadPath)
                        bestAny = built;
                    if (built.Collisions == 0 && (best is null || built.LoadPath < best.LoadPath))
                        best = built;
                }
                Level chosen = best ?? bestAny!;
                placement.Built = chosen;
                placement.GroundPlaced = chosen.Ground;
            }
```

- [ ] **Step 4: Rewrite the check's PASS line**

In `tests/native_smoke/Program.cs`, replace the `Console.WriteLine` argument at lines 601 to 619 with:

```csharp
                "PASS  ColumnPlacement: nine notches at Branching 2 group into a "
                + "centre single and four mirrored pairs with mirrored mains, "
                + "eight at Branching 3 into two triples and a single at each "
                + "anchor end; the fork lies on the foot-to-main segment at "
                + "65% height with trunk and main branch collinear; an arch "
                + "whose pulls carry a flank scale and an along-chord skew "
                + "still puts every mirrored pair of feet astride the span's "
                + "midpoint and its centre foot ON it, plumb; three bars of "
                + "one family, one of them traced backwards, carry the same "
                + "feet in their own frames; a wide arch asked for one "
                + "central foot PLACES it and peels the flank trunks that "
                + "would pass the 60 degree cap, and at two feet its bands "
                + "come out mirrored with the centre tree on the midpoint on "
                + "its own foot; a symmetric arch puts its one foot on the "
                + "span centre within a hundredth of the span; feet inside the clearance stay two unless they are a "
                + "mirrored pair, which stands on its span's midpoint; "
                + "mid-bar anchors give half-spans and no head; two bars "
                + "ending on an anchor-free rim get one ring tree at their "
                + "tangents' plan intersection; a crossing node is held once; "
                + "at Branching 3 a branch below the fork still leaves lower "
                + "end first and no held head becomes a foot in mid-air; "
                + "CountCollisions refuses two members at half the clearance, "
                + "passes them at twice, and refuses a member that rises "
                + "above the nearest net vertex; no level is refused, and "
                + "Auto places the shortest load path among the levels that "
                + "do not collide."
```

- [ ] **Step 5: Run the gate green**

Run the gate. Expected: `0 warnings`, `Components discovered: 19`, `Parameters discovered: 12`, `PASS  ColumnPlacement`, exit 0. `ColumnsComponent` still compiles: it reads `built.Feasible`, `built.Ground` and `placement.Tried` and none of those changed shape. Its two runtime messages are still the old ones and are rewritten in Task 4.

- [ ] **Step 6: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): every level is judged and none refused; Auto prefers the levels that do not collide"
```

---

### Task 4: The component says Type

**Files:**
- Modify: `plugin/native_v02/Components/ColumnsComponent.cs` (`ValueLists` at lines 33 to 48; the class doc at 15 to 30; the constructor's description at 57 to 59; `RegisterInputParams` slot 2 at 164 to 176; `SolveInstance`'s clamp at 208 to 224; the fallback and collision warnings at 387 to 401; the `Place` and `ColumnsBlock` calls at 342 to 415; `Diagnostics` at 446 to 625)
- Modify: `tests/native_smoke/Program.cs` (`SpineComponentContracts` at lines 137 to 206)
- Modify: `docs/component-taxonomy.md` (line 55)
- Read only: `plugin/native_v02/Components/DiagnoseComponents.cs`

**Interfaces:**
- Consumes: `Placement.AsymmetryRemoved`, `Placement.Families`, `Placement.CentreTrees`, `Placement.Spans`, `Placement.Tried`, `Level.Peeled`, `Level.FeetMerged`, `Level.FeetClose`, `Level.WorstAlignment`, `Level.Collisions`, `Level.LoadPath` (Tasks 1 to 3), `ColumnPlacement.AlignmentDegrees`, `ResultDiagnostics.Entry(string source, string code, string severity, string message, double? value = null, double? tolerance = null, string unit = "", IReadOnlyDictionary<string, string>? context = null)`, `ResultDiagnostics.Context(params (string Key, string Value)[] pairs)`.
- Produces: input slot 2 named `Type`, nicknamed `T`; diagnostic codes `columns.type`, `columns.symmetry`, `columns.feet_merged`, `columns.feet_close`, `columns.alignment`, `columns.collision`, `columns.load_path`. `columns.ground` is gone.

- [ ] **Step 1: Write the failing pin**

In `tests/native_smoke/Program.cs`, in `SpineComponentContracts`, after the `StyleComponent` entry (which ends `new[] { "STY" }),` at line 196) add:

```csharp
                // Columns is pinned because slot 2 is RENAMED from Ground to
                // Type and keeps its slot: the nicknames are the canvas
                // contract, and a saved wire has to land on the same port it
                // left.
                ["Ananke.COMPAS.Native.Components.ColumnsComponent"] = (
                    "Columns",
                    "Columns",
                    "03 Visualise",
                    new[] { "RES", "B", "T" },
                    new[] { "RES" }),
```

- [ ] **Step 2: Run the gate and name the failure**

Run the gate. Expected: the build is clean and the harness reports

`FAIL  Columns [Ananke.COMPAS.Native.Components.ColumnsComponent]: ColumnsComponent input 2 nickname must be 'T'; received 'G'.`

because slot 2 is still Ground `G`.

- [ ] **Step 3: Rename the port and its value list**

In `plugin/native_v02/Components/ColumnsComponent.cs`, replace the `ValueLists` field (lines 33 to 48) with:

```csharp
        private static readonly ComponentValueListSpec[] ValueLists =
        {
            new(
                2,
                "Type",
                new (string Label, string Value)[]
                {
                    ("0 · own feet", "0"),
                    ("1 · one central foot", "1"),
                    ("2 · two feet", "2"),
                    ("3 · three feet", "3"),
                    ("4 · four feet", "4"),
                    ("Auto", "-1")
                },
                "0")
        };
```

Replace the first paragraph of the class doc comment (lines 16 to 20) with:

```csharp
    /// Columns: every notch of every principal line gets a column head, the
    /// heads group into trees by Branching, and the trees meet the ground by
    /// Type. Nothing is chosen by a beam search any more; the machine has a
    /// joint at every notch and this component says how the joints are held
    /// up.
```

Replace the constructor's description (lines 57 to 59) with:

```csharp
                "Hold every notch of every principal line with a column head, "
                    + "grouped into trees by Branching and footed by Type. "
                    + "The loads come from the Result's own member forces, "
                    + "mirrored about each span's midpoint before a foot is placed.",
```

Replace the slot 2 registration (lines 164 to 176) with:

```csharp
            parameters.AddIntegerParameter(
                "Type",
                "T",
                "How the trees meet the ground. 0 stands each tree on its own "
                    + "foot on the line of the force it carries; 1 to 4 gather "
                    + "each span's trees onto that many mirrored feet in bands "
                    + "about the span's midpoint, and a trunk that would lean "
                    + "past 60 degrees to its shared foot steps back onto its "
                    + "own foot instead of the level being refused; -1 is "
                    + "Auto, which builds every level and places the shortest "
                    + "load path among those whose members do not collide. "
                    + "The feet are mirrored about each span's midpoint and "
                    + "shared across every span that holds the same notches, "
                    + "so the principal lines agree with one another.",
                GH_ParamAccess.item,
                0);
```

- [ ] **Step 4: Rename the local, the clamp and the two warnings**

In `SolveInstance`, replace lines 208 to 224 with:

```csharp
            int branching = 1;
            int type = 0;
            data.GetData(1, ref branching);
            data.GetData(2, ref type);
            branching = Math.Min(Math.Max(branching, 1), ColumnPlacement.MaxBranching);
            if (type > ColumnPlacement.MaxGround)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"Type {type} is above the {ColumnPlacement.MaxGround} feet "
                        + "per span this machine places; clamped. An old Ground "
                        + "or Type value list goes to 6; place the Type list "
                        + "from the component menu.");
                type = ColumnPlacement.MaxGround;
            }
            if (type < -1)
                type = -1;
```

In the `ColumnPlacement.Place` call (lines 342 to 351) the last argument becomes `type` in place of `ground`:

```csharp
                    branching,
                    type);
```

Replace the two warning blocks (lines 387 to 401) with:

```csharp
                if (built.Collisions > 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        $"{built.Collisions} member(s) come within the clearance "
                            + "of another member or of the net; placed anyway so "
                            + "the chain keeps running. Diagnose says where.");
                }
                if (built.Peeled > 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        $"{built.Peeled} trunk(s) stand on their own feet: a "
                            + "trunk from the shared foot would lean past 60 "
                            + "degrees. The level itself is placed.");
                }
```

In the `MouldGeometry.ColumnsBlock` call (lines 406 to 415) the asked level becomes `type`:

```csharp
                    groundAsked: type,
```

And in the `Diagnostics` call (lines 431 to 434) the `ground` argument becomes `type`:

```csharp
                output = ResultDiagnostics.Replace(output, "Columns", Diagnostics(
                    bars, placement, built, force, angle, branching, type,
                    groundLevel, alongToAnchors, acrossToColumns, overlapping,
                    barShape, forceUnit));
```

- [ ] **Step 5: The diagnostics of spec section 4**

In `Diagnostics`, replace the `columns.ground` entry, the `columns.load_path` entry and the `columns.feet_merged` entry (lines 524 to 558) with:

```csharp
            string asked = groundAsked < 0 ? "Auto" : groundAsked.ToString(CultureInfo.InvariantCulture);
            string gathered = placement.GroundPlaced == 0
                ? $"every tree stands on its own foot; {built.Feet.Count} feet"
                : $"each span's trees gather onto up to {placement.GroundPlaced} feet "
                    + $"about its midpoint; {built.Feet.Count} feet built";
            d.Add(ResultDiagnostics.Entry(S, "columns.type",
                built.Peeled > 0 ? "warning" : "info",
                $"Type asked {asked}, placed {placement.GroundPlaced}: {gathered}"
                    + (built.Peeled > 0
                        ? $"; {built.Peeled} trunk(s) stand on their own feet because "
                            + $"a trunk to the shared foot would lean past {cap:0} degrees"
                        : string.Empty)
                    + ".",
                placement.GroundPlaced, unit: "feet per span",
                context: ResultDiagnostics.Context(
                    ("asked", groundAsked.ToString(CultureInfo.InvariantCulture)),
                    ("placed", placement.GroundPlaced.ToString(CultureInfo.InvariantCulture)),
                    ("peeled", built.Peeled.ToString(CultureInfo.InvariantCulture)),
                    ("feet", built.Feet.Count.ToString(CultureInfo.InvariantCulture)))));

            d.Add(ResultDiagnostics.Entry(S, "columns.symmetry", "info",
                $"{placement.Spans.Count} spans in {placement.Families} families; "
                    + "feet mirrored about each span's midpoint and shared across "
                    + "each family; the largest aim moved "
                    + $"{placement.AsymmetryRemoved:0.##} degrees; "
                    + $"{placement.CentreTrees} centre tree(s) plumb.",
                placement.AsymmetryRemoved, unit: "degrees",
                context: ResultDiagnostics.Context(
                    ("spans", placement.Spans.Count.ToString(CultureInfo.InvariantCulture)),
                    ("families", placement.Families.ToString(CultureInfo.InvariantCulture)),
                    ("moved", Inv(placement.AsymmetryRemoved, "0.##")),
                    ("centres", placement.CentreTrees.ToString(CultureInfo.InvariantCulture)))));

            var scored = placement.Tried
                .OrderByDescending(t => t.Ground)
                .Select(t => (t.Ground.ToString(CultureInfo.InvariantCulture),
                    Inv(t.LoadPath, "0") + (t.Collisions > 0 ? " collides" : string.Empty)))
                .ToArray();
            d.Add(ResultDiagnostics.Entry(S, "columns.load_path", "info",
                $"load path {built.LoadPath:0} {forceUnit} x model units, the sum "
                    + "over members of force times length"
                    + (groundAsked < 0
                        ? $"; levels scored: {string.Join(", ", scored.Select(s => $"{s.Item1}={s.Item2}"))}"
                        : string.Empty),
                built.LoadPath, unit: forceUnit + " x model units",
                context: ResultDiagnostics.Context(scored)));

            if (built.FeetMerged > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.feet_merged", "info",
                    $"{built.FeetMerged} MIRRORED PAIR(S) of feet lay within the "
                        + "clearance of each other and stand on one foot at their "
                        + "span's midpoint. Only a mirrored pair merges; any other "
                        + "two feet stay two, however close.",
                    built.FeetMerged, unit: "feet"));
            }
            if (built.FeetClose > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.feet_close", "warning",
                    $"{built.FeetClose} pairs of feet closer than the clearance "
                        + "stand separately; raise Type to gather them, or space "
                        + "the principal lines.",
                    built.FeetClose, unit: "pairs"));
            }
            if (built.WorstAlignment > ColumnPlacement.AlignmentDegrees)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.alignment", "warning",
                    $"a foot's push is {built.WorstAlignment:0.#} degrees off the "
                        + "thrust its trees ask for; the foundation sees that as "
                        + "thrust.",
                    built.WorstAlignment, ColumnPlacement.AlignmentDegrees, "degrees"));
            }
```

Then replace the old collision entry (lines 564 to 572, guarded by `if (!built.Feasible && built.Ground == 0)`) with:

```csharp
            if (built.Collisions > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.collision", "warning",
                    $"{built.Collisions} member(s) come within the clearance of "
                        + "another member or of the net; placed anyway. Draw the "
                        + "principal lines further apart or lower Branching.",
                    built.Collisions, unit: "members"));
            }
```

- [ ] **Step 6: Check Diagnose, and the taxonomy row**

Diagnose reads no Columns code. Prove it:

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
rg -n "columns\.(ground|type)" "$repo\plugin\native_v02"
```

Expected: one hit only, `ColumnsComponent.cs` writing `columns.type`. `DiagnoseComponents.cs` names `columns.lean` in a doc comment and writes `diagnose.frame_without_columns`, neither of which is a read of `columns.ground`, so nothing is renamed there.

Replace line 55 of `docs/component-taxonomy.md` with:

```markdown
| `03 Visualise` | **Columns** | Result `RES`, Branching `B`, Type `T` | Result `RES` | Hold every notch of every principal line with a column head. The Result is the form finder: the principal lines travel in it, resolved by Pattern, the load each notch hands its bar comes from the Result's own member forces, and the ground is the level the anchors sit at. `Branching` (1, 2, 3) groups neighbouring notches into trees of that size, mirrored about the middle of each span with the remainder at the anchors, and the centre notch of an odd count standing alone; a bar is cut into spans at its anchors (a held ring gives two half-spans and no column at the ring) and at a ring tree, which serves bars ending on a free central rim from one foot at the plan intersection of their end tangents. Before a single foot is placed the trees' resultants are MIRRORED about each span's midpoint (a tree and its mirror get equal and opposite along-chord pulls, the centre tree none) and averaged across every span that holds the same notches, because a solved net's forces are never mirrored to the last digit and that is what used to put one principal line's columns out of step with another's. `Type` is how the trees meet the ground: 0 stands each on its own foot on the line of its force; 1 to 4 gather each span's trees onto that many mirrored feet in bands about the span's midpoint, the band being decided per mirror pair so that a pair always lands in mirrored bands (a centre tree takes the central band at an odd Type, and at an even Type stands on its own foot on the midpoint); -1 is Auto. A trunk that would lean past 60 degrees to its shared foot is PEELED, standing on its own foot instead, and the level is never refused for it: a level is judged, not refused, and Auto builds all five and places the shortest load path among those whose members do not collide, ties to the higher. Feet merge in one case only, a mirrored pair inside the clearance, which stands on its span's midpoint; any other two feet closer than the clearance stay two and are reported. The fork of every tree lies on the segment from its foot to its main notch at 65% of the notch height, so trunk and main branch are one straight line. The built trees leave ONLY inside the Result's Mould block. **Deconstruct** hands the geometry back as trees, **Monitor** the numbers, **Diagnose** the words. |
```

- [ ] **Step 7: Run the gate green**

Run the gate. Expected: `0 warnings`, `Components discovered: 19`, `Parameters discovered: 12`, `PASS  Columns [Ananke.COMPAS.Native.Components.ColumnsComponent]`, `PASS  ColumnPlacement`, exit 0.

- [ ] **Step 8: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnsComponent.cs" "tests/native_smoke/Program.cs" "docs/component-taxonomy.md"
git -C $repo commit -m "feat(columns): slot 2 is Type, and the diagnostics say what the symmetry, the peel and the feet did"
```

---

### Task 5: Rebuild, install, hand over

**Files:** none. Spec section 10 requires the install as the final step. This task is NOT run by the implementer of Tasks 1 to 4: the controller executes it after the whole-branch review and the merge, so the installed `.gha` is the reviewed one.

- [ ] **Step 1: Check for clashes, then build and install with Rhino CLOSED**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests","$repo\docs" -Recurse -Filter "*Name clash*"
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve before installing" }
Get-Process -Name "Rhino" -ErrorAction SilentlyContinue
& "$repo\plugin\native_v02\Build-And-Install.ps1"
```

If `Get-Process` returns a running Rhino, stop and ask Param to close it: the installed `.gha` is locked while Rhino holds it.

- [ ] **Step 2: Hand over**

Tell Param, in plain text with full absolute paths:

- what changed, in one line per task;
- that the plugin is installed at `C:\Users\Param\AppData\Roaming\Grasshopper\Libraries\Ananke_COMPAS\Ananke.COMPAS.gha` and RHINO MUST BE RESTARTED, because an open session keeps the old `.gha` and the old worker;
- that slot 2 now reads Type and an old Ground value list still drives it, so nothing rewires, but a definition that showed Ground 0 after asking for 1 now shows Type 1 with peeled flank trunks and its feet have moved to mirrored positions;
- that the four commits are local and NOT pushed.

---

## Self-review

### Spec coverage

| Spec section | Where it lands |
| --- | --- |
| 1 Why | No code. Quoted in the comments on `Symmetrise` (Task 1 Step 3), the peel (Task 2 Step 3) and `MergeFeet` (Task 2 Step 3). |
| 2 Ports | Task 4 Steps 3 and 4: slot 2 is `Type`/`T` in its slot, the value list carries the six labelled items with the unchanged values, GUID, name and output untouched, `GroundAsked`/`GroundPlaced` keep their wire names. Pinned by Task 4 Step 1. |
| 3.4 Loads and aims, symmetrised | Task 1 Step 3: span frame, mirror pairs, families with the reversed-span rule, the dead band (`PlumbDegrees = 2`), the ring tree excluded, `Tree.RawResultant`, `Tree.Load` untouched, `Symmetrise` returning the largest angle moved. Measured by Task 1 Step 1. |
| 3.5 Feet | Task 2 Step 3: Type 0 unchanged and `AimFrom` taking the pull as it stands; the band decided per mirror pair (`BandIndex` read for the first-half member, the partner taking `N-1-band`, a centre tree taking the central band at an odd Type and its own foot at an even one); then the peel into `Level.Peeled`, a band with every tree peeled building no foot; the one-case merge onto the chord midpoint, `Level.FeetClose`, coincident feet welded as neither, the ring foot never merging. Measured by Task 2 Step 1. |
| 3.7 Judged, never refused | Task 3 Step 3: `Refuse` deleted, `Feasible = Collisions == 0`, `Rule`/`Value` naming the worst measure, Type N building level N alone, Auto building all five and preferring the collision-free. Measured by Task 3 Step 1. |
| 4 Diagnostics | Task 4 Step 5: `columns.type` with its context, `columns.symmetry`, `columns.feet_merged` narrowed, `columns.feet_close`, `columns.alignment`, `columns.collision` at any level, `columns.load_path` with the `collides` mark under Auto. Diagnose checked in Task 4 Step 6. |
| 5 Files | `ColumnPlacement.cs` (Tasks 1 to 3), `ColumnsComponent.cs` (Task 4), `DiagnoseComponents.cs` (read only, Task 4 Step 6), `tests/native_smoke/Program.cs` (Tasks 1 to 4), `docs/component-taxonomy.md` (Task 4 Step 6). The 2026-08-28 spec is not edited. |
| 6 Testing | Mirrored feet and one family (Task 1 Step 1); Type 1 placed not refused, neighbours stay apart, the centre pair merges, the rewritten refusal case (Task 2 Step 1); Auto prefers no collision and the adjusted old Auto case (Task 3 Step 1); the `SpineComponentContracts` pin, 19 components, 12 parameters (Task 4 Steps 1 and 7). |
| 7 What breaks on the canvas | No code. Carried into the hand-over, Task 5 Step 2. |
| 8 Amendments | Encoded in Tasks 1 to 4 as the rows above. |
| 9 Out of scope | Nothing in this plan touches Animate, the Frame component, Deconstruct, Monitor, Export, Display, panels, icons, the port order, the fork rule, the ring tree, the loads, the block, `MouldGeometry.AimFrom` or the 60 degree cap. |
| 10 Constraints | Global Constraints above, verbatim; the install is Task 5. |

### Placeholder scan

No step says "TBD", "add validation", "similar to Task N" or "and so on". Every step is either literal C# to insert or replace with a line anchor, a literal PowerShell block, or a named expected output. The only prose instructions are Task 5 Step 2 (a message to a human) and the two "run the gate" steps per task, which name the exact expected strings.

### Type consistency

- `Symmetrise(Placement, Point3d[], int[][]) -> double` is declared in Task 1 Step 3, called from `Place` with `(placement, nodes, bars)`, the same two arrays `Place` already holds. `Place`'s own signature is untouched, so Task 1's harness `Run` helper and `ColumnsComponent`'s call site both still compile.
- `Placement.Partner` is `int[]`, indexed by tree index, read in `MergeFeet` with a length guard (`partner >= n` skipped) because `Partner` is sized when `Symmetrise` runs and `MergeFeet` runs per level afterwards.
- `MergeFeet` changes shape from `(Point3d[], double, List<Point3d>, out int)` to `(Placement, Point3d[], Point3d[], int[][], double, List<Point3d>, out int, out int)`. It is `private static` with one caller, `BuildLevel`, which is updated in the same step.
- `Level.Rule` stays `string` and `Level.Value` `double`; the harness reads them with `Get<string>` and `Get<double>` as it already does. `Level.Peeled` and `Level.FeetClose` are `public int` fields, so the harness's `Get<T>` (which does `GetField` with default public-instance binding) finds them.
- `Level.Feet` is `List<int>` of node indices and `Level.MemberTree` `List<int>`; the new `FootOfTree` helper reads both through `IEnumerable` and `Cast<int>`, the pattern the existing cases use for `Feet`.
- `built.Feet.Count`, `built.Peeled`, `built.FeetClose`, `built.WorstAlignment` and `built.Collisions` are all read in `Diagnostics`, whose parameter is already `ColumnPlacement.Level built`. `ColumnPlacement.AlignmentDegrees` is `public const double`, reachable from the component.
- `ResultDiagnostics.Entry`'s positional tail is `(value, tolerance, unit, context)`; `columns.alignment` uses the four-positional form `(..., built.WorstAlignment, ColumnPlacement.AlignmentDegrees, "degrees")` and every other new entry uses `unit:` and `context:` by name, matching the file's existing calls.

### Where the code argued with the spec or with the suggested task shape

Items 1 to 4 were raised against the spec of 2026-08-30 and RULED by the coordinator on the same day; the spec at `docs/superpowers/specs/2026-08-30-columns-symmetric-type-design.md` now carries every ruling, and this plan implements it.

1. **`AimFrom` takes the pull, not its negative.** The first spec wrote `MouldGeometry.AimFrom(-Resultant)`, but `AimFrom` already negates what it is handed (`Vector3d supply = -pulled;`) and returns the upward push direction, and the engine calls `AimFrom(trees[t].Resultant)`. Negating twice would aim every column downward. RULED: 3.5 now says `AimFrom(Resultant)`, the symmetrised pull, AimFrom negating it itself. The plan keeps the existing call.
2. **Coincident feet must still weld.** "Any other two feet closer than the clearance stay two" taken to the letter would build two nodes at one point in the crossing case (two spans whose Type 1 band feet are both exactly `(0, 0)`), breaking the existing `Ground 1 on a cross merges the two midpoint feet into one` check and handing Deconstruct two feet where the block's own weld sees one. RULED: 3.5 now says feet at the SAME point are one node, neither a merge nor a close pair. `MergeFeet` welds within 1e-9 and applies the clearance rule to mirrored pairs alone, and its doc comment says so.
3. **The band rule was only mirror-symmetric away from a band boundary.** `floor(s * N)` mirrors correctly for every pair except one whose main notch projects exactly onto a boundary, which is precisely where the centre notch of a uniform arch sits at an even Type: it went to the upper band, the two central bands held different trees, and their feet came out unmirrored on a symmetric arch. RULED and 3.5 amended: the band is decided PER MIRROR PAIR, the first-half member reading `floor(s x N)` and its partner taking `N-1-band`; a centre tree takes the central band at an odd Type and its own Type 0 foot, which is on the midpoint, at an even one. Task 2 Step 3 implements it (`BandIndex` plus the pairing loop) and Task 2 Step 1 measures it on the eleven-notch arch at Type 2, where a plain `floor(s x N)` puts the centre notch in the upper band and the feet at 2.5 and 7 instead of 2.5, 5 and 7.5.
4. **The Auto fixture is the rise-five arch, not the wide arch.** Spec 6 asks for "Auto prefers no collision" on the wide arch. On the wide arch at a realistic clearance no level collides at all, so the preference would never be exercised, and at a clearance large enough to make Type 0 collide the peeled flank feet of Type 1 collide too, leaving no collision-free level. Task 3 therefore drives it on the rise-five arch eight wide at a clearance of 1.2, where Type 0 collides six times, Type 1 cannot collide (every member shares the one foot), and Type 0 still carries the shortest load path. The check recomputes the winner from `Tried` by the section 3.7 rule, exactly as the spec asks. RULED: agreed.
5. **`SpineComponentContracts` had no Columns row to change.** Spec 6 says the Columns nicknames "become RES, B, T", but Columns was never pinned there. Task 4 Step 1 ADDS the row (name, nickname, tab and every port nickname), which is what makes Step 2's failure a port-contract failure rather than a silent pass.
6. **The engine's internal Ground names stay.** Every port, message, tooltip and diagnostic says Type, as spec section 2 requires, but `Placement.GroundAsked`, `Placement.GroundPlaced`, `Level.Ground` and `MaxGround` keep their names because they fill the block's wire fields `GroundAsked` and `GroundPlaced`, which the spec explicitly does not rename, and because the harness reads them by those names in cases this plan does not otherwise touch.
7. **A fifth task.** The suggested shape has four. Spec section 10 requires the rebuild and install with Rhino closed as the final step, and that is neither a code change nor a commit, so it is Task 5. RULED: it stays in the plan, and the controller runs it after the whole-branch review and the merge.

### Known risk, ledgered for the executor

The hand-built nets in Tasks 1 to 3 were sized by arithmetic in this plan: the peel counts (4 on the eleven-notch arch, 6 on the thirteen), the foot positions (0.776, 1.601, 2.477, 3.402, 5.0 and their mirrors at Type 0; 2.5, 5.0 and 7.5 at Type 2, where the outermost trunk leans 59.04 degrees and so does not peel), the clearance windows (a thirtieth against gaps of 0.025 and 0.05; 0.05 against 0.0323 and 2.111; 1.2 against 1.0 and 2.0) and the load-path ordering (Type 0 at 26.25, Type 1 at 37.04). If a case does not behave as predicted, adjust the FIXTURE (the width, the rise, the bend, the median passed to `Run`) and re-derive, never the assertion: the assertions are the spec.
