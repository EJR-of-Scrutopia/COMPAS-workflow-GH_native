# Columns With Two Sliders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Columns holds every notch of every principal line, groups the heads into trees by Branching, foots the trees by Ground with rejection and Auto, puts each fork on the segment from its foot to its main notch, and writes the same Mould block as today.

**Architecture:** A new pure engine, `ColumnPlacement` (spans, ring tree, grouping, feet, fork, members, rejection, load path; arithmetic on arrays), replaces the beam search. The component (`ColumnsComponent`, same GUID) reads the Result, builds the engine's inputs, calls `Place`, and writes the block and diagnostics. `BeamSolver` shrinks to `Response` and `SolveDense` for Monitor. Dead geometry (`ForkPoint`, `Solve3`, `BuildColumnTree`) goes. The harness drives every engine rule on hand-built arrays.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8 (managed only in tests), the Rhino-free reflection smoke harness in `tests/native_smoke`.

**Spec:** `docs/superpowers/specs/2026-08-28-columns-two-sliders-design.md` (binding), which amends section 9 of `docs/superpowers/specs/2026-08-27-res-spine-design.md`.

## Global Constraints

- No em dashes anywhere, in code, comments, docs or commit messages.
- Full absolute Windows paths in any reply to Param.
- No Co-Authored-By or AI attribution in any commit.
- Commit locally after every task; never push. Push only on Param's word.
- Rebuild and install as the final step with Rhino CLOSED, then tell Param to restart Rhino.
- Every measured check runs in the smoke harness without launching Rhino. Anything that P/Invokes `rhcommon_c` (`Curve.DivideByCount`, `Vector3d.Unitize`, `Mesh` queries) cannot run there; `Point3d`, `Line`, `Vector3d.Length`, `DistanceTo`, `PointAt` on a `Line` and the operators are managed and fine. The engine file must not touch `Mesh` or `Curve` at all.
- Before every build and every commit, run the OneDrive clash check in the shared gate below.
- Component GUID `c47a1e93-8b25-4d60-a1f7-6e29b3c05d84` never changes. Slot 0 (Result) never moves.
- `ContractSchema.Current` and `ResultDto.ResultSchema` are untouched. The only contract change is `GroundAsked >= -1`.
- Members leave the engine LOWER END FIRST and a fork is one node shared exactly; Animate depends on both.
- Another session holds an uncommitted edit to `plugin/native_v02/Components/DeliveryComponents.cs`. NEVER stage that file. `git add` by explicit path only.
- Spec section 9 (Animate, Monitor, worker, tools/tree_forest) is OUT OF SCOPE.

---

## File structure

| Path (relative to `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`) | Responsibility |
| --- | --- |
| `plugin/native_v02/Components/ColumnPlacement.cs` (create) | The engine: spans, ring tree, grouping, feet, fork, members, rejection, Auto, load path. No Grasshopper, no Mesh, no Curve. |
| `plugin/native_v02/Components/ColumnsComponent.cs` (create, replaces ColumnFinderComponents.cs) | Ports, value list, preview, Result in, engine call, block out, diagnostics. |
| `plugin/native_v02/Components/BeamSolver.cs` (create, extracted) | `Response` and `SolveDense` only, for Monitor's bar sag. |
| `plugin/native_v02/Components/ColumnFinderComponents.cs` (delete in Task 4) | Retired. |
| `plugin/native_v02/Components/MouldComponents.cs` (modify) | `MouldGeometry.LeanFromVertical` added; `ForkPoint`, `Solve3`, `BuildColumnTree` deleted. |
| `plugin/native_v02/Contracts/MouldContracts.cs` (modify) | `GroundAsked >= -1`. |
| `plugin/native_v02/Components/DiagnoseComponents.cs` (modify) | `forks_raised` cross-check removed. |
| `tests/native_smoke/Program.cs` (modify) | Engine checks added; retired checks deleted; contract fixture extended. |
| `docs/component-taxonomy.md` (modify) | The Columns row. |

## The shared gate

Every "run the gate" step means this, from PowerShell. It refuses a OneDrive clash file first, builds the plugin, builds the harness, and runs the harness against the freshly built `.gha`.

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests" -Recurse -Filter "*Name clash*"
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve before building" }
dotnet build "$repo\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -v quiet --nologo
dotnet run --project "$repo\tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "$repo\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"
```

A passing gate ends with `Native component smoke test passed; Rhino was not launched.` and exit code 0. The build must produce 0 warnings. Commit messages follow the repo's `type(scope): sentence` style. Every commit uses explicit file paths.

---

### Task 1: The engine, `ColumnPlacement`

**Files:**
- Create: `plugin/native_v02/Components/ColumnPlacement.cs`
- Modify: `plugin/native_v02/Components/MouldComponents.cs` (add `LeanFromVertical` to `MouldGeometry`, next to `MaxLeanDegrees` at about line 1656)

**Interfaces:**
- Consumes: `MouldGeometry.AimFrom(Vector3d pulled)`, `MouldGeometry.MaxLeanDegrees`, `MouldGeometry.PlanDistanceSquared(Point3d, Point3d)` (all existing in MouldComponents.cs).
- Produces (Tasks 2 and 3 depend on these exact names):
  - `ColumnPlacement.ForkFraction = 0.65`, `AlignmentDegrees = 30.0`, `ClearanceFraction = 0.05`, `MaxGround = 4`, `MaxBranching = 3` (public const).
  - `public static (int[][] Groups, int[] Mains) Group(int count, int branching)`: positions `0..count-1` in span order grouped per spec 3.3; `Mains[g]` is the main position of group `g`; groups ordered by first position.
  - `public static Placement Place(Point3d[] nodes, int[][] bars, int[] anchors, Vector3d[][] across, int[][] perimeterLoops, (int, int)[] netEdges, double ground, double medianPlanEdge, int branching, int groundAsked)`.
  - Classes `Span`, `Tree`, `Level`, `Placement` with the public fields written below.
  - `MouldGeometry.LeanFromVertical(Point3d foot, Point3d top)` (public static, degrees).

No test in this task beyond the gate compiling; Task 2 adds the measured checks. The engine is written whole here because its parts only mean anything together.

- [ ] **Step 1: Add `LeanFromVertical` to `MouldGeometry`**

In `MouldComponents.cs`, directly after the `MaxLeanDegrees` constant (about line 1656, `public const double MaxLeanDegrees = 60.0;`), add:

```csharp
        /// <summary>
        /// How far a member stands off vertical, in degrees.
        ///
        /// Measured from the two ends rather than from a force, because this
        /// is the question the sliding joint asks: not "is the column on its
        /// line of thrust" but "can the mechanism reach this angle".
        /// </summary>
        public static double LeanFromVertical(Point3d foot, Point3d top)
        {
            double rise = top.Z - foot.Z;
            double reach = Math.Sqrt(PlanDistanceSquared(foot, top));
            if (rise <= 1.0e-9)
                return reach <= 1.0e-9 ? 0.0 : 90.0;
            return Math.Atan2(reach, rise) * 180.0 / Math.PI;
        }
