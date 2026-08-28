#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Native diagnostics written INTO the Result, so they travel forward and
/// Diagnose can read them back. Every entry names the component that
/// raised it in Provenance["source"] and carries a code namespaced by that
/// component in lower case (columns.lean, animate.anchors_isolated).
///
/// Numbers go in Value, Tolerance and Unit, never only inside the sentence,
/// so the prose stays readable and the number becomes graphable.
/// </summary>
internal static class ResultDiagnostics
{
    public const string SourceKey = "source";

    public static DiagnosticDto Entry(
        string source,
        string code,
        string severity,
        string message,
        double? value = null,
        double? tolerance = null,
        string unit = "",
        IReadOnlyDictionary<string, string>? context = null)
    {
        // A non-finite number is not a measurement. DiagnosticDto refuses it,
        // and the worker codecs throw on a refused entry, so drop it here
        // rather than let one NaN take a whole Result down.
        double? safeValue = value is double v && ContractRules.IsFinite(v) ? v : null;
        double? safeTolerance =
            tolerance is double t && ContractRules.IsFinite(t) && t >= 0.0 ? t : null;

        var entry = new DiagnosticDto
        {
            Code = code,
            Severity = severity,
            Message = message,
            Value = safeValue,
            Tolerance = safeTolerance,
            Unit = unit ?? string.Empty,
            Context = ContractData.FreezeStrings(context),
            Provenance = ContractData.FreezeStrings(
                new Dictionary<string, string> { [SourceKey] = source }),
        };
        IReadOnlyList<string> errors = entry.Validate();
        if (errors.Count > 0)
        {
            throw new InvalidOperationException(
                $"diagnostic {source}.{code} is invalid: {string.Join(" ", errors)}");
        }
        return entry;
    }

    public static string SourceOf(DiagnosticDto entry) =>
        entry.Provenance.TryGetValue(SourceKey, out string? source) &&
        !string.IsNullOrWhiteSpace(source)
            ? source
            : "worker";

    /// <summary>
    /// Replace one source's entries with these, keeping everything else in
    /// its existing order. Replace rather than append, so a component that
    /// runs twice on the same Result does not stack its own history.
    /// </summary>
    public static ResultDto Replace(
        ResultDto result,
        string source,
        IEnumerable<DiagnosticDto> entries)
    {
        var kept = result.Diagnostics
            .Where(d => !string.Equals(SourceOf(d), source, StringComparison.Ordinal))
            .ToList();
        kept.AddRange(entries);
        return result with { Diagnostics = kept.ToArray() };
    }

    public static IReadOnlyDictionary<string, string> Context(
        params (string Key, string Value)[] pairs)
    {
        var map = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach ((string key, string value) in pairs)
            map[key] = value;
        return ContractData.FreezeStrings(map);
    }
}
