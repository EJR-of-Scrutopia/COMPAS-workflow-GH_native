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
    /// It takes the solved Result as its form finder, projects the principal
    /// lines onto it to find the notches, and reads the load the net hands each
    /// notch straight off the Result's own reactions. Nothing has to be told to
    /// it twice.
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
            parameters.AddCurveParameter(
                "Principal Lines",
                "P",
                "The notched bars. Each is projected onto the Result to find "
                    + "which nodes are its notches.",
                GH_ParamAccess.list);
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
            parameters.AddNumberParameter(
                "Bar Stiffness",
                "EI",
                "Bending stiffness of a notched bar, N m2, used to solve the "
                    + "arm positions and report how far the bar droops between "
                    + "them. Zero falls back to even spacing, which is the "
                    + "wrong rule for a bar on two or three arms.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Ground",
                "G",
                "Elevation the feet stand on.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Allowable Stress",
                "S",
                "Allowable axial stress, N/m2, used to size each member. 235e6 "
                    + "is mild steel, 20e6 a fair working figure for timber.",
                GH_ParamAccess.item,
                235e6);
            parameters[2].Optional = true;
            parameters[3].Optional = true;
            parameters[4].Optional = true;
            parameters[5].Optional = true;
            parameters[6].Optional = true;
            parameters[7].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddLineParameter(
                "Columns",
                "C",
                "Every column member, from the arm head down to the ground. "
                    + "With Trees at 0 these are straight posts; above 0 they "
                    + "are the branches of each tree. Force and Radius align "
                    + "with this.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Heads",
                "H",
                "Where the arms meet the bars: the notches the columns hold.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Feet",
                "F",
                "Where the columns stand on the ground.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Force",
                "FO",
                "Axial force in each member, N. A leaning member carries more "
                    + "than the weight above it, by one over its vertical "
                    + "cosine, and that surplus is what the foot resists "
                    + "sideways.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Radius",
                "R",
                "Radius each member needs at the allowable stress, m. Pipe the "
                    + "columns by this and the taper is the load path made "
                    + "visible.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Bar Droop",
                "BD",
                "Worst droop of each bar between its own arms, mm, one per "
                    + "principal line. This lands in the cast surface on top of "
                    + "the sag of the net, so it has to sit inside tolerance "
                    + "too. Empty unless Bar Stiffness was given.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "Where the arms went and why, what they carry, and whether the "
                    + "load is all accounted for.",
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

            var curves = new List<Curve>();
            data.GetDataList(1, curves);

            int perLine = 3;
            int trees = 0;
            int depth = 2;
            double barEi = 0.0;
            double ground = 0.0;
            double allowable = 235e6;
            data.GetData(2, ref perLine);
            data.GetData(3, ref trees);
            data.GetData(4, ref depth);
            data.GetData(5, ref barEi);
            data.GetData(6, ref ground);
            data.GetData(7, ref allowable);
            perLine = Math.Max(perLine, 2);

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

                var edges = equilibrium.Edges
                    .Where(e => e.U >= 0 && e.U < n && e.V >= 0 && e.V < n && e.U != e.V)
                    .Select(e => (e.U, e.V))
                    .ToArray();

                var anchors = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));

                List<List<int>> bars = curves
                    .Where(c => c is not null)
                    .Select(c => MouldGeometry.SnapCurveToNodes(c, nodes, edges))
                    .Where(run => run.Count >= 2)
                    .ToList();
                if (bars.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "No principal line caught a node. The bars must lie on "
                            + "the Result's net.");
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
                var barDroop = new List<double>();

                foreach (List<int> bar in bars)
                {
                    (List<int> chosen, double droop, double[] reactions) =
                        BeamSolver.ArmsForBar(
                            bar, nodes, nodeLoad, anchors, perLine, barEi);
                    if (barEi > 0.0)
                        barDroop.Add(droop * 1000.0);
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
                        members.Add(new Line(forest.Points[child], forest.Points[parent]));
                        carried.Add(forest.CarriedLoad[s]);
                    }
                    feet.AddRange(forest.FootIndices.Select(i => forest.Points[i]));
                }

                var force = new List<double>(members.Count);
                var radius = new List<double>(members.Count);
                for (int i = 0; i < members.Count; i++)
                {
                    Vector3d v = members[i].To - members[i].From;
                    double length = v.Length;
                    double cos = length > 1e-12 ? Math.Abs(v.Z) / length : 1.0;
                    double axial = cos > 1e-6 ? carried[i] / cos : carried[i];
                    force.Add(axial);
                    radius.Add(allowable > 0.0
                        ? Math.Sqrt(axial / (Math.PI * allowable))
                        : 0.0);
                }

                data.SetDataList(0, members);
                data.SetDataList(1, heads);
                data.SetDataList(2, feet);
                data.SetDataList(3, force);
                data.SetDataList(4, radius);
                data.SetDataList(5, barDroop);
                data.SetData(6, Report(
                    bars, heads, headLoad, members, force, radius, feet,
                    barDroop, trees, depth, barEi, allowable));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        private static string Report(
            List<List<int>> bars,
            List<Point3d> heads,
            List<double> headLoad,
            List<Line> members,
            List<double> force,
            List<double> radius,
            List<Point3d> feet,
            List<double> barDroop,
            int trees,
            int depth,
            double barEi,
            double allowable)
        {
            double total = headLoad.Sum();
            var lines = new List<string>
            {
                $"{bars.Count} bars, {heads.Count} arms, {feet.Count} feet, "
                    + $"{members.Count} members",
                $"the arms carry {total:0} N between them",
            };

            if (barEi > 0.0)
            {
                lines.Add(
                    "arm positions SOLVED as a beam: a loaded bar wants its "
                        + "supports about a fifth of its length in from each "
                        + "end, never spread to the ends.");
                if (barDroop.Count > 0)
                {
                    lines.Add(
                        $"bar droop between arms {barDroop.Min():0.#} to "
                            + $"{barDroop.Max():0.#} mm. This adds to the sag of "
                            + "the net, so check it against the same tolerance.");
                }
            }
            else
            {
                lines.Add(
                    "arms SPACED EVENLY, which is the wrong rule for a bar on "
                        + "two or three supports. Give Bar Stiffness and they "
                        + "will be solved instead.");
            }

            lines.Add(trees <= 0
                ? "Trees 0: every arm drops straight to its own foot."
                : $"Trees {trees} at depth {depth}: the arms are gathered into "
                    + "branching trees clustered by equal load.");

            if (headLoad.Count > 0)
            {
                lines.Add(
                    $"arm force {headLoad.Min():0} to {headLoad.Max():0} N");
            }
            if (force.Count > 0)
            {
                lines.Add($"axial force up to {force.Max():0} N");
            }
            if (radius.Count > 0 && allowable > 0.0)
            {
                lines.Add(
                    $"member radius {radius.Min() * 1000.0:0.#} to "
                        + $"{radius.Max() * 1000.0:0.#} mm at {allowable / 1e6:0.#} MPa");
            }
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
