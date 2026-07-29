#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// Compact physical controls for one thrust-network solve. Viewport layout and
/// drawing style deliberately do not belong to this contract.
/// </summary>
public sealed record TnaControlDto : ContractDto
{
    public TnaControlDto()
        : base(ContractKinds.TnaControl)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.TnaControl;

    public string HeightMode { get; init; } = "zmax";

    public double HeightValue { get; init; } = 5.0;

    public double HorizontalAlpha { get; init; } = 100.0;

    public int HorizontalIterations { get; init; } = 100;

    public int VerticalIterations { get; init; } = 100;

    public double Tolerance { get; init; } = 1.0e-3;

    protected override void ValidatePayload(List<string> errors)
    {
        string mode = NormaliseHeightMode(HeightMode);
        if (mode is not ("zmax" or "q"))
            errors.Add("heightMode must be 'zmax' or 'q'.");
        if (!ContractRules.IsFinite(HeightValue))
            errors.Add("heightValue must be finite.");
        else if (mode == "q" && Math.Abs(HeightValue) <= 1.0e-12)
            errors.Add("q height control requires a non-zero heightValue.");
        if (!ContractRules.IsFinite(HorizontalAlpha) ||
            HorizontalAlpha < 0.0 ||
            HorizontalAlpha > 100.0)
        {
            errors.Add("horizontalAlpha must be between 0 and 100.");
        }
        if (HorizontalIterations < 1)
            errors.Add("horizontalIterations must be positive.");
        if (VerticalIterations < 1)
            errors.Add("verticalIterations must be positive.");
        if (!ContractRules.IsFinite(Tolerance) || Tolerance <= 0.0)
            errors.Add("tolerance must be finite and greater than zero.");
    }

    public static string NormaliseHeightMode(string? value)
    {
        string mode = (value ?? string.Empty)
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_", StringComparison.Ordinal);
        return mode switch
        {
            "crown_height" or "height" => "zmax",
            "force_scale" or "q_scale" => "q",
            _ => mode
        };
    }
}

public sealed record AnalysisPlaneDto
{
    public Point3Dto Origin { get; init; } = new(0.0, 0.0, 0.0);

    public Point3Dto XAxis { get; init; } = new(1.0, 0.0, 0.0);

    public Point3Dto YAxis { get; init; } = new(0.0, 1.0, 0.0);

    public Point3Dto ZAxis { get; init; } = new(0.0, 0.0, 1.0);
}

public sealed record TnaGraphVertexDto
{
    public int Id { get; init; }

    public JsonElement Key { get; init; }

    public Point3Dto Point { get; init; } = new(0.0, 0.0, 0.0);

    public IReadOnlyList<JsonElement> SourceVertexIds { get; init; } =
        Array.Empty<JsonElement>();
}

public sealed record TnaGraphEdgeDto
{
    public int Id { get; init; }

    public JsonElement Key { get; init; }

    public int U { get; init; }

    public int V { get; init; }

    public IReadOnlyList<int> SourceEdgeIds { get; init; } =
        Array.Empty<int>();
}

public sealed record TnaGraphFaceDto
{
    public int Id { get; init; }

    public JsonElement Key { get; init; }

    public IReadOnlyList<int> Vertices { get; init; } =
        Array.Empty<int>();
}

public sealed record TnaDiagramGraphDto
{
    public IReadOnlyList<TnaGraphVertexDto> Vertices { get; init; } =
        Array.Empty<TnaGraphVertexDto>();

    public IReadOnlyList<TnaGraphEdgeDto> Edges { get; init; } =
        Array.Empty<TnaGraphEdgeDto>();

    public IReadOnlyList<TnaGraphFaceDto> Faces { get; init; } =
        Array.Empty<TnaGraphFaceDto>();
}

public sealed record TnaEdgeStateDto
{
    public int Id { get; init; }

    public int EquilibriumEdgeId { get; init; }

    public IReadOnlyList<int> SourceEdgeIds { get; init; } =
        Array.Empty<int>();

    public int FormEdgeId { get; init; }

    public int ForceEdgeId { get; init; }

    public double ForceDensity { get; init; }

    public double HorizontalForce { get; init; }

