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
    /// Mould Animate: the reconfigurable mould's two motions, driven by two
    /// 0-100 sliders so the machine can be animated from a solved Result.
    ///
    /// The machine has two distinct movements and they are kept apart here
    /// because they are different mechanisms, not two halves of one:
    ///
    ///   Sag     the net lies flat on the ground and the stepper motors at each
    ///           principal node reel their infill cables in, so the surface
    ///           takes its shape while still down. Two steppers per node, one
    ///           per side, because the pull is not symmetric on a free form.
    ///   Height  the columns under the principal lines extend and lift the
    ///           whole formwork.
    ///
    /// Every node's elevation is
    ///
    ///     z = ground + height * (bare - ground) + sag * relief
    ///
    /// where `bare` is the surface the net takes between the principal lines
    /// with nothing reeled in, and `relief` is what the steppers must add on
    /// top of it to reach the solved Result. `bare` is the unloaded
    /// minimum-way surface of Schek's Theorem 1, computed here by relaxing the
    /// free nodes to the average of their neighbours with the principal nodes
    /// and anchors pinned, which is the same equilibrium at uniform force
    /// density. So sag 0, height 0 is the flat net on the ground; sag 100,
    /// height 0 is the shaped net still down; sag 100, height 100 is the
    /// Result exactly.
    ///
    /// RELIEF is therefore a machine specification rather than a structural
    /// one: it is stepper travel per node. A node reading near zero needs no
    /// stepper at all, and a node reading NEGATIVE is asking to be pushed UP,
    /// which no reel can do and which marks where the geometry wants curvature
    /// a cable net cannot take.
    ///
    /// This component animates a Result that has already been solved. It does
    /// no equilibrium check of its own, deliberately, so that a smooth
    /// animation is never mistaken for a structural result.
    /// </summary>
    public sealed class MouldAnimateComponent : NativeComponentBase
    {
        public MouldAnimateComponent()
            : base(
                "Mould Animate",
                "Mould",
                "Animate the reconfigurable mould's two motions from a solved "
                    + "Result: the steppers reeling the net into shape on the "
                    + "ground, then the columns lifting it to height. Also "
                    + "deconstructs the net into principal lines, principal "
                    + "nodes, anchors and perimeter nodes.",
                ComponentCategories.Visualise,
                "mould_animate")
        {
            // A data-and-animation boundary, like Deconstruct: Display owns the
            // viewport, so these outputs do not fight it in Grasshopper's red.
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("b1f4c7a2-5d63-4e19-9c88-3a7e6d0b52f4");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Solved FD or TNA result. Its vertices are the target the "
                    + "mould has to reach at sag 100, height 100.",
                GH_ParamAccess.item);
            parameters.AddCurveParameter(
                "Principal Lines",
                "P",
                "The notched bars. Each curve is snapped to the run of net "
                    + "nodes lying along it, and every node on a bar is held: "
                    + "it is positioned by the columns, not by the cables. "
                    + "Give the few bars you will actually build, not mesh "
                    + "edges.",
                GH_ParamAccess.list);
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "Optional surface to deform, usually Deconstruct's Thrust "
                    + "Mesh. Without it the animation still returns cables, "
                    + "bars and node sets, but no shaded surface, and the "
                    + "perimeter falls back to a topology guess.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Sag",
                "S",
                "0 to 100. How far the steppers have reeled the infill cables "
                    + "in. At 0 the net is flat, at 100 it carries the whole "
                    + "shape of the Result.",
                GH_ParamAccess.item,
                100.0);
            parameters.AddNumberParameter(
                "Height",
                "H",
                "0 to 100. How far the columns have lifted the principal "
                    + "lines. At 0 the bars sit on the ground, at 100 they are "
                    + "at the Result's elevation.",
                GH_ParamAccess.item,
                100.0);
            parameters.AddNumberParameter(
                "Ground",
                "G",
                "Elevation the net starts flat at, in model units.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddIntegerParameter(
                "Columns Per Line",
                "C",
                "How many column arms stand under EACH principal line, not "
                    + "shared across all of them, so no bar is left with fewer "
                    + "than the rest. Arms land on notches, since a notch is "
                    + "where a crossing cable meets the bar and the arm can "
                    + "only slide within one notch span. Positions are solved, "
                    + "not spaced: see EI.",
                GH_ParamAccess.item,
                3);
            parameters.AddNumberParameter(
                "Bar Stiffness",
                "EI",
                "Bending stiffness of a notched bar, N m2. The arms are placed "
                    + "by solving the bar as a beam on point supports under the "
                    + "load the net hands it, and keeping the arrangement that "
                    + "leaves it straightest. A uniformly loaded beam wants its "
                    + "supports about a fifth of the length in from each end, "
                    + "never spread to the ends, so spacing arms evenly is the "
                    + "wrong rule and this input is what replaces it. Zero or "
                    + "blank falls back to even spacing.",
                GH_ParamAccess.item,
                0.0);
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
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "The formwork surface at the current Sag and Height. Empty "
                    + "unless a Mesh was given.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Cables",
                "C",
                "Every net member at the current state, infill and bar alike.",
                GH_ParamAccess.list);
            parameters.AddCurveParameter(
                "Principal Lines",
                "PL",
                "The notched bars at the current state, one polyline each, "
                    + "bending as the columns lift them.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Principal Nodes",
                "PN",
                "Every node on a principal line: one notch, and a pair of "
                    + "stepper motors pulling its infill cable each side.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Anchor Nodes",
                "AN",
                "The Result's resolved supports: the side anchors that stay on "
                    + "the ground and take the perimeter cables' prestress.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Perimeter Nodes",
                "PRN",
                "Nodes on the naked boundary of the net, anchored or not. Not "
                    + "all of the perimeter is on the ground, only the sides.",
                GH_ParamAccess.list);
            parameters.AddLineParameter(
                "Columns",
                "COL",
                "The column arms at the current Height, foot on the ground and "
                    + "head at a notch. They lean along the surface slope, "
                    + "which is the sliding, angled case.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Column Heads",
                "CH",
                "Where each arm meets its bar, aligned with Columns.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Column Force",
                "CF",
                "Upward force each arm supplies, N, aligned with Columns. "
                    + "These sum to the load the net hands the bars. An arm "
                    + "that would have to PULL DOWN is rejected outright, "
                    + "because a column can only push.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Bar Droop",
                "BD",
                "Worst droop of each bar between its own arms, mm, one per "
                    + "principal line. This goes straight into the cast "
                    + "surface on top of the net's own sag, so it has to sit "
                    + "inside tolerance too. Empty unless EI was given.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Relief",
                "R",
                "Stepper travel per node, in millimetres, aligned with the "
                    + "Result's vertices: how far that cable is reeled below "
                    + "the bare surface. Near zero needs no stepper. NEGATIVE "
                    + "means the node wants to be pushed UP, which no cable "
                    + "can do.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "What the animation is showing, and the stepper and column "
                    + "numbers it implies.",
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

            Mesh? mesh = null;
            data.GetData(2, ref mesh);

            double sagPct = 100.0;
            double heightPct = 100.0;
            double ground = 0.0;
            int perLine = 3;
            double barEi = 0.0;
            data.GetData(3, ref sagPct);
            data.GetData(4, ref heightPct);
            data.GetData(5, ref ground);
            data.GetData(6, ref perLine);
            data.GetData(7, ref barEi);

            double sag = Math.Min(Math.Max(sagPct, 0.0), 100.0) / 100.0;
            double lift = Math.Min(Math.Max(heightPct, 0.0), 100.0) / 100.0;
            perLine = Math.Max(perLine, 2);

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                EquilibriumResultDto equilibrium = result.Equilibrium!;
                Point3d[] target = equilibrium.Vertices
                    .Select(v => new Point3d(v.X, v.Y, v.Z))
                    .ToArray();
                int n = target.Length;
                if (n == 0)
                    throw new InvalidOperationException("Result carries no vertices.");

                var edges = equilibrium.Edges
                    .Where(e => e.U >= 0 && e.U < n && e.V >= 0 && e.V < n && e.U != e.V)
                    .Select(e => (e.U, e.V))
                    .ToArray();
                if (edges.Length == 0)
                    throw new InvalidOperationException("Result carries no edges.");

                List<int>[] neighbours = BuildAdjacency(n, edges);

                var anchorIds = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));

                List<List<int>> bars = curves
                    .Where(c => c is not null)
                    .Select(c => SnapCurveToNodes(c, target, edges))
                    .Where(run => run.Count >= 2)
                    .ToList();

                var principalIds = new HashSet<int>(bars.SelectMany(b => b));
                if (principalIds.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "No principal line caught a node. The bars must lie on "
                            + "the net. Without them nothing is held and the "
                            + "animation has nothing to lift.");
                }

                // Pinned: the bars, because the columns place them, plus the
                // anchors, because they are fixed to the ground.
                var pinned = new bool[n];
                foreach (int i in principalIds)
                    pinned[i] = true;
                foreach (int i in anchorIds)
                    pinned[i] = true;

                double[] bare = BareSurface(target, neighbours, pinned);
                var relief = new double[n];
                for (int i = 0; i < n; i++)
                    relief[i] = target[i].Z - bare[i];

                var live = new Point3d[n];
                for (int i = 0; i < n; i++)
                {
                    double z = ground
                        + (lift * (bare[i] - ground))
                        + (sag * relief[i]);
                    live[i] = new Point3d(target[i].X, target[i].Y, z);
                }

                // What the net hands each notch: the vertical reaction the
                // solve already found there. That is the line load the bar has
                // to carry, and therefore what decides where its arms go.
                var barLoad = new double[n];
                foreach (NodalVectorDto reaction in equilibrium.Reactions)
                {
                    if (reaction.NodeId >= 0 && reaction.NodeId < n)
                        barLoad[reaction.NodeId] = Math.Abs(reaction.Vector.Z);
                }

                int[] perimeterIds = PerimeterNodes(mesh, target, neighbours, n);

                var cables = edges
                    .Select(e => new Line(live[e.Item1], live[e.Item2]))
                    .ToList();

                var barCurves = new List<Curve>();
                foreach (List<int> run in bars)
                {
                    var polyline = new Polyline(run.Select(i => live[i]));
                    if (polyline.IsValid && polyline.Count > 1)
                        barCurves.Add(polyline.ToNurbsCurve());
                }

                (List<Line> columns, List<Point3d> heads,
                 List<double> armForce, List<double> barDroop) =
                    PlaceColumns(
                        bars, live, barLoad, anchorIds, ground, perLine, barEi);

                Mesh? outMesh = mesh is null ? null : DeformMesh(mesh, target, live);

                data.SetData(0, outMesh);
                data.SetDataList(1, cables);
                data.SetDataList(2, barCurves);
                data.SetDataList(3, principalIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(4, anchorIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(5, perimeterIds.Select(i => live[i]));
                data.SetDataList(6, columns);
                data.SetDataList(7, heads);
                data.SetDataList(8, armForce);
                data.SetDataList(9, barDroop);
                data.SetDataList(10, relief.Select(r => r * 1000.0));
                data.SetData(11, Report(
                    n, edges.Length, bars, principalIds.Count, anchorIds.Count,
                    perimeterIds.Length, columns.Count, relief, sag, lift,
                    ground, bare, mesh is not null, barEi, barDroop, armForce));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        private static List<int>[] BuildAdjacency(
            int count,
            (int, int)[] edges)
        {
            var neighbours = new List<int>[count];
            for (int i = 0; i < count; i++)
                neighbours[i] = new List<int>();
            foreach ((int u, int v) in edges)
            {
                neighbours[u].Add(v);
                neighbours[v].Add(u);
            }
            return neighbours;
        }

        /// <summary>
        /// The surface the net takes between the pinned nodes with nothing
        /// reeled in: every free node at the average of its neighbours. That is
        /// the uniform force-density equilibrium, so by Schek's Theorem 1 it is
        /// the weighted minimum-way surface, flat or saddled and never domed.
        /// Gauss-Seidel rather than a matrix solve, because it has to run on
        /// every slider tick.
        /// </summary>
        private static double[] BareSurface(
            Point3d[] target,
            List<int>[] neighbours,
            bool[] pinned)
        {
            int n = target.Length;
            var z = new double[n];
            for (int i = 0; i < n; i++)
                z[i] = target[i].Z;

            const int maxSweeps = 2000;
            const double tolerance = 1e-9;
            for (int sweep = 0; sweep < maxSweeps; sweep++)
            {
                double shift = 0.0;
                for (int i = 0; i < n; i++)
                {
                    if (pinned[i] || neighbours[i].Count == 0)
                        continue;
                    double sum = 0.0;
                    foreach (int j in neighbours[i])
                        sum += z[j];
                    double updated = sum / neighbours[i].Count;
                    shift = Math.Max(shift, Math.Abs(updated - z[i]));
                    z[i] = updated;
                }
                if (shift < tolerance)
                    break;
            }
            return z;
        }

        /// <summary>
        /// The ordered run of net nodes lying along one principal bar. Nodes
        /// are ordered by curve parameter so the bar reads end to end, and the
        /// catch radius is set from the net's own edge lengths so it scales
        /// with the model rather than needing a tolerance input.
        /// </summary>
        private static List<int> SnapCurveToNodes(
            Curve curve,
            Point3d[] nodes,
            (int, int)[] edges)
        {
            double median = MedianEdgeLength(nodes, edges);
            double catchRadius = 0.6 * median;

            var hits = new List<(double Parameter, int Index)>();
            for (int i = 0; i < nodes.Length; i++)
            {
                if (!curve.ClosestPoint(nodes[i], out double t))
                    continue;
                if (nodes[i].DistanceTo(curve.PointAt(t)) < catchRadius)
                    hits.Add((t, i));
            }
            return hits
                .OrderBy(hit => hit.Parameter)
                .Select(hit => hit.Index)
                .ToList();
        }

        private static double MedianEdgeLength(
            Point3d[] nodes,
            (int, int)[] edges)
        {
            double[] lengths = edges
                .Select(e => nodes[e.Item1].DistanceTo(nodes[e.Item2]))
                .Where(length => length > 0.0)
                .OrderBy(length => length)
                .ToArray();
            if (lengths.Length == 0)
                return 1.0;
            return lengths[lengths.Length / 2];
        }

        /// <summary>
        /// Naked-boundary nodes. A mesh answers this exactly; without one the
        /// fall-back is a topology guess, flagging nodes with fewer neighbours
        /// than the interior of the net has.
        /// </summary>
        private static int[] PerimeterNodes(
            Mesh? mesh,
            Point3d[] target,
            List<int>[] neighbours,
            int count)
        {
            if (mesh is not null && mesh.Vertices.Count > 0)
            {
                bool[] naked = mesh.GetNakedEdgePointStatus();
                if (naked is not null && naked.Length == mesh.Vertices.Count)
                {
                    var found = new List<int>();
                    for (int v = 0; v < mesh.Vertices.Count; v++)
                    {
                        if (!naked[v])
                            continue;
                        int nearest = NearestNode(
                            new Point3d(mesh.Vertices[v]), target);
                        if (nearest >= 0 && !found.Contains(nearest))
                            found.Add(nearest);
                    }
                    if (found.Count > 0)
                        return found.ToArray();
                }
            }

            int[] degrees = neighbours.Select(list => list.Count).ToArray();
            if (degrees.Length == 0)
                return Array.Empty<int>();
            int[] sorted = degrees.OrderBy(d => d).ToArray();
            int interior = sorted[sorted.Length / 2];
            return Enumerable.Range(0, count)
                .Where(i => degrees[i] < interior)
                .ToArray();
        }

        private static int NearestNode(Point3d point, Point3d[] nodes)
        {
            int best = -1;
            double bestDistance = double.MaxValue;
            for (int i = 0; i < nodes.Length; i++)
            {
                double distance = point.DistanceToSquared(nodes[i]);
                if (distance < bestDistance)
                {
                    bestDistance = distance;
                    best = i;
                }
            }
            return best;
        }

        /// <summary>
        /// Column arms under each bar, counted PER BAR so no bar ends up with
        /// fewer arms than its neighbour. Arms are spread evenly along the bar
        /// by arc length and land on notches, which are the nodes where the
        /// crossing cables meet, because an arm can only slide within one notch
        /// span. Anchor nodes are skipped: the frame is already held down
        /// there, so an arm at an anchor would be lifting against its own tie.
        /// </summary>
        /// <summary>
        /// Column arms under each bar, counted PER BAR so no bar ends up with
        /// fewer arms than its neighbour, and POSITIONED by solving the bar
        /// rather than by spacing it.
        ///
        /// A notched bar on two or three arms is a beam, and a beam does not
        /// want its supports spread evenly: for a uniformly loaded one they
        /// belong about a fifth of the length in from each end, which balances
        /// the cantilever moment over each arm against the moment at midspan.
        /// Spreading arms to the ends leaves the middle to droop and spends
        /// them on a part of the bar already held by its anchor.
        ///
        /// Since arms can only stand at notches and there are only a handful,
        /// every arrangement is tried and the straightest kept. Anchors count
        /// as supports but cost no arm, and any arrangement needing an arm to
        /// PULL DOWN is rejected, because a column can only push.
        ///
        /// Without EI there is nothing to solve, so it falls back to even
        /// spacing and says so in the report.
        /// </summary>
        private static (List<Line>, List<Point3d>, List<double>, List<double>)
            PlaceColumns(
                List<List<int>> bars,
                Point3d[] live,
                double[] barLoad,
                HashSet<int> anchors,
                double ground,
                int perLine,
                double barEi)
        {
            var columns = new List<Line>();
            var heads = new List<Point3d>();
            var forces = new List<double>();
            var droops = new List<double>();

            foreach (List<int> bar in bars)
            {
                if (bar.Count < 2)
                    continue;

                var arc = new double[bar.Count];
                for (int k = 1; k < bar.Count; k++)
                {
                    arc[k] = arc[k - 1]
                        + live[bar[k - 1]].DistanceTo(live[bar[k]]);
                }
                double span = arc[arc.Length - 1];
                if (span <= 0.0)
                    continue;

                double[] load = bar.Select(i => barLoad[i]).ToArray();
                var anchored = new List<int>();
                for (int k = 0; k < bar.Count; k++)
                {
                    if (anchors.Contains(bar[k]))
                        anchored.Add(k);
                }

                List<int> chosen;
                double droop = 0.0;
                double[]? reactions = null;
                if (barEi > 0.0)
                {
                    (chosen, droop, reactions) = BestArms(
                        arc, load, anchored, perLine, barEi);
                }
                else
                {
                    chosen = new List<int>();
                    for (int c = 0; c < perLine; c++)
                    {
                        double want = span * (c + 0.5) / perLine;
                        int pick = 0;
                        double best = double.MaxValue;
                        for (int k = 0; k < arc.Length; k++)
                        {
                            double gap = Math.Abs(arc[k] - want);
                            if (gap < best)
                            {
                                best = gap;
                                pick = k;
                            }
                        }
                        if (!chosen.Contains(pick))
                            chosen.Add(pick);
                    }
                }

                if (barEi > 0.0)
                    droops.Add(droop * 1000.0);

                foreach (int k in chosen.Where(k => !anchored.Contains(k))
                             .OrderBy(k => k))
                {
                    Point3d head = live[bar[k]];
                    double rise = head.Z - ground;
                    if (rise <= 0.0)
                        continue;

                    // Lean the arm along the slope of the bar, so it stands in
                    // the direction of the force it carries rather than plumb.
                    int before = bar[Math.Max(k - 1, 0)];
                    int after = bar[Math.Min(k + 1, bar.Count - 1)];
                    Vector3d along = live[after] - live[before];
                    var foot = new Point3d(head.X, head.Y, ground);
                    double run = Math.Sqrt((along.X * along.X) + (along.Y * along.Y));
                    if (run > 1e-9 && Math.Abs(along.Z) > 1e-9)
                    {
                        double offset = 0.5 * rise * (along.Z / run);
                        foot = new Point3d(
                            head.X - (along.X / run * offset),
                            head.Y - (along.Y / run * offset),
                            ground);
                    }

                    columns.Add(new Line(foot, head));
                    heads.Add(head);
                    forces.Add(reactions is null ? 0.0 : reactions[k]);
                }
            }
            return (columns, heads, forces, droops);
        }

        /// <summary>
        /// Try every arrangement of arms on a coarsened bar and keep the one
        /// that leaves it straightest, rejecting any that needs an arm to pull
        /// down. Coarse on purpose: placement finer than a few per cent of the
        /// bar is wasted when arms can only stand at notches.
        /// </summary>
        private static (List<int>, double, double[]) BestArms(
            double[] arc,
            double[] load,
            List<int> anchored,
            int perLine,
            double EI)
        {
            int n = arc.Length;
            int stations = Math.Min(n, 41);
            int[] coarse = Enumerable.Range(0, stations)
                .Select(i => (int)Math.Round(
                    (double)i * (n - 1) / Math.Max(stations - 1, 1)))
                .Distinct()
                .ToArray();

            var anchoredCoarse = new HashSet<int>(
                anchored.Select(a => NearestIndex(coarse, a)));
            int[] pool = Enumerable.Range(0, coarse.Length)
                .Where(i => !anchoredCoarse.Contains(i))
                .ToArray();

            // budget the candidates so the trial count stays bounded
            int budget = 4000;
            int allowed = Math.Max(perLine + 1, 4);
            while (allowed < pool.Length && Choose(allowed + 1, perLine) <= budget)
                allowed++;
            if (pool.Length > allowed)
            {
                pool = Enumerable.Range(0, allowed)
                    .Select(i => pool[(int)Math.Round(
                        (double)i * (pool.Length - 1) / Math.Max(allowed - 1, 1))])
                    .Distinct()
                    .ToArray();
            }

            List<int>? best = null;
            double bestScore = double.MaxValue;
            List<int>? fallback = null;
            double fallbackScore = double.MaxValue;

            foreach (int[] combo in Combinations(pool, Math.Max(perLine, 0)))
            {
                var supports = new SortedSet<int>(anchoredCoarse);
                foreach (int c in combo)
                    supports.Add(c);
                if (supports.Count < 2)
                    continue;

                int[] full = supports.Select(s => coarse[s]).Distinct()
                    .OrderBy(s => s).ToArray();
                if (full.Length < 2)
                    continue;

                (double[]? defl, double[]? reac) = BeamResponse(arc, load, full, EI);
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

            List<int> chosen = best ?? fallback ?? new List<int> { 0, n - 1 };
            (double[]? d, double[]? r) = BeamResponse(arc, load, chosen.ToArray(), EI);
            double droop = d is null ? 0.0 : d.Select(Math.Abs).Max();
            return (chosen, droop, r ?? new double[n]);
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
            if (k <= 0)
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
        /// Euler-Bernoulli beam through the given arc-length stations, carrying
        /// point loads and standing on pinned supports that hold height and let
        /// the bar rotate, which is what a column head in a notch does.
        /// </summary>
        private static (double[]?, double[]?) BeamResponse(
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
            int[] free = Enumerable.Range(0, dofs).Where(d => !held.Contains(d))
                .ToArray();
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

        /// <summary>
        /// Gaussian elimination with partial pivoting on the free rows only.
        /// The systems here are a few dozen unknowns, so a dense solve is both
        /// simpler and quicker than pulling in a linear-algebra dependency.
        /// </summary>
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

        private static Mesh DeformMesh(
            Mesh source,
            Point3d[] target,
            Point3d[] live)
        {
            var deformed = source.DuplicateMesh();
            for (int v = 0; v < deformed.Vertices.Count; v++)
            {
                var point = new Point3d(deformed.Vertices[v]);
                int nearest = NearestNode(point, target);
                if (nearest < 0)
                    continue;
                deformed.Vertices.SetVertex(
                    v,
                    new Point3d(point.X, point.Y, live[nearest].Z));
            }
            deformed.Normals.ComputeNormals();
            deformed.Compact();
            return deformed;
        }

        private static string Report(
            int nodes,
            int edges,
            List<List<int>> bars,
            int principalNodes,
            int anchors,
            int perimeter,
            int columns,
            double[] relief,
            double sag,
            double lift,
            double ground,
            double[] bare,
            bool hasMesh,
            double barEi,
            List<double> barDroop,
            List<double> armForce)
        {
            double worstReel = relief.Length == 0
                ? 0.0
                : relief.Select(Math.Abs).Max() * 1000.0;
            int wantsPush = relief.Count(r => r > 1e-9);
            double barHeight = 0.0;
            if (bars.Count > 0)
            {
                barHeight = bars
                    .SelectMany(b => b)
                    .Select(i => bare[i])
                    .DefaultIfEmpty(ground)
                    .Average();
            }

            var lines = new List<string>
            {
                "ANIMATION ONLY. This replays a Result that was already solved; "
                    + "it runs no equilibrium check of its own. Use the solver "
                    + "components for that.",
                string.Empty,
                $"sag {sag * 100:0}%, height {lift * 100:0}%, ground {ground:0.###}",
                $"nodes {nodes}, cables {edges}, principal bars {bars.Count} "
                    + $"carrying {principalNodes} notches",
                $"anchors {anchors}, perimeter nodes {perimeter}, column arms "
                    + $"{columns}",
                $"steppers required: {principalNodes * 2} "
                    + "(two per notch, one pulling each side)",
                $"longest stepper travel {worstReel:0.#} mm",
                $"bars have risen to {(lift * (barHeight - ground)) * 1000.0:0.#} mm "
                    + "above the ground at this height",
            };

            if (barEi > 0.0 && barDroop.Count > 0)
            {
                lines.Add(
                    $"bar droop between arms, worst {barDroop.Max():0.#} mm "
                        + $"(EI {barEi:0.###} N m2). Arms are SOLVED, not "
                        + "spaced: a loaded bar wants them about a fifth of its "
                        + "length in from each end.");
                if (armForce.Count > 0)
                {
                    lines.Add(
                        $"arm force {armForce.Min():0} to {armForce.Max():0} N, "
                            + $"carrying {armForce.Sum():0} N in total");
                }
            }
            else
            {
                lines.Add(
                    "arms are spaced evenly, which is the WRONG rule for a bar "
                        + "on two or three supports. Give EI and they will be "
                        + "placed by solving the bar as a beam instead.");
            }

            if (!hasMesh)
            {
                lines.Add(
                    "no Mesh given, so the surface output is empty and the "
                        + "perimeter is a topology guess. Wire Deconstruct's "
                        + "Thrust Mesh in for both.");
            }
            if (wantsPush > 0)
            {
                lines.Add(string.Empty);
                lines.Add(
                    $"WARNING: {wantsPush} nodes have positive relief, meaning "
                        + "they sit ABOVE the bare surface and are asking to be "
                        + "pushed up. A reeled cable can only pull down, so "
                        + "this is the curvature a net cannot make between the "
                        + "bars, and it needs a mechanism this machine does not "
                        + "yet have.");
            }
            return string.Join(Environment.NewLine, lines);
        }
    }
}
