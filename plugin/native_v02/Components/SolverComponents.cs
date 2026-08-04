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

/// <summary>
/// Bundle the shared reciprocal solve settings both the staged and one-shot
/// TNA Solve paths take. Crown height/force-scale mode and value stay on TNA
/// Solve itself; only the numerical controls live here so one Control can
/// feed either path without carrying design decisions that belong upstream.
/// </summary>
public sealed class ControlComponent : NativeComponentBase
{
    public ControlComponent()
        : base(
            "Control",
            "Control",
            "Bundle the horizontal/vertical reciprocal solve controls " +
            "shared by staged and one-shot TNA solving. Radial and other " +
            "high-valence patterns need far more horizontal iterations " +
            "than a quad grid; raise them until the reported reciprocity " +
            "angle falls to near zero.",
            ComponentCategories.FormFinding,
            "tna_control")
    {
    }

    public override Guid ComponentGuid =>
        new("a6d19e73-5f2b-4c8e-b0a4-9c3e7d1f5b28");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddNumberParameter(
            "Horizontal Alpha",
            "Alpha",
            "Horizontal reciprocal update factor from 0 to 100.",
            GH_ParamAccess.item,
            100.0);
        parameters.AddIntegerParameter(
            "Horizontal Iterations",
            "HI",
            "Maximum horizontal reciprocal iterations.",
            GH_ParamAccess.item,
            100);
        parameters.AddIntegerParameter(
            "Vertical Iterations",
            "VI",
            "Maximum vertical equilibrium iterations.",
            GH_ParamAccess.item,
            100);
        parameters.AddNumberParameter(
            "Tolerance",
            "Tol",
            "Positive vertical solve tolerance.",
            GH_ParamAccess.item,
            1.0e-3);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaControlParam(),
            "Control",
            "CTL",
            "Typed TNA numerical controls shared by staged and one-shot " +
            "TNA solving.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        double alpha = 100.0;
        int horizontalIterations = 100;
        int verticalIterations = 100;
        double tolerance = 1.0e-3;
        data.GetData(0, ref alpha);
        data.GetData(1, ref horizontalIterations);
        data.GetData(2, ref verticalIterations);
        data.GetData(3, ref tolerance);