    public double AxialForce { get; init; }

    public string ForceState { get; init; } = "unknown";

    public double ReciprocityErrorDegrees { get; init; }
}

public sealed record TnaSourceVertexMappingDto
{
    public int? TopologyVertexId { get; init; }

    public JsonElement SourceVertexId { get; init; }

    public int? FormVertexId { get; init; }

    public int? EquilibriumVertexId { get; init; }
}

public sealed record TnaSourceEdgeMappingDto
{
    public int SourceEdgeId { get; init; }

    public int SourceU { get; init; }

    public int SourceV { get; init; }

    public int? FormEdgeId { get; init; }
}

public sealed record TnaEdgeMappingDto
{
    public int FormEdgeId { get; init; }

    public int TargetEdgeId { get; init; }
}

public sealed record TnaSupportMappingDto
{
    public int? TopologyVertexId { get; init; }

    public JsonElement? SourceVertexId { get; init; }

    public int FormVertexId { get; init; }

    public int EquilibriumVertexId { get; init; }

    public Point3Dto Reaction { get; init; } = new(0.0, 0.0, 0.0);
}

public sealed record TnaLoadMappingDto
{
    public IReadOnlyList<int> TopologyVertexIds { get; init; } =
        Array.Empty<int>();

    public IReadOnlyList<JsonElement> SourceVertexIds { get; init; } =
        Array.Empty<JsonElement>();

    public int FormVertexId { get; init; }

    public int EquilibriumVertexId { get; init; }

    public Point3Dto Vector { get; init; } = new(0.0, 0.0, 0.0);
}

public sealed record TnaMappingsDto
{
    public IReadOnlyList<TnaSourceVertexMappingDto>
        SourceVertexToFormVertex { get; init; } =
        Array.Empty<TnaSourceVertexMappingDto>();

    public IReadOnlyList<TnaSourceEdgeMappingDto>
        SourceEdgeToFormEdge { get; init; } =
        Array.Empty<TnaSourceEdgeMappingDto>();

    public IReadOnlyList<TnaEdgeMappingDto>
        FormEdgeToForceEdge { get; init; } =
        Array.Empty<TnaEdgeMappingDto>();

    public IReadOnlyList<TnaEdgeMappingDto>
        FormEdgeToEquilibriumEdge { get; init; } =
        Array.Empty<TnaEdgeMappingDto>();

    public IReadOnlyList<TnaSupportMappingDto> Supports { get; init; } =
        Array.Empty<TnaSupportMappingDto>();

    public IReadOnlyList<TnaLoadMappingDto> Loads { get; init; } =
        Array.Empty<TnaLoadMappingDto>();

    public IReadOnlyList<TnaSupportMappingDto> Reactions { get; init; } =
        Array.Empty<TnaSupportMappingDto>();
}

/// <summary>
/// One immutable TNA state: spatial equilibrium plus the reciprocal planar
/// form/force pair and explicit source correspondence.
/// </summary>
public sealed record TnaResultDto : ContractDto
{
    public TnaResultDto()
        : base(ContractKinds.TnaResult)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.TnaResult;

    public EquilibriumResultDto? Equilibrium { get; init; }

    public TnaControlDto? Control { get; init; }

    public AnalysisPlaneDto AnalysisPlane { get; init; } = new();

    public TnaDiagramGraphDto FormGraph { get; init; } = new();

    public TnaDiagramGraphDto ForceGraph { get; init; } = new();

    public IReadOnlyList<TnaEdgeStateDto> EdgeStates { get; init; } =
        Array.Empty<TnaEdgeStateDto>();

    public double HorizontalScale { get; init; } = 1.0;

    public TnaMappingsDto Mappings { get; init; } = new();

    public IReadOnlyList<DiagnosticDto> Diagnostics { get; init; } =
        Array.Empty<DiagnosticDto>();

    public string Report { get; init; } = string.Empty;

