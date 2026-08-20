#nullable enable

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// One decoded voussoir cell: the plain outline points and course band the
/// worker returned, still unconverted. The Rhino <see cref="PolylineCurve"/>
/// only comes into being on the solve thread, in <c>SolveInstance</c>'s
/// post-solve half -- the background task itself never touches
/// <c>RhinoCommon</c>.
/// </summary>
public sealed record ArmadilloDualCellData(int Course, double[][] Outline);

public sealed record ArmadilloDualTaskResult(
    IReadOnlyList<ArmadilloDualCellData>? Cells,
    IReadOnlyList<double[][]>? Flowlines,
    string? Diagnostics,
    string? Warning,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// The Armadillo Vault's force-aligned dual cutting pattern (BRG/ETH 2016),
/// generated from a solved Result: a line field tracks the thrust flow,
/// streamlines seed a running-bond point set, and a discrete geodesic
/// Voronoi of those seeds becomes the voussoir cells, so every joint runs
/// across the thrust instead of along it. This component only proposes the
/// cut on canvas -- Export still owns projecting to plan and writing the
/// sidecar.
///
/// A thin async dispatcher in the <c>ExportComponent</c> pattern: pre-solve
/// validates and posts the worker's <c>pattern.armadillo_dual</c> task with
/// only plain data crossing into it, post-solve decodes the worker's plain
/// numbers into Rhino curves. No Rhino geometry ever crosses into the
/// background task.
/// </summary>
public sealed class ArmadilloDualComponent :
    NativeTaskComponentBase<ArmadilloDualTaskResult>
{
    /// <summary>
    /// The shipped S default, in metres. Kept in step with the generator's
    /// own <c>armadillo_dual.DEFAULT_SIZE</c> (the worker reads that same
    /// constant when a request omits size). 0.6 is measured, not chosen:
    /// it is the smallest value on a 0.1 m grid at which the reference BRG
    /// armadillo primal clears every geometric acceptance bar. The 0.4 that
    /// shipped with wave 6c was never measured and does not clear them.
    /// </summary>
    private const double DefaultSize = 0.6;

    public ArmadilloDualComponent()
        : base(
            "Armadillo Dual",
            "Dual",
            "Generate the Armadillo Vault's force-aligned dual cutting " +
            "pattern from a solved Result: a line field tracks the " +
            "thrust flow, streamlines seed a running-bond point set, and " +
            "a discrete geodesic Voronoi of those seeds becomes the " +
            "voussoir cells, every joint crossing the thrust. Refuses " +
            "when the Result carries neither member forces nor a " +
            "form/force diagram pair to align with.",
            ComponentCategories.Delivery,
            "armadillo_dual")
    {
    }

    public override Guid ComponentGuid =>
        new("51f4ade8-f918-4455-9823-563afbf201f4");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new ResultParam(),
            "Result",
            "RES",
            "Solved FD or TNA result to align and cut into " +
            "force-aligned dual voussoirs.",
            GH_ParamAccess.item);
        parameters.AddNumberParameter(
            "Size",
            "S",
            "Target voussoir size in metres: both the along-flow seed " +
            "spacing and the across-flow streamline spacing.",
            GH_ParamAccess.item,
            DefaultSize);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "One closed 3D polyline per voussoir cell, on the thrust " +
            "surface. Wire into Export's Cells (Export projects to " +
            "plan and writes the sidecar; this component never writes " +
            "files).",
            GH_ParamAccess.list);
        parameters.AddIntegerParameter(
            "Courses",
            "CO",
            "The course band per cell, aligned one to one with Cells " +
            "-- never sorted. Wire into Export's Courses.",
            GH_ParamAccess.list);
        parameters.AddCurveParameter(
            "Flowlines",
            "FL",
            "The advected flow lines, for eyeballing the force field " +
            "on canvas before committing to a cut.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Diagnostics",
            "D",
            "Readable diagnostics: alignment source (forces or " +
            "diagrams), cell count, degenerate cells dropped, " +
            "streamline and seed counts, mean/min/max cell size, and " +
            "the count of cells whose plan projection self-crosses -- " +
            "the ones Bench Studio's import rejects the whole sidecar " +
            "for.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out ResultDto? result,
                    out double size,
                    report: false))
            {
                return;
            }
            TaskList.Add(Task.Run(
                () => ComputeAsync(
                    CloneResult(result!),
                    size,
                    CancelToken),
                CancelToken));
            return;
        }

        // The post phase re-reads RES/S itself, same as Export: the pre
        // phase read quietly, so invalid inputs are reported exactly once,
        // here.
        if (!TryReadInputs(
                data,
                out ResultDto? postResult,
                out double postSize))
        {
            return;
        }

        ArmadilloDualTaskResult taskResult;
        bool haveTaskResult = GetSolveResults(data, out taskResult!);
        if (!haveTaskResult ||
            taskResult.Error is OperationCanceledException)
        {
            // A cancelled background task is a scheduling race, not a
            // verdict on the current inputs; recompute synchronously so a
            // late cancellation cannot strand the canvas on "Cancelled"
            // with empty outputs.
            taskResult = ComputeAsync(
                    CloneResult(postResult!),
                    postSize,
                    CancellationToken.None)
                .GetAwaiter()
                .GetResult();
        }

        if (taskResult.Error is not null)
        {
            Message = taskResult.Error is OperationCanceledException
                ? "Cancelled"
                : "Failed";
            // The worker's refusal message (WorkerRemoteException, code
            // "pattern_refused") is shown verbatim here, never rewrapped
            // or switched on: GetBaseException().Message already is the
            // user-facing text the worker composed.
            AddRuntimeMessage(
                taskResult.Error is OperationCanceledException
                    ? GH_RuntimeMessageLevel.Warning
                    : GH_RuntimeMessageLevel.Error,
                "Armadillo Dual: " +
                taskResult.Error.GetBaseException().Message);
            return;
        }
        if (taskResult.Cells is null ||
            taskResult.Flowlines is null ||
            taskResult.Diagnostics is null)
        {
            Message = "Failed";
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Error,
                "Armadillo Dual produced no pattern.");
            return;
        }
        if (taskResult.Warning is not null)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                "Armadillo Dual: " + taskResult.Warning);
        }

        // Curve construction happens here, on the solve thread, and only
        // here: the background task above never sees RhinoCommon, only
        // plain doubles.
        var cellCurves = new List<Curve>(taskResult.Cells.Count);
        var courses = new List<int>(taskResult.Cells.Count);
        foreach (ArmadilloDualCellData cell in taskResult.Cells)
        {
            cellCurves.Add(ClosedOutlineCurve(cell.Outline));
            courses.Add(cell.Course);
        }
        var flowlineCurves = new List<Curve>(taskResult.Flowlines.Count);
        foreach (double[][] line in taskResult.Flowlines)
            flowlineCurves.Add(OpenOutlineCurve(line));

        if (taskResult.Cells.Count == 0)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                "Armadillo Dual: no cells were generated. " +
                taskResult.Diagnostics.Replace("\n", "; "));
        }

        Message =
            $"{taskResult.Cells.Count} cells - " +
            $"{taskResult.Elapsed.TotalMilliseconds:F0} ms";
        data.SetDataList(0, cellCurves);
        data.SetDataList(1, courses);
        data.SetDataList(2, flowlineCurves);
        data.SetData(3, taskResult.Diagnostics);
    }

    /// <summary>
    /// Each outline is CLOSED by appending its first point again, the same
    /// convention <c>VisualiseComponents.FacePolylines</c> uses for its own
    /// Cells-shaped output.
    /// </summary>
    private static PolylineCurve ClosedOutlineCurve(
        IReadOnlyList<double[]> outline)
    {
        var points = new List<Point3d>(outline.Count + 1);
        foreach (double[] coordinate in outline)
        {
            points.Add(new Point3d(
                coordinate[0],
                coordinate[1],
                coordinate[2]));
        }
        if (points.Count > 0)
            points.Add(points[0]);
        return new PolylineCurve(points);
    }

    /// <summary>A flowline is open: it is not a cell boundary.</summary>
    private static PolylineCurve OpenOutlineCurve(
        IReadOnlyList<double[]> line)
    {
        var points = new List<Point3d>(line.Count);
        foreach (double[] coordinate in line)
        {
            points.Add(new Point3d(
                coordinate[0],
                coordinate[1],
                coordinate[2]));
        }
        return new PolylineCurve(points);
    }

    /// <summary>
    /// Read RES and this component's own Size, validating both up front so
    /// the background task never has to report a runtime message itself.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out ResultDto? result,
        out double size,
        bool report = true)
    {
        result = null;
        size = DefaultSize;
        ResultGoo? resultGoo = null;
        double sizeInput = DefaultSize;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            return false;
        }
        data.GetData(1, ref sizeInput);

        var errors = new List<string>(resultValue.Validate());
        // Negated comparison, not "S <= 0": NaN fails every comparison, so
        // a NaN S would sail PAST a positivity guard written the other
        // way round. The worker passes size straight through to the
        // generator unvalidated, so a non-positive size would come back
        // as a silent empty result rather than a refusal; reject it here
        // instead, before dispatch. 1 mm is the sane floor for a physical
        // voussoir size.
        if (!(sizeInput > 0.001))
        {
            errors.Add(
                $"S must be greater than 1 mm (0.001 m); received " +
                $"{sizeInput}.");
        }
        if (errors.Count > 0)
        {
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
        size = sizeInput;
        return true;
    }

    /// <summary>
    /// <c>ContractJson.DeepClone</c> round-trips through
    /// <see cref="ResultDto"/>'s own serializer options, which
    /// <c>[JsonIgnore]</c> deliberately excludes <see cref="ResultDto.RawWire"/>
    /// from: it is a transport artefact, not part of the native contract, so
    /// a plain deep clone would silently drop it. Reattach it afterwards; a
    /// string needs no isolation of its own, it is immutable already. Copied
    /// from <c>ExportComponent.CloneResult</c>.
    /// </summary>
    private static ResultDto CloneResult(ResultDto result) =>
        ContractJson.DeepClone(result) with { RawWire = result.RawWire };

    private static async Task<ArmadilloDualTaskResult> ComputeAsync(
        ResultDto result,
        double size,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            (JsonElement response, string? warning) =
                await RequestPatternAsync(result, size, cancellationToken)
                    .ConfigureAwait(false);
            (IReadOnlyList<ArmadilloDualCellData> cells,
                IReadOnlyList<double[][]> flowlines,
                string diagnostics) = DecodeResponse(response);
            stopwatch.Stop();
            return new ArmadilloDualTaskResult(
                cells,
                flowlines,
                diagnostics,
                warning,
                null,
                stopwatch.Elapsed);
        }
        catch (Exception error)
        {
            stopwatch.Stop();
            return new ArmadilloDualTaskResult(
                null,
                null,
                null,
                null,
                error,
                stopwatch.Elapsed);
        }
    }

    /// <summary>
    /// Dispatch <c>pattern.armadillo_dual</c> exactly as
    /// <c>ExportComponent.BuildCompasJsonAsync</c> dispatches
    /// <c>export.compas</c>: when the Result carries
    /// <see cref="ResultDto.RawWire"/> (every Result produced by a live
    /// TNA/FD Solve this session does), that exact payload is forwarded
    /// verbatim, snake_case fields and all, so the worker sees back the
    /// same shape it produced -- the member forces and diagram graphs the
    /// generator's line field needs. A Result with no RawWire (built by
    /// hand, or round-tripped through a document save/reload that does not
    /// carry this transport-only field) falls back to a re-serialised
    /// <see cref="ResultDto"/> with the shared wire options every codec
    /// reuses; that fallback's camelCase member names do not match the
    /// worker's snake_case fields, so the alignment field is likely to come
    /// back empty, and callers are warned.
    /// </summary>
    private static async Task<(JsonElement Response, string? Warning)>
        RequestPatternAsync(
            ResultDto result,
            double size,
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
            resultPayload = JsonSerializer.SerializeToElement(
                result,
                ContractJson.Options);
            warning =
                "result was not produced by a live solve in this " +
                "session, so diagram extraction may be unavailable.";
        }

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["result"] = resultPayload,
            ["size"] = size
        };
        JsonElement response = await WorkerRuntime.Host
            .RequestAsync<JsonElement>(
                "pattern.armadillo_dual",
                payload,
                cancellationToken)
            .ConfigureAwait(false);
        return (response, warning);
    }

    /// <summary>
    /// Decode the worker's <c>{"cells": [...], "flowlines": [...],
    /// "diagnostics": {...}}</c> response (design spec "Worker command")
    /// into plain data: no <c>RhinoCommon</c> type appears anywhere in this
    /// method, so it is safe to run on the background task.
    /// </summary>
    private static (
        IReadOnlyList<ArmadilloDualCellData> Cells,
        IReadOnlyList<double[][]> Flowlines,
        string Diagnostics) DecodeResponse(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException(
                "Armadillo Dual response must be a JSON object.");
        }

        JsonElement cellsElement = RequiredArray(root, "cells");
        var cells = new List<ArmadilloDualCellData>(
            cellsElement.GetArrayLength());
        int cellIndex = 0;
        foreach (JsonElement cellElement in cellsElement.EnumerateArray())
        {
            if (cellElement.ValueKind != JsonValueKind.Object)
            {
                throw new JsonException(
                    $"cells[{cellIndex}] must be an object.");
            }
            double[][] outline = PointList(
                RequiredArray(cellElement, "outline"),
                $"cells[{cellIndex}].outline");
            int course = RequiredInt(cellElement, "course");
            cells.Add(new ArmadilloDualCellData(course, outline));
            cellIndex++;
        }

        JsonElement flowlinesElement = RequiredArray(root, "flowlines");
        var flowlines = new List<double[][]>(
            flowlinesElement.GetArrayLength());
        int lineIndex = 0;
        foreach (JsonElement lineElement in flowlinesElement.EnumerateArray())
        {
            flowlines.Add(PointList(lineElement, $"flowlines[{lineIndex}]"));
            lineIndex++;
        }

        string diagnostics = FormatDiagnostics(
            RequiredObject(root, "diagnostics"));
        return (cells, flowlines, diagnostics);
    }

    /// <summary>
    /// The readable multi-line diagnostics string: the alignment source
    /// used (forces or the diagrams fallback), cell count, degenerate
    /// cells dropped, streamline and seed counts, the two M5 (2026-08-20
    /// dual-quality wave) plan-projection dropped counts, and mean/min/max
    /// cell size when at least one cell exists.
    /// </summary>
    private static string FormatDiagnostics(JsonElement diagnostics)
    {
        // The design spec's "Delivery and the honest limit" promised a
        // plan-degeneracy count and wave 6c never shipped it. M5
        // (2026-08-20 dual-quality wave) closed that gap the OTHER
        // direction: generate() now DROPS a self-crossing cell, and any
        // cell that still overlaps another surviving one, itself, before
        // the response ever reaches this component -- so the sidecar it
        // writes always imports. What the author needs on canvas is no
        // longer "you must exclude these before writing the sidecar" (the
        // cells are already gone); it is simply how many were, and of
        // which kind, so a surprising drop is visible rather than silent.
        int planDegenerateDropped = ArrayLength(diagnostics, "plan_degenerate_dropped");
        int planOverlapDropped = ArrayLength(diagnostics, "plan_overlap_dropped");
        var lines = new List<string>
        {
            $"Alignment source: {OptionalString(diagnostics, "field_source")}",
            $"Cells: {OptionalInt(diagnostics, "cell_count")}",
            $"Degenerate cells dropped: {OptionalInt(diagnostics, "dropped")}",
            $"Streamlines: {OptionalInt(diagnostics, "streamline_count")}",
            $"Seeds: {OptionalInt(diagnostics, "seed_count")}",
            $"Plan-degenerate cells dropped: {planDegenerateDropped} (self-crossing " +
                "in plan; excluded automatically so the sidecar imports)",
            $"Plan-overlap cells dropped: {planOverlapDropped} (overlapped another " +
                "surviving cell in plan; excluded automatically so the sidecar imports)",
        };
        if (diagnostics.TryGetProperty(
                "mean_cell_size",
                out JsonElement mean) &&
            mean.ValueKind != JsonValueKind.Null)
        {
            lines.Add(
                $"Mean cell size: {FiniteDouble(mean, "mean_cell_size"):F3} m");
        }
        if (diagnostics.TryGetProperty("min_cell_size", out JsonElement min) &&
            min.ValueKind != JsonValueKind.Null)
        {
            lines.Add(
                $"Min cell size: {FiniteDouble(min, "min_cell_size"):F3} m");
        }
        if (diagnostics.TryGetProperty("max_cell_size", out JsonElement max) &&
            max.ValueKind != JsonValueKind.Null)
        {
            lines.Add(
                $"Max cell size: {FiniteDouble(max, "max_cell_size"):F3} m");
        }
        return string.Join("\n", lines);
    }

    private static double[][] PointList(JsonElement points, string label)
    {
        var result = new List<double[]>(points.GetArrayLength());
        int index = 0;
        foreach (JsonElement pointElement in points.EnumerateArray())
        {
            if (pointElement.ValueKind != JsonValueKind.Array)
            {
                throw new JsonException(
                    $"{label}[{index}] must be a coordinate array.");
            }
            double[] coordinates = pointElement
                .EnumerateArray()
                .Select(item => FiniteDouble(item, $"{label}[{index}]"))
                .ToArray();
            if (coordinates.Length != 3)
            {
                throw new JsonException(
                    $"{label}[{index}] must contain three coordinates.");
            }
            result.Add(coordinates);
            index++;
        }
        return result.ToArray();
    }

    private static JsonElement RequiredArray(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind != JsonValueKind.Array)
        {
            throw new JsonException(
                $"Armadillo Dual response requires array '{propertyName}'.");
        }
        return value;
    }

    private static JsonElement RequiredObject(
        JsonElement root,
        string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            value.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException(
                $"Armadillo Dual response requires object '{propertyName}'.");
        }
        return value;
    }

    private static int RequiredInt(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out JsonElement value) ||
            !value.TryGetInt32(out int result))
        {
            throw new JsonException(
                $"Armadillo Dual response requires integer '{propertyName}'.");
        }
        return result;
    }

    private static double FiniteDouble(JsonElement value, string label)
    {
        if (!value.TryGetDouble(out double number) || !double.IsFinite(number))
            throw new JsonException($"{label} contains a non-finite number.");
        return number;
    }

    private static string OptionalString(
        JsonElement root,
        string propertyName)
    {
        return root.TryGetProperty(propertyName, out JsonElement value) &&
            value.ValueKind == JsonValueKind.String
                ? value.GetString() ?? "unknown"
                : "unknown";
    }

    private static int OptionalInt(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out JsonElement value) &&
            value.TryGetInt32(out int result)
                ? result
                : 0;
    }

    /// <summary>
    /// The length of an array-valued diagnostics entry (M5's
    /// ``plan_degenerate_dropped`` / ``plan_overlap_dropped``: lists of
    /// the dropped cells' own seed indices, not bare counts -- D reports
    /// only how many, the list itself is for anyone reading the raw
    /// response). 0 when the key is absent or not an array, the same
    /// "missing reads as none" convention ``OptionalInt`` uses.
    /// </summary>
    private static int ArrayLength(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out JsonElement value) &&
            value.ValueKind == JsonValueKind.Array
                ? value.GetArrayLength()
                : 0;
    }
}
