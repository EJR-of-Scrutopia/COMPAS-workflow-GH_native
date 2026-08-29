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
/// Pushes an export set to the studio, off the UI thread.
///
/// Debounced: a solve enqueues a set and the send waits half a second
/// after the LAST enqueue, so a slider scrub sends only the final state.
/// A 409 means the studio has a run in flight for that study; the send
/// waits and retries on a short schedule, then gives up for this set and
/// says so. A set identical to the last one sent is skipped, which is
/// what lets the component expire itself to show an outcome without
/// sending again (<see cref="SetKey"/> defines identical). Nothing here
/// touches a Grasshopper object; the outcome lands in a field and the
/// owner is told through a callback it marshals to the UI thread itself.
///
/// Two threads that are not the owner's run in here, the debounce timer's
/// and the send task's, and neither is allowed to throw where it stands:
/// an exception out of a timer callback or out of a discarded task is not
/// a failed upload, it is a dead Rhino. Both are fenced, and every failure
/// they can see becomes an outcome line instead.
/// </summary>
internal sealed class LiveUploader : IDisposable
{
    public const int DebounceMilliseconds = 500;

    /// <summary>
    /// The one kind whose bytes <see cref="SetKey"/> does not read.
    /// </summary>
    public const string CompasKind = "compas";

    /// <summary>
    /// What the owner shows before anything has been sent. Named here so
    /// the port description and the code cannot drift apart.
    /// </summary>
    public const string NothingSentYet = "nothing sent yet";

    private static readonly HttpClient Client = new()
    {
        Timeout = TimeSpan.FromSeconds(30),
    };

    public sealed record Pending(
        string Studio,
        string Name,
        IReadOnlyList<(string Kind, string Json)> Payloads);

    /// <summary>
    /// Where the uploader stands, so the owner can say "sending" while a
    /// set is waiting out the debounce or on the wire instead of showing
    /// the PREVIOUS set's outcome as though it were this one's. Against an
    /// unreachable studio a set takes 30 seconds a kind, and a stale
    /// "stored" standing for two minutes is the component lying.
    /// </summary>
    public enum Phase
    {
        NeverSent,
        Pending,
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
    private Timer? _timer;
    private Pending? _pending;
    private string? _lastSentKey;
    // What the last COMPLETED send said, kept apart from what the owner
    // shows: the skip text quotes it, and quoting the displayed text
    // instead would nest one skip line inside the next.
    private string _sentOutcome = NothingSentYet;
    private string _lastOutcome = NothingSentYet;
    private bool _lastOutcomeFailed;
    private bool _disposed;
    private bool _sending;
    private long _latestStarted;
    private Phase _phase = Phase.NeverSent;
    // Cancelled by Cancel and by Dispose, and replaced there so the
    // uploader stays usable: Live off then on again has to send.
    private CancellationTokenSource _cancel = new();

