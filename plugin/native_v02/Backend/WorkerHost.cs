using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Ananke.COMPAS.Native.Backend;

/// <summary>
/// Owns a persistent, hidden COMPAS worker process and exchanges framed JSON requests.
/// </summary>
/// <remarks>
/// The host has no Rhino or Grasshopper dependencies and makes no UI calls.
/// It is safe to use from a task-capable Grasshopper component. The
/// worker is a single synchronous process that can only ever compute one
/// command at a time and cannot be told to abandon one mid-flight without
/// killing it, so request cancellation is fail-safe in a specific sense:
/// the CALLER is released immediately, but the worker itself is left
/// alone. An ordinary cancellation (a superseded drag tick; anything the
/// caller's own token requests) never kills the process - it just stops
/// waiting for an answer nobody needs any more, and the still-running
/// computation's eventual response is matched and discarded. Only a
/// genuine <see cref="WorkerConfiguration.RequestTimeoutMs"/> expiry -
/// the caller did NOT ask to abandon the request, the configured budget
/// simply elapsed - is treated as evidence the worker may actually be
/// stuck, and still recovers by killing and relaunching it. A
/// single-flight dispatch gate (<see cref="_dispatchGate"/>) means the
/// worker is only ever asked to do one thing at a time regardless: a
/// request still queued for its turn when its own token cancels never
/// reaches the worker at all.
/// </remarks>
public sealed class WorkerHost : IDisposable, IAsyncDisposable
{
    private const int RecentStderrCapacity = 200;

    private readonly WorkerConfiguration _configuration;
    private readonly JsonSerializerOptions _jsonOptions;
    private readonly ConcurrentDictionary<string, PendingRequest> _pending = new();
    private readonly ConcurrentQueue<string> _recentStderr = new();
    private readonly SemaphoreSlim _lifecycleGate = new(1, 1);
    private readonly SemaphoreSlim _writeGate = new(1, 1);

    // The worker's own serve loop (ananke_equilibrium.worker.serve) reads
    // one frame, dispatches it to completion, writes the response, THEN
    // reads the next frame: it is single-threaded and cannot compute two
    // commands at once. This gate makes that true on the C# side too, so
    // a cancelled-but-still-running request and a fresh one issued right
    // behind it are never both written to the pipe: the fresh one waits
    // its turn in memory, for free, and abandons instantly if IT is
    // superseded before its turn comes (see RequestWithRecoveryAsync).
    private readonly SemaphoreSlim _dispatchGate = new(1, 1);
    private readonly object _stateGate = new();

    private Process? _process;
    private CancellationTokenSource? _processLifetime;
    private Task? _stdoutTask;
    private Task? _stderrTask;
    private Task? _exitTask;
    private long _processGeneration;
    private bool _ready;
    private int _disposed;

    /// <summary>
    /// Creates a host for a validated worker configuration.
    /// </summary>
    /// <param name="configuration">The installed or explicitly loaded worker configuration.</param>
    /// <param name="jsonOptions">
    /// Optional finite-JSON serializer options. A private copy is made.
    /// </param>
    public WorkerHost(
        WorkerConfiguration configuration,
        JsonSerializerOptions? jsonOptions = null)
    {
        _configuration = configuration
            ?? throw new ArgumentNullException(nameof(configuration));
        _jsonOptions = jsonOptions is null
            ? CreateDefaultJsonOptions()
            : new JsonSerializerOptions(jsonOptions);
    }

    /// <summary>Raised when the worker emits a non-terminal progress event.</summary>
    public event EventHandler<WorkerEventEventArgs>? EventReceived;

    /// <summary>Gets the configuration used to launch the worker.</summary>
    public WorkerConfiguration Configuration => _configuration;

    /// <summary>Gets the most recent successful startup handshake.</summary>
    public WorkerHello? Hello { get; private set; }

    /// <summary>Gets whether a health-checked worker process is currently running.</summary>
    public bool IsRunning
    {
        get
        {
            lock (_stateGate)
                return _ready && IsAlive(_process);
        }
    }

    /// <summary>Gets a snapshot of recent diagnostic lines written to worker stderr.</summary>
    public IReadOnlyList<string> RecentStderr => _recentStderr.ToArray();

    /// <summary>
    /// The OS process id of the currently running worker, or null if none
    /// is running. Exists so a caller (a test, a diagnostic) can prove a
    /// process was NOT torn down and relaunched across some event -
    /// exactly what an ordinary cancellation must no longer do.
    /// </summary>
    public int? ProcessId
    {
        get
        {
            lock (_stateGate)
                return IsAlive(_process) ? _process!.Id : null;
        }
    }

