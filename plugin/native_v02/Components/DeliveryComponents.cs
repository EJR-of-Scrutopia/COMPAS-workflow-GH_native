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
using Rhino;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

public sealed record ExportComponentTaskResult(
    string? Json,
    string? Warning,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// One authored cutting cell, already reduced to the plan outline the
/// studio's bench.tessellation/1 sidecar carries: the curve conversion
/// happens on the solve thread (TryReadInputs), so the background task
/// only ever sees plain numbers, never live Rhino geometry.
/// </summary>
public sealed record TessellationCell(
    int Course,
    IReadOnlyList<double[]> Outline);

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
                ("COMPAS", "compas"),
                ("Tessellation", "tessellation")
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
            "Contract (portable native JSON), COMPAS (native " +
            "json_dumps geometry produced by the worker's export.compas " +
            "command), or Tessellation (the studio's " +
            "bench.tessellation/1 authored cutting sidecar, built from " +
            "the Cells input).",
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
        parameters.AddTextParameter(
            "Name",
            "N",
            "Optional file name for the write. Keep it to bake over the " +
            "same file; change it to bake a new one. Applied inside a " +
            "folder Path, or replacing the file name of a file Path. " +
            "Without an extension, -contract.json, -compas.json or " +
            "-tessellation.json is appended so the exports of one " +
            "geometry sit side by side (and the studio finds the " +
            "sidecar by exactly that <Name>-tessellation.json pairing); " +
            "an explicit extension is used verbatim. Blank uses " +
            "ananke-export-<format>.json.",
            GH_ParamAccess.item,
            string.Empty);
        parameters[4].Optional = true;
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "Tessellation format only: one closed planar outline per " +
            "cutting cell (a brick), authored against the solved form " +
            "Result still carries. Projected to plan (z dropped) into " +
            "the sidecar's outline points; non-polyline curves are " +
            "approximated at a 5 mm chord. Ignored by the other formats.",
            GH_ParamAccess.list);
        parameters[5].Optional = true;
        parameters.AddIntegerParameter(
            "Courses",
            "CO",
            "Tessellation format only: the course (row) index per cell, " +
            "same length as Cells. The studio stages the build animation " +
            "course by course. Empty puts every cell in course 0, one " +
            "single stage.",
            GH_ParamAccess.list);
        parameters[6].Optional = true;
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
        // FdSolve/Deconstruct sibling parity: without a local catch here,
        // an unexpected exception (most plausibly out of the Rhino curve
        // reads in TryReadInputs/PrepareTessellationCells, which run on
        // this thread) would climb out of SolveInstance and land on
        // Grasshopper's own framework-level handler, which reports a far
        // uglier message than AddRuntimeMessage does.
        try
        {
            if (InPreSolve)
            {
                if (!TryReadInputs(
                        data,
                        out ResultDto? result,
                        out string format,
                        out _,
                        out _,
                        out _,
                        out IReadOnlyList<TessellationCell>? cells,
                        out string? cellWarning,
                        report: false))
                {
                    return;
                }
                // Resolved here, on the solve thread: RhinoDoc.ActiveDoc
                // is not a background thread's to read, and the lambda
                // below runs on one.
                double unitFactor = ResolveUnitFactor();
                TaskList.Add(Task.Run(
                    () => ComputeAsync(
                        CloneResult(result!),
                        format,
                        cells,
                        cellWarning,
                        unitFactor,
                        CancelToken),
                    CancelToken));
                return;
            }

            // The post phase re-reads Write and Path itself: the disk
            // write is a side effect and belongs on this thread, where a
            // Button's release re-solve cannot cancel it mid-flight.
            if (!TryReadInputs(
                    data,
                    out ResultDto? postResult,
                    out string postFormat,
                    out string path,
                    out bool write,
                    out string name,
                    out IReadOnlyList<TessellationCell>? postCells,
                    out string? postCellWarning))
            {
                return;
            }
            ExportComponentTaskResult taskResult;
            bool haveTaskResult = GetSolveResults(data, out taskResult!);
            if (!haveTaskResult ||
                taskResult.Error is OperationCanceledException)
            {
                // A cancelled background task is a scheduling race, not a
                // verdict on the current inputs; recompute synchronously
                // so a late cancellation cannot strand the canvas on
                // "Cancelled".
                taskResult = ComputeAsync(
                        CloneResult(postResult!),
                        postFormat,
                        postCells,
                        postCellWarning,
                        ResolveUnitFactor(),
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
                    string resolved =
                        ResolveWritePath(path, postFormat, name);
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
        catch (Exception error)
        {
            Message = "Failed";
            ReportException("Export failed", error);
        }
    }

    /// <summary>
    /// A Path may name a file or a folder: canvas path pickers commonly
    /// hand over a directory when the target file does not exist yet. A
    /// directory (existing, or spelled with a trailing separator) receives
    /// the Name input inside it, or a deterministic per-format file name
    /// when Name is blank, so the Contract and COMPAS exports of one
    /// definition never overwrite each other; a file path is used as
    /// given unless Name overrides its file name. Parent directories are
    /// created when missing, and .json is appended to a Name given
    /// without an extension.
    /// </summary>
    private static string ResolveWritePath(
        string path,
        string format,
        string name)
    {
        string trimmed = path.Trim();
        string fileName = name.Trim();
        if (fileName.Length > 0 &&
            string.IsNullOrEmpty(Path.GetExtension(fileName)))
        {
            // One geometry is routinely exported in both formats with the
            // same Name; the format suffix keeps them side by side. A Name
            // spelled with an explicit extension is used verbatim.
            fileName += $"-{format}.json";
        }
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
                trimmed,
                fileName.Length > 0
                    ? fileName
                    : $"ananke-export-{format}.json");
        }
        string? parent = Path.GetDirectoryName(trimmed);
        if (!string.IsNullOrEmpty(parent))
            Directory.CreateDirectory(parent);
        if (fileName.Length > 0)
            return Path.Combine(parent ?? string.Empty, fileName);
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
        out string name,
        out IReadOnlyList<TessellationCell>? cells,
        out string? cellWarning,
        bool report = true)
    {
        result = null;
        format = "contract";
        path = string.Empty;
        write = false;
        name = string.Empty;
        cells = null;
        cellWarning = null;
        ResultGoo? resultGoo = null;
        string formatInput = "contract";
        string pathInput = string.Empty;
        bool writeInput = false;
        string nameInput = string.Empty;
        var cellInput = new List<Curve>();
        var courseInput = new List<int>();
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            return false;
        }
        data.GetData(1, ref formatInput);
        data.GetData(2, ref pathInput);
        data.GetData(3, ref writeInput);
        data.GetData(4, ref nameInput);
        data.GetDataList(5, cellInput);
        data.GetDataList(6, courseInput);

        string normalisedFormat = NormaliseFormat(formatInput);
        var errors = new List<string>(resultValue.Validate());
        if (normalisedFormat is not ("contract" or "compas" or "tessellation"))
            errors.Add("Format must be Contract, COMPAS or Tessellation.");
        if (writeInput && string.IsNullOrWhiteSpace(pathInput))
            errors.Add("Write requires a Path to write to.");
        if (normalisedFormat == "tessellation")
        {
            if (cellInput.Count == 0)
            {
                errors.Add(
                    "Tessellation needs at least one Cell outline.");
            }
            else if (courseInput.Count != 0 &&
                     courseInput.Count != cellInput.Count)
            {
                errors.Add(
                    $"Courses ({courseInput.Count}) must be empty or " +
                    $"match Cells ({cellInput.Count}).");
            }
            else if (HasNegativeCourse(courseInput, out string negative))
            {
                // A negative course survives all the way to the studio's
                // "c-1p0"-style key, which tessellation.from_document
                // pins course >= 0 and refuses -- late, remote, and
                // confusing. Catch it here instead, naming every
                // offending index and value, and write nothing.
                errors.Add(
                    "Courses must be zero or greater; negative at " +
                    negative + ".");
            }
            else
            {
                cells = PrepareTessellationCells(
                    cellInput, courseInput, errors, out cellWarning);
            }
        }
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
        name = nameInput ?? string.Empty;
        return true;
    }

    /// <summary>
    /// True when any Courses entry is negative, naming every offending
    /// index and value (not just the first) so the fix on the canvas is
    /// immediate. The Courses input is an Integer parameter, so
    /// Grasshopper itself already handles non-integer values before
    /// SolveInstance runs; this only guards the bound the studio's import
    /// actually enforces.
    /// </summary>
    private static bool HasNegativeCourse(
        IReadOnlyList<int> courses,
        out string detail)
    {
        var offending = new List<string>();
        for (int i = 0; i < courses.Count; i++)
        {
            if (courses[i] < 0)
                offending.Add($"index {i} = {courses[i]}");
        }
        detail = string.Join(", ", offending);
        return offending.Count > 0;
    }

    /// <summary>
    /// Reduce each cell curve to the plan outline the sidecar carries:
    /// polylines verbatim, anything else approximated at a 5 mm chord
    /// (the same chord target the studio's own cutter simplifies to), z
    /// dropped, the closing duplicate and consecutive near-duplicates
    /// removed. Curve access is why this runs on the solve thread and
    /// never inside the background task.
    /// </summary>
    private static IReadOnlyList<TessellationCell>? PrepareTessellationCells(
        IReadOnlyList<Curve> curves,
        IReadOnlyList<int> courses,
        List<string> errors,
        out string? warning)
    {
        warning = null;
        var prepared = new List<TessellationCell>(curves.Count);
        var openCells = new List<int>();
        for (int i = 0; i < curves.Count; i++)
        {
            Curve? curve = curves[i];
            if (curve is null)
            {
                errors.Add($"Cell {i} is null.");
                continue;
            }
            if (!curve.TryGetPolyline(out Polyline polyline))
            {
                PolylineCurve? approximated = curve.ToPolyline(
                    0.005, Math.PI / 90.0, 0.005, 0.0);
                if (approximated is null ||
                    !approximated.TryGetPolyline(out polyline))
                {
                    errors.Add(
                        $"Cell {i} could not be reduced to a polyline.");
                    continue;
                }
            }
            var outline = new List<double[]>(polyline.Count);
            foreach (Point3d point in polyline)
            {
                if (outline.Count > 0)
                {
                    double[] last = outline[outline.Count - 1];
                    if (Math.Abs(last[0] - point.X) < 1e-9 &&
                        Math.Abs(last[1] - point.Y) < 1e-9)
                    {
                        continue;
                    }
                }
                outline.Add(new[] { point.X, point.Y });
            }
            // The studio closes rings implicitly ((i + 1) % n), so the
            // closing repeat of a closed polyline is dropped, not kept.
            if (outline.Count > 1)
            {
                double[] first = outline[0];
                double[] final = outline[outline.Count - 1];
                if (Math.Abs(first[0] - final[0]) < 1e-9 &&
                    Math.Abs(first[1] - final[1]) < 1e-9)
                {
                    outline.RemoveAt(outline.Count - 1);
                }
                else if (!curve.IsClosed)
                {
                    openCells.Add(i);
                }
            }
            if (outline.Count < 3)
            {
                errors.Add(
                    $"Cell {i} has fewer than 3 distinct plan corners.");
                continue;
            }
            prepared.Add(new TessellationCell(
                courses.Count > 0 ? courses[i] : 0,
                outline));
        }
        if (openCells.Count > 0)
        {
            warning =
                $"{openCells.Count} cell(s) are not closed curves " +
                $"(first: {openCells[0]}); the studio closes each " +
                "outline implicitly.";
        }
        if (courses.Count == 0 && prepared.Count > 0)
        {
            warning = (warning is null ? string.Empty : warning + " ") +
                "No Courses wired: every cell is course 0, so the build " +
                "animation becomes a single stage.";
        }
        return errors.Count > 0 ? null : prepared;
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
        IReadOnlyList<TessellationCell>? cells,
        string? cellWarning,
        double unitFactor,
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
                        unitFactor,
                        cancellationToken)
                    .ConfigureAwait(false);
            }
            else if (format == "tessellation")
            {
                // Pure serialisation of cells already reduced to plain
                // numbers on the solve thread; no worker, no geometry.
                json = BuildTessellationJson(cells!, unitFactor);
                warning = cellWarning;
                if (Math.Abs(unitFactor - 1.0) > 1e-12)
                {
                    // Disclosed the way ImportPiecesComponent discloses
                    // its own factor: a silent scale is the thing that
                    // makes a units mismatch hard to find later.
                    string note =
                        "Document units converted to metres by a factor " +
                        "of " + unitFactor.ToString(
                            "0.################",
                            System.Globalization.CultureInfo.InvariantCulture) +
                        ".";
                    warning = string.IsNullOrEmpty(warning)
                        ? note
                        : warning + " " + note;
                }
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
        double unitFactor,
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
        return (BuildCompasJson(response, unitFactor), warning);
    }

    /// <summary>
    /// The compas-only export. lengthUnitToMetres states how many metres
    /// one of these coordinates is, which nothing in this chain used to
    /// say at all: the studio reads metres, its geometry.py asserts that
    /// as a flat assumption, and the contract it derives from this file
    /// carries no unit anywhere. A millimetre model therefore uploaded,
    /// derived, cut and staged in silence, describing a vault a thousand
    /// times too large. Declared rather than applied, because the
    /// diagrams here are opaque COMPAS documents the worker produced and
    /// rewriting their coordinates is not this component's to do; the
    /// studio refuses anything but 1.0 and names the number. Added last
    /// so the existing four keys keep their order.
    /// </summary>
    private static string BuildCompasJson(JsonElement response, double unitFactor)
    {
        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["thrustMesh"] = OptionalString(response, "thrustMesh"),
            ["formDiagram"] = OptionalString(response, "formDiagram"),
            ["forceDiagram"] = OptionalString(response, "forceDiagram"),
            ["compasVersion"] = RequiredString(response, "compasVersion"),
            ["lengthUnitToMetres"] = unitFactor
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
            "tessellation" or "tess" or "sidecar" => "tessellation",
            _ => format
        };
    }

    /// <summary>
    /// The studio's bench.tessellation/1 sidecar, verbatim: an authored
    /// cut the server consumes through tessellation.from_document. Keys
    /// are c&lt;course&gt;p&lt;n&gt; with n counting within each course,
    /// matching the generated patterns' own naming so the staging plan
    /// and the Data panel read the same either way. Units are metres and
    /// the domain is the plan projection; both are the sidecar's fixed
    /// contract, not options.
    /// </summary>
    /// <summary>
    /// The plan corners in METRES, which is what the sidecar's fixed
    /// "units": "m" declares and what the studio's
    /// tessellation.from_document refuses to read anything else as (its
    /// own message: "This schema version reads metres only, so a
    /// conversion is the author's to make"). The corners arrive in
    /// document units, so this is that conversion. A factor of exactly
    /// 1.0 returns the same numbers, so a metre document is unaffected
    /// byte for byte.
    /// </summary>
    private static List<double[]> ScaleOutline(
        IReadOnlyList<double[]> outline,
        double unitFactor)
    {
        var scaled = new List<double[]>(outline.Count);
        foreach (double[] point in outline)
        {
            scaled.Add(unitFactor == 1.0
                ? point
                : new[] { point[0] * unitFactor, point[1] * unitFactor });
        }
        return scaled;
    }

    /// <summary>
    /// Document units to metres, the inverse of
    /// ImportPiecesComponent.ResolveUnitFactor, so the pair round trips.
    /// RhinoDoc.ActiveDoc may be null in headless contexts (the native
    /// smoke harness never launches Rhino), so the guard defaults to
    /// 1.0; a factor other than 1.0 is always disclosed as a warning.
    /// Must be called on the solve thread.
    /// </summary>
    private static double ResolveUnitFactor()
    {
        RhinoDoc? activeDoc = RhinoDoc.ActiveDoc;
        if (activeDoc is null)
            return 1.0;
        return RhinoMath.UnitScale(activeDoc.ModelUnitSystem, UnitSystem.Meters);
    }

    private static string BuildTessellationJson(
        IReadOnlyList<TessellationCell> cells,
        double unitFactor)
    {
        var perCourse = new Dictionary<int, int>();
        var cellPayloads = new List<Dictionary<string, object?>>(cells.Count);
        foreach (TessellationCell cell in cells)
        {
            perCourse.TryGetValue(cell.Course, out int sequence);
            perCourse[cell.Course] = sequence + 1;
            cellPayloads.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["key"] = $"c{cell.Course}p{sequence}",
                ["course"] = cell.Course,
                ["outline"] = ScaleOutline(cell.Outline, unitFactor)
            });
        }
        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = "bench.tessellation/1",
            ["units"] = "m",
            ["domain"] = "plan",
            ["pattern"] = "authored",
            ["cells"] = cellPayloads
        };
        // The shared wire options every other codec in this component
        // already uses (BuildCompasJson below, ContractJson.Serialize
        // elsewhere): no field here is ever null and every key is
        // already a camelCase literal, so this changes no byte today --
        // it only stops this one call site from silently drifting from
        // the rest of the plugin's JSON shape later.
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }
}
