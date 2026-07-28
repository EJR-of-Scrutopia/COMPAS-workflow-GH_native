using System;
using System.Collections.Generic;
using System.Linq;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

internal sealed record GeometryTopologyData(
    string Kind,
    IReadOnlyList<Point3d> Vertices,
    IReadOnlyList<(int U, int V)> Edges,
    IReadOnlyList<string> SourceEdgeIds,
    IReadOnlyList<IReadOnlyList<int>> Faces,
    int ConnectedComponents);

/// <summary>
/// Converts Rhino line, polyline, and mesh values into one welded topology.
/// Rhino and Grasshopper values are deliberately removed at this boundary.
/// </summary>
internal static class GeometryTopologyBuilder
{
    public static GeometryTopologyData Build(
        IEnumerable<object> source,
        string? requestedKind,
        double tolerance)
    {
        if (!double.IsFinite(tolerance) || tolerance <= 0.0)
            throw new ArgumentOutOfRangeException(
                nameof(tolerance),
                "Weld tolerance must be a finite number greater than zero.");

        var values = source
            .Where(value => value is not null)
            .Select(Unwrap)
            .Where(value => value is not null)
            .ToArray();
        if (values.Length == 0)
            throw new ArgumentException(
                "Connect at least one line, polyline, or mesh.",
                nameof(source));

        string kind = NormaliseKind(requestedKind, values);
        var welder = new PointWelder(tolerance);
        var edges = new List<(int U, int V)>();
        var sourceEdgeIds = new List<string>();
        var edgeIndices = new Dictionary<(int U, int V), int>();
        var faces = new List<IReadOnlyList<int>>();

        for (int geometryIndex = 0;
             geometryIndex < values.Length;
             geometryIndex++)
        {
            object value = values[geometryIndex];
            switch (value)
            {
                case Mesh mesh:
                    AddMesh(
                        mesh,
                        geometryIndex,
                        welder,
                        edges,
                        sourceEdgeIds,
                        edgeIndices,
                        faces);
                    break;
                case Line line:
                    AddPolyline(
                        new[] { line.From, line.To },
                        geometryIndex,
                        welder,
                        edges,
                        sourceEdgeIds,
                        edgeIndices);
                    break;
                case Polyline polyline:
                    AddPolyline(
                        polyline,
                        geometryIndex,
                        welder,
                        edges,
                        sourceEdgeIds,
                        edgeIndices);
                    break;
                case Curve curve:
                    if (curve.TryGetPolyline(out Polyline curvePolyline))
                    {
                        AddPolyline(
                            curvePolyline,
                            geometryIndex,
                            welder,
                            edges,
                            sourceEdgeIds,
                            edgeIndices);
                    }
                    else
                    {
                        throw new ArgumentException(
                            $"Curve type {curve.GetType().Name} is not a line or polyline. " +
                            "Convert freeform curves to polylines before registration.");
                    }
                    break;
                default:
                    throw new ArgumentException(
                        $"Unsupported geometry type {value.GetType().FullName}. " +
                        "Use lines, polylines, or meshes.");
            }
        }

        if (edges.Count == 0)
            throw new ArgumentException(
                "The supplied geometry did not contain any non-collapsed edges.");
        if (kind == "faced" && faces.Count == 0)
            throw new ArgumentException(
                "Faced topology requires at least one valid mesh face.");

        GeometryTopologyData compacted = Compact(
            kind,
            welder.Points,
            edges,
            sourceEdgeIds,
            kind == "faced"
                ? faces
                : Array.Empty<IReadOnlyList<int>>());
        return new GeometryTopologyData(
            compacted.Kind,
            compacted.Vertices,
            compacted.Edges,
            compacted.SourceEdgeIds,
            compacted.Faces,
            CountConnectedComponents(
                compacted.Vertices.Count,
                compacted.Edges));
    }

    private static object Unwrap(object value)
    {
        if (value is not IGH_Goo goo)
            return value;

        object? unwrapped = goo.ScriptVariable();
        return unwrapped is null || ReferenceEquals(unwrapped, value)
            ? value
            : unwrapped;
    }

