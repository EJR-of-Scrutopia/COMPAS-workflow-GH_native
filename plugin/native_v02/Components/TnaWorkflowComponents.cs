#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Register the stable source geometry for the staged TNA workflow.
/// Mesh and already-split planar line patterns are concrete native paths.
/// The remaining value-list entries are visible design intent and fail
/// explicitly until a geometry generator with a stable contract exists.
/// </summary>
public sealed class TnaPatternComponent : NativePreviewComponentBase
{
    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            1,
            "Pattern Mode",
            new (string Label, string Value)[]
            {
                ("Mesh", "mesh"),
                ("Lines", "lines"),
                ("Surface", "surface"),
                ("Grid", "grid"),
                ("Triangulation", "triangulation"),
                ("Skeleton", "skeleton")
            },
            "mesh")
    };

    private readonly List<Line> _previewEdges = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaPatternComponent()
        : base(
            "TNA Pattern",
            "TNA Pattern",
            "Register a stable Rhino mesh or already-split planar line " +
            "pattern for staged thrust-network analysis.",
            ComponentCategories.FormFinding,
            "tna_pattern")
    {
    }

    public override Guid ComponentGuid =>
        new("2fb2617f-d952-4f22-b7d5-0383c8cc203b");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddGenericParameter(
            "Geometry",
            "G",
            "Mesh geometry, or planar straight lines/polylines whose " +
            "intersections have already been split.",
            GH_ParamAccess.list);
        parameters[0].DataMapping = GH_DataMapping.Flatten;
        parameters.AddTextParameter(
            "Mode",
            "M",
            "Mesh, Lines, Surface, Grid, Triangulation, or Skeleton.",
            GH_ParamAccess.item,
            "mesh");
        parameters.AddIntegerParameter(
            "Resolution",
            "R",
            "Generic positive pattern resolution. Retained for future " +
            "Surface/Grid/Triangulation generators; Mesh/Lines preserve input.",
            GH_ParamAccess.item,
            8);
        parameters.AddNumberParameter(
            "Weld Tolerance",
            "Tol",
            "Maximum distance used to weld coincident topology nodes.",
            GH_ParamAccess.item,
            1.0e-6);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPatternParam(),
            "Pattern",
            "P",
            "Compact typed TNA pattern on stable source node IDs.",
            GH_ParamAccess.item);
        parameters.AddParameter(
            new TopologyParam(),
            "Topology",
            "T",
            "Original topology for binding optional Load Case data.",
            GH_ParamAccess.item);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _previewEdges.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        var geometry = new List<object>();
        string modeInput = "mesh";
        int resolution = 8;
        double tolerance = 1.0e-6;
        if (!data.GetDataList(0, geometry))
            return;
        data.GetData(1, ref modeInput);
        data.GetData(2, ref resolution);
        data.GetData(3, ref tolerance);

        try
        {
            string mode = TnaPatternDto.NormaliseMode(modeInput);
            string requestedKind = mode switch
            {
                "mesh" => "faced",
                "lines" => "line",
                "surface" or "grid" or "triangulation" or "skeleton" =>
                    throw new NotSupportedException(
                        $"{DisplayMode(mode)} mode does not yet have a " +
                        "concrete native topology generator. Convert the " +
                        "source to a Rhino mesh or already-split planar lines; " +
                        "no substitute geometry was created."),
                _ => throw new ArgumentException(
                    "Mode must be Mesh, Lines, Surface, Grid, " +
                    "Triangulation, or Skeleton.")
            };
            if (resolution < 1)
                throw new ArgumentOutOfRangeException(
                    nameof(resolution),
                    "Resolution must be positive.");

            GeometryTopologyData registered =
                GeometryTopologyBuilder.Build(
                    geometry,
                    requestedKind,
                    tolerance);
            (string lengthUnit, string? unitWarning) = ModelLengthUnit();
            if (unitWarning is not null)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    unitWarning);
            }

            var provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["source"] = "Rhino/Grasshopper",
                ["pattern_mode"] = mode,
                ["resolution"] =
                    resolution.ToString(CultureInfo.InvariantCulture),
                ["weld_tolerance"] =
                    tolerance.ToString("R", CultureInfo.InvariantCulture),
                ["connected_components"] =
                    registered.ConnectedComponents.ToString(
                        CultureInfo.InvariantCulture)
            };
            TopologyDto topology = TopologyDto.Create(
                registered.Kind,
                registered.Vertices.Select(ToPoint),
                registered.Edges.Select(
                    edge => new EdgeDto(edge.U, edge.V)),
                registered.Faces,
                sourceVertexIds: Enumerable.Range(
                    0,
                    registered.Vertices.Count).Select(index => $"v{index}"),
                sourceEdgeIds: registered.SourceEdgeIds,
                lengthUnit: lengthUnit,
                provenance: provenance);
            var pattern = new TnaPatternDto
            {
                PatternMode = mode,
                Topology = topology,
                Resolution = resolution,
                WeldTolerance = tolerance,
                Provenance = provenance
            };
            EnsureValid(pattern);

            if (registered.ConnectedComponents > 1)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"Pattern contains {registered.ConnectedComponents} " +
                    "disconnected components; prepare each component " +
                    "separately.");
            }
            if (mode == "lines")
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Remark,
                    "Lines mode preserves the registered line graph. " +
                    "TNA Relax will derive closed faces in the worker and " +
                    "reject dangling or unsplit intersections.");
            }

            SetTopologyPreview(topology);
            Message =
                $"{DisplayMode(mode)} - {topology.Vertices.Count}V/" +
                $"{topology.Edges.Count}E";
            data.SetData(0, new TnaPatternGoo(pattern));
            data.SetData(1, new TopologyGoo(topology));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("TNA Pattern failed", error);
        }
    }

    protected override void DrawVisibleViewportWires(IGH_PreviewArgs args)
    {
        foreach (Line edge in _previewEdges)
        {
            args.Display.DrawLine(
                edge,
                Color.FromArgb(55, 65, 75),
                2);
        }
    }

    private void SetTopologyPreview(TopologyDto topology)
    {
        _previewEdges.Clear();
        _previewEdges.AddRange(TnaWorkflowPreview.TopologyLines(topology));
        _clippingBox = TnaWorkflowPreview.Box(_previewEdges);
    }

    private static (string Unit, string? Warning) ModelLengthUnit()
    {
        UnitSystem? units = RhinoDoc.ActiveDoc?.ModelUnitSystem;
        return units switch
        {
            UnitSystem.Millimeters => ("mm", null),
            UnitSystem.Centimeters => ("cm", null),
            UnitSystem.Meters => ("m", null),
            UnitSystem.Inches => ("in", null),
            UnitSystem.Feet => ("ft", null),
            null => (
                "m",
                "No active Rhino document was available; Pattern length " +
                "unit defaults to metres."),
            _ => throw new InvalidOperationException(
                $"Rhino model unit '{units}' is not supported by the v0.2 " +
                "contract. Change the document to mm, cm, m, in, or ft " +
                "before registering the TNA Pattern.")
        };
    }

    private static string DisplayMode(string mode) =>
        CultureInfo.InvariantCulture.TextInfo.ToTitleCase(mode);

    private static Point3Dto ToPoint(Point3d point) =>
        new(point.X, point.Y, point.Z);

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}

