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

public sealed class EquilibriumProblemParam :
    ContractParam<EquilibriumProblemGoo>
{
    public EquilibriumProblemParam()
        : base(
            "Ananke Equilibrium Problem",
            "Problem",
            "Topology, supports and loads bundled for FD or TNA.")
    {
    }

    public override Guid ComponentGuid =>
        new("d1e37db4-1afd-4656-b946-edcb6bd83c0b");
}

public sealed class FDSettingsParam : ContractParam<FDSettingsGoo>
{
    public FDSettingsParam()
        : base(
            "Ananke FD Settings",
            "FD Settings",
            "Force-density values and sign convention.")
    {
    }

    public override Guid ComponentGuid =>
        new("f24994b8-5cf1-475b-b876-fa590dd46abf");
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

public sealed class EquilibriumResultParam :
    ContractParam<EquilibriumResultGoo>
{
    public EquilibriumResultParam()
        : base(
            "Ananke Equilibrium Result",
            "Result",
            "A complete immutable FD or TNA result with provenance.")
    {
    }

    public override Guid ComponentGuid =>
        new("fbbfa975-0b0d-4362-8bce-7636b7be1c40");
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

public sealed class TnaResultParam : ContractParam<TnaResultGoo>
{
    public TnaResultParam()
        : base(
            "Ananke TNA Result",
            "TNA Result",
            "A solved thrust network with reciprocal form and force diagrams.")
    {
    }

    public override Guid ComponentGuid =>
        new("28312b79-af59-4f56-9536-5a0ff81e07e4");
}

public sealed class GraphicDiagramParam :
    ContractParam<GraphicDiagramGoo>
{
    public GraphicDiagramParam()
        : base(
            "Ananke Graphic Diagram",
            "Graphic Diagram",
            "A compact renderer-neutral graphic-statics diagram bundle.")
    {
    }

    public override Guid ComponentGuid =>
        new("fb4e1d1c-caf6-44f0-9e58-b499ae25d64c");
}