    protected override void ValidatePayload(List<string> errors)
    {
        if (Equilibrium is null)
        {
            errors.Add("equilibrium is missing.");
        }
        else
        {
            ContractRules.AddNested(
                errors,
                "equilibrium",
                Equilibrium.Validate());
            if (!string.Equals(
                    Equilibrium.Solver,
                    "tna",
                    StringComparison.OrdinalIgnoreCase))
            {
                errors.Add("equilibrium.solver must be 'tna'.");
            }
            if (!string.Equals(
                    Equilibrium.Problem?.Topology?.NetworkKind,
                    "faced",
                    StringComparison.OrdinalIgnoreCase))
            {
                errors.Add("TNA requires a faced source topology.");
            }
        }

        if (Control is null)
            errors.Add("control is missing.");
        else
            ContractRules.AddNested(errors, "control", Control.Validate());

        TnaContractRules.ValidatePlane(AnalysisPlane, "analysisPlane", errors);
        TnaContractRules.ValidateGraph(FormGraph, "formGraph", errors);
        TnaContractRules.ValidateGraph(ForceGraph, "forceGraph", errors);

        if (!ContractRules.IsFinite(HorizontalScale) ||
            Math.Abs(HorizontalScale) <= 1.0e-12)
        {
            errors.Add("horizontalScale must be finite and non-zero.");
        }

        if (EdgeStates is null || EdgeStates.Count == 0)
        {
            errors.Add("edgeStates must contain reciprocal member states.");
        }
        else
        {
            var stateIds = new HashSet<int>();
            var equilibriumIds = new HashSet<int>();
            var stateFormIds = new HashSet<int>();
            var stateForceIds = new HashSet<int>();
            HashSet<int> formIds = FormGraph.Edges.Select(edge => edge.Id).ToHashSet();
            HashSet<int> forceIds = ForceGraph.Edges.Select(edge => edge.Id).ToHashSet();
            int equilibriumCount = Equilibrium?.Edges.Count ?? 0;
            int sourceCount = Equilibrium?.Problem?.Topology?.Edges.Count ?? 0;
            for (int index = 0; index < EdgeStates.Count; index++)
            {
                TnaEdgeStateDto? state = EdgeStates[index];
                if (state is null)
                {
                    errors.Add($"edgeStates[{index}] is missing.");
                    continue;
                }
                if (!stateIds.Add(state.Id))
                    errors.Add($"edgeStates[{index}] has a duplicate id.");
                if (!equilibriumIds.Add(state.EquilibriumEdgeId))
                {
                    errors.Add(
                        $"edgeStates[{index}] duplicates an equilibrium edge.");
                }
                if (state.EquilibriumEdgeId < 0 ||
                    state.EquilibriumEdgeId >= equilibriumCount)
                {
                    errors.Add(
                        $"edgeStates[{index}].equilibriumEdgeId is invalid.");
                }
                if (!formIds.Contains(state.FormEdgeId))
                    errors.Add($"edgeStates[{index}].formEdgeId is invalid.");
                else if (!stateFormIds.Add(state.FormEdgeId))
                    errors.Add($"edgeStates[{index}] duplicates a form edge.");
                if (!forceIds.Contains(state.ForceEdgeId))
                    errors.Add($"edgeStates[{index}].forceEdgeId is invalid.");
                else if (!stateForceIds.Add(state.ForceEdgeId))
                    errors.Add($"edgeStates[{index}] duplicates a force edge.");
                if (state.SourceEdgeIds is null ||
                    state.SourceEdgeIds.Any(id => id < 0 || id >= sourceCount))
                {
                    errors.Add($"edgeStates[{index}].sourceEdgeIds is invalid.");
                }
                if (!ContractRules.IsFinite(state.ForceDensity) ||
                    !ContractRules.IsFinite(state.HorizontalForce) ||
                    !ContractRules.IsFinite(state.AxialForce) ||
                    !ContractRules.IsFinite(state.ReciprocityErrorDegrees) ||
                    state.ReciprocityErrorDegrees < 0.0)
                {
                    errors.Add($"edgeStates[{index}] contains an invalid value.");
                }
                string forceState = (state.ForceState ?? string.Empty)
                    .Trim()
                    .ToLowerInvariant();
                if (forceState is not (
                        "compression" or "tension" or "zero" or "unknown"))
                {
                    errors.Add(
                        $"edgeStates[{index}].forceState is not supported.");
                }
            }
            if (!stateFormIds.SetEquals(formIds))
                errors.Add("edgeStates do not cover every form edge exactly once.");
            if (!stateForceIds.SetEquals(forceIds))
                errors.Add("edgeStates do not cover every force edge exactly once.");
            if (equilibriumIds.Count != equilibriumCount)
            {
                errors.Add(
                    "edgeStates do not cover every equilibrium/thrust edge " +
                    "exactly once.");
            }
        }

        TnaContractRules.ValidateMappings(
            Mappings,
            Equilibrium?.Problem?.Topology,
            FormGraph,
            ForceGraph,
            Equilibrium,
            errors);

        if (Diagnostics is null)
        {
            errors.Add("diagnostics is missing.");
        }
        else
        {
            for (int index = 0; index < Diagnostics.Count; index++)
            {
                DiagnosticDto? diagnostic = Diagnostics[index];
                if (diagnostic is null)
                    errors.Add($"diagnostics[{index}] is missing.");
                else
                    ContractRules.AddNested(
                        errors,
                        $"diagnostics[{index}]",
                        diagnostic.Validate());
            }
        }
    }
}

