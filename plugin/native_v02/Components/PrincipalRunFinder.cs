#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Resolving the principal lines, the notched bars a reconfigurable mould
    /// holds rigid, into runs of vertex indices on the pattern.
    ///
    /// Two ways in, and both land on the same answer shape.
    ///
    /// From CURVES. An author draws the bars and each is matched to the run of
    /// pattern vertices lying along it. Matching is done in plan, so a bar
    /// drawn flat still finds its nodes.
    ///
    /// DERIVED, with no curves at all. On a quad mesh the bars run along one of
    /// the two mesh directions, which is what the mould's own mesh convention
    /// assumes. Those directions are edge loops: enter a quad by one edge and
    /// leave by the opposite one, and keep going. Tracing every loop and taking
    /// every k-th gives evenly spaced bars that follow the mesh exactly, which
    /// is both what the machine wants and impossible to draw by hand as
    /// accurately.
    ///
    /// Resolved here, on the pattern, because this is the one place where the
    /// curves and the geometry still agree. Downstream the surface rises and
    /// the curves do not follow it.
    /// </summary>
    internal static class PrincipalRunFinder
    {
        /// <summary>
        /// Runs traced from the mesh itself: every <paramref name="spacing"/>-th
        /// edge loop of the chosen family.
        ///
        /// Loops are grouped into families by walking them, then the families
        /// are ordered across the mesh so that "every third" means every third
        /// in space rather than every third in whatever order the mesh happened
        /// to store its faces.
        /// </summary>
        public static List<List<int>> Derive(
            IReadOnlyList<Point3d> vertices,
            IReadOnlyList<IReadOnlyList<int>> faces,
            int spacing,
            int family)
        {
            var runs = new List<List<int>>();
            if (spacing <= 0 || vertices.Count == 0 || faces.Count == 0)
                return runs;

            // Only quads carry a well-defined opposite edge, which is what an
            // edge loop follows. A triangulated pattern has no such direction
            // and derivation is refused rather than faked.
            var quads = faces.Where(f => f.Count == 4).ToList();
            if (quads.Count == 0)
                return runs;

            // edge -> the quads on it, and each quad's four edges in order
            var edgeFaces = new Dictionary<(int, int), List<int>>();
            var faceEdges = new List<(int, int)[]>();
            for (int q = 0; q < quads.Count; q++)
            {
                IReadOnlyList<int> f = quads[q];
                var own = new (int, int)[4];
                for (int k = 0; k < 4; k++)
                {
                    int a = f[k];
                    int b = f[(k + 1) % 4];
                    (int, int) key = a < b ? (a, b) : (b, a);
                    own[k] = key;
                    if (!edgeFaces.TryGetValue(key, out List<int>? list))
                    {
                        list = new List<int>();
                        edgeFaces[key] = list;
                    }
                    list.Add(q);
                }
                faceEdges.Add(own);
            }

            // Walk every loop once. A loop is a chain of edges linked through
            // quads by stepping to the opposite edge each time.
            var visited = new HashSet<(int, int)>();
            var loops = new List<List<(int, int)>>();
            foreach ((int, int) seed in edgeFaces.Keys)
            {
                if (visited.Contains(seed))
                    continue;
                List<(int, int)> loop = Walk(seed, edgeFaces, faceEdges, visited);
                if (loop.Count >= 2)
                    loops.Add(loop);
            }
            if (loops.Count == 0)
                return runs;

            // Two families alternate as the loops cross one another. Separate
            // them by direction: a loop's own edges all run roughly one way, so
            // the average plan direction sorts them cleanly into two groups.
            var directed = loops
                .Select(loop => (Loop: loop, Angle: MeanAngle(loop, vertices)))
                .ToList();
            double split = directed.Average(d => d.Angle);
            var chosen = directed
                .Where(d => family == 0 ? d.Angle <= split : d.Angle > split)
                .ToList();
            if (chosen.Count == 0)
                chosen = directed;

            // Order the family across the mesh so that "every k-th" is a
            // spacing rather than a coincidence of face order.
            var ordered = chosen
                .Select(d => (d.Loop, Key: Centroid(d.Loop, vertices)))
                .OrderBy(x => x.Key.Item1)
                .ThenBy(x => x.Key.Item2)
                .ToList();

            for (int i = 0; i < ordered.Count; i += spacing)
            {
                List<int> run = ToVertexRun(ordered[i].Loop);
                if (run.Count >= 2)
                    runs.Add(run);
            }
            return runs;
        }

        private static List<(int, int)> Walk(
            (int, int) seed,
            Dictionary<(int, int), List<int>> edgeFaces,
            List<(int, int)[]> faceEdges,
            HashSet<(int, int)> visited)
        {
            var loop = new List<(int, int)> { seed };
            visited.Add(seed);

            // Both ways from the seed, since a loop may start in its middle.
            for (int direction = 0; direction < 2; direction++)
            {
                (int, int) current = seed;
                int cameFrom = -1;
                while (true)
                {
                    List<int> onEdge = edgeFaces[current];
                    int next = -1;
                    foreach (int q in onEdge)
                    {
                        if (q == cameFrom)
                            continue;
                        if (direction == 0 && onEdge.Count > 1 && q == onEdge[1])
                            continue;
                        if (direction == 1 && onEdge.Count > 1 && q == onEdge[0]
                            && cameFrom == -1)
                        {
                            continue;
                        }
                        next = q;
                        break;
                    }
                    if (next < 0)
                        break;

                    (int, int)[] own = faceEdges[next];
                    int index = Array.IndexOf(own, current);
                    if (index < 0)
                        break;
                    (int, int) opposite = own[(index + 2) % 4];
                    if (!visited.Add(opposite))
                        break;
                    loop.Add(opposite);
                    cameFrom = next;
                    current = opposite;
                }
            }
            return loop;
        }

        /// <summary>
        /// A loop is a chain of parallel edges; the bar runs ACROSS them, so
        /// its vertex run is one endpoint of each edge, taken consistently and
        /// in order along the chain.
        /// </summary>
        private static List<int> ToVertexRun(List<(int, int)> loop)
        {
            var run = new List<int>();
            var seen = new HashSet<int>();
            foreach ((int a, int b) in loop)
            {
                if (seen.Add(a))
                    run.Add(a);
            }
            if (run.Count < 2)
            {
                run.Clear();
                foreach ((int a, int b) in loop)
                {
                    if (seen.Add(b))
                        run.Add(b);
                }
            }
            return run;
        }

        private static double MeanAngle(
            List<(int, int)> loop,
            IReadOnlyList<Point3d> vertices)
        {
            double x = 0.0;
            double y = 0.0;
            foreach ((int a, int b) in loop)
            {
                if (a >= vertices.Count || b >= vertices.Count)
                    continue;
                double dx = vertices[b].X - vertices[a].X;
                double dy = vertices[b].Y - vertices[a].Y;
                double length = Math.Sqrt((dx * dx) + (dy * dy));
                if (length <= 1e-12)
                    continue;
                // Double the angle so that opposite directions agree, which is
                // what makes this a direction rather than a heading.
                double angle = 2.0 * Math.Atan2(dy / length, dx / length);
                x += Math.Cos(angle);
                y += Math.Sin(angle);
            }
            return Math.Atan2(y, x);
        }

        private static (double, double) Centroid(
            List<(int, int)> loop,
            IReadOnlyList<Point3d> vertices)
        {
            double x = 0.0;
            double y = 0.0;
            int count = 0;
            foreach ((int a, int b) in loop)
            {
                if (a >= vertices.Count || b >= vertices.Count)
                    continue;
                x += 0.5 * (vertices[a].X + vertices[b].X);
                y += 0.5 * (vertices[a].Y + vertices[b].Y);
                count++;
            }
            return count == 0 ? (0.0, 0.0) : (x / count, y / count);
        }

        /// <summary>
        /// Runs matched from drawn curves. Matching is in plan, so a bar drawn
        /// on the flat pattern still finds its nodes on a surface that rises.
        /// </summary>
        public static List<List<int>> FromCurves(
            IReadOnlyList<Curve> curves,
            IReadOnlyList<Point3d> vertices,
            IReadOnlyList<EdgeDto> edges)
        {
            var runs = new List<List<int>>();
            if (curves.Count == 0 || vertices.Count == 0)
                return runs;

            Point3d[] nodes = vertices.ToArray();
            (int, int)[] pairs = edges
                .Where(e => e.U != e.V &&
                    e.U >= 0 && e.U < nodes.Length &&
                    e.V >= 0 && e.V < nodes.Length)
                .Select(e => (e.U, e.V))
                .ToArray();
            if (pairs.Length == 0)
                return runs;

            foreach (Curve curve in curves)
            {
                if (curve is null)
                    continue;
                List<int> run = MouldGeometry.SnapCurveToNodes(curve, nodes, pairs);
                if (run.Count >= 2)
                    runs.Add(run);
            }
            return runs;
        }
    }
}
