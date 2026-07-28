using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

internal sealed record SnappedTargets(
    IReadOnlyList<int> NodeIds,
    double Tolerance,
    double MaximumDistance);

internal static class TopologyTargets
{
    public static SnappedTargets Resolve(
        TopologyDto topology,
        IReadOnlyList<Point3d> points,
        double? requestedTolerance,
        string label)
    {
        ArgumentNullException.ThrowIfNull(topology);
        ArgumentNullException.ThrowIfNull(points);
        if (topology.Vertices.Count == 0)
            throw new ArgumentException("The topology contains no vertices.");

        double tolerance = requestedTolerance ??
            TopologyTolerance(topology);
        if (!double.IsFinite(tolerance) || tolerance <= 0.0)
        {
            throw new ArgumentException(
                $"{label} snap tolerance must be finite and greater than zero.");
        }

        var ids = new List<int>(points.Count);
        double maximumDistance = 0.0;
        for (int pointIndex = 0; pointIndex < points.Count; pointIndex++)
        {
            Point3d point = points[pointIndex];
            if (!point.IsValid)
                throw new ArgumentException(
                    $"{label} point {pointIndex} is invalid.");

            int nearest = -1;
            double nearestSquared = double.PositiveInfinity;
            for (int nodeId = 0; nodeId < topology.Vertices.Count; nodeId++)
            {
                Point3Dto candidate = topology.Vertices[nodeId];
                double dx = point.X - candidate.X;
                double dy = point.Y - candidate.Y;
                double dz = point.Z - candidate.Z;
                double squared = dx * dx + dy * dy + dz * dz;
                if (squared < nearestSquared)
                {
                    nearestSquared = squared;
                    nearest = nodeId;
                }
            }

            double distance = Math.Sqrt(nearestSquared);
            if (distance > tolerance)
            {
                throw new ArgumentException(
                    $"{label} point {pointIndex} is {distance:G6} from its " +
                    $"nearest topology node, beyond tolerance {tolerance:G6}.");
            }
            ids.Add(nearest);
            maximumDistance = Math.Max(maximumDistance, distance);
        }

        return new SnappedTargets(ids, tolerance, maximumDistance);
    }

    public static double TopologyTolerance(TopologyDto topology)
    {
        if (topology.Provenance.TryGetValue(
                "weld_tolerance",
                out string? text) &&
            double.TryParse(
                text,
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out double tolerance) &&
            double.IsFinite(tolerance) &&
            tolerance > 0.0)
        {
            return tolerance;
        }
        return 1.0e-6;
    }

    public static string JoinSourceIds(
        IEnumerable<string> sourceIds)
    {
        return string.Join(
            "|",
            sourceIds
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.Ordinal));
    }
}
