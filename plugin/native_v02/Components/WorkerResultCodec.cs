using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using Ananke.COMPAS.Native.Backend;
using Ananke.COMPAS.Native.Contracts;

namespace Ananke.COMPAS.Native.Components;

internal static class WorkerResultCodec
{
    public static EquilibriumResultDto DecodeFd(
        JsonElement root,
        EquilibriumProblemDto problem,
        FDSettingsDto settings,
        int loadCaseIndex)
    {
        if (root.ValueKind != JsonValueKind.Object)
            throw new JsonException("FD result must be a JSON object.");

        string schemaVersion = RequiredString(root, "schema_version");
        if (!string.Equals(
                schemaVersion,
                WorkerProtocol.CompatibleWorkerSchema,
                StringComparison.Ordinal))
        {
            throw new JsonException(
                $"FD result schema '{schemaVersion}' is not supported; "
                + $"expected '{WorkerProtocol.CompatibleWorkerSchema}'.");
        }

        string solver = RequiredString(root, "solver").ToLowerInvariant();
        if (solver != "fd")
            throw new JsonException($"Expected an FD result, received '{solver}'.");

        Point3Dto[] vertices = RequiredArray(root, "vertices")
            .EnumerateArray()
            .Select((value, index) => Point(value, $"vertices[{index}]"))
            .ToArray();
        EdgeDto[] edges = RequiredArray(root, "edges")
            .EnumerateArray()
            .Select((value, index) => Edge(value, $"edges[{index}]"))
            .ToArray();
        VerifyEdgeAlignment(edges, problem.Topology!.Edges);
        double[] forces = NumberArray(root, "member_forces");
        double[] densities = NumberArray(root, "force_densities");
        NodalVectorDto[] loads =
            NodalVectors(root, "loads", vertices);
        NodalVectorDto[] reactions =
            NodalVectors(root, "reactions", vertices);
        HashSet<int> reactionNodes = reactions
            .Select(item => item.NodeId)
            .ToHashSet();
        NodalVectorDto[] residuals =
            NodalVectors(root, "residuals", vertices)
                .Where(item => !reactionNodes.Contains(item.NodeId))
                .ToArray();
        DiagnosticDto[] diagnostics = Diagnostics(root);
        int[] resolvedSupportNodeIds =
            ResolvedSupportNodeIds(root, vertices.Length);

        LoadCaseDto loadCase = problem.LoadCases[loadCaseIndex];
        string forceUnit =
            loadCase.Provenance.TryGetValue("force_unit", out string? unit) &&
            !string.IsNullOrWhiteSpace(unit)
                ? unit
                : "kN";
        var solverSettings = new Dictionary<string, string>(
            StringComparer.Ordinal)
        {
            ["force_density_count"] =
                settings.ForceDensities.Count.ToString(
                    CultureInfo.InvariantCulture),
            ["force_densities"] = JsonSerializer.Serialize(
                settings.ForceDensities,
                ContractJson.Options),
            ["load_case_index"] =
                loadCaseIndex.ToString(CultureInfo.InvariantCulture),
            ["load_case_name"] = loadCase.Name
        };

        var provenance = new Dictionary<string, string>(
            StringComparer.Ordinal);
        if (root.TryGetProperty("provenance", out JsonElement provenanceJson) &&
            provenanceJson.ValueKind == JsonValueKind.Object)
        {
            foreach (JsonProperty property in provenanceJson.EnumerateObject())
                provenance[property.Name] = ScalarText(property.Value);
        }
        provenance["transport"] = "persistent-python-worker";

        var result = new EquilibriumResultDto
        {
            Solver = solver,
            Problem = problem,
            TopologyHash = problem.TopologyHash,
            Vertices = vertices,
            Edges = edges,
            MemberForces = forces,
            ForceDensities = densities,
            Loads = loads,
            Reactions = reactions,
            Residuals = residuals,
            Diagnostics = diagnostics,
            MemberSourceIds = problem.Topology.SourceEdgeIds.ToArray(),
            ResolvedSupportNodeIds = resolvedSupportNodeIds,
            LengthUnit = problem.Topology!.LengthUnit,
            ForceUnit = forceUnit,
            SignConvention = settings.SignConvention,
            SolverSettings = solverSettings,
            Report = OptionalString(root, "report"),
            Provenance = provenance
        };
        IReadOnlyList<string> errors = result.Validate();
        if (errors.Count > 0)
        {
            throw new JsonException(
                "The worker result failed its native contract: " +
                string.Join(" ", errors));
        }
        return result;
    }

