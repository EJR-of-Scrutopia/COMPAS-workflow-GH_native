using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Ananke.COMPAS.Native.Backend;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.NativeWorkerIntegration;

internal static class Program
{
    private const string FdSolveCommand = "fd.solve";

    public static async Task<int> Main(string[] args)
    {
        try
        {
            string configurationPath = ParseConfigurationPath(args);
            await RunAsync(configurationPath).ConfigureAwait(false);
            return 0;
        }
        catch (UsageException error)
        {
            Console.Error.WriteLine($"ERROR: {error.Message}");
            Console.Error.WriteLine(
                "Usage: dotnet run --project tests/native_worker_integration -- "
                + "<backend.json>");
            return 2;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(
                "ERROR: Native worker integration failed: "
                + DescribeException(error));
            return 3;
        }
    }

    private static async Task RunAsync(string configurationPath)
    {
        WorkerConfiguration configuration =
            WorkerConfiguration.Load(configurationPath);
        await using var host = new WorkerHost(configuration);

        WorkerHealth health = await host.HealthAsync().ConfigureAwait(false);
        Require(
            string.Equals(health.Status, "ok", StringComparison.OrdinalIgnoreCase),
            $"Worker health was '{health.Status}', not 'ok'.");

        ValidateTopologyRegistration();
        ValidateRequiredDiscriminators();
        (EquilibriumProblemDto problem, FDSettingsDto settings) =
            BuildProblem();
        IReadOnlyDictionary<string, object?> payload =
            problem.ToFdSolvePayload(settings);

        JsonElement response = await host.RequestAsync<JsonElement>(
            FdSolveCommand,
            payload).ConfigureAwait(false);
        EquilibriumResultDto result =
            DecodeFd(response, problem, settings);
        ValidateResult(result, problem);

        Console.WriteLine(
            $"PASS fd.solve: {result.Vertices.Count} nodes, "
            + $"{result.Edges.Count} members, "
            + $"max residual {MaximumResidual(result):0.000e+00}, "
            + $"worker {host.Hello?.Name ?? "unknown"}.");

        using var shutdownTimeout = new CancellationTokenSource(
            configuration.ShutdownTimeoutMs + 1_000);
        await host.ShutdownAsync(shutdownTimeout.Token).ConfigureAwait(false);

        await ValidateCancellationRecovery(configuration).ConfigureAwait(false);
        await ValidateSchemaHandshakeRejection(configuration).ConfigureAwait(false);
    }

    private static void ValidateRequiredDiscriminators()
    {
        RequireJsonFailure(
            "{\"kind\":\"ananke.topology\"}",
            "Contract JSON accepted a missing schemaVersion.");
        RequireJsonFailure(
            "{\"schemaVersion\":\"0.2\"}",
            "Contract JSON accepted a missing kind.");
    }

    private static void RequireJsonFailure(string json, string message)
    {
        try
        {
            _ = ContractJson.Deserialize<TopologyDto>(json);
        }
        catch (JsonException)
        {
            return;
        }
        throw new InvalidOperationException(message);
    }

    private static void ValidateTopologyRegistration()
    {
        Assembly nativeAssembly = typeof(WorkerHost).Assembly;
        Type builderType = nativeAssembly.GetType(
            "Ananke.COMPAS.Native.Components.GeometryTopologyBuilder",
            throwOnError: true)
            ?? throw new InvalidOperationException(
                "Native GeometryTopologyBuilder type was not found.");
        MethodInfo compactMethod = builderType.GetMethod(
            "Compact",
            BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException(
                "GeometryTopologyBuilder.Compact was not found.");
        Point3d[] sourceVertices =
        {
            new(99.0, 99.0, 99.0),
            new(88.0, 88.0, 88.0),
            new(10.0, 0.0, 0.0),
            new(20.0, 0.0, 0.0),
            new(10.0, 10.0, 0.0)
        };
        (int U, int V)[] sourceEdges =
        {
            (2, 3),
            (3, 4),
            (2, 4)
        };

        object registered;
        try
        {
            registered = compactMethod.Invoke(
                null,
                new object[]
                {
                    "Line",
                    sourceVertices,
                    sourceEdges,
                    new[] { "mesh:e0", "mesh:e1", "mesh:e2" },
                    Array.Empty<IReadOnlyList<int>>()
                }) ?? throw new InvalidOperationException(
                    "GeometryTopologyBuilder.Compact returned null.");
        }
        catch (TargetInvocationException error)
            when (error.InnerException is not null)
        {
            throw new InvalidOperationException(
                "GeometryTopologyBuilder rejected the edge-order fixture.",
                error.InnerException);
        }

        IReadOnlyList<Point3d> vertices =
            ReadProperty<IReadOnlyList<Point3d>>(registered, "Vertices");
        IReadOnlyList<(int U, int V)> edges =
            ReadProperty<IReadOnlyList<(int U, int V)>>(registered, "Edges");
        IReadOnlyList<string> sourceIds =
            ReadProperty<IReadOnlyList<string>>(registered, "SourceEdgeIds");
        Require(vertices.Count == 3, "Isolated mesh vertices were not compacted.");
        Require(
            vertices[0].X == 10.0 &&
            vertices[0].Y == 0.0 &&
            vertices[0].Z == 0.0,
            "Registered vertices do not follow first edge-endpoint encounter.");
        Require(
            edges.SequenceEqual(
                new[] { (U: 0, V: 1), (U: 1, V: 2), (U: 0, V: 2) }),
            "Registered mesh edges were not remapped canonically.");
        Require(
            sourceIds.Count == edges.Count &&
            sourceIds.All(value => !string.IsNullOrWhiteSpace(value)),
            "Stable source edge IDs do not align with registered edges.");
    }

    private static T ReadProperty<T>(object instance, string propertyName)
    {
        object? value = instance.GetType()
            .GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public)
            ?.GetValue(instance);
        return value is T typed
            ? typed
            : throw new InvalidOperationException(
                $"{instance.GetType().Name}.{propertyName} is not {typeof(T).Name}.");
    }

