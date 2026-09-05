#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Serialization;

namespace Ananke.COMPAS.Native.Contracts;

public sealed record Point3Dto(double X, double Y, double Z);

public sealed record EdgeDto(int U, int V);

public sealed record NodalVectorDto(
    int NodeId,
    Point3Dto Point,
    Point3Dto Vector);

public sealed record TopologyDto : ContractDto
{
    public TopologyDto()
        : base(ContractKinds.Topology)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.Topology;

    public string NetworkKind { get; init; } = "line";

    public IReadOnlyList<Point3Dto> Vertices { get; init; } =
        Array.Empty<Point3Dto>();

    public IReadOnlyList<EdgeDto> Edges { get; init; } =
        Array.Empty<EdgeDto>();

    public IReadOnlyList<IReadOnlyList<int>> Faces { get; init; } =
        Array.Empty<IReadOnlyList<int>>();

    public IReadOnlyList<string> SourceVertexIds { get; init; } =
        Array.Empty<string>();

    public IReadOnlyList<string> SourceEdgeIds { get; init; } =
        Array.Empty<string>();

    public string LengthUnit { get; init; } = "m";

    /// <summary>
    /// Runs of vertex indices marking the principal lines: the notched bars a
    /// reconfigurable mould holds rigid, ordered along each bar.
    ///
    /// They are resolved HERE, on the pattern, because this is the one place
    /// where the curves an author draws and the geometry they are drawn on
    /// still agree. Downstream the surface rises and the curves do not follow
    /// it, so a curve can no longer find its own nodes; indices survive that,
    /// curves do not. Every consumer therefore reads runs and never snaps.
    ///
    /// Purely an annotation: the solvers pass it through untouched and it is
    /// deliberately NOT part of the topology fingerprint, since marking which
    /// vertices form a bar does not make it a different topology.
    /// </summary>
    public IReadOnlyList<IReadOnlyList<int>> PrincipalRuns { get; init; } =
        Array.Empty<IReadOnlyList<int>>();

    public string TopologyHash { get; init; } = string.Empty;

    public static TopologyDto Create(
        string networkKind,
        IEnumerable<Point3Dto> vertices,
        IEnumerable<EdgeDto> edges,
        IEnumerable<IEnumerable<int>>? faces = null,
        IEnumerable<string>? sourceVertexIds = null,
        IEnumerable<string>? sourceEdgeIds = null,
        string lengthUnit = "m",
        IReadOnlyDictionary<string, string>? provenance = null,
        IEnumerable<IEnumerable<int>>? principalRuns = null)
    {
        ArgumentNullException.ThrowIfNull(vertices);
        ArgumentNullException.ThrowIfNull(edges);

        var draft = new TopologyDto
        {
            NetworkKind = networkKind,
            Vertices = vertices.ToArray(),
            Edges = edges.ToArray(),
            Faces = (faces ?? Array.Empty<IEnumerable<int>>())
                .Select(face => (IReadOnlyList<int>)face.ToArray())
                .ToArray(),
            SourceVertexIds = (sourceVertexIds ?? Array.Empty<string>()).ToArray(),
            SourceEdgeIds = (sourceEdgeIds ?? Array.Empty<string>()).ToArray(),
            LengthUnit = lengthUnit,
            PrincipalRuns = (principalRuns ?? Array.Empty<IEnumerable<int>>())
                .Select(run => (IReadOnlyList<int>)run.ToArray())
                .Where(run => run.Count >= 2)
                .ToArray(),
            Provenance = ContractData.FreezeStrings(provenance)
        };
        return draft with { TopologyHash = TopologyFingerprint.Compute(draft) };
    }