```

- [ ] **Step 2: Create `ColumnPlacement.cs`**

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Where the columns stand, as pure arithmetic on arrays.
    ///
    /// Every notch of every principal line is a joint with two steppers and a
    /// column head; nothing is chosen. What is decided here is how the heads
    /// GROUP into trees (Branching) and how the trees reach the GROUND
    /// (Ground), and every rule below is measured by the smoke harness on
    /// hand-built nets, which is why nothing in this file touches a Mesh, a
    /// Curve, or Rhino's native core.
    ///
    /// Order of operations for one Ground level: spans, ring tree, grouping,
    /// feet, fork, members, then the rejection tests. The fork lies ON THE
    /// SEGMENT from its foot to its main notch, so trunk and main branch are
    /// one straight line by construction and a fork can never kink.
    /// </summary>
    internal static class ColumnPlacement
    {
        /// <summary>
        /// Where a tree forks, as a fraction of its main notch's height off
        /// the ground. A constant, not a slider, because it cannot be solved:
        /// on a fixed foot-to-notch segment both minimum load path and force
        /// equilibrium run the fork to the foot and give a fan of full-height
        /// spokes. Frei Otto's trees branch high because their canopies are
        /// wide; notches a metre apart and nearly overhead are not.
        /// </summary>
        public const double ForkFraction = 0.65;

        /// <summary>
        /// How far a TRUNK may stand off the line of the force it carries.
        /// Branches are exempt: a fork-to-neighbour branch under a fork at
        /// two thirds height is routinely forty degrees off a vertical pull,
        /// and that is joint bending the machine takes, not a refusal.
        /// </summary>
        public const double AlignmentDegrees = 30.0;

        /// <summary>Collision clearance as a fraction of the median plan edge.</summary>
        public const double ClearanceFraction = 0.05;

        public const int MaxGround = 4;

        public const int MaxBranching = 3;

        /// <summary>One supported stretch of a bar.</summary>
        public sealed class Span
        {
            public int Bar;
            /// <summary>Bar position of the span's first node.</summary>
            public int First;
            /// <summary>Bar position of the span's last node.</summary>
            public int Last;
            /// <summary>anchor, rim or end.</summary>
            public string FirstKind = "end";
            public string LastKind = "end";
            /// <summary>Bar positions of the notches this span holds, in bar order.</summary>
            public List<int> Free = new();
        }

        /// <summary>One tree: its notches, its main notch, and what it carries.</summary>
        public sealed class Tree
        {
            /// <summary>-1 for the ring tree.</summary>
            public int Bar = -1;
            public int Span = -1;
            /// <summary>Net vertex of every notch, main first.</summary>
            public int[] Nodes = Array.Empty<int>();
            /// <summary>Vertical load per notch, aligned with Nodes.</summary>
            public double[] Load = Array.Empty<double>();
            /// <summary>Sum of the notches' transverse pulls.</summary>
            public Vector3d Resultant;
            /// <summary>Fixed foot, ring tree only.</summary>
            public Point3d? FixedFoot;
            public bool Ring;
        }

        /// <summary>One Ground level, built and judged.</summary>
        public sealed class Level
        {
            public int Ground;
            public bool Feasible = true;
            /// <summary>lean, alignment, member_collision, net_collision, or empty.</summary>
            public string Rule = string.Empty;
            /// <summary>The measured value that refused it.</summary>
            public double Value;
            /// <summary>Sum over members of axial force times length.</summary>
            public double LoadPath;
            public List<Point3d> Nodes = new();
            public List<(int Lower, int Upper)> Members = new();
            /// <summary>Vertical load carried, per member.</summary>
            public List<double> Carried = new();
            /// <summary>Axial demand, per member.</summary>
            public List<double> Axial = new();
            /// <summary>Which tree each member belongs to.</summary>
            public List<int> MemberTree = new();
            /// <summary>Node indices that are feet.</summary>
            public List<int> Feet = new();
            public int FeetMerged;
            public double WorstLean;
            public double WorstAlignment;
            public double WorstBranchOff;
            public int Collisions;
            public int PlumbTrees;
        }

        public sealed class Placement
        {
            public int GroundAsked;
            public int GroundPlaced;
            public Level Built = new();
            public List<Level> Tried = new();
            public List<Span> Spans = new();
            public List<Tree> Trees = new();
            public Tree? RingTree;
            public double Clearance;
        }

        // ------------------------------------------------------------------
        // Grouping

        /// <summary>
        /// Positions 0..count-1, in span order, grouped into trees of
        /// <paramref name="branching"/> consecutive notches. The span splits
        /// into a LEFT half, a CENTRE notch when the count is odd, and a
        /// RIGHT half; each half is grouped from the centre outward so the
        /// remainder, fewer than Branching, sits at the anchor end where the
        /// loads are smallest, and the right half mirrors the left. The
        /// centre notch is a single column: it has no mirror partner, so it
        /// stands outside the pairing rather than pushing everything to one
        /// side. Every position is in exactly one group.
        ///
        /// The MAIN notch of a group is its innermost position, so mirrored
        /// groups have mirrored mains.
        /// </summary>
        public static (int[][] Groups, int[] Mains) Group(int count, int branching)
        {
            branching = Math.Min(Math.Max(branching, 1), MaxBranching);
            var groups = new List<int[]>();
            var mains = new List<int>();
            if (count <= 0)
                return (Array.Empty<int[]>(), Array.Empty<int>());

            int half = count / 2;
            bool odd = (count % 2) == 1;

            // Left half, innermost first, outward to the anchor.
            var left = new List<(int[], int)>();
            int at = half - 1;
            while (at >= 0)
            {
                int size = Math.Min(branching, at + 1);
                int[] notches = Enumerable.Range(at - size + 1, size).ToArray();
                left.Add((notches, at));
                at -= size;
            }
            left.Reverse();
            foreach ((int[] notches, int main) in left)
            {
                groups.Add(notches);
                mains.Add(main);
            }

            if (odd)
            {
                groups.Add(new[] { half });
                mains.Add(half);
            }

            // Right half, the mirror of the left, innermost first.
            at = odd ? half + 1 : half;
            while (at < count)
            {
                int size = Math.Min(branching, count - at);
                groups.Add(Enumerable.Range(at, size).ToArray());
                mains.Add(at);
                at += size;
            }
            return (groups.ToArray(), mains.ToArray());
        }

        // ------------------------------------------------------------------
        // Entry

        /// <summary>
        /// Place the columns for one Result.
        ///
        /// <paramref name="across"/> is, per bar and per bar position, the
        /// transverse pull the net hands that notch (MouldGeometry.BarLoads
        /// then BarTransverse). <paramref name="perimeterLoops"/> are the
        /// boundary loops as net vertex lists; an empty array means no rim
        /// can be detected and no ring tree is placed. <paramref name="netEdges"/>
        /// are the net's members, for the collision tests.
        /// <paramref name="groundAsked"/> is 0 to MaxGround, or -1 for Auto.
        /// </summary>
        public static Placement Place(
            Point3d[] nodes,
            int[][] bars,
            int[] anchors,
            Vector3d[][] across,
            int[][] perimeterLoops,
            (int, int)[] netEdges,
            double ground,
            double medianPlanEdge,
            int branching,
            int groundAsked)
        {
            branching = Math.Min(Math.Max(branching, 1), MaxBranching);
            var anchorSet = new HashSet<int>(anchors);
            double clearance = ClearanceFraction * Math.Max(medianPlanEdge, 1.0e-9);
            var placement = new Placement
            {
                GroundAsked = groundAsked,
                Clearance = clearance,
            };

            var held = new HashSet<int>();
            Tree? ring = RingTree(nodes, bars, anchorSet, across, perimeterLoops, ground, held);
            if (ring is not null)
            {
                placement.RingTree = ring;
                placement.Trees.Add(ring);
            }

            placement.Spans = Spans(bars, anchorSet, held);
            foreach (Span span in placement.Spans)
            {
                // Free notches: everything the span holds that nothing has
                // taken yet. A notch shared with an earlier bar (a crossing)
                // is already held and is skipped; it does not cut the span.
                int[] free = span.Free.Where(p => !held.Contains(bars[span.Bar][p])).ToArray();
                (int[][] groups, int[] mains) = Group(free.Length, branching);
                for (int g = 0; g < groups.Length; g++)
                {
                    int[] positions = groups[g].Select(i => free[i]).ToArray();
                    int mainPosition = free[mains[g]];
                    var ordered = new List<int> { mainPosition };
                    ordered.AddRange(positions.Where(p => p != mainPosition));
                    var tree = new Tree
                    {
                        Bar = span.Bar,
                        Span = placement.Spans.IndexOf(span),
                        Nodes = ordered.Select(p => bars[span.Bar][p]).ToArray(),
                        Load = ordered.Select(p => Math.Abs(across[span.Bar][p].Z)).ToArray(),
                    };
                    Vector3d sum = Vector3d.Zero;
                    foreach (int p in ordered)
                        sum += across[span.Bar][p];
                    tree.Resultant = sum;
                    foreach (int node in tree.Nodes)
                        held.Add(node);
                    placement.Trees.Add(tree);
                }
            }

            if (groundAsked >= 0)
            {
                int start = Math.Min(groundAsked, MaxGround);
                for (int level = start; level >= 0; level--)
                {
                    Level built = BuildLevel(nodes, placement, bars, anchorSet, netEdges, ground, level, clearance, medianPlanEdge);
                    placement.Tried.Add(built);
                    if (built.Feasible || level == 0)
                    {
                        placement.Built = built;
                        placement.GroundPlaced = level;
                        break;
                    }
                }
            }
            else
            {
                Level? best = null;
                for (int level = MaxGround; level >= 0; level--)
                {
                    Level built = BuildLevel(nodes, placement, bars, anchorSet, netEdges, ground, level, clearance, medianPlanEdge);
                    placement.Tried.Add(built);
                    if (built.Feasible && (best is null || built.LoadPath < best.LoadPath))
                        best = built;
                }
                // Nothing feasible at all: level 0 is placed anyway, with its
                // collision reported, because a Result with no columns
                // breaks the chain.
                best ??= placement.Tried[placement.Tried.Count - 1];
                placement.Built = best;
                placement.GroundPlaced = best.Ground;
            }
            return placement;
        }

        // ------------------------------------------------------------------
        // Spans

        /// <summary>
        /// Cut every bar into spans at its anchors and at any notch already
        /// held by the ring tree. A held ring, anchors mid-bar, gives two
        /// half-spans and the ring gets no column because an anchor is never
        /// a head. A bar end that is neither an anchor nor a rim notch is a
        /// free notch of its span (kind "end").
        /// </summary>
        public static List<Span> Spans(int[][] bars, HashSet<int> anchors, HashSet<int> rimHeld)
        {
            var spans = new List<Span>();
            for (int b = 0; b < bars.Length; b++)
            {
                int[] bar = bars[b];
                if (bar.Length < 2)
                    continue;
                var cuts = new List<(int Position, string Kind)>();
                for (int p = 0; p < bar.Length; p++)
                {
                    if (anchors.Contains(bar[p]))
                        cuts.Add((p, "anchor"));
                    else if (rimHeld.Contains(bar[p]))
                        cuts.Add((p, "rim"));
                }
                if (cuts.Count == 0 || cuts[0].Position != 0)
                    cuts.Insert(0, (0, "end"));
                if (cuts[cuts.Count - 1].Position != bar.Length - 1)
                    cuts.Add((bar.Length - 1, "end"));

                for (int c = 0; c + 1 < cuts.Count; c++)
                {
                    (int first, string firstKind) = cuts[c];
                    (int last, string lastKind) = cuts[c + 1];
                    if (last <= first)
                        continue;
                    var span = new Span
                    {
                        Bar = b,
                        First = first,
                        Last = last,
                        FirstKind = firstKind,
                        LastKind = lastKind,
                    };
                    int from = firstKind == "end" ? first : first + 1;
                    int to = lastKind == "end" ? last : last - 1;
                    for (int p = from; p <= to; p++)
                        span.Free.Add(p);
                    if (span.Free.Count > 0)
                        spans.Add(span);
                }
            }
            return spans;
        }

        // ------------------------------------------------------------------
        // Ring tree

        /// <summary>
        /// A bar END is a free-rim end when its node is not an anchor and lies
        /// on a perimeter loop that holds no anchor. With rim ends on at least
        /// two bars, one tree serves them all: its foot is the plan point
        /// nearest every bar's end tangent line at once (the least-squares
        /// intersection), and it holds each bar's rim notch. Those notches are
        /// marked held so the spans end at them.
        /// </summary>
        public static Tree? RingTree(
            Point3d[] nodes,
            int[][] bars,
            HashSet<int> anchors,
            Vector3d[][] across,
            int[][] perimeterLoops,
            double ground,
            HashSet<int> held)
        {
            var freeLoopNodes = new HashSet<int>();
            foreach (int[] loop in perimeterLoops)
            {
                if (loop.Any(anchors.Contains))
                    continue;
                foreach (int node in loop)
                    freeLoopNodes.Add(node);
            }
            if (freeLoopNodes.Count == 0)
                return null;

            var rim = new List<(int Bar, int Position)>();
            for (int b = 0; b < bars.Length; b++)
            {
                int[] bar = bars[b];
                if (bar.Length < 2)
                    continue;
                if (!anchors.Contains(bar[0]) && freeLoopNodes.Contains(bar[0]))
                    rim.Add((b, 0));
                int last = bar.Length - 1;
                if (!anchors.Contains(bar[last]) && freeLoopNodes.Contains(bar[last]))
                    rim.Add((b, last));
            }
            if (rim.Select(r => r.Bar).Distinct().Count() < 2)
                return null;

            // Least-squares intersection of the end tangents in plan:
            // minimise sum |(I - d d^T)(x - p)|^2 over x.
            double a11 = 0.0, a12 = 0.0, a22 = 0.0, b1 = 0.0, b2 = 0.0;
            foreach ((int b, int p) in rim)
            {
                int[] bar = bars[b];
                int inner = p == 0 ? 1 : p - 1;
                double dx = nodes[bar[p]].X - nodes[bar[inner]].X;
                double dy = nodes[bar[p]].Y - nodes[bar[inner]].Y;
                double length = Math.Sqrt((dx * dx) + (dy * dy));
                if (length <= 1.0e-12)
                    continue;
                dx /= length;
                dy /= length;
                double m11 = 1.0 - (dx * dx);
                double m12 = -dx * dy;
                double m22 = 1.0 - (dy * dy);
                double px = nodes[bar[p]].X;
                double py = nodes[bar[p]].Y;
                a11 += m11;
                a12 += m12;
                a22 += m22;
                b1 += (m11 * px) + (m12 * py);
                b2 += (m12 * px) + (m22 * py);
            }
            double det = (a11 * a22) - (a12 * a12);
            double trace = a11 + a22;
            Point3d foot;
            if (Math.Abs(det) > 1.0e-9 * Math.Max(trace * trace, 1.0e-12))
            {
                double x = ((a22 * b1) - (a12 * b2)) / det;
                double y = ((a11 * b2) - (a12 * b1)) / det;
                foot = new Point3d(x, y, ground);
            }
            else
            {
                // Parallel tangents never meet: stand under the rim's centre.
                double sx = rim.Sum(r => nodes[bars[r.Bar][r.Position]].X);
                double sy = rim.Sum(r => nodes[bars[r.Bar][r.Position]].Y);
                foot = new Point3d(sx / rim.Count, sy / rim.Count, ground);
            }

            // Main notch: the rim notch nearest the foot in plan.
            (int Bar, int Position) main = rim
                .OrderBy(r => MouldGeometry.PlanDistanceSquared(foot, nodes[bars[r.Bar][r.Position]]))
                .First();
            var ordered = new List<(int Bar, int Position)> { main };
            ordered.AddRange(rim.Where(r => r != main));
            var tree = new Tree
            {
                Ring = true,
                FixedFoot = foot,
                Nodes = ordered.Select(r => bars[r.Bar][r.Position]).ToArray(),
                Load = ordered.Select(r => Math.Abs(across[r.Bar][r.Position].Z)).ToArray(),
            };
            Vector3d sum = Vector3d.Zero;
            foreach ((int b, int p) in ordered)
                sum += across[b][p];
            tree.Resultant = sum;
            foreach (int node in tree.Nodes)
                held.Add(node);
            return tree;
        }

        // ------------------------------------------------------------------
        // One level

        private static Level BuildLevel(
            Point3d[] nodes,
            Placement placement,
            int[][] bars,
            HashSet<int> anchors,
            (int, int)[] netEdges,
            double ground,
            int level,
            double clearance,
            double medianPlanEdge)
        {
            var result = new Level { Ground = level };
            List<Tree> trees = placement.Trees;
            var foot = new Point3d[trees.Count];
            var plumb = new bool[trees.Count];
            var aim = new Vector3d[trees.Count];

            for (int t = 0; t < trees.Count; t++)
            {
                Vector3d supply = -trees[t].Resultant;
                plumb[t] = supply.Z <= 1.0e-9;
                aim[t] = MouldGeometry.AimFrom(trees[t].Resultant);
            }

            if (level == 0)
            {
                // Each tree stands on its own foot, on the line of the force
                // it carries. AimFrom caps the lean, so this is never refused.
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is Point3d fixedFoot)
                    {
                        foot[t] = fixedFoot;
                        continue;
                    }
                    Point3d main = nodes[trees[t].Nodes[0]];
                    double rise = Math.Max(main.Z - ground, 0.0);
                    double along = rise / Math.Max(aim[t].Z, 1.0e-9);
                    foot[t] = new Point3d(
                        main.X - (aim[t].X * along),
                        main.Y - (aim[t].Y * along),
                        ground);
                }
            }
            else
            {
                // N bands per span about its own midpoint, by plan position
                // along the chord; a band's foot is the plan centre (midpoint
                // of the extremes) of the main notches it carries. Mirrored
                // trees land in mirrored bands, so an odd count gets a
                // genuinely central band and the centre never drifts.
                var bandMains = new Dictionary<(int Span, int Band), List<int>>();
                for (int t = 0; t < trees.Count; t++)
                {
                    Tree tree = trees[t];
                    if (tree.FixedFoot is Point3d fixedFoot)
                    {
                        foot[t] = fixedFoot;
                        continue;
                    }
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
                    int band = Math.Min(Math.Max((int)Math.Floor(s * level), 0), level - 1);
                    if (!bandMains.TryGetValue((tree.Span, band), out List<int>? list))
                    {
                        list = new List<int>();
                        bandMains[(tree.Span, band)] = list;
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
            }

            // Feet closer than the clearance are one foot, at their plan
            // centre. Ground 1 on two crossing bars puts a foot at each bar's
            // midpoint, which is the crossing, and they merge here.
            int[] footIndex = MergeFeet(foot, clearance, result.Nodes, out int merged);
            result.FeetMerged = merged;
            for (int i = 0; i < result.Nodes.Count; i++)
                result.Feet.Add(i);

            // Members. Trunk foot to fork, main branch fork to main notch,
            // branches fork to the other notches; a single notch is one member
            // foot to notch. Every member lower end first.
            for (int t = 0; t < trees.Count; t++)
            {
                Tree tree = trees[t];
                int footNode = footIndex[t];
                Point3d footPoint = result.Nodes[footNode];
                Point3d main = nodes[tree.Nodes[0]];
                double total = tree.Load.Sum();
                int mainNode = AddNode(result.Nodes, main);
                if (tree.Nodes.Length == 1)
                {
                    AddMember(result, footNode, mainNode, total, t);
                    continue;
                }
                var fork = new Point3d(
                    footPoint.X + ((main.X - footPoint.X) * ForkFraction),
                    footPoint.Y + ((main.Y - footPoint.Y) * ForkFraction),
                    footPoint.Z + ((main.Z - footPoint.Z) * ForkFraction));
                int forkNode = AddNode(result.Nodes, fork);
                AddMember(result, footNode, forkNode, total, t);
                AddMember(result, forkNode, mainNode, tree.Load[0], t);
                for (int k = 1; k < tree.Nodes.Length; k++)
                {
                    int notch = AddNode(result.Nodes, nodes[tree.Nodes[k]]);
                    AddMember(result, forkNode, notch, tree.Load[k], t);
                }
            }

            // Judge it. Trunks are the members leaving a foot.
            double worstLean = 0.0;
            double worstAlign = 0.0;
            double worstBranchOff = 0.0;
            var footSet = new HashSet<int>(result.Feet);
            for (int m = 0; m < result.Members.Count; m++)
            {
                (int lower, int upper) = result.Members[m];
                Point3d a = result.Nodes[lower];
                Point3d b = result.Nodes[upper];
                int t = result.MemberTree[m];
                Vector3d direction = b - a;
                if (footSet.Contains(lower))
                {
                    worstLean = Math.Max(worstLean, MouldGeometry.LeanFromVertical(a, b));
                    worstAlign = Math.Max(worstAlign, AngleBetween(direction, aim[t]));
                }
                else
                {
                    // A branch: how far off the push its own notch asks for,
                    // which is plumb once the along-bar part has gone to the
                    // anchors, scaled by that notch's vertical load.
                    int k = Array.FindIndex(
                        trees[t].Nodes, n => nodes[n].DistanceToSquared(b) <= 1.0e-18);
                    Vector3d pull = k >= 0
                        ? MouldGeometry.AimFrom(new Vector3d(0.0, 0.0, -trees[t].Load[k]))
                        : aim[t];
                    worstBranchOff = Math.Max(worstBranchOff, AngleBetween(direction, pull));
                }
            }
            result.WorstLean = worstLean;
            result.WorstAlignment = worstAlign;
            result.WorstBranchOff = worstBranchOff;
            result.PlumbTrees = plumb.Count(p => p);
            result.Collisions = CountCollisions(result, nodes, anchors, netEdges, clearance, medianPlanEdge);
            result.LoadPath = 0.0;
            for (int m = 0; m < result.Members.Count; m++)
            {
                (int lower, int upper) = result.Members[m];
                result.LoadPath += result.Axial[m] * result.Nodes[lower].DistanceTo(result.Nodes[upper]);
            }

            if (level > 0)
            {
                if (worstLean > MouldGeometry.MaxLeanDegrees + 1.0e-9)
                    Refuse(result, "lean", worstLean);
                else if (worstAlign > AlignmentDegrees + 1.0e-9)
                    Refuse(result, "alignment", worstAlign);
                else if (result.Collisions > 0)
                    Refuse(result, "collision", result.Collisions);
            }
            else if (result.Collisions > 0)
            {
                // Level 0 is placed regardless; the collision is reported.
                result.Feasible = false;
                result.Rule = "collision";
                result.Value = result.Collisions;
            }
            return result;
        }

        private static void Refuse(Level level, string rule, double value)
        {
            level.Feasible = false;
            level.Rule = rule;
            level.Value = value;
        }

        private static int AddNode(List<Point3d> nodes, Point3d point)
        {
            nodes.Add(point);
            return nodes.Count - 1;
        }

        private static void AddMember(Level level, int lower, int upper, double carried, int tree)
        {
            Point3d a = level.Nodes[lower];
            Point3d b = level.Nodes[upper];
            Vector3d v = b - a;
            double length = v.Length;
            double cos = length > 1.0e-12 ? Math.Abs(v.Z) / length : 1.0;
            level.Members.Add((lower, upper));
            level.Carried.Add(carried);
            level.Axial.Add(cos > 1.0e-6 ? carried / cos : carried);
            level.MemberTree.Add(tree);
        }

        /// <summary>
        /// Weld feet closer than the clearance in plan into one node each,
        /// at the plan centre of the feet it replaces. Returns, per tree,
        /// the node index of its foot; the feet are the first nodes added.
        /// </summary>
        private static int[] MergeFeet(Point3d[] foot, double clearance, List<Point3d> nodes, out int merged)
        {
            int n = foot.Length;
            var parent = Enumerable.Range(0, n).ToArray();
            int Find(int i)
            {
                while (parent[i] != i)
                {
                    parent[i] = parent[parent[i]];
                    i = parent[i];
                }
                return i;
            }
            double squared = clearance * clearance;
            for (int i = 0; i < n; i++)
            {
                for (int j = i + 1; j < n; j++)
                {
                    if (MouldGeometry.PlanDistanceSquared(foot[i], foot[j]) <= squared)
                        parent[Find(i)] = Find(j);
                }
            }
            var clusterNode = new Dictionary<int, int>();
            var clusterMembers = new Dictionary<int, List<int>>();
            for (int i = 0; i < n; i++)
            {
                int root = Find(i);
                if (!clusterMembers.TryGetValue(root, out List<int>? list))
                {
                    list = new List<int>();
                    clusterMembers[root] = list;
                }
                list.Add(i);
            }
            var footIndex = new int[n];
            merged = 0;
            foreach ((int root, List<int> members) in clusterMembers)
            {
                double x = members.Average(i => foot[i].X);
                double y = members.Average(i => foot[i].Y);
                double z = members.Average(i => foot[i].Z);
                nodes.Add(new Point3d(x, y, z));
                clusterNode[root] = nodes.Count - 1;
                // Distinct positions that merged, so two trees already
                // sharing one band's foot do not count as a merge.
                int distinct = members
                    .Select(i => (Math.Round(foot[i].X, 9), Math.Round(foot[i].Y, 9)))
                    .Distinct()
                    .Count();
                merged += Math.Max(distinct - 1, 0);
            }
            for (int i = 0; i < n; i++)
                footIndex[i] = clusterNode[Find(i)];
            return footIndex;
        }

        // ------------------------------------------------------------------
        // Collisions

        /// <summary>
        /// Two members that share no end and come closer than the clearance
        /// collide. A member whose interior comes closer than the clearance
        /// to a net cable it does not end on, or rises above the nearest
        /// interior net vertex in plan by more than the clearance, collides
        /// with the net. Anchors are left out of the height test because
        /// they sit on the ground and a foot beside one is not through the
        /// net.
        /// </summary>
        public static int CountCollisions(
            Level level,
            Point3d[] netNodes,
            HashSet<int> anchors,
            (int, int)[] netEdges,
            double clearance,
            double medianPlanEdge)
        {
            int collisions = 0;
            int count = level.Members.Count;
            for (int i = 0; i < count; i++)
            {
                (int a1, int a2) = level.Members[i];
                for (int j = i + 1; j < count; j++)
                {
                    (int b1, int b2) = level.Members[j];
                    if (a1 == b1 || a1 == b2 || a2 == b1 || a2 == b2)
                        continue;
                    double d = SegmentDistance(
                        level.Nodes[a1], level.Nodes[a2], level.Nodes[b1], level.Nodes[b2]);
                    if (d < clearance)
                        collisions++;
                }
            }

            int[] interior = Enumerable.Range(0, netNodes.Length)
                .Where(i => !anchors.Contains(i)).ToArray();
            double nearBy = 0.5 * medianPlanEdge;
            double nearBySquared = nearBy * nearBy;
            for (int m = 0; m < count; m++)
            {
                (int lower, int upper) = level.Members[m];
                Point3d a = level.Nodes[lower];
                Point3d b = level.Nodes[upper];
                int ownNotch = NearestNetNode(b, netNodes);
                bool hit = false;
                for (int s = 1; s <= 7 && !hit; s++)
                {
                    double t = s / 8.0;
                    var p = new Point3d(
                        a.X + ((b.X - a.X) * t),
                        a.Y + ((b.Y - a.Y) * t),
                        a.Z + ((b.Z - a.Z) * t));
                    foreach ((int u, int v) in netEdges)
                    {
                        if (u == ownNotch || v == ownNotch)
                            continue;
                        if (PointSegmentDistance(p, netNodes[u], netNodes[v]) < clearance)
                        {
                            hit = true;
                            break;
                        }
                    }
                    if (hit)
                        break;
                    int nearest = -1;
                    double best = double.MaxValue;
                    foreach (int i in interior)
                    {
                        if (i == ownNotch)
                            continue;
                        double d2 = MouldGeometry.PlanDistanceSquared(p, netNodes[i]);
                        if (d2 < best)
                        {
                            best = d2;
                            nearest = i;
                        }
                    }
                    if (nearest >= 0 && best <= nearBySquared &&
                        p.Z > netNodes[nearest].Z + clearance)
                    {
                        hit = true;
                    }
                }
                if (hit)
                    collisions++;
            }
            return collisions;
        }

        private static int NearestNetNode(Point3d point, Point3d[] netNodes)
        {
            int best = -1;
            double bestDistance = double.MaxValue;
            for (int i = 0; i < netNodes.Length; i++)
            {
                double d = point.DistanceToSquared(netNodes[i]);
                if (d < bestDistance)
                {
                    bestDistance = d;
                    best = i;
                }
            }
            return bestDistance <= 1.0e-12 ? best : -1;
        }

        /// <summary>Closest distance between two segments.</summary>
        public static double SegmentDistance(Point3d p1, Point3d q1, Point3d p2, Point3d q2)
        {
            Vector3d d1 = q1 - p1;
            Vector3d d2 = q2 - p2;
            Vector3d r = p1 - p2;
            double a = Dot(d1, d1);
            double e = Dot(d2, d2);
            double f = Dot(d2, r);
            double s;
            double t;
            const double eps = 1.0e-12;
            if (a <= eps && e <= eps)
                return r.Length;
            if (a <= eps)
            {
                s = 0.0;
                t = Clamp(f / e);
            }
            else
            {
                double c = Dot(d1, r);
                if (e <= eps)
                {
                    t = 0.0;
                    s = Clamp(-c / a);
                }
                else
                {
                    double b = Dot(d1, d2);
                    double denom = (a * e) - (b * b);
                    s = denom > eps ? Clamp(((b * f) - (c * e)) / denom) : 0.0;
                    t = ((b * s) + f) / e;
                    if (t < 0.0)
                    {
                        t = 0.0;
                        s = Clamp(-c / a);
                    }
                    else if (t > 1.0)
                    {
                        t = 1.0;
                        s = Clamp((b - c) / a);
                    }
                }
            }
            Point3d c1 = p1 + (d1 * s);
            Point3d c2 = p2 + (d2 * t);
            return c1.DistanceTo(c2);
        }

        private static double PointSegmentDistance(Point3d p, Point3d a, Point3d b)
        {
            Vector3d ab = b - a;
            double len2 = Dot(ab, ab);
            if (len2 <= 1.0e-18)
                return p.DistanceTo(a);
            double t = Clamp(Dot(p - a, ab) / len2);
            return p.DistanceTo(a + (ab * t));
        }

        private static double Clamp(double v) => Math.Min(Math.Max(v, 0.0), 1.0);

        private static double Dot(Vector3d a, Vector3d b) =>
            (a.X * b.X) + (a.Y * b.Y) + (a.Z * b.Z);

        /// <summary>The angle between two vectors, in degrees.</summary>
        public static double AngleBetween(Vector3d a, Vector3d b)
        {
            double la = a.Length;
            double lb = b.Length;
            if (la <= 1.0e-12 || lb <= 1.0e-12)
                return 0.0;
            double cosine = Dot(a, b) / (la * lb);
            cosine = Math.Min(Math.Max(cosine, -1.0), 1.0);
            return Math.Acos(cosine) * 180.0 / Math.PI;
        }
    }
}
```

