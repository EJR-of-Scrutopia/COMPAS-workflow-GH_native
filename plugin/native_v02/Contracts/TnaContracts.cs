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

internal static class TnaContractRules
{
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
}
