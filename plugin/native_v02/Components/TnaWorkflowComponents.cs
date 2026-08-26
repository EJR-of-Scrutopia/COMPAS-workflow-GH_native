#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text.Json;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Native Rhino geometry and solve metrics recovered from a unified
/// Result, shared by the solver components' outputs/previews. The mesh
/// construction mirrors the worker's own export: form-graph faces over
/// equilibrium vertices, index-aligned by construction.
/// </summary>
internal static class TnaResultGeometry
{
    internal static Mesh ThrustMesh(ResultDto result)
    {
        var mesh = new Mesh();
        EquilibriumResultDto? equilibrium = result.Equilibrium;
        TnaDiagramGraphDto? formGraph = result.FormGraph;
        TnaMappingsDto? mappings = result.Mappings;
        if (equilibrium is null || formGraph is null || mappings is null)
            return mesh;

        var formToEquilibrium = new Dictionary<int, int>();
        foreach (TnaSourceVertexMappingDto item in
                 mappings.SourceVertexToFormVertex)
        {
            if (item.FormVertexId.HasValue && item.EquilibriumVertexId.HasValue)
                formToEquilibrium[item.FormVertexId.Value] =
                    item.EquilibriumVertexId.Value;
        }

        var formToMesh = new Dictionary<int, int>();
        foreach (TnaGraphVertexDto vertex in
                 formGraph.Vertices.OrderBy(item => item.Id))
        {
            if (!formToEquilibrium.TryGetValue(vertex.Id, out int equilibriumId) ||
                equilibriumId < 0 ||
                equilibriumId >= equilibrium.Vertices.Count)
            {
                return new Mesh();
            }
            formToMesh[vertex.Id] = mesh.Vertices.Add(
                TnaWorkflowPreview.Point(equilibrium.Vertices[equilibriumId]));
        }

        foreach (TnaGraphFaceDto face in formGraph.Faces.OrderBy(item => item.Id))
        {
            int[] corners = new int[face.Vertices.Count];
            for (int index = 0; index < face.Vertices.Count; index++)
            {
                if (!formToMesh.TryGetValue(face.Vertices[index], out int meshId))
                    return new Mesh();
                corners[index] = meshId;
            }
            if (corners.Length == 3)
                mesh.Faces.AddFace(corners[0], corners[1], corners[2]);
            else if (corners.Length == 4)
                mesh.Faces.AddFace(corners[0], corners[1], corners[2], corners[3]);
            else
                for (int index = 1; index < corners.Length - 1; index++)
                    mesh.Faces.AddFace(
                        corners[0], corners[index], corners[index + 1]);
        }

        if (mesh.Faces.Count > 0)
            mesh.Normals.ComputeNormals();
        mesh.Compact();
        return mesh;
    }

    internal static List<Line> MemberLines(ResultDto result)
    {
        var lines = new List<Line>();
        EquilibriumResultDto? equilibrium = result.Equilibrium;
        if (equilibrium is null)
            return lines;
        foreach (EdgeDto edge in equilibrium.Edges)
        {
            lines.Add(new Line(
                TnaWorkflowPreview.Point(equilibrium.Vertices[edge.U]),
                TnaWorkflowPreview.Point(equilibrium.Vertices[edge.V])));
        }
        return lines;
    }

    internal static List<Point3d> SupportPoints(ResultDto result)
    {
        var points = new List<Point3d>();
        EquilibriumResultDto? equilibrium = result.Equilibrium;
        if (equilibrium is null)
            return points;
        if (result.Mappings is not null)
        {
            foreach (TnaSupportMappingDto item in result.Mappings.Reactions)
            {
                int id = item.EquilibriumVertexId;
                if (id >= 0 && id < equilibrium.Vertices.Count)
                    points.Add(TnaWorkflowPreview.Point(
                        equilibrium.Vertices[id]));
            }
            return points;
        }
        foreach (NodalVectorDto item in equilibrium.Reactions)
            points.Add(TnaWorkflowPreview.Point(item.Point));
        return points;
    }

    /// <summary>
    /// Solve metrics parsed out of the worker's own response payload. The
    /// native contract deliberately does not mirror the free-form
    /// diagnostic_metrics dictionary, but the raw wire retains it exactly.
    /// </summary>
    internal static IReadOnlyDictionary<string, double> Metrics(
        ResultDto result)
    {
        var metrics = new Dictionary<string, double>(StringComparer.Ordinal);
        if (string.IsNullOrEmpty(result.RawWire))
            return metrics;
        try
        {
            using JsonDocument document = JsonDocument.Parse(result.RawWire);
            if (!document.RootElement.TryGetProperty(
                    "diagnostic_metrics",
                    out JsonElement element) ||
                element.ValueKind != JsonValueKind.Object)
            {
                return metrics;
            }
            foreach (JsonProperty property in element.EnumerateObject())
            {
                if (property.Value.ValueKind == JsonValueKind.Number &&
                    property.Value.TryGetDouble(out double number))
                {
                    metrics[property.Name] = number;
                }
                else if (property.Value.ValueKind == JsonValueKind.True)
                {
                    metrics[property.Name] = 1.0;
                }
                else if (property.Value.ValueKind == JsonValueKind.False)
                {
                    metrics[property.Name] = 0.0;
                }
            }
        }
        catch (JsonException)
        {
            // The message line degrades gracefully without metrics.
        }
        return metrics;
    }
}