        var control = new TnaControlDto
        {
            HorizontalAlpha = alpha,
            HorizontalIterations = horizontalIterations,
            VerticalIterations = verticalIterations,
            Tolerance = tolerance,
            Provenance = new Dictionary<string, string>
            {
                ["component"] = "Control"
            }
        };
        IReadOnlyList<string> errors = control.Validate();
        if (errors.Count > 0)
        {
            Message = "Invalid";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                string.Join(" ", errors));
            return;
        }

        Message =
            $"α={control.HorizontalAlpha:G4} · " +
            $"HI={control.HorizontalIterations} · " +
            $"VI={control.VerticalIterations}";
        data.SetData(0, new TnaControlGoo(control));
    }
}

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
        if (!GetSolveResults(data, out result!))
        {
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
            SagIterations = 10,
            SagTolerance = 0.01,
            FixedNodeIds = Array.Empty<int>(),
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
/// the shared Result contract. This is the redesigned TNA Equilibrium: no
/// separate Load Case input and no default-load fallback, because RLX's
/// Problem already guarantees one.
/// </summary>
public sealed class TnaSolveComponent :
    NativeTaskComponentBase<TnaSolveTaskResult>
{
    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            1,
            "Equilibrium Mode",
            new (string Label, string Value)[]
            {
                ("Crown Height", "zmax"),
                ("Force Scale (signed q)", "q")
            },
            "zmax")
    };

    public TnaSolveComponent()
        : base(
            "TNA Solve",
            "TNA Solve",
            "Solve a Relaxed Pattern by crown height or signed q scale " +
            "against the load case its Problem carries.",
            ComponentCategories.FormFinding,
            "tna_solve")
    {
    }

    public override Guid ComponentGuid =>
        new("9d2f4b86-7e1a-4c50-b3f7-6a8e0c9d1235");

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

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
            "CTL",
            "Optional solver controls from Control. Empty uses alpha 100 " +
            "with 100 horizontal and vertical iterations. Radial and other " +
            "high-valence patterns need far more horizontal iterations than " +
            "a quad grid; raise them until the reported reciprocity angle " +
            "falls to near zero. Mode and Value on this component override " +
            "the ones carried by Control.",
            GH_ParamAccess.item);
        parameters[3].Optional = true;
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
        if (!GetSolveResults(data, out result!))
        {
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

        Message =
            $"{result.Mode} - {result.Result.EdgeStates.Count} edges - " +
            $"{result.Elapsed.TotalMilliseconds:F0} ms";
        data.SetData(0, new ResultGoo(result.Result));
    }

    /// <summary>
    /// Read RLX plus this component's own Mode/Value, merging any supplied
    /// Control's numerical settings over the previous hardcoded defaults.
    /// Mode and Value stay on this component because they are the design
    /// decision; Control only ever supplies the solver's numerical knobs.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out RelaxedDto? relaxed,
        out TnaControlDto? control)
    {
        relaxed = null;
        control = null;
        RelaxedGoo? relaxedGoo = null;
        string modeInput = "zmax";
        double value = 5.0;
        if (!data.GetData(0, ref relaxedGoo) ||
            relaxedGoo?.Value is not RelaxedDto relaxedValue)
        {
            return false;
        }
        data.GetData(1, ref modeInput);
        data.GetData(2, ref value);

        TnaControlGoo? controlGoo = null;
        TnaControlDto? suppliedControl =
            data.GetData(3, ref controlGoo) ? controlGoo?.Value : null;

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
                ["component"] = "TNA Solve",
                ["controls"] = suppliedControl is null ? "defaults" : "Control",
                ["force_scale_semantics"] =
                    "signed_q_force_per_length_positive_tension"
            }
        };

        var errors = new List<string>();
        errors.AddRange(relaxedValue.Validate());
        errors.AddRange(controlValue.Validate());
        if (mode is not ("zmax" or "q"))
        {
            errors.Add(
                "Mode must be Crown Height (zmax) or Force Scale (q).");
        }
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
/// Run whole-network COMPAS force-density form finding against a Problem's
/// own load case, building the solver-neutral EquilibriumProblemDto the
/// fd.solve worker command expects internally from the shared Problem/RLX
/// spine rather than requiring one wired in from upstream.
/// </summary>
public sealed class FdSolveComponent :
    NativeTaskComponentBase<FdSolveTaskResult>
{
    public FdSolveComponent()
        : base(
            "FD Solve",
            "FD Solve",
            "Run whole-network COMPAS force-density form finding against " +
            "the load case the Problem carries.",
            ComponentCategories.FormFinding,
            "fd_solve")
    {
    }

    public override Guid ComponentGuid =>
        new("4b8c6e0a-3d9f-47b2-95c1-e7a2d8f4b096");

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
        parameters.AddParameter(
            new TnaControlParam(),
            "Control",
            "CTL",
            "Optional controls carried through to the Result for " +
            "provenance. FD's direct linear solve has no iterative knobs " +
            "of its own, so nothing here changes the solve itself.",
            GH_ParamAccess.item);
        parameters[2].Optional = true;
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
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out ProblemDto? problem,
                    out EquilibriumProblemDto? equilibriumProblem,
                    out FDSettingsDto? settings,
                    out TnaControlDto? control))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    ContractJson.DeepClone(problem!),
                    ContractJson.DeepClone(equilibriumProblem!),
                    ContractJson.DeepClone(settings!),
                    control is null ? null : ContractJson.DeepClone(control),
                    CancelToken),
                CancelToken));
            return;
        }

        FdSolveTaskResult result;
        if (!GetSolveResults(data, out result!))
        {
            if (!TryReadInputs(
                    data,
                    out ProblemDto? problem,
                    out EquilibriumProblemDto? equilibriumProblem,
                    out FDSettingsDto? settings,
                    out TnaControlDto? control))
            {
                return;
            }
            result = ComputeAsync(
                    ContractJson.DeepClone(problem!),
                    ContractJson.DeepClone(equilibriumProblem!),
                    ContractJson.DeepClone(settings!),
                    control is null ? null : ContractJson.DeepClone(control),
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

        Message =
            $"{result.Result.Equilibrium.Edges.Count} members - " +
            $"{result.Elapsed.TotalMilliseconds:F0} ms";
        data.SetData(0, new ResultGoo(result.Result));
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
        out FDSettingsDto? settings,
        out TnaControlDto? control)
    {
        problem = null;
        equilibriumProblem = null;
        settings = null;
        control = null;
        ProblemGoo? problemGoo = null;
        var forceDensities = new List<double>();
        if (!data.GetData(0, ref problemGoo) ||
            problemGoo?.Value is not ProblemDto problemValue)
        {
            return false;
        }
        data.GetDataList(1, forceDensities);
        if (forceDensities.Count == 0)
            forceDensities.Add(1.0);

        TnaControlGoo? controlGoo = null;
        TnaControlDto? suppliedControl =
            data.GetData(2, ref controlGoo) ? controlGoo?.Value : null;

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
        if (suppliedControl is not null)
            errors.AddRange(suppliedControl.Validate());
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
        control = suppliedControl;
        return true;
    }

    private static async Task<FdSolveTaskResult> ComputeAsync(
        ProblemDto problem,
        EquilibriumProblemDto equilibriumProblem,
        FDSettingsDto settings,
        TnaControlDto? control,
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
            solved = solved with
            {
                Problem = problem,
                Control = control
            };
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
