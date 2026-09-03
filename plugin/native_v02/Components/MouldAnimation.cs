#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// The build animation's arithmetic, in ONE place.
    ///
    /// Animate draws a frame on the canvas and Export writes a whole sweep of
    /// them into the frames sidecar. Those two must be the same motion, not two
    /// implementations of it, or a studio replaying the sidecar shows a machine
    /// nobody ever saw in Grasshopper. So the phase timeline, the per-node
    /// blend and the live column nodes live here, and both callers sample them.
    ///
    /// The split is between what depends on the RESULT and what depends on the
    /// TIME. <see cref="Prepare"/> does the first, once: the start state, the
    /// bare surface, the relief, the principal bars, the ground. That is the
    /// expensive half, since the bare surface is two thousand relaxation
    /// sweeps. <see cref="At"/> does the second, per frame, and is arithmetic
    /// on arrays already in hand.
    /// </summary>
    internal static class MouldAnimation
    {
        /// <summary>
        /// Animate's own Pre-Sag port default, named here because Export has no
        /// Pre-Sag of its own to read and the sidecar has to be deterministic
        /// for a given Result. A sweep written at this value is the sweep the
        /// author sees when they drop an Animate on the canvas and touch only
        /// the Time slider.
        /// </summary>
        public const double DefaultPreSagPercent = 40.0;

        /// <summary>
        /// A caller's memory of the last bare surface, so dragging a Time
        /// slider does not re-relax a surface that Time never touched. The key
        /// names everything <c>MouldGeometry.BareSurface</c> reads, so a cached
        /// answer that no longer applies is recognised rather than reused.
        /// </summary>
        internal sealed class BareCache
        {
            public string Key { get; set; } = string.Empty;

            public double[]? Surface { get; set; }
        }

        /// <summary>
        /// Everything about one Result the animation needs, worked out once.
        /// The diagnostics Animate reports are read off this rather than
        /// recomputed, so the words and the motion cannot drift apart.
        /// </summary>
        internal sealed class Setup
        {
            public Point3d[] Target { get; init; } = Array.Empty<Point3d>();

            public Point3d[] Start { get; init; } = Array.Empty<Point3d>();

            public double[] Bare { get; init; } = Array.Empty<double>();

            public double[] Relief { get; init; } = Array.Empty<double>();

            public (int, int)[] Edges { get; init; } = Array.Empty<(int, int)>();

            public int[] EdgeSource { get; init; } = Array.Empty<int>();

            public List<List<int>> Bars { get; init; } = new();

            public HashSet<int> PrincipalIds { get; init; } = new();

            public HashSet<int> AnchorIds { get; init; } = new();

            public List<int>[] Neighbours { get; init; } =
                Array.Empty<List<int>>();

            public double Ground { get; init; }

            public double PlanTravel { get; init; }

            public bool FromPattern { get; init; }

            public bool StartIsFinal { get; init; }

            public MouldColumnsDto? Columns { get; init; }

            public int Count => Target.Length;

            public bool HasColumns =>
                Columns is not null && Columns.Members.Count > 0;
        }

        /// <summary>
        /// The machine at one instant: the live net, the live column nodes, and
        /// the two scalars that put them there.
        /// </summary>
        internal sealed class Frame
        {
            public double Time { get; init; }

            public string Phase { get; init; } = "hold";

            public double Sag { get; init; }

            public double Lift { get; init; }

            public Point3d[] Vertices { get; init; } = Array.Empty<Point3d>();

            public Point3d[]? ColumnNodes { get; init; }
        }

        /// <summary>
        /// Read the Result once. The caller has already validated it; what is
        /// refused here is a Result with nothing to animate.
        /// </summary>
        public static Setup Prepare(ResultDto result, BareCache? cache = null)
        {
            ArgumentNullException.ThrowIfNull(result);
            EquilibriumResultDto equilibrium = result.Equilibrium
                ?? throw new InvalidOperationException(
                    "Result carries no equilibrium.");
            Point3d[] target = equilibrium.Vertices
                .Select(v => new Point3d(v.X, v.Y, v.Z))
                .ToArray();
            int n = target.Length;
            if (n == 0)
                throw new InvalidOperationException("Result carries no vertices.");

            // Keep the ORIGINAL edge index alongside each kept edge. The
            // filter drops invalid and self edges, so a filtered position
            // no longer matches the Result's own MemberForces array, and
            // indexing forces by it would silently attach every force
            // after the first dropped edge to the wrong member.
            (int, int)[] edges = MouldGeometry.ValidEdges(
                equilibrium, n, out int[] edgeSource);
            if (edges.Length == 0)
                throw new InvalidOperationException("Result carries no edges.");

            // Start from the ORIGINAL PATTERN: the plan as drawn, taken
            // off the SPINE PROBLEM that every solver attaches to its own
            // Result. Deliberately not the equilibrium's analysis topology,
            // which is the network the worker actually solved and so
            // already carries the answer; starting there put frame zero at
            // the finished vault and left the animation with nothing to do.
            var anchorIds = new HashSet<int>(
                equilibrium.ResolvedSupportNodeIds
                    .Where(i => i >= 0 && i < n));
            double ground = MouldGeometry.GroundLevel(target, anchorIds);
            IReadOnlyList<Point3Dto>? pattern =
                result.Problem?.Anchored?.Pattern?.Topology?.Vertices;
            bool fromPattern = pattern is not null && pattern.Count == n;

            // A start that already matches the solved shape node for node
            // is not a plan, it is the answer. Lie the net flat and say so,
            // rather than replay a still image and call it an animation.
            double zSpan = Math.Max(target.Max(p => p.Z) - ground, 1.0e-9);
            double startDrift = 0.0;
            if (fromPattern)
            {
                for (int i = 0; i < n; i++)
                {
                    startDrift = Math.Max(
                        startDrift, Math.Abs(pattern![i].Z - target[i].Z));
                }
            }
            bool startIsFinal = fromPattern && startDrift < 1.0e-4 * zSpan;
            if (startIsFinal)
                fromPattern = false;

            // Frame zero is the pattern WHOLE: its plan as well as its
            // level. Reeling an infill cable in is one operation, and while
            // the net is still flat on the ground the only place it can
            // show is in PLAN, as the net draws in from the plan as drawn
            // toward the solved plan. Holding the plan at the solved one
            // and moving only Z is what lost the first phase: the net sat
            // flat and perfectly still until the columns began to lift.
            Point3d[] start = fromPattern
                ? pattern!.Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray()
                : target.Select(p => new Point3d(p.X, p.Y, ground)).ToArray();
            double planTravel = 0.0;
            for (int i = 0; i < n; i++)
            {
                planTravel = Math.Max(
                    planTravel,
                    Math.Sqrt(MouldGeometry.PlanDistanceSquared(
                        start[i], target[i])));
            }
            List<int>[] neighbours = MouldGeometry.BuildAdjacency(n, edges);

            // The principal lines this Result carries, resolved upstream
            // by Pattern from the curves drawn into it. Nothing is snapped
            // here, which is why there is no curve input: indices survive
            // a surface that rises and curves do not.
            List<List<int>> bars = MouldGeometry.PrincipalRuns(equilibrium, n);
            var principalIds = new HashSet<int>(bars.SelectMany(b => b));

            var pinned = new bool[n];
            foreach (int i in principalIds)
                pinned[i] = true;
            foreach (int i in anchorIds)
                pinned[i] = true;

            // BareSurface runs 2000 relaxation sweeps and reads only the
            // solved shape and what is pinned, neither of which Time or
            // Pre-Sag touch. Caching it is the difference between dragging
            // the timeline and re-solving a surface on every frame.
            string bareKey = MouldGeometry.SurfaceKey(target, pinned);
            double[] bare;
            if (cache is not null &&
                cache.Surface is not null &&
                cache.Surface.Length == n &&
                string.Equals(cache.Key, bareKey, StringComparison.Ordinal))
            {
                bare = cache.Surface;
            }
            else
            {
                bare = MouldGeometry.BareSurface(target, neighbours, pinned);
                if (cache is not null)
                {
                    cache.Key = bareKey;
                    cache.Surface = bare;
                }
            }

            var relief = new double[n];
            for (int i = 0; i < n; i++)
                relief[i] = target[i].Z - bare[i];

            return new Setup
            {
                Target = target,
                Start = start,
                Bare = bare,
                Relief = relief,
                Edges = edges,
                EdgeSource = edgeSource,
                Bars = bars,
                PrincipalIds = principalIds,
                AnchorIds = anchorIds,
                Neighbours = neighbours,
                Ground = ground,
                PlanTravel = planTravel,
                FromPattern = fromPattern,
                StartIsFinal = startIsFinal,
                Columns = result.Mould?.Columns,
            };
        }

        /// <summary>
        /// One frame, at a Time in 0 to 100 and a Pre-Sag in 0 to 100.
        ///
        /// SAG drives the plan as well as the depth, because they are the same
        /// operation seen twice: a cable reeled in pulls the net toward its bar
        /// and lets it drop between them at once. LIFT is the columns, and it
        /// moves only the height, so at lift zero the whole net stays down
        /// where it was drawn while the first reeling happens.
        ///
        /// At Time 100 both scalars are exactly one, so every vertex lands back
        /// on the solved geometry it was blended away from. That is what lets
        /// the sidecar's last frame be checked against the contract's own
        /// equilibrium vertices.
        /// </summary>
        public static Frame At(Setup setup, double timePct, double preSagPct)
        {
            ArgumentNullException.ThrowIfNull(setup);
            double clampedTime = Math.Min(Math.Max(timePct, 0.0), 100.0);
            double time = clampedTime / 100.0;
            double pre = Math.Min(Math.Max(preSagPct, 0.0), 100.0) / 100.0;
            (double sag, double lift, string phase) =
                MouldGeometry.Phases(time, pre);

            int n = setup.Count;
            Point3d[] start = setup.Start;
            Point3d[] target = setup.Target;
            double[] bare = setup.Bare;
            double[] relief = setup.Relief;
            var live = new Point3d[n];
            for (int i = 0; i < n; i++)
            {
                double z = start[i].Z
                    + (lift * (bare[i] - start[i].Z))
                    + (sag * relief[i]);
                live[i] = new Point3d(
                    start[i].X + (sag * (target[i].X - start[i].X)),
                    start[i].Y + (sag * (target[i].Y - start[i].Y)),
                    z);
            }

            return new Frame
            {
                Time = clampedTime,
                Phase = phase,
                Sag = Math.Min(Math.Max(sag, 0.0), 1.0),
                Lift = Math.Min(Math.Max(lift, 0.0), 1.0),
                Vertices = live,
                ColumnNodes = setup.HasColumns
                    ? MouldGeometry.LiveColumnNodes(setup.Columns!, live)
                    : null,
            };
        }
    }
}
