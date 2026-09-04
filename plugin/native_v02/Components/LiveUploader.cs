#nullable enable

using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// The rest schedule for one Export component: when the set is BUILT, which
/// documents are sent, and what the component says about both. Everything
/// here happens off the UI thread.
///
/// THE DEBOUNCE MOVED IN FRONT OF THE BUILD (design of 2026-09-04 section 3,
/// the studio's Live ask 1 accepted in the REPLY). It used to sit between a
/// finished set and the wire, so a slider scrub built five kinds a frame and
/// threw all but the last away. Now a solve only says what it would build:
/// <see cref="Schedule"/> records the request and arms the same half-second
/// one-shot, every solve resets it, and the BUILD runs on the tick. A drag
/// therefore costs one build, at the end, and a canvas that never rests
/// costs none at all.
///
/// A write is the exception and is deliberate: <see cref="BuildNow"/> builds
/// on the caller's own thread, so a Button press puts the set on disk in the
/// solve that pressed it.
///
/// ONLY WHAT CHANGED IS SENT (rule 3.3). Each document carries its own change
/// key (<see cref="DocumentKey"/>), the uploader remembers the key it last
/// sent for each kind, and a send carries the documents whose keys moved and
/// no others. The same ledger answers the one question the build has to ask
/// before it pays for a thrust mesh: whether the form document is going
/// anywhere.
///
/// A 409 means the studio has a run in flight for that study; the send waits
/// and retries on a short schedule, then gives up for that document and says
/// so. Nothing here touches a Grasshopper object; the outcome lands in a
/// field and the owner is told through a callback it marshals to the UI
/// thread itself.
///
/// Three threads that are not the owner's run in here, the debounce timer's,
/// the build's and the send's, and none of them is allowed to throw where it
/// stands: an exception out of a timer callback or out of a discarded task is
/// not a failed upload, it is a dead Rhino. All three are fenced, and every
/// failure they can see becomes an outcome line instead.
/// </summary>
internal sealed class LiveUploader : IDisposable
{
    public const int DebounceMilliseconds = 500;

    /// <summary>
    /// The one kind whose change key is not its own bytes: the form
    /// document's thrust mesh churns per serialisation, so the key reads the
    /// contract half of it and counts the mesh's presence alone.
    /// </summary>
    public const string FormKind = ExportPlan.FormKind;

    /// <summary>
    /// What the owner shows before anything has been sent. Named here
    /// and interpolated into the Uploaded port's own description, so the
    /// port and the outcome cannot drift apart.
    /// </summary>
    public const string NothingSentYet = "nothing sent yet";

    /// <summary>What the owner shows before the first build has landed.</summary>
    public const string NothingBuiltYet =
        "nothing built yet; the set is built on rest";

    private static readonly HttpClient Client = new()
    {
        Timeout = TimeSpan.FromSeconds(30),
    };

    /// <summary>
    /// One build's whole product: the documents in the plan's order, the one
    /// warning line the build wants said, and the one remark it wants said
    /// (a form document built without its thrust mesh is the remark, not a
    /// fault). Plain strings, because this crosses two threads and a
    /// Grasshopper object may not.
    /// </summary>
    public sealed record Built(
        IReadOnlyList<(string Kind, string Json)> Payloads,
        string? Warning,
        string? Note);

    /// <summary>
    /// What a solve says it would build, and where it would go.
    ///
    /// <c>Build</c> is the whole of the work, captured at solve time by the
    /// component, and it takes ONE argument: given the form document's own
    /// key material, is the thrust mesh worth building? That is the uploader's
    /// question, because only the uploader knows what the studio already
    /// holds, and it is asked in the middle of the build because the answer
    /// decides whether a worker is called at all.
    ///
    /// It takes NO cancellation token, deliberately. The build's own token is
    /// the component's lifetime, captured in the closure (rule 3.4): a
    /// superseded build finishes and is discarded, and nothing here is
    /// allowed to cancel a worker request and take the worker down with it.
    /// </summary>
    public sealed record Pending(
        string Studio,
        string Name,
        bool Live,
        bool Write,
        Func<Func<string, bool>, Task<Built>> Build);

    /// <summary>
    /// Where the uploader stands, so the owner can say what is happening
    /// rather than showing the PREVIOUS set's outcome as though it were this
    /// one's. Against an unreachable studio a set takes 30 seconds a
    /// document, and a stale "stored" standing for two minutes is the
    /// component lying.
    /// </summary>
    public enum Phase
    {
        NeverSent,
        Pending,
        Building,
        Sending,
        Done,
    }