public sealed record GraphicEdgeDto
{
    public int Id { get; init; }

    public string Role { get; init; } = string.Empty;

    public Point3Dto Start { get; init; } = new(0.0, 0.0, 0.0);

    public Point3Dto End { get; init; } = new(0.0, 0.0, 0.0);

    public double Magnitude { get; init; }

    public double ForceDensity { get; init; }

    public double HorizontalForce { get; init; }

    public double AxialForce { get; init; }

    public string ForceState { get; init; } = "unknown";

    public int? EquilibriumEdgeId { get; init; }

    public int? FormEdgeId { get; init; }

    public int? ForceEdgeId { get; init; }

    public IReadOnlyList<int> SourceEdgeIds { get; init; } =
        Array.Empty<int>();
}

/// <summary>
/// Renderer-neutral line bundle produced by TNA Reciprocal. It keeps the
/// three diagrams compact and preserves the explicit reciprocal mapping.
/// </summary>
public sealed record GraphicDiagramDto : ContractDto
{
    public GraphicDiagramDto()
        : base(ContractKinds.GraphicDiagram)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.GraphicDiagram;

    public string DiagramKind { get; init; } = "tna_reciprocal";

    public string TopologyHash { get; init; } = string.Empty;

    public AnalysisPlaneDto AnalysisPlane { get; init; } = new();

    public string Layout { get; init; } = "side_by_side";

    public Point3Dto ForceDiagramOffset { get; init; } =
        new(0.0, 0.0, 0.0);

    public double DisplayForceScale { get; init; } = 1.0;

    public string DisplayMetric { get; init; } = "natural";

    public double VectorScale { get; init; } = 1.0;

    public double HorizontalScale { get; init; } = 1.0;

    public IReadOnlyList<GraphicEdgeDto> ThrustEdges { get; init; } =
        Array.Empty<GraphicEdgeDto>();

    public IReadOnlyList<GraphicEdgeDto> FormEdges { get; init; } =
        Array.Empty<GraphicEdgeDto>();

    public IReadOnlyList<GraphicEdgeDto> ForceEdges { get; init; } =
        Array.Empty<GraphicEdgeDto>();

    public IReadOnlyList<GraphicEdgeDto> LoadEdges { get; init; } =
        Array.Empty<GraphicEdgeDto>();

    public IReadOnlyList<GraphicEdgeDto> ReactionEdges { get; init; } =
        Array.Empty<GraphicEdgeDto>();

    public string Report { get; init; } = string.Empty;

