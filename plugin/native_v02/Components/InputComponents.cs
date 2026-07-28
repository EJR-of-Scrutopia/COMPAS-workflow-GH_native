using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

public sealed class NetworkComponent : NativeComponentBase
{
    public NetworkComponent()
        : base(
            "Network",
            "Network",
            "Register lines, polylines, or meshes as one welded topology.",
            ComponentCategories.Model,
            "network")
    {
    }

    public override Guid ComponentGuid =>
        new("a9f470fc-e1a8-46c4-ba4c-d7fbe515b161");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddGenericParameter(
            "Geometry",
            "G",
            "Lines, polylines, or meshes. All input branches are flattened " +
            "and welded into one topology.",
            GH_ParamAccess.list);
        parameters[0].DataMapping = GH_DataMapping.Flatten;
        parameters.AddTextParameter(
            "Kind",
            "K",
            "Auto, Line (FD), or Faced (TNA).",
            GH_ParamAccess.item,
            "Auto");
        parameters.AddNumberParameter(
            "Weld Tolerance",
            "Tol",
            "Maximum point distance used to weld topology vertices.",
            GH_ParamAccess.item,
            1.0e-6);
        parameters.AddTextParameter(
            "Length Unit",
            "LU",
            "Metadata label for the coordinates, for example m. " +
            "No numeric unit conversion is performed.",
            GH_ParamAccess.item,
            "m");
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new TopologyParam(),
            "Topology",
            "T",
            "One immutable whole-object topology.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        var geometry = new List<object>();
        string kind = "Auto";
        double tolerance = 1.0e-6;
        string lengthUnit = "m";
        if (!data.GetDataList(0, geometry))
            return;
        data.GetData(1, ref kind);
        data.GetData(2, ref tolerance);
        data.GetData(3, ref lengthUnit);

        try
        {
            GeometryTopologyData registered =
                GeometryTopologyBuilder.Build(geometry, kind, tolerance);
            string unit = (lengthUnit ?? string.Empty).Trim();
            if (unit.Length == 0)
                throw new ArgumentException("Length Unit cannot be empty.");

            var provenance = new Dictionary<string, string>(
                StringComparer.Ordinal)
            {
                ["source"] = "Rhino/Grasshopper",
                ["weld_tolerance"] =
                    tolerance.ToString("R", CultureInfo.InvariantCulture),
                ["connected_components"] =
                    registered.ConnectedComponents.ToString(
                        CultureInfo.InvariantCulture)
            };
            TopologyDto topology = TopologyDto.Create(
                registered.Kind,
                registered.Vertices.Select(ToPoint),
                registered.Edges.Select(edge => new EdgeDto(edge.U, edge.V)),
                registered.Faces,
                sourceVertexIds: Enumerable.Range(
                    0,
                    registered.Vertices.Count).Select(index => $"v{index}"),
                sourceEdgeIds: registered.SourceEdgeIds,
                lengthUnit: unit,
                provenance: provenance);
            EnsureValid(topology);

            if (registered.ConnectedComponents > 1)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"The topology contains {registered.ConnectedComponents} " +
                    "disconnected components. Every component needs a support.");
            }

            Message =
                $"{topology.NetworkKind} · {topology.Vertices.Count}V/" +
                $"{topology.Edges.Count}E";
            data.SetData(0, new TopologyGoo(topology));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Network registration failed", error);
        }
    }

    private static Point3Dto ToPoint(Point3d point) =>
        new(point.X, point.Y, point.Z);

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}

public sealed class SupportSetComponent : NativeComponentBase
{
    public SupportSetComponent()
        : base(
            "Support Set",
            "Supports",
            "Bundle form-finding supports for one registered topology.",
            ComponentCategories.Model,
            "support_set")
    {
    }