    private static (EquilibriumProblemDto, FDSettingsDto) BuildProblem()
    {
        TopologyDto topology = TopologyDto.Create(
            "line",
            new[]
            {
                new Point3Dto(0.0, 0.0, 0.0),
                new Point3Dto(5.0, 0.0, 0.0),
                new Point3Dto(10.0, 0.0, 0.0)
            },
            new[]
            {
                new EdgeDto(0, 1),
                new EdgeDto(1, 2)
            },
            sourceVertexIds: new[] { "left", "mid", "right" },
            sourceEdgeIds: new[] { "span:left", "span:right" },
            provenance: new Dictionary<string, string>
            {
                ["source"] = "native-worker-integration"
            });
        ValidateNativeSafetyContracts(topology);

        var supports = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = "explicit",
            NodeIds = new[] { 0, 2 },
            Points = Array.Empty<Point3Dto>(),
            Provenance = new Dictionary<string, string>
            {
                ["source"] = "native-worker-integration"
            }
        };
        var loadCase = new LoadCaseDto
        {
            TopologyHash = topology.TopologyHash,
            Name = "integration-downward",
            Distribution = "point",
            NodeIds = new[] { 1 },
            Points = Array.Empty<Point3Dto>(),
            Vectors = new[] { new Point3Dto(0.0, 0.0, -1.0) },
            Factor = 1.0,
            CoordinateSystem = "world",
            Provenance = new Dictionary<string, string>
            {
                ["force_unit"] = "kN",
                ["source"] = "native-worker-integration"
            }
        };
        var problem = new EquilibriumProblemDto
        {
            Name = "three-node-cable",
            Topology = topology,
            Supports = supports,
            LoadCases = new[] { loadCase },
            Provenance = new Dictionary<string, string>
            {
                ["source"] = "native-worker-integration"
            }
        };
        var settings = new FDSettingsDto
        {
            ForceDensities = new[] { 2.0, 3.0 },
            SignConvention = "positive_tension",
            Provenance = new Dictionary<string, string>
            {
                ["source"] = "native-worker-integration"
            }
        };

