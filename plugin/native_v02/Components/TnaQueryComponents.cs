#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Rhino conversion helpers for focused TNA query components.
/// The typed TnaResult remains the source of truth; these methods only create
/// disposable viewport/downstream geometry at the Grasshopper boundary.
/// </summary>
internal static class TnaQueryGeometry
{
    public static void RequireValid(TnaResultDto result)
    {
        IReadOnlyList<string> errors = result.Validate();
        if (errors.Count > 0)
            throw new InvalidOperationException(string.Join(" ", errors));
    }

    public static Point3d Point(Point3Dto value) =>
        new(value.X, value.Y, value.Z);

    public static Vector3d Vector(Point3Dto value) =>
        new(value.X, value.Y, value.Z);

    public static Line ThrustLine(
        TnaResultDto result,
        TnaEdgeStateDto state)
    {
        EquilibriumResultDto equilibrium = result.Equilibrium
            ?? throw new InvalidOperationException(
                "The TNA result has no equilibrium state.");
        EdgeDto edge = equilibrium.Edges[state.EquilibriumEdgeId];
        return new Line(
            Point(equilibrium.Vertices[edge.U]),
            Point(equilibrium.Vertices[edge.V]));
    }

    public static Line FormLine(
        TnaEdgeStateDto state,
        IReadOnlyDictionary<int, TnaGraphEdgeDto> edges,
        IReadOnlyDictionary<int, Point3Dto> points)
    {
        if (!edges.TryGetValue(state.FormEdgeId, out TnaGraphEdgeDto? edge))
        {
            throw new InvalidOperationException(
                $"TNA member {state.Id} references unknown form edge " +
                $"{state.FormEdgeId}.");
        }
        if (!points.TryGetValue(edge.U, out Point3Dto? start) ||
            !points.TryGetValue(edge.V, out Point3Dto? end))
        {
            throw new InvalidOperationException(
                $"Form edge {edge.Id} references an unknown form vertex.");
        }
        return new Line(Point(start), Point(end));
    }

    public static Mesh ThrustMesh(TnaResultDto result)
    {
        EquilibriumResultDto equilibrium = result.Equilibrium
            ?? throw new InvalidOperationException(
                "The TNA result has no equilibrium state.");
        Dictionary<int, int> formToEquilibrium = result.Mappings
            .SourceVertexToFormVertex
            .Where(item =>
                item.FormVertexId.HasValue &&
                item.EquilibriumVertexId.HasValue)
            .GroupBy(item => item.FormVertexId!.Value)
            .ToDictionary(
                group => group.Key,
                group =>
                {
                    int[] equilibriumIds = group
                        .Select(item => item.EquilibriumVertexId!.Value)
                        .Distinct()
                        .ToArray();
                    if (equilibriumIds.Length != 1)
                    {
                        throw new InvalidOperationException(
                            $"Form vertex {group.Key} maps to multiple " +
                            "equilibrium vertices.");
                    }
                    return equilibriumIds[0];
                });

        var mesh = new Mesh();
        var formToMesh = new Dictionary<int, int>();
        foreach (TnaGraphVertexDto vertex in
                 result.FormGraph.Vertices.OrderBy(item => item.Id))
        {
            if (!formToEquilibrium.TryGetValue(
                    vertex.Id,
                    out int equilibriumId))
            {
                throw new InvalidOperationException(
                    $"Form vertex {vertex.Id} has no explicit equilibrium " +
                    "vertex mapping.");
            }
            if (equilibriumId < 0 ||
                equilibriumId >= equilibrium.Vertices.Count)
            {
                throw new InvalidOperationException(
                    $"Form vertex {vertex.Id} has no equilibrium vertex.");
            }
            formToMesh[vertex.Id] = mesh.Vertices.Add(
                Point(equilibrium.Vertices[equilibriumId]));
        }

        foreach (TnaGraphFaceDto face in
                 result.FormGraph.Faces.OrderBy(item => item.Id))
        {
            int[] vertices = face.Vertices
                .Select(id => formToMesh.TryGetValue(id, out int meshId)
                    ? meshId
                    : throw new InvalidOperationException(
                        $"Form face {face.Id} references unknown vertex {id}."))
                .ToArray();
            if (vertices.Length == 3)
            {
                mesh.Faces.AddFace(
                    vertices[0],
                    vertices[1],
                    vertices[2]);
            }
            else if (vertices.Length == 4)
            {
                mesh.Faces.AddFace(
                    vertices[0],
                    vertices[1],
                    vertices[2],
                    vertices[3]);
            }
            else
            {
                for (int index = 1; index < vertices.Length - 1; index++)
                {
                    mesh.Faces.AddFace(
                        vertices[0],
                        vertices[index],
                        vertices[index + 1]);
                }
            }
        }

        if (mesh.Faces.Count > 0)
            mesh.Normals.ComputeNormals();
        mesh.Compact();
        return mesh;
    }

