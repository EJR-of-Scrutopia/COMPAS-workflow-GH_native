using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Ananke.COMPAS.Native.Backend;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Components;

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