        RequireValid(topology);
        RequireValid(supports);
        RequireValid(loadCase);
        RequireValid(problem);
        RequireValid(settings);
        return (problem, settings);
    }

    private static void ValidateNativeSafetyContracts(TopologyDto topology)
    {
        var unresolvedSupport = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = "explicit",
            Points = new[] { new Point3Dto(999.0, 999.0, 999.0) }
        };
        Require(
            unresolvedSupport.Validate().Any(
                error => error.Contains(
                    "resolved to nodeIds",
                    StringComparison.Ordinal)),
            "Support contract accepted an unresolved point target.");

        var hiddenCornerFallback = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = "corners"
        };
        Require(
            hiddenCornerFallback.Validate().Count > 0,
            "Support contract accepted unimplemented corner detection.");

        var falseSelfWeight = new LoadCaseDto
        {
            TopologyHash = topology.TopologyHash,
            Name = "unsafe",
            Distribution = "self_weight",
            BaseVector = new Point3Dto(0.0, 0.0, -1.0)
        };
        Require(
            falseSelfWeight.Validate().Count > 0,
            "Load contract accepted unimplemented self weight.");

        var targetedUniform = new LoadCaseDto
        {
            TopologyHash = topology.TopologyHash,
            Name = "unsafe-uniform",
            Distribution = "uniform_nodes",
            NodeIds = new[] { 1 },
            BaseVector = new Point3Dto(0.0, 0.0, -1.0)
        };
        Require(
            targetedUniform.Validate().Any(
                error => error.Contains(
                    "selects every node",
                    StringComparison.Ordinal)),
            "Uniform Nodes accepted explicit targets.");

        var tinyDensity = new FDSettingsDto
        {
            ForceDensities = new[] { 1.0e-13 }
        };
        Require(
            tinyDensity.Validate().Any(
                error => error.Contains(
                    "greater than 1e-12",
                    StringComparison.Ordinal)),
            "FD settings accepted a force density rejected by the backend.");
    }

    private static async Task ValidateCancellationRecovery(
        WorkerConfiguration installed)
    {
        WorkerConfiguration configuration =
            FakeWorkerConfiguration(installed, badSchema: false);
        await using var host = new WorkerHost(configuration);
        await host.StartAsync().ConfigureAwait(false);

        using var firstCancellation = new CancellationTokenSource(75);
        using var secondCancellation = new CancellationTokenSource(75);
        Task<JsonElement> first = host.RequestAsync<JsonElement>(
            "test.delay",
            new Dictionary<string, object?> { ["seconds"] = 3.0 },
            firstCancellation.Token);
        Task<JsonElement> second = host.RequestAsync<JsonElement>(
            "test.delay",
            new Dictionary<string, object?> { ["seconds"] = 3.0 },
            secondCancellation.Token);

        await RequireCancelled(first, "first").ConfigureAwait(false);
        await RequireCancelled(second, "second").ConfigureAwait(false);
        await Task.Delay(configuration.CancellationGraceMs + 500)
            .ConfigureAwait(false);

        WorkerHealth firstHealth = await host.HealthAsync().ConfigureAwait(false);
        Require(
            string.Equals(
                firstHealth.Status,
                "ok",
                StringComparison.OrdinalIgnoreCase),
            "Replacement worker was not healthy after concurrent cancellation.");

        await Task.Delay(configuration.CancellationGraceMs + 250)
            .ConfigureAwait(false);
        WorkerHealth secondHealth = await host.HealthAsync().ConfigureAwait(false);
        Require(
            string.Equals(
                secondHealth.Status,
                "ok",
                StringComparison.OrdinalIgnoreCase),
            "A duplicate cancellation recovery killed the replacement worker.");

        Console.WriteLine(
            "PASS worker recovery: concurrent cancellations coalesced.");
    }

    private static async Task RequireCancelled(
        Task<JsonElement> task,
        string label)
    {
        try
        {
            _ = await task.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            return;
        }
        throw new InvalidOperationException(
            $"The {label} delayed request was not cancelled.");
    }

    private static async Task ValidateSchemaHandshakeRejection(
        WorkerConfiguration installed)
    {
        WorkerConfiguration configuration =
            FakeWorkerConfiguration(installed, badSchema: true);
        await using var host = new WorkerHost(configuration);
        try
        {
            await host.StartAsync().ConfigureAwait(false);
        }
        catch (WorkerProtocolException error)
            when (error.Message.Contains(
                "supported schema",
                StringComparison.Ordinal))
        {
            Console.WriteLine(
                "PASS worker negotiation: incompatible schema rejected.");
            return;
        }
        throw new InvalidOperationException(
            "Worker startup accepted an incompatible snapshot schema.");
    }

    private static WorkerConfiguration FakeWorkerConfiguration(
        WorkerConfiguration installed,
        bool badSchema)
    {
        string script = Path.Combine(
            AppContext.BaseDirectory,
            "fake_worker.py");
        Require(File.Exists(script), $"Fake worker was not copied to {script}.");
        var arguments = new List<string> { script };
        if (badSchema)
            arguments.Add("--bad-schema");

        return new WorkerConfiguration
        {
            Executable = installed.Executable,
            Arguments = arguments,
            WorkingDirectory = AppContext.BaseDirectory,
            PythonPaths = new List<string>(),
            EnvironmentName = "native-worker-race-test",
            Environment = new Dictionary<string, string>(),
            ProtocolVersion = WorkerProtocol.CurrentVersion,
            StartupTimeoutMs = 5_000,
            RequestTimeoutMs = 5_000,
            CancellationGraceMs = 100,
            ShutdownTimeoutMs = 1_000,
            MaxFrameBytes = WorkerProtocol.MaximumFrameBytes
        };
    }

    private static EquilibriumResultDto DecodeFd(
        JsonElement response,
        EquilibriumProblemDto problem,
        FDSettingsDto settings)
    {
        Assembly nativeAssembly = typeof(WorkerHost).Assembly;
        Type codecType = nativeAssembly.GetType(
            "Ananke.COMPAS.Native.Components.WorkerResultCodec",
            throwOnError: true)
            ?? throw new InvalidOperationException(
                "Native WorkerResultCodec type was not found.");
        MethodInfo decodeMethod = codecType.GetMethod(
            "DecodeFd",
            BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException(
                "Native WorkerResultCodec.DecodeFd was not found.");

        try
        {
            object? value = decodeMethod.Invoke(
                null,
                new object[] { response, problem, settings, 0 });
            return value as EquilibriumResultDto
                ?? throw new InvalidOperationException(
                    "WorkerResultCodec.DecodeFd returned the wrong type.");
        }
        catch (TargetInvocationException error)
            when (error.InnerException is not null)
        {
            throw new InvalidOperationException(
                "WorkerResultCodec.DecodeFd rejected the worker result.",
                error.InnerException);
        }
    }

    private static void ValidateResult(
        EquilibriumResultDto result,
        EquilibriumProblemDto problem)
    {
        RequireValid(result);
        Require(
            string.Equals(result.Solver, "fd", StringComparison.OrdinalIgnoreCase),
            $"Expected solver 'fd', received '{result.Solver}'.");
        Require(result.Vertices.Count == 3, "FD result must contain three nodes.");
        Require(result.Edges.Count == 2, "FD result must contain two members.");
        Require(
            result.MemberForces.Count == 2,
            "Member forces must align with both members.");
        Require(
            result.ForceDensities.Count == 2,
            "Force densities must align with both members.");
        Require(
            result.ForceDensities.SequenceEqual(new[] { 2.0, 3.0 }),
            "Asymmetric force densities did not preserve member order.");
        Require(
            result.MemberSourceIds.SequenceEqual(
                problem.Topology!.SourceEdgeIds),
            "Member source IDs did not survive the worker round-trip.");
        Require(
            result.ResolvedSupportNodeIds.SequenceEqual(new[] { 0, 2 }),
            "Resolved support node IDs did not survive the worker round-trip.");
        Require(
            result.Edges
                .Zip(
                    problem.Topology.Edges,
                    (actual, expected) =>
                        actual.U == expected.U &&
                        actual.V == expected.V)
                .All(matches => matches),
            "Solved edges do not preserve registered topology order.");
        Require(
            result.TopologyHash == problem.TopologyHash,
            "Result topology hash does not match the input problem.");
        Require(
            result.Vertices.All(point =>
                double.IsFinite(point.X)
                && double.IsFinite(point.Y)
                && double.IsFinite(point.Z)),
            "FD result contains a non-finite coordinate.");
        Require(
            result.MemberForces.All(double.IsFinite),
            "FD result contains a non-finite member force.");
        Require(
            result.Residuals.All(item =>
                double.IsFinite(item.Vector.X)
                && double.IsFinite(item.Vector.Y)
                && double.IsFinite(item.Vector.Z)),
            "FD result contains a non-finite residual.");

        Point3Dto midpoint = result.Vertices[1];
        Require(
            midpoint.Z < 0.0,
            $"Loaded free node should move downward; solved Z was {midpoint.Z}.");
        Require(
            MaximumResidual(result) <= 1.0e-8,
            "Free-node equilibrium residual exceeds 1e-8.");
    }

    private static double MaximumResidual(EquilibriumResultDto result)
    {
        return result.Residuals.Count == 0
            ? 0.0
            : result.Residuals.Max(item =>
                Math.Sqrt(
                    item.Vector.X * item.Vector.X
                    + item.Vector.Y * item.Vector.Y
                    + item.Vector.Z * item.Vector.Z));
    }

    private static void RequireValid(ContractDto value)
    {
        IReadOnlyList<string> errors = value.Validate();
        if (errors.Count != 0)
        {
            throw new InvalidOperationException(
                $"{value.GetType().Name} is invalid: "
                + string.Join(" ", errors));
        }
    }

    private static string ParseConfigurationPath(IReadOnlyList<string> args)
    {
        if (args.Count != 1 || string.IsNullOrWhiteSpace(args[0]))
            throw new UsageException("Exactly one backend.json path is required.");

        string path = Path.GetFullPath(args[0]);
        if (!File.Exists(path))
            throw new UsageException($"Backend configuration does not exist: {path}");
        return path;
    }

    private static void Require(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }

    private static string DescribeException(Exception error)
    {
        var descriptions = new List<string>();
        for (Exception? current = error;
             current is not null;
             current = current.InnerException)
        {
            descriptions.Add(
                $"{current.GetType().Name}: {current.Message}");
        }
        return string.Join(" -> ", descriptions);
    }

    private sealed class UsageException : Exception
    {
        public UsageException(string message)
            : base(message)
        {
        }
    }
}
