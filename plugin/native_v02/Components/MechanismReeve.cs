#nullable enable

using System;
using System.Collections.Generic;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// THE REEVE FACTOR (spec section 6): the mechanical advantage of one
/// wire's reeving through its block. Param's real unit has FOUR WHEELS that
/// MOVE WITH THE LOAD, so his authored default is 4.0; a wheel that merely
/// GUIDES the wire gives no advantage at all, and no amount of geometry
/// tells the two apart -- only Param knows which his are. That is exactly
/// why <see cref="SanityCeiling"/> below only ever informs a WARNING and
/// never a refusal (spec 6.4): a check that refused would be refusing a
/// machine it cannot actually assess.
///
/// THE FAILURE THIS CLASS EXISTS TO PREVENT, so nobody relaxes it later
/// (spec 6.6): a wrong factor makes every reel spin at the wrong RATE while
/// the geometry, the wire paths and the timing all stay correct. Nothing
/// looks broken; only the number is wrong, and nothing on screen says so.
/// </summary>
internal static class MechanismReeve
{
    /// <summary>
    /// THE RESOLUTION ORDER, exactly (the ruling made ahead of this task,
    /// binding): a per-wire override, if authored, beats everything else;
    /// failing that, <paramref name="machineDefault"/>.
    ///
    /// TODAY, <paramref name="machineDefault"/> IS THE PAYLOAD'S OWN
    /// PROVISIONAL reeve.default (Task 4), because the collector does not
    /// yet cite a machine -- the Machine (MA) port that will hand it the
    /// cited machine's own authored default is Task 6's own work, not
    /// this one's. THE SWAP TASK 6 MAKES IS AT ITS CALL SITE, NOT HERE:
    /// once MA is read, the one line that computes machineDefault is
    /// replaced to read the cited machine's own default instead of the
    /// payload's provisional one, and nothing about this method's
    /// signature, its resolution order, or its "machine" source name
    /// changes.
    ///
    /// NEVER a hardcoded 1.0: a caller with nothing authored for
    /// <paramref name="machineDefault"/> either has nothing to resolve
    /// with and must refuse by name itself (see
    /// <c>MechanismDocument.Json</c>'s own reeve.default refusal), rather
    /// than this method inventing a number nobody wrote down.
    /// </summary>
    public static (double Value, string Source) Resolve(
        double machineDefault,
        IReadOnlyDictionary<int, double> perWire,
        int wire)
    {
        ArgumentNullException.ThrowIfNull(perWire);
        return perWire.TryGetValue(wire, out double overridden)
            ? (overridden, "wire")
            : (machineDefault, "machine");
    }

    /// <summary>
    /// THE COSINE THRESHOLD past which two consecutive chords count as a
    /// REVERSAL: -0.5, cos(120 degrees). A wire wrapping smoothly around a
    /// drum turns only a few degrees between adjacent routing frames; a
    /// genuine reversal -- the wire doubling back on itself through a
    /// block -- turns through well over a right angle.
    /// </summary>
    public const double ReeveReversalCosine = -0.5;

