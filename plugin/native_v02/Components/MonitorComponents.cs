#nullable enable

using System;
using System.Collections.Generic;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>The pure arithmetic under the readers' measures: Forces,
    /// Fit and Supports all split, convert and summarise through here.
    /// The class keeps Monitor's name; the component it served retired in
    /// the readers rework and its GUID is not reused.</summary>
    internal static class MonitorMath
    {
        /// <summary>
        /// A reaction split along the tensioner axis (signed, positive along
        /// the axis) and across it (the magnitude of the remainder). The
        /// across part is what the anchorage carries and the tensioner cannot.
        /// </summary>
        public static (double Along, double Across) AnchorSplit(Vector3d reaction, Vector3d axis)
        {
            double length = axis.Length;
            if (length <= 1.0e-12)
                return (0.0, reaction.Length);
            Vector3d unit = axis / length;
            double along = (reaction.X * unit.X) + (reaction.Y * unit.Y) + (reaction.Z * unit.Z);
            Vector3d rest = reaction - (unit * along);
            return (along, rest.Length);
        }

        /// <summary>
        /// The tensioner axis at an anchor: the unit mean direction of the
        /// members leaving it into the net. Vertical when it has none.
        /// </summary>
        public static Vector3d TensionerAxis(int anchor, Point3d[] v, List<int>[] neighbours)
        {
            var sum = Vector3d.Zero;
            if (anchor < 0 || anchor >= v.Length || anchor >= neighbours.Length)
                return Vector3d.ZAxis;
            foreach (int other in neighbours[anchor])
            {
                if (other < 0 || other >= v.Length)
                    continue;
                Vector3d d = v[other] - v[anchor];
                double length = d.Length;
                if (length > 1.0e-12)
                    sum += d / length;
            }
            double total = sum.Length;
            return total > 1.0e-12 ? sum / total : Vector3d.ZAxis;
        }

        /// <summary>
        /// RMS, worst absolute, and nearest-rank 95th percentile of the
        /// absolute values. Zeros on an empty field.
        /// </summary>
        public static (double Rms, double Max, double P95) DeviationStats(IReadOnlyList<double> values)
        {
            if (values.Count == 0)
                return (0.0, 0.0, 0.0);
            double sumSquares = 0.0;
            var absolute = new double[values.Count];
            for (int i = 0; i < values.Count; i++)
            {
                sumSquares += values[i] * values[i];
                absolute[i] = Math.Abs(values[i]);
            }
            Array.Sort(absolute);
            int rank = (int)Math.Ceiling(0.95 * absolute.Length);
            rank = Math.Min(Math.Max(rank, 1), absolute.Length);
            return (Math.Sqrt(sumSquares / values.Count), absolute[^1], absolute[rank - 1]);
        }

        /// <summary>
        /// The unstrained length of a member: strained over one plus force
        /// over EA. The strained length comes back when EA is not positive,
        /// and also when one plus force over EA collapses to nothing or goes
        /// negative, which is a member whose EA cannot carry its own
        /// compression: it has no unstrained length worth reporting, and
        /// dividing by that denominator would hand back an infinity or a
        /// length with its sign flipped.
        /// </summary>
        public static double UnstrainedLength(double strained, double force, double EA)
        {
            if (EA <= 0.0)
                return strained;
            double stretch = 1.0 + (force / EA);
            return stretch > 1.0e-9 ? strained / stretch : strained;
        }

        /// <summary>
        /// What a force in the Result's own unit must be multiplied by to be
        /// newtons: 1 for N, 1000 for kN, and NULL for a unit this does not
        /// know.
        ///
        /// The ONE place the conversion is decided. Every stiffness the author
        /// wires is in newtons (EA in N, EI in N.m2, the capacities in N) and
        /// every force the Result carries is in the Result's unit, so each
        /// place the two meet asks here rather than assuming. Null rather than
        /// one on an unknown unit, because a caller silently scaling by one is
        /// exactly the fault this exists to stop: it must decide whether to
        /// refuse the reading or leave it unscaled and say so.
        /// </summary>
        public static double? ToNewtons(string unit)
        {
            string named = (unit ?? string.Empty).Trim();
            if (string.Equals(named, "N", StringComparison.OrdinalIgnoreCase))
                return 1.0;
            if (string.Equals(named, "kN", StringComparison.OrdinalIgnoreCase))
                return 1000.0;
            return null;
        }
    }
}
