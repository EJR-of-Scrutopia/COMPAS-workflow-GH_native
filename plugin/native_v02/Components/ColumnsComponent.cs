#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Columns: every notch of every principal line gets a column head, the
    /// heads group into trees by Branching, and the trees reach the ground
    /// by Ground. Nothing is chosen by a beam search any more; the machine
    /// has a joint at every notch and this component says how the joints
    /// are held up.
    ///
    /// The Result is the form finder: the principal lines travel in it,
    /// resolved once by Pattern, and the load each notch hands its bar comes
    /// from the Result's own member forces. The ground is the level the
    /// anchors sit at.
    ///
    /// The engine is ColumnPlacement, pure arithmetic the harness measures.
    /// This class only reads the Result, builds the engine's inputs, writes
    /// the block and says what happened.
    /// </summary>
    public sealed class ColumnsComponent : NativeComponentBase
    {
        private static readonly ComponentValueListSpec[] ValueLists =
        {
            new(
                2,
                "Ground",
                new (string Label, string Value)[]
                {
                    ("0 · standalone", "0"),
                    ("1 · one central foot", "1"),
                    ("2 · two feet", "2"),
                    ("3 · three feet", "3"),
                    ("4 · four feet", "4"),
                    ("Auto", "-1")
                },
                "0")
        };

        private protected override IReadOnlyList<ComponentValueListSpec>
            SuggestedValueLists => ValueLists;

        public ColumnsComponent()
            : base(
                "Columns",
                "Columns",
                "Hold every notch of every principal line with a column head, "
                    + "grouped into trees by Branching and footed by Ground. "
                    + "The loads come from the Result's own member forces.",
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

        /// <summary>
        /// Blue for the columns: the one thing on screen that is not part of
        /// the net. Green already means a support, red a notched bar.
        /// </summary>
        private static readonly Color ColumnColour =
            Color.FromArgb(40, 85, 175);

        private Mesh? _previewMesh;
        private readonly List<Line> _previewCables = new();
        private readonly List<Line> _previewColumns = new();
        private readonly List<Point3d> _previewSupports = new();
        private BoundingBox _clippingBox = BoundingBox.Empty;

        public override bool IsPreviewCapable => true;

        public override BoundingBox ClippingBox => _clippingBox;

        protected override void BeforeSolveInstance()
        {
            base.BeforeSolveInstance();
            _previewMesh = null;
            _previewCables.Clear();
            _previewColumns.Clear();
            _previewSupports.Clear();
            _clippingBox = BoundingBox.Empty;
        }

        /// <summary>
        /// Draw the finished mould the way TNA Solve and Animate draw theirs,
        /// same shaded material, wire colour and support points, so the three
        /// read as one object seen at three moments. On top of that goes the
        /// one thing only this component knows, the columns. The bars are
        /// Pattern's to draw. The geometry outputs stay hidden so nothing
        /// draws twice.
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
                foreach (Line cable in _previewCables)
                    args.Display.DrawLine(cable, Color.FromArgb(95, 95, 100));
            }
            foreach (Line column in _previewColumns)
                args.Display.DrawLine(column, ColumnColour, 3);
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
                "Solved FD or TNA result. Used as the form finder: its geometry "
                    + "gives the notches and its member forces give the load "
                    + "each one hands the bar.",
                GH_ParamAccess.item);
            parameters.AddIntegerParameter(
                "Branching",
                "B",
                "Notches per tree: 1 stands a column under every notch, 2 and "
                    + "3 group neighbouring notches into trees of that size, "
                    + "mirrored about the middle of each span with the "
                    + "remainder at the anchors. Every notch is held.",
                GH_ParamAccess.item,
                1);
            parameters.AddIntegerParameter(
                "Ground",
                "G",
                "How the trees reach the ground. 0 stands each tree on its "
                    + "own foot on the line of the force it carries; 1 to 4 "
                    + "gather each span's trees onto that many feet about its "
                    + "midpoint, and a level that would lean a trunk past 60 "
                    + "degrees, stand it more than 30 degrees off its force, "
                    + "or run a member into another or into the net is "
                    + "refused and the next lower one tried. -1 is Auto: every "
                    + "level is tried and the shortest load path is built.",
                GH_ParamAccess.item,
                0);
            parameters[1].Optional = true;
            parameters[2].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "The Result this component was given, with the built columns "
                    + "written into its Mould block: every tree node, every "
                    + "member with the force it carries, which nodes are heads, "
                    + "forks and feet, and which net vertex each head stands "
                    + "on. Read the geometry back with Deconstruct (Columns, "
                    + "Heads, Feet), the numbers with Monitor, and the words "
                    + "with Diagnose. Wire it into Animate to raise the "
                    + "columns with the net.",
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

            int branching = 1;
            int ground = 0;
            data.GetData(1, ref branching);
            data.GetData(2, ref ground);
            branching = Math.Min(Math.Max(branching, 1), ColumnPlacement.MaxBranching);
            if (ground > ColumnPlacement.MaxGround)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"Ground {ground} is above the {ColumnPlacement.MaxGround} feet "
                        + "per span this machine places; clamped. An old Type "
                        + "value list goes to 6; place the Ground list from the "
                        + "component menu.");
                ground = ColumnPlacement.MaxGround;
            }
            if (ground < -1)
                ground = -1;

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

                (int, int)[] edges = MouldGeometry.ValidEdges(
                    equilibrium, n, out int[] edgeSource);
                var anchors = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));
                double groundLevel = MouldGeometry.GroundLevel(nodes, anchors);
                List<List<int>> bars = MouldGeometry.PrincipalRuns(equilibrium, n);

                int overlapping = 0;
                for (int a = 0; a < bars.Count; a++)
                {
                    for (int b = a + 1; b < bars.Count; b++)
                    {
                        var left = new HashSet<int>(bars[a]);
                        int shared = bars[b].Count(left.Contains);
                        if (2 * shared <= Math.Min(bars[a].Count, bars[b].Count))
                            continue;
                        overlapping = Math.Max(overlapping, shared);
                        AddRuntimeMessage(
                            GH_RuntimeMessageLevel.Warning,
                            $"Principal lines {a} and {b} share {shared} "
                                + "notches, so they are one bar traced twice. "
                                + "Check the curves drawn into Pattern.");
                        a = bars.Count;
                        break;
                    }
                }

                var barShape = new List<string>();
                foreach (List<int> bar in bars)
                {
                    bool startTied = bar.Count > 0 && anchors.Contains(bar[0]);
                    bool endTied = bar.Count > 0 && anchors.Contains(bar[bar.Count - 1]);
                    string ends = startTied && endTied
                        ? "anchored at both ends"
                        : startTied || endTied
                            ? "ANCHORED AT ONE END ONLY, so it is half a line"
                            : "NOT ANCHORED AT EITHER END";
                    barShape.Add($"{bar.Count} notches, {ends}");
                }

                if (bars.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines. Draw Principal "
                            + "Lines into Pattern upstream; nothing derives them.");
                    data.SetData(0, new ResultGoo(ResultDiagnostics.Replace(
                        result, "Columns", new[]
                        {
                            ResultDiagnostics.Entry("Columns", "columns.no_principal_runs", "error",
                                "no principal runs on this Result, so there is nothing to "
                                    + "stand under. Draw Principal Lines into Pattern upstream."),
                        })));
                    return;
                }

                // What the net hands each node, from the solve's own member
                // forces, indexed through edgeSource because the filtered
                // edge list no longer matches the Result's arrays.
                var edgeForce = new double[edges.Length];
                for (int e = 0; e < edges.Length; e++)
                {
                    int src = e < edgeSource.Length ? edgeSource[e] : e;
                    edgeForce[e] = src < equilibrium.MemberForces.Count
                        ? equilibrium.MemberForces[src]
                        : 0.0;
                }
                var incident = new List<(int Other, double Force)>[n];
                for (int i = 0; i < n; i++)
                    incident[i] = new List<(int, double)>();
                for (int e = 0; e < edges.Length; e++)
                {
                    incident[edges[e].Item1].Add((edges[e].Item2, edgeForce[e]));
                    incident[edges[e].Item2].Add((edges[e].Item1, edgeForce[e]));
                }

                double alongToAnchors = 0.0;
                double acrossToColumns = 0.0;
                var across = new Vector3d[bars.Count][];
                for (int b = 0; b < bars.Count; b++)
                {
                    Vector3d[] pull = MouldGeometry.BarLoads(bars[b], nodes, incident);
                    Vector3d[] transverse = MouldGeometry.BarTransverse(bars[b], nodes, pull);
                    for (int k = 0; k < bars[b].Count; k++)
                    {
                        alongToAnchors += (pull[k] - transverse[k]).Length;
                        acrossToColumns += transverse[k].Length;
                    }
                    across[b] = transverse;
                }

                // The boundary loops, for the free-rim test. Computed the way
                // Animate computes its Perimeter Nodes: naked mesh edges when
                // the thrust mesh exists, a degree heuristic otherwise, grouped
                // over the union of solved and pattern edges.
                Mesh? thrust = MouldGeometry.ThrustMeshFromResult(result, out int[] meshToNode);
                List<int>[] neighbours = MouldGeometry.BuildAdjacency(n, edges);
                int[] perimeterIds = MouldGeometry.PerimeterNodes(thrust, meshToNode, neighbours, n);
                List<int>[] grouping = MouldGeometry.GroupingAdjacency(result, edges, n);
                List<List<int>> loops = MouldGeometry.ConnectedGroups(perimeterIds, grouping);

                double median = MouldGeometry.MedianEdgeLength(nodes, edges);
                ColumnPlacement.Placement placement = ColumnPlacement.Place(
                    nodes,
                    bars.Select(b => b.ToArray()).ToArray(),
                    anchors.ToArray(),
                    across,
                    loops.Select(l => l.ToArray()).ToArray(),
                    edges,
                    groundLevel,
                    median,
                    branching,
                    ground);
                ColumnPlacement.Level built = placement.Built;

                var members = new List<Line>(built.Members.Count);
                foreach ((int lower, int upper) in built.Members)
                    members.Add(new Line(built.Nodes[lower], built.Nodes[upper]));
                var force = new List<double>(built.Axial);
                var angle = members
                    .Select(m => MouldGeometry.LeanFromVertical(m.From, m.To))
                    .ToList();

                _previewMesh = thrust;
                _previewCables.Clear();
                _previewCables.AddRange(edges.Select(
                    e => new Line(nodes[e.Item1], nodes[e.Item2])));
                _previewColumns.Clear();
                _previewColumns.AddRange(members);
                _previewSupports.Clear();
                _previewSupports.AddRange(
                    anchors.OrderBy(i => i).Select(i => nodes[i]));
                _clippingBox = TnaWorkflowPreview.Box(
                    _previewCables.Concat(_previewColumns),
                    _previewSupports);

                if (placement.GroundPlaced != Math.Max(ground, 0) && ground >= 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        $"Ground {ground} was refused and Ground "
                            + $"{placement.GroundPlaced} built instead; Diagnose "
                            + "says which rule refused it.");
                }
                if (!built.Feasible && built.Ground == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        $"{built.Collisions} member(s) collide even standing "
                            + "alone; placed anyway so the chain keeps running.");
                }

                Point3d[] netNodes = nodes.ToArray();
                double weld = 1.0e-6 * Math.Max(
                    new BoundingBox(netNodes).Diagonal.Length, 1.0);
                MouldColumnsDto block = MouldGeometry.ColumnsBlock(
                    members,
                    force,
                    netNodes,
                    weld,
                    branching: branching,
                    groundAsked: ground,
                    groundPlaced: placement.GroundPlaced,
                    forkFraction: ColumnPlacement.ForkFraction,
                    forksRaised: 0);
                ResultDto output = result with
                {
                    Mould = new MouldDto
                    {
                        Ground = groundLevel,
                        Columns = block,
                        Frame = null,
                    },
                };
                output = ResultDiagnostics.Replace(output, "Columns", Diagnostics(
                    bars, placement, built, force, angle, branching, ground,
                    groundLevel, alongToAnchors, acrossToColumns, overlapping,
                    barShape));
                data.SetData(0, new ResultGoo(output));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        private static string Inv(double value, string format) =>
            value.ToString(format, CultureInfo.InvariantCulture);

        private static List<DiagnosticDto> Diagnostics(
            List<List<int>> bars,
            ColumnPlacement.Placement placement,
            ColumnPlacement.Level built,
            List<double> force,
            List<double> angle,
            int branching,
            int groundAsked,
            double groundLevel,
            double alongToAnchors,
            double acrossToColumns,
            int overlapping,
            List<string> barShape)
        {
            const string S = "Columns";
            double cap = MouldGeometry.MaxLeanDegrees;
            var d = new List<DiagnosticDto>
            {
                overlapping > 0
                    ? ResultDiagnostics.Entry(S, "columns.overlap", "warning",
                        $"two principal lines share {overlapping} notches, so ONE "
                            + "bar is being traced twice and given two full sets of "
                            + "columns.",
                        overlapping, unit: "notches")
                    : ResultDiagnostics.Entry(S, "columns.overlap", "ok",
                        "each principal line is distinct", 0.0, unit: "notches"),
            };

            for (int i = 0; i < barShape.Count; i++)
            {
                bool halfLine =
                    barShape[i].Contains("ONE END", StringComparison.Ordinal) ||
                    barShape[i].Contains("NOT ANCHORED", StringComparison.Ordinal);
                d.Add(ResultDiagnostics.Entry(S, "columns.bar_shape",
                    halfLine ? "warning" : "info",
                    $"bar {i}: {barShape[i]}",
                    context: ResultDiagnostics.Context(("bar", i.ToString(CultureInfo.InvariantCulture)))));
            }

            for (int b = 0; b < bars.Count; b++)
            {
                var spans = placement.Spans.Where(s => s.Bar == b).ToList();
                string cuts = string.Join(", ", spans.Select(s =>
                    $"{s.FirstKind} to {s.LastKind}, {s.Free.Count} notches"));
                d.Add(ResultDiagnostics.Entry(S, "columns.spans", "info",
                    $"bar {b}: {spans.Count} span(s): {cuts}",
                    spans.Count, unit: "spans",
                    context: ResultDiagnostics.Context(("bar", b.ToString(CultureInfo.InvariantCulture)))));
            }

            int singles = placement.Trees.Count(t => t.Nodes.Length == 1);
            int smaller = placement.Trees.Count(t => !t.Ring && t.Nodes.Length > 1 && t.Nodes.Length < branching);
            d.Add(ResultDiagnostics.Entry(S, "columns.grouping", "info",
                $"Branching {branching}: {placement.Trees.Count} trees hold "
                    + $"{placement.Trees.Sum(t => t.Nodes.Length)} notches, "
                    + $"{singles} single columns, {smaller} remainder trees "
                    + "smaller than Branching at the anchors; every notch is held.",
                placement.Trees.Count, unit: "trees",
                context: ResultDiagnostics.Context(
                    ("branching", branching.ToString(CultureInfo.InvariantCulture)),
                    ("singles", singles.ToString(CultureInfo.InvariantCulture)),
                    ("remainder", smaller.ToString(CultureInfo.InvariantCulture)))));

            if (placement.RingTree is ColumnPlacement.Tree ring && ring.FixedFoot is Point3d rf)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.ring_tree", "info",
                    $"a ring tree holds the {ring.Nodes.Length} rim notches of a "
                        + "free central rim from one foot at the plan intersection "
                        + $"of the bars' end tangents, ({rf.X:0.###}, {rf.Y:0.###}).",
                    ring.Nodes.Length, unit: "notches",
                    context: ResultDiagnostics.Context(
                        ("x", Inv(rf.X, "0.###")), ("y", Inv(rf.Y, "0.###")))));
            }

            string asked = groundAsked < 0 ? "Auto" : groundAsked.ToString(CultureInfo.InvariantCulture);
            var refused = placement.Tried.Where(t => !t.Feasible && t.Ground > 0)
                .Select(t => $"level {t.Ground} refused on {t.Rule} at {t.Value:0.##}")
                .ToList();
            bool fellBack = groundAsked >= 0 && placement.GroundPlaced < groundAsked;
            d.Add(ResultDiagnostics.Entry(S, "columns.ground",
                fellBack ? "warning" : "info",
                $"Ground asked {asked}, placed {placement.GroundPlaced}"
                    + (refused.Count > 0 ? "; " + string.Join("; ", refused) : "")
                    + (placement.GroundPlaced == 0
                        ? ". Every tree stands on its own foot on the line of its force."
                        : $". Each span's trees gather onto {placement.GroundPlaced} feet about its midpoint."),
                placement.GroundPlaced, unit: "feet per span",
                context: ResultDiagnostics.Context(
                    ("asked", groundAsked.ToString(CultureInfo.InvariantCulture)),
                    ("placed", placement.GroundPlaced.ToString(CultureInfo.InvariantCulture)),
                    ("refused", refused.Count.ToString(CultureInfo.InvariantCulture)))));

            var scored = placement.Tried.Where(t => t.Feasible)
                .Select(t => (t.Ground.ToString(CultureInfo.InvariantCulture), Inv(t.LoadPath, "0")))
                .ToArray();
            d.Add(ResultDiagnostics.Entry(S, "columns.load_path", "info",
                $"load path {built.LoadPath:0} N x model units, the sum over "
                    + "members of force times length"
                    + (groundAsked < 0 ? $"; feasible levels scored: {string.Join(", ", scored.Select(s => $"{s.Item1}={s.Item2}"))}" : ""),
                built.LoadPath, unit: "N x model units",
                context: ResultDiagnostics.Context(scored)));

            if (built.FeetMerged > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.feet_merged", "info",
                    $"{built.FeetMerged} feet closer than the clearance were "
                        + "merged into one, at their plan centre.",
                    built.FeetMerged, unit: "feet"));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.branch_off_thrust", "info",
                $"branches stand up to {built.WorstBranchOff:0.#} degrees off the "
                    + "pull at their notch; a fork can only be in one place, and "
                    + "what is left is bending for the joint to take.",
                built.WorstBranchOff, unit: "degrees"));
            if (!built.Feasible && built.Ground == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.collision", "warning",
                    $"{built.Collisions} member(s) come within the clearance of "
                        + "another member or of the net even standing alone; placed "
                        + "anyway. Draw the principal lines further apart or lower "
                        + "Branching.",
                    built.Collisions, unit: "members"));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.head_load_total", "info",
                $"the heads carry {placement.Trees.Sum(t => t.Load.Sum()):0} N between "
                    + $"them, ground read as {groundLevel:0.###}, the level the anchors sit at",
                placement.Trees.Sum(t => t.Load.Sum()), unit: "N",
                context: ResultDiagnostics.Context(("ground", Inv(groundLevel, "0.###")))));
            d.Add(ResultDiagnostics.Entry(S, "columns.load_split", "info",
                $"of the net's pull on the bars, {alongToAnchors:0} N runs ALONG "
                    + "them to the anchors, which are this machine's buttresses. "
                    + $"The {acrossToColumns:0} N ACROSS them is the columns' to "
                    + "take, and it sets their lean.",
                acrossToColumns, unit: "N",
                context: ResultDiagnostics.Context(("along_to_anchors", Inv(alongToAnchors, "0")))));
            d.Add(ResultDiagnostics.Entry(S, "columns.principal_source", "info",
                "principal lines came from the contract, resolved upstream by "
                    + "Pattern from the curves drawn into it; nothing was "
                    + "re-matched here.",
                bars.Count, unit: "bars"));
            if (built.PlumbTrees > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.plumb_fallback",
                    built.PlumbTrees >= placement.Trees.Count ? "warning" : "info",
                    $"{built.PlumbTrees} trees stand PLUMB because the net pulls "
                        + "their notches down onto the column rather than off it. "
                        + "If that is ALL of them, the aiming is not working.",
                    built.PlumbTrees, unit: "trees"));
            }
            var loads = placement.Trees.SelectMany(t => t.Load).ToList();
            if (loads.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.head_load", "info",
                    $"head load {loads.Min():0} to {loads.Max():0} N",
                    loads.Max(), unit: "N",
                    context: ResultDiagnostics.Context(("min", Inv(loads.Min(), "0")))));
            }
            if (force.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.force_max", "info",
                    $"axial force up to {force.Max():0} N", force.Max(), unit: "N"));
            }
            if (angle.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.lean", "info",
                    $"lean {angle.Min():0.#} to {angle.Max():0.#} degrees from vertical",
                    angle.Max(), cap, "degrees",
                    ResultDiagnostics.Context(("min", Inv(angle.Min(), "0.#")))));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.demand_only", "info",
                "no capacity is assumed anywhere here: Force is the demand, to "
                    + "size and test against, not a pass or a fail."));
            return d;
        }
    }
}