    protected override void ValidatePayload(List<string> errors)
    {
        if (!string.Equals(
                DiagramKind,
                "tna_reciprocal",
                StringComparison.Ordinal))
        {
            errors.Add("diagramKind must be 'tna_reciprocal'.");
        }
        ContractRules.ValidateTopologyHash(
            TopologyHash,
            "topologyHash",
            errors);
        TnaContractRules.ValidatePlane(AnalysisPlane, "analysisPlane", errors);
        string layout = (Layout ?? string.Empty).Trim().ToLowerInvariant();
        if (layout is not ("side_by_side" or "overlay"))
            errors.Add("layout must be 'side_by_side' or 'overlay'.");
        ContractRules.ValidatePoint(
            ForceDiagramOffset,
            "forceDiagramOffset",
            errors);
        if (!ContractRules.IsFinite(DisplayForceScale) ||
            DisplayForceScale <= 0.0)
        {
            errors.Add("displayForceScale must be greater than zero.");
        }
        string metric = (DisplayMetric ?? string.Empty)
            .Trim()
            .ToLowerInvariant();
        if (metric is not (
                "natural" or
                "force_density" or
                "horizontal_force" or
                "axial_force"))
        {
            errors.Add(
                "displayMetric must be natural, force_density, " +
                "horizontal_force, or axial_force.");
        }
        if (!ContractRules.IsFinite(VectorScale) || VectorScale <= 0.0)
            errors.Add("vectorScale must be greater than zero.");
        if (!ContractRules.IsFinite(HorizontalScale) ||
            Math.Abs(HorizontalScale) <= 1.0e-12)
        {
            errors.Add("horizontalScale must be finite and non-zero.");
        }
        TnaContractRules.ValidateGraphicEdges(
            ThrustEdges,
            "thrust",
            "thrustEdges",
            errors);
        TnaContractRules.ValidateGraphicEdges(
            FormEdges,
            "form",
            "formEdges",
            errors);
        TnaContractRules.ValidateGraphicEdges(
            ForceEdges,
            "force",
            "forceEdges",
            errors);
        TnaContractRules.ValidateGraphicEdges(
            LoadEdges,
            "load",
            "loadEdges",
            errors,
            required: false);
        TnaContractRules.ValidateGraphicEdges(
            ReactionEdges,
            "reaction",
            "reactionEdges",
            errors,
            required: false);
    }
}

internal static class TnaContractRules
{
    public static void ValidatePlane(
        AnalysisPlaneDto? plane,
        string label,
        List<string> errors)
    {
        if (plane is null)
        {
            errors.Add($"{label} is missing.");
            return;
        }
        ContractRules.ValidatePoint(plane.Origin, $"{label}.origin", errors);
        ContractRules.ValidatePoint(plane.XAxis, $"{label}.xAxis", errors);
        ContractRules.ValidatePoint(plane.YAxis, $"{label}.yAxis", errors);
        ContractRules.ValidatePoint(plane.ZAxis, $"{label}.zAxis", errors);
        if (LengthSquared(plane.XAxis) <= 1.0e-24 ||
            LengthSquared(plane.YAxis) <= 1.0e-24 ||
            LengthSquared(plane.ZAxis) <= 1.0e-24)
        {
            errors.Add($"{label} axes must be non-zero.");
        }
        else
        {
            Point3Dto cross = Cross(plane.XAxis, plane.YAxis);
            if (LengthSquared(cross) <=
                1.0e-20 *
                LengthSquared(plane.XAxis) *
                LengthSquared(plane.YAxis))
            {
                errors.Add($"{label} X and Y axes must not be parallel.");
            }
        }
    }