    protected override void ValidatePayload(List<string> errors)
    {
        string networkKind = (NetworkKind ?? string.Empty).Trim().ToLowerInvariant();
        if (networkKind is not ("line" or "faced"))
            errors.Add("networkKind must be 'line' or 'faced'.");

        int runVertexCount = Vertices?.Count ?? 0;
        for (int run = 0; run < PrincipalRuns.Count; run++)
        {
            IReadOnlyList<int> indices = PrincipalRuns[run];
            if (indices is null || indices.Count < 2)
            {
                errors.Add(
                    $"principalRuns[{run}] must name at least two vertices.");
                continue;
            }
            for (int step = 0; step < indices.Count; step++)
            {
                if (indices[step] < 0 || indices[step] >= runVertexCount)
                {
                    errors.Add(
                        $"principalRuns[{run}][{step}] is not a vertex index.");
                }
            }
        }

        if (Vertices is null || Vertices.Count == 0)
        {
            errors.Add("vertices must contain at least one point.");
        }
        else
        {
            for (int index = 0; index < Vertices.Count; index++)
                ContractRules.ValidatePoint(Vertices[index], $"vertices[{index}]", errors);
        }

        int vertexCount = Vertices?.Count ?? 0;
        if (Edges is null || Edges.Count == 0)
        {
            errors.Add("edges must contain at least one member.");
        }
        else
        {
            var seen = new HashSet<(int, int)>();
            for (int index = 0; index < Edges.Count; index++)
            {
                EdgeDto? edge = Edges[index];
                if (edge is null)
                {
                    errors.Add($"edges[{index}] is missing.");
                    continue;
                }

                if (edge.U == edge.V)
                    errors.Add($"edges[{index}] is collapsed.");
                if (edge.U < 0 || edge.V < 0 ||
                    edge.U >= vertexCount || edge.V >= vertexCount)
                {
                    errors.Add($"edges[{index}] contains an invalid vertex ID.");
                }

                (int, int) key = edge.U < edge.V
                    ? (edge.U, edge.V)
                    : (edge.V, edge.U);
                if (!seen.Add(key))
                    errors.Add($"edges[{index}] duplicates an existing member.");
            }

            int[] encounterOrder = Edges
                .Where(edge => edge is not null)
                .SelectMany(edge => new[] { edge.U, edge.V })
                .Distinct()
                .ToArray();
            if (!encounterOrder.SequenceEqual(
                    Enumerable.Range(0, vertexCount)))
            {
                errors.Add(
                    "vertices must be indexed in first edge-endpoint encounter " +
                    "order and every vertex must participate in an edge.");
            }
        }

        if (Faces is null)
        {
            errors.Add("faces is missing.");
        }
        else
        {
            for (int index = 0; index < Faces.Count; index++)
            {
                IReadOnlyList<int>? face = Faces[index];
                if (face is null || face.Distinct().Count() < 3)
                {
                    errors.Add($"faces[{index}] needs at least three distinct vertices.");
                    continue;
                }

                if (face.Any(nodeId => nodeId < 0 || nodeId >= vertexCount))
                    errors.Add($"faces[{index}] contains an invalid vertex ID.");
            }
        }

        if (networkKind == "faced" && (Faces is null || Faces.Count == 0))
            errors.Add("A faced topology requires at least one face.");

        if (SourceVertexIds is null)
        {
            errors.Add("sourceVertexIds is missing.");
        }
        else if (SourceVertexIds.Count != 0 && SourceVertexIds.Count != vertexCount)
        {
            errors.Add("sourceVertexIds must be empty or align with every vertex.");
        }
        else if (SourceVertexIds.Any(string.IsNullOrWhiteSpace))
        {
            errors.Add("sourceVertexIds cannot contain empty values.");
        }

        if (SourceEdgeIds is null)
        {
            errors.Add("sourceEdgeIds is missing.");
        }
        else if (SourceEdgeIds.Count != 0 &&
                 SourceEdgeIds.Count != (Edges?.Count ?? 0))
        {
            errors.Add("sourceEdgeIds must be empty or align with every edge.");
        }
        else if (SourceEdgeIds.Any(string.IsNullOrWhiteSpace))
        {
            errors.Add("sourceEdgeIds cannot contain empty values.");
        }

        if (string.IsNullOrWhiteSpace(LengthUnit))
            errors.Add("lengthUnit cannot be empty.");

        ContractRules.ValidateTopologyHash(TopologyHash, "topologyHash", errors);
        if (errors.Count == 0)
        {
            string computed = TopologyFingerprint.Compute(this);
            if (!string.Equals(TopologyHash, computed, StringComparison.OrdinalIgnoreCase))
                errors.Add("topologyHash does not match the topology payload.");
        }
    }
}

public sealed record SupportSetDto : ContractDto
{
    public SupportSetDto()
        : base(ContractKinds.SupportSet)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.SupportSet;

    public string TopologyHash { get; init; } = string.Empty;

    public string Mode { get; init; } = "explicit";

    public IReadOnlyList<Point3Dto> Points { get; init; } =
        Array.Empty<Point3Dto>();

