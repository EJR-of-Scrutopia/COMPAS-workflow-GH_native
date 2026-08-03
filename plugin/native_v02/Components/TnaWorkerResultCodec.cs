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
/// Strict translation from the worker's snake_case TNA snapshot into native,
/// persistable contracts. The translation is intentionally explicit so
/// COMPAS object keys and source identifiers remain lossless.
/// </summary>
internal static class TnaWorkerResultCodec
{
    public static TnaResultDto Decode(
        JsonElement root,
        EquilibriumProblemDto problem,
        TnaControlDto control,
        int loadCaseIndex)
    {
        RequireObject(root, "TNA result");
        string schemaVersion = RequiredString(root, "schema_version");
        if (!string.Equals(
                schemaVersion,
                WorkerProtocol.CompatibleWorkerSchema,
                StringComparison.Ordinal))
        {
            throw new JsonException(
                $"TNA result schema '{schemaVersion}' is not supported; " +
                $"expected '{WorkerProtocol.CompatibleWorkerSchema}'.");
        }
        string kind = RequiredString(root, "kind");
        if (!string.Equals(kind, "tna_result", StringComparison.Ordinal))
            throw new JsonException($"Expected tna_result, received '{kind}'.");

        AnalysisPlaneDto plane = Plane(
            RequiredObject(root, "analysis_plane"),
            "analysis_plane");
        TnaDiagramGraphDto form = Graph(
            RequiredObject(root, "form_graph"),
            "form_graph");
        TnaDiagramGraphDto force = Graph(
            RequiredObject(root, "force_graph"),
            "force_graph");
        TnaEdgeStateDto[] states = RequiredArray(root, "edge_states")
            .EnumerateArray()
            .Select((value, index) => EdgeState(
                value,
                $"edge_states[{index}]"))
            .ToArray();
        TnaMappingsDto mappings = Mappings(
            RequiredObject(root, "mappings"));
        DiagnosticDto[] diagnostics = Diagnostics(root);
        JsonElement equilibriumJson =
            RequiredObject(root, "equilibrium");
        EquilibriumResultDto equilibrium = DecodeEquilibrium(
            equilibriumJson,
            problem,
            control,
            loadCaseIndex,
            states,
            mappings,
            diagnostics);

        var provenance = StringMap(root, "provenance");
        provenance["transport"] = "persistent-python-worker";
        var result = new TnaResultDto
        {
            Equilibrium = equilibrium,
            Control = control,
            AnalysisPlane = plane,
            FormGraph = form,
            ForceGraph = force,
            EdgeStates = states,
            HorizontalScale = RequiredDouble(root, "horizontal_scale"),
            Mappings = mappings,
            Diagnostics = diagnostics,
            Report = OptionalString(root, "report"),
            Provenance = provenance
        };
        IReadOnlyList<string> errors = result.Validate();
        if (errors.Count > 0)
        {
            throw new JsonException(
                "The TNA worker result failed its native contract: " +
                string.Join(" ", errors));
        }
        return result;
    }

