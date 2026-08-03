using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Ananke.COMPAS.Native.Backend;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Components;

public sealed record FDSolveTaskResult(
    EquilibriumResultDto? Result,
    Exception? Error,
    TimeSpan Elapsed);

public sealed class FDSolveComponent :
    NativeTaskComponentBase<FDSolveTaskResult>
{
    public FDSolveComponent()
        : base(
            "FD Solve",
            "FD",
            "Run whole-network COMPAS force-density form finding.",
            ComponentCategories.FormFinding,
            "fd_solve")
    {
    }

    public override Guid ComponentGuid =>
        new("cfcade39-f94d-4367-b9a8-9defedeff537");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new EquilibriumProblemParam(),
            "Problem",
            "P",
            "Validated edge topology, supports, and load cases. A faced " +
            "mesh is solved through its registered edge network.",
            GH_ParamAccess.item);
        parameters.AddParameter(
            new FDSettingsParam(),
            "Settings",
            "S",
            "Force-density values. Native FD uses positive=tension.",
            GH_ParamAccess.item);
        parameters.AddIntegerParameter(
            "Load Case Index",
            "LC",
            "Zero-based load-case index from the Problem.",
            GH_ParamAccess.item,
            0);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new EquilibriumResultParam(),
            "Result",
            "R",
            "Stable COMPAS FD result with geometry, forces, and diagnostics.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out EquilibriumProblemDto? problem,
                    out FDSettingsDto? settings,
                    out int loadCaseIndex))
            {
                return;
            }

            EquilibriumProblemDto frozenProblem =
                ContractJson.DeepClone(problem!);
            FDSettingsDto frozenSettings =
                ContractJson.DeepClone(settings!);
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    frozenProblem,
                    frozenSettings,
                    loadCaseIndex,
                    CancelToken),
                CancelToken));
            return;
        }

        FDSolveTaskResult result;
        if (!GetSolveResults(data, out result!))
        {
            if (!TryReadInputs(
                    data,
                    out EquilibriumProblemDto? problem,
                    out FDSettingsDto? settings,
                    out int loadCaseIndex))
            {
                return;
            }
            result = ComputeAsync(
                    ContractJson.DeepClone(problem!),
                    ContractJson.DeepClone(settings!),
                    loadCaseIndex,
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
        if (result.Result is null)
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
            $"{result.Result.Edges.Count} members · " +
            $"{result.Elapsed.TotalMilliseconds:F0} ms";
        data.SetData(0, new EquilibriumResultGoo(result.Result));
    }

    private bool TryReadInputs(
        IGH_DataAccess data,
        out EquilibriumProblemDto? problem,
        out FDSettingsDto? settings,
        out int loadCaseIndex)
    {
        problem = null;
        settings = null;
        loadCaseIndex = 0;
        EquilibriumProblemGoo? problemGoo = null;
        FDSettingsGoo? settingsGoo = null;
        if (!data.GetData(0, ref problemGoo) ||
            problemGoo?.Value is not EquilibriumProblemDto problemValue ||
            !data.GetData(1, ref settingsGoo) ||
            settingsGoo?.Value is not FDSettingsDto settingsValue)
        {
            return false;
        }
        data.GetData(2, ref loadCaseIndex);

        var errors = new List<string>();
        errors.AddRange(problemValue.Validate());
        errors.AddRange(settingsValue.Validate());
        if (problemValue.Topology?.NetworkKind is not ("line" or "faced"))
            errors.Add("FD Solve requires a registered edge topology.");
        if (loadCaseIndex < 0 ||
            loadCaseIndex >= problemValue.LoadCases.Count)
        {
            errors.Add(
                $"Load Case Index must be between 0 and " +
                $"{problemValue.LoadCases.Count - 1}.");
        }
        int densityCount = settingsValue.ForceDensities.Count;
        int edgeCount = problemValue.Topology?.Edges.Count ?? 0;
        if (densityCount != 1 && densityCount != edgeCount)
        {
            errors.Add(
                "Force Densities must contain one broadcast value or " +
                $"exactly {edgeCount} member values.");
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
        settings = settingsValue;
        return true;
    }

    private static async Task<FDSolveTaskResult> ComputeAsync(
        EquilibriumProblemDto problem,
        FDSettingsDto settings,
        int loadCaseIndex,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            IReadOnlyDictionary<string, object?> payload =
                problem.ToFdSolvePayload(settings, loadCaseIndex);
            JsonElement response = await WorkerRuntime.Host
                .RequestAsync<JsonElement>(
                    "fd.solve",
                    payload,
                    cancellationToken)
                .ConfigureAwait(false);
            EquilibriumResultDto result = WorkerResultCodec.DecodeFd(
                response,
                problem,
                settings,
                loadCaseIndex);
            stopwatch.Stop();
            return new FDSolveTaskResult(result, null, stopwatch.Elapsed);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new FDSolveTaskResult(null, error, stopwatch.Elapsed);
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

public sealed record BackendHealthTaskResult(
    WorkerHealth? Health,
    Exception? Error,
    IReadOnlyList<string> Stderr);

public sealed class BackendHealthComponent :
    NativeTaskComponentBase<BackendHealthTaskResult>
{
    public BackendHealthComponent()
        : base(
            "Backend Health",
            "Health",
            "Inspect the persistent Python/COMPAS worker and installed capabilities.",
            ComponentCategories.System,
            "backend_health")
    {
    }

    public override Guid ComponentGuid =>
        new("b0f27564-8304-4b4c-863f-871fc8682373");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddBooleanParameter(
            "Ready",
            "R",
            "True when the worker handshake and health request succeeded.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Python",
            "Py",
            "Python runtime and configured environment.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Packages",
            "Pkg",
            "Detected COMPAS package versions.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Capabilities",
            "Cap",
            "Advertised solver and exchange capabilities.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Report",
            "Out",
            "Readable health report or launch error.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            TaskList.Add(Task.Run(
                () => ComputeAsync(CancelToken),
                CancelToken));
            return;
        }

        BackendHealthTaskResult result;
        if (!GetSolveResults(data, out result!))
        {
            result = ComputeAsync(CancellationToken.None)
                .GetAwaiter()
                .GetResult();
        }

        if (result.Error is not null || result.Health is null)
        {
            string message =
                result.Error?.GetBaseException().Message ??
                "The worker returned no health data.";
            Message = "Unavailable";
            AddRuntimeMessage(GH_RuntimeMessageLevel.Error, message);
            data.SetData(0, false);
            data.SetData(1, string.Empty);
            data.SetDataList(2, Array.Empty<string>());
            data.SetDataList(3, Array.Empty<string>());
            data.SetData(
                4,
                result.Stderr.Count == 0
                    ? message
                    : message + Environment.NewLine +
                      string.Join(Environment.NewLine, result.Stderr.TakeLast(8)));
            return;
        }

        WorkerHealth health = result.Health;
        string python =
            $"{health.Python?.Implementation} {health.Python?.Version} · " +
            $"{WorkerRuntime.Host.Configuration.EnvironmentName}";
        string[] packages = health.Packages
            .OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase)
            .Select(pair => $"{pair.Key}: {pair.Value ?? "not installed"}")
            .ToArray();
        string[] capabilities = health.Capabilities
            .OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase)
            .Select(pair => $"{pair.Key}: {FormatJson(pair.Value)}")
            .ToArray();
        string report =
            $"{health.Worker?.Name} {health.Worker?.Version}" +
            Environment.NewLine +
            python +
            Environment.NewLine +
            $"Protocol {health.Worker?.ProtocolVersion}; " +
            $"schema {health.Worker?.SchemaVersion}";

        Message = "Ready";
        data.SetData(
            0,
            string.Equals(
                health.Status,
                "ok",
                StringComparison.OrdinalIgnoreCase));
        data.SetData(1, python);
        data.SetDataList(2, packages);
        data.SetDataList(3, capabilities);
        data.SetData(4, report);
    }

    private static async Task<BackendHealthTaskResult> ComputeAsync(
        CancellationToken cancellationToken)
    {
        try
        {
            WorkerHealth health = await WorkerRuntime.Host
                .HealthAsync(cancellationToken)
                .ConfigureAwait(false);
            return new BackendHealthTaskResult(
                health,
                null,
                WorkerRuntime.Host.RecentStderr);
        }
        catch (Exception error)
        {
            IReadOnlyList<string> stderr;
            try
            {
                stderr = WorkerRuntime.Host.RecentStderr;
            }
            catch
            {
                stderr = Array.Empty<string>();
            }
            return new BackendHealthTaskResult(null, error, stderr);
        }
    }

    private static string FormatJson(JsonElement value)
    {
        return value.ValueKind switch
        {
            JsonValueKind.True => "yes",
            JsonValueKind.False => "no",
            JsonValueKind.String => value.GetString() ?? string.Empty,
            _ => value.GetRawText()
        };
    }
}
