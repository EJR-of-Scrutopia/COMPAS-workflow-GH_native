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
            /// <summary>
            /// Whether this tree builds a member to that notch, aligned with
            /// <see cref="Nodes"/>. Spec section 10's three lists are not the
            /// same list: ALL notches enter the layout, the pairing, the
            /// group construction and the candidate set; only OWNED notches
            /// enter Load and Resultant; only owned notches receive a member.
            /// A borrowed notch enters Load with a load of zero because its
            /// head is not this tree's to carry.
            /// </summary>
            public bool[] Owned = Array.Empty<bool>();
            /// <summary>
            /// The index into <see cref="Nodes"/> of the tree's innermost
            /// OWNED notch, ties to the lower bar position. 0 on every tree
            /// that owns its main, which is every tree on a net with no
            /// crossing, and -1 on a tree with no owned notch, which builds
            /// nothing at all.
            /// </summary>
            public int HeadMain;
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
            /// its span's STRUCTURAL mirror plane (spec 9.2), ITSELF for a
            /// SELF-PAIRED tree, -1 for the ring tree and for every UNPAIRED
            /// tree (see <c>UnpairedTrees</c>).
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
            /// <summary>Trees that are their own mirror partner (SELF-PAIRED, spec 9.3).</summary>
            public int CentreTrees;
            /// <summary>
            /// Trees that found no mirror partner. It REPLACES
            /// AsymmetricSpans, because no span is placed unmirrored any
            /// more: the common mode goes by subtraction before any pairing
            /// runs, and an unpaired tree now costs only the sharing of one
            /// partner's across and down.
            /// </summary>
            public int UnpairedTrees;
            /// <summary>Spans every tree of which is paired or self-paired.</summary>
            public int ClosedSpans;
            /// <summary>
            /// The largest along-chord common mode still standing after
            /// placement, as a fraction of its own span's mean pull. It reads
            /// ZERO when the rule ran and large exactly when it did not, which
            /// is why it and not AsymmetryRemoved is the number to look at:
            /// the investigation measured AsymmetryRemoved FALLING from 75.40
            /// degrees to 1.81 the moment the mirror rule stopped running.
            /// </summary>
            public double CommonModeResidual;
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
            /// <summary>
            /// Spans of the two degenerate kinds of spec section 15: a chord
            /// of no length, and a notch row that falls at one chord
            /// parameter. Reported as columns.span_degenerate at warning;
            /// nothing refuses the level.
            /// </summary>
            public int SpanDegenerate;
            /// <summary>Notches held by two spans at once.</summary>
            public int SharedNotches;
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
        /// Remove the COMMON MODE by subtraction, locate the span's
        /// STRUCTURAL mirror plane from where the residual along-chord pull
        /// changes sign, pair trees about that plane by chord-parameter
        /// reflection, average CLOSED spans into families, and report the
        /// largest angle an aim moved through. Spec section 9, in order:
        ///
        /// 9.1 THE COMMON MODE GOES FIRST, BY SUBTRACTION, NOT BY PAIRING.
        /// Every non-ring tree's resultant is read in its span's frame as
        /// (along, across, down); for each span the MEAN along part over the
        /// trees that carry a resultant at all (<c>HeadMain >= 0</c>) is
        /// subtracted from every one of them, unconditionally, with no test
        /// to fail and no state in which the step is skipped.
        ///
        /// 9.2 THE MIRROR PLANE COMES FROM THE STRUCTURE, not the anchors.
        /// The span's trees are sorted by their MAIN NOTCH'S CHORD PARAMETER,
        /// ties to the lower bar position, and s_mirror is located from the
        /// sign change in the residual along part 9.1 leaves behind, falling
        /// back to the row centre by parameter where there is none (a span
        /// whose residuals are all deemed zero, or of fewer than two trees).
        /// It is not clamped to the chord.
        ///
        /// 9.3 THE PAIRING, PER TREE, BY PARAMETER. Tree i's candidate
        /// partner is whichever tree sits nearest its reflection about
        /// s_mirror; the pair is accepted on a mismatch of at most h / 4,
        /// mutuality, and an equal notch count; a tree that is its own
        /// nearest within h / 4 is SELF-PAIRED; everything else, including a
        /// tree with no owned notch, is UNPAIRED and keeps what 9.1 left it.
        ///
        /// 9.4 SYMMETRISE, AND THE INVARIANT. An accepted pair's along parts
        /// are made equal and opposite about their mean difference and its
        /// across and down replaced by the pair's means; a self-paired
        /// tree's along is zeroed; the family averaging of 9.5 runs; THE
        /// SPAN MEAN IS SUBTRACTED ONCE MORE, because the pair step can put
        /// a common mode back on a span holding unpaired trees; and only
        /// then does the dead band apply, so an aim within PlumbDegrees of
        /// vertical is vertical. AFTER PLACEMENT, EVERY SPAN'S MEAN
        /// ALONG-CHORD COMPONENT IS ZERO except where the dead band moved a
        /// tree.
        ///
        /// 9.5 THE FAMILIES. Only a CLOSED span, every tree of which is
        /// paired or self-paired, may join one; the rest is unchanged from
        /// spec 3.4: alike in free notch count, in Branching, and in chord
        /// length within a tenth of the family LEAD's; ALONG and DOWN shared
        /// by tree index, every span keeping its OWN across, which is what
        /// makes the frame's one arbitrary choice, which end of the bar was
        /// traced first, drop out of the answer entirely.
        ///
        /// 9.6 THE RESIDUAL. Placement.CommonModeResidual is the largest,
        /// over every span, of the surviving mean along part AS PLACED
        /// divided by the mean |resultant|, excluding trees the dead band
        /// moved and trees with no owned notch. It reads zero when the rule
        /// worked and large exactly when it did not, which is why it and not
        /// AsymmetryRemoved is the number to look at: the investigation
        /// measured AsymmetryRemoved FALLING from 75.40 degrees to 1.81 the
        /// moment the mirror rule stopped running.
        ///
        /// The RING TREE takes no part in any of this: it has no span, its
        /// foot is fixed, and it is not symmetrised. Tree.Load is
        /// deliberately NOT averaged by the family step: the forces a tree
        /// reports are its own; only WHERE IT STANDS is shared.
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
            placement.UnpairedTrees = 0;
            placement.ClosedSpans = 0;
            placement.SpansWithTrees = 0;
            placement.CommonModeResidual = 0.0;
            if (count == 0)
                return 0.0;

            int spanCount = placement.Spans.Count;

            // Each span's trees, IN BAR ORDER: they are added to Trees span
            // by span, group by group, so insertion order IS bar order, and
            // a tree's position in this list is the row index spec section 9
            // uses for its tie-breaks.
            var order = new List<int>[spanCount];
            for (int s = 0; s < spanCount; s++)
                order[s] = new List<int>();
            for (int t = 0; t < count; t++)
            {
                Tree tree = trees[t];
                if (tree.Ring || tree.Span < 0 || tree.Span >= spanCount)
                    continue;
                order[tree.Span].Add(t);
            }

            // Each tree's resultant, read once in its own span's frame as
            // (along, across, down), and its MAIN notch's chord parameter:
            // the one place this method reads parameter order rather than
            // bar order (9.2).
            var along = new double[count];
            var across = new double[count];
            var down = new double[count];
            var sParam = new double[count];
            for (int s = 0; s < spanCount; s++)
            {
                if (order[s].Count == 0)
                    continue;
                placement.SpansWithTrees++;
                SpanFrame frame = placement.Frames[s];
                foreach (int t in order[s])
                {
                    Vector3d r = trees[t].Resultant;
                    along[t] = (r.X * frame.C.X) + (r.Y * frame.C.Y);
                    across[t] = (r.X * frame.N.X) + (r.Y * frame.N.Y);
                    down[t] = r.Z;
                    sParam[t] = ChordParameter(frame.P0, frame.P1, nodes[trees[t].Nodes[0]]);
                }
            }

            // 9.1: the common mode goes first, by subtraction, and
            // unconditionally: for a span of one tree, a free end, a span
            // whose every tree is unpaired, a crossing, or any other span.
            // A tree with no owned notch carries no resultant and takes no
            // part in the mean.
            SubtractSpanMean(trees, order, along);

            // 9.2 and 9.3: the structural mirror plane and the pairing, per
            // span. Also settles which spans are CLOSED, spec 9.5's gate on
            // joining a family.
            var closed = new bool[spanCount];
            for (int s = 0; s < spanCount; s++)
            {
                List<int> ids = order[s];
                int rowCount = ids.Count;
                if (rowCount == 0)
                    continue;
                SpanFrame frame = placement.Frames[s];
                double h = frame.H;
                var rowIndexOf = new Dictionary<int, int>();
                for (int i = 0; i < rowCount; i++)
                    rowIndexOf[ids[i]] = i;

                // The row centre by parameter (spec section 4), the
                // fallback for s_mirror, over EVERY free notch of the span.
                double rowCentre = 0.5 * (frame.Sigma.Min() + frame.Sigma.Max());

                double sMirror = LocateMirror(trees, ids, rowIndexOf, sParam, along, rowCentre);

                // The candidate partner of every LOADED tree: the tree
                // nearest its reflection about s_mirror. A tree with no
                // owned notch takes no part at all, on either side of the
                // search (9.3).
                int[] loaded = ids.Where(t => trees[t].HeadMain >= 0).ToArray();
                var nearest = new Dictionary<int, int>();
                foreach (int t in loaded)
                {
                    int rowIndex = rowIndexOf[t];
                    int mirrorRow = rowCount - 1 - rowIndex;
                    int mirrorTreeId = ids[mirrorRow];
                    double reflection = (2.0 * sMirror) - sParam[t];
                    int best = -1;
                    double bestDist = double.PositiveInfinity;
                    foreach (int u in loaded)
                    {
                        double dist = Math.Abs(sParam[u] - reflection);
                        if (best < 0 || dist < bestDist - 1.0e-12)
                        {
                            best = u;
                            bestDist = dist;
                        }
                        else if (dist <= bestDist + 1.0e-12)
                        {
                            bool uIsMirror = u == mirrorTreeId;
                            bool bestIsMirror = best == mirrorTreeId;
                            if ((uIsMirror && !bestIsMirror)
                                || (uIsMirror == bestIsMirror && rowIndexOf[u] < rowIndexOf[best]))
                            {
                                best = u;
                                bestDist = dist;
                            }
                        }
                    }
                    nearest[t] = best;
                }

                var settled = new HashSet<int>();
                foreach (int t in loaded)
                {
                    if (settled.Contains(t))
                        continue;
                    int j = nearest[t];
                    if (j == t)
                    {
                        double selfMismatch = Math.Abs(2.0 * (sParam[t] - sMirror));
                        if (selfMismatch <= (h / 4.0) + 1.0e-12)
                        {
                            placement.Partner[t] = t;
                            along[t] = 0.0;
                            placement.CentreTrees++;
                            settled.Add(t);
                        }
                        continue;
                    }
                    if (settled.Contains(j) || nearest[j] != t)
                        continue;
                    double mismatch = Math.Abs(sParam[t] + sParam[j] - (2.0 * sMirror));
                    bool sameCount = trees[t].Nodes.Length == trees[j].Nodes.Length;
                    if (mismatch > (h / 4.0) + 1.0e-12 || !sameCount)
                        continue;
                    double half = 0.5 * (along[t] - along[j]);
                    along[t] = half;
                    along[j] = -half;
                    double side = 0.5 * (across[t] + across[j]);
                    across[t] = side;
                    across[j] = side;
                    double weight = 0.5 * (down[t] + down[j]);
                    down[t] = weight;
                    down[j] = weight;
                    placement.Partner[t] = j;
                    placement.Partner[j] = t;
                    settled.Add(t);
                    settled.Add(j);
                }

                closed[s] = ids.All(t => placement.Partner[t] != -1);
                if (closed[s])
                    placement.ClosedSpans++;
            }
            placement.UnpairedTrees = Enumerable.Range(0, count).Count(t =>
                !trees[t].Ring && trees[t].Span >= 0 && trees[t].Span < spanCount
                    && placement.Partner[t] < 0);

            // 9.5: families, gated on CLOSED spans, otherwise unchanged from
            // spec 3.4: alike in free-notch count (hence tree count and
            // layout at this one Branching), in Branching (one slider, so
            // alike by construction) and in chord LENGTH within a tenth of
            // the family LEAD's. Length is in the key because the family
            // shares an AIM: without it a three metre span and a ten metre
            // one holding the same number of notches average together, and
            // the short one takes an aim that can throw its foot past its
            // own anchors. Measuring against the lead makes the bucketing
            // non-transitive and order dependent, which is deliberate: it is
            // a cheap grouping of like with like, not an equivalence
            // relation.
            var families = new List<List<int>>();
            var familyNotches = new List<int>();
            var familyLength = new List<double>();
            for (int s = 0; s < spanCount; s++)
            {
                if (order[s].Count == 0 || !closed[s])
                    continue;
                int notches = order[s].Sum(t => trees[t].Nodes.Length);
                double length = placement.Frames[s].L;
                int found = -1;
                for (int f = 0; f < families.Count && found < 0; f++)
                {
                    if (familyNotches[f] != notches)
                        continue;
                    if (Math.Abs(length - familyLength[f]) > 0.10 * familyLength[f])
                        continue;
                    found = f;
                }
                if (found < 0)
                {
                    families.Add(new List<int>());
                    familyNotches.Add(notches);
                    familyLength.Add(length);
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
                // ALONG and DOWN only. Both are node-order invariant after
                // the pair step, along by being antisymmetric and down by
                // being symmetric, so tree i of one span and tree i of
                // another are the same tree of the family whichever way
                // either bar was traced. ACROSS is not: it comes out
                // negated when a bar is traced the other way, and there is
                // no rule for which way round a span is that does not fail
                // on a rib lying in the structure's own mirror plane. So
                // across stays the span's own, already mirrored within the
                // span by the pair step.
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

            // 9.4: the span mean is subtracted ONCE MORE, because the pair
            // step (and the family averaging inside it) can put a common
            // mode back on a span holding unpaired trees: with residuals of
            // 1, -2 and 1, pairing the outer two to zero leaves a mean of
            // -2/3 that was not there before.
            SubtractSpanMean(trees, order, along);

            // Back into each span's own frame, with the dead band, and the
            // angle every aim moved through.
            double moved = 0.0;
            var deadBand = new bool[count];
            for (int t = 0; t < count; t++)
            {
                Tree tree = trees[t];
                if (tree.Ring || tree.Span < 0 || tree.Span >= spanCount)
                    continue;
                int s = tree.Span;
                SpanFrame frame = placement.Frames[s];
                Vector3d rebuilt = new Vector3d(
                    (along[t] * frame.C.X) + (across[t] * frame.N.X),
                    (along[t] * frame.C.Y) + (across[t] * frame.N.Y),
                    down[t]);
                if (AngleBetween(MouldGeometry.AimFrom(rebuilt), Vector3d.ZAxis) <= PlumbDegrees)
                {
                    rebuilt = new Vector3d(0.0, 0.0, down[t]);
                    deadBand[t] = true;
                }
                tree.Resultant = rebuilt;
                moved = Math.Max(moved, AngleBetween(
                    MouldGeometry.AimFrom(tree.RawResultant),
                    MouldGeometry.AimFrom(tree.Resultant)));
            }

            // 9.6: the residual. For each span, the along parts of its
            // non-ring trees AS PLACED, excluding trees the dead band moved
            // and trees with no owned notch; the span's residual is the
            // absolute mean of those divided by the mean of their
            // |resultant|, zero where the set is empty or that mean is zero.
            // CommonModeResidual is the largest of them over the net.
            for (int s = 0; s < spanCount; s++)
            {
                List<int> ids = order[s];
                if (ids.Count == 0)
                    continue;
                int[] set = ids.Where(t => trees[t].HeadMain >= 0 && !deadBand[t]).ToArray();
                if (set.Length == 0)
                    continue;
                double meanAlongPlaced = set.Average(t => along[t]);
                double meanMagnitude = set.Average(t => trees[t].Resultant.Length);
                double residual = meanMagnitude <= 1.0e-15
                    ? 0.0
                    : Math.Abs(meanAlongPlaced) / meanMagnitude;
                placement.CommonModeResidual = Math.Max(placement.CommonModeResidual, residual);
            }

            return moved;
        }

        /// <summary>
        /// Spec 9.1, and its repetition in 9.4: subtract, from every tree of
        /// every span that carries a resultant at all (<c>HeadMain >= 0</c>),
        /// the MEAN along part over that same set. Unconditional, with no
        /// test to fail and no state in which it is skipped.
        /// </summary>
        private static void SubtractSpanMean(
            List<Tree> trees, List<int>[] order, double[] along)
        {
            for (int s = 0; s < order.Length; s++)
            {
                List<int> ids = order[s];
                if (ids.Count == 0)
                    continue;
                int[] carrying = ids.Where(t => trees[t].HeadMain >= 0).ToArray();
                if (carrying.Length == 0)
                    continue;
                double mean = carrying.Average(t => along[t]);
                foreach (int t in carrying)
                    along[t] -= mean;
            }
        }

        /// <summary>
        /// Spec 9.2: locate one span's structural mirror plane from where
        /// the residual along part 9.1 leaves behind changes sign. The
        /// span's trees are read SORTED BY THEIR MAIN NOTCH'S CHORD
        /// PARAMETER, ties to the lower bar position (<paramref
        /// name="rowIndexOf"/>), which is the one place spec section 9 reads
        /// parameter order rather than bar order.
        /// </summary>
        private static double LocateMirror(
            List<Tree> trees,
            List<int> ids,
            Dictionary<int, int> rowIndexOf,
            double[] sParam,
            double[] along,
            double rowCentre)
        {
            int[] sorted = ids.OrderBy(t => sParam[t]).ThenBy(t => rowIndexOf[t]).ToArray();

            // A_mag over the span's own trees, unfiltered: spec 9.2 reads it
            // over "those trees", the sorted row, not the loaded subset.
            double magnitudeMean = ids.Average(t => trees[t].Resultant.Length);
            bool AllZero()
            {
                if (magnitudeMean <= 1.0e-15)
                    return true;
                foreach (int t in sorted)
                {
                    if (Math.Abs(along[t]) > 1.0e-9 * magnitudeMean)
                        return false;
                }
                return true;
            }
            bool DeemedZero(int t) => magnitudeMean <= 1.0e-15 || Math.Abs(along[t]) <= 1.0e-9 * magnitudeMean;

            var candidates = new List<double>();
            if (sorted.Length >= 2 && !AllZero())
            {
                for (int k = 0; k < sorted.Length; k++)
                {
                    int t = sorted[k];
                    if (DeemedZero(t))
                    {
                        // A tree whose residual is deemed zero is itself a
                        // sign change, at its own parameter: the exact limit
                        // of the interpolation below, so the plane moves
                        // continuously as a residual passes through zero.
                        candidates.Add(sParam[t]);
                        continue;
                    }
                    if (k + 1 < sorted.Length)
                    {
                        int u = sorted[k + 1];
                        if (!DeemedZero(u) && (along[t] > 0.0) != (along[u] > 0.0))
                        {
                            double frac = along[t] / (along[t] - along[u]);
                            candidates.Add(sParam[t] + (frac * (sParam[u] - sParam[t])));
                        }
                    }
                }
            }

            if (candidates.Count == 0)
                return rowCentre;
            if (candidates.Count == 1)
                return candidates[0];
            double sMirror = candidates[0];
            double best = Math.Abs(candidates[0] - rowCentre);
            for (int k = 1; k < candidates.Count; k++)
            {
                double d = Math.Abs(candidates[k] - rowCentre);
                if (d < best - 1.0e-12)
                {
                    best = d;
                    sMirror = candidates[k];
                }
            }
            return sMirror;
        }

        /// <summary>
        /// The pull the HEAD at a shared node actually carries, counted
        /// exactly once and in full. PARAM RULED ON 2026-09-01 that this is
        /// to be fixed properly, and the arithmetic is stated because the
        /// obvious form is wrong.
        ///
        /// Summing the bars' transverse pulls DOUBLE COUNTS.
        /// <c>MouldGeometry.BarLoads</c> sums every member incident on a node
        /// except the edges running ALONG that bar, so at a node shared by
        /// bars A and B, pull_A is the infill plus B's along-bar edges and
        /// pull_B is the infill plus A's, and their sum is the infill TWICE.
        /// On any real vault the infill dominates, so the head load at a
        /// crossing would come out close to double, and with it the axial
        /// force, the load path and Auto's choice.
        ///
        /// Let the node be held by k DISTINCT bars, two bars being the same
        /// run at a node when they reach it through the same two neighbouring
        /// net vertices in either order, so a run traced twice counts once.
        /// Then headPull = (pull_1 + ... + pull_k) - (k - 1) * total, which
        /// is the node's infill pull exactly once, since each pull_i is total
        /// less that bar's own along-bar contribution. For k = 1 it is
        /// pull_1 and nothing changes anywhere.
        ///
        /// The head pull is then projected off every distinct bar tangent at
        /// the node in turn, by Gram-Schmidt, a tangent being dropped when
        /// its residual norm falls to 1e-9 of its own length because it is
        /// parallel to one already taken. For k = 1 that is BarTransverse
        /// exactly, so every single-bar number in the harness is untouched.
        /// Where the surviving tangents span all three dimensions the residue
        /// is zero, AimFrom returns vertical, and the column stands plumb,
        /// which is the honest answer for a node whose every direction is
        /// already carried to an anchor.
        /// </summary>
        public static Vector3d HeadPull(
            Point3d[] nodes,
            int[][] bars,
            Vector3d[][] pull,
            Vector3d[] nodePull,
            int node,
            IReadOnlyList<(int Bar, int Position)> holders)
        {
            // Distinct runs, keyed on the two neighbouring net vertices in
            // either order.
            var seen = new HashSet<(int, int)>();
            var distinct = new List<(int Bar, int Position)>();
            foreach ((int b, int p) in holders)
            {
                int[] bar = bars[b];
                int before = bar[Math.Max(p - 1, 0)];
                int after = bar[Math.Min(p + 1, bar.Length - 1)];
                (int, int) key = before <= after ? (before, after) : (after, before);
                if (seen.Add(key))
                    distinct.Add((b, p));
            }

            var summed = Vector3d.Zero;
            foreach ((int b, int p) in distinct)
                summed += pull[b][p];
            int k = distinct.Count;
            Vector3d head = summed - ((k - 1) * nodePull[node]);

            // Project off every distinct bar tangent in turn.
            var taken = new List<Vector3d>();
            foreach ((int b, int p) in distinct)
            {
                int[] bar = bars[b];
                Vector3d tangent = nodes[bar[Math.Min(p + 1, bar.Length - 1)]]
                    - nodes[bar[Math.Max(p - 1, 0)]];
                double length = tangent.Length;
                if (length <= 1.0e-12)
                    continue;
                tangent = new Vector3d(tangent.X / length, tangent.Y / length, tangent.Z / length);
                foreach (Vector3d already in taken)
                {
                    double dot = (tangent.X * already.X) + (tangent.Y * already.Y) + (tangent.Z * already.Z);
                    tangent -= dot * already;
                }
                double residual = tangent.Length;
                if (residual <= 1.0e-9)
                    continue;
                tangent = new Vector3d(tangent.X / residual, tangent.Y / residual, tangent.Z / residual);
                taken.Add(tangent);
                double along = (head.X * tangent.X) + (head.Y * tangent.Y) + (head.Z * tangent.Z);
                head -= along * tangent;
            }
            return head;
        }

        /// <summary>
        /// Which span builds the member to a shared notch. THE OWNER IS
        /// DECIDED BY THE SPANS, NOT BY THE TRACE, and the rule must not end
        /// in bar order: a regularly ribbed vault, a cross vault and a dome
        /// of equal ribs and hoops all give two spans of equal notch count
        /// and equal chord, and ending on the bar index would make the answer
        /// depend on which curve Pattern traced first, which is the very
        /// finding this rule answers.
        ///
        /// A span's ENDPOINT PAIR is its two cut nodes' plan positions sorted
        /// lexicographically by X then Y, which is node-order invariant. The
        /// owner is the first of these that separates the spans, each
        /// compared within 1e-9 * min(L_A, L_B) except the last: the greater
        /// FREE NOTCH COUNT; then the longer CHORD LENGTH; then the lower X
        /// of the endpoint pair's first point, then its lower Y; then the
        /// same for the second point; then the lower mean Z of the span's
        /// free notches; then, and only then, the lower bar index and span
        /// index, which is reached only when the two spans are the same
        /// segment in space to within a billionth of their own length.
        ///
        /// Every key is a property of the SPAN and not of the node, so every
        /// notch shared between the same two spans resolves the same way,
        /// which is what keeps a symmetric pair of crossings symmetric. The
        /// more central notch was considered and rejected for exactly that
        /// reason: it reads the node, and it can hand two mirrored shared
        /// notches to different owners.
        /// </summary>
        private static int OwnerOf(Placement placement, Point3d[] nodes, int a, int b)
        {
            if (a == b)
                return a;
            SpanFrame fa = placement.Frames[a];
            SpanFrame fb = placement.Frames[b];
            if (fa.Nodes.Length != fb.Nodes.Length)
                return fa.Nodes.Length > fb.Nodes.Length ? a : b;

            double tolerance = 1.0e-9 * Math.Min(fa.L, fb.L);
            if (Math.Abs(fa.L - fb.L) > tolerance)
                return fa.L > fb.L ? a : b;

            static (double X, double Y)[] EndpointPair(SpanFrame frame) =>
                new[] { (frame.P0.X, frame.P0.Y), (frame.P1.X, frame.P1.Y) }
                    .OrderBy(p => p.Item1).ThenBy(p => p.Item2).ToArray();

            (double X, double Y)[] ea = EndpointPair(fa);
            (double X, double Y)[] eb = EndpointPair(fb);
            for (int k = 0; k < 2; k++)
            {
                if (Math.Abs(ea[k].X - eb[k].X) > tolerance)
                    return ea[k].X < eb[k].X ? a : b;
                if (Math.Abs(ea[k].Y - eb[k].Y) > tolerance)
                    return ea[k].Y < eb[k].Y ? a : b;
            }

            double meanZa = fa.Nodes.Length > 0 ? fa.Nodes.Average(n => nodes[n].Z) : 0.0;
            double meanZb = fb.Nodes.Length > 0 ? fb.Nodes.Average(n => nodes[n].Z) : 0.0;
            if (Math.Abs(meanZa - meanZb) > tolerance)
                return meanZa < meanZb ? a : b;

            int barA = placement.Spans[a].Bar;
            int barB = placement.Spans[b].Bar;
            if (barA != barB)
                return barA < barB ? a : b;
            return a < b ? a : b;
        }

        /// <summary>
        /// The index into a tree's <see cref="Tree.Nodes"/> of its innermost
        /// OWNED notch: the owned notch whose station (its index into the
        /// span's own free list) sits nearest the row centre, ties to the
        /// lower bar position, exactly the rule <see cref="Group"/> uses to
        /// choose a group's main. -1 where the tree owns nothing at all.
        /// Where the tree owns its main (Nodes[0], every tree on a net with
        /// no crossing) this returns 0 by construction, since the main is
        /// already the group's nearest-to-centre station.
        /// </summary>
        private static int HeadMainOf(Tree tree, SpanFrame? frame, int[][] bars)
        {
            double rowCentre = frame is not null && frame.Positions.Length > 0
                ? (frame.Positions.Length - 1) / 2.0
                : 0.0;
            int best = -1;
            double bestDistance = double.MaxValue;
            int bestTie = int.MaxValue;
            for (int k = 0; k < tree.Nodes.Length; k++)
            {
                if (!tree.Owned[k])
                    continue;
                int barPosition = tree.Bar >= 0 && tree.Bar < bars.Length
                    ? Array.IndexOf(bars[tree.Bar], tree.Nodes[k])
                    : -1;
                double distance = k;
                if (frame is not null && barPosition >= 0)
                {
                    int station = Array.IndexOf(frame.Positions, barPosition);
                    if (station >= 0)
                        distance = Math.Abs(station - rowCentre);
                }
                int tie = barPosition >= 0 ? barPosition : k;
                if (best < 0 || distance < bestDistance - 1.0e-9 ||
                    (Math.Abs(distance - bestDistance) <= 1.0e-9 && tie < bestTie))
                {
                    best = k;
                    bestDistance = distance;
                    bestTie = tie;
                }
            }
            return best;
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

            var ringHeld = new HashSet<int>();
            Tree? ring = RingTree(nodes, bars, anchorSet, across, perimeterLoops, ground, ringHeld);
            if (ring is not null)
            {
                placement.RingTree = ring;
                placement.Trees.Add(ring);
            }

            // Pass 1: every span's frame and free list, built in full BEFORE
            // any tree, because the owner rule of spec section 10 compares
            // SPANS (their free notch count, their chord, their endpoint
            // pair) and needs every span's frame to exist first. A notch
            // shared with another bar (a crossing) is NO LONGER skipped: both
            // lines hold it, so neither span acquires a hole and the bar
            // order cannot change any layout. ringHeld keeps its OTHER job
            // unchanged, the ring tree's: a rim notch it holds still cuts the
            // spans and is still no span's free notch.
            placement.Spans = Spans(bars, anchorSet, ringHeld);
            var freeOf = new int[placement.Spans.Count][];
            var holderMap = new Dictionary<int, List<(int Bar, int Position, int Span)>>();
            for (int s = 0; s < placement.Spans.Count; s++)
            {
                Span span = placement.Spans[s];
                int[] free = span.Free.Where(p => !ringHeld.Contains(bars[span.Bar][p])).ToArray();
                freeOf[s] = free;
                SpanFrame frame = Frame(nodes, bars, span, free);
                placement.Frames.Add(frame);
                if (free.Length > 0 && (frame.ChordZero || frame.OneParameter))
                    placement.SpanDegenerate++;
                foreach (int p in free)
                {
                    int node = bars[span.Bar][p];
                    if (!holderMap.TryGetValue(node, out List<(int Bar, int Position, int Span)>? holders))
                    {
                        holders = new List<(int, int, int)>();
                        holderMap[node] = holders;
                    }
                    holders.Add((span.Bar, p, s));
                }
            }

            // The owner of every shared notch, decided by the SPANS and not
            // by the trace (spec section 10). Folded pairwise over OwnerOf so
            // a notch held by more than two spans still resolves to one.
            var ownerOfNode = new Dictionary<int, int>();
            foreach (KeyValuePair<int, List<(int Bar, int Position, int Span)>> entry in holderMap)
            {
                if (entry.Value.Count < 2)
                    continue;
                placement.SharedNotches++;
                int owner = entry.Value[0].Span;
                for (int i = 1; i < entry.Value.Count; i++)
                    owner = OwnerOf(placement, nodes, owner, entry.Value[i].Span);
                ownerOfNode[entry.Key] = owner;
            }

            // Pass 2: the trees, span by span, over the same free lists and
            // frames Pass 1 built.
            for (int s = 0; s < placement.Spans.Count; s++)
            {
                Span span = placement.Spans[s];
                int[] free = freeOf[s];
                SpanFrame frame = placement.Frames[s];
                (int[][] groups, int[] mains) = Group(free.Length, branching);
                for (int g = 0; g < groups.Length; g++)
                {
                    int[] positions = groups[g].Select(i => free[i]).ToArray();
                    int mainPosition = free[mains[g]];
                    var ordered = new List<int> { mainPosition };
                    ordered.AddRange(positions.Where(p => p != mainPosition));
                    int[] treeNodes = ordered.Select(p => bars[span.Bar][p]).ToArray();
                    var owned = new bool[treeNodes.Length];
                    var load = new double[treeNodes.Length];
                    Vector3d sum = Vector3d.Zero;
                    for (int k = 0; k < treeNodes.Length; k++)
                    {
                        int p = ordered[k];
                        int node = treeNodes[k];
                        List<(int Bar, int Position, int Span)> holders = holderMap[node];
                        if (holders.Count <= 1)
                        {
                            // Held by ONE bar: the head pull is that bar's own
                            // untransversed pull unchanged, so every existing
                            // harness number is untouched.
                            owned[k] = true;
                            load[k] = Math.Abs(across[span.Bar][p].Z);
                            sum += across[span.Bar][p];
                        }
                        else
                        {
                            bool isOwner = ownerOfNode[node] == s;
                            owned[k] = isOwner;
                            if (isOwner)
                            {
                                var holderPairs = holders.Select(h => (h.Bar, h.Position)).ToList();
                                Vector3d headPull = HeadPull(nodes, bars, pull, nodePull, node, holderPairs);
                                load[k] = Math.Abs(headPull.Z);
                                sum += headPull;
                            }
                            else
                            {
                                // A borrowed notch enters Load with a load of
                                // zero: its head is not this tree's to carry.
                                load[k] = 0.0;
                            }
                        }
                    }
                    var tree = new Tree
                    {
                        Bar = span.Bar,
                        Span = s,
                        Nodes = treeNodes,
                        Load = load,
                        Owned = owned,
                        Resultant = sum,
                    };
                    tree.HeadMain = HeadMainOf(tree, frame, bars);
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
            // The ring tree is the sole holder of every one of its own rim
            // notches: spec section 10's shared-node ownership never touches
            // it, so it owns everything and its main is its head main.
            tree.Owned = Enumerable.Repeat(true, tree.Nodes.Length).ToArray();
            tree.HeadMain = tree.Nodes.Length > 0 ? 0 : -1;
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
            // peeled trunk falls back to. A tree whose main notch is at or
            // below GROUND cannot meet the lean cap from any foot, so it
            // peels, with its partner, and its Type 0 foot lies directly
            // under that notch because the aim ray has no rise to travel.
            // `ownRise` is already clamped at zero, so the case is recorded
            // rather than discovered.
            var own = new Point3d[trees.Count];
            for (int t = 0; t < trees.Count; t++)
            {
                if (trees[t].FixedFoot is Point3d fixedFoot)
                {
                    own[t] = fixedFoot;
                    continue;
                }
                // A tree whose HeadMain is -1 owns no notch at all: it builds
                // no member and no foot, so it needs none computed here.
                if (trees[t].HeadMain < 0)
                    continue;
                Point3d ownMain = nodes[trees[t].Nodes[trees[t].HeadMain]];
                double ownRise = Math.Max(ownMain.Z - ground, 0.0);
                double ownAlong = ownRise / Math.Max(aim[t].Z, 1.0e-9);
                own[t] = new Point3d(
                    ownMain.X - (aim[t].X * ownAlong),
                    ownMain.Y - (aim[t].Y * ownAlong),
                    ground);
            }

            // A span whose CHORD LENGTH is zero has no chord direction and no
            // parameter. It takes ONE foot at the plan mean of its free
            // notches WHATEVER THE TYPE, Type 0 included, which is why this
            // runs before the level split rather than inside its else. The
            // one-parameter span needs no branch at all: its group centre is
            // that one parameter, so every notch of the group is a tied
            // candidate and GroupFoot already returns their plan mean.
            var chordZeroTree = new bool[trees.Count];
            for (int s = 0; s < placement.Spans.Count; s++)
            {
                SpanFrame frame = placement.Frames[s];
                if (!frame.ChordZero || frame.Nodes.Length == 0)
                    continue;
                double sumX = 0.0;
                double sumY = 0.0;
                foreach (int node in frame.Nodes)
                {
                    sumX += nodes[node].X;
                    sumY += nodes[node].Y;
                }
                var oneFoot = new Point3d(
                    sumX / frame.Nodes.Length, sumY / frame.Nodes.Length, ground);
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null || trees[t].Span != s)
                        continue;
                    foot[t] = oneFoot;
                    chordZeroTree[t] = true;
                }
            }

            if (level == 0)
            {
                // Each tree stands on its own foot, on the line of the force
                // it carries. AimFrom caps the lean, so this is never refused.
                // A tree whose HeadMain is -1 is skipped here for the same
                // reason it is skipped everywhere else in this method: it owns
                // no notch, so `own` was never computed for it and copying
                // that uncomputed default across would put a plan-origin foot
                // in the array. Nothing downstream reads it, because every
                // consumer re-checks HeadMain, but a foot no tree stands on
                // has no business being written. The FixedFoot test comes
                // first, exactly as it does in the `own` loop above: the ring
                // tree's foot is given and not derived from a head main.
                for (int t = 0; t < trees.Count; t++)
                {
                    if (chordZeroTree[t])
                        continue;
                    if (trees[t].FixedFoot is null && trees[t].HeadMain < 0)
                        continue;
                    foot[t] = own[t];
                }
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
                    if (frame.ChordZero)
                        continue;
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

                // A tree that peels takes its mirror PARTNER with it, whether
                // or not the partner is over the cap. Both feet are then Type
                // 0 feet, and they are mirror images wherever the two main
                // notches are, because the pair step made the two aims mirror
                // images. Both members count in Peeled. An unpaired tree
                // peels alone. A self-paired tree peels onto its own Type 0
                // foot, which has no along-chord component because the pair
                // step set its along aim to zero, so it stands directly under
                // its own notch along the chord; it lies on the span's plane
                // of symmetry exactly when that notch does, and no step
                // projects it there.
                //
                // The loop cannot cascade: peeling is one-way, a peeled tree
                // never rejoins a shared foot, and no foot moves on account
                // of a peel.
                var stepped = new bool[trees.Count];
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null || stepped[t] || trees[t].HeadMain < 0)
                        continue;
                    double lean = MouldGeometry.LeanFromVertical(foot[t], nodes[trees[t].Nodes[trees[t].HeadMain]]);
                    if (lean <= MouldGeometry.MaxLeanDegrees + 1.0e-9)
                        continue;
                    stepped[t] = true;
                    int mate = t < placement.Partner.Length ? placement.Partner[t] : -1;
                    if (mate >= 0 && mate < trees.Count && mate != t && trees[mate].FixedFoot is null)
                        stepped[mate] = true;
                }
                for (int t = 0; t < trees.Count; t++)
                {
                    if (!stepped[t])
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

            // Members. Trunk foot to fork, main branch fork to the HEAD MAIN
            // (the tree's innermost OWNED notch, Nodes[0] on every tree that
            // owns its main), branches fork to the other OWNED notches; a
            // single owned notch is one member foot to notch. A tree whose
            // HeadMain is -1 owns nothing at all: it builds no member and no
            // foot, carries no load, and has a zero resultant, but is still
            // counted in its span's layout so the palindrome stands. Every
            // member lower end first.
            for (int t = 0; t < trees.Count; t++)
            {
                Tree tree = trees[t];
                if (tree.HeadMain < 0)
                    continue;
                int footNode = footIndex[t];
                Point3d footPoint = result.Nodes[footNode];
                Point3d main = nodes[tree.Nodes[tree.HeadMain]];
                double total = tree.Load.Sum();
                int mainNode = AddNode(result.Nodes, main);
                if (tree.Nodes.Length == 1)
                {
                    AddMember(result, footNode, mainNode, total, t);
                    continue;
                }
                // The fork lies on the segment from the foot to the head
                // main, at ForkFraction of its height (spec 3.6). The head
                // main is the tree's innermost OWNED notch, which on an arch
                // is also its HIGHEST, so at Branching 3 an anchor-end tree
                // can hold a notch BELOW that height and the branch to it
                // would run down from the fork. A fork above one of its own
                // heads is not a tree: the block sorts every member by Z
                // (MouldGeometry.ColumnsBlock), so such a notch is only ever
                // a lower end and TreeFromPairs reads it as a FOOT, which
                // puts a foot in mid-air in Frame's Columns, drops the head
                // out of Fit's held set and makes Animate drive a held head
                // down to ground level on the rail. Where the spec's height
                // would sit at or above the tree's lowest OWNED notch the
                // fork is therefore lowered to ForkFraction of THAT notch's
                // height, on the same segment. Every ordinary tree, head main
                // lowest or the branches above the fork already, is
                // untouched. A borrowed notch is not this tree's to build to
                // at all, so it plays no part in this measure.
                double fraction = ForkFraction;
                double rise = main.Z - footPoint.Z;
                if (rise > 1.0e-9)
                {
                    double lowest = main.Z;
                    for (int k = 0; k < tree.Nodes.Length; k++)
                    {
                        if (k == tree.HeadMain || !tree.Owned[k])
                            continue;
                        lowest = Math.Min(lowest, nodes[tree.Nodes[k]].Z);
                    }
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
                AddMember(result, forkNode, mainNode, tree.Load[tree.HeadMain], t);
                for (int k = 0; k < tree.Nodes.Length; k++)
                {
                    if (k == tree.HeadMain || !tree.Owned[k])
                        continue;
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
                // A tree with no owned notch builds no foot at all, so it
                // never enters a merge.
                if (placement.Trees[t].HeadMain < 0 || placement.Trees[partner].HeadMain < 0)
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
                // A tree with no owned notch builds no member and no foot at
                // all: it never enters the level's node list.
                if (placement.Trees[t].HeadMain < 0)
                    continue;
                for (int u = 0; u < t; u++)
                {
                    if (placement.Trees[u].HeadMain < 0)
                        continue;
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