    /// <summary>
    /// Creates a host by discovering the installed <c>backend.json</c>.
    /// </summary>
    /// <param name="configurationPath">Optional explicit configuration path.</param>
    /// <param name="pluginDirectory">Optional plug-in installation directory.</param>
    /// <returns>An unstarted worker host.</returns>
    public static WorkerHost FromInstalledConfiguration(
        string? configurationPath = null,
        string? pluginDirectory = null)
    {
        return new WorkerHost(
            WorkerConfiguration.LoadInstalled(configurationPath, pluginDirectory));
    }

    /// <summary>
    /// Starts the persistent process and validates it with <c>system.hello</c>.
    /// Calling this method while the host is healthy is a no-op.
    /// </summary>
    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        await _lifecycleGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (IsRunning)
                return;

            await StopProcessLockedAsync(
                graceful: false,
                new WorkerProcessException("Replacing an unavailable worker process."))
                .ConfigureAwait(false);
            StartProcessLocked();

            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(
                    cancellationToken);
                timeout.CancelAfter(_configuration.StartupTimeoutMs);
                WorkerHello hello = await RequestWithoutRecoveryAsync<WorkerHello>(
                    WorkerProtocol.HelloCommand,
                    payload: null,
                    timeout.Token).ConfigureAwait(false);
                ValidateHello(hello);