    /// <summary>
    /// Everything the owner reads about the last send, taken under ONE
    /// lock acquisition: reading the text and the verdict separately let a
    /// send land between them, so the component could print one set's
    /// failure with the other set's flag and suppress the Warning for a
    /// failure that was on screen.
    /// </summary>
    public readonly record struct Snapshot(
        Phase Phase,
        string Text,
        bool Failed);

    private readonly object _gate = new();
    private readonly Action _onOutcome;

    /// <summary>
    /// The wire itself, one PUT, substitutable so a check can drive the
    /// whole schedule without a studio listening. The shipped value is the
    /// shared <see cref="HttpClient"/>.
    /// </summary>
    private readonly Func<string, string, CancellationToken,
        Task<HttpResponseMessage>> _put;

    private Timer? _timer;
    private Pending? _pending;
    // The ledger: what the studio holds, by kind, and for which study and
    // studio. Cleared by Cancel, which is what makes Live off then on send
    // the same set again instead of calling it unchanged.
    private string? _sentName;
    private string? _sentStudio;
    private readonly Dictionary<string, string> _sentKeys =
        new(StringComparer.Ordinal);
    private Built? _built;
    private string? _builtKey;
    // What the last COMPLETED send said, kept apart from what the owner
    // shows: the skip text quotes it, and quoting the displayed text
    // instead would nest one skip line inside the next.
    private string _sentOutcome = NothingSentYet;
    private string _lastOutcome = NothingBuiltYet;
    private bool _lastOutcomeFailed;
    private bool _disposed;
    // HOW MANY BUILDS ARE RUNNING, counted rather than asserted. It was one
    // flag, set by whoever started a build and cleared by whichever build
    // finished, which is only sound while exactly one build can be in flight.
    // A write does not wait its turn (that is the whole of rule 3.2), so a
    // Write landing during a send used to clear the flag the SEND was
    // holding, and the ledger is not latched until the send's own tail: every
    // rest tick after that read all three documents as moved, found the wire
    // busy, re-armed the timer and built again, for as long as the send took.
    // Against an unreachable studio that is ninety seconds of full builds,
    // animation sweep and worker round trip included, on an idle canvas.
    // A build now releases only its own count, and the gate a build has to
    // pass is this count AND _sending, so a send still holds it.
    private int _buildsRunning;
    private bool _sending;
    private long _latestStarted;
    private Phase _phase = Phase.NeverSent;
    // Cancelled by Cancel and by Dispose, and replaced there so the
    // uploader stays usable: Live off then on again has to send.
    private CancellationTokenSource _cancel = new();
    // Bumped inside Cancel's lock and compared inside the send tail's,
    // which is the only way the two can be ordered against each other.
    // The token cannot do this job: Cancel has to cancel it AFTER
    // releasing the lock (cancelling Task.Delay can inline the send's
    // continuation onto this thread, and under the lock that deadlocks),
    // so a tail taking the gate in that window would read the token as
    // not cancelled and put the keys back that Cancel had just cleared.
    private long _cancelGeneration;

    public LiveUploader(
        Action onOutcome,
        Func<string, string, CancellationToken, Task<HttpResponseMessage>>?
            put = null)
    {
        _onOutcome = onOutcome;
        _put = put ?? DefaultPut;
    }

    private static async Task<HttpResponseMessage> DefaultPut(
        string route,
        string json,
        CancellationToken token)
    {
        using var content =
            new StringContent(json, Encoding.UTF8, "application/json");
        return await Client.PutAsync(route, content, token)
            .ConfigureAwait(false);
    }

    /// <summary>
    /// The phase, the outcome text, and whether that outcome names a
    /// refusal, a deferral or a transport failure, all read together.
    /// The verdict is recorded from the classified statuses as the lines
    /// are built, so the owner asks the uploader what happened instead of
    /// reading its prose back: rewording an outcome line must not be able
    /// to turn a Warning off.
    /// </summary>
    public Snapshot Current
    {
        get
        {
            lock (_gate)
                return new Snapshot(_phase, _lastOutcome, _lastOutcomeFailed);
        }
    }