    private static string NormaliseKind(
        string? requestedKind,
        IReadOnlyList<object> values)
    {
        string key = (requestedKind ?? "auto")
            .Trim()
            .ToLowerInvariant()
            .Replace(" ", "_");
        key = key switch
        {
            "" or "auto" => values.Any(value => value is Mesh)
                ? "faced"
                : "line",
            "fd" or "lines" or "network" => "line",
            "mesh" or "face" or "faces" or "tna" or "thrust" => "faced",
            _ => key
        };
        if (key is not ("line" or "faced"))
            throw new ArgumentException(
                "Network kind must be Auto, Line, or Faced.",
                nameof(requestedKind));
        return key;
    }

    private static void AddMesh(
        Mesh mesh,
        int geometryIndex,
        PointWelder welder,
        ICollection<(int U, int V)> edges,
        IList<string> sourceEdgeIds,
        IDictionary<(int U, int V), int> edgeIndices,
        ICollection<IReadOnlyList<int>> faces)
    {
        if (mesh.Vertices.Count == 0)
            return;

        var vertexMap = new int[mesh.Vertices.Count];
        for (int index = 0; index < mesh.Vertices.Count; index++)
            vertexMap[index] = welder.Add(mesh.Vertices.Point3dAt(index));

        for (int faceIndex = 0; faceIndex < mesh.Faces.Count; faceIndex++)
        {
            MeshFace face = mesh.Faces[faceIndex];
            int[] local = face.IsTriangle
                ? new[] { face.A, face.B, face.C }
                : new[] { face.A, face.B, face.C, face.D };
            int[] cycle = local
                .Select(index => vertexMap[index])
                .ToArray();
            cycle = RemoveConsecutiveDuplicates(cycle);
            if (cycle.Distinct().Count() < 3)
                continue;

            faces.Add(cycle);
            for (int index = 0; index < cycle.Length; index++)
                AddEdge(
                    cycle[index],
                    cycle[(index + 1) % cycle.Length],
                    $"g{geometryIndex}:f{faceIndex}:s{index}",
                    edges,
                    sourceEdgeIds,
                    edgeIndices);
        }
    }

    private static void AddPolyline(
        IEnumerable<Point3d> source,
        int geometryIndex,
        PointWelder welder,
        ICollection<(int U, int V)> edges,
        IList<string> sourceEdgeIds,
        IDictionary<(int U, int V), int> edgeIndices)
    {
        int? previous = null;
        int segmentIndex = 0;
        foreach (Point3d point in source)
        {
            if (!point.IsValid)
                throw new ArgumentException(
                    "Geometry contains an invalid point coordinate.");

            int current = welder.Add(point);
            if (previous.HasValue)
            {
                AddEdge(
                    previous.Value,
                    current,
                    $"g{geometryIndex}:s{segmentIndex}",
                    edges,
                    sourceEdgeIds,
                    edgeIndices);
                segmentIndex++;
            }
            previous = current;
        }
    }

    private static void AddEdge(
        int u,
        int v,
        string sourceId,
        ICollection<(int U, int V)> edges,
        IList<string> sourceEdgeIds,
        IDictionary<(int U, int V), int> edgeIndices)
    {
        if (u == v)
            return;
        var key = u < v ? (u, v) : (v, u);
        if (edgeIndices.TryGetValue(key, out int existing))
        {
            sourceEdgeIds[existing] = TopologyTargets.JoinSourceIds(
                sourceEdgeIds[existing]
                    .Split('|', StringSplitOptions.RemoveEmptyEntries)
                    .Append(sourceId));
            return;
        }
        edgeIndices.Add(key, edges.Count);
        edges.Add(key);
        sourceEdgeIds.Add(sourceId);
    }

    private static int[] RemoveConsecutiveDuplicates(IReadOnlyList<int> cycle)
    {
        var clean = new List<int>(cycle.Count);
        foreach (int value in cycle)
        {
            if (clean.Count == 0 || clean[^1] != value)
                clean.Add(value);
        }
        if (clean.Count > 1 && clean[0] == clean[^1])
            clean.RemoveAt(clean.Count - 1);
        return clean.ToArray();
    }

