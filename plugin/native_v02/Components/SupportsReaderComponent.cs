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
    /// Supports: what the ground sees, anchors and columns.
    ///
    /// One of Monitor's three children. Every anchor output is branched by
    /// support strip exactly as Deconstruct's Reaction Points, and every
    /// column output by column tree exactly as Frame's Columns, because this
    /// reads the same <see cref="ResultTables"/> rows and the block's own
    /// Trees in the same order.
    ///
    /// The CLASS is SupportsReaderComponent because the 01 Model panel
    /// already has a SupportsComponent; the canvas name is the spec's,
    /// Supports.
    ///
    /// Every force here is in THE RESULT'S OWN FORCE UNIT, kN unless the
    /// Result says otherwise. Column Capacity is newtons, so the one place
    /// the two meet, the column utilisation, converts through
    /// <see cref="MonitorMath.ToNewtons"/> and nowhere else. Every force
    /// here is a DEMAND; utilisation is the only verdict, and only against
    /// a capacity the author supplies.
    /// </summary>
    public sealed class SupportsReaderComponent : NativeComponentBase
    {
        public SupportsReaderComponent()
            : base(
                "Supports",
                "SP",
                "What the ground sees: each anchor's reaction split along "
                    + "its tensioner axis and across it (the across part is "
                    + "the anchorage's), the tip reaction under every column "
                    + "head, the column demands, thrusts and leans, and the "
                    + "column utilisation against a capacity you wire. "
                    + "Anchor trees align with Deconstruct's Reaction Points "
                    + "and column trees with Frame's Columns. Forces are in "
                    + "the Result's own force unit, kN unless it says "
                    + "otherwise, converted to newtons where they meet "
                    + "Column Capacity. Demands only, unless a capacity is "
                    + "wired.",
                ComponentCategories.Read,
                "supports")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("3d99b855-4c2e-4d03-94ec-f695f21f86cc");

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
                "Column Capacity",
                "CO",
                "Allowable compression in one column member, in NEWTONS "
                    + "whatever unit the Result's own forces are in, exactly "
                    + "as FORCES' Cable Capacity. Wired, Column Utilisation "
                    + "is filled with the force over this. Left alone it "
                    + "stays empty.",
                GH_ParamAccess.item,
                0.0);
            for (int slot = 1; slot < parameters.ParamCount; slot++)
                parameters[slot].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "The Result passed through with Supports' own diagnostics "
                    + "replacing its earlier ones: column force, foundation "
                    + "thrust, the anchor split and the column utilisation. "
                    + "Chain it through Forces and Fit in any order; each "
                    + "child replaces only its own entries. Wire it to "
                    + "Diagnose.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Anchor Along",
                "AA",
                "The part of each anchor's reaction acting ALONG its tensioner "
                    + "axis, in the Result's force unit (kN unless the Result "
                    + "says otherwise), positive along that axis: the pull the "
                    + "tensioner itself takes. The axis is the unit mean "
                    + "direction of the members leaving the anchor into the "
                    + "net, and document 07's legs are these anchors. As a "
                    + "TREE branched EXACTLY as DECONSTRUCT's Reaction Points: "
                    + "one branch per connected strip of supports, item for "
                    + "item.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Anchor Across",
                "AX",
                "What is left of the reaction once the along part is taken "
                    + "out, as a magnitude in the same unit as Anchor Along. "
                    + "This is what the ANCHORAGE has "
                    + "to carry, because a tensioner can only pull along its "
                    + "own axis. Branched exactly as Anchor Along.",
                GH_ParamAccess.tree);
            parameters.AddVectorParameter(
                "Tip Reaction",
                "TR",
                "The axial force of the member under each column head, as a "
                    + "vector along that member pointing UP into the head, in "
                    + "the Result's force unit (kN unless the Result says "
                    + "otherwise). It comes from the block's own member forces "
                    + "and not "
                    + "from a solver's node reactions, because the columns are "
                    + "solved as a block upstream. As a TREE with one branch "
                    + "per column tree, the same tree as FRAME's Columns "
                    + "branch {b}, heads in the order that tree's members are "
                    + "walked. Measured at the frame the Result carries, "
                    + "exactly as FRAME's Columns are drawn.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Column Force",
                "CF",
                "Axial demand in each column member, in the Result's force "
                    + "unit (kN unless the Result says otherwise). As a TREE "
                    + "with one branch per column tree, members in the "
                    + "block's own order, the same tree as FRAME's Columns "
                    + "branch {b}. Measured at the frame the Result carries.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Thrust",
                "TH",
                "The horizontal force in each column member, in the Result's "
                    + "force unit (kN unless the Result says otherwise): the "
                    + "part of a leaning member's axial force that acts "
                    + "sideways. A "
                    + "plumb member reads zero. Only the members STANDING ON "
                    + "THE GROUND put theirs into the foundation, and the "
                    + "supports.thrust_into_ground diagnostic sums those alone; "
                    + "a branch's horizontal is balanced at its junction by "
                    + "its siblings. Branched exactly as Column Force, and "
                    + "measured at the frame the Result carries.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Lean",
                "LN",
                "Degrees from vertical per column member, branched exactly as "
                    + "Column Force. Past sixty a member pushes sideways more "
                    + "than it holds up. Measured at the frame the Result "
                    + "carries.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Column Utilisation",
                "CLU",
                "The ABSOLUTE FORCE OVER CAPACITY per column member, the "
                    + "magnitude of the force in NEWTONS over Column "
                    + "Capacity, branched exactly "
                    + "as Column Force. A utilisation is a magnitude ratio, so "
                    + "the sign of the member force is not in it. The block's "
                    + "member force is in the net's own unit and is converted "
                    + "to newtons first, exactly as FORCES' Cable "
                    + "Utilisation. EMPTY "
                    + "unless Column Capacity is wired, and empty when the "
                    + "Result's force unit is neither N nor kN.",
                GH_ParamAccess.tree);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }

            double columnCapacity = 0.0;
            data.GetData(1, ref columnCapacity);

            try
            {
                Readings r = Read(result, columnCapacity);
                data.SetData(0, new ResultGoo(r.Result));
                data.SetDataTree(1, OutputTree.Numbers(r.AnchorAlong));
                data.SetDataTree(2, OutputTree.Numbers(r.AnchorAcross));
                data.SetDataTree(3, OutputTree.Vectors(r.TipReaction));
                data.SetDataTree(4, OutputTree.Numbers(r.ColumnForce));
                data.SetDataTree(5, OutputTree.Numbers(r.Thrust));
                data.SetDataTree(6, OutputTree.Numbers(r.Lean));
                data.SetDataTree(7, OutputTree.Numbers(r.EmitColumnUtilisation
                    ? r.ColumnUtilisation
                    : Enumerable.Empty<IEnumerable<double>>()));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        /// <summary>
        /// Everything Supports computes, in one record, so the smoke harness
        /// can drive the same code path the canvas runs without a Rhino.
        /// <see cref="SolveInstance"/> is a thin shell over <see cref="Read"/>.
        /// </summary>
        internal sealed record Readings(
            ResultDto Result,
            List<List<double>> AnchorAlong,
            List<List<double>> AnchorAcross,
            List<List<Vector3d>> TipReaction,
            List<List<double>> ColumnForce,
            List<List<double>> Thrust,
            List<List<double>> Lean,
            List<List<double>> ColumnUtilisation,
            bool EmitColumnUtilisation);

        internal static Readings Read(ResultDto result, double columnCapacity)
        {
            IReadOnlyList<string> errors = result.Validate();
            if (errors.Count > 0)
                throw new InvalidOperationException(string.Join(" ", errors));

            EquilibriumResultDto equilibrium = result.Equilibrium!;
            MouldDto? mould = result.Mould;
            MouldColumnsDto? block = mould?.Columns;
            MouldFrameDto? frame = mould?.Frame;

            int n = equilibrium.Vertices.Count;
            // The live net when a frame is present, the solved one
            // otherwise. Validation already refuses a frame with the wrong
            // vertex count; testing the count here as well is what lets
            // every net index below be checked once, against n, and never
            // against two different lengths.
            IReadOnlyList<Point3Dto> source =
                frame?.Vertices is IReadOnlyList<Point3Dto> live && live.Count == n
                    ? live
                    : equilibrium.Vertices;
            Point3d[] v = source.Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray();

            (int, int)[] edges = MouldGeometry.ValidEdges(equilibrium, n, out _);

            // The unit rule is Forces' rule, read the same way: Column
            // Capacity is newtons whatever the Result's unit, so a kN force
            // is converted before the division and an unknown unit publishes
            // no utilisation, with supports.utilisation naming the unit.
            string declaredUnit = (equilibrium.ForceUnit ?? string.Empty).Trim();
            string forceUnit = declaredUnit.Length > 0 ? declaredUnit : "kN";
            double? scale = MonitorMath.ToNewtons(forceUnit);
            bool forceUnitKnown = scale.HasValue;
            double toNewtons = scale ?? 1.0;
            bool columnRatio = columnCapacity > 0.0 && forceUnitKnown;

            // ---- anchors ------------------------------------------------
            // Exactly Deconstruct's calls: the same support ids, the same
            // grouping adjacency over the plan unioned with the solved net,
            // the same connected strips. The tensioner axis needs the net's
            // OWN adjacency instead, because it asks which members leave
            // the anchor pulling, and a plan edge pulls on nothing.
            int[] nodeIds = ResultTables.SupportNodes(result);
            List<int>[] grouping = MouldGeometry.GroupingAdjacency(
                result, edges, n);
            List<List<int>> strips = MouldGeometry.ConnectedGroups(
                nodeIds, grouping);
            List<int>[] adjacency = MouldGeometry.BuildAdjacency(n, edges);
            (int Node, Vector3d Vector)[] reactions = ResultTables.Reactions(result)
                .Where(item => item.Node >= 0 && item.Node < n)
                .ToArray();
            var reactionAt = new Dictionary<int, Vector3d>();
            foreach ((int node, Vector3d vector) in reactions)
                reactionAt[node] = vector;

            // An anchor whose net-adjacent nodes are ALL supports has no
            // net edge at all: a TNA analysis topology carries none
            // between two fixed nodes, because such an edge contributes
            // no unknown. Defaulting to vertical there would report the
            // vertical reaction as the tensioner's pull and the whole
            // horizontal as the anchorage's, which is the exact opposite
            // of what a side tie does. The grouping adjacency, which
            // unions the pattern's own edges in, carries the strip
            // direction, and that is what a perimeter tensioner pulls
            // along. Counted, because a number nobody can check should
            // not pass unremarked.
            int axisFromStrip = 0;
            Vector3d AxisAt(int node)
            {
                bool onTheNet =
                    node >= 0 &&
                    node < adjacency.Length &&
                    adjacency[node].Count > 0;
                if (onTheNet)
                    return MonitorMath.TensionerAxis(node, v, adjacency);
                axisFromStrip++;
                return MonitorMath.TensionerAxis(node, v, grouping);
            }

            var alongBranches = new List<List<double>>();
            var acrossBranches = new List<List<double>>();
            var anchorReaction = new List<Vector3d>();
            foreach (List<int> strip in strips)
            {
                var along = new List<double>();
                var across = new List<double>();
                foreach (int id in strip)
                {
                    Vector3d reaction = reactionAt.TryGetValue(id, out Vector3d found)
                        ? found
                        : Vector3d.Zero;
                    (double a, double x) = MonitorMath.AnchorSplit(
                        reaction, AxisAt(id));
                    along.Add(a);
                    across.Add(x);
                    anchorReaction.Add(reaction);
                }
                alongBranches.Add(along);
                acrossBranches.Add(across);
            }

            // Deconstruct gives a reaction sitting on no strip a trailing
            // branch of its own rather than losing it. Mirrored here, or
            // the branch counts would part company on exactly the Result
            // that most needs reading.
            var onAStrip = new HashSet<int>(strips.SelectMany(s => s));
            var strayAlong = new List<double>();
            var strayAcross = new List<double>();
            foreach ((int node, Vector3d vector) in reactions)
            {
                if (onAStrip.Contains(node))
                    continue;
                (double a, double x) = MonitorMath.AnchorSplit(
                    vector, AxisAt(node));
                strayAlong.Add(a);
                strayAcross.Add(x);
                anchorReaction.Add(vector);
            }
            if (strayAlong.Count > 0)
            {
                alongBranches.Add(strayAlong);
                acrossBranches.Add(strayAcross);
            }

            // ---- columns ------------------------------------------------
            // Branched by the block's own Trees, which is what
            // DeconstructComponent.ColumnTrees branches by, skipping a
            // member on exactly the same two tests and taking the heads in
            // the same first-seen order. Any other grouping here, a
            // fallback included, would put a number in a branch
            // Frame's Columns never drew.
            var tipReaction = new List<List<Vector3d>>();
            var columnForceBranches = new List<List<double>>();
            var thrustBranches = new List<List<double>>();
            var leanBranches = new List<List<double>>();
            var columnUtilBranches = new List<List<double>>();
            var standsOnGround = new List<bool>();
            bool columnFrameAbsent = false;
            if (block is not null)
            {
                // MouldFrameDto.Validate only checks ColumnNodes when it
                // carries them, so a Result with columns and a frame that
                // names no column nodes validates, and every column number
                // below is then the BUILT state's under four port
                // descriptions that each say "measured at the frame".
                // Animate always writes them, so this needs an imported
                // Result; it is still said out loud rather than assumed
                // away.
                columnFrameAbsent = frame is not null && frame.ColumnNodes is null;
                // Length-matched to the block's own nodes, so the range
                // test below is the tree walk's range test and not a second
                // one over a different array.
                IReadOnlyList<Point3Dto> columnSource =
                    frame?.ColumnNodes is IReadOnlyList<Point3Dto> liveNodes &&
                    liveNodes.Count == block.Nodes.Count
                        ? liveNodes
                        : block.Nodes;
                Point3d[] cn = columnSource
                    .Select(p => new Point3d(p.X, p.Y, p.Z))
                    .ToArray();
                var headSet = new HashSet<int>(block.Heads);
                var footSet = new HashSet<int>(block.Feet);
                // Members run lower end first always, so the member UNDER a
                // head is the one whose upper end is that head. This
                // block-wide map is the LAST resort: two members can share
                // an upper node, MouldColumnsDto.Validate permits it, and
                // a first-by-index winner would report one tree's member
                // as the other tree's tip reaction while the tree walk
                // correctly drew the head in both branches. The
                // group's own map is asked first, below.
                var under = new Dictionary<int, int>();
                for (int m = 0; m < block.Members.Count; m++)
                {
                    if (!under.ContainsKey(block.Members[m].V))
                        under[block.Members[m].V] = m;
                }
                Vector3d Tip(int head, IReadOnlyDictionary<int, int> inGroup)
                {
                    if (!inGroup.TryGetValue(head, out int m) &&
                        !under.TryGetValue(head, out m))
                    {
                        return Vector3d.Zero;
                    }
                    EdgeDto member = block.Members[m];
                    if (member.U < 0 || member.U >= cn.Length ||
                        member.V < 0 || member.V >= cn.Length)
                    {
                        return Vector3d.Zero;
                    }
                    Vector3d d = cn[member.V] - cn[member.U];
                    double length = d.Length;
                    double axial = m < block.MemberForce.Count
                        ? block.MemberForce[m]
                        : 0.0;
                    return length > 1.0e-12 ? (d / length) * axial : Vector3d.Zero;
                }

                foreach (IReadOnlyList<int> group in block.Trees)
                {
                    // The member under a head, resolved WITHIN the tree
                    // that is emitting the head. Built in a pass of its
                    // own because Tip is called while the members are
                    // being walked, and the head can be the upper end of a
                    // member the walk has not reached yet.
                    var underHere = new Dictionary<int, int>();
                    foreach (int m in group)
                    {
                        if (m < 0 || m >= block.Members.Count)
                            continue;
                        if (!underHere.ContainsKey(block.Members[m].V))
                            underHere[block.Members[m].V] = m;
                    }
                    var tips = new List<Vector3d>();
                    var force = new List<double>();
                    var thrust = new List<double>();
                    var lean = new List<double>();
                    var utilisation = new List<double>();
                    var seen = new HashSet<int>();
                    foreach (int m in group)
                    {
                        if (m < 0 || m >= block.Members.Count)
                            continue;
                        EdgeDto member = block.Members[m];
                        if (member.U < 0 || member.U >= cn.Length ||
                            member.V < 0 || member.V >= cn.Length)
                        {
                            continue;
                        }
                        double axial = m < block.MemberForce.Count
                            ? block.MemberForce[m]
                            : 0.0;
                        Vector3d d = cn[member.V] - cn[member.U];
                        double length = d.Length;
                        double plan = Math.Sqrt((d.X * d.X) + (d.Y * d.Y));
                        force.Add(axial);
                        thrust.Add(length > 1.0e-12 ? axial * plan / length : 0.0);
                        lean.Add(length > 1.0e-12
                            ? Rhino.RhinoMath.ToDegrees(
                                Math.Atan2(plan, Math.Abs(d.Z)))
                            : 0.0);
                        // The block's member force is in the NET's unit,
                        // so it takes the same conversion the cables take.
                        if (columnRatio)
                        {
                            utilisation.Add(
                                Math.Abs(axial) * toNewtons / columnCapacity);
                        }
                        // A member stands on the ground when its lower end
                        // is a foot in the block, by index; no height test.
                        standsOnGround.Add(footSet.Contains(member.U));
                        // Heads in the order ColumnTrees emits them: an end
                        // seen for the first time while the group's members
                        // are walked, U before V.
                        foreach (int end in new[] { member.U, member.V })
                        {
                            if (!seen.Add(end))
                                continue;
                            if (headSet.Contains(end))
                                tips.Add(Tip(end, underHere));
                        }
                    }
                    tipReaction.Add(tips);
                    columnForceBranches.Add(force);
                    thrustBranches.Add(thrust);
                    leanBranches.Add(lean);
                    columnUtilBranches.Add(utilisation);
                }
            }

            ResultDto annotated = ResultDiagnostics.Replace(
                result, "Supports", Diagnostics(
                    frame: frame,
                    columnForce: columnForceBranches.SelectMany(b => b).ToList(),
                    thrust: thrustBranches.SelectMany(b => b).ToList(),
                    standsOnGround: standsOnGround,
                    anchorReaction: anchorReaction,
                    anchorAcross: acrossBranches.SelectMany(b => b).ToList(),
                    columnUtilisation: columnRatio
                        ? columnUtilBranches.SelectMany(b => b).ToList()
                        : new List<double>(),
                    axisFromStrip: axisFromStrip,
                    columnFrameAbsent: columnFrameAbsent,
                    forceUnit: forceUnit,
                    forceUnitKnown: forceUnitKnown));

            return new Readings(
                annotated,
                alongBranches,
                acrossBranches,
                tipReaction,
                columnForceBranches,
                thrustBranches,
                leanBranches,
                columnUtilBranches,
                columnRatio);
        }

        private static List<DiagnosticDto> Diagnostics(
            MouldFrameDto? frame,
            List<double> columnForce,
            List<double> thrust,
            List<bool> standsOnGround,
            List<Vector3d> anchorReaction,
            List<double> anchorAcross,
            List<double> columnUtilisation,
            int axisFromStrip,
            bool columnFrameAbsent,
            string forceUnit,
            bool forceUnitKnown)
        {
            const string S = "Supports";
            var d = new List<DiagnosticDto>();

            if (columnForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "supports.column_force", "info",
                    $"column compression {columnForce.Min():0} to "
                        + $"{columnForce.Max():0} {forceUnit}, carrying "
                        + $"{columnForce.Sum():0} {forceUnit} in total",
                    columnForce.Max(), unit: forceUnit,
                    context: ResultDiagnostics.Context(("total", columnForce.Sum().ToString("0", CultureInfo.InvariantCulture)))));
                // Only the FEET push on the ground. A branch inside a tree leans
                // too, but its horizontal is balanced at the junction by its
                // siblings.
                double[] footThrust = thrust
                    .Where((_, index) => index < standsOnGround.Count && standsOnGround[index])
                    .ToArray();
                d.Add(footThrust.Length == 0
                    ? ResultDiagnostics.Entry(S, "supports.thrust_into_ground", "info",
                        "no member reaches the ground in this state, so there is no "
                            + "foundation thrust to report.", 0.0, unit: forceUnit)
                    : ResultDiagnostics.Entry(S, "supports.thrust_into_ground", "info",
                        $"horizontal thrust at the {footThrust.Length} feet up to "
                            + $"{footThrust.Max():0} {forceUnit}, "
                            + $"{footThrust.Sum():0} {forceUnit} summed. This "
                            + "is what the ground has to resist sideways, and it is the "
                            + "price of leaning the arms."
                            + (frame is not null && frame.Time < 100.0 - 1.0e-9
                                // The direction is the frame's and the force is
                                // the finished state's, so the product is not
                                // yet a foundation demand. At frame zero the
                                // trunks lie flat along their rails and every
                                // member reads its whole axial force as
                                // horizontal, which is a number worth stating
                                // but not worth asserting as fact.
                                ? " At this frame the DIRECTION is this frame's and the "
                                    + "FORCE is the finished state's, so that figure is "
                                    + "what the ground would see if the finished force "
                                    + "acted along this frame's lean, not what it is "
                                    + "carrying now."
                                : string.Empty),
                        footThrust.Max(), unit: forceUnit,
                        context: ResultDiagnostics.Context(
                            ("feet", footThrust.Length.ToString(CultureInfo.InvariantCulture)),
                            ("sum", footThrust.Sum().ToString("0", CultureInfo.InvariantCulture)))));
            }
            else
            {
                d.Add(ResultDiagnostics.Entry(S, "supports.no_columns", "info",
                    "no columns on this Result: wire Columns upstream to see what "
                        + "they carry."));
            }
            if (anchorReaction.Count > 0)
            {
                double worst = anchorReaction
                    .Select(a => Math.Sqrt((a.X * a.X) + (a.Y * a.Y)))
                    .DefaultIfEmpty(0.0)
                    .Max();
                d.Add(ResultDiagnostics.Entry(S, "supports.anchor_horizontal", "info",
                    $"anchor pull up to {worst:0} {forceUnit} horizontally: the side "
                        + "ties hold the perimeter cables against exactly this.",
                    worst, unit: forceUnit));
            }
            if (anchorAcross.Count > 0)
            {
                double worstAcross = anchorAcross.Max();
                double total = anchorReaction.Sum(a => a.Length);
                double share = total > 1.0e-9 ? anchorAcross.Sum() / total : 0.0;
                d.Add(ResultDiagnostics.Entry(S, "supports.anchor_split", "info",
                    $"the worst anchor puts {worstAcross:0} {forceUnit} ACROSS its "
                        + "tensioner, and "
                        + $"{share * 100.0:0.#} percent of all the anchor pull is across "
                        + "rather than along. A tensioner can only pull along its own "
                        + "axis, so that share is the anchorage's to carry."
                        + (axisFromStrip > 0
                            ? $" {axisFromStrip} anchors have no member of the solved net "
                                + "leaving them, so their axis was read from the strip "
                                + "the pattern joins them into rather than from the net."
                            : string.Empty),
                    worstAcross, unit: forceUnit,
                    context: ResultDiagnostics.Context(
                        ("share", share.ToString("0.###", CultureInfo.InvariantCulture)),
                        ("axis_from_strip",
                            axisFromStrip.ToString(CultureInfo.InvariantCulture)))));
            }
            if (columnFrameAbsent)
            {
                d.Add(ResultDiagnostics.Entry(S, "supports.column_frame_absent", "info",
                    "this frame carries no column nodes, so the column numbers here "
                        + "are read at the BUILT state while the net is read at the "
                        + "frame. Column Force, Thrust, Lean and Tip Reaction each say "
                        + "they are measured at the frame; on this Result they are "
                        + "not."));
            }

            if (!forceUnitKnown)
            {
                // Dividing a force in an unknown unit by a capacity in newtons
                // is a ratio between two things, not a utilisation. The number
                // is refused rather than published with a caveat, because the
                // caveat would not travel with the number.
                d.Add(ResultDiagnostics.Entry(S, "supports.utilisation", "warning",
                    $"this Result's forces are in '{forceUnit}', which is neither N "
                        + "nor kN, so no column utilisation is reported: Column "
                        + "Capacity is newtons and there is nothing here to convert "
                        + "that unit with. Every force stays a demand, not a "
                        + "verdict."));
            }
            else if (columnUtilisation.Count == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "supports.utilisation", "info",
                    "no column member is checked against a capacity, either because "
                        + "Column Capacity is not wired or because this Result "
                        + "carries no columns, so every figure here is a DEMAND, NOT "
                        + "A VERDICT. Wire Column Capacity to turn the column forces "
                        + "into utilisations."));
            }
            else
            {
                double worstColumn = columnUtilisation.Max();
                // Both units named, because this is the one figure on the
                // component that mixes them: the forces are the Result's and
                // the capacity is the author's, in newtons.
                string denominated = string.Equals(
                    forceUnit, "N", StringComparison.OrdinalIgnoreCase)
                    ? " The forces and the capacity are both in N."
                    : $" The forces are in {forceUnit}, converted to N against "
                        + "the capacity you supplied, which is in N.";
                d.Add(ResultDiagnostics.Entry(S, "supports.utilisation",
                    worstColumn > 1.0 ? "warning" : "info",
                    $"utilisation column up to {worstColumn:0.###}"
                        + (worstColumn > 1.0
                            ? ". Above one a member is OVER the capacity you supplied."
                            : " of the capacity you supplied.")
                        + denominated,
                    worstColumn, tolerance: 1.0, unit: "ratio"));
            }
            d.Add(ResultDiagnostics.Entry(S, "supports.demand_only", "info",
                "every force here is a DEMAND. Utilisation is the one verdict "
                    + "on force, and only against a Column Capacity you supplied "
                    + "yourself. Nothing else here assumes a limit."));
            return d;
        }
    }
}