- [ ] **Step 3: Run the gate**

Expected: build 0 warnings (the new file compiles; nothing calls it yet, which is not a warning), harness unchanged and green.

- [ ] **Step 4: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "plugin/native_v02/Components/MouldComponents.cs"
git -C $repo commit -m "feat(columns): ColumnPlacement, the pure engine that holds every notch and foots the trees by rule"
```

---

### Task 2: The engine's measured checks

**Files:**
- Test: `tests/native_smoke/Program.cs` (new try block after the `ValidateRegisteredMappingWins` block, which ends at about line 613; new check methods next to `ValidateColumnAim`, about line 2219)

**Interfaces:**
- Consumes: `ColumnPlacement.Group`, `ColumnPlacement.Place`, `ColumnPlacement.SegmentDistance`, the `Placement`/`Level` fields, `ColumnPlacement.ForkFraction`, `MouldGeometry.MaxLeanDegrees`, all from Task 1.

- [ ] **Step 1: Register the check**

After the `ValidateRegisteredMappingWins` try/catch block add:

```csharp
        try
        {
            ValidateColumnPlacement(plugin);
            Console.WriteLine(
                "PASS  ColumnPlacement: nine notches at Branching 2 group into a "
                + "centre single and four mirrored pairs with mirrored mains, "
                + "eight at Branching 3 into two triples and a single at each "
                + "anchor end; the fork lies on the foot-to-main segment at "
                + "65% height with trunk and main branch collinear; a shallow "
                + "arch asked for one central foot REFUSES it on lean and "
                + "records asked 1, placed 0; a symmetric arch puts its one "
                + "foot on the span centre within a hundredth of the span; "
                + "mid-bar anchors give half-spans and no head; two bars "
                + "ending on an anchor-free rim get one ring tree at their "
                + "tangents' plan intersection; a crossing node is held once; "
                + "the segment distance and the net test refuse what they "
                + "should; Auto picks the shorter load path.");
        }
        catch (Exception exception)
        {
            failures.Add($"ColumnPlacement: {DescribeException(exception)}");
        }