    public override Guid ComponentGuid =>
        new("73b719d9-9b24-4086-a023-a06313f4dd17");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TopologyParam(),
            "Topology",
            "T",
            "Topology to which the supports belong.",
            GH_ParamAccess.item);
        parameters.AddPointParameter(
            "Points",
            "P",
            "Support locations to snap to topology nodes.",
            GH_ParamAccess.list);
        parameters.AddIntegerParameter(
            "Node IDs",
            "ID",
            "Explicit zero-based topology node IDs.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Mode",
            "M",
            "Explicit, Terminals, or Boundary. Corner detection is not yet " +
            "available in the native workflow.",
            GH_ParamAccess.item,
            "Explicit");
        parameters.AddNumberParameter(
            "Snap Tolerance",
            "Tol",
            "Optional maximum support-point snapping distance.",
            GH_ParamAccess.item);

        parameters[1].DataMapping = GH_DataMapping.Flatten;
        parameters[2].DataMapping = GH_DataMapping.Flatten;
        parameters[1].Optional = true;
        parameters[2].Optional = true;
        parameters[4].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new SupportSetParam(),
            "Supports",
            "S",
            "Topology-bound form-finding supports.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TopologyGoo? topologyGoo = null;
        var points = new List<Point3d>();
        var nodeIds = new List<int>();
        string mode = "Explicit";
        double snap = 0.0;
        if (!data.GetData(0, ref topologyGoo) ||
            topologyGoo?.Value is not TopologyDto topology)
        {
            return;
        }
        data.GetDataList(1, points);
        data.GetDataList(2, nodeIds);
        data.GetData(3, ref mode);
        bool hasSnap = data.GetData(4, ref snap);

        try
        {
            if (points.Count > 0 && nodeIds.Count > 0)
            {
                throw new ArgumentException(
                    "Connect support Points or Node IDs, not both.");
            }
            string supportMode = NormaliseSupportMode(mode);
            if (supportMode != "explicit" &&
                (points.Count > 0 || nodeIds.Count > 0))
            {
                throw new ArgumentException(
                    "Terminals and Boundary select nodes automatically. " +
                    "Remove Points/Node IDs or use Explicit mode.");
            }
            if (nodeIds.Any(id => id < 0 || id >= topology.Vertices.Count))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(nodeIds),
                    "A support Node ID lies outside the topology.");
            }
            SnappedTargets snapped = TopologyTargets.Resolve(
                topology,
                points,
                hasSnap ? snap : null,
                "Support");
            int[] resolvedNodeIds = points.Count > 0
                ? snapped.NodeIds.Distinct().ToArray()
                : nodeIds.Distinct().ToArray();

            var supports = new SupportSetDto
            {
                TopologyHash = topology.TopologyHash,
                Mode = supportMode,
                Points = Array.Empty<Point3Dto>(),
                NodeIds = resolvedNodeIds,
                SnapTolerance = points.Count > 0
                    ? snapped.Tolerance
                    : hasSnap
                        ? snap
                        : null,
                Provenance = new Dictionary<string, string>
                {
                    ["source"] = "Grasshopper",
                    ["point_targets_resolved"] =
                        (points.Count > 0).ToString().ToLowerInvariant(),
                    ["maximum_snap_distance"] =
                        snapped.MaximumDistance.ToString(
                            "R",
                            CultureInfo.InvariantCulture)
                }
            };
            EnsureValid(supports);
            Message =
                $"{supports.Mode} · " +
                $"{Math.Max(supports.Points.Count, supports.NodeIds.Count)}";
            data.SetData(0, new SupportSetGoo(supports));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Support Set failed", error);
        }
    }

    private static string NormaliseSupportMode(string? value)
    {
        string mode = (value ?? "explicit")
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_");
        return mode switch
        {
            "ids" or "points" => "explicit",
            "all_boundary" => "boundary",
            "corners" or "boundary_corners" => throw new ArgumentException(
                "Corners is not implemented yet. Use Boundary or provide " +
                "explicit corner points/node IDs."),
            _ => mode
        };
    }

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}

public sealed class LoadCaseComponent : NativeComponentBase
{
    public LoadCaseComponent()
        : base(
            "Load Case",
            "Loads",
            "Bundle one named, topology-bound form-finding load case.",
            ComponentCategories.Model,
            "load_case")
    {
    }