    public LiveUploader(Action onOutcome)
    {
        _onOutcome = onOutcome;
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
    /// The study name is free text from the canvas and lands in a URL
    /// path segment, so it is escaped: a space, a <c>#</c> or a <c>?</c>
    /// left raw either breaks the URI or silently retargets the PUT, and
    /// the author sees only a 404 for a route nobody asked for.
    /// </summary>
    public static string RouteFor(string kind, string name, string studio)
    {
        string root = studio.Trim().TrimEnd('/');
        string segment = Uri.EscapeDataString(name);
        return kind == "columns"
            ? $"{root}/api/uploads/columns/{segment}-columns.json"
            : $"{root}/api/uploads/exports/{segment}/{kind}";
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
    /// What the owner shows when a set was skipped for being the one
    /// already sent. It quotes the outcome that still stands, because
    /// "stored" on its own reads as a fresh success for a set that never
    /// left the machine, and it names the two ways out.
    /// </summary>
    public static string UnchangedText(string previous) =>
        "unchanged since: " + previous +
        "; toggle Live or change the Result to send again";

    /// <summary>
    /// What "the same set as the last one sent" means: the study name,
    /// the studio it is going to, and every kind in the set, by name and
    /// by content.
    ///
    /// Except the compas kind's content. That document is the worker's
    /// <c>compas.data.json_dumps</c> of freshly built Mesh and Graph
    /// objects, and json_dumps writes each object's <c>guid</c>, a fresh
    /// uuid4 per call, so two solves of an unchanged Result produce two
    /// different compas strings. A key that read them could never repeat:
    /// every outcome would expire the component, the re-solve would
    /// enqueue a set that looked new, and the sending would go round for
    /// as long as Live was left on. The compas document is a pure
    /// function of the contract apart from those guids, so leaving its
    /// bytes out of the key loses nothing: a changed Result changes the
    /// contract kind, which IS read.
    ///
    /// Its PRESENCE still counts, so a set carrying a compas kind and a
    /// set without one (a worker failure dropped it) key differently, and
    /// the recovered set is sent rather than skipped.
    /// </summary>
    public static string SetKey(
        string name,
        string studio,
        IReadOnlyList<(string Kind, string Json)> set)
    {
        using var sha = SHA256.Create();
        var builder = new StringBuilder();
        builder.Append(name).Append('\u001f')
            .Append(studio).Append('\u001e');
        foreach ((string kind, string json) in set)
        {
            builder.Append(kind).Append('\u001f');
            if (kind != CompasKind)
                builder.Append(json);
            builder.Append('\u001e');
        }
        byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(builder.ToString()));
        return Convert.ToHexString(hash);
    }

    /// <summary>
    /// Take a set to send after the debounce, or recognise it as the one
    /// already sent and say so on the spot.
    ///
    /// The skip is decided HERE and not after the debounce because the
    /// owner reads the state in the same solve that enqueues: a set
    /// parked as pending would show as "sending" for a send that is never
    /// going to happen, and every outcome expires the component, so the
    /// solve after a send would enqueue the same set, read "sending"
    /// again, and go round for as long as Live was left on.
    /// </summary>
    public void Enqueue(Pending set)
    {
        // Hashed outside the lock: the caller's own thread pays for it,
        // and a send finishing meanwhile only means the comparison below
        // reads a fresher key.
        string key = SetKey(set.Name, set.Studio, set.Payloads);
        lock (_gate)
        {
            if (_disposed)
                return;
            if (key == _lastSentKey)
            {
                _pending = null;
                _timer?.Dispose();
                _timer = null;
                _lastOutcome = UnchangedText(_sentOutcome);
                _phase = Phase.Done;
                return;
            }
            _pending = set;
            _phase = Phase.Pending;
            _timer?.Dispose();
            _timer = new Timer(_ => Fire(), null, DebounceMilliseconds, Timeout.Infinite);
        }
    }

    /// <summary>
    /// Live went off, or the component is going away. The pending set is
    /// dropped, a send in flight is cancelled through its token, and the
    /// last-sent key is CLEARED so that turning Live back on sends the
    /// same set again instead of calling it unchanged. Nothing is
    /// disposed: the uploader takes a fresh token source and waits for the
    /// next enqueue.
    /// </summary>
    public void Cancel()
    {
        CancellationTokenSource cancelling;
        lock (_gate)
        {
            _pending = null;
            _timer?.Dispose();
            _timer = null;
            _lastSentKey = null;
            cancelling = _cancel;
            _cancel = new CancellationTokenSource();
        }
        try
        {
            // Outside the lock: cancelling runs the callbacks HttpClient
            // and Task.Delay registered, and none of that is work to do
            // while a solve thread is waiting to read an outcome. The
            // source itself is not disposed, because a send in flight is
            // still holding its token.
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
            string key;
            long sequence;
            CancellationToken token;
            lock (_gate)
            {
                if (_disposed || _sending)
                    return;
                set = _pending;
                if (set is null)
                    return;
                key = SetKey(set.Name, set.Studio, set.Payloads);
                _pending = null;
                if (key == _lastSentKey)
                {
                    // Enqueue has already turned away every set it could
                    // see was a repeat. This one became a repeat between
                    // the enqueue and now, which takes a send of the same
                    // set landing in that window, and that send announced
                    // its own outcome: the solve it asks for will read
                    // this and settle, so nothing is announced here.
                    _lastOutcome = UnchangedText(_sentOutcome);
                    _phase = Phase.Done;
                    return;
                }
                _sending = true;
                started = true;
                _phase = Phase.Sending;
                sequence = ++_latestStarted;
                token = _cancel.Token;
            }
            _ = Task.Run(() => SendAsync(set, key, sequence, token));
        }
        catch (Exception)
        {
            // A timer callback runs on a thread-pool thread, where an
            // escaping exception is not a failed send but a killed
            // process. The plausible thrower is the hash of a large set
            // running out of memory. That set is dropped; what must not
            // be dropped with it is the uploader's ability to send the
            // next one, so the single-flight flag goes back.
            if (!started)
                return;
            try
            {
                lock (_gate)
                    _sending = false;
            }
            catch (Exception)
            {
            }
        }
    }

    private async Task SendAsync(
        Pending set,
        string key,
        long sequence,
        CancellationToken token)
    {
        bool notify = false;
        try
        {
            var lines = new List<string>();
            // Recorded as the verdicts are classified, not read back out of
            // the lines afterwards: the owner turns a Warning on from this,
            // and a reworded outcome line must not be able to turn it off.
            bool anyFailed = false;
            bool cancelled = false;
            string? kindInFlight = null;
            try
            {
                foreach ((string kind, string json) in set.Payloads)
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
                            using var content = new StringContent(json, Encoding.UTF8, "application/json");
                            using HttpResponseMessage response =
                                await Client.PutAsync(route, content, token).ConfigureAwait(false);
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

            // Under single flight (_sending, held from Fire to here) a
            // second send cannot start while this one runs, so this
            // sequence is always the latest by the time the tail reads it
            // and the comparison cannot fail today. It stays as the thing
            // that would have to be revisited first if single flight ever
            // stopped holding.
            lock (_gate)
            {
                _sending = false;
                if (!_disposed && sequence == _latestStarted)
                {
                    // Latched whatever the studio said, so a refused or
                    // an unreachable set does not re-open the expire loop
                    // on every solve. A CANCELLED send did not complete,
                    // and Cancel has just cleared the key on purpose, so
                    // that one must not put it back.
                    if (!token.IsCancellationRequested)
                        _lastSentKey = key;
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
            // throw. The single-flight flag goes back so the next set can
            // still go.
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
    /// Checked before every kind, so a set already on its way stops at the
    /// next boundary instead of going on PUTting a deleted component's
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