```

- [ ] **Step 2: Write the check**

Next to `ValidateColumnAim` add. It builds every net by hand; `point3d` and `vector3d` are the plugin's RhinoCommon types resolved through a method parameter type, exactly as `ValidateStiffnessSeparation` does today.

```csharp
    /// <summary>
    /// <c>ColumnPlacement</c>, the engine that replaced the beam search:
    /// every rule of spec section 3, driven on hand-built nets. A net here is
    /// an arch of notches in the XZ plane, anchored at both ends, with a
    /// vertical pull on every notch; that is enough to measure grouping,
    /// feet, fork, rejection and Auto, and it is the case Param's three
    /// screenshots were of.
    /// </summary>
    private static void ValidateColumnPlacement(Assembly plugin)
    {
        Type engine = plugin.GetType(
            "Ananke.COMPAS.Native.Components.ColumnPlacement", throwOnError: true)!;
        MethodInfo group = RequirePublicStatic(engine, "Group");
        MethodInfo place = RequirePublicStatic(engine, "Place");
        MethodInfo segment = RequirePublicStatic(engine, "SegmentDistance");
        Type point3d = place.GetParameters()[0].ParameterType.GetElementType()!;
        Type vector3d = place.GetParameters()[3].ParameterType.GetElementType()!.GetElementType()!;
        double forkFraction = (double)engine.GetField("ForkFraction")!.GetValue(null)!;
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        double maxLean = (double)geometry.GetField("MaxLeanDegrees")!.GetValue(null)!;

        // ---- Grouping.
        (int[][] Groups, int[] Mains) Grouped(int count, int branching)
        {
            object result = group.Invoke(null, new object?[] { count, branching })!;
            Type type = result.GetType();
            return (
                (int[][])type.GetField("Item1")!.GetValue(result)!,
                (int[])type.GetField("Item2")!.GetValue(result)!);
        }
        string Show(int[][] groups) => string.Join(" ", groups.Select(g => "[" + string.Join(",", g) + "]"));

        (int[][] nine, int[] nineMains) = Grouped(9, 2);
        string nineText = Show(nine);
        if (nineText != "[0,1] [2,3] [4] [5,6] [7,8]")
            throw new InvalidOperationException($"Nine notches at Branching 2 must be a centre single and four mirrored pairs; got {nineText}.");
        if (!nineMains.SequenceEqual(new[] { 1, 3, 4, 5, 7 }))
            throw new InvalidOperationException($"Mains must be the innermost notch of each group, mirrored; got [{string.Join(",", nineMains)}].");
        (int[][] eight, _) = Grouped(8, 3);
        string eightText = Show(eight);
        if (eightText != "[0] [1,2,3] [4,5,6] [7]")
            throw new InvalidOperationException($"Eight notches at Branching 3 must be two triples with a single at each anchor end; got {eightText}.");
        (int[][] five, _) = Grouped(5, 1);
        if (five.Length != 5 || five.Any(g => g.Length != 1))
            throw new InvalidOperationException($"Five notches at Branching 1 are five singles; got {Show(five)}.");
        (int[][] none, _) = Grouped(0, 2);
        if (none.Length != 0)
            throw new InvalidOperationException("No notches group into nothing.");

        // ---- A hand-built arch.
        // count notches from x = 0 to x = width, z = rise * 4 * s * (1 - s),
        // anchored at both ends, every notch pulled straight down by `load`.
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        object V(double x, double y, double z) => Activator.CreateInstance(vector3d, x, y, z)!;

        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Arch(int count, double width, double rise, double load)
        {
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            for (int i = 0; i < count; i++)
            {
                double s = (double)i / (count - 1);
                nodes.SetValue(P(width * s, 0.0, rise * 4.0 * s * (1.0 - s)), i);
                acrossBar.SetValue(V(0.0, 0.0, -load), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }

        object Run((Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net, int[][] loops, double median, int branching, int ground)
        {
            return place.Invoke(null, new object?[]
            {
                net.Nodes, net.Bars, net.Anchors, net.Across, loops, net.Edges, 0.0, median, branching, ground,
            })!;
        }
        T Get<T>(object o, string name)
        {
            Type type = o.GetType();
            object value = type.GetField(name)?.GetValue(o) ?? type.GetProperty(name)?.GetValue(o)
                ?? throw new InvalidOperationException($"{type.Name} has no {name}.");
            return (T)value;
        }
        double X(object p) => (double)point3d.GetProperty("X")!.GetValue(p)!;
        double Y(object p) => (double)point3d.GetProperty("Y")!.GetValue(p)!;
        double Z(object p) => (double)point3d.GetProperty("Z")!.GetValue(p)!;

        // ---- Fork on the segment, collinear. Rise five over eight so the
        // outer trunks stay inside the cap when this arch is reused below.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 2, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var members = ((IEnumerable)Get<object>(built, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!, (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToHashSet();
            if (members.Any(m => Z(nodes[m.Item1]) > Z(nodes[m.Item2]) + 1.0e-9))
                throw new InvalidOperationException("Every member must leave the engine lower end first.");
            int forks = 0;
            foreach ((int lower, int upper) in members)
            {
                if (!feet.Contains(lower))
                    continue;
                // A trunk. Its upper end is a fork when something leaves it.
                var above = members.Where(m => m.Item1 == upper).ToArray();
                if (above.Length == 0)
                    continue;
                forks++;
                object foot = nodes[lower];
                object fork = nodes[upper];
                // The main branch is the one collinear with the trunk.
                double bestAngle = double.MaxValue;
                object? main = null;
                foreach ((int _, int notch) in above)
                {
                    double angle = AngleDeg(
                        X(fork) - X(foot), Y(fork) - Y(foot), Z(fork) - Z(foot),
                        X(nodes[notch]) - X(fork), Y(nodes[notch]) - Y(fork), Z(nodes[notch]) - Z(fork));
                    if (angle < bestAngle)
                    {
                        bestAngle = angle;
                        main = nodes[notch];
                    }
                }
                if (bestAngle > 0.5)
                    throw new InvalidOperationException($"Trunk and main branch must be collinear within 0.5 degrees; a fork kinks by {bestAngle:0.###}.");
                double expectedZ = Z(foot) + ((Z(main!) - Z(foot)) * forkFraction);
                if (Math.Abs(Z(fork) - expectedZ) > 1.0e-9)
                    throw new InvalidOperationException($"The fork must sit at {forkFraction:0.##} of the main notch height; it sits at z {Z(fork):0.###} against {expectedZ:0.###}.");
            }
            if (forks < 2)
                throw new InvalidOperationException($"Nine notches at Branching 2 must build forked trees; {forks} forks found.");
        }

        // ---- The wide arch refuses one central foot.
        {
            var wide = Arch(13, 12.0, 2.0, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 1);
            int asked = Get<int>(placed, "GroundAsked");
            int got = Get<int>(placed, "GroundPlaced");
            if (asked != 1 || got != 0)
                throw new InvalidOperationException($"A shallow arch twelve wide asked for one foot must fall back to standalone; asked {asked}, placed {got}.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            object first = tried[0];
            if (Get<int>(first, "Ground") != 1 || Get<bool>(first, "Feasible") || Get<string>(first, "Rule") != "lean")
                throw new InvalidOperationException("Level 1 must be recorded as refused on lean.");
            if (Get<double>(first, "Value") <= maxLean)
                throw new InvalidOperationException("The refusing lean must exceed the cap.");
        }

        // ---- The centred foot, odd and even counts.
        foreach (int count in new[] { 9, 8 })
        {
            var arch = Arch(count, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 1);
            if (Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"A rise-five arch eight wide holds one central foot; {count} notches fell back.");
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 1)
                throw new InvalidOperationException($"Ground 1 on one bar is one foot; {feet.Length} built with {count} notches.");
            double off = Math.Abs(X(nodes[feet[0]]) - 4.0);
            if (off > 0.08)
                throw new InvalidOperationException($"The one foot must stand on the span's plan centre within a hundredth of the span; it is {off:0.####} off with {count} notches. This is Param's off-centre foot, refused.");
        }

        // ---- A held ring: mid-bar anchors cut the bar and are never heads.
        // Anchors at 0, 3, 5 and 8 on nine notches leave three spans: 1..2,
        // the single notch 4 between two anchors, and 6..7.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            var held = (arch.Nodes, arch.Bars, new[] { 0, 3, 5, 8 }, arch.Across, arch.Edges);
            object placed = Run(held, Array.Empty<int[]>(), 1.0, 1, 0);
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 3)
                throw new InvalidOperationException($"Anchors at 0, 3, 5 and 8 cut a nine-notch bar into three spans; got {spans.Length}.");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var headNodes = trees.SelectMany(t => ((int[])Get<object>(t, "Nodes"))).ToArray();
            if (headNodes.Any(h => h == 0 || h == 3 || h == 5 || h == 8))
                throw new InvalidOperationException("An anchor is never a head.");
            if (headNodes.Length != 5)
                throw new InvalidOperationException($"Five free notches must all be held; {headNodes.Length} heads built.");
        }

        // ---- A free rim: two bars ending on an anchor-free loop.
        {
            // Bar 0 along +x from an anchor at x=-4 to a rim notch at x=-1;
            // bar 1 along +y from an anchor at y=-4 to a rim notch at y=-1.
            // The hole's rim is the loop {2, 5, 6}; node 6 is a spare rim node.
            Array nodes = Array.CreateInstance(point3d, 7);
            nodes.SetValue(P(-4.0, 0.0, 0.0), 0);
            nodes.SetValue(P(-2.5, 0.0, 2.0), 1);
            nodes.SetValue(P(-1.0, 0.0, 3.0), 2);
            nodes.SetValue(P(0.0, -4.0, 0.0), 3);
            nodes.SetValue(P(0.0, -2.5, 2.0), 4);
            nodes.SetValue(P(0.0, -1.0, 3.0), 5);
            nodes.SetValue(P(1.0, 1.0, 3.0), 6);
            Array acrossA = Array.CreateInstance(vector3d, 3);
            Array acrossB = Array.CreateInstance(vector3d, 3);
            for (int i = 0; i < 3; i++)
            {
                acrossA.SetValue(V(0.0, 0.0, -1.0), i);
                acrossB.SetValue(V(0.0, 0.0, -1.0), i);
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(acrossA, 0);
            across.SetValue(acrossB, 1);
            var net = (nodes, new[] { new[] { 0, 1, 2 }, new[] { 3, 4, 5 } }, new[] { 0, 3 }, across, new[] { (0, 1), (1, 2), (3, 4), (4, 5), (2, 6), (5, 6), (2, 5) });
            object placed = Run(net, new[] { new[] { 2, 5, 6 } }, 1.5, 1, 0);
            object? ring = Get<object?>(placed, "RingTree");
            if (ring is null)
                throw new InvalidOperationException("Two bars ending on an anchor-free rim must get a ring tree.");
            object foot = Get<object>(ring, "FixedFoot");
            if (Math.Abs(X(foot)) > 0.04 || Math.Abs(Y(foot)) > 0.04)
                throw new InvalidOperationException($"The ring foot is the plan intersection of the end tangents, the origin here within a hundredth of the span; it is at ({X(foot):0.###}, {Y(foot):0.###}).");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var allHeads = trees.SelectMany(t => (int[])Get<object>(t, "Nodes")).ToArray();
            if (allHeads.Count(h => h == 2) != 1 || allHeads.Count(h => h == 5) != 1)
                throw new InvalidOperationException("Each rim notch is held exactly once, by the ring tree.");
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Any(s => Get<string>(s, "LastKind") != "rim" && Get<string>(s, "FirstKind") != "rim"))
                throw new InvalidOperationException("Every span on these bars ends at the rim notch.");
        }

        // ---- A crossing: the shared node is held once, by the lower bar.
        {
            Array nodes = Array.CreateInstance(point3d, 9);
            // Bar 0 along x through the crossing at index 2; bar 1 along y
            // through the same node.
            nodes.SetValue(P(-4.0, 0.0, 0.0), 0);
            nodes.SetValue(P(-2.0, 0.0, 2.0), 1);
            nodes.SetValue(P(0.0, 0.0, 3.0), 2);
            nodes.SetValue(P(2.0, 0.0, 2.0), 3);
            nodes.SetValue(P(4.0, 0.0, 0.0), 4);
            nodes.SetValue(P(0.0, -4.0, 0.0), 5);
            nodes.SetValue(P(0.0, -2.0, 2.0), 6);
            nodes.SetValue(P(0.0, 2.0, 2.0), 7);
            nodes.SetValue(P(0.0, 4.0, 0.0), 8);
            Array acrossA = Array.CreateInstance(vector3d, 5);
            Array acrossB = Array.CreateInstance(vector3d, 5);
            for (int i = 0; i < 5; i++)
            {
                acrossA.SetValue(V(0.0, 0.0, -1.0), i);
                acrossB.SetValue(V(0.0, 0.0, -1.0), i);
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(acrossA, 0);
            across.SetValue(acrossB, 1);
            var net = (nodes, new[] { new[] { 0, 1, 2, 3, 4 }, new[] { 5, 6, 2, 7, 8 } }, new[] { 0, 4, 5, 8 }, across,
                new[] { (0, 1), (1, 2), (2, 3), (3, 4), (5, 6), (6, 2), (2, 7), (7, 8) });
            object placed = Run(net, Array.Empty<int[]>(), 2.0, 1, 1);
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var heads = trees.SelectMany(t => (int[])Get<object>(t, "Nodes")).ToArray();
            if (heads.Count(h => h == 2) != 1)
                throw new InvalidOperationException($"The crossing node is held exactly once; it is held {heads.Count(h => h == 2)} times.");
            object owner = trees.First(t => ((int[])Get<object>(t, "Nodes")).Contains(2));
            if (Get<int>(owner, "Bar") != 0)
                throw new InvalidOperationException("The crossing belongs to the lower-indexed bar.");
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 2)
                throw new InvalidOperationException($"A crossing does not cut a span: two bars give two spans, got {spans.Length}.");
            object built = Get<object>(placed, "Built");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (Get<int>(placed, "GroundPlaced") == 1 && feet.Length != 1)
                throw new InvalidOperationException($"Ground 1 on a cross merges the two midpoint feet into one; {feet.Length} built.");
        }

        // ---- The segment distance.
        {
            double D(double[] a, double[] b, double[] c, double[] d) =>
                (double)segment.Invoke(null, new[] { P(a[0], a[1], a[2]), P(b[0], b[1], b[2]), P(c[0], c[1], c[2]), P(d[0], d[1], d[2]) })!;
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 0.0, 0.5, 0.0 }, new[] { 1.0, 0.5, 0.0 }) - 0.5) > 1.0e-9)
                throw new InvalidOperationException("Parallel unit segments half a unit apart are half a unit apart.");
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 0.5, -1.0, 0.2 }, new[] { 0.5, 1.0, 0.2 }) - 0.2) > 1.0e-9)
                throw new InvalidOperationException("A segment crossing over another at height 0.2 is 0.2 away.");
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 3.0, 0.0, 0.0 }, new[] { 4.0, 0.0, 0.0 }) - 2.0) > 1.0e-9)
                throw new InvalidOperationException("Collinear segments two apart are two apart.");
        }

        // ---- Auto picks the shorter load path where both are feasible.
        {
            // A steep, narrow arch: one central foot is feasible and shorter
            // than five standalone posts leaning out to their own feet.
            var arch = Arch(5, 3.0, 3.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 0.75, 1, -1);
            if (Get<int>(placed, "GroundAsked") != -1)
                throw new InvalidOperationException("Auto records GroundAsked as -1.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            var feasible = tried.Where(t => Get<bool>(t, "Feasible")).ToArray();
            if (feasible.Length < 2)
                throw new InvalidOperationException($"This arch must offer at least two feasible levels for Auto to choose between; {feasible.Length} were.");
            object bestTried = feasible.OrderBy(t => Get<double>(t, "LoadPath")).First();
            if (Get<int>(placed, "GroundPlaced") != Get<int>(bestTried, "Ground"))
                throw new InvalidOperationException("Auto must place the feasible level with the least load path.");
        }
    }

    private static double AngleDeg(double ax, double ay, double az, double bx, double by, double bz)
    {
        double la = Math.Sqrt((ax * ax) + (ay * ay) + (az * az));
        double lb = Math.Sqrt((bx * bx) + (by * by) + (bz * bz));
        if (la <= 1.0e-12 || lb <= 1.0e-12)
            return 0.0;
        double c = ((ax * bx) + (ay * by) + (az * bz)) / (la * lb);
        return Math.Acos(Math.Min(Math.Max(c, -1.0), 1.0)) * 180.0 / Math.PI;
    }
