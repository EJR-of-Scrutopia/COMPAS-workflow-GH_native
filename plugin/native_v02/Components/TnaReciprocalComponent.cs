#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

internal static class TnaGraphicDiagramFactory
{
    public static GraphicDiagramDto Build(
        TnaResultDto result,
        string layout,
        string displayMetric,
        double displayForceScale,
        double vectorScale,
        double gapRatio)
    {
        ArgumentNullException.ThrowIfNull(result);
        IReadOnlyList<string> errors = result.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
        string layoutMode = NormaliseLayout(layout);
        if (layoutMode is not ("side_by_side" or "overlay"))
            throw new ArgumentException("Layout must be Side by Side or Overlay.");
        string metric = NormaliseMetric(displayMetric);
        if (metric is not (
                "natural" or
                "force_density" or
                "horizontal_force" or
                "axial_force"))
        {
            throw new ArgumentException(
                "Metric must be Natural, Force Density, Horizontal Force, " +
                "or Axial Force.");
        }
        if (!double.IsFinite(displayForceScale) || displayForceScale <= 0.0)
        {
            throw new ArgumentException(
                "Force Scale must be finite and greater than zero.");
        }
        if (!double.IsFinite(vectorScale) || vectorScale <= 0.0)
        {
            throw new ArgumentException(
                "Vector Scale must be finite and greater than zero.");
        }
        if (!double.IsFinite(gapRatio) || gapRatio < 0.0)
        {
            throw new ArgumentException(
                "Gap Ratio must be finite and non-negative.");
        }

        var stateByForm = result.EdgeStates.ToDictionary(
            state => state.FormEdgeId);
        var stateByForce = result.EdgeStates.ToDictionary(
            state => state.ForceEdgeId);
        var formVertices = result.FormGraph.Vertices.ToDictionary(
            vertex => vertex.Id,
            vertex => vertex.Point);
        var forceVertices = result.ForceGraph.Vertices.ToDictionary(
            vertex => vertex.Id,
            vertex => vertex.Point);
        EquilibriumResultDto equilibrium = result.Equilibrium!;

        GraphicEdgeDto[] thrustEdges = result.EdgeStates
            .Select(state =>
            {
                EdgeDto edge = equilibrium.Edges[state.EquilibriumEdgeId];
                return GraphicEdge(
                    state.Id,
                    "thrust",
                    equilibrium.Vertices[edge.U],
                    equilibrium.Vertices[edge.V],
                    DisplayMagnitude(state, "thrust", metric),
                    state);
            })
            .ToArray();
        GraphicEdgeDto[] formEdges = result.FormGraph.Edges
            .Select(edge =>
            {
                if (!stateByForm.TryGetValue(
                        edge.Id,
                        out TnaEdgeStateDto? state))
                {
                    throw new InvalidOperationException(
                        $"Form edge {edge.Id} has no reciprocal state.");
                }
                return GraphicEdge(
                    edge.Id,
                    "form",
                    formVertices[edge.U],
                    formVertices[edge.V],
                    DisplayMagnitude(state, "form", metric),
                    state);
            })
            .ToArray();

        PlaneFrame frame = PlaneFrame.Create(result.AnalysisPlane);
        Bounds2 formBounds = Bounds2.From(
            formVertices.Values.Select(frame.Project));
        (Dictionary<int, Point3Dto> forceDisplay, Point3Dto offset) =
            LayoutForceGraph(
                forceVertices,
                frame,
                formBounds,
                layoutMode,
                result.HorizontalScale * displayForceScale,
                gapRatio);
        GraphicEdgeDto[] forceEdges = result.ForceGraph.Edges
            .Select(edge =>
            {
                if (!stateByForce.TryGetValue(
                        edge.Id,
                        out TnaEdgeStateDto? state))
                {
                    throw new InvalidOperationException(
                        $"Force edge {edge.Id} has no reciprocal state.");
                }
                return GraphicEdge(
                    edge.Id,
                    "force",
                    forceDisplay[edge.U],
                    forceDisplay[edge.V],
                    DisplayMagnitude(state, "force", metric),
                    state);
            })
            .ToArray();
        GraphicEdgeDto[] loadEdges = result.Mappings.Loads
            .Select((item, index) => ExternalEdge(
                index,
                "load",
                equilibrium.Vertices[item.EquilibriumVertexId],
                item.Vector,
                vectorScale))
            .Where(edge => edge.Magnitude > 0.0)
            .ToArray();
        GraphicEdgeDto[] reactionEdges = result.Mappings.Reactions
            .Select((item, index) => ExternalEdge(
                index,
                "reaction",
                equilibrium.Vertices[item.EquilibriumVertexId],
                item.Reaction,
                vectorScale))
            .Where(edge => edge.Magnitude > 0.0)
            .ToArray();

        var diagram = new GraphicDiagramDto
        {
            TopologyHash = equilibrium.TopologyHash,
            AnalysisPlane = result.AnalysisPlane,
            Layout = layoutMode,
            ForceDiagramOffset = offset,
            DisplayForceScale = displayForceScale,
            DisplayMetric = metric,
            VectorScale = vectorScale,
            HorizontalScale = result.HorizontalScale,
            ThrustEdges = thrustEdges,
            FormEdges = formEdges,
            ForceEdges = forceEdges,
            LoadEdges = loadEdges,
            ReactionEdges = reactionEdges,
            Report =
                $"TNA reciprocal · {formEdges.Length} form ↔ " +
                $"{forceEdges.Length} force ↔ {thrustEdges.Length} thrust edges",
            Provenance = new Dictionary<string, string>
            {
                ["source"] = "TNA Reciprocal",
                ["load_case_name"] =
                    equilibrium.SolverSettings.TryGetValue(
                        "load_case_name",
                        out string? name)
                            ? name
                            : string.Empty
            }
        };
        IReadOnlyList<string> diagramErrors = diagram.Validate();
        if (diagramErrors.Count > 0)
        {
            throw new InvalidOperationException(
                "Graphic diagram is invalid: " +
                string.Join(" ", diagramErrors));
        }
        return diagram;
    }

