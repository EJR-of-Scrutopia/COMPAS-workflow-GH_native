#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// Contract discriminators for the staged RhinoVault-style TNA canvas.
/// These are deliberately separate from a solved <see cref="TnaResultDto"/>:
/// a prepared topological dual is not an equilibrium result.
/// </summary>
public static class TnaWorkflowContractKinds
{
    public const string Pattern = "ananke.tna_pattern";
    public const string Prepared = "ananke.tna_prepared";
}

/// <summary>
/// One source pattern on stable Rhino/Grasshopper node IDs. Supports are
/// attached by the next canvas stage without splitting the topology and
/// support state across parallel wires.
/// </summary>
public sealed record TnaPatternDto : ContractDto
{
    public TnaPatternDto()
        : base(TnaWorkflowContractKinds.Pattern)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => TnaWorkflowContractKinds.Pattern;

    public string PatternMode { get; init; } = "mesh";

    public TopologyDto? Topology { get; init; }

    public SupportSetDto? Supports { get; init; }

    public int Resolution { get; init; } = 8;

    public double WeldTolerance { get; init; } = 1.0e-6;

    public static string NormaliseMode(string? value)
    {
        string mode = (value ?? string.Empty)
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_", StringComparison.Ordinal);
        return mode switch
        {
            "rhinolines" or "rhino_lines" or "line" => "lines",
            "rhinomesh" or "rhino_mesh" => "mesh",
            "rhinosurface" or "rhino_surface" => "surface",
            "meshgrid" or "mesh_grid" => "grid",
            "triangulate" => "triangulation",
            _ => mode
        };
    }

    protected override void ValidatePayload(List<string> errors)
    {
        string mode = NormaliseMode(PatternMode);
        if (mode is not (
                "mesh" or
                "lines" or
                "surface" or
                "grid" or
                "triangulation" or
                "skeleton"))
        {
            errors.Add(
                "patternMode must be Mesh, Lines, Surface, Grid, " +
                "Triangulation, or Skeleton.");
        }

        if (Topology is null)
        {
            errors.Add("topology is missing.");
        }
        else
        {
            ContractRules.AddNested(errors, "topology", Topology.Validate());
            string topologyKind = (Topology.NetworkKind ?? string.Empty)
                .Trim()
                .ToLowerInvariant();
            if (mode == "lines" && topologyKind != "line")
                errors.Add("Lines mode requires a line topology.");
            if (mode != "lines" && topologyKind != "faced")
                errors.Add($"{mode} mode requires a faced topology.");
        }

        if (Resolution < 1)
            errors.Add("resolution must be positive.");
        if (!ContractRules.IsFinite(WeldTolerance) || WeldTolerance <= 0.0)
            errors.Add("weldTolerance must be finite and greater than zero.");

        if (Supports is not null)
        {
            ContractRules.AddNested(errors, "supports", Supports.Validate());
            if (Topology is not null &&
                !string.Equals(
                    Supports.TopologyHash,
                    Topology.TopologyHash,
                    StringComparison.OrdinalIgnoreCase))
            {
                errors.Add("supports belongs to a different source topology.");
            }
            if (Topology is not null &&
                Supports.NodeIds.Any(
                    nodeId => nodeId >= Topology.Vertices.Count))
            {
                errors.Add("supports contains a node ID outside topology.");
            }
        }
    }
}

/// <summary>
/// Exact plan-relaxation controls crossing the <c>tna.prepare</c> boundary.
/// Boundary sag is stored as rise/span, not as the percentage shown on canvas.
/// </summary>
public sealed record TnaPrepareConfigDto
{
    public double ForceDensity { get; init; } = 1.0;

    public bool Relax { get; init; } = true;

    public double? BoundarySag { get; init; } = 0.10;

    public int SagIterations { get; init; } = 10;

    public double SagTolerance { get; init; } = 0.01;

    public IReadOnlyList<int> FixedNodeIds { get; init; } =
        Array.Empty<int>();

    public IReadOnlyDictionary<string, string> Metadata { get; init; } =
        ContractData.EmptyStrings;

