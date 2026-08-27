#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Serialization;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Contracts
{
    /// <summary>
    /// One frame of the mould, complete enough to work the forces out from:
    /// where every node is, what every member carries, which members are bars
    /// and which are infill cables, which nodes are notches, anchors and
    /// perimeter, and where the columns stand and what they take.
    ///
    /// Animate and Column Finder each emit this so that Stress Analysis can be
    /// a separate component rather than every component growing its own tail of
    /// force outputs. Animate's state carries no columns; Column Finder's does.
    ///
    /// It is a snapshot, not a solve. Member forces come from the Result that
    /// produced it, so they belong to the FINAL state; an intermediate frame
    /// has the geometry of that frame and the forces of the finished one, which
    /// is honest only because the mould is meant to reach that state. Stress
    /// Analysis says so rather than pretending otherwise.
    /// </summary>
    public sealed record MouldStateDto : ContractDto
    {
        public MouldStateDto()
            : base(ContractKinds.MouldState)
        {
        }

        [JsonIgnore]
        public override string ExpectedKind => ContractKinds.MouldState;

        /// <summary>Which frame this is, in words, for the report.</summary>
        public string Stage { get; init; } = "final";

        public double Ground { get; init; }

        public IReadOnlyList<Point3Dto> Vertices { get; init; } =
            Array.Empty<Point3Dto>();

        public IReadOnlyList<EdgeDto> Edges { get; init; } =
            Array.Empty<EdgeDto>();

        /// <summary>Axial force per edge, N. Positive is tension.</summary>
        public IReadOnlyList<double> MemberForce { get; init; } =
            Array.Empty<double>();

        /// <summary>Force density per edge, force over length.</summary>
        public IReadOnlyList<double> ForceDensity { get; init; } =
            Array.Empty<double>();

        /// <summary>"bar" for a notched-bar member, "infill" for a cable.</summary>
        public IReadOnlyList<string> EdgeKind { get; init; } =
            Array.Empty<string>();

        public IReadOnlyList<int> PrincipalNodes { get; init; } =
            Array.Empty<int>();

        /// <summary>
        /// The notches of each principal line, in order along that bar.
        ///
        /// Carried rather than rebuilt. A bar could be recovered downstream by
        /// walking the "bar" edges, but two bars that CROSS share a notch, and
        /// a walk cannot tell which of the two it should carry on down. The
        /// runs are known exactly where they are made, so they travel.
        /// </summary>
        public IReadOnlyList<IReadOnlyList<int>> PrincipalRuns { get; init; } =
            Array.Empty<IReadOnlyList<int>>();

        public IReadOnlyList<int> AnchorNodes { get; init; } =
            Array.Empty<int>();

        public IReadOnlyList<int> PerimeterNodes { get; init; } =
            Array.Empty<int>();

        public IReadOnlyList<NodalVectorDto> Reactions { get; init; } =
            Array.Empty<NodalVectorDto>();

        public IReadOnlyList<Point3Dto> ColumnFoot { get; init; } =
            Array.Empty<Point3Dto>();

        public IReadOnlyList<Point3Dto> ColumnHead { get; init; } =
            Array.Empty<Point3Dto>();

        /// <summary>Axial force in each column, N. Compression is positive.</summary>
        public IReadOnlyList<double> ColumnForce { get; init; } =
            Array.Empty<double>();

        protected override void ValidatePayload(List<string> errors)
        {
            int e = Edges.Count;
            if (MemberForce.Count != 0 && MemberForce.Count != e)
                errors.Add("memberForce must be empty or one value per edge.");
            if (ForceDensity.Count != 0 && ForceDensity.Count != e)
                errors.Add("forceDensity must be empty or one value per edge.");
            if (EdgeKind.Count != 0 && EdgeKind.Count != e)
                errors.Add("edgeKind must be empty or one label per edge.");
            if (ColumnFoot.Count != ColumnHead.Count)
                errors.Add("columnFoot and columnHead must be the same length.");
            if (ColumnForce.Count != 0 && ColumnForce.Count != ColumnFoot.Count)
                errors.Add("columnForce must be empty or one value per column.");
        }
    }

    public sealed class MouldStateGoo : ContractGoo<MouldStateDto>
    {
        public MouldStateGoo()
        {
        }

        public MouldStateGoo(MouldStateDto value)
            : base(value)
        {
        }

        protected override string ExpectedKind => ContractKinds.MouldState;

        public override string TypeName => "Ananke Mould State";

        public override string TypeDescription =>
            "One frame of the mould: geometry, member forces, node roles and "
            + "columns, bundled for Stress Analysis.";

        protected override ContractGoo<MouldStateDto> Create(MouldStateDto? value) =>
            value is null ? new MouldStateGoo() : new MouldStateGoo(value);

        protected override string Format(MouldStateDto value) =>
            $"Mould State · {value.Stage} · {value.Vertices.Count} nodes · "
            + $"{value.Edges.Count} members · {value.ColumnFoot.Count} columns";
    }

    public sealed class MouldStateParam : ContractParam<MouldStateGoo>
    {
        public MouldStateParam()
            : base(
                "Mould State",
                "S",
                "One frame of the mould, bundled for Stress Analysis.")
        {
        }

        public override Guid ComponentGuid =>
            new("7a3d90e5-24bc-4f18-9f6a-1c85d7b3e402");
    }
}

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Stress Analysis: decode a mould State into the forces the structure is
    /// actually under, split by what carries them.
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
                "Stress Analysis",
                "SA",
                "Decode a mould State into the forces on the cables, the bars, "
                    + "the columns and the anchors. Demands only: no capacity, "
                    + "stress limit or tolerance is assumed.",
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
                new MouldStateParam(),
                "State",
                "S",
                "A frame from Animate or Column Finder. Column Finder's state "
                    + "carries the columns; Animate's carries only the net.",
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
                "The columns, if the state came from Column Finder. Column "
                    + "Force and Thrust align with this.",
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
                    + "and the Report sums those alone. A branch's horizontal "
                    + "is balanced at its junction by its siblings.",
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
            parameters.AddTextParameter(
                "Report",
                "Out",
                "The summary: worst tension, worst compression, any slack "
                    + "cable, and how the load divides between the columns and "
                    + "the anchors.",
                GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            MouldStateGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not MouldStateDto state)
            {
                return;
            }

            double stiffness = 0.0;
            data.GetData(1, ref stiffness);

            try
            {
                IReadOnlyList<string> errors = state.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                Point3d[] v = state.Vertices
                    .Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray();

                var cables = new List<Line>();
                var cableForce = new List<double>();
                var bars = new List<Line>();
                var barForce = new List<double>();

                for (int e = 0; e < state.Edges.Count; e++)
                {
                    EdgeDto edge = state.Edges[e];
                    if (edge.U < 0 || edge.U >= v.Length ||
                        edge.V < 0 || edge.V >= v.Length)
                    {
                        continue;
                    }
                    var line = new Line(v[edge.U], v[edge.V]);
                    double force = e < state.MemberForce.Count
                        ? state.MemberForce[e]
                        : 0.0;
                    bool isBar = e < state.EdgeKind.Count &&
                        string.Equals(state.EdgeKind[e], "bar",
                            StringComparison.OrdinalIgnoreCase);
                    if (isBar)
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
                var standsOnGround = new List<bool>();
                // A member counts as a foot when its lower end is on the floor.
                // Scaled to the model so the test means the same thing in
                // millimetres as in metres.
                double reach = state.Vertices.Count == 0
                    ? 1.0
                    : Math.Max(
                        state.Vertices.Max(v => v.Z) -
                        state.Vertices.Min(v => v.Z),
                        1.0e-9);
                double onGround = (1.0e-6 * reach) + 1.0e-9;
                for (int c = 0; c < state.ColumnFoot.Count; c++)
                {
                    Point3Dto a = state.ColumnFoot[c];
                    Point3Dto b = state.ColumnHead[c];
                    var line = new Line(
                        new Point3d(a.X, a.Y, a.Z), new Point3d(b.X, b.Y, b.Z));
                    columns.Add(line);
                    double force = c < state.ColumnForce.Count
                        ? state.ColumnForce[c]
                        : 0.0;
                    columnForce.Add(force);

                    // The horizontal share of a leaning column's axial load.
                    Vector3d d = line.To - line.From;
                    double length = d.Length;
                    double sin = length > 1e-12
                        ? Math.Sqrt((d.X * d.X) + (d.Y * d.Y)) / length
                        : 0.0;
                    thrust.Add(force * sin);
                    standsOnGround.Add(
                        Math.Abs(a.Z - state.Ground) <= onGround);
                }

                var anchorPoints = new List<Point3d>();
                var anchorForce = new List<Vector3d>();
                var reactionByNode = new Dictionary<int, Vector3d>();
                foreach (NodalVectorDto r in state.Reactions)
                {
                    reactionByNode[r.NodeId] =
                        new Vector3d(r.Vector.X, r.Vector.Y, r.Vector.Z);
                }
                foreach (int id in state.AnchorNodes)
                {
                    if (id < 0 || id >= v.Length)
                        continue;
                    anchorPoints.Add(v[id]);
                    anchorForce.Add(
                        reactionByNode.TryGetValue(id, out Vector3d vec)
                            ? vec
                            : Vector3d.Zero);
                }

                data.SetDataList(0, cables);
                data.SetDataList(1, cableForce);
                data.SetDataList(2, bars);
                data.SetDataList(3, barForce);
                data.SetDataList(4, columns);
                data.SetDataList(5, columnForce);
                data.SetDataList(6, thrust);
                data.SetDataList(7, anchorPoints);
                (List<List<Point3d>> barNodes, List<List<double>> barSag) =
                    BarBending(state, v, stiffness);
                data.SetDataTree(9, OutputTree.Points(barNodes));
                data.SetDataTree(10, OutputTree.Numbers(barSag));
                data.SetData(11, ReportFor(standsOnGround,
                    state, cableForce, barForce, columnForce, thrust,
                    anchorForce, barSag, stiffness));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        /// <summary>
        /// How far each bar bends away from straight, in millimetres.
        ///
        /// EI IS ASKED FOR HERE AND NOWHERE ELSE, and that placing is the
        /// point. Where the arms go is chosen by comparing one arrangement
        /// against another, and stiffness is a common factor in that
        /// comparison, so it cancels: the same arms come out whatever EI is.
        /// Putting the number upstream would therefore have looked like a
        /// tuning knob on the placement while doing nothing to it, and would
        /// have put a tolerance next to a decision that cannot honour one.
        ///
        /// Downstream it is exactly what is missing. The placement knows the
        /// SHAPE of the bending; only EI turns that shape into millimetres,
        /// and millimetres are what a build tolerance is written in.
        ///
        /// The bar is solved the same way it was placed: an Euler-Bernoulli
        /// beam on point supports, held wherever a column head or an anchor
        /// meets it. Held at the same places, loaded the same way, so the sag
        /// reported here is the sag the arms were chosen to minimise, and not
        /// a second opinion from a different model.
        ///
        /// With EI at zero there is no scale to report, so the deflected shape
        /// is returned in the solver's own units with EI of one. It still
        /// shows WHERE the bar bends and in what proportion; it is simply not
        /// millimetres, and the Report says so.
        /// </summary>
        private static (List<List<Point3d>>, List<List<double>>) BarBending(
            MouldStateDto state,
            Point3d[] v,
            double stiffness)
        {
            var nodes = new List<List<Point3d>>();
            var sag = new List<List<double>>();
            if (state.PrincipalRuns.Count == 0)
                return (nodes, sag);

            double EI = stiffness > 0.0 ? stiffness : 1.0;

            // Every member on every notch, so the load across a bar can be
            // read the way Column Finder read it when it placed the arms.
            var incident = new List<(int Other, double Force)>[v.Length];
            for (int i = 0; i < v.Length; i++)
                incident[i] = new List<(int, double)>();
            for (int e = 0; e < state.Edges.Count; e++)
            {
                EdgeDto edge = state.Edges[e];
                if (edge.U < 0 || edge.U >= v.Length ||
                    edge.V < 0 || edge.V >= v.Length)
                {
                    continue;
                }
                double force = e < state.MemberForce.Count
                    ? state.MemberForce[e] : 0.0;
                incident[edge.U].Add((edge.V, force));
                incident[edge.V].Add((edge.U, force));
            }

            // A notch is HELD where a column head reaches it, or where it is
            // itself an anchor. Heads arrive as points rather than indices, so
            // they are matched in plan, which is how they were placed.
            var held = new HashSet<int>(
                state.AnchorNodes.Where(i => i >= 0 && i < v.Length));
            foreach (Point3Dto head in state.ColumnHead)
            {
                int at = MouldGeometry.NearestNodeInPlan(
                    new Point3d(head.X, head.Y, head.Z), v);
                if (at >= 0)
                    held.Add(at);
            }

            foreach (IReadOnlyList<int> raw in state.PrincipalRuns)
            {
                List<int> run = raw
                    .Where(i => i >= 0 && i < v.Length)
                    .ToList();
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

                // Under two supports the bar is a mechanism, not a beam. Report
                // nothing rather than an arbitrary number.
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

        private static string ReportFor(
            List<bool> standsOnGround,
            MouldStateDto state,
            List<double> cableForce,
            List<double> barForce,
            List<double> columnForce,
            List<double> thrust,
            List<Vector3d> anchorForce,
            List<List<double>> barSag,
            double stiffness)
        {
            var lines = new List<string>
            {
                $"state: {state.Stage}",
                $"{cableForce.Count} infill cables, {barForce.Count} bar "
                    + $"members, {columnForce.Count} columns, "
                    + $"{anchorForce.Count} anchors",
                string.Empty,
            };

            if (cableForce.Count > 0)
            {
                int slack = cableForce.Count(f => f <= 1e-9);
                lines.Add(
                    $"cable tension {cableForce.Min():0} to {cableForce.Max():0} N");
                lines.Add(slack == 0
                    ? "no cable is slack: every one is still pulling"
                    : $"WARNING: {slack} cables are SLACK. A slack cable holds "
                        + "nothing, so the surface between its neighbours is "
                        + "unsupported. Raise the prestress or move the bars "
                        + "closer.");
            }
            if (barForce.Count > 0)
            {
                lines.Add(
                    $"bar axial force {barForce.Min():0} to {barForce.Max():0} N");
            }
            if (columnForce.Count > 0)
            {
                lines.Add(
                    $"column compression {columnForce.Min():0} to "
                        + $"{columnForce.Max():0} N, carrying "
                        + $"{columnForce.Sum():0} N in total");
                // Only the FEET push on the ground. A branch inside a tree
                // leans too, but its horizontal is balanced at the junction by
                // its siblings, which is precisely what the junctions are now
                // placed to do. Summing every member's horizontal counted that
                // cancelled force as load on the foundations.
                double[] footThrust = thrust
                    .Where((_, index) => index < standsOnGround.Count &&
                        standsOnGround[index])
                    .ToArray();
                lines.Add(footThrust.Length == 0
                    ? "no member reaches the ground in this state, so there is "
                        + "no foundation thrust to report."
                    : $"horizontal thrust at the {footThrust.Length} feet up to "
                        + $"{footThrust.Max():0} N, {footThrust.Sum():0} N "
                        + "summed. This is what the ground has to resist "
                        + "sideways, and it is the price of leaning the arms. "
                        + "Branches above a foot lean too, but their horizontal "
                        + "is balanced at the junction, not by the foundation.");
            }
            else
            {
                lines.Add(
                    "no columns in this state: it came from Animate, which "
                        + "carries only the net. Use Column Finder's state for "
                        + "the columns.");
            }
            if (anchorForce.Count > 0)
            {
                double worst = anchorForce
                    .Select(a => Math.Sqrt((a.X * a.X) + (a.Y * a.Y)))
                    .DefaultIfEmpty(0.0)
                    .Max();
                lines.Add(
                    $"anchor pull up to {worst:0} N horizontally: the side ties "
                        + "hold the perimeter cables against exactly this.");
            }

            lines.Add(string.Empty);
            lines.Add(
                "all of these are DEMANDS. Nothing here assumes a capacity, a "
                    + "stress limit or a tolerance; those are for the tests to "
                    + "establish.");
            if (!string.Equals(state.Stage, "final", StringComparison.OrdinalIgnoreCase))
            {
                lines.Add(
                    "note: this is an intermediate frame, so the geometry is "
                        + "part way through the build while the forces are "
                        + "those of the finished state. Read it as where the "
                        + "structure is going, not as the load at this instant.");
            }
            double worstSag = barSag
                .SelectMany(b => b)
                .Select(Math.Abs)
                .DefaultIfEmpty(0.0)
                .Max();
            lines.Add(string.Empty);
            if (barSag.Count == 0)
            {
                lines.Add(
                    "bar bending not reported: this state carries no principal "
                        + "runs, so there is no bar to solve as a beam.");
            }
            else if (stiffness > 0.0)
            {
                lines.Add(
                    $"bars bend up to {worstSag:0.##} mm between their supports, "
                        + $"with EI {stiffness:G4} N.m2. That is the demand to "
                        + "hold a build tolerance against; no allowable is "
                        + "assumed here.");
            }
            else
            {
                lines.Add(
                    "bar bending is reported as SHAPE ONLY, because EI was "
                        + "left at zero. It shows where the bar bends and in "
                        + "what proportion, and it is not millimetres. Give EI "
                        + "the section you mean to build to put a scale on it.");
            }

            return string.Join(Environment.NewLine, lines);
        }
    }
}
