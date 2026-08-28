#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Monitor: decode a Result into the forces the structure is actually
    /// under, split by what carries them.
    ///
    /// It separates the three load paths that behave differently and are worth
    /// reading apart: the infill cables, which must stay in tension or they go
    /// slack; the notched bars, which take the cable pull along their length
    /// and hand it to the columns; and the columns, which are the only members
    /// in compression and whose lean turns part of their load into horizontal
    /// thrust at the foot.
    ///
    /// Nothing here assumes a capacity. Every number is a demand, to size and
    /// test against.
    /// </summary>
    public sealed class StressAnalysisComponent : NativeComponentBase
    {
        public StressAnalysisComponent()
            : base(
                "Monitor",
                "MON",
                "Read the numbers off a Result at whatever frame it carries: "
                    + "the forces on the cables, the bars, the columns and the "
                    + "anchors, and how far the bars bend. Demands only: no "
                    + "capacity, stress limit or tolerance is assumed.",
                ComponentCategories.Visualise,
                "stress_analysis")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("e8c216af-5b74-4d93-a027-9f61be40d5c3");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "A Result from Columns (the built state) or from Animate (this "
                    + "frame). With a frame the numbers are read at the live "
                    + "geometry; the member forces are those of the finished "
                    + "state either way, because the mould is meant to reach it.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "EI",
                "EI",
                "Bending stiffness of one notched bar, N.m2: Young's modulus "
                    + "times the second moment of area of the section you mean "
                    + "to build it from. This is the ONLY place a stiffness is "
                    + "asked for, and it is asked for here on purpose. Where "
                    + "the arms go does not depend on it, because stiffness "
                    + "cancels out of that comparison, so putting a number on "
                    + "it upstream would look like it were tuning the "
                    + "placement when it cannot. Here it converts the bar's "
                    + "bending into millimetres you can hold a tolerance "
                    + "against. Steel 40x40x3 SHS is about 1.9e5; a 48.3x4 CHS "
                    + "about 2.4e5. Zero or negative reports the shape of the "
                    + "bending without a scale.",
                GH_ParamAccess.item,
                0.0);
            parameters[1].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddLineParameter(
                "Cables",
                "C",
                "The infill cables: everything the steppers reel. Cable Force "
                    + "aligns with this.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Cable Force",
                "CF",
                "Tension in each infill cable, N. A cable at or below zero has "
                    + "gone SLACK and is holding nothing, which is a failure of "
                    + "the prestress rather than of the cable.",
                GH_ParamAccess.list);
            parameters.AddLineParameter(
                "Bars",
                "B",
                "The notched-bar members, between consecutive notches on a "
                    + "principal line. Bar Force aligns with this.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Bar Force",
                "BF",
                "Axial force along each bar member, N. This is the pull the bar "
                    + "carries between its notches, on top of the bending it "
                    + "takes between its columns.",
                GH_ParamAccess.list);
            parameters.AddLineParameter(
                "Columns",
                "CO",
                "The columns from the Result's Mould block, at the frame it carries "
                    + "if it has one and at the built state otherwise. Column Force, "
                    + "Thrust and Lean align with this.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Column Force",
                "CL",
                "Axial compression in each column, N.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Thrust",
                "TH",
                "Horizontal force in each column member, N: the part of a "
                    + "leaning member's axial force that acts sideways. A plumb "
                    + "member reads zero. Aligned with Columns, so a tree "
                    + "branch reports its own horizontal too; only the members "
                    + "STANDING ON THE GROUND put theirs into the foundation, "
                    + "and the monitor.thrust_into_ground diagnostic sums those "
                    + "alone. A branch's horizontal is balanced at its junction "
                    + "by its siblings.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Anchors",
                "A",
                "The anchor nodes. Anchor Force aligns with this.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Anchor Force",
                "AF",
                "Reaction at each anchor, N. These are the side ties holding "
                    + "the perimeter cables down, so their horizontal part is "
                    + "what the ground anchorage has to take.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Bar Nodes",
                "BN",
                "Every notch, as a TREE with one branch per principal line, in "
                    + "order along that bar. Bar Sag aligns with this, branch "
                    + "for branch and item for item.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Bar Sag",
                "BS",
                "How far the bar bends away from straight at each notch, in "
                    + "MILLIMETRES, with EI as given. Positive is downward. "
                    + "The bar is solved as a continuous beam on its own "
                    + "columns and anchors, so a notch between two columns "
                    + "sags and a notch over one does not. This is the number "
                    + "to hold a build tolerance against; it is a demand, not "
                    + "a verdict, and no allowable is assumed. Empty if the "
                    + "state carries no principal runs.",
                GH_ParamAccess.tree);
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "The Result passed through with Monitor's own diagnostics "
                    + "added: slack cables, worst forces, foundation thrust, bar "
                    + "sag. Wire it to Diagnose.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Lean",
                "LN",
                "Degrees from vertical per column member, aligned with "
                    + "Columns. Past sixty a member pushes sideways more than it "
                    + "holds up.",
                GH_ParamAccess.list);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }

            double stiffness = 0.0;
            data.GetData(1, ref stiffness);

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                EquilibriumResultDto equilibrium = result.Equilibrium!;
                MouldDto? mould = result.Mould;
                MouldColumnsDto? block = mould?.Columns;
                MouldFrameDto? frame = mould?.Frame;

                // The live net when a frame is present, the solved one otherwise.
                IReadOnlyList<Point3Dto> source = frame?.Vertices ?? equilibrium.Vertices;
                Point3d[] v = source.Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray();
                int n = v.Length;
                (int, int)[] edges = MouldGeometry.ValidEdges(equilibrium, n, out int[] edgeSource);
                List<List<int>> runs = MouldGeometry.PrincipalRuns(equilibrium, n);
                var principal = new HashSet<int>(runs.SelectMany(r => r));
                var anchors = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));

                var cables = new List<Line>();
                var cableForce = new List<double>();
                var bars = new List<Line>();
                var barForce = new List<double>();
                for (int e = 0; e < edges.Length; e++)
                {
                    (int a, int b) = edges[e];
                    int src = e < edgeSource.Length ? edgeSource[e] : e;
                    double force = src < equilibrium.MemberForces.Count
                        ? equilibrium.MemberForces[src]
                        : 0.0;
                    var line = new Line(v[a], v[b]);
                    // A member joining two notches is the bar; everything else
                    // is an infill cable the steppers reel.
                    if (principal.Contains(a) && principal.Contains(b))
                    {
                        bars.Add(line);
                        barForce.Add(force);
                    }
                    else
                    {
                        cables.Add(line);
                        cableForce.Add(force);
                    }
                }

                var columns = new List<Line>();
                var columnForce = new List<double>();
                var thrust = new List<double>();
                var lean = new List<double>();
                var standsOnGround = new List<bool>();
                if (block is not null)
                {
                    IReadOnlyList<Point3Dto> columnSource = frame?.ColumnNodes ?? block.Nodes;
                    Point3d[] cn = columnSource.Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray();
                    var feet = new HashSet<int>(block.Feet);
                    for (int m = 0; m < block.Members.Count; m++)
                    {
                        EdgeDto member = block.Members[m];
                        if (member.U < 0 || member.U >= cn.Length ||
                            member.V < 0 || member.V >= cn.Length)
                        {
                            continue;
                        }
                        var line = new Line(cn[member.U], cn[member.V]);
                        columns.Add(line);
                        double force = m < block.MemberForce.Count ? block.MemberForce[m] : 0.0;
                        columnForce.Add(force);

                        Vector3d d = line.To - line.From;
                        double length = d.Length;
                        double horizontal = Math.Sqrt((d.X * d.X) + (d.Y * d.Y));
                        double sin = length > 1e-12 ? horizontal / length : 0.0;
                        thrust.Add(force * sin);
                        lean.Add(length > 1e-12
                            ? Rhino.RhinoMath.ToDegrees(Math.Atan2(horizontal, Math.Abs(d.Z)))
                            : 0.0);
                        // A member stands on the ground when its lower end is a
                        // foot in the block, by index; no height test needed.
                        standsOnGround.Add(feet.Contains(member.U));
                    }
                }

                var reactionByNode = new Dictionary<int, Vector3d>();
                foreach (NodalVectorDto r in equilibrium.Reactions)
                    reactionByNode[r.NodeId] = new Vector3d(r.Vector.X, r.Vector.Y, r.Vector.Z);
                var anchorPoints = new List<Point3d>();
                var anchorForce = new List<Vector3d>();
                foreach (int id in anchors.OrderBy(i => i))
                {
                    anchorPoints.Add(v[id]);
                    anchorForce.Add(
                        reactionByNode.TryGetValue(id, out Vector3d vec) ? vec : Vector3d.Zero);
                }

                // A notch is HELD where a column head stands on it, by index,
                // or where it is itself an anchor.
                var held = new HashSet<int>(anchors);
                if (block is not null)
                {
                    foreach (int node in block.HeadNode)
                    {
                        if (node >= 0 && node < n)
                            held.Add(node);
                    }
                }
                (List<List<Point3d>> barNodes, List<List<double>> barSag) =
                    BarBending(runs, v, edges, edgeSource, equilibrium, held, stiffness);

                data.SetDataList(0, cables);
                data.SetDataList(1, cableForce);
                data.SetDataList(2, bars);
                data.SetDataList(3, barForce);
                data.SetDataList(4, columns);
                data.SetDataList(5, columnForce);
                data.SetDataList(6, thrust);
                data.SetDataList(7, anchorPoints);
                data.SetDataList(8, anchorForce);
                data.SetDataTree(9, OutputTree.Points(barNodes));
                data.SetDataTree(10, OutputTree.Numbers(barSag));
                data.SetData(11, new ResultGoo(ResultDiagnostics.Replace(
                    result, "Monitor", Diagnostics(
                        standsOnGround, frame, block, cableForce, barForce,
                        columnForce, thrust, anchorForce, barSag, stiffness))));
                data.SetDataList(12, lean);
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        /// <summary>
        /// How far each bar bends away from straight, in millimetres.
        ///
        /// EI IS ASKED FOR HERE AND NOWHERE ELSE. Where the arms go is chosen
        /// by comparing one arrangement against another, and stiffness is a
        /// common factor in that comparison, so it cancels: the same arms come
        /// out whatever EI is. Here it turns the shape of the bending into the
        /// millimetres a build tolerance is written in.
        ///
        /// The bar is solved the same way it was placed: an Euler-Bernoulli
        /// beam on point supports, held wherever a column head or an anchor
        /// meets it. With EI at zero the deflected shape is returned with EI of
        /// one; it still shows WHERE the bar bends and in what proportion.
        /// </summary>
        private static (List<List<Point3d>>, List<List<double>>) BarBending(
            List<List<int>> runs,
            Point3d[] v,
            (int, int)[] edges,
            int[] edgeSource,
            EquilibriumResultDto equilibrium,
            HashSet<int> held,
            double stiffness)
        {
            var nodes = new List<List<Point3d>>();
            var sag = new List<List<double>>();
            if (runs.Count == 0)
                return (nodes, sag);

            double EI = stiffness > 0.0 ? stiffness : 1.0;

            var incident = new List<(int Other, double Force)>[v.Length];
            for (int i = 0; i < v.Length; i++)
                incident[i] = new List<(int, double)>();
            for (int e = 0; e < edges.Length; e++)
            {
                (int a, int b) = edges[e];
                int src = e < edgeSource.Length ? edgeSource[e] : e;
                double force = src < equilibrium.MemberForces.Count
                    ? equilibrium.MemberForces[src]
                    : 0.0;
                incident[a].Add((b, force));
                incident[b].Add((a, force));
            }

            foreach (List<int> run in runs)
            {
                nodes.Add(run.Select(i => v[i]).ToList());
                if (run.Count < 2)
                {
                    sag.Add(new List<double>());
                    continue;
                }

                Vector3d[] pull = MouldGeometry.BarLoads(run, v, incident);
                Vector3d[] across = MouldGeometry.BarTransverse(run, v, pull);
                var arc = new double[run.Count];
                for (int k = 1; k < run.Count; k++)
                    arc[k] = arc[k - 1] + v[run[k - 1]].DistanceTo(v[run[k]]);
                double[] load = across.Select(a => Math.Abs(a.Z)).ToArray();
                int[] supports = Enumerable.Range(0, run.Count)
                    .Where(k => held.Contains(run[k]))
                    .ToArray();

                // Under two supports the bar is a mechanism, not a beam.
                if (supports.Length < 2)
                {
                    sag.Add(Enumerable.Repeat(0.0, run.Count).ToList());
                    continue;
                }

                (double[]? deflection, double[]? _) =
                    BeamSolver.Response(arc, load, supports, EI);
                sag.Add(deflection is null
                    ? Enumerable.Repeat(0.0, run.Count).ToList()
                    : deflection.Select(d => d * 1000.0).ToList());
            }

            return (nodes, sag);
        }

        private static List<DiagnosticDto> Diagnostics(
            List<bool> standsOnGround,
            MouldFrameDto? frame,
            MouldColumnsDto? block,
            List<double> cableForce,
            List<double> barForce,
            List<double> columnForce,
            List<double> thrust,
            List<Vector3d> anchorForce,
            List<List<double>> barSag,
            double stiffness)
        {
            const string S = "Monitor";
            var d = new List<DiagnosticDto>
            {
                ResultDiagnostics.Entry(S, "monitor.counts", "info",
                    $"{cableForce.Count} infill cables, {barForce.Count} bar members, "
                        + $"{columnForce.Count} columns, {anchorForce.Count} anchors"
                        + (frame is null ? ", read at the solved state" : $", read at frame {frame.Phase}"),
                    cableForce.Count, unit: "cables",
                    context: ResultDiagnostics.Context(
                        ("bars", barForce.Count.ToString(CultureInfo.InvariantCulture)),
                        ("columns", columnForce.Count.ToString(CultureInfo.InvariantCulture)),
                        ("anchors", anchorForce.Count.ToString(CultureInfo.InvariantCulture)))),
            };

            if (cableForce.Count > 0)
            {
                int slack = cableForce.Count(f => f <= 1e-9);
                d.Add(ResultDiagnostics.Entry(S, "monitor.cable_tension", "info",
                    $"cable tension {cableForce.Min():0} to {cableForce.Max():0} N",
                    cableForce.Max(), unit: "N",
                    context: ResultDiagnostics.Context(("min", cableForce.Min().ToString("0", CultureInfo.InvariantCulture)))));
                d.Add(slack == 0
                    ? ResultDiagnostics.Entry(S, "monitor.slack_cables", "ok",
                        "no cable is slack: every one is still pulling", 0.0, unit: "cables")
                    : ResultDiagnostics.Entry(S, "monitor.slack_cables", "warning",
                        $"{slack} cables are SLACK. A slack cable holds nothing, so the "
                            + "surface between its neighbours is unsupported. Raise the "
                            + "prestress or move the bars closer.",
                        slack, unit: "cables"));
            }
            if (barForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.bar_force", "info",
                    $"bar axial force {barForce.Min():0} to {barForce.Max():0} N",
                    barForce.Max(), unit: "N"));
            }
            if (columnForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.column_force", "info",
                    $"column compression {columnForce.Min():0} to {columnForce.Max():0} N, "
                        + $"carrying {columnForce.Sum():0} N in total",
                    columnForce.Max(), unit: "N",
                    context: ResultDiagnostics.Context(("total", columnForce.Sum().ToString("0", CultureInfo.InvariantCulture)))));
                // Only the FEET push on the ground. A branch inside a tree leans
                // too, but its horizontal is balanced at the junction by its
                // siblings.
                double[] footThrust = thrust
                    .Where((_, index) => index < standsOnGround.Count && standsOnGround[index])
                    .ToArray();
                d.Add(footThrust.Length == 0
                    ? ResultDiagnostics.Entry(S, "monitor.thrust_into_ground", "info",
                        "no member reaches the ground in this state, so there is no "
                            + "foundation thrust to report.", 0.0, unit: "N")
                    : ResultDiagnostics.Entry(S, "monitor.thrust_into_ground", "info",
                        $"horizontal thrust at the {footThrust.Length} feet up to "
                            + $"{footThrust.Max():0} N, {footThrust.Sum():0} N summed. This "
                            + "is what the ground has to resist sideways, and it is the "
                            + "price of leaning the arms.",
                        footThrust.Max(), unit: "N",
                        context: ResultDiagnostics.Context(
                            ("feet", footThrust.Length.ToString(CultureInfo.InvariantCulture)),
                            ("sum", footThrust.Sum().ToString("0", CultureInfo.InvariantCulture)))));
            }
            else
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.no_columns", "info",
                    "no columns on this Result: wire Columns upstream to see what "
                        + "they carry."));
            }
            if (anchorForce.Count > 0)
            {
                double worst = anchorForce
                    .Select(a => Math.Sqrt((a.X * a.X) + (a.Y * a.Y)))
                    .DefaultIfEmpty(0.0)
                    .Max();
                d.Add(ResultDiagnostics.Entry(S, "monitor.anchor_horizontal", "info",
                    $"anchor pull up to {worst:0} N horizontally: the side ties hold "
                        + "the perimeter cables against exactly this.",
                    worst, unit: "N"));
            }
            if (frame is not null && frame.Time < 100.0 - 1.0e-9)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.intermediate_frame", "info",
                    "this is an intermediate frame, so the geometry is part way "
                        + "through the build while the forces are those of the "
                        + "finished state. Read it as where the structure is going.",
                    frame.Time, unit: "percent"));
            }

            double worstSag = barSag.SelectMany(b => b).Select(Math.Abs).DefaultIfEmpty(0.0).Max();
            if (barSag.Count == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.bar_sag_absent", "info",
                    "bar bending not reported: this Result carries no principal "
                        + "runs, so there is no bar to solve as a beam."));
            }
            else if (stiffness > 0.0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.bar_sag", "info",
                    $"bars bend up to {worstSag:0.##} mm between their supports, with "
                        + $"EI {stiffness:G4} N.m2. That is the demand to hold a build "
                        + "tolerance against; no allowable is assumed here.",
                    worstSag, unit: "mm",
                    context: ResultDiagnostics.Context(("EI", stiffness.ToString("G6", CultureInfo.InvariantCulture)))));
            }
            else
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.bar_sag_shape_only", "info",
                    "bar bending is reported as SHAPE ONLY, because EI was left at "
                        + "zero. It shows where the bar bends and in what proportion, "
                        + "and it is not millimetres. Give EI the section you mean to "
                        + "build to put a scale on it.",
                    worstSag));
            }
            d.Add(ResultDiagnostics.Entry(S, "monitor.demand_only", "info",
                "all of these are DEMANDS. Nothing here assumes a capacity, a stress "
                    + "limit or a tolerance; those are for the tests to establish."));
            return d;
        }
    }
}
