#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

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
}