```

`RequirePublicStatic` already exists in the harness (line 2611).

- [ ] **Step 3: Run the gate**

Expected: `PASS  ColumnPlacement: ...`. The arches were sized by this arithmetic: the wide case, 13 notches over 12 with rise 2, has its outermost tree's main notch at x = 1, z = 0.61, so a trunk from the central foot at (6, 0, 0) leans atan(5 / 0.61) = 83 degrees and level 1 refuses on lean. The centred and fork cases at rise 5 over 8 (mains at x = 1, z = 2.19 for nine notches) lean atan(3 / 2.19) = 54 degrees from a central foot, inside the cap. The Auto case at 3 wide, 3 high has both levels feasible; the check asserts only that the placed level is the feasible one with the least load path, never which level that is. If a case does not behave as predicted, adjust the width or rise, never the assertion, and say so in the report.

- [ ] **Step 4: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "tests/native_smoke/Program.cs"
git -C $repo commit -m "test(columns): the engine's grouping, fork, refusal, centred foot, held ring, free rim, crossing, distance and Auto, measured"
```

---

### Task 3: The component

**Files:**
- Create: `plugin/native_v02/Components/ColumnsComponent.cs`
- Delete: `plugin/native_v02/Components/ColumnFinderComponents.cs` (the whole file; `BeamSolver` is re-created in Task 4 from the copy below, so this task also creates `BeamSolver.cs` to keep Monitor compiling)
- Create: `plugin/native_v02/Components/BeamSolver.cs`
- Modify: `plugin/native_v02/Contracts/MouldContracts.cs` line 130
- Modify: `plugin/native_v02/Components/DiagnoseComponents.cs` lines 183 to 192
- Test: `tests/native_smoke/Program.cs`: delete the `ValidateBeamPlacement`, `ValidateForkPoint`, `ValidateColumnTree`, `ValidateSharedFoot` try blocks (lines 479 to 532 and 615 to 629) and methods; rewrite `ValidateStiffnessSeparation`; delete the `forks_raised` sub-check (lines 1934 to 1945); extend the contract fixture.

