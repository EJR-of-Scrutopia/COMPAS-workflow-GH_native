#nullable enable

using System;
using System.Collections.Generic;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// The line field the force-aligned pattern's head joints follow (spec
/// 2026-09-01 section 3.2a), computed natively. The arithmetic is taken from
/// the shipped Python worker and cited rule by rule; the OUTPUT is not
/// comparable with it and must not be validated against it, because the two
/// sides triangulate differently (rule 3.5.1).
///
/// Nothing here may reference RhinoCommon, the rule the harness's whole
/// ability to measure the engine rests on.
/// </summary>
internal static class SkinFlowField
{
    /// <summary>Rule 3.2.5. Each triangle carries its own orthonormal plane
    /// basis: e1 is the first edge normalised, the normal is the normalised
    /// cross product of the first two edges falling back to (0, 0, 1) where
    /// it degenerates, and e2 is the cross product of normal and e1. Every
    /// direction lives in its own face's (e1, e2) and never in a shared
    /// world frame.</summary>
    private static (double[] E1, double[] E2, double[] Normal) Basis(
        SkinNet net,
        int[] face)
    {
        double[] a = net.Vertices[face[0]];
        double[] b = net.Vertices[face[1]];
        double[] c = net.Vertices[face[2]];
        double[] first = { b[0] - a[0], b[1] - a[1], b[2] - a[2] };
        double[] second = { c[0] - a[0], c[1] - a[1], c[2] - a[2] };
        double[] normal =
        {
            first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0]
        };
        double normalLength = Length(normal);
        normal = normalLength > 1.0e-12
            ? Scale(normal, 1.0 / normalLength)
            : new[] { 0.0, 0.0, 1.0 };
        double firstLength = Length(first);
        double[] e1 = firstLength > 1.0e-12
            ? Scale(first, 1.0 / firstLength)
            : new[] { 1.0, 0.0, 0.0 };
        double[] e2 =
        {
            normal[1] * e1[2] - normal[2] * e1[1],
            normal[2] * e1[0] - normal[0] * e1[2],
            normal[0] * e1[1] - normal[1] * e1[0]
        };
        return (e1, e2, normal);
    }

    private static double Length(double[] vector) =>
        Math.Sqrt(
            vector[0] * vector[0] +
            vector[1] * vector[1] +
            vector[2] * vector[2]);

    private static double[] Scale(double[] vector, double by) =>
        new[] { vector[0] * by, vector[1] * by, vector[2] * by };

    /// <summary>Rule 3.2.6. A unit plane direction is carried as
    /// (dx dx - dy dy, 2 dx dy), which is (cos 2 theta, sin 2 theta): a line
    /// and its negation are the same line, and doubling is what makes an
    /// average of lines mean anything at all.</summary>
    private static (double X, double Y) Double(double dx, double dy) =>
        (dx * dx - dy * dy, 2.0 * dx * dy);

    /// <summary>Rule 3.2.6's inverse, returning (1, 0) where the magnitude
    /// is at or below 1e-12.</summary>
    private static (double X, double Y) Undouble(double x, double y)
    {
        if (Math.Sqrt(x * x + y * y) <= 1.0e-12)
            return (1.0, 0.0);
        double half = Math.Atan2(y, x) / 2.0;
        return (Math.Cos(half), Math.Sin(half));
    }

    /// <summary>
    /// Rules 3.2.7 to 3.2.9: the raw per-face direction weighted by member
    /// force, its coherence, the (1, 0) fallback, and EXACTLY THREE
    /// neighbour-averaging passes, which is a constant and not an input.
    /// </summary>
    public static IReadOnlyList<double[]> Directions(SkinNet net)
    {
        (double[] Plane, double Coherence)[] state = Raw(net);
        var bases = new (double[] E1, double[] E2, double[] Normal)[
            net.Faces.Count];
        for (int face = 0; face < net.Faces.Count; face++)
            bases[face] = Basis(net, net.Faces[face]);
        var neighbours = Neighbours(net);
        // The coherence used in the weight is the RAW coherence, fixed from
        // the unsmoothed field and never recomputed between passes.
        // Weighting every neighbour by its raw coherence instead, without
        // the clamp, was tried and measured: it discounts the ninety-two per
        // cent of ordinary faces along with the eight per cent meant,
        // changes every face's final direction and regresses the vault's own
        // bars. Do not.
        double[] coherence = new double[net.Faces.Count];
        var current = new double[net.Faces.Count][];
        for (int face = 0; face < net.Faces.Count; face++)
        {
            coherence[face] = state[face].Coherence;
            current[face] = state[face].Plane;
        }
        for (int pass = 0; pass < 3; pass++)
        {
            var next = new double[net.Faces.Count][];
            for (int face = 0; face < net.Faces.Count; face++)
            {
                (double[] e1, double[] e2, double[] normal) = bases[face];
                double x = 0.0;
                double y = 0.0;
                (double px, double py) = Project(current[face], e1, e2);
                (double dx, double dy) = Double(px, py);
                x += dx;
                y += dy;
                foreach (int other in neighbours[face])
                {
                    double[] world = current[other];
                    double dot =
                        world[0] * normal[0] +
                        world[1] * normal[1] +
                        world[2] * normal[2];
                    double[] flattened =
                    {
                        world[0] - normal[0] * dot,
                        world[1] - normal[1] * dot,
                        world[2] - normal[2] * dot
                    };
                    double flatLength = Length(flattened);
                    if (flatLength <= 1.0e-12)
                        continue;
                    (double ox, double oy) = Project(
                        Scale(flattened, 1.0 / flatLength), e1, e2);
                    double planeLength = Math.Sqrt(ox * ox + oy * oy);
                    if (planeLength <= 1.0e-12)
                        continue;
                    ox /= planeLength;
                    oy /= planeLength;
                    double weight = Math.Min(1.0, coherence[other] / 0.2);
                    (double ddx, double ddy) = Double(ox, oy);
                    x += weight * ddx;
                    y += weight * ddy;
                }
                (double ux, double uy) = Undouble(x, y);
                next[face] = new[]
                {
                    e1[0] * ux + e2[0] * uy,
                    e1[1] * ux + e2[1] * uy,
                    e1[2] * ux + e2[2] * uy
                };
            }
            current = next;
        }
        return current;
    }

    public static IReadOnlyList<double> Coherences(SkinNet net)
    {
        (double[] Plane, double Coherence)[] state = Raw(net);
        var read = new double[state.Length];
        for (int face = 0; face < state.Length; face++)
            read[face] = state[face].Coherence;
        return read;
    }

    private static (double X, double Y) Project(
        double[] world,
        double[] e1,
        double[] e2) =>
        (world[0] * e1[0] + world[1] * e1[1] + world[2] * e1[2],
         world[0] * e2[0] + world[1] * e2[1] + world[2] * e2[2]);

    /// <summary>Rule 3.2.7's raw per-face direction and its coherence, and
    /// rule 3.2.8's fallback: a face NONE of whose edges carries a weight
    /// takes the direction (1, 0), which is its own e1, and reports
    /// coherence 1.0, so that a fixed default is never discounted as though
    /// it were a contested vote.</summary>
    private static (double[] Plane, double Coherence)[] Raw(SkinNet net)
    {
        var forceOf = new Dictionary<(int, int), double>();
        foreach (SkinNetEdge edge in net.Edges)
            forceOf[(edge.A, edge.B)] = edge.Force;
        var read = new (double[], double)[net.Faces.Count];
        for (int face = 0; face < net.Faces.Count; face++)
        {
            int[] triangle = net.Faces[face];
            (double[] e1, double[] e2, double[] _) = Basis(net, triangle);
            double x = 0.0;
            double y = 0.0;
            double weight = 0.0;
            for (int corner = 0; corner < triangle.Length; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % triangle.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                if (!forceOf.TryGetValue(key, out double force) ||
                    Math.Abs(force) <= 1.0e-12)
                {
                    continue;
                }
                double[] from = net.Vertices[key.Item1];
                double[] to = net.Vertices[key.Item2];
                double[] along =
                    { to[0] - from[0], to[1] - from[1], to[2] - from[2] };
                double alongLength = Length(along);
                if (alongLength <= 1.0e-12)
                    continue;
                (double px, double py) = Project(
                    Scale(along, 1.0 / alongLength), e1, e2);
                double planeLength = Math.Sqrt(px * px + py * py);
                if (planeLength <= 1.0e-12)
                    continue;
                (double dx, double dy) = Double(
                    px / planeLength, py / planeLength);
                x += Math.Abs(force) * dx;
                y += Math.Abs(force) * dy;
                weight += Math.Abs(force);
            }
            if (!(weight > 0.0))
            {
                read[face] = (e1, 1.0);
                continue;
            }
            (double ux, double uy) = Undouble(x, y);
            read[face] = (
                new[]
                {
                    e1[0] * ux + e2[0] * uy,
                    e1[1] * ux + e2[1] * uy,
                    e1[2] * ux + e2[2] * uy
                },
                Math.Sqrt(x * x + y * y) / weight);
        }
        return read;
    }

    /// <summary>Every face's neighbours across a shared triangle edge.
    /// Public to the file because the advection walk of rule 3.2.10 needs
    /// the same adjacency.</summary>
    internal static IReadOnlyList<int>[] Neighbours(SkinNet net)
    {
        var byEdge = new Dictionary<(int, int), List<int>>();
        for (int face = 0; face < net.Faces.Count; face++)
        {
            int[] triangle = net.Faces[face];
            for (int corner = 0; corner < triangle.Length; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % triangle.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                if (!byEdge.TryGetValue(key, out List<int>? owners))
                    byEdge[key] = owners = new List<int>();
                owners.Add(face);
            }
        }
        var read = new IReadOnlyList<int>[net.Faces.Count];
        for (int face = 0; face < net.Faces.Count; face++)
        {
            var found = new List<int>();
            int[] triangle = net.Faces[face];
            for (int corner = 0; corner < triangle.Length; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % triangle.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                foreach (int owner in byEdge[key])
                {
                    if (owner != face)
                        found.Add(owner);
                }
            }
            read[face] = found;
        }
        return read;
    }
}