    /// <summary>
    /// Decode a unified-envelope FD result (<c>kind == "Result"</c>,
    /// <c>solver == "fd"</c>) into <see cref="ResultDto"/>. FD payloads are
    /// flat: the envelope only adds the discriminator keys on top of the
    /// same solved-case shape <see cref="DecodeFd"/> already maps, so the
    /// flat-to-equilibrium mapping is reused as-is rather than duplicated;
    /// only the wrapping and the envelope check are new here.
    /// </summary>
    public static ResultDto DecodeResult(
        JsonElement root,
        EquilibriumProblemDto problem,
        FDSettingsDto settings,
        int loadCaseIndex)
    {
        if (root.ValueKind != JsonValueKind.Object)
            throw new JsonException("FD result must be a JSON object.");

        string kind = RequiredString(root, "kind");
        if (!string.Equals(kind, "Result", StringComparison.Ordinal))
            throw new JsonException($"Expected Result, received '{kind}'.");
        string resultSchema = RequiredString(root, "resultSchema");

        EquilibriumResultDto equilibrium = DecodeFd(
            root,
            problem,
            settings,
            loadCaseIndex);

        var result = new ResultDto
        {
            Solver = "fd",
            ResultSchema = resultSchema,
            Equilibrium = equilibrium,
            Diagnostics = equilibrium.Diagnostics,
            Report = equilibrium.Report,
            Provenance = equilibrium.Provenance,
            RawWire = root.GetRawText()
        };
        IReadOnlyList<string> resultErrors = result.Validate();
        if (resultErrors.Count > 0)
        {
            throw new JsonException(
                "The FD worker result failed its native contract: " +
                string.Join(" ", resultErrors));
        }
        return result;
    }

    private static void VerifyEdgeAlignment(
        IReadOnlyList<EdgeDto> solved,
        IReadOnlyList<EdgeDto> registered)
    {
        if (solved.Count != registered.Count)
        {
            throw new JsonException(
                "The worker returned a different member count than the " +
                "registered topology; source mappings are unsafe.");
        }
        for (int index = 0; index < solved.Count; index++)
        {
            if (solved[index].U != registered[index].U ||
                solved[index].V != registered[index].V)
            {
                throw new JsonException(
                    $"Worker edge {index} does not match the registered " +
                    "topology; source mappings are unsafe.");
            }
        }
    }

