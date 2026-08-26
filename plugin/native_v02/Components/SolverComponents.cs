#nullable enable

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

public sealed record TnaRelaxTaskResult(
    TnaPreparedDto? Prepared,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// Run the real, stateless Pattern relaxation/boundary-opening worker stage
/// against the shared spine's Problem. The returned force graph is
/// explicitly an unbalanced topological dual, paired with the Problem it
/// will be solved against so Deconstruct and Export can recover every
/// upstream input at this depth without a second wire back to the spine.
/// </summary>
public sealed class TnaRelaxComponent :
    NativeTaskComponentBase<TnaRelaxTaskResult>
{
    private readonly List<Line> _formPreview = new();
    private readonly List<Line> _forcePreview = new();
    private readonly List<Line> _boundaryPreview = new();
    private readonly List<Point3d> _supportPreview = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaRelaxComponent()
        : base(
            "TNA Relax",
            "TNA Relax",
            "Relax the Problem's plan Pattern, match unsupported-boundary " +
            "sag, and build an inspectable unbalanced topological force " +
            "dual.",
            ComponentCategories.FormFinding,
            "tna_relax")
    {
    }

    public override Guid ComponentGuid =>
        new("e5a0c8d4-2b7f-4963-a1e8-7d3b9f5c2084");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new ProblemParam(),
            "Problem",
            "PRB",
            "The Anchored Pattern bundled with the load case from Loads.",
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
        parameters.AddPointParameter(
            "Floating Anchors",
            "FA",
            "Anchors that hold their plan position but not their height. " +
            "Nodes named here are held while the boundary relaxes, WITHOUT " +
            "joining the support set. An oculus rim belongs here rather than " +
            "on Supports: held in plan the ring keeps its shape at any sag, " +
            "and left off the support set its height stays free for the " +
            "vertical solve, so the opening floats at the crown instead of " +
            "being pinned to the springing plane.",
            GH_ParamAccess.list);
        parameters[3].Optional = true;
        parameters[3].DataMapping = GH_DataMapping.Flatten;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new RelaxedParam(),
            "Relaxed",
            "RLX",
            "Relaxed Pattern, opening records, and unsolved form/force " +
            "state paired with the Problem it solves.",
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
                    out TnaPrepareConfigDto? config,
                    out ProblemDto? _))
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

        if (!TryReadInputs(
                data,
                out TnaPatternDto? fallbackPattern,
                out TnaPrepareConfigDto? fallbackConfig,
                out ProblemDto? problem))
        {
            return;
        }

        TnaRelaxTaskResult result;
        bool haveTaskResult = GetSolveResults(data, out result!);
        if (!haveTaskResult ||
            result.Error is OperationCanceledException)
        {
            // A background task cancelled by a mid-drag solution race is
            // not a verdict on the current inputs, and Grasshopper does
            // not always follow a late cancellation with another
            // solution: the canvas stayed on "Cancelled" with an empty
            // output and no boundary preview until something forced a
            // re-solve. Recompute synchronously for the solution that is
            // actually completing.
            result = ComputeAsync(
                    ContractJson.DeepClone(fallbackPattern!),
                    fallbackConfig!,
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
                "TNA Relax: " +
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
                "TNA Relax produced no prepared state.");
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
        data.SetData(
            0,
            new RelaxedGoo(new RelaxedDto
            {
                Prepared = result.Prepared,
                Problem = problem
            }));
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

    /// <summary>
    /// Read the Problem, split it back into the Pattern (with its anchors
    /// attached as an explicit SupportSet) and the plan-FDM config the
    /// existing <c>tna.prepare</c> worker call expects, and hand back the
    /// original Problem unchanged so it can travel through to Relaxed.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out TnaPatternDto? pattern,
        out TnaPrepareConfigDto? config,
        out ProblemDto? problem)
    {
        pattern = null;
        config = null;
        problem = null;
        ProblemGoo? problemGoo = null;
        double q = 1.0;
        double sagPercent = 10.0;
        if (!data.GetData(0, ref problemGoo) ||
            problemGoo?.Value is not ProblemDto value)
        {
            return false;
        }
        data.GetData(1, ref q);
        data.GetData(2, ref sagPercent);
        var fixedPoints = new List<Point3d>();
        data.GetDataList(3, fixedPoints);

        var errors = new List<string>(value.Validate());
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

        // value.Validate() above already guarantees Anchored, Anchored.Pattern
        // and Anchored.Pattern.Topology are all present.
        TnaPatternDto sourcePattern = value.Anchored!.Pattern!;
        TopologyDto topology = sourcePattern.Topology!;
        // Plan-fixed nodes are held by prepare_tna_problem's ``held_always``
        // set, which is the union of the supports and the fixed-plan keys.
        // Being in that set only stops the boundary relaxation's apron from
        // recruiting them; it never marks them ``is_support``, so
        // FormDiagram.update_boundaries still takes its zero-support branch
        // for an unanchored hole and the vertical solve is free to lift the
        // rim. That distinction is the whole point of this input.
        int[] fixedNodeIds = Array.Empty<int>();
        if (fixedPoints.Count > 0)
        {
            try
            {
                SnappedTargets snappedFixed = TopologyTargets.Resolve(
                    topology,
                    fixedPoints,
                    value.Anchored.SnapTolerance,
                    "Floating anchor");
                fixedNodeIds = snappedFixed.NodeIds.Distinct().ToArray();
            }
            catch (Exception error)
            {
                Message = "Invalid";
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    "Floating Anchors failed: " + error.Message);
                return false;
            }
        }
        var supportSet = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = "explicit",
            Points = Array.Empty<Point3Dto>(),
            NodeIds = value.Anchored.AnchorNodeIds,
            SnapTolerance = value.Anchored.SnapTolerance,
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["source"] = "Supports",
                ["point_targets_resolved"] = "true"
            }
        };

        problem = value;
        pattern = sourcePattern with { Supports = supportSet };
        config = new TnaPrepareConfigDto
        {
            ForceDensity = q,
            Relax = true,
            BoundarySag = sagPercent / 100.0,
            SagIterations = 50,
            SagTolerance = 0.01,
            FixedNodeIds = fixedNodeIds,
            Metadata = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["component"] = "TNA Relax",
                ["sag_input_percent"] =
                    sagPercent.ToString("R", CultureInfo.InvariantCulture)
            }
        };
        return true;
    }

    private static async Task<TnaRelaxTaskResult> ComputeAsync(
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
            return new TnaRelaxTaskResult(
                prepared,
                null,
                stopwatch.Elapsed);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new TnaRelaxTaskResult(
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

public sealed record TnaSolveTaskResult(
    ResultDto? Result,
    Exception? Error,
    TimeSpan Elapsed,
    string Mode);

/// <summary>
/// Solve a Relaxed stage's prepared Pattern against the load case its own
/// Problem always carries, and decode the worker's unified envelope into
/// the shared Result contract. A blank Height solves to the natural
/// equilibrium height of the current force densities and reports it; a
/// number solves the vertical scale so the crown lands exactly there. A
/// blank Iterations runs the worker's auto-converging horizontal solve,
/// so radial and other slow-converging patterns no longer need a manually
/// tuned count. Alongside the Result envelope the component returns the
/// thrust network as native Grasshopper geometry, so the solved vault can
/// be used directly, not only visualised.
/// </summary>
public class TnaSolveComponent :
    NativeTaskComponentBase<TnaSolveTaskResult>
{
    // Lazily assigned: a Mesh constructor touches Rhino's native runtime,
    // which must not happen while Grasshopper merely enumerates components.
    private Mesh? _previewMesh;
    private readonly List<Point3d> _previewSupports = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaSolveComponent()
        : this(
            "TNA Solve",
            "TNA Solve",
            "Solve a Relaxed Pattern against the load case its Problem " +
            "carries. Blank Height finds the natural equilibrium height; " +
            "a number solves exactly to that crown height. Blank " +
            "Iterations auto-converges the reciprocal diagrams.")
    {
    }

    protected TnaSolveComponent(
        string name,
        string nickname,
        string description)
        : base(
            name,
            nickname,
            description,
            ComponentCategories.FormFinding,
            "tna_solve")
    {
        for (int index = 1; index < Params.Output.Count; index++)
        {
            if (Params.Output[index] is IGH_PreviewObject preview)
                preview.Hidden = true;
        }
    }

    /// <summary>
    /// The worker-side horizontal solver this component requests;
    /// the algebraic sibling overrides it.
    /// </summary>
    protected virtual string SolveMethod => "iterative";

    /// <summary>
    /// Whether the component carries the Iterations input. The algebraic
    /// sibling has no iteration knob worth exposing, so it drops the port
    /// and Run moves up one index.
    /// </summary>
    protected virtual bool HasIterationsInput => true;

    public override Guid ComponentGuid =>
        new("9d2f4b86-7e1a-4c50-b3f7-6a8e0c9d1235");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new RelaxedParam(),
            "Relaxed",
            "RLX",
            "Relaxed Pattern paired with the Problem carrying its load " +
            "case, from TNA Relax.",
            GH_ParamAccess.item);
        parameters.AddNumberParameter(
            "Height",
            "H",
            "Optional target crown height. Blank solves to the natural " +
            "equilibrium height of the current force densities and " +
            "reports it below the component; a number scales the solve " +
            "so the highest point lands exactly there.",
            GH_ParamAccess.item);
        parameters[1].Optional = true;
        if (HasIterationsInput)
        {
            parameters.AddIntegerParameter(
                "Iterations",
                "I",
                "Optional horizontal iteration count. Blank " +
                "auto-converges: the worker keeps the best reciprocal " +
                "state it finds and polishes within a bounded budget " +
                "beyond acceptance, stopping earlier at a tenth of a " +
                "degree or on a plateau; under five degrees " +
                "(RhinoVault's own acceptance) counts as converged. " +
                "Tolerance is fixed through the whole calculation.",
                GH_ParamAccess.item);
            parameters[2].Optional = true;
        }
        parameters.AddBooleanParameter(
            "Run",
            "Run",
            "False holds the solve so upstream edits stay responsive; " +
            "True runs it.",
            GH_ParamAccess.item,
            true);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new ResultParam(),
            "Result",
            "RES",
            "Solved thrust network carried in the unified Result envelope.",
            GH_ParamAccess.item);
        parameters.AddMeshParameter(
            "Thrust Mesh",
            "M",
            "The solved funicular shape as a native mesh.",
            GH_ParamAccess.item);
        parameters.AddLineParameter(
            "Thrust Lines",
            "L",
            "The solved thrust-network members as native lines.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Supports",
            "S",
            "The structural support nodes as native points.",
            GH_ParamAccess.list);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _previewMesh = null;
        _previewSupports.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    public override void DrawViewportMeshes(IGH_PreviewArgs args)
    {
        if (Hidden || _previewMesh is null || _previewMesh.Faces.Count == 0)
            return;
        args.Display.DrawMeshShaded(
            _previewMesh,
            new DisplayMaterial(Color.FromArgb(225, 222, 215), 0.35));
    }

    public override void DrawViewportWires(IGH_PreviewArgs args)
    {
        if (Hidden)
            return;
        base.DrawViewportWires(args);
        if (_previewMesh is not null && _previewMesh.Faces.Count > 0)
        {
            args.Display.DrawMeshWires(
                _previewMesh,
                Color.FromArgb(95, 95, 100));
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

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out RelaxedDto? relaxed,
                    out TnaControlDto? control))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    ContractJson.DeepClone(relaxed!),
                    ContractJson.DeepClone(control!),
                    CancelToken),
                CancelToken));
            return;
        }

        TnaSolveTaskResult result;
        bool haveTaskResult = GetSolveResults(data, out result!);
        if (!haveTaskResult ||
            result.Error is OperationCanceledException)
        {
            // A cancelled background task is a scheduling race, not a
            // verdict on the current inputs; recompute synchronously so a
            // late cancellation cannot strand the canvas on "Cancelled"
            // with empty outputs and a stale preview.
            if (!TryReadInputs(
                    data,
                    out RelaxedDto? relaxed,
                    out TnaControlDto? control))
            {
                return;
            }
            result = ComputeAsync(
                    ContractJson.DeepClone(relaxed!),
                    ContractJson.DeepClone(control!),
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
                "TNA Solve: " +
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
                "TNA Solve produced no result.");
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

        Mesh thrustMesh = TnaResultGeometry.ThrustMesh(result.Result);
        List<Line> thrustLines = TnaResultGeometry.MemberLines(result.Result);
        List<Point3d> supports = TnaResultGeometry.SupportPoints(result.Result);
        _previewMesh = thrustMesh;
        _previewSupports.Clear();
        _previewSupports.AddRange(supports);
        _clippingBox = thrustMesh.Faces.Count > 0
            ? thrustMesh.GetBoundingBox(false)
            : TnaWorkflowPreview.Box(thrustLines, supports);

        IReadOnlyDictionary<string, double> metrics =
            TnaResultGeometry.Metrics(result.Result);
        var summary = new List<string>();
        if (metrics.TryGetValue("zmax_solved", out double solvedHeight))
            summary.Add($"z {solvedHeight:G4}");
        if (metrics.TryGetValue(
                "max_reciprocal_angle_deviation",
                out double angle))
        {
            summary.Add($"angle {angle:F1}°");
        }
        if (metrics.TryGetValue(
                "horizontal_converged",
                out double converged) &&
            converged < 0.5)
        {
            bool autoMode = metrics.TryGetValue(
                    "horizontal_mode_is_auto",
                    out double isAuto) &&
                isAuto >= 0.5;
            string advice = autoMode
                ? "More iterations will not pass the gate: the held " +
                  "pattern interior is not in horizontal equilibrium. " +
                  "Smooth the pattern or accept the residual."
                : "Raise Iterations, or leave the input blank for " +
                  "auto-convergence.";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                $"Reciprocity stalled at {angle:F1}° on force-bearing " +
                "edges (RhinoVault accepts under 5°). " + advice);
        }
        if (metrics.TryGetValue(
                "algebraic_negative_q_count",
                out double negativeQ) &&
            negativeQ >= 1.0)
        {
            // Information, not failure: the exact solve names the edges
            // that need ties, where the iterative solver expresses the
            // same fact as residual unbalanced thrust. Only a pattern
            // that leans heavily on tension escalates to a warning.
            int edgeCount = Math.Max(1, result.Result.EdgeStates.Count);
            double share = negativeQ / edgeCount;
            AddRuntimeMessage(
                share > 0.05
                    ? GH_RuntimeMessageLevel.Warning
                    : GH_RuntimeMessageLevel.Remark,
                $"{negativeQ:F0} of {edgeCount} edges " +
                $"({share:P1}) need tension for exact horizontal " +
                "equilibrium; the iterative solver expresses the same " +
                "fact as residual unbalanced thrust. Place ties there, " +
                "or adjust the pattern/supports if strict " +
                "compression-only is required.");
        }
        summary.Add($"{result.Elapsed.TotalMilliseconds:F0} ms");
        Message = string.Join(" · ", summary);

        data.SetData(0, new ResultGoo(result.Result));
        data.SetData(1, thrustMesh);
        data.SetDataList(2, thrustLines);
        data.SetDataList(3, supports);
    }

    /// <summary>
    /// Read RLX plus this component's own optional Height and Iterations.
    /// Absence is meaningful on both: no Height means the natural
    /// equilibrium height, no Iterations means the auto-converging
    /// horizontal solve. Alpha and tolerance are fixed; they were knobs
    /// nobody needed to turn.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out RelaxedDto? relaxed,
        out TnaControlDto? control)
    {
        relaxed = null;
        control = null;
        RelaxedGoo? relaxedGoo = null;
        double height = 0.0;
        int iterations = 0;
        bool run = true;
        data.GetData(HasIterationsInput ? 3 : 2, ref run);
        if (!run)
        {
            Message = "Off";
            return false;
        }
        if (!data.GetData(0, ref relaxedGoo) ||
            relaxedGoo?.Value is not RelaxedDto relaxedValue)
        {
            return false;
        }
        bool hasHeight = data.GetData(1, ref height);
        bool hasIterations =
            HasIterationsInput && data.GetData(2, ref iterations);

        var controlValue = new TnaControlDto
        {
            HeightMode = hasHeight ? "zmax" : "natural",
            HeightValue = hasHeight ? height : null,
            HorizontalAlpha = 100.0,
            HorizontalIterations = hasIterations ? iterations : null,
            HorizontalMethod = SolveMethod,
            VerticalIterations = 1000,
            Tolerance = 1.0e-3,
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["component"] = Name,
                ["controls"] = "component"
            }
        };

        var errors = new List<string>();
        errors.AddRange(relaxedValue.Validate());
        errors.AddRange(controlValue.Validate());
        if (errors.Count > 0)
        {
            Message = "Invalid";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                string.Join(" ", errors));
            return false;
        }

        relaxed = relaxedValue;
        control = controlValue;
        return true;
    }

    private static async Task<TnaSolveTaskResult> ComputeAsync(
        RelaxedDto relaxed,
        TnaControlDto control,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            TnaPreparedDto prepared = relaxed.Prepared!;
            LoadCaseDto loadCase = relaxed.Problem!.Load!;
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
            ResultDto solved = TnaWorkerResultCodec.DecodeResult(
                response,
                analysisProblem,
                control,
                0);
            solved = solved with { Problem = relaxed.Problem };
            stopwatch.Stop();
            return new TnaSolveTaskResult(
                solved,
                null,
                stopwatch.Elapsed,
                TnaControlDto.NormaliseHeightMode(control.HeightMode));
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new TnaSolveTaskResult(
                null,
                error,
                stopwatch.Elapsed,
                TnaControlDto.NormaliseHeightMode(control.HeightMode));
        }
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

