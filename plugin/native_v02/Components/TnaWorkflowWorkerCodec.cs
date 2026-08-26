#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using Ananke.COMPAS.Native.Backend;
using Ananke.COMPAS.Native.Contracts;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Explicit snake_case boundary for the stateless staged TNA worker commands.
/// A prepared response is decoded into a native v0.2 document contract and
/// can later be reconstructed without retaining a live Python object.
/// </summary>
internal static class TnaWorkflowWorkerCodec
{
    public static IReadOnlyDictionary<string, object?> PreparePayload(
        TnaPatternDto pattern,
        TnaPrepareConfigDto config)
    {
        EnsureValid(pattern);
        if (pattern.Topology is not TopologyDto topology ||
            pattern.Supports is not SupportSetDto supports)
        {
            throw new InvalidOperationException(
                "TNA Relax + Boundaries requires a Pattern with explicit " +
                "supports from TNA Supports.");
        }

        var configErrors = new List<string>();
        config.Validate(topology.Vertices.Count, "config", configErrors);
        if (configErrors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", configErrors));

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["topology"] = topology.ToWorkerPayload(),
            ["supports"] = supports.ToWorkerPayload(),
            ["settings"] = PrepareConfigPayload(config)
        };
    }

    public static TnaPreparedDto DecodePrepared(
        JsonElement root,
        TnaPatternDto source)
    {
        RequireObject(root, "TNA prepared result");
        RequireWorkerSchema(root, "TNA prepared result");
        string kind = RequiredString(root, "kind");
        if (!string.Equals(kind, "tna_prepared", StringComparison.Ordinal))
        {
            throw new JsonException(
                $"Expected tna_prepared, received '{kind}'.");
        }
        if (source.Topology is not TopologyDto sourceTopology ||
            source.Supports is null)
        {
            throw new JsonException(
                "The source Pattern has no explicit topology/support state.");
        }

        JsonElement topologyJson = RequiredObject(root, "topology");
        string workerTopologyHash =
            VerifyUnchangedTopology(topologyJson, sourceTopology);
        SupportSetDto supports = DecodeSupportSet(
            RequiredObject(root, "support_set"),
            sourceTopology);
        TnaPrepareConfigDto config = DecodeConfig(
            RequiredObject(root, "config"));
        TnaPreparedPatternDto pattern = DecodePattern(
            RequiredObject(root, "pattern"));
        TnaDiagramGraphDto form = DecodeGraph(
            RequiredObject(root, "form_graph"),
            "form_graph");
        TnaDiagramGraphDto force = DecodeGraph(
            RequiredObject(root, "force_graph"),
            "force_graph");
        TnaBoundarySegmentDto[] boundaries =
            OptionalArray(root, "boundary_segments")
                .EnumerateArray()
                .Select((value, index) =>
                    DecodeBoundary(
                        value,
                        $"boundary_segments[{index}]"))
                .ToArray();
        TnaPreparedMappingsDto mappings = DecodePreparedMappings(
            RequiredObject(root, "mappings"));
        DiagnosticDto[] diagnostics = DecodeDiagnostics(root);

        var workerMetadata = new SortedDictionary<string, string>(
            StringComparer.Ordinal);
        AddJsonMap(workerMetadata, root, "metadata", "metadata.");
        AddJsonMap(
            workerMetadata,
            root,
            "diagnostic_metrics",
            "diagnostic_metrics.");
        AddJsonMap(workerMetadata, root, "provenance", "provenance.");

        var prepared = new TnaPreparedDto
        {
            Source = source,
            WorkerTopologyHash = workerTopologyHash,
            SupportSet = supports,
            Config = config,
            Pattern = pattern,
            FormGraph = form,
            ForceGraph = force,
            BoundarySegments = boundaries,
            Mappings = mappings,
            Diagnostics = diagnostics,
            Report = OptionalString(root, "report"),
            WorkerMetadata = workerMetadata,
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["source"] = "COMPAS tna.prepare worker",
                ["worker_topology_hash"] = workerTopologyHash
            }
        };
        EnsureValid(prepared);
        return prepared;
    }

    public static IReadOnlyDictionary<string, object?> StagedSolvePayload(
        TnaPreparedDto prepared,
        LoadCaseDto loadCase,
        TnaControlDto control)
    {
        EnsureValid(prepared);
        EnsureValid(loadCase);
        EnsureValid(control);
        TopologyDto sourceTopology = prepared.Source!.Topology!;
        if (!string.Equals(
                loadCase.TopologyHash,
                sourceTopology.TopologyHash,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                "Load Case belongs to a different source Pattern topology.");
        }

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["prepared"] = PreparedPayload(prepared),
            ["load_case"] = loadCase.ToWorkerPayload(),
            ["control"] = control.ToWorkerPayload()
        };
    }

    /// <summary>
    /// Build the native faced problem expected by the existing strict TNA
    /// result decoder. For line sources, the worker promotes the prepared
    /// pattern to a faced analysis topology in equilibrium.topology.
    /// </summary>
    public static EquilibriumProblemDto AnalysisProblem(
        JsonElement tnaResult,
        TnaPreparedDto prepared,
        LoadCaseDto sourceLoad)
    {
        JsonElement equilibrium = RequiredObject(tnaResult, "equilibrium");
        JsonElement topologyJson =
            RequiredObject(equilibrium, "topology");
        TopologyDto analysisTopology = DecodeAnalysisTopology(
            topologyJson,
            prepared);

        SupportSetDto sourceSupports = prepared.SupportSet!;
        var analysisSupports = sourceSupports with
        {
            TopologyHash = analysisTopology.TopologyHash,
            Provenance = Merge(
                sourceSupports.Provenance,
                "analysis_rebound",
                "true")
        };
        var analysisLoad = sourceLoad with
        {
            TopologyHash = analysisTopology.TopologyHash,
            Provenance = Merge(
                sourceLoad.Provenance,
                "analysis_rebound",
                "true")
        };
        var problem = new EquilibriumProblemDto
        {
            Name = "staged-tna-equilibrium",
            Topology = analysisTopology,
            Supports = analysisSupports,
            LoadCases = new[] { analysisLoad },
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["source"] = "TNA Equilibrium",
                ["source_topology_hash"] =
                    prepared.Source!.Topology!.TopologyHash,
                ["source_topology_kind"] =
                    prepared.Source.Topology.NetworkKind,
                ["worker_source_topology_hash"] =
                    prepared.WorkerTopologyHash
            }
        };
        EnsureValid(problem);
        return problem;
    }

    private static IReadOnlyDictionary<string, object?> PreparedPayload(
        TnaPreparedDto prepared)
    {
        TopologyDto topology = prepared.Source!.Topology!;
        var topologyPayload = new Dictionary<string, object?>(
            topology.ToWorkerPayload(),
            StringComparer.Ordinal)
        {
            ["schema_version"] = WorkerProtocol.CompatibleWorkerSchema,
            ["topology_hash"] = prepared.WorkerTopologyHash
        };
        var metadata = prepared.WorkerMetadata
            .Where(item => item.Key.StartsWith(
                "metadata.",
                StringComparison.Ordinal))
            .ToDictionary(
                item => item.Key["metadata.".Length..],
                item => (object?)item.Value,
                StringComparer.Ordinal);
        var provenance = prepared.WorkerMetadata
            .Where(item => item.Key.StartsWith(
                "provenance.",
                StringComparison.Ordinal))
            .ToDictionary(
                item => item.Key["provenance.".Length..],
                item => (object?)item.Value,
                StringComparer.Ordinal);
        provenance["native_reconstructed"] = true;

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema_version"] = WorkerProtocol.CompatibleWorkerSchema,
            ["kind"] = "tna_prepared",
            ["topology"] = topologyPayload,
            ["support_set"] = prepared.SupportSet!.ToWorkerPayload(),
            ["config"] = PrepareConfigPayload(prepared.Config),
            ["pattern"] = PatternPayload(prepared.Pattern),
            ["form_graph"] = GraphPayload(prepared.FormGraph, false),
            ["force_graph"] = GraphPayload(prepared.ForceGraph, true),
            ["boundary_segments"] = prepared.BoundarySegments
                .Select(BoundaryPayload)
                .ToArray(),
            ["diagnostics"] = prepared.Diagnostics
                .Select(DiagnosticPayload)
                .ToArray(),
            ["mappings"] = MappingsPayload(prepared.Mappings),
            ["report"] = prepared.Report,
            ["metadata"] = metadata,
            ["provenance"] = provenance
        };
    }

    private static IReadOnlyDictionary<string, object?> PrepareConfigPayload(
        TnaPrepareConfigDto config) =>
        new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["force_density"] = config.ForceDensity,
            ["relax"] = config.Relax,
            ["boundary_sag"] = config.BoundarySag,
            ["sag_iterations"] = config.SagIterations,
            ["sag_tolerance"] = config.SagTolerance,
            ["fixed_node_ids"] = config.FixedNodeIds.ToArray(),
            ["metadata"] = new Dictionary<string, string>(
                config.Metadata,
                StringComparer.Ordinal)
        };

    private static IReadOnlyDictionary<string, object?> PatternPayload(
        TnaPreparedPatternDto pattern) =>
        new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["kind"] = "faced",
            ["vertices"] = pattern.Vertices
                .Select(PointPayload)
                .ToArray(),
            ["edges"] = pattern.Edges
                .Select(edge => new[] { edge.U, edge.V })
                .ToArray(),
            ["faces"] = pattern.Faces
                .Select(face => face.ToArray())
                .ToArray(),
            ["edge_force_densities"] =
                pattern.EdgeForceDensities.ToArray(),
            ["fixed_node_ids"] = pattern.FixedNodeIds.ToArray()
        };

    private static IReadOnlyDictionary<string, object?> GraphPayload(
        TnaDiagramGraphDto graph,
        bool force)
    {
        object[] vertices = graph.Vertices
            .Select(vertex => (object)new Dictionary<string, object?>(
                StringComparer.Ordinal)
            {
                ["id"] = vertex.Id,
                ["key"] = JsonValue(vertex.Key),
                ["point"] = PointPayload(vertex.Point),
                ["source_vertex_ids"] = vertex.SourceVertexIds
                    .Select(JsonValue)
                    .ToArray()
            })
            .ToArray();
        object[] edges = graph.Edges
            .Select(edge =>
            {
                var item = new Dictionary<string, object?>(
                    StringComparer.Ordinal)
                {
                    ["id"] = edge.Id,
                    ["key"] = JsonValue(edge.Key),
                    ["u"] = edge.U,
                    ["v"] = edge.V
                };
                if (force)
                    item["form_edge_id"] = edge.Id;
                else
                    item["source_edge_ids"] = edge.SourceEdgeIds.ToArray();
                return (object)item;
            })
            .ToArray();
        object[] faces = graph.Faces
            .Select(face => (object)new Dictionary<string, object?>(
                StringComparer.Ordinal)
            {
                ["id"] = face.Id,
                ["key"] = JsonValue(face.Key),
                ["vertices"] = face.Vertices.ToArray()
            })
            .ToArray();
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["vertices"] = vertices,
            ["edges"] = edges,
            ["faces"] = faces
        };
    }

    private static IReadOnlyDictionary<string, object?> BoundaryPayload(
        TnaBoundarySegmentDto segment) =>
        new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["boundary_index"] = segment.BoundaryIndex,
            ["segment_index"] = segment.SegmentIndex,
            ["node_ids"] = segment.NodeIds.ToArray(),
            ["source_vertex_ids"] = segment.SourceVertexIds
                .Select(JsonValue)
                .ToArray(),
            ["target_sag"] = segment.TargetSag,
            ["initial_sag"] = segment.InitialSag,
            ["actual_sag"] = segment.ActualSag,
            ["sag_error"] = segment.SagError
        };

    private static IReadOnlyDictionary<string, object?> DiagnosticPayload(
        DiagnosticDto diagnostic) =>
        new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["code"] = diagnostic.Code,
            ["severity"] = diagnostic.Severity,
            ["message"] = diagnostic.Message,
            ["value"] = diagnostic.Value,
            ["tolerance"] = diagnostic.Tolerance,
            ["unit"] = diagnostic.Unit,
            ["context"] = new Dictionary<string, string>(
                diagnostic.Context,
                StringComparer.Ordinal)
        };

    private static IReadOnlyDictionary<string, object?> MappingsPayload(
        TnaPreparedMappingsDto mappings) =>
        new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["pattern_vertex_to_topology_vertex"] =
                mappings.PatternVertexToTopologyVertex.ToArray(),
            ["backend_source_to_topology_vertex"] =
                mappings.BackendSourceToTopologyVertex
                    .Select(item =>
                        (object)new Dictionary<string, object?>(
                            StringComparer.Ordinal)
                        {
                            ["source_key"] = JsonValue(item.SourceKey),
                            ["topology_vertex_id"] = item.TopologyVertexId
                    })
                    .ToArray(),
            ["source_edge_to_pattern_edge"] =
                mappings.SourceEdgeToPatternEdge
                    .Select(item =>
                        (object)new Dictionary<string, object?>(
                            StringComparer.Ordinal)
                        {
                            ["source_edge_id"] = item.SourceEdgeId,
                            ["pattern_edge_id"] = item.PatternEdgeId,
                            ["u"] = item.U,
                            ["v"] = item.V
                        })
                    .ToArray(),
            ["support_node_ids"] = mappings.SupportNodeIds.ToArray(),
            ["fixed_plan_node_ids"] =
                mappings.FixedPlanNodeIds.ToArray(),
            ["form_edge_to_force_edge"] =
                mappings.FormEdgeToForceEdge
                    .Select(item =>
                        (object)new Dictionary<string, object?>(
                            StringComparer.Ordinal)
                        {
                            ["form_edge_id"] = item.FormEdgeId,
                            ["force_edge_id"] = item.TargetEdgeId
                        })
                    .ToArray()
        };

    private static string VerifyUnchangedTopology(
        JsonElement root,
        TopologyDto expected)
    {
        string kind = RequiredString(root, "kind");
        if (!string.Equals(
                kind,
                expected.NetworkKind,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new JsonException(
                "tna.prepare changed the source topology kind.");
        }
        Point3Dto[] vertices = DecodePoints(root, "vertices");
        EdgeDto[] edges = DecodeEdges(root, "edges");
        int[][] faces = DecodeFaces(root, "faces");
        if (vertices.Length != expected.Vertices.Count ||
            !vertices.Zip(expected.Vertices, SamePoint).All(value => value) ||
            edges.Length != expected.Edges.Count ||
            !edges.Zip(expected.Edges, SameEdge).All(value => value) ||
            faces.Length != expected.Faces.Count ||
            !faces.Zip(
                    expected.Faces,
                    (actual, source) => actual.SequenceEqual(source))
                .All(value => value))
        {
            throw new JsonException(
                "tna.prepare did not return the original stable source " +
                "topology unchanged.");
        }
        string hash = RequiredString(root, "topology_hash");
        if (!TopologyFingerprint.IsSha256(hash))
            throw new JsonException("Worker topology_hash is not SHA-256.");
        return hash;
    }

    private static SupportSetDto DecodeSupportSet(
        JsonElement root,
        TopologyDto topology)
    {
        string mode = RequiredString(root, "mode").ToLowerInvariant();
        int[] ids = OptionalIntArray(root, "node_ids");
        var value = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = mode,
            Points = Array.Empty<Point3Dto>(),
            NodeIds = ids,
            SnapTolerance = OptionalDouble(root, "snap_tolerance"),
            Provenance = StringMap(root, "metadata")
        };
        EnsureValid(value);
        return value;
    }

    private static TnaPrepareConfigDto DecodeConfig(JsonElement root) =>
        new()
        {
            ForceDensity = RequiredDouble(root, "force_density"),
            Relax = OptionalBoolean(root, "relax", true),
            BoundarySag = OptionalDouble(root, "boundary_sag"),
            SagIterations = RequiredInt(root, "sag_iterations"),
            SagTolerance = RequiredDouble(root, "sag_tolerance"),
            FixedNodeIds = OptionalIntArray(root, "fixed_node_ids"),
            Metadata = StringMap(root, "metadata")
        };

    private static TnaPreparedPatternDto DecodePattern(JsonElement root) =>
        new()
        {
            PatternKind = RequiredString(root, "kind"),
            Vertices = DecodePoints(root, "vertices"),
            Edges = DecodeEdges(root, "edges"),
            Faces = DecodeFaces(root, "faces"),
            EdgeForceDensities =
                RequiredArray(root, "edge_force_densities")
                    .EnumerateArray()
                    .Select((value, index) =>
                        FiniteDouble(
                            value,
                            $"edge_force_densities[{index}]"))
                    .ToArray(),
            FixedNodeIds = OptionalIntArray(root, "fixed_node_ids")
        };

    private static TnaDiagramGraphDto DecodeGraph(
        JsonElement root,
        string label)
    {
        TnaGraphVertexDto[] vertices = RequiredArray(root, "vertices")
            .EnumerateArray()
            .Select((value, index) =>
            {
                RequireObject(value, $"{label}.vertices[{index}]");
                return new TnaGraphVertexDto
                {
                    Id = RequiredInt(value, "id"),
                    Key = RequiredProperty(value, "key").Clone(),
                    Point = DecodePoint(
                        RequiredProperty(value, "point"),
                        $"{label}.vertices[{index}].point"),
                    SourceVertexIds =
                        OptionalJsonArray(value, "source_vertex_ids")
                };
            })
            .ToArray();
        TnaGraphEdgeDto[] edges = RequiredArray(root, "edges")
            .EnumerateArray()
            .Select((value, index) =>
            {
                RequireObject(value, $"{label}.edges[{index}]");
                return new TnaGraphEdgeDto
                {
                    Id = RequiredInt(value, "id"),
                    Key = RequiredProperty(value, "key").Clone(),
                    U = RequiredInt(value, "u"),
                    V = RequiredInt(value, "v"),
                    SourceEdgeIds =
                        OptionalIntArray(value, "source_edge_ids")
                };
            })
            .ToArray();
        TnaGraphFaceDto[] faces = OptionalArray(root, "faces")
            .EnumerateArray()
            .Select(value => new TnaGraphFaceDto
            {
                Id = RequiredInt(value, "id"),
                Key = RequiredProperty(value, "key").Clone(),
                Vertices = OptionalIntArray(value, "vertices")
            })
            .ToArray();
        return new TnaDiagramGraphDto
        {
            Vertices = vertices,
            Edges = edges,
            Faces = faces
        };
    }

    private static TnaBoundarySegmentDto DecodeBoundary(
        JsonElement root,
        string label)
    {
        RequireObject(root, label);
        return new TnaBoundarySegmentDto
        {
            BoundaryIndex = RequiredInt(root, "boundary_index"),
            SegmentIndex = RequiredInt(root, "segment_index"),
            NodeIds = OptionalIntArray(root, "node_ids"),
            SourceVertexIds =
                OptionalJsonArray(root, "source_vertex_ids"),
            TargetSag = OptionalDouble(root, "target_sag"),
            InitialSag = RequiredDouble(root, "initial_sag"),
            ActualSag = RequiredDouble(root, "actual_sag"),
            SagError = RequiredDouble(root, "sag_error")
        };
    }

    private static TnaPreparedMappingsDto DecodePreparedMappings(
        JsonElement root)
    {
        TnaBackendSourceMappingDto[] backend =
            RequiredArray(root, "backend_source_to_topology_vertex")
                .EnumerateArray()
                .Select(value => new TnaBackendSourceMappingDto
                {
                    SourceKey =
                        RequiredProperty(value, "source_key").Clone(),
                    TopologyVertexId =
                        RequiredInt(value, "topology_vertex_id")
                })
                .ToArray();
        TnaEdgeMappingDto[] formToForce =
            RequiredArray(root, "form_edge_to_force_edge")
                .EnumerateArray()
                .Select(value => new TnaEdgeMappingDto
                {
                    FormEdgeId = RequiredInt(value, "form_edge_id"),
                    TargetEdgeId = RequiredInt(value, "force_edge_id")
                })
                .ToArray();
        TnaSourcePatternEdgeMappingDto[] sourceEdges =
            RequiredArray(root, "source_edge_to_pattern_edge")
                .EnumerateArray()
                .Select(value => new TnaSourcePatternEdgeMappingDto
                {
                    SourceEdgeId =
                        RequiredInt(value, "source_edge_id"),
                    PatternEdgeId =
                        RequiredInt(value, "pattern_edge_id"),
                    U = RequiredInt(value, "u"),
                    V = RequiredInt(value, "v")
                })
                .ToArray();
        return new TnaPreparedMappingsDto
        {
            PatternVertexToTopologyVertex =
                OptionalIntArray(
                    root,
                    "pattern_vertex_to_topology_vertex"),
            BackendSourceToTopologyVertex = backend,
            SourceEdgeToPatternEdge = sourceEdges,
            SupportNodeIds =
                OptionalIntArray(root, "support_node_ids"),
            FixedPlanNodeIds =
                OptionalIntArray(root, "fixed_plan_node_ids"),
            FormEdgeToForceEdge = formToForce
        };
    }

    private static DiagnosticDto[] DecodeDiagnostics(JsonElement root)
    {
        var result = new List<DiagnosticDto>();
        int index = 0;
        foreach (JsonElement value in
                 OptionalArray(root, "diagnostics").EnumerateArray())
        {
            RequireObject(value, $"diagnostics[{index}]");
            var diagnostic = new DiagnosticDto
            {
                Code = OptionalString(value, "code"),
                Severity = OptionalString(value, "severity"),
                Message = OptionalString(value, "message"),
                Value = OptionalDouble(value, "value"),
                Tolerance = OptionalDouble(value, "tolerance"),
                Unit = OptionalString(value, "unit"),
                Context = StringMap(value, "context"),
                Provenance = new Dictionary<string, string>(
                    StringComparer.Ordinal)
                {
                    ["source"] = "COMPAS tna.prepare worker"
                }
            };
            EnsureValid(diagnostic);
            result.Add(diagnostic);
            index++;
        }
        return result.ToArray();
    }

    private static TopologyDto DecodeAnalysisTopology(
        JsonElement root,
        TnaPreparedDto prepared)
    {
        string kind = RequiredString(root, "kind");
        if (!string.Equals(kind, "faced", StringComparison.OrdinalIgnoreCase))
            throw new JsonException("Staged TNA analysis topology is not faced.");
        Point3Dto[] vertices = DecodePoints(root, "vertices");
        EdgeDto[] edges = DecodeEdges(root, "edges");
        int[][] faces = DecodeFaces(root, "faces");
        TopologyDto source = prepared.Source!.Topology!;
        string[] sourceVertexIds =
            source.SourceVertexIds.Count == vertices.Length
                ? source.SourceVertexIds.ToArray()
                : Enumerable.Range(0, vertices.Length)
                    .Select(index => $"prepared-v{index}")
                    .ToArray();
        string[] sourceEdgeIds =
            source.SourceEdgeIds.Count == edges.Length &&
            source.Edges.Zip(edges, SameEdge).All(value => value)
                ? source.SourceEdgeIds.ToArray()
                : Enumerable.Range(0, edges.Length)
                    .Select(index => $"prepared-edge:{index}")
                    .ToArray();
        var provenance = new Dictionary<string, string>(
            source.Provenance,
            StringComparer.Ordinal)
        {
            ["source_topology_hash"] = source.TopologyHash,
            ["source_topology_kind"] = source.NetworkKind,
            ["worker_source_topology_hash"] =
                prepared.WorkerTopologyHash,
            ["prepared_analysis_topology"] = "true",
            ["worker_analysis_topology_hash"] =
                OptionalString(root, "topology_hash")
        };
        // The principal-line runs are a C# annotation and never went to the
        // worker, so they have to be carried across this rebuild or the
        // downstream components find none on a TNA result. Carried only when
        // the analysis kept the source's vertex count, which is the same
        // condition under which the source vertex IDs are carried above: it is
        // what says the indices still mean the same vertices. Where the count
        // changed the runs are dropped rather than reindexed by guesswork.
        bool indicesHold = source.Vertices.Count == vertices.Length;
        IEnumerable<IEnumerable<int>>? principalRuns =
            indicesHold && source.PrincipalRuns.Count > 0
                ? source.PrincipalRuns
                : null;
        if (!indicesHold && source.PrincipalRuns.Count > 0)
        {
            provenance["principal_runs_dropped"] =
                "analysis vertex count differs from the source";
        }

        TopologyDto topology = TopologyDto.Create(
            "faced",
            vertices,
            edges,
            faces,
            sourceVertexIds,
            sourceEdgeIds,
            source.LengthUnit,
            provenance,
            principalRuns);
        EnsureValid(topology);
        return topology;
    }

    private static IReadOnlyDictionary<string, string> Merge(
        IReadOnlyDictionary<string, string> source,
        string key,
        string value)
    {
        var result = new Dictionary<string, string>(
            source,
            StringComparer.Ordinal)
        {
            [key] = value
        };
        return result;
    }

    private static Point3Dto[] DecodePoints(
        JsonElement root,
        string propertyName) =>
        RequiredArray(root, propertyName)
            .EnumerateArray()
            .Select((value, index) =>
                DecodePoint(value, $"{propertyName}[{index}]"))
            .ToArray();

    private static EdgeDto[] DecodeEdges(
        JsonElement root,
        string propertyName) =>
        RequiredArray(root, propertyName)
            .EnumerateArray()
            .Select((value, index) =>
                DecodeEdge(value, $"{propertyName}[{index}]"))
            .ToArray();

    private static int[][] DecodeFaces(
        JsonElement root,
        string propertyName) =>
        OptionalArray(root, propertyName)
            .EnumerateArray()
            .Select((face, index) =>
            {
                if (face.ValueKind != JsonValueKind.Array)
                    throw new JsonException(
                        $"{propertyName}[{index}] must be an array.");
                return face.EnumerateArray()
                    .Select((value, vertexIndex) =>
                        Integer(
                            value,
                            $"{propertyName}[{index}][{vertexIndex}]"))
                    .ToArray();
            })
            .ToArray();

    private static Point3Dto DecodePoint(
        JsonElement value,
        string label)
    {
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{label} must be a coordinate array.");
        double[] coordinates = value
            .EnumerateArray()
            .Select(item => FiniteDouble(item, label))
            .ToArray();
        if (coordinates.Length != 3)
            throw new JsonException($"{label} must contain three coordinates.");
        return new Point3Dto(
            coordinates[0],
            coordinates[1],
            coordinates[2]);
    }

    private static EdgeDto DecodeEdge(
        JsonElement value,
        string label)
    {
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{label} must be an index pair.");
        int[] ids = value.EnumerateArray()
            .Select((item, index) =>
                Integer(item, $"{label}[{index}]"))
            .ToArray();
        if (ids.Length != 2)
            throw new JsonException($"{label} must contain two node IDs.");
        return new EdgeDto(ids[0], ids[1]);
    }

    private static bool SamePoint(Point3Dto left, Point3Dto right) =>
        left.X.Equals(right.X) &&
        left.Y.Equals(right.Y) &&
        left.Z.Equals(right.Z);

    private static bool SameEdge(EdgeDto left, EdgeDto right) =>
        left.U == right.U && left.V == right.V;

    private static double[] PointPayload(Point3Dto point) =>
        new[] { point.X, point.Y, point.Z };

    private static object? JsonValue(JsonElement value) =>
        value.ValueKind == JsonValueKind.Undefined
            ? null
            : JsonSerializer.Deserialize<object>(
                value.GetRawText(),
                ContractJson.Options);

    private static void RequireWorkerSchema(
        JsonElement root,
        string label)
    {
        string schema = RequiredString(root, "schema_version");
        if (!string.Equals(
                schema,
                WorkerProtocol.CompatibleWorkerSchema,
                StringComparison.Ordinal))
        {
            throw new JsonException(
                $"{label} schema '{schema}' is not supported; expected " +
                $"'{WorkerProtocol.CompatibleWorkerSchema}'.");
        }
    }

    private static JsonElement RequiredObject(
        JsonElement root,
        string propertyName)
    {
        JsonElement value = RequiredProperty(root, propertyName);
        RequireObject(value, propertyName);
        return value;
    }

    private static void RequireObject(JsonElement value, string label)
    {
        if (value.ValueKind != JsonValueKind.Object)
            throw new JsonException($"{label} must be a JSON object.");
    }

    private static JsonElement RequiredArray(
        JsonElement root,
        string propertyName)
    {
        JsonElement value = RequiredProperty(root, propertyName);
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{propertyName} must be an array.");
        return value;
    }

    private static JsonElement OptionalArray(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind == JsonValueKind.Null)
        {
            return EmptyArray();
        }
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{propertyName} must be an array.");
        return value;
    }

    private static JsonElement EmptyArray()
    {
        using JsonDocument document = JsonDocument.Parse("[]");
        return document.RootElement.Clone();
    }

    private static JsonElement RequiredProperty(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value))
            throw new JsonException($"Missing required '{propertyName}'.");
        return value;
    }

    private static string RequiredString(
        JsonElement root,
        string propertyName)
    {
        string value = OptionalString(root, propertyName);
        if (value.Length == 0)
            throw new JsonException(
                $"Missing required string '{propertyName}'.");
        return value;
    }

    private static string OptionalString(
        JsonElement root,
        string propertyName) =>
        root.TryGetProperty(propertyName, out JsonElement value) &&
        value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static int RequiredInt(
        JsonElement root,
        string propertyName) =>
        Integer(
            RequiredProperty(root, propertyName),
            propertyName);

    private static int Integer(JsonElement value, string label)
    {
        if (!value.TryGetInt32(out int result))
            throw new JsonException($"{label} must be a 32-bit integer.");
        return result;
    }

    private static double RequiredDouble(
        JsonElement root,
        string propertyName) =>
        FiniteDouble(
            RequiredProperty(root, propertyName),
            propertyName);

    private static double? OptionalDouble(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }
        return FiniteDouble(value, propertyName);
    }

    private static double FiniteDouble(
        JsonElement value,
        string label)
    {
        if (!value.TryGetDouble(out double result) ||
            !double.IsFinite(result))
        {
            throw new JsonException($"{label} must be a finite number.");
        }
        return result;
    }

    private static bool OptionalBoolean(
        JsonElement root,
        string propertyName,
        bool fallback)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value))
            return fallback;
        return value.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            _ => throw new JsonException(
                $"{propertyName} must be a boolean.")
        };
    }

    private static int[] OptionalIntArray(
        JsonElement root,
        string propertyName) =>
        OptionalArray(root, propertyName)
            .EnumerateArray()
            .Select((value, index) =>
                Integer(value, $"{propertyName}[{index}]"))
            .ToArray();

    private static JsonElement[] OptionalJsonArray(
        JsonElement root,
        string propertyName) =>
        OptionalArray(root, propertyName)
            .EnumerateArray()
            .Select(value => value.Clone())
            .ToArray();

    private static IReadOnlyDictionary<string, string> StringMap(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind == JsonValueKind.Null)
        {
            return new Dictionary<string, string>(
                StringComparer.Ordinal);
        }
        if (value.ValueKind != JsonValueKind.Object)
            throw new JsonException($"{propertyName} must be an object.");
        var output = new SortedDictionary<string, string>(
            StringComparer.Ordinal);
        foreach (JsonProperty property in value.EnumerateObject())
            output[property.Name] = ScalarText(property.Value);
        return output;
    }

    private static void AddJsonMap(
        IDictionary<string, string> output,
        JsonElement root,
        string propertyName,
        string prefix)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind == JsonValueKind.Null)
        {
            return;
        }
        if (value.ValueKind != JsonValueKind.Object)
            throw new JsonException($"{propertyName} must be an object.");
        foreach (JsonProperty property in value.EnumerateObject())
            output[prefix + property.Name] = ScalarText(property.Value);
    }

    private static string ScalarText(JsonElement value) =>
        value.ValueKind switch
        {
            JsonValueKind.String => value.GetString() ?? string.Empty,
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            JsonValueKind.Null => "null",
            _ => value.GetRawText()
        };

    private static void EnsureValid(ContractDto value)
    {
        IReadOnlyList<string> errors = value.Validate();
        if (errors.Count > 0)
        {
            throw new InvalidOperationException(
                $"{value.GetType().Name} is invalid: " +
                string.Join(" ", errors));
        }
    }
}
