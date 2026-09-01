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
    /// heads group into trees by Branching, and the trees meet the ground by
    /// Type. Nothing is chosen by a beam search any more; the machine has a
    /// joint at every notch and this component says how the joints are held
    /// up.
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
                "Type",
                new (string Label, string Value)[]
                {
                    ("0 · own feet", "0"),
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
                    + "grouped into trees by Branching and footed by Type. "
                    + "The loads come from the Result's own member forces, "
                    + "mirrored about each span's midpoint before a foot is placed.",
                ComponentCategories.Mould,
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
                "Type",
                "T",
                "How the trees meet the ground. 0 stands each tree on its own "
                    + "foot on the line of the force it carries; 1 to 4 gather "
                    + "each span's trees onto that many mirrored feet in bands "
                    + "about the span's midpoint, and a trunk that would lean "
                    + "past 60 degrees to its shared foot steps back onto its "
                    + "own foot instead of the level being refused; -1 is "
                    + "Auto, which builds every level and places the shortest "
                    + "load path among those whose members do not collide. "
                    + "The feet are mirrored about each span's midpoint and "
                    + "shared across every span that holds the same NUMBER of "
                    + "notches and whose chord is within a tenth of its length, "
                    + "so the principal lines agree with one another. A span "
                    + "whose free notches are not symmetric about its midpoint, "
                    + "which is what a crossing or a free bar end leaves behind, "
                    + "is placed unmirrored.",
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
                    + "on. Read the geometry back with Frame (Columns), the "
                    + "numbers with Forces, Fit and Supports, and the words "
                    + "with Diagnose. Wire it into Animate to raise the "
                    + "columns with the net.",
                GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            // The Message is cleared FIRST. It is set only where a level is
            // actually built, so without this the last good solve's "Type 2,
            // 12 feet" sat under an error balloon, or beside an input that had
            // just been unwired, saying columns were standing that are not.
            Message = null;
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                Message = "No Result";
                return;
            }

            int branching = 1;
            int type = 0;
            data.GetData(1, ref branching);
            data.GetData(2, ref type);
            branching = Math.Min(Math.Max(branching, 1), ColumnPlacement.MaxBranching);
            if (type > ColumnPlacement.MaxGround)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"Type {type} is above the {ColumnPlacement.MaxGround} feet "
                        + "per span this machine places; clamped. A seven-item "
                        + "Type value list from before the two-slider rework goes "
                        + "to 6; delete it, then place the Type list from the "
                        + "component menu. A list already wired is never "
                        + "replaced.");
                type = ColumnPlacement.MaxGround;
            }
            if (type < -1)
                type = -1;

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
                var barPull = new Vector3d[bars.Count][];
                for (int b = 0; b < bars.Count; b++)
                {
                    // The untransversed pull is KEPT rather than discarded
                    // after BarTransverse: spec section 10 threads it through
                    // so the head load at a shared node is counted exactly
                    // once and in full.
                    Vector3d[] pull = MouldGeometry.BarLoads(bars[b], nodes, incident);
                    Vector3d[] transverse = MouldGeometry.BarTransverse(bars[b], nodes, pull);
                    for (int k = 0; k < bars[b].Count; k++)
                    {
                        alongToAnchors += (pull[k] - transverse[k]).Length;
                        acrossToColumns += transverse[k].Length;
                    }
                    barPull[b] = pull;
                    across[b] = transverse;
                }
                Vector3d[] nodePull = MouldGeometry.NodeLoads(nodes, incident);

                // The boundary loops, for the free-rim test. Computed the way
                // Animate computes its Perimeter Nodes: naked mesh edges when
                // the thrust mesh exists, a degree heuristic otherwise, grouped
                // over the union of solved and pattern edges.
                Mesh? thrust = MouldGeometry.ThrustMeshFromResult(result, out int[] meshToNode);
                List<int>[] neighbours = MouldGeometry.BuildAdjacency(n, edges);
                // The route taken is discarded here on purpose: this walk
                // only needs the ring to place the anchor trees, and it
                // labels no curve the boundary.
                int[] perimeterIds = MouldGeometry.PerimeterNodes(
                    thrust, meshToNode, neighbours, n, out _);
                List<int>[] grouping = MouldGeometry.GroupingAdjacency(result, edges, n);
                List<List<int>> loops = MouldGeometry.ConnectedGroups(perimeterIds, grouping);

                ColumnPlacement.Placement placement = ColumnPlacement.Place(
                    nodes,
                    bars.Select(b => b.ToArray()).ToArray(),
                    edges,
                    anchors.ToArray(),
                    across,
                    barPull,
                    nodePull,
                    loops.Select(l => l.ToArray()).ToArray(),
                    groundLevel,
                    branching,
                    type);
                ColumnPlacement.Level built = placement.Built;
                if (placement.Trees.Count == 0)
                {
                    // Every node on every principal line is an anchor, so
                    // there is no notch to hold. The block is written empty
                    // rather than skipped, so downstream still sees Columns
                    // ran, but it must not pass in silence.
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "No free notch on any principal line: every node on the "
                            + "bars is an anchor, so no column was built. Draw "
                            + "the lines across the form, not along the sides.");
                }

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

                if (built.Collisions > 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        $"{built.Collisions} member(s) come within the clearance "
                            + "of another member or of the net; placed anyway so "
                            + "the chain keeps running. Diagnose counts them and "
                            + "names the lever.");
                }
                bool nothingGathered = built.Gathered > 0 && built.Peeled >= built.Gathered;
                if (built.Peeled > 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        nothingGathered
                            ? "nothing gathered: every trunk to the shared feet "
                                + "would lean past 60 degrees; the columns stand "
                                + "as Type 0."
                            : $"{built.Peeled} trunk(s) stand on their own feet: a "
                                + "trunk from the shared foot would lean past 60 "
                                + "degrees. The level itself is placed.");
                }

                // What the canvas can read without opening Diagnose. This is
                // the branch that made the slider mean something, so the
                // slider's answer belongs on the component.
                Message = (type < 0 ? "Auto: " : string.Empty)
                    + $"Type {placement.GroundPlaced}, {Count(built.Feet.Count, "foot", "feet")}"
                    + (built.Peeled > 0 ? $", {built.Peeled} peeled" : string.Empty)
                    + (placement.AsymmetricSpans > 0
                        ? $", unmirrored {placement.AsymmetricSpans}"
                        : string.Empty);

                Point3d[] netNodes = nodes.ToArray();
                double weld = 1.0e-6 * Math.Max(
                    new BoundingBox(netNodes).Diagonal.Length, 1.0);
                MouldColumnsDto block = MouldGeometry.ColumnsBlock(
                    members,
                    force,
                    netNodes,
                    weld,
                    branching: branching,
                    groundAsked: type,
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
                // The loads and forces below are the Result's own, in the
                // Result's own unit, so they are labelled with it rather than
                // with a newton this component never converted to. The
                // readers read it the same way. No arithmetic here changes.
                string declaredUnit = (equilibrium.ForceUnit ?? string.Empty).Trim();
                string forceUnit = declaredUnit.Length > 0 ? declaredUnit : "kN";
                output = ResultDiagnostics.Replace(output, "Columns", Diagnostics(
                    bars, placement, built, force, angle, branching, type,
                    groundLevel, alongToAnchors, acrossToColumns, overlapping,
                    barShape, forceUnit));
                data.SetData(0, new ResultGoo(output));
            }
            catch (Exception ex)
            {
                Message = "Error";
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        /// <summary>
        /// A count and its noun, so a diagnostic reads "1 foot" and not
        /// "1 feet". Type 1 and one family are the ordinary settings, so the
        /// plural was the one an author met most often.
        /// </summary>
        private static string Count(int count, string one, string many) =>
            count.ToString(CultureInfo.InvariantCulture) + " " + (count == 1 ? one : many);

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
            List<string> barShape,
            string forceUnit)
        {
            const string S = "Columns";
            double cap = MouldGeometry.MaxLeanDegrees;
            var d = new List<DiagnosticDto>
            {
                overlapping > 0
                    ? ResultDiagnostics.Entry(S, "columns.overlap", "warning",
                        $"two principal lines share {overlapping} notches, so ONE "
                            + "bar is traced twice. The second trace finds its "
                            + "notches already held and builds nothing of its own, "
                            + "so the columns are right, but its spans are counted "
                            + "and its bar is reported: check the curves drawn into "
                            + "Pattern.",
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
            // Every trunk peeled is the state this branch was written to make
            // visible: the level is placed, and the geometry that comes back
            // is Type 0's exactly. Saying the trees gathered would be saying
            // the opposite of what the author is looking at.
            //
            // Judged against the trees the level HANDED A BAND, not against
            // every tree it holds. At an even Type the centre tree of an odd
            // count takes no band and stands on its own foot, and the ring
            // tree never had one, so counting those made the state
            // unreachable on exactly the arch it was written for.
            bool nothingGathered = built.Gathered > 0 && built.Peeled >= built.Gathered;
            string gathered = placement.GroundPlaced == 0
                ? $"every tree stands on its own foot; {Count(built.Feet.Count, "foot", "feet")}"
                : nothingGathered
                    ? "nothing gathered: every trunk to the shared feet would lean "
                        + $"past {cap:0} degrees; the columns stand as Type 0; "
                        + $"{Count(built.Feet.Count, "foot", "feet")}"
                    : $"each span's trees gather onto up to "
                        + $"{Count(placement.GroundPlaced, "foot", "feet")} about its "
                        + $"midpoint; {Count(built.Feet.Count, "foot", "feet")} built";
            // A peel is not a fault. It is the rule working: the level stands
            // and the trunk that could not reach the shared foot stands on its
            // own, which is what the refusal used to prevent.
            d.Add(ResultDiagnostics.Entry(S, "columns.type", "info",
                $"Type asked {asked}, placed {placement.GroundPlaced}: {gathered}"
                    + (built.Peeled > 0 && !nothingGathered
                        ? $"; {built.Peeled} trunk(s) stand on their own feet because "
                            + $"a trunk to the shared foot would lean past {cap:0} degrees"
                        : string.Empty)
                    + ".",
                placement.GroundPlaced, unit: "feet per span",
                context: ResultDiagnostics.Context(
                    ("asked", groundAsked.ToString(CultureInfo.InvariantCulture)),
                    ("placed", placement.GroundPlaced.ToString(CultureInfo.InvariantCulture)),
                    ("peeled", built.Peeled.ToString(CultureInfo.InvariantCulture)),
                    ("feet", built.Feet.Count.ToString(CultureInfo.InvariantCulture)))));

            // Spans WITH TREES, not placement.Spans.Count: a span whose only
            // free notches were already claimed by a crossing or by the ring
            // tree holds none, and saying "S spans in K families" would claim
            // every span joined a family when some hold no tree to symmetrise
            // at all. The engine counts them as it walks the spans, so this
            // reads that count rather than deriving it a second way.
            int spansWithTrees = placement.SpansWithTrees;
            d.Add(ResultDiagnostics.Entry(S, "columns.symmetry", "info",
                $"{Count(spansWithTrees, "span", "spans")} with trees in "
                    + $"{Count(placement.Families, "family", "families")}; "
                    + "feet mirrored about each span's midpoint, the along-chord "
                    + "and vertical pulls shared across each family and each line "
                    + "keeping its own across-chord pull; the largest aim moved "
                    + $"{placement.AsymmetryRemoved:0.##} degrees; "
                    + $"{placement.CentreTrees} centre tree(s) standing in the "
                    + "mirror plane"
                    + (placement.AsymmetricSpans > 0
                        ? $"; {Count(placement.AsymmetricSpans, "span", "spans")} placed "
                            + "unmirrored: a crossing or a free end breaks their symmetry"
                        : string.Empty)
                    + ".",
                placement.AsymmetryRemoved, unit: "degrees",
                context: ResultDiagnostics.Context(
                    ("spans", spansWithTrees.ToString(CultureInfo.InvariantCulture)),
                    ("families", placement.Families.ToString(CultureInfo.InvariantCulture)),
                    ("moved", Inv(placement.AsymmetryRemoved, "0.##")),
                    ("centres", placement.CentreTrees.ToString(CultureInfo.InvariantCulture)),
                    ("unmirrored", placement.AsymmetricSpans.ToString(CultureInfo.InvariantCulture)))));

            var scored = placement.Tried
                .OrderByDescending(t => t.Ground)
                .Select(t => (t.Ground.ToString(CultureInfo.InvariantCulture),
                    Inv(t.LoadPath, "0") + (t.Collisions > 0 ? " collides" : string.Empty)))
                .ToArray();
            d.Add(ResultDiagnostics.Entry(S, "columns.load_path", "info",
                $"load path {built.LoadPath:0} {forceUnit} x model units, the sum "
                    + "over members of force times length"
                    + (groundAsked < 0
                        ? $"; levels scored: {string.Join(", ", scored.Select(s => $"{s.Item1}={s.Item2}"))}"
                        : string.Empty),
                built.LoadPath, unit: forceUnit + " x model units",
                context: ResultDiagnostics.Context(scored)));

            if (built.FeetMerged > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.feet_merged", "info",
                    $"{Count(built.FeetMerged, "MIRRORED PAIR", "MIRRORED PAIRS")} of "
                        + "feet lay within the clearance of each other and stand on "
                        + "one foot at the mean of the two, in their span's mirror "
                        + "plane. Only a mirrored pair merges; any other two feet "
                        + "stay two, however close.",
                    built.FeetMerged, unit: "feet"));
            }
            if (built.FeetClose > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.feet_close", "warning",
                    $"{Count(built.FeetClose, "pair", "pairs")} of feet closer than "
                        + "the clearance stand separately; raise Type to gather them, "
                        + "or space the principal lines.",
                    built.FeetClose, unit: "pairs"));
            }
            if (built.WorstAlignment > ColumnPlacement.AlignmentDegrees)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.alignment", "warning",
                    $"a foot's push is {built.WorstAlignment:0.#} degrees off the "
                        + "thrust its trees ask for; the foundation sees that as "
                        + "thrust.",
                    built.WorstAlignment, ColumnPlacement.AlignmentDegrees, "degrees"));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.branch_off_thrust", "info",
                $"branches stand up to {built.WorstBranchOff:0.#} degrees off the "
                    + "pull at their notch; a fork can only be in one place, and "
                    + "what is left is bending for the joint to take.",
                built.WorstBranchOff, unit: "degrees"));
            if (built.Collisions > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.collision", "warning",
                    $"{built.Collisions} member(s) come within the clearance of "
                        + "another member or of the net; placed anyway. Draw the "
                        + "principal lines further apart or lower Branching.",
                    built.Collisions, unit: "members"));
            }
            d.Add(ResultDiagnostics.Entry(S, "columns.head_load_total", "info",
                $"the heads carry {placement.Trees.Sum(t => t.Load.Sum()):0} "
                    + $"{forceUnit} between them, ground read as {groundLevel:0.###}, "
                    + "the level the anchors sit at",
                placement.Trees.Sum(t => t.Load.Sum()), unit: forceUnit,
                context: ResultDiagnostics.Context(("ground", Inv(groundLevel, "0.###")))));
            d.Add(ResultDiagnostics.Entry(S, "columns.load_split", "info",
                $"of the net's pull on the bars, {alongToAnchors:0} {forceUnit} runs "
                    + "ALONG them to the anchors, which are this machine's buttresses. "
                    + $"The {acrossToColumns:0} {forceUnit} ACROSS them is the columns' "
                    + "to take, and it sets their lean.",
                acrossToColumns, unit: forceUnit,
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
                    $"head load {loads.Min():0} to {loads.Max():0} {forceUnit}",
                    loads.Max(), unit: forceUnit,
                    context: ResultDiagnostics.Context(("min", Inv(loads.Min(), "0")))));
            }
            if (force.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "columns.force_max", "info",
                    $"axial force up to {force.Max():0} {forceUnit}",
                    force.Max(), unit: forceUnit));
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