    /// <summary>
    /// Decode a unified-envelope TNA result (<c>kind == "Result"</c>,
    /// <c>solver == "tna"</c>) into <see cref="ResultDto"/>. The envelope
    /// only adds the discriminator keys on top of the same TNA payload
    /// shape <see cref="Decode"/> reads, so the field-by-field mapping is
    /// identical; only the wrapping kind check and target type differ.
    /// </summary>
    public static ResultDto DecodeResult(
        JsonElement root,
        EquilibriumProblemDto problem,
        TnaControlDto control,
        int loadCaseIndex)
    {
        RequireObject(root, "TNA result");
        string schemaVersion = RequiredString(root, "schema_version");
        if (!string.Equals(
                schemaVersion,
                WorkerProtocol.CompatibleWorkerSchema,
                StringComparison.Ordinal))
        {
            throw new JsonException(
                $"TNA result schema '{schemaVersion}' is not supported; " +
                $"expected '{WorkerProtocol.CompatibleWorkerSchema}'.");
        }
        string kind = RequiredString(root, "kind");
        if (!string.Equals(kind, "Result", StringComparison.Ordinal))
            throw new JsonException($"Expected Result, received '{kind}'.");
        string solver = RequiredString(root, "solver").ToLowerInvariant();
        if (solver != "tna")
            throw new JsonException($"Expected a TNA result, received '{solver}'.");
        string resultSchema = RequiredString(root, "resultSchema");

        AnalysisPlaneDto plane = Plane(
            RequiredObject(root, "analysis_plane"),
            "analysis_plane");
        TnaDiagramGraphDto form = Graph(
            RequiredObject(root, "form_graph"),
            "form_graph");
        TnaDiagramGraphDto force = Graph(
            RequiredObject(root, "force_graph"),
            "force_graph");
        TnaEdgeStateDto[] states = RequiredArray(root, "edge_states")
            .EnumerateArray()
            .Select((value, index) => EdgeState(
                value,
                $"edge_states[{index}]"))
            .ToArray();
        TnaMappingsDto mappings = Mappings(
            RequiredObject(root, "mappings"));
        DiagnosticDto[] diagnostics = Diagnostics(root);
        JsonElement equilibriumJson =
            RequiredObject(root, "equilibrium");
        EquilibriumResultDto equilibrium = DecodeEquilibrium(
            equilibriumJson,
            problem,
            control,
            loadCaseIndex,
            states,
            mappings,
            diagnostics);

        var provenance = StringMap(root, "provenance");
        provenance["transport"] = "persistent-python-worker";
        var result = new ResultDto
        {
            Solver = "tna",
            ResultSchema = resultSchema,
            Equilibrium = equilibrium,
            Control = control,
            AnalysisPlane = plane,
            FormGraph = form,
            ForceGraph = force,
            EdgeStates = states,
            HorizontalScale = RequiredDouble(root, "horizontal_scale"),
            Mappings = mappings,
            Diagnostics = diagnostics,
            Report = OptionalString(root, "report"),
            Provenance = provenance
        };
        IReadOnlyList<string> resultErrors = result.Validate();
        if (resultErrors.Count > 0)
        {
            throw new JsonException(
                "The TNA worker result failed its native contract: " +
                string.Join(" ", resultErrors));
        }
        return result;
    }