    public override Guid ComponentGuid =>
        new("1ba4e155-b5e5-4043-89b3-e062a8e72fb5");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TopologyParam(),
            "Topology",
            "T",
            "Topology to which the loads belong.",
            GH_ParamAccess.item);
        parameters.AddPointParameter(
            "Points",
            "P",
            "Load application locations to snap to topology nodes.",
            GH_ParamAccess.list);
        parameters.AddIntegerParameter(
            "Node IDs",
            "ID",
            "Explicit zero-based topology load-node IDs.",
            GH_ParamAccess.list);
        parameters.AddVectorParameter(
            "Vectors",
            "V",
            "One vector to broadcast or one vector per target.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Distribution",
            "D",
            "Point, Uniform Nodes, or Custom. Tributary-area and self-weight " +
            "generation are not yet implemented.",
            GH_ParamAccess.item,
            "Point");
        parameters.AddTextParameter(
            "Name",
            "N",
            "Unique load-case name.",
            GH_ParamAccess.item,
            "equilibrium");
        parameters.AddNumberParameter(
            "Factor",
            "F",
            "Multiplier applied to all input vectors.",
            GH_ParamAccess.item,
            1.0);
        parameters.AddTextParameter(
            "Force Unit",
            "FU",
            "Metadata label for load vectors, for example kN. " +
            "No numeric unit conversion is performed.",
            GH_ParamAccess.item,
            "kN");
        parameters.AddNumberParameter(
            "Snap Tolerance",
            "Tol",
            "Maximum distance for resolving load Points to stable topology " +
            "node IDs. Defaults to the Network weld tolerance.",
            GH_ParamAccess.item);

        parameters[1].DataMapping = GH_DataMapping.Flatten;
        parameters[2].DataMapping = GH_DataMapping.Flatten;
        parameters[3].DataMapping = GH_DataMapping.Flatten;
        parameters[1].Optional = true;
        parameters[2].Optional = true;
        parameters[8].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new LoadCaseParam(),
            "Load Case",
            "L",
            "Named topology-bound load data.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TopologyGoo? topologyGoo = null;
        var points = new List<Point3d>();
        var nodeIds = new List<int>();
        var vectors = new List<Vector3d>();
        string distribution = "Point";
        string name = "equilibrium";
        double factor = 1.0;
        string forceUnit = "kN";
        double snap = 0.0;
        if (!data.GetData(0, ref topologyGoo) ||
            topologyGoo?.Value is not TopologyDto topology)
        {
            return;
        }
        data.GetDataList(1, points);
        data.GetDataList(2, nodeIds);
        if (!data.GetDataList(3, vectors))
            return;
        data.GetData(4, ref distribution);
        data.GetData(5, ref name);
        data.GetData(6, ref factor);
        data.GetData(7, ref forceUnit);
        bool hasSnap = data.GetData(8, ref snap);

        try
        {
            if (!double.IsFinite(factor))
                throw new ArgumentException("Load Factor must be finite.");
            if (points.Count > 0 && nodeIds.Count > 0)
            {
                throw new ArgumentException(
                    "Connect load Points or Node IDs, not both.");
            }
            if (nodeIds.Any(id => id < 0 || id >= topology.Vertices.Count))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(nodeIds),
                    "A load Node ID lies outside the topology.");
            }
            if (vectors.Any(vector => !vector.IsValid))
                throw new ArgumentException(
                    "A load Vector contains invalid coordinates.");

            SnappedTargets snapped = TopologyTargets.Resolve(
                topology,
                points,
                hasSnap ? snap : null,
                "Load");
            int[] resolvedNodeIds = points.Count > 0
                ? snapped.NodeIds.ToArray()
                : nodeIds.ToArray();

            string mode = NormaliseDistribution(distribution);
            int targetCount = resolvedNodeIds.Length;
            if (vectors.Count == 0)
                throw new ArgumentException("Connect at least one load Vector.");
            if (targetCount > 0 &&
                vectors.Count != 1 &&
                vectors.Count != targetCount)
            {
                throw new ArgumentException(
                    "Vectors must contain one item or one item per load target.");
            }
            if (targetCount == 0 && vectors.Count != 1)
            {
                throw new ArgumentException(
                    "A target-free distribution accepts one base Vector.");
            }

            Point3Dto[] factored = vectors
                .Select(vector => new Point3Dto(
                    factor * vector.X,
                    factor * vector.Y,
                    factor * vector.Z))
                .ToArray();
            if (factored.Any(vector =>
                    !double.IsFinite(vector.X) ||
                    !double.IsFinite(vector.Y) ||
                    !double.IsFinite(vector.Z)))
            {
                throw new ArgumentException(
                    "Factored load vectors must remain finite.");
            }
            string unit = (forceUnit ?? string.Empty).Trim();
            if (unit.Length == 0)
                throw new ArgumentException("Force Unit cannot be empty.");

            var loadCase = new LoadCaseDto
            {
                TopologyHash = topology.TopologyHash,
                Name = (name ?? string.Empty).Trim(),
                Distribution = mode,
                Points = Array.Empty<Point3Dto>(),
                NodeIds = resolvedNodeIds,
                Vectors = targetCount > 0
                    ? factored
                    : Array.Empty<Point3Dto>(),
                BaseVector = targetCount == 0 ? factored[0] : null,
                // The native component stores effective vectors so every
                // downstream consumer sees one unambiguous load value.
                Factor = 1.0,
                CoordinateSystem = "world",
                Provenance = new Dictionary<string, string>
                {
                    ["source"] = "Grasshopper",
                    ["force_unit"] = unit,
                    ["input_factor"] =
                        factor.ToString("R", CultureInfo.InvariantCulture),
                    ["vectors_factored"] = "true",
                    ["point_targets_resolved"] =
                        (points.Count > 0).ToString().ToLowerInvariant(),
                    ["snap_tolerance"] =
                        snapped.Tolerance.ToString(
                            "R",
                            CultureInfo.InvariantCulture),
                    ["maximum_snap_distance"] =
                        snapped.MaximumDistance.ToString(
                            "R",
                            CultureInfo.InvariantCulture)
                }
            };
            EnsureValid(loadCase);
            Message = $"{loadCase.Name} · {loadCase.Distribution}";
            data.SetData(0, new LoadCaseGoo(loadCase));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Load Case failed", error);
        }
    }

    private static string NormaliseDistribution(string? value)
    {
        string mode = (value ?? "point")
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_");
        return mode switch
        {
            "points" => "point",
            "uniform" or "nodes" => "uniform_nodes",
            "area" or "tributary" or "tributary_area" =>
                throw new ArgumentException(
                    "Tributary Area is not implemented yet. Supply explicit " +
                    "nodal vectors with Point or Custom."),
            "selfweight" or "self_weight" => throw new ArgumentException(
                "Self Weight is not implemented yet. Supply explicit nodal " +
                "vectors with Point or Custom."),
            _ => mode
        };
    }

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}

