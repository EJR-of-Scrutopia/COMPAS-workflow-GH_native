using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

public sealed class ResultBreakdownComponent : NativeComponentBase
{
    public ResultBreakdownComponent()
        : base(
            "Result Breakdown",
            "Result Data",
            "Legacy full deconstruction of a generic FD equilibrium result. " +
            "For TNA, prefer TNA Geometry, TNA Members, and TNA Actions.",
            ComponentCategories.Query,
            "result_breakdown")
    {
    }

    public override Guid ComponentGuid =>
        new("c80b2201-c11b-4364-895e-5600ff6bcf01");

    public override GH_Exposure Exposure => GH_Exposure.secondary;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new EquilibriumResultParam(),
            "Result",
            "R",
            "Solved generic FD equilibrium result. TNA Geometry can expose " +
            "the embedded equilibrium bridge for legacy definitions.",
            GH_ParamAccess.item);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddLineParameter(
            "Member Lines",
            "M",
            "Solved member axes aligned with forces and densities.",
            GH_ParamAccess.list);
        parameters.AddNumberParameter(
            "Member Forces",
            "F",
            "Signed member forces; interpretation follows Sign Convention.",
            GH_ParamAccess.list);
        parameters.AddNumberParameter(
            "Force Densities",
            "q",
            "Member-aligned force densities in Force Unit per Length Unit.",
            GH_ParamAccess.list);
        parameters.AddColourParameter(
            "Force Colours",
            "C",
            "Analysis preset colours aligned with Member Lines.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Load Points",
            "LP",
            "Points carrying non-zero applied loads.",
            GH_ParamAccess.list);
        parameters.AddVectorParameter(
            "Load Vectors",
            "LV",
            "Applied load vectors aligned with Load Points.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Reaction Points",
            "RP",
            "Points carrying non-zero support reactions.",
            GH_ParamAccess.list);
        parameters.AddVectorParameter(
            "Reaction Vectors",
            "RV",
            "Support reactions aligned with Reaction Points.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Residual Points",
            "EP",
            "Points carrying non-zero equilibrium residuals.",
            GH_ParamAccess.list);
        parameters.AddVectorParameter(
            "Residual Vectors",
            "EV",
            "Equilibrium residuals aligned with Residual Points.",
            GH_ParamAccess.list);
        parameters.AddParameter(
            new DiagnosticParam(),
            "Diagnostics",
            "D",
            "Structured solver diagnostics.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Sign Convention",
            "Sign",
            "How signed member forces are interpreted.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Report",
            "Out",
            "Readable backend solve report.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Member Source IDs",
            "SID",
            "Stable source-segment IDs aligned with Member Lines.",
            GH_ParamAccess.list);
        parameters.AddIntegerParameter(
            "Support Node IDs",
            "SN",
            "Resolved zero-based support node IDs in the solved topology.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Support Points",
            "SP",
            "Solved vertex positions aligned with Support Node IDs.",
            GH_ParamAccess.list);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        EquilibriumResultGoo? resultGoo = null;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not EquilibriumResultDto result)
        {
            return;
        }

        try
        {
            IReadOnlyList<string> errors = result.Validate();
            if (errors.Count > 0)
                throw new InvalidOperationException(string.Join(" ", errors));

            Line[] lines = MemberLines(result);
            Color[] colours = result.MemberForces
                .Select(force => ForceColour(force, result.SignConvention))
                .ToArray();
            data.SetDataList(0, lines);
            data.SetDataList(1, result.MemberForces);
            data.SetDataList(2, result.ForceDensities);
            data.SetDataList(3, colours);
            SetNodalVectors(data, 4, 5, result.Loads);
            SetNodalVectors(data, 6, 7, result.Reactions);
            SetNodalVectors(data, 8, 9, result.Residuals);
            data.SetDataList(
                10,
                result.Diagnostics.Select(item => new DiagnosticGoo(item)));
            data.SetData(11, result.SignConvention);
            data.SetData(12, result.Report);
            data.SetDataList(13, result.MemberSourceIds);
            data.SetDataList(14, result.ResolvedSupportNodeIds);
            data.SetDataList(
                15,
                result.ResolvedSupportNodeIds.Select(
                    nodeId => Point(result.Vertices[nodeId])));
            Message = $"{result.Solver.ToUpperInvariant()} · {lines.Length}";
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Result Breakdown failed", error);
        }
    }

    internal static Line[] MemberLines(EquilibriumResultDto result)
    {
        return result.Edges
            .Select(edge => new Line(
                Point(result.Vertices[edge.U]),
                Point(result.Vertices[edge.V])))
            .ToArray();
    }

    internal static Color ForceColour(double force, string signConvention)
    {
        if (Math.Abs(force) <= 1.0e-12)
            return Color.FromArgb(145, 145, 145);
        bool positiveTension = string.Equals(
            signConvention,
            "positive_tension",
            StringComparison.OrdinalIgnoreCase);
        bool tension = positiveTension ? force > 0.0 : force < 0.0;
        return tension
            ? Color.FromArgb(210, 45, 45)
            : Color.FromArgb(35, 95, 210);
    }

    internal static Point3d Point(Point3Dto point) =>
        new(point.X, point.Y, point.Z);

    internal static Vector3d Vector(Point3Dto vector) =>
        new(vector.X, vector.Y, vector.Z);

    private static void SetNodalVectors(
        IGH_DataAccess data,
        int pointOutput,
        int vectorOutput,
        IReadOnlyList<NodalVectorDto> values)
    {
        data.SetDataList(
            pointOutput,
            values.Select(item => Point(item.Point)));
        data.SetDataList(
            vectorOutput,
            values.Select(item => Vector(item.Vector)));
    }
}