    public static string NormaliseMetric(string? value)
    {
        string metric = (value ?? string.Empty)
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_", StringComparison.Ordinal)
            .Replace("-", "_", StringComparison.Ordinal);
        return metric switch
        {
            "" => "natural",
            "q" or "density" => "force_density",
            "h" or "horizontal" => "horizontal_force",
            "f" or "axial" => "axial_force",
            _ => metric
        };
    }

    public static string NormaliseLayout(string? value)
    {
        string layout = (value ?? string.Empty)
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_", StringComparison.Ordinal);
        return layout switch
        {
            "side-by-side" or "sidebyside" => "side_by_side",
            _ => layout
        };
    }

    private static GraphicEdgeDto GraphicEdge(
        int id,
        string role,
        Point3Dto start,
        Point3Dto end,
        double magnitude,
        TnaEdgeStateDto state) =>
        new()
        {
            Id = id,
            Role = role,
            Start = start,
            End = end,
            Magnitude = magnitude,
            ForceDensity = state.ForceDensity,
            HorizontalForce = state.HorizontalForce,
            AxialForce = state.AxialForce,
            ForceState = state.ForceState,
            EquilibriumEdgeId = state.EquilibriumEdgeId,
            FormEdgeId = state.FormEdgeId,
            ForceEdgeId = state.ForceEdgeId,
            SourceEdgeIds = state.SourceEdgeIds.ToArray()
        };

    private static GraphicEdgeDto ExternalEdge(
        int id,
        string role,
        Point3Dto start,
        Point3Dto vector,
        double vectorScale)
    {
        double magnitude = Math.Sqrt(
            vector.X * vector.X +
            vector.Y * vector.Y +
            vector.Z * vector.Z);
        return new GraphicEdgeDto
        {
            Id = id,
            Role = role,
            Start = start,
            End = new Point3Dto(
                start.X + vectorScale * vector.X,
                start.Y + vectorScale * vector.Y,
                start.Z + vectorScale * vector.Z),
            Magnitude = magnitude,
            ForceState = "external"
        };
    }

    private static double DisplayMagnitude(
        TnaEdgeStateDto state,
        string role,
        string metric) =>
        metric switch
        {
            "force_density" => Math.Abs(state.ForceDensity),
            "horizontal_force" => Math.Abs(state.HorizontalForce),
            "axial_force" => Math.Abs(state.AxialForce),
            _ => role == "thrust"
                ? Math.Abs(state.AxialForce)
                : Math.Abs(state.HorizontalForce)
        };