    public IReadOnlyList<int> NodeIds { get; init; } =
        Array.Empty<int>();

    public double? SnapTolerance { get; init; }

    protected override void ValidatePayload(List<string> errors)
    {
        ContractRules.ValidateTopologyHash(TopologyHash, "topologyHash", errors);

        string mode = (Mode ?? string.Empty).Trim().ToLowerInvariant();
        if (mode is not ("explicit" or "terminals" or "boundary"))
        {
            errors.Add(
                "mode must be explicit, terminals, or boundary.");
        }

        if (Points is null)
        {
            errors.Add("points is missing.");
        }
        else
        {
            for (int index = 0; index < Points.Count; index++)
                ContractRules.ValidatePoint(Points[index], $"points[{index}]", errors);
            if (Points.Count > 0)
            {
                errors.Add(
                    "v0.2 support point targets must be resolved to nodeIds " +
                    "by the native Support Set component.");
            }
        }

        if (NodeIds is null)
        {
            errors.Add("nodeIds is missing.");
        }
        else
        {
            if (NodeIds.Any(nodeId => nodeId < 0))
                errors.Add("nodeIds cannot contain negative values.");
            if (NodeIds.Distinct().Count() != NodeIds.Count)
                errors.Add("nodeIds contains duplicates.");
        }

        if (mode == "explicit" &&
            (NodeIds is null || NodeIds.Count == 0))
        {
            errors.Add("Explicit supports require resolved nodeIds.");
        }
        if ((mode is "terminals" or "boundary") &&
            NodeIds is not null &&
            NodeIds.Count > 0)
        {
            errors.Add(
                $"{mode} support mode selects nodes automatically; " +
                "nodeIds must be empty.");
        }

        if (SnapTolerance is double tolerance &&
            (!ContractRules.IsFinite(tolerance) || tolerance <= 0.0))
        {
            errors.Add("snapTolerance must be finite and greater than zero.");
        }
    }
}

public sealed record LoadCaseDto : ContractDto
{
    public LoadCaseDto()
        : base(ContractKinds.LoadCase)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.LoadCase;

    public string TopologyHash { get; init; } = string.Empty;

    public string Name { get; init; } = "equilibrium";

    public string Distribution { get; init; } = "point";

    public IReadOnlyList<Point3Dto> Points { get; init; } =
        Array.Empty<Point3Dto>();

    public IReadOnlyList<int> NodeIds { get; init; } =
        Array.Empty<int>();

    public IReadOnlyList<Point3Dto> Vectors { get; init; } =
        Array.Empty<Point3Dto>();

    public Point3Dto? BaseVector { get; init; }

    /// <summary>
    /// RhinoVault's selfweight pair, adopted by rule 2.4(a) of the
    /// 2026-09-04 design: a self-weight weighs tributary area times
    /// THICKNESS times DENSITY. Both default to 1.0, which is what a
    /// definition saved before the Loads component grew the two ports
    /// sends, and area x baseVector.z x 1 x 1 is the weight that
    /// definition always had.
    /// </summary>
    public double Thickness { get; init; } = 1.0;

    /// <summary>
    /// The density is a MAGNITUDE. The base vector's Z carries the
    /// direction, so a negative density here would flip a vault's weight
    /// upward while every arrow on the canvas still pointed down.
    /// </summary>
    public double Density { get; init; } = 1.0;

    public double Factor { get; init; } = 1.0;

    public string CoordinateSystem { get; init; } = "world";

