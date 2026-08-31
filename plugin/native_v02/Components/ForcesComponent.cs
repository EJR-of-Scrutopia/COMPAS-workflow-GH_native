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
    /// Forces: what the net's members carry, and what to cut.
    ///
    /// One of Monitor's three children. Every member output is branched by
    /// bar exactly as Deconstruct's Member Lines for the same Result: one
    /// branch per principal line holding that bar's own members, and a LAST
    /// branch holding the infill, because both components read the same
    /// <see cref="ResultTables"/> rows and make the same grouping calls in
    /// the same order. Nothing here is a flat list that has to be matched
    /// against a drawing by eye.
    ///
    /// Every force here is in THE RESULT'S OWN FORCE UNIT, which is kN
    /// unless the Result says otherwise, and every diagnostic names it. The
    /// stiffness and capacity the author wires are newtons, so the two
    /// places the two meet, the utilisation against Cable Capacity and the
    /// unstrained length against EA, convert through
    /// <see cref="MonitorMath.ToNewtons"/> and nowhere else.
    ///
    /// Every force here is a DEMAND. The only verdict is utilisation,
    /// against a capacity the author supplies. Nothing else assumes a limit.
    /// </summary>
    public sealed class ForcesComponent : NativeComponentBase
    {
        public ForcesComponent()
            : base(
                "Forces",
                "FO",
                "What the net's members carry, and what to cut: member "
                    + "forces, densities and horizontals as trees aligned "
                    + "with Deconstruct's Member Lines, the slack flags, the "
                    + "spool length of each bar and, with EA wired, what to "
                    + "cut it to, the equilibrium residuals, and the cable "
                    + "utilisation against a capacity you wire. Forces are in "
                    + "the Result's own force unit, kN unless it says "
                    + "otherwise, converted to newtons where they meet EA or "
                    + "Cable Capacity. Demands only, unless a capacity is "
                    + "wired.",
                ComponentCategories.Read,
                "forces")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("6ca7992e-0d9c-46ed-85af-47448276d09d");

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
                "The Result passed through with Forces' own diagnostics "
                    + "replacing its earlier ones: counts, cable tension and "
                    + "slack, bar force, spool lengths and the cable "
                    + "utilisation. Chain it through Fit and Supports in any "
                    + "order; each child replaces only its own entries. Wire "
                    + "it to Diagnose.",
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
                    + "segment. forces.spool counts them. As a TREE with ONE "
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
            parameters.AddVectorParameter(
                "Residuals",
                "E",
                "The Result's equilibrium residual vector, ONE PER NODE IN "
                    + "VERTEX ORDER, as one branch. Like Fit's Deviation this "
                    + "has NO "
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
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }

            double axialStiffness = 0.0;
            data.GetData(1, ref axialStiffness);
            double cableCapacity = 0.0;
            data.GetData(2, ref cableCapacity);

            try
            {
                Readings r = Read(result, axialStiffness, cableCapacity);
                data.SetData(0, new ResultGoo(r.Result));
                data.SetDataTree(1, OutputTree.Numbers(r.MemberForce));
                data.SetDataTree(2, OutputTree.Numbers(r.ForceDensity));
                data.SetDataTree(3, OutputTree.Numbers(r.Horizontal));
                data.SetDataTree(4, OutputTree.Booleans(r.Slack));
                data.SetDataTree(5, OutputTree.Numbers(
                    r.Spool.Select(one => new[] { one })));
                data.SetDataTree(6, OutputTree.Numbers(r.EmitUnstrained
                    ? r.Unstrained.Select(one => new[] { one })
                    : Enumerable.Empty<IEnumerable<double>>()));
                data.SetDataTree(7, OutputTree.Vectors(new[] { r.Residuals }));
                data.SetDataTree(8, OutputTree.Numbers(r.EmitCableUtilisation
                    ? r.CableUtilisation
                    : Enumerable.Empty<IEnumerable<double>>()));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        /// <summary>
        /// Everything Forces computes, in one record, so the smoke harness
        /// can drive the same code path the canvas runs without a Rhino.
        /// <see cref="SolveInstance"/> is a thin shell over <see cref="Read"/>.
        /// </summary>
        internal sealed record Readings(
            ResultDto Result,
            List<List<double>> MemberForce,
            List<List<double>> ForceDensity,
            List<List<double>> Horizontal,
            List<List<bool>> Slack,
            List<double> Spool,
            List<double> Unstrained,
            bool EmitUnstrained,
            Vector3d[] Residuals,
            List<List<double>> CableUtilisation,
            bool EmitCableUtilisation);

        internal static Readings Read(
            ResultDto result,
            double axialStiffness,
            double cableCapacity)
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
            (int, int)[] edges = MouldGeometry.ValidEdges(equilibrium, n, out _);
            List<List<int>> runs = MouldGeometry.PrincipalRuns(equilibrium, n);
            int[] memberBar = MouldGeometry.MemberRunIndex(memberEnds, runs);

            // One branch per bar, then infill LAST. Copied from
            // Deconstruct's own local, so branch {i} is bar {i} in both.
            List<List<T>> ByBar<T>(IReadOnlyList<T> values)
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

            // The Result's forces carry a unit and the capacity is
            // newtons whatever it is, so a kN Result is converted before
            // the division rather than reported a thousand times too
            // small. An unknown unit buys nothing: a ratio between two
            // different units is not a utilisation, so none is published
            // and forces.utilisation names the unit instead.
            // Read ONCE, and every force this component reports carries
            // it. The contract refuses an empty forceUnit, so the fallback
            // is for a hand-built DTO alone, and it is the contract's own
            // default.
            string declaredUnit = (equilibrium.ForceUnit ?? string.Empty).Trim();
            string forceUnit = declaredUnit.Length > 0 ? declaredUnit : "kN";
            // Every place a Result's force meets a number the author wired
            // in newtons goes through this one factor: the utilisation
            // against Cable Capacity and the unstrained length against EA.
            // An unknown unit leaves the value unscaled and
            // forces.utilisation says which readings that touches.
            double? scale = MonitorMath.ToNewtons(forceUnit);
            bool forceUnitKnown = scale.HasValue;
            double toNewtons = scale ?? 1.0;
            bool cableRatio = cableCapacity > 0.0 && forceUnitKnown;

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
                // branches that forces.slack_cables, drawn from the same
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

            // ---- the other two populations, counted ---------------------
            // forces.counts keeps Monitor's full sentence, naming all four
            // populations, so the author sees the whole Result from any one
            // child. The columns and the anchors are Supports' to MEASURE;
            // here they are only counted, with the same skip tests and the
            // same grouping calls Supports makes, so the two components
            // cannot disagree about how many there are.
            int columnMembers = 0;
            if (block is not null)
            {
                foreach (IReadOnlyList<int> group in block.Trees)
                {
                    foreach (int m in group)
                    {
                        if (m < 0 || m >= block.Members.Count)
                            continue;
                        EdgeDto member = block.Members[m];
                        if (member.U < 0 || member.U >= block.Nodes.Count ||
                            member.V < 0 || member.V >= block.Nodes.Count)
                        {
                            continue;
                        }
                        columnMembers++;
                    }
                }
            }
            int[] nodeIds = ResultTables.SupportNodes(result);
            List<int>[] grouping = MouldGeometry.GroupingAdjacency(
                result, edges, n);
            List<List<int>> strips = MouldGeometry.ConnectedGroups(
                nodeIds, grouping);
            var onAStrip = new HashSet<int>(strips.SelectMany(s => s));
            int anchors = strips.Sum(strip => strip.Count) +
                ResultTables.Reactions(result)
                    .Count(item =>
                        item.Node >= 0 && item.Node < n &&
                        !onAStrip.Contains(item.Node));

            // One per node in VERTEX ORDER, from the table every reader of
            // this Result shares. It sits there rather than here because
            // it is the fourth per-Result table beside the members, the
            // supports and the reactions, and because a rule with no seam
            // is a rule nothing can measure.
            Vector3d[] residuals = ResultTables.Residuals(result);

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

            ResultDto annotated = ResultDiagnostics.Replace(
                result, "Forces", Diagnostics(
                    frame: frame,
                    cableForce: infillForce,
                    barForce: barMemberForce,
                    slackCables: slackCables,
                    columnMembers: columnMembers,
                    anchors: anchors,
                    spool: spool,
                    unstrained: axialStiffness > 0.0 ? unstrained : new List<double>(),
                    cableUtilisation: cableRatio
                        ? infillUtilisation
                        : new List<double>(),
                    spoolSegmentsWithoutMember: spoolSegmentsWithoutMember,
                    forceUnit: forceUnit,
                    forceUnitKnown: forceUnitKnown));

            return new Readings(
                annotated,
                ByBar(memberForce),
                ByBar(forceDensity),
                ByBar(horizontal),
                ByBar(slack),
                spool,
                unstrained,
                axialStiffness > 0.0,
                residuals,
                ByBar(cableUtilisation),
                cableRatio);
        }

        private static List<DiagnosticDto> Diagnostics(
            MouldFrameDto? frame,
            List<double> cableForce,
            List<double> barForce,
            int slackCables,
            int columnMembers,
            int anchors,
            List<double> spool,
            List<double> unstrained,
            List<double> cableUtilisation,
            int spoolSegmentsWithoutMember,
            string forceUnit,
            bool forceUnitKnown)
        {
            const string S = "Forces";
            var d = new List<DiagnosticDto>
            {
                ResultDiagnostics.Entry(S, "forces.counts", "info",
                    $"{cableForce.Count} infill cables, {barForce.Count} bar members, "
                        + $"{columnMembers} columns, {anchors} anchors"
                        + (frame is null ? ", read at the solved state" : $", read at frame {frame.Phase}"),
                    cableForce.Count, unit: "cables",
                    context: ResultDiagnostics.Context(
                        ("bars", barForce.Count.ToString(CultureInfo.InvariantCulture)),
                        ("columns", columnMembers.ToString(CultureInfo.InvariantCulture)),
                        ("anchors", anchors.ToString(CultureInfo.InvariantCulture)))),
            };

            if (cableForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "forces.cable_tension", "info",
                    $"cable tension {cableForce.Min():0} to {cableForce.Max():0} "
                        + forceUnit,
                    cableForce.Max(), unit: forceUnit,
                    context: ResultDiagnostics.Context(("min", cableForce.Min().ToString("0", CultureInfo.InvariantCulture)))));
                d.Add(slackCables == 0
                    ? ResultDiagnostics.Entry(S, "forces.slack_cables", "ok",
                        "no cable is slack: every one is still pulling", 0.0, unit: "cables")
                    : ResultDiagnostics.Entry(S, "forces.slack_cables", "warning",
                        $"{slackCables} cables are SLACK. A slack cable holds nothing, so the "
                            + "surface between its neighbours is unsupported. Raise the "
                            + "prestress or move the bars closer.",
                        slackCables, unit: "cables"));
            }
            if (barForce.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "forces.bar_force", "info",
                    $"bar axial force {barForce.Min():0} to {barForce.Max():0} "
                        + forceUnit,
                    barForce.Max(), unit: forceUnit));
            }
            if (spool.Count > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "forces.spool", "info",
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

            if (!forceUnitKnown)
            {
                // Dividing a force in an unknown unit by a capacity in newtons
                // is a ratio between two things, not a utilisation. The number
                // is refused rather than published with a caveat, because the
                // caveat would not travel with the number.
                d.Add(ResultDiagnostics.Entry(S, "forces.utilisation", "warning",
                    $"this Result's forces are in '{forceUnit}', which is neither N nor "
                        + "kN, so no cable utilisation is reported: Cable Capacity is "
                        + "newtons and there is nothing here to convert that unit with. "
                        + "Every force stays a demand, not a verdict. The same block "
                        + "leaves Unstrained Length reading the force UNCONVERTED "
                        + "against EA, which is newtons, so it is not to scale until "
                        + "this Result names a unit."));
            }
            else if (cableUtilisation.Count == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "forces.utilisation", "info",
                    "no infill cable is checked against a capacity, either because "
                        + "Cable Capacity is not wired or because this net has no "
                        + "infill, so every figure here is a DEMAND, NOT A VERDICT. "
                        + "Wire Cable Capacity to turn the infill forces into "
                        + "utilisations."));
            }
            else
            {
                // The figure is the worst of the INFILL alone. Cable Capacity
                // was asked for as the allowable tension in one infill cable,
                // so a notched bar's axial force has no business raising a
                // warning against it.
                double worstCable = cableUtilisation.Max();
                // Both units named, because this is the one figure on the
                // component that mixes them: the forces are the Result's and
                // the capacity is the author's, in newtons.
                string denominated = string.Equals(
                    forceUnit, "N", StringComparison.OrdinalIgnoreCase)
                    ? " The forces and the capacity are both in N."
                    : $" The forces are in {forceUnit}, converted to N against "
                        + "the capacity you supplied, which is in N.";
                d.Add(ResultDiagnostics.Entry(S, "forces.utilisation",
                    worstCable > 1.0 ? "warning" : "info",
                    $"utilisation infill cable up to {worstCable:0.###}"
                        + (worstCable > 1.0
                            ? ". Above one a member is OVER the capacity you supplied."
                            : " of the capacity you supplied.")
                        + denominated,
                    worstCable, tolerance: 1.0, unit: "ratio"));
            }
            d.Add(ResultDiagnostics.Entry(S, "forces.demand_only", "info",
                "every force here is a DEMAND. Utilisation is the one verdict "
                    + "on force, and only against a Cable Capacity you supplied "
                    + "yourself. Nothing else here assumes a limit."));
            return d;
        }
    }
}
