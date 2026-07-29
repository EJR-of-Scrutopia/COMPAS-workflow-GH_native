#nullable enable

using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// Version and kind identifiers written into every persisted contract.
/// </summary>
public static class ContractSchema
{
    public const string Current = "0.2";
}

public static class ContractKinds
{
    public const string Topology = "ananke.topology";
    public const string SupportSet = "ananke.support_set";
    public const string LoadCase = "ananke.load_case";
    public const string EquilibriumProblem = "ananke.equilibrium_problem";
    public const string FDSettings = "ananke.fd_settings";
    public const string TnaControl = "ananke.tna_control";
    public const string Diagnostic = "ananke.diagnostic";
    public const string EquilibriumResult = "ananke.equilibrium_result";
    public const string TnaResult = "ananke.tna_result";
    public const string GraphicDiagram = "ananke.graphic_diagram";
}

/// <summary>
/// Immutable-by-contract base for the JSON payloads stored in Grasshopper Goo.
/// Derived records expose init-only properties. Factory methods defensively
/// copy input collections before a payload is handed to Grasshopper.
/// </summary>
public abstract record ContractDto
{
    protected ContractDto(string kind)
    {
        Kind = kind;
    }

    [JsonRequired]
    public string SchemaVersion { get; init; } = ContractSchema.Current;

    [JsonRequired]
    public string Kind { get; init; }

    public IReadOnlyDictionary<string, string> Provenance { get; init; } =
        ContractData.EmptyStrings;

    [JsonIgnore]
    public abstract string ExpectedKind { get; }

    public IReadOnlyList<string> Validate()
    {
        var errors = new List<string>();
        if (!string.Equals(SchemaVersion, ContractSchema.Current, StringComparison.Ordinal))
        {
            errors.Add(
                $"Unsupported schema '{SchemaVersion ?? "<null>"}'; " +
                $"expected '{ContractSchema.Current}'.");
        }

        if (!string.Equals(Kind, ExpectedKind, StringComparison.Ordinal))
        {
            errors.Add(
                $"Contract kind '{Kind ?? "<null>"}' does not match " +
                $"'{ExpectedKind}'.");
        }

        ContractRules.ValidateStringMap(Provenance, "provenance", errors);
        ValidatePayload(errors);
        return errors;
    }

    protected abstract void ValidatePayload(List<string> errors);
}

/// <summary>
/// Shared System.Text.Json configuration for document persistence and worker
/// communication. It deliberately rejects named floating-point literals.
/// </summary>
public static class ContractJson
{
    public static JsonSerializerOptions Options { get; } = CreateOptions();

    public static string Serialize<TContract>(TContract value)
        where TContract : ContractDto
    {
        ArgumentNullException.ThrowIfNull(value);
        return JsonSerializer.Serialize(value, Options);
    }

    public static TContract Deserialize<TContract>(string json)
        where TContract : ContractDto
    {
        if (string.IsNullOrWhiteSpace(json))
            throw new JsonException("Contract JSON is empty.");

        TContract? value = JsonSerializer.Deserialize<TContract>(json, Options);
        return value ?? throw new JsonException(
            $"Contract JSON did not contain a {typeof(TContract).Name}.");
    }

    public static TContract DeepClone<TContract>(TContract value)
        where TContract : ContractDto
    {
        return Deserialize<TContract>(Serialize(value));
    }

    private static JsonSerializerOptions CreateOptions()
    {
        return new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            PropertyNameCaseInsensitive = false,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            NumberHandling = JsonNumberHandling.Strict,
            UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
            WriteIndented = false
        };
    }
}

/// <summary>
/// Canonical topology fingerprint independent of JSON property or dictionary
/// ordering. Vertex, edge and face order remain significant because they are
/// part of the source-to-solver mapping contract.
/// </summary>
public static class TopologyFingerprint
{
    public static string Compute(TopologyDto topology)
    {
        ArgumentNullException.ThrowIfNull(topology);
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);

        AppendString(hash, (topology.NetworkKind ?? string.Empty).Trim().ToLowerInvariant());
        AppendInt32(hash, topology.Vertices?.Count ?? -1);
        foreach (Point3Dto point in topology.Vertices ?? Array.Empty<Point3Dto>())
        {
            AppendDouble(hash, point.X);
            AppendDouble(hash, point.Y);
            AppendDouble(hash, point.Z);
        }

