#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text.Json.Serialization;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Contracts
{
    /// <summary>
    /// Display-only style settings threaded through the Visualise tab: which
    /// analysis/classical/monochrome preset to draw, and the weight/vector
    /// scale multipliers Display layers on top of its own auto-scaling. This
    /// is deliberately thin; it carries no geometry and no solved data, only
    /// the presentation choices Display needs.
    ///
    /// The component that bundled these three fields, StyleComponent, is
    /// retired (the display wave, 2026-09-08): its own Preset value list
    /// moved to Display's own Preset input, which now reads its preset
    /// directly and falls back to a wired Style's Preset only when its own
    /// input is left blank. This DTO, StyleGoo and StyleParam are kept
    /// alive rather than deleted with it, because Display's optional Style
    /// input still accepts one, the way Weight and Vector Scale already
    /// did before this wave; nothing in the plugin builds a StyleDto any
    /// more, so a wire reaching Display's Style input now has to come from
    /// a hand-built source (an Expression or Script component).
    /// </summary>
    public sealed record StyleDto : ContractDto
    {
        public StyleDto()
            : base(ContractKinds.Style)
        {
        }

        [JsonIgnore]
        public override string ExpectedKind => ContractKinds.Style;

        public string Preset { get; init; } = "analysis";

        public double WeightScale { get; init; } = 1.0;

        /// <summary>Zero means Display chooses an automatic vector scale.</summary>
        public double VectorScale { get; init; } = 0.0;

        protected override void ValidatePayload(List<string> errors)
        {
            string preset = NormalisePreset(Preset);
            if (preset is not ("analysis" or "classical" or "monochrome"))
                errors.Add("preset must be Analysis, Classical GS, or Monochrome.");
            if (!ContractRules.IsFinite(WeightScale) || WeightScale <= 0.0)
                errors.Add("weightScale must be finite and greater than zero.");
            if (!ContractRules.IsFinite(VectorScale) || VectorScale < 0.0)
            {
                errors.Add(
                    "vectorScale must be finite and non-negative; zero " +
                    "means automatic.");
            }
        }

        /// <summary>
        /// Copied from the deleted <c>GraphicDiagramDisplayComponent</c>'s
        /// <c>NormaliseStyle</c> so this contract accepts the same preset
        /// spellings without a contract referencing a component. Unlike the
        /// source, an unrecognised value is returned as-is rather than
        /// thrown, so callers can decide whether to treat it as a
        /// validation error or a runtime exception.
        /// </summary>
        public static string NormalisePreset(string? value)
        {
            string style = (value ?? string.Empty)
                .Trim()
                .ToLowerInvariant()
                .Replace(" ", "_", StringComparison.Ordinal)
                .Replace("-", "_", StringComparison.Ordinal);
            return style switch
            {
                "" => "analysis",
                "classical_gs" or "graphic_statics" => "classical",
                "mono" => "monochrome",
                _ => style
            };
        }
    }

    public sealed class StyleGoo : ContractGoo<StyleDto>
    {
        public StyleGoo()
        {
        }

        public StyleGoo(StyleDto value)
            : base(value)
        {
        }

        protected override string ExpectedKind => ContractKinds.Style;
        public override string TypeName => "Ananke Style";
        public override string TypeDescription =>
            "Display preset, weight scale, and vector scale bundled for " +
            "one Display call.";

        protected override ContractGoo<StyleDto> Create(StyleDto? value) =>
            value is null ? new StyleGoo() : new StyleGoo(value);

        protected override string Format(StyleDto value)
        {
            string preset = StyleDto.NormalisePreset(value.Preset);
            string vector = value.VectorScale > 0.0
                ? $"x{value.VectorScale:G4}"
                : "auto";
            return $"Style · {preset} · weight x{value.WeightScale:G4} " +
                $"· vector {vector}";
        }
    }

    public sealed class StyleParam : ContractParam<StyleGoo>
    {
        public StyleParam()
            : base(
                "Style",
                "STY",
                "Display preset, weight scale, and vector scale bundled " +
                "for one Display call.")
        {
        }

        public override Guid ComponentGuid =>
            new("6513f056-cf3c-4e4c-b999-ac865a55ee54");
    }
}

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// The member, support and reaction tables of a Result in ONE fixed
    /// order, so every component that branches by member or by support
    /// strip reads the same rows. Deconstruct builds its geometry from
    /// them and Forces its numbers, which is what makes their trees align
    /// item for item without either matching coordinates.
    /// </summary>
    internal static class ResultTables
    {
        /// <summary>One member: its equilibrium ends, signed force, q and H
        /// (NaN when the Result does not carry them), and its stable id.</summary>
        public readonly record struct MemberRow(
            int U, int V, double Force, double Q, double H, int Id, int EquilibriumEdgeId);

        public static bool IsTna(ResultDto result) =>
            string.Equals(result.Solver, "tna", StringComparison.OrdinalIgnoreCase) &&
            result.FormGraph is not null &&
            result.ForceGraph is not null &&
            result.Mappings is not null;

        /// <summary>TNA: edge states ordered by Id; FD: equilibrium edges in order.</summary>
        public static MemberRow[] Members(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            if (IsTna(result))
            {
                return result.EdgeStates
                    .OrderBy(state => state.Id)
                    .Select(state =>
                    {
                        (int u, int v) = Ends(equilibrium, state.EquilibriumEdgeId);
                        return new MemberRow(
                            u, v, state.AxialForce, state.ForceDensity,
                            state.HorizontalForce, state.Id, state.EquilibriumEdgeId);
                    })
                    .ToArray();
            }

            // FD carries no horizontal-force demand and may carry no force
            // densities at all. NaN rather than zero, because zero is a real
            // reading a reader would draw and believe.
            var rows = new MemberRow[equilibrium.Edges.Count];
            for (int i = 0; i < rows.Length; i++)
            {
                (int u, int v) = Ends(equilibrium, i);
                double force = i < equilibrium.MemberForces.Count
                    ? equilibrium.MemberForces[i]
                    : 0.0;
                double q = i < equilibrium.ForceDensities.Count
                    ? equilibrium.ForceDensities[i]
                    : double.NaN;
                rows[i] = new MemberRow(u, v, force, q, double.NaN, i, i);
            }
            return rows;
        }

        /// <summary>
        /// Support node ids in the order Deconstruct's Node IDs use before
        /// stripping: TNA Mappings.Supports, FD ResolvedSupportNodeIds.
        ///
        /// An id this net does not have is dropped HERE, once, so both
        /// readers drop the same one. TnaMappingsDto carries no validation
        /// of its own and ResultDto.Validate never reaches it, so a Result
        /// deserialised straight from JSON can name a vertex that is not
        /// there; the FD list is already range-checked by the contract and
        /// the same filter costs it nothing. Dropping it here rather than
        /// at each reader is what stops one component indexing off the end
        /// of the vertex list while the other quietly walks on.
        /// </summary>
        public static int[] SupportNodes(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            int count = equilibrium.Vertices.Count;
            return (IsTna(result)
                    ? result.Mappings!.Supports
                        .Select(item => item.EquilibriumVertexId)
                    : equilibrium.ResolvedSupportNodeIds.AsEnumerable())
                .Where(id => id >= 0 && id < count)
                .ToArray();
        }

        /// <summary>Reactions by node: TNA Mappings.Reactions with zero-length
        /// vectors dropped, FD equilibrium.Reactions in order.</summary>
        public static (int Node, Vector3d Vector)[] Reactions(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            if (IsTna(result))
            {
                return result.Mappings!.Reactions
                    .Select(item => (
                        item.EquilibriumVertexId,
                        new Vector3d(
                            item.Reaction.X, item.Reaction.Y, item.Reaction.Z)))
                    .Where(item => item.Item2.SquareLength > 1.0e-24)
                    .ToArray();
            }
            return equilibrium.Reactions
                .Select(item => (
                    item.NodeId,
                    new Vector3d(item.Vector.X, item.Vector.Y, item.Vector.Z)))
                .ToArray();
        }

        /// <summary>
        /// The residual at every node IN VERTEX ORDER, and the fourth
        /// per-Result table beside the members, the supports and the
        /// reactions.
        ///
        /// The Result's own list is sparse: the codec writes no entry for a
        /// support and none for an exact zero. A node carrying none holds
        /// its slot here as a zero rather than shifting its neighbours up,
        /// which is what reading that sparse list positionally would do:
        /// node 7's residual would land at item 4 and every node after it
        /// would read someone else's. Out-of-range node ids are ignored for
        /// the same reason the reactions ignore them.
        /// </summary>
        public static Vector3d[] Residuals(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            var placed = new Vector3d[equilibrium.Vertices.Count];
            foreach (NodalVectorDto item in equilibrium.Residuals)
            {
                if (item.NodeId >= 0 && item.NodeId < placed.Length)
                {
                    placed[item.NodeId] = new Vector3d(
                        item.Vector.X, item.Vector.Y, item.Vector.Z);
                }
            }
            return placed;
        }

        /// <summary>
        /// The two node indices a member runs between, or (-1, -1) if the id
        /// does not name a real edge. The ONE ends lookup: Deconstruct's
        /// Member Lines and Forces' numbers both come through here, so they
        /// cannot disagree about which two nodes a member joins.
        ///
        /// Out of range rather than throwing, because this decides which
        /// BRANCH a member goes in. A member whose ends cannot be read is
        /// still a member and still belongs in the output; it lands in the
        /// infill branch, which is where anything not proved to be on a bar
        /// belongs anyway.
        /// </summary>
        public static (int U, int V) Ends(
            EquilibriumResultDto equilibrium,
            int edgeId)
        {
            if (edgeId < 0 || edgeId >= equilibrium.Edges.Count)
                return (-1, -1);
            EdgeDto edge = equilibrium.Edges[edgeId];
            return (edge.U, edge.V);
        }
    }

    /// <summary>
    /// The GEOMETRY of a solved Result: lines, points, vectors and the ids
    /// that name them. Nothing else. The numbers each member and support
    /// carries (member force, force density, horizontal force, slack,
    /// residuals) belong to Forces, and the cells of the skin to Skin, so a
    /// canvas that wants the shape does not drag the whole analysis behind
    /// it.
    ///
    /// It reads the unified <see cref="ResultDto"/> and takes one of two
    /// extraction paths keyed on <see cref="ResultDto.Solver"/> plus the
    /// null-ness of the reciprocal members: the richer TNA path (form/force
    /// graphs, edge states, mappings) or the flat FD path.
    ///
    /// Its member, support and reaction order comes from
    /// <see cref="ResultTables"/>, which is the same table Forces reads, so
    /// Forces' number trees line up with these geometry trees branch for
    /// branch and item for item without either component matching
    /// coordinates.
    /// </summary>
    public sealed class DeconstructComponent : NativeComponentBase
    {
        public DeconstructComponent()
            : base(
                "Deconstruct",
                "Deconstruct",
                "Extract the statics geometry of one solved FD or TNA " +
                "Result: member, form and force lines, supports, loads and " +
                "reactions. Forces, Fit and Supports carry the numbers, " +
                "Frame the built state and Skin the cells. Reciprocal-only " +
                "streams (Form Lines, Force Lines) come out empty for FD.",
                ComponentCategories.Read,
                "result_breakdown")
        {
            // Deconstruct is a data boundary, not a renderer: Display owns
            // the viewport. Grasshopper's default red preview on these
            // geometry outputs is what clashed with Display's element
            // colours, so previews start hidden; each output can still be
            // re-enabled from its own context menu.
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("68d0b4f2-9a3e-4c17-85d6-f2b8a0c4e961");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Solved FD or TNA result.",
                GH_ParamAccess.item);
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddLineParameter(
                "Member Lines",
                "M",
                "Resolved spatial member axes, as a TREE: one branch per " +
                "principal line holding that bar's own members, and a LAST " +
                "branch holding the infill, everything not on a bar. Every " +
                "member-aligned output below is branched and ordered " +
                "identically, and so are FORCES' number trees (Member " +
                "Force, Force Density, Horizontal Force, Slack) for the " +
                "same Result, so the alignment holds branch to branch and " +
                "item to item across both components. " +
                "A bar with no members of its own keeps an empty branch, " +
                "so branch {i} is always bar {i}.",
                GH_ParamAccess.tree);
            parameters.AddLineParameter(
                "Form Lines",
                "FL",
                "Planar form-diagram edges, branched and ordered exactly " +
                "as Member Lines. Empty for FD.",
                GH_ParamAccess.tree);
            parameters.AddIntegerParameter(
                "Member IDs",
                "MID",
                "Stable member IDs, branched and ordered exactly as " +
                "Member Lines.",
                GH_ParamAccess.tree);
            parameters.AddIntegerParameter(
                "Node IDs",
                "NID",
                "Resolved support node IDs, as a TREE with one branch per " +
                "CONNECTED STRIP of supports, walked end to end. Branched " +
                "and ordered exactly as Support Points, so opposite sides " +
                "of the vault arrive as separate branches.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Support Points",
                "SP",
                "Resolved structural-support locations, branched and " +
                "ordered exactly as Node IDs.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Load Points",
                "LP",
                "Points carrying applied loads. TNA: non-zero only; FD: " +
                "unfiltered.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Load Vectors",
                "LV",
                "Applied load vectors aligned with Load Points. TNA: " +
                "non-zero only; FD: unfiltered.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Reaction Points",
                "RP",
                "Points carrying support reactions, as a TREE branched and " +
                "ordered EXACTLY as Support Points: one branch per " +
                "connected strip of supports, walked end to end, so strip " +
                "{i} item [k] names the same support in Node IDs, Support " +
                "Points and here. A support carrying no reaction holds its " +
                "slot as a zero rather than dropping out, which is what " +
                "keeps that correspondence true.",
                GH_ParamAccess.tree);
            parameters.AddVectorParameter(
                "Reaction Vectors",
                "RV",
                "Support reactions, branched and ordered exactly as " +
                "Reaction Points and Support Points. Sum one branch to get " +
                "what a single side of the vault puts into the ground.",
                GH_ParamAccess.tree);
            // APPENDED, and it has to stay appended: every slot above is an
            // index some saved definition's wire already sits on, so a new
            // port anywhere but the end would move one of them silently.
            parameters.AddLineParameter(
                "Force Lines",
                "FCL",
                "The reciprocal FORCE diagram's edges, branched and ordered "
                    + "exactly as Member Lines and Form Lines, so branch {i} "
                    + "item [k] is the same member in all three. This is the "
                    + "force polygon at its OWN coordinates: Display lays a "
                    + "copy of it out beside the model to draw, and this "
                    + "hands back the diagram itself. Empty for FD, which "
                    + "has no reciprocal diagram.",
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

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                EquilibriumResultDto equilibrium = result.Equilibrium!;
                bool isTna = ResultTables.IsTna(result);

                // The one ordering every reader of this Result shares.
                // Forces builds its numbers from these same rows, which is
                // what makes its trees align with the geometry trees here
                // without either component matching coordinates.
                ResultTables.MemberRow[] members = ResultTables.Members(result);
                int[] memberIds = members.Select(row => row.Id).ToArray();
                // The two ends of each member as NODE INDICES, which is what
                // says whether a member lies along a principal line. The lines
                // themselves cannot answer that: a point is not an index, and
                // matching by coordinate would make an exact question into a
                // tolerance one.
                (int U, int V)[] memberEnds = members
                    .Select(row => (row.U, row.V))
                    .ToArray();
                int[] nodeIds = ResultTables.SupportNodes(result);
                // The support POINTS come off that same list rather than
                // being read a second time from the Result, so a support id
                // this net does not have is dropped in ONE place and both
                // this component and Forces drop the same one. Reading
                // Mappings.Supports again here is what let a bad id throw on
                // this side while Forces walked past it.
                Point3d[] supportPoints = nodeIds
                    .Select(id => Point(equilibrium.Vertices[id]))
                    .ToArray();
                // Reactions carry the NODE they act at, not just a point.
                // Grouping them by strip is a question about which support
                // they belong to, and that is an index question; matching them
                // back by coordinate would turn an exact answer into a
                // tolerance.
                //
                // The point is read from the node rather than carried
                // alongside it because that is where it came from anyway: both
                // codecs build every NodalVectorDto as
                // (nodeId, vertices[nodeId], vector), so the vertex IS the
                // point. Nothing downstream re-checks the id, though. A
                // ResultDto deserialised straight from JSON can name a node
                // this net does not have, and result.Validate() would not stop
                // it, so a reaction whose node is out of range is dropped here
                // rather than indexing off the end of the vertex list.
                (int Node, Point3d Point, Vector3d Vector)[] reactions =
                    ResultTables.Reactions(result)
                        .Where(item =>
                            item.Node >= 0 &&
                            item.Node < equilibrium.Vertices.Count)
                        .Select(item => (
                            item.Node,
                            Point(equilibrium.Vertices[item.Node]),
                            item.Vector))
                        .ToArray();

                Line[] memberLines;
                Line[] formLines;
                (Point3d Point, Vector3d Vector)[] loads;

                if (isTna)
                {
                    // Both line arrays are driven by the TABLE's rows, not by
                    // a second sort of the edge states. Two sorts that agree
                    // today are still two places to disagree tomorrow, and the
                    // point of the table is that there is one order.
                    var stateById = new Dictionary<int, TnaEdgeStateDto>();
                    foreach (TnaEdgeStateDto state in result.EdgeStates)
                        stateById[state.Id] = state;
                    IReadOnlyDictionary<int, TnaGraphEdgeDto> formEdges =
                        result.FormGraph!.Edges.ToDictionary(edge => edge.Id);
                    IReadOnlyDictionary<int, Point3Dto> formPoints =
                        result.FormGraph!.Vertices.ToDictionary(
                            vertex => vertex.Id,
                            vertex => vertex.Point);

                    memberLines = members
                        .Select(row => ThrustLine(
                            equilibrium, row.EquilibriumEdgeId))
                        .ToArray();
                    formLines = members
                        .Select(row => FormLine(
                            stateById[row.Id], formEdges, formPoints))
                        .ToArray();

                    loads = result.Mappings!.Loads
                        .Select(item => (
                            Point(equilibrium.Vertices[item.EquilibriumVertexId]),
                            Vector(item.Vector)))
                        .Where(item => item.Item2.SquareLength > 1.0e-24)
                        .ToArray();
                }
                else
                {
                    memberLines = MemberLines(equilibrium);
                    formLines = Array.Empty<Line>();

                    loads = equilibrium.Loads
                        .Select(item => (Point(item.Point), Vector(item.Vector)))
                        .ToArray();
                }

                // The force diagram, on the SAME rows as the form diagram
                // above. Read from the Result rather than from the locals of
                // the branch above so the rule "one line per member row, at
                // the force graph's own coordinates, nothing for FD" is one
                // method the harness can drive without a Result the whole
                // component would accept.
                Line[] forceLines = ForceLines(result, members);

                // ---- grouping ----------------------------------------------
                // The principal lines this Result carries, resolved upstream by
                // Pattern from the curves drawn into it, travelling in the
                // contract, so this component reads the same bars Animate and
                // Column Finder do rather than deriving its own and
                // disagreeing with them.
                List<List<int>> bars = MouldGeometry.PrincipalRuns(
                    equilibrium, equilibrium.Vertices.Count);
                int[] memberBar = MouldGeometry.MemberRunIndex(
                    memberEnds, bars);

                // One branch per bar, then infill LAST. Every member-aligned
                // output is sliced by the same index array below, so the
                // index-to-index alignment the old flat lists promised now
                // holds branch to branch as well.
                IEnumerable<IEnumerable<T>> ByBar<T>(IReadOnlyList<T> values)
                {
                    var branches = new List<List<T>>();
                    for (int b = 0; b <= bars.Count; b++)
                        branches.Add(new List<T>());
                    for (int i = 0; i < values.Count; i++)
                    {
                        int bar = i < memberBar.Length ? memberBar[i] : -1;
                        branches[bar >= 0 ? bar : bars.Count].Add(values[i]);
                    }
                    return branches;
                }

                // The supports, split into the strips they physically form.
                //
                // Grouped over the plan as drawn unioned with the solved net.
                // The solved net alone is the wrong graph here: it carries no
                // edge between two supports, because such an edge joins two
                // fixed nodes and contributes no unknown, so every anchor comes
                // back isolated and the tree degenerates into one branch per
                // point. See MouldGeometry.GroupingAdjacency.
                (int, int)[] netEdges = MouldGeometry.ValidEdges(
                    equilibrium, equilibrium.Vertices.Count, out _);
                List<int>[] neighbours = MouldGeometry.GroupingAdjacency(
                    result, netEdges, equilibrium.Vertices.Count);
                List<List<int>> strips = MouldGeometry.ConnectedGroups(
                    nodeIds, neighbours);
                var nodeIdAt = new Dictionary<int, int>();
                for (int i = 0; i < nodeIds.Length; i++)
                    nodeIdAt[nodeIds[i]] = i;

                data.SetDataTree(0, OutputTree.Lines(ByBar(memberLines)));
                data.SetDataTree(1, OutputTree.Lines(ByBar(formLines)));
                data.SetDataTree(2, OutputTree.Integers(ByBar(memberIds)));
                data.SetDataTree(3, OutputTree.Integers(
                    strips.Select(strip => strip.AsEnumerable())));
                data.SetDataTree(4, OutputTree.Points(
                    strips.Select(strip => strip
                        .Where(nodeIdAt.ContainsKey)
                        .Select(id => supportPoints[nodeIdAt[id]]))));
                // The reactions, laid out ON the support strips.
                //
                // Branched AND ordered exactly as Support Points, item for
                // item, so strip {i} item [k] is the same support in all
                // three outputs. That alignment costs something and it is
                // worth stating: a support carrying no reaction is now a ZERO
                // VECTOR holding its own slot rather than being dropped.
                // Dropping it is what made the old flat list unreadable
                // against the supports, because nothing said which support a
                // given reaction belonged to short of matching coordinates by
                // eye.
                var reactionAt = new Dictionary<int, (Point3d P, Vector3d V)>();
                foreach ((int node, Point3d p, Vector3d vec) in reactions)
                    reactionAt[node] = (p, vec);

                var reactionPointBranches = new List<List<Point3d>>();
                var reactionVectorBranches = new List<List<Vector3d>>();
                foreach (List<int> strip in strips)
                {
                    var points = new List<Point3d>();
                    var vectors = new List<Vector3d>();
                    foreach (int id in strip)
                    {
                        if (reactionAt.TryGetValue(id, out var found))
                        {
                            points.Add(found.P);
                            vectors.Add(found.V);
                        }
                        else
                        {
                            points.Add(nodeIdAt.TryGetValue(id, out int at)
                                ? supportPoints[at]
                                : Point3d.Origin);
                            vectors.Add(Vector3d.Zero);
                        }
                    }
                    reactionPointBranches.Add(points);
                    reactionVectorBranches.Add(vectors);
                }

                // A reaction at a node that is not a support should not exist.
                // If one ever does it gets a branch of its own at the end,
                // because losing it silently would be worse than an extra
                // branch nobody expected.
                var onAStrip = new HashSet<int>(strips.SelectMany(s => s));
                var strayPoints = new List<Point3d>();
                var strayVectors = new List<Vector3d>();
                foreach ((int node, Point3d p, Vector3d vec) in reactions)
                {
                    if (onAStrip.Contains(node))
                        continue;
                    strayPoints.Add(p);
                    strayVectors.Add(vec);
                }
                if (strayPoints.Count > 0)
                {
                    reactionPointBranches.Add(strayPoints);
                    reactionVectorBranches.Add(strayVectors);
                }

                data.SetDataList(5, loads.Select(item => item.Point));
                data.SetDataList(6, loads.Select(item => item.Vector));
                data.SetDataTree(7, OutputTree.Points(reactionPointBranches));
                data.SetDataTree(8, OutputTree.Vectors(reactionVectorBranches));
                data.SetDataTree(9, OutputTree.Lines(ByBar(forceLines)));
                Message =
                    $"{result.Solver.ToUpperInvariant()} · " +
                    $"{memberLines.Length} members";
            }
            catch (Exception error)
            {
                Message = "Invalid";
                ReportException("Deconstruct failed", error);
            }
        }

        /// <summary>Copied from <c>TnaQueryGeometry.ThrustMesh</c>. The
        /// Thrust Mesh OUTPUT left in the readers rework (Frame carries the
        /// surface); the helper stays because Skin and Export build the
        /// surface through it.</summary>
        internal static Mesh ThrustMesh(ResultDto result)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium!;
            TnaDiagramGraphDto formGraph = result.FormGraph!;
            TnaMappingsDto mappings = result.Mappings!;

            Dictionary<int, int> formToEquilibrium = mappings
                .SourceVertexToFormVertex
                .Where(item =>
                    item.FormVertexId.HasValue &&
                    item.EquilibriumVertexId.HasValue)
                .GroupBy(item => item.FormVertexId!.Value)
                .ToDictionary(
                    group => group.Key,
                    group =>
                    {
                        int[] equilibriumIds = group
                            .Select(item => item.EquilibriumVertexId!.Value)
                            .Distinct()
                            .ToArray();
                        if (equilibriumIds.Length != 1)
                        {
                            throw new InvalidOperationException(
                                $"Form vertex {group.Key} maps to multiple " +
                                "equilibrium vertices.");
                        }
                        return equilibriumIds[0];
                    });

            var mesh = new Mesh();
            var formToMesh = new Dictionary<int, int>();
            foreach (TnaGraphVertexDto vertex in
                     formGraph.Vertices.OrderBy(item => item.Id))
            {
                if (!formToEquilibrium.TryGetValue(
                        vertex.Id,
                        out int equilibriumId))
                {
                    throw new InvalidOperationException(
                        $"Form vertex {vertex.Id} has no explicit " +
                        "equilibrium vertex mapping.");
                }
                if (equilibriumId < 0 ||
                    equilibriumId >= equilibrium.Vertices.Count)
                {
                    throw new InvalidOperationException(
                        $"Form vertex {vertex.Id} has no equilibrium vertex.");
                }
                formToMesh[vertex.Id] = mesh.Vertices.Add(
                    Point(equilibrium.Vertices[equilibriumId]));
            }

            foreach (TnaGraphFaceDto face in
                     formGraph.Faces.OrderBy(item => item.Id))
            {
                int[] vertices = face.Vertices
                    .Select(id => formToMesh.TryGetValue(id, out int meshId)
                        ? meshId
                        : throw new InvalidOperationException(
                            $"Form face {face.Id} references unknown " +
                            $"vertex {id}."))
                    .ToArray();
                if (vertices.Length == 3)
                {
                    mesh.Faces.AddFace(vertices[0], vertices[1], vertices[2]);
                }
                else if (vertices.Length == 4)
                {
                    mesh.Faces.AddFace(
                        vertices[0],
                        vertices[1],
                        vertices[2],
                        vertices[3]);
                }
                else
                {
                    for (int index = 1; index < vertices.Length - 1; index++)
                    {
                        mesh.Faces.AddFace(
                            vertices[0],
                            vertices[index],
                            vertices[index + 1]);
                    }
                }
            }

            if (mesh.Faces.Count > 0)
                mesh.Normals.ComputeNormals();
            mesh.Compact();
            return mesh;
        }

        /// <summary>
        /// Copied from <c>TnaQueryGeometry.ThrustLine</c>, then rewritten to
        /// take the equilibrium edge id straight off a
        /// <see cref="ResultTables.MemberRow"/> and read its two ends from
        /// <see cref="ResultTables.Ends"/>, the same lookup the table itself
        /// uses. That is what makes a Member Line and the row Forces numbers
        /// describe the same member: they are not two readings of the edge
        /// that happen to agree, they are one reading drawn twice.
        ///
        /// A member whose ends cannot be read keeps its SLOT as a default
        /// line rather than throwing, which is the contract
        /// <see cref="ResultTables.Ends"/> states and the one Forces
        /// already honours. Indexing the vertex list with the (-1, -1) it
        /// promises would take the whole component down and leave Forces
        /// emitting a full set of trees against no geometry at all, on
        /// exactly the Result that contract was written for.
        /// </summary>
        private static Line ThrustLine(
            EquilibriumResultDto equilibrium,
            int equilibriumEdgeId)
        {
            (int u, int v) = ResultTables.Ends(equilibrium, equilibriumEdgeId);
            if (u < 0 || v < 0)
                return default;
            return new Line(
                Point(equilibrium.Vertices[u]),
                Point(equilibrium.Vertices[v]));
        }

        /// <summary>
        /// The block's trees as Grasshopper will branch them: one branch per
        /// tree in the block's own order, every member a line from LOWER end
        /// to UPPER end, and the heads and feet of each tree as points, each
        /// node once. No block, empty trees: a Result that has not been
        /// through Columns is not an error here.
        /// </summary>
        internal static (List<List<Line>>, List<List<Point3d>>, List<List<Point3d>>)
            ColumnTrees(MouldColumnsDto? block)
        {
            var lines = new List<List<Line>>();
            var heads = new List<List<Point3d>>();
            var feet = new List<List<Point3d>>();
            if (block is null)
                return (lines, heads, feet);

            Point3d[] nodes = block.Nodes.Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray();
            var headSet = new HashSet<int>(block.Heads);
            var footSet = new HashSet<int>(block.Feet);
            foreach (IReadOnlyList<int> tree in block.Trees)
            {
                var treeLines = new List<Line>();
                var treeHeads = new List<Point3d>();
                var treeFeet = new List<Point3d>();
                var seen = new HashSet<int>();
                foreach (int m in tree)
                {
                    if (m < 0 || m >= block.Members.Count)
                        continue;
                    EdgeDto member = block.Members[m];
                    if (member.U < 0 || member.U >= nodes.Length ||
                        member.V < 0 || member.V >= nodes.Length)
                    {
                        continue;
                    }
                    treeLines.Add(new Line(nodes[member.U], nodes[member.V]));
                    foreach (int end in new[] { member.U, member.V })
                    {
                        if (!seen.Add(end))
                            continue;
                        if (headSet.Contains(end))
                            treeHeads.Add(nodes[end]);
                        if (footSet.Contains(end))
                            treeFeet.Add(nodes[end]);
                    }
                }
                lines.Add(treeLines);
                heads.Add(treeHeads);
                feet.Add(treeFeet);
            }
            return (lines, heads, feet);
        }

        /// <summary>Copied from <c>TnaQueryGeometry.FormLine</c>.</summary>
        private static Line FormLine(
            TnaEdgeStateDto state,
            IReadOnlyDictionary<int, TnaGraphEdgeDto> edges,
            IReadOnlyDictionary<int, Point3Dto> points)
        {
            if (!edges.TryGetValue(state.FormEdgeId, out TnaGraphEdgeDto? edge))
            {
                throw new InvalidOperationException(
                    $"Member {state.Id} references unknown form edge " +
                    $"{state.FormEdgeId}.");
            }
            if (!points.TryGetValue(edge.U, out Point3Dto? start) ||
                !points.TryGetValue(edge.V, out Point3Dto? end))
            {
                throw new InvalidOperationException(
                    $"Form edge {edge.Id} references an unknown form vertex.");
            }
            return new Line(Point(start), Point(end));
        }

        /// <summary>
        /// The reciprocal FORCE diagram, one line per member row and in the
        /// same order, so it branches beside Member Lines and Form Lines
        /// item for item.
        ///
        /// This is the diagram at its own coordinates. Display draws a copy
        /// laid out beside the model, which is a drawing decision and takes
        /// a Gap input this component does not have; what travels down a
        /// wire is the polygon itself, which is what a bake or a measurement
        /// wants.
        ///
        /// Empty for anything that is not a TNA Result: FD carries no
        /// reciprocal diagram at all. The edge-state lookup is rebuilt here
        /// rather than shared with the caller, which costs one dictionary
        /// over the members per solve and buys a rule that can be driven on
        /// its own, with a Result and nothing else.
        /// </summary>
        internal static Line[] ForceLines(
            ResultDto result,
            IReadOnlyList<ResultTables.MemberRow> members)
        {
            if (!ResultTables.IsTna(result))
                return Array.Empty<Line>();
            var stateById = new Dictionary<int, TnaEdgeStateDto>();
            foreach (TnaEdgeStateDto state in result.EdgeStates)
                stateById[state.Id] = state;
            IReadOnlyDictionary<int, TnaGraphEdgeDto> edges =
                result.ForceGraph!.Edges.ToDictionary(edge => edge.Id);
            IReadOnlyDictionary<int, Point3Dto> points =
                result.ForceGraph!.Vertices.ToDictionary(
                    vertex => vertex.Id,
                    vertex => vertex.Point);
            var lines = new Line[members.Count];
            for (int index = 0; index < members.Count; index++)
                lines[index] = ForceLine(stateById[members[index].Id], edges, points);
            return lines;
        }

        /// <summary>
        /// <see cref="FormLine"/>'s twin on the other diagram: the force
        /// edge a member's state NAMES, not the edge at its own index.
        /// </summary>
        private static Line ForceLine(
            TnaEdgeStateDto state,
            IReadOnlyDictionary<int, TnaGraphEdgeDto> edges,
            IReadOnlyDictionary<int, Point3Dto> points)
        {
            if (!edges.TryGetValue(state.ForceEdgeId, out TnaGraphEdgeDto? edge))
            {
                throw new InvalidOperationException(
                    $"Member {state.Id} references unknown force edge " +
                    $"{state.ForceEdgeId}.");
            }
            if (!points.TryGetValue(edge.U, out Point3Dto? start) ||
                !points.TryGetValue(edge.V, out Point3Dto? end))
            {
                throw new InvalidOperationException(
                    $"Force edge {edge.Id} references an unknown force vertex.");
            }
            return new Line(Point(start), Point(end));
        }

        /// <summary>Copied from <c>ResultBreakdownComponent.MemberLines</c>.</summary>
        private static Line[] MemberLines(EquilibriumResultDto equilibrium)
        {
            return equilibrium.Edges
                .Select(edge => new Line(
                    Point(equilibrium.Vertices[edge.U]),
                    Point(equilibrium.Vertices[edge.V])))
                .ToArray();
        }

        private static Point3d Point(Point3Dto value) =>
            new(value.X, value.Y, value.Z);

        private static Vector3d Vector(Point3Dto value) =>
            new(value.X, value.Y, value.Z);
    }

    /// <summary>
    /// The one native viewport boundary for a solved Result: lifts the
    /// side-by-side reciprocal layout out of the deleted
    /// <c>TnaReciprocalComponent</c>, the styled line weights/colours out of
    /// the deleted <c>GraphicDiagramDisplayComponent</c>, and the
    /// load/reaction/residual vector drawing out of the deleted
    /// <c>EquilibriumPreviewComponent</c>, so drawing now happens in one
    /// current place. Each of those older display-capable components' logic
    /// was copied here, not called, before all three were deleted.
    ///
    /// The display wave (2026-09-08) retires StyleComponent and moves its
    /// Preset value list here: Preset is APPENDED at input 7 rather than
    /// replacing the Style input at 1, so no existing wire on Elements,
    /// Metric, Weight, Vector Scale or Gap moves. Display's own Preset
    /// input wins whenever it carries a value; a wired Style's Preset is
    /// still honoured, but only as the fallback for when Preset is left
    /// blank, matching the priority Weight and Vector Scale already gave
    /// their own inputs over Style's fields. The same wave APPENDS Force
    /// Scale at input 8: it sizes the reciprocal force diagram's own
    /// layout, against the form diagram's span, independently of Vector
    /// Scale (which sizes load/reaction/residual arrows); one reproduces
    /// today's fixed fit exactly.
    ///
    /// The same wave also settles how load/reaction/residual arrows scale:
    /// <c>VectorArrowLine</c> draws each one at the vector's own magnitude
    /// times Vector Scale, RhinoVAULT's own rule (read directly from the
    /// installed plugin's <c>draw_thrust_loads</c>, not guessed at), and a
    /// vector at or below the near-zero tolerance draws NOTHING rather
    /// than a zero-length line -- a gap that existed on the FD
    /// loads/reactions and the shared residuals branch, which had no
    /// zero-skip before this wave even though the TNA branches already
    /// did.
    /// </summary>
    public sealed class DisplayComponent : NativePreviewComponentBase
    {
        private static readonly ComponentValueListSpec[] ValueLists =
        {
            new(
                2,
                "Elements",
                new (string Label, string Value)[]
                {
                    ("Thrust", "thrust"),
                    ("Force", "force"),
                    ("Loads", "loads"),
                    ("Reactions", "reactions"),
                    ("Residuals", "residuals")
                },
                "thrust,force",
                true),
            new(
                3,
                "Metric",
                new (string Label, string Value)[]
                {
                    ("None", "none"),
                    ("Force Density q", "q"),
                    ("Horizontal Force H", "H"),
                    ("Axial Force F", "F")
                },
                "none"),
            // APPENDED: StyleComponent's own Preset dropdown, retired along
            // with the component itself. Placed under Preset's own input
            // (index 7), not under Style's (index 1), so the fresh-vs-
            // archive placement rule in SuggestedValueListPlacement.Create
            // still keys off Preset's own pivot and this addition costs no
            // existing wire its port; see the class doc comment above.
            new(
                7,
                "Preset",
                new (string Label, string Value)[]
                {
                    ("Analysis", "analysis"),
                    ("Classical GS", "classical"),
                    ("Monochrome", "monochrome")
                },
                "analysis")
        };

        // The force diagram's fit fraction at Force Scale 1.0 -- pinned so
        // the default reproduces today's drawing exactly. Force Scale
        // multiplies it directly, so the diagram's drawn extent scales
        // linearly with the input.
        private const double ForceDiagramBaseFitFraction = 0.35;

        private readonly List<DrawLine> _preview = new();
        private BoundingBox _clippingBox = BoundingBox.Empty;

        public DisplayComponent()
            : base(
                "Display",
                "Display",
                "Draw a solved Result's element lines: thrust network, " +
                "reciprocal force diagram, and mapped " +
                "load/reaction/residual vectors, with one style preset, " +
                "auto-scaling, and Elements/Metric filters. The shaded " +
                "thrust mesh is TNA Solve's preview; the geometry itself " +
                "is Deconstruct's.",
                ComponentCategories.Read,
                "graphic_diagram_display")
        {
        }

        public override Guid ComponentGuid =>
            new("1e7b3a95-8c4d-4f26-a9b0-5d2c8e6f7143");

        public override bool IsPreviewCapable => true;

        public override BoundingBox ClippingBox => _clippingBox;

        private protected override IReadOnlyList<ComponentValueListSpec>
            SuggestedValueLists => ValueLists;

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Solved FD or TNA result.",
                GH_ParamAccess.item);
            parameters.AddParameter(
                new StyleParam(),
                "Style",
                "STY",
                "Optional display preset, weight scale, and vector scale.",
                GH_ParamAccess.item);
            parameters[1].Optional = true;
            parameters.AddTextParameter(
                "Elements",
                "E",
                "Which streams to draw: thrust, force, loads, reactions, " +
                "residuals. Nothing here is emitted; wire Deconstruct for " +
                "the lines and the vectors themselves.",
                GH_ParamAccess.list);
            parameters[2].Optional = true;
            parameters.AddTextParameter(
                "Metric",
                "M",
                "Line-weight metric: None (natural: axial for thrust, " +
                "horizontal for form/force), Force Density q, Horizontal " +
                "Force H, or Axial Force F.",
                GH_ParamAccess.item,
                "none");
            parameters.AddNumberParameter(
                "Weight",
                "W",
                "Line-weight multiplier; zero uses Style's weight scale, " +
                "or 1 when no Style is supplied.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Vector Scale",
                "VS",
                "Load/reaction/residual arrow length is the vector's own " +
                "magnitude times this number (RhinoVAULT's own " +
                "draw_thrust_loads rule); a zero vector draws nothing. " +
                "Zero here uses Style's vector scale, or an automatic " +
                "scale from the solved model's bounding diagonal and " +
                "largest load/reaction.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Gap",
                "G",
                "Side-by-side force-diagram offset as a fraction of the " +
                "larger diagram span.",
                GH_ParamAccess.item,
                0.15);
            // APPENDED (the display wave, 2026-09-08), so no existing wire
            // on the six inputs above moves: StyleComponent's own preset
            // dropdown lands here now that component is retired. Blank
            // means "use the wired Style's Preset, or Analysis if there is
            // none", the same fallback shape Weight and Vector Scale
            // already gave their own inputs over Style's fields.
            parameters.AddTextParameter(
                "Preset",
                "Preset",
                "Analysis, Classical GS, or Monochrome viewport preset; " +
                "blank uses Style's preset, or Analysis when no Style is " +
                "supplied.",
                GH_ParamAccess.item,
                string.Empty);
            // APPENDED (the display wave, 2026-09-08), so no existing wire
            // on the eight inputs above moves. Sizes the reciprocal force
            // diagram's own layout against the form diagram's span; distinct
            // from Vector Scale, which sizes load/reaction/residual arrows.
            // One reproduces today's fixed fit exactly (see
            // ForceDiagramBaseFitFraction); the drawn diagram's extent
            // scales linearly with this input.
            parameters.AddNumberParameter(
                "Force Scale",
                "FS",
                "Reciprocal force-diagram size, against the form " +
                "diagram's own span; one reproduces today's fixed fit.",
                GH_ParamAccess.item,
                1.0);
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            // None. Display draws; the data it used to hand back is
            // Deconstruct's (Member Lines, Form Lines, the load and
            // reaction points and vectors) and Diagnose's (the report),
            // branched and ordered the way every other reader of a Result
            // gets it. Two components emitting the same lines under two
            // names is two things to keep in step and one of them to be
            // wrong.
        }

        protected override void BeforeSolveInstance()
        {
            base.BeforeSolveInstance();
            _preview.Clear();
            _clippingBox = BoundingBox.Empty;
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? resultGoo = null;
            StyleGoo? styleGoo = null;
            var elementsInput = new List<string>();
            string metricInput = "none";
            double weightInput = 0.0;
            double vectorScaleInput = 0.0;
            double gap = 0.15;
            string presetInput = string.Empty;
            double forceScaleInput = 1.0;

            if (!data.GetData(0, ref resultGoo) ||
                resultGoo?.Value is not ResultDto result)
            {
                return;
            }
            data.GetData(1, ref styleGoo);
            data.GetDataList(2, elementsInput);
            data.GetData(3, ref metricInput);
            data.GetData(4, ref weightInput);
            data.GetData(5, ref vectorScaleInput);
            data.GetData(6, ref gap);
            data.GetData(7, ref presetInput);
            data.GetData(8, ref forceScaleInput);

            try
            {
                var errors = new List<string>(result.Validate());
                StyleDto? style = styleGoo?.Value;
                if (style is not null)
                    errors.AddRange(style.Validate());

                string preset = EffectivePreset(presetInput, style);
                if (preset is not ("analysis" or "classical" or "monochrome"))
                    errors.Add("Preset must be Analysis, Classical GS, or Monochrome.");

                HashSet<string> elements = NormaliseElements(elementsInput);
                elements.Remove("form");
                foreach (string element in elements)
                {
                    if (element is not (
                            "thrust" or "force" or
                            "loads" or "reactions" or "residuals"))
                    {
                        errors.Add(
                            $"Elements value '{element}' is not supported.");
                    }
                }
                string metric = NormaliseMetric(metricInput);
                if (metric is not ("none" or "q" or "H" or "F"))
                    errors.Add("Metric must be None, q, H, or F.");
                if (!double.IsFinite(weightInput) || weightInput < 0.0)
                    errors.Add("Weight must be finite and non-negative.");
                if (!double.IsFinite(vectorScaleInput) || vectorScaleInput < 0.0)
                {
                    errors.Add(
                        "Vector Scale must be finite and non-negative.");
                }
                if (!double.IsFinite(gap) || gap < 0.0)
                    errors.Add("Gap must be finite and non-negative.");
                if (!double.IsFinite(forceScaleInput) || forceScaleInput <= 0.0)
                    errors.Add("Force Scale must be finite and positive.");
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                EquilibriumResultDto equilibrium = result.Equilibrium!;
                bool isTna =
                    string.Equals(
                        result.Solver,
                        "tna",
                        StringComparison.OrdinalIgnoreCase) &&
                    result.FormGraph is not null &&
                    result.ForceGraph is not null &&
                    result.Mappings is not null &&
                    result.AnalysisPlane is not null;

                // The readings that are DISPLAY'S OWN, raised where an
                // author will meet them. The solver's own report is
                // Diagnose's and Diagnose carries the no-reciprocal-diagram
                // line too, but the metric fallback is a fact about THIS
                // component's Metric input: it never reaches the Result, so
                // no other component can say it. Asking for H on an FD
                // Result and being drawn F without a word was the one thing
                // here that could mislead in silence.
                if (!isTna)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        "FD result: no reciprocal diagram.");
                    if (metric == "H")
                    {
                        AddRuntimeMessage(
                            GH_RuntimeMessageLevel.Remark,
                            "Metric H unavailable for FD result; used F " +
                            "magnitude.");
                    }
                }

                double effectiveWeight = weightInput > 0.0
                    ? weightInput
                    : style?.WeightScale ?? 1.0;

                Point3d[] equilibriumPoints =
                    equilibrium.Vertices.Select(Point).ToArray();
                double diag = equilibriumPoints.Length == 0
                    ? 0.0
                    : new BoundingBox(equilibriumPoints).Diagonal.Length;

                IEnumerable<double> actionMagnitudes = isTna
                    ? result.Mappings!.Loads
                        .Select(item => Length(item.Vector))
                        .Concat(result.Mappings!.Reactions
                            .Select(item => Length(item.Reaction)))
                    : equilibrium.Loads
                        .Select(item => Length(item.Vector))
                        .Concat(equilibrium.Reactions
                            .Select(item => Length(item.Vector)));
                // Metre-scale default: the largest action vector draws at
                // one-and-a-half percent of the model's bounding diagonal.
                double maxAction = actionMagnitudes.DefaultIfEmpty(0.0).Max();
                double autoVectorScale = maxAction > 1.0e-12
                    ? 0.015 * diag / maxAction
                    : 1.0;

                double effectiveVectorScale;
                bool vectorScaleIsAuto = false;
                if (vectorScaleInput > 0.0)
                {
                    effectiveVectorScale = vectorScaleInput;
                }
                else if (style is not null && style.VectorScale > 0.0)
                {
                    effectiveVectorScale = style.VectorScale;
                }
                else
                {
                    effectiveVectorScale = autoVectorScale;
                    vectorScaleIsAuto = true;
                }

                var thrustEdges = new List<MemberEdge>();
                var forceEdges = new List<MemberEdge>();
                var loadLines = new List<Line>();
                var reactionLines = new List<Line>();
                var residualLines = new List<Line>();

                if (isTna)
                {
                    TnaEdgeStateDto[] states = result.EdgeStates
                        .OrderBy(item => item.Id)
                        .ToArray();

                    if (elements.Contains("thrust"))
                    {
                        foreach (TnaEdgeStateDto state in states)
                        {
                            thrustEdges.Add(new MemberEdge(
                                ThrustLine(equilibrium, state),
                                DisplayMagnitude(state, "thrust", metric),
                                state.ForceState));
                        }
                    }
                    if (elements.Contains("force"))
                    {
                        Dictionary<int, TnaGraphEdgeDto> forceGraphEdges =
                            result.ForceGraph!.Edges
                                .ToDictionary(edge => edge.Id);
                        Dictionary<int, Point3Dto> formVerticesForLayout =
                            result.FormGraph!.Vertices.ToDictionary(
                                vertex => vertex.Id,
                                vertex => vertex.Point);
                        Dictionary<int, Point3Dto> forceVertices =
                            result.ForceGraph!.Vertices.ToDictionary(
                                vertex => vertex.Id,
                                vertex => vertex.Point);
                        Dictionary<int, Point3Dto> forceDisplay =
                            LayoutForceGraph(
                                formVerticesForLayout,
                                forceVertices,
                                result.AnalysisPlane!,
                                ForceDiagramBaseFitFraction * forceScaleInput,
                                gap);
                        foreach (TnaEdgeStateDto state in states)
                        {
                            TnaGraphEdgeDto edge =
                                forceGraphEdges[state.ForceEdgeId];
                            forceEdges.Add(new MemberEdge(
                                new Line(
                                    Point(forceDisplay[edge.U]),
                                    Point(forceDisplay[edge.V])),
                                DisplayMagnitude(state, "force", metric),
                                state.ForceState));
                        }
                    }
                    if (elements.Contains("loads"))
                    {
                        foreach (TnaLoadMappingDto item in
                                 result.Mappings!.Loads)
                        {
                            Point3d start = Point(
                                equilibrium.Vertices[
                                    item.EquilibriumVertexId]);
                            Line? line = VectorArrowLine(
                                start,
                                Vector(item.Vector),
                                effectiveVectorScale);
                            if (line is not null)
                                loadLines.Add(line.Value);
                        }
                    }
                    if (elements.Contains("reactions"))
                    {
                        foreach (TnaSupportMappingDto item in
                                 result.Mappings!.Reactions)
                        {
                            Point3d start = Point(
                                equilibrium.Vertices[
                                    item.EquilibriumVertexId]);
                            Line? line = VectorArrowLine(
                                start,
                                Vector(item.Reaction),
                                effectiveVectorScale);
                            if (line is not null)
                                reactionLines.Add(line.Value);
                        }
                    }
                }
                else
                {
                    if (elements.Contains("thrust"))
                    {
                        Line[] memberLines = MemberLines(equilibrium);
                        for (int index = 0;
                             index < memberLines.Length;
                             index++)
                        {
                            double memberForce =
                                equilibrium.MemberForces[index];
                            double density =
                                equilibrium.ForceDensities[index];
                            double magnitude = metric == "q"
                                ? Math.Abs(density)
                                : Math.Abs(memberForce);
                            thrustEdges.Add(new MemberEdge(
                                memberLines[index],
                                magnitude,
                                ForceStateFor(
                                    memberForce,
                                    equilibrium.SignConvention)));
                        }
                    }
                    if (elements.Contains("loads"))
                    {
                        foreach (NodalVectorDto item in equilibrium.Loads)
                        {
                            Point3d start = Point(item.Point);
                            Line? line = VectorArrowLine(
                                start,
                                Vector(item.Vector),
                                effectiveVectorScale);
                            if (line is not null)
                                loadLines.Add(line.Value);
                        }
                    }
                    if (elements.Contains("reactions"))
                    {
                        foreach (NodalVectorDto item in
                                 equilibrium.Reactions)
                        {
                            Point3d start = Point(item.Point);
                            Line? line = VectorArrowLine(
                                start,
                                Vector(item.Vector),
                                effectiveVectorScale);
                            if (line is not null)
                                reactionLines.Add(line.Value);
                        }
                    }
                }

                if (elements.Contains("residuals"))
                {
                    foreach (NodalVectorDto item in equilibrium.Residuals)
                    {
                        Point3d start = Point(item.Point);
                        Line? line = VectorArrowLine(
                            start,
                            Vector(item.Vector),
                            effectiveVectorScale);
                        if (line is not null)
                            residualLines.Add(line.Value);
                    }
                }

                _preview.AddRange(
                    ToDrawLines(
                        thrustEdges,
                        "thrust",
                        preset,
                        effectiveWeight));
                _preview.AddRange(
                    ToDrawLines(
                        forceEdges,
                        "force",
                        preset,
                        effectiveWeight));

                _preview.AddRange(ToArrowLines(loadLines, "load", preset));
                _preview.AddRange(
                    ToArrowLines(reactionLines, "reaction", preset));
                _preview.AddRange(
                    ToArrowLines(residualLines, "residual", preset));

                Point3d[] previewPoints = _preview
                    .SelectMany(item => new[] { item.Line.From, item.Line.To })
                    .ToArray();
                _clippingBox = previewPoints.Length == 0
                    ? BoundingBox.Empty
                    : new BoundingBox(previewPoints);

                // The chin carries the two scales the drawing was made at,
                // because they are the only readings this component owns
                // and nothing else emits them now the outputs are gone. A
                // vector scale the component chose for itself says "auto":
                // an author comparing two Displays needs to know which of
                // the two numbers was theirs. "linear x magnitude" NAMES
                // the rule VectorArrowLine actually draws by (RhinoVAULT's
                // own draw_thrust_loads rule, read directly rather than
                // guessed at): arrow length is the vector's own magnitude
                // times this one number, nothing normalised or clamped, so
                // nobody reading a saved canvas has to guess what "vectors
                // x..." means.
                Message =
                    $"{result.Solver.ToUpperInvariant()} · {preset} · " +
                    $"thrust x{effectiveWeight:G3} · vectors linear x" +
                    $"{effectiveVectorScale:G3}" +
                    (vectorScaleIsAuto ? " auto" : string.Empty);
            }
            catch (Exception error)
            {
                Message = "Invalid";
                ReportException("Display failed", error);
            }
        }

        protected override void DrawVisibleViewportWires(IGH_PreviewArgs args)
        {
            foreach (DrawLine item in _preview)
            {
                if (item.Arrow)
                    args.Display.DrawArrow(item.Line, item.Colour);
                else
                    args.Display.DrawLine(item.Line, item.Colour, item.Weight);
            }
        }

        private static HashSet<string> NormaliseElements(
            IEnumerable<string> values)
        {
            string[] tokens = values
                .SelectMany(value => (value ?? string.Empty).Split(','))
                .Select(token => token.Trim().ToLowerInvariant())
                .Where(token => token.Length > 0)
                .ToArray();
            return tokens.Length == 0
                ? new HashSet<string>(
                    new[] { "thrust", "force" },
                    StringComparer.Ordinal)
                : new HashSet<string>(tokens, StringComparer.Ordinal);
        }

        /// <summary>
        /// Display's own Preset input, retired StyleComponent's replacement,
        /// takes priority whenever it carries anything after trimming; a
        /// blank input falls back to a wired Style's Preset, and Analysis
        /// when there is no Style either. The same shape as
        /// <c>effectiveWeight</c> and <c>effectiveVectorScale</c> above:
        /// Display's own input over Style's field over a hard default.
        /// </summary>
        private static string EffectivePreset(string? presetInput, StyleDto? style) =>
            !string.IsNullOrWhiteSpace(presetInput)
                ? StyleDto.NormalisePreset(presetInput)
                : style is null
                    ? "analysis"
                    : StyleDto.NormalisePreset(style.Preset);

        private static string NormaliseMetric(string? value)
        {
            string trimmed = (value ?? string.Empty).Trim();
            if (trimmed.Length == 0)
                return "none";
            return trimmed.ToUpperInvariant() switch
            {
                "NONE" => "none",
                "Q" => "q",
                "H" => "H",
                "F" => "F",
                _ => trimmed
            };
        }

        /// <summary>
        /// Copied and adapted from
        /// <c>TnaGraphicDiagramFactory.DisplayMagnitude</c>.
        /// </summary>
        private static double DisplayMagnitude(
            TnaEdgeStateDto state,
            string role,
            string metric) =>
            metric switch
            {
                "q" => Math.Abs(state.ForceDensity),
                "H" => Math.Abs(state.HorizontalForce),
                "F" => Math.Abs(state.AxialForce),
                _ => role == "thrust"
                    ? Math.Abs(state.AxialForce)
                    : Math.Abs(state.HorizontalForce)
            };

        /// <summary>Copied from <c>DeconstructComponent.ThrustLine</c>.</summary>
        private static Line ThrustLine(
            EquilibriumResultDto equilibrium,
            TnaEdgeStateDto state)
        {
            EdgeDto edge = equilibrium.Edges[state.EquilibriumEdgeId];
            return new Line(
                Point(equilibrium.Vertices[edge.U]),
                Point(equilibrium.Vertices[edge.V]));
        }

        /// <summary>Copied from <c>DeconstructComponent.MemberLines</c>.</summary>
        private static Line[] MemberLines(EquilibriumResultDto equilibrium) =>
            equilibrium.Edges
                .Select(edge => new Line(
                    Point(equilibrium.Vertices[edge.U]),
                    Point(equilibrium.Vertices[edge.V])))
                .ToArray();

        /// <summary>
        /// One load/reaction/residual arrow: the raw vector times
        /// <paramref name="scale"/>, arrow length linear in the vector's
        /// own magnitude. This is RhinoVAULT's own rule for drawing loads
        /// -- read directly from the installed plugin, not guessed at --
        /// <c>compas_rv.scene.formobject.draw_thrust_loads</c>: <c>vector
        /// = Vector(*load) * scale</c>, a flat user-set scalar with no
        /// per-draw normalisation against the largest load or the model's
        /// own size. A vector at or below the SAME near-zero tolerance the
        /// TNA loads/reactions branches already used (1e-24 on the square
        /// length, ~1e-12 on the length itself) draws NOTHING rather than
        /// a zero-length line: RhinoVAULT's own <c>tol_vectors</c> check
        /// does the same (<c>if vector.length > tol</c>), and a
        /// zero-length arrow reads as a stray dot, not "no load here".
        ///
        /// Shared by all five of Display's vector streams (TNA
        /// loads/reactions, FD loads/reactions, residuals) so the rule and
        /// its zero-skip apply identically everywhere; before this, the
        /// zero-skip existed only on the TNA branches and FD
        /// loads/reactions and residuals could draw a degenerate
        /// zero-length "arrow" for an exactly-zero vector.
        ///
        /// Degenerate cases, by construction: two loads differing in
        /// magnitude draw arrows differing in length by the exact same
        /// ratio (this is a straight multiply, nothing is compressed or
        /// clamped); all loads equal in magnitude draw arrows all the
        /// same length; a single load draws one arrow at
        /// <paramref name="scale"/> times its own magnitude; a zero load
        /// draws nothing (this method's own null); and one enormous
        /// outlier alongside small loads is drawn EXACTLY, not compressed
        /// -- under a fixed user Scale every arrow is still magnitude
        /// times that one number, so the outlier simply draws very long
        /// (matching RhinoVAULT, which has no per-draw normalisation
        /// either); under Display's own AUTOMATIC scale (Vector Scale
        /// left at zero, no Style supplying one) the single largest action
        /// across ALL loads and reactions sets the scale so IT draws at
        /// about 1.5% of the model's bounding diagonal, which is Display's
        /// own pre-existing convenience layer on top of this rule, not
        /// something this method does -- an outlier under auto-scale still
        /// draws every other arrow in exact linear proportion to it, only
        /// smaller in absolute terms, which is the correct, honest reading
        /// of "linear in magnitude" rather than a bug to compress away.
        /// </summary>
        private static Line? VectorArrowLine(
            Point3d start,
            Vector3d vector,
            double scale)
        {
            if (vector.SquareLength <= 1.0e-24)
                return null;
            return new Line(start, start + scale * vector);
        }

        /// <summary>
        /// Copied from the since-deleted <c>DeconstructComponent.ForceState</c>,
        /// which went when Deconstruct became geometry only.
        /// </summary>
        private static string ForceStateFor(double force, string signConvention)
        {
            if (Math.Abs(force) <= 1.0e-12)
                return "zero";
            bool positiveTension = string.Equals(
                signConvention,
                "positive_tension",
                StringComparison.OrdinalIgnoreCase);
            bool tension = positiveTension ? force > 0.0 : force < 0.0;
            return tension ? "tension" : "compression";
        }

        /// <summary>
        /// Side-by-side force-diagram placement lifted out of
        /// <c>TnaGraphicDiagramFactory.LayoutForceGraph</c> (the Overlay
        /// branch is dropped; Display always places the force diagram
        /// beside the form diagram). The force diagram is normalised to
        /// <paramref name="fitFraction"/> of the form diagram's larger
        /// span: its edge lengths are ratios to read, and at natural
        /// scale it regularly dwarfed the model in metre units.
        /// </summary>
        private static Dictionary<int, Point3Dto> LayoutForceGraph(
            IReadOnlyDictionary<int, Point3Dto> formVertices,
            IReadOnlyDictionary<int, Point3Dto> forceVertices,
            AnalysisPlaneDto plane,
            double fitFraction,
            double gapRatio)
        {
            PlaneFrame frame = PlaneFrame.Create(plane);
            Bounds2 formBounds =
                Bounds2.From(formVertices.Values.Select(frame.Project));
            Dictionary<int, LocalPoint> local = forceVertices.ToDictionary(
                item => item.Key,
                item => frame.Project(item.Value));
            Bounds2 rawBounds = Bounds2.From(local.Values);
            double formSpan = Math.Max(
                formBounds.Width,
                formBounds.Height);
            double rawSpan = Math.Max(rawBounds.Width, rawBounds.Height);
            double scale = rawSpan > 1.0e-12 && formSpan > 1.0e-12
                ? fitFraction * formSpan / rawSpan
                : 1.0;
            LocalPoint centre = rawBounds.Centre;
            Dictionary<int, LocalPoint> scaled = local.ToDictionary(
                item => item.Key,
                item => centre + scale * (item.Value - centre));
            Bounds2 scaledBounds = Bounds2.From(scaled.Values);
            double reference = Math.Max(
                Math.Max(formBounds.Width, formBounds.Height),
                Math.Max(scaledBounds.Width, scaledBounds.Height));
            if (reference <= 1.0e-12)
                reference = 1.0;

            double dx =
                formBounds.MaximumX -
                scaledBounds.MinimumX +
                gapRatio * reference;
            double dy = formBounds.Centre.Y - scaledBounds.Centre.Y;
            var offset = new LocalPoint(dx, dy, 0.0);
            return scaled.ToDictionary(
                item => item.Key,
                item => frame.Unproject(item.Value + offset));
        }

        private static IEnumerable<DrawLine> ToDrawLines(
            IReadOnlyList<MemberEdge> edges,
            string role,
            string preset,
            double weightScale)
        {
            double maximum = edges
                .Select(edge => edge.Magnitude)
                .DefaultIfEmpty(0.0)
                .Max();
            foreach (MemberEdge edge in edges)
            {
                double normalised = maximum > 0.0
                    ? edge.Magnitude / maximum
                    : 0.0;
                double rawWeight = 1.0 + 2.0 * normalised;
                int weight = Math.Clamp(
                    (int)Math.Round(rawWeight * weightScale),
                    1,
                    12);
                yield return new DrawLine(
                    edge.Line,
                    RoleColour(role, edge.ForceState, preset),
                    weight,
                    false);
            }
        }

        private static IEnumerable<DrawLine> ToArrowLines(
            IReadOnlyList<Line> lines,
            string role,
            string preset)
        {
            Color colour = RoleColour(role, string.Empty, preset);
            foreach (Line line in lines)
                yield return new DrawLine(line, colour, 1, true);
        }

        /// <summary>
        /// Copied and extended (with a "residual" case) from
        /// <c>GraphicDiagramDisplayComponent.RoleColour</c>.
        /// </summary>
        private static Color RoleColour(
            string role,
            string forceState,
            string preset)
        {
            if (preset == "monochrome")
            {
                return role switch
                {
                    "form" => Color.FromArgb(65, 65, 65),
                    "load" or "reaction" or "residual" =>
                        Color.FromArgb(105, 105, 105),
                    _ => Color.FromArgb(25, 25, 25)
                };
            }
            if (preset == "classical")
            {
                return role switch
                {
                    "form" or "thrust" => Color.FromArgb(30, 30, 30),
                    "force" => Color.FromArgb(35, 95, 210),
                    "load" => Color.FromArgb(238, 135, 35),
                    "reaction" => Color.FromArgb(35, 155, 75),
                    "residual" => Color.FromArgb(220, 30, 170),
                    _ => Color.FromArgb(105, 105, 105)
                };
            }
            return role switch
            {
                "form" => Color.FromArgb(105, 105, 105),
                "load" => Color.FromArgb(238, 135, 35),
                "reaction" => Color.FromArgb(35, 155, 75),
                "residual" => Color.FromArgb(220, 30, 170),
                _ => StateColour(forceState)
            };
        }

        /// <summary>
        /// Copied from <c>GraphicDiagramDisplayComponent.StateColour</c>.
        /// </summary>
        private static Color StateColour(string state) =>
            (state ?? string.Empty).Trim().ToLowerInvariant() switch
            {
                "compression" => Color.FromArgb(35, 95, 210),
                "tension" => Color.FromArgb(210, 45, 45),
                "zero" => Color.FromArgb(125, 125, 125),
                _ => Color.FromArgb(35, 155, 75)
            };

        private static double Length(Point3Dto value) =>
            Math.Sqrt(
                value.X * value.X + value.Y * value.Y + value.Z * value.Z);

        private static Point3d Point(Point3Dto value) =>
            new(value.X, value.Y, value.Z);

        private static Vector3d Vector(Point3Dto value) =>
            new(value.X, value.Y, value.Z);

        private sealed record DrawLine(
            Line Line,
            Color Colour,
            int Weight,
            bool Arrow);

        private sealed record MemberEdge(
            Line Line,
            double Magnitude,
            string ForceState);

        private readonly record struct LocalPoint(double X, double Y, double Z)
        {
            public static LocalPoint operator +(LocalPoint a, LocalPoint b) =>
                new(a.X + b.X, a.Y + b.Y, a.Z + b.Z);

            public static LocalPoint operator -(LocalPoint a, LocalPoint b) =>
                new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);

            public static LocalPoint operator *(
                double scale,
                LocalPoint value) =>
                new(scale * value.X, scale * value.Y, scale * value.Z);
        }

        private readonly record struct Bounds2(
            double MinimumX,
            double MinimumY,
            double MaximumX,
            double MaximumY)
        {
            public double Width => MaximumX - MinimumX;
            public double Height => MaximumY - MinimumY;
            public LocalPoint Centre => new(
                0.5 * (MinimumX + MaximumX),
                0.5 * (MinimumY + MaximumY),
                0.0);

            public static Bounds2 From(IEnumerable<LocalPoint> values)
            {
                LocalPoint[] points = values.ToArray();
                if (points.Length == 0)
                {
                    throw new InvalidOperationException(
                        "Diagram has no vertices.");
                }
                return new Bounds2(
                    points.Min(point => point.X),
                    points.Min(point => point.Y),
                    points.Max(point => point.X),
                    points.Max(point => point.Y));
            }
        }

        private readonly record struct PlaneFrame(
            Point3Dto Origin,
            Point3Dto XAxis,
            Point3Dto YAxis,
            Point3Dto ZAxis)
        {
            public static PlaneFrame Create(AnalysisPlaneDto plane)
            {
                Point3Dto x = Unit(plane.XAxis, "analysis plane X axis");
                Point3Dto z =
                    Unit(Cross(x, plane.YAxis), "analysis plane normal");
                Point3Dto y = Unit(Cross(z, x), "analysis plane Y axis");
                return new PlaneFrame(plane.Origin, x, y, z);
            }

            public LocalPoint Project(Point3Dto point)
            {
                Point3Dto delta = Subtract(point, Origin);
                return new LocalPoint(
                    Dot(delta, XAxis),
                    Dot(delta, YAxis),
                    Dot(delta, ZAxis));
            }

            public Point3Dto Unproject(LocalPoint point) =>
                new(
                    Origin.X +
                    point.X * XAxis.X +
                    point.Y * YAxis.X +
                    point.Z * ZAxis.X,
                    Origin.Y +
                    point.X * XAxis.Y +
                    point.Y * YAxis.Y +
                    point.Z * ZAxis.Y,
                    Origin.Z +
                    point.X * XAxis.Z +
                    point.Y * YAxis.Z +
                    point.Z * ZAxis.Z);

            private static Point3Dto Unit(Point3Dto value, string label)
            {
                double length = Math.Sqrt(Dot(value, value));
                if (!double.IsFinite(length) || length <= 1.0e-12)
                    throw new InvalidOperationException($"{label} is invalid.");
                return new Point3Dto(
                    value.X / length,
                    value.Y / length,
                    value.Z / length);
            }

            private static Point3Dto Cross(Point3Dto a, Point3Dto b) =>
                new(
                    a.Y * b.Z - a.Z * b.Y,
                    a.Z * b.X - a.X * b.Z,
                    a.X * b.Y - a.Y * b.X);

            private static Point3Dto Subtract(Point3Dto a, Point3Dto b) =>
                new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);

            private static double Dot(Point3Dto a, Point3Dto b) =>
                a.X * b.X + a.Y * b.Y + a.Z * b.Z;
        }
    }
}
