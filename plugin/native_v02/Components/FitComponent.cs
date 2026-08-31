#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Fit: whether the machine reaches the solved state.
    ///
    /// One of Monitor's three children. Deviation and its statistics are in
    /// VERTEX order, the one order here with no partner tree; Bar Sag is one
    /// branch per principal line, aligned with Frame's Principal Nodes
    /// branch for branch and item for item. Reachability is the one verdict,
    /// and only against the Tolerance the author sets.
    ///
    /// EI is asked for here and nowhere else. Where the arms go does not
    /// depend on it, because stiffness cancels out of that comparison; here
    /// it converts the bar's bending into millimetres a build tolerance is
    /// written in. The bar load is the Result's own member forces, converted
    /// to newtons through <see cref="MonitorMath.ToNewtons"/> before it
    /// meets EI.
    /// </summary>
    public sealed class FitComponent : NativeComponentBase
    {
        public FitComponent()
            : base(
                "Fit",
                "FI",
                "Whether the machine reaches the solved state: the signed "
                    + "deviation of this frame from the solved shape at every "
                    + "node with its RMS, worst and 95th percentile, whether "
                    + "every node is within Tolerance with the set that is "
                    + "not, and how far each bar bends between its supports "
                    + "with EI as given. Millimetres throughout. Reachability "
                    + "is the one verdict, against the Tolerance you set; "
                    + "nothing else assumes a limit.",
                ComponentCategories.Read,
                "fit")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("9878783a-048d-4c95-bbc0-31351131a6a6");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "A Result from Columns (the built state) or from Animate (this "
                    + "frame). With a frame the numbers are read at the live "
                    + "geometry; the member forces are those of the finished "
                    + "state either way, because the mould is meant to reach it.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "EI",
                "EI",
                "Bending stiffness of one notched bar, N.m2: Young's modulus "
                    + "times the second moment of area of the section you mean "
                    + "to build it from. It is in NEWTON metres squared "
                    + "whatever unit the Result's forces are in: the load on "
                    + "the bar is converted to newtons before it meets this, "
                    + "so Bar Sag is true millimetres. This is the ONLY place "
                    + "a bending "
                    + "stiffness is asked for, and it is asked for here on "
                    + "purpose. Where the arms go does not depend on it, "
                    + "because stiffness cancels out of that comparison, so "
                    + "putting a number on it upstream would look like it were "
                    + "tuning the placement when it cannot. Here it converts "
                    + "the bar's bending into millimetres you can hold a "
                    + "tolerance against. Steel 40x40x3 SHS is about 1.9e5; a "
                    + "48.3x4 CHS about 2.4e5. Zero or negative reports the "
                    + "shape of the bending without a scale.",
                GH_ParamAccess.item,
                0.0);
            parameters.AddNumberParameter(
                "Tolerance",
                "Tol",
                "How far a node may sit from the solved state and still count "
                    + "as reached, in MILLIMETRES. Reachable and Unreachable "
                    + "are read against this, and nothing else here assumes it.",
                GH_ParamAccess.item,
                5.0);
            for (int slot = 1; slot < parameters.ParamCount; slot++)
                parameters[slot].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "The Result passed through with Fit's own diagnostics "
                    + "replacing its earlier ones: deviation, reachability "
                    + "and bar sag. Chain it through Forces and Supports in "
                    + "any order; each child replaces only its own entries. "
                    + "Wire it to Diagnose.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Deviation",
                "DV",
                "Signed vertical distance from the frame to the solved state "
                    + "at each node, in MILLIMETRES, positive where the frame "
                    + "sits above the state it is heading for. One branch, in "
                    + "VERTEX order, which is the one order here with NO "
                    + "partner tree: DECONSTRUCT's Node IDs are per support "
                    + "strip and its points are branched the same way, so "
                    + "nothing on that side is item-for-item with this. Read "
                    + "it against the Result's own vertex list. Zero "
                    + "everywhere without a frame. This is frame to SOLVED "
                    + "STATE; a photoscan target is a later input and not this "
                    + "one.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Deviation Stats",
                "DS",
                "Three numbers over the whole Deviation field, in mm: the RMS, "
                    + "the worst absolute, and the 95th percentile of the "
                    + "absolute values by nearest rank. One branch of three "
                    + "items, in that order.",
                GH_ParamAccess.tree);
            parameters.AddBooleanParameter(
                "Reachable",
                "RC",
                "One boolean: true when every node's absolute deviation is "
                    + "within Tolerance AT THIS FRAME. That is the whole "
                    + "claim. Whether a constrained solver could drive the "
                    + "machine there is the M1 bridge's question, and it is "
                    + "not answered here. Without a frame the deviation is "
                    + "zero by definition, so this reads true and "
                    + "fit.reachability says the question was not "
                    + "measured.",
                GH_ParamAccess.tree);
            parameters.AddIntegerParameter(
                "Unreachable",
                "UN",
                "The node ids whose absolute deviation is outside Tolerance, "
                    + "ascending. One branch; empty when Reachable is true.",
                GH_ParamAccess.tree);
            parameters.AddNumberParameter(
                "Bar Sag",
                "BS",
                "How far the bar bends away from straight at each notch, in "
                    + "MILLIMETRES, with EI as given. Positive is downward. "
                    + "The bar is solved as a continuous beam on its own "
                    + "columns and anchors, so a notch between two columns "
                    + "sags and a notch over one does not. This is the number "
                    + "to hold a build tolerance against; it is a demand, not "
                    + "a verdict, and no allowable is assumed. As a TREE with "
                    + "one branch per principal line, aligned with FRAME's "
                    + "Principal Nodes branch for branch and item for item. "
                    + "Empty if the state carries no principal runs.",
                GH_ParamAccess.tree);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }

            double stiffness = 0.0;
            data.GetData(1, ref stiffness);
            double tolerance = 5.0;
            data.GetData(2, ref tolerance);
            // Skin's idiom, and for Skin's reason: NaN fails every
            // comparison, so "|deviation| > NaN" is false at every node and
            // Reachable would read TRUE while fit.reachability announced
            // every node within NaN mm. An upstream Expression dividing by
            // zero is the ordinary route to it. A silent pass on a question
            // nobody asked is worse than a warning.
            if (!double.IsFinite(tolerance))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Tolerance must be a real number of millimetres; using 5 mm.");
                tolerance = 5.0;
            }

            try
            {
                Readings r = Read(result, stiffness, tolerance);
                data.SetData(0, new ResultGoo(r.Result));
                data.SetDataTree(1, OutputTree.Numbers(new[] { r.Deviation }));
                data.SetDataTree(2, OutputTree.Numbers(
                    new[] { new List<double> { r.Rms, r.Max, r.P95 } }));
                data.SetDataTree(3, OutputTree.Booleans(
                    new[] { new List<bool> { r.Reachable } }));
                data.SetDataTree(4, OutputTree.Integers(new[] { r.Unreachable }));
                data.SetDataTree(5, OutputTree.Numbers(r.BarSag));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }

        /// <summary>
        /// Everything Fit computes, in one record, so the smoke harness can
        /// drive the same code path the canvas runs without a Rhino.
        /// <see cref="SolveInstance"/> is a thin shell over <see cref="Read"/>.
        /// </summary>
        internal sealed record Readings(
            ResultDto Result,
            List<double> Deviation,
            double Rms,
            double Max,
            double P95,
            bool Reachable,
            List<int> Unreachable,
            List<List<double>> BarSag);

        internal static Readings Read(
            ResultDto result,
            double stiffness,
            double tolerance)
        {
            IReadOnlyList<string> errors = result.Validate();
            if (errors.Count > 0)
                throw new InvalidOperationException(string.Join(" ", errors));

            EquilibriumResultDto equilibrium = result.Equilibrium!;
            MouldDto? mould = result.Mould;
            MouldColumnsDto? block = mould?.Columns;
            MouldFrameDto? frame = mould?.Frame;

            int n = equilibrium.Vertices.Count;
            // The live net when a frame is present, the solved one
            // otherwise. Validation already refuses a frame with the wrong
            // vertex count; testing the count here as well is what lets
            // every net index below be checked once, against n, and never
            // against two different lengths.
            IReadOnlyList<Point3Dto> source =
                frame?.Vertices is IReadOnlyList<Point3Dto> live && live.Count == n
                    ? live
                    : equilibrium.Vertices;
            Point3d[] v = source.Select(p => new Point3d(p.X, p.Y, p.Z)).ToArray();
            bool Known(int i) => i >= 0 && i < v.Length;

            (int, int)[] edges = MouldGeometry.ValidEdges(
                equilibrium, n, out int[] edgeSource);
            List<List<int>> runs = MouldGeometry.PrincipalRuns(equilibrium, n);
            int[] nodeIds = ResultTables.SupportNodes(result);

            // The bar load is built from the Result's own member forces and
            // EI is newtons, so the one conversion happens before the two
            // meet; an unknown unit leaves the load unscaled and
            // fit.bar_sag says the millimetres are not to scale.
            string declaredUnit = (equilibrium.ForceUnit ?? string.Empty).Trim();
            string forceUnit = declaredUnit.Length > 0 ? declaredUnit : "kN";
            double? scale = MonitorMath.ToNewtons(forceUnit);
            bool forceUnitKnown = scale.HasValue;
            double toNewtons = scale ?? 1.0;

            // ---- deviation ----------------------------------------------
            var deviation = new List<double>(n);
            for (int i = 0; i < n; i++)
            {
                deviation.Add(frame is null
                    ? 0.0
                    : (v[i].Z - equilibrium.Vertices[i].Z) * 1000.0);
            }
            (double Rms, double Max, double P95) stats =
                MonitorMath.DeviationStats(deviation);
            var unreachable = new List<int>();
            for (int i = 0; i < deviation.Count; i++)
            {
                if (Math.Abs(deviation[i]) > tolerance)
                    unreachable.Add(i);
            }

            // ---- bar sag ------------------------------------------------
            // A notch is HELD where a column head stands on it, by index,
            // or where it is itself an anchor.
            var held = new HashSet<int>(nodeIds.Where(Known));
            if (block is not null)
            {
                foreach (int node in block.HeadNode)
                {
                    if (Known(node))
                        held.Add(node);
                }
            }
            // The notch positions BarBending returns are Frame's
            // Principal Nodes; only the sag is Fit's to report. The
            // count of bars held at fewer than two notches comes back with
            // it, because their branches are zeros and zeros read as the
            // straightest bars on the model.
            (_, List<List<double>> barSag, int unheldBars) =
                BarBending(
                    runs, v, edges, edgeSource, equilibrium, held, stiffness,
                    toNewtons);

            ResultDto annotated = ResultDiagnostics.Replace(
                result, "Fit", Diagnostics(
                    frame: frame,
                    rms: stats.Rms,
                    max: stats.Max,
                    p95: stats.P95,
                    nodeCount: deviation.Count,
                    unreachable: unreachable.Count,
                    tolerance: tolerance,
                    barSag: barSag,
                    stiffness: stiffness,
                    unheldBars: unheldBars,
                    forceUnit: forceUnit,
                    forceUnitKnown: forceUnitKnown));

            return new Readings(
                annotated,
                deviation,
                stats.Rms,
                stats.Max,
                stats.P95,
                unreachable.Count == 0,
                unreachable,
                barSag);
        }

        /// <summary>
        /// How far each bar bends away from straight, in millimetres.
        ///
        /// EI IS ASKED FOR HERE AND NOWHERE ELSE. Where the arms go is chosen
        /// by comparing one arrangement against another, and stiffness is a
        /// common factor in that comparison, so it cancels: the same arms come
        /// out whatever EI is. Here it turns the shape of the bending into the
        /// millimetres a build tolerance is written in.
        ///
        /// The bar is solved the same way it was placed: an Euler-Bernoulli
        /// beam on point supports, held wherever a column head or an anchor
        /// meets it. With EI at zero the deflected shape is returned with EI of
        /// one; it still shows WHERE the bar bends and in what proportion.
        /// </summary>
        private static (List<List<Point3d>>, List<List<double>>, int) BarBending(
            List<List<int>> runs,
            Point3d[] v,
            (int, int)[] edges,
            int[] edgeSource,
            EquilibriumResultDto equilibrium,
            HashSet<int> held,
            double stiffness,
            double toNewtons)
        {
            var nodes = new List<List<Point3d>>();
            var sag = new List<List<double>>();
            // Bars held at fewer than two notches: their branches are zeros,
            // which is right for alignment and reads as perfect straightness,
            // so the count leaves with them.
            int unheld = 0;
            if (runs.Count == 0)
                return (nodes, sag, unheld);

            double EI = stiffness > 0.0 ? stiffness : 1.0;

            var incident = new List<(int Other, double Force)>[v.Length];
            for (int i = 0; i < v.Length; i++)
                incident[i] = new List<(int, double)>();
            for (int e = 0; e < edges.Length; e++)
            {
                (int a, int b) = edges[e];
                int src = e < edgeSource.Length ? edgeSource[e] : e;
                double force = src < equilibrium.MemberForces.Count
                    ? equilibrium.MemberForces[src]
                    : 0.0;
                incident[a].Add((b, force));
                incident[b].Add((a, force));
            }

            foreach (List<int> run in runs)
            {
                nodes.Add(run.Select(i => v[i]).ToList());
                if (run.Count < 2)
                {
                    // Fewer than two notches is nothing to bend between at
                    // all, which is the same fact the support test below
                    // reports and belongs in the same count.
                    unheld++;
                    sag.Add(new List<double>());
                    continue;
                }

                Vector3d[] pull = MouldGeometry.BarLoads(run, v, incident);
                Vector3d[] across = MouldGeometry.BarTransverse(run, v, pull);
                var arc = new double[run.Count];
                for (int k = 1; k < run.Count; k++)
                    arc[k] = arc[k - 1] + v[run[k - 1]].DistanceTo(v[run[k]]);
                // EI is N.m2, and the load is built from the Result's own
                // member forces, so it is converted here: without it a kN
                // Result reports a thousandth of the sag it will actually
                // build with, in a number the port calls millimetres.
                double[] load = across
                    .Select(a => Math.Abs(a.Z) * toNewtons)
                    .ToArray();
                int[] supports = Enumerable.Range(0, run.Count)
                    .Where(k => held.Contains(run[k]))
                    .ToArray();

                // Under two supports the bar is a mechanism, not a beam.
                if (supports.Length < 2)
                {
                    unheld++;
                    sag.Add(Enumerable.Repeat(0.0, run.Count).ToList());
                    continue;
                }

                (double[]? deflection, double[]? _) =
                    BeamSolver.Response(arc, load, supports, EI);
                sag.Add(deflection is null
                    ? Enumerable.Repeat(0.0, run.Count).ToList()
                    : deflection.Select(d => d * 1000.0).ToList());
            }

            return (nodes, sag, unheld);
        }

        private static List<DiagnosticDto> Diagnostics(
            MouldFrameDto? frame,
            double rms,
            double max,
            double p95,
            int nodeCount,
            int unreachable,
            double tolerance,
            List<List<double>> barSag,
            double stiffness,
            int unheldBars,
            string forceUnit,
            bool forceUnitKnown)
        {
            const string S = "Fit";
            var d = new List<DiagnosticDto>();

            if (frame is not null && frame.Time < 100.0 - 1.0e-9)
            {
                d.Add(ResultDiagnostics.Entry(S, "fit.intermediate_frame", "info",
                    "this is an intermediate frame, so the geometry is part way "
                        + "through the build while the forces are those of the "
                        + "finished state. Read it as where the structure is going.",
                    frame.Time, unit: "percent"));
            }

            d.Add(frame is null
                ? ResultDiagnostics.Entry(S, "fit.deviation", "info",
                    "no frame on this Result, so the deviation to the solved state is "
                        + "zero everywhere by definition. Wire Animate upstream to read "
                        + "it at a frame.",
                    0.0, unit: "mm")
                : ResultDiagnostics.Entry(S, "fit.deviation", "info",
                    $"the frame stands {rms:0.##} mm RMS off the solved "
                        + $"state, {max:0.##} mm at worst and "
                        + $"{p95:0.##} mm at the 95th percentile.",
                    max, unit: "mm",
                    context: ResultDiagnostics.Context(
                        ("rms", rms.ToString("0.###", CultureInfo.InvariantCulture)),
                        ("p95", p95.ToString("0.###", CultureInfo.InvariantCulture)))));
            if (frame is null)
            {
                // Without a frame the net IS the solved state, so every node is
                // trivially inside any tolerance. Reporting that as reachable
                // would be a verdict on a question nobody asked.
                d.Add(ResultDiagnostics.Entry(S, "fit.reachability", "info",
                    "no frame on this Result, so deviation is zero by definition and "
                        + "reachability is not measured. Wire Animate upstream to put "
                        + "the machine at a frame and ask the question properly.",
                    unit: "nodes"));
            }
            else
            {
                d.Add(unreachable == 0
                    ? ResultDiagnostics.Entry(S, "fit.reachability", "ok",
                        $"every one of the {nodeCount} nodes is within {tolerance:0.##} mm "
                            + "of the solved state at this frame.",
                        0.0, tolerance: tolerance, unit: "nodes")
                    : ResultDiagnostics.Entry(S, "fit.reachability", "warning",
                        $"{unreachable} of {nodeCount} nodes sit further than "
                            + $"{tolerance:0.##} mm from the solved state. That is "
                            + "reachability AT THIS FRAME and nothing more; whether the "
                            + "machine can be driven there is the M1 bridge's question.",
                        unreachable, tolerance: tolerance, unit: "nodes"));
            }

            double worstSag = barSag.SelectMany(b => b).Select(Math.Abs).DefaultIfEmpty(0.0).Max();
            // A bar held at fewer than two notches is a mechanism, not a
            // beam, so its branch is zeros. Left unsaid, those zeros are the
            // most reassuring numbers on the model, sitting under the least
            // supported bar there is.
            string unheldNote = unheldBars > 0
                ? $" {unheldBars} of them cannot be solved as a beam at all, being "
                    + "held at fewer than two notches or carrying fewer than two, so "
                    + "nothing is solved for them: that is a bar with nothing to bend "
                    + "between, not a straight one."
                : string.Empty;
            if (barSag.Count == 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "fit.bar_sag_absent", "info",
                    "bar bending not reported: this Result carries no principal "
                        + "runs, so there is no bar to solve as a beam."));
            }
            else if (stiffness > 0.0)
            {
                d.Add(ResultDiagnostics.Entry(S, "fit.bar_sag", "info",
                    $"bars bend up to {worstSag:0.##} mm between their supports, with "
                        + $"EI {stiffness:G4} N.m2. That is the demand to hold a build "
                        + "tolerance against; no allowable is assumed here."
                        + unheldNote
                        + (forceUnitKnown
                            ? string.Empty
                            : $" This Result's forces are in '{forceUnit}', which is "
                                + "neither N nor kN, so the bar load met EI "
                                + "UNCONVERTED and these millimetres are not to scale "
                                + "until the Result names a unit."),
                    worstSag, unit: "mm",
                    context: ResultDiagnostics.Context(
                        ("EI", stiffness.ToString("G6", CultureInfo.InvariantCulture)),
                        ("unheld", unheldBars.ToString(CultureInfo.InvariantCulture)))));
            }
            else
            {
                d.Add(ResultDiagnostics.Entry(S, "fit.bar_sag_shape_only", "info",
                    "bar bending is reported as SHAPE ONLY, because EI was left at "
                        + "zero. It shows where the bar bends and in what proportion, "
                        + "and it is not millimetres. Give EI the section you mean to "
                        + "build to put a scale on it."
                        + unheldNote,
                    worstSag));
            }
            if (unheldBars > 0)
            {
                d.Add(ResultDiagnostics.Entry(S, "fit.bar_unheld", "warning",
                    $"{unheldBars} bars cannot be solved as a beam: they are held at "
                        + "fewer than two notches, by a column head or an anchor, or "
                        + "carry fewer than two notches at all. A bar on one support or "
                        + "none is a mechanism, so no sag is solved for it and its "
                        + "branch reads zero. Run Columns, or place a head on it, "
                        + "before reading its bending.",
                    unheldBars, unit: "bars"));
            }
            return d;
        }
    }
}