    internal void Validate(
        int vertexCount,
        string label,
        List<string> errors)
    {
        if (!ContractRules.IsFinite(ForceDensity) || ForceDensity <= 0.0)
            errors.Add($"{label}.forceDensity must be greater than zero.");
        if (BoundarySag is double sag &&
            (!ContractRules.IsFinite(sag) || sag <= 0.0 || sag > 1.0))
        {
            errors.Add(
                $"{label}.boundarySag must be a rise/span ratio greater " +
                "than zero and no greater than one.");
        }
        if (SagIterations < 0)
            errors.Add($"{label}.sagIterations cannot be negative.");
        if (!ContractRules.IsFinite(SagTolerance) || SagTolerance <= 0.0)
            errors.Add($"{label}.sagTolerance must be greater than zero.");
        if (FixedNodeIds is null)
        {
            errors.Add($"{label}.fixedNodeIds is missing.");
        }
        else
        {
            if (FixedNodeIds.Distinct().Count() != FixedNodeIds.Count)
                errors.Add($"{label}.fixedNodeIds contains duplicates.");
            if (FixedNodeIds.Any(id => id < 0 || id >= vertexCount))
                errors.Add($"{label}.fixedNodeIds contains an invalid node ID.");
        }
        ContractRules.ValidateStringMap(
            Metadata,
            $"{label}.metadata",
            errors);
    }
}

/// <summary>
/// Relaxed plan geometry returned by the worker. Vertices retain the original
/// topology node IDs, but edges/faces describe the faced, active TNA pattern.
/// </summary>
public sealed record TnaPreparedPatternDto
{
    public string PatternKind { get; init; } = "faced";

    public IReadOnlyList<Point3Dto> Vertices { get; init; } =
        Array.Empty<Point3Dto>();

    public IReadOnlyList<EdgeDto> Edges { get; init; } =
        Array.Empty<EdgeDto>();

    public IReadOnlyList<IReadOnlyList<int>> Faces { get; init; } =
        Array.Empty<IReadOnlyList<int>>();

    public IReadOnlyList<double> EdgeForceDensities { get; init; } =
        Array.Empty<double>();

    public IReadOnlyList<int> FixedNodeIds { get; init; } =
        Array.Empty<int>();

    internal void Validate(
        int stableVertexCount,
        string label,
        List<string> errors)
    {
        if (!string.Equals(
                PatternKind,
                "faced",
                StringComparison.OrdinalIgnoreCase))
        {
            errors.Add($"{label}.patternKind must be 'faced'.");
        }
        if (Vertices is null ||
            Vertices.Count == 0 ||
            Vertices.Count != stableVertexCount)
        {
            errors.Add(
                $"{label}.vertices must align one-to-one with the stable " +
                "source topology.");
        }
        else
        {
            for (int index = 0; index < Vertices.Count; index++)
            {
                ContractRules.ValidatePoint(
                    Vertices[index],
                    $"{label}.vertices[{index}]",
                    errors);
            }
        }

        int vertexCount = Vertices?.Count ?? 0;
        if (Edges is null || Edges.Count == 0)
        {
            errors.Add($"{label}.edges must not be empty.");
        }
        else
        {
            var seen = new HashSet<(int, int)>();
            for (int index = 0; index < Edges.Count; index++)
            {
                EdgeDto? edge = Edges[index];
                if (edge is null ||
                    edge.U == edge.V ||
                    edge.U < 0 ||
                    edge.V < 0 ||
                    edge.U >= vertexCount ||
                    edge.V >= vertexCount)
                {
                    errors.Add($"{label}.edges[{index}] is invalid.");
                    continue;
                }
                (int, int) key = edge.U < edge.V
                    ? (edge.U, edge.V)
                    : (edge.V, edge.U);
                if (!seen.Add(key))
                    errors.Add($"{label}.edges[{index}] is duplicated.");
            }
        }

        if (Faces is null || Faces.Count == 0)
        {
            errors.Add($"{label}.faces must not be empty.");
        }
        else
        {
            for (int index = 0; index < Faces.Count; index++)
            {
                IReadOnlyList<int>? face = Faces[index];
                if (face is null ||
                    face.Distinct().Count() < 3 ||
                    face.Any(id => id < 0 || id >= vertexCount))
                {
                    errors.Add($"{label}.faces[{index}] is invalid.");
                }
            }
        }

        if (EdgeForceDensities is null ||
            EdgeForceDensities.Count != (Edges?.Count ?? 0))
        {
            errors.Add(
                $"{label}.edgeForceDensities must align with every edge.");
        }
        else if (EdgeForceDensities.Any(
                     value => !ContractRules.IsFinite(value)))
        {
            errors.Add(
                $"{label}.edgeForceDensities contains a non-finite value.");
        }

        if (FixedNodeIds is null)
        {
            errors.Add($"{label}.fixedNodeIds is missing.");
        }
        else if (
            FixedNodeIds.Distinct().Count() != FixedNodeIds.Count ||
            FixedNodeIds.Any(id => id < 0 || id >= vertexCount))
        {
            errors.Add($"{label}.fixedNodeIds is invalid.");
        }
    }
}

