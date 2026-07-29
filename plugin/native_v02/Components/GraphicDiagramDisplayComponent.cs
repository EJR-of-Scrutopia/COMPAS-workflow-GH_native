#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Explicit native display boundary for renderer-neutral graphic-statics
/// bundles. The component draws its own styled viewport preview and exposes
/// ordinary Rhino lines for downstream Grasshopper operations.
/// </summary>
public sealed class GraphicDiagramDisplayComponent : NativeComponentBase
{
    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            1,
            "Graphic Style",
            new (string Label, string Value)[]
            {
                ("Analysis", "analysis"),
                ("Classical GS", "classical"),
                ("Monochrome", "monochrome")
            },
            "analysis")
    };

    private readonly List<DisplayEdge> _form = new();
    private readonly List<DisplayEdge> _thrust = new();
    private readonly List<DisplayEdge> _force = new();
    private readonly List<DisplayEdge> _loads = new();
    private readonly List<DisplayEdge> _reactions = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public GraphicDiagramDisplayComponent()
        : base(
            "Graphic Diagram Display",
            "GS Display",
            "Display a TNA graphic diagram with reliable native viewport " +
            "preview and extract its form, thrust, force, load, and reaction " +
            "lines as ordinary Rhino geometry.",
            ComponentCategories.GraphicStatics,
            "graphic_diagram_display")
    {
        // The component supplies the coloured/weighted preview itself.
        // Keeping these output previews hidden avoids drawing a second set of
        // default-green Grasshopper lines, while their data remains available
        // to every downstream component.
        for (int index = 0; index < Math.Min(5, Params.Output.Count); index++)
        {
            if (Params.Output[index] is IGH_PreviewObject preview)
                preview.Hidden = true;
        }
    }

    public override Guid ComponentGuid =>
        new("0c17dc94-a6f0-48b0-98fa-ab6766c64912");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new GraphicDiagramParam(),
            "Diagram",
            "D",
            "Renderer-neutral Graphic Diagram produced by TNA Reciprocal.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Style",
            "Style",
            "Analysis, Classical GS, or Monochrome viewport preset.",
            GH_ParamAccess.item,
            "analysis");
        parameters.AddBooleanParameter(
            "Show Form",
            "Form",
            "Show and output the planar form diagram.",
            GH_ParamAccess.item,
            true);
        parameters.AddBooleanParameter(
            "Show Thrust",
            "Thrust",
            "Show and output the spatial thrust network.",
            GH_ParamAccess.item,
            true);
        parameters.AddBooleanParameter(
            "Show Force",
            "Force",
            "Show and output the reciprocal force diagram.",
            GH_ParamAccess.item,
            true);
        parameters.AddBooleanParameter(
            "Show Loads",
            "Loads",
            "Show and output applied-load arrows.",
            GH_ParamAccess.item,
            true);
        parameters.AddBooleanParameter(
            "Show Reactions",
            "Reactions",
            "Show and output support-reaction arrows.",
            GH_ParamAccess.item,
            true);
        parameters.AddNumberParameter(
            "Weight Scale",
            "Weight",
            "Display-only multiplier for force-responsive line weights.",
            GH_ParamAccess.item,
            1.0);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddLineParameter(
            "Form Lines",
            "Form",
            "Visible planar form-diagram edges.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Thrust Lines",
            "Thrust",
            "Visible spatial thrust-network edges.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Force Lines",
            "Force",
            "Visible reciprocal force-diagram edges.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Load Lines",
            "Loads",
            "Visible applied-load vectors as Rhino lines.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Reaction Lines",
            "Reactions",
            "Visible support-reaction vectors as Rhino lines.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Report",
            "Report",
            "Display preset and visible geometry counts.",
            GH_ParamAccess.item);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _form.Clear();
        _thrust.Clear();
        _force.Clear();
        _loads.Clear();
        _reactions.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        GraphicDiagramGoo? diagramGoo = null;
        string style = "analysis";
        bool showForm = true;
        bool showThrust = true;
        bool showForce = true;
        bool showLoads = true;
        bool showReactions = true;
        double weightScale = 1.0;

        if (!data.GetData(0, ref diagramGoo) ||
            diagramGoo?.Value is not GraphicDiagramDto diagram)
        {
            return;
        }
        data.GetData(1, ref style);
        data.GetData(2, ref showForm);
        data.GetData(3, ref showThrust);
        data.GetData(4, ref showForce);
        data.GetData(5, ref showLoads);
        data.GetData(6, ref showReactions);
        data.GetData(7, ref weightScale);

        try
        {
            IReadOnlyList<string> errors = diagram.Validate();
            if (errors.Count > 0)
                throw new InvalidOperationException(string.Join(" ", errors));
            string stylePreset = NormaliseStyle(style);
            if (!double.IsFinite(weightScale) || weightScale <= 0.0)
            {
                throw new ArgumentException(
                    "Weight Scale must be finite and greater than zero.");
            }

            if (showForm)
                AddEdges(_form, diagram.FormEdges, "form", stylePreset, weightScale);
            if (showThrust)
            {
                AddEdges(
                    _thrust,
                    diagram.ThrustEdges,
                    "thrust",
                    stylePreset,
                    weightScale);
            }
            if (showForce)
            {
                AddEdges(
                    _force,
                    diagram.ForceEdges,
                    "force",
                    stylePreset,
                    weightScale);
            }
            if (showLoads)
            {
                AddEdges(
                    _loads,
                    diagram.LoadEdges,
                    "load",
                    stylePreset,
                    weightScale,
                    arrow: true);
            }
            if (showReactions)
            {
                AddEdges(
                    _reactions,
                    diagram.ReactionEdges,
                    "reaction",
                    stylePreset,
                    weightScale,
                    arrow: true);
            }

            DisplayEdge[] all = _form
                .Concat(_thrust)
                .Concat(_force)
                .Concat(_loads)
                .Concat(_reactions)
                .ToArray();
            Point3d[] points = all
                .SelectMany(edge => new[] { edge.Line.From, edge.Line.To })
                .ToArray();
            _clippingBox = points.Length == 0
                ? BoundingBox.Empty
                : new BoundingBox(points);

            data.SetDataList(0, _form.Select(edge => edge.Line));
            data.SetDataList(1, _thrust.Select(edge => edge.Line));
            data.SetDataList(2, _force.Select(edge => edge.Line));
            data.SetDataList(3, _loads.Select(edge => edge.Line));
            data.SetDataList(4, _reactions.Select(edge => edge.Line));
            string report =
                $"Graphic display · {stylePreset} · " +
                $"form {_form.Count}, thrust {_thrust.Count}, " +
                $"force {_force.Count}, loads {_loads.Count}, " +
                $"reactions {_reactions.Count}";
            data.SetData(5, report);
            Message = $"{stylePreset} · {all.Length}";
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Graphic Diagram Display failed", error);
        }
    }

    public override void DrawViewportWires(IGH_PreviewArgs args)
    {
        base.DrawViewportWires(args);
        Draw(args, _form);
        Draw(args, _thrust);
        Draw(args, _force);
        Draw(args, _loads);
        Draw(args, _reactions);
    }

    private static void AddEdges(
        ICollection<DisplayEdge> target,
        IReadOnlyList<GraphicEdgeDto> edges,
        string role,
        string style,
        double weightScale,
        bool arrow = false)
    {
        double maximum = edges
            .Select(edge => Math.Abs(edge.Magnitude))
            .DefaultIfEmpty(0.0)
            .Max();
        foreach (GraphicEdgeDto edge in edges)
        {
            double normalised = maximum > 0.0
                ? Math.Abs(edge.Magnitude) / maximum
                : 0.0;
            double rawWeight = role is "load" or "reaction"
                ? 2.0
                : role == "form"
                    ? 1.0 + 4.0 * normalised
                    : 1.0 + 5.0 * normalised;
            int weight = Math.Clamp(
                (int)Math.Round(rawWeight * weightScale),
                1,
                12);
            target.Add(
                new DisplayEdge(
                    new Line(Point(edge.Start), Point(edge.End)),
                    RoleColour(role, edge.ForceState, style),
                    weight,
                    arrow));
        }
    }

    private static void Draw(
        IGH_PreviewArgs args,
        IEnumerable<DisplayEdge> edges)
    {
        foreach (DisplayEdge edge in edges)
        {
            if (edge.Arrow)
                args.Display.DrawArrow(edge.Line, edge.Colour);
            else
                args.Display.DrawLine(edge.Line, edge.Colour, edge.Weight);
        }
    }

    private static Color RoleColour(
        string role,
        string forceState,
        string style)
    {
        if (style == "monochrome")
        {
            return role switch
            {
                "form" => Color.FromArgb(65, 65, 65),
                "load" or "reaction" => Color.FromArgb(105, 105, 105),
                _ => Color.FromArgb(25, 25, 25)
            };
        }

        if (style == "classical")
        {
            return role switch
            {
                "form" or "thrust" => Color.FromArgb(30, 30, 30),
                "force" => Color.FromArgb(35, 95, 210),
                "load" => Color.FromArgb(238, 135, 35),
                "reaction" => Color.FromArgb(35, 155, 75),
                _ => Color.FromArgb(105, 105, 105)
            };
        }

        return role switch
        {
            "form" => Color.FromArgb(105, 105, 105),
            "load" => Color.FromArgb(238, 135, 35),
            "reaction" => Color.FromArgb(35, 155, 75),
            _ => StateColour(forceState)
        };
    }

    private static Color StateColour(string state) =>
        (state ?? string.Empty).Trim().ToLowerInvariant() switch
        {
            "compression" => Color.FromArgb(35, 95, 210),
            "tension" => Color.FromArgb(210, 45, 45),
            "zero" => Color.FromArgb(125, 125, 125),
            _ => Color.FromArgb(35, 155, 75)
        };

    private static string NormaliseStyle(string? value)
    {
        string style = (value ?? string.Empty)
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_", StringComparison.Ordinal)
            .Replace("-", "_", StringComparison.Ordinal);
        return style switch
        {
            "" => "analysis",
            "classical_gs" or "graphic_statics" => "classical",
            "mono" => "monochrome",
            "analysis" or "classical" or "monochrome" => style,
            _ => throw new ArgumentException(
                "Style must be Analysis, Classical GS, or Monochrome.")
        };
    }

    private static Point3d Point(Point3Dto value) =>
        new(value.X, value.Y, value.Z);

    private sealed record DisplayEdge(
        Line Line,
        Color Colour,
        int Weight,
        bool Arrow);
}