public sealed class EquilibriumPreviewComponent : NativePreviewComponentBase
{
    private readonly List<Line> _members = new();
    private readonly List<Color> _memberColours = new();
    private readonly List<int> _memberWeights = new();
    private readonly List<Line> _loads = new();
    private readonly List<Line> _reactions = new();
    private readonly List<Line> _residuals = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public EquilibriumPreviewComponent()
        : base(
            "Equilibrium Preview",
            "Preview",
            "Preview signed member forces, loads, reactions, and residuals.",
            ComponentCategories.Visualisation,
            "equilibrium_preview")
    {
    }

    public override Guid ComponentGuid =>
        new("471c5479-6c2c-479c-9372-3dc1fd31e85e");

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new EquilibriumResultParam(),
            "Result",
            "R",
            "Solved FD or TNA result.",
            GH_ParamAccess.item);
        parameters.AddNumberParameter(
            "Force Weight",
            "FW",
            "Relative member line-weight response to force magnitude.",
            GH_ParamAccess.item,
            1.0);
        parameters.AddNumberParameter(
            "Vector Scale",
            "VS",
            "Viewport scale for load, reaction, and residual vectors.",
            GH_ParamAccess.item,
            1.0);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddLineParameter(
            "Member Lines",
            "M",
            "Solved member axes.",
            GH_ParamAccess.list);
        parameters.AddColourParameter(
            "Member Colours",
            "C",
            "Tension/compression colours aligned with Member Lines.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Load Lines",
            "L",
            "Scaled applied-load vectors.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Reaction Lines",
            "R",
            "Scaled support-reaction vectors.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Residual Lines",
            "E",
            "Scaled equilibrium residual vectors.",
            GH_ParamAccess.list);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _members.Clear();
        _memberColours.Clear();
        _memberWeights.Clear();
        _loads.Clear();
        _reactions.Clear();
        _residuals.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        EquilibriumResultGoo? resultGoo = null;
        double forceWeight = 1.0;
        double vectorScale = 1.0;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not EquilibriumResultDto result)
        {
            return;
        }
        data.GetData(1, ref forceWeight);
        data.GetData(2, ref vectorScale);

        try
        {
            if (!double.IsFinite(forceWeight) || forceWeight < 0.0)
                throw new ArgumentException("Force Weight must be finite and non-negative.");
            if (!double.IsFinite(vectorScale) || vectorScale <= 0.0)
                throw new ArgumentException("Vector Scale must be finite and greater than zero.");
            IReadOnlyList<string> errors = result.Validate();
            if (errors.Count > 0)
                throw new InvalidOperationException(string.Join(" ", errors));

            Line[] members = ResultBreakdownComponent.MemberLines(result);
            Color[] memberColours =
                result.MemberForces.Select(
                    force => ResultBreakdownComponent.ForceColour(
                        force,
                        result.SignConvention))
                .ToArray();
            double maximum = result.MemberForces
                .Select(Math.Abs)
                .DefaultIfEmpty(0.0)
                .Max();
            int[] memberWeights =
                result.MemberForces.Select(force =>
                {
                    double normalised = maximum > 0.0
                        ? Math.Abs(force) / maximum
                        : 0.0;
                    return Math.Clamp(
                        1 + (int)Math.Round(5.0 * forceWeight * normalised),
                        1,
                        9);
                })
                .ToArray();
            Line[] loads = VectorLines(result.Loads, vectorScale).ToArray();
            Line[] reactions =
                VectorLines(result.Reactions, vectorScale).ToArray();
            Line[] residuals =
                VectorLines(result.Residuals, vectorScale).ToArray();

            _members.AddRange(members);
            _memberColours.AddRange(memberColours);
            _memberWeights.AddRange(memberWeights);
            _loads.AddRange(loads);
            _reactions.AddRange(reactions);
            _residuals.AddRange(residuals);

            IEnumerable<Point3d> points =
                _members.SelectMany(line => new[] { line.From, line.To })
                .Concat(_loads.SelectMany(line => new[] { line.From, line.To }))
                .Concat(_reactions.SelectMany(line => new[] { line.From, line.To }))
                .Concat(_residuals.SelectMany(line => new[] { line.From, line.To }));
            Point3d[] pointArray = points.ToArray();
            _clippingBox = pointArray.Length == 0
                ? BoundingBox.Empty
                : new BoundingBox(pointArray);

            data.SetDataList(0, members);
            data.SetDataList(1, memberColours);
            data.SetDataList(2, loads);
            data.SetDataList(3, reactions);
            data.SetDataList(4, residuals);
            Message =
                $"{result.Solver.ToUpperInvariant()} · {members.Length}";
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Equilibrium Preview failed", error);
        }
    }

    protected override void DrawVisibleViewportWires(IGH_PreviewArgs args)
    {
        for (int index = 0; index < _members.Count; index++)
        {
            args.Display.DrawLine(
                _members[index],
                _memberColours[index],
                _memberWeights[index]);
        }
        foreach (Line line in _loads)
            args.Display.DrawLine(line, Color.FromArgb(238, 135, 35), 2);
        foreach (Line line in _reactions)
            args.Display.DrawLine(line, Color.FromArgb(35, 155, 75), 2);
        foreach (Line line in _residuals)
            args.Display.DrawLine(line, Color.FromArgb(220, 30, 170), 1);
    }

    private static IEnumerable<Line> VectorLines(
        IEnumerable<NodalVectorDto> values,
        double scale)
    {
        foreach (NodalVectorDto value in values)
        {
            Point3d start = ResultBreakdownComponent.Point(value.Point);
            Vector3d vector =
                scale * ResultBreakdownComponent.Vector(value.Vector);
            yield return new Line(start, start + vector);
        }
    }
}
