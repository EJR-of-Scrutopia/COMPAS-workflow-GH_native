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
    private const string TnaSolveCommand = "tna.solve";

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
        ValidateTnaContractsAndCodec();
        await ValidateRealTnaWorker(host).ConfigureAwait(false);
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

    private static async Task ValidateRealTnaWorker(WorkerHost host)
    {
        var vertices = new List<Point3Dto>();
        for (int y = 0; y < 3; y++)
        {
            for (int x = 0; x < 3; x++)
                vertices.Add(new Point3Dto(x, y, 0.0));
        }
        int[][] faces =
        {
            new[] { 0, 1, 4, 3 },
            new[] { 1, 2, 5, 4 },
            new[] { 3, 4, 7, 6 },
            new[] { 4, 5, 8, 7 }
        };
        var edges = new List<EdgeDto>
        {
            new(0, 1),
            new(1, 2),
            new(0, 3),
            new(1, 4),
            new(2, 5),
            new(3, 6),
            new(4, 7),
            new(5, 8),
            new(3, 4),
            new(4, 5),
            new(6, 7),
            new(7, 8)
        };

        TopologyDto topology = TopologyDto.Create(
            "faced",
            vertices,
            edges,
            faces,
            sourceVertexIds: Enumerable.Range(0, vertices.Count)
                .Select(index => $"grid-{index}"),
            sourceEdgeIds: Enumerable.Range(0, edges.Count)
                .Select(index => $"grid-edge-{index}"),
            lengthUnit: "m");
        var supports = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = "boundary"
        };
        var loadCase = new LoadCaseDto
        {
            TopologyHash = topology.TopologyHash,
            Name = "real-tna-dead",
            Distribution = "uniform_nodes",
            BaseVector = new Point3Dto(0.0, 0.0, -1.0),
            Provenance = new Dictionary<string, string>
            {
                ["force_unit"] = "kN"
            }
        };
        var problem = new EquilibriumProblemDto
        {
            Name = "real-tna-grid",
            Topology = topology,
            Supports = supports,
            LoadCases = new[] { loadCase }
        };
        var control = new TnaControlDto
        {
            HeightMode = "zmax",
            HeightValue = 1.0,
            HorizontalAlpha = 100.0,
            HorizontalIterations = 100,
            VerticalIterations = 100,
            Tolerance = 1.0e-3
        };
        RequireValid(problem);
        RequireValid(control);

        JsonElement response = await host.RequestAsync<JsonElement>(
            TnaSolveCommand,
            problem.ToTnaSolvePayload(control)).ConfigureAwait(false);
        TnaResultDto result = DecodeTna(
            response,
            problem,
            control);
        RequireValid(result);
        Require(
            result.FormGraph.Edges.Count == 4 &&
            result.ForceGraph.Edges.Count == 4 &&
            result.EdgeStates.Count == 4,
            "Real TNA worker did not return four aligned reciprocal edges.");
        Require(
            result.FormGraph.Vertices
                .SelectMany(vertex => vertex.SourceVertexIds)
                .Any(value =>
                    value.ValueKind == JsonValueKind.String &&
                    value.GetString()?.StartsWith(
                        "grid-",
                        StringComparison.Ordinal) == true),
            "Real TNA string source-vertex IDs did not survive native decoding.");
        GraphicDiagramDto diagram = BuildTnaGraphicDiagram(result);
        RequireValid(diagram);
        Require(
            diagram.LoadEdges.Count > 0 &&
            diagram.ReactionEdges.Count > 0,
            "Real TNA graphic diagram omitted loads or reactions.");
        Console.WriteLine(
            "PASS tna.solve: real COMPAS TNA reciprocal state decoded natively.");
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

    private static void ValidateTnaContractsAndCodec()
    {
        (EquilibriumProblemDto problem, TnaControlDto control) =
            BuildTnaProblem();
        IReadOnlyDictionary<string, object?> payload =
            problem.ToTnaSolvePayload(control);
        JsonElement payloadJson = JsonSerializer.SerializeToElement(
            payload,
            ContractJson.Options);
        Require(
            payloadJson.TryGetProperty("control", out JsonElement controlJson) &&
            controlJson.TryGetProperty(
                "height_control",
                out JsonElement heightJson) &&
            heightJson.GetProperty("mode").GetString() == "zmax",
            "Native TNA payload did not preserve nested height control.");

        JsonElement fixture = BuildTnaResultFixture();
        TnaResultDto result = DecodeTna(
            fixture,
            problem,
            control);
        RequireValid(result);
        Require(
            result.HorizontalScale == -0.375,
            "Signed physical force-diagram scale was not preserved.");
        Require(
            result.EdgeStates.Count == 3 &&
            result.Mappings.FormEdgeToForceEdge.Count == 3,
            "TNA reciprocal edge mappings were not decoded.");
        TnaEdgeStateDto[] duplicateFormStates =
            result.EdgeStates.ToArray();
        duplicateFormStates[1] = duplicateFormStates[1] with
        {
            FormEdgeId = duplicateFormStates[0].FormEdgeId
        };
        TnaResultDto unsafeCorrespondence = result with
        {
            EdgeStates = duplicateFormStates
        };
        Require(
            unsafeCorrespondence.Validate().Any(error =>
                error.Contains(
                    "duplicates a form edge",
                    StringComparison.Ordinal)),
            "TNA contract accepted ambiguous reciprocal correspondence.");
        Require(
            result.Equilibrium?.SolverSettings["load_case_name"] ==
            "vault-dead",
            "Named TNA load-case provenance was not preserved.");

        GraphicDiagramDto diagram = BuildTnaGraphicDiagram(result);
        RequireValid(diagram);
        Require(
            diagram.ThrustEdges.Count == 3 &&
            diagram.FormEdges.Count == 3 &&
            diagram.ForceEdges.Count == 3,
            "TNA Reciprocal did not preserve all three mapped diagrams.");
        Require(
            diagram.ForceEdges.All(edge =>
                edge.FormEdgeId.HasValue &&
                edge.ForceEdgeId.HasValue &&
                edge.EquilibriumEdgeId.HasValue),
            "Graphic diagram lost form/force/thrust correspondence.");
        GraphicEdgeDto firstForceEdge = diagram.ForceEdges[0];
        double displayedLength = Distance(
            firstForceEdge.Start,
            firstForceEdge.End);
        Require(
            Math.Abs(displayedLength - 0.75) <= 1.0e-12,
            "TNA Reciprocal did not apply the signed physical horizontal scale.");
        Require(
            diagram.LoadEdges.Count == 1 &&
            diagram.ReactionEdges.Count == 2,
            "TNA Reciprocal did not preserve loads and reactions.");
        Console.WriteLine(
            "PASS tna contracts: named case, reciprocal mappings, signed scale, "
            + "and compact graphic diagram.");
    }

    private static (EquilibriumProblemDto, TnaControlDto) BuildTnaProblem()
    {
        TopologyDto topology = TopologyDto.Create(
            "faced",
            new[]
            {
                new Point3Dto(0.0, 0.0, 0.0),
                new Point3Dto(5.0, 0.0, 0.0),
                new Point3Dto(2.5, 4.0, 0.0)
            },
            new[]
            {
                new EdgeDto(0, 1),
                new EdgeDto(1, 2),
                new EdgeDto(2, 0)
            },
            faces: new[]
            {
                (IEnumerable<int>)new[] { 0, 1, 2 }
            },
            sourceVertexIds: new[] { "left", "right", "crown" },
            sourceEdgeIds: new[] { "base", "right-rise", "left-rise" },
            provenance: new Dictionary<string, string>
            {
                ["source"] = "native-tna-fixture"
            });
        var supports = new SupportSetDto
        {
            TopologyHash = topology.TopologyHash,
            Mode = "explicit",
            NodeIds = new[] { 0, 1 }
        };
        var loadCase = new LoadCaseDto
        {
            TopologyHash = topology.TopologyHash,
            Name = "vault-dead",
            Distribution = "point",
            NodeIds = new[] { 2 },
            Vectors = new[] { new Point3Dto(0.0, 0.0, -1.0) },
            Provenance = new Dictionary<string, string>
            {
                ["force_unit"] = "kN",
                ["id"] = "LC-DEAD"
            }
        };
        var problem = new EquilibriumProblemDto
        {
            Name = "triangular-vault",
            Topology = topology,
            Supports = supports,
            LoadCases = new[] { loadCase }
        };
        var control = new TnaControlDto
        {
            HeightMode = "zmax",
            HeightValue = 2.0,
            HorizontalAlpha = 100.0,
            HorizontalIterations = 50,
            VerticalIterations = 50,
            Tolerance = 1.0e-3
        };
        RequireValid(topology);
        RequireValid(supports);
        RequireValid(loadCase);
        RequireValid(problem);
        RequireValid(control);
        return (problem, control);
    }

    private static JsonElement BuildTnaResultFixture()
    {
        double[][] planar =
        {
            new[] { 0.0, 0.0, 0.0 },
            new[] { 5.0, 0.0, 0.0 },
            new[] { 2.5, 4.0, 0.0 }
        };
        double[][] thrust =
        {
            new[] { 0.0, 0.0, 0.0 },
            new[] { 5.0, 0.0, 0.0 },
            new[] { 2.5, 4.0, 2.0 }
        };
        int[][] edges =
        {
            new[] { 0, 1 },
            new[] { 1, 2 },
            new[] { 2, 0 }
        };
        object[] formVertices = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["id"] = index,
                ["key"] = index,
                ["point"] = planar[index],
                ["source_vertex_ids"] = new[]
                {
                    new[] { "left", "right", "crown" }[index]
                }
            })
            .ToArray();
        object[] formEdges = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["id"] = index,
                ["key"] = edges[index],
                ["u"] = edges[index][0],
                ["v"] = edges[index][1],
                ["source_edge_ids"] = new[] { index }
            })
            .ToArray();
        object[] forceVertices =
        {
            new Dictionary<string, object?>
            {
                ["id"] = 0,
                ["key"] = "a",
                ["point"] = new[] { 0.0, 0.0, 0.0 }
            },
            new Dictionary<string, object?>
            {
                ["id"] = 1,
                ["key"] = "b",
                ["point"] = new[] { 0.0, 2.0, 0.0 }
            },
            new Dictionary<string, object?>
            {
                ["id"] = 2,
                ["key"] = "c",
                ["point"] = new[] { 1.5, 1.0, 0.0 }
            }
        };
        object[] forceEdges = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["id"] = index,
                ["key"] = edges[index],
                ["u"] = edges[index][0],
                ["v"] = edges[index][1]
            })
            .ToArray();
        object[] states = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["id"] = index,
                ["source_edge_ids"] = new[] { index },
                ["form_edge_id"] = index,
                ["force_edge_id"] = index,
                ["equilibrium_edge_id"] = index,
                ["q"] = -1.0,
                ["horizontal_force"] = -2.0 - index,
                ["axial_force"] = -2.5 - index,
                ["force_state"] = "compression",
                ["reciprocity_error_degrees"] = 0.0
            })
            .ToArray();
        object[] sourceVertexMappings = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["topology_vertex_id"] = index,
                ["source_vertex_id"] =
                    new[] { "left", "right", "crown" }[index],
                ["form_vertex_id"] = index,
                ["equilibrium_vertex_id"] = index
            })
            .ToArray();
        object[] sourceEdgeMappings = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["source_edge_id"] = index,
                ["source_u"] = edges[index][0],
                ["source_v"] = edges[index][1],
                ["form_edge_id"] = index
            })
            .ToArray();
        object[] formToForce = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["form_edge_id"] = index,
                ["force_edge_id"] = index
            })
            .ToArray();
        object[] formToEquilibrium = Enumerable.Range(0, 3)
            .Select(index => (object)new Dictionary<string, object?>
            {
                ["form_edge_id"] = index,
                ["equilibrium_edge_id"] = index
            })
            .ToArray();
        object[] supports =
        {
            new Dictionary<string, object?>
            {
                ["topology_vertex_id"] = 0,
                ["source_vertex_id"] = "left",
                ["form_vertex_id"] = 0,
                ["equilibrium_vertex_id"] = 0,
                ["reaction"] = new[] { 1.0, 0.0, 0.5 }
            },
            new Dictionary<string, object?>
            {
                ["topology_vertex_id"] = 1,
                ["source_vertex_id"] = "right",
                ["form_vertex_id"] = 1,
                ["equilibrium_vertex_id"] = 1,
                ["reaction"] = new[] { -1.0, 0.0, 0.5 }
            }
        };
        object[] loads =
        {
            new Dictionary<string, object?>
            {
                ["topology_vertex_ids"] = new[] { 2 },
                ["source_vertex_ids"] = new[] { "crown" },
                ["form_vertex_id"] = 2,
                ["equilibrium_vertex_id"] = 2,
                ["vector"] = new[] { 0.0, 0.0, -1.0 }
            }
        };
        var equilibrium = new Dictionary<string, object?>
        {
            ["schema_version"] = "0.1",
            ["solver"] = "tna",
            ["vertices"] = thrust,
            ["edges"] = edges,
            ["member_forces"] = new[] { -2.5, -3.5, -4.5 },
            ["force_densities"] = new[] { -1.0, -1.0, -1.0 },
            ["diagnostics"] = Array.Empty<object>(),
            ["report"] = "Fixture equilibrium.",
            ["provenance"] = new Dictionary<string, object?>
            {
                ["worker"] = "fixture"
            }
        };
        var fixture = new Dictionary<string, object?>
        {
            ["schema_version"] = "0.1",
            ["kind"] = "tna_result",
            ["equilibrium"] = equilibrium,
            ["analysis_plane"] = new Dictionary<string, object?>
            {
                ["origin"] = new[] { 0.0, 0.0, 0.0 },
                ["xaxis"] = new[] { 1.0, 0.0, 0.0 },
                ["yaxis"] = new[] { 0.0, 1.0, 0.0 },
                ["zaxis"] = new[] { 0.0, 0.0, 1.0 }
            },
            ["form_graph"] = new Dictionary<string, object?>
            {
                ["vertices"] = formVertices,
                ["edges"] = formEdges,
                ["faces"] = new object[]
                {
                    new Dictionary<string, object?>
                    {
                        ["id"] = 0,
                        ["key"] = 0,
                        ["vertices"] = new[] { 0, 1, 2 }
                    }
                }
            },
            ["force_graph"] = new Dictionary<string, object?>
            {
                ["vertices"] = forceVertices,
                ["edges"] = forceEdges,
                ["faces"] = new object[]
                {
                    new Dictionary<string, object?>
                    {
                        ["id"] = 0,
                        ["key"] = 0,
                        ["vertices"] = new[] { 0, 1, 2 }
                    }
                }
            },
            ["edge_states"] = states,
            ["horizontal_scale"] = -0.375,
            ["mappings"] = new Dictionary<string, object?>
            {
                ["source_vertex_to_form_vertex"] = sourceVertexMappings,
                ["source_edge_to_form_edge"] = sourceEdgeMappings,
                ["form_edge_to_force_edge"] = formToForce,
                ["form_edge_to_equilibrium_edge"] = formToEquilibrium,
                ["supports"] = supports,
                ["loads"] = loads,
                ["reactions"] = supports
            },
            ["diagnostics"] = Array.Empty<object>(),
            ["report"] = "Fixture TNA solve.",
            ["provenance"] = new Dictionary<string, object?>
            {
                ["worker"] = "fixture"
            }
        };
        return JsonSerializer.SerializeToElement(
            fixture,
            ContractJson.Options);
    }

    private static TnaResultDto DecodeTna(
        JsonElement response,
        EquilibriumProblemDto problem,
        TnaControlDto control)
    {
        Assembly nativeAssembly = typeof(WorkerHost).Assembly;
        Type codecType = nativeAssembly.GetType(
            "Ananke.COMPAS.Native.Components.TnaWorkerResultCodec",
            throwOnError: true)
            ?? throw new InvalidOperationException(
                "Native TnaWorkerResultCodec type was not found.");
        MethodInfo decodeMethod = codecType.GetMethod(
            "Decode",
            BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException(
                "TnaWorkerResultCodec.Decode was not found.");
        try
        {
            object? value = decodeMethod.Invoke(
                null,
                new object[] { response, problem, control, 0 });
            return value as TnaResultDto
                ?? throw new InvalidOperationException(
                    "TnaWorkerResultCodec.Decode returned the wrong type.");
        }
        catch (TargetInvocationException error)
            when (error.InnerException is not null)
        {
            throw new InvalidOperationException(
                "TnaWorkerResultCodec.Decode rejected the fixture.",
                error.InnerException);
        }
    }

    private static GraphicDiagramDto BuildTnaGraphicDiagram(
        TnaResultDto result)
    {
        Assembly nativeAssembly = typeof(WorkerHost).Assembly;
        Type factoryType = nativeAssembly.GetType(
            "Ananke.COMPAS.Native.Components.TnaGraphicDiagramFactory",
            throwOnError: true)
            ?? throw new InvalidOperationException(
                "Native TnaGraphicDiagramFactory type was not found.");
        MethodInfo buildMethod = factoryType.GetMethod(
            "Build",
            BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new InvalidOperationException(
                "TnaGraphicDiagramFactory.Build was not found.");
        try
        {
            object? value = buildMethod.Invoke(
                null,
                new object[]
                {
                    result,
                    "side_by_side",
                    "natural",
                    1.0,
                    1.0,
                    0.15
                });
            return value as GraphicDiagramDto
                ?? throw new InvalidOperationException(
                    "TnaGraphicDiagramFactory.Build returned the wrong type.");
        }
        catch (TargetInvocationException error)
            when (error.InnerException is not null)
        {
            throw new InvalidOperationException(
                "TnaGraphicDiagramFactory.Build rejected the fixture.",
                error.InnerException);
        }
    }

    private static double Distance(Point3Dto a, Point3Dto b)
    {
        double dx = b.X - a.X;
        double dy = b.Y - a.Y;
        double dz = b.Z - a.Z;
        return Math.Sqrt(dx * dx + dy * dy + dz * dz);
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