    public static Color ForceColour(string state) =>
        (state ?? string.Empty).Trim().ToLowerInvariant() switch
        {
            "compression" => Color.FromArgb(35, 95, 210),
            "tension" => Color.FromArgb(210, 45, 45),
            "zero" => Color.FromArgb(130, 130, 130),
            _ => Color.FromArgb(45, 45, 45)
        };
}

/// <summary>
/// Compact bridge from a rich TNA state to resolved Rhino geometry. This is
/// intentionally not a replacement for TnaResult and does not unpack member
/// values or nodal actions.
/// </summary>
public sealed class TnaGeometryComponent : NativeComponentBase
{
    public TnaGeometryComponent()
        : base(
            "TNA Geometry",
            "TNA Geometry",
            "Extract the resolved thrust mesh, thrust/form edges, and generic " +
            "equilibrium bridge from one TNA result.",
            ComponentCategories.Query,
            "tna_geometry")
    {
    }

    public override Guid ComponentGuid =>
        new("3943da0e-bb1e-4375-9fa9-8b6e3019aacb");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaResultParam(),
            "TNA Result",
            "R",
            "Final solved TNA state.",
            GH_ParamAccess.item);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddMeshParameter(
            "Thrust Mesh",
            "M",
            "Resolved funicular mesh reconstructed from the active form faces.",
            GH_ParamAccess.item);
        parameters.AddLineParameter(
            "Thrust Edges",
            "T",
            "Resolved spatial member axes aligned with TNA member states.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Form Edges",
            "F",
            "Planar form-diagram edges aligned with TNA member states.",
            GH_ParamAccess.list);
        parameters.AddParameter(
            new EquilibriumResultParam(),
            "Equilibrium",
            "E",
            "Embedded generic equilibrium result for compatibility with " +
            "Equilibrium Preview and focused FD result queries.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TnaResultGoo? goo = null;
        if (!data.GetData(0, ref goo) ||
            goo?.Value is not TnaResultDto result)
        {
            return;
        }

        try
        {
            TnaQueryGeometry.RequireValid(result);
            TnaEdgeStateDto[] states = result.EdgeStates
                .OrderBy(state => state.Id)
                .ToArray();
            IReadOnlyDictionary<int, TnaGraphEdgeDto> formEdges =
                result.FormGraph.Edges.ToDictionary(edge => edge.Id);
            IReadOnlyDictionary<int, Point3Dto> formPoints =
                result.FormGraph.Vertices.ToDictionary(
                    vertex => vertex.Id,
                    vertex => vertex.Point);
            Mesh mesh = TnaQueryGeometry.ThrustMesh(result);
            Line[] thrust = states
                .Select(state => TnaQueryGeometry.ThrustLine(result, state))
                .ToArray();
            Line[] form = states
                .Select(state => TnaQueryGeometry.FormLine(
                    state,
                    formEdges,
                    formPoints))
                .ToArray();

            data.SetData(0, mesh);
            data.SetDataList(1, thrust);
            data.SetDataList(2, form);
            data.SetData(
                3,
                new EquilibriumResultGoo(result.Equilibrium!));
            Message =
                $"{mesh.Vertices.Count}V/{mesh.Faces.Count}F | " +
                $"{thrust.Length} edges";
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("TNA Geometry failed", error);
        }
    }
}