**Interfaces:**
- Consumes: `ColumnPlacement.Place` and friends (Task 1); `MouldGeometry.ThrustMeshFromResult`, `PerimeterNodes`, `GroupingAdjacency`, `ConnectedGroups`, `BuildAdjacency`, `BarLoads`, `BarTransverse`, `MedianEdgeLength`, `ColumnsBlock`, `ValidEdges`, `GroundLevel`, `PrincipalRuns` (existing).
- Produces: `ColumnsComponent` (GUID unchanged), `BeamSolver.Response` unchanged for Monitor.

- [ ] **Step 1: Extract BeamSolver**

Create `plugin/native_v02/Components/BeamSolver.cs` containing exactly the `Response` and `SolveDense` methods from `ColumnFinderComponents.cs` lines 1830 to 1944, wrapped as:

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// A bar on point supports, solved as an Euler-Bernoulli beam. Monitor
    /// uses it to turn the notches a column holds into bar sag between them.
    /// It no longer chooses where columns stand: every notch is held.
    /// </summary>
    internal static class BeamSolver
    {
        // Response and SolveDense, copied verbatim from ColumnFinderComponents.cs
        // lines 1830 to 1944.
    }
}
```

- [ ] **Step 2: Write the component**

Create `plugin/native_v02/Components/ColumnsComponent.cs`:

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Columns: every notch of every principal line gets a column head, the
    /// heads group into trees by Branching, and the trees reach the ground
    /// by Ground. Nothing is chosen by a beam search any more; the machine
    /// has a joint at every notch and this component says how the joints
    /// are held up.
    ///
    /// The Result is the form finder: the principal lines travel in it,
    /// resolved once by Pattern, and the load each notch hands its bar comes
    /// from the Result's own member forces. The ground is the level the
    /// anchors sit at.
    ///
    /// The engine is ColumnPlacement, pure arithmetic the harness measures.
    /// This class only reads the Result, builds the engine's inputs, writes
    /// the block and says what happened.
    /// </summary>
    public sealed class ColumnsComponent : NativeComponentBase
    {
        private static readonly ComponentValueListSpec[] ValueLists =
        {
            new(
                2,
                "Ground",
                new (string Label, string Value)[]
                {
                    ("0 · standalone", "0"),
                    ("1 · one central foot", "1"),
                    ("2 · two feet", "2"),
                    ("3 · three feet", "3"),
                    ("4 · four feet", "4"),
                    ("Auto", "-1")
                },
                "0")
        };

        private protected override IReadOnlyList<ComponentValueListSpec>
            SuggestedValueLists => ValueLists;

        public ColumnsComponent()
            : base(
                "Columns",
                "Columns",
                "Hold every notch of every principal line with a column head, "
                    + "grouped into trees by Branching and footed by Ground. "
                    + "The loads come from the Result's own member forces.",
                ComponentCategories.Visualise,
                "column_finder")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("c47a1e93-8b25-4d60-a1f7-6e29b3c05d84");

        /// <summary>
        /// Blue for the columns: the one thing on screen that is not part of
        /// the net. Green already means a support, red a notched bar.
        /// </summary>
        private static readonly Color ColumnColour =
            Color.FromArgb(40, 85, 175);

        private Mesh? _previewMesh;
        private readonly List<Line> _previewCables = new();
        private readonly List<Line> _previewColumns = new();
        private readonly List<Point3d> _previewSupports = new();
        private BoundingBox _clippingBox = BoundingBox.Empty;

        public override bool IsPreviewCapable => true;

        public override BoundingBox ClippingBox => _clippingBox;

        protected override void BeforeSolveInstance()
        {
            base.BeforeSolveInstance();
            _previewMesh = null;
            _previewCables.Clear();
            _previewColumns.Clear();
            _previewSupports.Clear();
            _clippingBox = BoundingBox.Empty;
        }

        /// <summary>
        /// Draw the finished mould the way TNA Solve and Animate draw theirs,
        /// same shaded material, wire colour and support points, so the three
        /// read as one object seen at three moments. On top of that goes the
        /// one thing only this component knows, the columns. The bars are
        /// Pattern's to draw. The geometry outputs stay hidden so nothing
        /// draws twice.
        /// </summary>
        public override void DrawViewportMeshes(IGH_PreviewArgs args)
        {
            if (Hidden || _previewMesh is null || _previewMesh.Faces.Count == 0)
                return;
            args.Display.DrawMeshShaded(
                _previewMesh,
                new DisplayMaterial(Color.FromArgb(225, 222, 215), 0.35));
        }

        public override void DrawViewportWires(IGH_PreviewArgs args)
        {
            if (Hidden)
                return;
            base.DrawViewportWires(args);
            if (_previewMesh is not null && _previewMesh.Faces.Count > 0)
            {
                args.Display.DrawMeshWires(
                    _previewMesh, Color.FromArgb(95, 95, 100));
            }
            else
            {
                foreach (Line cable in _previewCables)
                    args.Display.DrawLine(cable, Color.FromArgb(95, 95, 100));
            }
            foreach (Line column in _previewColumns)
                args.Display.DrawLine(column, ColumnColour, 3);
            foreach (Point3d point in _previewSupports)
            {
                args.Display.DrawPoint(
                    point,
                    PointStyle.RoundControlPoint,
                    4,
                    Color.FromArgb(30, 165, 85));
            }
        }

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Solved FD or TNA result. Used as the form finder: its geometry "
                    + "gives the notches and its member forces give the load "
                    + "each one hands the bar.",
                GH_ParamAccess.item);
            parameters.AddIntegerParameter(
                "Branching",
                "B",
                "Notches per tree: 1 stands a column under every notch, 2 and "
                    + "3 group neighbouring notches into trees of that size, "
                    + "mirrored about the middle of each span with the "
                    + "remainder at the anchors. Every notch is held.",
                GH_ParamAccess.item,
                1);
            parameters.AddIntegerParameter(
                "Ground",
                "G",
                "How the trees reach the ground. 0 stands each tree on its "
                    + "own foot on the line of the force it carries; 1 to 4 "
                    + "gather each span's trees onto that many feet about its "
                    + "midpoint, and a level that would lean a trunk past 60 "
                    + "degrees, stand it more than 30 degrees off its force, "
                    + "or run a member into another or into the net is "
                    + "refused and the next lower one tried. -1 is Auto: every "
                    + "level is tried and the shortest load path is built.",
                GH_ParamAccess.item,
                0);
            parameters[1].Optional = true;
            parameters[2].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "The Result this component was given, with the built columns "
                    + "written into its Mould block: every tree node, every "
                    + "member with the force it carries, which nodes are heads, "
                    + "forks and feet, and which net vertex each head stands "
                    + "on. Read the geometry back with Deconstruct (Columns, "
                    + "Heads, Feet), the numbers with Monitor, and the words "
                    + "with Diagnose. Wire it into Animate to raise the "
                    + "columns with the net.",
                GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }

            int branching = 1;
            int ground = 0;
            data.GetData(1, ref branching);
            data.GetData(2, ref ground);
            branching = Math.Min(Math.Max(branching, 1), ColumnPlacement.MaxBranching);
            if (ground > ColumnPlacement.MaxGround)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"Ground {ground} is above the {ColumnPlacement.MaxGround} feet "
                        + "per span this machine places; clamped. An old Type "
                        + "value list goes to 6; place the Ground list from the "
                        + "component menu.");
                ground = ColumnPlacement.MaxGround;
            }
            if (ground < -1)
                ground = -1;

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                EquilibriumResultDto equilibrium = result.Equilibrium!;
                Point3d[] nodes = equilibrium.Vertices
                    .Select(v => new Point3d(v.X, v.Y, v.Z))
                    .ToArray();
                int n = nodes.Length;
                if (n == 0)
                    throw new InvalidOperationException("Result carries no vertices.");

                (int, int)[] edges = MouldGeometry.ValidEdges(
                    equilibrium, n, out int[] edgeSource);
                var anchors = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));
                double groundLevel = MouldGeometry.GroundLevel(nodes, anchors);
                List<List<int>> bars = MouldGeometry.PrincipalRuns(equilibrium, n);

                int overlapping = 0;
                for (int a = 0; a < bars.Count; a++)
                {
                    for (int b = a + 1; b < bars.Count; b++)
                    {
                        var left = new HashSet<int>(bars[a]);
                        int shared = bars[b].Count(left.Contains);
                        if (2 * shared <= Math.Min(bars[a].Count, bars[b].Count))
                            continue;
                        overlapping = Math.Max(overlapping, shared);
                        AddRuntimeMessage(
                            GH_RuntimeMessageLevel.Warning,
                            $"Principal lines {a} and {b} share {shared} "
                                + "notches, so they are one bar traced twice. "
                                + "Check the curves drawn into Pattern.");
                        a = bars.Count;
                        break;
                    }
                }

                var barShape = new List<string>();
                foreach (List<int> bar in bars)
                {
                    bool startTied = bar.Count > 0 && anchors.Contains(bar[0]);
                    bool endTied = bar.Count > 0 && anchors.Contains(bar[bar.Count - 1]);
                    string ends = startTied && endTied
                        ? "anchored at both ends"
                        : startTied || endTied
                            ? "ANCHORED AT ONE END ONLY, so it is half a line"
                            : "NOT ANCHORED AT EITHER END";
                    barShape.Add($"{bar.Count} notches, {ends}");
                }

                if (bars.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines. Draw Principal "
                            + "Lines into Pattern upstream; nothing derives them.");
                    data.SetData(0, new ResultGoo(ResultDiagnostics.Replace(
                        result, "Columns", new[]
                        {
                            ResultDiagnostics.Entry("Columns", "columns.no_principal_runs", "error",
                                "no principal runs on this Result, so there is nothing to "
                                    + "stand under. Draw Principal Lines into Pattern upstream."),
                        })));
                    return;
                }

                // What the net hands each node, from the solve's own member
                // forces, indexed through edgeSource because the filtered
                // edge list no longer matches the Result's arrays.
                var edgeForce = new double[edges.Length];
                for (int e = 0; e < edges.Length; e++)
                {
                    int src = e < edgeSource.Length ? edgeSource[e] : e;
                    edgeForce[e] = src < equilibrium.MemberForces.Count
                        ? equilibrium.MemberForces[src]
                        : 0.0;
                }
                var incident = new List<(int Other, double Force)>[n];
                for (int i = 0; i < n; i++)
                    incident[i] = new List<(int, double)>();
                for (int e = 0; e < edges.Length; e++)
                {
                    incident[edges[e].Item1].Add((edges[e].Item2, edgeForce[e]));
                    incident[edges[e].Item2].Add((edges[e].Item1, edgeForce[e]));
                }

                double alongToAnchors = 0.0;
                double acrossToColumns = 0.0;
                var across = new Vector3d[bars.Count][];
                for (int b = 0; b < bars.Count; b++)
                {
                    Vector3d[] pull = MouldGeometry.BarLoads(bars[b], nodes, incident);
                    Vector3d[] transverse = MouldGeometry.BarTransverse(bars[b], nodes, pull);
                    for (int k = 0; k < bars[b].Count; k++)
                    {
                        alongToAnchors += (pull[k] - transverse[k]).Length;
                        acrossToColumns += transverse[k].Length;
                    }
                    across[b] = transverse;
                }

                // The boundary loops, for the free-rim test. Computed the way
                // Animate computes its Perimeter Nodes: naked mesh edges when
                // the thrust mesh exists, a degree heuristic otherwise, grouped
                // over the union of solved and pattern edges.
                Mesh? thrust = MouldGeometry.ThrustMeshFromResult(result, out int[] meshToNode);
                List<int>[] neighbours = MouldGeometry.BuildAdjacency(edges, n);
                List<int> perimeterIds = MouldGeometry.PerimeterNodes(thrust, meshToNode, neighbours, n);
                List<int>[] grouping = MouldGeometry.GroupingAdjacency(result, edges, n);
                List<List<int>> loops = MouldGeometry.ConnectedGroups(perimeterIds, grouping);

                double median = MouldGeometry.MedianEdgeLength(nodes, edges);
                ColumnPlacement.Placement placement = ColumnPlacement.Place(
                    nodes,
                    bars.Select(b => b.ToArray()).ToArray(),
                    anchors.ToArray(),
                    across,
                    loops.Select(l => l.ToArray()).ToArray(),
                    edges,
                    groundLevel,
                    median,
                    branching,
                    ground);
                ColumnPlacement.Level built = placement.Built;

                var members = new List<Line>(built.Members.Count);
                foreach ((int lower, int upper) in built.Members)
                    members.Add(new Line(built.Nodes[lower], built.Nodes[upper]));
                var force = new List<double>(built.Axial);
                var angle = members
                    .Select(m => MouldGeometry.LeanFromVertical(m.From, m.To))
                    .ToList();

                _previewMesh = thrust;
                _previewCables.Clear();
                _previewCables.AddRange(edges.Select(
                    e => new Line(nodes[e.Item1], nodes[e.Item2])));
                _previewColumns.Clear();
                _previewColumns.AddRange(members);
                _previewSupports.Clear();
                _previewSupports.AddRange(
                    anchors.OrderBy(i => i).Select(i => nodes[i]));
                _clippingBox = TnaWorkflowPreview.Box(
                    _previewCables.Concat(_previewColumns),
                    _previewSupports);

                if (placement.GroundPlaced != Math.Max(ground, 0) && ground >= 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        $"Ground {ground} was refused and Ground "
                            + $"{placement.GroundPlaced} built instead; Diagnose "
                            + "says which rule refused it.");
                }
                if (!built.Feasible && built.Ground == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        $"{built.Collisions} member(s) collide even standing "
                            + "alone; placed anyway so the chain keeps running.");
                }

                Point3d[] netNodes = nodes.ToArray();
                double weld = 1.0e-6 * Math.Max(
                    new BoundingBox(netNodes).Diagonal.Length, 1.0);
                MouldColumnsDto block = MouldGeometry.ColumnsBlock(
                    members,
                    force,
                    netNodes,
                    weld,
                    branching: branching,
                    groundAsked: ground,
                    groundPlaced: placement.GroundPlaced,
                    forkFraction: ColumnPlacement.ForkFraction,
                    forksRaised: 0);
                ResultDto output = result with
                {
                    Mould = new MouldDto
                    {
                        Ground = groundLevel,
                        Columns = block,
                        Frame = null,
                    },
                };
                output = ResultDiagnostics.Replace(output, "Columns", Diagnostics(
                    bars, placement, built, force, angle, branching, ground,
                    groundLevel, alongToAnchors, acrossToColumns, overlapping,
                    barShape));
                data.SetData(0, new ResultGoo(output));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        private static string Inv(double value, string format) =>
            value.ToString(format, CultureInfo.InvariantCulture);

        private static List<DiagnosticDto> Diagnostics(
            List<List<int>> bars,
            ColumnPlacement.Placement placement,
            ColumnPlacement.Level built,
            List<double> force,
            List<double> angle,
            int branching,
            int groundAsked,
            double groundLevel,
            double alongToAnchors,
            double acrossToColumns,
            int overlapping,
            List<string> barShape)
        {
            const string S = "Columns";
            double cap = MouldGeometry.MaxLeanDegrees;
            var d = new List<DiagnosticDto>
            {
                overlapping > 0
                    ? ResultDiagnostics.Entry(S, "columns.overlap", "warning",
                        $"two principal lines share {overlapping} notches, so ONE "
                            + "bar is being traced twice and given two full sets of "
                            + "columns.",
                        overlapping, unit: "notches")
                    : ResultDiagnostics.Entry(S, "columns.overlap", "ok",
                        "each principal line is distinct", 0.0, unit: "notches"),
            };

            for (int i = 0; i < barShape.Count; i++)
            {
                bool halfLine =
                    barShape[i].Contains("ONE END", StringComparison.Ordinal) ||
                    barShape[i].Contains("NOT ANCHORED", StringComparison.Ordinal);
                d.Add(ResultDiagnostics.Entry(S, "columns.bar_shape",
                    halfLine ? "warning" : "info",
                    $"bar {i}: {barShape[i]}",
                    context: ResultDiagnostics.Context(("bar", i.ToString(CultureInfo.InvariantCulture)))));
            }

            for (int b = 0; b < bars.Count; b++)
            {
                var spans = placement.Spans.Where(s => s.Bar == b).ToList();
                string cuts = string.Join(", ", spans.Select(s =>
                    $"{s.FirstKind} to {s.LastKind}, {s.Free.Count} notches"));
                d.Add(ResultDiagnostics.Entry(S, "columns.spans", "info",
                    $"bar {b}: {spans.Count} span(s): {cuts}",
                    spans.Count, unit: "spans",
                    context: ResultDiagnostics.Context(("bar", b.ToString(CultureInfo.InvariantCulture)))));
            }

            int singles = placement.Trees.Count(t => t.Nodes.Length == 1);
            int smaller = placement.Trees.Count(t => !t.Ring && t.Nodes.Length > 1 && t.Nodes.Length < branching);
            d.Add(ResultDiagnostics.Entry(S, "columns.grouping", "info",
                $"Branching {branching}: {placement.Trees.Count} trees hold "
                    + $"{placement.Trees.Sum(t => t.Nodes.Length)} notches, "
                    + $"{singles} single columns, {smaller} remainder trees "
                    + "smaller than Branching at the anchors; every notch is held.",
                placement.Trees.Count, unit: "trees",
                context: ResultDiagnostics.Context(
                    ("branching", branching.ToString(CultureInfo.InvariantCulture)),
                    ("singles", singles.ToString(CultureInfo.InvariantCulture)),
                    ("remainder", smaller.ToString(CultureInfo.InvariantCulture)))));

            if (placement.RingTree is ColumnPlacement.Tree ring && ring.FixedFoot is Point3d rf)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.ring_tree", "info",
                    $"a ring tree holds the {ring.Nodes.Length} rim notches of a "
                        + "free central rim from one foot at the plan intersection "
                        + $"of the bars' end tangents, ({rf.X:0.###}, {rf.Y:0.###}).",
                    ring.Nodes.Length, unit: "notches",
                    context: ResultDiagnostics.Context(
                        ("x", Inv(rf.X, "0.###")), ("y", Inv(rf.Y, "0.###")))));
            }

            string asked = groundAsked < 0 ? "Auto" : groundAsked.ToString(CultureInfo.InvariantCulture);
            var refused = placement.Tried.Where(t => !t.Feasible && t.Ground > 0)
                .Select(t => $"level {t.Ground} refused on {t.Rule} at {t.Value:0.##}")
                .ToList();
            bool fellBack = groundAsked >= 0 && placement.GroundPlaced < groundAsked;
            d.Add(ResultDiagnostics.Entry(S, "columns.ground",
                fellBack ? "warning" : "info",
                $"Ground asked {asked}, placed {placement.GroundPlaced}"
                    + (refused.Count > 0 ? "; " + string.Join("; ", refused) : "")
                    + (placement.GroundPlaced == 0
                        ? ". Every tree stands on its own foot on the line of its force."
                        : $". Each span's trees gather onto {placement.GroundPlaced} feet about its midpoint."),
                placement.GroundPlaced, unit: "feet per span",
                context: ResultDiagnostics.Context(
                    ("asked", groundAsked.ToString(CultureInfo.InvariantCulture)),
                    ("placed", placement.GroundPlaced.ToString(CultureInfo.InvariantCulture)),
                    ("refused", refused.Count.ToString(CultureInfo.InvariantCulture)))));

            var scored = placement.Tried.Where(t => t.Feasible)
                .Select(t => (t.Ground.ToString(CultureInfo.InvariantCulture), Inv(t.LoadPath, "0")))
                .ToArray();
            d.Add(ResultDiagnostics.Entry(S, "columns.load_path", "info",
                $"load path {built.LoadPath:0} N x model units, the sum over "
                    + "members of force times length"
                    + (groundAsked < 0 ? $"; feasible levels scored: {string.Join(", ", scored.Select(s => $"{s.Item1}={s.Item2}"))}" : ""),
                built.LoadPath, unit: "N x model units",
                context: ResultDiagnostics.Context(scored)));

            if (built.FeetMerged > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.feet_merged", "info",
                    $"{built.FeetMerged} feet closer than the clearance were "
                        + "merged into one, at their plan centre.",
                    built.FeetMerged, unit: "feet"));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.branch_off_thrust", "info",
                $"branches stand up to {built.WorstBranchOff:0.#} degrees off the "
                    + "pull at their notch; a fork can only be in one place, and "
                    + "what is left is bending for the joint to take.",
                built.WorstBranchOff, unit: "degrees"));
            if (!built.Feasible && built.Ground == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.collision", "warning",
                    $"{built.Collisions} member(s) come within the clearance of "
                        + "another member or of the net even standing alone; placed "
                        + "anyway. Draw the principal lines further apart or lower "
                        + "Branching.",
                    built.Collisions, unit: "members"));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.head_load_total", "info",
                $"the heads carry {placement.Trees.Sum(t => t.Load.Sum()):0} N between "
                    + $"them, ground read as {groundLevel:0.###}, the level the anchors sit at",
                placement.Trees.Sum(t => t.Load.Sum()), unit: "N",
                context: ResultDiagnostics.Context(("ground", Inv(groundLevel, "0.###")))));
            d.Add(ResultDiagnostics.Entry(S, "columns.load_split", "info",
                $"of the net's pull on the bars, {alongToAnchors:0} N runs ALONG "
                    + "them to the anchors, which are this machine's buttresses. "
                    + $"The {acrossToColumns:0} N ACROSS them is the columns' to "
                    + "take, and it sets their lean.",
                acrossToColumns, unit: "N",
                context: ResultDiagnostics.Context(("along_to_anchors", Inv(alongToAnchors, "0")))));
            d.Add(ResultDiagnostics.Entry(S, "columns.principal_source", "info",
                "principal lines came from the contract, resolved upstream by "
                    + "Pattern from the curves drawn into it; nothing was "
                    + "re-matched here.",
                bars.Count, unit: "bars"));
            if (built.PlumbTrees > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.plumb_fallback",
                    built.PlumbTrees >= placement.Trees.Count ? "warning" : "info",
                    $"{built.PlumbTrees} trees stand PLUMB because the net pulls "
                        + "their notches down onto the column rather than off it. "
                        + "If that is ALL of them, the aiming is not working.",
                    built.PlumbTrees, unit: "trees"));
            }
            var loads = placement.Trees.SelectMany(t => t.Load).ToList();
            if (loads.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.head_load", "info",
                    $"head load {loads.Min():0} to {loads.Max():0} N",
                    loads.Max(), unit: "N",
                    context: ResultDiagnostics.Context(("min", Inv(loads.Min(), "0")))));
            }
            if (force.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.force_max", "info",
                    $"axial force up to {force.Max():0} N", force.Max(), unit: "N"));
            }
            if (angle.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.lean", "info",
                    $"lean {angle.Min():0.#} to {angle.Max():0.#} degrees from vertical",
                    angle.Max(), cap, "degrees",
                    ResultDiagnostics.Context(("min", Inv(angle.Min(), "0.#")))));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.demand_only", "info",
                "no capacity is assumed anywhere here: Force is the demand, to "
                    + "size and test against, not a pass or a fail."));
            return d;
        }
    }
}
```