                lock (_stateGate)
                {
                    Hello = hello;
                    _ready = true;
                }
            }
            catch (Exception error)
            {
                await StopProcessLockedAsync(
                    graceful: false,
                    new WorkerProcessException(
                        "The worker failed its startup handshake.",
                        error)).ConfigureAwait(false);

                if (error is OperationCanceledException
                    && !cancellationToken.IsCancellationRequested)
                {
                    throw new TimeoutException(
                        $"Worker startup exceeded {_configuration.StartupTimeoutMs} ms.",
                        error);
                }

                throw;
            }
        }
        finally
        {
            _lifecycleGate.Release();
        }
    }

    /// <summary>
    /// Requests a fresh <c>system.health</c> snapshot.
    /// </summary>
    /// <returns>Python, package, and worker-capability information.</returns>
    public async Task<WorkerHealth> HealthAsync(
        CancellationToken cancellationToken = default)
    {
        await StartAsync(cancellationToken).ConfigureAwait(false);
        return await RequestAsync<WorkerHealth>(
            WorkerProtocol.HealthCommand,
            payload: null,
            cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// Sends a command with a serializable payload and deserializes its terminal result.
    /// </summary>
    /// <typeparam name="TResponse">The finite-JSON response contract type.</typeparam>
    /// <param name="command">A command from the worker's allowlist.</param>
    /// <param name="payload">A serializable JSON object; null becomes an empty object.</param>
    /// <param name="cancellationToken">Cancels the request and triggers fail-safe recovery.</param>
    /// <returns>The deserialized terminal result.</returns>
    public async Task<TResponse> RequestAsync<TResponse>(
        string command,
        object? payload = null,
        CancellationToken cancellationToken = default)
    {
        await StartAsync(cancellationToken).ConfigureAwait(false);
        ThrowIfDisposed();

        using var requestCancellation =
            CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        requestCancellation.CancelAfter(_configuration.RequestTimeoutMs);

        try
        {
            return await RequestWithRecoveryAsync<TResponse>(
                command,
                payload,
                cancellationToken,
                requestCancellation.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException error)
            when (!cancellationToken.IsCancellationRequested
                && requestCancellation.IsCancellationRequested)
        {
            throw new TimeoutException(
                $"Worker command '{command}' exceeded "
                + $"{_configuration.RequestTimeoutMs} ms.",
                error);
        }
    }

    /// <summary>
    /// Sends a strongly typed command payload and deserializes its terminal result.
    /// </summary>
    /// <typeparam name="TRequest">The finite-JSON request contract type.</typeparam>
    /// <typeparam name="TResponse">The finite-JSON response contract type.</typeparam>
    /// <param name="command">A command from the worker's allowlist.</param>
    /// <param name="payload">The strongly typed request payload.</param>
    /// <param name="cancellationToken">Cancels the request and triggers fail-safe recovery.</param>
    /// <returns>The deserialized terminal result.</returns>
    public Task<TResponse> RequestAsync<TRequest, TResponse>(
        string command,
        TRequest payload,
        CancellationToken cancellationToken = default)
    {
        return RequestAsync<TResponse>(command, payload, cancellationToken);
    }

    /// <summary>
    /// Kills any current worker, starts a clean process, and repeats protocol negotiation.
    /// </summary>
    public async Task RestartAsync(CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        await _lifecycleGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await StopProcessLockedAsync(
                graceful: false,
                new WorkerProcessException("The worker was restarted."))
                .ConfigureAwait(false);
            StartProcessLocked();

            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(
                    cancellationToken);
                timeout.CancelAfter(_configuration.StartupTimeoutMs);
                WorkerHello hello = await RequestWithoutRecoveryAsync<WorkerHello>(
                    WorkerProtocol.HelloCommand,
                    payload: null,
                    timeout.Token).ConfigureAwait(false);
                ValidateHello(hello);
                lock (_stateGate)
                {
                    Hello = hello;
                    _ready = true;
                }
            }
            catch
            {
                await StopProcessLockedAsync(
                    graceful: false,
                    new WorkerProcessException(
                        "The replacement worker failed its startup handshake."))
                    .ConfigureAwait(false);
                throw;
            }
        }
        finally
        {
            _lifecycleGate.Release();
        }
    }

    /// <summary>
    /// Requests a graceful worker shutdown and kills the process if it does not exit in time.
    /// </summary>
    public async Task ShutdownAsync(CancellationToken cancellationToken = default)
    {
        if (Volatile.Read(ref _disposed) != 0)
            return;

        await _lifecycleGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await StopProcessLockedAsync(
                graceful: true,
                new WorkerProcessException("The worker was shut down."))
                .ConfigureAwait(false);
        }
        finally
        {
            _lifecycleGate.Release();
        }
    }

    /// <summary>Synchronously releases the external worker process.</summary>
    public void Dispose()
    {
        DisposeAsync().AsTask().GetAwaiter().GetResult();
    }

    /// <summary>Asynchronously releases the external worker process.</summary>
    public async ValueTask DisposeAsync()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
            return;

        await _lifecycleGate.WaitAsync().ConfigureAwait(false);
        try
        {
            await StopProcessLockedAsync(
                graceful: true,
                new ObjectDisposedException(nameof(WorkerHost)))
                .ConfigureAwait(false);
        }
        finally
        {
            _lifecycleGate.Release();
            _lifecycleGate.Dispose();
            _writeGate.Dispose();
        }
    }

    private static JsonSerializerOptions CreateDefaultJsonOptions()
    {
        return new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = false,
            MaxDepth = 128
        };
    }

    private async Task<TResponse> RequestWithRecoveryAsync<TResponse>(
        string command,
        object? payload,
        CancellationToken callerToken,
        CancellationToken operationToken)
    {
        // Waits for the single worker slot. A request that is superseded
        // before its turn comes is cancelled HERE, by the same token the
        // caller already carries, and never reaches the worker at all -
        // the cheapest possible "abandon its own work".
        await _dispatchGate.WaitAsync(operationToken).ConfigureAwait(false);
        bool releaseGate = true;
        try
        {
            string requestId = Guid.NewGuid().ToString("N");
            PendingRequest pending;
            CancellationTokenRegistration registration = default;
            await _lifecycleGate.WaitAsync(operationToken).ConfigureAwait(false);
            try
            {
                ThrowIfDisposed();
                lock (_stateGate)
                {
                    if (!IsAlive(_process))
                    {
                        throw new WorkerProcessException(
                            "The worker process is not available.");
                    }
                    pending = new PendingRequest(
                        requestId,
                        command,
                        _processGeneration)
                    {
                        HoldsDispatchGate = true
                    };
                    if (!_pending.TryAdd(requestId, pending))
                    {
                        throw new WorkerProtocolException(
                            $"Duplicate request id '{requestId}'.");
                    }

                    // The entry is live in _pending from here, so
                    // ConcurrentDictionary.TryRemove's exactly-once
                    // semantics now own releasing the gate (whichever of
                    // RouteInboundEnvelope, the write-failure catch below,
                    // or a FailPending sweep removes it first, and only
                    // that one): never this method's own finally again.
                    releaseGate = false;
                }

                // Cancellation releases the CALLER immediately and never
                // the worker. The pending entry is left in place so the
                // real response, whenever the worker gets to it, is still
                // matched and quietly discarded (RouteInboundEnvelope),
                // and the dispatch gate is released only there - not by
                // this callback - because the worker is still busy on it
                // regardless of who stopped waiting. The one exception is
                // a genuine RequestTimeoutMs expiry: the caller's OWN
                // token did not fire, so nothing asked to abandon this,
                // and a request that has run that long unanswered is
                // reasonably treated as a stuck worker rather than a
                // superseded one - that case alone still recovers by
                // killing and relaunching, exactly as before.
                registration = operationToken.Register(
                    static state =>
                    {
                        var context = (CancellationContext)state!;
                        if (!context.Host._pending.ContainsKey(context.Request.Id))
                            return;

                        context.Request.Completion.TrySetCanceled(context.Token);
                        if (!context.CallerToken.IsCancellationRequested)
                        {
                            _ = context.Host.RecoverCancelledRequestAsync(
                                context.Request.Id);
                        }
                    },
                    new CancellationContext(
                        this,
                        pending,
                        operationToken,
                        callerToken));

            }
            finally
            {
                _lifecycleGate.Release();
            }

            try
            {
                await WriteRequestAsync(
                    new WorkerRequestEnvelope(
                        requestId,
                        command,
                        payload,
                        _configuration.ProtocolVersion),
                    pending.Generation,
                    operationToken).ConfigureAwait(false);
            }
            catch (Exception error)
            {
                registration.Dispose();
                if (_pending.TryRemove(
                    requestId,
                    out PendingRequest? removed))
                {
                    removed.Completion.TrySetException(error);
                    ReleaseDispatchGateIfHeld(removed);
                }
                throw;
            }

            using (registration)
            {
                WorkerInboundEnvelope response =
                    await pending.Completion.Task.ConfigureAwait(false);
                return DeserializeTerminalResult<TResponse>(
                    response,
                    requestId,
                    command);
            }
        }
        finally
        {
            if (releaseGate)
                _dispatchGate.Release();
        }
    }

    private async Task<TResponse> RequestWithoutRecoveryAsync<TResponse>(
        string command,
        object? payload,
        CancellationToken cancellationToken)
    {
        string requestId = Guid.NewGuid().ToString("N");
        PendingRequest pending;
        lock (_stateGate)
        {
            if (!IsAlive(_process))
            {
                throw new WorkerProcessException(
                    "The worker process is not available.");
            }
            pending = new PendingRequest(
                requestId,
                command,
                _processGeneration);
            if (!_pending.TryAdd(requestId, pending))
            {
                throw new WorkerProtocolException(
                    $"Duplicate request id '{requestId}'.");
            }
        }

        try
        {
            await WriteRequestAsync(
                new WorkerRequestEnvelope(
                    requestId,
                    command,
                    payload,
                    _configuration.ProtocolVersion),
                pending.Generation,
                cancellationToken).ConfigureAwait(false);

            WorkerInboundEnvelope response =
                await pending.Completion.Task
                    .WaitAsync(cancellationToken)
                    .ConfigureAwait(false);
            return DeserializeTerminalResult<TResponse>(
                response,
                requestId,
                command);
        }
        catch
        {
            _pending.TryRemove(requestId, out _);
            throw;
        }
    }

    private async Task WriteRequestAsync(
        WorkerRequestEnvelope request,
        long expectedGeneration,
        CancellationToken cancellationToken)
    {
        await _writeGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            Stream stream;
            lock (_stateGate)
            {
                if (!IsAlive(_process))
                {
                    throw new WorkerProcessException(
                        "The worker process is not available.");
                }
                if (_processGeneration != expectedGeneration)
                {
                    throw new WorkerProcessException(
                        $"Worker generation changed before command "
                        + $"'{request.Command}' could be sent.");
                }

                stream = _process!.StandardInput.BaseStream;
            }

            // Once a frame starts, it must finish or the byte stream becomes
            // corrupt. Cancellation recovery kills the process after its grace
            // period, which also unblocks a failed pipe write.
            await WorkerFrameCodec.WriteAsync(
                stream,
                request,
                _jsonOptions,
                _configuration.MaxFrameBytes,
                CancellationToken.None).ConfigureAwait(false);
        }
        catch (WorkerException)
        {
            throw;
        }
        catch (Exception error)
        {
            throw new WorkerProcessException(
                $"Could not send worker command '{request.Command}'.",
                error);
        }
        finally
        {
            _writeGate.Release();
        }
    }

    private TResponse DeserializeTerminalResult<TResponse>(
        WorkerInboundEnvelope response,
        string requestId,
        string command)
    {
        switch (response.Type)
        {
            case "result":
                if (response.Result.ValueKind == JsonValueKind.Undefined)
                {
                    throw new WorkerProtocolException(
                        $"Worker result for '{command}' has no 'result' value.");
                }

                if (typeof(TResponse) == typeof(JsonElement))
                    return (TResponse)(object)response.Result.Clone();

                try
                {
                    TResponse? value =
                        response.Result.Deserialize<TResponse>(_jsonOptions);
                    if (value is null)
                    {
                        throw new WorkerProtocolException(
                            $"Worker result for '{command}' deserialized to null.");
                    }

                    return value;
                }
                catch (WorkerProtocolException)
                {
                    throw;
                }
                catch (Exception error) when (error is JsonException or NotSupportedException)
                {
                    throw new WorkerProtocolException(
                        $"Could not decode worker result for '{command}'.",
                        error);
                }

            case "error":
                WorkerErrorPayload remote = response.Error
                    ?? new WorkerErrorPayload
                    {
                        Code = "malformed_error",
                        Message = "The worker returned an error envelope without error data."
                    };
                throw new WorkerRemoteException(
                    remote.Code,
                    remote.Message,
                    remote.Details);

            case "cancelled":
                throw new WorkerRequestCancelledException(requestId);

            default:
                throw new WorkerProtocolException(
                    $"Unsupported terminal worker envelope type '{response.Type}'.");
        }
    }

    private void StartProcessLocked()
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = _configuration.Executable,
            WorkingDirectory = _configuration.WorkingDirectory!,
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };

        foreach (string argument in _configuration.Arguments)
            startInfo.ArgumentList.Add(argument);
        foreach (KeyValuePair<string, string> variable in _configuration.Environment)
            startInfo.Environment[variable.Key] = variable.Value;

        MergePythonPath(startInfo);
        if (!string.IsNullOrWhiteSpace(_configuration.EnvironmentName))
        {
            startInfo.Environment["ANANKE_COMPAS_ENVIRONMENT"] =
                _configuration.EnvironmentName;
        }

        var process = new Process
        {
            StartInfo = startInfo,
            EnableRaisingEvents = true
        };

        try
        {
            if (!process.Start())
                throw new WorkerProcessException("The worker process did not start.");
        }
        catch (WorkerException)
        {
            process.Dispose();
            throw;
        }
        catch (Exception error)
        {
            process.Dispose();
            throw new WorkerProcessException(
                $"Could not start worker executable '{_configuration.Executable}'.",
                error);
        }

        var lifetime = new CancellationTokenSource();
        long generation;
        lock (_stateGate)
        {
            _process = process;
            _processLifetime = lifetime;
            _processGeneration = checked(_processGeneration + 1);
            generation = _processGeneration;
            _ready = false;
            Hello = null;
        }

        _stdoutTask = ReadStdoutAsync(
            process,
            generation,
            lifetime.Token);
        _stderrTask = ReadStderrAsync(process, lifetime.Token);
        _exitTask = MonitorExitAsync(process, generation);
    }

    private async Task StopProcessLockedAsync(
        bool graceful,
        Exception pendingFailure)
    {
        Process? process;
        CancellationTokenSource? lifetime;
        Task? stdoutTask;
        Task? stderrTask;
        Task? exitTask;
        long generation;

        lock (_stateGate)
        {
            process = _process;
            lifetime = _processLifetime;
            stdoutTask = _stdoutTask;
            stderrTask = _stderrTask;
            exitTask = _exitTask;
            generation = _processGeneration;
            _ready = false;
            Hello = null;
        }

        if (process is null)
        {
            FailAllPending(pendingFailure);
            return;
        }

        if (graceful && IsAlive(process))
        {
            try
            {
                using var timeout = new CancellationTokenSource(
                    _configuration.ShutdownTimeoutMs);
                _ = await RequestWithoutRecoveryAsync<JsonElement>(
                    WorkerProtocol.ShutdownCommand,
                    payload: null,
                    timeout.Token).ConfigureAwait(false);
            }
            catch (Exception error)
            {
                AppendStderr($"Graceful worker shutdown failed: {error.Message}");
            }
        }

        if (!graceful && IsAlive(process))
        {
            KillProcess(process);
        }
        else if (IsAlive(process))
        {
            try
            {
                using var timeout = new CancellationTokenSource(
                    _configuration.ShutdownTimeoutMs);
                await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                KillProcess(process);
            }
            catch (InvalidOperationException)
            {
                // The process exited between the liveness check and the wait.
            }
        }

        if (IsAlive(process))
            KillProcess(process);

        lifetime?.Cancel();
        FailPendingGeneration(generation, pendingFailure);

        await ObserveBackgroundTaskAsync(stdoutTask).ConfigureAwait(false);
        await ObserveBackgroundTaskAsync(stderrTask).ConfigureAwait(false);
        await ObserveBackgroundTaskAsync(exitTask).ConfigureAwait(false);

        lock (_stateGate)
        {
            if (ReferenceEquals(_process, process))
            {
                _process = null;
                _processLifetime = null;
                _stdoutTask = null;
                _stderrTask = null;
                _exitTask = null;
            }
        }

        lifetime?.Dispose();
        process.Dispose();
    }

    private async Task ReadStdoutAsync(
        Process process,
        long generation,
        CancellationToken cancellationToken)
    {
        try
        {
            Stream stream = process.StandardOutput.BaseStream;
            while (!cancellationToken.IsCancellationRequested)
            {
                byte[]? frame = await WorkerFrameCodec.ReadAsync(
                    stream,
                    _configuration.MaxFrameBytes,
                    cancellationToken).ConfigureAwait(false);
                if (frame is null)
                    return;

                WorkerInboundEnvelope? envelope;
                try
                {
                    envelope = JsonSerializer.Deserialize<WorkerInboundEnvelope>(
                        frame,
                        _jsonOptions);
                }
                catch (JsonException error)
                {
                    throw new WorkerProtocolException(
                        "The worker returned invalid JSON.",
                        error);
                }

                if (envelope is null)
                    throw new WorkerProtocolException("The worker returned an empty envelope.");
                RouteInboundEnvelope(envelope, generation);
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch (Exception error)
        {
            HandleTransportFailure(process, generation, error);
        }
    }

    private async Task ReadStderrAsync(
        Process process,
        CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                string? line = await process.StandardError
                    .ReadLineAsync(cancellationToken)
                    .ConfigureAwait(false);
                if (line is null)
                    return;
                AppendStderr(line);
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch (Exception error)
        {
            AppendStderr($"stderr reader failed: {error.Message}");
        }
    }

    private async Task MonitorExitAsync(Process process, long generation)
    {
        try
        {
            await process.WaitForExitAsync().ConfigureAwait(false);
            int exitCode = process.ExitCode;
            bool current;
            lock (_stateGate)
            {
                current =
                    ReferenceEquals(_process, process) &&
                    _processGeneration == generation;
                if (current)
                    _ready = false;
            }
            if (!current)
                return;

            FailPendingGeneration(
                generation,
                new WorkerProcessException(
                    $"The COMPAS worker exited with code {exitCode}. "
                    + FormatRecentStderr()));
        }
        catch (Exception error)
        {
            HandleTransportFailure(process, generation, error);
        }
    }

    private void RouteInboundEnvelope(
        WorkerInboundEnvelope envelope,
        long generation)
    {
        if (envelope.Version != _configuration.ProtocolVersion)
        {
            throw new WorkerProtocolException(
                $"Worker response uses protocol {envelope.Version}; "
                + $"expected {_configuration.ProtocolVersion}.");
        }
        if (string.IsNullOrWhiteSpace(envelope.Id))
            throw new WorkerProtocolException("Worker response has no request id.");

        if (string.Equals(envelope.Type, "event", StringComparison.Ordinal))
        {
            if (string.IsNullOrWhiteSpace(envelope.Event))
                throw new WorkerProtocolException("Worker event has no event name.");
            if (!_pending.TryGetValue(
                    envelope.Id,
                    out PendingRequest? eventRequest) ||
                eventRequest.Generation != generation)
            {
                return;
            }

            var eventArgs = new WorkerEventEventArgs(
                envelope.Id,
                envelope.Event,
                envelope.Payload);
            Delegate[] handlers = EventReceived?.GetInvocationList()
                ?? Array.Empty<Delegate>();
            foreach (Delegate handler in handlers)
            {
                try
                {
                    ((EventHandler<WorkerEventEventArgs>)handler).Invoke(
                        this,
                        eventArgs);
                }
                catch (Exception error)
                {
                    AppendStderr(
                        $"Worker event subscriber failed: {error.Message}");
                }
            }
            return;
        }

        if (envelope.Type is not ("result" or "error" or "cancelled"))
        {
            throw new WorkerProtocolException(
                $"Unknown worker envelope type '{envelope.Type}'.");
        }

        if (_pending.TryGetValue(
                envelope.Id,
                out PendingRequest? pending) &&
            pending.Generation == generation &&
            _pending.TryRemove(envelope.Id, out PendingRequest? removed))
        {
            removed.Completion.TrySetResult(envelope);
            ReleaseDispatchGateIfHeld(removed);
        }
    }

    private async Task RecoverCancelledRequestAsync(string requestId)
    {
        try
        {
            if (_configuration.CancellationGraceMs > 0)
            {
                await Task.Delay(_configuration.CancellationGraceMs)
                    .ConfigureAwait(false);
            }

            if (!_pending.TryGetValue(
                    requestId,
                    out PendingRequest? scheduled) ||
                Volatile.Read(ref _disposed) != 0)
            {
                return;
            }

            await _lifecycleGate.WaitAsync(CancellationToken.None)
                .ConfigureAwait(false);
            try
            {
                if (Volatile.Read(ref _disposed) != 0 ||
                    !_pending.TryGetValue(
                        requestId,
                        out PendingRequest? current) ||
                    current.Generation != scheduled.Generation)
                {
                    return;
                }
                lock (_stateGate)
                {
                    if (_processGeneration != scheduled.Generation)
                        return;
                }

                await StopProcessLockedAsync(
                    graceful: false,
                    new WorkerProcessException(
                        $"Worker request {requestId} was cancelled."))
                    .ConfigureAwait(false);
                StartProcessLocked();
                try
                {
                    using var timeout = new CancellationTokenSource(
                        _configuration.StartupTimeoutMs);
                    WorkerHello hello =
                        await RequestWithoutRecoveryAsync<WorkerHello>(
                            WorkerProtocol.HelloCommand,
                            payload: null,
                            timeout.Token)
                        .ConfigureAwait(false);
                    ValidateHello(hello);
                    lock (_stateGate)
                    {
                        Hello = hello;
                        _ready = true;
                    }
                }
                catch
                {
                    await StopProcessLockedAsync(
                        graceful: false,
                        new WorkerProcessException(
                            "The replacement worker failed its startup handshake."))
                        .ConfigureAwait(false);
                    throw;
                }
            }
            finally
            {
                _lifecycleGate.Release();
            }
        }
        catch (Exception error)
        {
            AppendStderr(
                $"Worker recovery after cancellation of {requestId} failed: "
                + error.Message);
        }
    }

    private void HandleTransportFailure(
        Process process,
        long generation,
        Exception error)
    {
        bool current;
        lock (_stateGate)
        {
            current =
                ReferenceEquals(_process, process) &&
                _processGeneration == generation;
            if (current)
                _ready = false;
        }
        if (!current)
            return;

        AppendStderr($"Worker transport failed: {error.Message}");
        FailPendingGeneration(
            generation,
            error as WorkerException
            ?? new WorkerProcessException("The worker transport failed.", error));
        KillProcess(process);
    }

    private void ValidateHello(WorkerHello hello)
    {
        if (hello.ProtocolVersion != _configuration.ProtocolVersion)
        {
            throw new WorkerProtocolException(
                $"Worker protocol {hello.ProtocolVersion} does not match "
                + $"configured protocol {_configuration.ProtocolVersion}.");
        }
        if (!string.Equals(
                hello.SchemaVersion,
                WorkerProtocol.CompatibleWorkerSchema,
                StringComparison.Ordinal))
        {
            throw new WorkerProtocolException(
                $"Worker schema '{hello.SchemaVersion}' does not match "
                + $"supported schema '{WorkerProtocol.CompatibleWorkerSchema}'.");
        }
        if (hello.MaxFrameBytes <= 0
            || hello.MaxFrameBytes > WorkerProtocol.MaximumFrameBytes)
        {
            throw new WorkerProtocolException(
                $"Worker advertised invalid frame limit {hello.MaxFrameBytes}.");
        }
        if (_configuration.MaxFrameBytes > hello.MaxFrameBytes)
        {
            throw new WorkerProtocolException(
                $"Configured frame limit {_configuration.MaxFrameBytes} exceeds "
                + $"the worker limit {hello.MaxFrameBytes}.");
        }
        if (!hello.Commands.Contains(
            WorkerProtocol.HealthCommand,
            StringComparer.Ordinal))
        {
            throw new WorkerProtocolException(
                $"Worker does not advertise required command '{WorkerProtocol.HealthCommand}'.");
        }
    }

    private void MergePythonPath(ProcessStartInfo startInfo)
    {
        var entries = new List<string>(_configuration.PythonPaths);
        if (startInfo.Environment.TryGetValue("PYTHONPATH", out string? existing)
            && !string.IsNullOrWhiteSpace(existing))
        {
            entries.AddRange(
                existing.Split(
                    Path.PathSeparator,
                    StringSplitOptions.RemoveEmptyEntries
                    | StringSplitOptions.TrimEntries));
        }

        if (entries.Count > 0)
        {
            startInfo.Environment["PYTHONPATH"] = string.Join(
                Path.PathSeparator,
                entries.Distinct(StringComparer.OrdinalIgnoreCase));
        }
    }

    private void FailAllPending(Exception error)
    {
        foreach (KeyValuePair<string, PendingRequest> pair in _pending)
        {
            if (_pending.TryRemove(pair.Key, out PendingRequest? pending))
            {
                pending.Completion.TrySetException(error);
                ReleaseDispatchGateIfHeld(pending);
            }
        }
    }

    private void FailPendingGeneration(long generation, Exception error)
    {
        foreach (KeyValuePair<string, PendingRequest> pair in _pending)
        {
            if (pair.Value.Generation == generation &&
                _pending.TryRemove(pair.Key, out PendingRequest? pending))
            {
                pending.Completion.TrySetException(error);
                ReleaseDispatchGateIfHeld(pending);
            }
        }
    }

    /// <summary>
    /// Releases the single-flight dispatch gate for a pending request that
    /// held it, exactly once, at the one moment its fate is actually known
    /// (a real response routed back, or a process failure/kill sweep). A
    /// cancelled CALLER never releases it directly (see
    /// RequestWithRecoveryAsync): the worker may still be computing the
    /// request regardless of who is still listening for the answer.
    /// </summary>
    private void ReleaseDispatchGateIfHeld(PendingRequest pending)
    {
        if (pending.HoldsDispatchGate)
            _dispatchGate.Release();
    }

    private void AppendStderr(string line)
    {
        _recentStderr.Enqueue(line);
        while (_recentStderr.Count > RecentStderrCapacity)
            _recentStderr.TryDequeue(out _);
    }

    private string FormatRecentStderr()
    {
        string[] lines = _recentStderr.TakeLast(8).ToArray();
        return lines.Length == 0
            ? "No worker stderr was captured."
            : "Recent stderr: " + string.Join(" | ", lines);
    }

    private static bool IsAlive(Process? process)
    {
        if (process is null)
            return false;

        try
        {
            return !process.HasExited;
        }
        catch (InvalidOperationException)
        {
            return false;
        }
    }

    private static void KillProcess(Process process)
    {
        try
        {
            if (!process.HasExited)
                process.Kill(entireProcessTree: true);
        }
        catch (InvalidOperationException)
        {
        }
        catch (System.ComponentModel.Win32Exception)
        {
        }
    }

    private static async Task ObserveBackgroundTaskAsync(Task? task)
    {
        if (task is null)
            return;
        try
        {
            await task.ConfigureAwait(false);
        }
        catch
        {
            // The transport failure has already been propagated to pending work.
        }
    }

    private void ThrowIfDisposed()
    {
        ObjectDisposedException.ThrowIf(
            Volatile.Read(ref _disposed) != 0,
            this);
    }

    private sealed class PendingRequest
    {
        internal PendingRequest(
            string id,
            string command,
            long generation)
        {
            Id = id;
            Command = command;
            Generation = generation;
            Completion = new TaskCompletionSource<WorkerInboundEnvelope>(
                TaskCreationOptions.RunContinuationsAsynchronously);
        }

        internal string Id { get; }

        internal string Command { get; }

        internal long Generation { get; }

        internal TaskCompletionSource<WorkerInboundEnvelope> Completion { get; }

        /// <summary>
        /// Whether this request holds the single-flight dispatch gate
        /// (<see cref="_dispatchGate"/>). Only requests dispatched through
        /// <see cref="RequestWithRecoveryAsync{TResponse}"/> ever do; the
        /// unrecovered startup/shutdown handshake
        /// (<see cref="RequestWithoutRecoveryAsync{TResponse}"/>) does not
        /// take a turn in that queue and must never release it.
        /// </summary>
        internal bool HoldsDispatchGate { get; init; }
    }

    private sealed class CancellationContext
    {
        internal CancellationContext(
            WorkerHost host,
            PendingRequest request,
            CancellationToken token,
            CancellationToken callerToken)
        {
            Host = host;
            Request = request;
            Token = token;
            CallerToken = callerToken;
        }

        internal WorkerHost Host { get; }

        internal PendingRequest Request { get; }

        internal CancellationToken Token { get; }

        /// <summary>
        /// The ORIGINAL token the caller passed to
        /// <see cref="RequestAsync{TResponse}"/>, distinct from
        /// <see cref="Token"/> (that token linked with the
        /// RequestTimeoutMs budget). Cancelled only by the caller
        /// abandoning the request; never fires on a bare timeout, which
        /// is exactly the distinction that decides whether a cancellation
        /// here is an ordinary supersede (leave the worker alone) or
        /// evidence of a genuinely stuck one (recover it).
        /// </summary>
        internal CancellationToken CallerToken { get; }
    }
}