    public static void ValidateGraph(
        TnaDiagramGraphDto? graph,
        string label,
        List<string> errors)
    {
        if (graph is null)
        {
            errors.Add($"{label} is missing.");
            return;
        }
        if (graph.Vertices is null || graph.Vertices.Count == 0)
            errors.Add($"{label}.vertices must not be empty.");
        if (graph.Edges is null || graph.Edges.Count == 0)
            errors.Add($"{label}.edges must not be empty.");

        var vertexIds = new HashSet<int>();
        foreach (TnaGraphVertexDto vertex in
                 graph.Vertices ?? Array.Empty<TnaGraphVertexDto>())
        {
            if (!vertexIds.Add(vertex.Id))
                errors.Add($"{label}.vertices contains duplicate id {vertex.Id}.");
            ContractRules.ValidatePoint(
                vertex.Point,
                $"{label}.vertices[{vertex.Id}].point",
                errors);
        }

        var edgeIds = new HashSet<int>();
        foreach (TnaGraphEdgeDto edge in
                 graph.Edges ?? Array.Empty<TnaGraphEdgeDto>())
        {
            if (!edgeIds.Add(edge.Id))
                errors.Add($"{label}.edges contains duplicate id {edge.Id}.");
            if (edge.U == edge.V ||
                !vertexIds.Contains(edge.U) ||
                !vertexIds.Contains(edge.V))
            {
                errors.Add($"{label}.edges[{edge.Id}] has invalid endpoints.");
            }
        }

        var faceIds = new HashSet<int>();
        foreach (TnaGraphFaceDto face in
                 graph.Faces ?? Array.Empty<TnaGraphFaceDto>())
        {
            if (!faceIds.Add(face.Id))
                errors.Add($"{label}.faces contains duplicate id {face.Id}.");
            if (face.Vertices is null ||
                face.Vertices.Distinct().Count() < 3 ||
                face.Vertices.Any(vertexId => !vertexIds.Contains(vertexId)))
            {
                errors.Add($"{label}.faces[{face.Id}] is invalid.");
            }
        }
    }

    public static void ValidateMappings(
        TnaMappingsDto? mappings,
        TopologyDto? topology,
        TnaDiagramGraphDto form,
        TnaDiagramGraphDto force,
        EquilibriumResultDto? equilibrium,
        List<string> errors)
    {
        if (mappings is null)
        {
            errors.Add("mappings is missing.");
            return;
        }
        int topologyVertexCount = topology?.Vertices.Count ?? 0;
        int topologyEdgeCount = topology?.Edges.Count ?? 0;
        int equilibriumVertexCount = equilibrium?.Vertices.Count ?? 0;
        int equilibriumEdgeCount = equilibrium?.Edges.Count ?? 0;
        HashSet<int> formVertices =
            form.Vertices.Select(vertex => vertex.Id).ToHashSet();
        HashSet<int> formEdges = form.Edges.Select(edge => edge.Id).ToHashSet();
        HashSet<int> forceEdges = force.Edges.Select(edge => edge.Id).ToHashSet();

        foreach (TnaSourceVertexMappingDto item in
                 mappings.SourceVertexToFormVertex)
        {
            if (item.TopologyVertexId is int topologyId &&
                (topologyId < 0 || topologyId >= topologyVertexCount))
            {
                errors.Add("mappings.sourceVertexToFormVertex has an invalid topology vertex.");
            }
            if (item.FormVertexId is int formId &&
                !formVertices.Contains(formId))
            {
                errors.Add("mappings.sourceVertexToFormVertex has an invalid form vertex.");
            }
            if (item.EquilibriumVertexId is int equilibriumId &&
                (equilibriumId < 0 || equilibriumId >= equilibriumVertexCount))
            {
                errors.Add("mappings.sourceVertexToFormVertex has an invalid equilibrium vertex.");
            }
        }
        foreach (TnaSourceEdgeMappingDto item in
                 mappings.SourceEdgeToFormEdge)
        {
            if (item.SourceEdgeId < 0 ||
                item.SourceEdgeId >= topologyEdgeCount)
            {
                errors.Add("mappings.sourceEdgeToFormEdge has an invalid source edge.");
            }
            if (item.FormEdgeId is int formId && !formEdges.Contains(formId))
                errors.Add("mappings.sourceEdgeToFormEdge has an invalid form edge.");
        }
        foreach (TnaEdgeMappingDto item in mappings.FormEdgeToForceEdge)
        {
            if (!formEdges.Contains(item.FormEdgeId) ||
                !forceEdges.Contains(item.TargetEdgeId))
            {
                errors.Add("mappings.formEdgeToForceEdge contains an invalid edge.");
            }
        }
        foreach (TnaEdgeMappingDto item in mappings.FormEdgeToEquilibriumEdge)
        {
            if (!formEdges.Contains(item.FormEdgeId) ||
                item.TargetEdgeId < 0 ||
                item.TargetEdgeId >= equilibriumEdgeCount)
            {
                errors.Add("mappings.formEdgeToEquilibriumEdge contains an invalid edge.");
            }
        }
        foreach (TnaSupportMappingDto item in mappings.Supports)
        {
            ValidateSupport(
                item,
                topologyVertexCount,
                formVertices,
                equilibriumVertexCount,
                "supports",
                errors);
        }
        foreach (TnaSupportMappingDto item in mappings.Reactions)
        {
            ValidateSupport(
                item,
                topologyVertexCount,
                formVertices,
                equilibriumVertexCount,
                "reactions",
                errors);
        }
        foreach (TnaLoadMappingDto item in mappings.Loads)
        {
            if (item.TopologyVertexIds.Any(
                    id => id < 0 || id >= topologyVertexCount) ||
                !formVertices.Contains(item.FormVertexId) ||
                item.EquilibriumVertexId < 0 ||
                item.EquilibriumVertexId >= equilibriumVertexCount)
            {
                errors.Add("mappings.loads contains an invalid vertex.");
            }
            ContractRules.ValidatePoint(item.Vector, "mappings.loads.vector", errors);
        }
    }

