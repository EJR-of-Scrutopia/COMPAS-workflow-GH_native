using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace Ananke.COMPAS.Native.Backend;

/// <summary>
/// Constants shared by the native host and the isolated COMPAS worker.
/// </summary>
public static class WorkerProtocol
{
    /// <summary>The protocol version implemented by this assembly.</summary>
    public const int CurrentVersion = 1;

    /// <summary>
    /// The Python worker snapshot schema explicitly supported by native v0.2.
    /// </summary>
    public const string CompatibleWorkerSchema = "0.1";

    /// <summary>The absolute upper bound for a framed JSON message (32 MiB).</summary>
    public const int MaximumFrameBytes = 32 * 1024 * 1024;

    /// <summary>The protocol command used during startup negotiation.</summary>
    public const string HelloCommand = "system.hello";

    /// <summary>The protocol command used for a worker health check.</summary>
    public const string HealthCommand = "system.health";

    /// <summary>The protocol command used for a graceful worker shutdown.</summary>
    public const string ShutdownCommand = "system.shutdown";
}

/// <summary>
/// A versioned request sent from the native plug-in to the Python worker.
/// </summary>
public sealed class WorkerRequestEnvelope
{
    /// <summary>
    /// Creates a request envelope.
    /// </summary>
    /// <param name="id">A host-generated request identifier.</param>
    /// <param name="command">A command from the worker's fixed allowlist.</param>
    /// <param name="payload">A finite-JSON object; <see langword="null"/> becomes an empty object.</param>
    /// <param name="version">The protocol version.</param>
    public WorkerRequestEnvelope(
        string id,
        string command,
        object? payload = null,
        int version = WorkerProtocol.CurrentVersion)
    {
        if (string.IsNullOrWhiteSpace(id))
            throw new ArgumentException("A request id is required.", nameof(id));
        if (string.IsNullOrWhiteSpace(command))
            throw new ArgumentException("A worker command is required.", nameof(command));

        Version = version;
        Type = "request";
        Id = id;
        Command = command;
        Payload = payload ?? EmptyPayload.Value;
    }

    /// <summary>Gets the protocol version.</summary>
    [JsonPropertyName("v")]
    public int Version { get; }

    /// <summary>Gets the envelope type, which is always <c>request</c>.</summary>
    [JsonPropertyName("type")]
    public string Type { get; }

    /// <summary>Gets the request identifier.</summary>
    [JsonPropertyName("id")]
    public string Id { get; }

    /// <summary>Gets the worker command.</summary>
    [JsonPropertyName("command")]
    public string Command { get; }

    /// <summary>Gets the finite-JSON command payload.</summary>
    [JsonPropertyName("payload")]
    public object Payload { get; }

    private static class EmptyPayload
    {
        internal static readonly IReadOnlyDictionary<string, object?> Value =
            new Dictionary<string, object?>();
    }
}

/// <summary>
/// Structured error information returned by the worker.
/// </summary>
public sealed class WorkerErrorPayload
{
    /// <summary>Gets or sets the stable machine-readable error code.</summary>
    [JsonPropertyName("code")]
    public string Code { get; set; } = "worker_error";

    /// <summary>Gets or sets the human-readable error message.</summary>
    [JsonPropertyName("message")]
    public string Message { get; set; } = "The worker reported an error.";

    /// <summary>Gets or sets optional structured diagnostic details.</summary>
    [JsonPropertyName("details")]
    public JsonElement Details { get; set; }
}

/// <summary>
/// A decoded inbound worker envelope.
/// </summary>
/// <remarks>
/// Terminal envelope types are <c>result</c>, <c>error</c>, and
/// <c>cancelled</c>. An <c>event</c> envelope is non-terminal and does not
/// complete its associated request.
/// </remarks>
public sealed class WorkerInboundEnvelope
{
    /// <summary>Gets or sets the protocol version.</summary>
    [JsonPropertyName("v")]
    public int Version { get; set; }

    /// <summary>Gets or sets the envelope type.</summary>
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    /// <summary>Gets or sets the associated request identifier.</summary>
    [JsonPropertyName("id")]
    public string? Id { get; set; }

    /// <summary>Gets or sets the successful result payload.</summary>
    [JsonPropertyName("result")]
    public JsonElement Result { get; set; }

    /// <summary>Gets or sets structured worker error information.</summary>
    [JsonPropertyName("error")]
    public WorkerErrorPayload? Error { get; set; }

    /// <summary>Gets or sets the name of a non-terminal progress event.</summary>
    [JsonPropertyName("event")]
    public string? Event { get; set; }

    /// <summary>Gets or sets the payload of a non-terminal progress event.</summary>
    [JsonPropertyName("payload")]
    public JsonElement Payload { get; set; }
}

/// <summary>
/// Event data raised when the worker emits a non-terminal protocol event.
/// </summary>
public sealed class WorkerEventEventArgs : EventArgs
{
    /// <summary>Creates event data from a decoded protocol envelope.</summary>
    /// <param name="requestId">The request that produced the event.</param>
    /// <param name="eventName">The stable event name.</param>
    /// <param name="payload">The event's finite-JSON payload.</param>
    public WorkerEventEventArgs(string requestId, string eventName, JsonElement payload)
    {
        RequestId = requestId;
        EventName = eventName;
        Payload = payload.Clone();
    }

    /// <summary>Gets the request that produced the event.</summary>
    public string RequestId { get; }

    /// <summary>Gets the stable event name.</summary>
    public string EventName { get; }

    /// <summary>Gets the event's finite-JSON payload.</summary>
    public JsonElement Payload { get; }
}

