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

        /// <summary>
        /// What a force in the Result's own unit must be multiplied by to be
        /// newtons: 1 for N, 1000 for kN, and NULL for a unit this does not
        /// know.
        ///
        /// The ONE place the conversion is decided. Every stiffness the author
        /// wires is in newtons (EA in N, EI in N.m2, the capacities in N) and
        /// every force the Result carries is in the Result's unit, so each
        /// place the two meet asks here rather than assuming. Null rather than
        /// one on an unknown unit, because a caller silently scaling by one is
        /// exactly the fault this exists to stop: it must decide whether to
        /// refuse the reading or leave it unscaled and say so.
        /// </summary>
        public static double? ToNewtons(string unit)
        {
            string named = (unit ?? string.Empty).Trim();
            if (string.Equals(named, "N", StringComparison.OrdinalIgnoreCase))
                return 1.0;
            if (string.Equals(named, "kN", StringComparison.OrdinalIgnoreCase))
                return 1000.0;
            return null;
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
    /// Every force here is in THE RESULT'S OWN FORCE UNIT, which is kN
    /// unless the Result says otherwise, and every diagnostic names it. The
    /// stiffnesses and capacities the author wires are newtons, so the three
    /// places the two meet, the utilisations against a capacity, the
    /// unstrained length against EA and the bar load against EI, convert
    /// through <see cref="MonitorMath.ToNewtons"/> and nowhere else.
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
                    + "tolerance. Forces are in the Result's own force unit, kN "
                    + "unless it says otherwise, and are converted to newtons "
                    + "where they meet a stiffness or a capacity you wire. "
                    + "Demands only, unless a capacity is wired.",
                ComponentCategories.Read,
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
                    + "to build it from. It is in NEWTON metres squared "
                    + "whatever unit the Result's forces are in: the load on "
                    + "the bar is converted to newtons before it meets this, "
                    + "so Bar Sag is true millimetres. This is the ONLY place "
                    + "a bending "
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
                    + "times the area of its section, in NEWTONS whatever unit "
                    + "the Result's forces are in, because the member force is "
                    + "converted to newtons before it meets this. Wired, "
                    + "Unstrained Length "
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
                "Allowable tension in one infill cable, in NEWTONS whatever "
                    + "unit the Result's own forces are in: a kN Result is "
                    + "converted before the division, so this number never "
                    + "changes meaning. Wired, Cable Utilisation is filled "
                    + "with the force over this. Left alone it stays empty and "
                    + "every force remains a demand: the capacity is yours to "
                    + "supply and none is assumed.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Column Capacity",
                "CO",
                "Allowable compression in one column member, in NEWTONS "
                    + "whatever unit the Result's own forces are in, exactly "
                    + "as Cable Capacity. Wired, Column Utilisation is filled "
                    + "the same way. Left alone it stays empty.",
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
                "The Result passed through with Monitor's own diagnostics "
                    + "added: counts, cable tension and slack, bar and column "
                    + "force, foundation thrust, the anchor split, spool "
                    + "lengths, bar sag, deviation, reachability and "
                    + "utilisation. Wire it to Diagnose.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Member Force",
                "F",
                "Signed axial force in each member, in the RESULT'S OWN "
                    + "FORCE UNIT (kN unless the Result says otherwise) and in "
                    + "its own sign convention. Every force on this component "
                    + "is in that unit, and the diagnostics name it. As a TREE "
                    + "branched EXACTLY as "
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
                "The horizontal component of each member force, in the "
                    + "Result's force unit (kN unless the Result says "
                    + "otherwise), branched exactly as Member Force. Read from "
                    + "the Result's own H "
                    + "where it carries one, else the force times the member's "
                    + "plan length over its length.",
                GH_ParamAccess.tree);
            parameters.AddBooleanParameter(
                "Slack",
                "SL",
                "True where an INFILL cable's force opposes the Result's "
                    + "tension convention, or is zero: a cable in compression "
                    + "is holding nothing. A BAR is never slack, so the bar "
                    + "branches read false throughout: a notched bar in "
                    + "compression is doing its job, and this flag is for the "
                    + "cables. The branches stay, so the tree is still aligned "
                    + "with Member Lines. Document 07 asked for a sign-CHANGE "
                    + "flag; a Result carries no solve history, so the only "
                    + "sign fact available is whether the force opposes the "
                    + "convention, and that is what this reports of the "
                    + "infill. Branched exactly as Member Force.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Spool Length",
                "SP",
                "The STRAINED length of each principal bar at this frame: the "
                    + "sum of the RUN's segment lengths, notch to notch. A "
                    + "segment the net carries no member for still contributes "
                    + "its length here, and is cut as if it carried no force, "
                    + "so a bar can be longer here than the members Member "
                    + "Force lists for it. That is ORDINARY rather than a "
                    + "fault: a TNA net carries no edge between two supports, "
                    + "so a run ending anchor to anchor has no member on that "
                    + "segment. monitor.spool counts them. As a TREE with ONE "
                    + "BRANCH PER PRINCIPAL LINE "
                    + "holding that bar's single length, so branch {b} is bar "
                    + "{b}: the same branch that bar's members sit in in "
                    + "Member Force and in DECONSTRUCT's Member Lines.",
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
                "Axial demand in each column member, in the Result's force "
                    + "unit (kN unless the Result says otherwise). As a TREE "
                    + "branched "
                    + "EXACTLY as DECONSTRUCT's Columns: one branch per column "
                    + "tree, members in the block's own order. Measured at the "
                    + "frame the Result carries, where DECONSTRUCT draws the "
                    + "BUILT state; the index alignment holds, the geometry "
                    + "may differ.",
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
                    + "VERTEX order, which is the one order here with NO "
                    + "partner tree: DECONSTRUCT's Node IDs are per support "
                    + "strip and its points are branched the same way, so "
                    + "nothing on that side is item-for-item with this. Read "
                    + "it against the Result's own vertex list. Zero "
                    + "everywhere without a frame. This is frame to SOLVED "
                    + "STATE; a photoscan target is a later input and not this "
                    + "one.",
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
                    + "VERTEX ORDER, as one branch. Like Deviation this has NO "
                    + "partner tree: DECONSTRUCT's Node IDs are per support "
                    + "strip, so read this against the Result's own vertex "
                    + "list. The Result's own list is sparse, carrying no "
                    + "entry for a support or an exact zero, so a node with no "
                    + "residual of its own holds its slot here as a zero "
                    + "rather than letting every node after it read someone "
                    + "else's. It moved here from Deconstruct, which is "
                    + "geometry only now. A large residual means the solve did "
                    + "not settle, whatever the shape looks like.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Cable Utilisation",
                "CU",
                "The ABSOLUTE FORCE OVER CAPACITY per member, the magnitude "
                    + "of the force in NEWTONS over Cable Capacity, branched "
                    + "exactly as Member "
                    + "Force. A utilisation is a magnitude ratio, so a cable "
                    + "pushing rather than pulling reads its size here and "
                    + "SLACK is what names the sign. The Result's force is "
                    + "converted to newtons first, so a kN Result and an N "
                    + "Result give the same ratio against the same capacity. "
                    + "EMPTY unless Cable Capacity is wired, and empty when "
                    + "the Result's force unit is neither N nor kN, because a "
                    + "ratio between two different units is not a utilisation. "
                    + "Above one the member is over the capacity YOU supplied; "
                    + "nothing here supplies one.",
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
                    + "to newtons first, exactly as Cable Utilisation. EMPTY "
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

            double stiffness = 0.0;
            data.GetData(1, ref stiffness);
            double axialStiffness = 0.0;
            data.GetData(2, ref axialStiffness);
            double tolerance = 5.0;
            data.GetData(3, ref tolerance);
            // Skin's idiom, and for Skin's reason: NaN fails every
            // comparison, so "|deviation| > NaN" is false at every node and
            // Reachable would read TRUE while monitor.reachability announced
            // every node within NaN mm. An upstream Expression dividing by
            // zero is the ordinary route to it. A silent pass on a question
            // nobody asked is worse than a warning.
            if (!double.IsFinite(tolerance))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Tolerance must be a real number of millimetres; using 5 mm.");
                tolerance = 5.0;
            }
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
                //
                // TRIMMED exactly as EquilibriumResultDto's own validator
                // trims it. It compares (SignConvention ?? "").Trim()
                // lowercased, so " positive_tension " passes Validate; reading
                // it untrimmed here would then fail the comparison and invert
                // Slack on every member of a Result the contract accepted.
                string signConvention =
                    (equilibrium.SignConvention ?? string.Empty).Trim();
                bool positiveTension = string.Equals(
                    signConvention,
                    "positive_tension",
                    StringComparison.OrdinalIgnoreCase);

                // The Result's forces carry a unit and the capacities are
                // newtons whatever it is, so a kN Result is converted before
                // the division rather than reported a thousand times too
                // small. An unknown unit buys nothing: a ratio between two
                // different units is not a utilisation, so none is published
                // and monitor.utilisation names the unit instead.
                // Read ONCE, and every force this component reports carries
                // it: a port saying N beside a utilisation computed from kN is
                // a reader's trap, and the utilisation is the only figure that
                // was ever converted. The contract refuses an empty forceUnit,
                // so the fallback is for a hand-built DTO alone, and it is the
                // contract's own default.
                string declaredUnit = (equilibrium.ForceUnit ?? string.Empty).Trim();
                string forceUnit = declaredUnit.Length > 0 ? declaredUnit : "kN";
                // Every place a Result's force meets a stiffness the author
                // wired in newtons goes through this one factor: the two
                // utilisations, the unstrained length against EA, and the bar
                // load against EI. An unknown unit leaves the value unscaled
                // and monitor.utilisation says which readings that touches.
                double? scale = MonitorMath.ToNewtons(forceUnit);
                bool forceUnitKnown = scale.HasValue;
                double toNewtons = scale ?? 1.0;
                bool cableRatio = cableCapacity > 0.0 && forceUnitKnown;
                bool columnRatio = columnCapacity > 0.0 && forceUnitKnown;

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
                    // Slack is a CABLE fact. A member on a principal line is
                    // notched steel: it carries compression as its job, and
                    // calling that slack would put a verdict on the bar
                    // branches that monitor.slack_cables, drawn from the same
                    // numbers, deliberately refuses to make. The branch stays,
                    // holding false, so the tree is still Member Lines' tree.
                    bool onABar = i < memberBar.Length && memberBar[i] >= 0;
                    slack.Add(!onABar && !tension);
                    if (cableRatio)
                    {
                        cableUtilisation.Add(
                            Math.Abs(force) * toNewtons / cableCapacity);
                    }
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
                // A run segment the net carries no member for still spools:
                // it is bar to cut whether or not the solve gave it an edge.
                // It is counted rather than hidden, because a bar accounting
                // for more length than its own members is a pattern fault
                // worth knowing about, and because such a segment is cut as
                // if it carried no force.
                int spoolSegmentsWithoutMember = 0;
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
                        bool isMember = memberAt.TryGetValue(
                            MouldGeometry.EdgeKey(a, b), out int m);
                        double force = isMember ? members[m].Force : 0.0;
                        if (!isMember)
                            spoolSegmentsWithoutMember++;
                        strained += segment;
                        // EA is newtons and the force is the Result's, so the
                        // force is converted here or the strain comes out a
                        // thousand times too small on a kN Result and the bar
                        // is cut to very nearly its tensioned length.
                        relaxed += MonitorMath.UnstrainedLength(
                            segment, force * toNewtons, axialStiffness);
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
                // Deconstruct never drew.
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
                    // head is the one whose upper end is that head. This
                    // block-wide map is the LAST resort: two members can share
                    // an upper node, MouldColumnsDto.Validate permits it, and
                    // a first-by-index winner would report one tree's member
                    // as the other tree's tip reaction while Deconstruct's
                    // Heads correctly drew the head in both branches. The
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
                // Principal Nodes; only the sag is Monitor's to report. The
                // count of bars held at fewer than two notches comes back with
                // it, because their branches are zeros and zeros read as the
                // straightest bars on the model.
                (_, List<List<double>> barSag, int unheldBars) =
                    BarBending(
                        runs, v, edges, edgeSource, equilibrium, held, stiffness,
                        toNewtons);

                // One per node in VERTEX ORDER, from the table every reader of
                // this Result shares. It sits there rather than here because
                // it is the fourth per-Result table beside the members, the
                // supports and the reactions, and because a rule with no seam
                // is a rule nothing can measure.
                Vector3d[] residuals = ResultTables.Residuals(result);

                data.SetDataTree(1, OutputTree.Numbers(ByBar(memberForce)));
                data.SetDataTree(2, OutputTree.Numbers(ByBar(forceDensity)));
                data.SetDataTree(3, OutputTree.Numbers(ByBar(horizontal)));
                data.SetDataTree(4, OutputTree.Booleans(ByBar(slack)));
                data.SetDataTree(5, OutputTree.Numbers(
                    spool.Select(one => new[] { one })));
                data.SetDataTree(6, OutputTree.Numbers(axialStiffness > 0.0
                    ? unstrained.Select(one => new[] { one })
                    : Enumerable.Empty<IEnumerable<double>>()));
                data.SetDataTree(7, OutputTree.Numbers(alongBranches));
                data.SetDataTree(8, OutputTree.Numbers(acrossBranches));
                data.SetDataTree(9, OutputTree.Vectors(tipReaction));
                data.SetDataTree(10, OutputTree.Numbers(columnForceBranches));
                data.SetDataTree(11, OutputTree.Numbers(thrustBranches));
                data.SetDataTree(12, OutputTree.Numbers(leanBranches));
                data.SetDataTree(13, OutputTree.Numbers(new[] { deviation }));
                data.SetDataTree(14, OutputTree.Numbers(
                    new[] { new List<double> { stats.Rms, stats.Max, stats.P95 } }));
                data.SetDataTree(15, OutputTree.Booleans(
                    new[] { new List<bool> { unreachable.Count == 0 } }));
                data.SetDataTree(16, OutputTree.Integers(new[] { unreachable }));
                data.SetDataTree(17, OutputTree.Numbers(barSag));
                data.SetDataTree(18, OutputTree.Vectors(new[] { residuals }));
                data.SetDataTree(19, OutputTree.Numbers(cableRatio
                    ? ByBar(cableUtilisation)
                    : Enumerable.Empty<IEnumerable<double>>()));
                data.SetDataTree(20, OutputTree.Numbers(columnRatio
                    ? columnUtilBranches
                    : Enumerable.Empty<IEnumerable<double>>()));

                // The diagnostics still speak of cables and bars as two
                // populations, which is the same split the bar branches make:
                // a member on no bar is infill the steppers reel. The cable
                // utilisation the diagnostic reports is taken from the INFILL
                // alone for the same reason: the capacity was asked for as
                // "allowable tension in one infill cable", so a notched bar's
                // axial force must not trip a warning against it. The PORT
                // stays per member, because that is the tree Member Lines is.
                var infillForce = new List<double>();
                var infillUtilisation = new List<double>();
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
                    if (i < cableUtilisation.Count)
                        infillUtilisation.Add(cableUtilisation[i]);
                    if (slack[i])
                        slackCables++;
                }
                data.SetData(0, new ResultGoo(ResultDiagnostics.Replace(
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
                        cableUtilisation: cableRatio
                            ? infillUtilisation
                            : new List<double>(),
                        columnUtilisation: columnRatio
                            ? columnUtilBranches.SelectMany(b => b).ToList()
                            : new List<double>(),
                        barSag: barSag,
                        stiffness: stiffness,
                        spoolSegmentsWithoutMember: spoolSegmentsWithoutMember,
                        axisFromStrip: axisFromStrip,
                        columnFrameAbsent: columnFrameAbsent,
                        unheldBars: unheldBars,
                        forceUnit: forceUnit,
                        forceUnitKnown: forceUnitKnown))));
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
        private static (List<List<Point3d>>, List<List<double>>, int) BarBending(
            List<List<int>> runs,
            Point3d[] v,
            (int, int)[] edges,
            int[] edgeSource,
            EquilibriumResultDto equilibrium,
            HashSet<int> held,
            double stiffness,
            double toNewtons)
        {
            var nodes = new List<List<Point3d>>();
            var sag = new List<List<double>>();
            // Bars held at fewer than two notches: their branches are zeros,
            // which is right for alignment and reads as perfect straightness,
            // so the count leaves with them.
            int unheld = 0;
            if (runs.Count == 0)
                return (nodes, sag, unheld);

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
                    // Fewer than two notches is nothing to bend between at
                    // all, which is the same fact the support test below
                    // reports and belongs in the same count.
                    unheld++;
                    sag.Add(new List<double>());
                    continue;
                }

                Vector3d[] pull = MouldGeometry.BarLoads(run, v, incident);
                Vector3d[] across = MouldGeometry.BarTransverse(run, v, pull);
                var arc = new double[run.Count];
                for (int k = 1; k < run.Count; k++)
                    arc[k] = arc[k - 1] + v[run[k - 1]].DistanceTo(v[run[k]]);
                // EI is N.m2, and the load is built from the Result's own
                // member forces, so it is converted here: without it a kN
                // Result reports a thousandth of the sag it will actually
                // build with, in a number the port calls millimetres.
                double[] load = across
                    .Select(a => Math.Abs(a.Z) * toNewtons)
                    .ToArray();
                int[] supports = Enumerable.Range(0, run.Count)
                    .Where(k => held.Contains(run[k]))
                    .ToArray();

                // Under two supports the bar is a mechanism, not a beam.
                if (supports.Length < 2)
                {
                    unheld++;
                    sag.Add(Enumerable.Repeat(0.0, run.Count).ToList());
                    continue;
                }

                (double[]? deflection, double[]? _) =
                    BeamSolver.Response(arc, load, supports, EI);
                sag.Add(deflection is null
                    ? Enumerable.Repeat(0.0, run.Count).ToList()
                    : deflection.Select(d => d * 1000.0).ToList());
            }

            return (nodes, sag, unheld);
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
            double stiffness,
            int spoolSegmentsWithoutMember,
            int axisFromStrip,
            bool columnFrameAbsent,
            int unheldBars,
            string forceUnit,
            bool forceUnitKnown)
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
                    $"cable tension {cableForce.Min():0} to {cableForce.Max():0} "
                        + forceUnit,
                    cableForce.Max(), unit: forceUnit,
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
                    $"bar axial force {barForce.Min():0} to {barForce.Max():0} "
                        + forceUnit,
                    barForce.Max(), unit: forceUnit));
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
                                + "tensioned.")
                        + (spoolSegmentsWithoutMember > 0
                            ? $" {spoolSegmentsWithoutMember} run segments carry no "
                                + "member in the net, which is ordinary rather than a "
                                + "fault: a TNA net carries no edge between two "
                                + "supports, because such an edge joins two fixed nodes "
                                + "and contributes no unknown, so a run ending anchor to "
                                + "anchor has no member on that segment. Their length is "
                                + "spooled and they are cut as if they carried no force, "
                                + "so a bar can account for more length here than Member "
                                + "Force lists for it."
                            : string.Empty),
                    spool.Max(), unit: "m",
                    context: ResultDiagnostics.Context(
                        ("bars", spool.Count.ToString(CultureInfo.InvariantCulture)),
                        ("shortest", spool.Min().ToString("0.###", CultureInfo.InvariantCulture)),
                        ("segments_without_member",
                            spoolSegmentsWithoutMember.ToString(CultureInfo.InvariantCulture)))));
            }
            if (columnForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.column_force", "info",
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
                    ? ResultDiagnostics.Entry(S, "monitor.thrust_into_ground", "info",
                        "no member reaches the ground in this state, so there is no "
                            + "foundation thrust to report.", 0.0, unit: forceUnit)
                    : ResultDiagnostics.Entry(S, "monitor.thrust_into_ground", "info",
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
                    $"anchor pull up to {worst:0} {forceUnit} horizontally: the side "
                        + "ties hold the perimeter cables against exactly this.",
                    worst, unit: forceUnit));
            }
            if (anchorAcross.Count > 0)
            {
                double worstAcross = anchorAcross.Max();
                double total = anchorReaction.Sum(a => a.Length);
                double share = total > 1.0e-9 ? anchorAcross.Sum() / total : 0.0;
                d.Add(ResultDiagnostics.Entry(S, "monitor.anchor_split", "info",
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
                d.Add(ResultDiagnostics.Entry(S, "monitor.column_frame_absent", "info",
                    "this frame carries no column nodes, so the column numbers here "
                        + "are read at the BUILT state while the net is read at the "
                        + "frame. Column Force, Thrust, Lean and Tip Reaction each say "
                        + "they are measured at the frame; on this Result they are "
                        + "not."));
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
            // A bar held at fewer than two notches is a mechanism, not a
            // beam, so its branch is zeros. Left unsaid, those zeros are the
            // most reassuring numbers on the model, sitting under the least
            // supported bar there is.
            string unheldNote = unheldBars > 0
                ? $" {unheldBars} of them cannot be solved as a beam at all, being "
                    + "held at fewer than two notches or carrying fewer than two, so "
                    + "nothing is solved for them: that is a bar with nothing to bend "
                    + "between, not a straight one."
                : string.Empty;
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
                        + "tolerance against; no allowable is assumed here."
                        + unheldNote,
                    worstSag, unit: "mm",
                    context: ResultDiagnostics.Context(
                        ("EI", stiffness.ToString("G6", CultureInfo.InvariantCulture)),
                        ("unheld", unheldBars.ToString(CultureInfo.InvariantCulture)))));
            }
            else
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.bar_sag_shape_only", "info",
                    "bar bending is reported as SHAPE ONLY, because EI was left at "
                        + "zero. It shows where the bar bends and in what proportion, "
                        + "and it is not millimetres. Give EI the section you mean to "
                        + "build to put a scale on it."
                        + unheldNote,
                    worstSag));
            }
            if (unheldBars > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.bar_unheld", "warning",
                    $"{unheldBars} bars cannot be solved as a beam: they are held at "
                        + "fewer than two notches, by a column head or an anchor, or "
                        + "carry fewer than two notches at all. A bar on one support or "
                        + "none is a mechanism, so no sag is solved for it and its "
                        + "branch reads zero. Run Columns, or place a head on it, "
                        + "before reading its bending.",
                    unheldBars, unit: "bars"));
            }

            if (!forceUnitKnown)
            {
                // Dividing a force in an unknown unit by a capacity in newtons
                // is a ratio between two things, not a utilisation. The number
                // is refused rather than published with a caveat, because the
                // caveat would not travel with the number.
                d.Add(ResultDiagnostics.Entry(S, "monitor.utilisation", "warning",
                    $"this Result's forces are in '{forceUnit}', which is neither N nor "
                        + "kN, so no utilisation is reported: the capacities are "
                        + "newtons and there is nothing here to convert that unit with. "
                        + "Every force stays a demand, not a verdict. The same block "
                        + "leaves Unstrained Length and Bar Sag reading the force "
                        + "UNCONVERTED against EA and EI, which are newtons, so neither "
                        + "is to scale until this Result names a unit."));
            }
            else if (cableUtilisation.Count == 0 && columnUtilisation.Count == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "monitor.utilisation", "info",
                    "no capacity is wired, so nothing here is checked against one and "
                        + "every figure is a DEMAND, NOT A VERDICT. Wire Cable Capacity "
                        + "or Column Capacity to turn these forces into utilisations."));
            }
            else
            {
                double worstCable = cableUtilisation.DefaultIfEmpty(0.0).Max();
                double worstColumn = columnUtilisation.DefaultIfEmpty(0.0).Max();
                double worstUse = Math.Max(worstCable, worstColumn);
                var said = new List<string>();
                // The cable figure is the worst of the INFILL alone. Cable
                // Capacity was asked for as the allowable tension in one
                // infill cable, so a notched bar's axial force has no business
                // raising a warning against it.
                if (cableUtilisation.Count > 0)
                    said.Add($"infill cable up to {worstCable:0.###}");
                if (columnUtilisation.Count > 0)
                    said.Add($"column up to {worstColumn:0.###}");
                // Both units named, because this is the one figure on the
                // component that mixes them: the forces are the Result's and
                // the capacity is the author's, in newtons.
                string denominated = string.Equals(
                    forceUnit, "N", StringComparison.OrdinalIgnoreCase)
                    ? " The forces and the capacity are both in N."
                    : $" The forces are in {forceUnit}, converted to N against "
                        + "the capacity you supplied, which is in N.";
                d.Add(ResultDiagnostics.Entry(S, "monitor.utilisation",
                    worstUse > 1.0 ? "warning" : "info",
                    "utilisation " + string.Join(", ", said)
                        + (worstUse > 1.0
                            ? ". Above one a member is OVER the capacity you supplied."
                            : " of the capacity you supplied.")
                        + denominated,
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