/// <summary>
/// Attach explicit structural anchors to a stable TNA source pattern.
/// Empty anchors are rejected: treating every naked boundary vertex as a
/// support would hold the very edges that the next stage is meant to sag.
/// </summary>
public sealed class TnaSupportsComponent : NativePreviewComponentBase
{
    private readonly List<Line> _previewEdges = new();
    private readonly List<Point3d> _previewSupports = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaSupportsComponent()
        : base(
            "TNA Supports",
            "TNA Supports",
            "Snap explicit structural anchors to a staged TNA pattern.",
            ComponentCategories.FormFinding,
            "tna_supports")
    {
    }

    public override Guid ComponentGuid =>
        new("fd767b85-9dc2-48a2-afdb-504f9db33640");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPatternParam(),
            "Pattern",
            "P",
            "Stable source Pattern from TNA Pattern.",
            GH_ParamAccess.item);
        parameters.AddPointParameter(
            "Anchor Points",
            "A",
            "Explicit structural support locations. At least two distinct " +
            "anchors are required; adjacent anchors define a held edge, not " +
            "a sagging opening.",
            GH_ParamAccess.list);
        parameters[1].DataMapping = GH_DataMapping.Flatten;
        parameters.AddNumberParameter(
            "Snap Tolerance",
            "Tol",
            "Optional maximum anchor-to-node snapping distance. Empty uses " +
            "the Pattern weld tolerance.",
            GH_ParamAccess.item);
        parameters[2].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPatternParam(),
            "Pattern",
            "P",
            "The same compact Pattern bundle with explicit supports attached.",
            GH_ParamAccess.item);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _previewEdges.Clear();
        _previewSupports.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TnaPatternGoo? patternGoo = null;
        var anchors = new List<Point3d>();
        double snapTolerance = 0.0;
        if (!data.GetData(0, ref patternGoo) ||
            patternGoo?.Value is not TnaPatternDto source ||
            source.Topology is not TopologyDto topology)
        {
            return;
        }
        data.GetDataList(1, anchors);
        bool hasTolerance = data.GetData(2, ref snapTolerance);

        try
        {
            if (anchors.Count == 0)
            {
                throw new ArgumentException(
                    "Connect explicit Anchor Points. Automatically supporting " +
                    "every boundary node would hold the boundary straight and " +
                    "leave no unsupported opening to sag.");
            }
            SnappedTargets snapped = TopologyTargets.Resolve(
                topology,
                anchors,
                hasTolerance ? snapTolerance : null,
                "TNA anchor");
            int[] nodeIds = snapped.NodeIds.Distinct().ToArray();
            if (nodeIds.Length < 2)
            {
                throw new ArgumentException(
                    "TNA Supports requires at least two distinct snapped " +
                    "anchor nodes.");
            }
            if (!HasNonCollinearAnchors(
                    topology,
                    nodeIds,
                    snapped.Tolerance))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "All anchor nodes are collinear in the Pattern XY plane. " +
                    "This can be valid for an arch or strip, but a general " +
                    "two-dimensional mesh may remain singular; TNA Relax will " +
                    "perform the topology-specific check.");
            }

            var supports = new SupportSetDto
            {
                TopologyHash = topology.TopologyHash,
                Mode = "explicit",
                Points = Array.Empty<Point3Dto>(),
                NodeIds = nodeIds,
                SnapTolerance = snapped.Tolerance,
                Provenance = new Dictionary<string, string>(
                    StringComparer.Ordinal)
                {
                    ["source"] = "TNA Supports",
                    ["point_targets_resolved"] = "true",
                    ["maximum_snap_distance"] =
                        snapped.MaximumDistance.ToString(
                            "R",
                            CultureInfo.InvariantCulture)
                }
            };
            var provenance = new Dictionary<string, string>(
                source.Provenance,
                StringComparer.Ordinal)
            {
                ["supports_component"] = "TNA Supports"
            };
            TnaPatternDto supported = source with
            {
                Supports = supports,
                Provenance = provenance
            };
            EnsureValid(supported);

            var supportSet = nodeIds.ToHashSet();
            int heldEdges = topology.Edges.Count(
                edge =>
                    supportSet.Contains(edge.U) &&
                    supportSet.Contains(edge.V));
            if (heldEdges > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{heldEdges} source edge(s) have anchors at both ends. " +
                    "Those are held boundary segments, not unsupported " +
                    "openings, so they cannot receive the requested sag.");
            }
            if (nodeIds.Length >=
                Math.Max(3, (int)Math.Ceiling(0.75 * topology.Vertices.Count)))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{nodeIds.Length} of {topology.Vertices.Count} pattern " +
                    "nodes are supported. Supporting most boundary nodes can " +
                    "leave no opening for TNA Relax + Boundaries to sag.");
            }

            SetPreview(topology, nodeIds);
            Message = $"{nodeIds.Length} explicit anchors";
            data.SetData(0, new TnaPatternGoo(supported));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("TNA Supports failed", error);
        }
    }

    protected override void DrawVisibleViewportWires(IGH_PreviewArgs args)
    {
        foreach (Line edge in _previewEdges)
        {
            args.Display.DrawLine(
                edge,
                Color.FromArgb(85, 90, 95),
                1);
        }
        foreach (Point3d point in _previewSupports)
        {
            args.Display.DrawPoint(
                point,
                PointStyle.RoundControlPoint,
                7,
                Color.FromArgb(30, 165, 85));
        }
    }

    private void SetPreview(
        TopologyDto topology,
        IReadOnlyList<int> nodeIds)
    {
        _previewEdges.Clear();
        _previewEdges.AddRange(TnaWorkflowPreview.TopologyLines(topology));
        _previewSupports.Clear();
        _previewSupports.AddRange(
            nodeIds.Select(id => TnaWorkflowPreview.Point(topology.Vertices[id])));
        _clippingBox = TnaWorkflowPreview.Box(
            _previewEdges,
            _previewSupports);
    }

    private static bool HasNonCollinearAnchors(
        TopologyDto topology,
        IReadOnlyList<int> nodeIds,
        double tolerance)
    {
        if (nodeIds.Count < 3)
            return false;
        Point3Dto first = topology.Vertices[nodeIds[0]];
        for (int left = 1; left < nodeIds.Count - 1; left++)
        for (int right = left + 1; right < nodeIds.Count; right++)
        {
            Point3Dto a = topology.Vertices[nodeIds[left]];
            Point3Dto b = topology.Vertices[nodeIds[right]];
            double twiceArea =
                (a.X - first.X) * (b.Y - first.Y) -
                (a.Y - first.Y) * (b.X - first.X);
            if (Math.Abs(twiceArea) > tolerance * tolerance)
                return true;
        }
        return false;
    }

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}

