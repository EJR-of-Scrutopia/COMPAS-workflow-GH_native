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
    /// A frame is z = ground + height * (bare - ground) + sag * relief, with
    /// height and sag driven by Time through three phases.
    ///
    /// This component animates. It runs no equilibrium check and it places no
    /// columns; Column Finder owns that.
    /// </summary>
    public sealed class MouldAnimateComponent : NativeComponentBase
    {
        public MouldAnimateComponent()
            : base(
                "Mould Animate",
                "Mould",
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

        public override Guid ComponentGuid =>
            new("b1f4c7a2-5d63-4e19-9c88-3a7e6d0b52f4");

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
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "Optional surface to deform, usually Deconstruct's Thrust Mesh. "
                    + "Without it there is no shaded surface and the perimeter "
                    + "falls back to a topology guess.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Ground",
                "G",
                "Elevation the net starts flat at.",
                GH_ParamAccess.item,
                0.0);
            parameters[2].Optional = true;
            parameters[3].Optional = true;
            parameters[4].Optional = true;
            parameters[5].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "The formwork surface at this frame.",
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
            parameters.AddNumberParameter(
                "Reel",
                "R",
                "Stepper travel per node at this frame, in millimetres, aligned "
                    + "with the Result's vertices. NEGATIVE marks a node asking "
                    + "to be pushed UP, which no reel can do.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Phase",
                "PH",
                "Which phase of the build this frame is in, for captioning.",
                GH_ParamAccess.item);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "Stepper count, travel, lift, and any node the net cannot reach.",
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
            Mesh? mesh = null;
            double ground = 0.0;
            data.GetData(2, ref timePct);
            data.GetData(3, ref preSag);
            data.GetData(4, ref mesh);
            data.GetData(5, ref ground);

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

                List<int>[] neighbours = MouldGeometry.BuildAdjacency(n, edges);
                var anchorIds = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));

                List<List<int>> bars = curves
                    .Where(c => c is not null)
                    .Select(c => MouldGeometry.SnapCurveToNodes(c, target, edges))
                    .Where(run => run.Count >= 2)
                    .ToList();
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
                    double z = ground
                        + (lift * (bare[i] - ground))
                        + (sag * relief[i]);
                    live[i] = new Point3d(target[i].X, target[i].Y, z);
                }

                int[] perimeterIds =
                    MouldGeometry.PerimeterNodes(mesh, target, neighbours, n);

                var barCurves = new List<Curve>();
                foreach (List<int> run in bars)
                {
                    var polyline = new Polyline(run.Select(i => live[i]));
                    if (polyline.IsValid && polyline.Count > 1)
                        barCurves.Add(polyline.ToNurbsCurve());
                }

                double barRise = principalIds.Count > 0
                    ? lift * (principalIds.Select(i => bare[i]).Average() - ground)
                    : 0.0;
                double worstReel = relief.Length == 0
                    ? 0.0
                    : relief.Select(Math.Abs).Max() * 1000.0;
                int wantsPush = relief.Count(r => r > 1e-9);

                var report = new List<string>
                {
                    phase,
                    string.Empty,
                    $"nodes {n}, cables {edges.Length}, bars {bars.Count} carrying "
                        + $"{principalIds.Count} notches",
                    $"anchors {anchorIds.Count}, perimeter nodes {perimeterIds.Length}",
                    $"steppers required {principalIds.Count * 2} "
                        + "(two per notch, one pulling each side)",
                    $"longest stepper travel {worstReel:0.#} mm, bars risen "
                        + $"{barRise * 1000.0:0.#} mm at this frame",
                };
                if (mesh is null)
                {
                    report.Add(
                        "no Mesh given: no shaded surface, and the perimeter is a "
                            + "topology guess. Wire Deconstruct's Thrust Mesh in.");
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

                data.SetData(0, mesh is null
                    ? null
                    : MouldGeometry.DeformMesh(mesh, target, live));
                data.SetDataList(1, edges.Select(
                    e => new Line(live[e.Item1], live[e.Item2])));
                data.SetDataList(2, barCurves);
                data.SetDataList(3, principalIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(4, anchorIds.OrderBy(i => i).Select(i => live[i]));
                data.SetDataList(5, perimeterIds.Select(i => live[i]));
                data.SetDataList(6, relief.Select(r => r * sag * 1000.0));
                data.SetData(7, phase);
                data.SetData(8, string.Join(Environment.NewLine, report));
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
        public static List<int> SnapCurveToNodes(
            Curve curve,
            Point3d[] nodes,
            (int, int)[] edges)
        {
            double catchRadius = 0.6 * MedianEdgeLength(nodes, edges);
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

        public static double MedianEdgeLength(Point3d[] nodes, (int, int)[] edges)
        {
            double[] lengths = edges
                .Select(e => nodes[e.Item1].DistanceTo(nodes[e.Item2]))
                .Where(length => length > 0.0)
                .OrderBy(length => length)
                .ToArray();
            return lengths.Length == 0 ? 1.0 : lengths[lengths.Length / 2];
        }

        public static int[] PerimeterNodes(
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
                        int nearest = NearestNode(new Point3d(mesh.Vertices[v]), target);
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

        public static int NearestNode(Point3d point, Point3d[] nodes)
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

        public static Mesh DeformMesh(Mesh source, Point3d[] target, Point3d[] live)
        {
            Mesh deformed = source.DuplicateMesh();
            for (int v = 0; v < deformed.Vertices.Count; v++)
            {
                var point = new Point3d(deformed.Vertices[v]);
                int nearest = NearestNode(point, target);
                if (nearest < 0)
                    continue;
                deformed.Vertices.SetVertex(
                    v, new Point3d(point.X, point.Y, live[nearest].Z));
            }
            deformed.Normals.ComputeNormals();
            deformed.Compact();
            return deformed;
        }
    }
}
