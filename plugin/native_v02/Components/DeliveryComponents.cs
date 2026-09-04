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

/// <summary>
/// Putting one document on disk WITHOUT a window in which it is neither the
/// old one nor the new one.
///
/// This exists because of a defect the studio measured and filed as R-005.
/// Export used to write every kind with <c>File.WriteAllText</c>, which
/// truncates the destination and then fills it. With Live on and Path aimed at
/// a folder the studio polls, every solve therefore opened a window, as wide as
/// the write took, in which a reader saw a file that was empty or half a
/// document. The frames sidecar is the widest window of all, being the largest
/// kind.
///
/// So the content goes to a temporary beside the destination, in the SAME
/// directory (the name is the destination's own with a suffix, which is what
/// makes that true by construction rather than by care), and only a completed
/// temporary is moved over the destination. A reader therefore sees the whole
/// old document or the whole new one.
///
/// One consequence, stated rather than hidden: the move needs to displace the
/// destination, so a reader holding the destination open without granting
/// delete sharing makes the WRITE fail instead of making the READ tear. That is
/// the trade this asks for. The old file stands whole, the failure is reported
/// by name on the component, and the next solve writes again.
/// </summary>
internal static class AtomicFile
{
    /// <summary>
    /// What an incomplete document is called while it is being written. It
    /// ends the name rather than replacing the extension, so an interrupted
    /// write leaves something nobody can mistake for a kind of the set.
    /// </summary>
    public const string TemporarySuffix = ".writing";

    /// <summary>
    /// The destination's own path with a fresh id and the suffix on the end,
    /// so the temporary is always in the destination's directory (a move
    /// across volumes is a copy, and a copy is not atomic) and two writers
    /// racing on one study never collide on one temporary.
    /// </summary>
    public static string TemporaryFor(string target) =>
        target + "." + Guid.NewGuid().ToString("N") + TemporarySuffix;

    /// <summary>
    /// Write, then move. The destination is never opened for writing at all,
    /// which is the whole point: there is no instant at which it is short.
    /// </summary>
    public static void Write(string target, string contents)
    {
        string temporary = TemporaryFor(target);
        try
        {
            File.WriteAllText(temporary, contents);
            File.Move(temporary, target, overwrite: true);
        }
        catch
        {
            // A failed write must not leave its scratch behind in the
            // author's own export folder. Swept on the way out, and the
            // sweep's own failure never replaces the real one.
            try
            {
                if (File.Exists(temporary))
                    File.Delete(temporary);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }

            throw;
        }
    }
}

/// <summary>
/// What one solve's disk write did: the files that landed, in order, and where
/// and why it stopped if it stopped.
/// </summary>
internal sealed record ExportSetWrite(
    IReadOnlyList<string> Written,
    string? FailedTarget,
    string? Error);

/// <summary>
/// Everything ONE build reads, captured on the solve thread and never read
/// from it again (design of 2026-09-04 section 3).
///
/// This is the whole of the marshalling discipline, in one place. The build
/// runs on the uploader's timer thread now, so a Grasshopper object, a
/// RhinoDoc or a live curve reaching it would be a read off the UI thread
/// from a thread that is not it: the Result is a deep CLONE, the cells are
/// already reduced to plain numbers by <c>PrepareTessellationCells</c>, and
/// the unit factor is resolved by <c>ResolveUnitFactor</c> before this record
/// is built. Nothing in here is live.
///
/// The one exception is the Result, which is REFERENCED here and deep cloned
/// by the build itself. That is safe for the same reason the reference is
/// worth keeping: a ResultDto is an immutable record, a new solve produces a
/// new one and schedules a new request carrying it, and this one therefore
/// still describes the solve that captured it. Cloning on the solve thread
/// instead would charge every frame of a drag for a serialisation the build
/// may never read.
///
/// <c>Worker</c> is the one dispatch a build makes, as a seam rather than a
/// call, so the thrust mesh can be driven against a host of somebody else's
/// choosing. <c>Lifetime</c> is the COMPONENT's token and never the
/// solution's (rule 3.4): a superseded build finishes on it and is
/// discarded, so no scrub, drag or re-solve can cancel a worker request and
/// take the worker down with it.
/// </summary>
internal sealed record ExportBuildInputs(
    ResultDto Result,
    string Study,
    IReadOnlyList<TessellationCell>? Cells,
    string? CellWarning,
    double UnitFactor,
    double Radius,
    Func<string, object, CancellationToken, Task<JsonElement>> Worker,
    CancellationToken Lifetime);

