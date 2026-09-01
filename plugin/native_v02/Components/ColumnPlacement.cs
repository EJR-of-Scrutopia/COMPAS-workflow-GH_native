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
    /// GROUP into trees (Branching) and how the trees reach the ground
    /// (Type), and every rule below is measured by the smoke harness on
    /// hand-built nets, which is why nothing in this file touches a Mesh, a
    /// Curve, or Rhino's native core.
    ///
    /// Order of operations: spans, ring tree, grouping, symmetrise, and then
    /// for each Type level the feet, the fork, the members, then the measures.
    /// The fork lies ON THE SEGMENT from its foot to its main notch, so trunk
    /// and main branch are one straight line by construction and a fork can
    /// never kink.
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

        /// <summary>
        /// Collision clearance as a fraction of a MEMBER's own tree's span
        /// spacing (<c>SpacingOf</c>'s <c>g</c>), read fresh for each member
        /// judged: spec section 4 puts every tolerance in this engine in the
        /// terms of the span, or the pair of spans, it applies to, and the
        /// net's median plan edge is gone from the signature so it cannot
        /// stand in for it by accident.
        /// </summary>
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

        /// <summary>
        /// One span read in its OWN terms, which is where every tolerance in
        /// this engine now comes from. Nothing here reads the net's median
        /// plan edge, and the argument that carried it is gone from
        /// <see cref="Place"/> so that it cannot be read by accident.
        /// </summary>
        public sealed class SpanFrame
        {
            /// <summary>Plan positions of the span's first and last node.</summary>
            public Point3d P0;
            public Point3d P1;
            /// <summary>Chord length in plan.</summary>
            public double L;
            /// <summary>Unit chord direction in plan.</summary>
            public Vector3d C;
            /// <summary>Plan normal to the chord.</summary>
            public Vector3d N;
            /// <summary>
            /// The chord midpoint. A coordinate origin and nothing more: no
            /// rule places a foot at it or measures a symmetry about it.
            /// </summary>
            public Point3d M;
            /// <summary>
            /// Plan bounding box diagonal over the two cut nodes and all the
            /// free notches, which is a length the span always has even when
            /// its chord has none.
            /// </summary>
            public double D;
            /// <summary>Bar positions of the free notches, in bar order.</summary>
            public int[] Positions = Array.Empty<int>();
            /// <summary>Net vertices of the free notches, in bar order.</summary>
            public int[] Nodes = Array.Empty<int>();
            /// <summary>Chord parameter per free notch, aligned with Nodes.</summary>
            public double[] Sigma = Array.Empty<double>();
            /// <summary>The span spacing in chord parameter.</summary>
            public double H;
            /// <summary>The same spacing as a LENGTH, H * L.</summary>
            public double G;
            /// <summary>L is zero by the bound of spec section 4.</summary>
            public bool ChordZero;
            /// <summary>Every notch falls at one chord parameter.</summary>
            public bool OneParameter;
            /// <summary>
            /// The chord parameter within which two candidate notches count
            /// as equidistant from a target: 1e-6 * H.
            /// </summary>
            public double TauSnap;
            /// <summary>
            /// The plan distance within which two feet of THIS span are the
            /// same point and become one node: 1e-9 * L.
            /// </summary>
            public double TauWeld;
        }

        /// <summary>
        /// The span's own frame. The chord parameters are NOT assumed to rise
        /// with bar order: a bar that is not plan-monotone disagrees, and
        /// nothing below reads an index where a parameter is meant or a
        /// parameter where an index is meant.
        ///
        /// The spacing is MEASURED rather than assumed, because a crossing, a
        /// free end or a crest that crowds its neighbours leaves the notches
        /// unevenly spread and the measured mean is then the span's own
        /// answer. It agrees exactly with the old 0.25 / (count + 1) form
        /// wherever the notches are uniform between the cuts.
        /// </summary>
        public static SpanFrame Frame(
            Point3d[] nodes, int[][] bars, Span span, IReadOnlyList<int> freePositions)
        {
            int[] bar = bars[span.Bar];
            var frame = new SpanFrame
            {
                P0 = nodes[bar[span.First]],
                P1 = nodes[bar[span.Last]],
                Positions = freePositions.ToArray(),
            };
            frame.Nodes = frame.Positions.Select(p => bar[p]).ToArray();

            double minX = Math.Min(frame.P0.X, frame.P1.X);
            double maxX = Math.Max(frame.P0.X, frame.P1.X);
            double minY = Math.Min(frame.P0.Y, frame.P1.Y);
            double maxY = Math.Max(frame.P0.Y, frame.P1.Y);
            foreach (int node in frame.Nodes)
            {
                minX = Math.Min(minX, nodes[node].X);
                maxX = Math.Max(maxX, nodes[node].X);
                minY = Math.Min(minY, nodes[node].Y);
                maxY = Math.Max(maxY, nodes[node].Y);
            }
            frame.D = Math.Sqrt(((maxX - minX) * (maxX - minX)) + ((maxY - minY) * (maxY - minY)));

            double dx = frame.P1.X - frame.P0.X;
            double dy = frame.P1.Y - frame.P0.Y;
            frame.L = Math.Sqrt((dx * dx) + (dy * dy));
            // A span's CHORD LENGTH IS ZERO when L <= 1e-9 * D. Where D is
            // itself zero, so that every node stands at one plan point, the
            // span is degenerate by the same rule.
            frame.ChordZero = frame.L <= 1.0e-9 * frame.D;
            if (frame.ChordZero)
            {
                frame.C = new Vector3d(1.0, 0.0, 0.0);
                frame.N = new Vector3d(0.0, 1.0, 0.0);
            }
            else
            {
                frame.C = new Vector3d(dx / frame.L, dy / frame.L, 0.0);
                frame.N = new Vector3d(-frame.C.Y, frame.C.X, 0.0);
            }
            frame.M = new Point3d(
                0.5 * (frame.P0.X + frame.P1.X), 0.5 * (frame.P0.Y + frame.P1.Y), 0.0);

            int m = frame.Nodes.Length;
            frame.Sigma = new double[m];
            for (int i = 0; i < m; i++)
            {
                frame.Sigma[i] = frame.ChordZero
                    ? 0.5
                    : (((nodes[frame.Nodes[i]].X - frame.P0.X) * frame.C.X)
                        + ((nodes[frame.Nodes[i]].Y - frame.P0.Y) * frame.C.Y)) / frame.L;
            }
            double smallest = m > 0 ? frame.Sigma.Min() : 0.0;
            double largest = m > 0 ? frame.Sigma.Max() : 0.0;
            frame.OneParameter = (largest - smallest) <= 1.0e-9;
            frame.H = (m >= 2 && !frame.OneParameter)
                ? (largest - smallest) / (m - 1)
                : 1.0 / (m + 1);
            frame.G = frame.H * (frame.ChordZero ? frame.D : frame.L);
            frame.TauSnap = 1.0e-6 * frame.H;
            frame.TauWeld = 1.0e-9 * (frame.ChordZero ? frame.D : frame.L);
            return frame;
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

        /// <summary>One Type level, built and judged.</summary>
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
            /// <summary>
            /// Trees the level ASSIGNED to a shared foot, BEFORE the peel
            /// runs: every tree of a group whose size is more than one.
            /// Peeled counts a subset of these, so the two together say
            /// whether ANY trunk reached the shared feet.
            /// </summary>
            public int Gathered;
            /// <summary>Pairs of feet inside the clearance that stayed two.</summary>
            public int FeetClose;
            public double WorstLean;
            public double WorstAlignment;
            public double WorstBranchOff;
            public int Collisions;
            /// <summary>
            /// Trees with no thrust line to follow at all, because the net
            /// pulls their notch onto the column rather than off it, which is
            /// the one input <c>MouldGeometry.AimFrom</c> answers with plain
            /// vertical. NOT the trees the dead band stood plumb: those have a
            /// thrust line and it is within two degrees of vertical.
            /// <c>ColumnsComponent</c> reads this as columns.plumb_fallback.
            /// </summary>
            public int PlumbTrees;
            /// <summary>
            /// Trees standing alone in the middle of an ODD row at an EVEN
            /// Type, by the clause of spec section 7. Counted BY
            /// CONSTRUCTION and never by testing a distance to a plane.
            /// </summary>
            public int CentralColumns;
            /// <summary>The largest snap distance as a fraction of its own span's g.</summary>
            public double SnapWorst;
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
            /// <summary>
            /// Each span's own frame, aligned with <see cref="Spans"/>. Every
            /// tolerance in this engine is a formula in these terms.
            /// </summary>
            public List<SpanFrame> Frames = new();
            /// <summary>
            /// The mirror partner of each tree: the tree it pairs with about
            /// its span's midpoint, ITSELF for the centre tree of an odd
            /// count, -1 where there is no partner at all: the ring tree, and
            /// every tree of a span whose free notches are not symmetric about
            /// its chord midpoint (see <c>AsymmetricSpans</c>).
            /// </summary>
            public int[] Partner = Array.Empty<int>();
            /// <summary>The largest angle Symmetrise moved an aim through, in degrees.</summary>
            public double AsymmetryRemoved;
            /// <summary>
            /// How many families were actually averaged: the spans alike in
            /// free-notch count, in Branching and in chord length, counted
            /// AFTER the guard that drops a family whose spans disagree on
            /// tree count, so the number reported is the number shared.
            /// </summary>
            public int Families;
            /// <summary>Trees that are their own mirror partner.</summary>
            public int CentreTrees;
            /// <summary>
            /// Spans placed UNMIRRORED, because their free notches are not
            /// symmetric about their chord midpoint: a crossing that took an
            /// interior notch, or a free bar end that put the first notch on
            /// the chord's own start. Mirroring those would pair trees that do
            /// not straddle the mirror plane.
            /// </summary>
            public int AsymmetricSpans;
            /// <summary>
            /// Spans holding at least one tree. A span whose only free notches
            /// were already claimed by a crossing or by the ring tree holds
            /// none, and is not a span the symmetry rules ever touch.
            /// </summary>
            public int SpansWithTrees;
            /// <summary>
            /// Set once <c>Symmetrise</c> has run. A second call on the same
            /// Placement with the same trees is a no-op: it would otherwise
            /// overwrite <c>Tree.RawResultant</c> with the already-symmetrised
            /// vector and report an <c>AsymmetryRemoved</c> of zero.
            /// </summary>
            public bool Symmetrised;
            /// <summary>
            /// The tree count at the last <c>Symmetrise</c>. The guard keys on
            /// this as well as the flag, so a tree added after the first call
            /// is symmetrised rather than left standing on its raw aim.
            /// </summary>
            public int SymmetrisedTrees = -1;
        }

        // ------------------------------------------------------------------
        // Grouping

        /// <summary>
        /// Positions 0..count-1, in BAR ORDER along the span, grouped into
        /// trees by THE LADDER of spec section 5: a span's stations are the
        /// CENTRE, then the outermost mirrored pair, then the next pair
        /// inward, and when n things are placed the centre station is
        /// occupied if and only if n is odd.
        ///
        /// Two properties constrain the layout before any counting begins,
        /// and neither reads a coordinate. The sequence of tree sizes is a
        /// PALINDROME about the row centre by index, so tree i and tree
        /// T-1-i hold the same number of notches. And a tree that STRADDLES
        /// the row centre has ODD size, because a straddling tree of even
        /// size has two equally inner notches and the choice between them is
        /// a coin toss that puts the fork off the centre.
        ///
        /// The centre tree size k is then chosen by FEWEST STRAYS, which is
        /// Param's ruling of 2026-09-01. A stray is a REMAINDER tree of one
        /// notch, not merely a tree of one notch: at Branching 1 every tree
        /// holds one notch and none of them is a stray. Where two admissible
        /// k leave equally few strays the SMALLER wins, which is what the
        /// shipped engine always picked, so on a tie no column moves; the
        /// tie is unreachable for Branching 1 to 3 and the clause is there
        /// for totality. Anyone raising Branching past three must revisit
        /// this method rather than leaning on the ladder's fourth rung.
        ///
        /// The MAIN notch of a group is its innermost, the one nearest the
        /// row centre by index, so mirrored groups have mirrored mains.
        /// </summary>
        public static (int[][] Groups, int[] Mains) Group(int count, int branching)
        {
            branching = Math.Min(Math.Max(branching, 1), MaxBranching);
            if (count <= 0)
                return (Array.Empty<int[]>(), Array.Empty<int>());

            int[] sizes = Layout(count, branching);
            var groups = new int[sizes.Length][];
            var mains = new int[sizes.Length];
            double rowCentre = (count - 1) / 2.0;
            int at = 0;
            for (int g = 0; g < sizes.Length; g++)
            {
                groups[g] = Enumerable.Range(at, sizes[g]).ToArray();
                int main = groups[g][0];
                double best = Math.Abs(main - rowCentre);
                foreach (int p in groups[g])
                {
                    double d = Math.Abs(p - rowCentre);
                    if (d < best - 1.0e-12)
                    {
                        best = d;
                        main = p;
                    }
                }
                mains[g] = main;
                at += sizes[g];
            }
            return (groups, mains);
        }

        /// <summary>
        /// The tree sizes along the span, anchor to anchor. Each half is
        /// tiled from the CENTRE OUTWARD with trees of size B and the
        /// leftover rem notches at the ANCHOR END form one tree of size rem,
        /// which is a stray when rem is 1. The remainder trees therefore land
        /// on the ladder's stations by construction: the centre tree when k
        /// is 1, and the two anchor-end trees when rem is not zero. There are
        /// at most three of them, which is why the ladder is never asked for
        /// four.
        /// </summary>
        private static int[] Layout(int count, int branching)
        {
            if (branching == 1)
                return Enumerable.Repeat(1, count).ToArray();

            // Admissible centre tree sizes: 0 when the count is even, 1 when
            // it is odd, and 3 when it is odd, B is at least 3 and there are
            // at least three notches to hold.
            var admissible = new List<int>();
            if ((count % 2) == 0)
                admissible.Add(0);
            else
                admissible.Add(1);
            if ((count % 2) == 1 && branching >= 3 && count >= 3)
                admissible.Add(3);

            int chosen = -1;
            int fewest = int.MaxValue;
            foreach (int k in admissible)
            {
                int halfLength = (count - k) / 2;
                int remainder = halfLength % branching;
                int strays = (k == 1 ? 1 : 0) + (remainder == 1 ? 2 : 0);
                if (strays < fewest || (strays == fewest && k < chosen))
                {
                    fewest = strays;
                    chosen = k;
                }
            }

            int hlf = (count - chosen) / 2;
            int rem = hlf % branching;
            var left = new List<int>();
            if (rem > 0)
                left.Add(rem);
            for (int i = 0; i < hlf / branching; i++)
                left.Add(branching);

            var sizes = new List<int>(left);
            if (chosen > 0)
                sizes.Add(chosen);
            for (int i = left.Count - 1; i >= 0; i--)
                sizes.Add(left[i]);
            return sizes.ToArray();
        }

        /// <summary>
        /// A span's T trees, IN BAR ORDER, cut into contiguous FOOT GROUPS by
        /// the ladder. Every tree of a group stands on that group's one foot.
        /// Nothing about a tree except its position in the row is read, and
        /// the row is the row <see cref="Group"/> built, so on a bar that is
        /// not plan-monotone the groups follow the bar and not the chord
        /// parameter.
        ///
        /// A span with fewer trees than the Type asks for places one foot per
        /// tree and no more; a foot with no tree is not built. A span of ODD
        /// tree count at an EVEN Type takes its middle tree out as a group of
        /// ONE, standing straight on its own foot, which is PARAM'S RULING of
        /// 2026-09-01: he objected to "just moving the standing coloumn for
        /// symmetry reasons away from center when it shold obviously default
        /// to center". Type names the number of GATHERED feet per span, so
        /// such a span shows N gathered feet and one further column.
        ///
        /// The returned Central is that tree's index, or -1 where the clause
        /// did not fire. It is defined BY CONSTRUCTION, never by testing a
        /// distance to a plane, because on an asymmetric notch row that foot
        /// is not on the plane and a positional test would need a bound
        /// nothing has given it.
        /// </summary>
        public static (int[][] Groups, int Central) FootGroups(int treeCount, int type)
        {
            if (treeCount <= 0)
                return (Array.Empty<int[]>(), -1);
            int n = Math.Min(Math.Max(type, 1), MaxGround);
            if (treeCount <= n)
                return (Enumerable.Range(0, treeCount).Select(i => new[] { i }).ToArray(), -1);

            int central = -1;
            int t2 = treeCount;
            if ((treeCount % 2) == 1 && (n % 2) == 0)
            {
                central = treeCount / 2;
                t2 = treeCount - 1;
            }

            int q = t2 / n;
            int s = t2 % n;
            var sizes = new int[n];
            for (int j = 0; j < n; j++)
                sizes[j] = q;
            if (s == 1)
            {
                // Only reachable at an ODD N, where there IS a centre station.
                sizes[n / 2] += 1;
            }
            else if (s == 2)
            {
                sizes[0] += 1;
                sizes[n - 1] += 1;
            }

            // Lay the groups along the span, stepping over the central tree
            // and inserting it as its own group at the middle of the row,
            // which is the only station a single thing can occupy without
            // choosing a side.
            var groups = new List<int[]>();
            int at = 0;
            for (int j = 0; j < n; j++)
            {
                if (central >= 0 && j == n / 2)
                    groups.Add(new[] { central });
                var members = new List<int>();
                while (members.Count < sizes[j])
                {
                    if (at == central)
                        at++;
                    members.Add(at);
                    at++;
                }
                groups.Add(members.ToArray());
            }
            return (groups.ToArray(), central);
        }

        /// <summary>
        /// Where a group's foot stands, on ONE span. Param's rule, quoted:
        /// "best is to take the closest points to center from the principle
        /// lines and then get them to all point inwards where they touch".
        ///
        /// THE GROUP'S CENTRE is (t_min + t_max) / 2, the midpoint of the
        /// stretch of chord the group's own notches occupy. Not the mean of
        /// all its parameters, not the middle index, and not any plane of the
        /// span: the midpoint of the stretch is the centre of the group's own
        /// piece of the principal line, which is what his phrase names, and
        /// it commutes with the mirror.
        ///
        /// THE CANDIDATES are the notches nearest that centre: one notch
        /// where it is nearer than every other by more than TauSnap, and
        /// every notch within TauSnap of the nearest distance otherwise. The
        /// foot is their plan MEAN. There is no further tie-break, because
        /// the mean of any set of tied candidates is well defined, is
        /// independent of the order they are listed in, and commutes with the
        /// mirror. On an evenly spaced row this reduces to the familiar
        /// answer: an ODD count gives one candidate, the middle notch; an
        /// EVEN count gives two, tied to the last bit.
        ///
        /// The least-squares system of spec section 8.3 is NOT solved,
        /// because the candidates come from one span. A single line does not
        /// need to be intersected with itself to find its own middle, and on
        /// a bar that curves gently in plan the two central notches' tangents
        /// are nearly parallel and meet hundreds of metres away toward the
        /// centre of curvature.
        ///
        /// A group with two tied candidates stands at their midpoint and is
        /// NOT snapped to either: snapping would move the foot half a notch
        /// spacing to a side chosen by nothing, and on the centre group it
        /// would move the one column Param ruled must stand straight. That is
        /// the single stated departure from the letter of his snap ruling and
        /// spec section 18.3 leaves it open for him.
        ///
        /// Every notch of the group is listed, whether it is OWNED or
        /// BORROWED at a shared node, because a borrowed notch is still a
        /// point on this line.
        /// </summary>
        private static Point3d GroupFoot(
            Point3d[] nodes,
            SpanFrame frame,
            IReadOnlyList<int> notchIndices,
            double ground,
            out double snapDistance)
        {
            double smallest = double.MaxValue;
            double largest = double.MinValue;
            foreach (int i in notchIndices)
            {
                smallest = Math.Min(smallest, frame.Sigma[i]);
                largest = Math.Max(largest, frame.Sigma[i]);
            }
            double centre = 0.5 * (smallest + largest);

            double nearest = double.MaxValue;
            foreach (int i in notchIndices)
                nearest = Math.Min(nearest, Math.Abs(frame.Sigma[i] - centre));

            double sumX = 0.0;
            double sumY = 0.0;
            int taken = 0;
            foreach (int i in notchIndices)
            {
                if (Math.Abs(frame.Sigma[i] - centre) > nearest + frame.TauSnap)
                    continue;
                sumX += nodes[frame.Nodes[i]].X;
                sumY += nodes[frame.Nodes[i]].Y;
                taken++;
            }
            var foot = new Point3d(sumX / taken, sumY / taken, ground);

            // The SNAP DISTANCE: how far the foot stands from the nearest
            // candidate notch, so that a coarse bar shows up as a coarse bar
            // rather than as a surprise.
            snapDistance = double.MaxValue;
            foreach (int i in notchIndices)
            {
                if (Math.Abs(frame.Sigma[i] - centre) > nearest + frame.TauSnap)
                    continue;
                snapDistance = Math.Min(snapDistance,
                    Math.Sqrt(MouldGeometry.PlanDistanceSquared(foot, nodes[frame.Nodes[i]])));
            }
            return foot;
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
        /// its own partner and its along part is zero.
        ///
        /// A span is only mirrored when it CAN be: when its free notches are
        /// symmetric about its chord midpoint, each notch's partner standing
        /// within a quarter of THAT SPAN'S notch spacing of where the mirror
        /// would put it, which in chord parameter is 0.25 / (count + 1).
        /// A crossing that takes an interior notch, or a bar end that is
        /// neither anchor nor rim and so puts a notch on the chord's own
        /// start, leaves a free list whose index i and index m-1-i are not
        /// geometric mirrors at all, and forcing them equal and opposite would
        /// move feet toward a plane nothing straddles. Such a span keeps its
        /// own aims, takes its bands from each tree's own projection, merges
        /// nothing, and is counted in AsymmetricSpans.
        ///
        /// A FAMILY then shares the ALONG and DOWN profiles only, and every
        /// span keeps its OWN across. That is what makes the frame's one
        /// arbitrary choice, which end of the bar Pattern traced first, drop
        /// out of the answer entirely. Read a span in either node order and
        /// the pair step leaves along ANTISYMMETRIC and down SYMMETRIC, so
        /// along[i] and down[i] come out the same both ways and can be
        /// averaged at face value; across comes out NEGATED, and is left
        /// alone, so it is rebuilt against the same negated normal and lands
        /// back in the world where the net put it. Bars congruent by
        /// TRANSLATION (a barrel whose bars are traced in mixed directions)
        /// and by ROTATION (opposite ribs of a dome, chord and pull turned
        /// together) therefore both carry the same columns, by construction
        /// and with no test to get wrong.
        ///
        /// Sharing across as well needed a rule for which way round a span
        /// was, and every such rule has a null: a rib lying IN the structure's
        /// own mirror plane, pulled equally from both sides, has no opinion,
        /// and would take the family's across in a frame that exists only
        /// because a curve was drawn left to right. It would lean out of the
        /// plane it lies in, and to the other side if the curve were redrawn.
        /// The across a span needs is its own, mirrored within itself by the
        /// pair step, which is what 3.4 always said it was.
        ///
        /// A family is the spans alike in free-notch count, in Branching (one
        /// slider, so alike by construction) and in chord LENGTH within a
        /// tenth of the family LEAD's. Length is in the key because the aim is
        /// shared, and a short steep span handed a long flat one's aim can put
        /// its foot beyond its own anchors. Measuring against the lead rather
        /// than pairwise makes the bucketing non-transitive and order
        /// dependent, which is deliberate: it is a cheap grouping of like with
        /// like, not an equivalence relation. A span like no other is its own
        /// family and keeps its own aims. An aim within PlumbDegrees of
        /// vertical is vertical.
        ///
        /// Tree.Load is deliberately NOT averaged. The forces a tree reports
        /// are its own; only WHERE IT STANDS is shared.
        /// </summary>
        public static double Symmetrise(Placement placement, Point3d[] nodes, int[][] bars)
        {
            // Called exactly once per Place, but guarded rather than trusted:
            // Tasks 2 and 3 edit around this call site, and a second call
            // would overwrite RawResultant with the already-symmetrised
            // vector and report the asymmetry removed as zero. The guard keys
            // on the TREE COUNT as well as the flag, so a caller that adds a
            // tree to a Placement already symmetrised gets the whole set
            // symmetrised again rather than a silent no-op that would leave
            // the new tree standing on its own raw aim.
            if (placement.Symmetrised && placement.SymmetrisedTrees == placement.Trees.Count)
                return placement.AsymmetryRemoved;
            placement.Symmetrised = true;
            placement.SymmetrisedTrees = placement.Trees.Count;

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
            placement.AsymmetricSpans = 0;
            placement.SpansWithTrees = 0;
            if (count == 0)
                return 0.0;

            // Span frames, and each span's trees in grouping order: they are
            // added to Trees span by span, group by group, so insertion order
            // IS grouping order.
            int spanCount = placement.Spans.Count;
            var chord = new Vector3d[spanCount];
            var normal = new Vector3d[spanCount];
            var chordLength = new double[spanCount];
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
                chordLength[s] = length;
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

            // Which spans can be mirrored at all. A span is SYMMETRIC when
            // every free notch's chord parameter s has a partner at 1 - s: the
            // sorted parameters then pair off across the midpoint, which is
            // exactly what index i and index m-1-i of the grouping claim to
            // be. The free notches are the nodes the span's trees hold, every
            // one of them in exactly one tree. A crossing that took an
            // interior notch, or a free bar end that put the first notch at
            // parameter zero, breaks it.
            //
            // The tolerance is a quarter of THIS SPAN'S notch spacing. In
            // chord parameter that is 0.25 / (count + 1): count notches cut
            // the chord into count + 1 gaps, so one gap is 1 / (count + 1) of
            // it. The span's own count, not the net's median plan edge, which
            // is a median over every edge in both mesh directions and stands
            // in no fixed ratio to the spacing along any one bar: on a mesh
            // refined along its principal lines that median is several notch
            // spacings and the test stops discriminating, and on one refined
            // across them it is a fraction of one and the test becomes exact
            // coincidence again.
            //
            // The positions being compared come out of the solve, not off the
            // curve the author drew, so they are never mirrored to the last
            // digit: an exact-coincidence tolerance would call an ordinary
            // relaxed arch asymmetric and quietly hand it back its pre-branch
            // placement. A quarter of the spacing is a constant factor of four
            // inside the failures this test exists to catch, which move a
            // notch by a whole spacing or more (a crossing takes one out; a
            // free end shifts every partner by half of one), and far outside
            // the millimetres a solver moves a node it meant to leave alone.
            //
            // A span with a free END has one interval fewer than count + 1,
            // an error of one part in count that a quarter-spacing bound does
            // not notice.
            var symmetric = new bool[spanCount];
            var parameters = new List<double>();
            for (int s = 0; s < spanCount; s++)
            {
                if (order[s].Count == 0)
                    continue;
                placement.SpansWithTrees++;
                Span span = placement.Spans[s];
                int[] bar = bars[span.Bar];
                Point3d first = nodes[bar[span.First]];
                Point3d last = nodes[bar[span.Last]];
                parameters.Clear();
                foreach (int t in order[s])
                {
                    foreach (int node in trees[t].Nodes)
                        parameters.Add(ChordParameter(first, last, nodes[node]));
                }
                parameters.Sort();
                double spacing = parameters.Count > 0
                    ? 0.25 / (parameters.Count + 1)
                    : 1.0;
                symmetric[s] = true;
                for (int i = 0; i < parameters.Count; i++)
                {
                    double partner = parameters[parameters.Count - 1 - i];
                    if (Math.Abs(parameters[i] + partner - 1.0) > spacing)
                    {
                        symmetric[s] = false;
                        break;
                    }
                }
                if (!symmetric[s])
                    placement.AsymmetricSpans++;
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

            // Mirror pairs, per span. An asymmetric span has no pairs at all:
            // its trees keep Partner -1, which is what makes BuildLevel read
            // each of their bands off its own projection and MergeFeet leave
            // them alone.
            for (int s = 0; s < spanCount; s++)
            {
                if (!symmetric[s])
                    continue;
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

            // Families: the symmetric spans alike in free-notch count (hence
            // in tree count and layout at this one Branching) and in chord
            // LENGTH within a tenth of the family LEAD's. Length is in the key
            // because the family shares an AIM: without it a three metre span
            // and a ten metre one holding the same number of notches average
            // together, and the short one takes an aim that can throw its foot
            // past its own anchors. Measuring against the lead makes the
            // grouping order dependent and non-transitive, which is what a
            // bucket is; it is not claiming to be an equivalence relation. A
            // span that matches no family is its own family, and averaging it
            // with itself changes nothing.
            var families = new List<List<int>>();
            var familyNotches = new List<int>();
            var familyLength = new List<double>();
            for (int s = 0; s < spanCount; s++)
            {
                if (order[s].Count == 0 || !symmetric[s])
                    continue;
                int notches = order[s].Sum(t => trees[t].Nodes.Length);
                int found = -1;
                for (int f = 0; f < families.Count && found < 0; f++)
                {
                    if (familyNotches[f] != notches)
                        continue;
                    if (Math.Abs(chordLength[s] - familyLength[f]) > 0.10 * familyLength[f])
                        continue;
                    found = f;
                }
                if (found < 0)
                {
                    families.Add(new List<int>());
                    familyNotches.Add(notches);
                    familyLength.Add(chordLength[s]);
                    found = families.Count - 1;
                }
                families[found].Add(s);
            }
            foreach (List<int> family in families)
            {
                int lead = family[0];
                int m = order[lead].Count;
                if (family.Any(s => order[s].Count != m))
                    continue;
                placement.Families++;
                // ALONG and DOWN only. Both are node-order invariant after the
                // pair step, along by being antisymmetric and down by being
                // symmetric, so tree i of one span and tree i of another are
                // the same tree of the family whichever way either bar was
                // traced. ACROSS is not: it comes out negated when a bar is
                // traced the other way, and there is no way to tell which way
                // round a span is that does not fail on a span pulled equally
                // from both sides. So across stays the span's own, already
                // mirrored within the span by the pair step.
                var meanAlong = new double[m];
                var meanDown = new double[m];
                foreach (int s in family)
                {
                    for (int i = 0; i < m; i++)
                    {
                        int t = order[s][i];
                        meanAlong[i] += along[t];
                        meanDown[i] += down[t];
                    }
                }
                for (int i = 0; i < m; i++)
                {
                    meanAlong[i] /= family.Count;
                    meanDown[i] /= family.Count;
                }
                foreach (int s in family)
                {
                    for (int i = 0; i < m; i++)
                    {
                        int t = order[s][i];
                        along[t] = meanAlong[i];
                        down[t] = meanDown[i];
                    }
                }
            }

            // Back into each span's own frame, with the dead band, and the
            // angle every aim moved through. An asymmetric span was never
            // read into a pair or a family, so it is handed back the
            // resultant it came in with; the dead band is not part of the
            // mirror machinery and still applies, because a degree of
            // residual lean out of a solved net is noise on any span.
            double moved = 0.0;
            for (int t = 0; t < count; t++)
            {
                Tree tree = trees[t];
                if (tree.Ring || tree.Span < 0 || tree.Span >= spanCount)
                    continue;
                int s = tree.Span;
                Vector3d rebuilt = symmetric[s]
                    ? new Vector3d(
                        (along[t] * chord[s].X) + (across[t] * normal[s].X),
                        (along[t] * chord[s].Y) + (across[t] * normal[s].Y),
                        down[t])
                    : tree.Resultant;
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
        /// then BarTransverse). <paramref name="pull"/> is that same notch's
        /// UNTRANSVERSED pull, and <paramref name="nodePull"/> is the whole
        /// incident pull per NET NODE (MouldGeometry.NodeLoads): spec section
        /// 10's head-pull arithmetic reads both, starting at Task 6, so that
        /// a notch held by several bars is counted exactly once and in full.
        /// <paramref name="edges"/> is the net's edge list; spec section 4
        /// threads it through so that every tolerance below can be judged in
        /// the terms of the span, or the pair of spans, it applies to, rather
        /// than the net's median plan edge. <paramref name="perimeterLoops"/>
        /// are the boundary loops as net vertex lists; an empty array means
        /// no rim can be detected and no ring tree is placed.
        /// <paramref name="groundAsked"/> is 0 to MaxGround, or -1 for Auto.
        /// </summary>
        public static Placement Place(
            Point3d[] nodes,
            int[][] bars,
            (int, int)[] edges,
            int[] anchors,
            Vector3d[][] across,
            Vector3d[][] pull,
            Vector3d[] nodePull,
            int[][] perimeterLoops,
            double ground,
            int branching,
            int groundAsked)
        {
            // Neither pull nor nodePull is optional and neither has a
            // default: a null or short array is a programming error and not a
            // fallback, because the head-pull arithmetic of spec section 10
            // has no answer without them.
            if (pull is null || pull.Length != bars.Length)
                throw new ArgumentException("pull is the untransversed pull per bar and bar position, one array per bar.", nameof(pull));
            if (nodePull is null || nodePull.Length != nodes.Length)
                throw new ArgumentException("nodePull is the whole incident pull per NET NODE, one entry for every node.", nameof(nodePull));
            if (edges is null)
                throw new ArgumentException("edges is the net's edge list, which decides which spans are adjacent.", nameof(edges));

            branching = Math.Min(Math.Max(branching, 1), MaxBranching);
            var anchorSet = new HashSet<int>(anchors);
            var placement = new Placement { GroundAsked = groundAsked };

            var held = new HashSet<int>();
            Tree? ring = RingTree(nodes, bars, anchorSet, across, perimeterLoops, ground, held);
            if (ring is not null)
            {
                placement.RingTree = ring;
                placement.Trees.Add(ring);
            }

            placement.Spans = Spans(bars, anchorSet, held);
            for (int s = 0; s < placement.Spans.Count; s++)
            {
                Span span = placement.Spans[s];
                // Free notches: everything the span holds that nothing has
                // taken yet. A notch shared with an earlier bar (a crossing)
                // is already held and is skipped; it does not cut the span.
                int[] free = span.Free.Where(p => !held.Contains(bars[span.Bar][p])).ToArray();
                SpanFrame frame = Frame(nodes, bars, span, free);
                placement.Frames.Add(frame);
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
                        Span = s,
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
                Level built = BuildLevel(nodes, placement, bars, anchorSet, ground, level);
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
                    Level built = BuildLevel(nodes, placement, bars, anchorSet, ground, level);
                    placement.Tried.Add(built);
                    if (bestAny is null || built.LoadPath < bestAny.LoadPath)
                        bestAny = built;
                    if (built.Feasible && (best is null || built.LoadPath < best.LoadPath))
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

        /// <summary>
        /// The tree's own span spacing as a LENGTH. The ring tree has no
        /// span, so its scale R is the smallest plan distance between two of
        /// its own rim notches, which is in its own terms and needs no net
        /// median.
        /// </summary>
        private static double SpacingOf(Placement placement, Point3d[] nodes, int tree)
        {
            Tree t = placement.Trees[tree];
            if (!t.Ring && t.Span >= 0 && t.Span < placement.Frames.Count)
                return placement.Frames[t.Span].G;
            double smallest = double.MaxValue;
            for (int i = 0; i < t.Nodes.Length; i++)
            {
                for (int j = i + 1; j < t.Nodes.Length; j++)
                {
                    double d = Math.Sqrt(MouldGeometry.PlanDistanceSquared(nodes[t.Nodes[i]], nodes[t.Nodes[j]]));
                    if (d > 0.0)
                        smallest = Math.Min(smallest, d);
                }
            }
            return smallest < double.MaxValue ? smallest : 1.0;
        }

        private static Level BuildLevel(
            Point3d[] nodes,
            Placement placement,
            int[][] bars,
            HashSet<int> anchors,
            double ground,
            int level)
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
                // THE INVERSION (spec section 3, step 8). No tree's aim, load
                // or resultant is consulted anywhere in here: a foot's
                // position is a function of the span's own notch positions,
                // the span's tree count and the Type. That is what makes a
                // foot stable under a solve change, and it is why the band
                // rule that rebuilt a foot from its surviving trees is gone
                // along with the bands.
                var spanTrees = new List<int>[placement.Spans.Count];
                for (int s = 0; s < spanTrees.Length; s++)
                    spanTrees[s] = new List<int>();
                for (int t = 0; t < trees.Count; t++)
                {
                    Tree tree = trees[t];
                    if (tree.FixedFoot is Point3d ringFoot)
                    {
                        foot[t] = ringFoot;
                        continue;
                    }
                    if (tree.Span >= 0 && tree.Span < spanTrees.Length)
                        spanTrees[tree.Span].Add(t);
                }

                for (int s = 0; s < spanTrees.Length; s++)
                {
                    List<int> row = spanTrees[s];
                    if (row.Count == 0)
                        continue;
                    SpanFrame frame = placement.Frames[s];
                    (int[][] groups, int central) = FootGroups(row.Count, level);
                    if (central >= 0)
                        result.CentralColumns++;
                    var notchIndex = new Dictionary<int, int>();
                    for (int i = 0; i < frame.Nodes.Length; i++)
                        notchIndex[frame.Nodes[i]] = i;
                    foreach (int[] group in groups)
                    {
                        var indices = new List<int>();
                        foreach (int j in group)
                        {
                            foreach (int node in trees[row[j]].Nodes)
                            {
                                if (notchIndex.TryGetValue(node, out int at))
                                    indices.Add(at);
                            }
                        }
                        if (indices.Count == 0)
                            continue;
                        Point3d placedFoot = GroupFoot(nodes, frame, indices, ground, out double snap);
                        foreach (int j in group)
                        {
                            foot[row[j]] = placedFoot;
                            // Gathered counts the trees the level ASSIGNED to
                            // a SHARED foot, BEFORE the peel runs, which is
                            // exactly what Banded counted. The centre tree
                            // standing alone takes no shared foot and is not
                            // one of them, which is what lets the component
                            // tell "some trunks stepped off" from "nothing
                            // gathered at all".
                            if (group.Length > 1)
                                result.Gathered++;
                        }
                        if (frame.G > 1.0e-12)
                            result.SnapWorst = Math.Max(result.SnapWorst, snap / frame.G);
                    }
                }

                // THE PEEL (spec section 11). A tree whose trunk from its
                // assigned foot to its main notch leans past the cap stands
                // instead on its Type 0 foot. A peel NEVER MOVES A FOOT: a
                // foot's position does not depend on the trees standing on
                // it, so the rebuild-and-rejudge loop the band rule needed is
                // gone with the bands, and a foot left with no trees is not
                // built.
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null)
                        continue;
                    double lean = MouldGeometry.LeanFromVertical(foot[t], nodes[trees[t].Nodes[0]]);
                    if (lean <= MouldGeometry.MaxLeanDegrees + 1.0e-9)
                        continue;
                    foot[t] = own[t];
                    result.Peeled++;
                }
            }

            // Each tree's own span spacing, read once and threaded through
            // both the merge and the close count so a five-notch span and a
            // twenty-one-notch span on the same net answer for their own
            // feet alone.
            var spacing = new double[trees.Count];
            for (int t = 0; t < trees.Count; t++)
                spacing[t] = SpacingOf(placement, nodes, t);
            var footSpacing = new List<double>();
            int[] footIndex = MergeFeet(
                placement, nodes, foot, spacing, result.Nodes, footSpacing,
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
                // puts a foot in mid-air in Frame's Columns, drops the head
                // out of Fit's held set and makes Animate drive a held head
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
            // The COLLISION CLEARANCE is 0.05 * g of the tree whose member is
            // being judged, and 0.05 * min(g_A, g_B) where two members of
            // different spans are judged against one another, which is the
            // minimum of their two clearances. This is a knowing change to a
            // measure that is not a placement rule: it will move collision
            // counts and with them Auto's choice on some nets.
            var memberClearance = new double[result.Members.Count];
            for (int mm = 0; mm < result.Members.Count; mm++)
                memberClearance[mm] = ClearanceFraction * SpacingOf(placement, nodes, result.MemberTree[mm]);
            result.Collisions = CountCollisions(result, nodes, anchors, memberClearance);
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
        /// The same parameter for any plan point against any chord: how far
        /// along from <paramref name="a"/> to <paramref name="b"/> it
        /// projects. A chord of no length puts everything at its middle.
        /// </summary>
        private static double ChordParameter(Point3d a, Point3d b, Point3d point)
        {
            double cx = b.X - a.X;
            double cy = b.Y - a.Y;
            double chord = (cx * cx) + (cy * cy);
            return chord > 1.0e-18
                ? (((point.X - a.X) * cx) + ((point.Y - a.Y) * cy)) / chord
                : 0.5;
        }

        /// <summary>
        /// Where the feet become NODES, and the one case in which two of them
        /// become one.
        ///
        /// Feet at the SAME point are one node whatever put them there: two
        /// trees in one band, every tree of a span at Type 1, or two spans
        /// whose bands meet at a crossing. That is WELDING, and it is not a
        /// merge and is not counted. The weld tolerance is now the SPAN's
        /// own, off <see cref="SpanFrame.TauWeld"/>: one span's for two feet
        /// of that span, the smaller of two spans' for feet of two spans, and
        /// a tiny flat fallback for a foot with no span at all (the ring
        /// tree), which stands where the flat weld epsilon always did.
        ///
        /// Beyond that only a MIRRORED PAIR merges (spec 3.5): when its two
        /// feet lie within 0.25 of the SMALLER of the two trees' own span
        /// spacings (<c>SpacingOf</c>) the pair stands on one foot at the
        /// MEAN of the two, which on symmetric geometry is on the mirror
        /// plane, where its own symmetry says it belongs. Not the span's
        /// chord midpoint, which is where this stood: a pair's two feet
        /// differ only in their along-chord part, so the clearance test says
        /// nothing at all about how far off the chord they sit, and on a bar
        /// that curves in plan the innermost notches sit off it by the plan
        /// sagitta. Merging onto the chord midpoint moved such a pair sideways
        /// by that sagitta, out from under its own bar, with nothing measuring
        /// the move. Any other two feet inside the same 0.25 * spacing stay
        /// two and are counted in FeetClose, against the SMALLER of the two
        /// BUILT feet's own recorded spacings. Merging those was what turned
        /// leaning neighbours into accidental V's and X's on Param's review
        /// arch: two trees that lean toward one another are not one tree, and
        /// the ring tree's foot, fixed by 3.2, never merges at all.
        ///
        /// The merge and weld RULES are Task 8's; only their SCALE is span-
        /// local here, the shape unchanged: a mirrored pair merges, nothing
        /// else does, and welding stays exact coincidence.
        /// </summary>
        private static int[] MergeFeet(
            Placement placement,
            Point3d[] nodes,
            Point3d[] foot,
            double[] spacing,
            List<Point3d> levelNodes,
            List<double> footSpacing,
            out int merged,
            out int close)
        {
            int n = foot.Length;
            merged = 0;

            // The weld tolerance for a pair of feet: the span each foot's
            // tree stands on decides it, the smaller of two when the trees
            // disagree, and a flat fallback (matching the old weld epsilon
            // exactly) where a tree carries no span at all.
            double TauWeldSquared(int a, int b)
            {
                int spanA = placement.Trees[a].Span;
                int spanB = placement.Trees[b].Span;
                double tauA = spanA >= 0 && spanA < placement.Frames.Count ? placement.Frames[spanA].TauWeld : 1.0e-9;
                double tauB = spanB >= 0 && spanB < placement.Frames.Count ? placement.Frames[spanB].TauWeld : 1.0e-9;
                double tau = spanA == spanB ? tauA : Math.Min(tauA, tauB);
                return tau * tau;
            }

            for (int t = 0; t < n; t++)
            {
                int partner = t < placement.Partner.Length ? placement.Partner[t] : -1;
                // -1 is the ring tree or a tree on an unmirrored span, t is a
                // centre tree standing alone, and anything below t was handled
                // when its partner came round.
                if (partner <= t || partner >= n)
                    continue;
                if (placement.Trees[t].FixedFoot is not null ||
                    placement.Trees[partner].FixedFoot is not null)
                    continue;
                double gap = MouldGeometry.PlanDistanceSquared(foot[t], foot[partner]);
                double weldSquared = TauWeldSquared(t, partner);
                double mergeClearance = 0.25 * Math.Min(spacing[t], spacing[partner]);
                if (gap <= weldSquared || gap > mergeClearance * mergeClearance)
                    continue;
                var middle = new Point3d(
                    0.5 * (foot[t].X + foot[partner].X),
                    0.5 * (foot[t].Y + foot[partner].Y),
                    foot[t].Z);
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
                    if (MouldGeometry.PlanDistanceSquared(foot[t], foot[u]) <= TauWeldSquared(t, u) &&
                        Math.Abs(foot[t].Z - foot[u].Z) <= 1.0e-9)
                    {
                        footIndex[t] = footIndex[u];
                        break;
                    }
                }
                if (footIndex[t] < 0)
                {
                    levelNodes.Add(foot[t]);
                    footSpacing.Add(spacing[t]);
                    footIndex[t] = levelNodes.Count - 1;
                }
            }

            // What stands close but apart, counted once per pair of feet,
            // each pair judged against 0.25 of the SMALLER of the two BUILT
            // feet's own recorded spacings. The feet are the only nodes in
            // the level so far, which is why this runs here and not after
            // the members are built.
            close = 0;
            for (int i = 0; i < levelNodes.Count; i++)
            {
                for (int j = i + 1; j < levelNodes.Count; j++)
                {
                    double closeClearance = 0.25 * Math.Min(footSpacing[i], footSpacing[j]);
                    if (MouldGeometry.PlanDistanceSquared(levelNodes[i], levelNodes[j]) <= closeClearance * closeClearance)
                        close++;
                }
            }
            return footIndex;
        }

        // ------------------------------------------------------------------
        // Collisions

        /// <summary>
        /// Two members that share no end and come closer than the SMALLER of
        /// their two clearances collide. A member collides with the NET when
        /// its interior, sampled at 1/8 .. 7/8 of its length, rises above it:
        /// a sample whose Z is more than that member's OWN clearance above
        /// the Z of the net vertex nearest it IN PLAN. That is spec 3.7's net
        /// test entire, with the clearance no longer one number for the whole
        /// level but the span-local one spec section 4 asks for: spec section
        /// 19 puts the SHAPE of the two tests, member-to-member and member-
        /// to-net, out of scope, and only their per-member scale changes.
        ///
        /// It used to be more and less than that at once. It also refused a
        /// sample within the clearance of any net EDGE the member did not end
        /// on, a rule the spec does not state, which could refuse a Type
        /// level the spec accepts; and it narrowed the height test to
        /// vertices within half a median plan edge, which let a member rise
        /// above the net anywhere away from a vertex, and skipped the
        /// member's own notch, which took the one vertex a near-plumb column
        /// is actually under out of its own test. Both narrowings are gone.
        ///
        /// ANCHORS are still left out, and that is a deliberate, measured
        /// deviation from the spec's "nearest net vertex": an anchor sits ON
        /// the ground, and spec 3.5 puts every Type 0 foot out along the
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
            double[] memberClearance)
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
                    if (d < Math.Min(memberClearance[i], memberClearance[j]))
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
                    if (nearest >= 0 && p.Z > netNodes[nearest].Z + memberClearance[m])
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
