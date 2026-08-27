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
            parameters.AddNumberParameter(
                "Fork",
                "F",
                "Where a branching column forks, as a percent of its height off "
                    + "the ground. 0 forks at the foot, which makes a fan; 100 "
                    + "forks right under the notches. This is an ARCHITECTURAL "
                    + "choice and not a structural one, which is why it is an "
                    + "input: on a near-vertical set of columns the statics are "
                    + "degenerate, and both minimum material and minimum "
                    + "bending prefer the fan. A tree costs a little more and "
                    + "looks like a tree. Ignored when Branches is 0.",
                GH_ParamAccess.item,
                65.0);
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
            parameters[4].Optional = true;
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
            double forkPct = 65.0;
            int branches = 0;
            data.GetData(1, ref perLine);
            data.GetData(2, ref columnType);
            data.GetData(3, ref forkPct);
            data.GetData(4, ref branches);
            double forkHeight = Math.Min(Math.Max(forkPct, 0.0), 100.0) / 100.0;
            branches = Math.Max(branches, 0);
            // Type 0 stands every column on its own foot; anything else IS
            // the number of ground points they all gather onto.
            int sharedFeet = Math.Max(columnType, 0);
            perLine = Math.Max(perLine, 2);

            // Stiffness cancels out of the placement, so any positive value
            // gives the same arms. One keeps the arithmetic well conditioned.
            const double placementStiffness = 1.0;
            const double MaxLean = MouldGeometry.MaxLeanDegrees;

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
                int overlapping = 0;
                var barShape = new List<string>();

                // Two bars sharing notches are one bar traced twice, and each
                // would be given its own full set of columns. Say so: it is
                // invisible in the viewport and it makes everything downstream
                // look lopsided.
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
                                + "Each is being given its own full set of "
                                + "columns, which crowds them onto the one line "
                                + "at two different spacings and reads as "
                                + "lopsided. Check Ribs on Supports, or the "
                                + "curves on Pattern.");
                        a = bars.Count;
                        break;
                    }
                }

                // What each bar actually is. A principal line should run
                // from one anchor strip to the other, so BOTH its ends are
                // anchors and it holds as many notches as the mesh is wide.
                // A bar with one anchored end is half a line: it stops
                // somewhere in the middle, its beam is a cantilever, its arms
                // bunch toward the free end, and the midpoint it mirrors about
                // is a quarter point of the real arch. Nothing downstream can
                // recover from that, and none of it is visible in the viewport
                // because the bar draws the same either way.
                foreach (List<int> bar in bars)
                {
                    bool startTied = bar.Count > 0 && anchors.Contains(bar[0]);
                    bool endTied = bar.Count > 0 &&
                        anchors.Contains(bar[bar.Count - 1]);
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
                int centreAdded = 0;
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
                    if (BeamSolver.LastCentreAdded)
                        centreAdded++;
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
                double footDrift = 0.0;

                // Every column: its notches, the fork solved from their
                // forces, and a trunk down the line of what it all adds up to.
                var trunkTop = new List<Point3d>();
                var trunkForce = new List<Vector3d>();
                var trunkAim = new List<Vector3d>();
                // Where each fork sits on its main column's line, as a
                // fraction of the way up from the ground to the notch. Held as
                // the fraction rather than the point because a shared foot may
                // force it higher, and raising it is what steepens the trunk.
                var forkFraction = new List<double>();
                int forksRaised = 0;
                double raisedTo = 0.0;
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
                    //
                    // The branches are NOT drawn here. On a shared foot the
                    // fork may still have to be raised, below, to keep the
                    // trunk under its lean limit, and a branch drawn from a
                    // fork that then moves is a branch drawn to the wrong
                    // place. Forks are settled first, geometry second.
                    forkFraction.Add(reach.Count > 1 ? forkHeight : 1.0);
                    trunkTop.Add(reach.Count > 1
                        ? MouldGeometry.ForkOnLine(
                            reach[0],
                            MouldGeometry.AimFrom(-pushes[0]),
                            forkHeight,
                            ground)
                        : reach[0]);
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

                    // RAISE THE FORKS until the trunks stand within the lean
                    // limit.
                    //
                    // A standalone column drops on its own line of thrust, so
                    // its lean is chosen and ArmAim caps it at sixty degrees. A
                    // trunk to a SHARED foot has no such freedom: both its ends
                    // are already fixed, the foot at the shared centre and the
                    // top at the fork, so its lean is a consequence and it was
                    // going past eighty degrees unchecked. Past the cap a
                    // column pushes sideways more than it holds up and the
                    // sliding joint cannot reach the angle anyway.
                    //
                    // The one real lever is the FORK HEIGHT. Lifting a fork
                    // shortens the reach the trunk below it has to make and
                    // steepens it. Raising a fork moves it in plan as well,
                    // because it rides its main column's line, which moves the
                    // shared foot, which changes the leans; so this settles by
                    // repetition rather than in one pass. It converges because
                    // forks only ever move UP, and never past the notch, which
                    // is the point where the trunk simply is the column.
                    //
                    // A tree with no branches has no fork to raise. Nothing can
                    // be done for those here, and the report says so rather
                    // than pretending otherwise.
                    for (int pass = 0; pass < 12; pass++)
                    {
                        Point3d[] footFor = FeetForGroups(
                            trunkTop, group, wanted, ground);
                        bool moved = false;
                        for (int c = 0; c < trunkTop.Count; c++)
                        {
                            if (group[c] < 0 || forkFraction[c] >= 1.0)
                                continue;
                            Point3d foot = footFor[group[c]];
                            if (LeanFromVertical(foot, trunkTop[c]) <= MaxLean)
                                continue;

                            // The smallest raise that answers, found by
                            // stepping toward the notch. Deliberately the
                            // smallest: a fork lifted further than it needs to
                            // be is a shape nobody asked for.
                            double from = forkFraction[c];
                            double raised = 1.0;
                            for (int step = 1; step <= 24; step++)
                            {
                                double t = from + ((1.0 - from) * step / 24.0);
                                Point3d at = MouldGeometry.ForkOnLine(
                                    columnReach[c][0], trunkAim[c], t, ground);
                                if (LeanFromVertical(foot, at) <= MaxLean)
                                {
                                    raised = t;
                                    break;
                                }
                            }
                            if (raised <= from + 1.0e-9)
                                continue;
                            forkFraction[c] = raised;
                            trunkTop[c] = MouldGeometry.ForkOnLine(
                                columnReach[c][0], trunkAim[c], raised, ground);
                            raisedTo = Math.Max(raisedTo, raised);
                            moved = true;
                        }
                        if (!moved)
                            break;
                    }
                    forksRaised = Enumerable.Range(0, trunkTop.Count)
                        .Count(c => columnReach[c].Count > 1 &&
                            forkFraction[c] > forkHeight + 1.0e-9);
                    var nodesLocal = new List<Point3d>(trunkTop);
                    var segs = new List<(int, int)>();
                    var flow = new List<Vector3d>(trunkForce);
                    for (int g = 0; g < wanted; g++)
                    {
                        int[] mine = Enumerable.Range(0, trunkTop.Count)
                            .Where(i => group[i] == g).ToArray();
                        if (mine.Length == 0)
                            continue;
                        Point3d centre = SharedFoot(trunkTop, mine, ground);
                        double fx = 0.0;
                        double fy = 0.0;
                        double sw = 0.0;
                        foreach (int i in mine)
                        {
                            double w = Math.Max(
                                Math.Abs(trunkForce[i].Z), 1.0e-9);
                            fx += trunkTop[i].X * w;
                            fy += trunkTop[i].Y * w;
                            sw += w;
                        }
                        footDrift = Math.Max(
                            footDrift,
                            Math.Sqrt(MouldGeometry.PlanDistanceSquared(
                                centre, new Point3d(fx / sw, fy / sw, ground))));
                        nodesLocal.Add(centre);
                        flow.Add(Vector3d.Zero);
                        int foot = nodesLocal.Count - 1;
                        foreach (int i in mine)
                            segs.Add((i, foot));
                    }
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

                // THE BRANCHES, drawn last, from wherever each fork finished.
                // Held back until now because a fork raised to keep its trunk
                // within the lean limit takes its branches with it, and a
                // branch drawn from where the fork used to be would hang in
                // the air.
                for (int c = 0; c < columnReach.Count; c++)
                {
                    List<Point3d> reach = columnReach[c];
                    if (reach.Count <= 1)
                        continue;
                    Point3d fork = trunkTop[c];
                    for (int r = 0; r < reach.Count; r++)
                    {
                        if (reach[r].DistanceTo(fork) <= 1.0e-9)
                            continue;
                        members.Add(new Line(fork, reach[r]));
                        carried.Add(Math.Abs(columnForce[c][r].Z));
                        branchOff = Math.Max(
                            branchOff,
                            AngleBetween(
                                reach[r] - fork, columnForce[c][r]));
                    }
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
                    footPts, headPts, force, bars)));
                data.SetData(6, Report(
                    bars, armsPerBar, headLoad, members, force, angle, feet,
                    columnType, branches, forkPct, ground, alongToAnchors,
                    acrossToColumns, plumbArms, symmetricBars, symmetryCost,
                    lopsided, centreAdded, footDrift, overlapping, barShape,
                    forksRaised, raisedTo));
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
        /// Split the columns into that many groups for their shared feet.
        ///
        /// The groups must be CONTIGUOUS along the run of columns, or two
        /// trunks heading for different feet cross each other on the way down.
        /// Clustering by plan distance does not guarantee that and did not
        /// deliver it: near the crown, where the columns crowd, a column could
        /// be handed to a foot on the far side of its neighbour.
        ///
        /// So the columns are laid out along the line they actually run on,
        /// which is the first principal axis of where they stand in plan, and
        /// cut into blocks carrying roughly equal load. Contiguous by
        /// construction, so no two trunks can cross, and balanced so no foot
        /// takes far more than its share.
        /// </summary>
        private static int[] GroupByPlan(List<Point3d> points, int groups)
        {
            var label = new int[points.Count];
            if (groups <= 1 || points.Count == 0)
                return label;

            // The axis the columns run along: the direction in plan with the
            // most spread. Two sums are enough for that.
            double cx = points.Average(p => p.X);
            double cy = points.Average(p => p.Y);
            double sxx = 0.0;
            double syy = 0.0;
            double sxy = 0.0;
            foreach (Point3d p in points)
            {
                double dx = p.X - cx;
                double dy = p.Y - cy;
                sxx += dx * dx;
                syy += dy * dy;
                sxy += dx * dy;
            }
            double angle = 0.5 * Math.Atan2(2.0 * sxy, sxx - syy);
            double ax = Math.Cos(angle);
            double ay = Math.Sin(angle);

            // Equal bands by POSITION, not by count. Equal counts put the
            // band edges wherever the columns happen to fall, which is not
            // mirrored, so an odd number of feet gave no central foot and an
            // even number gave an off-centre pair. Equal bands about the middle
            // are symmetric by construction, so with an odd number one band is
            // centred on the middle and the rest come in mirrored pairs, and
            // the CENTRAL FOOT stands outside the pairing exactly as a central
            // column does.
            double lo = double.MaxValue;
            double hi = double.MinValue;
            var along = new double[points.Count];
            for (int i = 0; i < points.Count; i++)
            {
                along[i] = ((points[i].X - cx) * ax) + ((points[i].Y - cy) * ay);
                lo = Math.Min(lo, along[i]);
                hi = Math.Max(hi, along[i]);
            }
            double width = (hi - lo) / groups;
            if (width <= 1.0e-12)
                return label;
            for (int i = 0; i < points.Count; i++)
            {
                int band = (int)Math.Floor((along[i] - lo) / width);
                label[i] = Math.Min(Math.Max(band, 0), groups - 1);
            }

            // A band nobody stands in is not a foot. Close the gaps so the
            // count that comes out is the count that gets built.
            int[] present = label.Distinct().OrderBy(g => g).ToArray();
            var renumber = new Dictionary<int, int>();
            for (int i = 0; i < present.Length; i++)
                renumber[present[i]] = i;
            for (int i = 0; i < label.Length; i++)
                label[i] = renumber[label[i]];
            return label;
        }

        /// <summary>
        /// How far a member stands off vertical, in degrees.
        ///
        /// Measured from the two ends rather than from a force, because this
        /// is the question the sliding joint asks: not "is the column on its
        /// line of thrust" but "can the mechanism reach this angle".
        /// </summary>
        private static double LeanFromVertical(Point3d foot, Point3d top)
        {
            double rise = top.Z - foot.Z;
            double out2 = Math.Sqrt(
                MouldGeometry.PlanDistanceSquared(foot, top));
            if (rise <= 1.0e-9)
                return out2 <= 1.0e-9 ? 0.0 : 90.0;
            return Rhino.RhinoMath.ToDegrees(Math.Atan2(out2, rise));
        }

        /// <summary>
        /// The shared foot under each group, as one array indexed by group.
        ///
        /// Pulled out of the placement loop because the fork-raising pass has
        /// to ask the same question repeatedly, on tops that keep moving, and
        /// two copies of this rule would drift apart exactly where the last
        /// asymmetry lived.
        /// </summary>
        private static Point3d[] FeetForGroups(
            List<Point3d> tops,
            int[] group,
            int wanted,
            double ground)
        {
            var feet = new Point3d[Math.Max(wanted, 0)];
            for (int g = 0; g < wanted; g++)
            {
                int[] mine = Enumerable.Range(0, tops.Count)
                    .Where(i => group[i] == g).ToArray();
                feet[g] = mine.Length == 0
                    ? new Point3d(0.0, 0.0, ground)
                    : SharedFoot(tops, mine, ground);
            }
            return feet;
        }

        /// <summary>
        /// Where a shared foot stands: MIDWAY BETWEEN THE OUTERMOST columns it
        /// carries, not at their average.
        ///
        /// This is the whole of the Type 1 offset, and Param narrowed it to it:
        /// five columns or more and the one foot lands to one side, four or
        /// fewer and it is fine.
        ///
        /// An average is pulled by where the columns CROWD. With an even count
        /// the columns are mirrored pairs and the average happens to land dead
        /// centre, which is why four and under looked right. The moment there
        /// is a CENTRE COLUMN the count is odd, and a centre column sits on
        /// whichever notch is NEAREST the middle, which on a bar with no node
        /// exactly at its midpoint is half a bay off. That single unpaired
        /// column drags the average off by its own offset divided by the
        /// count, every time, in the same direction. Five columns, seven
        /// columns, or six with a centre added: all offset. Four: not.
        ///
        /// The midpoint of the outermost pair has no such weakness. Mirrored
        /// columns give mirrored extremes, so it is exactly centred however
        /// many there are and wherever the middle one sits, and it does not
        /// care how they crowd in between.
        /// </summary>
        private static Point3d SharedFoot(
            List<Point3d> tops,
            int[] members,
            double ground)
        {
            double minX = double.MaxValue;
            double maxX = double.MinValue;
            double minY = double.MaxValue;
            double maxY = double.MinValue;
            foreach (int i in members)
            {
                minX = Math.Min(minX, tops[i].X);
                maxX = Math.Max(maxX, tops[i].X);
                minY = Math.Min(minY, tops[i].Y);
                maxY = Math.Max(maxY, tops[i].Y);
            }
            return new Point3d(
                0.5 * (minX + maxX), 0.5 * (minY + maxY), ground);
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
            double forkPct,
            double ground,
            double alongToAnchors,
            double acrossToColumns,
            int plumbArms,
            int symmetricBars,
            double symmetryCost,
            double lopsided,
            int centreAdded,
            double footDrift,
            int overlapping,
            List<string> barShape,
            int forksRaised,
            double raisedTo)
        {
            var lines = new List<string>
            {
                overlapping > 0
                    ? $"WARNING: two principal lines share {overlapping} "
                        + "notches, so ONE bar is being traced twice and given "
                        + "two full sets of columns. Nothing below will look "
                        + "symmetric until that is fixed."
                    : "each principal line is distinct",
                string.Join(
                    Environment.NewLine,
                    barShape.Select((shape, i) => $"  bar {i}: {shape}")),
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
                        + "off being a mirror of itself in SHAPE, against a 2% "
                        + "tolerance. The arms are placed freely, so they will "
                        + "not match side to side."
                    : $"{symmetricBars} of {bars.Count} bars read as symmetric "
                        + "and got mirrored arms; the rest are up to "
                        + $"{lopsided * 100:0.#}% off being mirrors of "
                        + "themselves and were placed freely.");

            if (centreAdded > 0)
            {
                lines.Add(
                    $"{centreAdded} bars were given a CENTRE COLUMN on top of "
                        + "the count asked for, because the arms were already "
                        + "crowding the middle, which is the bar asking to be "
                        + "held there. A centre column has no mirror partner, "
                        + "so it stands outside the pairing rather than taking "
                        + "one of it and pushing everything to one side.");
            }
            if (footDrift > 0.0)
            {
                lines.Add(
                    $"a shared foot stands up to {footDrift:0.###} from the "
                        + "point where the trunks meeting it would balance. It "
                        + "sits at their GEOMETRIC centre instead, because the "
                        + "balance point is sensitive enough that ordinary "
                        + "solver noise moved it visibly off centre. That "
                        + "distance is the price, and it is horizontal thrust "
                        + "for the foundation.");
            }

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
                    + "notch(es) along its own principal line, never past a "
                    + $"neighbour, and forks at {forkPct:0}% of its height.");
            if (branches > 0)
            {
                lines.Add(
                    "the fork height is an ARCHITECTURAL choice, not a "
                        + "structural one, and it is an input for an honest "
                        + "reason: with the columns near vertical the statics "
                        + "are degenerate. A branch leaning less costs less "
                        + "bending AND less material, so both criteria run the "
                        + "fork all the way down to the foot and give a fan. "
                        + "Forking higher makes a tree and costs a little; how "
                        + "much is a decision, not a solve.");
            }

            if (headLoad.Count > 0)
                lines.Add($"arm load {headLoad.Min():0} to {headLoad.Max():0} N");
            if (force.Count > 0)
                lines.Add($"axial force up to {force.Max():0} N");
            if (angle.Count > 0)
            {
                lines.Add($"lean {angle.Min():0.#} to {angle.Max():0.#} degrees "
                    + "from vertical");
                if (angle.Max() > MouldGeometry.MaxLeanDegrees + 1.0e-6)
                {
                    lines.Add(
                        "WARNING: a column leans past "
                            + $"{MouldGeometry.MaxLeanDegrees:0} degrees, so it "
                            + "is pushing sideways more than it is holding up. "
                            + "A trunk on a shared foot is brought inside the "
                            + "limit by raising its fork; one still over it "
                            + "has no fork to raise, so give that column "
                            + "branches, or raise Type so each foot carries "
                            + "fewer columns.");
                }
            }
            if (forksRaised > 0)
            {
                lines.Add(
                    $"{forksRaised} "
                        + (forksRaised == 1 ? "fork was" : "forks were")
                        + " raised above the Fork setting, to "
                        + $"{raisedTo * 100.0:0}% at the highest, so their "
                        + "trunks stand within "
                        + $"{MouldGeometry.MaxLeanDegrees:0} degrees. A trunk "
                        + "to a shared foot has both ends fixed, so its lean "
                        + "is not a choice; lifting the fork shortens the "
                        + "reach below it and is the only lever there is.");
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

            // WHERE A STATION STANDS IN PLAN, which is what mirroring has to be
            // measured in.
            //
            // Arc length is how much bar has been travelled to reach a station,
            // and mirroring by it assumes the nodes are spread evenly. On a
            // mesh whose two ends are meshed differently, and they are whenever
            // the two anchor strips hold different numbers of nodes, they are
            // not: matching ARC puts a pair at matching distances along the bar
            // and at quite different places in space, which is not what a
            // mirrored pair looks like to anyone looking at it.
            var along = new double[count];
            Vector3d chord = nodes[bar[count - 1]] - nodes[bar[0]];
            double chordX = chord.X;
            double chordY = chord.Y;
            double chordLength = Math.Sqrt(
                (chordX * chordX) + (chordY * chordY));
            if (chordLength > 1.0e-12)
            {
                chordX /= chordLength;
                chordY /= chordLength;
                for (int k = 0; k < count; k++)
                {
                    along[k] =
                        ((nodes[bar[k]].X - nodes[bar[0]].X) * chordX) +
                        ((nodes[bar[k]].Y - nodes[bar[0]].Y) * chordY);
                }
            }
            else
            {
                Array.Copy(arc, along, count);
            }

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
            int[] mirrorOf = MirrorMap(along, coarse, out double lopsided);
            bool symmetric = mirrorOf.Length > 0;   // false only on a stub bar

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
            if (symmetric)
            {
                // Thinning the pool drops stations, and it drops them from the
                // two halves differently, so a kept station's mirror was often
                // no longer in the pool and no mirrored arrangement could be
                // built at all. Put every mirror back.
                pool = pool
                    .Concat(pool.Select(s => mirrorOf[s]))
                    .Where(s => !anchoredCoarse.Contains(s))
                    .Distinct()
                    .OrderBy(s => s)
                    .ToArray();
            }

            List<int>? best = null;
            double bestScore = double.MaxValue;
            List<int>? fallback = null;
            double fallbackScore = double.MaxValue;
            double freeScore = double.MaxValue;
            List<int>? centred = null;
            double centredScore = double.MaxValue;

            IEnumerable<int[]> candidates = symmetric
                ? Mirrored(pool, mirrorOf, coarse, along, perLine)
                : Combinations(pool, perLine);
            foreach (int[] combo in candidates)
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
                if (score < fallbackScore)
                {
                    fallbackScore = score;
                    fallback = full.ToList();
                }
                if (full.Any(s => reac[s] < -1e-6))
                    continue;                       // an arm cannot pull down

                // Kept apart, because the two families are not competing on
                // equal terms: one has an extra column in it.
                bool hasCentre = combo.Length > (perLine / 2) * 2;
                if (hasCentre)
                {
                    if (score < centredScore)
                    {
                        centredScore = score;
                        centred = full.ToList();
                    }
                }
                else if (score < bestScore)
                {
                    bestScore = score;
                    best = full.ToList();
                }
            }

            // Does the bar WANT a column on its centreline?
            //
            // Param's reading, and his trigger: an arch that needs holding at
            // midspan drags an arm inward to do it, and under mirroring that
            // arm's partner comes with it, so a pair ends up sitting on top of
            // the middle pretending to be two columns. Give it ONE REAL CENTRE
            // COLUMN instead and the pairs stay where they belong.
            //
            // So the trigger is the one he named: the centre being used. If the
            // best paired arrangement has put an arm within a station of the
            // middle, that is the bar asking, and it gets a centre on top of
            // the count rather than eating one of it. Deliberately NOT "when a
            // centre would reduce the droop": adding midspan support to a
            // uniformly loaded beam almost always does, so that fired on every
            // bar and quietly turned every even count odd.
            bool wantsCentre = (perLine % 2) == 1;
            if (!wantsCentre && centred is not null && best is not null)
            {
                // "The centre is being used" measured at the scale of the
                // COLUMNS, not of the mesh. One station is a fortieth of the
                // span, so the old threshold asked an arm to land almost
                // exactly on the middle before it counted, and it almost never
                // did: the pair would straddle the centre a few stations out,
                // crowding it plainly, and nothing fired.
                //
                // Half a bay is the honest scale. With N columns the bays are
                // about a span over N plus one, so an arm inside half of that
                // from the middle is standing where a centre column belongs.
                double middleAlong = 0.5 * along[count - 1];
                double bay = Math.Abs(along[count - 1]) / (perLine + 1);
                wantsCentre = best.Any(
                    s => Math.Abs(along[s] - middleAlong) <= 0.5 * bay);
            }
            LastCentreAdded = wantsCentre && (perLine % 2) == 0 &&
                centred is not null;
            if (wantsCentre && centred is not null)
            {
                best = centred;
                bestScore = centredScore;
            }

            if (symmetric && best is null && fallback is null)
            {
                // No mirrored arrangement fits, which happens on a very short
                // bar. Better a crooked answer than none, and the report says
                // which it was.
                symmetric = false;
                foreach (int[] combo in Combinations(pool, perLine))
                {
                    var supports = new SortedSet<int>(anchoredCoarse);
                    foreach (int c in combo)
                        supports.Add(c);
                    int[] full = supports.Select(s => coarse[s]).Distinct()
                        .OrderBy(s => s).ToArray();
                    if (full.Length < 2)
                        continue;
                    (double[]? d2, double[]? r2) =
                        Response(arc, load, full, EI);
                    if (d2 is null || r2 is null)
                        continue;
                    double s2 = d2.Select(Math.Abs).Max();
                    if (s2 < fallbackScore)
                    {
                        fallbackScore = s2;
                        fallback = full.ToList();
                    }
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
        /// Arrangements that are symmetric BY CONSTRUCTION: a centre column
        /// when an odd number is asked for, plus mirrored pairs.
        ///
        /// THE CENTRE COLUMN STANDS OUTSIDE THE PAIR COUNT, which is Param's
        /// own diagnosis of what was going wrong. A column on the centreline
        /// has no partner: it cannot be mirrored, so when it was counted like
        /// any other it left an odd number to divide between the two halves,
        /// one side took the extra, and everything else shifted to accommodate
        /// it. Asking for five now means a centre and two pairs, not two on one
        /// side and three on the other.
        ///
        /// Built rather than filtered, for the same reason. Generating every
        /// arrangement and keeping the mirrored ones needs a mirrored
        /// arrangement to exist in the first place, and after the pool is
        /// thinned it often does not. Choosing half the pairs from the left
        /// half and reflecting them cannot fail that way, and it searches a
        /// square root of the space, so more stations fit in the same budget.
        /// </summary>
        private static IEnumerable<int[]> Mirrored(
            int[] pool,
            int[] mirrorOf,
            int[] coarse,
            double[] along,
            int perLine)
        {
            double middle = 0.5 * along[along.Length - 1];

            // The one station that may stand alone, because it is its own
            // mirror: whichever sits nearest the middle.
            int centre = -1;
            double closest = double.MaxValue;
            foreach (int station in pool)
            {
                double gap = Math.Abs(along[coarse[station]] - middle);
                if (gap < closest)
                {
                    closest = gap;
                    centre = station;
                }
            }

            int pairs = perLine / 2;
            if (pairs == 0)
            {
                if (centre >= 0)
                    yield return new[] { centre };
                yield break;
            }

            // A station whose MIRROR is not itself usable cannot be half of
            // a pair.
            //
            // This is the asymmetry Param saw as "one side always getting one
            // node short of the other", and it was in this method. The pool
            // excludes anchored stations, but the mirror was taken straight
            // from the map without checking it against the pool. When it landed
            // on an anchor, that half of the pair was an anchor: it went into
            // the arrangement, and then dropped out again when the arms were
            // separated from the anchors, because an anchor holds the bar
            // without costing an arm. What came back was a lone column on one
            // side with no partner on the other, and a count one short of what
            // was asked for. The report showed it plainly, as six asked for and
            // five delivered, on both bars.
            var usable = new HashSet<int>(pool);
            int[] left = pool
                .Where(s => along[coarse[s]] < middle - 1.0e-9 &&
                    s != centre &&
                    usable.Contains(mirrorOf[s]) &&
                    mirrorOf[s] != s)
                .ToArray();
            if (left.Length < pairs)
                yield break;

            // BOTH, with and without the middle. An odd count needs the centre
            // to make up its number; an even count does not, but the bar may
            // still want one, and whether it does is a question for the beam
            // rather than for the arithmetic of the count. The caller compares
            // them and keeps the centre only when it earns its place.
            foreach (int[] half in Combinations(left, pairs))
            {
                if (half.Length != pairs)
                    continue;
                var paired = new List<int>(perLine + 1);
                foreach (int station in half)
                {
                    paired.Add(station);
                    paired.Add(mirrorOf[station]);
                }
                yield return paired.Distinct().ToArray();
                if (centre >= 0)
                {
                    var withCentre = new List<int>(paired) { centre };
                    yield return withCentre.Distinct().ToArray();
                }
            }
        }

        /// <summary>
        /// Each coarse station's mirror about the middle of the bar, or an
        /// empty array when the bar is not symmetric enough to bother.
        ///
        /// Each station's partner across the middle of the bar: whichever
        /// station stands nearest the same arc length measured from the other
        /// end.
        ///
        /// ALWAYS RETURNED, never refused. This was a test twice, and both
        /// times the test was what went wrong rather than the rule behind it.
        /// First it demanded the LOAD mirror to one percent, which no solved
        /// net's does. Then it demanded the SHAPE mirror to two percent, which
        /// a run one node short at one end cannot manage. Each time the answer
        /// was a silent fall back to free placement: the columns came out
        /// crooked and nothing said why.
        ///
        /// A gate that fails closed and says nothing is worse than no gate. So
        /// there is none. Every bar is mirrored about its own midpoint, which
        /// on a symmetric bar is exactly right and on a crooked one is the best
        /// its own geometry allows. How far it is from being a mirror of itself
        /// is measured and reported, so the reading is available without being
        /// load-bearing.
        /// </summary>
        private static int[] MirrorMap(
            double[] along,
            int[] coarse,
            out double lopsided)
        {
            lopsided = 0.0;
            int n = along.Length;
            double span = along[n - 1];
            if (Math.Abs(span) <= 1.0e-12 || n < 3)
                return Array.Empty<int>();

            // Does every station have a partner at span minus its own arc?
            for (int k = 0; k < n; k++)
            {
                double want = span - along[k];
                int partner = 0;
                double closest = double.MaxValue;
                for (int j = 0; j < n; j++)
                {
                    double gap = Math.Abs(along[j] - want);
                    if (gap < closest)
                    {
                        closest = gap;
                        partner = j;
                    }
                }
                lopsided = Math.Max(lopsided, closest / Math.Abs(span));
            }
            var mirrorOf = new int[coarse.Length];
            for (int i = 0; i < coarse.Length; i++)
            {
                double want = span - along[coarse[i]];
                int partner = 0;
                double closest = double.MaxValue;
                for (int j = 0; j < coarse.Length; j++)
                {
                    double gap = Math.Abs(along[coarse[j]] - want);
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

        /// <summary>
        /// Whether the last bar was given a centre column it did not ask for,
        /// because holding it at midspan was worth an extra one.
        /// </summary>
        public static bool LastCentreAdded { get; private set; }

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
}