        AppendInt32(hash, topology.Edges?.Count ?? -1);
        foreach (EdgeDto edge in topology.Edges ?? Array.Empty<EdgeDto>())
        {
            AppendInt32(hash, edge.U);
            AppendInt32(hash, edge.V);
        }

        AppendInt32(hash, topology.Faces?.Count ?? -1);
        foreach (IReadOnlyList<int> face in topology.Faces ?? Array.Empty<IReadOnlyList<int>>())
        {
            AppendInt32(hash, face?.Count ?? -1);
            if (face is null)
                continue;
            foreach (int nodeId in face)
                AppendInt32(hash, nodeId);
        }

        AppendInt32(hash, topology.SourceVertexIds?.Count ?? -1);
        foreach (string sourceId in
                 topology.SourceVertexIds ?? Array.Empty<string>())
        {
            AppendString(hash, sourceId ?? string.Empty);
        }

        AppendInt32(hash, topology.SourceEdgeIds?.Count ?? -1);
        foreach (string sourceId in
                 topology.SourceEdgeIds ?? Array.Empty<string>())
        {
            AppendString(hash, sourceId ?? string.Empty);
        }

        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    public static bool IsSha256(string? value)
    {
        return value is { Length: 64 } &&
            value.All(character =>
                character is >= '0' and <= '9' ||
                character is >= 'a' and <= 'f' ||
                character is >= 'A' and <= 'F');
    }

    private static void AppendInt32(IncrementalHash hash, int value)
    {
        Span<byte> buffer = stackalloc byte[sizeof(int)];
        BinaryPrimitives.WriteInt32BigEndian(buffer, value);
        hash.AppendData(buffer);
    }

    private static void AppendDouble(IncrementalHash hash, double value)
    {
        Span<byte> buffer = stackalloc byte[sizeof(long)];
        BinaryPrimitives.WriteInt64BigEndian(buffer, BitConverter.DoubleToInt64Bits(value));
        hash.AppendData(buffer);
    }

    private static void AppendString(IncrementalHash hash, string value)
    {
        byte[] encoded = Encoding.UTF8.GetBytes(value);
        AppendInt32(hash, encoded.Length);
        hash.AppendData(encoded);
    }
}

internal static class ContractData
{
    public static IReadOnlyDictionary<string, string> EmptyStrings { get; } =
        new ReadOnlyDictionary<string, string>(
            new SortedDictionary<string, string>(StringComparer.Ordinal));

    public static IReadOnlyDictionary<string, string> FreezeStrings(
        IReadOnlyDictionary<string, string>? source)
    {
        var copy = new SortedDictionary<string, string>(StringComparer.Ordinal);
        if (source is not null)
        {
            foreach (KeyValuePair<string, string> item in source)
                copy[item.Key] = item.Value;
        }

        return new ReadOnlyDictionary<string, string>(copy);
    }
}

internal static class ContractRules
{
    public static bool IsFinite(double value) =>
        !double.IsNaN(value) && !double.IsInfinity(value);

    public static void ValidatePoint(Point3Dto? point, string label, List<string> errors)
    {
        if (point is null)
        {
            errors.Add($"{label} is missing.");
            return;
        }

        if (!IsFinite(point.X) || !IsFinite(point.Y) || !IsFinite(point.Z))
            errors.Add($"{label} contains a non-finite coordinate.");
    }

    public static void ValidateTopologyHash(
        string? value,
        string label,
        List<string> errors)
    {
        if (!TopologyFingerprint.IsSha256(value))
            errors.Add($"{label} must be a 64-character SHA-256 value.");
    }

    public static void ValidateStringMap(
        IReadOnlyDictionary<string, string>? values,
        string label,
        List<string> errors)
    {
        if (values is null)
        {
            errors.Add($"{label} is missing.");
            return;
        }

        foreach (KeyValuePair<string, string> item in values)
        {
            if (string.IsNullOrWhiteSpace(item.Key))
                errors.Add($"{label} contains an empty key.");
            if (item.Value is null)
                errors.Add($"{label}['{item.Key}'] has a null value.");
        }
    }

    public static void AddNested(
        List<string> errors,
        string prefix,
        IReadOnlyList<string> nested)
    {
        errors.AddRange(nested.Select(error => $"{prefix}: {error}"));
    }
}
