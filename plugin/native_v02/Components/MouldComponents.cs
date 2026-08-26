#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Mould Animate: replay the reconfigurable mould building itself, from one
    /// timeline slider.
    ///
    /// Everything the animation needs is already in the solved Result, so there
    /// is nothing to dial. The final geometry says how high the columns must
    /// lift the bars and how far the steppers must reel each infill cable; the
    /// component works both out and interpolates between the flat net on the
    /// ground and that final state.
    ///
    ///   bare    the surface the net takes between the principal bars with
    ///           nothing reeled in, found by relaxing every free node to the
    ///           average of its neighbours with the bars and anchors pinned.
    ///           That is the uniform force-density equilibrium, so by Schek's
    ///           Theorem 1 it is the minimum-way surface: flat or saddled,
    ///           never domed. This carries the HEIGHT.
    ///   relief  what the steppers must reel on top of it to reach the Result.
    ///           This carries the SAG.
    ///
    /// The net starts as the ORIGINAL PATTERN, read back up the chain from the
    /// Result through its Problem's topology, so frame zero is the flat plan
    /// the whole thing was drawn from rather than a level guessed from the
    /// solved geometry. A frame is
    ///
    ///     z = pattern + height * (bare - pattern) + sag * relief
    ///
    /// so at height zero everything stays down on the pattern while the first
    /// reeling happens, which is the order the machine actually builds in.
    ///
    /// This component animates. It runs no equilibrium check and it places no
    /// columns; Column Finder owns that.
    /// </summary>
    public sealed class MouldAnimateComponent : NativeComponentBase
    {
        public MouldAnimateComponent()
            : base(
                "Animate",
                "AN",
                "Replay the mould building itself from one timeline slider: the "
                    + "steppers reeling the net into shape on the ground, the "
                    + "columns lifting it, then the final tensioning. Sag and "
                    + "height are read from the solved Result, not dialled.",
                ComponentCategories.Visualise,
                "mould_animate")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        private Mesh? _previewMesh;
        private readonly List<Line> _previewCables = new();
        private readonly List<Point3d> _previewSupports = new();
        private BoundingBox _clippingBox = BoundingBox.Empty;

        public override Guid ComponentGuid =>
            new("b1f4c7a2-5d63-4e19-9c88-3a7e6d0b52f4");

        public override bool IsPreviewCapable => true;

        public override BoundingBox ClippingBox => _clippingBox;

        protected override void BeforeSolveInstance()
        {
            base.BeforeSolveInstance();
            _previewMesh = null;
            _previewCables.Clear();
            _previewSupports.Clear();
            _clippingBox = BoundingBox.Empty;
        }

        /// <summary>
        /// Draw the frame in the viewport the way TNA Solve draws its solved
        /// network, with the same shaded material, wire colour and support
        /// points, so an animation reads as the same object at a different
        /// moment rather than as a different kind of drawing. The geometry
        /// outputs stay hidden, as on Deconstruct, so nothing double-draws.
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
                // No faces to shade, an FD result for instance, so the net
                // itself carries the drawing.
                foreach (Line cable in _previewCables)
                    args.Display.DrawLine(cable, Color.FromArgb(95, 95, 100));
            }
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
                "Solved FD or TNA result. Its geometry IS the final state, so "
                    + "the sag and the lift are read from it rather than set.",
                GH_ParamAccess.item);
            parameters.AddCurveParameter(
                "Principal Lines",
                "P",
                "The notched bars. Each curve is snapped to the run of net "
                    + "nodes along it; those nodes are carried by the columns, "
                    + "everything else hangs between them.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Time",
                "T",
                "0 to 100, the whole build in one slider. Phase one reels the "
                    + "net part way down while it is flat, phase two lifts it "
                    + "on the columns, phase three reels the rest and tensions "
                    + "both axes against the bars.",
                GH_ParamAccess.item,
                100.0);
            parameters.AddNumberParameter(
                "Pre-Sag",
                "PS",
                "0 to 100, as a percentage of the FINAL sag: how much is reeled "
                    + "in before the columns lift. The remainder is reeled "
                    + "after, which is the part that tightens the form against "
                    + "the bars.",
                GH_ParamAccess.item,
                40.0);
            parameters[2].Optional = true;
            parameters[3].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "The formwork surface at this frame, rebuilt from the Result's "
                    + "own faces. Empty for an FD result, which carries no "
                    + "faces to rebuild from.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Cables",
                "C",
                "Every net member at this frame, infill and bar alike.",
                GH_ParamAccess.list);
            parameters.AddCurveParameter(
                "Principal Lines",
                "PL",
                "The notched bars at this frame, bending as they rise.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Principal Nodes",
                "PN",
                "Every notch: one crossing cable, and a pair of stepper motors "
                    + "pulling it, one each side.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Anchor Nodes",
                "AN",
                "The Result's supports: the side anchors that stay on the "
                    + "ground and take the perimeter cables' prestress.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Perimeter Nodes",
                "PRN",
                "Nodes on the naked boundary of the net.",
                GH_ParamAccess.list);
            parameters.AddParameter(
                new MouldStateParam(),
                "State",
                "S",
                "This frame bundled for Stress Analysis: geometry, member "
                    + "forces, which members are bars and which are cables, and "
                    + "which nodes are notches, anchors and perimeter. Carries "
                    + "no columns; use Column Finder's State for those.",
                GH_ParamAccess.item);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "Which phase of the build this frame is in, the stepper count "
                    + "and how far the bars have risen, and a warning naming "
                    + "any node the net cannot reach.",
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

            double timePct = 100.0;
            double preSag = 40.0;
            data.GetData(2, ref timePct);
            data.GetData(3, ref preSag);

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

                // Keep the ORIGINAL edge index alongside each kept edge. The
                // filter drops invalid and self edges, so a filtered position
                // no longer matches the Result's own MemberForces array, and
                // indexing forces by it would silently attach every force
                // after the first dropped edge to the wrong member.
                (int, int)[] edges = MouldGeometry.ValidEdges(
                    equilibrium, n, out int[] edgeSource);
                if (edges.Length == 0)
                    throw new InvalidOperationException("Result carries no edges.");

                // Start from the ORIGINAL PATTERN, read back up the chain
                // through the Result's Problem. That is the flat plan the whole
                // definition was drawn from, so frame zero is exactly what the
                // Pattern component holds rather than a level inferred from the
                // solved shape. Falling back to the base of the geometry keeps
                // an older Result working.
                double ground = target.Min(p => p.Z);
                double[] startZ;
                IReadOnlyList<Point3Dto>? pattern =
                    equilibrium.Problem?.Topology?.Vertices;
                bool fromPattern = pattern is not null && pattern.Count == n;
                if (fromPattern)
                {
                    startZ = pattern!.Select(p => p.Z).ToArray();
                }
                else
                {
                    startZ = Enumerable.Repeat(ground, n).ToArray();
                }
                Mesh? mesh = MouldGeometry.ThrustMeshFromResult(
                    result, out int[] meshToNode);

                List<int>[] neighbours = MouldGeometry.BuildAdjacency(n, edges);
                var anchorIds = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));

                // Prefer the runs the Pattern already resolved and carried
                // down the chain: they were matched where the curves and the
                // geometry still agreed, and indices survive a surface that
                // rises. Curves wired here remain a per-component override.
                List<List<int>> bars = MouldGeometry.PrincipalRuns(
                    equilibrium, curves, target, edges, out bool fromContract);
                var principalIds = new HashSet<int>(bars.SelectMany(b => b));
                if (principalIds.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "No principal line caught a node, so nothing is held and "
                            + "there is nothing to lift. The bars must lie on the net.");
                }

                var pinned = new bool[n];
                foreach (int i in principalIds)
                    pinned[i] = true;
                foreach (int i in anchorIds)
                    pinned[i] = true;

                double[] bare = MouldGeometry.BareSurface(target, neighbours, pinned);
                var relief = new double[n];
                for (int i = 0; i < n; i++)
                    relief[i] = target[i].Z - bare[i];

                // Sag and height both come out of the Result, so Time is the
                // only thing left to drive.
                double time = Math.Min(Math.Max(timePct, 0.0), 100.0) / 100.0;
                double pre = Math.Min(Math.Max(preSag, 0.0), 100.0) / 100.0;
                double sag;
                double lift;
                string phase;
                if (time < 1.0 / 3.0)
                {
                    sag = pre * (time * 3.0);
                    lift = 0.0;
                    phase = $"1 of 3, reeling flat on the ground: {sag * 100:0}% "
                        + $"of the final sag, heading for {pre * 100:0}%";
                }
                else if (time < 2.0 / 3.0)
                {
                    sag = pre;
                    lift = (time - (1.0 / 3.0)) * 3.0;
                    phase = $"2 of 3, columns lifting: {lift * 100:0}% of the "
                        + $"height, holding {pre * 100:0}% sag";
                }
                else
                {
                    double u = (time - (2.0 / 3.0)) * 3.0;
                    sag = pre + ((1.0 - pre) * u);
                    lift = 1.0;
                    phase = "3 of 3, tensioning both axes against the columns: "
                        + $"{sag * 100:0}% sag";
                }

                var live = new Point3d[n];
                for (int i = 0; i < n; i++)
                {
                    // Interpolate from the pattern's own level, per node, so at
                    // height zero the whole net stays down where it was drawn
                    // while the first reeling happens.
                    double z = startZ[i]
                        + (lift * (bare[i] - startZ[i]))
                        + (sag * relief[i]);
                    live[i] = new Point3d(target[i].X, target[i].Y, z);
                }

                int[] perimeterIds = MouldGeometry.PerimeterNodes(
                    mesh, meshToNode, neighbours, n);

                var barCurves = new List<Curve>();
                foreach (List<int> run in bars)
                {
                    var polyline = new Polyline(run.Select(i => live[i]));
                    if (polyline.IsValid && polyline.Count > 1)
                        barCurves.Add(polyline.ToNurbsCurve());
                }

                double barRise = principalIds.Count > 0
                    ? lift * (principalIds.Select(i => bare[i] - startZ[i]).Average())
                    : 0.0;
                int wantsPush = relief.Count(r => r > 1e-9);

                var report = new List<string>
                {
                    phase,
                    string.Empty,
                    $"nodes {n}, cables {edges.Length}, bars {bars.Count} carrying "
                        + $"{principalIds.Count} notches",
                    $"anchors {anchorIds.Count}, perimeter nodes "
                        + $"{perimeterIds.Length}",
                    fromContract
                        ? "principal lines read from the Pattern via the "
                            + "contract, so nothing was snapped here"
                        : "principal lines snapped from the curves wired to "
                            + "this component, overriding the Pattern",
                    fromPattern
                        ? "starting from the ORIGINAL PATTERN read back through "
                            + "the Result's problem, so frame zero is the plan "
                            + "as drawn"
                        : $"this Result carries no problem topology, so the net "
                            + $"starts flat at {ground:0.###}, the base of the "
                            + "solved geometry",
                    $"steppers required {principalIds.Count * 2} "
                        + "(two per notch, one pulling each side)",
                    $"bars risen {barRise * 1000.0:0.#} mm at this frame",
                };
                if (mesh is null)
                {
                    report.Add(
                        "this Result carries no faces, so there is no shaded "
                            + "surface and the perimeter is read from the net's "
                            + "topology instead. That is expected for FD.");
                }
                if (wantsPush > 0)
                {
                    report.Add(string.Empty);
                    report.Add(
                        $"WARNING: {wantsPush} nodes sit ABOVE the bare surface, "
                            + "so they are asking to be pushed up. A reel only "
                            + "pulls down. That is curvature a net cannot make "
                            + "between the bars, and it needs a mechanism this "
                            + "machine does not have.");
                }

                Mesh? framed = mesh is null
                    ? null
                    : MouldGeometry.DeformMesh(mesh, meshToNode, live);
                var cables = edges
                    .Select(e => new Line(live[e.Item1], live[e.Item2]))
                    .ToList();

                _previewMesh = framed;
                _previewCables.Clear();
                _previewCables.AddRange(cables);
                _previewSupports.Clear();
                _previewSupports.AddRange(
                    anchorIds.OrderBy(i => i).Select(i => live[i]));
                _clippingBox = new BoundingBox(live);

                data.SetData(0, framed);
                data.SetDataList(1, cables);
                data.SetDataList(2, barCurves);
                data.SetDataList(3, principalIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(4, anchorIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(5, perimeterIds.Select(i => live[i]));
                data.SetData(6, new MouldStateGoo(MouldGeometry.BuildState(
                    phase, ground, live, edges, edgeSource, equilibrium,
                    principalIds, anchorIds, perimeterIds,
                    Array.Empty<Point3d>(), Array.Empty<Point3d>(),
                    Array.Empty<double>())));
                data.SetData(7, string.Join(Environment.NewLine, report));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }
    }

    /// <summary>
    /// Geometry shared by Mould Animate and Column Finder: reading the net out
    /// of a Result, snapping the principal bars to it, and the bare surface.
    /// </summary>
    internal static class MouldGeometry
    {
        /// <summary>
        /// The Result's edges, minus any that are out of range or join a node
        /// to itself, with the original index of each survivor returned
        /// alongside. Callers need that index because the Result's per-edge
        /// arrays (member forces, force densities) are still in the unfiltered
        /// order.
        /// </summary>
        public static (int, int)[] ValidEdges(
            EquilibriumResultDto equilibrium,
            int nodeCount,
            out int[] source)
        {
            var kept = new List<(int, int)>();
            var origin = new List<int>();
            for (int i = 0; i < equilibrium.Edges.Count; i++)
            {
                EdgeDto e = equilibrium.Edges[i];
                if (e.U < 0 || e.U >= nodeCount || e.V < 0 || e.V >= nodeCount)
                    continue;
                if (e.U == e.V)
                    continue;
                kept.Add((e.U, e.V));
                origin.Add(i);
            }
            source = origin.ToArray();
            return kept.ToArray();
        }

        public static List<int>[] BuildAdjacency(int count, (int, int)[] edges)
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
        /// the minimum-way surface, flat or saddled and never domed.
        /// </summary>
        public static double[] BareSurface(
            Point3d[] target,
            List<int>[] neighbours,
            bool[] pinned)
        {
            int n = target.Length;
            var z = new double[n];
            for (int i = 0; i < n; i++)
                z[i] = target[i].Z;

            for (int sweep = 0; sweep < 2000; sweep++)
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
                if (shift < 1e-9)
                    break;
            }
            return z;
        }

        /// <summary>
        /// The ordered run of net nodes lying along one principal bar, ordered
        /// by curve parameter so the bar reads end to end. The catch radius
        /// comes from the net's own edge lengths, so it scales with the model
        /// and needs no tolerance input.
        /// </summary>
        /// <summary>
        /// The ordered run of net nodes lying along one principal bar.
        ///
        /// Matching happens IN PLAN, ignoring height. The bars are drawn on the
        /// pattern, which is flat, while the nodes they have to find live on
        /// the solved surface, which is not: comparing in three dimensions puts
        /// the whole raised vault out of reach of its own bars and returns
        /// nothing at all. A principal line is a line in plan; which nodes it
        /// picks up is a plan question, and their heights come from the Result.
        /// </summary>
        /// <summary>
        /// The principal-line runs for a solved Result.
        ///
        /// The Pattern resolves these once, where the curves an author drew and
        /// the geometry they were drawn on still agree, and the contract
        /// carries them down as vertex indices. Preferring them means the
        /// snapping happens once for the whole definition rather than in every
        /// component on every frame, and it cannot go wrong on a raised
        /// surface, because there is no curve left to match. Curves passed here
        /// still win, as a per-component override.
        /// </summary>
        public static List<List<int>> PrincipalRuns(
            EquilibriumResultDto equilibrium,
            IReadOnlyList<Curve> curves,
            Point3d[] nodes,
            (int, int)[] edges,
            out bool fromContract)
        {
            var live = curves.Where(c => c is not null).ToList();
            if (live.Count > 0)
            {
                fromContract = false;
                return live
                    .Select(c => SnapCurveToNodes(c, nodes, edges))
                    .Where(run => run.Count >= 2)
                    .ToList();
            }

            fromContract = true;
            IReadOnlyList<IReadOnlyList<int>>? runs =
                equilibrium.Problem?.Topology?.PrincipalRuns;
            if (runs is null)
                return new List<List<int>>();
            return runs
                .Where(run => run is not null && run.Count >= 2)
                .Select(run => run
                    .Where(i => i >= 0 && i < nodes.Length)
                    .ToList())
                .Where(run => run.Count >= 2)
                .ToList();
        }

        public static List<int> SnapCurveToNodes(
            Curve curve,
            Point3d[] nodes,
            (int, int)[] edges,
            int samples = 512)
        {
            double catchRadius = 0.6 * MedianEdgeLength(nodes, edges);
            double catchSquared = catchRadius * catchRadius;

            // Sample the curve once and compare in plain arithmetic, rather
            // than asking Rhino for a closest point per node. ClosestPoint on a
            // NURBS curve is not cheap, and this runs for every node of every
            // bar on every solve, which an animation does on every frame.
            double[]? ts = curve.DivideByCount(samples, true);
            if (ts is null || ts.Length == 0)
            {
                var fallback = new List<(double, int)>();
                for (int i = 0; i < nodes.Length; i++)
                {
                    if (curve.ClosestPoint(nodes[i], out double t) &&
                        PlanDistanceSquared(nodes[i], curve.PointAt(t)) < catchSquared)
                    {
                        fallback.Add((t, i));
                    }
                }
                return fallback.OrderBy(h => h.Item1).Select(h => h.Item2).ToList();
            }

            var sampled = new Point3d[ts.Length];
            for (int s = 0; s < ts.Length; s++)
                sampled[s] = curve.PointAt(ts[s]);

            var hits = new List<(double Order, int Index)>();
            for (int i = 0; i < nodes.Length; i++)
            {
                int best = -1;
                double bestDistance = double.MaxValue;
                for (int s = 0; s < sampled.Length; s++)
                {
                    double d = PlanDistanceSquared(nodes[i], sampled[s]);
                    if (d < bestDistance)
                    {
                        bestDistance = d;
                        best = s;
                    }
                }
                if (best >= 0 && bestDistance < catchSquared)
                    hits.Add((ts[best], i));
            }
            return hits
                .OrderBy(hit => hit.Order)
                .Select(hit => hit.Index)
                .ToList();
        }

        /// <summary>Squared distance in plan, height ignored.</summary>
        public static double PlanDistanceSquared(Point3d a, Point3d b) =>
            ((a.X - b.X) * (a.X - b.X)) + ((a.Y - b.Y) * (a.Y - b.Y));

        /// <summary>
        /// Median edge length IN PLAN, so the snap radius is measured the same
        /// way the snapping is. Using the spatial length would set too generous
        /// a radius on a steep vault, where a short edge in plan can be long in
        /// space.
        /// </summary>
        public static double MedianEdgeLength(Point3d[] nodes, (int, int)[] edges)
        {
            double[] lengths = edges
                .Select(e => Math.Sqrt(
                    PlanDistanceSquared(nodes[e.Item1], nodes[e.Item2])))
                .Where(length => length > 0.0)
                .OrderBy(length => length)
                .ToArray();
            return lengths.Length == 0 ? 1.0 : lengths[lengths.Length / 2];
        }

        public static int[] PerimeterNodes(
            Mesh? mesh,
            int[] meshToNode,
            List<int>[] neighbours,
            int count)
        {
            if (mesh is not null && mesh.Vertices.Count > 0 &&
                meshToNode.Length == mesh.Vertices.Count)
            {
                bool[] naked = mesh.GetNakedEdgePointStatus();
                if (naked is not null && naked.Length == mesh.Vertices.Count)
                {
                    // The mesh was built from these very nodes, so the mapping
                    // is exact and no nearest-point search is needed. A set
                    // keeps this linear; List.Contains made it quadratic.
                    var found = new List<int>();
                    var seen = new HashSet<int>();
                    for (int v = 0; v < mesh.Vertices.Count; v++)
                    {
                        if (!naked[v])
                            continue;
                        int node = meshToNode[v];
                        if (node >= 0 && node < count && seen.Add(node))
                            found.Add(node);
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

        /// <summary>
        /// Rebuild the thrust mesh from a Result's own form faces, so neither
        /// component needs a mesh wired in. Returns null for an FD result,
        /// which carries no faces, and null rather than throwing if the
        /// mapping is incomplete: a missing surface should not stop the
        /// animation.
        /// </summary>
        public static Mesh? ThrustMeshFromResult(
            ResultDto result,
            out int[] meshToNode)
        {
            meshToNode = Array.Empty<int>();
            EquilibriumResultDto? equilibrium = result.Equilibrium;
            TnaDiagramGraphDto? formGraph = result.FormGraph;
            TnaMappingsDto? mappings = result.Mappings;
            if (equilibrium is null || formGraph is null || mappings is null)
                return null;

            try
            {
                var formToEquilibrium = new Dictionary<int, int>();
                foreach (var item in mappings.SourceVertexToFormVertex)
                {
                    if (!item.FormVertexId.HasValue ||
                        !item.EquilibriumVertexId.HasValue)
                    {
                        continue;
                    }
                    formToEquilibrium[item.FormVertexId.Value] =
                        item.EquilibriumVertexId.Value;
                }

                var mesh = new Mesh();
                var formToMesh = new Dictionary<int, int>();
                var map = new List<int>();
                foreach (TnaGraphVertexDto vertex in
                         formGraph.Vertices.OrderBy(item => item.Id))
                {
                    if (!formToEquilibrium.TryGetValue(vertex.Id, out int eqId) ||
                        eqId < 0 || eqId >= equilibrium.Vertices.Count)
                    {
                        return null;
                    }
                    Point3Dto p = equilibrium.Vertices[eqId];
                    formToMesh[vertex.Id] = mesh.Vertices.Add(p.X, p.Y, p.Z);
                    map.Add(eqId);
                }

                foreach (TnaGraphFaceDto face in
                         formGraph.Faces.OrderBy(item => item.Id))
                {
                    var ids = new List<int>();
                    foreach (int id in face.Vertices)
                    {
                        if (!formToMesh.TryGetValue(id, out int meshId))
                            return null;
                        ids.Add(meshId);
                    }
                    if (ids.Count == 3)
                    {
                        mesh.Faces.AddFace(ids[0], ids[1], ids[2]);
                    }
                    else if (ids.Count == 4)
                    {
                        mesh.Faces.AddFace(ids[0], ids[1], ids[2], ids[3]);
                    }
                    else
                    {
                        for (int i = 1; i < ids.Count - 1; i++)
                            mesh.Faces.AddFace(ids[0], ids[i], ids[i + 1]);
                    }
                }

                if (mesh.Faces.Count == 0)
                    return null;
                mesh.Normals.ComputeNormals();
                // Compact would renumber vertices and break the mapping, and
                // there is nothing to compact: every vertex was just added and
                // every face references one.
                meshToNode = map.ToArray();
                return mesh;
            }
            catch (Exception)
            {
                return null;
            }
        }

        /// <summary>
        /// Bundle a frame into a MouldState. Member forces come from the
        /// Result, so they are the forces of the FINAL state whatever frame the
        /// geometry belongs to; Stress Analysis says as much rather than
        /// letting the pairing pass unremarked.
        /// </summary>
        public static MouldStateDto BuildState(
            string stage,
            double ground,
            Point3d[] live,
            (int, int)[] edges,
            int[] edgeSource,
            EquilibriumResultDto equilibrium,
            IEnumerable<int> principalIds,
            IEnumerable<int> anchorIds,
            IEnumerable<int> perimeterIds,
            IReadOnlyList<Point3d> columnFoot,
            IReadOnlyList<Point3d> columnHead,
            IReadOnlyList<double> columnForce)
        {
            var principal = new HashSet<int>(principalIds);
            var kinds = new string[edges.Length];
            for (int e = 0; e < edges.Length; e++)
            {
                // A member joining two notches of the same bar IS the bar;
                // everything else is an infill cable the steppers reel.
                kinds[e] = principal.Contains(edges[e].Item1) &&
                    principal.Contains(edges[e].Item2)
                    ? "bar"
                    : "infill";
            }

            var forces = new double[edges.Length];
            var densities = new double[edges.Length];
            for (int e = 0; e < edges.Length; e++)
            {
                // Index by where the edge came from, not by where it ended up.
                int src = e < edgeSource.Length ? edgeSource[e] : e;
                forces[e] = src < equilibrium.MemberForces.Count
                    ? equilibrium.MemberForces[src]
                    : 0.0;
                densities[e] = src < equilibrium.ForceDensities.Count
                    ? equilibrium.ForceDensities[src]
                    : 0.0;
            }

            return new MouldStateDto
            {
                Stage = stage,
                Ground = ground,
                Vertices = live.Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                Edges = edges.Select(e => new EdgeDto(e.Item1, e.Item2)).ToArray(),
                MemberForce = forces,
                ForceDensity = densities,
                EdgeKind = kinds,
                PrincipalNodes = principal.OrderBy(i => i).ToArray(),
                AnchorNodes = anchorIds.OrderBy(i => i).ToArray(),
                PerimeterNodes = perimeterIds.ToArray(),
                Reactions = equilibrium.Reactions.ToArray(),
                ColumnFoot = columnFoot
                    .Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                ColumnHead = columnHead
                    .Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                ColumnForce = columnForce.ToArray(),
            };
        }

        public static Mesh DeformMesh(Mesh source, int[] meshToNode, Point3d[] live)
        {
            Mesh deformed = source.DuplicateMesh();
            for (int v = 0; v < deformed.Vertices.Count && v < meshToNode.Length; v++)
            {
                int node = meshToNode[v];
                if (node < 0 || node >= live.Length)
                    continue;
                // Exact, from the mapping the mesh was built with, rather than
                // a nearest-point search that cost one pass over every node for
                // every vertex on every frame.
                deformed.Vertices.SetVertex(v, live[node]);
            }
            deformed.Normals.ComputeNormals();
            deformed.Compact();
            return deformed;
        }
    }
}