    protected override void ValidatePayload(List<string> errors)
    {
        ContractRules.ValidateTopologyHash(TopologyHash, "topologyHash", errors);
        if (string.IsNullOrWhiteSpace(Name))
            errors.Add("name cannot be empty.");

        string distribution = (Distribution ?? string.Empty)
            .Trim()
            .ToLowerInvariant()
            .Replace(' ', '_');
        string[] permitted =
        {
            "point",
            "uniform_nodes",
            "tributary_area",
            // Rule 2.4 of the 2026-09-04 design. This is the shape the
            // Loads component now authors for a surface load, and the
            // only distribution that may carry a baseVector and nodeIds
            // at once: the self-weight and the point loads that ride
            // beside it, RhinoVault's pz + pzext split. "tributary_area"
            // stays exactly as strict as it was, for anything that still
            // authors one.
            "self_weight",
            "custom"
        };
        if (!permitted.Contains(distribution, StringComparer.Ordinal))
            errors.Add($"Unsupported distribution '{Distribution}'.");

        if (Points is null)
        {
            errors.Add("points is missing.");
        }
        else
        {
            for (int index = 0; index < Points.Count; index++)
                ContractRules.ValidatePoint(Points[index], $"points[{index}]", errors);
            if (Points.Count > 0)
            {
                errors.Add(
                    "v0.2 load point targets must be resolved to nodeIds " +
                    "by the native Load Case component.");
            }
        }

        if (NodeIds is null)
        {
            errors.Add("nodeIds is missing.");
        }
        else if (NodeIds.Any(nodeId => nodeId < 0))
        {
            errors.Add("nodeIds cannot contain negative values.");
        }

        int nodeCount = NodeIds?.Count ?? 0;

        if (Vectors is null)
        {
            errors.Add("vectors is missing.");
        }
        else
        {
            for (int index = 0; index < Vectors.Count; index++)
                ContractRules.ValidatePoint(Vectors[index], $"vectors[{index}]", errors);
        }

        if (BaseVector is not null)
            ContractRules.ValidatePoint(BaseVector, "baseVector", errors);

        int vectorCount = Vectors?.Count ?? 0;
        if (distribution is "point" or "custom")
        {
            if (nodeCount == 0)
                errors.Add($"{distribution} loads require resolved nodeIds.");
            if (vectorCount != 1 && vectorCount != nodeCount)
                errors.Add("vectors must broadcast once or align with every target.");
            if (BaseVector is not null)
                errors.Add($"{distribution} loads cannot use baseVector.");
        }
        else if (distribution is "uniform_nodes" or "tributary_area")
        {
            if (nodeCount > 0)
                errors.Add($"{distribution} selects every node; nodeIds must be empty.");
            if (vectorCount > 0)
                errors.Add($"{distribution} requires baseVector, not vectors.");
            if (BaseVector is null)
                errors.Add($"{distribution} requires one baseVector.");
        }
        else if (distribution is "self_weight")
        {
            // The self-weight itself is the base vector, over every
            // node. Nodal targets are the OTHER half, the point loads
            // riding beside it, so they are allowed here and nowhere
            // else, and their vectors must still align with them.
            if (BaseVector is null)
                errors.Add("self_weight requires one baseVector.");
            if (nodeCount == 0 && vectorCount > 0)
            {
                errors.Add(
                    "self_weight vectors are the point loads beside the " +
                    "weight and need the nodeIds they act on.");
            }
            if (nodeCount > 0 && vectorCount != 1 && vectorCount != nodeCount)
                errors.Add("vectors must broadcast once or align with every target.");
        }

        if (!ContractRules.IsFinite(Thickness) || Thickness < 0.0)
            errors.Add("thickness must be finite and zero or greater.");
        if (!ContractRules.IsFinite(Density) || Density < 0.0)
        {
            errors.Add(
                "density must be finite and zero or greater; the base " +
                "vector's Z carries the direction.");
        }

        if (!ContractRules.IsFinite(Factor) || Factor != 1.0)
        {
            errors.Add(
                "v0.2 stores effective load vectors and requires factor=1; " +
                "apply any input multiplier before creating the contract.");
        }
        if (!string.Equals(
                CoordinateSystem,
                "world",
                StringComparison.OrdinalIgnoreCase))
        {
            errors.Add("v0.2 supports only the world coordinate system.");
        }
    }
}

public sealed record EquilibriumProblemDto : ContractDto
{
    public EquilibriumProblemDto()
        : base(ContractKinds.EquilibriumProblem)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.EquilibriumProblem;

    public string Name { get; init; } = "equilibrium";

    public TopologyDto? Topology { get; init; }

    public SupportSetDto? Supports { get; init; }

    public IReadOnlyList<LoadCaseDto> LoadCases { get; init; } =
        Array.Empty<LoadCaseDto>();

    [JsonIgnore]
    public string TopologyHash => Topology?.TopologyHash ?? string.Empty;

