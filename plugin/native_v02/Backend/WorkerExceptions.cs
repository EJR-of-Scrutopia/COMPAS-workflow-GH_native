using System;
using System.Text.Json;

namespace Ananke.COMPAS.Native.Backend;

/// <summary>
/// Base exception for isolated-worker configuration, transport, and protocol failures.
/// </summary>
public class WorkerException : Exception
{
    /// <summary>Creates a worker exception.</summary>
    public WorkerException(string message)
        : base(message)
    {
    }

    /// <summary>Creates a worker exception with an inner exception.</summary>
    public WorkerException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

/// <summary>
/// Indicates that an installed <c>backend.json</c> is missing or invalid.
/// </summary>
public sealed class WorkerConfigurationException : WorkerException
{
    /// <summary>Creates a configuration exception.</summary>
    public WorkerConfigurationException(string message)
        : base(message)
    {
    }

    /// <summary>Creates a configuration exception with an inner exception.</summary>
    public WorkerConfigurationException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

/// <summary>
/// Indicates malformed, unsupported, or unexpectedly large protocol data.
/// </summary>
public sealed class WorkerProtocolException : WorkerException
{
    /// <summary>Creates a protocol exception.</summary>
    public WorkerProtocolException(string message)
        : base(message)
    {
    }

    /// <summary>Creates a protocol exception with an inner exception.</summary>
    public WorkerProtocolException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

/// <summary>
/// Indicates that the external worker could not be started or exited unexpectedly.
/// </summary>
public sealed class WorkerProcessException : WorkerException
{
    /// <summary>Creates a process exception.</summary>
    public WorkerProcessException(string message)
        : base(message)
    {
    }

    /// <summary>Creates a process exception with an inner exception.</summary>
    public WorkerProcessException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

/// <summary>
/// Represents a structured terminal <c>error</c> envelope returned by the worker.
/// </summary>
public sealed class WorkerRemoteException : WorkerException
{
    /// <summary>Creates a remote exception from a structured worker error.</summary>
    public WorkerRemoteException(string code, string message, JsonElement details)
        : base(message)
    {
        Code = string.IsNullOrWhiteSpace(code) ? "worker_error" : code;
        Details = details.ValueKind == JsonValueKind.Undefined
            ? default
            : details.Clone();
    }

    /// <summary>Gets the stable machine-readable error code.</summary>
    public string Code { get; }

    /// <summary>Gets structured diagnostic details supplied by the worker.</summary>
    public JsonElement Details { get; }
}

/// <summary>
/// Represents a terminal <c>cancelled</c> envelope returned by the worker.
/// </summary>
public sealed class WorkerRequestCancelledException : OperationCanceledException
{
    /// <summary>Creates a worker cancellation exception.</summary>
    public WorkerRequestCancelledException(string requestId)
        : base($"Worker request {requestId} was cancelled.")
    {
        RequestId = requestId;
    }

    /// <summary>Gets the cancelled request identifier.</summary>
    public string RequestId { get; }
}
