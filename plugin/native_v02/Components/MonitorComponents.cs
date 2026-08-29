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
    /// <summary>The pure arithmetic under Monitor's readings.</summary>
    internal static class MonitorMath
    {
        /// <summary>
        /// A reaction split along the tensioner axis (signed, positive along
        /// the axis) and across it (the magnitude of the remainder). The
        /// across part is what the anchorage carries and the tensioner cannot.
        /// </summary>
        public static (double Along, double Across) AnchorSplit(Vector3d reaction, Vector3d axis)
        {
            double length = axis.Length;
            if (length <= 1.0e-12)
                return (0.0, reaction.Length);
            Vector3d unit = axis / length;
            double along = (reaction.X * unit.X) + (reaction.Y * unit.Y) + (reaction.Z * unit.Z);
            Vector3d rest = reaction - (unit * along);
            return (along, rest.Length);
        }

        /// <summary>
        /// The tensioner axis at an anchor: the unit mean direction of the
        /// members leaving it into the net. Vertical when it has none.
        /// </summary>
        public static Vector3d TensionerAxis(int anchor, Point3d[] v, List<int>[] neighbours)
        {
            var sum = Vector3d.Zero;
            if (anchor < 0 || anchor >= v.Length || anchor >= neighbours.Length)
                return Vector3d.ZAxis;
            foreach (int other in neighbours[anchor])
            {
                if (other < 0 || other >= v.Length)
                    continue;
                Vector3d d = v[other] - v[anchor];
                double length = d.Length;
                if (length > 1.0e-12)
                    sum += d / length;
            }
            double total = sum.Length;
            return total > 1.0e-12 ? sum / total : Vector3d.ZAxis;
        }

        /// <summary>
        /// RMS, worst absolute, and nearest-rank 95th percentile of the
        /// absolute values. Zeros on an empty field.
        /// </summary>
        public static (double Rms, double Max, double P95) DeviationStats(IReadOnlyList<double> values)
        {
            if (values.Count == 0)
                return (0.0, 0.0, 0.0);
            double sumSquares = 0.0;
            var absolute = new double[values.Count];
            for (int i = 0; i < values.Count; i++)
            {
                sumSquares += values[i] * values[i];
                absolute[i] = Math.Abs(values[i]);
            }
            Array.Sort(absolute);
            int rank = (int)Math.Ceiling(0.95 * absolute.Length);
            rank = Math.Min(Math.Max(rank, 1), absolute.Length);
            return (Math.Sqrt(sumSquares / values.Count), absolute[^1], absolute[rank - 1]);
        }

        /// <summary>
        /// The unstrained length of a member: strained over one plus force
        /// over EA. The strained length comes back when EA is not positive,
        /// and also when one plus force over EA collapses to nothing or goes
        /// negative, which is a member whose EA cannot carry its own
        /// compression: it has no unstrained length worth reporting, and
        /// dividing by that denominator would hand back an infinity or a
        /// length with its sign flipped.
        /// </summary>
        public static double UnstrainedLength(double strained, double force, double EA)
        {
            if (EA <= 0.0)
                return strained;
            double stretch = 1.0 + (force / EA);
            return stretch > 1.0e-9 ? strained / stretch : strained;
        }
    }

    /// <summary>
    /// Monitor: every NUMBER a Result and its frame carry, as trees that line
    /// up with the geometry trees Deconstruct and Animate hand back.
    ///
    /// The split is the spine's: Deconstruct gives the shape, Monitor gives
    /// what that shape is carrying. Nothing here is a flat list that has to be
    /// matched against a drawing by eye. Every member output is branched by
    /// bar exactly as Deconstruct's Member Lines, every anchor output by
    /// support strip exactly as its Reaction Points, and every column output
    /// by column tree exactly as its Columns and Heads, because both
    /// components read the same <see cref="ResultTables"/> rows and make the
    /// same grouping calls in the same order.
    ///
    /// It also carries the machine's own readings, which existed nowhere
    /// before: the spool length of each bar and what to cut it to, the pull
    /// each anchor puts along its tensioner and across it, the reaction at
    /// each column tip, the deviation between the frame and the state it is
    /// heading for, and whether that deviation is inside the tolerance the
    /// author set.
    ///
    /// Every force here is a DEMAND. The only verdicts are utilisation,
    /// against a capacity the author supplies, and reachability, against the
    /// tolerance the author sets. Nothing else assumes a limit.
    /// </summary>
    public sealed class StressAnalysisComponent : NativeComponentBase
    {
        public StressAnalysisComponent()
            : base(
                "Monitor",
                "MON",
                "Every number a Result and its frame carry, as trees aligned "
                    + "with Deconstruct's and Animate's, plus the machine's own "
                    + "readings: spool lengths, the anchors' pull along and "
                    + "across their tensioners, the tip reactions, the "
                    + "deviation to the solved shape and whether it is within "
                    + "tolerance. Demands only, unless a capacity is wired.",
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
                    + "to build it from. This is the ONLY place a bending "
                    + "stiffness is asked for, and it is asked for here on "
                    + "purpose. Where the arms go does not depend on it, "
                    + "because stiffness cancels out of that comparison, so "
                    + "putting a number on it upstream would look like it were "
                    + "tuning the placement when it cannot. Here it converts "
                    + "the bar's bending into millimetres you can hold a "
                    + "tolerance against. Steel 40x40x3 SHS is about 1.9e5; a "
                    + "48.3x4 CHS about 2.4e5. Zero or negative reports the "
                    + "shape of the bending without a scale.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "EA",
                "EA",
                "Axial stiffness of one principal bar, N: Young's modulus "
                    + "times the area of its section. Wired, Unstrained Length "
                    + "reports what to CUT each bar to before it is tensioned. "
                    + "Left alone that output is empty, because the unstrained "
                    + "length of a spool cannot be known without a stiffness, "
                    + "and a guess would be cut to.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Tolerance",
                "Tol",
                "How far a node may sit from the solved state and still count "
                    + "as reached, in MILLIMETRES. Reachable and Unreachable "
                    + "are read against this, and nothing else here assumes it.",
                GH_ParamAccess.item,
                5.0);
            parameters.AddNumberParameter(
                "Cable Capacity",
                "CC",
                "Allowable tension in one infill cable, N. Wired, Cable "
                    + "Utilisation is filled with the force over this. Left "
                    + "alone it stays empty and every force remains a demand: "
                    + "the capacity is yours to supply and none is assumed.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Column Capacity",
                "CO",
                "Allowable compression in one column member, N. Wired, Column "
                    + "Utilisation is filled the same way. Left alone it stays "
                    + "empty.",
                GH_ParamAccess.item,
                0.0);
            for (int slot = 1; slot < parameters.ParamCount; slot++)
                parameters[slot].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddNumberParameter(
                "Member Force",
                "F",
                "Signed axial force in each member, N, in the Result's own "
                    + "sign convention. As a TREE branched EXACTLY as "
                    + "DECONSTRUCT's Member Lines for the same Result: one "
                    + "branch per principal line holding that bar's own "
                    + "members, and a LAST branch holding the infill. Item [i] "
                    + "of branch {b} here is item [i] of branch {b} there.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Force Density",
                "q",
                "Force over live length per member, branched exactly as Member "
                    + "Force. Read from the Result where it carries one (a TNA "
                    + "Result does), worked out as force over the member's "
                    + "length at this frame where it does not.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Horizontal Force",
                "H",
                "The horizontal component of each member force, N, branched "
                    + "exactly as Member Force. Read from the Result's own H "
                    + "where it carries one, else the force times the member's "
                    + "plan length over its length.",
                GH_ParamAccess.tree);
            parameters.AddBooleanParameter(
                "Slack",
                "SL",
                "True where a member's force OPPOSES the Result's tension "
                    + "convention, or is zero: a cable in compression is "
                    + "holding nothing. Document 07 asked for a sign-CHANGE "
                    + "flag; a Result carries no solve history, so the only "
                    + "sign fact available is whether the force opposes the "
                    + "convention, and that is what this reports. Branched "
                    + "exactly as Member Force.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Spool Length",
                "SP",
                "The STRAINED length of each principal bar at this frame: the "
                    + "sum of that bar's member lengths. As a TREE with ONE "
                    + "BRANCH PER PRINCIPAL LINE holding that bar's single "
                    + "length, so branch {b} is bar {b}: the same branch that "
                    + "bar's members sit in in Member Force and in "
                    + "DECONSTRUCT's Member Lines.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Unstrained Length",
                "UL",
                "The same bars with the stretch taken out, sum(L / (1 + N / "
                    + "EA)): what to cut each one to before it is tensioned. "
                    + "One branch per principal line, aligned with Spool "
                    + "Length branch for branch. EMPTY unless EA is wired, "
                    + "because without an axial stiffness the strained length "
                    + "is all there is.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Anchor Along",
                "AA",
                "The part of each anchor's reaction acting ALONG its tensioner "
                    + "axis, N, positive along that axis: the pull the "
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
                    + "out, as a magnitude, N. This is what the ANCHORAGE has "
                    + "to carry, because a tensioner can only pull along its "
                    + "own axis. Branched exactly as Anchor Along.",
                GH_ParamAccess.tree);
            parameters.AddVectorParameter(
                "Tip Reaction",
                "TR",
                "The axial force of the member under each column head, as a "
                    + "vector along that member pointing UP into the head, N. "
                    + "It comes from the block's own member forces and not "
                    + "from a solver's node reactions, because the columns are "
                    + "solved as a block upstream. As a TREE branched EXACTLY "
                    + "as DECONSTRUCT's Heads: one branch per column tree, "
                    + "heads in the order that tree's members are walked. "
                    + "Measured at the frame the Result carries, where "
                    + "DECONSTRUCT draws the BUILT state; the index alignment "
                    + "holds, the geometry may differ.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Column Force",
                "CF",
                "Axial demand in each column member, N. As a TREE branched "
                    + "EXACTLY as DECONSTRUCT's Columns: one branch per column "
                    + "tree, members in the block's own order. Measured at the "
                    + "frame the Result carries, where DECONSTRUCT draws the "
                    + "BUILT state; the index alignment holds, the geometry "
                    + "may differ.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Thrust",
                "TH",
                "The horizontal force in each column member, N: the part of a "
                    + "leaning member's axial force that acts sideways. A "
                    + "plumb member reads zero. Only the members STANDING ON "
                    + "THE GROUND put theirs into the foundation, and the "
                    + "monitor.thrust_into_ground diagnostic sums those alone; "
                    + "a branch's horizontal is balanced at its junction by "
                    + "its siblings. Branched exactly as Column Force, and "
                    + "measured at the frame the Result carries, where "
                    + "DECONSTRUCT draws the BUILT state; the index alignment "
                    + "holds, the geometry may differ.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Lean",
                "LN",
                "Degrees from vertical per column member, branched exactly as "
                    + "Column Force. Past sixty a member pushes sideways more "
                    + "than it holds up. Measured at the frame the Result "
                    + "carries, where DECONSTRUCT draws the BUILT state; the "
                    + "index alignment holds, the geometry may differ.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Deviation",
                "DV",
                "Signed vertical distance from the frame to the solved state "
                    + "at each node, in MILLIMETRES, positive where the frame "
                    + "sits above the state it is heading for. One branch, in "
                    + "vertex order. Zero everywhere without a frame. This is "
                    + "frame to SOLVED STATE; a photoscan target is a later "
                    + "input and not this one.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Deviation Stats",
                "DS",
                "Three numbers over the whole Deviation field, in mm: the RMS, "
                    + "the worst absolute, and the 95th percentile of the "
                    + "absolute values by nearest rank. One branch of three "
                    + "items, in that order.",
                GH_ParamAccess.tree);
            parameters.AddBooleanParameter(
                "Reachable",
                "RC",
                "One boolean: true when every node's absolute deviation is "
                    + "within Tolerance AT THIS FRAME. That is the whole "
                    + "claim. Whether a constrained solver could drive the "
                    + "machine there is the M1 bridge's question, and it is "
                    + "not answered here. Without a frame the deviation is "
                    + "zero by definition, so this reads true and "
                    + "monitor.reachability says the question was not "
                    + "measured.",
                GH_ParamAccess.tree);
            parameters.AddIntegerParameter(
                "Unreachable",
                "UN",
                "The node ids whose absolute deviation is outside Tolerance, "
                    + "ascending. One branch; empty when Reachable is true.",
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
                    + "a verdict, and no allowable is assumed. As a TREE with "
                    + "one branch per principal line, aligned with ANIMATE's "
                    + "Principal Nodes branch for branch and item for item. "
                    + "Empty if the state carries no principal runs.",
                GH_ParamAccess.tree);
            parameters.AddVectorParameter(
                "Residuals",
                "E",
                "The Result's equilibrium residual vector, ONE PER NODE IN "
                    + "VERTEX ORDER, as one branch. The Result's own list is "
                    + "sparse, carrying no entry for a support or an exact "
                    + "zero, so a node with no residual of its own holds its "
                    + "slot here as a zero rather than letting every node "
                    + "after it read someone else's. It moved here from "
                    + "Deconstruct, which is geometry only now. A large "
                    + "residual means the solve did not settle, whatever the "
                    + "shape looks like.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Cable Utilisation",
                "CU",
                "The ABSOLUTE FORCE OVER CAPACITY per member, the magnitude "
                    + "of N over Cable Capacity, branched exactly as Member "
                    + "Force. A utilisation is a magnitude ratio, so a cable "
                    + "pushing rather than pulling reads its size here and "
                    + "SLACK is what names the sign. EMPTY unless Cable "
                    + "Capacity is wired. Above one the member is over the "
                    + "capacity YOU supplied; nothing here supplies one.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Column Utilisation",
                "CLU",
                "The ABSOLUTE FORCE OVER CAPACITY per column member, the "
                    + "magnitude of N over Column Capacity, branched exactly "
                    + "as Column Force. A utilisation is a magnitude ratio, so "
                    + "the sign of the member force is not in it. EMPTY unless "
                    + "Column Capacity is wired.",
                GH_ParamAccess.tree);
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "The Result passed through with Monitor's own diagnostics "
                    + "added: counts, cable tension and slack, bar and column "
                    + "force, foundation thrust, the anchor split, spool "
                    + "lengths, bar sag, deviation, reachability and "
                    + "utilisation. Wire it to Diagnose.",
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

            double stiffness = 0.0;
            data.GetData(1, ref stiffness);
            double axialStiffness = 0.0;
            data.GetData(2, ref axialStiffness);
            double tolerance = 5.0;
            data.GetData(3, ref tolerance);
            double cableCapacity = 0.0;
            data.GetData(4, ref cableCapacity);
            double columnCapacity = 0.0;
            data.GetData(5, ref columnCapacity);

            try
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
                bool Known(int i) => i >= 0 && i < v.Length;

                // ---- members ------------------------------------------------
                // The one ordering every reader of this Result shares. These
                // are the SAME calls Deconstruct makes, in the same order, so
                // the number trees below align with its geometry trees without
                // either component matching coordinates.
                ResultTables.MemberRow[] members = ResultTables.Members(result);
                (int U, int V)[] memberEnds = members
                    .Select(row => (row.U, row.V))
                    .ToArray();
                (int, int)[] edges = MouldGeometry.ValidEdges(
                    equilibrium, n, out int[] edgeSource);
                List<List<int>> runs = MouldGeometry.PrincipalRuns(equilibrium, n);
                int[] memberBar = MouldGeometry.MemberRunIndex(memberEnds, runs);

                // One branch per bar, then infill LAST. Copied from
                // Deconstruct's own local, so branch {i} is bar {i} in both.
                IEnumerable<IEnumerable<T>> ByBar<T>(IReadOnlyList<T> values)
                {
                    var branches = new List<List<T>>();
                    for (int b = 0; b <= runs.Count; b++)
                        branches.Add(new List<T>());
                    for (int i = 0; i < values.Count; i++)
                    {
                        int bar = i < memberBar.Length ? memberBar[i] : -1;
                        branches[bar >= 0 ? bar : runs.Count].Add(values[i]);
                    }
                    return branches;
                }

                // The convention is a string on the Result, and the contracts
                // admit exactly one value today, positive_tension. Read rather
                // than assumed, because a Result that ever carries the other
                // one must not silently invert the slack flag.
                bool positiveTension = string.Equals(
                    equilibrium.SignConvention,
                    "positive_tension",
                    StringComparison.OrdinalIgnoreCase);

                var memberForce = new List<double>(members.Length);
                var forceDensity = new List<double>(members.Length);
                var horizontal = new List<double>(members.Length);
                var slack = new List<bool>(members.Length);
                var cableUtilisation = new List<double>();
                for (int i = 0; i < members.Length; i++)
                {
                    ResultTables.MemberRow row = members[i];
                    bool ends = Known(row.U) && Known(row.V);
                    double length = ends ? v[row.U].DistanceTo(v[row.V]) : 0.0;
                    double plan = ends
                        ? Math.Sqrt(MouldGeometry.PlanDistanceSquared(v[row.U], v[row.V]))
                        : 0.0;
                    double force = row.Force;
                    memberForce.Add(force);
                    forceDensity.Add(double.IsFinite(row.Q)
                        ? row.Q
                        : (length > 1.0e-12 ? force / length : 0.0));
                    horizontal.Add(double.IsFinite(row.H)
                        ? row.H
                        : force * plan / Math.Max(length, 1.0e-12));
                    bool tension = positiveTension ? force > 1.0e-9 : force < -1.0e-9;
                    slack.Add(!tension);
                    if (cableCapacity > 0.0)
                        cableUtilisation.Add(Math.Abs(force) / cableCapacity);
                }

                // ---- spools -------------------------------------------------
                // A bar's members are found by their two ENDS rather than by
                // position in the member table: the table is in the Result's
                // edge order and a bar is a run of nodes, and the packed key
                // here is the one MemberRunIndex matched on.
                var memberAt = new Dictionary<long, int>();
                for (int i = 0; i < members.Length; i++)
                {
                    if (!Known(members[i].U) || !Known(members[i].V))
                        continue;
                    long key = MouldGeometry.EdgeKey(members[i].U, members[i].V);
                    if (!memberAt.ContainsKey(key))
                        memberAt[key] = i;
                }
                var spool = new List<double>(runs.Count);
                var unstrained = new List<double>(runs.Count);
                foreach (List<int> run in runs)
                {
                    double strained = 0.0;
                    double relaxed = 0.0;
                    for (int k = 0; k + 1 < run.Count; k++)
                    {
                        int a = run[k];
                        int b = run[k + 1];
                        double segment = Known(a) && Known(b)
                            ? v[a].DistanceTo(v[b])
                            : 0.0;
                        double force = memberAt.TryGetValue(
                            MouldGeometry.EdgeKey(a, b), out int m)
                            ? members[m].Force
                            : 0.0;
                        strained += segment;
                        relaxed += MonitorMath.UnstrainedLength(
                            segment, force, axialStiffness);
                    }
                    spool.Add(strained);
                    unstrained.Add(relaxed);
                }

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
                            reaction, MonitorMath.TensionerAxis(id, v, adjacency));
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
                        vector, MonitorMath.TensionerAxis(node, v, adjacency));
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
                // Deconstruct never drew.
                var tipReaction = new List<List<Vector3d>>();
                var columnForceBranches = new List<List<double>>();
                var thrustBranches = new List<List<double>>();
                var leanBranches = new List<List<double>>();
                var columnUtilBranches = new List<List<double>>();
                var standsOnGround = new List<bool>();
                if (block is not null)
                {
                    // Length-matched to the block's own nodes, so the range
                    // test below is Deconstruct's range test and not a second
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
                    // head is the one whose upper end is that head.
                    var under = new Dictionary<int, int>();
                    for (int m = 0; m < block.Members.Count; m++)
                    {
                        if (!under.ContainsKey(block.Members[m].V))
                            under[block.Members[m].V] = m;
                    }
                    Vector3d Tip(int head)
                    {
                        if (!under.TryGetValue(head, out int m))
                            return Vector3d.Zero;
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
                            if (columnCapacity > 0.0)
                                utilisation.Add(Math.Abs(axial) / columnCapacity);
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
                                    tips.Add(Tip(end));
                            }
                        }
                        tipReaction.Add(tips);
                        columnForceBranches.Add(force);
                        thrustBranches.Add(thrust);
                        leanBranches.Add(lean);
                        columnUtilBranches.Add(utilisation);
                    }
                }

                // ---- deviation ----------------------------------------------
                var deviation = new List<double>(n);
                for (int i = 0; i < n; i++)
                {
                    deviation.Add(frame is null
                        ? 0.0
                        : (v[i].Z - equilibrium.Vertices[i].Z) * 1000.0);
                }
                (double Rms, double Max, double P95) stats =
                    MonitorMath.DeviationStats(deviation);
                var unreachable = new List<int>();
                for (int i = 0; i < deviation.Count; i++)
                {
                    if (Math.Abs(deviation[i]) > tolerance)
                        unreachable.Add(i);
                }

                // ---- bar sag and residuals ----------------------------------
                // A notch is HELD where a column head stands on it, by index,
                // or where it is itself an anchor.
                var held = new HashSet<int>(nodeIds.Where(Known));
                if (block is not null)
                {
                    foreach (int node in block.HeadNode)
                    {
                        if (Known(node))
                            held.Add(node);
                    }
                }
                // The notch positions BarBending returns are Animate's
                // Principal Nodes; only the sag is Monitor's to report.
                (_, List<List<double>> barSag) =
                    BarBending(runs, v, edges, edgeSource, equilibrium, held, stiffness);

                // One per node IN VERTEX ORDER, which the Result's own list
                // is not: the codec writes no entry for a support and none for
                // an exact zero, so reading that list positionally would put
                // node 7's residual at item 4 and every node after it would
                // read someone else's. Placed by NodeId, exactly as the
                // reactions are, with a node carrying none holding its slot as
                // a zero rather than shifting its neighbours up.
                var residuals = new List<Vector3d>(n);
                for (int i = 0; i < n; i++)
                    residuals.Add(Vector3d.Zero);
                foreach (NodalVectorDto item in equilibrium.Residuals)
                {
                    if (item.NodeId >= 0 && item.NodeId < n)
                    {
                        residuals[item.NodeId] = new Vector3d(
                            item.Vector.X, item.Vector.Y, item.Vector.Z);
                    }
                }

                data.SetDataTree(0, OutputTree.Numbers(ByBar(memberForce)));
                data.SetDataTree(1, OutputTree.Numbers(ByBar(forceDensity)));
                data.SetDataTree(2, OutputTree.Numbers(ByBar(horizontal)));
                data.SetDataTree(3, OutputTree.Booleans(ByBar(slack)));
                data.SetDataTree(4, OutputTree.Numbers(
                    spool.Select(one => new[] { one })));
                data.SetDataTree(5, OutputTree.Numbers(axialStiffness > 0.0
                    ? unstrained.Select(one => new[] { one })
                    : Enumerable.Empty<IEnumerable<double>>()));
                data.SetDataTree(6, OutputTree.Numbers(alongBranches));
                data.SetDataTree(7, OutputTree.Numbers(acrossBranches));
                data.SetDataTree(8, OutputTree.Vectors(tipReaction));
                data.SetDataTree(9, OutputTree.Numbers(columnForceBranches));
                data.SetDataTree(10, OutputTree.Numbers(thrustBranches));
                data.SetDataTree(11, OutputTree.Numbers(leanBranches));
                data.SetDataTree(12, OutputTree.Numbers(new[] { deviation }));
                data.SetDataTree(13, OutputTree.Numbers(
                    new[] { new List<double> { stats.Rms, stats.Max, stats.P95 } }));
                data.SetDataTree(14, OutputTree.Booleans(
                    new[] { new List<bool> { unreachable.Count == 0 } }));
                data.SetDataTree(15, OutputTree.Integers(new[] { unreachable }));
                data.SetDataTree(16, OutputTree.Numbers(barSag));
                data.SetDataTree(17, OutputTree.Vectors(new[] { residuals }));
                data.SetDataTree(18, OutputTree.Numbers(cableCapacity > 0.0
                    ? ByBar(cableUtilisation)
                    : Enumerable.Empty<IEnumerable<double>>()));
                data.SetDataTree(19, OutputTree.Numbers(columnCapacity > 0.0
                    ? columnUtilBranches
                    : Enumerable.Empty<IEnumerable<double>>()));

                // The diagnostics still speak of cables and bars as two
                // populations, which is the same split the bar branches make:
                // a member on no bar is infill the steppers reel.
                var infillForce = new List<double>();
                var barMemberForce = new List<double>();
                int slackCables = 0;
                for (int i = 0; i < memberForce.Count; i++)
                {
                    if (i < memberBar.Length && memberBar[i] >= 0)
                    {
                        barMemberForce.Add(memberForce[i]);
                        continue;
                    }
                    infillForce.Add(memberForce[i]);
                    if (slack[i])
                        slackCables++;
                }
                data.SetData(20, new ResultGoo(ResultDiagnostics.Replace(
                    result, "Monitor", Diagnostics(
                        frame: frame,
                        cableForce: infillForce,
                        barForce: barMemberForce,
                        slackCables: slackCables,
                        columnForce: columnForceBranches.SelectMany(b => b).ToList(),
                        thrust: thrustBranches.SelectMany(b => b).ToList(),
                        standsOnGround: standsOnGround,
                        anchorReaction: anchorReaction,
                        anchorAcross: acrossBranches.SelectMany(b => b).ToList(),
                        spool: spool,
                        unstrained: axialStiffness > 0.0 ? unstrained : new List<double>(),
                        deviation: stats,
                        nodeCount: deviation.Count,
                        unreachable: unreachable.Count,
                        tolerance: tolerance,
                        cableUtilisation: cableCapacity > 0.0
                            ? cableUtilisation
                            : new List<double>(),
                        columnUtilisation: columnCapacity > 0.0
                            ? columnUtilBranches.SelectMany(b => b).ToList()
                            : new List<double>(),
                        barSag: barSag,
                        stiffness: stiffness))));
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
            MouldFrameDto? frame,
            List<double> cableForce,
            List<double> barForce,
            int slackCables,
            List<double> columnForce,
            List<double> thrust,
            List<bool> standsOnGround,
            List<Vector3d> anchorReaction,
            List<double> anchorAcross,
            List<double> spool,
            List<double> unstrained,
            (double Rms, double Max, double P95) deviation,
            int nodeCount,
            int unreachable,
            double tolerance,
            List<double> cableUtilisation,
            List<double> columnUtilisation,
            List<List<double>> barSag,
            double stiffness)
        {
            const string S = "Monitor";
            var d = new List<DiagnosticDto>
            {
                ResultDiagnostics.Entry(S, "monitor.counts", "info",
                    $"{cableForce.Count} infill cables, {barForce.Count} bar members, "
                        + $"{columnForce.Count} columns, {anchorReaction.Count} anchors"
                        + (frame is null ? ", read at the solved state" : $", read at frame {frame.Phase}"),
                    cableForce.Count, unit: "cables",
                    context: ResultDiagnostics.Context(
                        ("bars", barForce.Count.ToString(CultureInfo.InvariantCulture)),
                        ("columns", columnForce.Count.ToString(CultureInfo.InvariantCulture)),
                        ("anchors", anchorReaction.Count.ToString(CultureInfo.InvariantCulture)))),
            };

            if (cableForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.cable_tension", "info",
                    $"cable tension {cableForce.Min():0} to {cableForce.Max():0} N",
                    cableForce.Max(), unit: "N",
                    context: ResultDiagnostics.Context(("min", cableForce.Min().ToString("0", CultureInfo.InvariantCulture)))));
                d.Add(slackCables == 0
                    ? ResultDiagnostics.Entry(S, "monitor.slack_cables", "ok",
                        "no cable is slack: every one is still pulling", 0.0, unit: "cables")
                    : ResultDiagnostics.Entry(S, "monitor.slack_cables", "warning",
                        $"{slackCables} cables are SLACK. A slack cable holds nothing, so the "
                            + "surface between its neighbours is unsupported. Raise the "
                            + "prestress or move the bars closer.",
                        slackCables, unit: "cables"));
            }
            if (barForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.bar_force", "info",
                    $"bar axial force {barForce.Min():0} to {barForce.Max():0} N",
                    barForce.Max(), unit: "N"));
            }
            if (spool.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.spool", "info",
                    $"{spool.Count} bars spool {spool.Min():0.###} to {spool.Max():0.###} m "
                        + "at this frame"
                        + (unstrained.Count > 0
                            ? $", and cut to {unstrained.Min():0.###} to "
                                + $"{unstrained.Max():0.###} m before they are tensioned."
                            : ". Wire EA to read what to cut them to before they are "
                                + "tensioned."),
                    spool.Max(), unit: "m",
                    context: ResultDiagnostics.Context(
                        ("bars", spool.Count.ToString(CultureInfo.InvariantCulture)),
                        ("shortest", spool.Min().ToString("0.###", CultureInfo.InvariantCulture)))));
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
            if (anchorReaction.Count > 0)
            {
                double worst = anchorReaction
                    .Select(a => Math.Sqrt((a.X * a.X) + (a.Y * a.Y)))
                    .DefaultIfEmpty(0.0)
                    .Max();
                d.Add(ResultDiagnostics.Entry(S, "monitor.anchor_horizontal", "info",
                    $"anchor pull up to {worst:0} N horizontally: the side ties hold "
                        + "the perimeter cables against exactly this.",
                    worst, unit: "N"));
            }
            if (anchorAcross.Count > 0)
            {
                double worstAcross = anchorAcross.Max();
                double total = anchorReaction.Sum(a => a.Length);
                double share = total > 1.0e-9 ? anchorAcross.Sum() / total : 0.0;
                d.Add(ResultDiagnostics.Entry(S, "monitor.anchor_split", "info",
                    $"the worst anchor puts {worstAcross:0} N ACROSS its tensioner, and "
                        + $"{share * 100.0:0.#} percent of all the anchor pull is across "
                        + "rather than along. A tensioner can only pull along its own "
                        + "axis, so that share is the anchorage's to carry.",
                    worstAcross, unit: "N",
                    context: ResultDiagnostics.Context(
                        ("share", share.ToString("0.###", CultureInfo.InvariantCulture)))));
            }
            if (frame is not null && frame.Time < 100.0 - 1.0e-9)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.intermediate_frame", "info",
                    "this is an intermediate frame, so the geometry is part way "
                        + "through the build while the forces are those of the "
                        + "finished state. Read it as where the structure is going.",
                    frame.Time, unit: "percent"));
            }

            d.Add(frame is null
                ? ResultDiagnostics.Entry(S, "monitor.deviation", "info",
                    "no frame on this Result, so the deviation to the solved state is "
                        + "zero everywhere by definition. Wire Animate upstream to read "
                        + "it at a frame.",
                    0.0, unit: "mm")
                : ResultDiagnostics.Entry(S, "monitor.deviation", "info",
                    $"the frame stands {deviation.Rms:0.##} mm RMS off the solved "
                        + $"state, {deviation.Max:0.##} mm at worst and "
                        + $"{deviation.P95:0.##} mm at the 95th percentile.",
                    deviation.Max, unit: "mm",
                    context: ResultDiagnostics.Context(
                        ("rms", deviation.Rms.ToString("0.###", CultureInfo.InvariantCulture)),
                        ("p95", deviation.P95.ToString("0.###", CultureInfo.InvariantCulture)))));
            if (frame is null)
            {
                // Without a frame the net IS the solved state, so every node is
                // trivially inside any tolerance. Reporting that as reachable
                // would be a verdict on a question nobody asked.
                d.Add(ResultDiagnostics.Entry(S, "monitor.reachability", "info",
                    "no frame on this Result, so deviation is zero by definition and "
                        + "reachability is not measured. Wire Animate upstream to put "
                        + "the machine at a frame and ask the question properly.",
                    unit: "nodes"));
            }
            else
            {
                d.Add(unreachable == 0
                    ? ResultDiagnostics.Entry(S, "monitor.reachability", "ok",
                        $"every one of the {nodeCount} nodes is within {tolerance:0.##} mm "
                            + "of the solved state at this frame.",
                        0.0, tolerance: tolerance, unit: "nodes")
                    : ResultDiagnostics.Entry(S, "monitor.reachability", "warning",
                        $"{unreachable} of {nodeCount} nodes sit further than "
                            + $"{tolerance:0.##} mm from the solved state. That is "
                            + "reachability AT THIS FRAME and nothing more; whether the "
                            + "machine can be driven there is the M1 bridge's question.",
                        unreachable, tolerance: tolerance, unit: "nodes"));
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

            if (cableUtilisation.Count == 0 && columnUtilisation.Count == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.utilisation", "info",
                    "no capacity is wired, so nothing here is checked against one. "
                        + "Wire Cable Capacity or Column Capacity to turn these forces "
                        + "into utilisations."));
            }
            else
            {
                double worstCable = cableUtilisation.DefaultIfEmpty(0.0).Max();
                double worstColumn = columnUtilisation.DefaultIfEmpty(0.0).Max();
                double worstUse = Math.Max(worstCable, worstColumn);
                var said = new List<string>();
                if (cableUtilisation.Count > 0)
                    said.Add($"cable up to {worstCable:0.###}");
                if (columnUtilisation.Count > 0)
                    said.Add($"column up to {worstColumn:0.###}");
                d.Add(ResultDiagnostics.Entry(S, "monitor.utilisation",
                    worstUse > 1.0 ? "warning" : "info",
                    "utilisation " + string.Join(", ", said)
                        + (worstUse > 1.0
                            ? ". Above one a member is OVER the capacity you supplied."
                            : " of the capacity you supplied."),
                    worstUse, tolerance: 1.0, unit: "ratio"));
            }
            d.Add(ResultDiagnostics.Entry(S, "monitor.demand_only", "info",
                "every force here is a DEMAND. Utilisation is the one verdict on "
                    + "force, and only against a capacity you supplied yourself; "
                    + "reachability is the one verdict on geometry, and only against "
                    + "the Tolerance you set. Nothing else assumes a limit."));
            return d;
        }
    }
}