    private static JsonElement RequiredArray(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind != JsonValueKind.Array)
        {
            throw new JsonException(
                $"FD result requires array '{propertyName}'.");
        }
        return value;
    }

    private static string RequiredString(
        JsonElement root,
        string propertyName)
    {
        string value = OptionalString(root, propertyName);
        if (value.Length == 0)
            throw new JsonException(
                $"FD result requires string '{propertyName}'.");
        return value;
    }

    private static string OptionalString(
        JsonElement root,
        string propertyName)
    {
        return root.TryGetProperty(propertyName, out JsonElement value) &&
            value.ValueKind == JsonValueKind.String
                ? value.GetString() ?? string.Empty
                : string.Empty;
    }

    private static Point3Dto Point(JsonElement value, string label)
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

    private static EdgeDto Edge(JsonElement value, string label)
    {
        if (value.ValueKind != JsonValueKind.Array)
            throw new JsonException($"{label} must be an index pair.");
        int[] indices = value
            .EnumerateArray()
            .Select(item =>
            {
                if (!item.TryGetInt32(out int index))
                    throw new JsonException($"{label} contains a non-integer.");
                return index;
            })
            .ToArray();
        if (indices.Length != 2)
            throw new JsonException($"{label} must contain two node IDs.");
        return new EdgeDto(indices[0], indices[1]);
    }

    private static double[] NumberArray(
        JsonElement root,
        string propertyName)
    {
        return RequiredArray(root, propertyName)
            .EnumerateArray()
            .Select(value => FiniteDouble(value, propertyName))
            .ToArray();
    }

    private static int[] ResolvedSupportNodeIds(
        JsonElement root,
        int vertexCount)
    {
        if (!root.TryGetProperty("mappings", out JsonElement mappings) ||
            mappings.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException(
                "FD result requires object 'mappings'.");
        }

        JsonElement values = RequiredArray(
            mappings,
            "resolved_support_ids");
        int[] nodeIds = values
            .EnumerateArray()
            .Select(value =>
            {
                if (!value.TryGetInt32(out int nodeId))
                {
                    throw new JsonException(
                        "resolved_support_ids contains a non-integer.");
                }
                if (nodeId < 0 || nodeId >= vertexCount)
                {
                    throw new JsonException(
                        "resolved_support_ids contains a node ID outside " +
                        "the solved vertices.");
                }
                return nodeId;
            })
            .ToArray();
        if (nodeIds.Length == 0)
        {
            throw new JsonException(
                "resolved_support_ids must contain at least one support.");
        }
        if (nodeIds.Distinct().Count() != nodeIds.Length)
        {
            throw new JsonException(
                "resolved_support_ids contains duplicates.");
        }
        return nodeIds;
    }

    private static double FiniteDouble(JsonElement value, string label)
    {
        if (!value.TryGetDouble(out double number) || !double.IsFinite(number))
            throw new JsonException($"{label} contains a non-finite number.");
        return number;
    }

    private static NodalVectorDto[] NodalVectors(
        JsonElement root,
        string propertyName,
        IReadOnlyList<Point3Dto> vertices)
    {
        JsonElement values = RequiredArray(root, propertyName);
        var output = new List<NodalVectorDto>();
        int index = 0;
        foreach (JsonElement value in values.EnumerateArray())
        {
            if (index >= vertices.Count)
            {
                throw new JsonException(
                    $"{propertyName} contains more vectors than vertices.");
            }
            Point3Dto vector = Point(value, $"{propertyName}[{index}]");
            if (vector.X != 0.0 || vector.Y != 0.0 || vector.Z != 0.0)
            {
                output.Add(new NodalVectorDto(
                    index,
                    vertices[index],
                    vector));
            }
            index++;
        }
        if (index != 0 && index != vertices.Count)
        {
            throw new JsonException(
                $"{propertyName} must be empty or align with every vertex.");
        }
        return output.ToArray();
    }

    private static DiagnosticDto[] Diagnostics(JsonElement root)
    {
        if (!root.TryGetProperty("diagnostics", out JsonElement values) ||
            values.ValueKind != JsonValueKind.Array)
        {
            return Array.Empty<DiagnosticDto>();
        }

        var output = new List<DiagnosticDto>();
        int index = 0;
        foreach (JsonElement value in values.EnumerateArray())
        {
            if (value.ValueKind != JsonValueKind.Object)
                throw new JsonException($"diagnostics[{index}] must be an object.");
            var context = new Dictionary<string, string>(
                StringComparer.Ordinal);
            if (value.TryGetProperty("context", out JsonElement contextJson) &&
                contextJson.ValueKind == JsonValueKind.Object)
            {
                foreach (JsonProperty property in contextJson.EnumerateObject())
                    context[property.Name] = ScalarText(property.Value);
            }

            var diagnostic = new DiagnosticDto
            {
                Code = OptionalString(value, "code"),
                Severity = OptionalString(value, "severity"),
                Message = OptionalString(value, "message"),
                Value = OptionalNumber(value, "value"),
                Tolerance = OptionalNumber(value, "tolerance"),
                Unit = OptionalString(value, "unit"),
                Context = context,
                Provenance = new Dictionary<string, string>
                {
                    ["source"] = "COMPAS worker"
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

    private static double? OptionalNumber(
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

    private static string ScalarText(JsonElement value)
    {
        return value.ValueKind switch
        {
            JsonValueKind.String => value.GetString() ?? string.Empty,
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            JsonValueKind.Null => "null",
            _ => value.GetRawText()
        };
    }
}