Two things to verify while transcribing, both against the existing code: (1) the exact signatures of `MouldGeometry.BuildAdjacency` (about line 1027) and `MouldGeometry.PerimeterNodes` (about line 2306) and how Animate calls them at MouldComponents.cs lines 553 to 556 and 929 to 934; copy Animate's call shapes. (2) `ResultDiagnostics.Context(params (string, string)[])` accepts the `scored` array only if its element type is `(string, string)`; it is, by construction above.

- [ ] **Step 3: Delete the old file**

Delete `plugin/native_v02/Components/ColumnFinderComponents.cs` entirely (`git rm`). Anything still referencing `ColumnFinderComponent` or `BeamSolver.ArmsForBar` is now the harness, handled in Step 5.

- [ ] **Step 4: The contract and Diagnose**

`MouldContracts.cs` line 130 to 131:

```csharp
        if (GroundAsked < -1)
            errors.Add($"{label}.groundAsked cannot be below -1 (Auto).");
```

Also change the doc comment on `GroundAsked` (line 67) to `/// <summary>The Ground level asked for; -1 is Auto.</summary>`.

`DiagnoseComponents.cs`: delete lines 183 to 192 (the `raised` lookup and the `diagnose.forks_raised` entry).

- [ ] **Step 5: The harness**