/// <summary>
/// Focused, aligned member deconstruction. Keeping it separate from nodal
/// actions prevents the oversized and unrelated parallel output surface of
/// the legacy Result Breakdown component.
/// </summary>
public sealed class TnaMembersComponent : NativeComponentBase
{
    public TnaMembersComponent()
        : base(
            "TNA Members",
            "TNA Members",
            "Extract one aligned TNA member table: geometry, q, horizontal and " +
            "axial demand, force state, and source-edge groups.",
            ComponentCategories.Query,
            "tna_members")
    {
    }

    public override Guid ComponentGuid =>
        new("f543cb90-bef4-46ea-8510-7aa075c57279");

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaResultParam(),
            "TNA Result",
            "R",
            "Final solved TNA state.",
            GH_ParamAccess.item);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddIntegerParameter(
            "Member IDs",
            "ID",
            "Stable TNA member-state IDs.",
            GH_ParamAccess.list);
        parameters.AddLineParameter(
            "Thrust Lines",
            "L",
            "Resolved member axes aligned with every other output.",
            GH_ParamAccess.list);
        parameters.AddNumberParameter(
            "Force Density",
            "q",
            "Signed force density aligned with Thrust Lines.",
            GH_ParamAccess.list);
        parameters.AddNumberParameter(
            "Horizontal Force",
            "H",
            "Signed horizontal-force demand aligned with Thrust Lines.",
            GH_ParamAccess.list);
        parameters.AddNumberParameter(
            "Axial Force",
            "F",
            "Signed full spatial axial-force demand aligned with Thrust Lines.",
            GH_ParamAccess.list);
        parameters.AddTextParameter(
            "Force State",
            "S",
            "Compression, tension, or zero state aligned with Thrust Lines.",
            GH_ParamAccess.list);
        parameters.AddIntegerParameter(
            "Source Edge IDs",
            "SID",
            "Source-edge IDs grouped by member-state branch.",
            GH_ParamAccess.tree);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TnaResultGoo? goo = null;
        if (!data.GetData(0, ref goo) ||
            goo?.Value is not TnaResultDto result)
        {
            return;
        }

        try
        {
            TnaQueryGeometry.RequireValid(result);
            TnaEdgeStateDto[] states = result.EdgeStates
                .OrderBy(state => state.Id)
                .ToArray();
            data.SetDataList(0, states.Select(state => state.Id));
            data.SetDataList(
                1,
                states.Select(
                    state => TnaQueryGeometry.ThrustLine(result, state)));
            data.SetDataList(2, states.Select(state => state.ForceDensity));
            data.SetDataList(3, states.Select(state => state.HorizontalForce));
            data.SetDataList(4, states.Select(state => state.AxialForce));
            data.SetDataList(5, states.Select(state => state.ForceState));

            var sourceTree = new GH_Structure<GH_Integer>();
            for (int index = 0; index < states.Length; index++)
            {
                GH_Path path = new(states[index].Id);
                foreach (int sourceId in states[index].SourceEdgeIds)
                    sourceTree.Append(new GH_Integer(sourceId), path);
            }
            data.SetDataTree(6, sourceTree);
            Message = $"{states.Length} aligned members";
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("TNA Members failed", error);
        }
    }
}

/// <summary>
/// Focused nodal-action deconstruction. Points and vectors remain paired by
/// output index, and the component itself draws the located arrows.
/// </summary>
public sealed class TnaActionsComponent : NativePreviewComponentBase
{
    private readonly List<Line> _loads = new();
    private readonly List<Line> _reactions = new();
    private BoundingBox _clippingBox = BoundingBox.Empty;

    public TnaActionsComponent()
        : base(
            "TNA Actions",
            "TNA Actions",
            "Extract structural supports plus aligned applied loads and support " +
            "reactions from one TNA result.",
            ComponentCategories.Query,
            "tna_actions")
    {
    }

    public override Guid ComponentGuid =>
        new("0ed716a8-744c-45dc-bc47-98b9e41d2f65");

    public override BoundingBox ClippingBox => _clippingBox;

