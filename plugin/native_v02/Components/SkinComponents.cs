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
/// <c>RhinoCommon</c>. Moved from PatternComponents.cs with its name kept.
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
/// Skin: ONE proposer for the buildable skin layout on the thrust surface
/// (spec 2026-08-31), under the old Skin's GUID so saved placements load
/// as this component behind the ports-moved warning. Three patterns behind
/// one flag: 0 running-bond courses and 1 stretched honeycomb, computed
/// natively and synchronously on the Result's own vertex and face arrays
/// through SkinPatterns; 2 the Armadillo Vault's force-aligned dual, the
/// worker dispatch moved from the retired ArmadilloDualComponent. Outputs
/// are VISIBLE: seeing the pattern the moment it computes is the point.
/// Export still owns projecting to plan and writing the sidecar, and still
/// calls <see cref="FacePolylines"/> for its unwired default tessellation.
/// </summary>
public sealed class SkinComponent :
    NativeTaskComponentBase<ArmadilloDualTaskResult>
{
    /// <summary>
    /// The shipped S default, in metres. Kept in step with the generator's
    /// own <c>armadillo_dual.DEFAULT_SIZE</c> (the worker reads that same
    /// constant when a request omits size). 0.6 is measured, not chosen:
    /// it is the smallest value on a 0.1 m grid at which the reference BRG
    /// armadillo primal clears every geometric acceptance bar.
    /// </summary>
    private const double DefaultSize = 0.6;

    /// <summary>The old Skin's CH default: one course rise, metres.</summary>
    private const double DefaultCourseHeight = 0.35;

    private static readonly ComponentValueListSpec[] ValueLists =
    {
        new(
            1,
            "Pattern",
            new (string Label, string Value)[]
            {
                ("0 · courses", "0"),
                ("1 · hexagonal", "1"),
                ("2 · force aligned", "2")
            },
            "0")
    };

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => ValueLists;

    public SkinComponent()
        : base(
            "Skin",
            "Skin",
            "Propose the buildable skin layout on the thrust surface: "
                + "running-bond courses or a stretched honeycomb, set out "
                + "natively from a seam with Size along the course and "
                + "Course Height up it, or the worker's force-aligned "
                + "dual. Cells and Courses wire straight into Export, "
                + "which projects to plan and writes the sidecar.",
            ComponentCategories.Deliver,
            "skin")
    {
        // A PROPOSER previews: no output is hidden, the Armadillo Dual
        // convention, because seeing the pattern the moment it computes
        // is the point of the component.
    }

    public override Guid ComponentGuid =>
        new("7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new ResultParam(),
            "Result",
            "RES",
            "A solved Result. The native patterns need a TNA Result with "
                + "faces; an FD Result gives empty outputs and a Remark. "
                + "The force-aligned pattern hands the Result to the "
                + "worker unchanged and inherits its refusal rules.",
            GH_ParamAccess.item);
        parameters.AddIntegerParameter(
            "Pattern",
            "P",
            "Which pattern to propose: 0 courses (running bond), 1 "
                + "hexagonal (stretched honeycomb), 2 force aligned (the "
                + "worker's Armadillo dual). A value list is offered on "
                + "the component menu.",
            GH_ParamAccess.item,
            0);
        parameters.AddNumberParameter(
            "Size",
            "S",
            "Target piece length along the course, metres. Minimum 1 mm. "
                + "Pattern 2 reads S alone as its voussoir size.",
            GH_ParamAccess.item,
            DefaultSize);
        parameters.AddNumberParameter(
            "Course Height",
            "CH",
            "Course rise, metres. Minimum 1 mm; below it the default is "
                + "used with a warning, the old Skin's rule. Ignored by "
                + "pattern 2.",
            GH_ParamAccess.item,
            DefaultCourseHeight);
        parameters[1].Optional = true;
        parameters[2].Optional = true;
        parameters[3].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "One closed polyline per cell, on the thrust surface, as a "
                + "TREE branched by COURSE (path = course, 0 up from the "
                + "bottom), cells ordered along the course within each "
                + "branch: the studio's build sequence. Wire into "
                + "Export's Cells; Export flattens and projects itself.",
            GH_ParamAccess.tree);
        parameters.AddIntegerParameter(
            "Courses",
            "CO",
            "The course per cell, branched and ordered exactly as Cells, "
                + "the index repeated per item, so the pairing survives "
                + "Export's flatten. Wire into Export's Courses.",
            GH_ParamAccess.tree);
        parameters.AddCurveParameter(
            "Flowlines",
            "FL",
            "The advected flow lines, force-aligned pattern only; empty "
                + "for the native patterns.",
            GH_ParamAccess.tree);
        parameters.AddTextParameter(
            "Diagnostics",
            "D",
            "Readable text. Native patterns: the pattern name, cell and "
                + "course counts, mean/min/max piece length, the stagger, "
                + "and the count of boundary-clipped cells. Force "
                + "aligned: the worker's diagnostics verbatim.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (InPreSolve)
        {
            if (!TryReadInputs(
                    data,
                    out ResultDto? result,
                    out int pattern,
                    out double size,
                    out double _,
                    report: false))
            {
                TaskList.Add(NoTask());
                return;
            }
            // Only the force-aligned pattern dispatches the worker; the
            // native patterns compute synchronously in the post phase.
            // Both still leave a PLACEHOLDER, so the list keeps its
            // iteration indices.
            if (pattern != 2)
            {
                TaskList.Add(NoTask());
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

        // The post phase re-reads the inputs itself, same as Export: the
        // pre phase read quietly, so invalid inputs are reported exactly
        // once, here.
        if (!TryReadInputs(
                data,
                out ResultDto? postResult,
                out int postPattern,
                out double postSize,
                out double postCourseHeight))
        {
            return;
        }

        if (postPattern == 2)
        {
            SolveForceAligned(data, postResult!, postSize);
            return;
        }
        SolveNative(
            data, postResult!, postPattern, postSize, postCourseHeight);
    }

    /// <summary>
    /// The placeholder an iteration that dispatches NOTHING still has to
    /// leave in the list. <c>GH_TaskCapableComponent</c> indexes
    /// <c>TaskList</c> BY ITERATION, so a list with a gap in it hands
    /// iteration 3 whatever iteration 1 left behind: on a list mixing
    /// Pattern values one branch would be shown another branch's
    /// force-aligned cells, and in the ordinary case, a native pattern
    /// sitting earlier in the list, the retrieval simply misses and the
    /// post phase falls into the synchronous worker call on the solve
    /// thread, blocking the canvas for the length of a solve. A
    /// COMPLETED task carrying a null result keeps the indices lined up
    /// and reads, in the post phase, as the miss it is; only the
    /// force-aligned pattern ever leaves a real one.
    /// </summary>
    private static Task<ArmadilloDualTaskResult> NoTask() =>
        Task.FromResult<ArmadilloDualTaskResult>(null!);

    private void SolveNative(
        IGH_DataAccess data,
        ResultDto result,
        int pattern,
        double size,
        double courseHeight)
    {
        try
        {
            SkinNet? net = SkinPatterns.ReadNet(result);
            if (net is null || net.Faces.Count == 0)
            {
                // The parenthesis is only true of the FD path. A TNA
                // Result whose form graph carries no faces reaches this
                // branch too, and telling its author it is an FD Result
                // would send them looking for the wrong fault.
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Remark,
                    ResultTables.IsTna(result)
                        ? "No faces on this Result, so there are no cells."
                        : "No faces on this Result (FD carries none), so "
                            + "there are no cells.");
                data.SetDataTree(
                    0, OutputTree.Curves(Array.Empty<List<Curve>>()));
                data.SetDataTree(
                    1, OutputTree.Integers(Array.Empty<List<int>>()));
                data.SetDataTree(
                    2, OutputTree.Curves(Array.Empty<List<Curve>>()));
                data.SetData(3, string.Empty);
                Message = $"0 cells · 0 courses · {PatternName(pattern)}";
                return;
            }
            SkinPatternResult generated = pattern == 0
                ? SkinPatterns.Courses(net, size, courseHeight)
                : SkinPatterns.Hexagonal(net, size, courseHeight);

            // A band the engine REFUSED because the level curves changed
            // component count across it (a low loop splitting into
            // separate strips higher up, a two-hump barrel). The engine
            // records the heights in D; the canvas has to be told there
            // is a HOLE, because an author who only sees the cells would
            // read the gap as a pattern he chose.
            if (generated.TransitionBands > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{generated.TransitionBands} band" +
                    (generated.TransitionBands == 1 ? " was" : "s were") +
                    " skipped where the level curves split, so the skin " +
                    "has a HOLE at those heights and this pattern does " +
                    "not cover the surface. Diagnostics names the " +
                    "heights.");
            }

            var cellBranches = new List<List<Curve>>();
            var courseBranches = new List<List<int>>();
            for (int course = 0; course < generated.CourseCount; course++)
            {
                cellBranches.Add(new List<Curve>());
                courseBranches.Add(new List<int>());
            }
            foreach (SkinCell cell in generated.Cells)
            {
                int course = Math.Min(
                    Math.Max(cell.Course, 0),
                    Math.Max(generated.CourseCount - 1, 0));
                cellBranches[course].Add(ClosedOutlineCurve(cell.Outline));
                courseBranches[course].Add(course);
            }
            data.SetDataTree(0, OutputTree.Curves(cellBranches));
            data.SetDataTree(1, OutputTree.Integers(courseBranches));
            data.SetDataTree(
                2, OutputTree.Curves(Array.Empty<List<Curve>>()));
            data.SetData(3, generated.Diagnostics);
            Message =
                $"{generated.Cells.Count} cells · " +
                $"{generated.CourseCount} courses · " +
                PatternName(pattern);
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Skin failed", error);
        }
    }

    /// <summary>
    /// The post-solve half of the retired ArmadilloDualComponent, moved:
    /// the cancellation recompute, the verbatim worker refusal, the
    /// decode to curves. Only the output boundary is new: the flat lists
    /// became course-branched trees, and the message line follows the
    /// one-component convention.
    /// </summary>
    private void SolveForceAligned(
        IGH_DataAccess data,
        ResultDto result,
        double size)
    {
        ArmadilloDualTaskResult taskResult;
        bool haveTaskResult = GetSolveResults(data, out taskResult!);
        if (!haveTaskResult ||
            taskResult is null ||
            taskResult.Error is OperationCanceledException)
        {
            // A NULL retrieval is the placeholder an iteration that did
            // not dispatch left behind (see NoTask), and it is a MISS,
            // not a result: this iteration's Pattern was read as 2 in
            // the post phase but not in the pre phase, which a change of
            // inputs between the two phases can do. Recompute.
            //
            // A cancelled background task is a scheduling race, not a
            // verdict on the current inputs; recompute synchronously so a
            // late cancellation cannot strand the canvas on "Cancelled"
            // with empty outputs.
            taskResult = ComputeAsync(
                    CloneResult(result),
                    size,
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
                "Skin force aligned: " +
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
                "Skin force aligned produced no pattern.");
            return;
        }
        if (taskResult.Warning is not null)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                "Skin force aligned: " + taskResult.Warning);
        }

        // Curve construction happens here, on the solve thread, and only
        // here: the background task above never sees RhinoCommon, only
        // plain doubles.
        int courseCount = 0;
        foreach (ArmadilloDualCellData cell in taskResult.Cells)
            courseCount = Math.Max(courseCount, Math.Max(cell.Course, 0) + 1);
        var cellBranches = new List<List<Curve>>();
        var courseBranches = new List<List<int>>();
        for (int course = 0; course < courseCount; course++)
        {
            cellBranches.Add(new List<Curve>());
            courseBranches.Add(new List<int>());
        }
        foreach (ArmadilloDualCellData cell in taskResult.Cells)
        {
            // A worker course below zero cannot be a tree path; it lands
            // in branch 0 with its cell KEPT.
            int course = Math.Max(cell.Course, 0);
            cellBranches[course].Add(ClosedOutlineCurve(cell.Outline));
            courseBranches[course].Add(course);
        }
        var flowlineCurves = new List<Curve>(taskResult.Flowlines.Count);
        foreach (double[][] line in taskResult.Flowlines)
            flowlineCurves.Add(OpenOutlineCurve(line));

        if (taskResult.Cells.Count == 0)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                "Skin force aligned: no cells were generated. " +
                taskResult.Diagnostics.Replace("\n", "; "));
        }

        data.SetDataTree(0, OutputTree.Curves(cellBranches));
        data.SetDataTree(1, OutputTree.Integers(courseBranches));
        data.SetDataTree(2, OutputTree.Curves(new[] { flowlineCurves }));
        data.SetData(3, taskResult.Diagnostics);
        Message =
            $"{taskResult.Cells.Count} cells · {courseCount} courses · " +
            "force aligned";
    }

    private static string PatternName(int pattern) =>
        pattern switch
        {
            0 => "courses",
            1 => "hexagonal",
            _ => "force aligned"
        };

    /// <summary>
    /// Each outline is CLOSED by appending its first point again; both
    /// the native engines' cells and the worker's decoded cells arrive
    /// as open rings and leave through this one method. Moved verbatim.
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

    /// <summary>A flowline is open: it is not a cell boundary. Moved
    /// verbatim.</summary>
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
    /// Read RES, Pattern, S and CH, validating up front so the background
    /// task never has to report a runtime message itself. S keeps the
    /// Armadillo Dual guard: a NaN or sub-millimetre S is REFUSED with
    /// the negated comparison (NaN fails every comparison, so a guard
    /// written the other way round would let it through, and the worker
    /// would return a silent empty result). CH keeps the old Skin's rule:
    /// floored to the default with a warning. A Pattern outside 0..2 is
    /// refused naming the three patterns.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out ResultDto? result,
        out int pattern,
        out double size,
        out double courseHeight,
        bool report = true)
    {
        result = null;
        pattern = 0;
        size = DefaultSize;
        courseHeight = DefaultCourseHeight;
        ResultGoo? resultGoo = null;
        int patternInput = 0;
        double sizeInput = DefaultSize;
        double courseHeightInput = DefaultCourseHeight;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            return false;
        }
        data.GetData(1, ref patternInput);
        data.GetData(2, ref sizeInput);
        data.GetData(3, ref courseHeightInput);

        var errors = new List<string>(resultValue.Validate());
        if (patternInput < 0 || patternInput > 2)
        {
            errors.Add(
                "Pattern must be 0 (courses), 1 (hexagonal) or 2 " +
                $"(force aligned); received {patternInput}.");
        }
        if (!(sizeInput > 0.001))
        {
            errors.Add(
                "S must be greater than 1 mm (0.001 m); received " +
                $"{sizeInput}.");
        }
        if (!(courseHeightInput > 0.001))
        {
            if (report)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Course Height must be at least 1 mm; using 0.35 m.");
            }
            courseHeightInput = DefaultCourseHeight;
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
        pattern = patternInput;
        size = sizeInput;
        courseHeight = courseHeightInput;
        return true;
    }

    /// <summary>
    /// <c>ContractJson.DeepClone</c> round-trips through
    /// <see cref="ResultDto"/>'s own serializer options, which
    /// <c>[JsonIgnore]</c> deliberately excludes <see cref="ResultDto.RawWire"/>
    /// from: it is a transport artefact, not part of the native contract, so
    /// a plain deep clone would silently drop it. Reattach it afterwards; a
    /// string needs no isolation of its own, it is immutable already. Copied
    /// from <c>ExportComponent.CloneResult</c>. Moved verbatim.
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
    /// back empty, and callers are warned. Moved verbatim.
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
    /// "diagnostics": {...}}</c> response into plain data: no
    /// <c>RhinoCommon</c> type appears anywhere in this method, so it is
    /// safe to run on the background task. Moved verbatim.
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
    /// cell size when at least one cell exists. Moved verbatim.
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
    /// "missing reads as none" convention ``OptionalInt`` uses. Moved
    /// verbatim.
    /// </summary>
    private static int ArrayLength(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out JsonElement value) &&
            value.ValueKind == JsonValueKind.Array
                ? value.GetArrayLength()
                : 0;
    }

    /// <summary>
    /// One mesh face's corner points, in winding order: three for a
    /// triangle, four for a quad. Kept from the old Skin because
    /// <see cref="FacePolylines"/> reads corners this way.
    /// </summary>
    private static IReadOnlyList<Point3d> FaceCorners(
        Mesh mesh,
        MeshFace face)
    {
        var points = new List<Point3d>(4)
        {
            mesh.Vertices[face.A],
            mesh.Vertices[face.B],
            mesh.Vertices[face.C]
        };
        if (face.IsQuad)
            points.Add(mesh.Vertices[face.D]);
        return points;
    }

    /// <summary>
    /// One closed polyline per mesh face, in face order. Internal because
    /// EXPORT calls it, for the tessellation it builds when nobody wired
    /// one (one cell per face, course 0): the signature is a compile-time
    /// contract with DeliveryComponents.cs and does not move.
    /// </summary>
    internal static IReadOnlyList<PolylineCurve> FacePolylines(Mesh mesh)
    {
        var polylines = new List<PolylineCurve>(mesh.Faces.Count);
        for (int i = 0; i < mesh.Faces.Count; i++)
        {
            IReadOnlyList<Point3d> corners =
                FaceCorners(mesh, mesh.Faces[i]);
            var points = new List<Point3d>(corners.Count + 1);
            points.AddRange(corners);
            points.Add(points[0]);
            polylines.Add(new PolylineCurve(points));
        }
        return polylines;
    }
}