public sealed record TnaPrepareTaskResult(
    TnaPreparedDto? Prepared,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// Run the real, stateless Pattern relaxation/boundary-opening worker stage.
/// The returned force graph is explicitly an unbalanced topological dual.
/// </summary>
public sealed class TnaRelaxBoundariesComponent :
    NativeTaskComponentBase<TnaPrepareTaskResult>
{
    private readonly List<Line> _formPreview = new();
    private readonly List<Line> _forcePreview = new();
    private readonly List<Line> _boundaryPreview = new();
    private readonly List<Point3d> _supportPreview = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaRelaxBoundariesComponent()
        : base(
            "TNA Relax + Boundaries",
            "TNA Relax",
            "Relax the plan Pattern, match unsupported-boundary sag, and " +
            "build an inspectable unbalanced topological force dual.",
            ComponentCategories.FormFinding,
            "tna_relax")
    {
    }

    public override Guid ComponentGuid =>
        new("2f8fddfa-1e46-4546-afa7-c114db411b09");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPatternParam(),
            "Pattern",
            "P",
            "Stable Pattern with explicit anchors from TNA Supports.",
            GH_ParamAccess.item);
        parameters.AddNumberParameter(
            "Force Density",
            "q",
            "Positive nominal plan-FDM force-density weight. Its absolute " +
            "uniform value does not calibrate physical kN forces.",
            GH_ParamAccess.item,
            1.0);
        parameters.AddNumberParameter(
            "Boundary Sag",
            "Sag %",
            "Target unsupported-boundary rise/span in percent.",
            GH_ParamAccess.item,
            10.0);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPreparedParam(),
            "Prepared",
            "P",
            "Relaxed Pattern, opening records, and unsolved form/force state.",
            GH_ParamAccess.item);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _formPreview.Clear();
        _forcePreview.Clear();
        _boundaryPreview.Clear();
        _supportPreview.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out TnaPatternDto? pattern,
                    out TnaPrepareConfigDto? config))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    ContractJson.DeepClone(pattern!),
                    config!,
                    CancelToken),
                CancelToken));
            return;
        }

        TnaPrepareTaskResult result;
        if (!GetSolveResults(data, out result!))
        {
            if (!TryReadInputs(
                    data,
                    out TnaPatternDto? pattern,
                    out TnaPrepareConfigDto? config))
            {
                return;
            }
            result = ComputeAsync(
                    ContractJson.DeepClone(pattern!),
                    config!,
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();
        }

        if (result.Error is not null)
        {
            Message = result.Error is OperationCanceledException
                ? "Cancelled"
                : "Failed";
            AddRuntimeMessage(
                result.Error is OperationCanceledException
                    ? GH_RuntimeMessageLevel.Warning
                    : GH_RuntimeMessageLevel.Error,
                "TNA Relax + Boundaries: " +
                result.Error.GetBaseException().Message);
            foreach (string line in SafeRecentStderr().TakeLast(3))
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, line);
            return;
        }
        if (result.Prepared is null)
        {
            Message = "Failed";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                "TNA Relax + Boundaries produced no prepared state.");
            return;
        }

        foreach (DiagnosticDto diagnostic in result.Prepared.Diagnostics)
        {
            GH_RuntimeMessageLevel? level =
                diagnostic.Severity.ToLowerInvariant() switch
                {
                    "error" => GH_RuntimeMessageLevel.Error,
                    "warning" => GH_RuntimeMessageLevel.Warning,
                    _ => null
                };
            if (level.HasValue)
            {
                AddRuntimeMessage(
                    level.Value,
                    $"{diagnostic.Code}: {diagnostic.Message}");
            }
        }
        if (result.Prepared.WorkerMetadata.TryGetValue(
                "diagnostic_metrics.boundary_condition_warning",
                out string? boundaryWarning) &&
            !string.IsNullOrWhiteSpace(boundaryWarning) &&
            !result.Prepared.Diagnostics.Any(diagnostic =>
                string.Equals(
                    diagnostic.Code,
                    "tna.boundary_supports",
                    StringComparison.OrdinalIgnoreCase)))
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                boundaryWarning);
        }
        double maximumSagError = result.Prepared.BoundarySegments
            .Select(segment => segment.SagError)
            .DefaultIfEmpty(0.0)
            .Max();
        if (maximumSagError > result.Prepared.Config.SagTolerance)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                $"Boundary sag did not meet its exact target: maximum " +
                $"rise/span error {maximumSagError:G6} exceeds tolerance " +
                $"{result.Prepared.Config.SagTolerance:G6} after " +
                $"{result.Prepared.Config.SagIterations} iterations.");
        }
        if (result.Prepared.BoundarySegments.Count == 0)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                "No unsupported boundary opening was found. Adjacent " +
                "supported boundary vertices define held edges and cannot " +
                "receive the requested sag.");
        }
        int supportCount =
            result.Prepared.SupportSet?.NodeIds.Count ?? 0;
        int vertexCount =
            result.Prepared.Source?.Topology?.Vertices.Count ?? 0;
        if (vertexCount > 0 &&
            supportCount >= Math.Max(
                2,
                (int)Math.Ceiling(0.75 * vertexCount)))
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                $"{supportCount} of {vertexCount} source nodes are supports. " +
                "Most/all boundary nodes may be held, leaving no opening " +
                "that can sag.");
        }

        BuildPreparedPreview(result.Prepared);
        Message =
            $"{result.Prepared.BoundarySegments.Count} opening(s) - " +
            $"{result.Elapsed.TotalMilliseconds:F0} ms";
        data.SetData(0, new TnaPreparedGoo(result.Prepared));
    }

    public override void DrawViewportWires(IGH_PreviewArgs args)
    {
        if (Hidden)
            return;
        base.DrawViewportWires(args);
        foreach (Line edge in _formPreview)
        {
            args.Display.DrawLine(
                edge,
                Color.FromArgb(55, 60, 65),
                2);
        }
        foreach (Line edge in _boundaryPreview)
        {
            args.Display.DrawLine(
                edge,
                Color.FromArgb(185, 65, 165),
                4);
        }
        foreach (Line edge in _forcePreview)
        {
            args.Display.DrawLine(
                edge,
                Color.FromArgb(215, 125, 35),
                2);
        }
        foreach (Point3d point in _supportPreview)
        {
            args.Display.DrawPoint(
                point,
                PointStyle.RoundControlPoint,
                7,
                Color.FromArgb(30, 165, 85));
        }
    }

    private bool TryReadInputs(
        IGH_DataAccess data,
        out TnaPatternDto? pattern,
        out TnaPrepareConfigDto? config)
    {
        pattern = null;
        config = null;
        TnaPatternGoo? patternGoo = null;
        double q = 1.0;
        double sagPercent = 10.0;
        if (!data.GetData(0, ref patternGoo) ||
            patternGoo?.Value is not TnaPatternDto value)
        {
            return false;
        }
        data.GetData(1, ref q);
        data.GetData(2, ref sagPercent);

        var errors = new List<string>(value.Validate());
        if (value.Supports is null)
        {
            errors.Add(
                "Pattern has no explicit anchors. Connect TNA Supports first.");
        }
        if (!double.IsFinite(q) || q <= 0.0)
            errors.Add("Force Density q must be finite and greater than zero.");
        if (!double.IsFinite(sagPercent) ||
            sagPercent <= 0.0 ||
            sagPercent > 100.0)
        {
            errors.Add(
                "Boundary Sag must be greater than 0% and no greater than 100%.");
        }
        if (errors.Count > 0)
        {
            Message = "Invalid";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                string.Join(" ", errors));
            return false;
        }

        pattern = value;
        config = new TnaPrepareConfigDto
        {
            ForceDensity = q,
            Relax = true,
            BoundarySag = sagPercent / 100.0,
            SagIterations = 10,
            SagTolerance = 0.01,
            FixedNodeIds = Array.Empty<int>(),
            Metadata = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["component"] = "TNA Relax + Boundaries",
                ["sag_input_percent"] =
                    sagPercent.ToString("R", CultureInfo.InvariantCulture)
            }
        };
        return true;
    }

    private static async Task<TnaPrepareTaskResult> ComputeAsync(
        TnaPatternDto pattern,
        TnaPrepareConfigDto config,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            JsonElement response = await WorkerRuntime.Host
                .RequestAsync<JsonElement>(
                    "tna.prepare",
                    TnaWorkflowWorkerCodec.PreparePayload(pattern, config),
                    cancellationToken)
                .ConfigureAwait(false);
            TnaPreparedDto prepared =
                TnaWorkflowWorkerCodec.DecodePrepared(response, pattern);
            stopwatch.Stop();
            return new TnaPrepareTaskResult(
                prepared,
                null,
                stopwatch.Elapsed);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new TnaPrepareTaskResult(
                null,
                error,
                stopwatch.Elapsed);
        }
    }

    private void BuildPreparedPreview(TnaPreparedDto prepared)
    {
        _formPreview.Clear();
        _forcePreview.Clear();
        _boundaryPreview.Clear();
        _supportPreview.Clear();

        _formPreview.AddRange(
            TnaWorkflowPreview.GraphLines(
                prepared.FormGraph,
                Vector3d.Zero));
        Vector3d translation =
            TnaWorkflowPreview.SideBySideTranslation(
                prepared.FormGraph,
                prepared.ForceGraph);
        _forcePreview.AddRange(
            TnaWorkflowPreview.GraphLines(
                prepared.ForceGraph,
                translation));

        foreach (TnaBoundarySegmentDto segment in
                 prepared.BoundarySegments)
        {
            for (int index = 0;
                 index + 1 < segment.NodeIds.Count;
                 index++)
            {
                _boundaryPreview.Add(new Line(
                    TnaWorkflowPreview.Point(
                        prepared.Pattern.Vertices[
                            segment.NodeIds[index]]),
                    TnaWorkflowPreview.Point(
                        prepared.Pattern.Vertices[
                            segment.NodeIds[index + 1]])));
            }
        }
        _supportPreview.AddRange(
            prepared.SupportSet!.NodeIds.Select(
                id => TnaWorkflowPreview.Point(
                    prepared.Pattern.Vertices[id])));
        _clippingBox = TnaWorkflowPreview.Box(
            _formPreview
                .Concat(_forcePreview)
                .Concat(_boundaryPreview),
            _supportPreview);
    }

    private static IReadOnlyList<string> SafeRecentStderr()
    {
        try
        {
            return WorkerRuntime.Host.RecentStderr;
        }
        catch
        {
            return Array.Empty<string>();
        }
    }
}

