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
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

public sealed class TnaControlComponent : NativeComponentBase
{
    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            0,
            "Height Mode",
            new (string Label, string Value)[]
            {
                ("Crown Height", "zmax"),
                ("Force Scale", "q")
            },
            "zmax")
    };

    public TnaControlComponent()
        : base(
            "TNA Control",
            "TNA Control",
            "Bundle crown-height/force-scale and reciprocal solve controls.",
            ComponentCategories.FormFinding,
            "tna_control")
    {
    }

    public override Guid ComponentGuid =>
        new("678439fc-d4d9-4734-9567-3f266d3e978b");

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddTextParameter(
            "Height Mode",
            "Mode",
            "Crown Height (zmax) or Force Scale (q).",
            GH_ParamAccess.item,
            "zmax");
        parameters.AddNumberParameter(
            "Height Value",
            "Value",
            "Target crown elevation for zmax, or non-zero q scale.",
            GH_ParamAccess.item,
            5.0);
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
            "C",
            "Typed TNA physical and numerical controls.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        string mode = "zmax";
        double value = 5.0;
        double alpha = 100.0;
        int horizontalIterations = 100;
        int verticalIterations = 100;
        double tolerance = 1.0e-3;
        if (!data.GetData(0, ref mode))
            return;
        data.GetData(1, ref value);
        data.GetData(2, ref alpha);
        data.GetData(3, ref horizontalIterations);
        data.GetData(4, ref verticalIterations);
        data.GetData(5, ref tolerance);

        var control = new TnaControlDto
        {
            HeightMode = TnaControlDto.NormaliseHeightMode(mode),
            HeightValue = value,
            HorizontalAlpha = alpha,
            HorizontalIterations = horizontalIterations,
            VerticalIterations = verticalIterations,
            Tolerance = tolerance,
            Provenance = new Dictionary<string, string>
            {
                ["component"] = "TNA Control"
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
            $"{control.HeightMode}={control.HeightValue:G5} · " +
            $"α={control.HorizontalAlpha:G4}";
        data.SetData(0, new TnaControlGoo(control));
    }
}

public sealed record TnaSolveTaskResult(
    TnaResultDto? Result,
    Exception? Error,
    TimeSpan Elapsed,
    string LoadCaseName);