/// <summary>
/// One Export solve's eight inputs, gathered and validated on the solve
/// thread. Both phases read the same eight, and eight out parameters had
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
/// what comes out of it: every Result is a FORM document (the portable
/// contract, the study name and the thrust mesh the studio's FEA reads), a
/// Result with Cells wired is also a SKIN document, and a Result whose
/// Mould block carries columns is also a self-contained FORMWORK document,
/// the machine and its motion together. Write puts the set on disk as
/// <c>&lt;Name&gt;-&lt;kind&gt;.json</c>; Live pushes the same set to the
/// studio, debounced, off the UI thread.
///
/// A SOLVE BUILDS NOTHING (design of 2026-09-04 section 3, rule 3.1). It
/// reads its inputs, captures them, and pokes the debouncer; the set is
/// built when the canvas RESTS, or synchronously on the solve that sets
/// Write, and on nothing else. So a slider scrub costs no documents at all,
/// and J carries the set one solve after the rest that built it.
/// </summary>
public sealed class ExportComponent : NativeComponentBase
{
    /// <summary>
    /// The one worker command Export sends, named once so the dispatch seam
    /// and the check that drives it cannot drift apart.
    /// </summary>
    internal const string ThrustMeshCommand = "export.compas";

    private const string DefaultStudio = "http://127.0.0.1:8600";
    private const string DefaultName = "ananke-export";
    private const double DefaultColumnRadius = 0.05;

    // The one word the skin document's "pattern" key carries. Every cell in
    // it was wired by somebody, because the COURTESY per-face tessellation
    // is never built any more: the studio discards a "faces" stamp unread,
    // and absence and "faces" mean the same thing to their reader (their
    // R-010(g)), so building one was work nobody read.
    private const string AuthoredPattern = "authored";

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

    // Live is HELD when the file this component came out of was saved
    // against different ports. Grasshopper reattaches archived wires by
    // index, and the Courses port going means every wire after it slides
    // up one: an old Export's Column Radius wire now lands on Name, its
    // Studio wire on Live, and Live obeys whatever stands there before
    // the author has read the warning saying the wires moved. That is
    // exactly the hazard this hold exists for, and the removal of input 2
    // is the case it was written against. Held until Live is seen False
    // and then True again, which is a deliberate act. Read on the first
    // solve, not in the constructor, because the archive is read after the
    // object is built.
    //
    // Gated on the INPUT side only. The hold's whole cause is an archived
    // wire landing on an input this component then obeys, which an
    // output-side change cannot do: Export's own outputs went from six to
    // two on the surface rework with its nine inputs untouched, and holding
    // on that would have held Live on every definition in existence for a
    // change that cannot have moved a single input wire.
    private bool _liveHoldRead;
    private bool _liveHeld;

    // THE COMPONENT'S OWN LIFETIME, and the token every thrust-mesh request
    // runs on (rule 3.4). Grasshopper's solution cancellation used to reach
    // the worker through the task-capable base's CancelToken, and a cancelled
    // worker request is not a cancelled request: WorkerHost.cs:911-991 KILLS
    // the worker process and starts a fresh one behind a new handshake, so a
    // scrub over a canvas carrying an Export tore the worker down and built
    // it again, over and over. Nothing but this component leaving the
    // document cancels this, so a superseded build finishes and its result is
    // discarded instead.
    private readonly CancellationTokenSource _lifetime = new();

    public ExportComponent()
        : base(
            "Export",
            "Export",
            "Write the three documents a solved Result can be: the form " +
            "document always, the skin document when cells are wired, the " +
            "self-contained formwork document when the Result carries " +
            "columns, and push the set live to the studio.",
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
        EndLifetime();
        base.RemovedFromDocument(document);
    }

    /// <summary>
    /// The component has left the canvas, so the work it asked for is nobody's
    /// any more: the token every thrust-mesh request runs on is cancelled
    /// HERE and in no other place, which is the whole of rule 3.4's
    /// "cancelled only when the component is removed or the document closes".
    ///
    /// Its own method so the lifetime can be ended without a GH_Document,
    /// which is what lets the token's two states be measured at all.
    /// </summary>
    internal void EndLifetime()
    {
        try
        {
            _lifetime.Cancel();
        }
        catch (Exception)
        {
            // A throw here came out of somebody else's cancellation
            // callback, on a component that is already leaving.
        }
    }