public sealed record TnaEquilibriumTaskResult(
    TnaResultDto? Result,
    Exception? Error,
    TimeSpan Elapsed,
    string Mode,
    bool UsedDefaultLoad);

/// <summary>
/// Solve vertical equilibrium from a reconstructible prepared Pattern.
/// The result remains the existing strict TnaResult bundle.
/// </summary>
public sealed class TnaEquilibriumComponent :
    NativeTaskComponentBase<TnaEquilibriumTaskResult>
{
    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            2,
            "Equilibrium Mode",
            new (string Label, string Value)[]
            {
                ("Crown Height", "zmax"),
                ("Force Scale (signed q)", "q")
            },
            "zmax")
    };

    private readonly List<SolvedPreviewEdge> _preview = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaEquilibriumComponent()
        : base(
            "TNA Equilibrium",
            "TNA Equilibrium",
            "Solve a prepared Pattern by crown height or signed q scale and " +
            "preview its thrust/form state beside the reciprocal force diagram.",
            ComponentCategories.FormFinding,
            "tna_equilibrium")
    {
    }

    public override Guid ComponentGuid =>
        new("8dc94461-dcd8-4556-8ace-d201d2e1c6c3");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPreparedParam(),
            "Prepared",
            "P",
            "Prepared state from TNA Relax + Boundaries.",
            GH_ParamAccess.item);
        parameters.AddParameter(
            new LoadCaseParam(),
            "Load Case",
            "L",
            "Optional source-topology-bound load. Empty uses a uniform " +
            "(0,0,-1) kN nodal load.",
            GH_ParamAccess.item);
        parameters[1].Optional = true;
        parameters.AddTextParameter(
            "Mode",
            "M",
            "Crown Height (zmax), or Force Scale as a signed q scale with " +
            "force/length units. Under positive=tension, compression uses " +
            "negative q; this is not a direct kN member force.",
            GH_ParamAccess.item,
            "zmax");
        parameters.AddNumberParameter(
            "Value",
            "V",
            "Target crown Z in Crown Height mode; signed q scale in Force " +
            "Scale mode.",
            GH_ParamAccess.item,
            5.0);
        parameters.AddParameter(
            new TnaControlParam(),
            "Control",
            "C",
            "Optional solver controls from TNA Control. Empty uses alpha 100 " +
            "with 100 horizontal and vertical iterations. Radial and other " +
            "high-valence patterns need far more horizontal iterations than " +
            "a quad grid; raise them until the reported reciprocity angle " +
            "falls to near zero. Mode and Value on this component override " +
            "the ones carried by Control.",
            GH_ParamAccess.item);
        parameters[4].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaResultParam(),
            "TNA Result",
            "R",
            "Solved thrust network with reciprocal form/force state.",
            GH_ParamAccess.item);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _preview.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out TnaPreparedDto? prepared,
                    out LoadCaseDto? loadCase,
                    out TnaControlDto? control,
                    out bool usedDefaultLoad))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    ContractJson.DeepClone(prepared!),
                    ContractJson.DeepClone(loadCase!),
                    ContractJson.DeepClone(control!),
                    usedDefaultLoad,
                    CancelToken),
                CancelToken));
            return;
        }

        TnaEquilibriumTaskResult result;
        if (!GetSolveResults(data, out result!))
        {
            if (!TryReadInputs(
                    data,
                    out TnaPreparedDto? prepared,
                    out LoadCaseDto? loadCase,
                    out TnaControlDto? control,
                    out bool usedDefaultLoad))
            {
                return;
            }
            result = ComputeAsync(
                    ContractJson.DeepClone(prepared!),
                    ContractJson.DeepClone(loadCase!),
                    ContractJson.DeepClone(control!),
                    usedDefaultLoad,
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();
        }

        if (result.Error is not null)
        {
            Message = result.Error is OperationCanceledException
                ? "Cancelled"
                : "Failed";
            AddRuntimeMessage(
                result.Error is OperationCanceledException
                    ? GH_RuntimeMessageLevel.Warning
                    : GH_RuntimeMessageLevel.Error,
                "TNA Equilibrium: " +
                result.Error.GetBaseException().Message);
            foreach (string line in SafeRecentStderr().TakeLast(3))
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, line);
            return;
        }
        if (result.Result is null)
        {
            Message = "Failed";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                "TNA Equilibrium produced no result.");
            return;
        }

        foreach (DiagnosticDto diagnostic in result.Result.Diagnostics)
        {
            GH_RuntimeMessageLevel? level =
                diagnostic.Severity.ToLowerInvariant() switch
                {
                    "error" => GH_RuntimeMessageLevel.Error,
                    "warning" => GH_RuntimeMessageLevel.Warning,
                    _ => null
                };
            if (level.HasValue)
            {
                AddRuntimeMessage(
                    level.Value,
                    $"{diagnostic.Code}: {diagnostic.Message}");
            }
        }
        if (result.UsedDefaultLoad)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Remark,
                "No Load Case was connected; solved with the explicit " +
                "default uniform nodal load (0,0,-1) kN.");
        }

        BuildSolvedPreview(result.Result);
        Message =
            $"{result.Mode} - {result.Result.EdgeStates.Count} edges - " +
            $"{result.Elapsed.TotalMilliseconds:F0} ms";
        data.SetData(0, new TnaResultGoo(result.Result));
    }

    public override void DrawViewportWires(IGH_PreviewArgs args)
    {
        if (Hidden)
            return;
        base.DrawViewportWires(args);
        foreach (SolvedPreviewEdge edge in _preview)
        {
            if (edge.Arrow)
                args.Display.DrawArrow(edge.Line, edge.Colour);
            else
                args.Display.DrawLine(
                    edge.Line,
                    edge.Colour,
                    edge.Weight);
        }
    }

    private bool TryReadInputs(
        IGH_DataAccess data,
        out TnaPreparedDto? prepared,
        out LoadCaseDto? loadCase,
        out TnaControlDto? control,
        out bool usedDefaultLoad)
    {
        prepared = null;
        loadCase = null;
        control = null;
        usedDefaultLoad = false;
        TnaPreparedGoo? preparedGoo = null;
        LoadCaseGoo? loadGoo = null;
        string modeInput = "zmax";
        double value = 5.0;
        if (!data.GetData(0, ref preparedGoo) ||
            preparedGoo?.Value is not TnaPreparedDto preparedValue ||
            preparedValue.Source?.Topology is not TopologyDto sourceTopology)
        {
            return false;
        }
        bool hasLoad =
            data.GetData(1, ref loadGoo) &&
            loadGoo?.Value is LoadCaseDto;
        data.GetData(2, ref modeInput);
        data.GetData(3, ref value);

        // Numerical controls come from an optional TNA Control so the staged
        // and one-shot paths share one settings component. Mode and Value stay
        // on this component because they are the two design decisions; the
        // rest are solver settings. Without a Control the previous hardcoded
        // defaults apply, which are only adequate for grid-like patterns.
        TnaControlGoo? controlGoo = null;
        TnaControlDto? suppliedControl =
            data.GetData(4, ref controlGoo) ? controlGoo?.Value : null;

        string mode = TnaControlDto.NormaliseHeightMode(modeInput);
        var controlValue = new TnaControlDto
        {
            HeightMode = mode,
            HeightValue = value,
            HorizontalAlpha = suppliedControl?.HorizontalAlpha ?? 100.0,
            HorizontalIterations = suppliedControl?.HorizontalIterations ?? 100,
            VerticalIterations = suppliedControl?.VerticalIterations ?? 100,
            Tolerance = suppliedControl?.Tolerance ?? 1.0e-3,
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["component"] = "TNA Equilibrium",
                ["controls"] = suppliedControl is null ? "defaults" : "TNA Control",
                ["force_scale_semantics"] =
                    "signed_q_force_per_length_positive_tension"
            }
        };
        LoadCaseDto loadValue;
        if (hasLoad)
        {
            loadValue = loadGoo!.Value;
        }
        else
        {
            usedDefaultLoad = true;
            loadValue = new LoadCaseDto
            {
                TopologyHash = sourceTopology.TopologyHash,
                Name = "uniform -1 kN",
                Distribution = "uniform_nodes",
                Points = Array.Empty<Point3Dto>(),
                NodeIds = Array.Empty<int>(),
                Vectors = Array.Empty<Point3Dto>(),
                BaseVector = new Point3Dto(0.0, 0.0, -1.0),
                Factor = 1.0,
                CoordinateSystem = "world",
                Provenance = new Dictionary<string, string>(
                    StringComparer.Ordinal)
                {
                    ["source"] = "TNA Equilibrium default",
                    ["force_unit"] = "kN",
                    ["default_uniform_load"] = "true"
                }
            };
        }

        var errors = new List<string>();
        errors.AddRange(preparedValue.Validate());
        errors.AddRange(controlValue.Validate());
        errors.AddRange(loadValue.Validate());
        if (mode is not ("zmax" or "q"))
        {
            errors.Add(
                "Mode must be Crown Height (zmax) or Force Scale (q).");
        }
        if (!string.Equals(
                loadValue.TopologyHash,
                sourceTopology.TopologyHash,
                StringComparison.OrdinalIgnoreCase))
        {
            errors.Add(
                "Load Case belongs to a different source Pattern topology. " +
                "Use the Topology output from TNA Pattern when creating it.");
        }
        if (errors.Count > 0)
        {
            Message = "Invalid";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                string.Join(" ", errors));
            return false;
        }

        prepared = preparedValue;
        loadCase = loadValue;
        control = controlValue;
        return true;
    }

    private static async Task<TnaEquilibriumTaskResult> ComputeAsync(
        TnaPreparedDto prepared,
        LoadCaseDto loadCase,
        TnaControlDto control,
        bool usedDefaultLoad,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            JsonElement response = await WorkerRuntime.Host
                .RequestAsync<JsonElement>(
                    "tna.solve",
                    TnaWorkflowWorkerCodec.StagedSolvePayload(
                        prepared,
                        loadCase,
                        control),
                    cancellationToken)
                .ConfigureAwait(false);
            EquilibriumProblemDto analysisProblem =
                TnaWorkflowWorkerCodec.AnalysisProblem(
                    response,
                    prepared,
                    loadCase);
            TnaResultDto solved = TnaWorkerResultCodec.Decode(
                response,
                analysisProblem,
                control,
                0);
            stopwatch.Stop();
            return new TnaEquilibriumTaskResult(
                solved,
                null,
                stopwatch.Elapsed,
                TnaControlDto.NormaliseHeightMode(control.HeightMode),
                usedDefaultLoad);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new TnaEquilibriumTaskResult(
                null,
                error,
                stopwatch.Elapsed,
                TnaControlDto.NormaliseHeightMode(control.HeightMode),
                usedDefaultLoad);
        }
    }

    private void BuildSolvedPreview(TnaResultDto result)
    {
        _preview.Clear();
        GraphicDiagramDto diagram = TnaGraphicDiagramFactory.Build(
            result,
            "side_by_side",
            "natural",
            1.0,
            1.0,
            0.15);
        AddPreview(diagram.FormEdges, "form");
        AddPreview(diagram.ThrustEdges, "thrust");
        AddPreview(diagram.ForceEdges, "force");
        AddPreview(diagram.LoadEdges, "load");
        AddPreview(diagram.ReactionEdges, "reaction");
        _clippingBox = TnaWorkflowPreview.Box(
            _preview.Select(item => item.Line));
    }

    private void AddPreview(
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
                : Math.Clamp(
                    1 + (int)Math.Round(5.0 * normalised),
                    1,
                    7);
            Color colour = role switch
            {
                "form" => Color.FromArgb(45, 45, 45),
                "load" => Color.FromArgb(238, 135, 35),
                "reaction" => Color.FromArgb(35, 155, 75),
                _ => ForceColour(edge.ForceState)
            };
            _preview.Add(new SolvedPreviewEdge(
                new Line(
                    TnaWorkflowPreview.Point(edge.Start),
                    TnaWorkflowPreview.Point(edge.End)),
                colour,
                weight,
                role is "load" or "reaction"));
        }
    }

    private static Color ForceColour(string state) =>
        (state ?? string.Empty).Trim().ToLowerInvariant() switch
        {
            "compression" => Color.FromArgb(35, 95, 210),
            "tension" => Color.FromArgb(210, 45, 45),
            "zero" => Color.FromArgb(125, 125, 125),
            _ => Color.FromArgb(35, 155, 75)
        };

    private static IReadOnlyList<string> SafeRecentStderr()
    {
        try
        {
            return WorkerRuntime.Host.RecentStderr;
        }
        catch
        {
            return Array.Empty<string>();
        }
    }

    private sealed record SolvedPreviewEdge(
        Line Line,
        Color Colour,
        int Weight,
        bool Arrow);
}