In `tests/native_smoke/Program.cs`:
- Delete the four try blocks that call `ValidateBeamPlacement`, `ValidateForkPoint`, `ValidateColumnTree` (lines 479 to 532) and `ValidateSharedFoot` (615 to 629), and delete the four methods and their doc comments (`ValidateBeamPlacement` at 2741, `ValidateForkPoint` at 2999, `ValidateColumnTree` at 3092, `ValidateSharedFoot` at 3550; locate by name).
- In the `ValidateStiffnessSeparation` try block (631 to 645) change the PASS text to: `"PASS  EI separation: bar sag scales exactly as one over EI, which is what lets Monitor's one number turn a bending shape into millimetres; lean from vertical is measured against hand-computed angles."` and rewrite the method body: delete everything from `MethodInfo arms = RequirePublicStatic(solver, "ArmsForBar");` through the `if (!soft.SequenceEqual(mid) ...` block (the ArmsForBar half), resolve `point3d` from `response.GetParameters()`... `Response` takes no Point3d, so resolve it from the geometry type instead:

```csharp
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo lean = RequirePublicStatic(geometry, "LeanFromVertical");
        Type point3d = lean.GetParameters()[0].ParameterType;
```

and keep the deflection-reciprocal block and the three lean assertions, invoking `lean` (now on `MouldGeometry`). Rewrite the method's doc comment to say what it now measures.
- In `ValidateDiagnoseRules` delete lines 1934 to 1945 (the `forky` block). If `ColumnsBlockForRules` then has no caller, delete it too.
- In `ValidateMouldContract`, after the existing round-trip fixture, add two assertions: a block with `GroundAsked = -1` validates clean, and one with `GroundAsked = -2` is refused with a message containing `groundAsked`. Use the same `SetContractProperty` pattern as the rest of that method.

- [ ] **Step 6: Run the gate**

Expected: 0 warnings, 18 components (the count is unchanged: one component replaced one), 12 parameters, every check passing including `PASS  ColumnPlacement` and the rewritten `PASS  EI separation`.

- [ ] **Step 7: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnsComponent.cs" "plugin/native_v02/Components/BeamSolver.cs" "plugin/native_v02/Components/ColumnFinderComponents.cs" "plugin/native_v02/Contracts/MouldContracts.cs" "plugin/native_v02/Components/DiagnoseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): two sliders, every notch held, feet by span with rejection and Auto; the beam search retires"
```

(`git add` of a deleted path stages the deletion.)

---

### Task 4: Dead geometry goes

**Files:**
- Modify: `plugin/native_v02/Components/MouldComponents.cs`: delete `ForkPoint` (with its doc comment, about lines 1790 to 1857), `Solve3` (1859 to about 1905), `BuildColumnTree` (2227 to 2261).

**Interfaces:** none. Verify first with a grep that nothing outside these methods references `ForkPoint`, `Solve3` or `BuildColumnTree`; after Task 3 the harness no longer does.

- [ ] **Step 1: Delete the three methods**

Locate each by its signature line and remove from the `/// <summary>` that precedes it through its closing brace. `ColumnTree` (the class) and `TreeFromPairs`, `TreeFromBlock`, `TreesByFoot`, `MainBranch`, `ForkOnLine` all STAY: Animate and ColumnsBlock use them.

- [ ] **Step 2: Grep**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
rg -n "ForkPoint|Solve3|BuildColumnTree|ArmsForBar|ColumnFinderComponent|LastPlumbFallbacks|SharedFoot|GroupByPlan" "$repo\plugin\native_v02" "$repo\tests\native_smoke"
```

Expected: no output.

- [ ] **Step 3: Run the gate, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/MouldComponents.cs"
git -C $repo commit -m "refactor(mould): the force-solved fork, its solver and the line-welding tree builder go; nothing called them"
```

---

### Task 5: The taxonomy row

**Files:**
- Modify: `docs/component-taxonomy.md` line 55 (the Columns row)

- [ ] **Step 1: Replace the row**

```markdown
| `03 Visualise` | **Columns** | Result `RES`, Branching `B`, Ground `G` | Result `RES` | Hold every notch of every principal line with a column head. The Result is the form finder: the principal lines travel in it, resolved by Pattern, the load each notch hands its bar comes from the Result's own member forces, and the ground is the level the anchors sit at. `Branching` (1, 2, 3) groups neighbouring notches into trees of that size, mirrored about the middle of each span with the remainder at the anchors, and the centre notch of an odd count standing alone; a bar is cut into spans at its anchors (a held ring gives two half-spans and no column at the ring) and at a ring tree, which serves bars ending on a free central rim from one foot at the plan intersection of their end tangents. `Ground` is how the trees reach the ground: 0 stands each on its own foot on the line of its force; 1 to 4 gather each span's trees onto that many feet in bands about the span's midpoint, coincident feet merged, and a level that would lean a trunk past 60 degrees, stand it more than 30 degrees off its force, or run a member into another or into the net is REFUSED and the next lower level tried, with the asked and placed levels recorded; Auto tries every level and builds the shortest load path. The fork of every tree lies on the segment from its foot to its main notch at 65% of the notch height, so trunk and main branch are one straight line. The built trees leave ONLY inside the Result's Mould block; **Deconstruct** hands the geometry back as trees, **Monitor** the numbers, **Diagnose** the words. |
```

- [ ] **Step 2: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "docs/component-taxonomy.md"
git -C $repo commit -m "docs(taxonomy): the Columns row says two sliders, spans, the ring tree, rejection and Auto"
```

---

## Self-review

Spec coverage: 2 (Task 3 ports and value list), 3.1 spans (Task 1 `Spans`), 3.2 ring tree (Task 1 `RingTree`), 3.3 grouping (Task 1 `Group`), 3.4 loads (Task 3 across arrays, Task 1 tree loads), 3.5 feet (Task 1 `BuildLevel`, `MergeFeet`), 3.6 fork and members (Task 1 `BuildLevel`), 3.7 rejection and Auto (Task 1 `BuildLevel`, `Place`, `CountCollisions`), 3.8 block (Task 3 `ColumnsBlock` call; `HeadNode` by ColumnsBlock's plan match, exact because every head is a net vertex), 4 diagnostics (Task 3 `Diagnostics`; removed codes absent), 5 files (Tasks 1, 3, 4), 6 testing (Task 2 new checks, Task 3 deletions and rewrites), 7 canvas (no code), 8 amendments (encoded in Tasks 1 and 3).

Type consistency: `Place(Point3d[], int[][], int[], Vector3d[][], int[][], (int,int)[], double, double, int, int)` in Task 1, Task 2's `Run` and Task 3's call; `Level.Members` is `List<(int Lower, int Upper)>` read as `Item1`/`Item2` by Task 2; `Tree.Nodes` is `int[]` cast as such in Task 2; `Placement.RingTree` is `Tree?` with `FixedFoot` `Point3d?`, and Task 2 reads it through `Get<object>` which unboxes the nullable to a `Point3d` box (a null `FixedFoot` would throw, and the check asserts the ring exists first).

Known risk, ledgered for the executor: the hand-built arches in Task 2 were sized by arithmetic in this plan; if a case does not behave as predicted the implementer adjusts the width or rise as Step 3 of Task 2 explains, never the assertion.
