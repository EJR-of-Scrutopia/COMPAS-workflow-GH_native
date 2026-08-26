#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Column Finder: grow branching tree columns under a set of loaded points,
    /// in the Frei Otto manner, and size every branch to the load it carries.
    ///
    /// Given the points that need holding up and what each one weighs, it
    /// clusters them into trees of roughly equal load, drops a foot at each
    /// cluster's load-weighted centroid, merges the cluster's points into a
    /// binary branching topology by repeatedly joining the nearest pair, and
    /// accumulates the load up the tree so every branch knows what it carries.
    ///
    /// The clustering is deterministic on purpose. Centroids are seeded by
    /// farthest-first starting at the heaviest point, then rebalanced by moving
    /// boundary points from the heaviest cluster to the lightest, but only
    /// while a single move strictly reduces the worst load. Two runs on the
    /// same input give the same trees, which matters when the drawing has to
    /// match the one in the document.
    ///
    /// Pairs with Mould Animate: wire its Column Heads into Points and its
    /// Column Force into Load, and the arms under the notched bars come out as
    /// branching trees instead of posts.
    ///
    /// This is a port of tools/tree_forest/core.py, which is the tested source
    /// of the algorithm; the numbers here should match it point for point.
    /// </summary>
    public sealed class ColumnFinderComponent : NativeComponentBase
    {
        public ColumnFinderComponent()
            : base(
                "Column Finder",
                "Columns",
                "Grow branching tree columns under loaded points and size each "
                    + "branch to the force it carries. Clusters the points into "
                    + "trees of equal load, merges each cluster into a binary "
                    + "branching topology, and reports axial force, radius and "
                    + "utilisation per branch.",
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
            parameters.AddPointParameter(
                "Points",
                "V",
                "The points that need holding up. From Mould Animate, wire "
                    + "Column Heads here.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Load",
                "W",
                "Vertical load at each point, N, aligned with Points. From "
                    + "Mould Animate, wire Column Force here. Missing or short, "
                    + "every point counts as one.",
                GH_ParamAccess.list);
            parameters.AddBooleanParameter(
                "Perimeter",
                "R",
                "True for points on the outer ring, aligned with Points. The "
                    + "ring is grown as its own tier of trees, so a perimeter "
                    + "column never branches into the middle of the vault.",
                GH_ParamAccess.list);
            parameters.AddIntegerParameter(
                "Interior Trees",
                "TI",
                "How many trees carry the interior points.",
                GH_ParamAccess.item,
                3);
            parameters.AddIntegerParameter(
                "Perimeter Trees",
                "TP",
                "How many trees carry the perimeter points.",
                GH_ParamAccess.item,
                0);
            parameters.AddIntegerParameter(
                "Depth",
                "D",
                "How many times a tree may fork. Each tree carries at most "
                    + "2^Depth tips, so nearby points are merged first if there "
                    + "are more than that.",
                GH_ParamAccess.item,
                2);
            parameters.AddNumberParameter(
                "Ground",
                "G",
                "Elevation the feet stand on.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Allowable Stress",
                "S",
                "Allowable axial stress in N/m2, used to size each branch. "
                    + "235e6 is mild steel, 20e6 is a fair working figure for "
                    + "timber. Zero leaves Radius empty.",
                GH_ParamAccess.item,
                235e6);
            parameters[1].Optional = true;
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
                "Branches",
                "B",
                "Every branch of every tree, from child to parent. All the "
                    + "per-branch outputs below are aligned with this.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Carried Load",
                "CL",
                "Vertical load each branch carries, N: everything hanging "
                    + "below it. Pipe or colour the branches by this and the "
                    + "tree reads as a load path.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Axial Force",
                "F",
                "True force along each branch, N, which is the carried load "
                    + "divided by the branch's vertical cosine. A leaning "
                    + "branch always carries MORE than the weight above it, and "
                    + "that difference is what has to go into the foot as "
                    + "horizontal thrust.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Radius",
                "R",
                "Radius each branch needs at the allowable stress, m. This is "
                    + "the taper: branches thicken toward the foot because they "
                    + "carry more, which is what makes a tree column look like "
                    + "one. Empty if Allowable Stress is zero.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Angle",
                "A",
                "Lean of each branch from vertical, degrees. Watch this: past "
                    + "roughly sixty degrees a branch is doing more pushing "
                    + "sideways than holding up.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Tips",
                "T",
                "Where the trees touch the load: anchor these.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Junctions",
                "J",
                "Where branches meet. Leave these free in a relaxation and the "
                    + "tree finds its own Frei Otto geometry.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Feet",
                "FT",
                "Where each tree stands on the ground.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Foot Load",
                "FL",
                "Total vertical load into each foot, N, aligned with Feet. "
                    + "These sum to the whole load, which is the check that "
                    + "nothing was invented or dropped.",
                GH_ParamAccess.list);
            parameters.AddIntegerParameter(
                "Tree",
                "TID",
                "Which tree each branch belongs to, aligned with Branches.",
                GH_ParamAccess.list);
            parameters.AddIntegerParameter(
                "Point Tree",
                "PT",
                "Which tree each input point was given to, aligned with Points. "
                    + "Colour the points by this to show the catchment of every "
                    + "column.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "Tree count, load balance across the feet, and the worst branch.",
                GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            var points = new List<Point3d>();
            if (!data.GetDataList(0, points) || points.Count == 0)
                return;

            var loads = new List<double>();
            data.GetDataList(1, loads);
            var ring = new List<bool>();
            data.GetDataList(2, ring);

            int interiorTrees = 3;
            int perimeterTrees = 0;
            int depth = 2;
            double ground = 0.0;
            double allowable = 235e6;
            data.GetData(3, ref interiorTrees);
            data.GetData(4, ref perimeterTrees);
            data.GetData(5, ref depth);
            data.GetData(6, ref ground);
            data.GetData(7, ref allowable);

            int n = points.Count;
            var w = new double[n];
            for (int i = 0; i < n; i++)
            {
                double value = i < loads.Count ? loads[i] : 1.0;
                w[i] = Math.Abs(value) > 1e-12 ? Math.Abs(value) : 1.0;
            }
            var isRing = new bool[n];
            for (int i = 0; i < n; i++)
                isRing[i] = i < ring.Count && ring[i];

            try
            {
                Forest forest = BuildForest(
                    points.ToArray(), w, isRing,
                    Math.Max(interiorTrees, 0), Math.Max(perimeterTrees, 0),
                    Math.Max(depth, 0), ground);

                int m = forest.Segments.Count;
                var branches = new List<Line>(m);
                var axial = new List<double>(m);
                var radius = new List<double>(m);
                var angle = new List<double>(m);

                for (int s = 0; s < m; s++)
                {
                    (int child, int parent) = forest.Segments[s];
                    Point3d a = forest.Points[child];
                    Point3d b = forest.Points[parent];
                    branches.Add(new Line(a, b));

                    Vector3d v = b - a;
                    double length = v.Length;
                    double vertical = Math.Abs(v.Z);
                    double carried = forest.CarriedLoad[s];
                    // A leaning branch carries more than the weight above it:
                    // the axial force is the vertical share divided by the
                    // branch's vertical cosine.
                    double cos = length > 1e-12 ? vertical / length : 1.0;
                    double force = cos > 1e-6 ? carried / cos : carried;
                    axial.Add(force);
                    angle.Add(
                        length > 1e-12
                            ? Rhino.RhinoMath.ToDegrees(Math.Acos(
                                Math.Min(Math.Max(cos, -1.0), 1.0)))
                            : 0.0);
                    if (allowable > 0.0)
                        radius.Add(Math.Sqrt(force / (Math.PI * allowable)));
                }

                var footLoad = new List<double>();
                foreach (int foot in forest.FootIndices)
                {
                    double total = 0.0;
                    for (int s = 0; s < m; s++)
                    {
                        if (forest.Segments[s].Parent == foot)
                            total += forest.CarriedLoad[s];
                    }
                    footLoad.Add(total);
                }

                data.SetDataList(0, branches);
                data.SetDataList(1, forest.CarriedLoad);
                data.SetDataList(2, axial);
                data.SetDataList(3, radius);
                data.SetDataList(4, angle);
                data.SetDataList(5, forest.TipIndices.Select(i => forest.Points[i]));
                data.SetDataList(
                    6, forest.JunctionIndices.Select(i => forest.Points[i]));
                data.SetDataList(7, forest.FootIndices.Select(i => forest.Points[i]));
                data.SetDataList(8, footLoad);
                data.SetDataList(9, forest.TreeOfSegment);
                data.SetDataList(10, forest.PointTree);
                data.SetData(11, Report(
                    n, w, forest, footLoad, axial, angle, radius, allowable));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        private static string Report(
            int pointCount,
            double[] w,
            Forest forest,
            List<double> footLoad,
            List<double> axial,
            List<double> angle,
            List<double> radius,
            double allowable)
        {
            double total = w.Sum();
            double intoFeet = footLoad.Sum();
            var lines = new List<string>
            {
                $"{forest.TreeCount} trees carrying {pointCount} points, "
                    + $"{forest.Segments.Count} branches",
                $"load {total:0} N in, {intoFeet:0} N into the feet "
                    + $"({(total > 0 ? 100.0 * intoFeet / total : 100.0):0.##}% "
                    + "accounted for)",
            };
            if (footLoad.Count > 0)
            {
                lines.Add(
                    $"foot loads {footLoad.Min():0} to {footLoad.Max():0} N; "
                        + "the clustering balances these, so a wide spread means "
                        + "the tree count does not suit the point layout");
            }
            if (axial.Count > 0)
            {
                lines.Add($"axial force up to {axial.Max():0} N");
                lines.Add($"worst lean {angle.Max():0.#} degrees from vertical");
            }
            if (radius.Count > 0)
            {
                lines.Add(
                    $"branch radius {radius.Min() * 1000.0:0.#} to "
                        + $"{radius.Max() * 1000.0:0.#} mm at {allowable / 1e6:0.#} "
                        + "MPa. Pipe the branches by Radius and the taper is the "
                        + "load path made visible.");
            }
            return string.Join(Environment.NewLine, lines);
        }

        // ------------------------------------------------------------------
        // The forest, ported from tools/tree_forest/core.py
        // ------------------------------------------------------------------

        private sealed class Forest
        {
            public List<Point3d> Points { get; } = new();

            public List<(int Child, int Parent)> Segments { get; } = new();

            public List<double> CarriedLoad { get; } = new();

            public List<int> TreeOfSegment { get; } = new();

            public List<int> TipIndices { get; } = new();

            public List<int> JunctionIndices { get; } = new();

            public List<int> FootIndices { get; } = new();

            public int[] PointTree { get; set; } = Array.Empty<int>();

            public int TreeCount { get; set; }
        }

        private static Forest BuildForest(
            Point3d[] nodes,
            double[] w,
            bool[] ring,
            int interiorTrees,
            int perimeterTrees,
            int depth,
            double ground)
        {
            var forest = new Forest
            {
                PointTree = Enumerable.Repeat(-1, nodes.Length).ToArray(),
            };
            int[] interior = Enumerable.Range(0, nodes.Length)
                .Where(i => !ring[i]).ToArray();
            int[] perimeter = Enumerable.Range(0, nodes.Length)
                .Where(i => ring[i]).ToArray();

            int next = BuildTier(
                forest, nodes, w, interior, interiorTrees, depth, ground, 0);
            next = BuildTier(
                forest, nodes, w, perimeter, perimeterTrees, depth, ground, next);
            forest.TreeCount = next;
            return forest;
        }

        private static int BuildTier(
            Forest forest,
            Point3d[] nodes,
            double[] w,
            int[] ids,
            int k,
            int depth,
            double ground,
            int treeBase)
        {
            if (ids.Length == 0 || k <= 0)
                return treeBase;
            k = Math.Min(k, ids.Length);

            Point3d[] sub = ids.Select(i => nodes[i]).ToArray();
            double[] subw = ids.Select(i => w[i]).ToArray();
            int[] labels = EqualLoadClusters(sub, subw, k);
            Point3d[] feet = ClusterFeet(sub, subw, labels, ground, k);

            for (int c = 0; c < k; c++)
            {
                int tree = treeBase + c;
                int[] members = Enumerable.Range(0, ids.Length)
                    .Where(i => labels[i] == c).ToArray();
                foreach (int i in members)
                    forest.PointTree[ids[i]] = tree;
                if (members.Length == 0)
                    continue;

                Point3d[] cxyz = members.Select(i => sub[i]).ToArray();
                double[] cw = members.Select(i => subw[i]).ToArray();
                int maxTips = Math.Max(1, (int)Math.Pow(2, depth));
                (Point3d[] tipXyz, double[] tipW) = AggregateTips(cxyz, cw, maxTips);
                (Point3d[] junctions, List<(int, int)> segs, int apex) =
                    MergeTopology(tipXyz);

                int tips = tipXyz.Length;
                var local = new List<Point3d>(tipXyz);
                local.AddRange(junctions);
                local.Add(feet[c]);
                int footLocal = local.Count - 1;
                segs.Add((apex, footLocal));

                double[] carried = AccumulateLoads(segs, tips, tipW, local.Count);

                int baseIndex = forest.Points.Count;
                forest.Points.AddRange(local);
                for (int s = 0; s < segs.Count; s++)
                {
                    forest.Segments.Add(
                        (segs[s].Item1 + baseIndex, segs[s].Item2 + baseIndex));
                    forest.CarriedLoad.Add(carried[s]);
                    forest.TreeOfSegment.Add(tree);
                }
                for (int i = 0; i < tips; i++)
                    forest.TipIndices.Add(baseIndex + i);
                for (int i = 0; i < junctions.Length; i++)
                    forest.JunctionIndices.Add(baseIndex + tips + i);
                forest.FootIndices.Add(baseIndex + footLocal);
            }
            return treeBase + k;
        }

        /// <summary>
        /// Load-weighted k-means with a greedy equal-load rebalance, seeded
        /// deterministically by farthest-first from the heaviest point so two
        /// runs on the same input give the same trees.
        /// </summary>
        private static int[] EqualLoadClusters(
            Point3d[] xy,
            double[] w,
            int k,
            int iterations = 50,
            int balancePasses = 200)
        {
            int n = xy.Length;
            var labels = new int[n];
            if (n == 0)
                return labels;
            k = Math.Max(1, Math.Min(k, n));
            if (k == 1)
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

            for (int it = 0; it < iterations; it++)
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
                RecentreAll(xy, w, labels, centroid, k);
            }

            for (int pass = 0; pass < balancePasses; pass++)
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
                int move = members
                    .OrderBy(i => Plan2(xy[i], centroid[lo]))
                    .First();
                if (loads[lo] + w[move] >= loads[hi] - 1e-9)
                    break;
                labels[move] = lo;
                RecentreAll(xy, w, labels, centroid, k);
            }
            return labels;
        }

        private static void RecentreAll(
            Point3d[] xy,
            double[] w,
            int[] labels,
            Point2d[] centroid,
            int k)
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
            Point3d[] xy,
            double[] w,
            int[] labels,
            double ground,
            int k)
        {
            var feet = new Point3d[k];
            double fx = 0.0;
            double fy = 0.0;
            double fw = 0.0;
            for (int i = 0; i < xy.Length; i++)
            {
                fx += xy[i].X * w[i];
                fy += xy[i].Y * w[i];
                fw += w[i];
            }
            var fallback = new Point2d(
                fw > 0 ? fx / fw : 0.0, fw > 0 ? fy / fw : 0.0);

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
                    : new Point3d(fallback.X, fallback.Y, ground);
            }
            return feet;
        }

        /// <summary>
        /// Merge the nearest pair of tips into their load-weighted midpoint
        /// until no more than maxTips remain, so a tree never has to fork more
        /// times than its Depth allows.
        /// </summary>
        private static (Point3d[], double[]) AggregateTips(
            Point3d[] xyz,
            double[] w,
            int maxTips)
        {
            var pts = xyz.ToList();
            var weights = w.ToList();
            maxTips = Math.Max(1, maxTips);
            while (pts.Count > maxTips && pts.Count > 1)
            {
                (int i, int j) = NearestPair(pts);
                double wi = weights[i];
                double wj = weights[j];
                double sum = wi + wj;
                pts[i] = new Point3d(
                    ((pts[i].X * wi) + (pts[j].X * wj)) / sum,
                    ((pts[i].Y * wi) + (pts[j].Y * wj)) / sum,
                    ((pts[i].Z * wi) + (pts[j].Z * wj)) / sum);
                weights[i] = sum;
                pts.RemoveAt(j);
                weights.RemoveAt(j);
            }
            return (pts.ToArray(), weights.ToArray());
        }

        private static (int, int) NearestPair(List<Point3d> pts)
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
            return (bi, bj);
        }

        /// <summary>
        /// Agglomerative nearest-pair binary merge of the tips up to one apex.
        /// Junction ids follow the tips and are created in order, so every
        /// parent id exceeds its children's, which is what lets the load
        /// accumulate in a single forward pass.
        /// </summary>
        private static (Point3d[], List<(int, int)>, int) MergeTopology(
            Point3d[] tips)
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
            List<(int, int)> segments,
            int tips,
            double[] tipWeights,
            int nodeCount)
        {
            var nodeWeight = new double[nodeCount];
            for (int i = 0; i < tips && i < tipWeights.Length; i++)
                nodeWeight[i] = tipWeights[i];

            var parent = new Dictionary<int, int>();
            foreach ((int child, int up) in segments)
                parent[child] = up;

            // Forward pass is valid because every parent id exceeds its
            // children's, by construction in MergeTopology.
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