    private static (
        Dictionary<int, Point3Dto> Points,
        Point3Dto Offset)
        LayoutForceGraph(
            IReadOnlyDictionary<int, Point3Dto> source,
            PlaneFrame frame,
            Bounds2 formBounds,
            string layout,
            double scale,
            double gapRatio)
    {
        Dictionary<int, LocalPoint> local = source.ToDictionary(
            item => item.Key,
            item => frame.Project(item.Value));
        Bounds2 rawBounds = Bounds2.From(local.Values);
        LocalPoint centre = rawBounds.Centre;
        Dictionary<int, LocalPoint> scaled = local.ToDictionary(
            item => item.Key,
            item => centre + scale * (item.Value - centre));
        Bounds2 scaledBounds = Bounds2.From(scaled.Values);
        double reference = Math.Max(
            Math.Max(formBounds.Width, formBounds.Height),
            Math.Max(scaledBounds.Width, scaledBounds.Height));
        if (reference <= 1.0e-12)
            reference = 1.0;

        double dx;
        double dy;
        if (layout == "overlay")
        {
            dx = formBounds.Centre.X - scaledBounds.Centre.X;
            dy = formBounds.Centre.Y - scaledBounds.Centre.Y;
        }
        else
        {
            dx =
                formBounds.MaximumX -
                scaledBounds.MinimumX +
                gapRatio * reference;
            dy = formBounds.Centre.Y - scaledBounds.Centre.Y;
        }
        var offset = new LocalPoint(dx, dy, 0.0);
        Dictionary<int, Point3Dto> display = scaled.ToDictionary(
            item => item.Key,
            item => frame.Unproject(item.Value + offset));
        return (display, frame.Vector(offset));
    }

    private readonly record struct LocalPoint(double X, double Y, double Z)
    {
        public static LocalPoint operator +(LocalPoint a, LocalPoint b) =>
            new(a.X + b.X, a.Y + b.Y, a.Z + b.Z);

        public static LocalPoint operator -(LocalPoint a, LocalPoint b) =>
            new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);

        public static LocalPoint operator *(double scale, LocalPoint value) =>
            new(scale * value.X, scale * value.Y, scale * value.Z);
    }

    private readonly record struct Bounds2(
        double MinimumX,
        double MinimumY,
        double MaximumX,
        double MaximumY)
    {
        public double Width => MaximumX - MinimumX;
        public double Height => MaximumY - MinimumY;
        public LocalPoint Centre => new(
            0.5 * (MinimumX + MaximumX),
            0.5 * (MinimumY + MaximumY),
            0.0);

        public static Bounds2 From(IEnumerable<LocalPoint> values)
        {
            LocalPoint[] points = values.ToArray();
            if (points.Length == 0)
                throw new InvalidOperationException("Diagram has no vertices.");
            return new Bounds2(
                points.Min(point => point.X),
                points.Min(point => point.Y),
                points.Max(point => point.X),
                points.Max(point => point.Y));
        }
    }

    private readonly record struct PlaneFrame(
        Point3Dto Origin,
        Point3Dto XAxis,
        Point3Dto YAxis,
        Point3Dto ZAxis)
    {
        public static PlaneFrame Create(AnalysisPlaneDto plane)
        {
            Point3Dto x = Unit(plane.XAxis, "analysis plane X axis");
            Point3Dto z = Unit(Cross(x, plane.YAxis), "analysis plane normal");
            Point3Dto y = Unit(Cross(z, x), "analysis plane Y axis");
            return new PlaneFrame(plane.Origin, x, y, z);
        }

        public LocalPoint Project(Point3Dto point)
        {
            Point3Dto delta = Subtract(point, Origin);
            return new LocalPoint(
                Dot(delta, XAxis),
                Dot(delta, YAxis),
                Dot(delta, ZAxis));
        }

        public Point3Dto Unproject(LocalPoint point) =>
            new(
                Origin.X +
                point.X * XAxis.X +
                point.Y * YAxis.X +
                point.Z * ZAxis.X,
                Origin.Y +
                point.X * XAxis.Y +
                point.Y * YAxis.Y +
                point.Z * ZAxis.Y,
                Origin.Z +
                point.X * XAxis.Z +
                point.Y * YAxis.Z +
                point.Z * ZAxis.Z);

        public Point3Dto Vector(LocalPoint point) =>
            new(
                point.X * XAxis.X + point.Y * YAxis.X + point.Z * ZAxis.X,
                point.X * XAxis.Y + point.Y * YAxis.Y + point.Z * ZAxis.Y,
                point.X * XAxis.Z + point.Y * YAxis.Z + point.Z * ZAxis.Z);

        private static Point3Dto Unit(Point3Dto value, string label)
        {
            double length = Math.Sqrt(Dot(value, value));
            if (!double.IsFinite(length) || length <= 1.0e-12)
                throw new InvalidOperationException($"{label} is invalid.");
            return new Point3Dto(
                value.X / length,
                value.Y / length,
                value.Z / length);
        }

        private static Point3Dto Cross(Point3Dto a, Point3Dto b) =>
            new(
                a.Y * b.Z - a.Z * b.Y,
                a.Z * b.X - a.X * b.Z,
                a.X * b.Y - a.Y * b.X);

        private static Point3Dto Subtract(Point3Dto a, Point3Dto b) =>
            new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);

        private static double Dot(Point3Dto a, Point3Dto b) =>
            a.X * b.X + a.Y * b.Y + a.Z * b.Z;
    }
}