public sealed record FdSolveTaskResult(
    ResultDto? Result,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// TNA Solve with the algebraic horizontal method: exact force densities
/// from the equilibrium matrix in one sparse least-squares solve, then a
/// single reciprocal fit for the force diagram. Same surface as TNA
/// Solve minus the Iterations input, because the direct solve has no
/// iteration knob worth turning.
/// </summary>
public sealed class TnaSolveAlgebraicComponent : TnaSolveComponent
{
    public TnaSolveAlgebraicComponent()
        : base(
            "TNA Solve Algebraic",
            "TNA Solve A",
            "Solve a Relaxed Pattern with the algebraic horizontal " +
            "method: exact force densities from the equilibrium matrix " +
            "in one sparse least-squares solve, reaching machine-" +
            "precision reciprocity wherever the pattern admits it. " +
            "Blank Height finds the natural equilibrium height.")
    {
    }

    public override Guid ComponentGuid =>
        new("b7c3e9a1-4f6d-4a82-9c05-2d8e7b3f5a19");

    protected override string SolveMethod => "algebraic";

    protected override bool HasIterationsInput => false;
}

/// <summary>
/// Run whole-network COMPAS force-density form finding against a Problem's
/// own load case, building the solver-neutral EquilibriumProblemDto the
/// fd.solve worker command expects internally from the shared Problem/RLX
/// spine rather than requiring one wired in from upstream.
/// </summary>
public sealed class FdSolveComponent :
    NativeTaskComponentBase<FdSolveTaskResult>
{
    private readonly List<Line> _previewLines = new();
    private readonly List<Point3d> _previewSupports = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public FdSolveComponent()
        : base(
            "FD Solve",
            "FD Solve",
            "Run whole-network COMPAS force-density form finding against " +
            "the load case the Problem carries.",
            ComponentCategories.FormFinding,
            "fd_solve")
    {
        for (int index = 1; index < Params.Output.Count; index++)
        {
            if (Params.Output[index] is IGH_PreviewObject preview)
                preview.Hidden = true;
        }
    }

    public override Guid ComponentGuid =>
        new("4b8c6e0a-3d9f-47b2-95c1-e7a2d8f4b096");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new ProblemParam(),
            "Problem",
            "PRB",
            "The Anchored Pattern bundled with the load case to solve " +
            "against it.",
            GH_ParamAccess.item);
        parameters.AddNumberParameter(
            "Force Density",
            "q",
            "One value broadcasts to all members; otherwise provide one " +
            "per member. Numeric units are Force Unit per Length Unit.",
            GH_ParamAccess.list);
        parameters[1].DataMapping = GH_DataMapping.Flatten;
        parameters[1].Optional = true;
        parameters.AddBooleanParameter(
            "Run",
            "Run",
            "False holds the solve so upstream edits stay responsive; " +
            "True runs it.",
            GH_ParamAccess.item,
            true);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new ResultParam(),
            "Result",
            "RES",
            "Stable COMPAS FD result carried in the unified Result " +
            "envelope.",
            GH_ParamAccess.item);
        parameters.AddLineParameter(
            "Member Lines",
            "L",
            "The solved network members as native lines.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Supports",
            "S",
            "The support nodes as native points.",
            GH_ParamAccess.list);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _previewLines.Clear();
        _previewSupports.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    public override void DrawViewportWires(IGH_PreviewArgs args)
    {
        if (Hidden)
            return;
        base.DrawViewportWires(args);
        foreach (Line line in _previewLines)
            args.Display.DrawLine(line, Color.FromArgb(95, 95, 100), 1);
        foreach (Point3d point in _previewSupports)
        {
            args.Display.DrawPoint(
                point,
                PointStyle.RoundControlPoint,
                4,
                Color.FromArgb(30, 165, 85));
        }
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out ProblemDto? problem,
                    out EquilibriumProblemDto? equilibriumProblem,
                    out FDSettingsDto? settings))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    ContractJson.DeepClone(problem!),
                    ContractJson.DeepClone(equilibriumProblem!),
                    ContractJson.DeepClone(settings!),
                    CancelToken),
                CancelToken));
            return;
        }

        FdSolveTaskResult result;
        bool haveTaskResult = GetSolveResults(data, out result!);
        if (!haveTaskResult ||
            result.Error is OperationCanceledException)
        {
            // A cancelled background task is a scheduling race, not a
            // verdict on the current inputs; recompute synchronously so a
            // late cancellation cannot strand the canvas on "Cancelled"
            // with empty outputs.
            if (!TryReadInputs(
                    data,
                    out ProblemDto? problem,
                    out EquilibriumProblemDto? equilibriumProblem,
                    out FDSettingsDto? settings))
            {
                return;
            }
            result = ComputeAsync(
                    ContractJson.DeepClone(problem!),
                    ContractJson.DeepClone(equilibriumProblem!),
                    ContractJson.DeepClone(settings!),
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();
        }

        if (result.Error is not null)
        {
            Message = result.Error is OperationCanceledException
                ? "Cancelled"
                : "Failed";
            GH_RuntimeMessageLevel level =
                result.Error is OperationCanceledException
                    ? GH_RuntimeMessageLevel.Warning
                    : GH_RuntimeMessageLevel.Error;
            AddRuntimeMessage(
                level,
                "FD Solve: " + result.Error.GetBaseException().Message);

            IReadOnlyList<string> stderr = SafeRecentStderr();
            foreach (string line in stderr.TakeLast(3))
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, line);
            return;
        }
        if (result.Result?.Equilibrium is null)
        {
            Message = "Failed";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                "FD Solve produced no result.");
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

        List<Line> memberLines = TnaResultGeometry.MemberLines(result.Result);
        List<Point3d> supports = TnaResultGeometry.SupportPoints(result.Result);
        _previewLines.Clear();
        _previewLines.AddRange(memberLines);
        _previewSupports.Clear();
        _previewSupports.AddRange(supports);
        _clippingBox = TnaWorkflowPreview.Box(memberLines, supports);

        Message =
            $"{result.Result.Equilibrium.Edges.Count} members - " +
            $"{result.Elapsed.TotalMilliseconds:F0} ms";
        data.SetData(0, new ResultGoo(result.Result));
        data.SetDataList(1, memberLines);
        data.SetDataList(2, supports);
    }

    /// <summary>
    /// Read PRB and this component's own Force Density, then reconstruct
    /// the solver-neutral EquilibriumProblemDto fd.solve expects: PRB's
    /// AnchorNodeIds become an explicit SupportSetDto (the same pattern TNA
    /// Relax follows), and PRB's own Load becomes the sole load case.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out ProblemDto? problem,
        out EquilibriumProblemDto? equilibriumProblem,
        out FDSettingsDto? settings)
    {
        problem = null;
        equilibriumProblem = null;
        settings = null;
        ProblemGoo? problemGoo = null;
        var forceDensities = new List<double>();
        bool run = true;
        data.GetData(2, ref run);
        if (!run)
        {
            Message = "Off";
            return false;
        }
        if (!data.GetData(0, ref problemGoo) ||
            problemGoo?.Value is not ProblemDto problemValue)
        {
            return false;
        }
        data.GetDataList(1, forceDensities);
        if (forceDensities.Count == 0)
            forceDensities.Add(1.0);

        var settingsValue = new FDSettingsDto
        {
            ForceDensities = forceDensities.ToArray(),
            SignConvention = "positive_tension",
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["component"] = "FD Solve"
            }
        };

        var errors = new List<string>(problemValue.Validate());
        errors.AddRange(settingsValue.Validate());
        if (errors.Count > 0)
        {
            Message = "Invalid";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                string.Join(" ", errors));
            return false;
        }

        // problemValue.Validate() above already guarantees Anchored,
        // Anchored.Pattern, Anchored.Pattern.Topology, and Load are present.
        TopologyDto topology = problemValue.Anchored!.Pattern!.Topology!;
        var supports = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = "explicit",
            Points = Array.Empty<Point3Dto>(),
            NodeIds = problemValue.Anchored.AnchorNodeIds,
            SnapTolerance = problemValue.Anchored.SnapTolerance,
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["source"] = "Supports",
                ["point_targets_resolved"] = "true"
            }
        };
        var equilibriumProblemValue = new EquilibriumProblemDto
        {
            Name = "fd-solve",
            Topology = topology,
            Supports = supports,
            LoadCases = new[] { problemValue.Load! },
            Provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["source"] = "FD Solve"
            }
        };

        int edgeCount = topology.Edges.Count;
        int densityCount = settingsValue.ForceDensities.Count;
        if (densityCount != 1 && densityCount != edgeCount)
        {
            Message = "Invalid";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                "Force Density must contain one broadcast value or " +
                $"exactly {edgeCount} member values.");
            return false;
        }

        problem = problemValue;
        equilibriumProblem = equilibriumProblemValue;
        settings = settingsValue;
        return true;
    }

    private static async Task<FdSolveTaskResult> ComputeAsync(
        ProblemDto problem,
        EquilibriumProblemDto equilibriumProblem,
        FDSettingsDto settings,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            IReadOnlyDictionary<string, object?> payload =
                equilibriumProblem.ToFdSolvePayload(settings, 0);
            JsonElement response = await WorkerRuntime.Host
                .RequestAsync<JsonElement>(
                    "fd.solve",
                    payload,
                    cancellationToken)
                .ConfigureAwait(false);
            ResultDto solved = WorkerResultCodec.DecodeResult(
                response,
                equilibriumProblem,
                settings,
                0);
            solved = solved with { Problem = problem };
            stopwatch.Stop();
            return new FdSolveTaskResult(solved, null, stopwatch.Elapsed);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new FdSolveTaskResult(null, error, stopwatch.Elapsed);
        }
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