    protected override void ValidatePayload(List<string> errors)
    {
        if (string.IsNullOrWhiteSpace(Name))
            errors.Add("name cannot be empty.");

        if (Topology is null)
        {
            errors.Add("topology is missing.");
        }
        else
        {
            ContractRules.AddNested(errors, "topology", Topology.Validate());
        }

        if (Supports is null)
        {
            errors.Add("supports is missing.");
        }
        else
        {
            ContractRules.AddNested(errors, "supports", Supports.Validate());
            if (Topology is not null &&
                !string.Equals(
                    Supports.TopologyHash,
                    Topology.TopologyHash,
                    StringComparison.OrdinalIgnoreCase))
            {
                errors.Add("supports belongs to a different topology.");
            }
            if (Topology is not null &&
                Supports.NodeIds.Any(
                    nodeId => nodeId >= Topology.Vertices.Count))
            {
                errors.Add("supports contains a node ID outside topology.");
            }
        }

        if (LoadCases is null || LoadCases.Count == 0)
        {
            errors.Add("loadCases must contain at least one load case.");
        }
        else
        {
            for (int index = 0; index < LoadCases.Count; index++)
            {
                LoadCaseDto? loadCase = LoadCases[index];
                if (loadCase is null)
                {
                    errors.Add($"loadCases[{index}] is missing.");
                    continue;
                }

                ContractRules.AddNested(
                    errors,
                    $"loadCases[{index}]",
                    loadCase.Validate());
                if (Topology is not null &&
                    !string.Equals(
                        loadCase.TopologyHash,
                        Topology.TopologyHash,
                        StringComparison.OrdinalIgnoreCase))
                {
                    errors.Add($"loadCases[{index}] belongs to a different topology.");
                }
                if (Topology is not null &&
                    loadCase.NodeIds.Any(
                        nodeId => nodeId >= Topology.Vertices.Count))
                {
                    errors.Add(
                        $"loadCases[{index}] contains a node ID outside topology.");
                }
            }

            IEnumerable<string> duplicateNames = LoadCases
                .Where(item => item is not null)
                .GroupBy(item => item.Name, StringComparer.OrdinalIgnoreCase)
                .Where(group => group.Count() > 1)
                .Select(group => group.Key);
            foreach (string duplicateName in duplicateNames)
                errors.Add($"loadCases contains duplicate name '{duplicateName}'.");
        }
    }
}

public sealed record FDSettingsDto : ContractDto
{
    public FDSettingsDto()
        : base(ContractKinds.FDSettings)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.FDSettings;

    public IReadOnlyList<double> ForceDensities { get; init; } =
        new[] { 1.0 };

    public string SignConvention { get; init; } = "positive_tension";

    protected override void ValidatePayload(List<string> errors)
    {
        if (ForceDensities is null || ForceDensities.Count == 0)
        {
            errors.Add("forceDensities must contain a scalar or member values.");
        }
        else
        {
            for (int index = 0; index < ForceDensities.Count; index++)
            {
                double value = ForceDensities[index];
                if (!ContractRules.IsFinite(value) || Math.Abs(value) <= 1.0e-12)
                {
                    errors.Add(
                        $"forceDensities[{index}] must be finite with magnitude "
                        + "greater than 1e-12.");
                }
            }
        }

        string sign = (SignConvention ?? string.Empty).Trim().ToLowerInvariant();
        if (sign != "positive_tension")
            errors.Add("v0.2 requires COMPAS signConvention 'positive_tension'.");
    }
}

public sealed record DiagnosticDto : ContractDto
{
    public DiagnosticDto()
        : base(ContractKinds.Diagnostic)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.Diagnostic;

    public string Code { get; init; } = string.Empty;

    public string Severity { get; init; } = "info";

    public string Message { get; init; } = string.Empty;

    public double? Value { get; init; }

    public double? Tolerance { get; init; }

    public string Unit { get; init; } = string.Empty;

    public IReadOnlyDictionary<string, string> Context { get; init; } =
        ContractData.EmptyStrings;

    protected override void ValidatePayload(List<string> errors)
    {
        if (string.IsNullOrWhiteSpace(Code))
            errors.Add("code cannot be empty.");
        if (string.IsNullOrWhiteSpace(Message))
            errors.Add("message cannot be empty.");

        string severity = (Severity ?? string.Empty).Trim().ToLowerInvariant();
        if (severity is not ("ok" or "info" or "warning" or "error"))
            errors.Add("severity must be ok, info, warning, or error.");

        if (Value is double value && !ContractRules.IsFinite(value))
            errors.Add("value must be finite.");
        if (Tolerance is double tolerance &&
            (!ContractRules.IsFinite(tolerance) || tolerance < 0.0))
        {
            errors.Add("tolerance must be finite and non-negative.");
        }

        ContractRules.ValidateStringMap(Context, "context", errors);
    }
}

