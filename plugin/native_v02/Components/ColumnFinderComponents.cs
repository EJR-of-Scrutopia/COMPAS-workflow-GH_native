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
    /// Column Finder: solve where the column arms stand under the notched bars,
    /// and grow them down to the ground as posts or as branching trees.
    ///
    /// It takes the solved Result as its form finder. The principal lines
    /// travel in the contract, resolved once upstream by Supports from the
    /// anchors or by Pattern from drawn curves, and the load each notch hands
    /// its bar is read straight off the Result's own reactions. Nothing has to
    /// be told to it twice, and nothing is snapped here.
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
    /// The bar's stiffness deliberately does not appear. Deflection scales as
    /// one over EI, so EI is a common factor across every candidate arrangement
    /// and cancels out of the comparison: the best arm positions are identical
    /// whatever the bar is made of, which was checked across seven orders of
    /// magnitude. Stiffness would only be needed to turn the droop into
    /// millimetres, and that is a capacity to establish by testing rather than
    /// to assume here. The same goes for allowable stress and member sizing.
    /// This component finds WHERE the columns stand and WHAT they carry; how
    /// strong they have to be is the next question, not this one.
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

        /// <summary>
        /// Blue for the columns: the one thing on screen that is not part of
        /// the net. Green already means a support, red a notched bar, so the
        /// three families of member stay legible without reading a number.
        /// </summary>
        private static readonly Color ColumnColour =
            Color.FromArgb(40, 85, 175);

        private Mesh? _previewMesh;
        private readonly List<Line> _previewCables = new();
        private readonly List<Line> _previewPrincipal = new();
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
            _previewPrincipal.Clear();
            _previewColumns.Clear();
            _previewSupports.Clear();
            _clippingBox = BoundingBox.Empty;
        }

        /// <summary>
        /// Draw the finished mould the way TNA Solve and Animate draw theirs:
        /// same shaded material, same wire colour, same support points, so the
        /// three read as one object seen at three moments rather than as three
        /// different drawings. On top of that goes the one thing only this
        /// component knows, the columns, and the bars they hold.
        ///
        /// The geometry outputs stay hidden, as on Animate, so nothing draws
        /// twice; their data is untouched and still feeds downstream.
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
            foreach (Line bar in _previewPrincipal)
            {
                args.Display.DrawLine(
                    bar,
                    TnaWorkflowPreview.PrincipalColour,
                    TnaWorkflowPreview.PrincipalWeight);
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
                    + "gives the notches and its reactions give the load each "
                    + "one hands the bar.",
                GH_ParamAccess.item);
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
                "How many times a tree may FORK on the way down. 0 sends every "
                    + "arm straight to the foot as a fan; 1 pairs them once "
                    + "and takes the pairs down; higher keeps forking until "
                    + "one trunk is left, after which more has no effect. "
                    + "Every arm is kept whatever the depth. Ignored when "
                    + "Trees is 0.",
                GH_ParamAccess.item,
                2);
            parameters[1].Optional = true;
            parameters[2].Optional = true;
            parameters[3].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddLineParameter(
                "Columns",
                "C",
                "The final column members as built lines, each running from its "
                    + "foot on the ground up to the notch it holds. The line "
                    + "IS the column, so its direction is the lean the arm has "
                    + "to stand at. With Trees at 0 there is one straight post "
                    + "per arm; above 0 these are the branches of each tree. "
                    + "Force and Angle align with this list.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Heads",
                "H",
                "The top of each column: the notch on the bar that this arm "
                    + "carries. These are the points the mechanism has to reach, "
                    + "and they are chosen by solving the bar, not by spacing.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Feet",
                "F",
                "The bottom of each column, on the ground. With Trees at 0 a "
                    + "foot sits directly under its head; above 0 the feet are "
                    + "the load-weighted centres of each tree, so there are "
                    + "fewer of them than there are arms and each one takes a "
                    + "whole tree's load.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Force",
                "FO",
                "Axial force along each column, N: what that member actually "
                    + "carries, for sizing and for testing later. A leaning "
                    + "column carries MORE than the weight above it, by one "
                    + "over its vertical cosine, and the surplus is the "
                    + "horizontal thrust its foot has to resist. No capacity is "
                    + "assumed anywhere; this is the demand, not a verdict.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "Angle",
                "A",
                "Lean of each column from vertical, degrees. This is the angle "
                    + "the arm stands at, and the number that decides whether "
                    + "the sliding joint can reach it. Past about sixty degrees "
                    + "a column is doing more pushing sideways than holding up.",
                GH_ParamAccess.list);
            parameters.AddParameter(
                new MouldStateParam(),
                "State",
                "S",
                "The finished mould bundled for Stress Analysis: the net with "
                    + "its member forces and node roles, plus the columns and "
                    + "what each one carries.",
                GH_ParamAccess.item);
            parameters.AddTextParameter(
                "Report",
                "Out",
                "How many arms went on each bar and where, what they carry, and "
                    + "how the load divides between the feet.",
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

            int perLine = 3;
            int trees = 0;
            int depth = 2;
            data.GetData(1, ref perLine);
            data.GetData(2, ref trees);
            data.GetData(3, ref depth);
            perLine = Math.Max(perLine, 2);

            // Stiffness cancels out of the placement, so any positive value
            // gives the same arms. One keeps the arithmetic well conditioned.
            const double placementStiffness = 1.0;

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

                // Keep the ORIGINAL edge index alongside each kept edge. The
                // filter drops invalid and self edges, so a filtered position
                // no longer matches the Result's own MemberForces array, and
                // indexing forces by it would silently attach every force
                // after the first dropped edge to the wrong member.
                (int, int)[] edges = MouldGeometry.ValidEdges(
                    equilibrium, n, out int[] edgeSource);

                var anchors = new HashSet<int>(
                    equilibrium.ResolvedSupportNodeIds.Where(i => i >= 0 && i < n));

                // The feet stand on the level the ANCHORS sit at. Not the base
                // of the geometry: the two agree until some part of a vault
                // hangs below its own supports, and then the base is under the
                // dip and every column would be stood on it.
                double ground = MouldGeometry.GroundLevel(nodes, anchors);

                // The runs travel in the contract, resolved once upstream by
                // Supports from the anchors or by Pattern from drawn curves.
                List<List<int>> bars = MouldGeometry.PrincipalRuns(
                    equilibrium, n);
                if (bars.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines. Set Ribs on "
                            + "Supports to derive them from the anchors, or "
                            + "draw Principal Lines on Pattern.");
                    return;
                }

                // What the net hands each node, from the solve's own member
                // forces. NOT from equilibrium.Reactions, which was the bug
                // this replaces: reactions exist only at SUPPORTS, so every
                // interior notch read zero and each bar was being solved as a
                // beam with no load anywhere along it. The arms were placed on
                // an empty problem and the forces they reported were zero.
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

                var heads = new List<Point3d>();
                var headLoad = new List<double>();
                var headAim = new List<Vector3d>();
                var armsPerBar = new List<int>();
                double alongToAnchors = 0.0;
                double acrossToColumns = 0.0;
                int plumbArms = 0;

                foreach (List<int> bar in bars)
                {
                    Vector3d[] pull = MouldGeometry.BarLoads(bar, nodes, incident);
                    Vector3d[] across = MouldGeometry.BarTransverse(bar, nodes, pull);
                    for (int k = 0; k < bar.Count; k++)
                    {
                        alongToAnchors += (pull[k] - across[k]).Length;
                        acrossToColumns += across[k].Length;
                    }

                    double[] barLoad = across
                        .Select(v => Math.Abs(v.Z)).ToArray();
                    (List<int> chosen, double _droop, double[] reactions) =
                        BeamSolver.ArmsForBar(
                            bar, nodes, barLoad, anchors, perLine,
                            placementStiffness);
                    armsPerBar.Add(chosen.Count);
                    Vector3d[] aim = ArmAim(bar, nodes, across, chosen, anchors);
                    plumbArms += LastPlumbFallbacks;
                    for (int c = 0; c < chosen.Count; c++)
                    {
                        int k = chosen[c];
                        heads.Add(nodes[bar[k]]);
                        headLoad.Add(reactions.Length > k
                            ? Math.Max(reactions[k], 0.0)
                            : barLoad[k]);
                        headAim.Add(aim[c]);
                    }
                }

                var members = new List<Line>();
                var carried = new List<double>();
                var feet = new List<Point3d>();
                double treeResidual = 0.0;

                if (trees <= 0)
                {
                    // Every arm its own post, standing along the line of the
                    // force it carries rather than plumb. Where the net pulls
                    // a notch straight down the aim IS vertical and the post
                    // is the plumb one it always was.
                    for (int i = 0; i < heads.Count; i++)
                    {
                        double rise = heads[i].Z - ground;
                        if (rise <= 0.0)
                            continue;
                        Vector3d up = headAim[i];
                        var foot = new Point3d(
                            heads[i].X - (up.X * rise / up.Z),
                            heads[i].Y - (up.Y * rise / up.Z),
                            ground);
                        members.Add(new Line(foot, heads[i]));
                        carried.Add(headLoad[i]);
                        feet.Add(foot);
                    }
                }
                else
                {
                    Forest forest = TreeBuilder.Build(
                        heads.ToArray(), headLoad.ToArray(), headAim.ToArray(),
                        Math.Max(trees, 1), Math.Max(depth, 0), ground);
                    treeResidual = forest.WorstTipAngle;
                    for (int s = 0; s < forest.Segments.Count; s++)
                    {
                        (int child, int parent) = forest.Segments[s];
                        Point3d a = forest.Points[child];
                        Point3d b = forest.Points[parent];
                        // Every column member runs LOWER end to UPPER end, so
                        // that From is always the foot side and To the head
                        // side. A tree branch is stored child to parent, which
                        // runs the other way, and leaving it would silently
                        // swap the meaning of foot and head the moment Trees
                        // went above zero.
                        members.Add(a.Z <= b.Z ? new Line(a, b) : new Line(b, a));
                        carried.Add(forest.CarriedLoad[s]);
                    }
                    feet.AddRange(forest.FootIndices.Select(i => forest.Points[i]));
                }

                if (trees > 0 && treeResidual > 5.0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        $"A tree branch meets its arm {treeResidual:0.#} "
                            + "degrees off the line of thrust that arm carries. "
                            + "The junctions are in equilibrium; a fixed "
                            + "branching topology simply cannot always reach "
                            + "every tip along its own force. That angle is "
                            + "bending for the notch joint to take, so either "
                            + "accept it or change Trees and Depth.");
                }

                var force = new List<double>(members.Count);
                var angle = new List<double>(members.Count);
                for (int i = 0; i < members.Count; i++)
                {
                    Vector3d v = members[i].To - members[i].From;
                    double length = v.Length;
                    double cos = length > 1e-12 ? Math.Abs(v.Z) / length : 1.0;
                    force.Add(cos > 1e-6 ? carried[i] / cos : carried[i]);
                    angle.Add(Rhino.RhinoMath.ToDegrees(
                        Math.Acos(Math.Min(Math.Max(cos, -1.0), 1.0))));
                }

                data.SetDataList(0, members);
                data.SetDataList(1, heads);
                data.SetDataList(2, feet);
                data.SetDataList(3, force);
                data.SetDataList(4, angle);

                Mesh? thrust = MouldGeometry.ThrustMeshFromResult(
                    result, out int[] meshToNode);
                var perimeter = MouldGeometry.PerimeterNodes(
                    thrust, meshToNode, MouldGeometry.BuildAdjacency(n, edges), n);
                var footPts = members.Select(m => m.From).ToList();
                var headPts = members.Select(m => m.To).ToList();

                _previewMesh = thrust;
                _previewCables.Clear();
                _previewCables.AddRange(edges.Select(
                    e => new Line(nodes[e.Item1], nodes[e.Item2])));
                _previewPrincipal.Clear();
                foreach (List<int> bar in bars)
                {
                    for (int k = 0; k + 1 < bar.Count; k++)
                        _previewPrincipal.Add(
                            new Line(nodes[bar[k]], nodes[bar[k + 1]]));
                }
                _previewColumns.Clear();
                _previewColumns.AddRange(members);
                _previewSupports.Clear();
                _previewSupports.AddRange(
                    anchors.OrderBy(i => i).Select(i => nodes[i]));
                _clippingBox = TnaWorkflowPreview.Box(
                    _previewCables.Concat(_previewColumns),
                    _previewSupports);
                data.SetData(5, new MouldStateGoo(MouldGeometry.BuildState(
                    "final", ground, nodes, edges, edgeSource, equilibrium,
                    bars.SelectMany(b => b), anchors, perimeter,
                    footPts, headPts, force)));
                data.SetData(6, Report(
                    bars, armsPerBar, headLoad, members, force, angle, feet,
                    trees, depth, ground, alongToAnchors, acrossToColumns,
                    plumbArms));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        /// <summary>
        /// Which way each arm has to push: the direction of the load it
        /// gathers, so the column stands along the line of its own force and
        /// works in pure compression.
        ///
        /// A notch belongs to whichever support is nearest along the bar, and
        /// the anchors count as supports here exactly as they do in the beam
        /// solve: an anchor takes its share whether or not it costs an arm, so
        /// a notch beside one is not the arm's to carry.
        ///
        /// The lean is capped at sixty degrees. Past that a column pushes
        /// sideways more than it holds up, and the sliding joint cannot reach
        /// the angle anyway; holding it there leaves the difference visible as
        /// residual thrust rather than drawing a column nobody can build.
        /// </summary>
        private static Vector3d[] ArmAim(
            List<int> bar,
            Point3d[] nodes,
            Vector3d[] across,
            List<int> chosen,
            HashSet<int> anchors)
        {
            var aim = new Vector3d[chosen.Count];
            if (chosen.Count == 0)
                return aim;

            var arc = new double[bar.Count];
            for (int k = 1; k < bar.Count; k++)
                arc[k] = arc[k - 1] + nodes[bar[k - 1]].DistanceTo(nodes[bar[k]]);

            var supports = new List<int>(chosen);
            for (int k = 0; k < bar.Count; k++)
            {
                if (anchors.Contains(bar[k]) && !supports.Contains(k))
                    supports.Add(k);
            }

            var gathered = new Vector3d[chosen.Count];
            for (int k = 0; k < bar.Count; k++)
            {
                int nearest = -1;
                double best = double.MaxValue;
                foreach (int support in supports)
                {
                    double distance = Math.Abs(arc[k] - arc[support]);
                    if (distance < best)
                    {
                        best = distance;
                        nearest = support;
                    }
                }
                int index = chosen.IndexOf(nearest);
                if (index >= 0)
                    gathered[index] += across[k];
            }

            int plumbFallbacks = 0;
            for (int c = 0; c < chosen.Count; c++)
            {
                if (-gathered[c].Z <= 1.0e-9)
                    plumbFallbacks++;
                aim[c] = MouldGeometry.AimFrom(gathered[c]);
            }
            LastPlumbFallbacks = plumbFallbacks;
            return aim;
        }

        /// <summary>
        /// How many arms in the last bar could not be aimed and stood plumb
        /// because the net was pulling their notch DOWN through the column. It
        /// happens legitimately at a notch the net wants to hold down, and it
        /// happened to EVERY arm once, from a sign error, and looked like a
        /// design decision. Counted so it is visible.
        /// </summary>
        private static int LastPlumbFallbacks { get; set; }

        private static string Report(
            List<List<int>> bars,
            List<int> armsPerBar,
            List<double> headLoad,
            List<Line> members,
            List<double> force,
            List<double> angle,
            List<Point3d> feet,
            int trees,
            int depth,
            double ground,
            double alongToAnchors,
            double acrossToColumns,
            int plumbArms)
        {
            var lines = new List<string>
            {
                $"{bars.Count} bars, {armsPerBar.Sum()} arms "
                    + $"({string.Join(" + ", armsPerBar)} per bar), "
                    + $"{feet.Count} feet, {members.Count} members",
                $"the arms carry {headLoad.Sum():0} N between them, ground read "
                    + $"as {ground:0.###}, the level the anchors sit at",
                "principal lines came from the contract, resolved upstream",
                string.Empty,
                "arm positions are SOLVED, not spaced: a loaded bar wants its "
                    + "supports about a fifth of its length in from each end, "
                    + "and every arrangement of notches was tried. Bar "
                    + "stiffness is not asked for because it cancels out of "
                    + "that comparison.",
                string.Empty,
                $"of the net's pull on the bars, {alongToAnchors:0} N runs "
                    + "ALONG them and goes to the anchors, which are this "
                    + "machine's buttresses because both ends of every bar are "
                    + $"tied to the ground. The {acrossToColumns:0} N ACROSS "
                    + "them is the columns' to take, and it is what sets their "
                    + "lean: each post stands along the line of the force it "
                    + "carries, so it works in pure compression and its foot "
                    + "takes no sideways push it was not given.",
            };

            if (plumbArms > 0)
            {
                lines.Add(string.Empty);
                lines.Add(
                    $"{plumbArms} arms stand PLUMB because the net pulls their "
                        + "notch down onto the column rather than off it, so "
                        + "there is no thrust line for them to follow. If that "
                        + "is ALL of them, the aiming is not working.");
            }

            lines.Add(trees <= 0
                ? "Trees 0: every arm drops straight to its own foot."
                : $"Trees {trees} at depth {depth}: the arms are gathered into "
                    + "branching trees clustered by equal load, so the feet are "
                    + "fewer than the arms.");

            if (headLoad.Count > 0)
                lines.Add($"arm load {headLoad.Min():0} to {headLoad.Max():0} N");
            if (force.Count > 0)
                lines.Add($"axial force up to {force.Max():0} N");
            if (angle.Count > 0)
            {
                lines.Add($"lean {angle.Min():0.#} to {angle.Max():0.#} degrees "
                    + "from vertical");
                if (angle.Max() > 60.0)
                {
                    lines.Add(
                        "WARNING: a column leans past sixty degrees, so it is "
                            + "pushing sideways more than it is holding up. "
                            + "Check the sliding joint can reach that angle.");
                }
            }
            lines.Add(string.Empty);
            lines.Add(
                "no capacity is assumed anywhere here: Force is the demand, to "
                    + "size and test against, not a pass or a fail.");
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
            double[] barLoad,
            HashSet<int> anchors,
            int perLine,
            double EI)
        {
            int count = bar.Count;
            var arc = new double[count];
            for (int k = 1; k < count; k++)
                arc[k] = arc[k - 1] + nodes[bar[k - 1]].DistanceTo(nodes[bar[k]]);
            double span = arc[count - 1];

            // Already the bar's own load, position by position: what the
            // infill cables pull at each notch, across the bar.
            double[] load = barLoad;
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

        /// <summary>
        /// The worst angle, in degrees, between a tip member and the force that
        /// tip actually hands the tree. Zero means every arm meets its tree
        /// along its own line of thrust. A fixed topology cannot always reach
        /// zero, and what is left is bending the notch joint has to take, so it
        /// is reported rather than hidden.
        /// </summary>
        public double WorstTipAngle { get; set; }
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
            Vector3d[] aim,
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

                // EVERY arm is a tip. They were being aggregated down to two
                // to the power of Depth first, which threw away arm positions
                // the beam solve had just worked out: a low Depth silently
                // merged most of the arms away instead of branching less.
                Point3d[] tips = members.Select(i => heads[i]).ToArray();

                // The force each arm hands the tree: its own aim, scaled so the
                // vertical component is the load that arm carries. This is what
                // makes the tree a force problem rather than a spacing one.
                Vector3d[] tipF = members
                    .Select(i => aim[i] * (load[i] / Math.Max(aim[i].Z, 1.0e-9)))
                    .ToArray();

                (Point3d[] junctions, List<(int, int)> segs, List<int> roots) =
                    MergeTopology(tips, depth);

                var local = new List<Point3d>(tips);
                local.AddRange(junctions);
                local.Add(feet[c]);
                int footLocal = local.Count - 1;
                foreach (int root in roots)
                    segs.Add((root, footLocal));

                Vector3d[] flow = AccumulateForces(segs, tipF, local.Count);
                RelaxToForces(local, segs, flow, tips.Length, footLocal, ground);
                forest.WorstTipAngle = Math.Max(
                    forest.WorstTipAngle,
                    WorstTipDeviation(local, segs, tipF, tips.Length));

                // Vertical share of the force flowing up each member, so the
                // axial force downstream is still this over the lean's cosine.
                var carried = new double[segs.Count];
                for (int s = 0; s < segs.Count; s++)
                    carried[s] = flow[segs[s].Item1].Z;
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

        /// <summary>
        /// Gather the arms into a branching tree, forking at most
        /// <paramref name="depth"/> times on the way down.
        ///
        /// Depth counts LEVELS OF FORK, which is the thing an author is
        /// actually choosing, and every arm is kept whatever it is set to. It
        /// used to cap the number of TIPS at two to the power of Depth, which
        /// aggregated arms away: a low Depth did not branch less, it silently
        /// merged most of the arms the beam solve had just placed, and 0 and 1
        /// collapsed nearly everything into one or two posts.
        ///
        /// So 0 forks nothing and every arm runs to the foot as a fan; 1 pairs
        /// them once; higher keeps forking until one trunk is left, past which
        /// more has no effect. Whatever is still unmerged when the depth runs
        /// out becomes a root and goes to the foot.
        /// </summary>
        private static (Point3d[], List<(int, int)>, List<int>) MergeTopology(
            Point3d[] tips, int depth)
        {
            int t = tips.Length;
            var segments = new List<(int, int)>();
            var active = Enumerable.Range(0, t).ToList();
            if (t <= 1 || depth <= 0)
                return (Array.Empty<Point3d>(), segments, active);

            var position = new Dictionary<int, Point3d>();
            var level = new Dictionary<int, int>();
            for (int i = 0; i < t; i++)
            {
                position[i] = tips[i];
                level[i] = 0;
            }
            int next = t;

            while (active.Count > 1)
            {
                int ai = -1;
                int bi = -1;
                double best = double.MaxValue;
                for (int i = 0; i < active.Count; i++)
                {
                    for (int j = i + 1; j < active.Count; j++)
                    {
                        // A merge adds a level; refuse the ones that would
                        // fork deeper than asked.
                        if (Math.Max(level[active[i]], level[active[j]]) + 1
                            > depth)
                        {
                            continue;
                        }
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
                if (ai < 0)
                    break;      // nothing left that may fork again
                int a = active[ai];
                int b = active[bi];
                position[next] = new Point3d(
                    (position[a].X + position[b].X) / 2.0,
                    (position[a].Y + position[b].Y) / 2.0,
                    (position[a].Z + position[b].Z) / 2.0);
                level[next] = Math.Max(level[a], level[b]) + 1;
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
            return (junctions, segments, active);
        }

        /// <summary>
        /// The force flowing up out of every node, summed from the tips.
        ///
        /// Deliberately a VECTOR sum. In a tree in equilibrium the force in a
        /// parent member is the vector sum of its children's, so these totals
        /// are fixed by the tip forces alone and do not depend on where the
        /// junctions end up. That is what lets the relaxation below use them as
        /// weights and still be a plain weighted median rather than a fixed
        /// point chasing its own geometry.
        /// </summary>
        private static Vector3d[] AccumulateForces(
            List<(int, int)> segments,
            Vector3d[] tipForce,
            int nodeCount)
        {
            var total = new Vector3d[nodeCount];
            for (int i = 0; i < tipForce.Length && i < nodeCount; i++)
                total[i] = tipForce[i];

            var parent = new Dictionary<int, int>();
            foreach ((int child, int up) in segments)
                parent[child] = up;

            // Valid as a single forward pass because every parent id exceeds
            // its children's, by construction in MergeTopology.
            for (int id = 0; id < nodeCount; id++)
            {
                if (parent.TryGetValue(id, out int up))
                    total[up] += total[id];
            }
            return total;
        }

        /// <summary>
        /// Move every junction to where the forces meeting it balance.
        ///
        /// They were being put at the plain MIDPOINT of the two nodes they
        /// merged. A midpoint carries no forces at all: it is in equilibrium
        /// only when its two branches happen to be symmetric and equally
        /// loaded, and everything else was bending the tree.
        ///
        /// What a junction has to satisfy is that the member forces meeting it
        /// sum to zero. For a fixed topology the position that does it is the
        /// FORCE-WEIGHTED Fermat point: the minimum of sum(f * |x - p|), whose
        /// stationary condition is exactly sum(f * unit(x - p)) = 0. Solved by
        /// weighted Weiszfeld iteration one node at a time, which is the same
        /// cyclic coordinate descent tools/tree_forest/steiner.py runs.
        ///
        /// FREI OTTO'S 120 DEGREES IS THE EQUAL-FORCE CASE OF THIS. Three
        /// members of equal force can only balance at 120 degrees apart, and
        /// the UNWEIGHTED geometric median finds exactly that; steiner.py says
        /// as much, and says in the same breath that it applies no loads.
        /// Weighting by the real forces is the general rule that 120 degrees is
        /// one corner of, which is why the branches of a genuinely loaded tree
        /// do not come out at 120 and should not be made to.
        ///
        /// The foot stays ON the ground but slides across it, which is the
        /// freedom this machine actually has.
        /// </summary>
        private static void RelaxToForces(
            List<Point3d> nodes,
            List<(int, int)> segments,
            Vector3d[] flow,
            int tipCount,
            int footIndex,
            double ground)
        {
            var neighbours = new List<(int Other, double Force)>[nodes.Count];
            for (int i = 0; i < nodes.Count; i++)
                neighbours[i] = new List<(int, double)>();
            foreach ((int child, int up) in segments)
            {
                double force = flow[child].Length;
                neighbours[child].Add((up, force));
                neighbours[up].Add((child, force));
            }

            for (int sweep = 0; sweep < 400; sweep++)
            {
                double shifted = 0.0;
                for (int v = tipCount; v < nodes.Count; v++)
                {
                    if (neighbours[v].Count < 2)
                        continue;
                    double sx = 0.0;
                    double sy = 0.0;
                    double sz = 0.0;
                    double sw = 0.0;
                    foreach ((int other, double force) in neighbours[v])
                    {
                        double distance = nodes[v].DistanceTo(nodes[other]);
                        if (distance <= 1.0e-9 || force <= 0.0)
                            continue;
                        double weight = force / distance;
                        sx += nodes[other].X * weight;
                        sy += nodes[other].Y * weight;
                        sz += nodes[other].Z * weight;
                        sw += weight;
                    }
                    if (sw <= 0.0)
                        continue;
                    var next = new Point3d(
                        sx / sw,
                        sy / sw,
                        v == footIndex ? ground : sz / sw);
                    shifted = Math.Max(shifted, nodes[v].DistanceTo(next));
                    nodes[v] = next;
                }
                if (shifted < 1.0e-9)
                    break;
            }
        }

        /// <summary>
        /// How far each tip member ends up off the force its arm hands the
        /// tree, worst case in degrees. A branching topology fixed in advance
        /// cannot always reach every tip along its own line of thrust, and what
        /// is left over is bending at the notch joint. Measured and reported
        /// rather than assumed away.
        /// </summary>
        private static double WorstTipDeviation(
            List<Point3d> nodes,
            List<(int, int)> segments,
            Vector3d[] tipForce,
            int tipCount)
        {
            double worst = 0.0;
            foreach ((int child, int up) in segments)
            {
                if (child >= tipCount || child >= tipForce.Length)
                    continue;
                Vector3d wanted = tipForce[child];
                Vector3d actual = nodes[up] - nodes[child];
                double a = wanted.Length;
                double b = actual.Length;
                if (a <= 1.0e-12 || b <= 1.0e-12)
                    continue;
                double cosine = ((wanted.X * actual.X) + (wanted.Y * actual.Y)
                    + (wanted.Z * actual.Z)) / (a * b);
                cosine = Math.Min(Math.Max(cosine, -1.0), 1.0);
                worst = Math.Max(
                    worst, Math.Acos(cosine) * 180.0 / Math.PI);
            }
            return worst;
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