internal static class TnaWorkflowPreview
{
    public static IEnumerable<Line> TopologyLines(TopologyDto topology)
    {
        foreach (EdgeDto edge in topology.Edges)
        {
            yield return new Line(
                Point(topology.Vertices[edge.U]),
                Point(topology.Vertices[edge.V]));
        }
    }

    public static IEnumerable<Line> PatternLines(
        TnaPreparedPatternDto pattern)
    {
        foreach (EdgeDto edge in pattern.Edges)
        {
            yield return new Line(
                Point(pattern.Vertices[edge.U]),
                Point(pattern.Vertices[edge.V]));
        }
    }

    public static IEnumerable<Line> GraphLines(
        TnaDiagramGraphDto graph,
        Vector3d translation)
    {
        var points = graph.Vertices.ToDictionary(
            vertex => vertex.Id,
            vertex => Point(vertex.Point) + translation);
        foreach (TnaGraphEdgeDto edge in graph.Edges)
        {
            if (points.TryGetValue(edge.U, out Point3d from) &&
                points.TryGetValue(edge.V, out Point3d to))
            {
                yield return new Line(from, to);
            }
        }
    }

    public static Vector3d SideBySideTranslation(
        TnaDiagramGraphDto form,
        TnaDiagramGraphDto force,
        double gapRatio = 0.15)
    {
        Point3d[] formPoints = form.Vertices
            .Select(vertex => Point(vertex.Point))
            .ToArray();
        Point3d[] forcePoints = force.Vertices
            .Select(vertex => Point(vertex.Point))
            .ToArray();
        if (formPoints.Length == 0 || forcePoints.Length == 0)
            return Vector3d.Zero;

        var formBox = new BoundingBox(formPoints);
        var forceBox = new BoundingBox(forcePoints);
        double span = Math.Max(
            Math.Max(formBox.Diagonal.X, formBox.Diagonal.Y),
            Math.Max(forceBox.Diagonal.X, forceBox.Diagonal.Y));
        double gap = Math.Max(span * gapRatio, 1.0e-6);
        return new Vector3d(
            formBox.Max.X + gap - forceBox.Min.X,
            formBox.Center.Y - forceBox.Center.Y,
            formBox.Center.Z - forceBox.Center.Z);
    }

    public static BoundingBox Box(
        IEnumerable<Line> lines,
        IEnumerable<Point3d>? extra = null)
    {
        Point3d[] points = lines
            .SelectMany(line => new[] { line.From, line.To })
            .Concat(extra ?? Array.Empty<Point3d>())
            .ToArray();
        return points.Length == 0
            ? BoundingBox.Empty
            : new BoundingBox(points);
    }

    public static Point3d Point(Point3Dto point) =>
        new(point.X, point.Y, point.Z);

    /// <summary>
    /// The principal lines: the notched bars a reconfigurable mould holds
    /// rigid along the net.
    ///
    /// Red, at the same weight as the network they lie on, so the only
    /// distinction is colour. That is deliberate: a bar is a member of the
    /// net, not a highlight laid over it, and drawing it heavier would say
    /// otherwise.
    ///
    /// Every stage draws them from the same source, the vertex runs the
    /// contract carries, resolved once upstream by Supports from the anchors
    /// or by Pattern from drawn curves. So a bar cannot appear at one stage
    /// and be missing at the next, and a definition that carries no runs
    /// draws nothing at all rather than guessing.
    /// </summary>
    public static readonly Color PrincipalColour = Color.FromArgb(205, 45, 45);

    public const int PrincipalWeight = 2;

    public static IEnumerable<Line> PrincipalLines(
        IReadOnlyList<Point3Dto> vertices,
        IReadOnlyList<IReadOnlyList<int>>? runs)
    {
        if (runs is null)
            yield break;
        foreach (IReadOnlyList<int> run in runs)
        {
            if (run is null)
                continue;
            for (int index = 0; index + 1 < run.Count; index++)
            {
                int from = run[index];
                int to = run[index + 1];
                if (from < 0 || from >= vertices.Count ||
                    to < 0 || to >= vertices.Count)
                {
                    continue;
                }
                yield return new Line(
                    Point(vertices[from]),
                    Point(vertices[to]));
            }
        }
    }

    public static IEnumerable<Line> TopologyPrincipalLines(
        TopologyDto? topology) =>
        topology is null
            ? Array.Empty<Line>()
            : PrincipalLines(topology.Vertices, topology.PrincipalRuns);

    /// <summary>
    /// The runs a solved Result carries, drawn on the solved geometry. Read
    /// from the ANALYSIS topology hanging off the equilibrium, because that
    /// is the one whose indices match the equilibrium vertices; the spine
    /// Problem on the Result is in source index space and is the wrong ruler
    /// for these points.
    /// </summary>
    public static IEnumerable<Line> ResultPrincipalLines(ResultDto? result)
    {
        EquilibriumResultDto? equilibrium = result?.Equilibrium;
        return equilibrium is null
            ? Array.Empty<Line>()
            : PrincipalLines(
                equilibrium.Vertices,
                equilibrium.Problem?.Topology?.PrincipalRuns);
    }
}
