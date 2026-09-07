#nullable enable

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Text;

namespace Ananke.COMPAS.NativeSmoke;

/// <summary>
/// THE INSTRUMENT SPEC RULE B ASKS FOR: a plan-view and elevation SVG of one
/// study's own generated skin tessellation, so a defect can be LOOKED AT
/// rather than inferred from a count. A command-line diagnostic mode on the
/// smoke harness (--render-svg), never wired into the 163-check suite
/// itself, writing wherever the caller points it -- the caller's job is to
/// point it at the repo's gitignored scratch or the system temp, never at a
/// tracked path, since generated SVGs are not committed.
///
/// Deliberately independent of <see cref="Program.Run"/>: this mode loads
/// its own copy of the plugin/Rhino/Grasshopper assemblies rather than
/// reusing Run's loader, so a mistake here can never perturb the 163-check
/// suite's own proven loading path.
///
/// WHAT "FAILED TO CLOSE" MEANS HERE, HONESTLY STATED: the real closure
/// this task cares about is ThickenCellSurface's walls-first Brep build,
/// which needs RhinoCommon's native core and cannot run in this console
/// process (confirmed elsewhere in this suite: DllNotFoundException outside
/// Rhino). The one pure-math, PROVEN-EXACT guard that predicts one class of
/// that failure without Rhino is SkinComponent.CellOffsetImpossible (the
/// concave-fold self-intersection under offset); this renderer calls it, by
/// reflection, at the given --thickness. It is a LOWER BOUND, not a proof:
/// a cell this guard passes can still fail Rhino's own wall build or its
/// final Brep.JoinBreps sew, and this renderer cannot see that from here.
/// Read the accompanying report before trusting a study with zero cells in
/// this colour as proof nothing closes badly on canvas.
/// </summary>
internal static partial class Program
{
    private const string RenderSvgFlag = "--render-svg";