public sealed record EquilibriumResultDto : ContractDto
{
    public EquilibriumResultDto()
        : base(ContractKinds.EquilibriumResult)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.EquilibriumResult;

    public string Solver { get; init; } = string.Empty;

    public EquilibriumProblemDto? Problem { get; init; }

    public string TopologyHash { get; init; } = string.Empty;

    public IReadOnlyList<Point3Dto> Vertices { get; init; } =
        Array.Empty<Point3Dto>();

    public IReadOnlyList<EdgeDto> Edges { get; init; } =
        Array.Empty<EdgeDto>();

    public IReadOnlyList<double> MemberForces { get; init; } =
        Array.Empty<double>();

    public IReadOnlyList<double> ForceDensities { get; init; } =
        Array.Empty<double>();

    public IReadOnlyList<NodalVectorDto> Loads { get; init; } =
        Array.Empty<NodalVectorDto>();

    public IReadOnlyList<NodalVectorDto> Reactions { get; init; } =
        Array.Empty<NodalVectorDto>();

    public IReadOnlyList<NodalVectorDto> Residuals { get; init; } =
        Array.Empty<NodalVectorDto>();

    public IReadOnlyList<DiagnosticDto> Diagnostics { get; init; } =
        Array.Empty<DiagnosticDto>();

    public IReadOnlyList<string> MemberSourceIds { get; init; } =
        Array.Empty<string>();

    public IReadOnlyList<int> ResolvedSupportNodeIds { get; init; } =
        Array.Empty<int>();

    public string LengthUnit { get; init; } = "m";

    public string ForceUnit { get; init; } = "kN";

    public string SignConvention { get; init; } = "positive_tension";

    public IReadOnlyDictionary<string, string> SolverSettings { get; init; } =
        ContractData.EmptyStrings;

    public string Report { get; init; } = string.Empty;