public sealed class EquilibriumProblemComponent : NativeComponentBase
{
    public EquilibriumProblemComponent()
        : base(
            "Equilibrium Problem",
            "Problem",
            "Bundle topology, supports, and named loads for a solver.",
            ComponentCategories.Model,
            "equilibrium_problem")
    {
    }

    public override Guid ComponentGuid =>
        new("24868635-057b-4926-92d9-ec9a76bcf451");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TopologyParam(),
            "Topology",
            "T",
            "Registered whole-object topology.",
            GH_ParamAccess.item);
        parameters.AddParameter(
            new SupportSetParam(),
            "Supports",
            "S",
            "Form-finding support set.",
            GH_ParamAccess.item);
        parameters.AddParameter(
            new LoadCaseParam(),
            "Load Cases",
            "L",
            "One or more uniquely named load cases.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Name",
            "N",
            "Problem name.",
            GH_ParamAccess.item,
            "equilibrium");
        parameters[2].DataMapping = GH_DataMapping.Flatten;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new EquilibriumProblemParam(),
            "Problem",
            "P",
            "Validated solver-neutral equilibrium problem.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TopologyGoo? topologyGoo = null;
        SupportSetGoo? supportsGoo = null;
        var loadGoos = new List<LoadCaseGoo>();
        string name = "equilibrium";
        if (!data.GetData(0, ref topologyGoo) ||
            topologyGoo?.Value is not TopologyDto topology ||
            !data.GetData(1, ref supportsGoo) ||
            supportsGoo?.Value is not SupportSetDto supports ||
            !data.GetDataList(2, loadGoos))
        {
            return;
        }
        data.GetData(3, ref name);

        try
        {
            LoadCaseDto[] loads = loadGoos
                .Where(goo => goo?.Value is not null)
                .Select(goo => goo.Value)
                .ToArray();
            var problem = new EquilibriumProblemDto
            {
                Name = (name ?? string.Empty).Trim(),
                Topology = topology,
                Supports = supports,
                LoadCases = loads,
                Provenance = new Dictionary<string, string>
                {
                    ["source"] = "Grasshopper"
                }
            };
            EnsureValid(problem);
            Message =
                $"{topology.NetworkKind} · {topology.Edges.Count} members";
            data.SetData(0, new EquilibriumProblemGoo(problem));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("Equilibrium Problem failed", error);
        }
    }

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}

public sealed class FDSettingsComponent : NativeComponentBase
{
    public FDSettingsComponent()
        : base(
            "FD Settings",
            "FD Settings",
            "Bundle scalar or member-aligned force densities.",
            ComponentCategories.FormFinding,
            "fd_settings")
    {
    }

    public override Guid ComponentGuid =>
        new("9de76173-8146-4b52-98d0-a0cc1c3d120a");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddNumberParameter(
            "Force Densities",
            "q",
            "One value broadcasts to all members; otherwise provide one per " +
            "member. Numeric units are Force Unit per Length Unit.",
            GH_ParamAccess.list);
        parameters[0].DataMapping = GH_DataMapping.Flatten;
        parameters[0].Optional = true;
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddParameter(
            new FDSettingsParam(),
            "Settings",
            "S",
            "Reusable force-density settings.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        var forceDensities = new List<double>();
        data.GetDataList(0, forceDensities);
        if (forceDensities.Count == 0)
            forceDensities.Add(1.0);

        try
        {
            var settings = new FDSettingsDto
            {
                ForceDensities = forceDensities.ToArray(),
                SignConvention = "positive_tension",
                Provenance = new Dictionary<string, string>
                {
                    ["source"] = "Grasshopper"
                }
            };
            EnsureValid(settings);
            Message = forceDensities.Count == 1
                ? $"q={forceDensities[0]:G6}"
                : $"{forceDensities.Count} q values";
            data.SetData(0, new FDSettingsGoo(settings));
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("FD Settings failed", error);
        }
    }

    private static void EnsureValid(ContractDto contract)
    {
        IReadOnlyList<string> errors = contract.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }
}