public sealed class TnaReciprocalComponent : NativeComponentBase
{
    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            1,
            "Diagram Layout",
            new (string Label, string Value)[]
            {
                ("Side by Side", "side_by_side"),
                ("Overlay", "overlay")
            },
            "side_by_side"),
        new(
            2,
            "Display Metric",
            new (string Label, string Value)[]
            {
                ("Natural F / H", "natural"),
                ("Force Density q", "force_density"),
                ("Horizontal Force H", "horizontal_force"),
                ("Axial Force F", "axial_force")
            },
            "natural")
    };

    private readonly List<PreviewEdge> _thrust = new();
    private readonly List<PreviewEdge> _form = new();
    private readonly List<PreviewEdge> _force = new();
    private readonly List<PreviewEdge> _loads = new();
    private readonly List<PreviewEdge> _reactions = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaReciprocalComponent()
        : base(
            "TNA Reciprocal",
            "TNA Reciprocal",
            "Preview the planar form, spatial thrust, physically scaled " +
            "reciprocal force diagram, and mapped load/reaction vectors.",
            ComponentCategories.GraphicStatics,
            "tna_reciprocal")
    {
    }

    public override Guid ComponentGuid =>
        new("30aa4b56-6d9e-47dd-8b15-94a56a046cf6");

    public override BoundingBox ClippingBox => _clippingBox;

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaResultParam(),
            "TNA Result",
            "R",
            "Solved thrust network with reciprocal form/force correspondence.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Layout",
            "Layout",
            "Side by Side offsets the force diagram; Overlay aligns diagram centres.",
            GH_ParamAccess.item,
            "side_by_side");
        parameters.AddTextParameter(
            "Metric",
            "Metric",
            "Line-weight metric: Natural F/H, Force Density q, " +
            "Horizontal Force H, or Axial Force F.",
            GH_ParamAccess.item,
            "natural");
        parameters.AddNumberParameter(
            "Force Scale",
            "FS",
            "Display scale applied after the physical TNA horizontal-force scale.",
            GH_ParamAccess.item,
            1.0);
        parameters.AddNumberParameter(
            "Vector Scale",
            "VS",
            "Display-only scale for applied-load and support-reaction vectors.",
            GH_ParamAccess.item,
            1.0);
        parameters.AddNumberParameter(
            "Gap Ratio",
            "Gap",
            "Side-by-side gap as a fraction of the larger diagram span.",
            GH_ParamAccess.item,
            0.15);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new GraphicDiagramParam(),
            "Diagram",
            "D",
            "One compact graphic-statics bundle with mapped thrust/form/force " +
            "edges and external vectors.",
            GH_ParamAccess.item);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _thrust.Clear();
        _form.Clear();
        _force.Clear();
        _loads.Clear();
        _reactions.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TnaResultGoo? resultGoo = null;
        string layout = "side_by_side";
        string metric = "natural";
        double forceScale = 1.0;
        double vectorScale = 1.0;
        double gapRatio = 0.15;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not TnaResultDto result)
        {
            return;
        }
        data.GetData(1, ref layout);
        data.GetData(2, ref metric);
        data.GetData(3, ref forceScale);
        data.GetData(4, ref vectorScale);
        data.GetData(5, ref gapRatio);

        try
        {
            GraphicDiagramDto diagram = TnaGraphicDiagramFactory.Build(
                result,
                layout,
                metric,
                forceScale,
                vectorScale,
                gapRatio);
            _thrust.AddRange(ToPreview(diagram.ThrustEdges, "thrust"));
            _form.AddRange(ToPreview(diagram.FormEdges, "form"));
            _force.AddRange(ToPreview(diagram.ForceEdges, "force"));
            _loads.AddRange(ToPreview(diagram.LoadEdges, "load"));
            _reactions.AddRange(ToPreview(
                diagram.ReactionEdges,
                "reaction"));
            Point3d[] points = _thrust
                .Concat(_form)
                .Concat(_force)
                .Concat(_loads)
                .Concat(_reactions)
                .SelectMany(edge => new[]
                {
                    edge.Line.From,
                    edge.Line.To
                })
                .ToArray();
            _clippingBox = points.Length == 0
                ? BoundingBox.Empty
                : new BoundingBox(points);

            Message =
                $"{diagram.FormEdges.Count} ↔ {diagram.ForceEdges.Count}";
            data.SetData(0, new GraphicDiagramGoo(diagram));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("TNA Reciprocal failed", error);
        }
    }

    public override void DrawViewportWires(IGH_PreviewArgs args)
    {
        base.DrawViewportWires(args);
        Draw(args, _form);
        Draw(args, _thrust);
        Draw(args, _force);
        DrawArrows(args, _loads);
        DrawArrows(args, _reactions);
    }

    private static IEnumerable<PreviewEdge> ToPreview(
        IReadOnlyList<GraphicEdgeDto> edges,
        string role)
    {
        double maximum = edges
            .Select(edge => edge.Magnitude)
            .DefaultIfEmpty(0.0)
            .Max();
        foreach (GraphicEdgeDto edge in edges)
        {
            double normalised = maximum > 0.0
                ? edge.Magnitude / maximum
                : 0.0;
            int weight = role is "load" or "reaction"
                ? 2
                : role == "form"
                    ? Math.Clamp(
                        1 + (int)Math.Round(4.0 * normalised),
                        1,
                        5)
                    : Math.Clamp(
                        1 + (int)Math.Round(5.0 * normalised),
                        1,
                        7);
            Color colour = role switch
            {
                "form" => Color.FromArgb(45, 45, 45),
                "load" => Color.FromArgb(238, 135, 35),
                "reaction" => Color.FromArgb(35, 155, 75),
                _ => StateColour(edge.ForceState)
            };
            yield return new PreviewEdge(
                new Line(Point(edge.Start), Point(edge.End)),
                colour,
                weight);
        }
    }

    private static void Draw(
        IGH_PreviewArgs args,
        IEnumerable<PreviewEdge> edges)
    {
        foreach (PreviewEdge edge in edges)
            args.Display.DrawLine(edge.Line, edge.Colour, edge.Weight);
    }

    private static void DrawArrows(
        IGH_PreviewArgs args,
        IEnumerable<PreviewEdge> edges)
    {
        foreach (PreviewEdge edge in edges)
            args.Display.DrawArrow(edge.Line, edge.Colour);
    }

    private static Color StateColour(string state) =>
        (state ?? string.Empty).Trim().ToLowerInvariant() switch
        {
            "compression" => Color.FromArgb(35, 95, 210),
            "tension" => Color.FromArgb(210, 45, 45),
            "zero" => Color.FromArgb(125, 125, 125),
            _ => Color.FromArgb(35, 155, 75)
        };

    private static Point3d Point(Point3Dto value) =>
        new(value.X, value.Y, value.Z);

    private sealed record PreviewEdge(
        Line Line,
        Color Colour,
        int Weight);
}