/// <summary>
/// Startup-negotiation information returned by <c>system.hello</c>.
/// </summary>
public sealed class WorkerHello
{
    /// <summary>Gets or sets the worker implementation name.</summary>
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    /// <summary>Gets or sets the worker protocol version.</summary>
    [JsonPropertyName("protocol_version")]
    public int ProtocolVersion { get; set; }

    /// <summary>Gets or sets the data-contract schema version.</summary>
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; set; } = string.Empty;

    /// <summary>Gets or sets the worker's frame-size limit.</summary>
    [JsonPropertyName("max_frame_bytes")]
    public int MaxFrameBytes { get; set; }

    /// <summary>Gets or sets the worker's command allowlist.</summary>
    [JsonPropertyName("commands")]
    public List<string> Commands { get; set; } = new();

    /// <summary>Gets or sets the health snapshot included in the handshake.</summary>
    [JsonPropertyName("health")]
    public WorkerHealth? Health { get; set; }
}

/// <summary>
/// Environment and capability information returned by <c>system.health</c>.
/// </summary>
public sealed class WorkerHealth
{
    /// <summary>Gets or sets the health status, normally <c>ok</c>.</summary>
    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    /// <summary>Gets or sets worker identity information.</summary>
    [JsonPropertyName("worker")]
    public WorkerIdentity? Worker { get; set; }

    /// <summary>Gets or sets Python runtime information.</summary>
    [JsonPropertyName("python")]
    public WorkerPythonRuntime? Python { get; set; }

    /// <summary>Gets or sets detected Python distribution versions.</summary>
    [JsonPropertyName("packages")]
    public Dictionary<string, string?> Packages { get; set; } =
        new(StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Gets or sets worker capabilities. Values remain JSON because capability
    /// entries may be booleans, strings, or arrays.
    /// </summary>
    [JsonPropertyName("capabilities")]
    public Dictionary<string, JsonElement> Capabilities { get; set; } =
        new(StringComparer.OrdinalIgnoreCase);
}

/// <summary>
/// Worker identity information included in health responses.
/// </summary>
public sealed class WorkerIdentity
{
    /// <summary>Gets or sets the worker name.</summary>
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    /// <summary>Gets or sets the worker package version.</summary>
    [JsonPropertyName("version")]
    public string Version { get; set; } = string.Empty;

    /// <summary>Gets or sets the protocol version.</summary>
    [JsonPropertyName("protocol_version")]
    public int ProtocolVersion { get; set; }

    /// <summary>Gets or sets the stable contract schema version.</summary>
    [JsonPropertyName("schema_version")]
    public string SchemaVersion { get; set; } = string.Empty;
}

/// <summary>
/// Python runtime information included in health responses.
/// </summary>
public sealed class WorkerPythonRuntime
{
    /// <summary>Gets or sets the Python version.</summary>
    [JsonPropertyName("version")]
    public string Version { get; set; } = string.Empty;

    /// <summary>Gets or sets the Python implementation.</summary>
    [JsonPropertyName("implementation")]
    public string Implementation { get; set; } = string.Empty;

    /// <summary>Gets or sets the executable reported by the worker.</summary>
    [JsonPropertyName("executable")]
    public string Executable { get; set; } = string.Empty;
}

internal static class WorkerFrameCodec
{
    private const int HeaderBytes = sizeof(int);

    internal static async Task WriteAsync(
        Stream stream,
        object value,
        JsonSerializerOptions options,
        int maxFrameBytes,
        CancellationToken cancellationToken)
    {
        byte[] payload = JsonSerializer.SerializeToUtf8Bytes(
            value,
            value.GetType(),
            options);

        ValidateLength(payload.Length, maxFrameBytes);

        byte[] header = new byte[HeaderBytes];
        BinaryPrimitives.WriteInt32BigEndian(header, payload.Length);
        await stream.WriteAsync(header, cancellationToken).ConfigureAwait(false);
        await stream.WriteAsync(payload, cancellationToken).ConfigureAwait(false);
        await stream.FlushAsync(cancellationToken).ConfigureAwait(false);
    }

    internal static async Task<byte[]?> ReadAsync(
        Stream stream,
        int maxFrameBytes,
        CancellationToken cancellationToken)
    {
        byte[] header = new byte[HeaderBytes];
        int headerRead = await ReadAtMostAsync(
            stream,
            header,
            cancellationToken).ConfigureAwait(false);

        if (headerRead == 0)
            return null;
        if (headerRead != HeaderBytes)
            throw new EndOfStreamException("The worker stream ended inside a frame header.");

        int length = BinaryPrimitives.ReadInt32BigEndian(header);
        ValidateLength(length, maxFrameBytes);

        byte[] payload = new byte[length];
        int payloadRead = await ReadAtMostAsync(
            stream,
            payload,
            cancellationToken).ConfigureAwait(false);
        if (payloadRead != length)
        {
            throw new EndOfStreamException(
                $"The worker stream ended after {payloadRead} of {length} frame bytes.");
        }

        return payload;
    }

    private static async Task<int> ReadAtMostAsync(
        Stream stream,
        byte[] buffer,
        CancellationToken cancellationToken)
    {
        int offset = 0;
        while (offset < buffer.Length)
        {
            int read = await stream.ReadAsync(
                buffer.AsMemory(offset, buffer.Length - offset),
                cancellationToken).ConfigureAwait(false);
            if (read == 0)
                break;
            offset += read;
        }

        return offset;
    }

    private static void ValidateLength(int length, int configuredMaximum)
    {
        int maximum = Math.Min(configuredMaximum, WorkerProtocol.MaximumFrameBytes);
        if (length <= 0)
            throw new WorkerProtocolException($"Invalid worker frame length {length}.");
        if (length > maximum)
        {
            throw new WorkerProtocolException(
                $"Worker frame length {length} exceeds the {maximum}-byte limit.");
        }
    }
}