    protected override void RegisterInputParams(
        GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new TnaResultParam(),
            "TNA Result",
            "R",
            "Final solved TNA state.",
            GH_ParamAccess.item);
        parameters.AddNumberParameter(
            "Vector Scale",
            "VS",
            "Display-only scale for viewport load/reaction arrows.",
            GH_ParamAccess.item,
            1.0);
    }

    protected override void RegisterOutputParams(
        GH_OutputParamManager parameters)
    {
        parameters.AddPointParameter(
            "Support Points",
            "S",
            "Resolved structural-support locations.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Load Points",
            "LP",
            "Points carrying non-zero applied loads.",
            GH_ParamAccess.list);
        parameters.AddVectorParameter(
            "Load Vectors",
            "LV",
            "Physical load vectors aligned with Load Points.",
            GH_ParamAccess.list);
        parameters.AddPointParameter(
            "Reaction Points",
            "RP",
            "Points carrying non-zero support reactions.",
            GH_ParamAccess.list);
        parameters.AddVectorParameter(
            "Reaction Vectors",
            "RV",
            "Physical support reactions aligned with Reaction Points.",
            GH_ParamAccess.list);
    }

    protected override void BeforeSolveInstance()
    {
        base.BeforeSolveInstance();
        _loads.Clear();
        _reactions.Clear();
        _clippingBox = BoundingBox.Empty;
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        TnaResultGoo? goo = null;
        double scale = 1.0;
        if (!data.GetData(0, ref goo) ||
            goo?.Value is not TnaResultDto result)
        {
            return;
        }
        data.GetData(1, ref scale);

        try
        {
            TnaQueryGeometry.RequireValid(result);
            if (!double.IsFinite(scale) || scale <= 0.0)
            {
                throw new ArgumentException(
                    "Vector Scale must be finite and greater than zero.");
            }
            EquilibriumResultDto equilibrium = result.Equilibrium!;

            Point3d[] supports = result.Mappings.Supports
                .Select(item =>
                    TnaQueryGeometry.Point(
                        equilibrium.Vertices[item.EquilibriumVertexId]))
                .ToArray();
            (Point3d Point, Vector3d Vector)[] loads = result.Mappings.Loads
                .Select(item => (
                    TnaQueryGeometry.Point(
                        equilibrium.Vertices[item.EquilibriumVertexId]),
                    TnaQueryGeometry.Vector(item.Vector)))
                .Where(item => item.Item2.SquareLength > 1.0e-24)
                .ToArray();
            (Point3d Point, Vector3d Vector)[] reactions =
                result.Mappings.Reactions
                    .Select(item => (
                        TnaQueryGeometry.Point(
                            equilibrium.Vertices[item.EquilibriumVertexId]),
                        TnaQueryGeometry.Vector(item.Reaction)))
                    .Where(item => item.Item2.SquareLength > 1.0e-24)
                    .ToArray();

            _loads.AddRange(loads.Select(item =>
                new Line(item.Point, item.Point + scale * item.Vector)));
            _reactions.AddRange(reactions.Select(item =>
                new Line(item.Point, item.Point + scale * item.Vector)));
            Point3d[] clipping = supports
                .Concat(_loads.SelectMany(line =>
                    new[] { line.From, line.To }))
                .Concat(_reactions.SelectMany(line =>
                    new[] { line.From, line.To }))
                .ToArray();
            _clippingBox = clipping.Length == 0
                ? BoundingBox.Empty
                : new BoundingBox(clipping);

            data.SetDataList(0, supports);
            data.SetDataList(1, loads.Select(item => item.Point));
            data.SetDataList(2, loads.Select(item => item.Vector));
            data.SetDataList(3, reactions.Select(item => item.Point));
            data.SetDataList(4, reactions.Select(item => item.Vector));
            Message =
                $"{supports.Length} supports | {loads.Length} loads | " +
                $"{reactions.Length} reactions";
        }
        catch (Exception error)
        {
            Message = "Invalid";
            ReportException("TNA Actions failed", error);
        }
    }

    protected override void DrawVisibleViewportWires(IGH_PreviewArgs args)
    {
        foreach (Line line in _loads)
            args.Display.DrawArrow(line, Color.FromArgb(238, 135, 35));
        foreach (Line line in _reactions)
            args.Display.DrawArrow(line, Color.FromArgb(35, 155, 75));
    }
}
