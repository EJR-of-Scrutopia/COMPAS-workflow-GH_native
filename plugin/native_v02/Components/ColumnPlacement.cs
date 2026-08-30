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

        /// <summary>
        /// How close to vertical an aim has to be to BE vertical. A degree of
        /// residual lean out of a solved net is noise, not a thrust line, and
        /// a column that follows it stands crooked for no reason.
        /// </summary>
        public const double PlumbDegrees = 2.0;

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
            /// <summary>
            /// The resultant as the net handed it over, before the mirror
            /// rule of spec 3.4. The diagnostics measure how far the
            /// symmetrised aim moved from this one.
            /// </summary>
            public Vector3d RawResultant;
            /// <summary>Fixed foot, ring tree only.</summary>
            public Point3d? FixedFoot;
            public bool Ring;
        }

        /// <summary>One Ground level, built and judged.</summary>
        public sealed class Level
        {
            public int Ground;
            /// <summary>No member collides. Auto reads this and nothing else.</summary>
            public bool Feasible = true;
            /// <summary>collision, lean, alignment, or none: the worst measure.</summary>
            public string Rule = "none";
            /// <summary>The measure Rule names.</summary>
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
            /// <summary>Trunks that stepped off a shared foot onto their own.</summary>
            public int Peeled;
            /// <summary>Pairs of feet inside the clearance that stayed two.</summary>
            public int FeetClose;
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
            /// <summary>
            /// Set once <c>Symmetrise</c> has run. A second call on the same
            /// Placement is a no-op: it would otherwise overwrite
            /// <c>Tree.RawResultant</c> with the already-symmetrised vector
            /// and report an <c>AsymmetryRemoved</c> of zero.
            /// </summary>
            public bool Symmetrised;
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
            // Called exactly once per Place, but guarded rather than trusted:
            // Tasks 2 and 3 edit around this call site, and a second call
            // would overwrite RawResultant with the already-symmetrised
            // vector and report the asymmetry removed as zero.
            if (placement.Symmetrised)
                return placement.AsymmetryRemoved;
            placement.Symmetrised = true;

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

        // ------------------------------------------------------------------
        // Entry

        /// <summary>
        /// Place the columns for one Result.
        ///
        /// <paramref name="across"/> is, per bar and per bar position, the
        /// transverse pull the net hands that notch (MouldGeometry.BarLoads
        /// then BarTransverse). <paramref name="perimeterLoops"/> are the
        /// boundary loops as net vertex lists; an empty array means no rim
        /// can be detected and no ring tree is placed.
        /// <paramref name="groundAsked"/> is 0 to MaxGround, or -1 for Auto.
        ///
        /// The net's edges are not taken: spec 3.7's net test is against the
        /// net's VERTICES, and the edge-proximity rule that used to want them
        /// was never in the spec.
        /// </summary>
        public static Placement Place(
            Point3d[] nodes,
            int[][] bars,
            int[] anchors,
            Vector3d[][] across,
            int[][] perimeterLoops,
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

            // Spec 3.4: the resultants are mirrored about each span's
            // midpoint and shared across each family BEFORE a single foot is
            // placed. The ring tree keeps its own; it has no mirror partner
            // and no family, and its foot is fixed by 3.2 anyway.
            placement.AsymmetryRemoved = Symmetrise(placement, nodes, bars);

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
            double ground,
            int level,
            double clearance)
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
                    // The pair member with the SMALLER chord parameter is on
                    // the first half of the span. Grouping order usually
                    // agrees with this, but a bar that is not plan-monotone
                    // (its parameter along the chord does not rise with its
                    // node order) can disagree, so the chord parameter itself
                    // decides, never the grouping index.
                    int first = t;
                    int mirrored = paired ? partner : -1;
                    if (paired &&
                        ChordParameter(nodes, placement, bars, trees[partner]) <
                        ChordParameter(nodes, placement, bars, trees[t]))
                    {
                        first = partner;
                        mirrored = t;
                    }
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
                // The fork lies on the segment from the foot to the main
                // notch, at ForkFraction of the main notch's height (spec
                // 3.6). The main notch is the tree's INNERMOST, which on an
                // arch is also its HIGHEST, so at Branching 3 an anchor-end
                // tree can hold a notch BELOW that height and the branch to
                // it would run down from the fork. A fork above one of its
                // own heads is not a tree: the block sorts every member by Z
                // (MouldGeometry.ColumnsBlock), so such a notch is only ever
                // a lower end and TreeFromPairs reads it as a FOOT, which
                // puts a foot in mid-air in Deconstruct, drops the head out
                // of Monitor's held set and makes Animate drive a held head
                // down to ground level on the rail. Where the spec's height
                // would sit at or above the tree's lowest notch the fork is
                // therefore lowered to ForkFraction of THAT notch's height,
                // on the same segment. Every ordinary tree, main notch
                // lowest or the branches above the fork already, is
                // untouched.
                double fraction = ForkFraction;
                double rise = main.Z - footPoint.Z;
                if (rise > 1.0e-9)
                {
                    double lowest = main.Z;
                    for (int k = 1; k < tree.Nodes.Length; k++)
                        lowest = Math.Min(lowest, nodes[tree.Nodes[k]].Z);
                    if (lowest > footPoint.Z &&
                        footPoint.Z + (ForkFraction * rise) >= lowest)
                    {
                        fraction = ForkFraction * (lowest - footPoint.Z) / rise;
                    }
                }
                var fork = new Point3d(
                    footPoint.X + ((main.X - footPoint.X) * fraction),
                    footPoint.Y + ((main.Y - footPoint.Y) * fraction),
                    footPoint.Z + ((main.Z - footPoint.Z) * fraction));
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
            //
            // Alignment is judged PER FOOT, not per trunk. A shared foot
            // gathers trunks that each lean toward it, and under a plumb pull
            // every one of them is off its own tree's force by its lean; what
            // the foot actually carries is their SUM, and two mirrored trunks
            // sum to a vertical push. That is the A-frame a central foot is
            // for, and judging each trunk alone refused it on every ordinary
            // arch. The foot's resultant against the load its trees hand it
            // is the thrust the foundation sees, and that is what is bounded.
            double worstLean = 0.0;
            double worstAlign = 0.0;
            double worstBranchOff = 0.0;
            var footSet = new HashSet<int>(result.Feet);
            var footPush = new Dictionary<int, Vector3d>();
            var footWanted = new Dictionary<int, Vector3d>();
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
                    double length = direction.Length;
                    Vector3d push = length > 1.0e-12
                        ? direction * (result.Axial[m] / length)
                        : Vector3d.Zero;
                    Vector3d wanted = aim[t] * trees[t].Load.Sum();
                    footPush[lower] = footPush.TryGetValue(lower, out Vector3d p) ? p + push : push;
                    footWanted[lower] = footWanted.TryGetValue(lower, out Vector3d w) ? w + wanted : wanted;
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
            foreach ((int footNode, Vector3d push) in footPush)
            {
                if (footWanted.TryGetValue(footNode, out Vector3d wanted))
                    worstAlign = Math.Max(worstAlign, AngleBetween(push, wanted));
            }
            result.WorstLean = worstLean;
            result.WorstAlignment = worstAlign;
            result.WorstBranchOff = worstBranchOff;
            result.PlumbTrees = plumb.Count(p => p);
            result.Collisions = CountCollisions(result, nodes, anchors, clearance);
            result.LoadPath = 0.0;
            for (int m = 0; m < result.Members.Count; m++)
            {
                (int lower, int upper) = result.Members[m];
                result.LoadPath += result.Axial[m] * result.Nodes[lower].DistanceTo(result.Nodes[upper]);
            }

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
        }

        private static int AddNode(List<Point3d> nodes, Point3d point)
        {
            nodes.Add(point);
            return nodes.Count - 1;
        }

        private static void AddMember(Level level, int lower, int upper, double carried, int tree)
        {
            // Spec 3.6: every member leaves the engine LOWER END FIRST.
            // Animate and the block's tree both depend on it, and a caller
            // handing a fork and a notch cannot always know which of the two
            // is lower, so the order is settled here rather than trusted.
            if (level.Nodes[lower].Z > level.Nodes[upper].Z)
            {
                (lower, upper) = (upper, lower);
            }

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
        /// A main notch's parameter along its span's chord: 0 at the first
        /// node, 1 at the last. Used both to pick a band and, in
        /// <c>BuildLevel</c>, to decide which member of a mirror pair sits on
        /// the first half of the chord.
        /// </summary>
        private static double ChordParameter(
            Point3d[] nodes, Placement placement, int[][] bars, Tree tree)
        {
            Span span = placement.Spans[tree.Span];
            int[] bar = bars[span.Bar];
            Point3d a = nodes[bar[span.First]];
            Point3d b = nodes[bar[span.Last]];
            double cx = b.X - a.X;
            double cy = b.Y - a.Y;
            double chord = (cx * cx) + (cy * cy);
            Point3d main = nodes[tree.Nodes[0]];
            return chord > 1.0e-18
                ? (((main.X - a.X) * cx) + ((main.Y - a.Y) * cy)) / chord
                : 0.5;
        }

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
            double s = ChordParameter(nodes, placement, bars, tree);
            return Math.Min(Math.Max((int)Math.Floor(s * level), 0), level - 1);
        }

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

        // ------------------------------------------------------------------
        // Collisions

        /// <summary>
        /// Two members that share no end and come closer than the clearance
        /// collide. A member collides with the NET when its interior, sampled
        /// at 1/8 .. 7/8 of its length, rises above it: a sample whose Z is
        /// more than the clearance above the Z of the net vertex nearest it
        /// IN PLAN. That is spec 3.7's net test entire.
        ///
        /// It used to be more and less than that at once. It also refused a
        /// sample within the clearance of any net EDGE the member did not end
        /// on, a rule the spec does not state, which could refuse a Ground
        /// level the spec accepts; and it narrowed the height test to
        /// vertices within half a median plan edge, which let a member rise
        /// above the net anywhere away from a vertex, and skipped the
        /// member's own notch, which took the one vertex a near-plumb column
        /// is actually under out of its own test. Both narrowings are gone.
        ///
        /// ANCHORS are still left out, and that is a deliberate, measured
        /// deviation from the spec's "nearest net vertex": an anchor sits ON
        /// the ground, and spec 3.5 puts every Ground 0 foot out along the
        /// AimFrom ray, which on a one-sided bay lands beside or beyond an
        /// anchor. Counting anchors would make the nearest vertex to that
        /// trunk's lower samples an anchor at ground level and refuse the
        /// standalone level spec 3.7 says is never refused. A foot beside an
        /// anchor is not through the net.
        /// </summary>
        public static int CountCollisions(
            Level level,
            Point3d[] netNodes,
            HashSet<int> anchors,
            double clearance)
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
            for (int m = 0; m < count; m++)
            {
                (int lower, int upper) = level.Members[m];
                Point3d a = level.Nodes[lower];
                Point3d b = level.Nodes[upper];
                bool hit = false;
                for (int s = 1; s <= 7 && !hit; s++)
                {
                    double t = s / 8.0;
                    var p = new Point3d(
                        a.X + ((b.X - a.X) * t),
                        a.Y + ((b.Y - a.Y) * t),
                        a.Z + ((b.Z - a.Z) * t));
                    int nearest = -1;
                    double best = double.MaxValue;
                    foreach (int i in interior)
                    {
                        double d2 = MouldGeometry.PlanDistanceSquared(p, netNodes[i]);
                        if (d2 < best)
                        {
                            best = d2;
                            nearest = i;
                        }
                    }
                    if (nearest >= 0 && p.Z > netNodes[nearest].Z + clearance)
                    {
                        hit = true;
                    }
                }
                if (hit)
                    collisions++;
            }
            return collisions;
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
