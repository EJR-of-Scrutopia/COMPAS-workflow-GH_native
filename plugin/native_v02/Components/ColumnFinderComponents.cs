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
        private static readonly ComponentValueListSpec[] ValueLists =
        {
            new(
                2,
                "Column Type",
                new (string Label, string Value)[]
                {
                    ("0 · standalone", "0"),
                    ("1 · one central point", "1"),
                    ("2 · two points", "2"),
                    ("3 · three points", "3"),
                    ("4 · four points", "4"),
                    ("5 · five points", "5"),
                    ("6 · six points", "6")
                },
                "0")
        };

        private protected override IReadOnlyList<ComponentValueListSpec>
            SuggestedValueLists => ValueLists;

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
                "Type",
                "T",
                "How the columns meet the ground. 0 stands each one on its "
                    + "own foot; any other number is how many ground points "
                    + "they all gather onto, so 1 is a single central point, 2 "
                    + "is a pair, and so on.",
                GH_ParamAccess.item,
                0);
            parameters.AddIntegerParameter(
                "Branches",
                "B",
                "How many internal branches sprout from each main column. Each "
                    + "one reaches the nearest notch along its own principal "
                    + "line that no other column has taken, so a column with 2 "
                    + "branches carries three notches. Where they FORK is not "
                    + "set: it is solved, as the point where the branches come "
                    + "closest to standing on their own lines of thrust.",
                GH_ParamAccess.item,
                0);
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
            int columnType = 0;
            int branches = 0;
            data.GetData(1, ref perLine);
            data.GetData(2, ref columnType);
            data.GetData(3, ref branches);
            branches = Math.Max(branches, 0);
            // Type 0 stands every column on its own foot; anything else IS
            // the number of ground points they all gather onto.
            int sharedFeet = Math.Max(columnType, 0);
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
                var columnReach = new List<List<Point3d>>();
                var columnForce = new List<List<Vector3d>>();
                var armsPerBar = new List<int>();
                double alongToAnchors = 0.0;
                double acrossToColumns = 0.0;
                int plumbArms = 0;
                int symmetricBars = 0;
                double symmetryCost = 0.0;
                double lopsided = 0.0;

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
                    if (BeamSolver.LastSymmetric)
                    {
                        symmetricBars++;
                        symmetryCost = Math.Max(
                            symmetryCost, BeamSolver.LastSymmetryCost);
                    }
                    else
                    {
                        lopsided = Math.Max(lopsided, BeamSolver.LastLopsided);
                    }
                    armsPerBar.Add(chosen.Count);
                    Vector3d[] aim = ArmAim(bar, nodes, across, chosen, anchors);
                    plumbArms += LastPlumbFallbacks;

                    // Each main column claims its branch notches: the nearest
                    // along ITS OWN principal line that nothing else has taken.
                    // Round by round, so a column beside a crowded neighbour is
                    // not left with none.
                    List<int>[] served = ClaimBranches(
                        bar, nodes, chosen, anchors, branches);

                    for (int c = 0; c < chosen.Count; c++)
                    {
                        int k = chosen[c];
                        var reach = new List<Point3d>();
                        var reachForce = new List<Vector3d>();
                        double load = reactions.Length > k
                            ? Math.Max(reactions[k], 0.0)
                            : barLoad[k];
                        reach.Add(nodes[bar[k]]);
                        reachForce.Add(aim[c] * (load / Math.Max(aim[c].Z, 1e-9)));
                        foreach (int b in served[c])
                        {
                            Vector3d branchAim =
                                MouldGeometry.AimFrom(across[b]);
                            double branchLoad = Math.Abs(across[b].Z);
                            reach.Add(nodes[bar[b]]);
                            reachForce.Add(branchAim *
                                (branchLoad / Math.Max(branchAim.Z, 1e-9)));
                            load += branchLoad;
                        }
                        columnReach.Add(reach);
                        columnForce.Add(reachForce);
                        heads.Add(nodes[bar[k]]);
                        headLoad.Add(load);
                        headAim.Add(aim[c]);
                    }
                }

                var members = new List<Line>();
                var carried = new List<double>();
                var feet = new List<Point3d>();
                double branchOff = 0.0;
                double trunkOff = 0.0;

                // Every column: its notches, the fork solved from their
                // forces, and a trunk down the line of what it all adds up to.
                var trunkTop = new List<Point3d>();
                var trunkForce = new List<Vector3d>();
                var trunkAim = new List<Vector3d>();
                for (int c = 0; c < columnReach.Count; c++)
                {
                    List<Point3d> reach = columnReach[c];
                    List<Vector3d> pushes = columnForce[c];
                    Vector3d total = Vector3d.Zero;
                    foreach (Vector3d push in pushes)
                        total += push;

                    // The fork rides the MAIN column's own line, so that
                    // member stays straight from foot to notch and reads as one
                    // column with limbs leaving it, which is the Frei Otto
                    // shape. A freely placed fork puts trunk and branches on
                    // the same footing and no member reads as the column.
                    Point3d fork = reach.Count > 1
                        ? MouldGeometry.ForkOnLine(
                            reach[0],
                            MouldGeometry.AimFrom(-pushes[0]),
                            reach.Skip(1).ToList(),
                            pushes.Skip(1).ToList(),
                            ground)
                        : reach[0];

                    // The branches, each from its own notch down to the fork.
                    if (reach.Count > 1)
                    {
                        for (int r = 0; r < reach.Count; r++)
                        {
                            if (reach[r].DistanceTo(fork) <= 1.0e-9)
                                continue;
                            members.Add(new Line(fork, reach[r]));
                            carried.Add(Math.Abs(pushes[r].Z));
                            branchOff = Math.Max(
                                branchOff, AngleBetween(
                                    reach[r] - fork, pushes[r]));
                        }
                    }
                    trunkTop.Add(fork);
                    trunkForce.Add(total);
                    trunkAim.Add(MouldGeometry.AimFrom(-pushes[0]));
                }

                if (sharedFeet <= 0)
                {
                    // Standalone: every trunk drops on its own line of thrust.
                    for (int c = 0; c < trunkTop.Count; c++)
                    {
                        Point3d top = trunkTop[c];
                        double rise = top.Z - ground;
                        if (rise <= 0.0)
                            continue;
                        // Down the MAIN column's line, not the resultant's,
                        // so the member above and below the fork is one
                        // straight column rather than a kink.
                        Vector3d up = trunkAim[c];
                        var foot = new Point3d(
                            top.X - (up.X * rise / up.Z),
                            top.Y - (up.Y * rise / up.Z),
                            ground);
                        members.Add(new Line(foot, top));
                        carried.Add(Math.Abs(trunkForce[c].Z));
                        feet.Add(foot);
                    }
                }
                else
                {
                    // Shared: the trunks gather onto that many ground points,
                    // each relaxed to where the trunks meeting it balance. The
                    // same weighted-median rule the forks use, run on the
                    // ground plane because a foot stands on it.
                    int wanted = Math.Min(sharedFeet, trunkTop.Count);
                    int[] group = GroupByPlan(trunkTop, wanted);
                    var nodesLocal = new List<Point3d>(trunkTop);
                    var segs = new List<(int, int)>();
                    var flow = new List<Vector3d>(trunkForce);
                    for (int g = 0; g < wanted; g++)
                    {
                        int[] mine = Enumerable.Range(0, trunkTop.Count)
                            .Where(i => group[i] == g).ToArray();
                        if (mine.Length == 0)
                            continue;
                        double sx = 0.0;
                        double sy = 0.0;
                        double sw = 0.0;
                        foreach (int i in mine)
                        {
                            double w = Math.Max(
                                Math.Abs(trunkForce[i].Z), 1.0e-9);
                            sx += trunkTop[i].X * w;
                            sy += trunkTop[i].Y * w;
                            sw += w;
                        }
                        nodesLocal.Add(new Point3d(sx / sw, sy / sw, ground));
                        flow.Add(Vector3d.Zero);
                        int foot = nodesLocal.Count - 1;
                        foreach (int i in mine)
                            segs.Add((i, foot));
                    }
                    TreeBuilder.RelaxOnGround(
                        nodesLocal, segs, flow.ToArray(), trunkTop.Count,
                        ground);
                    foreach ((int child, int foot) in segs)
                    {
                        members.Add(new Line(
                            nodesLocal[foot], nodesLocal[child]));
                        carried.Add(Math.Abs(trunkForce[child].Z));
                        trunkOff = Math.Max(
                            trunkOff,
                            AngleBetween(
                                nodesLocal[child] - nodesLocal[foot],
                                trunkForce[child]));
                    }
                    for (int i = trunkTop.Count; i < nodesLocal.Count; i++)
                        feet.Add(nodesLocal[i]);
                }

                if (branchOff > 5.0 || trunkOff > 5.0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        $"Members stand up to {Math.Max(branchOff, trunkOff):0.#} "
                            + "degrees off their own line of thrust: "
                            + $"{branchOff:0.#} on the branches, {trunkOff:0.#} "
                            + "on the trunks. A fork can only be in one place "
                            + "and a shared foot can only be under one point, "
                            + "so some of this is unavoidable; what is left is "
                            + "bending for the joints to take.");
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
                    columnType, branches, ground, alongToAnchors,
                    acrossToColumns, plumbArms, symmetricBars, symmetryCost,
                    lopsided));
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

        /// <summary>
        /// Which notches each main column reaches with its internal branches:
        /// the nearest ones along ITS OWN principal line that nothing else has
        /// taken.
        ///
        /// Claimed round by round rather than column by column, so a column
        /// standing beside a crowded neighbour is not left with none while that
        /// neighbour takes everything within reach. Anchors are never claimed:
        /// the ground already holds those.
        /// </summary>
        private static List<int>[] ClaimBranches(
            List<int> bar,
            Point3d[] nodes,
            List<int> chosen,
            HashSet<int> anchors,
            int branches)
        {
            var served = new List<int>[chosen.Count];
            for (int c = 0; c < chosen.Count; c++)
                served[c] = new List<int>();
            if (branches <= 0 || chosen.Count == 0)
                return served;

            var arc = new double[bar.Count];
            for (int k = 1; k < bar.Count; k++)
                arc[k] = arc[k - 1] + nodes[bar[k - 1]].DistanceTo(nodes[bar[k]]);

            var taken = new HashSet<int>(chosen);
            for (int k = 0; k < bar.Count; k++)
            {
                if (anchors.Contains(bar[k]))
                    taken.Add(k);
            }

            for (int round = 0; round < branches; round++)
            {
                for (int c = 0; c < chosen.Count; c++)
                {
                    int best = -1;
                    double closest = double.MaxValue;
                    for (int k = 0; k < bar.Count; k++)
                    {
                        if (taken.Contains(k))
                            continue;
                        double gap = Math.Abs(arc[k] - arc[chosen[c]]);
                        // ONLY within this column's own stretch of bar. Taking
                        // the nearest notch outright let a column reach past
                        // its neighbour to a notch on the far side of it, and
                        // the two columns' branches crossed over each other.
                        // Around the crown, where the columns crowd together,
                        // that is exactly the notch that looks nearest.
                        bool mine = true;
                        for (int o = 0; o < chosen.Count && mine; o++)
                        {
                            if (o == c)
                                continue;
                            if (Math.Abs(arc[k] - arc[chosen[o]]) < gap)
                                mine = false;
                        }
                        if (!mine)
                            continue;
                        if (gap < closest)
                        {
                            closest = gap;
                            best = k;
                        }
                    }
                    if (best < 0)
                        continue;       // this column has run out of its own bar
                    served[c].Add(best);
                    taken.Add(best);
                }
            }
            return served;
        }

        /// <summary>
        /// Split the columns into that many groups by where they stand in plan,
        /// so a shared foot gathers the ones actually near it. Furthest-first
        /// seeds then nearest assignment, the same shape the old clustering
        /// used, kept because it is deterministic.
        /// </summary>
        private static int[] GroupByPlan(List<Point3d> points, int groups)
        {
            var label = new int[points.Count];
            if (groups <= 1 || points.Count == 0)
                return label;

            var seeds = new List<int> { 0 };
            while (seeds.Count < groups && seeds.Count < points.Count)
            {
                int best = 0;
                double furthest = -1.0;
                for (int i = 0; i < points.Count; i++)
                {
                    double nearest = seeds.Min(
                        s => MouldGeometry.PlanDistanceSquared(
                            points[i], points[s]));
                    if (nearest > furthest)
                    {
                        furthest = nearest;
                        best = i;
                    }
                }
                seeds.Add(best);
            }

            for (int pass = 0; pass < 30; pass++)
            {
                for (int i = 0; i < points.Count; i++)
                {
                    int best = 0;
                    double closest = double.MaxValue;
                    for (int g = 0; g < seeds.Count; g++)
                    {
                        double d = MouldGeometry.PlanDistanceSquared(
                            points[i], points[seeds[g]]);
                        if (d < closest)
                        {
                            closest = d;
                            best = g;
                        }
                    }
                    label[i] = best;
                }
                bool moved = false;
                for (int g = 0; g < seeds.Count; g++)
                {
                    int[] mine = Enumerable.Range(0, points.Count)
                        .Where(i => label[i] == g).ToArray();
                    if (mine.Length == 0)
                        continue;
                    double cx = mine.Average(i => points[i].X);
                    double cy = mine.Average(i => points[i].Y);
                    int centre = mine
                        .OrderBy(i =>
                            ((points[i].X - cx) * (points[i].X - cx)) +
                            ((points[i].Y - cy) * (points[i].Y - cy)))
                        .First();
                    if (centre != seeds[g])
                    {
                        seeds[g] = centre;
                        moved = true;
                    }
                }
                if (!moved)
                    break;
            }
            return label;
        }

        /// <summary>The angle between two vectors, in degrees.</summary>
        private static double AngleBetween(Vector3d a, Vector3d b)
        {
            double la = a.Length;
            double lb = b.Length;
            if (la <= 1.0e-12 || lb <= 1.0e-12)
                return 0.0;
            double cosine =
                ((a.X * b.X) + (a.Y * b.Y) + (a.Z * b.Z)) / (la * lb);
            cosine = Math.Min(Math.Max(cosine, -1.0), 1.0);
            return Math.Acos(cosine) * 180.0 / Math.PI;
        }

        private static string Report(
            List<List<int>> bars,
            List<int> armsPerBar,
            List<double> headLoad,
            List<Line> members,
            List<double> force,
            List<double> angle,
            List<Point3d> feet,
            int columnType,
            int branches,
            double ground,
            double alongToAnchors,
            double acrossToColumns,
            int plumbArms,
            int symmetricBars,
            double symmetryCost,
            double lopsided)
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

            lines.Add(string.Empty);
            lines.Add(symmetricBars == bars.Count
                ? $"all {bars.Count} bars read as SYMMETRIC, so their arms are "
                    + "mirrored. On a discrete bar an asymmetric pair can droop "
                    + $"less, and here that was worth {symmetryCost * 100:0.#}%; "
                    + "it is refused, because that gain is the grid straddling "
                    + "the optimum, not a structural insight, and an arch is "
                    + "not built lopsided for it."
                : symmetricBars == 0
                    ? $"no bar reads as symmetric: the worst is {lopsided * 100:0.#}% "
                        + "off being a mirror of itself, against a 1% "
                        + "tolerance. The arms are placed freely, so they will "
                        + "not match side to side."
                    : $"{symmetricBars} of {bars.Count} bars read as symmetric "
                        + "and got mirrored arms; the rest are up to "
                        + $"{lopsided * 100:0.#}% off being mirrors of "
                        + "themselves and were placed freely.");

            if (plumbArms > 0)
            {
                lines.Add(string.Empty);
                lines.Add(
                    $"{plumbArms} arms stand PLUMB because the net pulls their "
                        + "notch down onto the column rather than off it, so "
                        + "there is no thrust line for them to follow. If that "
                        + "is ALL of them, the aiming is not working.");
            }

            lines.Add(columnType <= 0
                ? "Type 0: every column stands on its own foot, on the line of "
                    + "the force it carries."
                : $"Type {columnType}: the columns gather onto {columnType} "
                    + "ground point(s), each settled where the trunks meeting "
                    + "it balance.");
            lines.Add(branches <= 0
                ? "Branches 0: each column carries only its own notch."
                : $"Branches {branches}: each column reaches {branches} further "
                    + "notch(es) along its own principal line, and forks where "
                    + "those branches come closest to standing on their own "
                    + "lines of thrust. That height is SOLVED, not set.");

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

            // Is this bar symmetric? If it is, only mirrored arrangements
            // are allowed to win.
            //
            // The unrestricted search picks asymmetric arms on a symmetric bar
            // and is RIGHT to by its own measure: with stations a fortieth of
            // the span apart, neither 0.200 nor 0.225 is the optimum inset, and
            // one arm at each straddles it and droops less than either matched
            // pair. But that gain is a discretisation artefact. The continuous
            // optimum on a symmetric problem IS symmetric, and an arch built
            // with its columns in different places on the two halves is not
            // worth a few percent of droop. So the grid's trick is refused, and
            // the cost of refusing it is reported instead of hidden.
            int[] mirrorOf = MirrorMap(arc, load, coarse, out double lopsided);
            bool symmetric = mirrorOf.Length > 0;

            List<int>? best = null;
            double bestScore = double.MaxValue;
            List<int>? fallback = null;
            double fallbackScore = double.MaxValue;
            double freeScore = double.MaxValue;

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
                freeScore = Math.Min(freeScore, score);
                if (symmetric && !IsMirrored(combo, mirrorOf))
                    continue;
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
            LastSymmetric = symmetric;
            LastLopsided = lopsided;
            LastSymmetryCost = symmetric && freeScore > 0.0 && best is not null
                ? (bestScore - freeScore) / freeScore
                : 0.0;
            (double[]? d, double[]? r) = Response(arc, load, chosen.ToArray(), EI);
            double droop = d is null ? 0.0 : d.Select(Math.Abs).Max();
            List<int> arms = chosen.Where(k => !anchored.Contains(k)).ToList();
            return (arms, droop, r ?? new double[count]);
        }

        /// <summary>
        /// True when a station set is closed under mirroring, so the arms it
        /// describes fall in the same places on both halves of the bar.
        /// </summary>
        private static bool IsMirrored(int[] combo, int[] mirrorOf)
        {
            var set = new HashSet<int>(combo);
            foreach (int station in combo)
            {
                if (station < 0 || station >= mirrorOf.Length)
                    return false;
                if (!set.Contains(mirrorOf[station]))
                    return false;
            }
            return true;
        }

        /// <summary>
        /// Each coarse station's mirror about the middle of the bar, or an
        /// empty array when the bar is not symmetric enough to bother.
        ///
        /// Symmetry is judged on both the SHAPE and the LOAD, at one percent,
        /// which is loose enough for a solved mesh that is symmetric to solver
        /// precision and tight enough that a genuinely lopsided bar is left
        /// alone. The measured lopsidedness comes back either way, so a bar
        /// that just missed can be seen to have missed rather than silently
        /// treated as crooked.
        /// </summary>
        private static int[] MirrorMap(
            double[] arc,
            double[] load,
            int[] coarse,
            out double lopsided)
        {
            lopsided = 0.0;
            int n = arc.Length;
            double span = arc[n - 1];
            if (span <= 0.0 || n < 3)
                return Array.Empty<int>();
            double heaviest = Math.Max(load.Max(), 1.0e-12);

            // Does every station have a partner at span minus its own arc,
            // carrying the same load?
            for (int k = 0; k < n; k++)
            {
                double want = span - arc[k];
                int partner = 0;
                double closest = double.MaxValue;
                for (int j = 0; j < n; j++)
                {
                    double gap = Math.Abs(arc[j] - want);
                    if (gap < closest)
                    {
                        closest = gap;
                        partner = j;
                    }
                }
                lopsided = Math.Max(lopsided, closest / span);
                lopsided = Math.Max(
                    lopsided, Math.Abs(load[partner] - load[k]) / heaviest);
            }
            if (lopsided > 0.01)
                return Array.Empty<int>();

            var mirrorOf = new int[coarse.Length];
            for (int i = 0; i < coarse.Length; i++)
            {
                double want = span - arc[coarse[i]];
                int partner = 0;
                double closest = double.MaxValue;
                for (int j = 0; j < coarse.Length; j++)
                {
                    double gap = Math.Abs(arc[coarse[j]] - want);
                    if (gap < closest)
                    {
                        closest = gap;
                        partner = j;
                    }
                }
                mirrorOf[i] = partner;
            }
            return mirrorOf;
        }

        /// <summary>Whether the last bar solved was treated as symmetric.</summary>
        public static bool LastSymmetric { get; private set; }

        /// <summary>How far the last bar was from being a mirror of itself.</summary>
        public static double LastLopsided { get; private set; }

        /// <summary>
        /// What insisting on symmetry cost the last bar in peak droop, as a
        /// fraction of what the unrestricted search would have managed.
        /// </summary>
        public static double LastSymmetryCost { get; private set; }

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

    internal static class TreeBuilder
    {
        public static void RelaxOnGround(
            List<Point3d> nodes,
            List<(int, int)> segments,
            Vector3d[] flow,
            int fixedCount,
            double ground)
        {
            // The trunks' own forces are the weights; a foot carries whatever
            // reaches it, so its own entry stays empty and is never read as a
            // child.
            RelaxToForces(nodes, segments, flow, fixedCount, -1, ground);
            for (int i = fixedCount; i < nodes.Count; i++)
            {
                nodes[i] = new Point3d(nodes[i].X, nodes[i].Y, ground);
            }
        }

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
    }
}
