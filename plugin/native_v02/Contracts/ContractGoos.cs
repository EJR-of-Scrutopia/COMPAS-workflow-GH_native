#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using GH_IO.Serialization;
using Grasshopper.Kernel.Types;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// Strict JSON-persisted Goo base. Runtime DTO instances are deep-cloned at
/// every public construction and duplication boundary so collection aliasing
/// cannot leak between Grasshopper wires or document branches.
/// </summary>
public abstract class ContractGoo<TContract> : GH_Goo<TContract>
    where TContract : ContractDto
{
    private const string StorageKey = "AnankeContractJson";
    private string? _readError;

    protected ContractGoo()
    {
    }

    protected ContractGoo(TContract value)
        : base(ContractJson.DeepClone(
            value ?? throw new ArgumentNullException(nameof(value))))
    {
    }

    protected abstract string ExpectedKind { get; }

    protected abstract ContractGoo<TContract> Create(TContract? value);

    protected abstract string Format(TContract value);

    public override bool IsValid => ValidationErrors().Count == 0;

    public override string IsValidWhyNot =>
        IsValid ? string.Empty : string.Join(" ", ValidationErrors());

    public override IGH_Goo Duplicate()
    {
        return Value is null
            ? Create(null)
            : Create(ContractJson.DeepClone(Value));
    }

    public override bool CastFrom(object source)
    {
        try
        {
            switch (source)
            {
                case TContract contract:
                    Value = ContractJson.DeepClone(contract);
                    _readError = null;
                    return IsValid;
                case ContractGoo<TContract> goo when goo.Value is not null:
                    Value = ContractJson.DeepClone(goo.Value);
                    _readError = null;
                    return IsValid;
                case string json when !string.IsNullOrWhiteSpace(json):
                    Value = ContractJson.Deserialize<TContract>(json);
                    _readError = null;
                    return IsValid;
                default:
                    return false;
            }
        }
        catch (Exception error) when (
            error is ArgumentException ||
            error is InvalidOperationException ||
            error is System.Text.Json.JsonException)
        {
            Value = null!;
            _readError = error.Message;
            return false;
        }
    }

    public override bool CastTo<Q>(ref Q target)
    {
        if (Value is null)
            return false;

        if (typeof(Q).IsAssignableFrom(typeof(TContract)))
        {
            object boxed = ContractJson.DeepClone(Value);
            target = (Q)boxed;
            return true;
        }

        if (typeof(Q) == typeof(string))
        {
            object boxed = ContractJson.Serialize(Value);
            target = (Q)boxed;
            return true;
        }

        return base.CastTo(ref target);
    }

    public override bool Write(GH_IWriter writer)
    {
        ArgumentNullException.ThrowIfNull(writer);
        try
        {
            writer.SetString(
                StorageKey,
                Value is null ? string.Empty : ContractJson.Serialize(Value));
            return true;
        }
        catch (Exception error) when (
            error is ArgumentException ||
            error is InvalidOperationException ||
            error is System.Text.Json.JsonException)
        {
            _readError = error.Message;
            return false;
        }
    }

    public override bool Read(GH_IReader reader)
    {
        ArgumentNullException.ThrowIfNull(reader);
        string json = string.Empty;
        if (!reader.TryGetString(StorageKey, ref json))
        {
            Value = null!;
            _readError = $"Missing Grasshopper archive item '{StorageKey}'.";
            return false;
        }

        if (string.IsNullOrWhiteSpace(json))
        {
            Value = null!;
            _readError = null;
            return true;
        }

        try
        {
            Value = ContractJson.Deserialize<TContract>(json);
            _readError = null;
            return true;
        }
        catch (Exception error) when (
            error is ArgumentException ||
            error is InvalidOperationException ||
            error is System.Text.Json.JsonException)
        {
            Value = null!;
            _readError = error.Message;
            return false;
        }
    }

    public override string ToString()
    {
        if (Value is null)
            return $"Empty {TypeName}";

        IReadOnlyList<string> errors = ValidationErrors();
        return errors.Count == 0
            ? Format(Value)
            : $"Invalid {TypeName}: {errors[0]}";
    }

    private IReadOnlyList<string> ValidationErrors()
    {
        var errors = new List<string>();
        if (!string.IsNullOrWhiteSpace(_readError))
            errors.Add(_readError);
        if (Value is null)
        {
            errors.Add($"{TypeName} has no payload.");
            return errors;
        }

        if (!string.Equals(Value.Kind, ExpectedKind, StringComparison.Ordinal))
        {
            errors.Add(
                $"Goo expects kind '{ExpectedKind}', received '{Value.Kind}'.");
        }

        errors.AddRange(Value.Validate());
        return errors.Distinct(StringComparer.Ordinal).ToArray();
    }

    protected static string ShortHash(string? value)
    {
        return string.IsNullOrWhiteSpace(value)
            ? "no hash"
            : value[..Math.Min(12, value.Length)];
    }
}

public sealed class TopologyGoo : ContractGoo<TopologyDto>
{
    public TopologyGoo()
    {
    }

