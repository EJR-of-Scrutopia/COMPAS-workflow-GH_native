#nullable enable

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;
using Rhino.Display;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Building the tree outputs, in one place, so that every component that
    /// hands back grouped geometry groups it the same way.
    ///
    /// The rule these components follow is that a BRANCH IS A THING: one
    /// principal line, one anchor strip, one boundary loop, one column tree.
    /// Not one item, and not the whole lot. A flat list of every notch on every
    /// bar, sorted by node index, carries no trace of which bar a notch was on,
    /// and rebuilding that downstream means re-deriving the bars from geometry
    /// that the component had in front of it and threw away.
    ///
    /// EMPTY BRANCHES ARE KEPT, which is the part worth stating. When several
    /// outputs branch by the same thing, branch {2} must mean bar 2 in all of
    /// them, and it stops meaning that the moment one output quietly omits a
    /// bar that happened to have nothing in it. Every branch is created before
    /// it is filled, so an empty one survives as an empty branch rather than
    /// shifting everything after it up by one.
    /// </summary>
    public static class OutputTree
    {
        public static GH_Structure<GH_Point> Points(
            IEnumerable<IEnumerable<Point3d>> branches) =>
            Build(branches, value => new GH_Point(value));

        public static GH_Structure<GH_Line> Lines(
            IEnumerable<IEnumerable<Line>> branches) =>
            Build(branches, value => new GH_Line(value));

        public static GH_Structure<GH_Curve> Curves(
            IEnumerable<IEnumerable<Curve>> branches) =>
            Build(branches, value => new GH_Curve(value));

        public static GH_Structure<GH_Vector> Vectors(
            IEnumerable<IEnumerable<Vector3d>> branches) =>
            Build(branches, value => new GH_Vector(value));

        public static GH_Structure<GH_Number> Numbers(
            IEnumerable<IEnumerable<double>> branches) =>
            Build(branches, value => new GH_Number(value));

        public static GH_Structure<GH_Integer> Integers(
            IEnumerable<IEnumerable<int>> branches) =>
            Build(branches, value => new GH_Integer(value));

        public static GH_Structure<GH_Boolean> Booleans(
            IEnumerable<IEnumerable<bool>> branches) =>
            Build(branches, value => new GH_Boolean(value));

        public static GH_Structure<GH_String> Strings(
            IEnumerable<IEnumerable<string>> branches) =>
            Build(branches, value => new GH_String(value));

        private static GH_Structure<TGoo> Build<TValue, TGoo>(
            IEnumerable<IEnumerable<TValue>> branches,
            Func<TValue, TGoo> wrap)
            where TGoo : IGH_Goo
        {
            var tree = new GH_Structure<TGoo>();
            int index = 0;
            foreach (IEnumerable<TValue> branch in branches)
            {
                var path = new GH_Path(index++);
                // Before filling it, so a branch with nothing in it is still a
                // branch. See the class note: this is what keeps branch {2} the
                // same bar in every output that branches by bar.
                tree.EnsurePath(path);
                foreach (TValue value in branch)
                    tree.Append(wrap(value), path);
            }
            return tree;
        }
    }

    /// <summary>
    /// Mould Animate: replay the reconfigurable mould building itself, from one
    /// timeline slider.
    ///
    /// Everything the animation needs is already in the solved Result, so there
    /// is nothing to dial. The final geometry says how high the columns must
    /// lift the bars and how far the steppers must reel each infill cable; the
    /// component works both out and interpolates between the flat net on the
    /// ground and that final state.
    ///
    ///   bare    the surface the net takes between the principal bars with
    ///           nothing reeled in, found by relaxing every free node to the
    ///           average of its neighbours with the bars and anchors pinned.
    ///           That is the uniform force-density equilibrium, so by Schek's
    ///           Theorem 1 it is the minimum-way surface: flat or saddled,
    ///           never domed. This carries the HEIGHT.
    ///   relief  what the steppers must reel on top of it to reach the Result.
    ///           This carries the SAG.
    ///
    /// The net starts as the ORIGINAL PATTERN, read back up the chain from the
    /// Result through its Problem's topology, so frame zero is the flat plan
    /// the whole thing was drawn from rather than a level guessed from the
    /// solved geometry. A frame is
    ///
    ///     z = pattern + height * (bare - pattern) + sag * relief
    ///
    /// so at height zero everything stays down on the pattern while the first
    /// reeling happens, which is the order the machine actually builds in.
    ///
    /// The timeline runs in FOUR phases: reel (0 to 30) draws the net in on
    /// the ground, raise (30 to 60) rotates the columns up and lifts the
    /// bars, finish (60 to 90) reels the rest against the bars, and hold
    /// (90 to 100) keeps the shape while load arrives.
    ///
    /// The columns are rigid and their FEET ARE FIXED. Every tree stands on
    /// the foot Columns built for it, from frame zero, and turns about that
    /// foot as ONE BODY: its heads ride the live net and its fork keeps its
    /// built fraction along the live foot-to-main segment. At time zero a
    /// trunk lies flat along its rail from its foot to its notch's drawn
    /// position; as the notch rises the trunk rotates up, and its length at
    /// this frame is what the ram delivers. Nothing slides and nothing is
    /// re-aimed.
    ///
    /// This component animates. It runs no equilibrium check and it places no
    /// columns; Column Finder owns that.
    /// </summary>
    public sealed class MouldAnimateComponent : NativeComponentBase
    {
        public MouldAnimateComponent()
            : base(
                "Animate",
                "AN",
                "Replay the mould building itself from one timeline slider, in "
                    + "four phases: reel the net into shape on the ground, raise "
                    + "it on the columns, finish by tensioning both axes against "
                    + "them, then hold the shape while load arrives. Sag and "
                    + "height are read from the solved Result, not dialled. The "
                    + "geometry of a frame is Frame's, which reads it back off "
                    + "this Result.",
                ComponentCategories.Mould,
                "mould_animate")
        {
        }

        private string _bareKey = string.Empty;
        private double[]? _bareSurface;
        private Mesh? _previewMesh;
        private readonly List<Line> _previewCables = new();
        private readonly List<Line> _previewColumns = new();
        private readonly List<Point3d> _previewSupports = new();
        private BoundingBox _clippingBox = BoundingBox.Empty;

        public override Guid ComponentGuid =>
            new("b1f4c7a2-5d63-4e19-9c88-3a7e6d0b52f4");

        public override bool IsPreviewCapable => true;

        public override BoundingBox ClippingBox => _clippingBox;

        protected override void BeforeSolveInstance()
        {
            base.BeforeSolveInstance();
            _previewMesh = null;
            _previewCables.Clear();
            _previewColumns.Clear();
            _previewSupports.Clear();
            _clippingBox = BoundingBox.Empty;
        }

        /// <summary>
        /// Draw the frame in the viewport the way TNA Solve draws its solved
        /// network, with the same shaded material, wire colour and support
        /// points, so an animation reads as the same object at a different
        /// moment rather than as a different kind of drawing. The geometry
        /// outputs stay hidden, as on Deconstruct, so nothing double-draws.
        /// </summary>
        public override void DrawViewportMeshes(IGH_PreviewArgs args)
        {
            if (Hidden || _previewMesh is null || _previewMesh.Faces.Count == 0)
                return;
            args.Display.DrawMeshShaded(
                _previewMesh,
                new DisplayMaterial(Color.FromArgb(225, 222, 215), 0.35));
        }

        public override void DrawViewportWires(IGH_PreviewArgs args)
        {
            if (Hidden)
                return;
            base.DrawViewportWires(args);
            if (_previewMesh is not null && _previewMesh.Faces.Count > 0)
            {
                args.Display.DrawMeshWires(
                    _previewMesh, Color.FromArgb(95, 95, 100));
            }
            else
            {
                // No faces to shade, an FD result for instance, so the net
                // itself carries the drawing.
                foreach (Line cable in _previewCables)
                    args.Display.DrawLine(cable, Color.FromArgb(95, 95, 100));
            }
            // The same blue Column Finder draws its columns in, so a raising
            // column reads as the same member at a different moment.
            foreach (Line column in _previewColumns)
                args.Display.DrawLine(column, Color.FromArgb(40, 85, 175), 3);
            foreach (Point3d point in _previewSupports)
            {
                args.Display.DrawPoint(
                    point,
                    PointStyle.RoundControlPoint,
                    4,
                    Color.FromArgb(30, 165, 85));
            }
        }

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "Solved FD or TNA result. Its geometry IS the final state, so "
                    + "the sag and the lift are read from it rather than set.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Time",
                "T",
                "0 to 100, the whole build in one slider. Four phases: reel "
                    + "(0 to 30) draws the net in on the ground, raise (30 to "
                    + "60) rotates the columns up and lifts the bars, finish "
                    + "(60 to 90) reels the rest against the bars, hold (90 to "
                    + "100) keeps the shape while load arrives.",
                GH_ParamAccess.item,
                100.0);
            parameters.AddNumberParameter(
                "Pre-Sag",
                "PS",
                "0 to 100, as a percentage of the FINAL sag: how much is reeled "
                    + "in before the columns lift. The remainder is reeled "
                    + "after, which is the part that tightens the form against "
                    + "the bars.",
                GH_ParamAccess.item,
                40.0);
            parameters.AddNumberParameter(
                "Extension",
                "E",
                "How much of a column's built length its ram can drive out, in "
                    + "percent. The feet are fixed, so this is a CHECK, not a "
                    + "driver: a trunk whose length at this frame falls below "
                    + "built x (100 - Extension)% or above built is reported by "
                    + "animate.ram_range.",
                GH_ParamAccess.item,
                40.0);
            parameters[1].Optional = true;
            parameters[2].Optional = true;
            parameters[3].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "The Result this component was given, with this frame written "
                    + "into its Mould block: time, phase, the live net and the "
                    + "live column nodes. The built columns travel through "
                    + "untouched. Wire it to FRAME for the geometry at this "
                    + "frame, to Monitor for the numbers and to Diagnose for "
                    + "the words.",
                GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }

            double timePct = 100.0;
            double preSag = 40.0;
            data.GetData(1, ref timePct);
            data.GetData(2, ref preSag);
            double extendPct = 40.0;
            data.GetData(3, ref extendPct);

            // A NaN survives Math.Min and Math.Max untouched, so the clamps
            // below are no guard at all. An Expression that divides by zero
            // upstream would put NaN straight into Frame.Time, and this
            // component validates the Result it is GIVEN and never the one it
            // emits, so the NaN would first surface downstream, in Monitor's
            // re-validation or as a serialiser failure in Export.
            var notFinite = new List<string>();
            if (!double.IsFinite(timePct))
            {
                timePct = 100.0;
                notFinite.Add("Time");
            }
            if (!double.IsFinite(preSag))
            {
                preSag = 40.0;
                notFinite.Add("Pre-Sag");
            }
            if (!double.IsFinite(extendPct))
            {
                extendPct = 40.0;
                notFinite.Add("Extension");
            }
            if (notFinite.Count > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    string.Join(" and ", notFinite)
                        + (notFinite.Count == 1 ? " is" : " are")
                        + " not a finite number, so the default was used "
                        + "instead. A NaN passes through a clamp unchanged and "
                        + "would travel on inside the Result.");
            }

            MouldColumnsDto? columnsBlock = result.Mould?.Columns;
            bool hasColumns = columnsBlock is not null && columnsBlock.Members.Count > 0;

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                EquilibriumResultDto equilibrium = result.Equilibrium!;
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
                List<List<int>> bars = MouldGeometry.PrincipalRuns(
                    equilibrium, target.Length);
                var principalIds = new HashSet<int>(bars.SelectMany(b => b));
                if (principalIds.Count == 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        "The Result carries no principal lines, so nothing is "
                            + "held and there is nothing to lift. Draw Principal "
                            + "Lines into Pattern upstream.");
                }

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
                if (_bareSurface is null ||
                    _bareSurface.Length != n ||
                    !string.Equals(_bareKey, bareKey, StringComparison.Ordinal))
                {
                    _bareSurface = MouldGeometry.BareSurface(
                        target, neighbours, pinned);
                    _bareKey = bareKey;
                }
                double[] bare = _bareSurface;
                var relief = new double[n];
                for (int i = 0; i < n; i++)
                    relief[i] = target[i].Z - bare[i];

                // Sag and height both come out of the Result, so Time is the
                // only thing left to drive.
                double time = Math.Min(Math.Max(timePct, 0.0), 100.0) / 100.0;
                double pre = Math.Min(Math.Max(preSag, 0.0), 100.0) / 100.0;
                (double sag, double lift, string phase) =
                    MouldGeometry.Phases(time, pre);
                string phaseDetail = phase switch
                {
                    "reel" => $"reel: reeling flat on the ground, {sag * 100:0}% "
                        + $"of the final sag, heading for {pre * 100:0}%",
                    "raise" => $"raise: columns rotating up about their feet, "
                        + $"{lift * 100:0}% of the height, holding {pre * 100:0}% sag",
                    "finish" => "finish: tensioning both axes against the columns, "
                        + $"{sag * 100:0}% sag",
                    _ => "hold: the mould holds its shape while load arrives",
                };

                // The thrust direction at each notch on THIS frame's own
                // geometry. Nothing is re-aimed by it: the columns are rigid
                // and stand where their feet and their notches put them. It is
                // computed only so animate.column_alignment can measure each
                // trunk against the thrust at its notch and report how far off
                // the force path the machine is at this frame.
                var liveAim = new Dictionary<int, Vector3d>();

                var live = new Point3d[n];
                for (int i = 0; i < n; i++)
                {
                    // SAG drives the plan as well as the depth, because they
                    // are the same operation seen twice: a cable reeled in
                    // pulls the net toward its bar and lets it drop between
                    // them at once. LIFT is the columns, and it moves only the
                    // height, so at lift zero the whole net stays down where it
                    // was drawn while the first reeling happens.
                    double z = start[i].Z
                        + (lift * (bare[i] - start[i].Z))
                        + (sag * relief[i]);
                    live[i] = new Point3d(
                        start[i].X + (sag * (target[i].X - start[i].X)),
                        start[i].Y + (sag * (target[i].Y - start[i].Y)),
                        z);
                }

                if (hasColumns)
                {
                    var edgeForce = new double[edges.Length];
                    for (int e = 0; e < edges.Length; e++)
                    {
                        int src = e < edgeSource.Length ? edgeSource[e] : e;
                        edgeForce[e] = src < equilibrium.MemberForces.Count
                            ? equilibrium.MemberForces[src]
                            : 0.0;
                    }
                    var incident = new List<(int Other, double Force)>[n];
                    for (int i = 0; i < n; i++)
                        incident[i] = new List<(int, double)>();
                    for (int e = 0; e < edges.Length; e++)
                    {
                        incident[edges[e].Item1].Add(
                            (edges[e].Item2, edgeForce[e]));
                        incident[edges[e].Item2].Add(
                            (edges[e].Item1, edgeForce[e]));
                    }
                    foreach (List<int> run in bars)
                    {
                        Vector3d[] pull =
                            MouldGeometry.BarLoads(run, live, incident);
                        Vector3d[] across =
                            MouldGeometry.BarTransverse(run, live, pull);
                        for (int k = 0; k < run.Count; k++)
                        {
                            liveAim[run[k]] = MouldGeometry.AimFrom(across[k]);
                        }
                    }
                }

                // The columns at this frame, on the feet the block was built
                // with. Worked out here, before the diagnostics, because the
                // FRAME carries them and the frame is what the geometry is
                // read back out of.
                Point3d[]? liveColumnNodes = hasColumns
                    ? MouldGeometry.LiveColumnNodes(columnsBlock!, live)
                    : null;

                // THE FRAME, written into the Result, and its geometry read
                // straight back out of it. What Animate draws and what Frame
                // emits are the same call: the mesh, the cables, the notches,
                // the anchors, the boundary and the columns are
                // FrameGeometry's, and what is left in this component is the
                // animation itself.
                var frame = new MouldFrameDto
                {
                    Time = Math.Min(Math.Max(timePct, 0.0), 100.0),
                    Phase = phase,
                    Lift = Math.Min(Math.Max(lift, 0.0), 1.0),
                    Sag = Math.Min(Math.Max(sag, 0.0), 1.0),
                    Vertices = live.Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                    ColumnNodes = liveColumnNodes?
                        .Select(p => new Point3Dto(p.X, p.Y, p.Z))
                        .ToArray(),
                };
                MouldDto mould = (result.Mould ?? new MouldDto()) with
                {
                    Ground = ground,
                    Frame = frame,
                };
                ResultDto framedResult = result with { Mould = mould };
                FrameGeometry.Set set = FrameGeometry.Build(framedResult);

                double barRise = principalIds.Count > 0
                    ? lift * (principalIds
                        .Select(i => bare[i] - start[i].Z).Average())
                    : 0.0;
                int wantsPush = relief.Count(r => r > 1e-9);

                const string S = "Animate";
                var entries = new List<DiagnosticDto>
                {
                    ResultDiagnostics.Entry(S, "animate.phase", "info", phaseDetail,
                        Math.Min(Math.Max(timePct, 0.0), 100.0), unit: "percent"),
                    ResultDiagnostics.Entry(S, "animate.counts", "info",
                        $"nodes {n}, cables {edges.Length}, bars {bars.Count} carrying "
                            + $"{principalIds.Count} notches; anchors {anchorIds.Count}, "
                            + $"perimeter nodes {set.PerimeterCount}; "
                            + $"{principalIds.Count * 2} steppers, two per notch",
                        n, unit: "nodes",
                        context: ResultDiagnostics.Context(
                            ("cables", edges.Length.ToString(CultureInfo.InvariantCulture)),
                            ("bars", bars.Count.ToString(CultureInfo.InvariantCulture)),
                            ("notches", principalIds.Count.ToString(CultureInfo.InvariantCulture)),
                            ("anchors", anchorIds.Count.ToString(CultureInfo.InvariantCulture)),
                            ("perimeter", set.PerimeterCount.ToString(CultureInfo.InvariantCulture)),
                            ("steppers", (principalIds.Count * 2).ToString(CultureInfo.InvariantCulture)))),
                    ResultDiagnostics.Entry(S, "animate.ground", "info",
                        $"ground read as {ground:0.###}, the level the anchors sit at, "
                            + "which is what the columns stand on",
                        ground, unit: "model units"),
                    ResultDiagnostics.Entry(S, "animate.start", "info",
                        startIsFinal
                            ? "the pattern this Result carries IS its own solved shape, "
                                + "so there was nothing to rise from; the net starts "
                                + "flat at ground instead"
                            : fromPattern
                                ? "starting from the ORIGINAL PATTERN, the plan as "
                                    + "drawn, read off the Result's own Problem, so "
                                    + "frame zero is what Pattern holds"
                                : "this Result carries no source pattern, so the net "
                                    + "starts flat at ground, the base of the solved "
                                    + "geometry",
                        context: ResultDiagnostics.Context(
                            ("source", startIsFinal ? "final" : fromPattern ? "pattern" : "flat"))),
                    ResultDiagnostics.Entry(S, "animate.travel", "info",
                        $"net travels from {start.Min(p => p.Z):0.###}/"
                            + $"{start.Max(p => p.Z):0.###} at frame zero to "
                            + $"{ground:0.###}/{target.Max(p => p.Z):0.###} at the end, "
                            + $"reeling {relief.Max(Math.Abs) * 1000.0:0.#} mm at the "
                            + "deepest node",
                        relief.Max(Math.Abs) * 1000.0, unit: "mm"),
                    ResultDiagnostics.Entry(S, "animate.plan_draw", "info",
                        $"net draws in {planTravel * 1000.0:0.#} mm in plan as the "
                            + "sag grows, through reel and finish",
                        planTravel * 1000.0, unit: "mm"),
                    ResultDiagnostics.Entry(S, "animate.bar_rise", "info",
                        $"bars risen {barRise * 1000.0:0.#} mm at this frame",
                        barRise * 1000.0, unit: "mm"),
                };
                if (set.Mesh is null)
                {
                    entries.Add(ResultDiagnostics.Entry(S, "animate.no_faces", "info",
                        "this Result carries no faces, so there is no shaded surface "
                            + "and the perimeter is read from the net's topology "
                            + "instead. That is expected for FD."));
                }
                if (set.PerimeterEstimated)
                {
                    entries.Add(ResultDiagnostics.Entry(
                        S, "animate.perimeter_estimated", "info",
                        "this Result carries no faces of its own and no pattern "
                            + "topology with faces, so the perimeter above is an "
                            + "ESTIMATE from node degree rather than a boundary: "
                            + "the nodes joined to fewer neighbours than the middle "
                            + "of the net. That set need not be a loop, or even be "
                            + "on the rim, so Perimeter Lines is left EMPTY rather "
                            + "than draw a curve through it and call it the boundary.",
                        set.PerimeterCount, unit: "nodes"));
                }
                if (wantsPush > 0)
                {
                    entries.Add(ResultDiagnostics.Entry(S, "animate.nodes_want_push", "warning",
                        $"{wantsPush} nodes sit ABOVE the bare surface, so they are "
                            + "asking to be pushed up. A reel only pulls down. That is "
                            + "curvature a net cannot make between the bars, and it "
                            + "needs a mechanism this machine does not have.",
                        wantsPush, unit: "nodes",
                        context: ResultDiagnostics.Context(("total", n.ToString(CultureInfo.InvariantCulture)))));
                }

                // The columns, from frame zero. Every tree stands on the foot
                // Columns built for it. Its TRUNK turns about that foot as a
                // rigid body: the fork keeps its built fraction along the live
                // foot-to-main segment, so at time zero the trunk lies flat
                // along the rail from its foot to its notch's drawn position
                // and rises with the notch, its length being what the ram
                // delivers. Its ARMS run from that fork to their own notches,
                // which ride the net independently, so an arm's length changes
                // frame to frame and animate.arm_stretch says how far. Nothing
                // slides and nothing is re-aimed: the trunk points where its
                // foot and its notch put it, and how far that is from the
                // force path is reported.
                if (extendPct > 95.0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        $"Extension {extendPct:0.#} is held at 95: a ram that "
                            + "drove out more than 95% of a column's built "
                            + "length would leave nothing retracted. The check "
                            + "below uses 95.");
                }
                double extend = Math.Min(Math.Max(extendPct, 0.0), 95.0) / 100.0;
                var liveColumns = new List<Line>();
                double shortest = double.MaxValue;
                double longest = 0.0;
                int totalMembers = 0;
                int collapsedMembers = 0;
                int ramViolations = 0;
                double worstRatio = 1.0;
                int worstBranch = -1;
                int worstFoot = -1;
                double worstAlign = 0.0;
                int alignedTrunks = 0;
                int armsMeasured = 0;
                double worstArm = 1.0;
                int worstArmBranch = -1;
                int worstArmMember = -1;

                if (hasColumns)
                {
                    MouldGeometry.ColumnTree tree =
                        MouldGeometry.TreeFromBlock(columnsBlock!);
                    Point3d[] at = liveColumnNodes!;
                    var footSet = new HashSet<int>(tree.Feet);
                    var headVertex = new Dictionary<int, int>();
                    for (int h = 0; h < columnsBlock!.Heads.Count && h < columnsBlock.HeadNode.Count; h++)
                        headVertex[columnsBlock.Heads[h]] = columnsBlock.HeadNode[h];

                    // Branch by the grouping the BLOCK already carries when it
                    // accounts for every member exactly once, so Columns branch
                    // {i} here is Trees[{i}] there and the two components agree
                    // without either rederiving the other's answer. TreesByFoot
                    // is the fallback for a block whose Trees do not cover the
                    // members it carries.
                    List<List<int>> groups =
                        FrameGeometry.ColumnGroups(columnsBlock!, tree);

                    for (int b = 0; b < groups.Count; b++)
                    {
                        List<int> group = groups[b];
                        for (int k = 0; k < group.Count; k++)
                        {
                            int m = group[k];
                            if (m < 0 || m >= tree.Members.Count)
                                continue;
                            (int lower, int upper) = tree.Members[m];
                            double length = at[lower].DistanceTo(at[upper]);
                            double builtLength =
                                tree.Nodes[lower].DistanceTo(tree.Nodes[upper]);
                            totalMembers++;

                            // MEASURE FIRST, DRAW AFTER. A member whose two
                            // ends have met is the most extreme reach there is,
                            // and testing for it before measuring made the one
                            // case that most needs reporting the one case that
                            // reported nothing at all.
                            if (footSet.Contains(lower))
                            {
                                // A trunk. The ram: this frame's length against
                                // the built one, inside the range the ram
                                // allows. A collapsed trunk is ratio 0, which
                                // is a violation.
                                if (builtLength > 1.0e-9)
                                {
                                    double ratio = length / builtLength;
                                    if (ratio < (1.0 - extend) - 1.0e-9 ||
                                        ratio > 1.0 + 1.0e-9)
                                    {
                                        ramViolations++;
                                        if (Math.Abs(ratio - 1.0) > Math.Abs(worstRatio - 1.0))
                                        {
                                            worstRatio = ratio;
                                            worstBranch = b;
                                            worstFoot = lower;
                                        }
                                    }
                                }
                                // Alignment: the trunk against the live thrust
                                // at its main notch.
                                int head = tree.Above[upper].Count == 0
                                    ? upper
                                    : MouldGeometry.MainBranch(tree, upper);
                                // A collapsed trunk has no direction to
                                // measure; counting it as aligned at zero
                                // degrees would report perfect alignment where
                                // nothing was measurable.
                                if (length > 1.0e-9 &&
                                    headVertex.TryGetValue(head, out int vertex) &&
                                    liveAim.TryGetValue(vertex, out Vector3d aim))
                                {
                                    Vector3d direction = at[upper] - at[lower];
                                    worstAlign = Math.Max(
                                        worstAlign, ColumnPlacement.AngleBetween(direction, aim));
                                    alignedTrunks++;
                                }
                            }
                            else if (builtLength > 1.0e-9)
                            {
                                // An ARM: a fixed limb from a fork to a notch,
                                // with no ram in it. Both its ends move, so its
                                // length is a measurement of whether the frame
                                // is asking a rigid member to change length.
                                double ratio = length / builtLength;
                                armsMeasured++;
                                // The first arm measured is the worst so far,
                                // so an arm that reads exactly 100% is still
                                // named rather than leaving the entry at -1.
                                if (worstArmMember < 0 ||
                                    Math.Abs(ratio - 1.0) > Math.Abs(worstArm - 1.0))
                                {
                                    worstArm = ratio;
                                    worstArmBranch = b;
                                    worstArmMember = k;
                                }
                            }

                            if (length <= 1.0e-9)
                            {
                                collapsedMembers++;
                                continue;
                            }
                            var member = new Line(at[lower], at[upper]);
                            liveColumns.Add(member);
                            shortest = Math.Min(shortest, length);
                            longest = Math.Max(longest, length);
                        }
                    }
                }

                // Emitted whenever the Result carries columns, not only when
                // something was drawn. A frame in which every member has
                // collapsed is exactly the frame a reader most needs told
                // about, and gating on the drawn count made that the one frame
                // Animate said nothing about at all.
                if (hasColumns)
                {
                    double drawnShortest = liveColumns.Count > 0 ? shortest : 0.0;
                    entries.Add(ResultDiagnostics.Entry(S, "animate.columns", "info",
                        $"{liveColumns.Count} of {totalMembers} column member(s) drawn "
                            + $"at this frame, {drawnShortest:0.###} to {longest:0.###} "
                            + "long"
                            + (collapsedMembers > 0
                                ? $"; {collapsedMembers} member(s) have collapsed to "
                                    + "nothing at this frame and are not drawn, which "
                                    + "is why a branch can come back short or empty"
                                : string.Empty)
                            + ". Every tree stands on its built foot from frame zero; "
                            + "its trunk turns about that foot and its length is the "
                            + "ram, while its arms follow their own notches.",
                        liveColumns.Count, unit: "members",
                        context: ResultDiagnostics.Context(
                            ("shortest", drawnShortest.ToString("0.###", CultureInfo.InvariantCulture)),
                            ("longest", longest.ToString("0.###", CultureInfo.InvariantCulture)),
                            ("members", totalMembers.ToString(CultureInfo.InvariantCulture)),
                            ("collapsed", collapsedMembers.ToString(CultureInfo.InvariantCulture)))));
                    entries.Add(ResultDiagnostics.Entry(S, "animate.column_alignment", "info",
                        alignedTrunks == 0
                            ? "no trunk could be measured against a live aim at this "
                                + "frame, so the zero below is nothing measured rather "
                                + "than perfect alignment. Nothing is re-aimed either "
                                + "way: a trunk points where its foot and its notch "
                                + "put it."
                            : $"{alignedTrunks} trunk(s) measured, standing up to "
                                + $"{worstAlign:0.#} degrees off the live thrust at "
                                + "their notch at this frame. Nothing is re-aimed: a "
                                + "trunk points where its foot and its notch put it.",
                        worstAlign, unit: "degrees",
                        context: ResultDiagnostics.Context(
                            ("measured", alignedTrunks.ToString(CultureInfo.InvariantCulture)))));
                    if (armsMeasured > 0)
                    {
                        entries.Add(ResultDiagnostics.Entry(S, "animate.arm_stretch", "info",
                            $"{armsMeasured} arm(s) measured, the worst at "
                                + $"{worstArm * 100:0}% of its built length, member "
                                + $"{worstArmMember} of Columns branch {worstArmBranch}. "
                                + "An arm has no ram: it is a fixed limb from a fork to "
                                + "its notch, and both its ends move on the net, so a "
                                + "figure away from 100% is the frame asking a rigid "
                                + "member to change length.",
                            worstArm, unit: "ratio",
                            context: ResultDiagnostics.Context(
                                ("arms", armsMeasured.ToString(CultureInfo.InvariantCulture)),
                                ("branch", worstArmBranch.ToString(CultureInfo.InvariantCulture)),
                                ("member", worstArmMember.ToString(CultureInfo.InvariantCulture)))));
                    }
                    if (ramViolations > 0)
                    {
                        // A warning only once the columns are up. Below lift 1
                        // the trunks are mid-rotation and their live length is
                        // MEANT to be short of built, so warning on every early
                        // frame taught the reader to skip the line.
                        entries.Add(ResultDiagnostics.Entry(
                            S, "animate.ram_range",
                            lift >= 1.0 ? "warning" : "info",
                            $"{ramViolations} trunk(s) need a length outside their ram's "
                                + $"range at this frame, which is {phase}. The worst is "
                                + $"at {worstRatio * 100:0}% of built length against a "
                                + $"range of {(1.0 - extend) * 100:0}% to 100%: Columns "
                                + $"branch {worstBranch}, standing on foot node "
                                + $"{worstFoot}. The trunk cannot be this short while "
                                + "retracted; the machine cannot follow this frame "
                                + "exactly.",
                            worstRatio, unit: "ratio",
                            context: ResultDiagnostics.Context(
                                ("violations", ramViolations.ToString(CultureInfo.InvariantCulture)),
                                ("extension", (extend * 100.0).ToString("0", CultureInfo.InvariantCulture)),
                                ("phase", phase),
                                ("branch", worstBranch.ToString(CultureInfo.InvariantCulture)),
                                ("foot", worstFoot.ToString(CultureInfo.InvariantCulture)))));
                    }
                }

                _previewMesh = set.Mesh;
                _previewCables.Clear();
                _previewCables.AddRange(set.Cables.SelectMany(branch => branch));
                _previewColumns.Clear();
                _previewColumns.AddRange(
                    set.ColumnBranches.SelectMany(branch => branch));
                _previewSupports.Clear();
                _previewSupports.AddRange(
                    set.AnchorGroups.SelectMany(strip => strip));
                _clippingBox = new BoundingBox(
                    live.Concat(_previewColumns.Select(c => c.From)));

                entries.Add(ResultDiagnostics.Entry(S, "animate.anchor_strips", "info",
                    $"anchors grouped into {set.AnchorGroups.Count} "
                        + (set.AnchorGroups.Count == 1 ? "strip" : "strips")
                        + $" of {string.Join("/", set.AnchorGroups.Select(s => s.Count))}, "
                        + $"perimeter into {set.PerimeterNodes.Count} "
                        + (set.PerimeterNodes.Count == 1 ? "loop" : "loops"),
                    set.AnchorGroups.Count, unit: "strips",
                    context: ResultDiagnostics.Context(
                        ("loops", set.PerimeterNodes.Count.ToString(CultureInfo.InvariantCulture)))));
                if (anchorIds.Count > 1 && set.AnchorGroups.Count == anchorIds.Count)
                {
                    entries.Add(ResultDiagnostics.Entry(S, "animate.anchors_isolated", "warning",
                        "every anchor came back in a branch of its own, which means "
                            + "no two anchors are joined in either the plan or the "
                            + "solved net. Check that the Result still carries its "
                            + "source Pattern; without it there is no graph in which "
                            + "a side is continuous.",
                        set.AnchorGroups.Count, unit: "strips"));
                }

                ResultDto output = ResultDiagnostics.Replace(
                    framedResult, "Animate", entries);
                data.SetData(0, new ResultGoo(output));
            }
            catch (Exception ex)
            {
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.Message);
            }
        }
    }

    /// <summary>
    /// Geometry shared by Mould Animate and Column Finder: reading the net out
    /// of a Result, snapping the principal bars to it, and the bare surface.
    /// </summary>
    internal static class MouldGeometry
    {
        /// <summary>
        /// The Result's edges, minus any that are out of range or join a node
        /// to itself, with the original index of each survivor returned
        /// alongside. Callers need that index because the Result's per-edge
        /// arrays (member forces, force densities) are still in the unfiltered
        /// order.
        /// </summary>
        public static (int, int)[] ValidEdges(
            EquilibriumResultDto equilibrium,
            int nodeCount,
            out int[] source)
        {
            var kept = new List<(int, int)>();
            var origin = new List<int>();
            for (int i = 0; i < equilibrium.Edges.Count; i++)
            {
                EdgeDto e = equilibrium.Edges[i];
                if (e.U < 0 || e.U >= nodeCount || e.V < 0 || e.V >= nodeCount)
                    continue;
                if (e.U == e.V)
                    continue;
                kept.Add((e.U, e.V));
                origin.Add(i);
            }
            source = origin.ToArray();
            return kept.ToArray();
        }

        /// <summary>
        /// Adjacency as a SET of neighbours, one list per node.
        ///
        /// The edge set is deduped on the way in, by EdgeKey. The same pair
        /// can arrive twice, most obviously from GroupingAdjacency, which
        /// unions the plan's edges onto the solved ones and so lists every
        /// edge present in both graphs twice. A doubled neighbour is not
        /// harmless: ConnectedGroups finds the END of an open strip by
        /// counting its neighbours inside the group, so a doubled entry makes
        /// an end count two, no end is recognised, and the strip is walked
        /// from its lowest index instead of end to end.
        /// </summary>
        public static List<int>[] BuildAdjacency(int count, (int, int)[] edges)
        {
            var neighbours = new List<int>[count];
            for (int i = 0; i < count; i++)
                neighbours[i] = new List<int>();
            var seen = new HashSet<long>();
            foreach ((int u, int v) in edges)
            {
                if (!seen.Add(EdgeKey(u, v)))
                    continue;
                neighbours[u].Add(v);
                neighbours[v].Add(u);
            }
            return neighbours;
        }

        /// <summary>
        /// The graph to GROUP by, which is not the graph the solver solved.
        ///
        /// This distinction is the whole of the "42 branches of one node each"
        /// fault. Grouping the anchors by the EQUILIBRIUM edges gave every
        /// anchor a branch to itself, because a TNA analysis topology carries
        /// no edge between two supports: such an edge joins two fixed nodes, so
        /// it contributes no unknown and the network never needs it. Every
        /// anchor was therefore isolated from the anchor beside it, and a walk
        /// over that graph can only return singletons. It looks like a graft
        /// and it is not one; it is a correct walk over the wrong graph.
        ///
        /// The sides are connected in the PLAN AS DRAWN, which is the plan
        /// topology Pattern is the one source of; Supports derives no rib and
        /// walks no graph of its own. So the pattern's own edges are added to
        /// the solved ones and grouping happens over the union: two nodes are
        /// together if they are joined in either the plan or the solved
        /// network.
        ///
        /// The pattern is trusted only when it has the SAME NUMBER OF VERTICES
        /// as the solved network. Anything else is a different index space, and
        /// quietly mixing two index spaces would group nodes that have nothing
        /// to do with one another.
        ///
        /// An edge present in BOTH graphs is handed on twice, which is why
        /// BuildAdjacency dedupes: a doubled neighbour hides the end of an
        /// open strip from the walk that has to start there.
        /// </summary>
        public static List<int>[] GroupingAdjacency(
            ResultDto result,
            (int, int)[] solvedEdges,
            int nodeCount)
        {
            var all = new List<(int, int)>(solvedEdges);
            TopologyDto? pattern =
                result.Problem?.Anchored?.Pattern?.Topology;
            if (pattern is not null && pattern.Vertices.Count == nodeCount)
            {
                foreach (EdgeDto edge in pattern.Edges)
                {
                    if (edge.U < 0 || edge.U >= nodeCount ||
                        edge.V < 0 || edge.V >= nodeCount ||
                        edge.U == edge.V)
                    {
                        continue;
                    }
                    all.Add((edge.U, edge.V));
                }
            }
            return BuildAdjacency(nodeCount, all.ToArray());
        }

        /// <summary>
        /// Split a set of nodes into CONNECTED GROUPS, each in walking order.
        ///
        /// This is what turns a flat output into a tree that means something.
        /// The anchors of a vault are not one list of points, they are two
        /// strips down opposite sides, and the perimeter is not one list
        /// either, it is a loop, or several where the net has a hole. Handing
        /// all of them back merged and sorted by node index throws that away,
        /// and the index order is not even geometric: node 7 can sit at the far
        /// end of the far side from node 6. Whoever wants the strips back has
        /// to rediscover them downstream from the geometry, which is the work
        /// this method exists to stop repeating.
        ///
        /// Grouping is by MESH ADJACENCY rather than by proximity, so two
        /// strips that pass close to each other do not merge, and a strip that
        /// straggles does not split.
        ///
        /// Each group is then ORDERED by walking it. An open strip is walked
        /// from one of its ends, so the points come out in the order you would
        /// travel them; a closed loop has no end, so it is walked from its
        /// lowest node and comes back round. Both beat index order, which is
        /// what the caller had before and had to sort out by hand.
        ///
        /// The groups themselves are returned in the order of their lowest node
        /// index. That is arbitrary but STABLE, which is the property that
        /// matters: branch {0} must be the same strip on every frame of an
        /// animation, or the tree is no better than the flat list.
        /// </summary>
        public static List<List<int>> ConnectedGroups(
            IEnumerable<int> ids,
            List<int>[] neighbours)
        {
            var pool = new HashSet<int>(
                ids.Where(i => i >= 0 && i < neighbours.Length));
            var groups = new List<List<int>>();
            var seen = new HashSet<int>();

            foreach (int start in pool.OrderBy(i => i))
            {
                if (seen.Contains(start))
                    continue;

                // Collect the whole connected component first, so the walk
                // below knows what it is walking and can find a real end.
                var member = new HashSet<int>();
                var stack = new Stack<int>();
                stack.Push(start);
                member.Add(start);
                while (stack.Count > 0)
                {
                    int at = stack.Pop();
                    foreach (int next in neighbours[at])
                    {
                        if (pool.Contains(next) && member.Add(next))
                            stack.Push(next);
                    }
                }
                foreach (int i in member)
                    seen.Add(i);

                // An END is a node with one neighbour inside the group. A
                // closed loop has none, and then any node will do; taking the
                // lowest keeps it deterministic.
                int from = member
                    .Where(i => neighbours[i].Count(member.Contains) <= 1)
                    .DefaultIfEmpty(member.Min())
                    .Min();

                var order = new List<int>();
                var walked = new HashSet<int>();
                int cursor = from;
                while (walked.Add(cursor))
                {
                    order.Add(cursor);
                    int next = -1;
                    foreach (int candidate in neighbours[cursor])
                    {
                        if (!member.Contains(candidate) ||
                            walked.Contains(candidate))
                        {
                            continue;
                        }
                        if (next < 0 || candidate < next)
                            next = candidate;
                    }
                    if (next < 0)
                        break;
                    cursor = next;
                }

                // A forked group cannot be walked in one pass. Whatever the
                // walk could not reach is appended rather than dropped, because
                // losing a node silently would be worse than an imperfect
                // order.
                foreach (int i in member.OrderBy(i => i))
                {
                    if (!walked.Contains(i))
                        order.Add(i);
                }
                groups.Add(order);
            }

            return groups;
        }

        /// <summary>
        /// Which principal line each member belongs to, or -1 for infill.
        ///
        /// A member is on a bar when its two ends are CONSECUTIVE along that
        /// bar's run. Consecutive matters: a cable can join two notches of the
        /// same bar without being part of it, by cutting a corner across the
        /// net, and that cable belongs with the infill it acts as.
        ///
        /// Callers give the members as node-index pairs rather than as lines,
        /// so this stays arithmetic on arrays and the smoke harness can measure
        /// it without Rhino's native core.
        /// </summary>
        public static int[] MemberRunIndex(
            IReadOnlyList<(int U, int V)> members,
            IReadOnlyList<IReadOnlyList<int>> runs)
        {
            var owner = new Dictionary<long, int>();
            for (int r = 0; r < runs.Count; r++)
            {
                IReadOnlyList<int> run = runs[r];
                for (int k = 0; k + 1 < run.Count; k++)
                {
                    long key = EdgeKey(run[k], run[k + 1]);
                    // First bar wins. Two bars sharing a member means they
                    // cross, and the member is drawn once, under the earlier
                    // one, rather than duplicated into both branches.
                    if (!owner.ContainsKey(key))
                        owner[key] = r;
                }
            }

            var index = new int[members.Count];
            for (int i = 0; i < members.Count; i++)
            {
                index[i] = owner.TryGetValue(
                    EdgeKey(members[i].U, members[i].V), out int r) ? r : -1;
            }
            return index;
        }

        /// <summary>
        /// The surface the net takes between the pinned nodes with nothing
        /// reeled in: every free node at the average of its neighbours. That is
        /// the uniform force-density equilibrium, so by Schek's Theorem 1 it is
        /// the minimum-way surface, flat or saddled and never domed.
        /// </summary>
        public static double[] BareSurface(
            Point3d[] target,
            List<int>[] neighbours,
            bool[] pinned)
        {
            int n = target.Length;
            var z = new double[n];
            for (int i = 0; i < n; i++)
                z[i] = target[i].Z;

            for (int sweep = 0; sweep < 2000; sweep++)
            {
                double shift = 0.0;
                for (int i = 0; i < n; i++)
                {
                    if (pinned[i] || neighbours[i].Count == 0)
                        continue;
                    double sum = 0.0;
                    foreach (int j in neighbours[i])
                        sum += z[j];
                    double updated = sum / neighbours[i].Count;
                    shift = Math.Max(shift, Math.Abs(updated - z[i]));
                    z[i] = updated;
                }
                if (shift < 1e-9)
                    break;
            }
            return z;
        }

        /// <summary>
        /// The ordered run of net nodes lying along one principal bar, ordered
        /// by curve parameter so the bar reads end to end. The catch radius
        /// comes from the net's own edge lengths, so it scales with the model
        /// and needs no tolerance input.
        /// </summary>
        /// <summary>
        /// The ordered run of net nodes lying along one principal bar.
        ///
        /// Matching happens IN PLAN, ignoring height. The bars are drawn on the
        /// pattern, which is flat, while the nodes they have to find live on
        /// the solved surface, which is not: comparing in three dimensions puts
        /// the whole raised vault out of reach of its own bars and returns
        /// nothing at all. A principal line is a line in plan; which nodes it
        /// picks up is a plan question, and their heights come from the Result.
        /// </summary>
        /// <summary>
        /// The principal-line runs for a solved Result.
        ///
        /// They are resolved once upstream, by Pattern from the curves drawn
        /// into it, and the contract carries them down as vertex indices. So
        /// the matching happens once for the whole
        /// definition rather than in every component on every frame, and it
        /// cannot go wrong on a raised surface, because by here there is no
        /// curve left to match.
        /// </summary>
        public static List<List<int>> PrincipalRuns(
            EquilibriumResultDto equilibrium,
            int nodeCount)
        {
            IReadOnlyList<IReadOnlyList<int>>? runs =
                equilibrium.Problem?.Topology?.PrincipalRuns;
            if (runs is null)
                return new List<List<int>>();
            return runs
                .Where(run => run is not null && run.Count >= 2)
                .Select(run => run
                    .Where(i => i >= 0 && i < nodeCount)
                    .ToList())
                .Where(run => run.Count >= 2)
                .ToList();
        }

        /// <summary>
        /// Match one drawn bar to the run of net nodes along it, as a WALK on
        /// the mesh rather than a sort along the curve.
        ///
        /// The sort is the obvious implementation and it is wrong. A line
        /// drawn down a bay catches the column of nodes either side of it, and
        /// their positions along the curve interleave, so ordering the caught
        /// nodes by how far along they lie hands back a run that crosses the
        /// bay on every step: a zigzag, not a bar. It looks like a drawing
        /// fault and is not one. Downstream that run is pinned by Animate and
        /// solved as a beam by Column Finder, so the zigzag is load-bearing
        /// nonsense: notches on both sides of a bay, and a bar reported twice
        /// its true length.
        ///
        /// A bar is a CONNECTED CHAIN OF NOTCHES, so only a neighbour may
        /// follow a node. From each node the walk takes the neighbour that
        /// advances furthest along the curve, closest to the line where two
        /// advance equally. A sideways step advances nothing, so it is never
        /// preferred to a real one, and the run cannot double back. On a line
        /// drawn at an angle to the mesh the two directions advance together
        /// and the walk staircases, which is the honest discrete answer.
        ///
        /// <paramref name="meanOffset"/> reports how far the matched run sits
        /// from the curve that asked for it, in plan. It is not zero when the
        /// author drew between two columns of nodes: no bar can be there, the
        /// nearest run of nodes was taken instead, and the caller can say so
        /// rather than let the offset pass unremarked.
        /// </summary>
        public static List<int> SnapCurveToNodes(
            Curve curve,
            Point3d[] nodes,
            (int, int)[] edges,
            out double meanOffset,
            int samples = 512)
        {
            // Sample the curve once and compare in plain arithmetic, rather
            // than asking Rhino for a closest point per node. ClosestPoint on a
            // NURBS curve is not cheap, and this runs for every node of every
            // bar on every solve, which an animation does on every frame.
            //
            // Sampling is the ONLY part of this that needs Rhino, so it is the
            // only part that lives here. Everything below the sampling is
            // arithmetic on arrays, and keeping it that way is what lets the
            // smoke harness measure it: that harness never launches Rhino's
            // native core, so a walk that asked a Curve anything could only
            // ever be read, not run.
            double[]? ts = curve.DivideByCount(samples, true);
            Point3d[] sampled;
            if (ts is null || ts.Length == 0)
            {
                sampled = new[] { curve.PointAtStart, curve.PointAtEnd };
            }
            else
            {
                sampled = new Point3d[ts.Length];
                for (int s = 0; s < ts.Length; s++)
                    sampled[s] = curve.PointAt(ts[s]);
            }
            return SnapSampledLineToNodes(
                sampled, nodes, edges, out meanOffset);
        }

        /// <summary>
        /// The walk itself, over a line already reduced to points. See
        /// <see cref="SnapCurveToNodes"/> for why it is a walk and not a sort.
        /// </summary>
        public static List<int> SnapSampledLineToNodes(
            Point3d[] sampled,
            Point3d[] nodes,
            (int, int)[] edges,
            out double meanOffset)
        {
            meanOffset = 0.0;
            var run = new List<int>();
            if (nodes.Length == 0 || edges.Length == 0 || sampled.Length == 0)
                return run;

            double catchRadius = 0.6 * MedianEdgeLength(nodes, edges);
            double catchSquared = catchRadius * catchRadius;

            // Project every node onto the sampled curve once: which station it
            // stands at, and how far off the line it sits. Neither changes
            // during the walk, so neither is recomputed inside it.
            var station = new int[nodes.Length];
            var offset = new double[nodes.Length];
            for (int i = 0; i < nodes.Length; i++)
            {
                int best = -1;
                double bestDistance = double.MaxValue;
                for (int s = 0; s < sampled.Length; s++)
                {
                    double d = PlanDistanceSquared(nodes[i], sampled[s]);
                    if (d < bestDistance)
                    {
                        bestDistance = d;
                        best = s;
                    }
                }
                station[i] = best;
                offset[i] = bestDistance;
            }

            // Start at the node standing at the curve's beginning: of every
            // node inside the catch radius, the earliest station, and of those
            // the one nearest the line.
            int at = -1;
            for (int i = 0; i < nodes.Length; i++)
            {
                if (offset[i] >= catchSquared)
                    continue;
                if (at < 0 ||
                    station[i] < station[at] ||
                    (station[i] == station[at] && offset[i] < offset[at]))
                {
                    at = i;
                }
            }
            if (at < 0)
                return run;

            List<int>[] neighbours = BuildAdjacency(nodes.Length, edges);
            var used = new HashSet<int> { at };
            run.Add(at);
            while (true)
            {
                int next = -1;
                int bestAdvance = 0;
                foreach (int candidate in neighbours[at])
                {
                    if (used.Contains(candidate))
                        continue;
                    if (offset[candidate] >= catchSquared)
                        continue;
                    int advance = station[candidate] - station[at];
                    if (advance <= 0)
                        continue;
                    if (next < 0 ||
                        advance > bestAdvance ||
                        (advance == bestAdvance &&
                            offset[candidate] < offset[next]))
                    {
                        next = candidate;
                        bestAdvance = advance;
                    }
                }
                if (next < 0)
                    break;
                run.Add(next);
                used.Add(next);
                at = next;
            }

            // FINISH BOTH ENDS. The walk above needs a STRICT advance
            // along the curve, and at the end of one several nodes share the
            // last sample, so nothing advances and the run stops short. One
            // side of a symmetric bar then comes back a notch shorter than the
            // other, which makes the beam under it asymmetric, which puts the
            // arms in different places on the two halves and drags the shared
            // foot off centre with them. A whole family of asymmetries from one
            // missing node.
            //
            // Past the last station there is no ordering left to use, so finish
            // by the straightest continuation instead, while still inside the
            // catch radius. Applied at both ends, because the same thing can
            // happen at the start.
            Continue(run, neighbours, nodes, offset, catchSquared, used);
            run.Reverse();
            Continue(run, neighbours, nodes, offset, catchSquared, used);
            run.Reverse();

            meanOffset = run.Average(i => Math.Sqrt(offset[i]));
            return run;
        }

        /// <summary>
        /// Carry a run on past its last ordered node, by whichever unused
        /// neighbour continues straightest and still lies on the line.
        /// </summary>
        private static void Continue(
            List<int> run,
            List<int>[] neighbours,
            Point3d[] nodes,
            double[] offset,
            double catchSquared,
            HashSet<int> used)
        {
            while (run.Count >= 2)
            {
                int at = run[run.Count - 1];
                Vector3d heading = nodes[at] - nodes[run[run.Count - 2]];
                double length = heading.Length;
                if (length <= 1.0e-12)
                    return;
                heading = new Vector3d(
                    heading.X / length, heading.Y / length, heading.Z / length);

                int best = -1;
                double bestScore = 0.0;
                foreach (int candidate in neighbours[at])
                {
                    if (used.Contains(candidate))
                        continue;
                    if (offset[candidate] >= catchSquared)
                        continue;
                    Vector3d step = nodes[candidate] - nodes[at];
                    double stepLength = step.Length;
                    if (stepLength <= 1.0e-12)
                        continue;
                    double score =
                        ((heading.X * step.X) + (heading.Y * step.Y) +
                         (heading.Z * step.Z)) / stepLength;
                    if (score > bestScore)
                    {
                        bestScore = score;
                        best = candidate;
                    }
                }
                // A turn of more than a right angle is not a continuation.
                if (best < 0)
                    return;
                run.Add(best);
                used.Add(best);
            }
        }

        /// <summary>
        /// Where the ground is: the level the ANCHORS sit at.
        ///
        /// In this machine they define it. They are tied down on the two sides
        /// and stay there through the whole build, so the plane they lie in IS
        /// the floor the columns stand on.
        ///
        /// The lowest point of the geometry is NOT the ground, though it agrees
        /// with it whenever a vault stays above its own supports. The moment
        /// any part of one hangs below them, taking the minimum puts the floor
        /// under the dip and stands every column on it. The median of the
        /// anchors, so one stray anchor cannot move the floor.
        /// </summary>
        public static double GroundLevel(
            Point3d[] nodes,
            IEnumerable<int> anchorIds)
        {
            double[] levels = anchorIds
                .Where(i => i >= 0 && i < nodes.Length)
                .Select(i => nodes[i].Z)
                .OrderBy(z => z)
                .ToArray();
            if (levels.Length > 0)
                return levels[levels.Length / 2];
            return nodes.Length == 0 ? 0.0 : nodes.Min(p => p.Z);
        }

        /// <summary>
        /// A key naming everything <see cref="BareSurface"/> reads, so a caller
        /// can tell whether a cached answer still applies.
        ///
        /// Deliberately NOT the topology hash. That names the analysis network,
        /// and the solved vertices are not part of it: re-solving at a
        /// different height leaves the hash alone and moves every point, which
        /// is exactly the case a topology-keyed cache would get wrong. Hashing
        /// the coordinates bit for bit costs one pass and cannot drift.
        /// </summary>
        public static string SurfaceKey(Point3d[] target, bool[] pinned)
        {
            long rolling = 17;
            for (int i = 0; i < target.Length; i++)
            {
                rolling = (rolling * 31) +
                    BitConverter.DoubleToInt64Bits(target[i].X);
                rolling = (rolling * 31) +
                    BitConverter.DoubleToInt64Bits(target[i].Y);
                rolling = (rolling * 31) +
                    BitConverter.DoubleToInt64Bits(target[i].Z);
            }
            long held = 19;
            for (int i = 0; i < pinned.Length; i++)
            {
                if (pinned[i])
                    held = (held * 37) + i;
            }
            return $"{target.Length}:{rolling}:{held}";
        }

        /// <summary>
        /// What the NET hands each notch of a bar, as a force vector in three
        /// dimensions.
        ///
        /// Only the infill cables count. The edges running ALONG the bar are
        /// the bar itself, and a beam does not load itself, so they are left
        /// out. Positive is tension, so a member pulls its node toward the far
        /// end and a negative one pushes it away.
        /// </summary>
        public static Vector3d[] BarLoads(
            List<int> bar,
            Point3d[] nodes,
            List<(int Other, double Force)>[] incident)
        {
            var along = new HashSet<long>();
            for (int k = 0; k + 1 < bar.Count; k++)
                along.Add(EdgeKey(bar[k], bar[k + 1]));

            var pull = new Vector3d[bar.Count];
            for (int k = 0; k < bar.Count; k++)
            {
                int node = bar[k];
                var total = Vector3d.Zero;
                foreach ((int other, double force) in incident[node])
                {
                    if (along.Contains(EdgeKey(node, other)))
                        continue;
                    Vector3d step = nodes[other] - nodes[node];
                    double length = step.Length;
                    if (length <= 1.0e-12)
                        continue;
                    // MAGNITUDE, deliberately. Every infill member of this
                    // mould is a CABLE and pulls its notch toward the far end,
                    // whatever sign the analysis attached to it. A Result's
                    // sign convention is not fixed: Display reads it off the
                    // Result rather than assuming, and a TNA thrust network is
                    // the COMPRESSION MIRROR of the net that will be built, so
                    // its member forces come back negative under positive
                    // tension. Taking the signed value flipped every pull
                    // upward, which made the aim ask a column to hold its notch
                    // DOWN, which no column can do, so every one of them fell
                    // back to plumb. That is what put straight posts under a
                    // steeply inclined bar and collapsed the trees to a fan.
                    total += (Math.Abs(force) / length) * step;
                }
                pull[k] = total;
            }
            return pull;
        }

        /// <summary>
        /// How far off vertical a column member may stand, in degrees.
        ///
        /// Past this a column pushes sideways more than it holds up, and the
        /// sliding joint cannot reach the angle anyway. One constant because
        /// two parts of the machine obey it and they must obey the same
        /// number: a standalone column, whose aim is free and so is simply
        /// capped here; and a trunk to a shared foot, whose ends are both
        /// fixed and which is brought inside the limit by raising its fork
        /// instead.
        /// </summary>
        public const double MaxLeanDegrees = 60.0;

        /// <summary>
        /// How far a member stands off vertical, in degrees.
        ///
        /// Measured from the two ends rather than from a force, because this
        /// is the question the sliding joint asks: not "is the column on its
        /// line of thrust" but "can the mechanism reach this angle".
        /// </summary>
        public static double LeanFromVertical(Point3d foot, Point3d top)
        {
            double rise = top.Z - foot.Z;
            double reach = Math.Sqrt(PlanDistanceSquared(foot, top));
            if (rise <= 1.0e-9)
                return reach <= 1.0e-9 ? 0.0 : 90.0;
            return Math.Atan2(reach, rise) * 180.0 / Math.PI;
        }

        public static long EdgeKey(int a, int b) =>
            a < b
                ? ((long)a << 32) | (uint)b
                : ((long)b << 32) | (uint)a;

        /// <summary>
        /// The part of that pull the COLUMNS have to take.
        ///
        /// This is where Gaudi's rule lands in this machine, and it lands
        /// differently from how it reads at first. Inclining a column pays only
        /// when the force arriving at its head is ALREADY inclined; under a
        /// purely vertical load a lean costs axial force (P over cos) and hands
        /// the foot a sideways push (P times tan) that something then has to
        /// resist. Gaudi's columns lean because the vault delivers thrust, and
        /// the lean is what removes the buttress.
        ///
        /// Here the buttresses already exist: every principal bar runs from one
        /// anchor strip to the other and BOTH ITS ENDS ARE TIED TO THE GROUND,
        /// so the pull running along a bar travels to those anchors, not to the
        /// columns. Leaning a column to take that component would double up on
        /// work the anchors are already doing.
        ///
        /// What no one takes is the pull ACROSS the bar. The bars curve in
        /// plan, so the infill cables pull them sideways and their own tension
        /// around that plan curve pushes sideways too, and nothing resists it
        /// but the bar's own bending. That component, plus the weight, is the
        /// columns' share and it is what their lean should follow.
        ///
        /// So: project the pull off the bar's local tangent and keep the rest.
        /// On a bar lying in a vertical plane the remainder is vertical and the
        /// columns come out plumb, which is the right answer for that case.
        /// </summary>
        public static Vector3d[] BarTransverse(
            List<int> bar,
            Point3d[] nodes,
            Vector3d[] pull)
        {
            var across = new Vector3d[bar.Count];
            for (int k = 0; k < bar.Count; k++)
            {
                int before = Math.Max(k - 1, 0);
                int after = Math.Min(k + 1, bar.Count - 1);
                Vector3d tangent = nodes[bar[after]] - nodes[bar[before]];
                double length = tangent.Length;
                if (length <= 1.0e-12)
                {
                    across[k] = pull[k];
                    continue;
                }
                // Divided rather than Unitized: Vector3d.Unitize P/Invokes into
                // Rhino's native core, which puts it out of reach of the smoke
                // harness, and this runs per node per bar per solve anyway.
                tangent = new Vector3d(
                    tangent.X / length, tangent.Y / length, tangent.Z / length);
                across[k] = pull[k] - ((pull[k] * tangent) * tangent);
            }
            return across;
        }

        /// <summary>
        /// Which way a column must push, given what the net pulls across its
        /// bar there. One rule, used by Column Finder to place the arms and by
        /// Animate to re-aim them on every frame, so a rising column follows
        /// the same thrust line the finished one stands on.
        ///
        /// Capped at sixty degrees from vertical: past that a column pushes
        /// sideways more than it holds up and the sliding joint cannot reach
        /// the angle. A net pulling its notch DOWN onto the column has no
        /// thrust line to follow at all, so that one stands plumb.
        /// </summary>
        public static Vector3d AimFrom(Vector3d pulled)
        {
            Vector3d supply = -pulled;
            if (supply.Z <= 1.0e-9)
                return Vector3d.ZAxis;

            double horizontal = Math.Sqrt(
                (supply.X * supply.X) + (supply.Y * supply.Y));
            double allowed =
                Math.Tan(Rhino.RhinoMath.ToRadians(MaxLeanDegrees)) * supply.Z;
            if (horizontal > allowed && horizontal > 1.0e-12)
            {
                double scale = allowed / horizontal;
                supply = new Vector3d(
                    supply.X * scale, supply.Y * scale, supply.Z);
            }
            double length = supply.Length;
            return length > 1.0e-12
                ? new Vector3d(
                    supply.X / length, supply.Y / length, supply.Z / length)
                : Vector3d.ZAxis;
        }


        /// <summary>
        /// Rebuild a branching column out of the bare lines Column Finder
        /// hands over.
        ///
        /// The wire between the two components carries geometry, not topology,
        /// so a forked column arrives as a heap of segments with nothing saying
        /// which branch belongs to which trunk. Animating them one at a time
        /// treated every branch as though it stood on the ground, which is what
        /// left a fork hanging in mid air.
        ///
        /// Two facts make the tree recoverable without a new contract. Every
        /// member runs LOWER end to UPPER end, an invariant Column Finder keeps
        /// deliberately, and a fork is one point shared exactly. So welding the
        /// endpoints and reading the direction back gives the whole structure:
        /// a node that is only ever an upper end is a NOTCH, one that is only
        /// ever a lower end is a FOOT, and anything that is both is a FORK.
        /// </summary>
        public sealed class ColumnTree
        {
            public List<Point3d> Nodes { get; } = new();

            public List<(int Lower, int Upper)> Members { get; } = new();

            public List<int> Notches { get; } = new();

            public List<int> Feet { get; } = new();

            /// <summary>Upper ends of each node, nearest the notches.</summary>
            public List<int>[] Above { get; set; } = Array.Empty<List<int>>();
        }

        /// <summary>
        /// Which of a fork's branches is the MAIN column: the one most nearly
        /// in line with the trunk below it. That collinearity is not an
        /// accident, it is the invariant Columns creates by putting the fork
        /// on the segment from the foot to the main notch, so reading it back
        /// recovers which branch that was without carrying a label across the
        /// wire.
        /// </summary>
        public static int MainBranch(ColumnTree tree, int fork)
        {
            List<int> above = tree.Above[fork];
            if (above.Count == 1)
                return above[0];

            // The trunk below this fork, if there is one.
            var down = Vector3d.Zero;
            foreach ((int lower, int upper) in tree.Members)
            {
                if (upper != fork)
                    continue;
                down = tree.Nodes[fork] - tree.Nodes[lower];
                break;
            }
            double downLength = down.Length;
            if (downLength <= 1.0e-12)
                return above[0];

            int best = above[0];
            double straightest = -2.0;
            foreach (int candidate in above)
            {
                Vector3d up = tree.Nodes[candidate] - tree.Nodes[fork];
                double length = up.Length;
                if (length <= 1.0e-12)
                    continue;
                double score = ((down.X * up.X) + (down.Y * up.Y) +
                    (down.Z * up.Z)) / (downLength * length);
                if (score > straightest)
                {
                    straightest = score;
                    best = candidate;
                }
            }
            return best;
        }

        /// <summary>
        /// The four phases of the build on one Time slider, from the
        /// seven-questions state machine as the spine spec bound it: reel the
        /// net part way in while it is flat (0 to 30), raise it on the columns
        /// (30 to 60), reel the rest and tension both axes (60 to 90), then
        /// hold while load arrives (90 to 100). Sag and lift are continuous
        /// across every boundary so the slider never jumps.
        /// </summary>
        public static (double Sag, double Lift, string Phase) Phases(
            double time, double preSag)
        {
            time = Math.Min(Math.Max(time, 0.0), 1.0);
            double pre = Math.Min(Math.Max(preSag, 0.0), 1.0);
            if (time < 0.3)
                return (pre * (time / 0.3), 0.0, "reel");
            if (time < 0.6)
                return (pre, (time - 0.3) / 0.3, "raise");
            if (time < 0.9)
                return (pre + ((1.0 - pre) * ((time - 0.6) / 0.3)), 1.0, "finish");
            return (1.0, 1.0, "hold");
        }

        /// <summary>
        /// Every column node's position for one frame of the net.
        ///
        /// The TRUNK turns about its foot as a rigid body. The foot is fixed
        /// where the block put it, from frame zero. Each head is on the live
        /// net at the vertex HeadNode names for it, never found by matching
        /// plan coordinates. Each fork sits on the segment from its foot to
        /// its main head's live position at the fraction it was built at, the
        /// main head being the branch collinear with the trunk, which is the
        /// invariant Columns creates by putting the fork on that segment. So
        /// at time zero a trunk lies flat along the rail from its foot to its
        /// notch's drawn position, and rises with the notch, its length being
        /// what the ram delivers.
        ///
        /// The ARMS are not rigid in this model. Each runs from that fork to
        /// its own head, and the two ends move independently, so an arm's
        /// length changes frame to frame. That is a real limitation of the
        /// mechanism rather than a property of it, which is why Animate
        /// measures every arm and reports the worst as animate.arm_stretch:
        /// an arm reading far from its built length is the frame telling you
        /// the machine cannot make this shape.
        ///
        /// A node nothing resolves (a head with no HeadNode, a fragment with
        /// no foot) keeps its built position rather than vanishing. Two forks
        /// in a chain along one trunk block each other in this loop (each
        /// needs the other placed first) and keep their built positions; the
        /// plugin never builds that shape, since Columns places exactly one
        /// fork per tree.
        /// </summary>
        public static Point3d[] LiveColumnNodes(
            MouldColumnsDto block, Point3d[] live)
        {
            ColumnTree tree = TreeFromBlock(block);
            int count = tree.Nodes.Count;
            var at = new Point3d[count];
            var known = new bool[count];

            foreach (int foot in tree.Feet)
            {
                at[foot] = tree.Nodes[foot];
                known[foot] = true;
            }
            for (int h = 0; h < block.Heads.Count && h < block.HeadNode.Count; h++)
            {
                int node = block.Heads[h];
                int vertex = block.HeadNode[h];
                if (node < 0 || node >= count || vertex < 0 || vertex >= live.Length)
                    continue;
                at[node] = live[vertex];
                known[node] = true;
            }

            // Forks, once their foot below and main head above are placed.
            for (int pass = 0; pass < count + 2; pass++)
            {
                bool moved = false;
                for (int v = 0; v < count; v++)
                {
                    if (known[v] || tree.Above[v].Count == 0)
                        continue;
                    int lower = -1;
                    foreach ((int lo, int up) in tree.Members)
                    {
                        if (up == v)
                        {
                            lower = lo;
                            break;
                        }
                    }
                    if (lower < 0 || !known[lower])
                        continue;
                    int main = MainBranch(tree, v);
                    if (!known[main])
                        continue;
                    double span = tree.Nodes[lower].DistanceTo(tree.Nodes[main]);
                    double fraction = span > 1.0e-12
                        ? tree.Nodes[lower].DistanceTo(tree.Nodes[v]) / span
                        : 1.0;
                    fraction = Math.Min(Math.Max(fraction, 0.0), 1.0);
                    at[v] = at[lower] + ((at[main] - at[lower]) * fraction);
                    known[v] = true;
                    moved = true;
                }
                if (!moved)
                    break;
            }

            for (int v = 0; v < count; v++)
            {
                if (!known[v])
                    at[v] = tree.Nodes[v];
            }
            return at;
        }

        /// <summary>
        /// The built columns as the block the Result carries.
        ///
        /// Welds the members into shared nodes, and KEEPS THE FORCE ALIGNED:
        /// a zero-length line is skipped together with its force rather than
        /// leaving the forces one ahead of the members from that point on.
        /// Heads name the net vertex under them by nearest point in plan,
        /// which is exact here because every head IS a net vertex.
        /// </summary>
        public static MouldColumnsDto ColumnsBlock(
            IReadOnlyList<Line> members,
            IReadOnlyList<double> force,
            Point3d[] netNodes,
            double weldTolerance,
            int branching,
            int groundAsked,
            int groundPlaced,
            double forkFraction,
            int forksRaised)
        {
            var nodes = new List<Point3d>();
            var pairs = new List<(int Lower, int Upper)>();
            var forces = new List<double>();
            double squared = weldTolerance * weldTolerance;

            int Weld(Point3d point)
            {
                for (int i = 0; i < nodes.Count; i++)
                {
                    if (nodes[i].DistanceToSquared(point) <= squared)
                        return i;
                }
                nodes.Add(point);
                return nodes.Count - 1;
            }

            for (int i = 0; i < members.Count; i++)
            {
                Line member = members[i];
                if (member.Length <= 1.0e-9)
                    continue;
                Point3d lower = member.From.Z <= member.To.Z ? member.From : member.To;
                Point3d upper = member.From.Z <= member.To.Z ? member.To : member.From;
                int a = Weld(lower);
                int b = Weld(upper);
                if (a == b)
                    continue;
                pairs.Add((a, b));
                forces.Add(i < force.Count ? force[i] : 0.0);
            }

            ColumnTree tree = TreeFromPairs(nodes, pairs);
            var isLower = new bool[nodes.Count];
            var isUpper = new bool[nodes.Count];
            foreach ((int lower, int upper) in pairs)
            {
                isLower[lower] = true;
                isUpper[upper] = true;
            }
            var forks = new List<int>();
            for (int i = 0; i < nodes.Count; i++)
            {
                if (isLower[i] && isUpper[i])
                    forks.Add(i);
            }

            return new MouldColumnsDto
            {
                Nodes = nodes.Select(p => new Point3Dto(p.X, p.Y, p.Z)).ToArray(),
                Members = pairs.Select(p => new EdgeDto(p.Lower, p.Upper)).ToArray(),
                MemberForce = forces.ToArray(),
                Trees = TreesByFoot(tree)
                    .Select(t => (IReadOnlyList<int>)t.ToArray())
                    .ToArray(),
                Heads = tree.Notches.ToArray(),
                Forks = forks.ToArray(),
                Feet = tree.Feet.ToArray(),
                HeadNode = tree.Notches
                    .Select(h => NearestNodeInPlan(nodes[h], netNodes))
                    .ToArray(),
                Branching = Math.Max(branching, 1),
                // -1 is Auto, which spec 3.8 requires the block to carry and
                // the contract now allows. Clamping it to 0 made a block
                // built by Auto indistinguishable from one the author asked
                // Ground 0 for, so the relaxed contract could never be
                // exercised by the production path.
                GroundAsked = Math.Max(groundAsked, -1),
                GroundPlaced = Math.Max(groundPlaced, 0),
                ForkFraction = Math.Min(Math.Max(forkFraction, 0.0), 1.0),
                ForksRaised = Math.Max(forksRaised, 0),
            };
        }

        /// <summary>
        /// The block read back as the tree Animate walks. No welding: the
        /// block already carries indices.
        /// </summary>
        public static ColumnTree TreeFromBlock(MouldColumnsDto block)
        {
            var nodes = block.Nodes.Select(p => new Point3d(p.X, p.Y, p.Z)).ToList();
            var pairs = new List<(int Lower, int Upper)>();
            foreach (EdgeDto member in block.Members)
            {
                if (member.U < 0 || member.U >= nodes.Count ||
                    member.V < 0 || member.V >= nodes.Count || member.U == member.V)
                {
                    continue;
                }
                pairs.Add((member.U, member.V));
            }
            return TreeFromPairs(nodes, pairs);
        }

        /// <summary>
        /// Which members stand on each foot: climb from every foot through
        /// the nodes above it; a member belongs to the foot its lower end
        /// stands on. Feet in ascending node order so branch {i} is the same
        /// tree on every frame. Anything no foot reaches goes in one last
        /// group rather than vanishing.
        /// </summary>
        public static List<List<int>> TreesByFoot(ColumnTree tree)
        {
            int count = tree.Nodes.Count;
            var standsOn = new int[count];
            for (int i = 0; i < count; i++)
                standsOn[i] = -1;
            int[] feet = tree.Feet.Distinct().OrderBy(f => f).ToArray();
            for (int b = 0; b < feet.Length; b++)
            {
                var climb = new Stack<int>();
                climb.Push(feet[b]);
                while (climb.Count > 0)
                {
                    int at = climb.Pop();
                    if (at < 0 || at >= count || standsOn[at] >= 0)
                        continue;
                    standsOn[at] = b;
                    foreach (int up in tree.Above[at])
                        climb.Push(up);
                }
            }

            var groups = feet.Select(_ => new List<int>()).ToList();
            var orphans = new List<int>();
            for (int m = 0; m < tree.Members.Count; m++)
            {
                (int lower, int upper) = tree.Members[m];
                int owner = standsOn[lower] >= 0 ? standsOn[lower] : standsOn[upper];
                if (owner >= 0)
                    groups[owner].Add(m);
                else
                    orphans.Add(m);
            }
            if (orphans.Count > 0)
                groups.Add(orphans);
            return groups;
        }

        private static ColumnTree TreeFromPairs(
            List<Point3d> nodes,
            List<(int Lower, int Upper)> pairs)
        {
            var tree = new ColumnTree();
            tree.Nodes.AddRange(nodes);
            tree.Members.AddRange(pairs);
            var above = new List<int>[nodes.Count];
            for (int i = 0; i < nodes.Count; i++)
                above[i] = new List<int>();
            var isLower = new bool[nodes.Count];
            var isUpper = new bool[nodes.Count];
            foreach ((int lower, int upper) in pairs)
            {
                above[lower].Add(upper);
                isLower[lower] = true;
                isUpper[upper] = true;
            }
            tree.Above = above;
            for (int i = 0; i < nodes.Count; i++)
            {
                if (isUpper[i] && !isLower[i])
                    tree.Notches.Add(i);
                else if (isLower[i] && !isUpper[i])
                    tree.Feet.Add(i);
            }
            return tree;
        }

        /// <summary>
        /// The index of the node nearest a point IN PLAN. Plan, because a
        /// column drawn against the finished shape has to find its notch on a
        /// net that is still on the ground.
        /// </summary>
        public static int NearestNodeInPlan(Point3d point, Point3d[] nodes)
        {
            int best = -1;
            double closest = double.MaxValue;
            for (int i = 0; i < nodes.Length; i++)
            {
                double d = PlanDistanceSquared(point, nodes[i]);
                if (d < closest)
                {
                    closest = d;
                    best = i;
                }
            }
            return best;
        }


        /// <summary>Squared distance in plan, height ignored.</summary>
        public static double PlanDistanceSquared(Point3d a, Point3d b) =>
            ((a.X - b.X) * (a.X - b.X)) + ((a.Y - b.Y) * (a.Y - b.Y));

        /// <summary>
        /// Median edge length IN PLAN, so the snap radius is measured the same
        /// way the snapping is. Using the spatial length would set too generous
        /// a radius on a steep vault, where a short edge in plan can be long in
        /// space.
        /// </summary>
        public static double MedianEdgeLength(Point3d[] nodes, (int, int)[] edges)
        {
            double[] lengths = edges
                .Select(e => Math.Sqrt(
                    PlanDistanceSquared(nodes[e.Item1], nodes[e.Item2])))
                .Where(length => length > 0.0)
                .OrderBy(length => length)
                .ToArray();
            return lengths.Length == 0 ? 1.0 : lengths[lengths.Length / 2];
        }

        /// <summary>
        /// The boundary read from FACES, which is where a boundary actually
        /// lives when there is no mesh to ask.
        ///
        /// An edge used by exactly ONE face is a boundary edge and both its
        /// ends are boundary nodes; an edge shared by two faces is interior.
        /// That is the same rule Rhino's naked-edge status applies, written
        /// out over a face list, so an FD Result, which carries no thrust
        /// mesh, still gets a real boundary from its pattern topology instead
        /// of the degree ESTIMATE below, which is not a cycle and on a coarse
        /// quad net returns the four corners and nothing else.
        ///
        /// Pure and index-only: no geometry is read, so the same answer holds
        /// on every frame of an animation. Nodes come back in ascending index
        /// order. An empty array means there were no usable faces, which is
        /// the caller's cue to fall back and to say that it did.
        /// </summary>
        public static int[] PerimeterFromFaces(
            IReadOnlyList<IReadOnlyList<int>> faces,
            int nodeCount)
        {
            if (faces is null || faces.Count == 0 || nodeCount <= 0)
                return Array.Empty<int>();

            var uses = new Dictionary<long, int>();
            var ends = new Dictionary<long, (int A, int B)>();
            foreach (IReadOnlyList<int> face in faces)
            {
                if (face is null || face.Count < 3)
                    continue;
                for (int k = 0; k < face.Count; k++)
                {
                    int a = face[k];
                    int b = face[(k + 1) % face.Count];
                    if (a < 0 || a >= nodeCount ||
                        b < 0 || b >= nodeCount || a == b)
                    {
                        continue;
                    }
                    long key = EdgeKey(a, b);
                    uses[key] = uses.TryGetValue(key, out int used) ? used + 1 : 1;
                    ends[key] = (a, b);
                }
            }

            var boundary = new HashSet<int>();
            foreach (KeyValuePair<long, int> use in uses)
            {
                if (use.Value != 1)
                    continue;
                (int a, int b) = ends[use.Key];
                boundary.Add(a);
                boundary.Add(b);
            }
            return boundary.OrderBy(i => i).ToArray();
        }

        public static int[] PerimeterNodes(
            Mesh? mesh,
            int[] meshToNode,
            List<int>[] neighbours,
            int count)
        {
            if (mesh is not null && mesh.Vertices.Count > 0 &&
                meshToNode.Length == mesh.Vertices.Count)
            {
                bool[] naked = mesh.GetNakedEdgePointStatus();
                if (naked is not null && naked.Length == mesh.Vertices.Count)
                {
                    // The mesh was built from these very nodes, so the mapping
                    // is exact and no nearest-point search is needed. A set
                    // keeps this linear; List.Contains made it quadratic.
                    var found = new List<int>();
                    var seen = new HashSet<int>();
                    for (int v = 0; v < mesh.Vertices.Count; v++)
                    {
                        if (!naked[v])
                            continue;
                        int node = meshToNode[v];
                        if (node >= 0 && node < count && seen.Add(node))
                            found.Add(node);
                    }
                    if (found.Count > 0)
                        return found.ToArray();
                }
            }

            int[] degrees = neighbours.Select(list => list.Count).ToArray();
            if (degrees.Length == 0)
                return Array.Empty<int>();
            int[] sorted = degrees.OrderBy(d => d).ToArray();
            int interior = sorted[sorted.Length / 2];
            return Enumerable.Range(0, count)
                .Where(i => degrees[i] < interior)
                .ToArray();
        }

        /// <summary>
        /// Rebuild the thrust mesh from a Result's own form faces, so neither
        /// component needs a mesh wired in. Returns null for an FD result,
        /// which carries no faces, and null rather than throwing if the
        /// mapping is incomplete: a missing surface should not stop the
        /// animation.
        /// </summary>
        public static Mesh? ThrustMeshFromResult(
            ResultDto result,
            out int[] meshToNode)
        {
            meshToNode = Array.Empty<int>();
            EquilibriumResultDto? equilibrium = result.Equilibrium;
            TnaDiagramGraphDto? formGraph = result.FormGraph;
            TnaMappingsDto? mappings = result.Mappings;
            if (equilibrium is null || formGraph is null || mappings is null)
                return null;

            try
            {
                var formToEquilibrium = new Dictionary<int, int>();
                foreach (var item in mappings.SourceVertexToFormVertex)
                {
                    if (!item.FormVertexId.HasValue ||
                        !item.EquilibriumVertexId.HasValue)
                    {
                        continue;
                    }
                    formToEquilibrium[item.FormVertexId.Value] =
                        item.EquilibriumVertexId.Value;
                }

                var mesh = new Mesh();
                var formToMesh = new Dictionary<int, int>();
                var map = new List<int>();
                foreach (TnaGraphVertexDto vertex in
                         formGraph.Vertices.OrderBy(item => item.Id))
                {
                    if (!formToEquilibrium.TryGetValue(vertex.Id, out int eqId) ||
                        eqId < 0 || eqId >= equilibrium.Vertices.Count)
                    {
                        return null;
                    }
                    Point3Dto p = equilibrium.Vertices[eqId];
                    formToMesh[vertex.Id] = mesh.Vertices.Add(p.X, p.Y, p.Z);
                    map.Add(eqId);
                }

                foreach (TnaGraphFaceDto face in
                         formGraph.Faces.OrderBy(item => item.Id))
                {
                    var ids = new List<int>();
                    foreach (int id in face.Vertices)
                    {
                        if (!formToMesh.TryGetValue(id, out int meshId))
                            return null;
                        ids.Add(meshId);
                    }
                    if (ids.Count == 3)
                    {
                        mesh.Faces.AddFace(ids[0], ids[1], ids[2]);
                    }
                    else if (ids.Count == 4)
                    {
                        mesh.Faces.AddFace(ids[0], ids[1], ids[2], ids[3]);
                    }
                    else
                    {
                        for (int i = 1; i < ids.Count - 1; i++)
                            mesh.Faces.AddFace(ids[0], ids[i], ids[i + 1]);
                    }
                }

                if (mesh.Faces.Count == 0)
                    return null;
                mesh.Normals.ComputeNormals();
                // Compact would renumber vertices and break the mapping, and
                // there is nothing to compact: every vertex was just added and
                // every face references one.
                meshToNode = map.ToArray();
                return mesh;
            }
            catch (Exception)
            {
                return null;
            }
        }

        public static Mesh DeformMesh(Mesh source, int[] meshToNode, Point3d[] live)
        {
            Mesh deformed = source.DuplicateMesh();
            for (int v = 0; v < deformed.Vertices.Count && v < meshToNode.Length; v++)
            {
                int node = meshToNode[v];
                if (node < 0 || node >= live.Length)
                    continue;
                // Exact, from the mapping the mesh was built with, rather than
                // a nearest-point search that cost one pass over every node for
                // every vertex on every frame.
                deformed.Vertices.SetVertex(v, live[node]);
            }
            deformed.Normals.ComputeNormals();
            deformed.Compact();
            return deformed;
        }
    }

    /// <summary>
    /// The geometry of the frame a Result stands at, built ONCE and read by
    /// both the component that makes a frame and the component that reads
    /// one.
    ///
    /// Positions are the whole rule. A Result carrying a Mould frame is read
    /// at <c>Frame.Vertices</c>; a Result without one is read at
    /// <c>Equilibrium.Vertices</c>, which is the finished vault. So Frame on
    /// a Solve or a Columns Result draws the vault, Frame on an Animate
    /// Result draws that frame, and neither component needs to know which it
    /// was handed. The columns follow one level down:
    /// <c>Frame.ColumnNodes</c> where the frame carries them, the block's own
    /// nodes otherwise.
    ///
    /// The topology all travels on the Result and none of it is persisted
    /// per frame: the edges, the principal runs, the pattern faces and the
    /// column block are read back out of it every time, exactly as Animate
    /// used to read them for its own outputs. That is what stops the frame's
    /// geometry needing a contract of its own.
    ///
    /// Split in two on purpose. <see cref="Read"/> is arithmetic over
    /// managed types (Point3d, Line, index lists) and is measured in the
    /// smoke harness, which has no Rhino to P/Invoke. <see cref="Build"/> is
    /// <see cref="Read"/> plus the two things that need one: the thrust mesh
    /// deformed onto the frame, and the polylines turned into curves. Both
    /// read the same <see cref="Net.Positions"/>, so what is measured is
    /// what is drawn.
    /// </summary>
    internal static class FrameGeometry
    {
        /// <summary>
        /// What a Result with no frame stands at: its own solved shape, the
        /// end of the build rather than a moment in it.
        /// </summary>
        public const string FinalPhase = "final";

        /// <summary>
        /// A member whose two ends have met is not drawn. Animate reports it
        /// (animate.columns counts the collapsed) and this leaves it out, so
        /// a branch can come back short or empty at an early frame.
        /// </summary>
        private const double Collapsed = 1.0e-9;

        /// <summary>
        /// The frame in managed types: everything that can be worked out
        /// without a Rhino to call.
        /// </summary>
        public sealed record Net(
            Point3d[] Positions,
            List<List<Line>> Cables,
            List<List<Point3d>> PrincipalNodes,
            List<List<Point3d>> AnchorGroups,
            List<List<Point3d>> PerimeterLoops,
            bool[] PerimeterCloses,
            bool PerimeterEstimated,
            int PerimeterCount,
            List<List<Line>> ColumnBranches,
            string Phase);

        /// <summary>
        /// The frame as a component emits it: the Net plus the mesh and the
        /// curves. Branch {i} of Cables, PrincipalLines and PrincipalNodes
        /// is bar {i}; Cables carries the infill in a LAST branch; branch
        /// {i} of PerimeterNodes and PerimeterLines is boundary group {i};
        /// branch {i} of ColumnBranches is column tree {i}.
        /// </summary>
        public sealed record Set(
            Mesh? Mesh,
            List<List<Line>> Cables,
            List<List<Curve>> PrincipalLines,
            List<List<Point3d>> PrincipalNodes,
            List<List<Point3d>> AnchorGroups,
            List<List<Point3d>> PerimeterNodes,
            List<List<Curve>> PerimeterLines,
            bool PerimeterEstimated,
            int PerimeterCount,
            List<List<Line>> ColumnBranches,
            string Phase);

        /// <summary>
        /// The frame's geometry, given the Result and whatever thrust mesh it
        /// has (null for an FD Result, which carries no faces). The mesh is a
        /// parameter rather than a read, because building one needs Rhino and
        /// this has to run where there is none; the caller that has one hands
        /// it over, and the boundary is then read from its naked edges
        /// instead of from node degree.
        /// </summary>
        public static Net Read(ResultDto result, Mesh? mesh, int[] meshToNode)
        {
            EquilibriumResultDto equilibrium = result.Equilibrium
                ?? throw new InvalidOperationException(
                    "Result carries no equilibrium.");
            Point3d[] solved = equilibrium.Vertices
                .Select(v => new Point3d(v.X, v.Y, v.Z))
                .ToArray();
            int n = solved.Length;
            if (n == 0)
                throw new InvalidOperationException("Result carries no vertices.");

            MouldFrameDto? frame = result.Mould?.Frame;
            bool positionsMatch = frame is not null && frame.Vertices.Count == n;
            Point3d[] positions =
                positionsMatch
                    ? frame!.Vertices
                        .Select(v => new Point3d(v.X, v.Y, v.Z))
                        .ToArray()
                    : solved;
            (List<List<Line>> columnBranches, bool columnsMatch) =
                ColumnLines(result, frame);

            // A frame that fails either count guard is not the frame it
            // claims to be: positions or columns fell back to the solved
            // state, and reporting the frame's own phase over that would say
            // "raise" about geometry that is really the finished vault. Both
            // guards feed the SAME phase, because a Result whose Frame is
            // malformed in one is not trustworthy in the other either.
            string phase =
                frame is null ||
                string.IsNullOrWhiteSpace(frame.Phase) ||
                !positionsMatch ||
                !columnsMatch
                    ? FinalPhase
                    : frame.Phase;

            (int, int)[] edges = MouldGeometry.ValidEdges(equilibrium, n, out _);
            List<List<int>> bars = MouldGeometry.PrincipalRuns(equilibrium, n);
            List<int>[] neighbours = MouldGeometry.BuildAdjacency(n, edges);

            // Every member sorted into the bar it belongs to, with whatever
            // is left over as the infill branch at the end. The empty
            // branches are kept, so branch {i} is bar {i} whether or not
            // that bar carries a member here.
            int[] memberBar = MouldGeometry.MemberRunIndex(
                edges.Select(e => (e.Item1, e.Item2)).ToArray(), bars);
            var cables = new List<List<Line>>();
            for (int b = 0; b < bars.Count; b++)
                cables.Add(new List<Line>());
            var infill = new List<Line>();
            for (int e = 0; e < edges.Length; e++)
            {
                var member = new Line(
                    positions[edges[e].Item1], positions[edges[e].Item2]);
                if (memberBar[e] >= 0)
                    cables[memberBar[e]].Add(member);
                else
                    infill.Add(member);
            }
            cables.Add(infill);

            var principalNodes = bars
                .Select(run => run.Select(i => positions[i]).ToList())
                .ToList();

            var anchorIds = new HashSet<int>(
                equilibrium.ResolvedSupportNodeIds
                    .Where(i => i >= 0 && i < n));

            // The boundary. With a thrust mesh the naked edges give it
            // exactly. Without one, which is every FD Result, the PATTERN
            // topology still names it if it carries faces: an edge used by
            // exactly one face is a boundary edge. Only when there are no
            // faces either is the degree heuristic left, and that is an
            // ESTIMATE rather than a boundary, so it is labelled as one and
            // no curve is drawn through it.
            int[] perimeterIds;
            bool perimeterEstimated = false;
            if (mesh is null)
            {
                TopologyDto? patternTopology =
                    result.Problem?.Anchored?.Pattern?.Topology;
                IReadOnlyList<IReadOnlyList<int>> faces =
                    patternTopology is not null &&
                    patternTopology.Vertices.Count == n
                        ? patternTopology.Faces
                        : Array.Empty<IReadOnlyList<int>>();
                perimeterIds = MouldGeometry.PerimeterFromFaces(faces, n);
                if (perimeterIds.Length == 0)
                {
                    perimeterIds = MouldGeometry.PerimeterNodes(
                        mesh, meshToNode, neighbours, n);
                    perimeterEstimated = true;
                }
            }
            else
            {
                perimeterIds = MouldGeometry.PerimeterNodes(
                    mesh, meshToNode, neighbours, n);
            }

            // Grouped over the PLAN AS DRAWN unioned with the solved net,
            // not over the solved net alone. The solved net has no edge
            // between two supports, so grouping by it alone gave every
            // anchor a branch to itself. See GroupingAdjacency.
            List<int>[] grouping =
                MouldGeometry.GroupingAdjacency(result, edges, n);
            List<List<int>> anchorStrips =
                MouldGeometry.ConnectedGroups(anchorIds, neighbours: grouping);
            List<List<int>> perimeterLoops =
                MouldGeometry.ConnectedGroups(perimeterIds, neighbours: grouping);

            // CLOSED ONLY WHEN IT CLOSES. The last node walked has to be
            // adjacent to the first in the very graph the walk used, or the
            // closing segment is a chord across the net rather than a member
            // of it, drawn as a valid closed curve and labelled the
            // boundary.
            var closes = new bool[perimeterLoops.Count];
            for (int loop = 0; loop < perimeterLoops.Count; loop++)
            {
                List<int> walk = perimeterLoops[loop];
                closes[loop] =
                    !perimeterEstimated &&
                    walk.Count >= 3 &&
                    grouping[walk[walk.Count - 1]].Contains(walk[0]);
            }

            return new Net(
                positions,
                cables,
                principalNodes,
                anchorStrips
                    .Select(strip => strip.Select(i => positions[i]).ToList())
                    .ToList(),
                perimeterLoops
                    .Select(loop => loop.Select(i => positions[i]).ToList())
                    .ToList(),
                closes,
                perimeterEstimated,
                perimeterIds.Length,
                columnBranches,
                phase);
        }

        /// <summary>
        /// The frame as a component emits it: <see cref="Read"/>, the thrust
        /// mesh deformed onto the frame's own positions, and the polylines
        /// turned into curves. This is the only entry point that touches
        /// Rhino, and it is the one both components call.
        /// </summary>
        public static Set Build(ResultDto result)
        {
            Mesh? source = MouldGeometry.ThrustMeshFromResult(
                result, out int[] meshToNode);
            Net net = Read(result, source, meshToNode);
            Mesh? framed = source is null
                ? null
                : MouldGeometry.DeformMesh(source, meshToNode, net.Positions);

            // One BRANCH per bar, holding that bar's curve. Deliberately a
            // branch rather than a curve, and deliberately added even when
            // the polyline will not build: branch {i} has to stay bar {i} to
            // match Principal Nodes and Cables, and a bar silently missing
            // from the middle of the list would shift every bar after it and
            // quietly mislabel the lot.
            var principalLines = new List<List<Curve>>();
            foreach (List<Point3d> run in net.PrincipalNodes)
            {
                var branch = new List<Curve>();
                var polyline = new Polyline(run);
                if (polyline.IsValid && polyline.Count > 1)
                    branch.Add(polyline.ToNurbsCurve());
                principalLines.Add(branch);
            }

            var perimeterLines = new List<List<Curve>>();
            for (int loop = 0; loop < net.PerimeterLoops.Count; loop++)
            {
                var branch = new List<Curve>();
                List<Point3d> walk = net.PerimeterLoops[loop];
                if (!net.PerimeterEstimated && walk.Count >= 2)
                {
                    var points = new List<Point3d>(walk);
                    if (net.PerimeterCloses[loop])
                        points.Add(points[0]);
                    var polyline = new Polyline(points);
                    if (polyline.IsValid && polyline.Count > 1)
                        branch.Add(polyline.ToNurbsCurve());
                }
                perimeterLines.Add(branch);
            }

            return new Set(
                framed,
                net.Cables,
                principalLines,
                net.PrincipalNodes,
                net.AnchorGroups,
                net.PerimeterLoops,
                perimeterLines,
                net.PerimeterEstimated,
                net.PerimeterCount,
                net.ColumnBranches,
                net.Phase);
        }

        /// <summary>
        /// Which members stand together as one tree. The grouping the BLOCK
        /// carries is used when it accounts for every member exactly once,
        /// so Columns branch {i} here is Trees[{i}] there and no component
        /// rederives another's answer; TreesByFoot is the fallback for a
        /// block whose Trees do not cover the members it carries.
        /// </summary>
        public static List<List<int>> ColumnGroups(
            MouldColumnsDto block,
            MouldGeometry.ColumnTree tree)
        {
            var listed = new HashSet<int>(block.Trees.SelectMany(t => t));
            bool blockCovers =
                block.Trees.Count > 0 &&
                block.Members.Count == tree.Members.Count &&
                block.Trees.Sum(t => t.Count) == tree.Members.Count &&
                listed.Count == tree.Members.Count &&
                listed.All(m => m >= 0 && m < tree.Members.Count);
            return blockCovers
                ? block.Trees.Select(t => t.ToList()).ToList()
                : MouldGeometry.TreesByFoot(tree);
        }

        /// <summary>
        /// The live column members, one branch per tree, at the frame's own
        /// column nodes where it carries them and at the nodes the block was
        /// built with where it does not. Empty when the Result carries no
        /// columns.
        ///
        /// The second value is whether the frame's own nodes were usable: a
        /// Result with no columns block has nothing to mismatch and reports
        /// true, so it never by itself forces <see cref="Read"/>'s phase back
        /// to <see cref="FinalPhase"/>. A frame present but short or long
        /// against the block's own node count reports false, which is the
        /// same "this frame is not trustworthy" signal <c>positionsMatch</c>
        /// gives on the vertex count.
        /// </summary>
        private static (List<List<Line>> Branches, bool ColumnsMatch) ColumnLines(
            ResultDto result, MouldFrameDto? frame)
        {
            var branches = new List<List<Line>>();
            MouldColumnsDto? block = result.Mould?.Columns;
            if (block is null || block.Members.Count == 0)
                return (branches, true);
            MouldGeometry.ColumnTree tree = MouldGeometry.TreeFromBlock(block);
            IReadOnlyList<Point3Dto>? frameNodes = frame?.ColumnNodes;
            bool columnsMatch =
                frameNodes is not null && frameNodes.Count == tree.Nodes.Count;
            Point3d[] at =
                columnsMatch
                    ? frameNodes!
                        .Select(p => new Point3d(p.X, p.Y, p.Z))
                        .ToArray()
                    : tree.Nodes.ToArray();
            foreach (List<int> group in ColumnGroups(block, tree))
            {
                var branch = new List<Line>();
                foreach (int m in group)
                {
                    if (m < 0 || m >= tree.Members.Count)
                        continue;
                    (int lower, int upper) = tree.Members[m];
                    if (at[lower].DistanceTo(at[upper]) <= Collapsed)
                        continue;
                    branch.Add(new Line(at[lower], at[upper]));
                }
                branches.Add(branch);
            }
            return (branches, columnsMatch);
        }
    }
}
