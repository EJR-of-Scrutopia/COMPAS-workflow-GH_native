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
/// sending again. Nothing here touches a Grasshopper object; the
/// outcome lands in a field and the owner is told through a callback it
/// marshals to the UI thread itself.
/// </summary>
internal sealed class LiveUploader : IDisposable
{
    public const int DebounceMilliseconds = 500;

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
    private bool _disposed;

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

    public static string SetKey(IReadOnlyList<(string Kind, string Json)> payloads)
    {
        using var sha = SHA256.Create();
        var builder = new StringBuilder();
        foreach ((string kind, string json) in payloads)
        {
            builder.Append(kind).Append('\u001f').Append(json).Append('\u001e');
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
        lock (_gate)
        {
            set = _pending;
            _pending = null;
        }
        if (set is null)
            return;
        string key = SetKey(set.Payloads);
        lock (_gate)
        {
            if (key == _lastSentKey)
                return;
        }
        _ = Task.Run(() => SendAsync(set, key));
    }

    private async Task SendAsync(Pending set, string key)
    {
        var lines = new List<string>();
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
                    line += verdict switch
                    {
                        "stored" => "stored",
                        "deferred" => $"deferred, 409 after {attempt} retries {Short(body)}",
                        _ => $"refused {status} {Short(body)}",
                    };
                }
                catch (Exception error)
                {
                    line += "failed: " + error.GetBaseException().Message;
                }
                break;
            }
            lines.Add(line);
        }
        lock (_gate)
        {
            _lastSentKey = key;
            _lastOutcome = string.Join(Environment.NewLine, lines);
        }
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
