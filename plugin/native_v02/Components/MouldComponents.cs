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
                    + "only slide within one notch span.",
                GH_ParamAccess.item,
                3);
            parameters[2].Optional = true;
            parameters[3].Optional = true;
            parameters[4].Optional = true;
            parameters[5].Optional = true;
            parameters[6].Optional = true;
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
            data.GetData(3, ref sagPct);
            data.GetData(4, ref heightPct);
            data.GetData(5, ref ground);
            data.GetData(6, ref perLine);

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

                (List<Line> columns, List<Point3d> heads) =
                    PlaceColumns(bars, live, anchorIds, ground, perLine);

                Mesh? outMesh = mesh is null ? null : DeformMesh(mesh, target, live);

                data.SetData(0, outMesh);
                data.SetDataList(1, cables);
                data.SetDataList(2, barCurves);
                data.SetDataList(3, principalIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(4, anchorIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(5, perimeterIds.Select(i => live[i]));
                data.SetDataList(6, columns);
                data.SetDataList(7, heads);
                data.SetDataList(8, relief.Select(r => r * 1000.0));
                data.SetData(9, Report(
                    n, edges.Length, bars, principalIds.Count, anchorIds.Count,
                    perimeterIds.Length, columns.Count, relief, sag, lift,
                    ground, bare, mesh is not null));
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
        private static (List<Line>, List<Point3d>) PlaceColumns(
            List<List<int>> bars,
            Point3d[] live,
            HashSet<int> anchors,
            double ground,
            int perLine)
        {
            var columns = new List<Line>();
            var heads = new List<Point3d>();

            foreach (List<int> bar in bars)
            {
                List<int> usable = bar.Where(i => !anchors.Contains(i)).ToList();
                if (usable.Count < 2)
                    usable = bar;
                if (usable.Count == 0)
                    continue;

                var arc = new double[usable.Count];
                for (int k = 1; k < usable.Count; k++)
                {
                    arc[k] = arc[k - 1]
                        + live[usable[k - 1]].DistanceTo(live[usable[k]]);
                }
                double span = arc[arc.Length - 1];
                if (span <= 0.0)
                    continue;

                var chosen = new SortedSet<int>();
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
                    chosen.Add(pick);
                }

                foreach (int k in chosen)
                {
                    Point3d head = live[usable[k]];
                    double rise = head.Z - ground;
                    if (rise <= 0.0)
                        continue;

                    // Lean the arm along the slope of the bar, so it stands in
                    // the direction of the force it carries rather than plumb.
                    int before = usable[Math.Max(k - 1, 0)];
                    int after = usable[Math.Min(k + 1, usable.Count - 1)];
                    Vector3d along = live[after] - live[before];
                    var foot = new Point3d(head.X, head.Y, ground);
                    double run = Math.Sqrt((along.X * along.X) + (along.Y * along.Y));
                    if (run > 1e-9 && Math.Abs(along.Z) > 1e-9)
                    {
                        double slope = along.Z / run;
                        double offset = 0.5 * rise * slope;
                        foot = new Point3d(
                            head.X - (along.X / run * offset),
                            head.Y - (along.Y / run * offset),
                            ground);
                    }

                    columns.Add(new Line(foot, head));
                    heads.Add(head);
                }
            }
            return (columns, heads);
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
            bool hasMesh)
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
