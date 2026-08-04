#nullable enable

using System;
using System.Collections.Generic;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;

namespace Ananke.COMPAS.Native.Contracts;

/// <summary>
/// Hidden typed parameters used by native Ananke components. Persistent data
/// is supported for document serialization, while interactive prompting is
/// intentionally disabled because these contracts are built by components.
/// </summary>
public abstract class ContractParam<TGoo> : GH_PersistentParam<TGoo>
    where TGoo : class, IGH_Goo
{
    protected ContractParam(
        string name,
        string nickname,
        string description)
        : base(
            name,
            nickname,
            description,
            "Ananke COMPAS",
            "90 Parameters")
    {
    }

    public override GH_Exposure Exposure => GH_Exposure.hidden;

    protected override GH_GetterResult Prompt_Singular(ref TGoo value) =>
        GH_GetterResult.cancel;

    protected override GH_GetterResult Prompt_Plural(ref List<TGoo> values) =>
        GH_GetterResult.cancel;
}

public sealed class TopologyParam : ContractParam<TopologyGoo>
{
    public TopologyParam()
        : base(
            "Ananke Topology",
            "Topology",
            "A registered whole-object line or faced topology.")
    {
    }

    public override Guid ComponentGuid =>
        new("8243adc5-239f-4f6f-a9b2-3e2ff59e26d1");
}

public sealed class SupportSetParam : ContractParam<SupportSetGoo>
{
    public SupportSetParam()
        : base(
            "Ananke Support Set",
            "Supports",
            "Form-finding supports bound to one topology.")
    {
    }

    public override Guid ComponentGuid =>
        new("b33bd170-93ea-4070-aafb-5e1395c2789d");
}

public sealed class LoadCaseParam : ContractParam<LoadCaseGoo>
{
    public LoadCaseParam()
        : base(
            "Ananke Load Case",
            "Loads",
            "A named set of topology-bound form-finding loads.")
    {
    }

    public override Guid ComponentGuid =>
        new("7c0dd117-2c80-40ee-b515-2c17d8e105fc");
}

public sealed class DiagnosticParam : ContractParam<DiagnosticGoo>
{
    public DiagnosticParam()
        : base(
            "Ananke Diagnostic",
            "Diagnostic",
            "One structured solver or validation diagnostic.")
    {
    }

    public override Guid ComponentGuid =>
        new("b53722d4-c09e-4f37-b98b-ace25793cc33");
}

public sealed class TnaControlParam : ContractParam<TnaControlGoo>
{
    public TnaControlParam()
        : base(
            "Ananke TNA Control",
            "TNA Control",
            "Crown-height or force-scale controls for one TNA solve.")
    {
    }

    public override Guid ComponentGuid =>
        new("99e438f7-d28f-4198-a3f2-ff7ed98bf4c0");
}