    public TopologyGoo(TopologyDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.Topology;
    public override string TypeName => "Ananke Topology";
    public override string TypeDescription =>
        "A registered whole-object line or faced topology.";

    protected override ContractGoo<TopologyDto> Create(TopologyDto? value) =>
        value is null ? new TopologyGoo() : new TopologyGoo(value);

    protected override string Format(TopologyDto value) =>
        $"Topology · {value.NetworkKind} · " +
        $"{value.Vertices.Count}V/{value.Edges.Count}E/{value.Faces.Count}F · " +
        $"#{ShortHash(value.TopologyHash)}";
}

public sealed class SupportSetGoo : ContractGoo<SupportSetDto>
{
    public SupportSetGoo()
    {
    }

    public SupportSetGoo(SupportSetDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.SupportSet;
    public override string TypeName => "Ananke Support Set";
    public override string TypeDescription =>
        "Form-finding supports bound to one topology.";

    protected override ContractGoo<SupportSetDto> Create(SupportSetDto? value) =>
        value is null ? new SupportSetGoo() : new SupportSetGoo(value);

    protected override string Format(SupportSetDto value)
    {
        int count = Math.Max(value.NodeIds.Count, value.Points.Count);
        return $"Supports · {value.Mode} · {count} target(s) · " +
            $"#{ShortHash(value.TopologyHash)}";
    }
}

public sealed class LoadCaseGoo : ContractGoo<LoadCaseDto>
{
    public LoadCaseGoo()
    {
    }

    public LoadCaseGoo(LoadCaseDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.LoadCase;
    public override string TypeName => "Ananke Load Case";
    public override string TypeDescription =>
        "A named set of topology-bound form-finding loads.";

    protected override ContractGoo<LoadCaseDto> Create(LoadCaseDto? value) =>
        value is null ? new LoadCaseGoo() : new LoadCaseGoo(value);

    protected override string Format(LoadCaseDto value)
    {
        int targets = Math.Max(value.NodeIds.Count, value.Points.Count);
        return $"Load Case · {value.Name} · {value.Distribution} · " +
            $"{targets} target(s)";
    }
}

public sealed class EquilibriumProblemGoo :
    ContractGoo<EquilibriumProblemDto>
{
    public EquilibriumProblemGoo()
    {
    }

    public EquilibriumProblemGoo(EquilibriumProblemDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.EquilibriumProblem;
    public override string TypeName => "Ananke Equilibrium Problem";
    public override string TypeDescription =>
        "Topology, supports and load cases bundled for FD or TNA.";

    protected override ContractGoo<EquilibriumProblemDto> Create(
        EquilibriumProblemDto? value) =>
        value is null
            ? new EquilibriumProblemGoo()
            : new EquilibriumProblemGoo(value);

    protected override string Format(EquilibriumProblemDto value)
    {
        TopologyDto? topology = value.Topology;
        return topology is null
            ? $"Problem · {value.Name} · incomplete"
            : $"Problem · {value.Name} · {topology.NetworkKind} · " +
              $"{topology.Edges.Count} members · {value.LoadCases.Count} case(s)";
    }
}

public sealed class FDSettingsGoo : ContractGoo<FDSettingsDto>
{
    public FDSettingsGoo()
    {
    }

    public FDSettingsGoo(FDSettingsDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.FDSettings;
    public override string TypeName => "Ananke FD Settings";
    public override string TypeDescription =>
        "Force-density values and sign convention for an FD solve.";

    protected override ContractGoo<FDSettingsDto> Create(FDSettingsDto? value) =>
        value is null ? new FDSettingsGoo() : new FDSettingsGoo(value);

    protected override string Format(FDSettingsDto value)
    {
        string density = value.ForceDensities.Count == 1
            ? $"q={value.ForceDensities[0]:G6}"
            : $"{value.ForceDensities.Count} q values";
        return $"FD Settings · {density} · {value.SignConvention}";
    }
}

public sealed class DiagnosticGoo : ContractGoo<DiagnosticDto>
{
    public DiagnosticGoo()
    {
    }

    public DiagnosticGoo(DiagnosticDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.Diagnostic;
    public override string TypeName => "Ananke Diagnostic";
    public override string TypeDescription =>
        "One structured validation or solver diagnostic.";

    protected override ContractGoo<DiagnosticDto> Create(DiagnosticDto? value) =>
        value is null ? new DiagnosticGoo() : new DiagnosticGoo(value);

    protected override string Format(DiagnosticDto value) =>
        $"[{value.Severity.ToUpperInvariant()}] {value.Code}: {value.Message}";
}

public sealed class EquilibriumResultGoo :
    ContractGoo<EquilibriumResultDto>
{
    public EquilibriumResultGoo()
    {
    }

    public EquilibriumResultGoo(EquilibriumResultDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.EquilibriumResult;
    public override string TypeName => "Ananke Equilibrium Result";
    public override string TypeDescription =>
        "A complete immutable FD or TNA result with provenance.";

    protected override ContractGoo<EquilibriumResultDto> Create(
        EquilibriumResultDto? value) =>
        value is null
            ? new EquilibriumResultGoo()
            : new EquilibriumResultGoo(value);

    protected override string Format(EquilibriumResultDto value)
    {
        int warningCount = value.Diagnostics.Count(item =>
            item.Severity.Equals("warning", StringComparison.OrdinalIgnoreCase) ||
            item.Severity.Equals("error", StringComparison.OrdinalIgnoreCase));
        return $"{value.Solver.ToUpperInvariant()} Result · " +
            $"{value.Vertices.Count}V/{value.Edges.Count}E · " +
            $"{warningCount} warning(s) · #{ShortHash(value.TopologyHash)}";
    }
}