    public static void ValidateGraphicEdges(
        IReadOnlyList<GraphicEdgeDto>? values,
        string role,
        string label,
        List<string> errors,
        bool required = true)
    {
        if (values is null)
        {
            errors.Add($"{label} is missing.");
            return;
        }
        if (required && values.Count == 0)
        {
            errors.Add($"{label} must not be empty.");
            return;
        }
        var ids = new HashSet<int>();
        for (int index = 0; index < values.Count; index++)
        {
            GraphicEdgeDto? edge = values[index];
            if (edge is null)
            {
                errors.Add($"{label}[{index}] is missing.");
                continue;
            }
            if (!ids.Add(edge.Id))
                errors.Add($"{label}[{index}] has a duplicate id.");
            if (!string.Equals(edge.Role, role, StringComparison.Ordinal))
                errors.Add($"{label}[{index}] has an invalid role.");
            ContractRules.ValidatePoint(edge.Start, $"{label}[{index}].start", errors);
            ContractRules.ValidatePoint(edge.End, $"{label}[{index}].end", errors);
            if (!ContractRules.IsFinite(edge.Magnitude) ||
                edge.Magnitude < 0.0 ||
                !ContractRules.IsFinite(edge.ForceDensity) ||
                !ContractRules.IsFinite(edge.HorizontalForce) ||
                !ContractRules.IsFinite(edge.AxialForce))
            {
                errors.Add($"{label}[{index}].magnitude is invalid.");
            }
            bool external = role is "load" or "reaction";
            if (!external &&
                (!edge.EquilibriumEdgeId.HasValue ||
                 !edge.FormEdgeId.HasValue ||
                 !edge.ForceEdgeId.HasValue))
            {
                errors.Add(
                    $"{label}[{index}] is missing reciprocal correspondence.");
            }
            if (external &&
                !string.Equals(
                    edge.ForceState,
                    "external",
                    StringComparison.Ordinal))
            {
                errors.Add($"{label}[{index}] must be marked external.");
            }
        }
    }

    private static void ValidateSupport(
        TnaSupportMappingDto item,
        int topologyVertexCount,
        HashSet<int> formVertices,
        int equilibriumVertexCount,
        string label,
        List<string> errors)
    {
        if (item.TopologyVertexId is int topologyId &&
            (topologyId < 0 || topologyId >= topologyVertexCount))
        {
            errors.Add($"mappings.{label} has an invalid topology vertex.");
        }
        if (!formVertices.Contains(item.FormVertexId) ||
            item.EquilibriumVertexId < 0 ||
            item.EquilibriumVertexId >= equilibriumVertexCount)
        {
            errors.Add($"mappings.{label} has an invalid mapped vertex.");
        }
        ContractRules.ValidatePoint(
            item.Reaction,
            $"mappings.{label}.reaction",
            errors);
    }

    private static double LengthSquared(Point3Dto value) =>
        value.X * value.X + value.Y * value.Y + value.Z * value.Z;

    private static Point3Dto Cross(Point3Dto a, Point3Dto b) =>
        new(
            a.Y * b.Z - a.Z * b.Y,
            a.Z * b.X - a.X * b.Z,
            a.X * b.Y - a.Y * b.X);
}