    /// <summary>
    /// The documents the last ADOPTED build produced, which is what the J
    /// output carries. Null until the first build lands, which is why J is
    /// empty on the solve that first pokes the debouncer and full one solve
    /// later: the set is built on rest, and a canvas that never rests longer
    /// than the debounce carries no set at all.
    /// </summary>
    public Built? LatestBuild
    {
        get
        {
            lock (_gate)
                return _built;
        }
    }

    /// <summary>
    /// A disposed uploader accepts nothing more, so an owner that outlives
    /// one (a component deleted and then undone) can see it has to build
    /// another.
    /// </summary>
    public bool IsDisposed
    {
        get
        {
            lock (_gate)
                return _disposed;
        }
    }

    public static int? RetryDelay(int attempt) => attempt switch
    {
        0 => 2000,
        1 => 4000,
        2 => 8000,
        _ => null,
    };

    /// <summary>
    /// ONE ROUTE FOR ALL THREE DOCUMENTS, PUT
    /// <c>/api/uploads/exports/{study}/{kind}</c> (design of 2026-09-04
    /// section 1). The columns kind had a route of its own, a file name
    /// under <c>/api/uploads/columns/</c> rather than a study and a kind,
    /// and that special case dies with the kind: the formwork document goes
    /// where its siblings go, and the studio's upload route writes all
    /// three the same way.
    ///
    /// The study name is free text from the canvas and lands in a URL
    /// path segment, so it is escaped: a space, a <c>#</c> or a <c>?</c>
    /// left raw either breaks the URI or silently retargets the PUT, and
    /// the author sees only a 404 for a route nobody asked for.
    /// </summary>
    public static string RouteFor(string kind, string name, string studio)
    {
        string root = studio.Trim().TrimEnd('/');
        string segment = Uri.EscapeDataString(name);
        return $"{root}/api/uploads/exports/{segment}/{kind}";
    }

    public static string Outcome(int status, int attempt)
    {
        if (status >= 200 && status < 300)
            return "stored";
        if (status == 409)
            return RetryDelay(attempt) is null ? "deferred" : "retry";
        return "refused";
    }