    private static EquilibriumResultDto DecodeEquilibrium(
        JsonElement root,
        EquilibriumProblemDto problem,
        TnaControlDto control,
        int loadCaseIndex,
        IReadOnlyList<TnaEdgeStateDto> states,
        TnaMappingsDto mappings,
        IReadOnlyList<DiagnosticDto> diagnostics)
    {
        RequireObject(root, "equilibrium");
        string schemaVersion = RequiredString(root, "schema_version");
        if (!string.Equals(
                schemaVersion,
                WorkerProtocol.CompatibleWorkerSchema,
                StringComparison.Ordinal))
        {
            throw new JsonException(
                $"TNA equilibrium schema '{schemaVersion}' is not supported.");
        }
        string solver = RequiredString(root, "solver").ToLowerInvariant();
        if (solver != "tna")
            throw new JsonException($"Expected TNA equilibrium, received '{solver}'.");

        Point3Dto[] vertices = RequiredArray(root, "vertices")
            .EnumerateArray()
            .Select((value, index) => Point(value, $"vertices[{index}]"))
            .ToArray();
        EdgeDto[] edges = RequiredArray(root, "edges")
            .EnumerateArray()
            .Select((value, index) => Edge(value, $"edges[{index}]"))
            .ToArray();
        double[] memberForces = NumberArray(root, "member_forces");
        double[] densities = NumberArray(root, "force_densities");

        NodalVectorDto[] loads = mappings.Loads
            .Select(item => NodalVector(
                item.EquilibriumVertexId,
                item.Vector,
                vertices,
                "load"))
            .Where(item => !IsZero(item.Vector))
            .ToArray();
        NodalVectorDto[] reactions = mappings.Reactions
            .Select(item => NodalVector(
                item.EquilibriumVertexId,
                item.Reaction,
                vertices,
                "reaction"))
            .Where(item => !IsZero(item.Vector))
            .ToArray();
        int[] supportIds = mappings.Supports
            .Select(item => item.EquilibriumVertexId)
            .Distinct()
            .OrderBy(value => value)
            .ToArray();

        Dictionary<int, TnaEdgeStateDto> stateByEquilibrium = states
            .GroupBy(state => state.EquilibriumEdgeId)
            .ToDictionary(group => group.Key, group => group.First());
        string[] memberSourceIds = Enumerable.Range(0, edges.Length)
            .Select(edgeId => MemberSourceId(
                edgeId,
                stateByEquilibrium,
                problem.Topology!))
            .ToArray();

        LoadCaseDto loadCase = problem.LoadCases[loadCaseIndex];
        string forceUnit =
            loadCase.Provenance.TryGetValue("force_unit", out string? unit) &&
            !string.IsNullOrWhiteSpace(unit)
                ? unit
                : "kN";
        var settings = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["height_mode"] =
                TnaControlDto.NormaliseHeightMode(control.HeightMode),
            ["height_value"] =
                control.HeightValue.ToString("R", CultureInfo.InvariantCulture),
            ["horizontal_alpha"] =
                control.HorizontalAlpha.ToString("R", CultureInfo.InvariantCulture),
            ["horizontal_iterations"] =
                control.HorizontalIterations.ToString(CultureInfo.InvariantCulture),
            ["vertical_iterations"] =
                control.VerticalIterations.ToString(CultureInfo.InvariantCulture),
            ["tolerance"] =
                control.Tolerance.ToString("R", CultureInfo.InvariantCulture),
            ["load_case_index"] =
                loadCaseIndex.ToString(CultureInfo.InvariantCulture),
            ["load_case_name"] = loadCase.Name
        };
        var provenance = StringMap(root, "provenance");
        provenance["transport"] = "persistent-python-worker";
        var result = new EquilibriumResultDto
        {
            Solver = "tna",
            Problem = problem,
            TopologyHash = problem.TopologyHash,
            Vertices = vertices,
            Edges = edges,
            MemberForces = memberForces,
            ForceDensities = densities,
            Loads = loads,
            Reactions = reactions,
            Residuals = Array.Empty<NodalVectorDto>(),
            Diagnostics = diagnostics.ToArray(),
            MemberSourceIds = memberSourceIds,
            ResolvedSupportNodeIds = supportIds,
            LengthUnit = problem.Topology!.LengthUnit,
            ForceUnit = forceUnit,
            SignConvention = "positive_tension",
            SolverSettings = settings,
            Report = OptionalString(root, "report"),
            Provenance = provenance
        };
        IReadOnlyList<string> errors = result.Validate();
        if (errors.Count > 0)
        {
            throw new JsonException(
                "The TNA equilibrium snapshot failed its native contract: " +
                string.Join(" ", errors));
        }
        return result;
    }

    private static string MemberSourceId(
        int equilibriumEdgeId,
        IReadOnlyDictionary<int, TnaEdgeStateDto> states,
        TopologyDto topology)
    {
        if (!states.TryGetValue(equilibriumEdgeId, out TnaEdgeStateDto? state))
            return $"tna-edge:{equilibriumEdgeId}";
        string[] values = state.SourceEdgeIds
            .Where(id => id >= 0 && id < topology.Edges.Count)
            .Select(id =>
                topology.SourceEdgeIds.Count == topology.Edges.Count
                    ? topology.SourceEdgeIds[id]
                    : $"source-edge:{id}")
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        return values.Length == 0
            ? $"tna-edge:{equilibriumEdgeId}"
            : string.Join("+", values);
    }

    private static AnalysisPlaneDto Plane(JsonElement root, string label) =>
        new()
        {
            Origin = Point(
                RequiredProperty(root, "origin"),
                $"{label}.origin"),
            XAxis = Point(
                RequiredProperty(root, "xaxis"),
                $"{label}.xaxis"),
            YAxis = Point(
                RequiredProperty(root, "yaxis"),
                $"{label}.yaxis"),
            ZAxis = Point(
                RequiredProperty(root, "zaxis"),
                $"{label}.zaxis")
        };

    private static TnaDiagramGraphDto Graph(
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
                    Point = Point(
                        RequiredProperty(value, "point"),
                        $"{label}.vertices[{index}].point"),
                    SourceVertexIds = OptionalJsonArray(
                        value,
                        "source_vertex_ids")
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
                    SourceEdgeIds = OptionalIntArray(
                        value,
                        "source_edge_ids")
                };
            })
            .ToArray();
        TnaGraphFaceDto[] faces = OptionalArray(root, "faces")
            .EnumerateArray()
            .Select((value, index) =>
            {
                RequireObject(value, $"{label}.faces[{index}]");
                return new TnaGraphFaceDto
                {
                    Id = RequiredInt(value, "id"),
                    Key = RequiredProperty(value, "key").Clone(),
                    Vertices = RequiredArray(value, "vertices")
                        .EnumerateArray()
                        .Select((item, vertexIndex) =>
                            Integer(
                                item,
                                $"{label}.faces[{index}].vertices[{vertexIndex}]"))
                        .ToArray()
                };
            })
            .ToArray();
        return new TnaDiagramGraphDto
        {
            Vertices = vertices,
            Edges = edges,
            Faces = faces
        };
    }

    private static TnaEdgeStateDto EdgeState(
        JsonElement value,
        string label)
    {
        RequireObject(value, label);
        return new TnaEdgeStateDto
        {
            Id = RequiredInt(value, "id"),
            EquilibriumEdgeId =
                RequiredInt(value, "equilibrium_edge_id"),
            SourceEdgeIds = OptionalIntArray(value, "source_edge_ids"),
            FormEdgeId = RequiredInt(value, "form_edge_id"),
            ForceEdgeId = RequiredInt(value, "force_edge_id"),
            ForceDensity = RequiredDouble(value, "q"),
            HorizontalForce = RequiredDouble(value, "horizontal_force"),
            AxialForce = RequiredDouble(value, "axial_force"),
            ForceState = RequiredString(value, "force_state"),
            ReciprocityErrorDegrees =
                RequiredDouble(value, "reciprocity_error_degrees")
        };
    }

    private static TnaMappingsDto Mappings(JsonElement root)
    {
        TnaSourceVertexMappingDto[] sourceVertices =
            RequiredArray(root, "source_vertex_to_form_vertex")
                .EnumerateArray()
                .Select(value =>
                {
                    RequireObject(value, "source_vertex_to_form_vertex item");
                    return new TnaSourceVertexMappingDto
                    {
                        TopologyVertexId =
                            OptionalInt(value, "topology_vertex_id"),
                        SourceVertexId =
                            RequiredProperty(value, "source_vertex_id").Clone(),
                        FormVertexId =
                            OptionalInt(value, "form_vertex_id"),
                        EquilibriumVertexId =
                            OptionalInt(value, "equilibrium_vertex_id")
                    };
                })
                .ToArray();
        TnaSourceEdgeMappingDto[] sourceEdges =
            RequiredArray(root, "source_edge_to_form_edge")
                .EnumerateArray()
                .Select(value =>
                {
                    RequireObject(value, "source_edge_to_form_edge item");
                    return new TnaSourceEdgeMappingDto
                    {
                        SourceEdgeId = RequiredInt(value, "source_edge_id"),
                        SourceU = RequiredInt(value, "source_u"),
                        SourceV = RequiredInt(value, "source_v"),
                        FormEdgeId = OptionalInt(value, "form_edge_id")
                    };
                })
                .ToArray();
        TnaEdgeMappingDto[] formToForce = RequiredArray(
                root,
                "form_edge_to_force_edge")
            .EnumerateArray()
            .Select(value => new TnaEdgeMappingDto
            {
                FormEdgeId = RequiredInt(value, "form_edge_id"),
                TargetEdgeId = RequiredInt(value, "force_edge_id")
            })
            .ToArray();
        TnaEdgeMappingDto[] formToEquilibrium = RequiredArray(
                root,
                "form_edge_to_equilibrium_edge")
            .EnumerateArray()
            .Select(value => new TnaEdgeMappingDto
            {
                FormEdgeId = RequiredInt(value, "form_edge_id"),
                TargetEdgeId = RequiredInt(value, "equilibrium_edge_id")
            })
            .ToArray();
        TnaSupportMappingDto[] supports =
            SupportMappings(root, "supports");
        TnaLoadMappingDto[] loads = RequiredArray(root, "loads")
            .EnumerateArray()
            .Select(value =>
            {
                RequireObject(value, "loads item");
                return new TnaLoadMappingDto
                {
                    TopologyVertexIds =
                        OptionalIntArray(value, "topology_vertex_ids"),
                    SourceVertexIds =
                        OptionalArray(value, "source_vertex_ids")
                            .EnumerateArray()
                            .Select(item => item.Clone())
                            .ToArray(),
                    FormVertexId = RequiredInt(value, "form_vertex_id"),
                    EquilibriumVertexId =
                        RequiredInt(value, "equilibrium_vertex_id"),
                    Vector = Point(
                        RequiredProperty(value, "vector"),
                        "loads.vector")
                };
            })
            .ToArray();
        TnaSupportMappingDto[] reactions =
            SupportMappings(root, "reactions");
        return new TnaMappingsDto
        {
            SourceVertexToFormVertex = sourceVertices,
            SourceEdgeToFormEdge = sourceEdges,
            FormEdgeToForceEdge = formToForce,
            FormEdgeToEquilibriumEdge = formToEquilibrium,
            Supports = supports,
            Loads = loads,
            Reactions = reactions
        };
    }

    private static TnaSupportMappingDto[] SupportMappings(
        JsonElement root,
        string propertyName) =>
        RequiredArray(root, propertyName)
            .EnumerateArray()
            .Select(value =>
            {
                RequireObject(value, $"{propertyName} item");
                JsonElement sourceId =
                    RequiredProperty(value, "source_vertex_id");
                return new TnaSupportMappingDto
                {
                    TopologyVertexId =
                        OptionalInt(value, "topology_vertex_id"),
                    SourceVertexId =
                        sourceId.ValueKind == JsonValueKind.Null
                            ? null
                            : sourceId.Clone(),
                    FormVertexId = RequiredInt(value, "form_vertex_id"),
                    EquilibriumVertexId =
                        RequiredInt(value, "equilibrium_vertex_id"),
                    Reaction = Point(
                        RequiredProperty(value, "reaction"),
                        $"{propertyName}.reaction")
                };
            })
            .ToArray();

    private static DiagnosticDto[] Diagnostics(JsonElement root)
    {
        JsonElement values = OptionalArray(root, "diagnostics");
        var output = new List<DiagnosticDto>();
        int index = 0;
        foreach (JsonElement value in values.EnumerateArray())
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
                Provenance = new Dictionary<string, string>
                {
                    ["source"] = "COMPAS TNA worker"
                }
            };
            IReadOnlyList<string> errors = diagnostic.Validate();
            if (errors.Count > 0)
            {
                throw new JsonException(
                    $"diagnostics[{index}] is invalid: " +
                    string.Join(" ", errors));
            }
            output.Add(diagnostic);
            index++;
        }
        return output.ToArray();
    }

    private static NodalVectorDto NodalVector(
        int nodeId,
        Point3Dto vector,
        IReadOnlyList<Point3Dto> vertices,
        string label)
    {
        if (nodeId < 0 || nodeId >= vertices.Count)
            throw new JsonException($"{label} mapping has an invalid node ID.");
        return new NodalVectorDto(nodeId, vertices[nodeId], vector);
    }

    private static bool IsZero(Point3Dto value) =>
        value.X == 0.0 && value.Y == 0.0 && value.Z == 0.0;

    private static EdgeDto Edge(JsonElement value, string label)
    {
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{label} must be an index pair.");
        int[] indices = value
            .EnumerateArray()
            .Select((item, index) => Integer(item, $"{label}[{index}]"))
            .ToArray();
        if (indices.Length != 2)
            throw new JsonException($"{label} must contain two node IDs.");
        return new EdgeDto(indices[0], indices[1]);
    }

    private static Point3Dto Point(JsonElement value, string label)
    {
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{label} must be a coordinate array.");
        double[] coordinates = value
            .EnumerateArray()
            .Select((item, index) => Number(item, $"{label}[{index}]"))
            .ToArray();
        if (coordinates.Length != 3)
            throw new JsonException($"{label} must contain three coordinates.");
        return new Point3Dto(
            coordinates[0],
            coordinates[1],
            coordinates[2]);
    }

    private static double[] NumberArray(
        JsonElement root,
        string propertyName) =>
        RequiredArray(root, propertyName)
            .EnumerateArray()
            .Select((value, index) =>
                Number(value, $"{propertyName}[{index}]"))
            .ToArray();

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
            throw new JsonException($"{propertyName} must be a JSON array.");
        return value;
    }

    private static JsonElement OptionalArray(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value))
            return EmptyArray();
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{propertyName} must be a JSON array.");
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
            throw new JsonException($"TNA result requires '{propertyName}'.");
        return value;
    }

    private static int RequiredInt(JsonElement root, string propertyName) =>
        Integer(RequiredProperty(root, propertyName), propertyName);

    private static int? OptionalInt(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }
        return Integer(value, propertyName);
    }

    private static double RequiredDouble(
        JsonElement root,
        string propertyName) =>
        Number(RequiredProperty(root, propertyName), propertyName);

    private static double? OptionalDouble(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }
        return Number(value, propertyName);
    }

    private static string RequiredString(
        JsonElement root,
        string propertyName)
    {
        string value = OptionalString(root, propertyName);
        if (value.Length == 0)
            throw new JsonException($"TNA result requires '{propertyName}'.");
        return value;
    }

    private static string OptionalString(
        JsonElement root,
        string propertyName) =>
        root.TryGetProperty(propertyName, out JsonElement value) &&
        value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static int Integer(JsonElement value, string label)
    {
        if (!value.TryGetInt32(out int number))
            throw new JsonException($"{label} must be an integer.");
        return number;
    }

    private static double Number(JsonElement value, string label)
    {
        if (!value.TryGetDouble(out double number) || !double.IsFinite(number))
            throw new JsonException($"{label} must be finite.");
        return number;
    }

    private static Dictionary<string, string> StringMap(
        JsonElement root,
        string propertyName)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind == JsonValueKind.Null)
        {
            return result;
        }
        if (value.ValueKind != JsonValueKind.Object)
            throw new JsonException($"{propertyName} must be an object.");
        foreach (JsonProperty property in value.EnumerateObject())
            result[property.Name] = ScalarText(property.Value);
        return result;
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
}
