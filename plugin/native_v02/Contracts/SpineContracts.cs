#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Serialization;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// The shared spine that every native component after pattern-authoring
/// traffics in: a stable source pattern with the plan-relaxation supports
/// resolved to node IDs. Both the FD and TNA solvers consume this same
/// shape so a single canvas stage feeds either downstream path.
/// </summary>
public sealed record AnchoredPatternDto : ContractDto
{
    public AnchoredPatternDto()
        : base(ContractKinds.AnchoredPattern)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.AnchoredPattern;

    public TnaPatternDto? Pattern { get; init; }

    public IReadOnlyList<int> AnchorNodeIds { get; init; } = Array.Empty<int>();

    public double SnapTolerance { get; init; } = 1.0e-3;

    protected override void ValidatePayload(List<string> errors)
    {
        if (Pattern is null)
        {
            errors.Add("pattern is missing.");
        }
        else
        {
            ContractRules.AddNested(errors, "pattern", Pattern.Validate());
        }

        int vertexCount = Pattern?.Topology?.Vertices.Count ?? 0;
        if (AnchorNodeIds is null)
        {
            errors.Add("anchorNodeIds is missing.");
        }
        else
        {
            if (AnchorNodeIds.Count == 0)
                errors.Add("anchorNodeIds must contain at least one node ID.");
            if (AnchorNodeIds.Any(nodeId => nodeId < 0))
                errors.Add("anchorNodeIds cannot contain negative values.");
            if (AnchorNodeIds.Distinct().Count() != AnchorNodeIds.Count)
                errors.Add("anchorNodeIds contains duplicates.");
            if (Pattern?.Topology is not null &&
                AnchorNodeIds.Any(nodeId => nodeId >= vertexCount))
            {
                errors.Add("anchorNodeIds contains a node ID outside topology.");
            }
        }

        if (!ContractRules.IsFinite(SnapTolerance) || SnapTolerance <= 0.0)
            errors.Add("snapTolerance must be finite and greater than zero.");
    }
}

/// <summary>
/// One anchored pattern bundled with the load case it will be solved
/// against. Both members share the same source topology fingerprint so a
/// mismatched wire is caught before it reaches either solver.
/// </summary>
public sealed record ProblemDto : ContractDto
{
    public ProblemDto()
        : base(ContractKinds.Problem)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.Problem;

    public AnchoredPatternDto? Anchored { get; init; }

    public LoadCaseDto? Load { get; init; }

    protected override void ValidatePayload(List<string> errors)
    {
        if (Anchored is null)
            errors.Add("anchored is missing.");
        else
            ContractRules.AddNested(errors, "anchored", Anchored.Validate());

        if (Load is null)
        {
            errors.Add("load is missing.");
        }
        else
        {
            ContractRules.AddNested(errors, "load", Load.Validate());
            string? patternTopologyHash =
                Anchored?.Pattern?.Topology?.TopologyHash;
            if (patternTopologyHash is not null &&
                !string.Equals(
                    Load.TopologyHash,
                    patternTopologyHash,
                    StringComparison.OrdinalIgnoreCase))
            {
                errors.Add("load belongs to a different source topology.");
            }
        }
    }
}

/// <summary>
/// A relaxed plan-geometry stage paired with the problem it will be solved
/// against, so Deconstruct and Export can recover every upstream input at
/// this depth without a second wire back to the pattern stage.
/// </summary>
public sealed record RelaxedDto : ContractDto
{
    public RelaxedDto()
        : base(ContractKinds.Relaxed)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.Relaxed;

    public TnaPreparedDto? Prepared { get; init; }

    public ProblemDto? Problem { get; init; }

    protected override void ValidatePayload(List<string> errors)
    {
        if (Prepared is null)
            errors.Add("prepared is missing.");
        else
            ContractRules.AddNested(errors, "prepared", Prepared.Validate());

        if (Problem is null)
            errors.Add("problem is missing.");
        else
            ContractRules.AddNested(errors, "problem", Problem.Validate());
    }
}

public sealed class AnchoredPatternGoo : ContractGoo<AnchoredPatternDto>
{
    public AnchoredPatternGoo()
    {
    }

    public AnchoredPatternGoo(AnchoredPatternDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.AnchoredPattern;
    public override string TypeName => "Ananke Anchored Pattern";
    public override string TypeDescription =>
        "A source pattern with plan-relaxation supports resolved to node IDs.";

    protected override ContractGoo<AnchoredPatternDto> Create(
        AnchoredPatternDto? value) =>
        value is null ? new AnchoredPatternGoo() : new AnchoredPatternGoo(value);

    protected override string Format(AnchoredPatternDto value)
    {
        TopologyDto? topology = value.Pattern?.Topology;
        return topology is null
            ? "Anchored Pattern · incomplete"
            : $"Anchored Pattern · {topology.Vertices.Count}V/" +
              $"{topology.Edges.Count}E · {value.AnchorNodeIds.Count} anchor(s)";
    }
}

public sealed class ProblemGoo : ContractGoo<ProblemDto>
{
    public ProblemGoo()
    {
    }

    public ProblemGoo(ProblemDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.Problem;
    public override string TypeName => "Ananke Problem";
    public override string TypeDescription =>
        "An anchored pattern bundled with the load case to solve against it.";

    protected override ContractGoo<ProblemDto> Create(ProblemDto? value) =>
        value is null ? new ProblemGoo() : new ProblemGoo(value);

    protected override string Format(ProblemDto value)
    {
        TopologyDto? topology = value.Anchored?.Pattern?.Topology;
        string loadName = value.Load?.Name ?? "no load";
        return topology is null
            ? $"Problem · incomplete · {loadName}"
            : $"Problem · {topology.Edges.Count} members · {loadName}";
    }
}

public sealed class RelaxedGoo : ContractGoo<RelaxedDto>
{
    public RelaxedGoo()
    {
    }

    public RelaxedGoo(RelaxedDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.Relaxed;
    public override string TypeName => "Ananke Relaxed";
    public override string TypeDescription =>
        "A relaxed plan-geometry stage paired with the problem it solves.";

    protected override ContractGoo<RelaxedDto> Create(RelaxedDto? value) =>
        value is null ? new RelaxedGoo() : new RelaxedGoo(value);

    protected override string Format(RelaxedDto value)
    {
        int edges = value.Prepared?.Pattern.Edges.Count ?? 0;
        string loadName = value.Problem?.Load?.Name ?? "no load";
        return $"Relaxed · {edges} edges · {loadName}";
    }
}

public sealed class AnchoredPatternParam : ContractParam<AnchoredPatternGoo>
{
    public AnchoredPatternParam()
        : base(
            "Anchored Pattern",
            "SUP",
            "A source pattern with plan-relaxation supports resolved to " +
            "node IDs.")
    {
    }

    public override Guid ComponentGuid =>
        new("f92fa56c-aeeb-4bd3-b918-c90d3455650a");
}

public sealed class ProblemParam : ContractParam<ProblemGoo>
{
    public ProblemParam()
        : base(
            "Problem",
            "PRB",
            "An anchored pattern bundled with the load case to solve " +
            "against it.")
    {
    }

    public override Guid ComponentGuid =>
        new("2ccd3504-1ca3-41cb-91c9-bad39526d7ff");
}

public sealed class RelaxedParam : ContractParam<RelaxedGoo>
{
    public RelaxedParam()
        : base(
            "Relaxed",
            "RLX",
            "A relaxed plan-geometry stage paired with the problem it " +
            "solves.")
    {
    }

    public override Guid ComponentGuid =>
        new("66f5d655-0958-4b56-b258-07a732a9916d");
}
