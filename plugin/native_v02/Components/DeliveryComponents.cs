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
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;
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
    double Radius,
    // Which of the two the cells came from, in the word the sidecar's own
    // "pattern" key carries: "authored" for cells somebody wired, "faces"
    // for the ones Export made from the Result's own mesh. The studio reads
    // this to know whether anyone chose the cutting pattern, so the fallback
    // must not claim to have been authored.
    string TessellationPattern);

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
/// Where one solve's cutting cells come from.
/// </summary>
internal enum CellSource
{
    /// <summary>Cells wired on the canvas, from Skin or from anywhere.</summary>
    Wired,

    /// <summary>The Result's own thrust-mesh faces, one cell each.</summary>
    Faces,

    /// <summary>Neither, so the set carries no tessellation sidecar.</summary>
    None,
}

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

    // The two words the sidecar's "pattern" key can carry. Cells somebody
    // wired were authored; cells Export built from the Result's own faces
    // were not, and saying they were told the studio a cutting pattern had
    // been chosen when nobody had chosen one.
    private const string AuthoredPattern = "authored";
    private const string FacesPattern = "faces";

    // A Button feeding Write is only True for the press solve; the release
    // immediately triggers a second solve with Write false. Latching the
    // last written set keeps the evidence of the one-shot write on the
    // component instead of wiping it milliseconds after it happened.
    private IReadOnlyList<string>? _lastWritten;

    // The default tessellation is a pure function of the Result, and both
    // phases of one solve call TryReadInputs against the same Result
    // instance, so without this the thrust mesh, the face polylines and the
    // whole reduction ran twice for a set nobody had wired a cell to. Keyed
    // on the reference: a different Result is a different object, and the
    // same object is the same mesh. Both phases run on the solve thread, so
    // there is nothing here for a lock to protect.
    private DefaultTessellation? _defaultTessellation;

    // One uploader per component, so two Exports on a canvas debounce and
    // retry independently. Its callback arrives on a thread-pool thread,
    // so the expire it asks for is marshalled to the UI thread here:
    // nothing off that thread is allowed to touch a Grasshopper object.
    // Not readonly and not built in the constructor: RemovedFromDocument
    // disposes it, and Grasshopper puts the SAME instance back when that
    // removal is undone, so it has to be replaceable.
    private LiveUploader? _uploader;

    // Live is HELD when the file this component came out of was saved
    // against different ports. Grasshopper reattaches archived wires by
    // index, so an old Export's Courses wire now lands on Live, and item
    // access takes the FIRST course: 0 reads false, anything else reads
    // TRUE, and courses can be authored or reordered so that first one
    // is not always 0. Where it is not, the study would be pushed to a
    // studio before the author had read the warning saying the wires
    // moved. Held until Live is seen False and then True again, which is
    // a deliberate act. Read on the first solve, not in the constructor,
    // because the archive is read after the object is built.
    //
    // Gated on the INPUT side only. The hold's whole cause is an archived
    // wire landing on an input this component then obeys, which an
    // output-side change cannot do: Export's own outputs went from six to
    // two on the surface rework with its nine inputs untouched, and holding
    // on that would have held Live on every definition in existence for a
    // change that cannot have moved a single input wire.
    private bool _liveHoldRead;
    private bool _liveHeld;

    public ExportComponent()
        : base(
            "Export",
            "Export",
            "Write everything a solved Result can be, contract and " +
            "COMPAS always, the tessellation sidecar always, from wired " +
            "cells or from the Result's own faces, a columns mesh when the " +
            "Result carries columns, and push the set live to the studio.",
            ComponentCategories.Deliver,
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
        base.AddedToDocument(document);
        EnsureUploader();
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
        // And the cached default tessellation goes with it. It holds a whole
        // ResultDto (equilibrium, form and force graphs, RawWire) plus the
        // cells prepared from it, and a deleted component has no solve
        // coming to replace it, so without this every Export ever placed
        // keeps one solved net alive for the rest of the session.
        _defaultTessellation = null;
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
                () => RhinoApp.InvokeOnUiThread(new Action(OnUploadOutcome)));
        }
        return _uploader;
    }

    /// <summary>
    /// An outcome has landed and the component has to show it. On the UI
    /// thread by the time this runs, and still not free to expire on the
    /// spot: an outcome can arrive while a solution is running, and the
    /// component may have left its document between the send starting and
    /// the outcome coming back. Scheduling asks the document for the
    /// re-solve on its own terms; a component with no document does
    /// nothing at all.
    /// </summary>
    private void OnUploadOutcome()
    {
        if (_uploader is null || _uploader.IsDisposed)
            return;
        GH_Document? document = OnPingDocument();
        if (document is null)
            return;
        document.ScheduleSolution(5, _ => ExpireSolution(false));
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
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "One closed planar outline per cutting cell (a brick), " +
            "authored against the solved form the Result still carries. " +
            "Wire Skin's Cells (C) straight in as a TREE: each branch's " +
            "path index is the course of every cell in that branch, which " +
            "is what the studio stages the build animation by. Any " +
            "Flatten, graft or regraft between Skin and here DESTROYS the " +
            "courses, and a Flatten specifically sends every cell to " +
            "course 0, which is one studio stage instead of many. " +
            "Projected to plan (z dropped) into the sidecar's outline " +
            "points; non-polyline curves are approximated at a 5 mm chord. " +
            "Wiring them is what adds the tessellation kind to the export.",
            GH_ParamAccess.tree);
        parameters[1].Optional = true;
        parameters.AddIntegerParameter(
            "Courses",
            "CO",
            "The course (row) index per cell, same length as Cells, from " +
            "Skin's Courses (CO); the tree is flattened here, on every " +
            "open, so a graft set on this port by hand is wiped when the " +
            "file is reopened. The studio stages the build animation " +
            "course by course. Empty puts every cell in course 0, one " +
            "single stage.",
            GH_ParamAccess.list);
        parameters[2].Optional = true;
        parameters[2].DataMapping = GH_DataMapping.Flatten;
        parameters.AddNumberParameter(
            "Column Radius",
            "R",
            "Radius of the prism each column member is drawn as in the " +
            "columns mesh, in document units (0.05 suits metres; scale it " +
            "for millimetres).",
            GH_ParamAccess.item,
            DefaultColumnRadius);
        parameters[3].Optional = true;
        parameters.AddTextParameter(
            "Name",
            "N",
            "The study name. Files are <Name>-<kind>.json under Path and " +
            "the studio's export name is <Name>; blank uses " +
            "ananke-export. ONE path segment: a Name carrying a slash, a " +
            "backslash, a colon or a dot-dot is refused with a warning, " +
            "and nothing is written or sent. Two Exports sharing a Name " +
            "and a Studio write over each other's files and each other's " +
            "study.",
            GH_ParamAccess.item,
            string.Empty);
        parameters[4].Optional = true;
        parameters.AddTextParameter(
            "Path",
            "P",
            "A folder, or a file whose folder is used, for the Write " +
            "trigger; missing folders are created. The path must be " +
            "ROOTED: a bare name or a relative path is refused with a " +
            "warning and nothing is written, since it would land wherever " +
            "Rhino's working directory happens to be. A path with no " +
            "extension is a folder whether or not it exists yet, and a " +
            "path with an extension gives its own folder. A drive root is " +
            "refused: a study is not scattered across the top of a disk.",
            GH_ParamAccess.item,
            string.Empty);
        parameters[5].Optional = true;
        parameters.AddTextParameter(
            "Studio",
            "S",
            "The studio's base URL.",
            GH_ParamAccess.item,
            DefaultStudio);
        parameters[6].Optional = true;
        parameters.AddBooleanParameter(
            "Live",
            "L",
            "Push the set to the studio on every solve, debounced half a " +
            "second so a slider scrub sends only the final state, " +
            "retrying a 409 (the studio has a run in flight for this " +
            "study) after 2, 4 and 8 seconds and then deferring. A set " +
            "identical to the last one sent is NOT sent again: change the " +
            "Result, or toggle Live off and on. Failures are warnings; " +
            "the files and outputs stand. After a file whose ports moved " +
            "is opened, Live is held until it is set off and then on " +
            "again, so a wire that landed here by accident cannot push a " +
            "study on the first solve.",
            GH_ParamAccess.item,
            false);
        parameters[7].Optional = true;
        parameters.AddBooleanParameter(
            "Write",
            "W",
            "Push the export to disk: while True, every kind this Result " +
            "carries is written under Path on every solve. Wire a button " +
            "for one-shot writes. The JSON outputs themselves are always " +
            "live.",
            GH_ParamAccess.item,
            false);
        parameters[8].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddTextParameter(
            "JSON",
            "J",
            "Every JSON this Result can be, one item per kind and in the " +
            "plan's order: the portable contract and the COMPAS document " +
            "always, the bench.tessellation/1 sidecar whenever there are " +
            "cells, and the bench.columns/1 mesh when the Mould block " +
            "carries columns. A kind that is absent, or that failed, is " +
            "simply not in the list, and every text names itself, so a " +
            "reader knows what each item is without counting slots: the " +
            "contract by its kind and schemaVersion, the COMPAS document " +
            "by its compasVersion and the dtype inside each diagram it " +
            "carries, the tessellation and the columns mesh by their " +
            "schema.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Status",
            "ST",
            "What this solve did, one per line. written: <path> per file " +
            "of the most recent write, or written: nothing; then live: " +
            "<kind>: <outcome> per kind, or live: off while Live is " +
            "False, live: sending while a set is waiting out the debounce " +
            "or on the wire, and a live: held line when the file's ports " +
            "moved on load and Live is waiting to be set off and on; then " +
            "any warning this solve raised, in its own words.",
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
                        StudyName(pre.Name),
                        pre.Cells,
                        pre.CellWarning,
                        pre.TessellationPattern,
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
                        StudyName(inputs.Name),
                        inputs.Cells,
                        inputs.CellWarning,
                        inputs.TessellationPattern,
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

            string name = StudyName(inputs!.Name);
            // Checked after the blank-to-default, so the default is never
            // the thing refused. A Name that is not one segment stops the
            // two side effects and nothing else: the JSON outputs are the
            // Result's own and stand whatever the Name says.
            bool nameIsOneSegment = ExportPlan.NameIsOneSegment(name);
            if (!nameIsOneSegment)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Name '" + name + "' must be one path segment: no " +
                    "slash, backslash, colon or dot-dot. Nothing was " +
                    "written and nothing was sent.");
            }

            bool wroteThisSolve = false;
            if (inputs.Write && nameIsOneSegment &&
                !string.IsNullOrWhiteSpace(inputs.Path))
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
                    string? failedTarget = null;
                    try
                    {
                        Directory.CreateDirectory(folder);
                        foreach ((string kind, string json) in taskResult.Payloads)
                        {
                            string target = Path.Combine(
                                folder, $"{name}-{kind}.json");
                            failedTarget = target;
                            File.WriteAllText(target, json);
                            written.Add(target);
                            failedTarget = null;
                        }
                    }
                    catch (Exception writeException)
                    {
                        AddRuntimeMessage(
                            GH_RuntimeMessageLevel.Error,
                            "Export: failed to write " +
                            (failedTarget ?? folder) + ": " +
                            writeException.Message);
                    }
                    // What THIS solve put on disk, even when that is
                    // nothing: a set failing on its first kind used to
                    // leave the previous solve's list standing under an
                    // Error saying the write had failed, which reads as
                    // files that are there and are not.
                    _lastWritten = written;
                    wroteThisSolve = written.Count > 0;
                }
            }

            // The hold is read once, on the first solve after the archive
            // was read, and cleared by a solve that sees Live False.
            if (!_liveHoldRead)
            {
                _liveHoldRead = true;
                _liveHeld = InputPortsMovedOnLoad;
            }

            // Enqueued here and never in InPreSolve: a send is a side
            // effect on the studio, the pre phase runs once per branch and
            // can be cancelled, and the uploader is not the solve thread's
            // to drive twice.
            string uploaded = "off";
            if (!inputs.Live)
            {
                // Live off means nothing is sent, including a set already
                // waiting out its debounce and a send already sleeping
                // between 409 retries, which without this went on for
                // another quarter of a minute after the toggle. Setting
                // Live off is also the deliberate act that clears the
                // hold, so turning it back on sends.
                _liveHeld = false;
                _uploader?.Cancel();
            }
            else if (_liveHeld)
            {
                uploaded =
                    "held: ports changed on load; set Live off then on to " +
                    "resume";
            }
            else
            {
                LiveUploader uploader = EnsureUploader();
                // Why nothing was enqueued this solve, where nothing was.
                // Live is on and the uploader still holds the LAST set's
                // outcome, so reporting that outcome would say "live:
                // stored" on a solve that sent nothing at all, one line
                // under a Warning saying nothing was sent. Null while a set
                // did go out.
                string? notSent = nameIsOneSegment
                    ? null
                    : "name refused";
                if (notSent is null)
                {
                    uploader.Enqueue(new LiveUploader.Pending(
                        inputs.Studio,
                        name,
                        taskResult.Payloads));
                }
                // Read ONCE, under one lock acquisition: the text and the
                // verdict taken separately let a send land between them,
                // and the component would print one set's failure with
                // the other set's flag.
                LiveUploader.Snapshot state = uploader.Current;
                uploaded = notSent is null
                    ? Display(state)
                    : "nothing sent this solve (" + notSent + ")";
                // The upload is best effort: the files and the JSON
                // outputs stand whatever the studio said, so a refusal, a
                // deferral or a transport failure is a Warning here and
                // never an Error. Whether it was one is the uploader's own
                // record of the verdicts it classified, not this
                // component's reading of its prose. Only an outcome that
                // has landed is worth a Warning; a set still going carries
                // the previous verdict and nothing to say about this one.
                // A solve that enqueued nothing has no outcome of its own
                // to report, and the previous set's failure was reported on
                // the solve it happened.
                if (notSent is null &&
                    state.Failed && state.Phase == LiveUploader.Phase.Done)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "Export live: " + state.Text);
                }
            }

            // One item per kind, in ExportPlan.Kinds order, each naming
            // itself: a reader tells them apart by reading one, not by
            // counting slots, and a kind that is absent or that failed is
            // simply not in the list.
            var payloads = new List<string>(taskResult.Payloads.Count);
            foreach ((string _, string json) in taskResult.Payloads)
                payloads.Add(json);

            // What this solve did, in lines. The written list is the
            // session's latest rather than this solve's, so a one-shot
            // Button write stays visible after the button releases; the
            // live lines are the uploader's own, one per kind; and the
            // warnings are repeated here because a bubble is not a value
            // and the chin holds one line.
            var status = new List<string>();
            if (_lastWritten is null || _lastWritten.Count == 0)
            {
                status.Add("written: nothing");
            }
            else
            {
                foreach (string written in _lastWritten)
                    status.Add("written: " + written);
            }
            foreach (string line in uploaded
                .Replace("\r\n", "\n", StringComparison.Ordinal)
                .Split('\n'))
            {
                status.Add("live: " + line);
            }
            foreach (string warning in
                     RuntimeMessages(GH_RuntimeMessageLevel.Warning))
            {
                status.Add(warning);
            }

            data.SetDataList(0, payloads);
            data.SetData(1, string.Join(Environment.NewLine, status));
            Message =
                $"{taskResult.Payloads.Count} kinds · live {FirstLine(uploaded)}" +
                (wroteThisSolve ? " written" : string.Empty);
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
    /// positive finite number falls back to 0.05, a blank Studio under
    /// Live falls back to the default URL, and Write with a blank Path
    /// writes nothing, all three with a Warning saying so and none of
    /// them costing the solve. The write and the upload themselves happen
    /// in the post phase; this only gathers and validates.
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
        List<string> errors;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            // Said in the chin as well as by the empty port: without it
            // the component sits red under the previous solve's "4 kinds"
            // as though that set were still standing.
            if (report)
                Message = "No Result";
            return false;
        }
        data.GetDataTree(1, out GH_Structure<GH_Curve> cellTree);
        data.GetDataList(2, courseInput);
        data.GetData(3, ref radiusInput);
        data.GetData(4, ref nameInput);
        data.GetData(5, ref pathInput);
        data.GetData(6, ref studioInput);
        data.GetData(7, ref liveInput);
        data.GetData(8, ref writeInput);

        errors = new List<string>(resultValue.Validate());
        var derivedCourses = new List<int>();
        WalkCellTree(cellTree, cellInput, derivedCourses);
        string? branchConflict = DeriveBranchCourses(
            cellTree.Paths.Count, derivedCourses, courseInput);
        if (branchConflict is not null)
            errors.Add(branchConflict);

        IReadOnlyList<TessellationCell>? cells = null;
        string? cellWarning = null;
        var notes = new List<string>();
        var remarks = new List<string>();
        if (writeInput && string.IsNullOrWhiteSpace(pathInput))
        {
            // A missing disk target is not a reason to lose the solve.
            // As an Error this returned before a single output was set,
            // so the four JSON kinds, Written, Uploaded and the live push
            // were all thrown away because nowhere had been named to put
            // a copy. Its sibling refusal, a Path that is not rooted, was
            // only ever a Warning.
            notes.Add("Write is on but Path is blank; nothing written.");
        }
        // The faces are only read when they might be needed, and never
        // when cells are wired: rebuilding a thrust mesh on every solve to
        // throw it away is the kind of cost that turns a slider into a
        // slideshow.
        DefaultTessellation? fallback = null;
        int faceCount = 0;
        if (cellInput.Count == 0 && ResultTables.IsTna(resultValue))
        {
            fallback = DefaultTessellationFor(resultValue);
            faceCount = fallback.FaceCount;
            if (fallback.Note is not null)
                notes.Add(fallback.Note);
        }
        CellSource cellSource = ChooseCells(
            cellInput.Count, courseInput.Count, faceCount, out string? cellRemark);
        if (cellRemark is not null)
            remarks.Add(cellRemark);
        if (cellSource == CellSource.Wired)
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
        else if (cellSource == CellSource.Faces && fallback is not null)
        {
            // Nothing here can reach the errors list. Nobody wired these
            // cells and nobody asked for this tessellation: it is the
            // courtesy the studio's build animation needs, so a face of the
            // Result's own mesh that will not reduce to a cell is skipped
            // and counted, never allowed to cost the contract, the COMPAS
            // document, the columns mesh, the write and the live push. With
            // no face left the list is empty, hasCells is false, and the
            // kind is simply absent, which is the shape every other absent
            // kind already has.
            cells = fallback.Cells;
            foreach (string remark in fallback.Remarks)
                remarks.Add(remark);
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
            foreach (string remark in remarks)
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, remark);
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
            radius,
            PatternFor(cellSource));
        return true;
    }

    /// <summary>
    /// The course of a branch path is its LAST index (rule 10.2.1), not
    /// its first: Skin's own Cells tree only ever nests one level deep
    /// (<c>GH_Path(course)</c>, <c>PiecesComponents.cs</c>'s sibling
    /// convention), so the two coincide for every wire this component
    /// actually receives from Skin today, and this is the one place that
    /// distinction is decided, in case a future author grafts Cells into a
    /// deeper tree before wiring it here. A path with no indices at all
    /// (the tree's own root) is course 0, which is what a single flat
    /// branch means.
    /// </summary>
    private static int CourseForPath(GH_Path branchPath)
    {
        return branchPath.Indices.Length > 0
            ? branchPath.Indices[^1]
            : 0;
    }

    /// <summary>
    /// Flattens <paramref name="tree"/> into <paramref name="values"/> and
    /// <paramref name="derivedCourses"/>, path order preserved and each
    /// branch's own items lined up against <see cref="CourseForPath"/> of
    /// that branch's path. Generic over the Goo wrapper and its value so
    /// this harness's own reflection-only reach can drive it against a
    /// <c>GH_Structure&lt;GH_Integer&gt;</c> (a plain int, no native Rhino
    /// core, the same ground <c>Point3d</c> already stands on for
    /// <c>SnapSampledLineToNodes</c>) and prove the walk itself -- not
    /// only <see cref="CourseForPath"/> in isolation -- can fail; this
    /// component always calls it with <c>GH_Structure&lt;GH_Curve&gt;</c>,
    /// which needs the native core this harness deliberately never
    /// launches and so cannot drive directly with real curve values.
    /// </summary>
    private static void WalkCellTree<TGoo, TValue>(
        GH_Structure<TGoo> tree,
        List<TValue> values,
        List<int> derivedCourses)
        where TGoo : GH_Goo<TValue>
    {
        foreach (GH_Path branchPath in tree.Paths)
        {
            int course = CourseForPath(branchPath);
            foreach (TGoo? item in tree.get_Branch(branchPath))
            {
                if (item is null || item.Value is null)
                    continue;
                values.Add(item.Value);
                derivedCourses.Add(course);
            }
        }
    }

    /// <summary>
    /// Cells arrived as a tree of one or more branches, each already
    /// carrying, in <paramref name="derivedCourses"/>, the course every
    /// one of its cells belongs to (the branch path's last index; rule
    /// 10.2.1), which reproduces exactly what a hand-authored Courses
    /// list supplies today for Skin-sourced cells, since Skin already
    /// branches Cells by course. Pure and taking only the branch count
    /// and the two lists, so check 12.10(e) can drive it directly without
    /// a live IGH_DataAccess/GH_Structure, the same reach
    /// <see cref="HasNegativeCourse"/> above is held to.
    ///
    /// Courses SURVIVES on Export for the one case branch-path derivation
    /// cannot serve: an author wiring a FLAT list of hand-authored cells
    /// (one branch) with an explicit per-item course list, which passes
    /// through untouched. The two are mutually exclusive when Cells
    /// arrives as more than one branch, and the conflict is REFUSED, not
    /// resolved: guessing which the author meant is how a study silently
    /// loses its stages (rule 10.2.3). Returns the refusal message, or
    /// null having applied the derived courses (or having left a single
    /// branch's Courses alone).
    /// </summary>
    private static string? DeriveBranchCourses(
        int branchCount,
        IReadOnlyList<int> derivedCourses,
        List<int> courseInput)
    {
        if (branchCount > 1 && courseInput.Count > 0)
        {
            return
                "Cells arrived as more than one branch AND Courses is not " +
                "empty. The branch path IS the course when a tree is " +
                "wired, so wire one or the other: Skin's Cells straight " +
                "in, or a FLAT list of cells with your own Courses list.";
        }
        if (branchCount > 1)
        {
            courseInput.Clear();
            courseInput.AddRange(derivedCourses);
        }
        return null;
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
    /// Which cells this solve exports, and what to say about the ones it
    /// was not given. Pure, so the rule is measured without a mesh.
    ///
    /// Wired cells always win: they are what the author authored, and a
    /// default that could override them would make Skin's course bands
    /// disappear on a solve nobody touched. With none wired, the Result's
    /// own faces are a tessellation already, so Export builds it rather
    /// than write a set with a hole in it, and the sidecar is therefore
    /// present for every TNA Result.
    ///
    /// Courses without Cells is ignored, and said out loud: a course
    /// belongs to a cell, there are no authored cells for it to belong to,
    /// and the faces Export falls back on are all course 0.
    /// </summary>
    internal static CellSource ChooseCells(
        int wiredCells,
        int wiredCourses,
        int faceCount,
        out string? remark)
    {
        remark = null;
        if (wiredCells > 0)
            return CellSource.Wired;
        // Only where a default tessellation is actually coming: the
        // sentence describes the thing the courses were ignored in favour
        // of, and on a Result with no faces at all (an FD Result) that
        // thing is never built.
        if (wiredCourses > 0 && faceCount > 0)
        {
            remark =
                "Courses is wired with no Cells, so it was ignored: a " +
                "course belongs to a cell, and the tessellation Export " +
                "builds from the Result's own faces is one cell per face " +
                "at course 0.";
        }
        return faceCount > 0 ? CellSource.Faces : CellSource.None;
    }

    /// <summary>
    /// The word the sidecar's "pattern" key carries for a set of cells that
    /// came from this source. Pure, and separate from
    /// <see cref="ChooseCells"/>, so the decision and its consequence can
    /// both be driven without a mesh: an author's cells were authored and
    /// the Result's own faces were not, and the studio reads the difference
    /// to know whether a cutting pattern was ever chosen. The None case
    /// never reaches the sidecar, since no tessellation kind is built for
    /// it; it answers with the fallback's word rather than inventing a
    /// third.
    /// </summary>
    internal static string PatternFor(CellSource source) =>
        source == CellSource.Wired ? AuthoredPattern : FacesPattern;

    /// <summary>
    /// One Result's default tessellation and everything the component has
    /// to say about it, built once and read by both phases of the solve.
    /// </summary>
    private sealed record DefaultTessellation(
        ResultDto Result,
        int FaceCount,
        IReadOnlyList<TessellationCell> Cells,
        IReadOnlyList<string> Remarks,
        string? Note);

    /// <summary>
    /// The default tessellation for this Result, off the cache when the
    /// Result is the one it was built from. Reference equality, not the
    /// record's own: comparing two solved nets field by field costs more
    /// than rebuilding the mesh it was meant to save.
    /// </summary>
    private DefaultTessellation DefaultTessellationFor(ResultDto result)
    {
        if (_defaultTessellation is DefaultTessellation cached &&
            ReferenceEquals(cached.Result, result))
        {
            return cached;
        }
        DefaultTessellation built = BuildDefaultTessellation(result);
        _defaultTessellation = built;
        return built;
    }

    /// <summary>
    /// The Result's own faces as cutting cells: Skin's rule through Skin's
    /// own code, one closed polyline per face in face order, read back as
    /// plain corners and reduced to plan outlines at course 0.
    ///
    /// A Result whose form graph will not rebuild into a mesh is Skin's to
    /// report and not a reason to lose the whole export: it comes back as a
    /// note, with no faces and no cells, and the set goes out without a
    /// tessellation.
    /// </summary>
    private static DefaultTessellation BuildDefaultTessellation(
        ResultDto result)
    {
        Mesh mesh;
        try
        {
            mesh = DeconstructComponent.ThrustMesh(result);
        }
        catch (Exception meshError)
        {
            return new DefaultTessellation(
                result,
                0,
                Array.Empty<TessellationCell>(),
                Array.Empty<string>(),
                "The thrust mesh could not be rebuilt, so no tessellation " +
                "was built from the Result's own faces: " +
                meshError.GetBaseException().Message);
        }
        IReadOnlyList<PolylineCurve> outlines =
            SkinComponent.FacePolylines(mesh);
        var corners = new List<Point3d[]>(outlines.Count);
        foreach (PolylineCurve outline in outlines)
        {
            // Every face is represented, including one whose polyline will
            // not read back, so the skipped count stays the difference
            // between the faces the mesh has and the cells that came out.
            corners.Add(outline.TryGetPolyline(out Polyline polyline)
                ? polyline.ToArray()
                : Array.Empty<Point3d>());
        }
        IReadOnlyList<TessellationCell> cells =
            DefaultTessellationCells(corners, out int skipped);
        var remarks = new List<string>(2);
        if (cells.Count > 0)
        {
            remarks.Add(
                "Cells is unwired, so Export tessellated the Result's own " +
                $"{cells.Count} faces, one cell each at course 0. Wire " +
                "Skin's Cells (C), or cells of your own, to override " +
                "it.");
        }
        if (skipped > 0)
        {
            remarks.Add(
                $"{skipped} thrust-mesh faces with fewer than three plan " +
                "corners were skipped from the default tessellation.");
        }
        return new DefaultTessellation(
            result, mesh.Faces.Count, cells, remarks, null);
    }

    /// <summary>
    /// One cell per face, in face order, every one at course 0, and the
    /// count of the faces that gave none. A face that will not reduce to
    /// three distinct plan corners (one vertical in plan, or carrying a
    /// repeated vertex) is SKIPPED, never an error: an authored Cells port
    /// is the author saying what to cut and its faults are errors, while
    /// this tessellation was never asked for and must not cost another
    /// kind. The survivors renumber, so the studio's keys have no holes.
    ///
    /// Pure, and takes corners rather than curves, so the rule is measured
    /// in the smoke harness, which has RhinoCommon's structs but no native
    /// core to build a Curve or a Mesh with.
    /// </summary>
    internal static IReadOnlyList<TessellationCell> DefaultTessellationCells(
        IReadOnlyList<Point3d[]> faces,
        out int skipped)
    {
        var prepared = new List<TessellationCell>(faces.Count);
        foreach (Point3d[] face in faces)
        {
            IReadOnlyList<double[]>? outline = PlanOutline(face, out _);
            if (outline is not null)
                prepared.Add(new TessellationCell(0, outline));
        }
        skipped = faces.Count - prepared.Count;
        return prepared;
    }

    /// <summary>
    /// One cell's corners as the plan outline the sidecar carries: z
    /// dropped, consecutive near-duplicates dropped, and the closing repeat
    /// of a ring dropped because the studio closes every ring implicitly
    /// ((i + 1) % n). Null when fewer than three distinct plan corners
    /// survive, which is the one shape neither caller can write; whether
    /// that is an error or a skip is the caller's to decide.
    /// <paramref name="closedByRepeat"/> reports that the ring closed
    /// itself, which is how the wired path tells a genuinely open cell from
    /// a closed one.
    /// </summary>
    private static IReadOnlyList<double[]>? PlanOutline(
        IEnumerable<Point3d> corners,
        out bool closedByRepeat)
    {
        closedByRepeat = false;
        var outline = new List<double[]>();
        foreach (Point3d point in corners)
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
        if (outline.Count > 1)
        {
            double[] first = outline[0];
            double[] final = outline[outline.Count - 1];
            if (Math.Abs(first[0] - final[0]) < 1e-9 &&
                Math.Abs(first[1] - final[1]) < 1e-9)
            {
                outline.RemoveAt(outline.Count - 1);
                closedByRepeat = true;
            }
        }
        return outline.Count < 3 ? null : outline;
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
            IReadOnlyList<double[]>? outline =
                PlanOutline(polyline, out bool closedByRepeat);
            if (outline is null)
            {
                errors.Add(
                    $"Cell {i} has fewer than 3 distinct plan corners.");
                continue;
            }
            if (!closedByRepeat && !curve.IsClosed)
                openCells.Add(i);
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
    /// The study's identity, resolved once and read everywhere: trimmed, and
    /// the default where the author left the Name blank. It is the file name
    /// stem, the studio's route segment and the "study" key inside the frames
    /// sidecar, and those three must agree or the studio cannot key a received
    /// document to the set it belongs to.
    /// </summary>
    private static string StudyName(string name)
    {
        string trimmed = (name ?? string.Empty).Trim();
        return trimmed.Length == 0 ? DefaultName : trimmed;
    }

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
        string studyName,
        IReadOnlyList<TessellationCell>? cells,
        string? cellWarning,
        string tessellationPattern,
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
                        payloads.Add((
                            kind,
                            BuildTessellationJson(
                                cells!, unitFactor, tessellationPattern)));
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
                    case "frames":
                    {
                        // Caught on its own, the way the compas kind is. The
                        // sweep runs the animation engine over a Result the
                        // author may never have wired an Animate to, so a
                        // Result the engine cannot animate (no edges, say)
                        // must cost this kind and nothing else: the contract,
                        // the columns, the disk write and the outputs all
                        // stand, and the set simply lacks its animation.
                        try
                        {
                            payloads.Add((
                                kind, MouldFrames.Json(result, studyName)));
                        }
                        catch (OperationCanceledException)
                        {
                            throw;
                        }
                        catch (Exception framesError)
                        {
                            warnings.Add(
                                "frames: " +
                                framesError.GetBaseException().Message);
                        }
                        break;
                    }
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
        double unitFactor,
        string pattern)
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
            // AUTHORED only where somebody authored it. A sidecar built
            // from the Result's own faces because nobody wired a cell says
            // "faces", so the studio can tell a chosen cutting pattern from
            // the courtesy one and never reports a face fallback as a
            // decision.
            ["pattern"] = pattern,
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