    /// <summary>
    /// Remove welded points that do not participate in a member and remap all
    /// indices. COMPAS registers networks from edge endpoints, so retaining
    /// isolated Rhino mesh/polyline points here would make downstream node IDs
    /// differ from the IDs returned by the Python solver.
    /// </summary>
    private static GeometryTopologyData Compact(
        string kind,
        IReadOnlyList<Point3d> vertices,
        IReadOnlyList<(int U, int V)> edges,
        IReadOnlyList<string> sourceEdgeIds,
        IReadOnlyList<IReadOnlyList<int>> faces)
    {
        int[] used = edges
            .SelectMany(edge => new[] { edge.U, edge.V })
            .Distinct()
            .ToArray();
        var remap = used
            .Select((oldIndex, newIndex) => (oldIndex, newIndex))
            .ToDictionary(item => item.oldIndex, item => item.newIndex);

        Point3d[] compactVertices = used
            .Select(index => vertices[index])
            .ToArray();
        (int U, int V)[] compactEdges = edges
            .Select(edge => (remap[edge.U], remap[edge.V]))
            .ToArray();
        IReadOnlyList<int>[] compactFaces = faces
            .Select(face =>
                (IReadOnlyList<int>)face.Select(index => remap[index]).ToArray())
            .ToArray();

        return new GeometryTopologyData(
            kind,
            compactVertices,
            compactEdges,
            sourceEdgeIds.ToArray(),
            compactFaces,
            0);
    }

    private static int CountConnectedComponents(
        int vertexCount,
        IReadOnlyCollection<(int U, int V)> edges)
    {
        var adjacency = Enumerable
            .Range(0, vertexCount)
            .Select(_ => new List<int>())
            .ToArray();
        foreach ((int u, int v) in edges)
        {
            adjacency[u].Add(v);
            adjacency[v].Add(u);
        }

        int count = 0;
        var visited = new bool[vertexCount];
        var pending = new Stack<int>();
        for (int start = 0; start < vertexCount; start++)
        {
            if (visited[start] || adjacency[start].Count == 0)
                continue;

            count++;
            pending.Push(start);
            while (pending.Count > 0)
            {
                int current = pending.Pop();
                if (visited[current])
                    continue;
                visited[current] = true;
                foreach (int neighbour in adjacency[current])
                    if (!visited[neighbour])
                        pending.Push(neighbour);
            }
        }
        return count;
    }

    private sealed class PointWelder
    {
        private readonly double _tolerance;
        private readonly double _toleranceSquared;
        private readonly Dictionary<Cell, List<int>> _cells = new();

        public PointWelder(double tolerance)
        {
            _tolerance = tolerance;
            _toleranceSquared = tolerance * tolerance;
        }

        public List<Point3d> Points { get; } = new();

        public int Add(Point3d point)
        {
            if (!point.IsValid)
                throw new ArgumentException(
                    "Geometry contains an invalid point coordinate.");

            var cell = Cell.From(point, _tolerance);
            for (long dx = -1; dx <= 1; dx++)
            for (long dy = -1; dy <= 1; dy++)
            for (long dz = -1; dz <= 1; dz++)
            {
                var neighbour = new Cell(
                    cell.X + dx,
                    cell.Y + dy,
                    cell.Z + dz);
                if (!_cells.TryGetValue(neighbour, out List<int>? candidates))
                    continue;
                foreach (int index in candidates)
                    if (Points[index].DistanceToSquared(point) <= _toleranceSquared)
                        return index;
            }

            int added = Points.Count;
            Points.Add(point);
            if (!_cells.TryGetValue(cell, out List<int>? bucket))
            {
                bucket = new List<int>();
                _cells.Add(cell, bucket);
            }
            bucket.Add(added);
            return added;
        }
    }

    private readonly record struct Cell(long X, long Y, long Z)
    {
        public static Cell From(Point3d point, double size)
        {
            return new Cell(
                checked((long)Math.Floor(point.X / size)),
                checked((long)Math.Floor(point.Y / size)),
                checked((long)Math.Floor(point.Z / size)));
        }
    }
}
