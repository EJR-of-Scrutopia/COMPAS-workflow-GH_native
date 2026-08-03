#nullable enable

using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// One solved FD or TNA result carried in the unified worker envelope. The
/// reciprocal TNA block (form/force graphs, edge states, mappings, analysis
/// plane) is present only when <see cref="Solver"/> is "tna"; FD results
/// carry only <see cref="Equilibrium"/>.
/// </summary>
public sealed record ResultDto : ContractDto
{
    public ResultDto()
        : base(ContractKinds.Result)
    {
    }

    [JsonIgnore]
    public override string ExpectedKind => ContractKinds.Result;

    public string Solver { get; init; } = "tna";

    public string ResultSchema { get; init; } = "0.2";

    public EquilibriumResultDto? Equilibrium { get; init; }

    public TnaControlDto? Control { get; init; }

    public AnalysisPlaneDto? AnalysisPlane { get; init; }

    public TnaDiagramGraphDto? FormGraph { get; init; }

    public TnaDiagramGraphDto? ForceGraph { get; init; }

    public IReadOnlyList<TnaEdgeStateDto> EdgeStates { get; init; } =
        Array.Empty<TnaEdgeStateDto>();

    public double HorizontalScale { get; init; } = 1.0;

    public TnaMappingsDto? Mappings { get; init; }

    public IReadOnlyList<DiagnosticDto> Diagnostics { get; init; } =
        Array.Empty<DiagnosticDto>();

    public string Report { get; init; } = string.Empty;

    /// <summary>
    /// The spine problem this result was solved against. The worker never
    /// sends this; solver components attach it client-side so Deconstruct
    /// and Export can recover every upstream input from the result alone.
    /// </summary>
    public ProblemDto? Problem { get; init; }

    /// <summary>
    /// The worker's original result payload JSON, exactly as received
    /// (snake_case field names throughout, aside from the envelope's own
    /// <c>kind</c>/<c>solver</c>/<c>resultSchema</c> keys). Both decoders
    /// set this from the response root they already hold. Export forwards
    /// it verbatim to <c>export.compas</c> so the worker sees back the
    /// exact shape it produced, instead of a re-serialised
    /// <see cref="ResultDto"/> whose camelCase member names do not match
    /// the worker's own snake_case fields. <see cref="JsonIgnoreAttribute"/>
    /// keeps this out of Contract-mode serialisation and every other
    /// contract round trip; it is a transport artefact, not part of the
    /// native contract.
    /// </summary>
    [JsonIgnore]
    public string? RawWire { get; init; }

    protected override void ValidatePayload(List<string> errors)
    {
        string solver = (Solver ?? string.Empty).Trim().ToLowerInvariant();
        if (solver is not ("tna" or "fd"))
            errors.Add("solver must be 'tna' or 'fd'.");

        if (Equilibrium is null)
            errors.Add("equilibrium is missing.");

        if (solver == "tna")
        {
            if (FormGraph is null)
                errors.Add("formGraph is missing.");
            if (ForceGraph is null)
                errors.Add("forceGraph is missing.");
        }
    }
}

public sealed class ResultGoo : ContractGoo<ResultDto>
{
    public ResultGoo()
    {
    }

    public ResultGoo(ResultDto value)
        : base(value)
    {
    }

    protected override string ExpectedKind => ContractKinds.Result;
    public override string TypeName => "Ananke Result";
    public override string TypeDescription =>
        "A solved FD or TNA result carried in the unified Result envelope.";

    protected override ContractGoo<ResultDto> Create(ResultDto? value) =>
        value is null ? new ResultGoo() : new ResultGoo(value);

    protected override string Format(ResultDto value)
    {
        string solver = (value.Solver ?? string.Empty).ToUpperInvariant();
        return $"{solver} Result · #{ShortHash(value.Equilibrium?.TopologyHash)}";
    }
}

public sealed class ResultParam : ContractParam<ResultGoo>
{
    public ResultParam()
        : base(
            "Result",
            "RES",
            "A solved FD or TNA result carried in the unified Result envelope.")
    {
    }

    public override Guid ComponentGuid =>
        new("e2f634fe-b5c1-44ec-bcc2-09435d23fe9a");
}