public sealed record TnaBoundarySegmentDto
{
    public int BoundaryIndex { get; init; }

    public int SegmentIndex { get; init; }

    public IReadOnlyList<int> NodeIds { get; init; } =
        Array.Empty<int>();

    public IReadOnlyList<JsonElement> SourceVertexIds { get; init; } =
        Array.Empty<JsonElement>();

    public double? TargetSag { get; init; }

    public double InitialSag { get; init; }

    public double ActualSag { get; init; }

    public double SagError { get; init; }

    internal void Validate(
        int vertexCount,
        string label,
        List<string> errors)
    {
        if (BoundaryIndex < 0 || SegmentIndex < 0)
            errors.Add($"{label} has a negative boundary/segment index.");
        if (NodeIds is null ||
            NodeIds.Count < 2 ||
            NodeIds.Any(id => id < 0 || id >= vertexCount))
        {
            errors.Add($"{label}.nodeIds is invalid.");
        }
        if (SourceVertexIds is null)
            errors.Add($"{label}.sourceVertexIds is missing.");
        else if (
            NodeIds is not null &&
            SourceVertexIds.Count != NodeIds.Count)
        {
            errors.Add($"{label}.sourceVertexIds must align with nodeIds.");
        }
        if (TargetSag is double target &&
            (!ContractRules.IsFinite(target) || target < 0.0))
        {
            errors.Add($"{label}.targetSag is invalid.");
        }
        if (!ContractRules.IsFinite(InitialSag) ||
            InitialSag < 0.0 ||
            !ContractRules.IsFinite(ActualSag) ||
            ActualSag < 0.0 ||
            !ContractRules.IsFinite(SagError) ||
            SagError < 0.0)
        {
            errors.Add($"{label} contains an invalid sag measurement.");
        }
    }
}

/// <summary>
/// Stable, inspectable correspondence for the prepared plan state.
/// </summary>
public sealed record TnaPreparedMappingsDto
{
    public IReadOnlyList<int> PatternVertexToTopologyVertex { get; init; } =
        Array.Empty<int>();

    public IReadOnlyList<TnaBackendSourceMappingDto>
        BackendSourceToTopologyVertex { get; init; } =
        Array.Empty<TnaBackendSourceMappingDto>();

    public IReadOnlyList<TnaSourcePatternEdgeMappingDto>
        SourceEdgeToPatternEdge { get; init; } =
        Array.Empty<TnaSourcePatternEdgeMappingDto>();

    public IReadOnlyList<int> SupportNodeIds { get; init; } =
        Array.Empty<int>();

    public IReadOnlyList<int> FixedPlanNodeIds { get; init; } =
        Array.Empty<int>();

    public IReadOnlyList<TnaEdgeMappingDto> FormEdgeToForceEdge { get; init; } =
        Array.Empty<TnaEdgeMappingDto>();

    internal void Validate(
        int vertexCount,
        TnaPreparedPatternDto pattern,
        TnaDiagramGraphDto form,
        TnaDiagramGraphDto force,
        string label,
        List<string> errors)
    {
        if (PatternVertexToTopologyVertex is null ||
            PatternVertexToTopologyVertex.Count != vertexCount ||
            !PatternVertexToTopologyVertex.SequenceEqual(
                Enumerable.Range(0, vertexCount)))
        {
            errors.Add(
                $"{label}.patternVertexToTopologyVertex must preserve " +
                "the stable 0-based source node IDs.");
        }
        if (BackendSourceToTopologyVertex is null ||
            BackendSourceToTopologyVertex.Count != vertexCount ||
            !BackendSourceToTopologyVertex
                .Select(item => item.TopologyVertexId)
                .OrderBy(id => id)
                .SequenceEqual(Enumerable.Range(0, vertexCount)))
        {
            errors.Add(
                $"{label}.backendSourceToTopologyVertex must cover every " +
                "stable source node exactly once.");
        }
        if (SourceEdgeToPatternEdge is null ||
            SourceEdgeToPatternEdge.Count != pattern.Edges.Count)
        {
            errors.Add(
                $"{label}.sourceEdgeToPatternEdge must align with every " +
                "prepared Pattern edge.");
        }
        else
        {
            for (int index = 0;
                 index < SourceEdgeToPatternEdge.Count;
                 index++)
            {
                TnaSourcePatternEdgeMappingDto item =
                    SourceEdgeToPatternEdge[index];
                EdgeDto edge = pattern.Edges[index];
                if (item.SourceEdgeId != index ||
                    item.PatternEdgeId != index ||
                    item.U != edge.U ||
                    item.V != edge.V)
                {
                    errors.Add(
                        $"{label}.sourceEdgeToPatternEdge[{index}] does " +
                        "not preserve the stable source edge.");
                }
            }
        }
        ValidateIds(SupportNodeIds, vertexCount, $"{label}.supportNodeIds", errors);
        ValidateIds(
            FixedPlanNodeIds,
            vertexCount,
            $"{label}.fixedPlanNodeIds",
            errors);

        HashSet<int> formEdges =
            form.Edges.Select(edge => edge.Id).ToHashSet();
        HashSet<int> forceEdges =
            force.Edges.Select(edge => edge.Id).ToHashSet();
        if (FormEdgeToForceEdge is null ||
            FormEdgeToForceEdge.Count != formEdges.Count ||
            !FormEdgeToForceEdge
                .Select(item => item.FormEdgeId)
                .ToHashSet()
                .SetEquals(formEdges) ||
            !FormEdgeToForceEdge
                .Select(item => item.TargetEdgeId)
                .ToHashSet()
                .SetEquals(forceEdges) ||
            FormEdgeToForceEdge
                .Select(item => item.FormEdgeId)
                .Distinct()
                .Count() != FormEdgeToForceEdge.Count ||
            FormEdgeToForceEdge
                .Select(item => item.TargetEdgeId)
                .Distinct()
                .Count() != FormEdgeToForceEdge.Count)
        {
            errors.Add(
                $"{label}.formEdgeToForceEdge must be a one-to-one mapping " +
                "covering every prepared form and topological-dual edge.");
        }
    }

