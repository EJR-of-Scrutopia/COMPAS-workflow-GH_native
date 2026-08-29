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
    IReadOnlyList<(string Kind, string Json)>? Payloads,
    string? Warning,
    Exception? Error,
    TimeSpan Elapsed);

/// <summary>
/// One Export solve's nine inputs, gathered and validated on the solve
/// thread. Both phases read the same nine, and nine out parameters had
/// stopped being a signature anybody could read.
/// </summary>
public sealed record ExportInputs(
    ResultDto Result,
    string Path,
    bool Write,
    string Name,
    IReadOnlyList<TessellationCell>? Cells,
    string? CellWarning,
    bool Live,
    string Studio,
    double Radius);

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
/// The one delivery boundary for a solved Result, and the Result decides
/// what comes out of it: every Result is a portable contract and a native
/// COMPAS document (the worker's <c>export.compas</c>), a Result with
/// Cells wired is also the studio's bench.tessellation/1 cutting sidecar,
/// and a Result whose Mould block carries columns is also a columns mesh.
/// Write puts the whole set on disk as
/// <c>&lt;Name&gt;-&lt;kind&gt;.json</c>; Live pushes the same set to the
/// studio, debounced, off the UI thread.
/// </summary>
public sealed class ExportComponent :
    NativeTaskComponentBase<ExportComponentTaskResult>
{
    private const string DefaultStudio = "http://127.0.0.1:8600";
    private const string DefaultName = "ananke-export";
    private const double DefaultColumnRadius = 0.05;

    // A Button feeding Write is only True for the press solve; the release
    // immediately triggers a second solve with Write false. Latching the
    // last written set keeps the evidence of the one-shot write on the
    // component instead of wiping it milliseconds after it happened.
    private IReadOnlyList<string>? _lastWritten;

    // One uploader per component, so two Exports on a canvas debounce and
    // retry independently. Its callback arrives on a thread-pool thread,
    // so the expire it asks for is marshalled to the UI thread here:
    // nothing off that thread is allowed to touch a Grasshopper object.
    // Not readonly and not built in the constructor: RemovedFromDocument
    // disposes it, and Grasshopper puts the SAME instance back when that
    // removal is undone, so it has to be replaceable.
    private LiveUploader? _uploader;

    public ExportComponent()
        : base(
            "Export",
            "Export",
            "Write everything a solved Result can be, contract and " +
            "COMPAS always, a tessellation sidecar when cells are wired, " +
            "a columns mesh when the Result carries columns, and push " +
            "the set live to the studio.",
            ComponentCategories.Delivery,
            "export")
    {
    }

    public override Guid ComponentGuid =>
        new("f2a6c8e4-1b5d-49a3-b7e0-3c9f5d8a2617");

    /// <summary>
    /// An ordinary delete disposes the uploader (below), and an undo, a
    /// paste or a move into a cluster hands the very same instance back to
    /// a document. A disposed uploader accepts nothing, so without this
    /// Live would be dead for the rest of the session with nothing said
    /// anywhere. Built here, and lazily again before an enqueue, for a
    /// document that never announces the object at all.
    /// </summary>
    public override void AddedToDocument(GH_Document document)
    {
        EnsureUploader();
        base.AddedToDocument(document);
    }

    /// <summary>
    /// The uploader owns a debounce timer and may have a send in flight; a
    /// component deleted from the canvas must leave neither running, and
    /// must not be expired by an outcome arriving for something that is no
    /// longer there.
    /// </summary>
    public override void RemovedFromDocument(GH_Document document)
    {
        _uploader?.Dispose();
        base.RemovedFromDocument(document);
    }

    /// <summary>
    /// The live uploader, built on first use and rebuilt after a disposal.
    /// Called on the UI/solve thread only.
    /// </summary>
    private LiveUploader EnsureUploader()
    {
        if (_uploader is null || _uploader.IsDisposed)
        {
            _uploader = new LiveUploader(
                () => RhinoApp.InvokeOnUiThread(
                    new Action(() => ExpireSolution(true))));
        }
        return _uploader;
    }

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
            "Path",
            "P",
            "A folder, or a file whose folder is used, for the Write " +
            "trigger; missing folders are created.",
            GH_ParamAccess.item,
            string.Empty);
        parameters[1].Optional = true;
        parameters.AddBooleanParameter(
            "Write",
            "W",
            "Push the export to disk: while True, every kind this Result " +
            "carries is written under Path on every solve. Wire a button " +
            "for one-shot writes. The JSON outputs themselves are always " +
            "live.",
            GH_ParamAccess.item,
            false);
        parameters.AddTextParameter(
            "Name",
            "N",
            "The study name. Files are <Name>-<kind>.json under Path and " +
            "the studio's export name is <Name>; blank uses " +
            "ananke-export.",
            GH_ParamAccess.item,
            string.Empty);
        parameters[3].Optional = true;
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "One closed planar outline per cutting cell (a brick), " +
            "authored against the solved form the Result still carries. " +
            "Wire Skin's Face Polylines straight in; the tree is " +
            "flattened here. Projected to plan (z dropped) into the " +
            "sidecar's outline points; non-polyline curves are " +
            "approximated at a 5 mm chord. Wiring them is what adds the " +
            "tessellation kind to the export.",
            GH_ParamAccess.list);
        parameters[4].Optional = true;
        parameters[4].DataMapping = GH_DataMapping.Flatten;
        parameters.AddIntegerParameter(
            "Courses",
            "CO",
            "The course (row) index per cell, same length as Cells, from " +
            "Skin's Face Courses; the tree is flattened here. The studio " +
            "stages the build animation course by course. Empty puts " +
            "every cell in course 0, one single stage.",
            GH_ParamAccess.list);
        parameters[5].Optional = true;
        parameters[5].DataMapping = GH_DataMapping.Flatten;
        parameters.AddBooleanParameter(
            "Live",
            "L",
            "Push the set to the studio on every solve, debounced half a " +
            "second, retrying a 409 while the studio has a run in " +
            "flight. Failures are warnings; the files and outputs stand.",
            GH_ParamAccess.item,
            false);
        parameters.AddTextParameter(
            "Studio",
            "S",
            "The studio's base URL.",
            GH_ParamAccess.item,
            DefaultStudio);
        parameters[7].Optional = true;
        parameters.AddNumberParameter(
            "Column Radius",
            "R",
            "Radius of the prism each column member is drawn as in the " +
            "columns mesh, in document units.",
            GH_ParamAccess.item,
            DefaultColumnRadius);
        parameters[8].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddTextParameter(
            "Contract JSON",
            "CJ",
            "The portable native contract, always produced.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "COMPAS JSON",
            "MJ",
            "The native COMPAS json_dumps geometry the worker's " +
            "export.compas command produces; empty, with a warning, when " +
            "the worker could not produce it, and the rest of the export " +
            "stands.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Tessellation JSON",
            "TJ",
            "The studio's bench.tessellation/1 authored cutting sidecar; " +
            "empty unless Cells are wired.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Columns JSON",
            "KJ",
            "The columns mesh, one prism per column member, with the " +
            "members themselves beside it; empty unless the Result " +
            "carries columns.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Written",
            "W",
            "The most recent files this component wrote this session, " +
            "one per line, so a one-shot Button write stays visible " +
            "after release; empty until a write happens.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Uploaded",
            "U",
            "The most recent upload outcome, one line per kind; Live is " +
            "off says so while Live is False.",
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
                if (!TryReadInputs(data, out ExportInputs? pre, report: false))
                    return;
                // Resolved here, on the solve thread: RhinoDoc.ActiveDoc
                // is not a background thread's to read, and the lambda
                // below runs on one.
                double unitFactor = ResolveUnitFactor();
                TaskList.Add(Task.Run(
                    () => ComputeAsync(
                        CloneResult(pre!.Result),
                        pre.Cells,
                        pre.CellWarning,
                        unitFactor,
                        pre.Radius,
                        CancelToken),
                    CancelToken));
                return;
            }

            // One Export is one study: it writes one set of
            // <name>-<kind>.json files and enqueues one upload. Slot 0 is
            // item access, so a Result tree with more than one item makes
            // every iteration after the first overwrite the files the last
            // one wrote and supersede the set it enqueued, and only the
            // last one survives. Said once, on the second iteration, so a
            // wide tree does not repeat itself down the whole chin.
            if (data.Iteration == 1)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Export handles one Result per component; the last " +
                    "one wins.");
            }

            // The post phase re-reads the inputs itself: the disk write
            // and the upload are side effects and belong on this thread,
            // where a Button's release re-solve cannot cancel them
            // mid-flight, and where a cancelled pre-solve branch cannot
            // leave half a set behind.
            if (!TryReadInputs(data, out ExportInputs? inputs))
                return;
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
                        CloneResult(inputs!.Result),
                        inputs.Cells,
                        inputs.CellWarning,
                        ResolveUnitFactor(),
                        inputs.Radius,
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
            if (taskResult.Payloads is null || taskResult.Payloads.Count == 0)
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

            string name = inputs!.Name.Trim();
            if (name.Length == 0)
                name = DefaultName;

            if (inputs.Write && !string.IsNullOrWhiteSpace(inputs.Path))
            {
                if (!TryResolveWriteFolder(
                        inputs.Path,
                        out string folder,
                        out string refusal))
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "Export: " + refusal);
                }
                else
                {
                    // Declared outside the try so a set that fails halfway
                    // still latches the files that did land: which kinds
                    // reached disk is exactly what the author needs to see
                    // when one of them could not.
                    var written = new List<string>(taskResult.Payloads.Count);
                    try
                    {
                        Directory.CreateDirectory(folder);
                        foreach ((string kind, string json) in taskResult.Payloads)
                        {
                            string target = Path.Combine(
                                folder, $"{name}-{kind}.json");
                            File.WriteAllText(target, json);
                            written.Add(target);
                        }
                    }
                    catch (Exception writeException)
                    {
                        AddRuntimeMessage(
                            GH_RuntimeMessageLevel.Error,
                            "Export: failed to write file: " +
                            writeException.Message);
                    }
                    if (written.Count > 0)
                        _lastWritten = written;
                }
            }

            string contractJson = string.Empty;
            string compasJson = string.Empty;
            string tessellationJson = string.Empty;
            string columnsJson = string.Empty;
            foreach ((string kind, string json) in taskResult.Payloads)
            {
                switch (kind)
                {
                    case "contract":
                        contractJson = json;
                        break;
                    case "compas":
                        compasJson = json;
                        break;
                    case "tessellation":
                        tessellationJson = json;
                        break;
                    case "columns":
                        columnsJson = json;
                        break;
                }
            }

            // Enqueued here and never in InPreSolve: a send is a side
            // effect on the studio, the pre phase runs once per branch and
            // can be cancelled, and the uploader is not the solve thread's
            // to drive twice.
            string uploaded = "Live is off";
            if (inputs.Live)
            {
                LiveUploader uploader = EnsureUploader();
                uploader.Enqueue(new LiveUploader.Pending(
                    inputs.Studio,
                    name,
                    taskResult.Payloads));
                // Read ONCE, under one lock acquisition: the text and the
                // verdict taken separately let a send land between them,
                // and the component would print one set's failure with
                // the other set's flag.
                LiveUploader.Snapshot state = uploader.Current;
                uploaded = Display(state);
                // The upload is best effort: the files and the JSON
                // outputs stand whatever the studio said, so a refusal, a
                // deferral or a transport failure is a Warning here and
                // never an Error. Whether it was one is the uploader's own
                // record of the verdicts it classified, not this
                // component's reading of its prose. Only an outcome that
                // has landed is worth a Warning; a set still going carries
                // the previous verdict and nothing to say about this one.
                if (state.Failed && state.Phase == LiveUploader.Phase.Done)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "Export live: " + state.Text);
                }
            }

            data.SetData(0, contractJson);
            data.SetData(1, compasJson);
            data.SetData(2, tessellationJson);
            data.SetData(3, columnsJson);
            data.SetData(
                4,
                _lastWritten is null
                    ? string.Empty
                    : string.Join(Environment.NewLine, _lastWritten));
            data.SetData(5, uploaded);
            Message =
                $"{taskResult.Payloads.Count} kinds · {FirstLine(uploaded)}";
        }
        catch (Exception error)
        {
            Message = "Failed";
            ReportException("Export failed", error);
        }
    }

    /// <summary>
    /// What Uploaded says for one reading of the uploader. A set waiting
    /// out the debounce or on the wire says "sending" rather than showing
    /// the PREVIOUS set's outcome: against an unreachable studio a set
    /// takes half a minute a kind, and a "stored" left standing for two
    /// minutes claims a send that never happened.
    /// </summary>
    private static string Display(LiveUploader.Snapshot state) =>
        state.Phase switch
        {
            LiveUploader.Phase.Pending or LiveUploader.Phase.Sending =>
                "sending",
            _ => state.Text,
        };

    /// <summary>
    /// The Message is one line of a component's chin; the outcome carries
    /// one line per kind, so only the first of them fits.
    /// </summary>
    private static string FirstLine(string text)
    {
        int end = text.IndexOf('\n');
        return end < 0 ? text : text[..end].TrimEnd('\r');
    }

    /// <summary>
    /// A Path may name a file or a folder: canvas path pickers commonly
    /// hand over a directory when the target file does not exist yet, and
    /// a definition saved before this rework may still carry a file path.
    /// Either way only the folder is used, because one solve writes a
    /// whole set of files and the names inside it are the study's, not the
    /// Path's.
    ///
    /// A Path with no extension is a FOLDER, whether or not it exists yet:
    /// an author who types C:\exports\my-study means a new folder to hold
    /// the study, and reading it as a file dropped the whole set one level
    /// up, silently, beside the folder they meant. A trailing separator
    /// and an existing directory are folders too. A Path with an extension
    /// is a file and its own directory is used.
    ///
    /// Refused, rather than resolved, when the Path is not rooted
    /// (System.IO.Path.IsPathRooted is false): a bare name (my-study, or
    /// export.json) and a relative path with directories of its own
    /// (sub\study) are both relative to the process working directory,
    /// which under Rhino is somewhere the author will never find.
    /// Nothing is written and the caller says so, naming the path.
    ///
    /// A rooted Path can still be refused, unchanged from before: when
    /// the folder that comes out has no directory part of its own, a
    /// drive root is not a place to scatter a study, and the caller
    /// says so the same way.
    /// </summary>
    private static bool TryResolveWriteFolder(
        string path,
        out string folder,
        out string refusal)
    {
        string trimmed = path.Trim();
        if (!Path.IsPathRooted(trimmed))
        {
            refusal =
                "Path '" + trimmed + "' is not rooted, so nothing was " +
                "written. Give a full folder path, for example " +
                "C:\\exports\\my-study.";
            folder = string.Empty;
            return false;
        }
        bool looksLikeDirectory =
            trimmed.EndsWith(
                Path.DirectorySeparatorChar.ToString(),
                StringComparison.Ordinal) ||
            trimmed.EndsWith(
                Path.AltDirectorySeparatorChar.ToString(),
                StringComparison.Ordinal) ||
            Directory.Exists(trimmed) ||
            Path.GetExtension(trimmed).Length == 0;
        folder = looksLikeDirectory
            ? trimmed
            : Path.GetDirectoryName(trimmed) ?? string.Empty;
        if (string.IsNullOrEmpty(Path.GetDirectoryName(folder)))
        {
            refusal =
                "Path '" + trimmed + "' names no folder to write into, " +
                "so nothing was written. Give a full folder path, for " +
                "example C:\\exports\\my-study.";
            folder = string.Empty;
            return false;
        }
        refusal = string.Empty;
        return true;
    }

    /// <summary>
    /// Read the nine inputs and validate the Result up front so the
    /// background task never has to report a runtime message itself. Cells
    /// are validated whenever they are wired, since wiring them is what
    /// asks for the tessellation kind; a Column Radius that is not a
    /// positive finite number and a blank Studio under Live both fall back
    /// and say so. The write and the upload themselves happen in the post
    /// phase; this only gathers and validates.
    /// </summary>
    private bool TryReadInputs(
        IGH_DataAccess data,
        out ExportInputs? inputs,
        bool report = true)
    {
        inputs = null;
        ResultGoo? resultGoo = null;
        string pathInput = string.Empty;
        bool writeInput = false;
        string nameInput = string.Empty;
        var cellInput = new List<Curve>();
        var courseInput = new List<int>();
        bool liveInput = false;
        string studioInput = DefaultStudio;
        double radiusInput = DefaultColumnRadius;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            return false;
        }
        data.GetData(1, ref pathInput);
        data.GetData(2, ref writeInput);
        data.GetData(3, ref nameInput);
        data.GetDataList(4, cellInput);
        data.GetDataList(5, courseInput);
        data.GetData(6, ref liveInput);
        data.GetData(7, ref studioInput);
        data.GetData(8, ref radiusInput);

        IReadOnlyList<TessellationCell>? cells = null;
        string? cellWarning = null;
        var errors = new List<string>(resultValue.Validate());
        var notes = new List<string>();
        if (writeInput && string.IsNullOrWhiteSpace(pathInput))
            errors.Add("Write requires a Path to write to.");
        if (cellInput.Count > 0)
        {
            if (courseInput.Count != 0 &&
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
                // pins course >= 0 and refuses, late, remote, and
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

        double radius = radiusInput;
        if (!double.IsFinite(radius) || radius <= 0.0)
        {
            radius = DefaultColumnRadius;
            notes.Add(
                "Column Radius must be a positive finite number; " +
                DefaultColumnRadius.ToString(
                    "0.################",
                    System.Globalization.CultureInfo.InvariantCulture) +
                " used.");
        }
        string studio = (studioInput ?? string.Empty).Trim();
        if (studio.Length == 0)
        {
            studio = DefaultStudio;
            if (liveInput)
            {
                notes.Add(
                    "Live needs a Studio URL; " + DefaultStudio +
                    " used.");
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
        if (report)
        {
            foreach (string note in notes)
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, note);
        }

        inputs = new ExportInputs(
            resultValue,
            pathInput ?? string.Empty,
            writeInput,
            nameInput ?? string.Empty,
            cells,
            cellWarning,
            liveInput,
            studio,
            radius);
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

    /// <summary>
    /// Every kind the Result can be, in ExportPlan's order, built once.
    /// The contract and the COMPAS document are always asked for; the
    /// tessellation sidecar joins them when cells were wired and the
    /// columns mesh when the Mould block carries at least one member. Each
    /// kind's own warning joins the one warning the post phase reports,
    /// and a COMPAS document the worker could not produce is one of those
    /// warnings rather than the end of the whole export.
    /// </summary>
    private static async Task<ExportComponentTaskResult> ComputeAsync(
        ResultDto result,
        IReadOnlyList<TessellationCell>? cells,
        string? cellWarning,
        double unitFactor,
        double radius,
        CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            MouldColumnsDto? block = result.Mould?.Columns;
            bool hasColumns = block is not null && block.Members.Count > 0;
            bool hasCells = cells is not null && cells.Count > 0;
            string[] kinds = ExportPlan.Kinds(hasCells, hasColumns);
            var payloads = new List<(string Kind, string Json)>(kinds.Length);
            var warnings = new List<string>();
            foreach (string kind in kinds)
            {
                switch (kind)
                {
                    case "contract":
                        payloads.Add((kind, ContractJson.Serialize(result)));
                        break;
                    case "compas":
                    {
                        // The only kind that needs the worker, and so the
                        // only one that can fail because something outside
                        // this component is down. Caught on its own: a
                        // worker that will not start, a request that times
                        // out or a worker-side error used to cost the
                        // contract, the tessellation, the columns, the
                        // disk write and the Written output too, none of
                        // which ever touch the worker. Now the set simply
                        // lacks this kind, which is the same shape as any
                        // other absent kind, and everything else stands.
                        try
                        {
                            (string json, string? warning) =
                                await BuildCompasJsonAsync(
                                        result,
                                        unitFactor,
                                        cancellationToken)
                                    .ConfigureAwait(false);
                            payloads.Add((kind, json));
                            if (!string.IsNullOrEmpty(warning))
                                warnings.Add(warning!);
                        }
                        catch (OperationCanceledException)
                        {
                            // A cancellation is not a verdict on the
                            // worker; the post phase recomputes.
                            throw;
                        }
                        catch (Exception compasError)
                        {
                            warnings.Add(
                                "compas: " +
                                compasError.GetBaseException().Message);
                        }
                        break;
                    }
                    case "tessellation":
                    {
                        // Pure serialisation of cells already reduced to
                        // plain numbers on the solve thread; no worker, no
                        // geometry.
                        payloads.Add(
                            (kind, BuildTessellationJson(cells!, unitFactor)));
                        if (!string.IsNullOrEmpty(cellWarning))
                            warnings.Add(cellWarning!);
                        if (Math.Abs(unitFactor - 1.0) > 1e-12)
                        {
                            // Disclosed the way ImportPiecesComponent
                            // discloses its own factor: a silent scale is
                            // the thing that makes a units mismatch hard
                            // to find later.
                            warnings.Add(
                                "Document units converted to metres by a " +
                                "factor of " + unitFactor.ToString(
                                    "0.################",
                                    System.Globalization.CultureInfo
                                        .InvariantCulture) + ".");
                        }
                        break;
                    }
                    case "columns":
                        payloads.Add((
                            kind,
                            ColumnsMesh.Json(
                                ColumnMembers(block!),
                                radius,
                                ForceUnitOf(result),
                                unitFactor)));
                        break;
                    default:
                        throw new InvalidOperationException(
                            $"Export does not know the kind '{kind}'.");
                }
            }
            stopwatch.Stop();
            return new ExportComponentTaskResult(
                payloads,
                warnings.Count == 0 ? null : string.Join(" ", warnings),
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
    /// The block's members as the two node points and the force on each,
    /// which is the only shape ColumnsMesh reads. Every member index is
    /// already inside Nodes and MemberForce is already one value per
    /// member: MouldColumnsDto.Validate refuses anything else, and
    /// TryReadInputs runs that validation before this is ever reached.
    /// </summary>
    private static IReadOnlyList<(Point3d From, Point3d To, double Force)>
        ColumnMembers(MouldColumnsDto block)
    {
        var members =
            new List<(Point3d From, Point3d To, double Force)>(
                block.Members.Count);
        for (int i = 0; i < block.Members.Count; i++)
        {
            EdgeDto member = block.Members[i];
            Point3Dto from = block.Nodes[member.U];
            Point3Dto to = block.Nodes[member.V];
            members.Add((
                new Point3d(from.X, from.Y, from.Z),
                new Point3d(to.X, to.Y, to.Z),
                i < block.MemberForce.Count ? block.MemberForce[i] : 0.0));
        }
        return members;
    }

    /// <summary>
    /// The unit the Result's own forces are in, which the columns mesh
    /// carries so the studio never has to assume newtons. Blank falls back
    /// to the contract's own default rather than to nothing.
    /// </summary>
    private static string ForceUnitOf(ResultDto result)
    {
        string unit = (result.Equilibrium?.ForceUnit ?? string.Empty).Trim();
        return unit.Length == 0 ? "kN" : unit;
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
