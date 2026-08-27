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
    /// One data-extraction component replacing the four old query
    /// components (TNA Geometry, TNA Members, TNA Actions, Result
    /// Breakdown). It reads the unified <see cref="ResultDto"/> and takes
    /// one of two extraction paths keyed on <see cref="ResultDto.Solver"/>
    /// plus the null-ness of the reciprocal members: the richer TNA path
    /// (form/force graphs, edge states, mappings) mirrors
    /// <c>TnaGeometryComponent</c>, <c>TnaMembersComponent</c>, and
    /// <c>TnaActionsComponent</c>; the flat FD path mirrors
    /// <c>ResultBreakdownComponent</c>. Every reference component's
    /// extraction logic is copied here, not called, so this file keeps
    /// working after Task 12 deletes the old ones.
    /// </summary>
    public sealed class DeconstructComponent : NativeComponentBase
    {
        public DeconstructComponent()
            : base(
                "Deconstruct",
                "Deconstruct",
                "Extract thrust/form geometry, member forces, and nodal " +
                "actions from one solved FD or TNA Result. Reciprocal-only " +
                "streams (Thrust Mesh, Form Lines, H) come out empty for FD.",
                ComponentCategories.Visualise,
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
            parameters.AddNumberParameter(
                "Course Height",
                "CH",
                "Band height in metres for the Face Courses output: " +
                "faces whose centroid sits within the same height band " +
                "share a course. Zero or negative falls back to 0.35.",
                GH_ParamAccess.item,
                0.35);
            parameters[1].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddMeshParameter(
                "Thrust Mesh",
                "TM",
                "Resolved funicular mesh reconstructed from the active " +
                "form faces. Empty for FD.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Member Lines",
                "M",
                "Resolved spatial member axes, as a TREE: one branch per " +
                "principal line holding that bar's own members, and a LAST " +
                "branch holding the infill, everything not on a bar. Every " +
                "member-aligned output below is branched and ordered " +
                "identically, so the alignment holds branch to branch as " +
                "well as index to index. A bar with no members of its own " +
                "keeps an empty branch, so branch {i} is always bar {i}.",
                GH_ParamAccess.tree);
            parameters.AddLineParameter(
                "Form Lines",
                "FL",
                "Planar form-diagram edges, branched and ordered exactly " +
                "as Member Lines. Empty for FD.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "q",
                "q",
                "Signed force density, branched and ordered exactly as " +
                "Member Lines.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "H",
                "H",
                "Signed horizontal-force demand, branched and ordered " +
                "exactly as Member Lines. Empty for FD.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "F",
                "F",
                "Signed axial-force demand, branched and ordered exactly " +
                "as Member Lines.",
                GH_ParamAccess.tree);
            parameters.AddTextParameter(
                "Force State",
                "S",
                "Compression, tension, or zero state, branched and " +
                "ordered exactly as Member Lines.",
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
                "Points carrying support reactions. TNA: non-zero only; " +
                "FD: unfiltered.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Reaction Vectors",
                "RV",
                "Support reactions aligned with Reaction Points. TNA: " +
                "non-zero only; FD: unfiltered.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Residuals",
                "E",
                "Equilibrium residual vectors, one per solved node.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Diagnostics",
                "D",
                "Structured solver diagnostics formatted one per line.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Report",
                "Report",
                "Readable backend solve report. FD results gain the line " +
                "\"FD result: no reciprocal diagram.\"",
                GH_ParamAccess.item);
            parameters.AddCurveParameter(
                "Face Polylines",
                "FP",
                "One closed polyline per Thrust Mesh face, as a TREE " +
                "branched by COURSE (path = course, 0-up from the " +
                "bottom): the ready-made Cells input for the Export " +
                "component's Tessellation format (each face an authored " +
                "cutting cell). The same branching Import Pieces uses, so " +
                "a course means the same thing across the plugin. Empty " +
                "for FD.",
                GH_ParamAccess.tree);
            parameters.AddIntegerParameter(
                "Face Courses",
                "FC",
                "The course (build row) per face, branched and ordered " +
                "exactly as Face Polylines, so the pairing survives and " +
                "the branch path is the course as well. Courses band the " +
                "face centroids by height (Course Height per band), " +
                "bottom row 0: the ready-made Courses input for the " +
                "Export component's Tessellation format. Empty for FD.",
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
            double courseHeight = 0.35;
            data.GetData(1, ref courseHeight);
            // Negated comparison, not "<= 0": NaN fails every comparison,
            // so "NaN <= 0" would sail PAST a positivity guard and floor
            // every face to course 0 silently, and a tiny positive (a
            // slider dragged to nearly zero) would overflow the int cast
            // in FaceCourses into garbage negative courses. 1 mm is the
            // sane floor for a physical course height.
            if (!(courseHeight > 0.001))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Course Height must be at least 1 mm; using 0.35 m.");
                courseHeight = 0.35;
            }

            try
            {
                IReadOnlyList<string> errors = result.Validate();
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
                    result.Mappings is not null;

                Mesh thrustMesh;
                Line[] memberLines;
                Line[] formLines;
                double[] q;
                double[] h;
                double[] f;
                string[] forceStates;
                int[] memberIds;
                int[] nodeIds;
                Point3d[] supportPoints;
                (Point3d Point, Vector3d Vector)[] loads;
                (Point3d Point, Vector3d Vector)[] reactions;
                // The two ends of each member as NODE INDICES, which is what
                // says whether a member lies along a principal line. The lines
                // themselves cannot answer that: a point is not an index, and
                // matching by coordinate would make an exact question into a
                // tolerance one.
                (int U, int V)[] memberEnds;

                if (isTna)
                {
                    TnaEdgeStateDto[] states = result.EdgeStates
                        .OrderBy(state => state.Id)
                        .ToArray();
                    IReadOnlyDictionary<int, TnaGraphEdgeDto> formEdges =
                        result.FormGraph!.Edges.ToDictionary(edge => edge.Id);
                    IReadOnlyDictionary<int, Point3Dto> formPoints =
                        result.FormGraph!.Vertices.ToDictionary(
                            vertex => vertex.Id,
                            vertex => vertex.Point);

                    thrustMesh = ThrustMesh(result);
                    memberLines = states
                        .Select(state => ThrustLine(equilibrium, state))
                        .ToArray();
                    formLines = states
                        .Select(state => FormLine(state, formEdges, formPoints))
                        .ToArray();
                    q = states.Select(state => state.ForceDensity).ToArray();
                    h = states.Select(state => state.HorizontalForce).ToArray();
                    f = states.Select(state => state.AxialForce).ToArray();
                    forceStates = states.Select(state => state.ForceState).ToArray();
                    memberIds = states.Select(state => state.Id).ToArray();
                    memberEnds = states
                        .Select(state => EquilibriumEnds(
                            equilibrium, state.EquilibriumEdgeId))
                        .ToArray();

                    nodeIds = result.Mappings!.Supports
                        .Select(item => item.EquilibriumVertexId)
                        .ToArray();
                    supportPoints = result.Mappings!.Supports
                        .Select(item => Point(
                            equilibrium.Vertices[item.EquilibriumVertexId]))
                        .ToArray();
                    loads = result.Mappings!.Loads
                        .Select(item => (
                            Point(equilibrium.Vertices[item.EquilibriumVertexId]),
                            Vector(item.Vector)))
                        .Where(item => item.Item2.SquareLength > 1.0e-24)
                        .ToArray();
                    reactions = result.Mappings!.Reactions
                        .Select(item => (
                            Point(equilibrium.Vertices[item.EquilibriumVertexId]),
                            Vector(item.Reaction)))
                        .Where(item => item.Item2.SquareLength > 1.0e-24)
                        .ToArray();
                }
                else
                {
                    thrustMesh = new Mesh();
                    memberLines = MemberLines(equilibrium);
                    formLines = Array.Empty<Line>();
                    q = equilibrium.ForceDensities.ToArray();
                    h = Array.Empty<double>();
                    f = equilibrium.MemberForces.ToArray();
                    forceStates = equilibrium.MemberForces
                        .Select(force => ForceState(force, equilibrium.SignConvention))
                        .ToArray();
                    memberIds = Enumerable.Range(0, equilibrium.Edges.Count).ToArray();
                    memberEnds = Enumerable.Range(0, equilibrium.Edges.Count)
                        .Select(id => EquilibriumEnds(equilibrium, id))
                        .ToArray();

                    nodeIds = equilibrium.ResolvedSupportNodeIds.ToArray();
                    supportPoints = equilibrium.ResolvedSupportNodeIds
                        .Select(nodeId => Point(equilibrium.Vertices[nodeId]))
                        .ToArray();
                    loads = equilibrium.Loads
                        .Select(item => (Point(item.Point), Vector(item.Vector)))
                        .ToArray();
                    reactions = equilibrium.Reactions
                        .Select(item => (Point(item.Point), Vector(item.Vector)))
                        .ToArray();
                }

                Vector3d[] residuals = equilibrium.Residuals
                    .Select(item => Vector(item.Vector))
                    .ToArray();
                string[] diagnostics = result.Diagnostics
                    .Select(item =>
                        $"[{item.Severity.ToUpperInvariant()}] {item.Code}: " +
                        $"{item.Message}")
                    .ToArray();
                string report = isTna
                    ? result.Report
                    : string.IsNullOrEmpty(result.Report)
                        ? "FD result: no reciprocal diagram."
                        : result.Report + Environment.NewLine +
                          "FD result: no reciprocal diagram.";

                // ---- grouping ----------------------------------------------
                // The principal lines this Result carries, resolved upstream by
                // Supports or Pattern and travelling in the contract, so this
                // component reads the same bars Animate and Column Finder do
                // rather than deriving its own and disagreeing with them.
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
                (int, int)[] netEdges = MouldGeometry.ValidEdges(
                    equilibrium, equilibrium.Vertices.Count, out _);
                List<int>[] neighbours = MouldGeometry.BuildAdjacency(
                    equilibrium.Vertices.Count, netEdges);
                List<List<int>> strips = MouldGeometry.ConnectedGroups(
                    nodeIds, neighbours);
                var nodeIdAt = new Dictionary<int, int>();
                for (int i = 0; i < nodeIds.Length; i++)
                    nodeIdAt[nodeIds[i]] = i;

                // Faces by the course they build in, which is what Face Courses
                // was already reporting per face. The same shape Import Pieces
                // uses, so a course means the same thing across the plugin.
                IReadOnlyList<PolylineCurve> facePolylines =
                    FacePolylines(thrustMesh);
                IReadOnlyList<int> faceCourses =
                    FaceCourses(thrustMesh, courseHeight);
                var faceByCourse = new List<List<Curve>>();
                var courseByCourse = new List<List<int>>();
                int courseCount = faceCourses.Count == 0
                    ? 0 : faceCourses.Max() + 1;
                for (int c = 0; c < courseCount; c++)
                {
                    faceByCourse.Add(new List<Curve>());
                    courseByCourse.Add(new List<int>());
                }
                for (int i = 0; i < facePolylines.Count; i++)
                {
                    int course = i < faceCourses.Count ? faceCourses[i] : 0;
                    if (course < 0 || course >= courseCount)
                        continue;
                    faceByCourse[course].Add(facePolylines[i]);
                    courseByCourse[course].Add(course);
                }

                data.SetData(0, thrustMesh);
                data.SetDataTree(1, OutputTree.Lines(ByBar(memberLines)));
                data.SetDataTree(2, OutputTree.Lines(ByBar(formLines)));
                data.SetDataTree(3, OutputTree.Numbers(ByBar(q)));
                data.SetDataTree(4, OutputTree.Numbers(ByBar(h)));
                data.SetDataTree(5, OutputTree.Numbers(ByBar(f)));
                data.SetDataTree(6, OutputTree.Strings(ByBar(forceStates)));
                data.SetDataTree(7, OutputTree.Integers(ByBar(memberIds)));
                data.SetDataTree(8, OutputTree.Integers(
                    strips.Select(strip => strip.AsEnumerable())));
                data.SetDataTree(9, OutputTree.Points(
                    strips.Select(strip => strip
                        .Where(nodeIdAt.ContainsKey)
                        .Select(id => supportPoints[nodeIdAt[id]]))));
                data.SetDataList(10, loads.Select(item => item.Point));
                data.SetDataList(11, loads.Select(item => item.Vector));
                data.SetDataList(12, reactions.Select(item => item.Point));
                data.SetDataList(13, reactions.Select(item => item.Vector));
                data.SetDataList(14, residuals);
                data.SetDataList(15, diagnostics);
                data.SetData(16, report);
                data.SetDataTree(17, OutputTree.Curves(faceByCourse));
                data.SetDataTree(18, OutputTree.Integers(courseByCourse));
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

        /// <summary>
        /// One mesh face's corner points, in winding order: three for a
        /// triangle, four for a quad. <see cref="FacePolylines"/> and
        /// <see cref="FaceCourses"/> both read a face's corners this
        /// way, so the corner/count logic is written once, not twice.
        /// </summary>
        private static IReadOnlyList<Point3d> FaceCorners(
            Mesh mesh,
            MeshFace face)
        {
            var points = new List<Point3d>(4)
            {
                mesh.Vertices[face.A],
                mesh.Vertices[face.B],
                mesh.Vertices[face.C]
            };
            if (face.IsQuad)
                points.Add(mesh.Vertices[face.D]);
            return points;
        }

        /// <summary>
        /// One closed polyline per mesh face, in face order: the Export
        /// component's Tessellation format takes these as authored Cells
        /// verbatim (it drops z and dedupes the closing repeat itself).
        /// </summary>
        private static IReadOnlyList<PolylineCurve> FacePolylines(Mesh mesh)
        {
            var polylines = new List<PolylineCurve>(mesh.Faces.Count);
            for (int i = 0; i < mesh.Faces.Count; i++)
            {
                IReadOnlyList<Point3d> corners =
                    FaceCorners(mesh, mesh.Faces[i]);
                var points = new List<Point3d>(corners.Count + 1);
                points.AddRange(corners);
                points.Add(points[0]);
                polylines.Add(new PolylineCurve(points));
            }
            return polylines;
        }

        /// <summary>
        /// The course per face, aligned with <see cref="FacePolylines"/>:
        /// centroid heights banded from the lowest face upward, so the
        /// bottom row is 0 and nothing is ever sorted -- sorting is
        /// exactly what would break the one-to-one pairing the Export
        /// component's Cells/Courses inputs rely on.
        /// </summary>
        private static IReadOnlyList<int> FaceCourses(
            Mesh mesh,
            double courseHeight)
        {
            var centroids = new double[mesh.Faces.Count];
            double lowest = double.PositiveInfinity;
            for (int i = 0; i < mesh.Faces.Count; i++)
            {
                IReadOnlyList<Point3d> corners =
                    FaceCorners(mesh, mesh.Faces[i]);
                double z = 0.0;
                foreach (Point3d corner in corners)
                    z += corner.Z;
                centroids[i] = z / corners.Count;
                if (centroids[i] < lowest)
                    lowest = centroids[i];
            }
            var courses = new int[mesh.Faces.Count];
            for (int i = 0; i < mesh.Faces.Count; i++)
            {
                courses[i] = (int)Math.Floor(
                    (centroids[i] - lowest) / courseHeight);
            }
            return courses;
        }

        /// <summary>Copied from <c>TnaQueryGeometry.ThrustMesh</c>.</summary>
        private static Mesh ThrustMesh(ResultDto result)
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

        /// <summary>Copied from <c>TnaQueryGeometry.ThrustLine</c>.</summary>
        private static Line ThrustLine(
            EquilibriumResultDto equilibrium,
            TnaEdgeStateDto state)
        {
            EdgeDto edge = equilibrium.Edges[state.EquilibriumEdgeId];
            return new Line(
                Point(equilibrium.Vertices[edge.U]),
                Point(equilibrium.Vertices[edge.V]));
        }

        /// <summary>
        /// The two node indices a member runs between, or (-1, -1) if the id
        /// does not name a real edge.
        ///
        /// Out of range rather than throwing, because this is only used to
        /// decide which BRANCH a member goes in. A member whose ends cannot be
        /// read is still a member and still belongs in the output; it lands in
        /// the infill branch, which is where anything not proved to be on a bar
        /// belongs anyway.
        /// </summary>
        private static (int U, int V) EquilibriumEnds(
            EquilibriumResultDto equilibrium,
            int edgeId)
        {
            if (edgeId < 0 || edgeId >= equilibrium.Edges.Count)
                return (-1, -1);
            EdgeDto edge = equilibrium.Edges[edgeId];
            return (edge.U, edge.V);
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

        /// <summary>Copied from <c>ResultBreakdownComponent.MemberLines</c>.</summary>
        private static Line[] MemberLines(EquilibriumResultDto equilibrium)
        {
            return equilibrium.Edges
                .Select(edge => new Line(
                    Point(equilibrium.Vertices[edge.U]),
                    Point(equilibrium.Vertices[edge.V])))
                .ToArray();
        }

        /// <summary>
        /// FD's counterpart to a TNA edge state's ForceState string. Adapted
        /// from <c>ResultBreakdownComponent.ForceColour</c>'s sign logic,
        /// returning the state name instead of a viewport colour.
        /// </summary>
        private static string ForceState(double force, string signConvention)
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

        private static Point3d Point(Point3Dto value) =>
            new(value.X, value.Y, value.Z);

        private static Vector3d Vector(Point3Dto value) =>
            new(value.X, value.Y, value.Z);
    }

    /// <summary>
    /// Bundles the display preset, weight scale, and vector scale that
    /// Display consumes as <c>STY</c>, so a style choice can be authored
    /// once and wired to several Display calls. Preset names are copied
    /// from the deleted <c>GraphicDiagramDisplayComponent</c>'s own value
    /// list, kept aligned with Display's own preset spellings.
    /// </summary>
    public sealed class StyleComponent : NativeComponentBase
    {
        private static readonly ComponentValueListSpec[] ValueLists =
        {
            new(
                0,
                "Preset",
                new (string Label, string Value)[]
                {
                    ("Analysis", "analysis"),
                    ("Classical GS", "classical"),
                    ("Monochrome", "monochrome")
                },
                "analysis")
        };

        public StyleComponent()
            : base(
                "Style",
                "Style",
                "Bundle a display preset, weight scale, and vector scale " +
                "for the Display component.",
                ComponentCategories.Visualise,
                "diagram_style")
        {
        }

        public override Guid ComponentGuid =>
            new("c3f8a2d6-4e9b-4071-8f5a-b1d7c9e3a250");

        private protected override IReadOnlyList<ComponentValueListSpec>
            SuggestedValueLists => ValueLists;

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddTextParameter(
                "Preset",
                "Preset",
                "Analysis, Classical GS, or Monochrome viewport preset.",
                GH_ParamAccess.item,
                "analysis");
            parameters.AddNumberParameter(
                "Weight Scale",
                "Weight",
                "Display-only multiplier for force-responsive line weights.",
                GH_ParamAccess.item,
                1.0);
            parameters.AddNumberParameter(
                "Vector Scale",
                "Vector",
                "Display-only scale for load/reaction arrows; zero means " +
                "automatic.",
                GH_ParamAccess.item,
                0.0);
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddParameter(
                new StyleParam(),
                "Style",
                "STY",
                "Bundled display preset, weight scale, and vector scale.",
                GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            string preset = "analysis";
            double weightScale = 1.0;
            double vectorScale = 0.0;
            data.GetData(0, ref preset);
            data.GetData(1, ref weightScale);
            data.GetData(2, ref vectorScale);

            var style = new StyleDto
            {
                Preset = StyleDto.NormalisePreset(preset),
                WeightScale = weightScale,
                VectorScale = vectorScale
            };
            IReadOnlyList<string> errors = style.Validate();
            if (errors.Count > 0)
            {
                Message = "Invalid";
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    string.Join(" ", errors));
                return;
            }

            string vector = vectorScale > 0.0 ? $"x{vectorScale:G4}" : "auto";
            Message = $"{style.Preset} · weight x{weightScale:G4} · " +
                $"vector {vector}";
            data.SetData(0, new StyleGoo(style));
        }
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
                "none")
        };

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
                "thrust mesh is TNA Solve's preview; here it is data only.",
                ComponentCategories.Visualise,
                "graphic_diagram_display")
        {
            // This component draws element lines only. Grasshopper's
            // default red preview material on the geometry outputs is what
            // made the thrust surface clash with every element colour, so
            // all geometry outputs stay hidden; their data remains
            // available to every downstream component, and the shaded
            // mesh preview lives on TNA Solve alone.
            for (int index = 0; index <= 4; index++)
            {
                if (Params.Output[index] is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
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
                "Which streams to build and draw: thrust, force, loads, " +
                "reactions, residuals. Residuals draw in the viewport " +
                "only; every other selected stream also feeds its output.",
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
                "Load/reaction/residual vector scale; zero uses Style's " +
                "vector scale, or an automatic scale from the solved " +
                "model's bounding diagonal and largest load/reaction.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Gap",
                "G",
                "Side-by-side force-diagram offset as a fraction of the " +
                "larger diagram span.",
                GH_ParamAccess.item,
                0.15);
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddMeshParameter(
                "Thrust Mesh",
                "TM",
                "Resolved funicular mesh. Empty unless Elements includes " +
                "thrust on a TNA result.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Thrust Lines",
                "TL",
                "Spatial thrust-network edges (or FD member axes). Empty " +
                "unless Elements includes thrust.",
                GH_ParamAccess.list);
            parameters.AddLineParameter(
                "Force Lines",
                "FCL",
                "Reciprocal force-diagram edges, laid out beside the form " +
                "diagram. Empty unless Elements includes force on a TNA " +
                "result.",
                GH_ParamAccess.list);
            parameters.AddLineParameter(
                "Load Lines",
                "LL",
                "Scaled applied-load vectors. Empty unless Elements " +
                "includes loads.",
                GH_ParamAccess.list);
            parameters.AddLineParameter(
                "Reaction Lines",
                "RL",
                "Scaled support-reaction vectors. Empty unless Elements " +
                "includes reactions.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Report",
                "Report",
                "Auto-scale choices, drawn-element counts, and any " +
                "unavailable elements or metrics.",
                GH_ParamAccess.item);
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

            try
            {
                var errors = new List<string>(result.Validate());
                StyleDto? style = styleGoo?.Value;
                if (style is not null)
                    errors.AddRange(style.Validate());

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

                var report = new List<string>();
                if (!string.IsNullOrEmpty(result.Report))
                    report.Add(result.Report);
                if (!isTna)
                    report.Add("FD result: no reciprocal diagram.");
                if (!isTna && metric == "H")
                {
                    report.Add(
                        "Metric H unavailable for FD result; used F " +
                        "magnitude.");
                }

                string preset = style is null
                    ? "analysis"
                    : StyleDto.NormalisePreset(style.Preset);
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
                string vectorScaleSource;
                if (vectorScaleInput > 0.0)
                {
                    effectiveVectorScale = vectorScaleInput;
                    vectorScaleSource = "explicit";
                }
                else if (style is not null && style.VectorScale > 0.0)
                {
                    effectiveVectorScale = style.VectorScale;
                    vectorScaleSource = "style";
                }
                else
                {
                    effectiveVectorScale = autoVectorScale;
                    vectorScaleSource = "auto";
                }
                report.Add(
                    $"Weight x{effectiveWeight:G4}; vector scale " +
                    $"{vectorScaleSource} x{effectiveVectorScale:G4} " +
                    $"(diagonal {diag:G4}, max action {maxAction:G4}).");

                var thrustEdges = new List<MemberEdge>();
                var forceEdges = new List<MemberEdge>();
                var loadLines = new List<Line>();
                var reactionLines = new List<Line>();
                var residualLines = new List<Line>();
                Mesh thrustMesh = new();

                if (isTna)
                {
                    TnaEdgeStateDto[] states = result.EdgeStates
                        .OrderBy(item => item.Id)
                        .ToArray();

                    if (elements.Contains("thrust"))
                    {
                        thrustMesh = ThrustMesh(result);
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
                                0.35,
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
                            Vector3d vector = Vector(item.Vector);
                            if (vector.SquareLength <= 1.0e-24)
                                continue;
                            Point3d start = Point(
                                equilibrium.Vertices[
                                    item.EquilibriumVertexId]);
                            loadLines.Add(new Line(
                                start,
                                start + effectiveVectorScale * vector));
                        }
                    }
                    if (elements.Contains("reactions"))
                    {
                        foreach (TnaSupportMappingDto item in
                                 result.Mappings!.Reactions)
                        {
                            Vector3d vector = Vector(item.Reaction);
                            if (vector.SquareLength <= 1.0e-24)
                                continue;
                            Point3d start = Point(
                                equilibrium.Vertices[
                                    item.EquilibriumVertexId]);
                            reactionLines.Add(new Line(
                                start,
                                start + effectiveVectorScale * vector));
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
                            loadLines.Add(new Line(
                                start,
                                start +
                                effectiveVectorScale * Vector(item.Vector)));
                        }
                    }
                    if (elements.Contains("reactions"))
                    {
                        foreach (NodalVectorDto item in
                                 equilibrium.Reactions)
                        {
                            Point3d start = Point(item.Point);
                            reactionLines.Add(new Line(
                                start,
                                start +
                                effectiveVectorScale * Vector(item.Vector)));
                        }
                    }
                }

                if (elements.Contains("residuals"))
                {
                    foreach (NodalVectorDto item in equilibrium.Residuals)
                    {
                        Point3d start = Point(item.Point);
                        residualLines.Add(new Line(
                            start,
                            start +
                            effectiveVectorScale * Vector(item.Vector)));
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

                // The notched bars, over the thrust network they belong to.
                // Tied to the thrust stream rather than given a filter of
                // their own: on the force diagram there is no such thing as
                // a principal line, so there is nothing to switch on there.
                if (elements.Contains("thrust"))
                {
                    _preview.AddRange(
                        TnaWorkflowPreview.ResultPrincipalLines(result)
                            .Select(line => new DrawLine(
                                line,
                                TnaWorkflowPreview.PrincipalColour,
                                TnaWorkflowPreview.PrincipalWeight,
                                false)));
                }
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

                report.Add(
                    $"Drawn · thrust {thrustEdges.Count}, force " +
                    $"{forceEdges.Count}, loads {loadLines.Count}, " +
                    $"reactions {reactionLines.Count}, residuals " +
                    $"{residualLines.Count}.");

                data.SetData(0, thrustMesh);
                data.SetDataList(1, thrustEdges.Select(edge => edge.Line));
                data.SetDataList(2, forceEdges.Select(edge => edge.Line));
                data.SetDataList(3, loadLines);
                data.SetDataList(4, reactionLines);
                data.SetData(5, string.Join(Environment.NewLine, report));
                Message = $"{result.Solver.ToUpperInvariant()} · {preset}";
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
        /// Copied from <c>DeconstructComponent.ForceState</c>.
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

        /// <summary>Copied from <c>DeconstructComponent.ThrustMesh</c>.</summary>
        private static Mesh ThrustMesh(ResultDto result)
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