public sealed class TnaSolveComponent :
    NativeTaskComponentBase<TnaSolveTaskResult>
{
    private readonly List<PreviewEdge> _previewEdges = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaSolveComponent()
        : base(
            "TNA Solve",
            "TNA",
            "Solve a faced thrust network and preserve its reciprocal diagrams.",
            ComponentCategories.FormFinding,
            "tna_solve")
    {
    }

    public override Guid ComponentGuid =>
        new("8913cdd7-f563-4930-a310-fd62b3a31831");

    public override bool IsPreviewCapable => true;

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new EquilibriumProblemParam(),
            "Problem",
            "P",
            "A faced topology with supports and one or more named load cases.",
            GH_ParamAccess.item);
        parameters.AddParameter(
            new TnaControlParam(),
            "Control",
            "C",
            "TNA crown-height/force-scale and iteration controls.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Load Case",
            "LC",
            "Exact load-case name or zero-based index. Empty selects the first case.",
            GH_ParamAccess.item,
            string.Empty);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaResultParam(),
            "Result",
            "R",
            "One typed TNA state containing thrust, form and reciprocal force diagrams.",
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
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out EquilibriumProblemDto? problem,
                    out TnaControlDto? control,
                    out int loadCaseIndex,
                    out string loadCaseName))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    ContractJson.DeepClone(problem!),
                    ContractJson.DeepClone(control!),
                    loadCaseIndex,
                    loadCaseName,
                    CancelToken),
                CancelToken));
            return;
        }

        TnaSolveTaskResult result;
        if (!GetSolveResults(data, out result!))
        {
            if (!TryReadInputs(
                    data,
                    out EquilibriumProblemDto? problem,
                    out TnaControlDto? control,
                    out int loadCaseIndex,
                    out string loadCaseName))
            {
                return;
            }
            result = ComputeAsync(
                    ContractJson.DeepClone(problem!),
                    ContractJson.DeepClone(control!),
                    loadCaseIndex,
                    loadCaseName,
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
                "TNA Solve: " + result.Error.GetBaseException().Message);
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
            $"{result.LoadCaseName} · {result.Result.EdgeStates.Count} edges · " +
            $"{result.Elapsed.TotalMilliseconds:F0} ms";
        BuildPreview(result.Result);
        data.SetData(0, new TnaResultGoo(result.Result));
    }

    public override void DrawViewportWires(IGH_PreviewArgs args)
    {
        if (Hidden)
            return;
        base.DrawViewportWires(args);
        foreach (PreviewEdge edge in _previewEdges)
            args.Display.DrawLine(edge.Line, edge.Colour, 2);
    }

    private void BuildPreview(TnaResultDto result)
    {
        _previewEdges.Clear();
        foreach (TnaEdgeStateDto state in
                 result.EdgeStates.OrderBy(item => item.Id))
        {
            Line line = TnaQueryGeometry.ThrustLine(result, state);
            if (!line.IsValid)
                continue;
            _previewEdges.Add(
                new PreviewEdge(
                    line,
                    TnaQueryGeometry.ForceColour(state.ForceState)));
        }
        Point3d[] points = _previewEdges
            .SelectMany(edge => new[] { edge.Line.From, edge.Line.To })
            .ToArray();
        _clippingBox = points.Length == 0
            ? BoundingBox.Empty
            : new BoundingBox(points);
    }

    private bool TryReadInputs(
        IGH_DataAccess data,
        out EquilibriumProblemDto? problem,
        out TnaControlDto? control,
        out int loadCaseIndex,
        out string loadCaseName)
    {
        problem = null;
        control = null;
        loadCaseIndex = 0;
        loadCaseName = string.Empty;
        EquilibriumProblemGoo? problemGoo = null;
        TnaControlGoo? controlGoo = null;
        string selector = string.Empty;
        if (!data.GetData(0, ref problemGoo) ||
            problemGoo?.Value is not EquilibriumProblemDto problemValue ||
            !data.GetData(1, ref controlGoo) ||
            controlGoo?.Value is not TnaControlDto controlValue)
        {
            return false;
        }
        data.GetData(2, ref selector);

        var errors = new List<string>();
        errors.AddRange(problemValue.Validate());
        errors.AddRange(controlValue.Validate());
        if (!string.Equals(
                problemValue.Topology?.NetworkKind,
                "faced",
                StringComparison.OrdinalIgnoreCase) ||
            problemValue.Topology?.Faces.Count == 0)
        {
            errors.Add("TNA Solve requires a faced topology with registered faces.");
        }
        try
        {
            loadCaseIndex = ResolveLoadCase(
                problemValue.LoadCases,
                selector);
            loadCaseName = problemValue.LoadCases[loadCaseIndex].Name;
        }
        catch (ArgumentException error)
        {
            errors.Add(error.Message);
        }
        if (errors.Count > 0)
        {
            Message = "Invalid";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                string.Join(" ", errors));
            return false;
        }

        problem = problemValue;
        control = controlValue;
        return true;
    }

    internal static int ResolveLoadCase(
        IReadOnlyList<LoadCaseDto> loadCases,
        string? selector)
    {
        if (loadCases is null || loadCases.Count == 0)
            throw new ArgumentException("Problem contains no load cases.");
        string key = (selector ?? string.Empty).Trim();
        if (key.Length == 0)
            return 0;
        if (int.TryParse(
                key,
                NumberStyles.Integer,
                CultureInfo.InvariantCulture,
                out int index))
        {
            if (index >= 0 && index < loadCases.Count)
                return index;
            throw new ArgumentException(
                $"Load Case index must be between 0 and {loadCases.Count - 1}.");
        }

        int[] matches = loadCases
            .Select((loadCase, index) => (loadCase, index))
            .Where(item =>
                string.Equals(
                    item.loadCase.Name,
                    key,
                    StringComparison.OrdinalIgnoreCase) ||
                HasStableId(item.loadCase, key))
            .Select(item => item.index)
            .ToArray();
        if (matches.Length == 1)
            return matches[0];
        if (matches.Length > 1)
            throw new ArgumentException($"Load Case selector '{key}' is ambiguous.");
        throw new ArgumentException(
            $"Load Case '{key}' was not found. Available cases: " +
            string.Join(", ", loadCases.Select(item => item.Name)) + ".");
    }

    private static bool HasStableId(
        LoadCaseDto loadCase,
        string selector)
    {
        foreach (string key in new[] { "id", "stable_id", "case_id" })
        {
            if (loadCase.Provenance.TryGetValue(key, out string? value) &&
                string.Equals(
                    value,
                    selector,
                    StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }
        return false;
    }

    private static async Task<TnaSolveTaskResult> ComputeAsync(
        EquilibriumProblemDto problem,
        TnaControlDto control,
        int loadCaseIndex,
        string loadCaseName,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            IReadOnlyDictionary<string, object?> payload =
                problem.ToTnaSolvePayload(control, loadCaseIndex);
            JsonElement response = await WorkerRuntime.Host
                .RequestAsync<JsonElement>(
                    "tna.solve",
                    payload,
                    cancellationToken)
                .ConfigureAwait(false);
            TnaResultDto result = TnaWorkerResultCodec.Decode(
                response,
                problem,
                control,
                loadCaseIndex);
            stopwatch.Stop();
            return new TnaSolveTaskResult(
                result,
                null,
                stopwatch.Elapsed,
                loadCaseName);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new TnaSolveTaskResult(
                null,
                error,
                stopwatch.Elapsed,
                loadCaseName);
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

    private sealed record PreviewEdge(Line Line, Color Colour);
}
