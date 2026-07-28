using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Ananke.COMPAS.Native.Backend;

/// <summary>
/// Describes how the native plug-in launches its isolated Python worker.
/// </summary>
/// <remarks>
/// Relative paths are resolved against the directory containing
/// <c>backend.json</c>. Configuration discovery checks an explicit path, the
/// <c>ANANKE_COMPAS_BACKEND_CONFIG</c> environment variable, the plug-in
/// assembly directory, and standard Grasshopper library installation folders.
/// </remarks>
public sealed class WorkerConfiguration
{
    /// <summary>The environment variable used to override configuration discovery.</summary>
    public const string ConfigurationEnvironmentVariable =
        "ANANKE_COMPAS_BACKEND_CONFIG";

    /// <summary>Gets or sets the Python executable or worker launcher.</summary>
    [JsonPropertyName("executable")]
    public string Executable { get; set; } = string.Empty;

    /// <summary>Gets or sets launcher arguments, normally <c>-m ananke_equilibrium.worker</c>.</summary>
    [JsonPropertyName("arguments")]
    public List<string> Arguments { get; set; } = new();

    /// <summary>Gets or sets the worker process's working directory.</summary>
    [JsonPropertyName("workingDirectory")]
    public string? WorkingDirectory { get; set; }

    /// <summary>
    /// Gets or sets import roots that are prepended to the launched process's
    /// <c>PYTHONPATH</c>.
    /// </summary>
    [JsonPropertyName("pythonPaths")]
    public List<string> PythonPaths { get; set; } = new();

    /// <summary>Gets or sets an informational environment name.</summary>
    [JsonPropertyName("environmentName")]
    public string? EnvironmentName { get; set; }

    /// <summary>Gets or sets environment variables applied to the worker process.</summary>
    [JsonPropertyName("environment")]
    public Dictionary<string, string> Environment { get; set; } =
        new(StringComparer.OrdinalIgnoreCase);

    /// <summary>Gets or sets the required worker protocol version.</summary>
    [JsonPropertyName("protocolVersion")]
    public int ProtocolVersion { get; set; } = WorkerProtocol.CurrentVersion;

    /// <summary>Gets or sets the startup and handshake timeout in milliseconds.</summary>
    [JsonPropertyName("startupTimeoutMs")]
    public int StartupTimeoutMs { get; set; } = 15_000;

    /// <summary>Gets or sets the default command timeout in milliseconds.</summary>
    [JsonPropertyName("requestTimeoutMs")]
    public int RequestTimeoutMs { get; set; } = 120_000;

    /// <summary>
    /// Gets or sets the grace period before a cancelled command causes the
    /// worker process to be killed and restarted.
    /// </summary>
    [JsonPropertyName("cancellationGraceMs")]
    public int CancellationGraceMs { get; set; } = 250;

    /// <summary>Gets or sets the graceful shutdown timeout in milliseconds.</summary>
    [JsonPropertyName("shutdownTimeoutMs")]
    public int ShutdownTimeoutMs { get; set; } = 2_000;

    /// <summary>
    /// Gets or sets the transport frame limit. Values above 32 MiB are rejected.
    /// </summary>
    [JsonPropertyName("maxFrameBytes")]
    public int MaxFrameBytes { get; set; } = WorkerProtocol.MaximumFrameBytes;

    /// <summary>Gets the resolved source <c>backend.json</c> path.</summary>
    [JsonIgnore]
    public string? ConfigurationPath { get; private set; }

    /// <summary>
    /// Loads and validates a specific <c>backend.json</c> file.
    /// </summary>
    /// <param name="path">The configuration path.</param>
    /// <returns>A normalized configuration with absolute local paths.</returns>
    public static WorkerConfiguration Load(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("A backend configuration path is required.", nameof(path));

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(
                System.Environment.ExpandEnvironmentVariables(path));
        }
        catch (Exception error)
        {
            throw new WorkerConfigurationException(
                $"Backend configuration path '{path}' is invalid.",
                error);
        }

