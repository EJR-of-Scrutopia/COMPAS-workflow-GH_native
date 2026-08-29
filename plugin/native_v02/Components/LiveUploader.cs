#nullable enable

using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
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
/// </summary>
internal sealed class LiveUploader : IDisposable
{
    public const int DebounceMilliseconds = 500;

    /// <summary>
    /// The one kind whose bytes <see cref="SetKey"/> does not read.
    /// </summary>
    public const string CompasKind = "compas";

    private static readonly HttpClient Client = new()
    {
        Timeout = TimeSpan.FromSeconds(30),
    };

    public sealed record Pending(
        string Studio,
        string Name,
        IReadOnlyList<(string Kind, string Json)> Payloads);

    private readonly object _gate = new();
    private readonly Action _onOutcome;
    private Timer? _timer;
    private Pending? _pending;
    private string? _lastSentKey;
    private string _lastOutcome = "idle";
    private bool _lastOutcomeFailed;
    private bool _disposed;
    private bool _sending;
    private long _latestStarted;

    public LiveUploader(Action onOutcome)
    {
        _onOutcome = onOutcome;
    }

    public string LastOutcome
    {
        get
        {
            lock (_gate)
                return _lastOutcome;
        }
    }

    /// <summary>
    /// Whether what <see cref="LastOutcome"/> carries names a refusal, a
    /// deferral or a transport failure. Recorded here from the
    /// classified verdicts as the lines are built, so the owner asks the
    /// uploader what happened instead of reading its prose back: rewording
    /// an outcome line must not be able to turn a Warning off.
    /// </summary>
    public bool LastOutcomeFailed
    {
        get
        {
            lock (_gate)
                return _lastOutcomeFailed;
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

    public static string RouteFor(string kind, string name, string studio)
    {
        string root = studio.Trim().TrimEnd('/');
        return kind == "columns"
            ? $"{root}/api/uploads/columns/{name}-columns.json"
            : $"{root}/api/uploads/exports/{name}/{kind}";
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

    public void Enqueue(Pending set)
    {
        lock (_gate)
        {
            if (_disposed)
                return;
            _pending = set;
            _timer?.Dispose();
            _timer = new Timer(_ => Fire(), null, DebounceMilliseconds, Timeout.Infinite);
        }
    }

    private void Fire()
    {
        Pending? set;
        string key;
        long sequence;
        lock (_gate)
        {
            if (_disposed || _sending)
                return;
            set = _pending;
            if (set is null)
                return;
            key = SetKey(set.Name, set.Studio, set.Payloads);
            if (key == _lastSentKey)
            {
                _pending = null;
                return;
            }
            _pending = null;
            _sending = true;
            sequence = ++_latestStarted;
        }
        _ = Task.Run(() => SendAsync(set, key, sequence));
    }

    private async Task SendAsync(Pending set, string key, long sequence)
    {
        var lines = new List<string>();
        // Recorded as the verdicts are classified, not read back out of the
        // lines afterwards: the owner turns a Warning on from this, and a
        // reworded outcome line must not be able to turn it off.
        bool anyFailed = false;
        foreach ((string kind, string json) in set.Payloads)
        {
            string route = RouteFor(kind, set.Name, set.Studio);
            string line = kind + ": ";
            for (int attempt = 0; ; attempt++)
            {
                try
                {
                    using var content = new StringContent(json, Encoding.UTF8, "application/json");
                    using HttpResponseMessage response =
                        await Client.PutAsync(route, content).ConfigureAwait(false);
                    int status = (int)response.StatusCode;
                    string verdict = Outcome(status, attempt);
                    if (verdict == "retry")
                    {
                        await Task.Delay(RetryDelay(attempt)!.Value).ConfigureAwait(false);
                        continue;
                    }
                    string body = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                    if (verdict != "stored")
                        anyFailed = true;
                    line += verdict switch
                    {
                        "stored" => "stored",
                        "deferred" => $"deferred, 409 after {attempt} retries {Short(body)}",
                        _ => $"refused {status} {Short(body)}",
                    };
                }
                catch (Exception error)
                {
                    anyFailed = true;
                    line += "failed: " + error.GetBaseException().Message;
                }
                break;
            }
            lines.Add(line);
        }

        // A slow send (retrying a 409) can still be running when a fresher
        // set finishes debouncing and starts its own send; _latestStarted
        // names the newest one, so a superseded send finishes its HTTP work
        // above but is not allowed to overwrite what the newer send wrote or
        // to announce an outcome nobody is waiting to see.
        bool notify = false;
        lock (_gate)
        {
            _sending = false;
            if (!_disposed && sequence == _latestStarted)
            {
                _lastSentKey = key;
                _lastOutcome = string.Join(Environment.NewLine, lines);
                _lastOutcomeFailed = anyFailed;
                notify = true;
            }
            if (!_disposed && _pending is not null)
            {
                _timer?.Dispose();
                _timer = new Timer(_ => Fire(), null, DebounceMilliseconds, Timeout.Infinite);
            }
        }
        if (notify)
            _onOutcome();
    }

    private static string Short(string body)
    {
        string trimmed = body.Trim();
        return trimmed.Length <= 120 ? trimmed : trimmed[..120] + "...";
    }

    public void Dispose()
    {
        lock (_gate)
        {
            _disposed = true;
            _timer?.Dispose();
            _timer = null;
            _pending = null;
        }
    }
}
