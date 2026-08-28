#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Register the stable source geometry for the shared spine. Mesh and
/// already-split planar line patterns are concrete native paths. The
/// remaining value-list entries are visible design intent and fail
/// explicitly until a geometry generator with a stable contract exists.
/// </summary>
public sealed class PatternComponent : NativePreviewComponentBase
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
    private readonly List<Line> _previewPrincipal = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public PatternComponent()
        : base(
            "Pattern",
            "Pattern",
            "Register a stable Rhino mesh or already-split planar line " +
            "pattern as the shared spine's source geometry.",
            ComponentCategories.Model,
            "tna_pattern")
    {
    }

    public override Guid ComponentGuid =>
        new("7c1a2e9b-4d3f-48a6-9b2e-51c8f0a7d310");

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
        parameters.AddCurveParameter(
            "Principal Lines",
            "P",
            "Optional. The notched bars a reconfigurable mould holds rigid, " +
            "drawn as curves over this pattern. They are matched HERE, in " +
            "plan, to runs of pattern vertices and carried downstream as " +
            "indices, because once the surface rises the curves no longer sit " +
            "on it and cannot find their own nodes. This is the ONLY way a " +
            "principal line enters the chain: nothing derives one for you. " +
            "Wired curves that match no run of nodes are an error and no " +
            "Pattern is emitted.",
            GH_ParamAccess.list);
        parameters[4].Optional = true;
        parameters[4].DataMapping = GH_DataMapping.Flatten;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPatternParam(),
            "Pattern",
            "PAT",
            "Compact typed pattern on stable source node IDs.",
            GH_ParamAccess.item);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _previewEdges.Clear();
        _previewPrincipal.Clear();
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
        var principalCurves = new List<Curve>();
        data.GetDataList(4, principalCurves);
        principalCurves.RemoveAll(curve => curve is null);

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
            // Resolve the principal lines HERE, where the curves an author
            // drew and the geometry they were drawn on still agree, and carry
            // them downstream as vertex indices. Curves cannot follow a
            // surface that rises; indices can.
            var patternPoints = registered.Vertices.Select(ToPoint).ToArray();
            var patternEdges = registered.Edges
                .Select(edge => new EdgeDto(edge.U, edge.V)).ToArray();
            var patternVertices = patternPoints
                .Select(pt => new Point3d(pt.X, pt.Y, pt.Z)).ToList();

            // The curves are the only way in. What Pattern says about them
            // is one pure function of three counts, so the error path is
            // measured in the harness rather than trusted: curves wired and
            // none placed is an error and NO pattern leaves this component,
            // because a pattern whose bars could not be placed is not the
            // pattern that was asked for.
            List<List<int>> principalRuns = PrincipalRunFinder.FromCurves(
                principalCurves,
                patternVertices,
                patternEdges,
                out double principalOffset,
                out double principalGauge,
                out int unmatchedCurves);
            PrincipalOutcome outcome = PrincipalRunFinder.Outcome(
                principalCurves.Count, unmatchedCurves, principalRuns.Count);
            switch (outcome.Severity)
            {
                case "error":
                    throw new InvalidOperationException(outcome.Message);
                case "warning":
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning, outcome.Message);
                    break;
                case "remark":
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark, outcome.Message);
                    break;
            }
            // A bar can only stand on nodes. A line drawn down the middle of a
            // bay has no run of nodes to sit on, so the nearest one is taken
            // and it lands half a cell off. That is a real offset in the built
            // thing, not a drawing artefact, so it is named rather than left
            // to be noticed in the viewport.
            if (principalRuns.Count > 0 &&
                principalGauge > 0.0 &&
                principalOffset > 0.25 * principalGauge)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Remark,
                    $"A principal line sits {principalOffset:G3} off the " +
                    "curve that asked for it, against a mesh spacing of " +
                    $"{principalGauge:G3}. A bar can only stand on nodes, so " +
                    "the nearest run of them was taken. Draw the line " +
                    "through a run of pattern nodes to place it exactly.");
            }

            TopologyDto topology = TopologyDto.Create(
                registered.Kind,
                patternPoints,
                patternEdges,
                registered.Faces,
                sourceVertexIds: Enumerable.Range(
                    0,
                    registered.Vertices.Count).Select(index => $"v{index}"),
                sourceEdgeIds: registered.SourceEdgeIds,
                lengthUnit: lengthUnit,
                provenance: provenance,
                principalRuns: principalRuns);
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
            int runCount = topology.PrincipalRuns.Count;
            string runNote = runCount switch
            {
                0 => string.Empty,
                1 => ", 1 principal line",
                _ => $", {runCount} principal lines"
            };
            Message =
                $"{DisplayMode(mode)} - {topology.Vertices.Count}V/" +
                $"{topology.Edges.Count}E{runNote}";
            data.SetData(0, new TnaPatternGoo(pattern));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Pattern failed", error);
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
        foreach (Line bar in _previewPrincipal)
        {
            args.Display.DrawLine(
                bar,
                TnaWorkflowPreview.PrincipalColour,
                TnaWorkflowPreview.PrincipalWeight);
        }
    }

    private void SetTopologyPreview(TopologyDto topology)
    {
        _previewEdges.Clear();
        _previewEdges.AddRange(TnaWorkflowPreview.TopologyLines(topology));
        _previewPrincipal.Clear();
        _previewPrincipal.AddRange(
            TnaWorkflowPreview.TopologyPrincipalLines(topology));
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
                "before registering the Pattern.")
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
/// Attach explicit structural anchors to a stable source Pattern, producing
/// the shared spine's next stage: a source pattern with its supports
/// resolved to node IDs. Empty anchors are rejected: treating every naked
/// boundary vertex as a support would hold the very edges the next stage is
/// meant to sag.
/// </summary>
public sealed class SupportsComponent : NativePreviewComponentBase
{
    private readonly List<Line> _previewEdges = new();
    private readonly List<Point3d> _previewSupports = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public SupportsComponent()
        : base(
            "Supports",
            "Supports",
            "Snap explicit structural anchors to a registered Pattern.",
            ComponentCategories.Model,
            "tna_supports")
    {
    }

