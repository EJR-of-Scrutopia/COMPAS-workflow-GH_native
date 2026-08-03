#nullable enable

using System;
using System.Collections.Generic;
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
        /// Copied from <c>GraphicDiagramDisplayComponent.NormaliseStyle</c>
        /// (that component is untouched) so this contract accepts the same
        /// preset spellings without a contract referencing a component.
        /// Unlike the source, an unrecognised value is returned as-is rather
        /// than thrown, so callers can decide whether to treat it as a
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
            parameters.AddMeshParameter(
                "Thrust Mesh",
                "TM",
                "Resolved funicular mesh reconstructed from the active " +
                "form faces. Empty for FD.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Member Lines",
                "M",
                "Resolved spatial member axes aligned with every other " +
                "member-aligned output.",
                GH_ParamAccess.list);
            parameters.AddLineParameter(
                "Form Lines",
                "FL",
                "Planar form-diagram edges aligned with Member Lines. " +
                "Empty for FD.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "q",
                "q",
                "Signed force density aligned with Member Lines.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "H",
                "H",
                "Signed horizontal-force demand aligned with Member " +
                "Lines. Empty for FD.",
                GH_ParamAccess.list);
            parameters.AddNumberParameter(
                "F",
                "F",
                "Signed axial-force demand aligned with Member Lines.",
                GH_ParamAccess.list);
            parameters.AddTextParameter(
                "Force State",
                "S",
                "Compression, tension, or zero state aligned with Member " +
                "Lines.",
                GH_ParamAccess.list);
            parameters.AddIntegerParameter(
                "Member IDs",
                "MID",
                "Stable member IDs aligned with Member Lines.",
                GH_ParamAccess.list);
            parameters.AddIntegerParameter(
                "Node IDs",
                "NID",
                "Resolved support node IDs aligned with Support Points.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Support Points",
                "SP",
                "Resolved structural-support locations.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Load Points",
                "LP",
                "Points carrying applied loads.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Load Vectors",
                "LV",
                "Applied load vectors aligned with Load Points.",
                GH_ParamAccess.list);
            parameters.AddPointParameter(
                "Reaction Points",
                "RP",
                "Points carrying support reactions.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Reaction Vectors",
                "RV",
                "Support reactions aligned with Reaction Points.",
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

                data.SetData(0, thrustMesh);
                data.SetDataList(1, memberLines);
                data.SetDataList(2, formLines);
                data.SetDataList(3, q);
                data.SetDataList(4, h);
                data.SetDataList(5, f);
                data.SetDataList(6, forceStates);
                data.SetDataList(7, memberIds);
                data.SetDataList(8, nodeIds);
                data.SetDataList(9, supportPoints);
                data.SetDataList(10, loads.Select(item => item.Point));
                data.SetDataList(11, loads.Select(item => item.Vector));
                data.SetDataList(12, reactions.Select(item => item.Point));
                data.SetDataList(13, reactions.Select(item => item.Vector));
                data.SetDataList(14, residuals);
                data.SetDataList(15, diagnostics);
                data.SetData(16, report);
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
    /// Bundles the display preset, weight scale, and vector scale that Task
    /// 11's Display component consumes as <c>STY</c>, so a style choice can
    /// be authored once and wired to several Display calls. Preset names
    /// are read out of <c>GraphicDiagramDisplayComponent</c>'s own value
    /// list so both components stay in lockstep without one referencing the
    /// other.
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
}
