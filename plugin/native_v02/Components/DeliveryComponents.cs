#nullable enable

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Components;

public sealed record ExportComponentTaskResult(
    string? Json,
    string? Warning,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// The one delivery boundary for a solved Result: Contract mode serialises
/// the ResultDto itself (the shared wire options every codec already
/// reuses), and COMPAS mode dispatches the worker's <c>export.compas</c>
/// command exactly as <c>FdSolveComponent</c> dispatches a solve, then
/// bundles the returned strings into one JSON object. An optional Path
/// writes that JSON to disk.
/// </summary>
public sealed class ExportComponent :
    NativeTaskComponentBase<ExportComponentTaskResult>
{
    // A Button feeding Write is only True for the press solve; the release
    // immediately triggers a second solve with Write false. Latching the
    // last successful write keeps the evidence of the one-shot write on the
    // component instead of wiping it milliseconds after it happened.
    private string? _lastWrittenPath;
    private DateTime _lastWrittenAt;

    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            1,
            "Format",
            new (string Label, string Value)[]
            {
                ("Contract", "contract"),
                ("COMPAS", "compas")
            },
            "contract")
    };

    public ExportComponent()
        : base(
            "Export",
            "Export",
            "Serialise a solved Result as portable Contract JSON or " +
            "native COMPAS json_dumps geometry via the worker, and " +
            "optionally write it to disk.",
            ComponentCategories.Delivery,
            "export")
    {
    }

    public override Guid ComponentGuid =>
        new("f2a6c8e4-1b5d-49a3-b7e0-3c9f5d8a2617");

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new ResultParam(),
            "Result",
            "RES",
            "Solved FD or TNA result to export.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Format",
            "F",
            "Contract (portable native JSON) or COMPAS (native " +
            "json_dumps geometry produced by the worker's export.compas " +
            "command).",
            GH_ParamAccess.item,
            "contract");
        parameters.AddTextParameter(
            "Path",
            "P",
            "Optional target for the Write trigger: a file path, or a " +
            "folder to receive ananke-export-<format>.json. Missing " +
            "parent folders are created.",
            GH_ParamAccess.item,
            string.Empty);
        parameters[2].Optional = true;
        parameters.AddBooleanParameter(
            "Write",
            "W",
            "Push the export to disk: while True, the JSON is written to " +
            "Path on every solve. Wire a button for one-shot writes. The " +
            "JSON output itself is always live.",
            GH_ParamAccess.item,
            false);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddTextParameter(
            "JSON",
            "J",
            "Exported JSON text.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Written",
            "W",
            "Most recent file path this component wrote this session, so " +
            "a one-shot Button write stays visible after release; empty " +
            "until a write happens.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out ResultDto? result,
                    out string format,
                    out _,
                    out _,
                    report: false))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    CloneResult(result!),
                    format,
                    CancelToken),
                CancelToken));
            return;
        }

        // The post phase re-reads Write and Path itself: the disk write is
        // a side effect and belongs on this thread, where a Button's
        // release re-solve cannot cancel it mid-flight.
        if (!TryReadInputs(
                data,
                out ResultDto? postResult,
                out string postFormat,
                out string path,
                out bool write))
        {
            return;
        }
        ExportComponentTaskResult taskResult;
        if (!GetSolveResults(data, out taskResult!))
        {
            taskResult = ComputeAsync(
                    CloneResult(postResult!),
                    postFormat,
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();
        }

        if (taskResult.Error is not null)
        {
            Message = taskResult.Error is OperationCanceledException
                ? "Cancelled"
                : "Failed";
            AddRuntimeMessage(
                taskResult.Error is OperationCanceledException
                    ? GH_RuntimeMessageLevel.Warning
                    : GH_RuntimeMessageLevel.Error,
                "Export: " + taskResult.Error.GetBaseException().Message);
            return;
        }
        if (taskResult.Json is null)
        {
            Message = "Failed";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                "Export produced no JSON.");
            return;
        }
        if (taskResult.Warning is not null)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                "Export: " + taskResult.Warning);
        }

        if (write && !string.IsNullOrWhiteSpace(path))
        {
            try
            {
                string resolved = ResolveWritePath(path, postFormat);
                File.WriteAllText(resolved, taskResult.Json);
                _lastWrittenPath = resolved;
                _lastWrittenAt = DateTime.Now;
            }
            catch (Exception writeException)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    "Export: failed to write file: " +
                    writeException.Message);
            }
        }

        data.SetData(0, taskResult.Json);
        data.SetData(1, _lastWrittenPath ?? string.Empty);
        Message = _lastWrittenPath is null
            ? $"{taskResult.Json.Length} chars · not written"
            : $"{taskResult.Json.Length} chars · wrote " +
              $"{Path.GetFileName(_lastWrittenPath)} " +
              $"{_lastWrittenAt:HH:mm:ss}";
    }

    /// <summary>
    /// A Path may name a file or a folder: canvas path pickers commonly
    /// hand over a directory when the target file does not exist yet. A
    /// directory (existing, or spelled with a trailing separator) receives
    /// a deterministic per-format file name inside it, so the Contract and
    /// COMPAS exports of one definition never overwrite each other; a file
    /// path is used as given, with its parent directory created when
    /// missing.
    /// </summary>
    private static string ResolveWritePath(string path, string format)
    {
        string trimmed = path.Trim();
        bool looksLikeDirectory =
            trimmed.EndsWith(
                Path.DirectorySeparatorChar.ToString(),
                StringComparison.Ordinal) ||
            trimmed.EndsWith(
                Path.AltDirectorySeparatorChar.ToString(),
                StringComparison.Ordinal) ||
            Directory.Exists(trimmed);
        if (looksLikeDirectory)
        {
            Directory.CreateDirectory(trimmed);
            return Path.Combine(
                trimmed, $"ananke-export-{format}.json");
        }
        string? parent = Path.GetDirectoryName(trimmed);
        if (!string.IsNullOrEmpty(parent))
            Directory.CreateDirectory(parent);
        return trimmed;
    }

    /// <summary>
    /// Read RES and this component's own Format/Path/Write, normalising
    /// Format and validating the Result up front so the background task
    /// never has to report a runtime message itself. The write itself
    /// happens in the post phase; this only gathers and validates.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out ResultDto? result,
        out string format,
        out string path,
        out bool write,
        bool report = true)
    {
        result = null;
        format = "contract";
        path = string.Empty;
        write = false;
        ResultGoo? resultGoo = null;
        string formatInput = "contract";
        string pathInput = string.Empty;
        bool writeInput = false;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            return false;
        }
        data.GetData(1, ref formatInput);
        data.GetData(2, ref pathInput);
        data.GetData(3, ref writeInput);

        string normalisedFormat = NormaliseFormat(formatInput);
        var errors = new List<string>(resultValue.Validate());
        if (normalisedFormat is not ("contract" or "compas"))
            errors.Add("Format must be Contract or COMPAS.");
        if (writeInput && string.IsNullOrWhiteSpace(pathInput))
            errors.Add("Write requires a Path to write to.");
        if (errors.Count > 0)
        {
            // The pre phase reads quietly; the post phase repeats the read
            // and owns the reporting, so invalid inputs surface once.
            if (report)
            {
                Message = "Invalid";
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    string.Join(" ", errors));
            }
            return false;
        }

        result = resultValue;
        format = normalisedFormat;
        path = pathInput ?? string.Empty;
        write = writeInput;
        return true;
    }

    /// <summary>
    /// <c>ContractJson.DeepClone</c> (the pattern every other solve
    /// component uses to snapshot inputs before they cross into a
    /// background task) round-trips through <c>ResultDto</c>'s own
    /// serializer options, which <c>[JsonIgnore]</c> deliberately excludes
    /// <see cref="ResultDto.RawWire"/> from: it is a transport artefact, not
    /// part of the native contract, so a plain deep clone would silently
    /// drop it. Reattach it afterwards; a string needs no isolation of its
    /// own, it is immutable already.
    /// </summary>
    private static ResultDto CloneResult(ResultDto result) =>
        ContractJson.DeepClone(result) with { RawWire = result.RawWire };

    private static async Task<ExportComponentTaskResult> ComputeAsync(
        ResultDto result,
        string format,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            string json;
            string? warning = null;
            if (format == "compas")
            {
                (json, warning) = await BuildCompasJsonAsync(
                        result,
                        cancellationToken)
                    .ConfigureAwait(false);
            }
            else
            {
                json = ContractJson.Serialize(result);
            }
            stopwatch.Stop();
            return new ExportComponentTaskResult(
                json,
                warning,
                null,
                stopwatch.Elapsed);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new ExportComponentTaskResult(
                null,
                null,
                error,
                stopwatch.Elapsed);
        }
    }

    /// <summary>
    /// Dispatch <c>export.compas</c> exactly as <c>FdSolveComponent</c>
    /// dispatches <c>fd.solve</c>: one <c>WorkerRuntime.Host.RequestAsync</c>
    /// call. When the Result carries <see cref="ResultDto.RawWire"/> (every
    /// Result produced by a live TNA/FD Solve this session does; both
    /// codecs set it from the worker's own response), that exact payload is
    /// forwarded verbatim, snake_case fields and all, so the worker sees
    /// back the same shape it produced. A Result with no RawWire (built by
    /// hand, or round-tripped through a document save/reload that does not
    /// carry this transport-only field) falls back to a re-serialised
    /// ResultDto with the shared wire options every codec reuses; that
    /// fallback's camelCase member names do not match the worker's
    /// snake_case fields, so diagram extraction is likely to come back
    /// null, and callers are warned.
    /// </summary>
    private static async Task<(string Json, string? Warning)> BuildCompasJsonAsync(
        ResultDto result,
        CancellationToken cancellationToken)
    {
        object resultPayload;
        string? warning;
        if (!string.IsNullOrEmpty(result.RawWire))
        {
            using JsonDocument document = JsonDocument.Parse(result.RawWire);
            resultPayload = document.RootElement.Clone();
            warning = null;
        }
        else
        {
            resultPayload =
                JsonSerializer.SerializeToElement(result, ContractJson.Options);
            warning =
                "result was not produced by a live solve in this " +
                "session, so diagram extraction may be unavailable.";
        }

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["result"] = resultPayload
        };
        JsonElement response = await WorkerRuntime.Host
            .RequestAsync<JsonElement>(
                "export.compas",
                payload,
                cancellationToken)
            .ConfigureAwait(false);
        return (BuildCompasJson(response), warning);
    }

    private static string BuildCompasJson(JsonElement response)
    {
        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["thrustMesh"] = OptionalString(response, "thrustMesh"),
            ["formDiagram"] = OptionalString(response, "formDiagram"),
            ["forceDiagram"] = OptionalString(response, "forceDiagram"),
            ["compasVersion"] = RequiredString(response, "compasVersion")
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    private static string? OptionalString(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined)
        {
            return null;
        }
        if (value.ValueKind != JsonValueKind.String)
        {
            throw new JsonException(
                $"export.compas response '{propertyName}' must be a " +
                "string or null.");
        }
        return value.GetString();
    }

    private static string RequiredString(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind != JsonValueKind.String)
        {
            throw new JsonException(
                $"export.compas response '{propertyName}' must be a " +
                "string.");
        }
        return value.GetString() ?? string.Empty;
    }

    private static string NormaliseFormat(string? value)
    {
        string format = (value ?? string.Empty).Trim().ToLowerInvariant();
        return format switch
        {
            "" => "contract",
            "compas" or "compas.data" => "compas",
            _ => format
        };
    }
}