    /// <summary>
    /// COUNTS DIRECTION REVERSALS along a wire's own routing frames (spec
    /// 6.4): consecutive CHORDS (the vector from one frame's origin to the
    /// next), each NORMALISED before the angle test, with a reversal
    /// counted wherever two adjacent chords' own dot product falls to or
    /// past <see cref="ReeveReversalCosine"/>.
    ///
    /// THE NORMALISATION IS NOT COSMETIC (spec 6.5). An unnormalised dot
    /// product is bounded by the product of the two chords' own lengths,
    /// so comparing it against a fixed cosine threshold is
    /// SCALE-DEPENDENT. Param's routing frames sit centimetres apart at
    /// drum scale, so two such chords dot to something two orders of
    /// magnitude below -0.5 however sharp the true turn is: the count
    /// would read ZERO on every wire of every real machine and this check
    /// could never fire, while a fixture authored with unit-length chords
    /// would pass by coincidence. Normalising each chord first measures
    /// the ANGLE between them alone, so the count is identical whatever
    /// units or frame spacing the route was authored at -- proved by the
    /// harness's own scale-invariance check, the same route scaled by
    /// 0.01 reporting the same count.
    ///
    /// A REPEATED POINT (a zero-length chord) is SKIPPED rather than
    /// counted as a reversal or folded into the running comparison as a
    /// direction of its own: it carries no direction to compare, and
    /// letting it reset or break the comparison would let an incidental
    /// duplicate frame fabricate or hide a turn that genuinely is not
    /// there.
    ///
    /// WHAT IS NOT PROVED HERE, said rather than left to be found: this
    /// counts direction changes in the AUTHORED route, which is a
    /// polyline approximation of the true wrap. A wrap captured at coarse
    /// frame spacing can under-count a real reversal that happens between
    /// two authored frames, and nothing here can see that it happened.
    /// </summary>
    public static int WrapReversals(IReadOnlyList<MechanismFrame> route)
    {
        ArgumentNullException.ThrowIfNull(route);
        int reversals = 0;
        double[]? previousUnit = null;
        for (int i = 1; i < route.Count; i++)
        {
            double[] origin = route[i - 1].Origin;
            double[] next = route[i].Origin;
            double[] chord =
            {
                next[0] - origin[0],
                next[1] - origin[1],
                next[2] - origin[2],
            };
            double length = Math.Sqrt(
                (chord[0] * chord[0]) + (chord[1] * chord[1]) + (chord[2] * chord[2]));
            if (length < 1.0e-12)
                continue;

            double[] unit = { chord[0] / length, chord[1] / length, chord[2] / length };
            if (previousUnit is not null)
            {
                double dot =
                    (previousUnit[0] * unit[0]) +
                    (previousUnit[1] * unit[1]) +
                    (previousUnit[2] * unit[2]);
                if (dot <= ReeveReversalCosine)
                    reversals++;
            }
            previousUnit = unit;
        }
        return reversals;
    }

    /// <summary>
    /// THE GENEROUS SLACK a declared factor is allowed over the wrap
    /// count's own implied ceiling before <see cref="SanityCeiling"/>
    /// names it (spec 6.4). Wide on purpose and deliberately ONE-SIDED: a
    /// reversal can come from a wheel that only GUIDES the wire and adds
    /// no advantage at all, so a HIGH reversal count never means the
    /// factor must be high, only that it COULD be, and a LOW declared
    /// factor is therefore always physically plausible whatever the wrap
    /// count shows -- there is no floor. What is implausible is the
    /// opposite: a factor claiming far more mechanical advantage than the
    /// route's own turns could ever supply.
    /// </summary>
    public const double ReeveSanitySlack = 8.0;

    /// <summary>
    /// THE IMPLIED CEILING (spec 6.4's "band"): with R wrap reversals, a
    /// wire can plausibly account for up to about R + 1 reeved parts (each
    /// pass between a fixed and a moving sheave costs roughly one
    /// reversal), multiplied by <see cref="ReeveSanitySlack"/> so the
    /// warning only ever fires on a declared factor WILDLY past what the
    /// route could support -- a wheel that only guides the wire still adds
    /// reversals with no advantage at all, so this is a loose hint, never
    /// a measurement, and REFUSES NOTHING (spec 6.4): only Param knows
    /// which of his wheels move with the load.
    ///
    /// WHAT IS NOT PROVED HERE, said rather than left to be found (the
    /// same honesty <see cref="WrapReversals"/> owes its own non-proof):
    /// the "+ 1" and the "x8" slack have never been checked against
    /// Param's own real machine's actual wrap-reversal count, because no
    /// fixture of his real routing exists for this harness to measure. He
    /// authored 4.0 as his real default; this band is tuned so that
    /// number draws no warning even against a route with ZERO measured
    /// reversals, which is the loosest case available, and it is
    /// red-proved to actually tell a wildly wrong factor from a correct
    /// one on the fixtures this harness can build. It is not proved to be
    /// the RIGHT band for his real machine's real wrap, only a band that
    /// does not cry wolf on the one real number he has given it.
    /// </summary>
    public static double SanityCeiling(int reversals) =>
        (reversals + 1) * ReeveSanitySlack;
}
