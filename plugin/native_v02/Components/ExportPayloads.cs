#nullable enable

using System;
using System.Collections.Generic;
using System.Text.Json;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// What a Result can be exported as. Every Result is a contract and a
/// COMPAS document; with cells wired it is also a tessellation sidecar,
/// and with columns in its Mould block a columns mesh. Export writes what
/// the Result can be rather than asking which one.
/// </summary>
internal static class ExportPlan
{
    public static string[] Kinds(bool hasCells, bool hasColumns)
    {
        var kinds = new List<string> { "contract", "compas" };
        if (hasCells)
            kinds.Add("tessellation");
        if (hasColumns)
            kinds.Add("columns");
        return kinds.ToArray();
    }
}

/// <summary>
/// The columns as a mesh the studio renders today: one closed prism per
/// member, six side quads and two triangle-fanned caps, at the radius
/// asked. The members themselves travel beside the mesh so a later
/// studio can draw them in its own material from lines and a radius.
/// Pure arithmetic: the harness builds it without Rhino.
/// </summary>
internal static class ColumnsMesh
{
    public static (double[][] Vertices, int[][] Faces) Build(
        IReadOnlyList<(Point3d From, Point3d To, double Force)> members,
        double radius,
        int sides = 6)
    {
        sides = Math.Max(sides, 3);
        radius = Math.Max(radius, 1.0e-9);
        var vertices = new List<double[]>();
        var faces = new List<int[]>();
        foreach ((Point3d from, Point3d to, double _) in members)
        {
            Vector3d axis = to - from;
            double length = axis.Length;
            if (length <= 1.0e-9)
                continue;
            axis = axis / length;
            Vector3d helper = Math.Abs(axis.Z) < 0.9 ? Vector3d.ZAxis : Vector3d.XAxis;
            Vector3d u = Cross(axis, helper);
            u = u / u.Length;
            Vector3d v = Cross(axis, u);
            int baseIndex = vertices.Count;
            for (int end = 0; end < 2; end++)
            {
                Point3d centre = end == 0 ? from : to;
                for (int s = 0; s < sides; s++)
                {
                    double a = 2.0 * Math.PI * s / sides;
                    Point3d p = centre + (u * (radius * Math.Cos(a))) + (v * (radius * Math.Sin(a)));
                    vertices.Add(new[] { p.X, p.Y, p.Z });
                }
            }
            for (int s = 0; s < sides; s++)
            {
                int n = (s + 1) % sides;
                faces.Add(new[] { baseIndex + s, baseIndex + n, baseIndex + sides + n, baseIndex + sides + s });
            }
            for (int s = 1; s + 1 < sides; s++)
            {
                faces.Add(new[] { baseIndex, baseIndex + s + 1, baseIndex + s });
                faces.Add(new[] { baseIndex + sides, baseIndex + sides + s, baseIndex + sides + s + 1 });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    public static string Json(
        IReadOnlyList<(Point3d From, Point3d To, double Force)> members,
        double radius,
        string forceUnit,
        double unitFactor)
    {
        (double[][] vertices, int[][] faces) = Build(members, radius);
        var memberPayloads = new List<Dictionary<string, object?>>(members.Count);
        foreach ((Point3d from, Point3d to, double force) in members)
        {
            memberPayloads.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["from"] = new[] { from.X, from.Y, from.Z },
                ["to"] = new[] { to.X, to.Y, to.Z },
                ["force"] = force,
            });
        }
        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = "bench.columns/1",
            ["lengthUnitToMetres"] = unitFactor,
            ["forceUnit"] = forceUnit,
            ["radius"] = radius,
            ["vertices"] = vertices,
            ["faces"] = faces,
            ["members"] = memberPayloads,
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    private static Vector3d Cross(Vector3d a, Vector3d b) => new(
        (a.Y * b.Z) - (a.Z * b.Y),
        (a.Z * b.X) - (a.X * b.Z),
        (a.X * b.Y) - (a.Y * b.X));
}