    private static int RunRenderSvg(IReadOnlyList<string> args)
    {
        try
        {
            SvgRenderOptions options = SvgRenderOptions.Parse(args);
            SvgRenderSummary summary = RenderSkinSvg(options);
            Console.WriteLine(
                $"Wrote {options.OutputPath}: {summary.CellCount} cells, " +
                $"{summary.CourseCount} courses, " +
                $"{summary.UndersizedCount} below the {options.MinPiece:0.###} " +
                $"x {options.Size:0.###} size floor, " +
                $"{summary.KnownImpossibleCount} known-impossible-to-close " +
                "(lower bound; see the renderer's own doc comment), " +
                $"{summary.UncoveredRegionsCount} uncovered-region " +
                "warning(s) from the engine's own audit.");
            return 0;
        }
        catch (UsageException exception)
        {
            Console.Error.WriteLine($"ERROR: {exception.Message}");
            Console.Error.WriteLine(
                "Usage: dotnet run --project tests/native_smoke -- " +
                RenderSvgFlag + " <plugin.gha> <study name> <pattern 0|1|2> " +
                "<output.svg> [--size N] [--course-height N] " +
                "[--min-piece N] [--thickness N] [--rhino-root DIR] " +
                "[--exports-root DIR]");
            return 2;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                $"ERROR: {RenderSvgFlag} failed: {DescribeException(exception)}");
            Console.Error.WriteLine(exception.StackTrace);
            return 3;
        }
    }

    private sealed record SvgRenderOptions(
        string PluginPath,
        string Study,
        int Pattern,
        string OutputPath,
        double Size,
        double CourseHeight,
        double MinPiece,
        double Thickness,
        string? RhinoRoot,
        string ExportsRoot)
    {
        public static SvgRenderOptions Parse(IReadOnlyList<string> args)
        {
            string? pluginPath = null;
            string? study = null;
            int? pattern = null;
            string? outputPath = null;
            double size = 0.5;
            double courseHeight = 0.5;
            double minPiece = 0.20;
            double thickness = 0.05;
            string? rhinoRoot = null;
            string exportsRoot = HisExportsRoot;

            var positionals = new List<string>();
            for (int at = 0; at < args.Count; at++)
            {
                string argument = args[at];
                double NextDouble(string flag)
                {
                    if (++at >= args.Count)
                        throw new UsageException($"{flag} requires a number.");
                    if (!double.TryParse(
                            args[at], NumberStyles.Float,
                            CultureInfo.InvariantCulture, out double parsed))
                    {
                        throw new UsageException(
                            $"{flag} value '{args[at]}' is not a number.");
                    }
                    return parsed;
                }
                string NextString(string flag)
                {
                    if (++at >= args.Count)
                        throw new UsageException($"{flag} requires a value.");
                    return args[at];
                }
                switch (argument.ToLowerInvariant())
                {
                    case "--size":
                        size = NextDouble("--size");
                        break;
                    case "--course-height":
                        courseHeight = NextDouble("--course-height");
                        break;
                    case "--min-piece":
                        minPiece = NextDouble("--min-piece");
                        break;
                    case "--thickness":
                        thickness = NextDouble("--thickness");
                        break;
                    case "--rhino-root":
                        rhinoRoot = NextString("--rhino-root");
                        break;
                    case "--exports-root":
                        exportsRoot = NextString("--exports-root");
                        break;
                    default:
                        if (argument.StartsWith("-", StringComparison.Ordinal))
                            throw new UsageException($"Unknown option: {argument}");
                        positionals.Add(argument);
                        break;
                }
            }
            if (positionals.Count != 4)
            {
                throw new UsageException(
                    "Expected exactly 4 positional arguments (plugin.gha, " +
                    $"study name, pattern, output.svg); got {positionals.Count}.");
            }
            pluginPath = positionals[0];
            study = positionals[1];
            if (!int.TryParse(
                    positionals[2], NumberStyles.Integer,
                    CultureInfo.InvariantCulture, out int parsedPattern) ||
                parsedPattern is < 0 or > 2)
            {
                throw new UsageException(
                    $"Pattern must be 0 (courses), 1 (hexagonal) or 2 " +
                    $"(force-aligned); got '{positionals[2]}'.");
            }
            pattern = parsedPattern;
            outputPath = positionals[3];

            return new SvgRenderOptions(
                pluginPath, study, pattern.Value, outputPath, size,
                courseHeight, minPiece, thickness, rhinoRoot, exportsRoot);
        }
    }

    private readonly record struct SvgRenderSummary(
        int CellCount,
        int CourseCount,
        int UndersizedCount,
        int KnownImpossibleCount,
        int UncoveredRegionsCount);

    /// <summary>One emitted cell, read off the engine's own SkinCell by
    /// reflection, plus the two per-cell defect flags this renderer can
    /// compute headlessly.</summary>
    private sealed record RenderCell(
        int Course,
        List<double[]> Outline,
        bool Cap,
        bool Closer,
        double U0,
        double U1,
        bool Undersized,
        bool KnownImpossible);

    private static SvgRenderSummary RenderSkinSvg(SvgRenderOptions options)
    {
        string rhinoRoot = ResolveRhinoRoot(options.RhinoRoot);
        string rhinoSystem = Path.Combine(rhinoRoot, "System");
        string grasshopperDirectory =
            Path.Combine(rhinoRoot, "Plug-ins", "Grasshopper");
        string rhinoCommonPath =
            RequireFile(Path.Combine(rhinoSystem, "RhinoCommon.dll"));
        string ghIoPath =
            RequireFile(Path.Combine(grasshopperDirectory, "GH_IO.dll"));
        string grasshopperPath =
            RequireFile(Path.Combine(grasshopperDirectory, "Grasshopper.dll"));

        string pluginPath = Path.GetFullPath(options.PluginPath);
        if (!File.Exists(pluginPath))
            throw new UsageException($"Plugin does not exist: {pluginPath}");
        string pluginDirectory =
            Path.GetDirectoryName(pluginPath)
            ?? throw new InvalidOperationException(
                "The plugin path has no parent directory.");
        string[] probingDirectories =
        {
            pluginDirectory, rhinoSystem, grasshopperDirectory,
            Path.Combine(grasshopperDirectory, "Components"), rhinoRoot,
            Path.Combine(rhinoRoot, "Plug-ins")
        };
        AssemblyLoadContext.Default.Resolving += (_, assemblyName) =>
            ResolveAssembly(assemblyName, probingDirectories);
        LoadAssembly(rhinoCommonPath);
        LoadAssembly(ghIoPath);
        LoadAssembly(grasshopperPath);
        Assembly plugin = LoadAssembly(pluginPath);

        Type patternsType = RequireComponentType(plugin, "SkinPatterns");
        // CellOffsetImpossible/CornerNormals live on the GH component class
        // itself (SkinComponent, singular), not a separate helper type.
        Type componentsType = RequireComponentType(plugin, "SkinComponent");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type resultType = RequireContractType(plugin, "ResultDto");
        MethodInfo readNet = RequirePublicStatic(patternsType, "ReadNet");
        MethodInfo courses = RequirePublicStatic(
            patternsType, "Courses",
            netType, typeof(double), typeof(double), typeof(double));
        MethodInfo hexagonal = RequirePublicStatic(
            patternsType, "Hexagonal",
            netType, typeof(double), typeof(double), typeof(double));
        MethodInfo cornerNormals =
            RequireStatic(componentsType, "CornerNormals");
        MethodInfo cellOffsetImpossible =
            RequireStatic(componentsType, "CellOffsetImpossible");

        string formPath = Path.Combine(
            options.ExportsRoot, $"{options.Study}-form.json");
        if (!File.Exists(formPath))
        {
            throw new UsageException(
                $"'{options.Study}' has no -form.json under " +
                $"'{options.ExportsRoot}'.");
        }
        object resultDto = DeserializeContract(
            plugin, resultType, HisNetExtractResultContractJson(formPath));
        object? net = readNet.Invoke(null, new object?[] { resultDto });
        if (net is null)
        {
            throw new InvalidOperationException(
                $"'{options.Study}': SkinPatterns.ReadNet returned null " +
                "(not a full TNA Result), so there is no net to render.");
        }

        object generated = options.Pattern switch
        {
            1 => hexagonal.Invoke(
                null,
                new object[]
                {
                    net, options.Size, options.CourseHeight, options.MinPiece
                })!,
            2 => throw new UsageException(
                "Pattern 2 (force-aligned) is not wired into this " +
                "renderer yet -- ForceAligned takes a different argument " +
                "shape (principal-line guides) this CLI does not collect. " +
                "His eight studies never use it at his canvas settings."),
            _ => courses.Invoke(
                null,
                new object[]
                {
                    net, options.Size, options.CourseHeight, options.MinPiece
                })!
        };

        double clampedMinPiece = Math.Clamp(options.MinPiece, 0.0, 0.5);
        double minimumPiece = clampedMinPiece * options.Size;

        IEnumerable rawCells =
            (IEnumerable)generated.GetType()
                .GetProperty("Cells")!.GetValue(generated)!;
        var cells = new List<RenderCell>();
        foreach (object cell in rawCells)
        {
            List<double[]> outline = ((IEnumerable)cell.GetType()
                    .GetProperty("Outline")!.GetValue(cell)!)
                .Cast<double[]>()
                .ToList();
            bool cap = Reading<bool>(cell, "Cap");
            bool closer = Reading<bool>(cell, "Closer");
            double u0 = Reading<double>(cell, "U0");
            double u1 = Reading<double>(cell, "U1");
            int course = Reading<int>(cell, "Course");

            bool undersized =
                !cap && Math.Abs(u1 - u0) < minimumPiece - 1.0e-9;

            bool impossible = false;
            if (outline.Count >= 3)
            {
                object normals = cornerNormals.Invoke(
                    null, new object[] { net, outline })!;
                object?[] callArgs =
                    { outline, normals, options.Thickness, null, null };
                impossible = (bool)cellOffsetImpossible.Invoke(
                    null, callArgs)!;
            }

            cells.Add(new RenderCell(
                course, outline, cap, closer, u0, u1, undersized,
                impossible));
        }

        List<double[]> netVertices = ((IEnumerable)netType
                .GetProperty("Vertices")!.GetValue(net)!)
            .Cast<double[]>().ToList();
        List<int[]> netFaces = ((IEnumerable)netType
                .GetProperty("Faces")!.GetValue(net)!)
            .Cast<int[]>().ToList();

        // Ad hoc root-cause aid, never in the committed report: dump the
        // highest cells' own real coordinates so a visual defect in the
        // SVG can be traced to an exact instance, the way rule STEP 2
        // asks. SKIN_SVG_DEBUG_DUMP=1 in the environment turns it on.
        if (Environment.GetEnvironmentVariable("SKIN_SVG_DEBUG_DUMP") == "1")
        {
            foreach (RenderCell cell in cells
                         .OrderByDescending(c => c.Outline.Max(p => p[2]))
                         .Take(40))
            {
                double maxZ = cell.Outline.Max(p => p[2]);
                double minZ = cell.Outline.Min(p => p[2]);
                Console.Error.WriteLine(
                    $"course={cell.Course} cap={cell.Cap} " +
                    $"closer={cell.Closer} u0={cell.U0:0.####} " +
                    $"u1={cell.U1:0.####} span={cell.U1 - cell.U0:0.####} " +
                    $"minZ={minZ:0.####} maxZ={maxZ:0.####} outline=[" +
                    string.Join(
                        " ",
                        cell.Outline.Select(
                            p => $"({p[0]:0.####},{p[1]:0.####},{p[2]:0.####})")) +
                    "]");
            }
            double netMaxZ = netVertices.Max(p => p[2]);
            Console.Error.WriteLine($"net own max Z = {netMaxZ:0.######}");
        }

        int courseCount = Reading<int>(generated, "CourseCount");
        int uncoveredRegionsCount = ((IEnumerable)generated.GetType()
                .GetProperty("UncoveredRegions")!.GetValue(generated)!)
            .Cast<string>().Count();
        var uncoveredRegionsText = ((IEnumerable)generated.GetType()
                .GetProperty("UncoveredRegions")!.GetValue(generated)!)
            .Cast<string>().ToList();
        var capCrescentsText = ((IEnumerable)generated.GetType()
                .GetProperty("CapCrescents")!.GetValue(generated)!)
            .Cast<string>().ToList();
        int capsOversized = Reading<int>(generated, "CapsOversized");
        var capGirths = ((IEnumerable)generated.GetType()
                .GetProperty("CapGirths")!.GetValue(generated)!)
            .Cast<double>().ToList();
        int closedSeams = Reading<int>(generated, "ClosedSeams");
        int closerCells = Reading<int>(generated, "CloserCells");
        int closerRefused = Reading<int>(generated, "CloserRefused");
        int closerUndersized = Reading<int>(generated, "CloserUndersized");
        int planOverlapDropped = Reading<int>(generated, "PlanOverlapDropped");
        int planDegenerateDropped =
            Reading<int>(generated, "PlanDegenerateDropped");
        int weldCollapsedDropped =
            Reading<int>(generated, "WeldCollapsedDropped");
        int bandEscapedRefused = Reading<int>(generated, "BandEscapedRefused");
        int mergedPieces = Reading<int>(generated, "MergedPieces");
        int mergedShortKept = Reading<int>(generated, "MergedShortKept");
        int mergedStillShort = Reading<int>(generated, "MergedStillShort");
        int sevenSidedCells = Reading<int>(generated, "SevenSidedCells");
        int fiveSidedCells = Reading<int>(generated, "FiveSidedCells");

        string legend = BuildLegendText(
            options, cells.Count, courseCount, minimumPiece,
            uncoveredRegionsCount, uncoveredRegionsText, capCrescentsText,
            capsOversized, capGirths, closedSeams, closerCells,
            closerRefused, closerUndersized, planOverlapDropped,
            planDegenerateDropped, weldCollapsedDropped, bandEscapedRefused,
            mergedPieces, mergedShortKept, mergedStillShort,
            sevenSidedCells, fiveSidedCells);

        string svg = BuildSvg(options, cells, netVertices, netFaces, legend);
        Directory.CreateDirectory(
            Path.GetDirectoryName(Path.GetFullPath(options.OutputPath))
            ?? ".");
        File.WriteAllText(options.OutputPath, svg, Encoding.UTF8);

        return new SvgRenderSummary(
            cells.Count, courseCount,
            cells.Count(c => c.Undersized),
            cells.Count(c => c.KnownImpossible),
            uncoveredRegionsCount);
    }

    private static string BuildLegendText(
        SvgRenderOptions options, int cellCount, int courseCount,
        double minimumPiece, int uncoveredRegionsCount,
        List<string> uncoveredRegionsText, List<string> capCrescentsText,
        int capsOversized, List<double> capGirths, int closedSeams,
        int closerCells, int closerRefused, int closerUndersized,
        int planOverlapDropped, int planDegenerateDropped,
        int weldCollapsedDropped, int bandEscapedRefused, int mergedPieces,
        int mergedShortKept, int mergedStillShort, int sevenSidedCells,
        int fiveSidedCells)
    {
        var sb = new StringBuilder();
        sb.Append(
            $"{options.Study} -- pattern {options.Pattern} -- Size " +
            $"{options.Size:0.###} Course Height {options.CourseHeight:0.###} " +
            $"Min Piece {options.MinPiece:0.###} (floor {minimumPiece:0.###} m) " +
            $"Thickness {options.Thickness:0.###} (assumed, not in the export)");
        sb.Append(
            $" | {cellCount} cells, {courseCount} courses, " +
            $"{capGirths.Count} cap(s) [{capsOversized} oversized" +
            (capGirths.Count > 0
                ? $", max girth {capGirths.Max():0.###} m"
                : string.Empty) + "]");
        sb.Append(
            $" | closer: {closedSeams} seam(s) closed, {closerCells} " +
            $"stones, {closerRefused} refused, {closerUndersized} undersized");
        sb.Append(
            $" | dropped: {planOverlapDropped} overlap, " +
            $"{planDegenerateDropped} degenerate, {weldCollapsedDropped} " +
            $"weld-collapsed, {bandEscapedRefused} band-escaped");
        sb.Append(
            $" | merge: {mergedPieces} merged ({mergedShortKept} kept " +
            $"short, {mergedStillShort} still short)");
        sb.Append(
            $" | {fiveSidedCells} five-sided, {sevenSidedCells} seven-sided");
        sb.Append($" | {uncoveredRegionsCount} uncovered-region warning(s)");
        foreach (string line in uncoveredRegionsText)
            sb.Append($" :: {line}");
        foreach (string line in capCrescentsText)
            sb.Append($" :: cap crescent: {line}");
        return sb.ToString();
    }

    private static string BuildSvg(
        SvgRenderOptions options, List<RenderCell> cells,
        List<double[]> netVertices, List<int[]> netFaces, string legend)
    {
        const double PanelSize = 900.0;
        const double Margin = 40.0;
        const double Gutter = 60.0;
        double totalWidth = (PanelSize * 2) + Gutter + (Margin * 2);
        double totalHeight = PanelSize + (Margin * 2) + 140.0;

        // Plan: model X/Y. Elevation: the horizontal axis with the wider
        // spread (X or Y), against model Z. Both panels flip the vertical
        // screen axis so "up" in the model reads as "up" on the page.
        double xRange = Range(netVertices, p => p[0]);
        double yRange = Range(netVertices, p => p[1]);
        bool elevationUsesX = xRange >= yRange;

        (double MinU, double MaxU, double MinV, double MaxV) planBounds =
            Bounds(netVertices, p => p[0], p => p[1]);
        (double MinU, double MaxU, double MinV, double MaxV) elevationBounds =
            Bounds(
                netVertices,
                p => elevationUsesX ? p[0] : p[1],
                p => p[2]);

        var sb = new StringBuilder();
        sb.Append(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" " +
            $"viewBox=\"0 0 {Fmt(totalWidth)} {Fmt(totalHeight)}\" " +
            "font-family=\"Consolas, monospace\">\n");
        sb.Append(
            $"<rect x=\"0\" y=\"0\" width=\"{Fmt(totalWidth)}\" " +
            $"height=\"{Fmt(totalHeight)}\" fill=\"#ffffff\"/>\n");

        double planX0 = Margin;
        double planY0 = Margin;
        DrawPanel(
            sb, "PLAN (x, y)", planX0, planY0, PanelSize, planBounds,
            p => p[0], p => p[1], cells, netVertices, netFaces);

        double elevX0 = Margin + PanelSize + Gutter;
        double elevY0 = Margin;
        DrawPanel(
            sb,
            elevationUsesX ? "ELEVATION (x, z)" : "ELEVATION (y, z)",
            elevX0, elevY0, PanelSize, elevationBounds,
            elevationUsesX ? (p => p[0]) : (p => p[1]), p => p[2],
            cells, netVertices, netFaces);

        double legendY = Margin + PanelSize + 30.0;
        int line = 0;
        foreach (string wrapped in WrapLines(legend, 150))
        {
            sb.Append(
                $"<text x=\"{Fmt(Margin)}\" y=\"{Fmt(legendY + (line * 16))}\" " +
                "font-size=\"12\" fill=\"#333\">" + Escape(wrapped) +
                "</text>\n");
            line++;
        }
        sb.Append(
            $"<text x=\"{Fmt(Margin)}\" y=\"{Fmt(legendY + (line * 16) + 10)}\" " +
            "font-size=\"12\" fill=\"#333\">colour key: pale blue = " +
            "ordinary course cell, amber = crown cap, pale green = " +
            "closer/seam stone, YELLOW = below the size floor, RED = " +
            "known-impossible-to-close (lower bound proxy, see report), " +
            "light grey backdrop = the net's own triangulated surface " +
            "(true uncovered area is WHITE grey, i.e. grey showing " +
            "through no cell at all; pure page-white outside the grey " +
            "is simply off the vault).</text>\n");
        sb.Append("</svg>\n");
        return sb.ToString();
    }

    private static void DrawPanel(
        StringBuilder sb, string title, double x0, double y0, double size,
        (double MinU, double MaxU, double MinV, double MaxV) bounds,
        Func<double[], double> u, Func<double[], double> v,
        List<RenderCell> cells, List<double[]> netVertices,
        List<int[]> netFaces)
    {
        double spanU = Math.Max(bounds.MaxU - bounds.MinU, 1.0e-6);
        double spanV = Math.Max(bounds.MaxV - bounds.MinV, 1.0e-6);
        double scale = 0.92 * size / Math.Max(spanU, spanV);
        double padU = (size - (spanU * scale)) / 2.0;
        double padV = (size - (spanV * scale)) / 2.0;

        (double, double) ToScreen(double[] point)
        {
            double sx = x0 + padU + ((u(point) - bounds.MinU) * scale);
            double sy = y0 + size - padV -
                ((v(point) - bounds.MinV) * scale);
            return (sx, sy);
        }

        sb.Append(
            $"<g><rect x=\"{Fmt(x0)}\" y=\"{Fmt(y0)}\" width=\"{Fmt(size)}\" " +
            $"height=\"{Fmt(size)}\" fill=\"#ffffff\" stroke=\"#999\" " +
            "stroke-width=\"1\"/>\n");
        sb.Append(
            $"<text x=\"{Fmt(x0)}\" y=\"{Fmt(y0 - 10)}\" font-size=\"14\" " +
            $"fill=\"#111\">{Escape(title)}</text>\n");

        // The net's own triangulated surface, as a light grey backdrop:
        // the TRUE silhouette (concavities included), so a real hole
        // inside it shows as grey peeking through no cell, distinct from
        // page-white that is simply off the vault altogether.
        foreach (int[] face in netFaces)
        {
            if (face.Length < 3)
                continue;
            var pts = new List<(double, double)>();
            for (int at = 0; at < face.Length; at++)
                pts.Add(ToScreen(netVertices[face[at]]));
            sb.Append(
                "<polygon points=\"" +
                string.Join(
                    " ", pts.Select(p => $"{Fmt(p.Item1)},{Fmt(p.Item2)}")) +
                "\" fill=\"#e9edf2\" stroke=\"none\"/>\n");
        }

        foreach (RenderCell cell in cells)
        {
            if (cell.Outline.Count < 3)
                continue;
            var pts = cell.Outline.Select(ToScreen).ToList();
            string fill = cell.KnownImpossible
                ? "#e63946"
                : cell.Undersized
                    ? "#ffe14d"
                    : cell.Cap
                        ? "#f4d9a0"
                        : cell.Closer
                            ? "#cde8d5"
                            : "#cfe3f7";
            string stroke =
                cell.KnownImpossible || cell.Undersized ? "#000000" : "#1c2733";
            string strokeWidth =
                cell.KnownImpossible || cell.Undersized ? "1.6" : "0.6";
            sb.Append(
                "<polygon points=\"" +
                string.Join(
                    " ", pts.Select(p => $"{Fmt(p.Item1)},{Fmt(p.Item2)}")) +
                $"\" fill=\"{fill}\" fill-opacity=\"0.9\" stroke=\"{stroke}\" " +
                $"stroke-width=\"{strokeWidth}\"/>\n");
        }
        sb.Append("</g>\n");
    }

    private static double Range(
        List<double[]> points, Func<double[], double> select)
    {
        if (points.Count == 0)
            return 0.0;
        return points.Max(select) - points.Min(select);
    }

    private static (double, double, double, double) Bounds(
        List<double[]> points, Func<double[], double> u,
        Func<double[], double> v)
    {
        if (points.Count == 0)
            return (0.0, 1.0, 0.0, 1.0);
        return (
            points.Min(u), points.Max(u), points.Min(v), points.Max(v));
    }

    private static string Fmt(double value) =>
        value.ToString("0.###", CultureInfo.InvariantCulture);

    private static string Escape(string text) =>
        text
            .Replace("&", "&amp;")
            .Replace("<", "&lt;")
            .Replace(">", "&gt;");

    private static IEnumerable<string> WrapLines(string text, int width)
    {
        var words = text.Split(' ');
        var line = new StringBuilder();
        foreach (string word in words)
        {
            if (line.Length + word.Length + 1 > width)
            {
                yield return line.ToString();
                line.Clear();
            }
            if (line.Length > 0)
                line.Append(' ');
            line.Append(word);
        }
        if (line.Length > 0)
            yield return line.ToString();
    }
}