        if (!File.Exists(fullPath))
        {
            throw new WorkerConfigurationException(
                $"Backend configuration was not found at '{fullPath}'.");
        }

        try
        {
            using FileStream stream = File.OpenRead(fullPath);
            using JsonDocument document = JsonDocument.Parse(
                stream,
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Skip,
                    MaxDepth = 64
                });

            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
                throw new WorkerConfigurationException("backend.json must contain a JSON object.");

            // Accept either the documented flat shape or {"worker": {...}} so
            // an installer may add unrelated metadata without changing the host.
            JsonElement configurationElement = root;
            if (root.TryGetProperty("worker", out JsonElement nested))
                configurationElement = nested;

            WorkerConfiguration? configuration =
                configurationElement.Deserialize<WorkerConfiguration>(JsonOptions);
            if (configuration is null)
                throw new WorkerConfigurationException("backend.json contains no worker configuration.");

            configuration.ConfigurationPath = fullPath;
            configuration.NormalizeAndValidate(Path.GetDirectoryName(fullPath)!);
            return configuration;
        }
        catch (WorkerConfigurationException)
        {
            throw;
        }
        catch (Exception error) when (error is JsonException or IOException or UnauthorizedAccessException)
        {
            throw new WorkerConfigurationException(
                $"Could not load backend configuration '{fullPath}'.",
                error);
        }
    }

    /// <summary>
    /// Discovers and loads the installed worker configuration.
    /// </summary>
    /// <param name="configurationPath">
    /// Optional explicit path. When supplied, no fallback location is used.
    /// </param>
    /// <param name="pluginDirectory">
    /// Optional plug-in directory used before standard installation folders.
    /// </param>
    /// <returns>The first valid installed configuration.</returns>
    public static WorkerConfiguration LoadInstalled(
        string? configurationPath = null,
        string? pluginDirectory = null)
    {
        if (!string.IsNullOrWhiteSpace(configurationPath))
            return Load(configurationPath);

        string? environmentOverride =
            System.Environment.GetEnvironmentVariable(ConfigurationEnvironmentVariable);
        if (!string.IsNullOrWhiteSpace(environmentOverride))
            return Load(environmentOverride);

        var candidates = new List<string>();
        if (!string.IsNullOrWhiteSpace(pluginDirectory))
            candidates.Add(Path.Combine(pluginDirectory, "backend.json"));

        string assemblyDirectory =
            Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)
            ?? AppContext.BaseDirectory;
        candidates.Add(Path.Combine(assemblyDirectory, "backend.json"));

        string appData = System.Environment.GetFolderPath(
            System.Environment.SpecialFolder.ApplicationData);
        if (!string.IsNullOrWhiteSpace(appData))
        {
            string libraries = Path.Combine(appData, "Grasshopper", "Libraries");
            candidates.Add(Path.Combine(libraries, "Ananke_COMPAS", "backend.json"));
            candidates.Add(Path.Combine(libraries, "Ananke_COMPAS_Native", "backend.json"));
        }

        string? found = candidates
            .Select(path => Path.GetFullPath(path))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault(File.Exists);

        if (found is not null)
            return Load(found);

        throw new WorkerConfigurationException(
            "No installed backend.json was found. Checked: "
            + string.Join(", ", candidates.Select(path => $"'{path}'"))
            + $". Set {ConfigurationEnvironmentVariable} to override discovery.");
    }

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = false,
        MaxDepth = 64
    };

    private void NormalizeAndValidate(string configurationDirectory)
    {
        if (string.IsNullOrWhiteSpace(Executable))
            throw new WorkerConfigurationException("backend.json requires 'executable'.");
        if (Arguments is null)
            throw new WorkerConfigurationException("'arguments' must be a JSON array.");
        if (PythonPaths is null)
            throw new WorkerConfigurationException("'pythonPaths' must be a JSON array.");
        if (Environment is null)
            throw new WorkerConfigurationException("'environment' must be a JSON object.");

        Executable = Expand(Executable, configurationDirectory);
        if (!Path.IsPathRooted(Executable) && ContainsDirectorySeparator(Executable))
            Executable = Path.GetFullPath(Path.Combine(configurationDirectory, Executable));

        if (Path.IsPathRooted(Executable) && !File.Exists(Executable))
        {
            throw new WorkerConfigurationException(
                $"Worker executable was not found at '{Executable}'.");
        }

        WorkingDirectory = string.IsNullOrWhiteSpace(WorkingDirectory)
            ? configurationDirectory
            : ResolveDirectory(WorkingDirectory, configurationDirectory);
        if (!Directory.Exists(WorkingDirectory))
        {
            throw new WorkerConfigurationException(
                $"Worker working directory was not found at '{WorkingDirectory}'.");
        }

        Arguments = Arguments
            .Select(argument => Expand(
                argument ?? throw new WorkerConfigurationException(
                    "'arguments' cannot contain null."),
                configurationDirectory))
            .ToList();

        PythonPaths = PythonPaths
            .Select(path => ResolveDirectory(
                path ?? throw new WorkerConfigurationException(
                    "'pythonPaths' cannot contain null."),
                configurationDirectory))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
        foreach (string pythonPath in PythonPaths)
        {
            if (!Directory.Exists(pythonPath))
            {
                throw new WorkerConfigurationException(
                    $"Configured Python import path was not found at '{pythonPath}'.");
            }
        }

        Environment = Environment.ToDictionary(
            pair => pair.Key,
            pair => Expand(
                pair.Value ?? throw new WorkerConfigurationException(
                    $"Environment variable '{pair.Key}' has a null value."),
                configurationDirectory),
            StringComparer.OrdinalIgnoreCase);

        if (ProtocolVersion != WorkerProtocol.CurrentVersion)
        {
            throw new WorkerConfigurationException(
                $"Protocol version {ProtocolVersion} is not supported; "
                + $"this host requires {WorkerProtocol.CurrentVersion}.");
        }
        if (StartupTimeoutMs <= 0)
            throw new WorkerConfigurationException("'startupTimeoutMs' must be greater than zero.");
        if (RequestTimeoutMs <= 0)
            throw new WorkerConfigurationException("'requestTimeoutMs' must be greater than zero.");
        if (CancellationGraceMs < 0)
            throw new WorkerConfigurationException("'cancellationGraceMs' cannot be negative.");
        if (ShutdownTimeoutMs <= 0)
            throw new WorkerConfigurationException("'shutdownTimeoutMs' must be greater than zero.");
        if (MaxFrameBytes <= 0 || MaxFrameBytes > WorkerProtocol.MaximumFrameBytes)
        {
            throw new WorkerConfigurationException(
                $"'maxFrameBytes' must be between 1 and {WorkerProtocol.MaximumFrameBytes}.");
        }
    }

    private static string ResolveDirectory(string value, string configurationDirectory)
    {
        string expanded = Expand(value, configurationDirectory);
        return Path.GetFullPath(
            Path.IsPathRooted(expanded)
                ? expanded
                : Path.Combine(configurationDirectory, expanded));
    }

    private static string Expand(string value, string configurationDirectory)
    {
        return System.Environment.ExpandEnvironmentVariables(value)
            .Replace("${configDir}", configurationDirectory, StringComparison.OrdinalIgnoreCase)
            .Replace("{configDir}", configurationDirectory, StringComparison.OrdinalIgnoreCase);
    }

    private static bool ContainsDirectorySeparator(string value)
    {
        return value.Contains(Path.DirectorySeparatorChar)
            || value.Contains(Path.AltDirectorySeparatorChar);
    }
}