    public override Guid ComponentGuid =>
        new("b8e4f6c2-91a7-4b5d-8c3e-2f9d0a6b7e41");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaPatternParam(),
            "Pattern",
            "PAT",
            "Stable source Pattern from Pattern.",
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
            new AnchoredPatternParam(),
            "Anchored Pattern",
            "SUP",
            "The source Pattern with explicit supports resolved to node IDs.",
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
                "Anchor");
            int[] nodeIds = snapped.NodeIds.Distinct().ToArray();
            if (nodeIds.Length < 2)
            {
                throw new ArgumentException(
                    "Supports requires at least two distinct snapped " +
                    "anchor nodes.");
            }
            if (!HasNonCollinearAnchors(topology, nodeIds, snapped.Tolerance))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "All anchor nodes are collinear in the Pattern XY plane. " +
                    "This can be valid for an arch or strip, but a general " +
                    "two-dimensional mesh may remain singular; the downstream " +
                    "solve will perform the topology-specific check.");
            }

            var anchored = new AnchoredPatternDto
            {
                Pattern = source,
                AnchorNodeIds = nodeIds,
                SnapTolerance = snapped.Tolerance
            };
            EnsureValid(anchored);

            SetPreview(topology, nodeIds);
            Message = $"{nodeIds.Length} explicit anchors";
            data.SetData(0, new AnchoredPatternGoo(anchored));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Supports failed", error);
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
                4,
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

    /// <summary>
    /// Recovered verbatim from the deleted <c>TnaSupportsComponent</c>
    /// (git history: <c>TnaWorkflowComponents.cs</c> before the twelve-
    /// component redesign). Collinear anchors reach the downstream solver
    /// and fail there as an opaque backend error instead of a canvas
    /// warning; this cheap planar check catches the common case early.
    /// </summary>
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

/// <summary>
/// Close the shared spine's setup: one load vector, bundled with the
/// Anchored Pattern into the Problem both solvers take. Without node IDs
/// the vector is a surface load: the worker weights it by each node's plan
/// tributary area, so the funicular shape does not depend on how finely
/// the pattern happens to be meshed (the same discretisation RhinoVault
/// uses for selfweight). Explicit node IDs apply the vector directly as
/// point loads. Radical simplicity is still the point: one vector,
/// optional node ids, one factor.
/// </summary>
public sealed class LoadsComponent : NativePreviewComponentBase
{
    private readonly List<Line> _previewArrows = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public LoadsComponent()
        : base(
            "Loads",
            "Loads",
            "Apply one load vector as a tributary-area surface load, or " +
            "as point loads on explicit nodes, producing the Problem the " +
            "solvers take.",
            ComponentCategories.Model,
            "load_case")
    {
    }