    /// <summary>
    /// What a deferred kind adds to its line: the run the studio is busy
    /// with, read out of the documented 409 body <c>{"run": id}</c>, so
    /// the author can find that run in the studio rather than reading a
    /// pasted document. Tolerant by design: a body that is not that JSON,
    /// or that carries no run, falls back to the body itself, trimmed.
    /// </summary>
    public static string DeferredDetail(string body)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(body);
            if (document.RootElement.ValueKind == JsonValueKind.Object &&
                document.RootElement.TryGetProperty("run", out JsonElement run))
            {
                string id = run.ValueKind == JsonValueKind.String
                    ? run.GetString() ?? string.Empty
                    : run.GetRawText();
                if (!string.IsNullOrWhiteSpace(id))
                    return "(run " + id.Trim() + ")";
            }
        }
        catch (Exception)
        {
            // Any body at all is worth showing; no body is worth a thrown
            // send.
        }
        return Short(body);
    }

    /// <summary>
    /// What the owner shows when a build produced nothing the studio does
    /// not already hold. It quotes the outcome that still stands, because
    /// "stored" on its own reads as a fresh success for a set that never
    /// left the machine, and it names the two ways out.
    /// </summary>
    public static string UnchangedText(string previous) =>
        "unchanged since: " + previous +
        "; toggle Live or change the Result to send again";

    /// <summary>
    /// ONE DOCUMENT'S CHANGE KEY (rule 3.3). Live sends the documents whose
    /// key moved and no others, so a form move no longer resends the
    /// animation and a formwork change no longer resends the contract.
    ///
    /// Every kind but form keys on its own bytes. FORM keys on the CONTRACT
    /// half plus a flag for whether a thrust mesh is present, and both
    /// halves of that are load-bearing:
    ///
    /// The mesh's BYTES are left out. That string is the worker's
    /// <c>compas.data.json_dumps</c> of a freshly built Mesh, and json_dumps
    /// writes a fresh uuid4 per call, so two builds of an unchanged Result
    /// produce two different strings. A key that read them could never
    /// repeat: every outcome expires the component, the re-solve would
    /// enqueue a set that looked new, and the sending would go round for as
    /// long as Live was left on. That lesson is inherited from the compas
    /// kind, and the hazard moved with the string.
    ///
    /// The mesh's PRESENCE is read. A worker that will not start leaves
    /// <c>"thrustMesh": null</c> in the form document; the same Result
    /// recovered on the next build carries the real string. If the two keyed
    /// alike the recovered document would be reported unchanged and never
    /// sent, and the studio would keep a form document with no staged
    /// analysis until the Result itself changed.
    /// </summary>
    public static string DocumentKey(string kind, string json)
    {
        if (!string.Equals(kind, FormKind, StringComparison.Ordinal))
            return Hash(json);
        string material = FormDocument.KeyMaterial(json);
        return Hash(FormDocument.ContractHalf(material)) +
            (FormDocument.CarriesMesh(material) ? MeshMark : NoMeshMark);
    }

    /// <summary>What a form key says about the mesh, appended to its hash.</summary>
    public const string MeshMark = "+mesh";

    public const string NoMeshMark = "+none";

    private static string Hash(string text)
    {
        byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(text));
        return Convert.ToHexString(hash);
    }

    /// <summary>
    /// Take a build to run after the debounce. Every solve calls this,
    /// whatever Live says, because the J output is fed by the build and an
    /// author with Live off still gets his documents; only the SENDING is
    /// Live's to gate.
    ///
    /// The timer is one-shot and is replaced on every call, so a burst of
    /// solves inside the window is one build at the end of it and not one
    /// build each.
    /// </summary>
    public void Schedule(Pending pending)
    {
        lock (_gate)
        {
            if (_disposed)
                return;
            _pending = pending;
            _phase = Phase.Pending;
            _timer?.Dispose();
            _timer = new Timer(
                _ => Fire(), null, DebounceMilliseconds, Timeout.Infinite);
        }
    }

    /// <summary>
    /// Build NOW, on the caller's own thread, and hand back THIS REQUEST'S
    /// own product, or null when it produced none.
    ///
    /// This is the write path and nothing else: a write is a deliberate act,
    /// so it builds on the solve that asked for it rather than half a second
    /// after it (rule 3.2). It supersedes a build waiting out the debounce,
    /// and a build already running finishes and is discarded, exactly as a
    /// superseded one is.
    ///
    /// IT RETURNS ITS OWN BUILD AND NOT THE LAST ADOPTED ONE. Reading the
    /// adopted build back out of the field meant that a build which THREW
    /// (a failed clone, a failed serialisation) handed the caller the
    /// PREVIOUS solve's documents, which the write then put on disk under
    /// this solve's names and reported as written, with nothing anywhere
    /// saying so while Live was off. A silent stale write is the one thing
    /// the design singles out about Write.
    ///
    /// The send that follows, if Live is on and anything moved, is not
    /// synchronous: nothing waits on a studio while a solve is running.
    /// </summary>
    public Built? BuildNow(Pending pending)
    {
        long sequence;
        lock (_gate)
        {
            if (_disposed)
                return null;
            _pending = null;
            _timer?.Dispose();
            _timer = null;
            _phase = Phase.Building;
            sequence = ++_latestStarted;
            // A write does not wait for the wire to be free, so this may be
            // the second build in flight. It counts itself in and out again;
            // what it must not do is release a count somebody else took.
            _buildsRunning++;
        }
        return RunAsync(pending, sequence, awaitSend: false)
            .GetAwaiter()
            .GetResult();
    }

    /// <summary>
    /// Live went off, or the component is going away. A send in flight is
    /// cancelled through its token and the ledger is CLEARED, so turning Live
    /// back on sends the same set again instead of calling it unchanged.
    ///
    /// THE PENDING BUILD IS LEFT ALONE. It feeds the J output, which is not
    /// Live's to switch off, and the build never touches the studio.
    /// </summary>
    public void Cancel()
    {
        CancellationTokenSource? cancelling = null;
        lock (_gate)
        {
            // Whether there is anything to cancel is decided before the
            // ledger is dropped. With Live off the component calls this on
            // every solve, and a source per solve is an allocation and a
            // cancellation for nothing.
            //
            // THE LEDGER IS DROPPED TWICE OVER, and that is deliberate but
            // it is defence in depth rather than two mechanisms: clearing
            // the keys alone would do it, and forgetting the study alone
            // would do it too, since a null study name makes every document
            // read as belonging somewhere else. Measured: deleting either
            // line on its own leaves the whole harness green, and deleting
            // both reddens the Live-off-and-on assertion.
            _sentKeys.Clear();
            _sentName = null;
            _sentStudio = null;
            _cancelGeneration++;
            if (_sending)
            {
                cancelling = _cancel;
                _cancel = new CancellationTokenSource();
            }
        }
        if (cancelling is null)
            return;
        try
        {
            // Outside the lock: cancelling runs the callbacks HttpClient
            // and Task.Delay registered, and cancelling a Delay can run
            // the send's own continuation on this thread, which under the
            // lock would be a deadlock. The ledger is protected from a tail
            // arriving in this window by the generation, not by the
            // token. The source itself is not disposed, because a send in
            // flight is still holding it.
            cancelling.Cancel();
        }
        catch (Exception)
        {
            // A throw here came out of somebody else's cancellation
            // callback. It is not this component's to report.
        }
    }

    private void Fire()
    {
        bool started = false;
        try
        {
            Pending? set;
            long sequence;
            lock (_gate)
            {
                // A build already running is not interrupted; its own tail
                // re-arms the timer for whatever is pending by then, so the
                // newer request is built after the older one finishes and
                // the older one's product is discarded.
                //
                // A SEND HOLDS THIS GATE TOO, and holds it in its own name
                // rather than by borrowing the build count: no set is built
                // while documents are on the wire, because the ledger of what
                // the studio holds is not latched until that send's tail and
                // a build before it would read every document as moved. The
                // send's own tail re-arms the timer for whatever is pending
                // by then, so nothing is lost by waiting.
                if (_disposed || _buildsRunning > 0 || _sending)
                    return;
                set = _pending;
                if (set is null)
                    return;
                _pending = null;
                _buildsRunning++;
                started = true;
                _phase = Phase.Building;
                sequence = ++_latestStarted;
            }
            _ = Task.Run(() => RunAsync(set, sequence, awaitSend: true));
        }
        catch (Exception)
        {
            // A timer callback runs on a thread-pool thread, where an
            // escaping exception is not a failed build but a killed
            // process. What must not be dropped is the uploader's ability
            // to build the next set, so this build's own count goes back.
            if (!started)
                return;
            try
            {
                lock (_gate)
                    _buildsRunning--;
            }
            catch (Exception)
            {
            }
        }
    }

    /// <summary>
    /// One tick: build, decide what moved, send it. The build is the
    /// component's own closure and carries the component's own cancellation;
    /// the send carries the uploader's, because Live going off must stop a
    /// send and must not stop a build.
    ///
    /// IT RETURNS WHAT IT BUILT, not what has been adopted: the write path
    /// puts exactly this on disk, and a build that failed must hand back
    /// nothing rather than the last set that worked.
    /// </summary>
    private async Task<Built?> RunAsync(Pending set, long sequence, bool awaitSend)
    {
        Built? built = null;
        string? failure = null;
        bool released = false;
        try
        {
            built = await set.Build(material => WantMesh(set, material))
                .ConfigureAwait(false);
        }
        catch (Exception error)
        {
            failure = "build failed: " + error.GetBaseException().Message;
        }

        var moved = new List<(string Kind, string Json, string Key)>();
        bool announce = false;
        bool send = false;
        long generation = 0;
        CancellationToken token = CancellationToken.None;
        try
        {
            lock (_gate)
            {
                // THIS BUILD'S OWN COUNT, and nobody else's. A send that
                // starts below takes the gate in its own name (_sending), so
                // releasing here cannot open the gate under a send in
                // flight, which is what a shared flag did when a write built
                // while the wire was busy. That is also what makes the "a
                // send was already running" case below a corner rather than
                // the ordinary one, and it costs nothing: a build landing
                // during a send could not send anyway.
                _buildsRunning--;
                released = true;
                if (_disposed)
                    return built;
                // SUPERSEDED: a newer request arrived, or a newer build has
                // already started and landed. This one finished, and is
                // discarded rather than shown, because showing it would put
                // an older canvas state on the outputs.
                if (sequence != _latestStarted || _pending is not null)
                {
                    if (_pending is not null)
                    {
                        _phase = Phase.Pending;
                        _timer?.Dispose();
                        _timer = new Timer(
                            _ => Fire(),
                            null,
                            DebounceMilliseconds,
                            Timeout.Infinite);
                    }
                    return built;
                }
                if (failure is not null || built is null)
                {
                    _lastOutcome = failure ?? "build failed";
                    _lastOutcomeFailed = true;
                    _phase = Phase.Done;
                    announce = true;
                }
                else
                {
                    string key = BuildKey(built);
                    // The outputs are refreshed only when the built set is
                    // not the one already on them. Without that guard the
                    // refresh IS the next solve, the next solve schedules
                    // the next build, and Export would build for as long as
                    // the file was open.
                    announce = !string.Equals(
                        key, _builtKey, StringComparison.Ordinal);
                    _built = built;
                    _builtKey = key;
                    if (set.Live)
                        moved.AddRange(MovedLocked(set, built));
                    send = moved.Count > 0 && !_sending;
                    if (send)
                    {
                        // AND _sending HOLDS THE BUILD GATE, from here to the
                        // send's own tail: no build begins while documents
                        // are on the wire, because one send at a time is what
                        // keeps the ledger and the outcome text describing
                        // the same set. It is held in the send's own name so
                        // that a build finishing meanwhile cannot release it.
                        _sending = true;
                        _phase = Phase.Sending;
                        generation = _cancelGeneration;
                        token = _cancel.Token;
                    }
                    else if (moved.Count > 0)
                    {
                        // A send was already on the wire, which takes a WRITE
                        // landing inside one, since every other path waits at
                        // the gate the send holds. These documents are
                        // NOT dropped: the request goes back as pending and
                        // the next tick builds and sends it. Dropping them
                        // would leave the studio holding a set the canvas has
                        // moved past, with nothing anywhere saying so.
                        _pending = set;
                        _phase = Phase.Pending;
                        _timer?.Dispose();
                        _timer = new Timer(
                            _ => Fire(),
                            null,
                            DebounceMilliseconds,
                            Timeout.Infinite);
                    }
                    else
                    {
                        _phase = Phase.Done;
                        if (set.Live)
                            _lastOutcome = UnchangedText(_sentOutcome);
                    }
                }
            }
        }
        catch (Exception)
        {
            try
            {
                // Only if the release above had not already happened: the
                // count is this build's own and giving it back twice would
                // let two builds through the gate at once.
                if (!released)
                {
                    lock (_gate)
                        _buildsRunning--;
                }
            }
            catch (Exception)
            {
            }
            return built;
        }

        // The build first, because the outputs are the author's and the
        // studio's copy is the side effect: a set that changed reaches J
        // whether or not the send that follows it ever lands.
        if (announce)
            Announce();
        if (!send)
            return built;
        // The write path does not wait on a studio: the solve thread is in
        // here, and a set going to an unreachable server takes 30 seconds a
        // document.
        if (awaitSend)
        {
            await SendAsync(set, moved, sequence, generation, token)
                .ConfigureAwait(false);
            return built;
        }
        _ = Task.Run(() => SendAsync(set, moved, sequence, generation, token));
        return built;
    }

    /// <summary>
    /// Whether this build should pay for a thrust mesh, asked in the middle
    /// of the build with the mesh-less form document in hand.
    ///
    /// It is the DOCUMENT that comes in, not its key: the contract half is
    /// the same slice of either, since <see cref="FormDocument.KeyMaterial"/>
    /// rewrites only the trailing member, so the hash compared here is the
    /// hash the key carries.
    ///
    /// A WRITE always pays: the document is going on disk and a form
    /// document with no mesh is a study with no staged analysis. A build
    /// with Live off and no write never pays: the mesh would be produced for
    /// the J output alone, which is the one refresh that has to stay cheap.
    /// Under Live it pays when the studio does not already hold this exact
    /// contract, and when it holds it without a mesh, which is how a set
    /// built while the worker was down recovers on the next rest.
    /// </summary>
    private bool WantMesh(Pending set, string formJson)
    {
        if (set.Write)
            return true;
        if (!set.Live)
            return false;
        lock (_gate)
        {
            if (!string.Equals(_sentName, set.Name, StringComparison.Ordinal) ||
                !string.Equals(_sentStudio, set.Studio, StringComparison.Ordinal))
            {
                return true;
            }
            if (!_sentKeys.TryGetValue(FormKind, out string? sent))
                return true;
            string wanted =
                Hash(FormDocument.ContractHalf(formJson));
            if (!string.Equals(
                    ContractPart(sent), wanted, StringComparison.Ordinal))
            {
                return true;
            }
            return sent.EndsWith(NoMeshMark, StringComparison.Ordinal);
        }
    }

    /// <summary>
    /// The documents this build carries that the studio does not already
    /// hold, in the plan's order. A different study name or a different
    /// studio moves everything: the ledger describes ONE study on ONE
    /// server, and nothing there answers for another.
    /// </summary>
    private List<(string Kind, string Json, string Key)> MovedLocked(
        Pending set,
        Built built)
    {
        var moved = new List<(string, string, string)>(built.Payloads.Count);
        bool elsewhere =
            !string.Equals(_sentName, set.Name, StringComparison.Ordinal) ||
            !string.Equals(_sentStudio, set.Studio, StringComparison.Ordinal);
        foreach ((string kind, string json) in built.Payloads)
        {
            string key = DocumentKey(kind, json);
            if (elsewhere ||
                !_sentKeys.TryGetValue(kind, out string? sent) ||
                Moved(kind, sent, key))
            {
                moved.Add((kind, json, key));
            }
        }
        return moved;
    }

    /// <summary>
    /// Whether one document has moved since the key the studio was last sent
    /// it under.
    ///
    /// Every kind but form is its own bytes, so the comparison is the whole
    /// key. FORM is not, and the asymmetry is deliberate: its key carries the
    /// contract half and a mark saying whether a thrust mesh went with it, and
    /// a document that LOST its mesh is not a change to send. The build only
    /// asks the worker for a mesh when one is wanted (see
    /// <see cref="WantMesh"/>), so the ordinary Live tick over an unchanged
    /// Result produces a form document carrying "thrustMesh": null; sending
    /// that would overwrite the studio's good document with a mesh-less one,
    /// on every rest, and take the staged analysis away from a study nobody
    /// had touched.
    ///
    /// So form moves on its CONTRACT half, and on gaining a mesh it did not
    /// have. Losing one is not a move.
    /// </summary>
    private static bool Moved(string kind, string sent, string key)
    {
        if (!string.Equals(kind, FormKind, StringComparison.Ordinal))
            return !string.Equals(sent, key, StringComparison.Ordinal);
        if (!string.Equals(
                ContractPart(sent), ContractPart(key), StringComparison.Ordinal))
        {
            return true;
        }
        return sent.EndsWith(NoMeshMark, StringComparison.Ordinal) &&
            key.EndsWith(MeshMark, StringComparison.Ordinal);
    }

    /// <summary>The hash half of a form key, without its mesh mark.</summary>
    private static string ContractPart(string key)
    {
        if (key.EndsWith(MeshMark, StringComparison.Ordinal))
            return key[..^MeshMark.Length];
        if (key.EndsWith(NoMeshMark, StringComparison.Ordinal))
            return key[..^NoMeshMark.Length];
        return key;
    }

    /// <summary>
    /// One string standing for everything a build produced, which is what
    /// decides whether the outputs are worth refreshing.
    /// </summary>
    private static string BuildKey(Built built)
    {
        var builder = new StringBuilder();
        foreach ((string kind, string json) in built.Payloads)
        {
            builder.Append(kind).Append('\u001f')
                .Append(DocumentKey(kind, json)).Append('\u001e');
        }
        builder.Append(built.Warning ?? string.Empty).Append('\u001f')
            .Append(built.Note ?? string.Empty);
        return builder.ToString();
    }

    private async Task SendAsync(
        Pending set,
        IReadOnlyList<(string Kind, string Json, string Key)> moved,
        long sequence,
        long generation,
        CancellationToken token)
    {
        bool notify = false;
        try
        {
            var lines = new List<string>();
            var delivered = new List<(string Kind, string Key)>();
            // Recorded as the verdicts are classified, not read back out of
            // the lines afterwards: the owner turns a Warning on from this,
            // and a reworded outcome line must not be able to turn it off.
            bool anyFailed = false;
            bool cancelled = false;
            string? kindInFlight = null;
            try
            {
                foreach ((string kind, string json, string key) in moved)
                {
                    if (Stopped(token))
                    {
                        lines.Add(kind + ": cancelled");
                        cancelled = true;
                        break;
                    }
                    kindInFlight = kind;
                    string route = RouteFor(kind, set.Name, set.Studio);
                    string line = kind + ": ";
                    for (int attempt = 0; ; attempt++)
                    {
                        try
                        {
                            using HttpResponseMessage response =
                                await _put(route, json, token)
                                    .ConfigureAwait(false);
                            int status = (int)response.StatusCode;
                            string verdict = Outcome(status, attempt);
                            if (verdict == "retry")
                            {
                                await Task.Delay(RetryDelay(attempt)!.Value, token).ConfigureAwait(false);
                                continue;
                            }
                            string body = await response.Content
                                .ReadAsStringAsync(token).ConfigureAwait(false);
                            if (verdict != "stored")
                                anyFailed = true;
                            // Latched whatever the studio said, so a refused
                            // or an unreachable document does not re-open the
                            // expire loop on every solve.
                            delivered.Add((kind, key));
                            line += verdict switch
                            {
                                "stored" => "stored",
                                "deferred" => $"deferred, 409 after {attempt} retries {DeferredDetail(body)}",
                                _ => $"refused {status} {Short(body)}",
                            };
                        }
                        catch (OperationCanceledException)
                            when (token.IsCancellationRequested)
                        {
                            // Live went off, or the component left the
                            // canvas. Not a failure the author has to
                            // answer for, so it raises no Warning.
                            cancelled = true;
                            line += "cancelled";
                        }
                        catch (Exception error)
                        {
                            anyFailed = true;
                            line += "failed: " + error.GetBaseException().Message;
                        }
                        break;
                    }
                    lines.Add(line);
                    if (cancelled)
                        break;
                }
            }
            catch (Exception error)
            {
                // Everything the send itself can throw is caught per
                // payload above, so what lands here is the surrounding
                // work: building a route, walking the set. It becomes the
                // outcome for the kind that was in flight, or for the set
                // when it happened between kinds.
                anyFailed = true;
                lines.Add(
                    (kindInFlight is null ? string.Empty : kindInFlight + ": ") +
                    "failed: " + error.GetBaseException().Message);
            }

            lock (_gate)
            {
                // The build gate goes back HERE, having been held from the
                // build that started this send, so that no build could begin
                // while the documents were on the wire.
                _sending = false;
                if (!_disposed && sequence == _latestStarted)
                {
                    // Not latched across a Cancel: that cleared the ledger on
                    // purpose, and putting it back would leave the author
                    // toggling Live off and on and being told the set was
                    // unchanged. The generation is read under the same lock
                    // Cancel bumps it under, so there is no window; the token
                    // is not, and cannot do this job (see _cancelGeneration).
                    if (generation == _cancelGeneration)
                    {
                        _sentName = set.Name;
                        _sentStudio = set.Studio;
                        foreach ((string kind, string key) in delivered)
                            _sentKeys[kind] = key;
                    }
                    _sentOutcome = lines.Count == 0
                        ? "cancelled"
                        : string.Join(Environment.NewLine, lines);
                    _lastOutcome = _sentOutcome;
                    _lastOutcomeFailed = anyFailed;
                    _phase = Phase.Done;
                    notify = true;
                }
                if (!_disposed && _pending is not null)
                {
                    _phase = Phase.Pending;
                    _timer?.Dispose();
                    _timer = new Timer(_ => Fire(), null, DebounceMilliseconds, Timeout.Infinite);
                }
            }
        }
        catch (Exception)
        {
            // The recording itself failed, which leaves nothing to record
            // it in. This task is a discard, so a fault here is an
            // unobserved task exception: the outcome is lost in silence on
            // a default runtime and takes the process on one configured to
            // throw. The send's hold on the build gate goes back, so the next
            // set can still be built and still go. The build count is not
            // touched: this send's own build gave that back before the send
            // began, and taking one off here would be taking somebody else's.
            try
            {
                lock (_gate)
                    _sending = false;
            }
            catch (Exception)
            {
            }
        }
        if (notify)
            Announce();
    }

    /// <summary>
    /// The owner's callback, fired outside the lock and inside its own
    /// guard: it marshals onto Rhino's UI thread, which can throw while
    /// Rhino has no UI thread yet or is tearing one down, and a throw
    /// there must neither fault this task nor lose what was recorded.
    /// </summary>
    private void Announce()
    {
        try
        {
            _onOutcome();
        }
        catch (Exception)
        {
        }
    }

    /// <summary>
    /// Checked before every document, so a send already on its way stops at
    /// the next boundary instead of going on PUTting a deleted component's
    /// study for the rest of its retry schedule.
    /// </summary>
    private bool Stopped(CancellationToken token)
    {
        if (token.IsCancellationRequested)
            return true;
        lock (_gate)
            return _disposed;
    }

    private static string Short(string body)
    {
        string trimmed = body.Trim();
        return trimmed.Length <= 120 ? trimmed : trimmed[..120] + "...";
    }

    public void Dispose()
    {
        Cancel();
        lock (_gate)
        {
            _disposed = true;
            _timer?.Dispose();
            _timer = null;
            _pending = null;
        }
    }
}