    /// <summary>
    /// Whether the lifetime token has been cancelled, which is the only
    /// thing that can cancel a thrust-mesh request.
    /// </summary>
    internal bool LifetimeEnded => _lifetime.IsCancellationRequested;

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
            "Projected to plan (z dropped) into the skin document's " +
            "outline points; non-polyline curves are approximated at a 5 mm " +
            "chord. Wiring them is what adds the skin document to the " +
            "export. THE COURSE COMES FROM THE BRANCH PATH AND FROM " +
            "NOTHING ELSE: a flat list is one course, course 0, and one " +
            "studio stage.",
            GH_ParamAccess.tree);
        parameters[1].Optional = true;
        parameters.AddNumberParameter(
            "Column Radius",
            "R",
            "Radius the column members are drawn at, in document units " +
            "(0.05 suits metres; scale it for millimetres). The formwork " +
            "document declares it and the studio draws its animated " +
            "members as tubes at exactly this radius, so the machine and " +
            "the exported solids are one drawing.",
            GH_ParamAccess.item,
            DefaultColumnRadius);
        parameters[2].Optional = true;
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
        parameters[3].Optional = true;
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
        parameters[4].Optional = true;
        parameters.AddTextParameter(
            "Studio",
            "S",
            "The studio's base URL.",
            GH_ParamAccess.item,
            DefaultStudio);
        parameters[5].Optional = true;
        parameters.AddBooleanParameter(
            "Live",
            "L",
            "Push the set to the studio when the canvas RESTS: the build " +
            "and the send both wait half a second after the last solve, so " +
            "a slider scrub costs one build and one push at the end of it " +
            "rather than one of each a frame. Only the DOCUMENTS THAT " +
            "CHANGED go: a form move does not resend the animation, and a " +
            "set identical to the last one sent sends nothing at all " +
            "(change the Result, or toggle Live off and on). A 409 (the " +
            "studio has a run in flight for this study) is retried after " +
            "2, 4 and 8 seconds and then deferred. Failures are warnings; " +
            "the files and outputs stand. After a file whose ports moved " +
            "is opened, Live is held until it is set off and then on " +
            "again, so a wire that landed here by accident cannot push a " +
            "study on the first solve.",
            GH_ParamAccess.item,
            false);
        parameters[6].Optional = true;
        parameters.AddBooleanParameter(
            "Write",
            "W",
            "Push the export to disk: while True, every document this " +
            "Result carries is BUILT ON THIS SOLVE, synchronously, and " +
            "written under Path. A write is a deliberate act, so it does " +
            "not wait for the canvas to rest the way every other build " +
            "does. Wire a button for one-shot writes.",
            GH_ParamAccess.item,
            false);
        parameters[7].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddTextParameter(
            "JSON",
            "J",
            "Every JSON this Result can be, one item per document and in " +
            "the plan's order: the FORM document always, the SKIN document " +
            "whenever there are cells, and the FORMWORK document when the " +
            "Mould block carries columns, since the machine that moves is " +
            "the columns. A document that is absent, or that failed, is " +
            "simply not in the list, and every text names itself, so a " +
            "reader knows what each item is without counting slots: form " +
            "by its kind and schemaVersion, skin and formwork by their " +
            "schema. Every one of them also carries its own study name. " +
            "BUILT ON REST, not on every solve: the set is built half a " +
            "second after the last solve, or on the spot when Write is " +
            "True, so this carries the previous build until the new one " +
            "lands and a canvas that never rests that long carries " +
            "nothing. The form document here holds \"thrustMesh\": null " +
            "unless the mesh was built for a write or for a push, since " +
            "that string costs a worker round trip and no reader of this " +
            "port has ever wanted it.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Status",
            "ST",
            "What this solve did, one per line. written: <path> per file " +
            "of the most recent write, or written: nothing; then built: " +
            "how many documents the last build produced, or that none has " +
            "landed yet, since the set is built on rest; then live: " +
            "<kind>: <outcome> per document actually sent, or live: off " +
            "while Live is False, live: waiting for rest while the " +
            "debounce is running, live: building or live: sending while " +
            "the tick is doing one of those, and a live: held line when " +
            "the file's ports moved on load and Live is waiting to be set " +
            "off and on; then any warning this solve raised, in its own " +
            "words.",
            GH_ParamAccess.item);
    }

    /// <summary>
    /// A SOLVE BUILDS NOTHING (rule 3.1). It reads the eight inputs,
    /// captures everything a build would read, and pokes the debouncer;
    /// the documents themselves are built when the canvas rests, or on
    /// this thread when Write is True, and the outputs carry the last
    /// build that landed.
    /// </summary>
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
            // One Export is one study: it writes one set of
            // <name>-<kind>.json files and schedules one build. Slot 0 is
            // item access, so a Result tree with more than one item makes
            // every iteration after the first overwrite the files the last
            // one wrote and supersede the build it scheduled, and only the
            // last one survives. Said once, on the second iteration, so a
            // wide tree does not repeat itself down the whole chin.
            if (data.Iteration == 1)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Export handles one Result per component; the last " +
                    "one wins.");
            }

            if (!TryReadInputs(data, out ExportInputs? inputs))
                return;

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

            // The write target is resolved BEFORE anything is built, because
            // whether there is one is what decides whether this solve builds
            // at all: a write is deliberate and builds on the spot, and
            // everything else waits for rest.
            string? folder = null;
            if (inputs.Write && nameIsOneSegment &&
                !string.IsNullOrWhiteSpace(inputs.Path))
            {
                if (!TryResolveWriteFolder(
                        inputs.Path,
                        out string resolved,
                        out string refusal))
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "Export: " + refusal);
                }
                else
                {
                    folder = resolved;
                }
            }

            // The hold, latched on the first solve after the archive was
            // read and cleared by a solve that sees Live False.
            bool liveHeld = LiveHeldOnThisSolve(inputs.Live);
            bool live = inputs.Live && !liveHeld && nameIsOneSegment;
            bool write = folder is not null;

            LiveUploader uploader = EnsureUploader();
            if (!inputs.Live)
            {
                // Live off means nothing is sent, including a send already
                // sleeping between 409 retries, and the ledger of what the
                // studio holds is dropped so that turning Live back on
                // sends the same set again. The BUILD is not cancelled: the
                // J output is fed by it and is not Live's to switch off.
                uploader.Cancel();
            }

            var pending = new LiveUploader.Pending(
                inputs.Studio,
                name,
                live,
                write,
                BuildFor(new ExportBuildInputs(
                    // Captured here, on the solve thread, because the build
                    // runs on the uploader's timer thread and nothing off the
                    // UI thread may touch a Grasshopper object or a live
                    // Rhino document. The CELLS were reduced to plain numbers
                    // by TryReadInputs and the unit factor is read off the
                    // active document below, both of which have to happen
                    // here; the Result is only REFERENCED here and is deep
                    // cloned by the build itself, where the old pre-phase
                    // cloned it too, because a solve that never rests must
                    // not pay for a serialisation nobody reads.
                    inputs.Result,
                    name,
                    inputs.Cells,
                    inputs.CellWarning,
                    ResolveUnitFactor(),
                    inputs.Radius,
                    DispatchToWorker,
                    _lifetime.Token)));

            LiveUploader.Built? built;
            bool wroteThisSolve = false;
            if (write)
            {
                built = uploader.BuildNow(pending);
                if (built is not null)
                {
                    ExportSetWrite outcome =
                        WriteSet(folder!, name, built.Payloads);
                    if (outcome.Error is not null)
                    {
                        AddRuntimeMessage(
                            GH_RuntimeMessageLevel.Error,
                            "Export: failed to write " +
                            outcome.FailedTarget + ": " + outcome.Error);
                    }
                    // What THIS solve put on disk, even when that is
                    // nothing: a set failing on its first kind used to
                    // leave the previous solve's list standing under an
                    // Error saying the write had failed, which reads as
                    // files that are there and are not.
                    _lastWritten = outcome.Written;
                    wroteThisSolve = outcome.Written.Count > 0;
                }
            }
            else
            {
                uploader.Schedule(pending);
                built = uploader.LatestBuild;
            }

            if (built is not null && !string.IsNullOrEmpty(built.Warning))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Export: " + built.Warning);
            }
            if (built is not null && !string.IsNullOrEmpty(built.Note))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Remark, built.Note);
            }

            string uploaded;
            if (!inputs.Live)
            {
                uploaded = "off";
            }
            else if (liveHeld)
            {
                uploaded =
                    "held: ports changed on load; set Live off then on to " +
                    "resume";
            }
            else if (!nameIsOneSegment)
            {
                // Why nothing was sent this solve, where nothing was. Live
                // is on and the uploader still holds the LAST send's
                // outcome, so reporting that outcome would say "live:
                // stored" on a solve that sent nothing at all, one line
                // under a Warning saying nothing was sent.
                uploaded = "nothing sent this solve (name refused)";
            }
            else
            {
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
                // has landed is worth a Warning; a set still building or
                // still going carries the previous verdict and nothing to
                // say about this one.
                if (state.Failed && state.Phase == LiveUploader.Phase.Done)
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
            var payloads = new List<string>(
                built?.Payloads.Count ?? 0);
            if (built is not null)
            {
                foreach ((string _, string json) in built.Payloads)
                    payloads.Add(json);
            }

            // What this solve did, in lines. The written list is the
            // session's latest rather than this solve's, so a one-shot
            // Button write stays visible after the button releases; the
            // built line is the last build that landed, which on a canvas
            // that never rests is the previous one; the live lines are the
            // uploader's own, one per document sent; and the warnings are
            // repeated here because a bubble is not a value and the chin
            // holds one line.
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
            status.Add(built is null
                ? "built: " + LiveUploader.NothingBuiltYet
                : "built: " + built.Payloads.Count + " documents on rest");
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
                $"{payloads.Count} documents · live {FirstLine(uploaded)}" +
                (wroteThisSolve ? " written" : string.Empty);
        }
        catch (Exception error)
        {
            Message = "Failed";
            ReportException("Export failed", error);
        }
    }

    /// <summary>
    /// The build itself, as the uploader takes it: one delegate over inputs
    /// already captured, answering the one question the uploader asks back.
    /// </summary>
    private static Func<Func<string, bool>, Task<LiveUploader.Built>> BuildFor(
        ExportBuildInputs inputs) =>
        wantMesh => BuildDocumentsAsync(inputs, wantMesh);

    /// <summary>
    /// The one worker dispatch Export makes, and the only reason this
    /// component knows a worker exists.
    /// </summary>
    private static Task<JsonElement> DispatchToWorker(
        string command,
        object payload,
        CancellationToken token) =>
        WorkerRuntime.Host.RequestAsync<JsonElement>(
            command, payload, token);

    /// <summary>
    /// Whether Live is held on THIS solve, and the whole of the latch that
    /// decides it.
    ///
    /// Lifted out of <see cref="SolveInstance"/> so the hold can be
    /// measured without a live IGH_DataAccess: the harness reads a
    /// definition archived with the OLD port count into a fresh component
    /// and asks this the three questions an author asks it, which is the
    /// verification the design's section 2 requires for the removal of the
    /// Courses port.
    ///
    /// Read ONCE, on the first solve after the archive was read, because
    /// that is when <see cref="InputPortsMovedOnLoad"/> is known; cleared
    /// by a solve that sees Live False, because setting Live off is the
    /// deliberate act, and turning it back on then sends.
    /// </summary>
    internal bool LiveHeldOnThisSolve(bool live)
    {
        if (!_liveHoldRead)
        {
            _liveHoldRead = true;
            _liveHeld = InputPortsMovedOnLoad;
        }
        if (!live)
            _liveHeld = false;
        return _liveHeld;
    }

    /// <summary>
    /// What the live line says for one reading of the uploader. A set still
    /// waiting for rest, still building or still on the wire says WHICH of
    /// those it is rather than showing the PREVIOUS set's outcome as though
    /// it were this one's: against an unreachable studio a set takes half a
    /// minute a document, and a "stored" left standing for two minutes
    /// claims a send that never happened.
    /// </summary>
    private static string Display(LiveUploader.Snapshot state) =>
        state.Phase switch
        {
            LiveUploader.Phase.Pending => "waiting for rest",
            LiveUploader.Phase.Building => "building",
            LiveUploader.Phase.Sending => "sending",
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
    /// Read the eight inputs and validate the Result up front so the
    /// background task never has to report a runtime message itself. Cells
    /// are validated whenever they are wired, since wiring them is what
    /// asks for the skin document; a Column Radius that is not a
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
        bool liveInput = false;
        string studioInput = DefaultStudio;
        double radiusInput = DefaultColumnRadius;
        List<string> errors;
        if (!data.GetData(0, ref resultGoo) ||
            resultGoo?.Value is not ResultDto resultValue)
        {
            // Said in the chin as well as by the empty port: without it
            // the component sits red under the previous solve's "3
            // documents" as though that set were still standing.
            if (report)
                Message = "No Result";
            return false;
        }
        data.GetDataTree(1, out GH_Structure<GH_Curve> cellTree);
        data.GetData(2, ref radiusInput);
        data.GetData(3, ref nameInput);
        data.GetData(4, ref pathInput);
        data.GetData(5, ref studioInput);
        data.GetData(6, ref liveInput);
        data.GetData(7, ref writeInput);

        errors = new List<string>(resultValue.Validate());
        // THE COURSES ARE THE BRANCH PATHS AND NOTHING ELSE. The Courses
        // input is gone (design of 2026-09-04 section 2), and with it the
        // hand-authored escape hatch, deliberately: a course belongs to a
        // branch, Skin already branches its Cells by course, and the two
        // ways of saying it could disagree.
        var courseInput = new List<int>();
        WalkCellTree(cellTree, cellInput, courseInput);

        IReadOnlyList<TessellationCell>? cells = null;
        string? cellWarning = null;
        var notes = new List<string>();
        var remarks = new List<string>();
        if (writeInput && string.IsNullOrWhiteSpace(pathInput))
        {
            // A missing disk target is not a reason to lose the solve.
            // As an Error this returned before a single output was set,
            // so the JSON documents, Written, Uploaded and the live push
            // were all thrown away because nowhere had been named to put
            // a copy. Its sibling refusal, a Path that is not rooted, was
            // only ever a Warning.
            notes.Add("Write is on but Path is blank; nothing written.");
        }
        if (cellInput.Count > 0)
        {
            if (HasNegativeCourse(courseInput, out string negative))
            {
                // A negative course survives all the way to the studio's
                // "c-1p0"-style key, which tessellation.from_document
                // pins course >= 0 and refuses, late, remote, and
                // confusing. Catch it here instead, naming every
                // offending index and value, and write nothing. Reachable
                // still, with Courses gone: a branch path index can itself
                // be negative.
                errors.Add(
                    "Courses must be zero or greater; negative at " +
                    negative + ".");
            }
            else
            {
                cells = PrepareTessellationCells(
                    cellInput, courseInput, errors, out cellWarning);
                if (cellTree.Paths.Count <= 1)
                {
                    // Said as a Remark rather than a Warning: one course is
                    // a legitimate thing to export, and the author who
                    // flattened Skin's Cells by accident needs to be told
                    // what that cost rather than scolded for it.
                    remarks.Add(
                        "Cells arrived as ONE branch, so every cell is " +
                        "course 0 and the studio's build animation is a " +
                        "single stage. Wire Skin's Cells (C) as the tree " +
                        "it comes as, with no Flatten between, for one " +
                        "stage per course.");
                }
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
            radius);
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
    /// True when any course is negative, naming every offending index and
    /// value (not just the first) so the fix on the canvas is immediate.
    /// The courses are branch path indices now, and a Grasshopper path
    /// index may itself be negative, so this guards the bound the studio's
    /// import actually enforces.
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
    /// <summary>
    /// One study's whole set onto disk, one file a kind, EVERY one of them
    /// through <see cref="AtomicFile.Write"/>. Lifted out of the solve so the
    /// harness can drive the real loop on a fixture study rather than assert
    /// against a copy of it.
    ///
    /// A set that fails halfway still reports the files that did land: which
    /// kinds reached disk is exactly what the author needs to see when one of
    /// them could not.
    /// </summary>
    internal static ExportSetWrite WriteSet(
        string folder,
        string name,
        IReadOnlyList<(string Kind, string Json)> payloads)
    {
        var written = new List<string>(payloads.Count);
        string? failedTarget = null;
        try
        {
            Directory.CreateDirectory(folder);
            foreach ((string kind, string json) in payloads)
            {
                string target = Path.Combine(folder, $"{name}-{kind}.json");
                failedTarget = target;
                AtomicFile.Write(target, json);
                written.Add(target);
                failedTarget = null;
            }
        }
        catch (Exception writeException)
        {
            return new ExportSetWrite(
                written, failedTarget ?? folder, writeException.Message);
        }

        return new ExportSetWrite(written, null, null);
    }

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
    /// The three documents the Result can be, in ExportPlan's order, built
    /// ONCE, on whichever thread the rest schedule is running on. FORM is
    /// always asked for; SKIN joins it when cells were wired and FORMWORK
    /// when the Mould block carries at least one member.
    ///
    /// THE THRUST MESH IS BUILT ON DEMAND (rule 3.3). The form document is
    /// written first with no mesh at all, which costs one serialisation of a
    /// contract this build needs anyway, and <paramref name="wantMesh"/> is
    /// then asked about that document: only a write, or a push the studio
    /// has not already had, is worth a worker round trip. A refresh that
    /// only feeds the J output answers no, keeps "thrustMesh": null, and
    /// says so in one line, so an idle canvas never calls a worker.
    ///
    /// Each document's own warning joins the one warning the component
    /// reports, and a thrust mesh the worker could not produce is one of
    /// those warnings rather than the end of the whole export.
    /// </summary>
    internal static async Task<LiveUploader.Built> BuildDocumentsAsync(
        ExportBuildInputs inputs,
        Func<string, bool> wantMesh)
    {
        ArgumentNullException.ThrowIfNull(inputs);
        ArgumentNullException.ThrowIfNull(wantMesh);
        // THE SNAPSHOT, taken here rather than on the solve thread: the
        // clone is a full round trip through the Result's own serialiser and
        // a solve that only pokes the debouncer must not pay for it. This is
        // where the pre-phase took it too, inside the task rather than
        // before it.
        ResultDto result = CloneResult(inputs.Result);
        MouldColumnsDto? block = result.Mould?.Columns;
        bool hasColumns = block is not null && block.Members.Count > 0;
        bool hasCells = inputs.Cells is not null && inputs.Cells.Count > 0;
        string[] kinds = ExportPlan.Kinds(hasCells, hasColumns);
        var payloads = new List<(string Kind, string Json)>(kinds.Length);
        var warnings = new List<string>();
        string? note = null;

        // THE UNIT FACTOR IS DISCLOSED FOR THE WHOLE SET, not inside
        // one document, which is the whole-branch review's finding 16.
        // The disclosure used to live inside one kind, so a study with a
        // Mould block and no wired cells never reached it and wrote its
        // animation in millimetres with no message anywhere on the
        // component. Every document of the set is affected by the
        // document unit, one by converting and one by declaring, so the
        // disclosure belongs to the set. Disclosed the way
        // ImportPiecesComponent discloses its own factor: a silent
        // scale is the thing that makes a units mismatch hard to find
        // later.
        if (Math.Abs(inputs.UnitFactor - 1.0) > 1e-12)
        {
            warnings.Add(
                "Document is not in metres: the skin document is CONVERTED by a factor of " +
                inputs.UnitFactor.ToString(
                    "0.################",
                    System.Globalization.CultureInfo.InvariantCulture) +
                "; the formwork document declares that factor as lengthUnitToMetres and keeps the document's own coordinates.");
        }

        foreach (string kind in kinds)
        {
            switch (kind)
            {
                case ExportPlan.FormKind:
                {
                    // The contract's bytes, serialised ONCE and spliced
                    // twice: the mesh-less document is what the change key
                    // is read off, and the answered one is the same string
                    // with the mesh in it.
                    string contract = ContractJson.Serialize(result);
                    string json = FormDocument.JsonFromContract(
                        contract, inputs.Study, null);
                    if (!wantMesh(json))
                    {
                        // The one-line note the design asks for, said as a
                        // Remark rather than a Warning: a J-only refresh
                        // carrying no mesh is the intended cheap path and
                        // not a fault, but a reader of that document has to
                        // know why the key is null.
                        note =
                            "thrustMesh is null in the J output: the mesh " +
                            "is built for a write or for a push and not " +
                            "for a refresh, because it costs a worker " +
                            "round trip. Set Write, or Live, to build it.";
                        payloads.Add((kind, json));
                        break;
                    }
                    // The one document that needs the worker, and so
                    // the only one that can fail because something
                    // outside this component is down. The thrust mesh
                    // is caught on its own: a worker that will not
                    // start, a request that times out or a worker-side
                    // error must not cost the contract, the skin, the
                    // formwork, the disk write and the outputs too,
                    // none of which ever touch the worker. The form
                    // document is still written, with "thrustMesh":
                    // null, so the study still resolves and only the
                    // staged analysis is unavailable.
                    try
                    {
                        (string? mesh, string? warning) =
                            await BuildThrustMeshAsync(
                                    result, inputs.Worker, inputs.Lifetime)
                                .ConfigureAwait(false);
                        if (!string.IsNullOrEmpty(warning))
                            warnings.Add(warning!);
                        if (mesh is not null)
                        {
                            json = FormDocument.JsonFromContract(
                                contract, inputs.Study, mesh);
                        }
                    }
                    catch (Exception meshError)
                    {
                        // A CANCELLATION IS NOT RETHROWN HERE. The only
                        // token this can carry is the component's own
                        // lifetime, so a cancelled request means the
                        // component has left the canvas and there is
                        // nothing left to recompute for: the set is
                        // finished with the mesh it has, and the schedule
                        // that asked for it is gone with the component.
                        warnings.Add(
                            "thrustMesh: " +
                            meshError.GetBaseException().Message);
                    }
                    payloads.Add((kind, json));
                    break;
                }
                case ExportPlan.SkinKind:
                {
                    // Pure serialisation of cells already reduced to
                    // plain numbers on the solve thread; no worker, no
                    // geometry.
                    payloads.Add((
                        kind,
                        BuildSkinJson(
                            inputs.Cells!,
                            inputs.UnitFactor,
                            inputs.Study,
                            result.Equilibrium?.Vertices.Count ?? 0,
                            result.Equilibrium?.TopologyHash
                                ?? string.Empty)));
                    if (!string.IsNullOrEmpty(inputs.CellWarning))
                        warnings.Add(inputs.CellWarning!);
                    break;
                }
                case ExportPlan.FormworkKind:
                {
                    // Caught on its own, the way the thrust mesh is.
                    // The sweep runs the animation engine over a Result
                    // the author may never have wired an Animate to, so
                    // a Result the engine cannot animate (no edges,
                    // say), or one whose machine and motion disagree,
                    // must cost this document and nothing else: form,
                    // skin, the disk write and the outputs all stand,
                    // and the set simply lacks its formwork.
                    try
                    {
                        payloads.Add((
                            kind,
                            FormworkDocument.Json(
                                result,
                                inputs.Study,
                                inputs.UnitFactor,
                                inputs.Radius,
                                ForceUnitOf(result))));
                    }
                    catch (Exception formworkError)
                    {
                        warnings.Add(
                            "formwork: " +
                            formworkError.GetBaseException().Message);
                    }
                    break;
                }
                default:
                    throw new InvalidOperationException(
                        $"Export does not know the kind '{kind}'.");
            }
        }
        return new LiveUploader.Built(
            payloads,
            warnings.Count == 0 ? null : string.Join(" ", warnings),
            note);
    }

    /// <summary>
    /// The unit the Result's own forces are in, which the formwork
    /// document carries so the studio never has to assume newtons. Blank
    /// falls back to the contract's own default rather than to nothing.
    /// </summary>
    private static string ForceUnitOf(ResultDto result)
    {
        string unit = (result.Equilibrium?.ForceUnit ?? string.Empty).Trim();
        return unit.Length == 0 ? "kN" : unit;
    }

    /// <summary>
    /// The thrust mesh for the form document, and nothing else out of that
    /// response.
    ///
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
    /// snake_case fields, so the mesh is likely to come back null, and
    /// callers are warned.
    ///
    /// THE FORM DIAGRAM, THE FORCE DIAGRAM AND THE COMPAS VERSION ARE NOT
    /// READ. The compas document carried all four, and the studio's own
    /// measurement is that nothing in bench or studio parses any of it but
    /// the thrust mesh: their staging path hands its path to the FEA runner
    /// and stops there. So the string comes back verbatim and lands at
    /// <c>form["thrustMesh"]</c>, which is where their ananke_fea/mesh.py
    /// json_loads it.
    /// </summary>
    internal static async Task<(string? ThrustMesh, string? Warning)> BuildThrustMeshAsync(
        ResultDto result,
        Func<string, object, CancellationToken, Task<JsonElement>> worker,
        CancellationToken lifetime)
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
                "session, so the thrust mesh may be unavailable.";
        }

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["result"] = resultPayload
        };
        // THE TOKEN IS THE COMPONENT'S LIFETIME AND NEVER THE SOLUTION'S
        // (rule 3.4). WorkerHost registers a callback on whatever token it is
        // handed, and that callback KILLS the worker process and starts a
        // fresh one behind a new handshake (WorkerHost.cs:911-991), so a
        // token that a re-solve cancels is a worker torn down mid-scrub. A
        // superseded build is not cancelled at all: it finishes on this
        // token, and the schedule that asked for it discards what it
        // produced.
        JsonElement response = await worker(
                ThrustMeshCommand, payload, lifetime)
            .ConfigureAwait(false);
        return (OptionalString(response, "thrustMesh"), warning);
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

    /// <summary>
    /// SKIN, <c>&lt;study&gt;-skin.json</c>: the studio's
    /// bench.tessellation/1 shape, verbatim, an authored cut the server
    /// consumes through tessellation.from_document. Keys are
    /// c&lt;course&gt;p&lt;n&gt; with n counting within each course,
    /// matching the generated patterns' own naming so the staging plan and
    /// the Data panel read the same either way. Units are metres and the
    /// domain is the plan projection; both are the fixed contract, not
    /// options.
    ///
    /// Three things are added round it by the design of 2026-09-04. The
    /// "study" key, so the studio can key Live's follow-the-push on a field
    /// we stamp rather than a file name it parses. And the CHEAP PAIRING
    /// ANCHOR, "vertexCount" and the contract's "topologyHash": a
    /// declaration only, which the reader is free to ignore, but which
    /// lets a skin document written against one solve be recognised beside
    /// a form document from another (channel agreement R-008/4).
    ///
    /// The "pattern" key is always "authored" now, because every cell in
    /// here was wired by somebody: the courtesy per-face tessellation is
    /// never built, and its absence says exactly what its "faces" stamp
    /// used to say to their reader.
    /// </summary>
    private static string BuildSkinJson(
        IReadOnlyList<TessellationCell> cells,
        double unitFactor,
        string study,
        int vertexCount,
        string topologyHash)
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
            ["pattern"] = AuthoredPattern,
            ["study"] = study,
            ["vertexCount"] = vertexCount,
            ["topologyHash"] = topologyHash,
            ["cells"] = cellPayloads
        };
        // The shared wire options every other codec in this component
        // already uses (ContractJson.Serialize elsewhere): no field here is
        // ever null and every key is already a camelCase literal, so this
        // changes no byte today -- it only stops this one call site from
        // silently drifting from the rest of the plugin's JSON shape later.
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }
}