internal static class TnaWorkflowPreview
{
    public static IEnumerable<Line> TopologyLines(TopologyDto topology)
    {
        foreach (EdgeDto edge in topology.Edges)
        {
            yield return new Line(
                Point(topology.Vertices[edge.U]),
                Point(topology.Vertices[edge.V]));
        }
    }

    public static IEnumerable<Line> PatternLines(
        TnaPreparedPatternDto pattern)
    {
        foreach (EdgeDto edge in pattern.Edges)
        {
            yield return new Line(
                Point(pattern.Vertices[edge.U]),
                Point(pattern.Vertices[edge.V]));
        }
    }

    public static IEnumerable<Line> GraphLines(
        TnaDiagramGraphDto graph,
        Vector3d translation)
    {
        var points = graph.Vertices.ToDictionary(
            vertex => vertex.Id,
            vertex => Point(vertex.Point) + translation);
        foreach (TnaGraphEdgeDto edge in graph.Edges)
        {
            if (points.TryGetValue(edge.U, out Point3d from) &&
                points.TryGetValue(edge.V, out Point3d to))
            {
                yield return new Line(from, to);
            }
        }
    }

    public static Vector3d SideBySideTranslation(
        TnaDiagramGraphDto form,
        TnaDiagramGraphDto force,
        double gapRatio = 0.15)
    {
        Point3d[] formPoints = form.Vertices
            .Select(vertex => Point(vertex.Point))
            .ToArray();
        Point3d[] forcePoints = force.Vertices
            .Select(vertex => Point(vertex.Point))
            .ToArray();
        if (formPoints.Length == 0 || forcePoints.Length == 0)
            return Vector3d.Zero;

        var formBox = new BoundingBox(formPoints);
        var forceBox = new BoundingBox(forcePoints);
        double span = Math.Max(
            Math.Max(formBox.Diagonal.X, formBox.Diagonal.Y),
            Math.Max(forceBox.Diagonal.X, forceBox.Diagonal.Y));
        double gap = Math.Max(span * gapRatio, 1.0e-6);
        return new Vector3d(
            formBox.Max.X + gap - forceBox.Min.X,
            formBox.Center.Y - forceBox.Center.Y,
            formBox.Center.Z - forceBox.Center.Z);
    }

    public static BoundingBox Box(
        IEnumerable<Line> lines,
        IEnumerable<Point3d>? extra = null)
    {
        Point3d[] points = lines
            .SelectMany(line => new[] { line.From, line.To })
            .Concat(extra ?? Array.Empty<Point3d>())
            .ToArray();
        return points.Length == 0
            ? BoundingBox.Empty
            : new BoundingBox(points);
    }

    public static Point3d Point(Point3Dto point) =>
        new(point.X, point.Y, point.Z);
}