    public override Guid ComponentGuid =>
        new("3f9b7d21-6c84-4e0a-b5d9-8a1c2e4f6072");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new AnchoredPatternParam(),
            "Anchored Pattern",
            "SUP",
            "The anchored source Pattern from Supports.",
            GH_ParamAccess.item);
        parameters.AddVectorParameter(
            "Vector",
            "V",
            "Load vector. Without Node IDs it is a surface load: the TNA " +
            "solve applies it selfweight-style to the built surface's " +
            "own tributary areas, updating as the shape rises (RhinoVault's " +
            "loading model); FD approximates it on plan areas. With Node " +
            "IDs it acts directly on each listed node.",
            GH_ParamAccess.item,
            new Vector3d(0.0, 0.0, -1.0));
        parameters.AddIntegerParameter(
            "Node IDs",
            "ID",
            "Explicit zero-based topology node IDs to load as point " +
            "loads. Empty applies the Vector as an area-weighted surface " +
            "load over the whole pattern.",
            GH_ParamAccess.list);
        parameters.AddNumberParameter(
            "Factor",
            "F",
            "Multiplier applied to the Vector.",
            GH_ParamAccess.item,
            1.0);

        parameters[2].DataMapping = GH_DataMapping.Flatten;
        parameters[2].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new ProblemParam(),
            "Problem",
            "PRB",
            "The Anchored Pattern bundled with the load case to solve " +
            "against it.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        AnchoredPatternGoo? supGoo = null;
        var vector = new Vector3d(0.0, 0.0, -1.0);
        var nodeIds = new List<int>();
        double factor = 1.0;
        if (!data.GetData(0, ref supGoo) ||
            supGoo?.Value is not AnchoredPatternDto sup ||
            sup.Pattern?.Topology is not TopologyDto topology)
        {
            return;
        }
        data.GetData(1, ref vector);
        data.GetDataList(2, nodeIds);
        data.GetData(3, ref factor);

        try
        {
            if (!vector.IsValid)
                throw new ArgumentException("Vector contains invalid coordinates.");
            if (!double.IsFinite(factor))
                throw new ArgumentException("Factor must be finite.");
            if (nodeIds.Any(id => id < 0 || id >= topology.Vertices.Count))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(nodeIds),
                    "A Node ID lies outside the topology.");
            }

            var factored = new Point3Dto(
                factor * vector.X,
                factor * vector.Y,
                factor * vector.Z);
            if (!double.IsFinite(factored.X) ||
                !double.IsFinite(factored.Y) ||
                !double.IsFinite(factored.Z))
            {
                throw new ArgumentException(
                    "The factored load vector must remain finite.");
            }

            bool surfaceLoad = nodeIds.Count == 0;
            var loadCase = new LoadCaseDto
            {
                TopologyHash = topology.TopologyHash,
                Name = "load",
                Distribution = surfaceLoad ? "tributary_area" : "point",
                Points = Array.Empty<Point3Dto>(),
                NodeIds = surfaceLoad
                    ? Array.Empty<int>()
                    : nodeIds.ToArray(),
                Vectors = surfaceLoad
                    ? Array.Empty<Point3Dto>()
                    : new[] { factored },
                BaseVector = surfaceLoad ? factored : null,
                Factor = 1.0,
                CoordinateSystem = "world",
                Provenance = new Dictionary<string, string>
                {
                    ["source"] = "Grasshopper",
                    ["force_unit"] = "kN",
                    ["input_factor"] =
                        factor.ToString("R", CultureInfo.InvariantCulture)
                }
            };
            EnsureValid(loadCase);

            var problem = new ProblemDto { Anchored = sup, Load = loadCase };
            EnsureValid(problem);

            SetPreview(topology, nodeIds, factored);
            Message = surfaceLoad
                ? "surface load"
                : $"{nodeIds.Count} node(s)";
            data.SetData(0, new ProblemGoo(problem));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Loads failed", error);
        }
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _previewArrows.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void DrawVisibleViewportWires(IGH_PreviewArgs args)
    {
        foreach (Line arrow in _previewArrows)
            args.Display.DrawArrow(arrow, Color.FromArgb(238, 135, 35));
    }

    /// <summary>
    /// One arrow per loaded node, pointing along the load vector into the
    /// node. Arrow length is proportional to the vector's magnitude: one
    /// force unit draws at three percent of the pattern's plan diagonal,
    /// capped at fifteen percent so a heavy case cannot swallow the model.
    /// </summary>
    private void SetPreview(
        TopologyDto topology,
        IReadOnlyList<int> nodeIds,
        Point3Dto factored)
    {
        _previewArrows.Clear();
        var vector = new Vector3d(factored.X, factored.Y, factored.Z);
        double magnitude = vector.Length;
        if (magnitude <= 1.0e-12 || topology.Vertices.Count == 0)
        {
            _clippingBox = BoundingBox.Empty;
            return;
        }

        Point3d[] points = topology.Vertices
            .Select(TnaWorkflowPreview.Point)
            .ToArray();
        double diagonal = new BoundingBox(points).Diagonal.Length;
        double length = Math.Min(
            magnitude * 0.03 * diagonal,
            0.15 * diagonal);
        Vector3d offset = vector * (length / magnitude);

        IEnumerable<int> targets = nodeIds.Count > 0
            ? nodeIds
            : Enumerable.Range(0, topology.Vertices.Count);
        foreach (int id in targets)
            _previewArrows.Add(new Line(points[id] - offset, points[id]));
        _clippingBox = TnaWorkflowPreview.Box(_previewArrows);
    }

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}