    private static void ValidateIds(
        IReadOnlyList<int>? values,
        int vertexCount,
        string label,
        List<string> errors)
    {
        if (values is null ||
            values.Distinct().Count() != values.Count ||
            values.Any(id => id < 0 || id >= vertexCount))
        {
            errors.Add($"{label} is invalid.");
        }
    }
}

public sealed record TnaBackendSourceMappingDto
{
    public JsonElement SourceKey { get; init; }

    public int TopologyVertexId { get; init; }
}

public sealed record TnaSourcePatternEdgeMappingDto
{
    public int SourceEdgeId { get; init; }

    public int PatternEdgeId { get; init; }

    public int U { get; init; }

    public int V { get; init; }
}

/// <summary>
/// Prepared, unsolved TNA state. The force graph here is the topological dual;
/// it deliberately carries no member-force or equilibrium claims.
/// </summary>
public sealed record TnaPreparedDto : ContractDto
{
    public TnaPreparedDto()
        : base(TnaWorkflowContractKinds.Prepared)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => TnaWorkflowContractKinds.Prepared;

    public TnaPatternDto? Source { get; init; }

    /// <summary>
    /// Python worker fingerprint of the unchanged source topology. The native
    /// topology retains its own stricter v0.2 fingerprint; both are kept
    /// explicit because their canonical hash inputs differ.
    /// </summary>
    public string WorkerTopologyHash { get; init; } = string.Empty;

    public SupportSetDto? SupportSet { get; init; }

    public TnaPrepareConfigDto Config { get; init; } = new();

    public TnaPreparedPatternDto Pattern { get; init; } = new();

    public TnaDiagramGraphDto FormGraph { get; init; } = new();

    public TnaDiagramGraphDto ForceGraph { get; init; } = new();

    public IReadOnlyList<TnaBoundarySegmentDto> BoundarySegments { get; init; } =
        Array.Empty<TnaBoundarySegmentDto>();

    public TnaPreparedMappingsDto Mappings { get; init; } = new();

    public IReadOnlyList<DiagnosticDto> Diagnostics { get; init; } =
        Array.Empty<DiagnosticDto>();

    public string Report { get; init; } = string.Empty;

    public IReadOnlyDictionary<string, string> WorkerMetadata { get; init; } =
        ContractData.EmptyStrings;

