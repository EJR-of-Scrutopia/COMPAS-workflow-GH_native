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
    /// DERIVED FROM THE ANCHORS, with no curves at all, which is how these
    /// lines are found in practice: a principal line starts at the middle of an
    /// anchor strip and runs straight off it, across the form, to the far side.
    /// That needs no quad structure, no drawn curve and no choice of direction,
    /// because the anchors already say where the bars belong.
    ///
    /// Resolved here, on the pattern, because this is the one place where the
    /// curves and the geometry still agree. Downstream the surface rises and
    /// the curves do not follow it.
    /// </summary>
    internal static class PrincipalRunFinder
    {
        /// <summary>
        /// Runs derived from the ANCHORS, which is how these lines are found in
        /// practice: a principal line starts at the middle of an anchor strip
        /// and runs straight off it, across the form, to the far side.
        ///
        /// The anchors fall into strips, one per side that is tied down. Each
        /// strip is walked to put its nodes in order, a start is taken at its
        /// midpoint, and the line is traced across the mesh by leaving each
        /// vertex through whichever edge continues straightest from the one it
        /// arrived by. That needs no quad structure and no drawn curve.
        ///
        /// <paramref name="ribsPerStrip"/> above one spreads that many starts
        /// evenly along each strip instead of taking only its midpoint.
        /// </summary>
        public static List<List<int>> DeriveFromAnchors(
            IReadOnlyList<Point3d> vertices,
            IReadOnlyList<EdgeDto> edges,
            IReadOnlyList<int> anchorIds,
            int ribsPerStrip)
        {
            var runs = new List<List<int>>();
            if (ribsPerStrip <= 0 || vertices.Count == 0 || anchorIds.Count == 0)
                return runs;

            List<int>[] neighbours = Adjacency(vertices.Count, edges);
            var anchors = new HashSet<int>(
                anchorIds.Where(i => i >= 0 && i < vertices.Count));
            if (anchors.Count == 0)
                return runs;

            var seenRun = new HashSet<string>();
            foreach (List<int> strip in Strips(anchors, neighbours))
            {
                foreach (int start in StartsAlong(strip, ribsPerStrip))
                {
                    List<int> run = WalkAcross(
                        start, vertices, neighbours, anchors);
                    if (run.Count < 2)
                        continue;
                    // A line traced from one side reaches the other, so the
                    // strip opposite would trace the same line backwards.
                    int first = run[0];
                    int last = run[run.Count - 1];
                    string key = first < last
                        ? $"{first}:{last}"
                        : $"{last}:{first}";
                    if (seenRun.Add(key))
                        runs.Add(run);
                }
            }
            return runs;
        }

        private static List<int>[] Adjacency(
            int count,
            IReadOnlyList<EdgeDto> edges)
        {
            var neighbours = new List<int>[count];
            for (int i = 0; i < count; i++)
                neighbours[i] = new List<int>();
            foreach (EdgeDto e in edges)
            {
                if (e.U < 0 || e.U >= count || e.V < 0 || e.V >= count)
                    continue;
                if (e.U == e.V)
                    continue;
                neighbours[e.U].Add(e.V);
                neighbours[e.V].Add(e.U);
            }
            return neighbours;
        }

        /// <summary>
        /// The anchor nodes fall into strips: connected runs of anchors, one
        /// per side that is tied down. Each comes back ordered end to end.
        /// </summary>
        private static List<List<int>> Strips(
            HashSet<int> anchors,
            List<int>[] neighbours)
        {
            var strips = new List<List<int>>();
            var unvisited = new HashSet<int>(anchors);
            while (unvisited.Count > 0)
            {
                int seed = unvisited.First();
                var group = new List<int>();
                var queue = new Queue<int>();
                queue.Enqueue(seed);
                unvisited.Remove(seed);
                while (queue.Count > 0)
                {
                    int at = queue.Dequeue();
                    group.Add(at);
                    foreach (int next in neighbours[at])
                    {
                        if (unvisited.Remove(next))
                            queue.Enqueue(next);
                    }
                }
                strips.Add(Order(group, neighbours, anchors));
            }
            return strips;
        }

        /// <summary>Put a strip's nodes in order by walking it end to end.</summary>
        private static List<int> Order(
            List<int> group,
            List<int>[] neighbours,
            HashSet<int> anchors)
        {
            if (group.Count <= 2)
                return group;
            var member = new HashSet<int>(group);

            // An end of the strip has only one neighbour inside it.
            int start = group[0];
            foreach (int candidate in group)
            {
                int inside = neighbours[candidate].Count(n => member.Contains(n));
                if (inside <= 1)
                {
                    start = candidate;
                    break;
                }
            }

            var ordered = new List<int> { start };
            var used = new HashSet<int> { start };
            int at2 = start;
            while (true)
            {
                int next = -1;
                foreach (int n in neighbours[at2])
                {
                    if (member.Contains(n) && !used.Contains(n))
                    {
                        next = n;
                        break;
                    }
                }
                if (next < 0)
                    break;
                ordered.Add(next);
                used.Add(next);
                at2 = next;
            }
            // Anything the walk could not reach still belongs to the strip.
            foreach (int leftover in group)
            {
                if (used.Add(leftover))
                    ordered.Add(leftover);
            }
            return ordered;
        }

        /// <summary>
        /// Where along a strip the lines start. One rib takes the midpoint,
        /// which is the usual case; more are spread evenly along it.
        /// </summary>
        private static IEnumerable<int> StartsAlong(List<int> strip, int ribs)
        {
            if (strip.Count == 0)
                yield break;
            if (ribs <= 1)
            {
                yield return strip[strip.Count / 2];
                yield break;
            }
            var seen = new HashSet<int>();
            for (int r = 0; r < ribs; r++)
            {
                double t = (r + 0.5) / ribs;
                int index = (int)Math.Round(t * (strip.Count - 1));
                index = Math.Min(Math.Max(index, 0), strip.Count - 1);
                if (seen.Add(index))
                    yield return strip[index];
            }
        }

        /// <summary>
        /// Trace a line across the form from an anchor, leaving each vertex
        /// through whichever edge continues straightest from the one it arrived
        /// by. The first step goes as square to the strip as the mesh allows,
        /// which is the tangent off the anchor line.
        /// </summary>
        private static List<int> WalkAcross(
            int start,
            IReadOnlyList<Point3d> vertices,
            List<int>[] neighbours,
            HashSet<int> anchors)
        {
            var run = new List<int> { start };
            var used = new HashSet<int> { start };

            // Step off the strip: prefer a neighbour that is not itself an
            // anchor, so the line leaves the tie rather than running along it.
            int at = -1;
            foreach (int candidate in neighbours[start])
            {
                if (anchors.Contains(candidate))
                    continue;
                if (at < 0 || Plan(vertices[start], vertices[candidate]) >
                    Plan(vertices[start], vertices[at]))
                {
                    at = candidate;
                }
            }
            if (at < 0)
                return run;

            run.Add(at);
            used.Add(at);
            int from = start;
            while (true)
            {
                Vector3d heading = vertices[at] - vertices[from];
                if (heading.Length <= 1e-12)
                    break;
                heading.Unitize();

                int best = -1;
                double bestScore = -2.0;
                foreach (int candidate in neighbours[at])
                {
                    if (used.Contains(candidate))
                        continue;
                    Vector3d step = vertices[candidate] - vertices[at];
                    if (step.Length <= 1e-12)
                        continue;
                    step.Unitize();
                    double score = (heading.X * step.X)
                        + (heading.Y * step.Y)
                        + (heading.Z * step.Z);
                    if (score > bestScore)
                    {
                        bestScore = score;
                        best = candidate;
                    }
                }
                // A turn of more than a right angle is not a continuation; the
                // line has reached an edge and should stop rather than double
                // back along the boundary.
                if (best < 0 || bestScore <= 0.0)
                    break;
                run.Add(best);
                used.Add(best);
                from = at;
                at = best;
            }
            return run;
        }

        private static double Plan(Point3d a, Point3d b) =>
            ((a.X - b.X) * (a.X - b.X)) + ((a.Y - b.Y) * (a.Y - b.Y));

        /// <summary>
        /// Runs matched from drawn curves. Matching is in plan, so a bar drawn
        /// on the flat pattern still finds its nodes on a surface that rises.
        ///
        /// <paramref name="worstOffset"/> and <paramref name="gauge"/> come
        /// back so the caller can tell the author when a line was drawn where
        /// no run of nodes goes: the offset is how far the furthest matched bar
        /// sits from the curve that asked for it, the gauge the mesh's own
        /// median edge length to measure that against.
        /// </summary>
        public static List<List<int>> FromCurves(
            IReadOnlyList<Curve> curves,
            IReadOnlyList<Point3d> vertices,
            IReadOnlyList<EdgeDto> edges,
            out double worstOffset,
            out double gauge)
        {
            worstOffset = 0.0;
            gauge = 0.0;
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

            gauge = MouldGeometry.MedianEdgeLength(nodes, pairs);
            foreach (Curve curve in curves)
            {
                if (curve is null)
                    continue;
                List<int> run = MouldGeometry.SnapCurveToNodes(
                    curve, nodes, pairs, out double offset);
                if (run.Count < 2)
                    continue;
                runs.Add(run);
                worstOffset = Math.Max(worstOffset, offset);
            }
            return runs;
        }
    }
}
