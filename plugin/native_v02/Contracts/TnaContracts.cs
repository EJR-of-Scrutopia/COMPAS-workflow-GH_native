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

    /// <summary>
    /// "natural" solves to the equilibrium height of the current force
    /// densities (no value); "zmax" scales to an exact crown height;
    /// "q" applies a signed force-density scale directly.
    /// </summary>
    public string HeightMode { get; init; } = "natural";

    /// <summary>Null in natural mode; the target in zmax/q mode.</summary>
    public double? HeightValue { get; init; }

    public double HorizontalAlpha { get; init; } = 100.0;

    /// <summary>
    /// Null runs the worker's auto-converging horizontal solve: blocks of
    /// iterations until the reciprocity angle falls below one degree or
    /// the hard cap is reached. A number fixes the iteration count.
    /// </summary>
    public int? HorizontalIterations { get; init; }

    /// <summary>
    /// "iterative" runs the parallelisation loop; "algebraic" solves the
    /// exact force densities from the equilibrium matrix in one sparse
    /// least-squares pass (requires HorizontalAlpha 100 and ignores
    /// HorizontalIterations).
    /// </summary>
    public string HorizontalMethod { get; init; } = "iterative";

    public int VerticalIterations { get; init; } = 1000;

    public double Tolerance { get; init; } = 1.0e-3;

    protected override void ValidatePayload(List<string> errors)
    {
        string mode = NormaliseHeightMode(HeightMode);
        if (mode is not ("zmax" or "q" or "natural"))
            errors.Add("heightMode must be 'zmax', 'q', or 'natural'.");
        if (mode == "natural")
        {
            if (HeightValue is not null)
                errors.Add("natural height control carries no heightValue.");
        }
        else if (HeightValue is null || !ContractRules.IsFinite(HeightValue.Value))
        {
            errors.Add($"{mode} height control requires a finite heightValue.");
        }
        else if (mode == "q" && Math.Abs(HeightValue.Value) <= 1.0e-12)
        {
            errors.Add("q height control requires a non-zero heightValue.");
        }
        if (!ContractRules.IsFinite(HorizontalAlpha) ||
            HorizontalAlpha < 0.0 ||
            HorizontalAlpha > 100.0)
        {
            errors.Add("horizontalAlpha must be between 0 and 100.");
        }
        if (HorizontalIterations is < 1)
            errors.Add("horizontalIterations must be positive when given.");
        string method = (HorizontalMethod ?? string.Empty)
            .Trim()
            .ToLowerInvariant();
        if (method is not ("" or "iterative" or "algebraic"))
            errors.Add(
                "horizontalMethod must be 'iterative' or 'algebraic'.");
        if (method == "algebraic" && HorizontalAlpha != 100.0)
            errors.Add(
                "the algebraic horizontal method fixes the form diagram; " +
                "horizontalAlpha must be 100.");
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
            "" or "auto" or "equilibrium" => "natural",
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

/// <summary>
/// One vertex of a diagram graph. <see cref="Id"/> IS THE IDENTITY and the
/// array position is NOT: read a graph by id, never by where a vertex
/// happens to sit in the list. Both of this plugin's own readers do
/// (<c>MouldGeometry.ThrustMeshFromResult</c> and
/// <c>SkinPatterns.ReadNet</c>, each <c>OrderBy(item => item.Id)</c>), and
/// that agreement is the contract rather than a coincidence.
///
/// <see cref="Point"/> is the FORM diagram's own position, which is a
/// diagram and not the vault: the built surface is at
/// <c>Equilibrium.Vertices</c>, reached through
/// <see cref="TnaMappingsDto.SourceVertexToFormVertex"/>. A reader wanting
/// geometry wants that, not this.
/// </summary>
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

/// <summary>
/// One face of a diagram graph, and the sharpest index-space trap the
/// contract carries.
///
/// <see cref="Vertices"/> holds FORM VERTEX IDS. They are not positions in
/// the face array, and they are NOT indices into
/// <c>Equilibrium.Vertices</c>: form vertices and equilibrium vertices are
/// two different numberings of the same points, and the ONLY bridge between
/// them is <see cref="TnaMappingsDto.SourceVertexToFormVertex"/>. Resolve
/// every entry through it, form id to equilibrium id, before touching a
/// coordinate.
///
/// IT MATTERS BECAUSE THE SHORTCUT FAILS AS A WRONG ANSWER RATHER THAN AN
/// ERROR. On a net whose two spaces happen to have the same count -- which
/// every study exported so far does, with the mapping the identity on every
/// vertex -- feeding a form id straight into an equilibrium lookup indexes
/// the wrong vertex SILENTLY, and builds a surface that renders, measures
/// and analyses without complaint. A reader that takes the shortcut
/// therefore passes its own tests, passes review, and breaks on the first
/// study whose two spaces diverge.
///
/// <see cref="Id"/> is the identity here too, exactly as on
/// <see cref="TnaGraphVertexDto"/>: order faces by it rather than trusting
/// their array position. Ids are positional on every contract written to
/// date, which is precisely why a reader that trusts position looks correct
/// for as long as anyone has checked.
/// </summary>
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

/// <summary>
/// THE JOINS BETWEEN THE CONTRACT'S INDEX SPACES, and the reason they have
/// to exist at all. One point of the vault is numbered THREE different ways:
/// as a SOURCE vertex (his input net), as a FORM vertex (the form diagram's
/// graph, whose faces are written in this numbering), and as an EQUILIBRIUM
/// vertex, which is a POSITION in <c>Equilibrium.Vertices</c> -- that array
/// carries no ids, so its index IS its equilibrium id. Nothing outside this
/// block says which numbering a given integer belongs to.
///
/// <see cref="SourceVertexToFormVertex"/> is the one a geometry reader
/// needs: its entries carry both <c>FormVertexId</c> and
/// <c>EquilibriumVertexId</c>, so it is what turns a face's form vertex ids
/// into coordinates. <see cref="Supports"/> names its vertices in BOTH
/// spaces for the same reason.
///
/// Every one of these joins is the identity on every study exported to
/// date, which is exactly what makes skipping them survive testing. See
/// <see cref="TnaGraphFaceDto"/> for what that costs when it stops being
/// true.
/// </summary>
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
