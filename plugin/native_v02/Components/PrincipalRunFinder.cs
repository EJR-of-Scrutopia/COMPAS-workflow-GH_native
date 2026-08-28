#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// What Pattern has to say about the principal lines it was handed, as a
    /// severity and a message. Produced by
    /// <see cref="PrincipalRunFinder.Outcome"/> from three counts so the
    /// words can be checked without a canvas.
    /// </summary>
    internal sealed record PrincipalOutcome(string Severity, string Message);

    /// <summary>
    /// Resolving the principal lines, the notched bars a reconfigurable mould
    /// holds rigid, into runs of vertex indices on the pattern.
    ///
    /// ONE way in. An author draws the bars as curves over the pattern and
    /// each is matched to the run of pattern vertices lying along it.
    /// Matching is done in plan, so a bar drawn flat still finds its nodes.
    /// A principal line is a decision, and nothing here makes it for the
    /// author: the derivation from the anchors that used to stand in when no
    /// curves were drawn is gone, because a definition that forgot its curves
    /// quietly got bars it never asked for.
    ///
    /// Resolved here, on the pattern, because this is the one place where the
    /// curves and the geometry still agree. Downstream the surface rises and
    /// the curves do not follow it.
    /// </summary>
    internal static class PrincipalRunFinder
    {
        /// <summary>
        /// One bar, however many times it was traced.
        ///
        /// Two curves laid near the same run of nodes both snap to it. The
        /// duplicate is invisible in the viewport, because the second bar
        /// draws exactly on top of the first, and it is ruinous downstream:
        /// each bar is given its OWN full set of columns, each mirrored about
        /// its own slightly different midpoint, so the columns land on one
        /// line at two offset spacings and read as hopelessly lopsided.
        ///
        /// Matched on WHAT THEY ARE MADE OF, not on where they stop. Endpoints
        /// were tried and could not catch it: two traces of one line rarely
        /// finish on exactly the same node. Two runs sharing more than half
        /// their nodes are one bar, and the longer trace is the one kept.
        /// </summary>
        private static List<List<int>> Deduplicate(List<List<int>> runs)
        {
            var kept = new List<List<int>>();
            var keptNodes = new List<HashSet<int>>();
            foreach (List<int> run in runs.OrderByDescending(r => r.Count))
            {
                var nodes = new HashSet<int>(run);
                bool duplicate = false;
                for (int i = 0; i < keptNodes.Count; i++)
                {
                    int shared = nodes.Count(keptNodes[i].Contains);
                    if (2 * shared > Math.Min(nodes.Count, keptNodes[i].Count))
                    {
                        duplicate = true;
                        break;
                    }
                }
                if (duplicate)
                    continue;
                keptNodes.Add(nodes);
                kept.Add(run);
            }
            return kept;
        }

        /// <summary>
        /// Runs matched from drawn curves. Matching is in plan, so a bar drawn
        /// on the flat pattern still finds its nodes on a surface that rises.
        ///
        /// <paramref name="worstOffset"/> and <paramref name="gauge"/> come
        /// back so the caller can tell the author when a line was drawn where
        /// no run of nodes goes: the offset is how far the furthest matched bar
        /// sits from the curve that asked for it, the gauge the mesh's own
        /// median edge length to measure that against.
        /// <paramref name="unmatched"/> is how many curves caught fewer than
        /// two nodes and were dropped, so the caller can tell a DROPPED curve
        /// from two curves MERGED onto one run by <see cref="Deduplicate"/>.
        /// </summary>
        public static List<List<int>> FromCurves(
            IReadOnlyList<Curve> curves,
            IReadOnlyList<Point3d> vertices,
            IReadOnlyList<EdgeDto> edges,
            out double worstOffset,
            out double gauge,
            out int unmatched)
        {
            worstOffset = 0.0;
            gauge = 0.0;
            unmatched = 0;
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
            {
                unmatched = curves.Count(c => c is not null);
                return runs;
            }

            gauge = MouldGeometry.MedianEdgeLength(nodes, pairs);
            foreach (Curve curve in curves)
            {
                if (curve is null)
                    continue;
                List<int> run = MouldGeometry.SnapCurveToNodes(
                    curve, nodes, pairs, out double offset);
                if (run.Count < 2)
                {
                    unmatched++;
                    continue;
                }
                runs.Add(run);
                worstOffset = Math.Max(worstOffset, offset);
            }
            return Deduplicate(runs);
        }

        /// <summary>
        /// What Pattern says about the curves it was handed, from three
        /// counts: how many curves were supplied, how many caught fewer than
        /// two nodes, and how many runs survived deduplication.
        ///
        /// No curves is silence, because the FD path never draws any. Curves
        /// with no run at all is an ERROR, and Pattern emits nothing on it: a
        /// pattern whose bars were asked for and could not be placed is not
        /// the pattern that was asked for, and a grey chain is louder than a
        /// red badge on one component. A dropped curve is a warning. Two
        /// curves that snapped to one run is a remark, because the author
        /// should know the safety net fired, and before this it was reported
        /// as a drop, which it is not.
        /// </summary>
        public static PrincipalOutcome Outcome(int supplied, int unmatched, int kept)
        {
            if (supplied <= 0)
                return new PrincipalOutcome("none", string.Empty);
            if (kept <= 0)
            {
                return new PrincipalOutcome(
                    "error",
                    $"{supplied} principal line(s) were wired into Pattern and "
                    + "none of them lie over a run of pattern nodes in plan. A "
                    + "bar can only stand on nodes: draw each line through at "
                    + "least two connected pattern nodes. No Pattern is emitted "
                    + "until one does.");
            }
            if (unmatched > 0)
            {
                return new PrincipalOutcome(
                    "warning",
                    $"{unmatched} of {supplied} principal lines caught fewer "
                    + "than two pattern vertices and were dropped. They must "
                    + "lie over the pattern in plan.");
            }
            int merged = supplied - kept;
            if (merged > 0)
            {
                return new PrincipalOutcome(
                    "remark",
                    $"{supplied} principal lines snapped to {kept} distinct "
                    + $"run(s) of nodes; {merged} duplicate(s) merged into the "
                    + "bar they share. Two curves on one run of nodes are one "
                    + "bar.");
            }
            return new PrincipalOutcome("none", string.Empty);
        }
    }
}
