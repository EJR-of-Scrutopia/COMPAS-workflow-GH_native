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
    /// Column Finder: solve where the column arms stand under the notched bars,
    /// and grow them down to the ground as posts or as branching trees.
    ///
    /// It takes the solved Result as its form finder. The principal lines
    /// travel in the contract, resolved once upstream by Supports from the
    /// anchors or by Pattern from drawn curves, and the load each notch hands
    /// its bar is read straight off the Result's own reactions. Nothing has to
    /// be told to it twice, and nothing is snapped here.
    ///
    /// WHERE the arms go is a beam problem, not a spacing one. A bar on two or
    /// three arms is a beam, and a loaded beam wants its supports about a fifth
    /// of its length in from each end, which balances the cantilever moment over
    /// each arm against the moment at midspan. Spreading arms evenly leaves the
    /// middle to droop and spends one on a part of the bar its anchor already
    /// holds. Since an arm can only stand at a notch and there are only a
    /// handful, every arrangement is tried and the straightest kept. Anchors
    /// count as supports but cost no arm, and any arrangement that would need an
    /// arm to PULL DOWN is rejected: a column can only push.
    ///
    /// The bar's stiffness deliberately does not appear. Deflection scales as
    /// one over EI, so EI is a common factor across every candidate arrangement
    /// and cancels out of the comparison: the best arm positions are identical
    /// whatever the bar is made of, which was checked across seven orders of
    /// magnitude. Stiffness would only be needed to turn the droop into
    /// millimetres, and that is a capacity to establish by testing rather than
    /// to assume here. The same goes for allowable stress and member sizing.
    /// This component finds WHERE the columns stand and WHAT they carry; how
    /// strong they have to be is the next question, not this one.
    ///
    /// HOW they reach the ground is Trees. At zero every arm drops straight to
    /// its own foot. Above zero the arms are gathered into that many branching
    /// trees in the Frei Otto manner, clustered by equal load, and Depth sets
    /// how many times each may fork.
    ///
    /// The tree algorithm is a port of tools/tree_forest/core.py, which stays
    /// the tested source; it is deterministic, so the same input always draws
    /// the same trees.
    /// </summary>
    public sealed class ColumnFinderComponent : NativeComponentBase
    {
        public ColumnFinderComponent()
            : base(
                "Column Finder",
                "Columns",
                "Solve where the column arms stand under the notched bars, and "
                    + "grow them to the ground as posts or branching trees. "
                    + "Arm positions come from solving each bar as a beam; the "
                    + "loads come from the Result's own reactions.",
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

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Solved FD or TNA result. Used as the form finder: its geometry "
                    + "gives the notches and its reactions give the load each "
                    + "one hands the bar.",
                GH_ParamAccess.item);
            parameters.AddIntegerParameter(
                "Columns Per Line",
                "C",
                "How many arms stand under EACH bar, so no bar is left with "
                    + "fewer than the rest. Two is the minimum for a bar to "
                    + "stand.",
                GH_ParamAccess.item,
                3);
            parameters.AddIntegerParameter(
                "Trees",
                "T",
                "0 gives every arm its own straight column to the ground. Any "
                    + "higher number gathers all the arms into that many "
                    + "branching trees, clustered by equal load.",
                GH_ParamAccess.item,
                0);
            parameters.AddIntegerParameter(
                "Depth",
                "D",
                "How many times a tree may fork. Ignored when Trees is 0.",
                GH_ParamAccess.item,
                2);
            parameters[1].Optional = true;
            parameters[2].Optional = true;
            parameters[3].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddLineParameter(
                "Columns",
                "C",
                "The final column members as built lines, each running from its "
                    + "foot on the ground up to the notch it holds. The line "
                    + "IS the column, so its direction is the lean the arm has "
                    + "to stand at. With Trees at 0 there is one straight post "
                    + "per arm; above 0 these are the branches of each tree. "
                    + "Force and Angle align with this list.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Heads",
                "H",
                "The top of each column: the notch on the bar that this arm "
                    + "carries. These are the points the mechanism has to reach, "
                    + "and they are chosen by solving the bar, not by spacing.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Feet",
                "F",
                "The bottom of each column, on the ground. With Trees at 0 a "
                    + "foot sits directly under its head; above 0 the feet are "
                    + "the load-weighted centres of each tree, so there are "
                    + "fewer of them than there are arms and each one takes a "
                    + "whole tree's load.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Force",
                "FO",
                "Axial force along each column, N: what that member actually "
                    + "carries, for sizing and for testing later. A leaning "
                    + "column carries MORE than the weight above it, by one "
                    + "over its vertical cosine, and the surplus is the "
                    + "horizontal thrust its foot has to resist. No capacity is "
                    + "assumed anywhere; this is the demand, not a verdict.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Angle",
                "A",
                "Lean of each column from vertical, degrees. This is the angle "
                    + "the arm stands at, and the number that decides whether "
                    + "the sliding joint can reach it. Past about sixty degrees "
                    + "a column is doing more pushing sideways than holding up.",
                GH_ParamAccess.list);
            parameters.AddParameter(
                new MouldStateParam(),
                "State",
                "S",
                "The finished mould bundled for Stress Analysis: the net with "
                    + "its member forces and node roles, plus the columns and "
                    + "what each one carries.",
                GH_ParamAccess.item);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "How many arms went on each bar and where, what they carry, and "
                    + "how the load divides between the feet.",
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

            int perLine = 3;
            int trees = 0;
            int depth = 2;
            data.GetData(1, ref perLine);
            data.GetData(2, ref trees);
            data.GetData(3, ref depth);
            perLine = Math.Max(perLine, 2);

            // Stiffness cancels out of the placement, so any positive value
            // gives the same arms. One keeps the arithmetic well conditioned.
            const double placementStiffness = 1.0;

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

                // Keep the ORIGINAL edge index alongside each kept edge. The
                // filter drops invalid and self edges, so a filtered position
                // no longer matches the Result's own MemberForces array, and
                // indexing forces by it would silently attach every force
                // after the first dropped edge to the wrong member.
                (int, int)[] edges = MouldGeometry.ValidEdges(
                    equilibrium, n, out int[] edgeSource);

                // The feet stand on the base of the geometry, which is where
                // the anchors already are; nothing to set.
                double ground = nodes.Min(p => p.Z);

                var anchors = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));

                // The runs travel in the contract, resolved once upstream by
                // Supports from the anchors or by Pattern from drawn curves.
                List<List<int>> bars = MouldGeometry.PrincipalRuns(
                    equilibrium, n);
                if (bars.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines. Set Ribs on "
                            + "Supports to derive them from the anchors, or "
                            + "draw Principal Lines on Pattern.");
                    return;
                }

                // The load each notch hands its bar, straight from the solve.
                var nodeLoad = new double[n];
                foreach (NodalVectorDto reaction in equilibrium.Reactions)
                {
                    if (reaction.NodeId >= 0 && reaction.NodeId < n)
                        nodeLoad[reaction.NodeId] = Math.Abs(reaction.Vector.Z);
                }

                var heads = new List<Point3d>();
                var headLoad = new List<double>();
                var armsPerBar = new List<int>();

                foreach (List<int> bar in bars)
                {
                    (List<int> chosen, double _droop, double[] reactions) =
                        BeamSolver.ArmsForBar(
                            bar, nodes, nodeLoad, anchors, perLine,
                            placementStiffness);
                    armsPerBar.Add(chosen.Count);
                    foreach (int k in chosen)
                    {
                        heads.Add(nodes[bar[k]]);
                        headLoad.Add(reactions.Length > k ? Math.Max(reactions[k], 0.0)
                            : nodeLoad[bar[k]]);
                    }
                }

                var members = new List<Line>();
                var carried = new List<double>();
                var feet = new List<Point3d>();

                if (trees <= 0)
                {
                    // Every arm its own straight post.
                    for (int i = 0; i < heads.Count; i++)
                    {
                        var foot = new Point3d(heads[i].X, heads[i].Y, ground);
                        if (heads[i].Z - ground <= 0.0)
                            continue;
                        members.Add(new Line(foot, heads[i]));
                        carried.Add(headLoad[i]);
                        feet.Add(foot);
                    }
                }
                else
                {
                    Forest forest = TreeBuilder.Build(
                        heads.ToArray(), headLoad.ToArray(),
                        Math.Max(trees, 1), Math.Max(depth, 0), ground);
                    for (int s = 0; s < forest.Segments.Count; s++)
                    {
                        (int child, int parent) = forest.Segments[s];
                        Point3d a = forest.Points[child];
                        Point3d b = forest.Points[parent];
                        // Every column member runs LOWER end to UPPER end, so
                        // that From is always the foot side and To the head
                        // side. A tree branch is stored child to parent, which
                        // runs the other way, and leaving it would silently
                        // swap the meaning of foot and head the moment Trees
                        // went above zero.
                        members.Add(a.Z <= b.Z ? new Line(a, b) : new Line(b, a));
                        carried.Add(forest.CarriedLoad[s]);
                    }
                    feet.AddRange(forest.FootIndices.Select(i => forest.Points[i]));
                }

                var force = new List<double>(members.Count);
                var angle = new List<double>(members.Count);
                for (int i = 0; i < members.Count; i++)
                {
                    Vector3d v = members[i].To - members[i].From;
                    double length = v.Length;
                    double cos = length > 1e-12 ? Math.Abs(v.Z) / length : 1.0;
                    force.Add(cos > 1e-6 ? carried[i] / cos : carried[i]);
                    angle.Add(Rhino.RhinoMath.ToDegrees(
                        Math.Acos(Math.Min(Math.Max(cos, -1.0), 1.0))));
                }

                data.SetDataList(0, members);
                data.SetDataList(1, heads);
                data.SetDataList(2, feet);
                data.SetDataList(3, force);
                data.SetDataList(4, angle);

                Mesh? thrust = MouldGeometry.ThrustMeshFromResult(
                    result, out int[] meshToNode);
                var perimeter = MouldGeometry.PerimeterNodes(
                    thrust, meshToNode, MouldGeometry.BuildAdjacency(n, edges), n);
                var footPts = members.Select(m => m.From).ToList();
                var headPts = members.Select(m => m.To).ToList();
                data.SetData(5, new MouldStateGoo(MouldGeometry.BuildState(
                    "final", ground, nodes, edges, edgeSource, equilibrium,
                    bars.SelectMany(b => b), anchors, perimeter,
                    footPts, headPts, force)));
                data.SetData(6, Report(
                    bars, armsPerBar, headLoad, members, force, angle, feet,
                    trees, depth, ground));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        private static string Report(
            List<List<int>> bars,
            List<int> armsPerBar,
            List<double> headLoad,
            List<Line> members,
            List<double> force,
            List<double> angle,
            List<Point3d> feet,
            int trees,
            int depth,
            double ground)
        {
            var lines = new List<string>
            {
                $"{bars.Count} bars, {armsPerBar.Sum()} arms "
                    + $"({string.Join(" + ", armsPerBar)} per bar), "
                    + $"{feet.Count} feet, {members.Count} members",
                $"the arms carry {headLoad.Sum():0} N between them, ground read "
                    + $"as {ground:0.###}",
                "principal lines came from the contract, resolved upstream",
                string.Empty,
                "arm positions are SOLVED, not spaced: a loaded bar wants its "
                    + "supports about a fifth of its length in from each end, "
                    + "and every arrangement of notches was tried. Bar "
                    + "stiffness is not asked for because it cancels out of "
                    + "that comparison.",
            };

            lines.Add(trees <= 0
                ? "Trees 0: every arm drops straight to its own foot."
                : $"Trees {trees} at depth {depth}: the arms are gathered into "
                    + "branching trees clustered by equal load, so the feet are "
                    + "fewer than the arms.");

            if (headLoad.Count > 0)
                lines.Add($"arm load {headLoad.Min():0} to {headLoad.Max():0} N");
            if (force.Count > 0)
                lines.Add($"axial force up to {force.Max():0} N");
            if (angle.Count > 0)
            {
                lines.Add($"lean {angle.Min():0.#} to {angle.Max():0.#} degrees "
                    + "from vertical");
                if (angle.Max() > 60.0)
                {
                    lines.Add(
                        "WARNING: a column leans past sixty degrees, so it is "
                            + "pushing sideways more than it is holding up. "
                            + "Check the sliding joint can reach that angle.");
                }
            }
            lines.Add(string.Empty);
            lines.Add(
                "no capacity is assumed anywhere here: Force is the demand, to "
                    + "size and test against, not a pass or a fail.");
            return string.Join(Environment.NewLine, lines);
        }
    }

    /// <summary>
    /// A bar on point supports, solved as an Euler-Bernoulli beam so the arms
    /// can be placed where they leave it straightest rather than spaced.
    /// </summary>
    internal static class BeamSolver
    {
        public static (List<int>, double, double[]) ArmsForBar(
            List<int> bar,
            Point3d[] nodes,
            double[] nodeLoad,
            HashSet<int> anchors,
            int perLine,
            double EI)
        {
            int count = bar.Count;
            var arc = new double[count];
            for (int k = 1; k < count; k++)
                arc[k] = arc[k - 1] + nodes[bar[k - 1]].DistanceTo(nodes[bar[k]]);
            double span = arc[count - 1];

            double[] load = bar.Select(i => nodeLoad[i]).ToArray();
            var anchored = new List<int>();
            for (int k = 0; k < count; k++)
            {
                if (anchors.Contains(bar[k]))
                    anchored.Add(k);
            }

            if (EI <= 0.0 || span <= 0.0)
            {
                var evenly = new List<int>();
                for (int c = 0; c < perLine; c++)
                {
                    double want = span * (c + 0.5) / perLine;
                    int pick = 0;
                    double closest = double.MaxValue;
                    for (int k = 0; k < count; k++)
                    {
                        double gap = Math.Abs(arc[k] - want);
                        if (gap < closest)
                        {
                            closest = gap;
                            pick = k;
                        }
                    }
                    if (!evenly.Contains(pick) && !anchored.Contains(pick))
                        evenly.Add(pick);
                }
                evenly.Sort();
                return (evenly, 0.0, new double[count]);
            }

            int stations = Math.Min(count, 41);
            int[] coarse = Enumerable.Range(0, stations)
                .Select(i => (int)Math.Round(
                    (double)i * (count - 1) / Math.Max(stations - 1, 1)))
                .Distinct()
                .ToArray();
            var anchoredCoarse = new HashSet<int>(
                anchored.Select(a => NearestIndex(coarse, a)));
            int[] pool = Enumerable.Range(0, coarse.Length)
                .Where(i => !anchoredCoarse.Contains(i))
                .ToArray();

            int budget = 4000;
            int allowed = Math.Max(perLine + 1, 4);
            while (allowed < pool.Length && Choose(allowed + 1, perLine) <= budget)
                allowed++;
            if (pool.Length > allowed && allowed > 1)
            {
                pool = Enumerable.Range(0, allowed)
                    .Select(i => pool[(int)Math.Round(
                        (double)i * (pool.Length - 1) / (allowed - 1))])
                    .Distinct()
                    .ToArray();
            }

            List<int>? best = null;
            double bestScore = double.MaxValue;
            List<int>? fallback = null;
            double fallbackScore = double.MaxValue;

            foreach (int[] combo in Combinations(pool, perLine))
            {
                var supports = new SortedSet<int>(anchoredCoarse);
                foreach (int c in combo)
                    supports.Add(c);
                int[] full = supports.Select(s => coarse[s]).Distinct()
                    .OrderBy(s => s).ToArray();
                if (full.Length < 2)
                    continue;

                (double[]? defl, double[]? reac) = Response(arc, load, full, EI);
                if (defl is null || reac is null)
                    continue;
                double score = defl.Select(Math.Abs).Max();
                if (score < fallbackScore)
                {
                    fallbackScore = score;
                    fallback = full.ToList();
                }
                if (full.Any(s => reac[s] < -1e-6))
                    continue;                       // an arm cannot pull down
                if (score < bestScore)
                {
                    bestScore = score;
                    best = full.ToList();
                }
            }

            List<int> chosen = best ?? fallback ?? new List<int> { 0, count - 1 };
            (double[]? d, double[]? r) = Response(arc, load, chosen.ToArray(), EI);
            double droop = d is null ? 0.0 : d.Select(Math.Abs).Max();
            List<int> arms = chosen.Where(k => !anchored.Contains(k)).ToList();
            return (arms, droop, r ?? new double[count]);
        }

        private static int NearestIndex(int[] values, int wanted)
        {
            int best = 0;
            int bestGap = int.MaxValue;
            for (int i = 0; i < values.Length; i++)
            {
                int gap = Math.Abs(values[i] - wanted);
                if (gap < bestGap)
                {
                    bestGap = gap;
                    best = i;
                }
            }
            return best;
        }

        private static double Choose(int n, int k)
        {
            if (k <= 0 || k > n)
                return 1.0;
            double result = 1.0;
            for (int i = 0; i < k; i++)
                result = result * (n - i) / (i + 1);
            return result;
        }

        private static IEnumerable<int[]> Combinations(int[] pool, int k)
        {
            if (k <= 0 || pool.Length < k)
            {
                yield return Array.Empty<int>();
                yield break;
            }
            var index = new int[k];
            for (int i = 0; i < k; i++)
                index[i] = i;
            while (index[0] <= pool.Length - k)
            {
                yield return index.Select(i => pool[i]).ToArray();
                int slot = k - 1;
                while (slot >= 0 && index[slot] == pool.Length - k + slot)
                    slot--;
                if (slot < 0)
                    yield break;
                index[slot]++;
                for (int j = slot + 1; j < k; j++)
                    index[j] = index[j - 1] + 1;
            }
        }

        /// <summary>
        /// Euler-Bernoulli beam through the arc-length stations, carrying point
        /// loads on pinned supports that hold height and let the bar rotate,
        /// which is what a column head in a notch does.
        /// </summary>
        public static (double[]?, double[]?) Response(
            double[] arc,
            double[] load,
            int[] supports,
            double EI)
        {
            int n = arc.Length;
            if (supports.Length < 2 || n < 2)
                return (null, null);

            int dofs = 2 * n;
            var K = new double[dofs, dofs];
            for (int e = 0; e < n - 1; e++)
            {
                double L = arc[e + 1] - arc[e];
                if (L <= 0.0)
                    continue;
                double c = EI / (L * L * L);
                double[,] k =
                {
                    { 12.0 * c, 6.0 * L * c, -12.0 * c, 6.0 * L * c },
                    { 6.0 * L * c, 4.0 * L * L * c, -6.0 * L * c, 2.0 * L * L * c },
                    { -12.0 * c, -6.0 * L * c, 12.0 * c, -6.0 * L * c },
                    { 6.0 * L * c, 2.0 * L * L * c, -6.0 * L * c, 4.0 * L * L * c },
                };
                int[] map = { 2 * e, (2 * e) + 1, (2 * e) + 2, (2 * e) + 3 };
                for (int a = 0; a < 4; a++)
                {
                    for (int b = 0; b < 4; b++)
                        K[map[a], map[b]] += k[a, b];
                }
            }

            var f = new double[dofs];
            for (int i = 0; i < n; i++)
                f[2 * i] = -load[i];

            var held = new HashSet<int>(supports.Select(s => 2 * s));
            int[] free = Enumerable.Range(0, dofs).Where(d => !held.Contains(d)).ToArray();
            double[]? solved = SolveDense(K, f, free);
            if (solved is null)
                return (null, null);

            var d = new double[dofs];
            for (int i = 0; i < free.Length; i++)
                d[free[i]] = solved[i];

            var reactions = new double[n];
            for (int i = 0; i < n; i++)
            {
                double sum = 0.0;
                for (int j = 0; j < dofs; j++)
                    sum += K[2 * i, j] * d[j];
                reactions[i] = sum - f[2 * i];
            }

            var deflection = new double[n];
            for (int i = 0; i < n; i++)
                deflection[i] = -d[2 * i];
            return (deflection, reactions);
        }

        private static double[]? SolveDense(double[,] K, double[] f, int[] free)
        {
            int m = free.Length;
            if (m == 0)
                return Array.Empty<double>();
            var a = new double[m, m + 1];
            for (int i = 0; i < m; i++)
            {
                for (int j = 0; j < m; j++)
                    a[i, j] = K[free[i], free[j]];
                a[i, m] = f[free[i]];
            }

            for (int col = 0; col < m; col++)
            {
                int pivot = col;
                for (int row = col + 1; row < m; row++)
                {
                    if (Math.Abs(a[row, col]) > Math.Abs(a[pivot, col]))
                        pivot = row;
                }
                if (Math.Abs(a[pivot, col]) < 1e-14)
                    return null;
                if (pivot != col)
                {
                    for (int j = col; j <= m; j++)
                        (a[col, j], a[pivot, j]) = (a[pivot, j], a[col, j]);
                }
                for (int row = col + 1; row < m; row++)
                {
                    double factor = a[row, col] / a[col, col];
                    if (factor == 0.0)
                        continue;
                    for (int j = col; j <= m; j++)
                        a[row, j] -= factor * a[col, j];
                }
            }

            var x = new double[m];
            for (int i = m - 1; i >= 0; i--)
            {
                double sum = a[i, m];
                for (int j = i + 1; j < m; j++)
                    sum -= a[i, j] * x[j];
                x[i] = sum / a[i, i];
            }
            return x;
        }
    }

    internal sealed class Forest
    {
        public List<Point3d> Points { get; } = new();

        public List<(int Child, int Parent)> Segments { get; } = new();

        public List<double> CarriedLoad { get; } = new();

        public List<int> FootIndices { get; } = new();
    }

    /// <summary>
    /// Branching tree columns in the Frei Otto manner, ported from
    /// tools/tree_forest/core.py, which stays the tested source. Points are
    /// clustered into trees of roughly equal load, a foot is dropped at each
    /// cluster's load-weighted centroid, the cluster is merged into a binary
    /// branching topology by repeatedly joining the nearest pair, and load is
    /// accumulated up the tree. Deterministic, so the same input always draws
    /// the same trees.
    /// </summary>
    internal static class TreeBuilder
    {
        public static Forest Build(
            Point3d[] heads,
            double[] load,
            int trees,
            int depth,
            double ground)
        {
            var forest = new Forest();
            if (heads.Length == 0)
                return forest;

            trees = Math.Max(1, Math.Min(trees, heads.Length));
            int[] labels = EqualLoadClusters(heads, load, trees);
            Point3d[] feet = ClusterFeet(heads, load, labels, ground, trees);

            for (int c = 0; c < trees; c++)
            {
                int[] members = Enumerable.Range(0, heads.Length)
                    .Where(i => labels[i] == c).ToArray();
                if (members.Length == 0)
                    continue;

                Point3d[] tips = members.Select(i => heads[i]).ToArray();
                double[] tipW = members.Select(i => load[i]).ToArray();
                int maxTips = Math.Max(1, (int)Math.Pow(2, depth));
                (tips, tipW) = AggregateTips(tips, tipW, maxTips);
                (Point3d[] junctions, List<(int, int)> segs, int apex) =
                    MergeTopology(tips);

                var local = new List<Point3d>(tips);
                local.AddRange(junctions);
                local.Add(feet[c]);
                int footLocal = local.Count - 1;
                segs.Add((apex, footLocal));

                double[] carried = AccumulateLoads(segs, tips.Length, tipW, local.Count);
                int baseIndex = forest.Points.Count;
                forest.Points.AddRange(local);
                for (int s = 0; s < segs.Count; s++)
                {
                    forest.Segments.Add(
                        (segs[s].Item1 + baseIndex, segs[s].Item2 + baseIndex));
                    forest.CarriedLoad.Add(carried[s]);
                }
                forest.FootIndices.Add(baseIndex + footLocal);
            }
            return forest;
        }

        private static int[] EqualLoadClusters(Point3d[] xy, double[] w, int k)
        {
            int n = xy.Length;
            var labels = new int[n];
            if (n == 0 || k <= 1)
                return labels;

            var seeds = new List<int> { ArgMax(w) };
            for (int c = 1; c < k; c++)
            {
                int best = 0;
                double bestDistance = -1.0;
                for (int i = 0; i < n; i++)
                {
                    double nearest = seeds.Min(s => Plan2(xy[i], xy[s]));
                    if (nearest > bestDistance)
                    {
                        bestDistance = nearest;
                        best = i;
                    }
                }
                seeds.Add(best);
            }
            var centroid = seeds.Select(s => new Point2d(xy[s].X, xy[s].Y)).ToArray();

            for (int it = 0; it < 50; it++)
            {
                var updated = new int[n];
                for (int i = 0; i < n; i++)
                {
                    int best = 0;
                    double bestDistance = double.MaxValue;
                    for (int c = 0; c < k; c++)
                    {
                        double d = Plan2(xy[i], centroid[c]);
                        if (d < bestDistance)
                        {
                            bestDistance = d;
                            best = c;
                        }
                    }
                    updated[i] = best;
                }
                bool same = it > 0 && updated.SequenceEqual(labels);
                labels = updated;
                if (same)
                    break;
                Recentre(xy, w, labels, centroid, k);
            }

            for (int pass = 0; pass < 200; pass++)
            {
                var loads = new double[k];
                for (int i = 0; i < n; i++)
                    loads[labels[i]] += w[i];
                int hi = ArgMax(loads);
                int lo = ArgMin(loads);
                if (loads[hi] - loads[lo] < 1e-9)
                    break;
                int[] members = Enumerable.Range(0, n)
                    .Where(i => labels[i] == hi).ToArray();
                if (members.Length <= 1)
                    break;
                int move = members.OrderBy(i => Plan2(xy[i], centroid[lo])).First();
                if (loads[lo] + w[move] >= loads[hi] - 1e-9)
                    break;
                labels[move] = lo;
                Recentre(xy, w, labels, centroid, k);
            }
            return labels;
        }

        private static void Recentre(
            Point3d[] xy, double[] w, int[] labels, Point2d[] centroid, int k)
        {
            for (int c = 0; c < k; c++)
            {
                double sx = 0.0;
                double sy = 0.0;
                double sw = 0.0;
                for (int i = 0; i < xy.Length; i++)
                {
                    if (labels[i] != c)
                        continue;
                    sx += xy[i].X * w[i];
                    sy += xy[i].Y * w[i];
                    sw += w[i];
                }
                if (sw > 0.0)
                    centroid[c] = new Point2d(sx / sw, sy / sw);
            }
        }

        private static Point3d[] ClusterFeet(
            Point3d[] xy, double[] w, int[] labels, double ground, int k)
        {
            var feet = new Point3d[k];
            for (int c = 0; c < k; c++)
            {
                double sx = 0.0;
                double sy = 0.0;
                double sw = 0.0;
                for (int i = 0; i < xy.Length; i++)
                {
                    if (labels[i] != c)
                        continue;
                    sx += xy[i].X * w[i];
                    sy += xy[i].Y * w[i];
                    sw += w[i];
                }
                feet[c] = sw > 0.0
                    ? new Point3d(sx / sw, sy / sw, ground)
                    : new Point3d(0.0, 0.0, ground);
            }
            return feet;
        }

        private static (Point3d[], double[]) AggregateTips(
            Point3d[] xyz, double[] w, int maxTips)
        {
            var pts = xyz.ToList();
            var weights = w.ToList();
            maxTips = Math.Max(1, maxTips);
            while (pts.Count > maxTips && pts.Count > 1)
            {
                int bi = 0;
                int bj = 1;
                double best = double.MaxValue;
                for (int i = 0; i < pts.Count; i++)
                {
                    for (int j = i + 1; j < pts.Count; j++)
                    {
                        double d = pts[i].DistanceToSquared(pts[j]);
                        if (d < best)
                        {
                            best = d;
                            bi = i;
                            bj = j;
                        }
                    }
                }
                double wi = weights[bi];
                double wj = weights[bj];
                double sum = wi + wj;
                pts[bi] = new Point3d(
                    ((pts[bi].X * wi) + (pts[bj].X * wj)) / sum,
                    ((pts[bi].Y * wi) + (pts[bj].Y * wj)) / sum,
                    ((pts[bi].Z * wi) + (pts[bj].Z * wj)) / sum);
                weights[bi] = sum;
                pts.RemoveAt(bj);
                weights.RemoveAt(bj);
            }
            return (pts.ToArray(), weights.ToArray());
        }

        private static (Point3d[], List<(int, int)>, int) MergeTopology(Point3d[] tips)
        {
            int t = tips.Length;
            var segments = new List<(int, int)>();
            if (t <= 1)
                return (Array.Empty<Point3d>(), segments, 0);

            var position = new Dictionary<int, Point3d>();
            for (int i = 0; i < t; i++)
                position[i] = tips[i];
            var active = Enumerable.Range(0, t).ToList();
            int next = t;

            while (active.Count > 1)
            {
                int ai = 0;
                int bi = 1;
                double best = double.MaxValue;
                for (int i = 0; i < active.Count; i++)
                {
                    for (int j = i + 1; j < active.Count; j++)
                    {
                        double d = position[active[i]]
                            .DistanceToSquared(position[active[j]]);
                        if (d < best)
                        {
                            best = d;
                            ai = i;
                            bi = j;
                        }
                    }
                }
                int a = active[ai];
                int b = active[bi];
                position[next] = new Point3d(
                    (position[a].X + position[b].X) / 2.0,
                    (position[a].Y + position[b].Y) / 2.0,
                    (position[a].Z + position[b].Z) / 2.0);
                segments.Add((a, next));
                segments.Add((b, next));
                active.RemoveAt(bi);
                active.RemoveAt(ai);
                active.Add(next);
                next++;
            }

            var junctions = new Point3d[next - t];
            for (int i = t; i < next; i++)
                junctions[i - t] = position[i];
            return (junctions, segments, active[0]);
        }

        private static double[] AccumulateLoads(
            List<(int, int)> segments, int tips, double[] tipWeights, int nodeCount)
        {
            var nodeWeight = new double[nodeCount];
            for (int i = 0; i < tips && i < tipWeights.Length; i++)
                nodeWeight[i] = tipWeights[i];

            var parent = new Dictionary<int, int>();
            foreach ((int child, int up) in segments)
                parent[child] = up;

            // Valid as a single forward pass because every parent id exceeds
            // its children's, by construction in MergeTopology.
            for (int id = 0; id < nodeCount; id++)
            {
                if (parent.TryGetValue(id, out int up))
                    nodeWeight[up] += nodeWeight[id];
            }

            var carried = new double[segments.Count];
            for (int s = 0; s < segments.Count; s++)
                carried[s] = nodeWeight[segments[s].Item1];
            return carried;
        }

        private static double Plan2(Point3d a, Point3d b) =>
            ((a.X - b.X) * (a.X - b.X)) + ((a.Y - b.Y) * (a.Y - b.Y));

        private static double Plan2(Point3d a, Point2d b) =>
            ((a.X - b.X) * (a.X - b.X)) + ((a.Y - b.Y) * (a.Y - b.Y));

        private static int ArgMax(double[] values)
        {
            int best = 0;
            for (int i = 1; i < values.Length; i++)
            {
                if (values[i] > values[best])
                    best = i;
            }
            return best;
        }

        private static int ArgMin(double[] values)
        {
            int best = 0;
            for (int i = 1; i < values.Length; i++)
            {
                if (values[i] < values[best])
                    best = i;
            }
            return best;
        }
    }
}