    protected override void ValidatePayload(List<string> errors)
    {
        if (Source is null)
        {
            errors.Add("source is missing.");
            return;
        }

        ContractRules.AddNested(errors, "source", Source.Validate());
        TopologyDto? topology = Source.Topology;
        int vertexCount = topology?.Vertices.Count ?? 0;
        ContractRules.ValidateTopologyHash(
            WorkerTopologyHash,
            "workerTopologyHash",
            errors);
        if (Source.Supports is null)
            errors.Add("source.supports is missing.");

        if (SupportSet is null)
        {
            errors.Add("supportSet is missing.");
        }
        else
        {
            ContractRules.AddNested(
                errors,
                "supportSet",
                SupportSet.Validate());
            if (topology is not null &&
                !string.Equals(
                    SupportSet.TopologyHash,
                    topology.TopologyHash,
                    StringComparison.OrdinalIgnoreCase))
            {
                errors.Add("supportSet belongs to a different source topology.");
            }
            if (Source.Supports is not null &&
                !SupportSet.NodeIds.SequenceEqual(Source.Supports.NodeIds))
            {
                errors.Add(
                    "supportSet does not preserve the selected source node IDs.");
            }
        }

        if (Config is null)
            errors.Add("config is missing.");
        else
            Config.Validate(vertexCount, "config", errors);
        if (Pattern is null)
            errors.Add("pattern is missing.");
        else
            Pattern.Validate(vertexCount, "pattern", errors);
        TnaContractRules.ValidateGraph(FormGraph, "formGraph", errors);
        TnaContractRules.ValidateGraph(ForceGraph, "forceGraph", errors);

        if (BoundarySegments is null)
        {
            errors.Add("boundarySegments is missing.");
        }
        else
        {
            for (int index = 0; index < BoundarySegments.Count; index++)
            {
                BoundarySegments[index]?.Validate(
                    vertexCount,
                    $"boundarySegments[{index}]",
                    errors);
            }
        }

        if (Mappings is null)
        {
            errors.Add("mappings is missing.");
        }
        else if (Pattern is not null)
        {
            Mappings.Validate(
                vertexCount,
                Pattern,
                FormGraph,
                ForceGraph,
                "mappings",
                errors);
        }
        if (Mappings is not null &&
            SupportSet is not null &&
            !Mappings.SupportNodeIds.SequenceEqual(SupportSet.NodeIds))
        {
            errors.Add(
                "mappings.supportNodeIds does not match supportSet.nodeIds.");
        }

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

        ContractRules.ValidateStringMap(
            WorkerMetadata,
            "workerMetadata",
            errors);
    }
}

public sealed class TnaPatternGoo : ContractGoo<TnaPatternDto>
{
    public TnaPatternGoo()
    {
    }

    public TnaPatternGoo(TnaPatternDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => TnaWorkflowContractKinds.Pattern;
    public override string TypeName => "Ananke TNA Pattern";
    public override string TypeDescription =>
        "A stable source pattern with optional explicit TNA supports.";

    protected override ContractGoo<TnaPatternDto> Create(TnaPatternDto? value) =>
        value is null ? new TnaPatternGoo() : new TnaPatternGoo(value);

    protected override string Format(TnaPatternDto value)
    {
        TopologyDto? topology = value.Topology;
        int supports = value.Supports?.NodeIds.Count ?? 0;
        return topology is null
            ? "TNA Pattern - incomplete"
            : $"TNA Pattern - {value.PatternMode} - " +
              $"{topology.Vertices.Count}V/{topology.Edges.Count}E - " +
              $"{supports} support(s)";
    }
}

public sealed class TnaPreparedGoo : ContractGoo<TnaPreparedDto>
{
    public TnaPreparedGoo()
    {
    }

    public TnaPreparedGoo(TnaPreparedDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => TnaWorkflowContractKinds.Prepared;
    public override string TypeName => "Ananke Prepared TNA";
    public override string TypeDescription =>
        "Relaxed TNA plan geometry with its unsolved topological force dual.";

    protected override ContractGoo<TnaPreparedDto> Create(
        TnaPreparedDto? value) =>
        value is null ? new TnaPreparedGoo() : new TnaPreparedGoo(value);

    protected override string Format(TnaPreparedDto value) =>
        $"Prepared TNA - {value.Pattern.Edges.Count} edges - " +
        $"{value.BoundarySegments.Count} opening(s) - unsolved";
}

public sealed class TnaPatternParam : ContractParam<TnaPatternGoo>
{
    public TnaPatternParam()
        : base(
            "Ananke TNA Pattern",
            "TNA Pattern",
            "Stable source topology and explicit supports for staged TNA.")
    {
    }

    public override Guid ComponentGuid =>
        new("35f566ce-b771-4707-bee9-5bc6b02c52c8");
}

public sealed class TnaPreparedParam : ContractParam<TnaPreparedGoo>
{
    public TnaPreparedParam()
        : base(
            "Ananke Prepared TNA",
            "Prepared",
            "Relaxed TNA plan geometry and its unsolved topological dual.")
    {
    }

    public override Guid ComponentGuid =>
        new("8ee5f13a-5584-4192-9bad-22fe00d05b64");
}
