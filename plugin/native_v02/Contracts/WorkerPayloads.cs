#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// Explicit boundary from versioned plugin contracts to the existing Python
/// worker protocol. Contract discriminators use <c>ananke.*</c>; the worker's
/// topology <c>kind</c> field instead receives <see cref="TopologyDto.NetworkKind"/>.
/// Keeping this translation explicit prevents the two meanings of "kind" from
/// being accidentally interchanged and avoids relying on CLR naming policy.
/// The C# topology hash is intentionally omitted: Python computes and binds
/// its own canonical topology fingerprint while decoding this payload.
/// </summary>
public static class WorkerPayloads
{
    public static IReadOnlyDictionary<string, object?> ToWorkerPayload(
        this TopologyDto value)
    {
        EnsureValid(value);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["kind"] = value.NetworkKind,
            ["vertices"] = value.Vertices.Select(Point).ToArray(),
            ["edges"] = value.Edges.Select(edge => new[] { edge.U, edge.V }).ToArray(),
            ["faces"] = value.Faces.Select(face => face.ToArray()).ToArray(),
            ["source_vertex_ids"] = value.SourceVertexIds.ToArray(),
            ["length_unit"] = value.LengthUnit,
            ["metadata"] = StringMap(value.Provenance)
        };
    }

    public static IReadOnlyDictionary<string, object?> ToWorkerPayload(
        this SupportSetDto value)
    {
        EnsureValid(value);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["mode"] = value.Mode,
            ["points"] = value.Points.Select(Point).ToArray(),
            ["node_ids"] = value.NodeIds.ToArray(),
            ["snap_tolerance"] = value.SnapTolerance,
            ["metadata"] = StringMap(value.Provenance)
        };
    }

    public static IReadOnlyDictionary<string, object?> ToWorkerPayload(
        this LoadCaseDto value)
    {
        EnsureValid(value);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["name"] = value.Name,
            ["distribution"] = value.Distribution,
            ["points"] = value.Points.Select(Point).ToArray(),
            ["node_ids"] = value.NodeIds.ToArray(),
            ["vectors"] = value.Vectors.Select(Point).ToArray(),
            ["base_vector"] = value.BaseVector is null ? null : Point(value.BaseVector),
            // Rule 2.4(a): the selfweight's two numbers cross as fields
            // of their own. The worker's decoder allowlists them by name,
            // so a rename on this side is a refused payload rather than a
            // silently ignored one.
            ["thickness"] = value.Thickness,
            ["density"] = value.Density,
            ["factor"] = value.Factor,
            ["coordinate_system"] = value.CoordinateSystem,
            ["metadata"] = StringMap(value.Provenance)
        };
    }

    /// <summary>
    /// Build the exact allowlisted payload accepted by the worker's
    /// <c>fd.solve</c> command.
    /// </summary>
    public static IReadOnlyDictionary<string, object?> ToFdSolvePayload(
        this EquilibriumProblemDto problem,
        FDSettingsDto settings,
        int loadCaseIndex = 0)
    {
        EnsureValid(problem);
        EnsureValid(settings);
        if (loadCaseIndex < 0 || loadCaseIndex >= problem.LoadCases.Count)
        {
            throw new ArgumentOutOfRangeException(
                nameof(loadCaseIndex),
                loadCaseIndex,
                $"Load-case index must be in 0..{problem.LoadCases.Count - 1}.");
        }

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["topology"] = problem.Topology!.ToWorkerPayload(),
            ["supports"] = problem.Supports!.ToWorkerPayload(),
            ["load_case"] = problem.LoadCases[loadCaseIndex].ToWorkerPayload(),
            ["settings"] = settings.ToWorkerPayload()
        };
    }

    public static IReadOnlyDictionary<string, object?> ToWorkerPayload(
        this EquilibriumProblemDto value)
    {
        EnsureValid(value);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["name"] = value.Name,
            ["topology"] = value.Topology!.ToWorkerPayload(),
            ["supports"] = value.Supports!.ToWorkerPayload(),
            ["load_cases"] = value.LoadCases
                .Select(loadCase => loadCase.ToWorkerPayload())
                .ToArray(),
            ["metadata"] = StringMap(value.Provenance)
        };
    }

    public static IReadOnlyDictionary<string, object?> ToWorkerPayload(
        this FDSettingsDto value)
    {
        EnsureValid(value);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["force_densities"] = value.ForceDensities.Count == 1
                ? value.ForceDensities[0]
                : value.ForceDensities.ToArray(),
            ["sign_convention"] = value.SignConvention,
            ["metadata"] = StringMap(value.Provenance)
        };
    }

    /// <summary>
    /// Build the exact allowlisted payload accepted by the worker's
    /// <c>tna.solve</c> command.
    /// </summary>
    public static IReadOnlyDictionary<string, object?> ToTnaSolvePayload(
        this EquilibriumProblemDto problem,
        TnaControlDto control,
        int loadCaseIndex = 0)
    {
        EnsureValid(problem);
        EnsureValid(control);
        if (loadCaseIndex < 0 || loadCaseIndex >= problem.LoadCases.Count)
        {
            throw new ArgumentOutOfRangeException(
                nameof(loadCaseIndex),
                loadCaseIndex,
                $"Load-case index must be in 0..{problem.LoadCases.Count - 1}.");
        }
        if (!string.Equals(
                problem.Topology?.NetworkKind,
                "faced",
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                "tna.solve requires a faced topology.");
        }

        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["topology"] = problem.Topology!.ToWorkerPayload(),
            ["supports"] = problem.Supports!.ToWorkerPayload(),
            ["load_case"] = problem.LoadCases[loadCaseIndex].ToWorkerPayload(),
            ["control"] = control.ToWorkerPayload()
        };
    }

    public static IReadOnlyDictionary<string, object?> ToWorkerPayload(
        this TnaControlDto value)
    {
        EnsureValid(value);
        return new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["height_control"] =
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["mode"] =
                        TnaControlDto.NormaliseHeightMode(value.HeightMode),
                    ["value"] = value.HeightValue,
                    ["metadata"] = new Dictionary<string, string>(
                        StringComparer.Ordinal)
                },
            ["settings"] =
                new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["horizontal_alpha"] = value.HorizontalAlpha,
                    ["horizontal_iterations"] =
                        value.HorizontalIterations,
                    ["horizontal_method"] = string.IsNullOrWhiteSpace(
                        value.HorizontalMethod)
                        ? "iterative"
                        : value.HorizontalMethod.Trim().ToLowerInvariant(),
                    ["vertical_iterations"] =
                        value.VerticalIterations,
                    ["tolerance"] = value.Tolerance,
                    ["metadata"] = new Dictionary<string, string>(
                        StringComparer.Ordinal)
                }
        };
    }

    public static string ToWorkerJson(
        this IReadOnlyDictionary<string, object?> payload)
    {
        ArgumentNullException.ThrowIfNull(payload);
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    private static double[] Point(Point3Dto value) =>
        new[] { value.X, value.Y, value.Z };

    private static IReadOnlyDictionary<string, string> StringMap(
        IReadOnlyDictionary<string, string> source)
    {
        var result = new SortedDictionary<string, string>(StringComparer.Ordinal);
        foreach (KeyValuePair<string, string> item in source)
            result[item.Key] = item.Value;
        return result;
    }

    private static void EnsureValid(ContractDto value)
    {
        ArgumentNullException.ThrowIfNull(value);
        IReadOnlyList<string> errors = value.Validate();
        if (errors.Count != 0)
        {
            throw new InvalidOperationException(
                $"{value.GetType().Name} cannot cross the worker boundary: " +
                string.Join(" ", errors));
        }
    }
}