    protected override void ValidatePayload(List<string> errors)
    {
        string solver = (Solver ?? string.Empty).Trim().ToLowerInvariant();
        if (solver is not ("fd" or "tna"))
            errors.Add("solver must be 'fd' or 'tna'.");

        if (Problem is null)
        {
            errors.Add("problem is missing.");
        }
        else
        {
            ContractRules.AddNested(errors, "problem", Problem.Validate());
        }

        ContractRules.ValidateTopologyHash(TopologyHash, "topologyHash", errors);
        if (Problem?.Topology is not null &&
            !string.Equals(
                TopologyHash,
                Problem.Topology.TopologyHash,
                StringComparison.OrdinalIgnoreCase))
        {
            errors.Add("topologyHash does not match problem.topology.");
        }

        if (Vertices is null || Vertices.Count == 0)
        {
            errors.Add("vertices must contain solved coordinates.");
        }
        else
        {
            for (int index = 0; index < Vertices.Count; index++)
                ContractRules.ValidatePoint(Vertices[index], $"vertices[{index}]", errors);
        }

        int vertexCount = Vertices?.Count ?? 0;
        if (Edges is null || Edges.Count == 0)
        {
            errors.Add("edges must contain solved members.");
        }
        else
        {
            for (int index = 0; index < Edges.Count; index++)
            {
                EdgeDto? edge = Edges[index];
                if (edge is null)
                {
                    errors.Add($"edges[{index}] is missing.");
                    continue;
                }
                if (edge.U == edge.V ||
                    edge.U < 0 || edge.V < 0 ||
                    edge.U >= vertexCount || edge.V >= vertexCount)
                {
                    errors.Add($"edges[{index}] is invalid.");
                }
            }
        }

        int edgeCount = Edges?.Count ?? 0;
        if (solver == "fd" &&
            Problem?.Topology is TopologyDto problemTopology)
        {
            bool edgesAlign =
                Edges is not null &&
                edgeCount == problemTopology.Edges.Count &&
                Edges.Zip(
                        problemTopology.Edges,
                        (actual, source) =>
                            actual.U == source.U &&
                            actual.V == source.V)
                    .All(value => value);
            if (!edgesAlign)
                errors.Add("FD result edges do not align with problem.topology.");
        }
        ValidateAlignedScalars(MemberForces, edgeCount, "memberForces", required: true, errors);
        ValidateAlignedScalars(ForceDensities, edgeCount, "forceDensities", required: false, errors);

        ValidateNodalVectors(Loads, vertexCount, "loads", errors);
        ValidateNodalVectors(Reactions, vertexCount, "reactions", errors);
        ValidateNodalVectors(Residuals, vertexCount, "residuals", errors);

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

        if (MemberSourceIds is null)
        {
            errors.Add("memberSourceIds is missing.");
        }
        else if (MemberSourceIds.Count != 0 && MemberSourceIds.Count != edgeCount)
        {
            errors.Add("memberSourceIds must be empty or align with every edge.");
        }
        else if (MemberSourceIds.Any(string.IsNullOrWhiteSpace))
        {
            errors.Add("memberSourceIds cannot contain empty values.");
        }
        else if (solver == "fd" &&
                 Problem?.Topology is TopologyDto sourceTopology &&
                 sourceTopology.SourceEdgeIds.Count > 0 &&
                 !MemberSourceIds.SequenceEqual(sourceTopology.SourceEdgeIds))
        {
            errors.Add(
                "memberSourceIds do not match problem.topology source edges.");
        }

        if (ResolvedSupportNodeIds is null)
        {
            errors.Add("resolvedSupportNodeIds is missing.");
        }
        else
        {
            if (solver == "fd" && ResolvedSupportNodeIds.Count == 0)
                errors.Add("FD results require resolved support node IDs.");
            if (ResolvedSupportNodeIds.Any(
                    nodeId => nodeId < 0 || nodeId >= vertexCount))
            {
                errors.Add(
                    "resolvedSupportNodeIds contains a node ID outside vertices.");
            }
            if (ResolvedSupportNodeIds.Distinct().Count() !=
                ResolvedSupportNodeIds.Count)
            {
                errors.Add("resolvedSupportNodeIds contains duplicates.");
            }

            if (solver == "fd" &&
                Problem?.Supports is SupportSetDto problemSupports &&
                string.Equals(
                    problemSupports.Mode,
                    "explicit",
                    StringComparison.OrdinalIgnoreCase) &&
                problemSupports.NodeIds is IReadOnlyList<int> explicitNodeIds &&
                !ResolvedSupportNodeIds
                    .OrderBy(nodeId => nodeId)
                    .SequenceEqual(
                        explicitNodeIds.OrderBy(nodeId => nodeId)))
            {
                errors.Add(
                    "resolvedSupportNodeIds do not match explicit problem supports.");
            }
        }

        if (string.IsNullOrWhiteSpace(LengthUnit))
            errors.Add("lengthUnit cannot be empty.");
        if (string.IsNullOrWhiteSpace(ForceUnit))
            errors.Add("forceUnit cannot be empty.");

        string sign = (SignConvention ?? string.Empty).Trim().ToLowerInvariant();
        if (sign != "positive_tension")
            errors.Add("v0.2 requires COMPAS signConvention 'positive_tension'.");

        ContractRules.ValidateStringMap(SolverSettings, "solverSettings", errors);
    }

    private static void ValidateAlignedScalars(
        IReadOnlyList<double>? values,
        int expectedCount,
        string label,
        bool required,
        List<string> errors)
    {
        if (values is null)
        {
            errors.Add($"{label} is missing.");
            return;
        }

        if ((required || values.Count > 0) && values.Count != expectedCount)
            errors.Add($"{label} must align with every edge.");
        if (values.Any(value => !ContractRules.IsFinite(value)))
            errors.Add($"{label} contains a non-finite value.");
    }

    private static void ValidateNodalVectors(
        IReadOnlyList<NodalVectorDto>? values,
        int vertexCount,
        string label,
        List<string> errors)
    {
        if (values is null)
        {
            errors.Add($"{label} is missing.");
            return;
        }

        for (int index = 0; index < values.Count; index++)
        {
            NodalVectorDto? item = values[index];
            if (item is null)
            {
                errors.Add($"{label}[{index}] is missing.");
                continue;
            }

            if (item.NodeId < 0 || item.NodeId >= vertexCount)
                errors.Add($"{label}[{index}] has an invalid node ID.");
            ContractRules.ValidatePoint(item.Point, $"{label}[{index}].point", errors);
            ContractRules.ValidatePoint(item.Vector, $"{label}[{index}].vector", errors);
        }
    }
}
