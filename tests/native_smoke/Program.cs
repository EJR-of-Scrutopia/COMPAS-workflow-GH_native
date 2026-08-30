using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json.Nodes;

namespace Ananke.COMPAS.NativeSmoke;

internal static class Program
{
    private const string GrasshopperComponentBase =
        "Grasshopper.Kernel.GH_Component";
    private const string GrasshopperPersistentParamBase =
        "Grasshopper.Kernel.GH_PersistentParam`1";
    private const string RhinoCodeNamespace = "RhinoCodePluginGH";

    private static readonly object ResolverLock = new();
    private static readonly HashSet<string> Resolving = new(
        StringComparer.OrdinalIgnoreCase);
    private static readonly IReadOnlyDictionary<string, int[]> FlattenedInputs =
        new Dictionary<string, int[]>(StringComparer.Ordinal)
        {
            ["Ananke.COMPAS.Native.Components.PatternComponent"] =
                new[] { 0, 4 },
            ["Ananke.COMPAS.Native.Components.SupportsComponent"] =
                new[] { 1 },
            ["Ananke.COMPAS.Native.Components.LoadsComponent"] =
                new[] { 2 },
            ["Ananke.COMPAS.Native.Components.FdSolveComponent"] =
                new[] { 1 },
            ["Ananke.COMPAS.Native.Components.ExportComponent"] =
                new[] { 4, 5 }
        };
    private static readonly HashSet<string> RequiredPreviewComponents = new(
        StringComparer.Ordinal)
        {
            "Ananke.COMPAS.Native.Components.PatternComponent",
            "Ananke.COMPAS.Native.Components.SupportsComponent",
            "Ananke.COMPAS.Native.Components.LoadsComponent",
            "Ananke.COMPAS.Native.Components.TnaRelaxComponent",
            "Ananke.COMPAS.Native.Components.TnaSolveComponent",
            "Ananke.COMPAS.Native.Components.TnaSolveAlgebraicComponent",
            "Ananke.COMPAS.Native.Components.FdSolveComponent",
            "Ananke.COMPAS.Native.Components.DisplayComponent"
        };
    private static readonly HashSet<string> NativeVisibilityGuardComponents =
        new(StringComparer.Ordinal)
        {
            "Ananke.COMPAS.Native.Components.PatternComponent",
            "Ananke.COMPAS.Native.Components.SupportsComponent",
            "Ananke.COMPAS.Native.Components.LoadsComponent",
            "Ananke.COMPAS.Native.Components.DisplayComponent"
        };
    /// <summary>
    /// Deconstruct is the one merged extraction surface over the unified
    /// <c>ResultDto</c>, replacing the four deleted v0.2 query components
    /// (TNA Geometry, TNA Members, TNA Actions, Result Breakdown). Checked
    /// the same way those were: full parameter Names, in registration
    /// order, against the plan's fixed output list.
    /// </summary>
    private static readonly IReadOnlyDictionary<
        string,
        (string[] Inputs, string[] Outputs)> VisualiseContracts =
            new Dictionary<
                string,
                (string[] Inputs, string[] Outputs)>(StringComparer.Ordinal)
            {
                ["Ananke.COMPAS.Native.Components.DeconstructComponent"] = (
                    new[] { "Result" },
                    new[]
                    {
                        "Thrust Mesh",
                        "Member Lines",
                        "Form Lines",
                        "Member IDs",
                        "Node IDs",
                        "Support Points",
                        "Load Points",
                        "Load Vectors",
                        "Reaction Points",
                        "Reaction Vectors",
                        "Columns",
                        "Heads",
                        "Feet"
                    }),
                ["Ananke.COMPAS.Native.Components.SkinComponent"] = (
                    new[] { "Result", "Course Height" },
                    new[] { "Face Polylines", "Face Courses" }),
                // Monitor's ports are pinned for the same reason Deconstruct's
                // are: every number tree here is READ AGAINST a Deconstruct
                // geometry tree by slot, so a renamed or reordered output is a
                // silently rewired canvas rather than a compile error.
                ["Ananke.COMPAS.Native.Components.StressAnalysisComponent"] = (
                    new[] { "Result", "EI", "EA", "Tolerance", "Cable Capacity", "Column Capacity" },
                    new[]
                    {
                        "Member Force", "Force Density", "Horizontal Force", "Slack",
                        "Spool Length", "Unstrained Length",
                        "Anchor Along", "Anchor Across",
                        "Tip Reaction", "Column Force", "Thrust", "Lean",
                        "Deviation", "Deviation Stats", "Reachable", "Unreachable",
                        "Bar Sag", "Residuals",
                        "Cable Utilisation", "Column Utilisation",
                        "Result"
                    }),
                // Animate's ports are pinned because every one of them is an
                // index a downstream branch is read by. Perimeter Lines was
                // APPENDED at 8 on purpose: outputs 0 to 7 keep their slots,
                // so a Grasshopper file saved before it existed still finds
                // its wires. Moving any of them silently rewires the canvas.
                ["Ananke.COMPAS.Native.Components.MouldAnimateComponent"] = (
                    new[] { "Result", "Time", "Pre-Sag", "Extension" },
                    new[]
                    {
                        "Mesh",
                        "Cables",
                        "Principal Lines",
                        "Principal Nodes",
                        "Anchor Nodes",
                        "Perimeter Nodes",
                        "Result",
                        "Columns",
                        "Perimeter Lines"
                    }),
                // Export's ports are pinned because Format's removal moved
                // every input after slot 0 up one and split the single JSON
                // output into one per kind: the order below IS the canvas
                // contract, and the four kind outputs are read by slot.
                ["Ananke.COMPAS.Native.Components.ExportComponent"] = (
                    new[] { "Result", "Path", "Write", "Name", "Cells", "Courses", "Live", "Studio", "Column Radius" },
                    new[] { "Contract JSON", "COMPAS JSON", "Tessellation JSON", "Columns JSON", "Written", "Uploaded" })
            };
    private static readonly IReadOnlyDictionary<
        string,
        (string Name, string NickName, string Tab, string[] InputNickNames,
            string[] OutputNickNames)> SpineComponentContracts =
            new Dictionary<
                string,
                (string Name, string NickName, string Tab,
                    string[] InputNickNames, string[] OutputNickNames)>(
                StringComparer.Ordinal)
            {
                ["Ananke.COMPAS.Native.Components.PatternComponent"] = (
                    "Pattern",
                    "Pattern",
                    "01 Model",
                    // P/RS/RD joined 2026-08-26: the principal lines are
                    // resolved to vertex runs HERE, where the curves and the
                    // geometry still agree, and carried down the contract.
                    new[] { "G", "M", "R", "Tol", "P" },
                    new[] { "PAT" }),
                ["Ananke.COMPAS.Native.Components.SupportsComponent"] = (
                    "Supports",
                    "Supports",
                    "01 Model",
                    new[] { "PAT", "A", "Tol" },
                    new[] { "SUP" }),
                ["Ananke.COMPAS.Native.Components.LoadsComponent"] = (
                    "Loads",
                    "Loads",
                    "01 Model",
                    new[] { "SUP", "V", "ID", "F" },
                    new[] { "PRB" }),
                ["Ananke.COMPAS.Native.Components.TnaRelaxComponent"] = (
                    "TNA Relax",
                    "TNA Relax",
                    "02 Form Finding",
                    new[] { "PRB", "q", "Sag %", "FA" },
                    new[] { "RLX" }),
                ["Ananke.COMPAS.Native.Components.TnaSolveComponent"] = (
                    "TNA Solve",
                    "TNA Solve",
                    "02 Form Finding",
                    new[] { "RLX", "H", "I", "Run" },
                    new[] { "RES", "M", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.TnaSolveAlgebraicComponent"] = (
                    "TNA Solve Algebraic",
                    "TNA Solve A",
                    "02 Form Finding",
                    new[] { "RLX", "H", "Run" },
                    new[] { "RES", "M", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.FdSolveComponent"] = (
                    "FD Solve",
                    "FD Solve",
                    "02 Form Finding",
                    new[] { "PRB", "q", "Run" },
                    new[] { "RES", "L", "S" }),
                ["Ananke.COMPAS.Native.Components.StyleComponent"] = (
                    "Style",
                    "Style",
                    "03 Visualise",
                    new[] { "Preset", "Weight", "Vector" },
                    new[] { "STY" }),
                ["Ananke.COMPAS.Native.Components.ImportPiecesComponent"] = (
                    "Import Pieces",
                    "Pieces",
                    "07 Delivery",
                    new[] { "P" },
                    // Addendum, 2026-08-20: the flat Courses (C) output is
                    // removed; M/K/S are trees branched by course, B is
                    // the new base-mesh item.
                    new[] { "M", "K", "S", "B", "D" })
            };

    public static int Main(string[] args)
    {
        try
        {
            Options options = Options.Parse(args);
            return Run(options);
        }
        catch (UsageException exception)
        {
            Console.Error.WriteLine($"ERROR: {exception.Message}");
            Console.Error.WriteLine(
                "Usage: dotnet run --project tests/native_smoke -- " +
                "<plugin.gha> [--rhino-root <Rhino 8 directory>]");
            return 2;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                $"ERROR: Native component smoke test could not run: " +
                $"{DescribeException(exception)}");
            Console.Error.WriteLine(exception.StackTrace);
            return 3;
        }
    }

    private static int Run(Options options)
    {
        string pluginPath = Path.GetFullPath(options.PluginPath);
        if (!File.Exists(pluginPath))
            throw new UsageException($"Plugin does not exist: {pluginPath}");

        string rhinoRoot = ResolveRhinoRoot(options.RhinoRoot);
        string rhinoSystem = Path.Combine(rhinoRoot, "System");
        string grasshopperDirectory = Path.Combine(
            rhinoRoot,
            "Plug-ins",
            "Grasshopper");

        string rhinoCommonPath = RequireFile(
            Path.Combine(rhinoSystem, "RhinoCommon.dll"));
        string ghIoPath = RequireFile(
            Path.Combine(grasshopperDirectory, "GH_IO.dll"));
        string grasshopperPath = RequireFile(
            Path.Combine(grasshopperDirectory, "Grasshopper.dll"));

        string pluginDirectory =
            Path.GetDirectoryName(pluginPath)
            ?? throw new InvalidOperationException(
                "The plugin path has no parent directory.");
        string[] probingDirectories =
        {
            pluginDirectory,
            rhinoSystem,
            grasshopperDirectory,
            Path.Combine(grasshopperDirectory, "Components"),
            rhinoRoot,
            Path.Combine(rhinoRoot, "Plug-ins")
        };

        AssemblyLoadContext.Default.Resolving += (_, assemblyName) =>
            ResolveAssembly(assemblyName, probingDirectories);

        // Establish the same type identity the plugin expects before loading it.
        LoadAssembly(rhinoCommonPath);
        LoadAssembly(ghIoPath);
        LoadAssembly(grasshopperPath);
        Assembly plugin = LoadAssembly(pluginPath);

        Type[] componentTypes = GetLoadableTypes(plugin)
            .Where(IsConcretePublicGrasshopperComponent)
            .OrderBy(type => type.FullName, StringComparer.Ordinal)
            .ToArray();
        Type[] parameterTypes = GetLoadableTypes(plugin)
            .Where(IsConcretePublicPersistentParameter)
            .OrderBy(type => type.FullName, StringComparer.Ordinal)
            .ToArray();

        Console.WriteLine($"Plugin: {plugin.FullName}");
        Console.WriteLine($"Path: {pluginPath}");
        Console.WriteLine($"Rhino root: {rhinoRoot}");

        if (componentTypes.Length == 0)
        {
            Console.Error.WriteLine(
                "ERROR: No concrete public GH_Component types were found.");
            return 4;
        }

        var failures = new List<string>();
        var documentGuids = new Dictionary<Guid, string>();
        foreach (Type componentType in componentTypes)
        {
            Type? forbiddenBase = FindRhinoCodeBase(componentType);
            if (forbiddenBase is not null)
            {
                failures.Add(
                    $"{componentType.FullName}: derives from forbidden " +
                    $"RhinoCode script base {forbiddenBase.FullName}.");
                continue;
            }

            object? instance = null;
            try
            {
                instance = Activator.CreateInstance(componentType);
                if (instance is null)
                    throw new InvalidOperationException(
                        "Activator.CreateInstance returned null.");

                string displayName = ReadDisplayName(instance, componentType);
                ValidateFlattenedInputs(instance, componentType);
                ValidatePreviewCapability(instance, componentType);
                ValidateNativePreviewVisibilityGuard(instance, componentType);
                ValidateVisualiseContract(instance, componentType);
                ValidateSpineComponentContract(instance, componentType);
                ValidateIcon(instance, componentType);
                RecordDocumentGuid(
                    instance,
                    componentType,
                    documentGuids,
                    failures);
                Console.WriteLine(
                    $"PASS  {displayName} [{componentType.FullName}]");
            }
            catch (Exception exception)
            {
                failures.Add(
                    $"{componentType.FullName}: constructor failed: " +
                    DescribeException(exception));
            }
            finally
            {
                if (instance is IDisposable disposable)
                    disposable.Dispose();
            }
        }

        Console.WriteLine($"Components discovered: {componentTypes.Length}");
        int componentFailureCount = failures.Count;
        Console.WriteLine(
            $"Components passed: {componentTypes.Length - componentFailureCount}");

        foreach (Type parameterType in parameterTypes)
        {
            object? instance = null;
            try
            {
                instance = Activator.CreateInstance(parameterType);
                if (instance is null)
                    throw new InvalidOperationException(
                        "Activator.CreateInstance returned null.");
                RecordDocumentGuid(
                    instance,
                    parameterType,
                    documentGuids,
                    failures);
                Console.WriteLine(
                    $"PASS  parameter [{parameterType.FullName}]");
            }
            catch (Exception exception)
            {
                failures.Add(
                    $"{parameterType.FullName}: constructor failed: " +
                    DescribeException(exception));
            }
            finally
            {
                if (instance is IDisposable disposable)
                    disposable.Dispose();
            }
        }
        if (parameterTypes.Length != 12)
        {
            failures.Add(
                $"Expected 12 public persistent contract parameters, found " +
                $"{parameterTypes.Length}.");
        }
        Console.WriteLine($"Parameters discovered: {parameterTypes.Length}");
        Console.WriteLine(
            $"Parameters passed: " +
            $"{parameterTypes.Length - (failures.Count - componentFailureCount)}");

        try
        {
            ValidateResultContract(plugin);
            Console.WriteLine(
                "PASS  ResultDto contract: valid TNA, valid FD, and " +
                "invalid-without-graphs cases validate correctly.");
        }
        catch (Exception exception)
        {
            failures.Add($"ResultDto contract: {DescribeException(exception)}");
        }

        try
        {
            ValidateSpineContracts(plugin);
            Console.WriteLine(
                "PASS  Spine contracts: AnchoredPattern, Problem, and " +
                "Relaxed validate correctly (valid and invalid cases), " +
                "and Problem attaches to ResultDto.");
        }
        catch (Exception exception)
        {
            failures.Add($"Spine contracts: {DescribeException(exception)}");
        }

        try
        {
            ValidateResultGooRawWireSnapshot(plugin);
            Console.WriteLine(
                "PASS  ResultGoo RawWire snapshot: construction and " +
                "Duplicate() both preserve RawWire, and Contract-mode " +
                "serialisation still excludes it.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ResultGoo RawWire snapshot: {DescribeException(exception)}");
        }

        try
        {
            ValidateExportCoursesValidation(plugin);
            Console.WriteLine(
                "PASS  ExportComponent.HasNegativeCourse: flags every " +
                "offending index/value and leaves a clean Courses list " +
                "alone.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ExportComponent.HasNegativeCourse: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidateExportTessellationJsonOptions(plugin);
            Console.WriteLine(
                "PASS  ExportComponent.BuildTessellationJson: shape and " +
                "byte content match the studio's bench.tessellation/1 " +
                "sidecar contract under the shared ContractJson.Options.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ExportComponent.BuildTessellationJson: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidateImportPiecesParsing(plugin);
            Console.WriteLine(
                "PASS  ImportPiecesComponent.ParseDocument: piece count, " +
                "drop-order preservation, vertex/face array shapes, and " +
                "base_mesh presence/shape match the committed " +
                "bench.pieces/1 fixture (2 courses, 14 pieces); the " +
                "course-tree partitioning is MEASURED against the exact " +
                "per-course counts and in-branch order; a doctored copy " +
                "with no base_mesh key still parses (BaseMesh null); " +
                "doctored schema/units copies are refused naming what " +
                "was found.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ImportPiecesComponent.ParseDocument: " +
                $"{DescribeException(exception)}");
        }

        try
        {
            ValidatePrincipalLineSnapping(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.SnapSampledLineToNodes: a line drawn down the "
                + "middle of a bay, with the node column either side of it "
                + "inside the catch radius, matches ONE connected column end "
                + "to end (9 nodes, every consecutive pair joined by a mesh "
                + "edge, x constant, y strictly increasing) and reports its "
                + "0.5 offset; a line drawn on a column matches that column "
                + "at zero offset. The zigzag regression is MEASURED, not "
                + "inspected.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"MouldGeometry.SnapSampledLineToNodes: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidateColumnAim(plugin);
            Console.WriteLine(
                "PASS  ColumnFinder load and aim: a symmetric bay pulls a notch "
                + "straight down and the column comes out plumb; a one-sided "
                + "bay at 45 degrees leans the column 45 degrees the other way, "
                + "its foot on the side the cable pulls toward; a nearly "
                + "horizontal pull is held at the 60-degree cap. Measured "
                + "against hand-computed vectors, not inspected.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ColumnFinder load and aim: {DescribeException(exception)}");
        }

        try
        {
            ValidateRunDeduplication(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder.Deduplicate: one line traced from "
                + "both ends is ONE bar even when the two traces finish on "
                + "different nodes, which is the case matching their endpoints "
                + "could not catch and which gave one line two full sets of "
                + "columns; separate lines and merely crossing lines both "
                + "survive as two.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder deduplication: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidateDerivationRemoved(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder: the anchor derivation is GONE. A "
                + "principal line is a decision Param draws into Pattern; "
                + "nothing in the plugin derives one from the anchors any more.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder derivation removed: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidatePrincipalOutcome(plugin);
            Console.WriteLine(
                "PASS  PrincipalRunFinder.Outcome: no curves is silence, a "
                + "dropped curve is a warning naming the count, two curves on "
                + "one run is a remark that says merged, and curves with NO "
                + "run at all is an error that says no Pattern is emitted.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"PrincipalRunFinder.Outcome: {DescribeException(exception)}");
        }

        try
        {
            ValidatePrincipalPreviewOwner(plugin, componentTypes);
            Console.WriteLine(
                "PASS  Preview ownership: Pattern is the ONLY component holding "
                + "a principal-line preview, and the Result-side helper that "
                + "fed the others is gone. Nine components painted the same "
                + "red bars, and with a solver's preview underneath each bar "
                + "drew twice; one owner, one drawing.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Principal preview owner: {DescribeException(exception)}");
        }

        try
        {
            ValidateRegisteredMappingWins(plugin);
            Console.WriteLine(
                "PASS  ParameterIdentity.Restore: a mapping the plugin REGISTERED "
                + "wins over the archive, so Pattern's P re-flattens in every "
                + "definition saved before it flattened; a port registered with "
                + "no mapping keeps the graft the author set by hand, which the "
                + "first fix would have wiped on every reopen.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ParameterIdentity registered mapping: "
                + $"{DescribeException(exception)}");
        }

        try
        {
            ValidateColumnPlacement(plugin);
            Console.WriteLine(
                "PASS  ColumnPlacement: nine notches at Branching 2 group into a "
                + "centre single and four mirrored pairs with mirrored mains, "
                + "eight at Branching 3 into two triples and a single at each "
                + "anchor end; the fork lies on the foot-to-main segment at "
                + "65% height with trunk and main branch collinear; a shallow "
                + "arch asked for one central foot REFUSES it on lean and "
                + "records asked 1, placed 0; a symmetric arch puts its one "
                + "foot on the span centre within a hundredth of the span; "
                + "mid-bar anchors give half-spans and no head; two bars "
                + "ending on an anchor-free rim get one ring tree at their "
                + "tangents' plan intersection; a crossing node is held once; "
                + "at Branching 3 a branch below the fork still leaves lower "
                + "end first and no held head becomes a foot in mid-air; "
                + "CountCollisions refuses two members at half the clearance, "
                + "passes them at twice, and refuses a member that rises "
                + "above the nearest net vertex; Auto places Ground 1 where "
                + "1 and 0 are both feasible and 1 is the shorter load "
                + "path.");
        }
        catch (Exception exception)
        {
            failures.Add($"ColumnPlacement: {DescribeException(exception)}");
        }

        try
        {
            ValidateStiffnessSeparation(plugin);
            Console.WriteLine(
                "PASS  EI separation: bar sag scales exactly as one over EI, "
                + "which is what lets Monitor's one number turn a bending "
                + "shape into millimetres; lean from vertical is measured "
                + "against hand-computed angles.");
        }
        catch (Exception exception)
        {
            failures.Add($"EI separation: {DescribeException(exception)}");
        }

        try
        {
            ValidateMouldContract(plugin);
            Console.WriteLine(
                "PASS  Mould contract: one block on the Result carries the "
                + "built columns and one live frame; counts that must agree "
                + "are refused when they do not, the block survives the JSON "
                + "round trip every Goo boundary makes, and a Result without "
                + "it serialises with no mould key at all.");
        }
        catch (Exception exception)
        {
            failures.Add($"Mould contract: {DescribeException(exception)}");
        }

        try
        {
            ValidateDiagnosticsAppend(plugin);
            Console.WriteLine(
                "PASS  Diagnostics append: native entries land after the "
                + "worker's and leave them untouched, a source replaces its "
                + "own earlier entries instead of piling up, every entry "
                + "validates, and a non-finite value is dropped rather than "
                + "written.");
        }
        catch (Exception exception)
        {
            failures.Add($"Diagnostics append: {DescribeException(exception)}");
        }

        try
        {
            ValidateColumnsBlock(plugin);
            Console.WriteLine(
                "PASS  Columns block: bare lines become a block whose force "
                + "stays aligned through welding, whose heads name the net "
                + "vertex under them, and whose trees are the members on "
                + "each foot; read back it is the tree Animate walks.");
        }
        catch (Exception exception)
        {
            failures.Add($"Columns block: {DescribeException(exception)}");
        }

        try
        {
            ValidateDeconstructColumnTrees(plugin);
            Console.WriteLine(
                "PASS  Deconstruct column trees: one branch per tree, every "
                + "member lower end to upper end, heads and feet per tree, and "
                + "an absent block gives empty trees rather than an error.");
        }
        catch (Exception exception)
        {
            failures.Add($"Deconstruct column trees: {DescribeException(exception)}");
        }

        try
        {
            ValidateDiagnoseRules(plugin);
            Console.WriteLine(
                "PASS  Diagnose rules: the cross-checks no single component "
                + "can make (no principal runs under Columns, a frame with no "
                + "columns, every anchor isolated, more than half the net "
                + "wanting to be pushed) fire on Results built to trigger "
                + "them and stay silent on a clean one; Render prints the "
                + "worker report last and names the components that have not "
                + "run.");
        }
        catch (Exception exception)
        {
            failures.Add($"Diagnose rules: {DescribeException(exception)}");
        }

        try
        {
            ValidateOutputGrouping(plugin);
            Console.WriteLine(
                "PASS  Output grouping: the anchors of a vault come back as "
                + "SEPARATE STRIPS rather than one merged list, each walked "
                + "end to end instead of sorted by node index, and a closed "
                + "loop comes back walked round. An edge supplied twice, which "
                + "is what the union of the plan and the solved net hands over, "
                + "still leaves the strip walked end to end. A member cutting a "
                + "corner between two notches of one bar is infill, not part of "
                + "that bar. This is what the new tree outputs branch by.");
        }
        catch (Exception exception)
        {
            failures.Add($"Output grouping: {DescribeException(exception)}");
        }

        try
        {
            ValidatePerimeterFromFaces(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.PerimeterFromFaces: an edge used by exactly "
                + "one face is a boundary edge, so a 2x2 grid of quads hands "
                + "back its eight rim nodes and never the centre. This is what "
                + "an FD Result's boundary comes from, since it carries no "
                + "thrust mesh to read naked edges off; with no faces at all it "
                + "returns nothing, which is the caller's cue to say the "
                + "perimeter is an estimate.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"MouldGeometry.PerimeterFromFaces: {DescribeException(exception)}");
        }

        try
        {
            ValidatePhases(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.Phases: reel 0 to 30 brings the sag to Pre-Sag "
                + "with the net still on the ground, raise 30 to 60 lifts it, "
                + "finish 60 to 90 reels the rest, hold 90 to 100 moves nothing, "
                + "at Pre-Sag 0, 0.4 and 1; sag and lift are continuous across "
                + "every boundary to 1e-9 and never decrease anywhere along the "
                + "timeline.");
        }
        catch (Exception exception)
        {
            failures.Add($"MouldGeometry.Phases: {DescribeException(exception)}");
        }

        try
        {
            ValidateLiveColumnNodes(plugin);
            Console.WriteLine(
                "PASS  MouldGeometry.LiveColumnNodes: with the net at its solved "
                + "shape every column node is where it was built; with the net "
                + "flat on the ground and drawn in every node lies on the ground "
                + "and the fork sits at its built fraction along the rail; "
                + "halfway up the fork keeps its fraction and trunk, fork and "
                + "main head stay collinear. The fraction is measured, not "
                + "assumed, the main branch is the collinear one and not the "
                + "first listed, and heads are found by HeadNode, which is "
                + "permuted here so plan matching would land them elsewhere.");
        }
        catch (Exception exception)
        {
            failures.Add($"MouldGeometry.LiveColumnNodes: {DescribeException(exception)}");
        }

        try
        {
            ValidateMonitorMath(plugin);
            Console.WriteLine(
                "PASS  MonitorMath: an anchor's reaction splits along its "
                + "tensioner axis and across it, signed and against an axis "
                + "that does not arrive unit, the axis is the mean of the "
                + "cables leaving it, the deviation statistics are the RMS, the "
                + "worst and the 95th percentile of the ABSOLUTE values of a "
                + "hand-built field and zero on an empty one, and the "
                + "unstrained length divides by one plus force over EA except "
                + "where that denominator collapses or the EA is not a "
                + "stiffness. A Result's force reaches the newtons EA, EI and "
                + "the capacities are wired in through one factor, 1 for N and "
                + "1000 for kN and null for a unit it does not know, so 0.1 kN "
                + "against EA 1000 cuts to the same 2/1.1 as 100 N.");
        }
        catch (Exception exception)
        {
            failures.Add($"MonitorMath: {DescribeException(exception)}");
        }

        try
        {
            ValidateResultTablesOrder(plugin);
            Console.WriteLine(
                "PASS  ResultTables order: the one table Deconstruct's geometry "
                + "and Monitor's numbers are both branched from hands back the "
                + "members in edge order with their ends, forces and ids, no "
                + "force density or horizontal force where an FD Result carries "
                + "none, the support ids as the Result lists them, each "
                + "reaction at the node it acts on, and every node's residual "
                + "on its own node with a zero where the Result carries none. "
                + "On a TNA Result whose state ids and equilibrium edge ids "
                + "disagree the rows come back in ID order with the ends of the "
                + "edge each state names, a support this net does not have is "
                + "dropped, and a zero reaction is not a reaction.");
        }
        catch (Exception exception)
        {
            failures.Add($"ResultTables order: {DescribeException(exception)}");
        }

        try
        {
            ValidateParameterMismatch(plugin);
            Console.WriteLine(
                "PASS  ParameterIdentity.Mismatch: a definition saved against a "
                + "component's older ports is told they moved, naming both what "
                + "was archived and what is registered, and one saved against "
                + "the current ports is told nothing; Export's own move, seven "
                + "inputs and two outputs against nine and six, is the case "
                + "measured beside Deconstruct's.");
        }
        catch (Exception exception)
        {
            failures.Add($"ParameterIdentity.Mismatch: {DescribeException(exception)}");
        }

        try
        {
            ValidateExportPlan(plugin);
            Console.WriteLine(
                "PASS  ExportPlan: contract and compas always, tessellation "
                + "with cells, columns with a block, in that order; and a "
                + "study Name is ONE path segment, so a separator, a colon "
                + "or a dot-dot is refused before it can write the set "
                + "outside the folder the author chose.");
        }
        catch (Exception exception)
        {
            failures.Add($"ExportPlan: {DescribeException(exception)}");
        }

        try
        {
            ValidateColumnsMesh(plugin);
            Console.WriteLine(
                "PASS  ColumnsMesh: one member is a closed prism of six "
                + "quads and eight cap triangles at the radius asked, a "
                + "zero-length member is nothing and is absent from the "
                + "members list too, two members index cleanly, a DIAGONAL "
                + "member's caps are perpendicular to the member and not to "
                + "world Z, and the radius the document declares is the one "
                + "the mesh was built at.");
        }
        catch (Exception exception)
        {
            failures.Add($"ColumnsMesh: {DescribeException(exception)}");
        }

        try
        {
            ValidateLiveUploader(plugin);
            Console.WriteLine(
                "PASS  LiveUploader: the retry schedule is 2, 4, 8 seconds "
                + "then deferred, the routes are the studio's, a 2xx is "
                + "stored, a 409 retries until the schedule runs out, "
                + "anything else is refused, and the set key reads the "
                + "Name, the Studio and every kind EXCEPT the compas "
                + "document's own bytes, whose fresh uuid per serialisation "
                + "would stop the key ever repeating; the compas kind's "
                + "presence still counts. The study name is escaped into "
                + "both routes, and a deferred kind names the run the "
                + "studio is busy with when the 409 body carries one.");
        }
        catch (Exception exception)
        {
            failures.Add($"LiveUploader: {DescribeException(exception)}");
        }

        try
        {
            ValidateExportWriteFolder(plugin);
            Console.WriteLine(
                "PASS  ExportComponent.TryResolveWriteFolder: an "
                + "extensionless Path is the folder to write into even "
                + "before it exists, a Path with an extension gives its "
                + "own directory, and a Path that is not rooted, a bare "
                + "name or a relative path with directories of its own, "
                + "is refused rather than written to whatever the "
                + "process's working directory happens to be.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ExportComponent.TryResolveWriteFolder: "
                + $"{DescribeException(exception)}");
        }

        if (failures.Count == 0)
        {
            Console.WriteLine(
                "Native component smoke test passed; Rhino was not launched.");
            return 0;
        }

        Console.Error.WriteLine(
            $"ERROR: {failures.Count} native component validation " +
            $"{(failures.Count == 1 ? "failure" : "failures")}:");
        foreach (string failure in failures)
            Console.Error.WriteLine($"  - {failure}");
        return 5;
    }

    private static Assembly LoadAssembly(string path)
    {
        string fullPath = Path.GetFullPath(path);
        AssemblyName requested = AssemblyName.GetAssemblyName(fullPath);
        Assembly? loaded = AssemblyLoadContext.Default.Assemblies.FirstOrDefault(
            assembly => AssemblyName.ReferenceMatchesDefinition(
                assembly.GetName(),
                requested));
        return loaded
            ?? AssemblyLoadContext.Default.LoadFromAssemblyPath(fullPath);
    }

    private static Assembly? ResolveAssembly(
        AssemblyName assemblyName,
        IEnumerable<string> probingDirectories)
    {
        string simpleName = assemblyName.Name ?? string.Empty;
        if (string.IsNullOrWhiteSpace(simpleName))
            return null;

        lock (ResolverLock)
        {
            if (!Resolving.Add(simpleName))
                return null;
        }

        try
        {
            Assembly? loaded =
                AssemblyLoadContext.Default.Assemblies.FirstOrDefault(
                    assembly => AssemblyName.ReferenceMatchesDefinition(
                        assembly.GetName(),
                        assemblyName));
            if (loaded is not null)
                return loaded;

            foreach (string directory in probingDirectories)
            {
                foreach (string extension in new[] { ".dll", ".gha" })
                {
                    string candidate =
                        Path.Combine(directory, simpleName + extension);
                    if (!File.Exists(candidate))
                        continue;
                    try
                    {
                        return AssemblyLoadContext.Default
                            .LoadFromAssemblyPath(candidate);
                    }
                    catch (FileLoadException)
                    {
                        // A candidate with the same filename may have a
                        // different identity; continue to the next location.
                    }
                    catch (BadImageFormatException)
                    {
                        // Ignore native or incompatible files in Rhino's
                        // probing directories.
                    }
                }
            }

            return null;
        }
        finally
        {
            lock (ResolverLock)
                Resolving.Remove(simpleName);
        }
    }

    private static IEnumerable<Type> GetLoadableTypes(Assembly assembly)
    {
        try
        {
            return assembly.GetTypes();
        }
        catch (ReflectionTypeLoadException exception)
        {
            string details = string.Join(
                Environment.NewLine,
                exception.LoaderExceptions
                    .Where(item => item is not null)
                    .Select(item => $"  - {DescribeException(item!)}"));
            throw new InvalidOperationException(
                "One or more plugin types could not be loaded:" +
                Environment.NewLine +
                details,
                exception);
        }
    }

    private static bool IsConcretePublicGrasshopperComponent(Type type)
    {
        return type.IsClass
            && !type.IsAbstract
            && type.IsVisible
            && EnumerateBaseTypes(type)
                .Any(baseType =>
                    string.Equals(
                        baseType.FullName,
                        GrasshopperComponentBase,
                        StringComparison.Ordinal));
    }

    private static bool IsConcretePublicPersistentParameter(Type type)
    {
        return type.IsClass
            && !type.IsAbstract
            && type.IsVisible
            && EnumerateBaseTypes(type)
                .Any(baseType =>
                    baseType.IsGenericType &&
                    string.Equals(
                        baseType.GetGenericTypeDefinition().FullName,
                        GrasshopperPersistentParamBase,
                        StringComparison.Ordinal));
    }

    private static Type? FindRhinoCodeBase(Type componentType)
    {
        return EnumerateBaseTypes(componentType)
            .FirstOrDefault(baseType =>
            {
                string namespaceName = baseType.Namespace ?? string.Empty;
                string fullName = baseType.FullName ?? string.Empty;
                string assemblyName =
                    baseType.Assembly.GetName().Name ?? string.Empty;
                return namespaceName.StartsWith(
                           RhinoCodeNamespace,
                           StringComparison.OrdinalIgnoreCase)
                    || fullName.Contains(
                        RhinoCodeNamespace,
                        StringComparison.OrdinalIgnoreCase)
                    || assemblyName.Contains(
                        RhinoCodeNamespace,
                        StringComparison.OrdinalIgnoreCase);
            });
    }

    private static IEnumerable<Type> EnumerateBaseTypes(Type type)
    {
        for (Type? current = type.BaseType;
             current is not null;
             current = current.BaseType)
        {
            yield return current;
        }
    }

    private static string ReadDisplayName(object instance, Type componentType)
    {
        try
        {
            object? value = componentType.GetProperty("Name")?.GetValue(instance);
            if (value is string name && !string.IsNullOrWhiteSpace(name))
                return name;
        }
        catch (TargetInvocationException)
        {
            // Name is diagnostic sugar; constructor validation has succeeded.
        }

        return componentType.Name;
    }

    private static void ValidateFlattenedInputs(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!FlattenedInputs.TryGetValue(typeName, out int[]? expected))
            return;

        object? parameters = componentType
            .GetProperty("Params")
            ?.GetValue(instance);
        object? inputs = parameters?
            .GetType()
            .GetProperty("Input")
            ?.GetValue(parameters);
        if (inputs is not IList list)
            throw new InvalidOperationException(
                "Could not inspect component input parameters.");

        foreach (int index in expected)
        {
            object parameter = list[index]
                ?? throw new InvalidOperationException(
                    $"Input {index} is null.");
            string mapping = parameter
                .GetType()
                .GetProperty("DataMapping")
                ?.GetValue(parameter)
                ?.ToString()
                ?? string.Empty;
            if (!string.Equals(
                    mapping,
                    "Flatten",
                    StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    $"Input {index} must flatten bundle collection trees; " +
                    $"mapping was '{mapping}'.");
            }
        }
    }

    private static void ValidatePreviewCapability(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!RequiredPreviewComponents.Contains(typeName))
            return;

        object? value = componentType
            .GetProperty("IsPreviewCapable")
            ?.GetValue(instance);
        if (value is not true)
        {
            throw new InvalidOperationException(
                "Graphic-statics display components must explicitly remain " +
                "viewport-preview-capable even when their primary input or " +
                "output is custom Goo.");
        }
    }

    private static void ValidateNativePreviewVisibilityGuard(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!NativeVisibilityGuardComponents.Contains(typeName))
            return;

        Type? previewBase = componentType.BaseType;
        if (!string.Equals(
                previewBase?.FullName,
                "Ananke.COMPAS.Native.Components.NativePreviewComponentBase",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Custom diagram preview components must derive from the " +
                "shared native visibility guard so Grasshopper's Preview " +
                "toggle controls all renderer-owned geometry.");
        }

        PropertyInfo hiddenProperty = componentType.GetProperty("Hidden")
            ?? throw new InvalidOperationException(
                "Preview component does not expose Grasshopper's Hidden state.");
        if (!hiddenProperty.CanRead || !hiddenProperty.CanWrite)
        {
            throw new InvalidOperationException(
                "Preview component Hidden state must remain readable and " +
                "writable by Grasshopper.");
        }

        hiddenProperty.SetValue(instance, true);
        if (hiddenProperty.GetValue(instance) is not true)
        {
            throw new InvalidOperationException(
                "Preview component did not retain Grasshopper's hidden state.");
        }
        hiddenProperty.SetValue(instance, false);
    }

    private static void ValidateVisualiseContract(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!VisualiseContracts.TryGetValue(
                typeName,
                out (string[] Inputs, string[] Outputs) contract))
        {
            return;
        }

        object parameters = componentType
            .GetProperty("Params")
            ?.GetValue(instance)
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} parameters.");
        IList inputs = parameters
            .GetType()
            .GetProperty("Input")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} inputs.");
        IList outputs = parameters
            .GetType()
            .GetProperty("Output")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} outputs.");
        ValidateParameterNames(
            inputs,
            contract.Inputs,
            componentType.Name,
            "input");
        ValidateParameterNames(
            outputs,
            contract.Outputs,
            componentType.Name,
            "output");
    }

    /// <summary>
    /// Spine components (Pattern, Supports, and later stages on the same
    /// wire) key their ports on the type nickname, not a descriptive word,
    /// so a wire is self-describing. This asserts the component's own
    /// Name/NickName, its tab (SubCategory), and every port's NickName
    /// against the redesign's fixed surface.
    /// </summary>
    private static void ValidateSpineComponentContract(
        object instance,
        Type componentType)
    {
        string typeName = componentType.FullName ?? componentType.Name;
        if (!SpineComponentContracts.TryGetValue(
                typeName,
                out (string Name, string NickName, string Tab,
                    string[] InputNickNames, string[] OutputNickNames)
                    contract))
        {
            return;
        }

        string actualName =
            componentType.GetProperty("Name")?.GetValue(instance) as string
            ?? string.Empty;
        if (!string.Equals(actualName, contract.Name, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{componentType.Name} Name must be '{contract.Name}'; " +
                $"received '{actualName}'.");
        }

        string actualNickName =
            componentType.GetProperty("NickName")?.GetValue(instance) as string
            ?? string.Empty;
        if (!string.Equals(
                actualNickName,
                contract.NickName,
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{componentType.Name} NickName must be " +
                $"'{contract.NickName}'; received '{actualNickName}'.");
        }

        string actualTab =
            componentType.GetProperty("SubCategory")?.GetValue(instance)
                as string
            ?? string.Empty;
        if (!string.Equals(actualTab, contract.Tab, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{componentType.Name} tab must be '{contract.Tab}'; " +
                $"received '{actualTab}'.");
        }

        object parameters = componentType
            .GetProperty("Params")
            ?.GetValue(instance)
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} parameters.");
        IList inputs = parameters
            .GetType()
            .GetProperty("Input")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} inputs.");
        IList outputs = parameters
            .GetType()
            .GetProperty("Output")
            ?.GetValue(parameters) as IList
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} outputs.");
        ValidateParameterNickNames(
            inputs,
            contract.InputNickNames,
            componentType.Name,
            "input");
        ValidateParameterNickNames(
            outputs,
            contract.OutputNickNames,
            componentType.Name,
            "output");
    }

    private static void ValidateParameterNickNames(
        IList parameters,
        IReadOnlyList<string> expected,
        string owner,
        string label)
    {
        if (parameters.Count != expected.Count)
        {
            throw new InvalidOperationException(
                $"{owner} expected {expected.Count} {label}s, " +
                $"found {parameters.Count}.");
        }

        for (int index = 0; index < expected.Count; index++)
        {
            object parameter = parameters[index]
                ?? throw new InvalidOperationException(
                    $"{owner} {label} {index} is null.");
            string actual = parameter
                .GetType()
                .GetProperty("NickName")
                ?.GetValue(parameter)
                ?.ToString()
                ?? string.Empty;
            if (!string.Equals(
                    actual,
                    expected[index],
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{owner} {label} {index} nickname must be " +
                    $"'{expected[index]}'; received '{actual}'.");
            }
        }
    }

    private static void ValidateParameterNames(
        IList parameters,
        IReadOnlyList<string> expected,
        string owner,
        string label)
    {
        if (parameters.Count != expected.Count)
        {
            throw new InvalidOperationException(
                $"{owner} expected {expected.Count} {label}s, " +
                $"found {parameters.Count}.");
        }

        for (int index = 0; index < expected.Count; index++)
        {
            object parameter = parameters[index]
                ?? throw new InvalidOperationException(
                    $"{owner} {label} {index} is null.");
            string actual = parameter
                .GetType()
                .GetProperty("Name")
                ?.GetValue(parameter)
                ?.ToString()
                ?? string.Empty;
            if (!string.Equals(
                    actual,
                    expected[index],
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{owner} {label} {index} must be " +
                    $"'{expected[index]}'; received '{actual}'.");
            }
        }
    }

    private static void ValidateIcon(object instance, Type componentType)
    {
        PropertyInfo? iconProperty = null;
        for (Type? current = componentType;
             current is not null && iconProperty is null;
             current = current.BaseType)
        {
            iconProperty = current.GetProperty(
                "Icon",
                BindingFlags.Instance |
                BindingFlags.NonPublic |
                BindingFlags.DeclaredOnly);
        }
        object icon = iconProperty?.GetValue(instance)
            ?? throw new InvalidOperationException(
                "Component icon is missing.");
        int width = Convert.ToInt32(
            icon.GetType().GetProperty("Width")?.GetValue(icon));
        int height = Convert.ToInt32(
            icon.GetType().GetProperty("Height")?.GetValue(icon));
        if (width != 24 || height != 24)
        {
            throw new InvalidOperationException(
                $"Component icon must be 24x24; received {width}x{height}.");
        }
    }

    private static void RecordDocumentGuid(
        object instance,
        Type objectType,
        IDictionary<Guid, string> documentGuids,
        ICollection<string> failures)
    {
        object? value = objectType
            .GetProperty("ComponentGuid")
            ?.GetValue(instance);
        if (value is not Guid guid || guid == Guid.Empty)
        {
            failures.Add(
                $"{objectType.FullName}: ComponentGuid is missing or empty.");
            return;
        }
        string name = objectType.FullName ?? objectType.Name;
        if (documentGuids.TryGetValue(guid, out string? existing))
        {
            failures.Add(
                $"{name}: ComponentGuid {guid} duplicates {existing}.");
            return;
        }
        documentGuids.Add(guid, name);
    }

    /// <summary>
    /// Constructs the unified <c>ResultDto</c> directly from the loaded
    /// plugin assembly via reflection (this harness has no compile-time
    /// reference to <c>Ananke.COMPAS.Native.Contracts</c>) and exercises
    /// its <c>Validate()</c> rules: a valid TNA result (with reciprocal
    /// graphs), a valid FD result (without them), and an invalid TNA
    /// result missing its graphs.
    /// </summary>
    private static void ValidateResultContract(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");

        object validTna = CreateResultDto(
            resultType,
            solver: "tna",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: CreateInstance(graphType),
            forceGraph: CreateInstance(graphType));
        RequireNoValidationErrors(validTna, "Valid TNA ResultDto");

        object validFd = CreateResultDto(
            resultType,
            solver: "fd",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: null,
            forceGraph: null);
        RequireNoValidationErrors(validFd, "Valid FD ResultDto");

        object invalidTna = CreateResultDto(
            resultType,
            solver: "tna",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: null,
            forceGraph: null);
        RequireValidationErrors(
            invalidTna,
            "Invalid TNA ResultDto without reciprocal graphs");
    }

    /// <summary>
    /// <c>ResultDto.RawWire</c> is <c>[JsonIgnore]</c>, so the shared
    /// <c>ContractJson.DeepClone</c> round trip every other snapshot
    /// boundary relies on would silently drop it. <c>ResultGoo</c>
    /// overrides <c>ContractGoo{TContract}.Snapshot</c> to reattach it;
    /// this exercises the exact paths the whole-branch review flagged as
    /// broken: the public constructor (what
    /// <c>SolverComponents.cs</c>'s <c>new ResultGoo(result.Result)</c>
    /// calls on every live solve) and <c>Duplicate()</c> (what a
    /// Grasshopper wire fan-out calls) must both preserve RawWire, while
    /// Contract-mode serialisation (<c>ContractJson.Serialize</c>) must
    /// still exclude it from the persisted contract.
    /// </summary>
    private static void ValidateResultGooRawWireSnapshot(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type resultGooType = RequireContractType(plugin, "ResultGoo");
        const string rawWire = "{\"worker\":\"raw\"}";

        object result = CreateResultDto(
            resultType,
            solver: "fd",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: null,
            forceGraph: null);
        SetContractProperty(result, resultType, "RawWire", rawWire);

        object goo = Activator.CreateInstance(resultGooType, result)
            ?? throw new InvalidOperationException(
                $"Could not construct {resultGooType.FullName}.");
        RequireRawWire(goo, resultType, rawWire, "Constructed ResultGoo");

        MethodInfo duplicateMethod = resultGooType.GetMethod("Duplicate")
            ?? throw new InvalidOperationException(
                "ResultGoo.Duplicate() was not found.");
        object duplicated = duplicateMethod.Invoke(goo, null)
            ?? throw new InvalidOperationException(
                "ResultGoo.Duplicate() returned null.");
        RequireRawWire(duplicated, resultType, rawWire, "Duplicated ResultGoo");

        Type contractJsonType = RequireContractType(plugin, "ContractJson");
        MethodInfo serializeMethod = contractJsonType.GetMethod(
            "Serialize",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ContractJson.Serialize was not found.");
        string serialized =
            serializeMethod.MakeGenericMethod(resultType)
                .Invoke(null, new object[] { result }) as string
            ?? throw new InvalidOperationException(
                "ContractJson.Serialize returned an unexpected type.");
        if (serialized.Contains("rawWire", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                "Contract-mode serialisation must exclude RawWire, but the " +
                "serialised ResultDto contains it.");
        }
    }

    private static void RequireRawWire(
        object goo,
        Type resultType,
        string expected,
        string label)
    {
        PropertyInfo valueProperty = goo.GetType().GetProperty("Value")
            ?? throw new InvalidOperationException(
                $"{goo.GetType().FullName} does not expose Value.");
        object? value = valueProperty.GetValue(goo);
        if (value is null || !resultType.IsInstanceOfType(value))
        {
            throw new InvalidOperationException(
                $"{label} lost its ResultDto payload.");
        }

        string? rawWire =
            resultType.GetProperty("RawWire")?.GetValue(value) as string;
        if (!string.Equals(rawWire, expected, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"{label} lost RawWire; expected '{expected}', found " +
                $"'{rawWire ?? "<null>"}'.");
        }
    }

    private static object CreateResultDto(
        Type resultType,
        string solver,
        object equilibrium,
        object? formGraph,
        object? forceGraph)
    {
        object instance = CreateInstance(resultType);
        SetContractProperty(instance, resultType, "Solver", solver);
        SetContractProperty(instance, resultType, "Equilibrium", equilibrium);
        SetContractProperty(instance, resultType, "FormGraph", formGraph);
        SetContractProperty(instance, resultType, "ForceGraph", forceGraph);
        return instance;
    }

    private static object CreateInstance(Type type)
    {
        return Activator.CreateInstance(type)
            ?? throw new InvalidOperationException(
                $"Could not construct {type.FullName}.");
    }

    private static void SetContractProperty(
        object instance,
        Type type,
        string propertyName,
        object? value)
    {
        PropertyInfo property = type.GetProperty(propertyName)
            ?? throw new InvalidOperationException(
                $"{type.FullName} does not expose property '{propertyName}'.");
        property.SetValue(instance, value);
    }

    private static void RequireNoValidationErrors(object instance, string label)
    {
        IReadOnlyList<string> errors = InvokeValidate(instance);
        if (errors.Count > 0)
        {
            throw new InvalidOperationException(
                $"{label} failed validation: {string.Join(" ", errors)}");
        }
    }

    private static void RequireValidationErrors(object instance, string label)
    {
        IReadOnlyList<string> errors = InvokeValidate(instance);
        if (errors.Count == 0)
        {
            throw new InvalidOperationException(
                $"{label} unexpectedly passed validation.");
        }
    }

    private static IReadOnlyList<string> InvokeValidate(object instance)
    {
        MethodInfo validateMethod = instance.GetType().GetMethod("Validate")
            ?? throw new InvalidOperationException(
                $"{instance.GetType().FullName} does not expose Validate().");
        object? result = validateMethod.Invoke(instance, null);
        return result as IReadOnlyList<string>
            ?? throw new InvalidOperationException(
                "Validate() returned an unexpected type.");
    }

    /// <summary>
    /// The Mould block: one nullable block on the Result that carries the
    /// built columns and one live frame. Validation is measured on the
    /// counts that must agree, and the round trip is measured because every
    /// Goo boundary deep-clones through JSON, so a block that does not
    /// survive serialisation does not exist.
    /// </summary>
    private static void ValidateMouldContract(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type frameType = RequireContractType(plugin, "MouldFrameDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Points(params object[] items)
        {
            Array array = Array.CreateInstance(point, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        Array Edges(params (int U, int V)[] pairs)
        {
            Array array = Array.CreateInstance(edge, pairs.Length);
            for (int i = 0; i < pairs.Length; i++)
                array.SetValue(Activator.CreateInstance(edge, pairs[i].U, pairs[i].V), i);
            return array;
        }
        object Equilibrium()
        {
            object eq = CreateInstance(equilibriumType);
            SetContractProperty(eq, equilibriumType, "Vertices",
                Points(P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(3, 0, 0)));
            return eq;
        }
        object Columns(double[] force, int[] headNode)
        {
            object c = CreateInstance(columnsType);
            SetContractProperty(c, columnsType, "Nodes",
                Points(P(0, 0, 0), P(0, 0, 5), P(3, 0, 0), P(3, 0, 6)));
            SetContractProperty(c, columnsType, "Members", Edges((0, 1), (2, 3)));
            SetContractProperty(c, columnsType, "MemberForce", force);
            SetContractProperty(c, columnsType, "Trees",
                new int[][] { new[] { 0 }, new[] { 1 } });
            SetContractProperty(c, columnsType, "Heads", new[] { 1, 3 });
            SetContractProperty(c, columnsType, "Feet", new[] { 0, 2 });
            SetContractProperty(c, columnsType, "HeadNode", headNode);
            SetContractProperty(c, columnsType, "Branching", 1);
            SetContractProperty(c, columnsType, "ForkFraction", 0.65);
            return c;
        }
        object Frame(int vertexCount, Array? columnNodes)
        {
            object f = CreateInstance(frameType);
            SetContractProperty(f, frameType, "Time", 50.0);
            SetContractProperty(f, frameType, "Phase", "raise");
            SetContractProperty(f, frameType, "Lift", 0.5);
            SetContractProperty(f, frameType, "Sag", 0.5);
            SetContractProperty(f, frameType, "Vertices",
                Points(Enumerable.Range(0, vertexCount)
                    .Select(i => P(i, 0, 1)).ToArray()));
            SetContractProperty(f, frameType, "ColumnNodes", columnNodes);
            return f;
        }
        object Mould(object? columns, object? frame)
        {
            object m = CreateInstance(mouldType);
            SetContractProperty(m, mouldType, "Ground", 0.0);
            SetContractProperty(m, mouldType, "Columns", columns);
            SetContractProperty(m, mouldType, "Frame", frame);
            return m;
        }
        object Result(object mould)
        {
            object r = CreateResultDto(resultType, "fd", Equilibrium(), null, null);
            SetContractProperty(r, resultType, "Mould", mould);
            return r;
        }

        // Good: two posts, one frame with live column nodes for all four.
        object good = Result(Mould(
            Columns(new[] { 100.0, 200.0 }, new[] { 1, 2 }),
            Frame(4, Points(P(0, 0, 0), P(0, 0, 4), P(3, 0, 0), P(3, 0, 5)))));
        RequireNoValidationErrors(good, "Result with a full Mould block");

        RequireValidationErrors(
            Result(Mould(Columns(new[] { 100.0 }, new[] { 1, 2 }), null)),
            "MemberForce one short of Members");
        RequireValidationErrors(
            Result(Mould(Columns(new[] { 100.0, 200.0 }, new[] { 1, 99 }), null)),
            "HeadNode outside the net");
        RequireValidationErrors(
            Result(Mould(null, Frame(3, null))),
            "Frame with the wrong vertex count");
        RequireValidationErrors(
            Result(Mould(null, Frame(4, Points(P(0, 0, 0))))),
            "ColumnNodes present with Columns absent");

        // Round trip through the same serialiser every Goo boundary uses.
        Type json = RequireContractType(plugin, "ContractJson");
        MethodInfo serialize = json.GetMethod("Serialize")!.MakeGenericMethod(resultType);
        MethodInfo deserialize = json.GetMethod("Deserialize")!.MakeGenericMethod(resultType);
        string text = (string)serialize.Invoke(null, new[] { good })!;
        if (!text.Contains("\"mould\"", StringComparison.Ordinal) ||
            !text.Contains("\"headNode\"", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A Result with a Mould block must serialise its mould and headNode keys.");
        }
        object back = deserialize.Invoke(null, new object[] { text })!;
        RequireNoValidationErrors(back, "Round-tripped Result with Mould");
        object mouldBack = resultType.GetProperty("Mould")!.GetValue(back)
            ?? throw new InvalidOperationException("Mould was lost in the round trip.");
        object columnsBack = mouldType.GetProperty("Columns")!.GetValue(mouldBack)
            ?? throw new InvalidOperationException("Mould.Columns was lost in the round trip.");
        int members = ((ICollection)columnsType.GetProperty("Members")!.GetValue(columnsBack)!).Count;
        if (members != 2)
            throw new InvalidOperationException($"Two members went in and {members} came back.");
        int trees = ((ICollection)columnsType.GetProperty("Trees")!.GetValue(columnsBack)!).Count;
        int[] headNode = ((IEnumerable)columnsType.GetProperty("HeadNode")!.GetValue(columnsBack)!).Cast<int>().ToArray();
        object frameBack = mouldType.GetProperty("Frame")!.GetValue(mouldBack)
            ?? throw new InvalidOperationException("Mould.Frame was lost in the round trip.");
        double time = (double)frameType.GetProperty("Time")!.GetValue(frameBack)!;
        int columnNodes = ((ICollection)frameType.GetProperty("ColumnNodes")!.GetValue(frameBack)!).Count;
        if (trees != 2 || !headNode.SequenceEqual(new[] { 1, 2 }) || Math.Abs(time - 50.0) > 1e-12 || columnNodes != 4)
        {
            throw new InvalidOperationException(
                $"The round trip must keep every field: trees {trees}, headNode [{string.Join(",", headNode)}], time {time}, columnNodes {columnNodes}.");
        }

        // A Result without the block serialises exactly as it always did.
        string bare = (string)serialize.Invoke(
            null, new[] { CreateResultDto(resultType, "fd", Equilibrium(), null, null) })!;
        if (bare.Contains("\"mould\"", StringComparison.Ordinal))
            throw new InvalidOperationException("A Result with no Mould block must not write a mould key.");
        RequireNoValidationErrors(
            deserialize.Invoke(null, new object[] { bare })!,
            "Old-shape Result JSON with no mould key");

        // Ground -1 is Auto, which is a level asked for and so has to travel
        // in the block. Anything below it is not a level at all.
        object autoColumns = Columns(new[] { 100.0, 200.0 }, new[] { 1, 2 });
        SetContractProperty(autoColumns, columnsType, "GroundAsked", -1);
        RequireNoValidationErrors(
            Result(Mould(autoColumns, null)), "Mould block asking for Ground -1 (Auto)");

        object belowColumns = Columns(new[] { 100.0, 200.0 }, new[] { 1, 2 });
        SetContractProperty(belowColumns, columnsType, "GroundAsked", -2);
        IReadOnlyList<string> groundErrors =
            InvokeValidate(Result(Mould(belowColumns, null)));
        if (!groundErrors.Any(e => e.Contains("groundAsked", StringComparison.Ordinal)))
        {
            throw new InvalidOperationException(
                "GroundAsked -2 is below Auto and must be refused by name; got "
                + $"[{string.Join("; ", groundErrors)}].");
        }
    }

    /// <summary>
    /// Native components append diagnostics INTO the Result instead of
    /// printing a report. The worker's entries stay first and untouched, a
    /// source's own earlier entries are replaced rather than piled up, and
    /// every native entry passes DiagnosticDto.Validate, because the worker
    /// codecs throw on an invalid one and Diagnose must be able to trust the
    /// list.
    /// </summary>
    private static void ValidateDiagnosticsAppend(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type diagnosticType = RequireContractType(plugin, "DiagnosticDto");
        Type helper = RequireComponentType(plugin, "ResultDiagnostics");
        MethodInfo entry = RequirePublicStatic(helper, "Entry");
        MethodInfo replace = RequirePublicStatic(helper, "Replace");
        MethodInfo sourceOf = RequirePublicStatic(helper, "SourceOf");

        object Worker(string code)
        {
            object d = CreateInstance(diagnosticType);
            SetContractProperty(d, diagnosticType, "Code", code);
            SetContractProperty(d, diagnosticType, "Severity", "info");
            SetContractProperty(d, diagnosticType, "Message", "from the worker");
            SetContractProperty(d, diagnosticType, "Provenance",
                new Dictionary<string, string> { ["source"] = "COMPAS TNA worker" });
            return d;
        }
        object Native(string code, double? value)
        {
            return entry.Invoke(null, new object?[]
            {
                "Columns", code, "info", "measured by Columns", value, 60.0, "degrees", null,
            })!;
        }
        Array Typed(params object[] items)
        {
            Array array = Array.CreateInstance(diagnosticType, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        IReadOnlyList<object> DiagnosticsOf(object result) =>
            ((IEnumerable)resultType.GetProperty("Diagnostics")!.GetValue(result)!)
                .Cast<object>().ToList();

        object workerA = Worker("worker.a");
        object workerB = Worker("worker.b");
        object result = CreateResultDto(
            resultType, "fd", CreateInstance(equilibriumType), null, null);
        SetContractProperty(result, resultType, "Diagnostics", Typed(workerA, workerB));

        object appended = replace.Invoke(null, new object?[]
        {
            result, "Columns",
            Typed(Native("columns.lean", 12.0), Native("columns.bars", 2.0), Native("columns.force_max", 900.0)),
        })!;
        IReadOnlyList<object> all = DiagnosticsOf(appended);
        if (all.Count != 5)
            throw new InvalidOperationException($"Two worker plus three native entries is five; got {all.Count}.");
        if (!ReferenceEquals(all[0], workerA) || !ReferenceEquals(all[1], workerB))
            throw new InvalidOperationException("The worker's entries must stay first and untouched.");
        for (int i = 2; i < 5; i++)
        {
            RequireNoValidationErrors(all[i], $"native diagnostic {i}");
            string source = (string)sourceOf.Invoke(null, new[] { all[i] })!;
            if (source != "Columns")
                throw new InvalidOperationException($"Native entry {i} has source '{source}', expected 'Columns'.");
        }

        object replaced = replace.Invoke(null, new object?[]
        {
            appended, "Columns", Typed(Native("columns.lean", 15.0)),
        })!;
        if (DiagnosticsOf(replaced).Count != 3)
            throw new InvalidOperationException("Replacing a source's entries must drop its earlier ones, leaving two worker plus one.");

        object nan = Native("columns.foot_drift", double.NaN);
        if (diagnosticType.GetProperty("Value")!.GetValue(nan) is not null)
            throw new InvalidOperationException("A non-finite Value must be dropped to null, not written and refused later.");
    }

    /// <summary>
    /// The block builder: bare lines in, a block out whose members keep
    /// their force aligned even though welding drops zero-length lines,
    /// whose heads name the net vertex under them, and whose trees are the
    /// members that stand on each foot. Read back into a ColumnTree it is
    /// the same tree Animate walks today.
    /// </summary>
    private static void ValidateColumnsBlock(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo columnsBlock = RequirePublicStatic(geometry, "ColumnsBlock");
        MethodInfo treeFromBlock = RequirePublicStatic(geometry, "TreeFromBlock");
        MethodInfo treesByFoot = RequirePublicStatic(geometry, "TreesByFoot");

        Type lineList = columnsBlock.GetParameters()[0].ParameterType;
        Type line = lineList.GetGenericArguments()[0];
        Type point3d = columnsBlock.GetParameters()[2].ParameterType.GetElementType()!;

        object Pt(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        Type concreteList = typeof(List<>).MakeGenericType(line);
        object members = Activator.CreateInstance(concreteList)!;
        MethodInfo add = concreteList.GetMethod("Add")!;
        void Member(object from, object to) =>
            add.Invoke(members, new[] { Activator.CreateInstance(line, from, to) });

        // Tree A: trunk to a fork, two branches. Tree B: one post. The
        // zero-length line between the trunk and the first branch welds
        // both ends to the same node and is dropped, along with its
        // sentinel force, so a naive pass-through would misalign every
        // force after it.
        Member(Pt(0, 0, 0), Pt(0, 0, 5));
        Member(Pt(0, 0, 5), Pt(1, 0, 8));
        Member(Pt(0, 0, 5), Pt(0, 0, 5));
        Member(Pt(0, 0, 5), Pt(-1, 0, 8));
        Member(Pt(10, 0, 0), Pt(10, 0, 6));
        double[] force = { 300.0, 100.0, 999.0, 100.0, 200.0 };

        Array net = Array.CreateInstance(point3d, 4);
        net.SetValue(Pt(1, 0, 8), 0);
        net.SetValue(Pt(-1, 0, 8), 1);
        net.SetValue(Pt(10, 0, 6), 2);
        net.SetValue(Pt(5, 0, 0), 3);

        object block = columnsBlock.Invoke(null, new object?[]
        {
            members, force, net, 1.0e-6, 2, 0, 0, 0.65, 0,
        })!;
        Type blockType = block.GetType();
        int[] Ints(string name) =>
            ((IEnumerable)blockType.GetProperty(name)!.GetValue(block)!).Cast<int>().ToArray();
        double[] Doubles(string name) =>
            ((IEnumerable)blockType.GetProperty(name)!.GetValue(block)!).Cast<double>().ToArray();
        int Count(string name) =>
            ((ICollection)blockType.GetProperty(name)!.GetValue(block)!).Count;

        if (Count("Nodes") != 6 || Count("Members") != 4)
            throw new InvalidOperationException($"Six nodes and four members; got {Count("Nodes")} and {Count("Members")}.");
        if (!Doubles("MemberForce").SequenceEqual(new[] { 300.0, 100.0, 100.0, 200.0 }))
            throw new InvalidOperationException("A dropped member must take its force with it and leave the rest aligned.");
        if (!Ints("Heads").SequenceEqual(new[] { 2, 3, 5 }))
            throw new InvalidOperationException($"Heads are the nodes that are only ever an upper end: expected 2,3,5, got {string.Join(",", Ints("Heads"))}.");
        if (!Ints("Forks").SequenceEqual(new[] { 1 }))
            throw new InvalidOperationException("The one node that is both a lower and an upper end is the fork.");
        if (!Ints("Feet").SequenceEqual(new[] { 0, 4 }))
            throw new InvalidOperationException("Feet are the nodes that are only ever a lower end.");
        if (!Ints("HeadNode").SequenceEqual(new[] { 0, 1, 2 }))
            throw new InvalidOperationException($"Each head names the net vertex under it: expected 0,1,2, got {string.Join(",", Ints("HeadNode"))}.");
        var trees = ((IEnumerable)blockType.GetProperty("Trees")!.GetValue(block)!)
            .Cast<IEnumerable<int>>().Select(t => t.ToArray()).ToArray();
        if (trees.Length != 2 || !trees[0].SequenceEqual(new[] { 0, 1, 2 }) || !trees[1].SequenceEqual(new[] { 3 }))
            throw new InvalidOperationException("Two feet give two trees: members 0,1,2 stand on the first foot and member 3 on the second.");

        object tree = treeFromBlock.Invoke(null, new[] { block })!;
        Type treeType = tree.GetType();
        int nodes = ((ICollection)treeType.GetProperty("Nodes")!.GetValue(tree)!).Count;
        int notches = ((ICollection)treeType.GetProperty("Notches")!.GetValue(tree)!).Count;
        int feet = ((ICollection)treeType.GetProperty("Feet")!.GetValue(tree)!).Count;
        if (nodes != 6 || notches != 3 || feet != 2)
            throw new InvalidOperationException($"Read back, the tree has {nodes} nodes, {notches} notches, {feet} feet; expected 6, 3, 2.");
        var byFoot = ((IEnumerable)treesByFoot.Invoke(null, new[] { tree })!)
            .Cast<IEnumerable<int>>().Select(t => t.ToArray()).ToArray();
        if (byFoot.Length != 2 || byFoot[0].Length != 3 || byFoot[1].Length != 1)
            throw new InvalidOperationException("TreesByFoot on the read-back tree must give the same two groups.");

        // Auto is GroundAsked -1 and the block must carry it. The contract
        // was relaxed to accept -1 and the harness fixture accepts it, but
        // both exercised a hand-built DTO; the block builder clamped the -1
        // the component passes to 0, so no Result the production path can
        // build ever carried it and Auto was indistinguishable from Ground 0
        // downstream.
        object auto = columnsBlock.Invoke(null, new object?[]
        {
            members, force, net, 1.0e-6, 2, -1, 3, 0.65, 0,
        })!;
        Type autoType = auto.GetType();
        if ((int)autoType.GetProperty("GroundAsked")!.GetValue(auto)! != -1)
            throw new InvalidOperationException("A block built by Auto must carry GroundAsked -1, not a 0 that reads as Ground 0 asked.");
        if ((int)autoType.GetProperty("GroundPlaced")!.GetValue(auto)! != 3)
            throw new InvalidOperationException("GroundPlaced is what was built and is never negative.");
        object below = columnsBlock.Invoke(null, new object?[]
        {
            members, force, net, 1.0e-6, 2, -7, 0, 0.65, 0,
        })!;
        if ((int)below.GetType().GetProperty("GroundAsked")!.GetValue(below)! != -1)
            throw new InvalidOperationException("Anything below -1 clamps to -1, the floor the contract allows.");
    }

    /// <summary>
    /// <c>MouldGeometry.Phases</c>: the four phases the spine spec bound from
    /// the seven-questions state machine, with the split Param chose (30, 30,
    /// 30, 10). Measured at every boundary because a discontinuity in sag or
    /// lift is a visible jump on the timeline slider.
    /// </summary>
    /// <summary>
    /// <c>MouldGeometry.PerimeterFromFaces</c>: the boundary from topology
    /// rather than from a guess.
    ///
    /// An FD Result carries no faces of its own, so Animate has no thrust mesh
    /// to read naked edges off and used to fall back to node degree: keep
    /// every node joined to fewer neighbours than the middle of the net. That
    /// is not a boundary and on a coarse quad net it is not even close. A 5x5
    /// net has four corners at degree 2, twelve edge nodes at degree 3 and
    /// nine interior at degree 4, so the median is 3 and the "perimeter" comes
    /// back as the four CORNERS, each isolated from the others.
    ///
    /// The face rule has no such failure: an edge used by exactly one face is
    /// on the boundary, an edge shared by two is not. The fixture is the
    /// smallest grid that has an interior vertex to get wrong, four quads on
    /// nine nodes, and the centre node is the assertion that matters.
    /// </summary>
    private static void ValidatePerimeterFromFaces(Assembly plugin)
    {
        Type mouldGeometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry",
            throwOnError: true)!;
        MethodInfo fromFaces = RequirePublicStatic(
            mouldGeometry, "PerimeterFromFaces");

        //   6 7 8
        //   3 4 5
        //   0 1 2
        var faces = new List<IReadOnlyList<int>>
        {
            new[] { 0, 1, 4, 3 },
            new[] { 1, 2, 5, 4 },
            new[] { 3, 4, 7, 6 },
            new[] { 4, 5, 8, 7 },
        };
        var rim = (int[])fromFaces.Invoke(null, new object?[] { faces, 9 })!;
        var expectedRim = new[] { 0, 1, 2, 3, 5, 6, 7, 8 };
        if (!rim.SequenceEqual(expectedRim))
        {
            throw new InvalidOperationException(
                "The rim of a 2x2 grid of quads is its eight outer nodes: "
                + $"expected [{string.Join(",", expectedRim)}] and got "
                + $"[{string.Join(",", rim)}]. Node 4 is the centre, shared by "
                + "all four faces, so every edge touching it is used twice and "
                + "it cannot be on the boundary.");
        }

        var none = (int[])fromFaces.Invoke(
            null, new object?[] { new List<IReadOnlyList<int>>(), 9 })!;
        if (none.Length != 0)
        {
            throw new InvalidOperationException(
                "With no faces there is no boundary to read, and the empty "
                + "array is what tells the caller to fall back to the degree "
                + $"estimate and say so; got {none.Length} node(s).");
        }
    }

    private static void ValidatePhases(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo phases = RequirePublicStatic(geometry, "Phases");

        (double Sag, double Lift, string Phase) At(double time, double pre)
        {
            object result = phases.Invoke(null, new object?[] { time, pre })!;
            Type type = result.GetType();
            return (
                (double)type.GetField("Item1")!.GetValue(result)!,
                (double)type.GetField("Item2")!.GetValue(result)!,
                (string)type.GetField("Item3")!.GetValue(result)!);
        }

        void Expect(double time, double pre, string phase, double sag, double lift)
        {
            (double s, double l, string p) = At(time, pre);
            if (p != phase)
                throw new InvalidOperationException($"Time {time} at Pre-Sag {pre} is '{phase}', got '{p}'.");
            if (Math.Abs(s - sag) > 1.0e-9 || Math.Abs(l - lift) > 1.0e-9)
                throw new InvalidOperationException($"Time {time} ({phase}) at Pre-Sag {pre} should give sag {sag}, lift {lift}; got sag {s:0.####}, lift {l:0.####}.");
        }

        // Every phase boundary at THREE pre-sags, the two ends included, with
        // the expected sag computed from the table rather than written out:
        // reel runs 0 to pre, raise holds pre, finish runs pre to 1. Checking
        // 0.4 alone left a Phases that ignored its second argument passing at
        // the boundaries, since 0.4 appears in the answer either way.
        foreach (double pre in new[] { 0.0, 0.4, 1.0 })
        {
            Expect(0.0, pre, "reel", 0.0, 0.0);
            Expect(0.15, pre, "reel", pre * 0.5, 0.0);
            Expect(0.3, pre, "raise", pre, 0.0);
            Expect(0.45, pre, "raise", pre, 0.5);
            Expect(0.6, pre, "finish", pre, 1.0);
            Expect(0.75, pre, "finish", pre + ((1.0 - pre) * 0.5), 1.0);
            Expect(0.9, pre, "hold", 1.0, 1.0);
            Expect(1.0, pre, "hold", 1.0, 1.0);
        }

        // Continuity: just below each boundary matches the boundary, to 1e-9,
        // which is what the spec binds. The step back has to be SMALLER than
        // the tolerance divided by the slope, or the probe fails an exact
        // function: at 1e-9 the sag inside reel has already moved 1.33e-9, so
        // the old probe could only ever be asserted at 1e-6. At 1e-12 the gap
        // is 1.33e-12 and the spec's own tolerance holds.
        foreach (double pre in new[] { 0.0, 0.4, 1.0 })
        {
            foreach (double boundary in new[] { 0.3, 0.6, 0.9 })
            {
                (double sBelow, double lBelow, _) = At(boundary - 1.0e-12, pre);
                (double sAt, double lAt, _) = At(boundary, pre);
                if (Math.Abs(sBelow - sAt) > 1.0e-9 || Math.Abs(lBelow - lAt) > 1.0e-9)
                    throw new InvalidOperationException($"Sag or lift jumps at time {boundary} with Pre-Sag {pre}: {sBelow:0.############}/{lBelow:0.############} below, {sAt:0.############}/{lAt:0.############} at.");
            }
        }

        // MONOTONE across the whole timeline. Continuity at three boundaries
        // says nothing about what happens between them, and a build that ran
        // backwards mid-phase would reel a cable out again: neither the sag
        // nor the lift may ever decrease as Time advances.
        foreach (double pre in new[] { 0.0, 0.4, 1.0 })
        {
            double lastSag = -1.0;
            double lastLift = -1.0;
            for (int step = 0; step <= 100; step++)
            {
                double t = step / 100.0;
                (double s, double l, _) = At(t, pre);
                if (s < lastSag - 1.0e-12 || l < lastLift - 1.0e-12)
                {
                    throw new InvalidOperationException(
                        $"Sag and lift must never decrease: at Pre-Sag {pre}, time {t:0.##} gave sag {s:0.######} and lift {l:0.######} after {lastSag:0.######} and {lastLift:0.######}.");
                }
                lastSag = s;
                lastLift = l;
            }
        }
        // Out-of-range inputs clamp rather than throw.
        (double sOver, double lOver, string pOver) = At(1.5, 2.0);
        if (pOver != "hold" || Math.Abs(sOver - 1.0) > 1.0e-9 || Math.Abs(lOver - 1.0) > 1.0e-9)
            throw new InvalidOperationException("Time past 1 and Pre-Sag past 1 clamp to hold at full sag and lift.");
    }

    /// <summary>
    /// <c>MouldGeometry.LiveColumnNodes</c>: the rigid rotation. A tree's foot
    /// is where the block put it, its heads are on the live net by HeadNode,
    /// and its fork keeps the fraction it was built at along the live
    /// foot-to-main segment, so the trunk turns about its foot as one body.
    /// Two trees share one foot here, and one of them forks.
    ///
    /// The fixture is built so that each of the three rules FAILS SEPARATELY
    /// if it is ever reverted:
    ///
    ///   THE FRACTION is 0.4, not the 0.65 an earlier fixture used, so a
    ///   hard-coded constant cannot pass by matching the test's own number.
    ///
    ///   THE MAIN BRANCH is listed SECOND in Members, so <c>Above[fork]</c>
    ///   reads {B, M} and a MainBranch that took the first entry above the
    ///   fork would put the fork on the arm's segment instead of the trunk's.
    ///
    ///   THE HEADS are found by HeadNode, which is permuted to {2, 1, 0}, and
    ///   the net at time zero is DRAWN IN in plan the way a reeling net is. So
    ///   the main head's built plan position is nearest to a different live
    ///   vertex from the one HeadNode names, and a revert to plan matching
    ///   puts that head, and the fork under it, somewhere else.
    /// </summary>
    private static void ValidateLiveColumnNodes(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo liveNodes = RequirePublicStatic(geometry, "LiveColumnNodes");
        Type point3d = liveNodes.GetParameters()[1].ParameterType.GetElementType()!;
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");

        // Foot F at the origin; fork K at 0.4 of the way to main head M; a
        // branch head B off the fork; a second tree from the same foot to
        // head H. HeadNode is permuted: M stands on net vertex 2, B on 1,
        // H on 0.
        double[][] built =
        {
            new[] { 0.0, 0.0, 0.0 },        // 0 F
            new[] { 0.4, 0.0, 0.8 },        // 1 K, exactly 0.4 of F to M
            new[] { 1.0, 0.0, 2.0 },        // 2 M
            new[] { 2.0, 0.0, 1.5 },        // 3 B
            new[] { -1.0, 0.0, 2.0 },       // 4 H
        };
        Array nodes = Array.CreateInstance(point, built.Length);
        for (int i = 0; i < built.Length; i++)
            nodes.SetValue(Activator.CreateInstance(point, built[i][0], built[i][1], built[i][2]), i);
        Array members = Array.CreateInstance(edge, 4);
        members.SetValue(Activator.CreateInstance(edge, 0, 1), 0);
        // The ARM before the trunk's continuation on purpose, so Above[1]
        // reads {3, 2} and picking the first entry gives the wrong branch.
        members.SetValue(Activator.CreateInstance(edge, 1, 3), 1);
        members.SetValue(Activator.CreateInstance(edge, 1, 2), 2);
        members.SetValue(Activator.CreateInstance(edge, 0, 4), 3);
        object block = CreateInstance(columnsType);
        SetContractProperty(block, columnsType, "Nodes", nodes);
        SetContractProperty(block, columnsType, "Members", members);
        SetContractProperty(block, columnsType, "MemberForce", new[] { 3.0, 1.0, 1.0, 1.0 });
        SetContractProperty(block, columnsType, "Trees", new int[][] { new[] { 0, 1, 2, 3 } });
        SetContractProperty(block, columnsType, "Heads", new[] { 2, 3, 4 });
        SetContractProperty(block, columnsType, "Forks", new[] { 1 });
        SetContractProperty(block, columnsType, "Feet", new[] { 0 });
        SetContractProperty(block, columnsType, "HeadNode", new[] { 2, 1, 0 });

        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        double X(object p) => (double)point3d.GetProperty("X")!.GetValue(p)!;
        double Y(object p) => (double)point3d.GetProperty("Y")!.GetValue(p)!;
        double Z(object p) => (double)point3d.GetProperty("Z")!.GetValue(p)!;
        object[] Run(params object[] live)
        {
            Array array = Array.CreateInstance(point3d, live.Length);
            for (int i = 0; i < live.Length; i++)
                array.SetValue(live[i], i);
            return ((Array)liveNodes.Invoke(null, new object?[] { block, array })!).Cast<object>().ToArray();
        }
        void Near(object got, double x, double y, double z, string what)
        {
            if (Math.Abs(X(got) - x) > 1.0e-9 || Math.Abs(Y(got) - y) > 1.0e-9 || Math.Abs(Z(got) - z) > 1.0e-9)
                throw new InvalidOperationException($"{what} should be ({x}, {y}, {z}); got ({X(got):0.####}, {Y(got):0.####}, {Z(got):0.####}).");
        }

        // The solved net: every node where it was built. Live vertex 2 is
        // under M, 1 under B, 0 under H, as HeadNode says.
        object[] final = Run(P(-1.0, 0.0, 2.0), P(2.0, 0.0, 1.5), P(1.0, 0.0, 2.0));
        if (final.Length != 5)
            throw new InvalidOperationException($"One position per block node; got {final.Length}.");
        for (int i = 0; i < built.Length; i++)
            Near(final[i], built[i][0], built[i][1], built[i][2], $"node {i} at the solved net");

        // Time zero: the net flat on the ground and DRAWN IN in plan, which is
        // where the plan as drawn differs from the solved plan and so the one
        // frame that can tell HeadNode from plan matching. Head M is named
        // vertex 2 at plan x 0.5, while the vertex nearest M's own built plan
        // position (x 1.0) is vertex 1: matching in plan would put M, and the
        // fork under it, half a metre out.
        object[] flat = Run(P(-0.5, 0.0, 0.0), P(1.0, 0.0, 0.0), P(0.5, 0.0, 0.0));
        Near(flat[0], 0.0, 0.0, 0.0, "the foot at time zero");
        Near(flat[2], 0.5, 0.0, 0.0, "the main head at time zero, on the vertex HeadNode names");
        Near(flat[3], 1.0, 0.0, 0.0, "the branch head at time zero");
        Near(flat[4], -0.5, 0.0, 0.0, "the second tree's head at time zero");
        Near(flat[1], 0.2, 0.0, 0.0, "the fork at time zero, on the rail at its built fraction");

        // Halfway: the fork keeps its fraction and stays on the line.
        object[] mid = Run(P(-0.75, 0.0, 1.0), P(1.5, 0.0, 0.75), P(0.75, 0.0, 1.0));
        Near(mid[1], 0.3, 0.0, 0.4, "the fork halfway up");
        double angle = AngleDeg(
            X(mid[1]) - X(mid[0]), Y(mid[1]) - Y(mid[0]), Z(mid[1]) - Z(mid[0]),
            X(mid[2]) - X(mid[1]), Y(mid[2]) - Y(mid[1]), Z(mid[2]) - Z(mid[1]));
        if (angle > 0.5)
            throw new InvalidOperationException($"Trunk, fork and main head must stay collinear; they kink by {angle:0.###} degrees halfway up.");
    }

    /// <summary>
    /// Deconstruct's column trees: one branch per tree in the block's own
    /// order, every member a line from lower end to upper end, heads and
    /// feet as points per tree, and an absent block giving empty trees
    /// rather than an error.
    /// </summary>
    private static void ValidateDeconstructColumnTrees(Assembly plugin)
    {
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo columnsBlock = RequirePublicStatic(geometry, "ColumnsBlock");
        Type deconstruct = RequireComponentType(plugin, "DeconstructComponent");
        MethodInfo columnTrees = RequireStatic(deconstruct, "ColumnTrees");

        Type lineList = columnsBlock.GetParameters()[0].ParameterType;
        Type line = lineList.GetGenericArguments()[0];
        Type point3d = columnsBlock.GetParameters()[2].ParameterType.GetElementType()!;
        object Pt(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        Type concreteList = typeof(List<>).MakeGenericType(line);
        object members = Activator.CreateInstance(concreteList)!;
        MethodInfo add = concreteList.GetMethod("Add")!;
        // Given upper end FIRST on purpose: the block must still hand back
        // lower to upper.
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(0, 0, 5), Pt(0, 0, 0)) });
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(0, 0, 5), Pt(1, 0, 8)) });
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(0, 0, 5), Pt(-1, 0, 8)) });
        add.Invoke(members, new[] { Activator.CreateInstance(line, Pt(10, 0, 0), Pt(10, 0, 6)) });
        Array net = Array.CreateInstance(point3d, 3);
        net.SetValue(Pt(1, 0, 8), 0);
        net.SetValue(Pt(-1, 0, 8), 1);
        net.SetValue(Pt(10, 0, 6), 2);
        object block = columnsBlock.Invoke(null, new object?[]
        {
            members, new[] { 300.0, 100.0, 100.0, 200.0 }, net, 1.0e-6, 2, 0, 0, 0.65, 0,
        })!;

        object trees = columnTrees.Invoke(null, new[] { block })!;
        Type tuple = trees.GetType();
        var lines = ((IEnumerable)tuple.GetField("Item1")!.GetValue(trees)!)
            .Cast<IEnumerable>().Select(b => b.Cast<object>().ToArray()).ToArray();
        var heads = ((IEnumerable)tuple.GetField("Item2")!.GetValue(trees)!)
            .Cast<IEnumerable>().Select(b => b.Cast<object>().ToArray()).ToArray();
        var feet = ((IEnumerable)tuple.GetField("Item3")!.GetValue(trees)!)
            .Cast<IEnumerable>().Select(b => b.Cast<object>().ToArray()).ToArray();

        if (lines.Length != 2 || lines[0].Length != 3 || lines[1].Length != 1)
            throw new InvalidOperationException("Two trees of three and one members; got " + string.Join("/", lines.Select(b => b.Length)) + ".");
        foreach (object member in lines.SelectMany(b => b))
        {
            object from = line.GetProperty("From")!.GetValue(member)!;
            object to = line.GetProperty("To")!.GetValue(member)!;
            double fromZ = (double)point3d.GetProperty("Z")!.GetValue(from)!;
            double toZ = (double)point3d.GetProperty("Z")!.GetValue(to)!;
            if (fromZ > toZ)
                throw new InvalidOperationException("Every column line runs from its lower end to its upper end.");
        }
        if (heads[0].Length != 2 || feet[0].Length != 1 || heads[1].Length != 1 || feet[1].Length != 1)
            throw new InvalidOperationException("Tree 0 has two heads and one foot; tree 1 has one of each.");

        object empty = columnTrees.Invoke(null, new object?[] { null })!;
        if (((ICollection)empty.GetType().GetField("Item1")!.GetValue(empty)!).Count != 0)
            throw new InvalidOperationException("No block means empty trees, never an error.");
    }

    /// <summary>
    /// Diagnose's cross-checks, the things no single component can see:
    /// Columns ran on a Result with no principal runs; Animate ran with no
    /// Columns upstream; every anchor is isolated; more than half the net
    /// wants pushing up. A clean Result raises nothing.
    /// </summary>
    private static void ValidateDiagnoseRules(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type diagnosticType = RequireContractType(plugin, "DiagnosticDto");
        Type mouldType = RequireContractType(plugin, "MouldDto");
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type frameType = RequireContractType(plugin, "MouldFrameDto");
        Type diagnose = RequireComponentType(plugin, "DiagnoseComponent");
        MethodInfo crossChecks = RequireStatic(diagnose, "CrossChecks");
        MethodInfo render = RequireStatic(diagnose, "Render");
        MethodInfo collect = RequireStatic(diagnose, "Collect");

        object P(double x, double y, double z) => Activator.CreateInstance(point, x, y, z)!;
        Array Points(params object[] items)
        {
            Array array = Array.CreateInstance(point, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        object Equilibrium(int[] supports)
        {
            object eq = CreateInstance(equilibriumType);
            SetContractProperty(eq, equilibriumType, "Vertices",
                Points(P(0, 0, 0), P(1, 0, 0), P(2, 0, 0), P(3, 0, 0)));
            SetContractProperty(eq, equilibriumType, "ResolvedSupportNodeIds", supports);
            return eq;
        }
        object Result(int[] supports, object? mould)
        {
            object r = CreateResultDto(resultType, "fd", Equilibrium(supports), null, null);
            SetContractProperty(r, resultType, "Mould", mould);
            return r;
        }
        object Mould(object? columns, object? frame)
        {
            object m = CreateInstance(mouldType);
            SetContractProperty(m, mouldType, "Columns", columns);
            SetContractProperty(m, mouldType, "Frame", frame);
            return m;
        }
        object Frame(int vertexCount)
        {
            object f = CreateInstance(frameType);
            SetContractProperty(f, frameType, "Vertices",
                Points(Enumerable.Range(0, vertexCount).Select(i => P(i, 0, 1)).ToArray()));
            return f;
        }
        string[] Codes(object result) =>
            ((IEnumerable)crossChecks.Invoke(null, new[] { result })!)
                .Cast<object>()
                .Select(d => (string)diagnosticType.GetProperty("Code")!.GetValue(d)!)
                .ToArray();
        void Expect(object result, string code)
        {
            string[] codes = Codes(result);
            if (!codes.Contains(code))
                throw new InvalidOperationException($"Expected {code}; got [{string.Join(", ", codes)}].");
        }

        // Columns block on a Result with no principal runs.
        object noRuns = Result(Array.Empty<int>(), Mould(ColumnsBlockForRules(plugin), null));
        Expect(noRuns, "diagnose.no_principal_runs");

        // A frame with no columns upstream.
        Expect(Result(Array.Empty<int>(), Mould(null, Frame(4))), "diagnose.frame_without_columns");

        // Two anchors and no edges at all: each is its own strip.
        Expect(Result(new[] { 0, 1 }, null), "diagnose.anchors_all_isolated");

        // 380 of 441 nodes want pushing up, said by Animate.
        object pushy = Result(Array.Empty<int>(), null);
        object push = CreateInstance(diagnosticType);
        SetContractProperty(push, diagnosticType, "Code", "animate.nodes_want_push");
        SetContractProperty(push, diagnosticType, "Severity", "warning");
        SetContractProperty(push, diagnosticType, "Message", "380 nodes sit above the bare surface");
        SetContractProperty(push, diagnosticType, "Value", 380.0);
        SetContractProperty(push, diagnosticType, "Context", new Dictionary<string, string> { ["total"] = "441" });
        SetContractProperty(push, diagnosticType, "Provenance", new Dictionary<string, string> { ["source"] = "Animate" });
        Array one = Array.CreateInstance(diagnosticType, 1);
        one.SetValue(push, 0);
        SetContractProperty(pushy, resultType, "Diagnostics", one);
        Expect(pushy, "diagnose.push_needed");

        // Clean: nothing to say.
        string[] clean = Codes(Result(Array.Empty<int>(), null));
        if (clean.Length != 0)
            throw new InvalidOperationException($"A clean Result raises nothing; got [{string.Join(", ", clean)}].");

        // An invalid Result: a frame of three vertices on a net of four, and
        // no columns, which would ALSO trip frame_without_columns if the
        // cross-checks ran. They must not: one error entry per validation
        // failure, and nothing else from Diagnose.
        object broken = Result(Array.Empty<int>(), Mould(null, Frame(3)));
        string[] collected = ((IEnumerable)collect.Invoke(null, new[] { broken })!)
            .Cast<object>()
            .Select(d => (string)diagnosticType.GetProperty("Code")!.GetValue(d)!)
            .ToArray();
        if (!collected.Contains("diagnose.invalid_result"))
            throw new InvalidOperationException($"An invalid Result must yield diagnose.invalid_result; got [{string.Join(", ", collected)}].");
        if (collected.Any(c => c.StartsWith("diagnose.", StringComparison.Ordinal) && c != "diagnose.invalid_result"))
            throw new InvalidOperationException($"Cross-checks must be skipped on an invalid Result; got [{string.Join(", ", collected)}].");

        // Render says the words and prints the worker report last.
        object rendered = Result(Array.Empty<int>(), null);
        SetContractProperty(rendered, resultType, "Report", "solver said so");
        Array none = Array.CreateInstance(diagnosticType, 0);
        string text = (string)render.Invoke(null, new object[] { rendered, none })!;
        if (!text.Contains("solver said so", StringComparison.Ordinal))
            throw new InvalidOperationException("Render must print the worker's Report.");
        if (!text.Contains("Columns", StringComparison.Ordinal))
            throw new InvalidOperationException("Render must say which mould components have not run.");

        // An FD Result with no report prints the standing FD line.
        string fdText = (string)render.Invoke(null, new object[] { Result(Array.Empty<int>(), null), none })!;
        if (!fdText.Contains("FD result: no reciprocal diagram.", StringComparison.Ordinal))
            throw new InvalidOperationException("Render must print the FD line when an FD Result carries no report.");
    }

    private static object ColumnsBlockForRules(Assembly plugin)
    {
        Type columnsType = RequireContractType(plugin, "MouldColumnsDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");
        object c = CreateInstance(columnsType);
        Array nodes = Array.CreateInstance(point, 2);
        nodes.SetValue(Activator.CreateInstance(point, 0.0, 0.0, 0.0), 0);
        nodes.SetValue(Activator.CreateInstance(point, 0.0, 0.0, 5.0), 1);
        Array members = Array.CreateInstance(edge, 1);
        members.SetValue(Activator.CreateInstance(edge, 0, 1), 0);
        SetContractProperty(c, columnsType, "Nodes", nodes);
        SetContractProperty(c, columnsType, "Members", members);
        SetContractProperty(c, columnsType, "MemberForce", new[] { 100.0 });
        SetContractProperty(c, columnsType, "Trees", new int[][] { new[] { 0 } });
        SetContractProperty(c, columnsType, "Heads", new[] { 1 });
        SetContractProperty(c, columnsType, "Feet", new[] { 0 });
        SetContractProperty(c, columnsType, "HeadNode", new[] { 0 });
        return c;
    }

    private static Type RequireContractType(Assembly plugin, string typeName)
    {
        const string ContractsNamespace = "Ananke.COMPAS.Native.Contracts";
        return plugin.GetType($"{ContractsNamespace}.{typeName}", throwOnError: true)
            ?? throw new InvalidOperationException(
                $"Type '{ContractsNamespace}.{typeName}' was not found.");
    }

    /// <summary>
    /// <c>MouldGeometry.SnapCurveToNodes</c>: a drawn principal line must
    /// match a CONNECTED run of net nodes, not merely the set of nodes near
    /// it.
    ///
    /// The regression this pins, found in the viewport 2026-08-26: the obvious
    /// implementation collects every node inside a catch radius of the curve
    /// and sorts them by how far along the curve they lie. A line drawn down
    /// the middle of a bay catches the column of nodes EITHER SIDE of it, and
    /// the two columns' positions along the curve interleave, so the sorted
    /// run crosses the bay on every step. It draws as a zigzag, and it is
    /// worse than a drawing fault: Animate pins that run and Column Finder
    /// solves it as a beam, so the bar has notches on both sides of a bay and
    /// is reported at roughly twice its true length.
    ///
    /// The fixture is that exact case. A five-by-nine unit grid; the line
    /// drawn at x = 1.5, halfway between the columns at x = 1 and x = 2, so
    /// both sit 0.5 from it and the catch radius (0.6 of the unit median edge)
    /// takes in both. A correct match picks ONE column and walks it end to
    /// end. The sorted implementation returns 18 nodes alternating between
    /// the two columns; the walk returns 9 on one.
    ///
    /// A second case draws the line ON the column at x = 2, where only that
    /// column is inside the radius, and asserts the offset comes back at zero
    /// so the reported offset is not merely always the same number.
    ///
    /// Reflection-only, in this harness's usual manner: no Rhino document and
    /// no SolveInstance, only the static geometry method and the RhinoCommon
    /// types it already has loaded.
    /// </summary>
    private static void ValidatePrincipalLineSnapping(Assembly plugin)
    {
        Type mouldGeometry = RequireComponentType(plugin, "MouldGeometry");
        MethodInfo snap = mouldGeometry.GetMethod(
            "SnapSampledLineToNodes",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "MouldGeometry.SnapSampledLineToNodes was not found.");

        // Take the Rhino types off the method's own signature rather than
        // naming an assembly: whatever RhinoCommon the plugin was loaded
        // against is by definition the one these arguments must satisfy.
        // Point3d is a plain struct and needs no native core; a Curve would,
        // which is exactly why the walk takes sampled points instead.
        ParameterInfo[] parameters = snap.GetParameters();
        Type point3d = parameters[0].ParameterType.GetElementType()
            ?? throw new InvalidOperationException(
                "SnapSampledLineToNodes' first parameter is not an array.");

        const int columns = 5;
        const int rows = 9;
        Array nodes = Array.CreateInstance(point3d, columns * rows);
        for (int row = 0; row < rows; row++)
        for (int column = 0; column < columns; column++)
        {
            nodes.SetValue(
                Activator.CreateInstance(
                    point3d, (double)column, (double)row, 0.0),
                (row * columns) + column);
        }

        var edges = new List<(int, int)>();
        for (int row = 0; row < rows; row++)
        for (int column = 0; column < columns; column++)
        {
            int id = (row * columns) + column;
            if (column + 1 < columns)
                edges.Add((id, id + 1));
            if (row + 1 < rows)
                edges.Add((id, id + columns));
        }
        var adjacency = new HashSet<(int, int)>();
        foreach ((int u, int v) in edges)
        {
            adjacency.Add((u, v));
            adjacency.Add((v, u));
        }
        (int, int)[] edgeArray = edges.ToArray();

        CheckOneSnap(
            snap, point3d, nodes, edgeArray, adjacency,
            drawnAt: 1.5, expectedOffset: 0.5, label: "drawn down a bay");
        CheckOneSnap(
            snap, point3d, nodes, edgeArray, adjacency,
            drawnAt: 2.0, expectedOffset: 0.0, label: "drawn on a column");
    }

    private static void CheckOneSnap(
        MethodInfo snap,
        Type point3d,
        Array nodes,
        (int, int)[] edges,
        HashSet<(int, int)> adjacency,
        double drawnAt,
        double expectedOffset,
        string label)
    {
        const int columns = 5;
        const int rows = 9;

        // The line the author drew, sampled the way the component samples it:
        // straight down the grid at x = drawnAt, running past both ends.
        const int samples = 512;
        Array sampled = Array.CreateInstance(point3d, samples + 1);
        for (int index = 0; index <= samples; index++)
        {
            double y = -1.0 + (10.0 * index / samples);
            sampled.SetValue(
                Activator.CreateInstance(point3d, drawnAt, y, 0.0),
                index);
        }

        object?[] arguments = { sampled, nodes, edges, 0.0 };
        object? returned = snap.Invoke(null, arguments);
        double offset = (double)arguments[3]!;
        List<int> run = (returned as IEnumerable
            ?? throw new InvalidOperationException(
                $"SnapCurveToNodes ({label}) returned no run."))
            .Cast<int>()
            .ToList();

        if (run.Count != rows)
        {
            throw new InvalidOperationException(
                $"A principal line {label} must match one node per row, "
                + $"{rows} in all; it matched {run.Count}. "
                + (run.Count > rows
                    ? "More than one per row is the zigzag: the run is "
                      + "crossing the bay instead of following it."
                    : "Fewer means the walk stopped short of the far side."));
        }

        int first = run[0];
        int firstColumn = first % columns;
        for (int step = 0; step < run.Count; step++)
        {
            int node = run[step];
            if (node % columns != firstColumn)
            {
                throw new InvalidOperationException(
                    $"A principal line {label} left its column at step "
                    + $"{step}: node {node} is in column {node % columns}, "
                    + $"the run started in column {firstColumn}. A bar "
                    + "cannot cross the bay it runs down.");
            }
            if (node / columns != step)
            {
                throw new InvalidOperationException(
                    $"A principal line {label} is out of order at step "
                    + $"{step}: node {node} is in row {node / columns}. The "
                    + "run must advance one row per step, end to end.");
            }
            if (step > 0 && !adjacency.Contains((run[step - 1], node)))
            {
                throw new InvalidOperationException(
                    $"A principal line {label} jumped at step {step}: nodes "
                    + $"{run[step - 1]} and {node} share no mesh edge. A bar "
                    + "is a connected chain of notches.");
            }
        }

        // The offset is measured to the nearest SAMPLE, not perpendicular to
        // the line, so half a sample spacing is the tightest it can honestly
        // be pinned. Derived from the sampling rather than hardcoded, because
        // a hardcoded number would quietly become wrong if the density
        // changed. It still separates the two cases by fifty to one, which is
        // the whole point: half a bay off reads as half a bay off.
        double tolerance = (0.5 * 10.0 / samples) + 1.0e-9;
        if (Math.Abs(offset - expectedOffset) > tolerance)
        {
            throw new InvalidOperationException(
                $"A principal line {label} must report an offset of "
                + $"{expectedOffset:G3} from the curve that asked for it; it "
                + $"reported {offset:G6}.");
        }
    }

    /// <summary>
    /// <c>MonitorMath</c>: the four pure rules Monitor's new outputs rest on,
    /// measured on hand-built inputs so a wrong sign or a wrong percentile
    /// rank cannot pass.
    /// </summary>
    private static void ValidateMonitorMath(Assembly plugin)
    {
        Type math = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MonitorMath", throwOnError: true)!;
        MethodInfo split = RequirePublicStatic(math, "AnchorSplit");
        MethodInfo axis = RequirePublicStatic(math, "TensionerAxis");
        MethodInfo stats = RequirePublicStatic(math, "DeviationStats");
        MethodInfo unstrained = RequirePublicStatic(math, "UnstrainedLength");
        MethodInfo toNewtons = RequirePublicStatic(math, "ToNewtons");
        Type vector3d = split.GetParameters()[0].ParameterType;
        Type point3d = axis.GetParameters()[1].ParameterType.GetElementType()!;

        object V(double x, double y, double z) => Activator.CreateInstance(vector3d, x, y, z)!;
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        double Get(object o, string name) => (double)o.GetType().GetProperty(name)!.GetValue(o)!;

        object parts = split.Invoke(null, new[] { V(3.0, 4.0, 0.0), V(1.0, 0.0, 0.0) })!;
        double along = (double)parts.GetType().GetField("Item1")!.GetValue(parts)!;
        double across = (double)parts.GetType().GetField("Item2")!.GetValue(parts)!;
        if (Math.Abs(along - 3.0) > 1.0e-9 || Math.Abs(across - 4.0) > 1.0e-9)
            throw new InvalidOperationException($"Reaction (3,4,0) on axis x splits into along 3, across 4; got {along}, {across}.");
        // The axis does NOT arrive unit. (2,0,0) is the same direction as
        // (1,0,0) and must give the same split; an implementation that
        // dropped the normalisation would double the along part here and
        // pass every other case in this check.
        object longAxis = split.Invoke(null, new[] { V(3.0, 4.0, 0.0), V(2.0, 0.0, 0.0) })!;
        double alongLong = (double)longAxis.GetType().GetField("Item1")!.GetValue(longAxis)!;
        double acrossLong = (double)longAxis.GetType().GetField("Item2")!.GetValue(longAxis)!;
        if (Math.Abs(alongLong - 3.0) > 1.0e-9 || Math.Abs(acrossLong - 4.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The axis is a DIRECTION, so (2,0,0) splits (3,4,0) exactly as "
                + $"(1,0,0) does, into 3 and 4; got {alongLong}, {acrossLong}. A "
                + "different answer means the axis was used unnormalised.");
        }
        // The SIGN of the along part is the port's whole content: a tensioner
        // pulling and a tensioner being pushed are the two cases, and a
        // magnitude cannot tell them apart.
        object pushed = split.Invoke(null, new[] { V(-3.0, 4.0, 0.0), V(1.0, 0.0, 0.0) })!;
        double alongPushed = (double)pushed.GetType().GetField("Item1")!.GetValue(pushed)!;
        double acrossPushed = (double)pushed.GetType().GetField("Item2")!.GetValue(pushed)!;
        if (Math.Abs(alongPushed + 3.0) > 1.0e-9 || Math.Abs(acrossPushed - 4.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Reaction (-3,4,0) on axis x pulls the OTHER way along it, so "
                + $"along is -3 and across is 4; got {alongPushed}, {acrossPushed}. "
                + "A positive along means the magnitude was taken and the sign lost.");
        }

        // Anchor 0 at the origin with cables to (1,0,0) and (0,1,0).
        Array nodes = Array.CreateInstance(point3d, 3);
        nodes.SetValue(P(0.0, 0.0, 0.0), 0);
        nodes.SetValue(P(1.0, 0.0, 0.0), 1);
        nodes.SetValue(P(0.0, 1.0, 0.0), 2);
        var neighbours = new List<int>[] { new() { 1, 2 }, new() { 0 }, new() { 0 } };
        object a = axis.Invoke(null, new object?[] { 0, nodes, neighbours })!;
        double r = 1.0 / Math.Sqrt(2.0);
        if (Math.Abs(Get(a, "X") - r) > 1.0e-9 || Math.Abs(Get(a, "Y") - r) > 1.0e-9 || Math.Abs(Get(a, "Z")) > 1.0e-9)
            throw new InvalidOperationException($"The tensioner axis is the unit mean of the cables leaving the anchor; got ({Get(a, "X"):0.###}, {Get(a, "Y"):0.###}, {Get(a, "Z"):0.###}).");
        object none = axis.Invoke(null, new object?[] { 1, nodes, new List<int>[] { new(), new(), new() } })!;
        if (Math.Abs(Get(none, "Z") - 1.0) > 1.0e-9)
            throw new InvalidOperationException("An anchor with no cable has a vertical axis.");

        object s = stats.Invoke(null, new object?[] { new List<double> { 1.0, -2.0, 3.0, -4.0, 5.0 } })!;
        double rms = (double)s.GetType().GetField("Item1")!.GetValue(s)!;
        double max = (double)s.GetType().GetField("Item2")!.GetValue(s)!;
        double p95 = (double)s.GetType().GetField("Item3")!.GetValue(s)!;
        if (Math.Abs(rms - Math.Sqrt(11.0)) > 1.0e-9 || Math.Abs(max - 5.0) > 1.0e-9 || Math.Abs(p95 - 5.0) > 1.0e-9)
            throw new InvalidOperationException($"Stats of (1,-2,3,-4,5) are RMS sqrt(11), max 5, p95 5; got {rms:0.####}, {max}, {p95}.");
        // A field whose worst reading is NEGATIVE. The frame sitting below
        // the state it is heading for is exactly that field, and an
        // implementation taking values.Max() returns 2 here.
        object below = stats.Invoke(null, new object?[] { new List<double> { -9.0, 1.0, 2.0 } })!;
        double belowMax = (double)below.GetType().GetField("Item2")!.GetValue(below)!;
        double belowP95 = (double)below.GetType().GetField("Item3")!.GetValue(below)!;
        if (Math.Abs(belowMax - 9.0) > 1.0e-9 || Math.Abs(belowP95 - 9.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The worst and the 95th percentile of (-9,1,2) are both 9, the "
                + $"worst ABSOLUTE deviation; got {belowMax} and {belowP95}. A 2 "
                + "means the signed maximum was taken, which reads a frame sagging "
                + "9 mm low as the flattest thing on the model.");
        }
        object empty = stats.Invoke(null, new object?[] { new List<double>() })!;
        double emptyRms = (double)empty.GetType().GetField("Item1")!.GetValue(empty)!;
        double emptyMax = (double)empty.GetType().GetField("Item2")!.GetValue(empty)!;
        double emptyP95 = (double)empty.GetType().GetField("Item3")!.GetValue(empty)!;
        if (emptyRms != 0.0 || emptyMax != 0.0 || emptyP95 != 0.0)
        {
            throw new InvalidOperationException(
                "Stats of nothing are zero in ALL THREE places; got "
                + $"{emptyRms}, {emptyMax}, {emptyP95}.");
        }
        // Twenty values 1..20: the nearest-rank 95th percentile is the 19th, 19.
        object twenty = stats.Invoke(null, new object?[] { Enumerable.Range(1, 20).Select(i => (double)i).ToList() })!;
        double p95twenty = (double)twenty.GetType().GetField("Item3")!.GetValue(twenty)!;
        if (Math.Abs(p95twenty - 19.0) > 1.0e-9)
            throw new InvalidOperationException($"The nearest-rank 95th percentile of 1..20 is 19; got {p95twenty}.");

        double u = (double)unstrained.Invoke(null, new object?[] { 2.0, 100.0, 1000.0 })!;
        if (Math.Abs(u - (2.0 / 1.1)) > 1.0e-9)
            throw new InvalidOperationException($"Unstrained length of 2 under 100 N with EA 1000 is 2/1.1; got {u:0.######}.");
        double raw = (double)unstrained.Invoke(null, new object?[] { 2.0, 100.0, 0.0 })!;
        if (Math.Abs(raw - 2.0) > 1.0e-9)
            throw new InvalidOperationException("Without EA the strained length is returned.");
        // One plus force over EA goes NEGATIVE here, and dividing by it would
        // hand back a length of -2: a bar to cut to a negative number.
        double collapsed = (double)unstrained.Invoke(
            null, new object?[] { 2.0, -2000.0, 1000.0 })!;
        if (Math.Abs(collapsed - 2.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A member whose EA cannot carry its own compression has no "
                + "unstrained length worth reporting, so the STRAINED 2 comes "
                + $"back; got {collapsed:0.######}.");
        }
        // A negative EA is not a stiffness at all, and 1 + 100/-5 = -19 would
        // otherwise divide 2 into a small negative length.
        double negativeEA = (double)unstrained.Invoke(
            null, new object?[] { 2.0, 100.0, -5.0 })!;
        if (Math.Abs(negativeEA - 2.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A negative EA is no stiffness, so the strained 2 comes back; "
                + $"got {negativeEA:0.######}.");
        }

        // The ONE conversion between a Result's force and the newtons every
        // stiffness and capacity is wired in. Null, not one, on a unit it
        // does not know: a silent factor of one is the fault it exists to
        // stop.
        double? Factor(string unit) => (double?)toNewtons.Invoke(null, new object?[] { unit });
        if (Factor("N") != 1.0 || Factor(" n ") != 1.0)
            throw new InvalidOperationException("A force already in N is multiplied by 1, trimmed and either case.");
        if (Factor("kN") != 1000.0 || Factor(" KN ") != 1000.0)
            throw new InvalidOperationException("A force in kN is multiplied by 1000, trimmed and either case.");
        if (Factor("lbf") is not null || Factor("") is not null || Factor(null!) is not null)
            throw new InvalidOperationException("A unit this does not know comes back NULL, so the caller has to decide rather than scaling by one behind its back.");

        // The whole point, end to end: 0.1 kN against an EA of 1000 N is the
        // same 2 / 1.1 that 100 N gives. Unconverted it would be 2 / 1.0001,
        // and a bar would be cut to very nearly its tensioned length.
        double kiloNewtonCut = (double)unstrained.Invoke(
            null, new object?[] { 2.0, 0.1 * Factor("kN")!.Value, 1000.0 })!;
        if (Math.Abs(kiloNewtonCut - (2.0 / 1.1)) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A force of 0.1 kN converted through ToNewtons against EA 1000 N "
                + $"gives the same 2/1.1 as 100 N does; got {kiloNewtonCut:0.######}.");
        }
    }

    /// <summary>
    /// <c>ResultTables</c> is the ONE order Deconstruct's geometry trees and
    /// Monitor's number trees are both built from, and nothing measured it:
    /// the two components agreed because they call the same method, not
    /// because anything said what that method hands back. A minimal FD Result
    /// of three vertices, two edges, one support and one reaction pins the
    /// rows.
    /// </summary>
    private static void ValidateResultTablesOrder(Assembly plugin)
    {
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type nodalType = RequireContractType(plugin, "NodalVectorDto");
        Type tables = RequireComponentType(plugin, "ResultTables");
        MethodInfo members = RequirePublicStatic(tables, "Members");
        MethodInfo supportNodes = RequirePublicStatic(tables, "SupportNodes");
        MethodInfo reactions = RequirePublicStatic(tables, "Reactions");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!));
        SetContractProperty(equilibrium, equilibriumType, "MemberForces",
            new[] { 11.0, -22.0 });
        SetContractProperty(equilibrium, equilibriumType, "ResolvedSupportNodeIds",
            new[] { 2 });
        SetContractProperty(equilibrium, equilibriumType, "Reactions",
            Of(nodalType,
                Activator.CreateInstance(nodalType, 2, P(2, 0, 0), P(0, 0, 7))!));
        // ONE residual, and on the LAST node on purpose: a positional reader
        // lands on item 0 and the correct reader on item 2, and that gap is
        // the whole fault being measured.
        SetContractProperty(equilibrium, equilibriumType, "Residuals",
            Of(nodalType,
                Activator.CreateInstance(nodalType, 2, P(2, 0, 0), P(0, 0, 13))!));
        object result = CreateResultDto(resultType, "fd", equilibrium, null, null);

        Array rows = (Array)members.Invoke(null, new[] { result })!;
        if (rows.Length != 2)
        {
            throw new InvalidOperationException(
                $"Two edges must give two member rows; got {rows.Length}.");
        }
        Type rowType = rows.GetType().GetElementType()!;
        int Whole(int at, string name) =>
            (int)rowType.GetProperty(name)!.GetValue(rows.GetValue(at))!;
        double Real(int at, string name) =>
            (double)rowType.GetProperty(name)!.GetValue(rows.GetValue(at))!;

        if (Whole(0, "U") != 0 || Whole(0, "V") != 1 ||
            Whole(1, "U") != 1 || Whole(1, "V") != 2)
        {
            throw new InvalidOperationException(
                "The rows keep the edges in order with their own ends; got "
                + $"({Whole(0, "U")},{Whole(0, "V")}) then "
                + $"({Whole(1, "U")},{Whole(1, "V")}).");
        }
        if (Math.Abs(Real(0, "Force") - 11.0) > 1.0e-9 ||
            Math.Abs(Real(1, "Force") + 22.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Each row carries its own edge's signed force; got "
                + $"{Real(0, "Force")} and {Real(1, "Force")}.");
        }
        if (Whole(0, "Id") != 0 || Whole(1, "Id") != 1 ||
            Whole(0, "EquilibriumEdgeId") != 0 || Whole(1, "EquilibriumEdgeId") != 1)
        {
            throw new InvalidOperationException(
                "An FD row's id and equilibrium edge id are its edge index.");
        }
        // NaN, not zero: this Result carries no force densities and an FD
        // Result carries no horizontal force at all, and zero is a reading a
        // monitor would draw and believe.
        if (!double.IsNaN(Real(0, "Q")) || !double.IsNaN(Real(0, "H")))
        {
            throw new InvalidOperationException(
                "A missing force density or horizontal force must arrive as "
                + $"NaN; got {Real(0, "Q")} and {Real(0, "H")}.");
        }

        int[] supports = ((IEnumerable)supportNodes.Invoke(null, new[] { result })!)
            .Cast<int>()
            .ToArray();
        if (!supports.SequenceEqual(new[] { 2 }))
        {
            throw new InvalidOperationException(
                $"The support ids are the Result's own; got [{string.Join(",", supports)}].");
        }

        Array acting = (Array)reactions.Invoke(null, new[] { result })!;
        if (acting.Length != 1)
        {
            throw new InvalidOperationException(
                $"One reaction went in and {acting.Length} came back.");
        }
        object pair = acting.GetValue(0)!;
        int node = (int)pair.GetType().GetField("Item1")!.GetValue(pair)!;
        object vector = pair.GetType().GetField("Item2")!.GetValue(pair)!;
        double z = (double)vector.GetType().GetProperty("Z")!.GetValue(vector)!;
        if (node != 2 || Math.Abs(z - 7.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                $"The reaction comes back at node 2 with Z 7; got node {node}, Z {z}.");
        }

        // The residual table: one slot per VERTEX, not one per sparse entry.
        MethodInfo residualTable = RequirePublicStatic(tables, "Residuals");
        Array placed = (Array)residualTable.Invoke(null, new[] { result })!;
        if (placed.Length != 3)
        {
            throw new InvalidOperationException(
                "The residuals come back ONE PER VERTEX, three here, however few "
                + $"the Result's sparse list carries; got {placed.Length}. A length "
                + "equal to the sparse list is the positional read this exists to "
                + "stop.");
        }
        double Rz(int at) => (double)placed.GetValue(at)!.GetType()
            .GetProperty("Z")!.GetValue(placed.GetValue(at))!;
        if (Math.Abs(Rz(2) - 13.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                $"Node 2's residual must land at item 2; got {Rz(2)} there. Reading "
                + "13 at item 0 means the sparse list was read positionally, which "
                + "puts every node's residual on some other node.");
        }
        if (Math.Abs(Rz(0)) > 1.0e-9 || Math.Abs(Rz(1)) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "A node the Result carries no residual for holds its slot as a ZERO "
                + $"rather than shifting its neighbours up; got {Rz(0)} and {Rz(1)}.");
        }

        // ---- the TNA path, which is where the table makes decisions -------
        // The FD path above is a straight walk of the edge list. Everything
        // that could actually misalign the two components lives here: the
        // sort by Id, the ends read through the edge each state NAMES, the
        // out-of-range support drop and the zero-reaction drop.
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");
        Type mappingsType = RequireContractType(plugin, "TnaMappingsDto");
        Type supportType = RequireContractType(plugin, "TnaSupportMappingDto");
        Type edgeStateType = RequireContractType(plugin, "TnaEdgeStateDto");

        object tnaEquilibrium = CreateInstance(equilibriumType);
        SetContractProperty(tnaEquilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(tnaEquilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!,
                Activator.CreateInstance(edgeType, 2, 0)!));

        object State(int id, int edge, double axial)
        {
            object state = CreateInstance(edgeStateType);
            SetContractProperty(state, edgeStateType, "Id", id);
            SetContractProperty(state, edgeStateType, "EquilibriumEdgeId", edge);
            SetContractProperty(state, edgeStateType, "AxialForce", axial);
            return state;
        }
        object At(int vertex, object reaction)
        {
            object item = CreateInstance(supportType);
            SetContractProperty(item, supportType, "EquilibriumVertexId", vertex);
            SetContractProperty(item, supportType, "Reaction", reaction);
            return item;
        }

        object mappings = CreateInstance(mappingsType);
        // Support 7 is not a vertex of this net. TnaMappingsDto validates
        // nothing and ResultDto.Validate never reaches it, so it has to be
        // dropped in the table or one reader indexes off the end of the
        // vertex list while the other walks past it.
        SetContractProperty(mappings, mappingsType, "Supports",
            Of(supportType, At(0, P(0, 0, 0)), At(7, P(0, 0, 0)), At(2, P(0, 0, 0))));
        SetContractProperty(mappings, mappingsType, "Reactions",
            Of(supportType, At(0, P(0, 0, 0)), At(2, P(0, 0, 5))));

        object tna = CreateResultDto(
            resultType,
            "tna",
            tnaEquilibrium,
            CreateInstance(graphType),
            CreateInstance(graphType));
        SetContractProperty(tna, resultType, "Mappings", mappings);
        // Id order and EquilibriumEdgeId order DISAGREE, and the list order is
        // neither: sorting by the wrong key, or not sorting at all, gives
        // three different answers here and only one of them is right.
        SetContractProperty(tna, resultType, "EdgeStates",
            Of(edgeStateType, State(2, 1, 30.0), State(0, 2, 10.0), State(1, 0, 20.0)));

        Array tnaRows = (Array)members.Invoke(null, new[] { tna })!;
        if (tnaRows.Length != 3)
        {
            throw new InvalidOperationException(
                $"Three edge states must give three member rows; got {tnaRows.Length}.");
        }
        int TnaWhole(int at, string name) =>
            (int)rowType.GetProperty(name)!.GetValue(tnaRows.GetValue(at))!;
        double TnaReal(int at, string name) =>
            (double)rowType.GetProperty(name)!.GetValue(tnaRows.GetValue(at))!;
        if (TnaWhole(0, "Id") != 0 || TnaWhole(1, "Id") != 1 || TnaWhole(2, "Id") != 2)
        {
            throw new InvalidOperationException(
                "The rows come back in EDGE STATE ID order, whatever order the "
                + $"Result lists them in; got ids {TnaWhole(0, "Id")}, "
                + $"{TnaWhole(1, "Id")}, {TnaWhole(2, "Id")}. This is the one "
                + "ordering that decides whether Deconstruct's Member Lines and "
                + "Monitor's forces describe the same member.");
        }
        if (TnaWhole(0, "U") != 2 || TnaWhole(0, "V") != 0 ||
            TnaWhole(1, "U") != 0 || TnaWhole(1, "V") != 1 ||
            TnaWhole(2, "U") != 1 || TnaWhole(2, "V") != 2)
        {
            throw new InvalidOperationException(
                "Each row's ends are those of the equilibrium edge its state "
                + "NAMES, not of the edge at its own index; state 0 names edge 2, "
                + $"so it runs 2 to 0. Got ({TnaWhole(0, "U")},{TnaWhole(0, "V")}), "
                + $"({TnaWhole(1, "U")},{TnaWhole(1, "V")}), "
                + $"({TnaWhole(2, "U")},{TnaWhole(2, "V")}).");
        }
        if (Math.Abs(TnaReal(0, "Force") - 10.0) > 1.0e-9 ||
            Math.Abs(TnaReal(1, "Force") - 20.0) > 1.0e-9 ||
            Math.Abs(TnaReal(2, "Force") - 30.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Each row keeps its own state's axial force through the sort; got "
                + $"{TnaReal(0, "Force")}, {TnaReal(1, "Force")}, "
                + $"{TnaReal(2, "Force")}.");
        }

        int[] tnaSupports = ((IEnumerable)supportNodes.Invoke(null, new[] { tna })!)
            .Cast<int>()
            .ToArray();
        if (!tnaSupports.SequenceEqual(new[] { 0, 2 }))
        {
            throw new InvalidOperationException(
                "A support naming a vertex this net does not have is dropped in "
                + "the TABLE, so both readers drop the same one; expected [0,2], "
                + $"got [{string.Join(",", tnaSupports)}].");
        }

        Array tnaReactions = (Array)reactions.Invoke(null, new[] { tna })!;
        if (tnaReactions.Length != 1)
        {
            throw new InvalidOperationException(
                "A zero reaction is not a reaction: two went in and only the "
                + $"non-zero one comes back; got {tnaReactions.Length}. Keeping the "
                + "zero would give Deconstruct and Monitor different stray branches.");
        }
        object tnaPair = tnaReactions.GetValue(0)!;
        int tnaNode = (int)tnaPair.GetType().GetField("Item1")!.GetValue(tnaPair)!;
        object tnaVector = tnaPair.GetType().GetField("Item2")!.GetValue(tnaPair)!;
        double tnaZ = (double)tnaVector.GetType().GetProperty("Z")!.GetValue(tnaVector)!;
        if (tnaNode != 2 || Math.Abs(tnaZ - 5.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                $"The surviving reaction is node 2's, Z 5; got node {tnaNode}, Z {tnaZ}.");
        }
    }

    /// <summary>
    /// <c>ParameterIdentity.Mismatch</c>: the one thing that tells a reopened
    /// definition that the component it is wired to has changed shape.
    ///
    /// Grasshopper matches archived parameter chunks to live parameters by
    /// INDEX, so a reshaped component does not come back with broken wires:
    /// they reattach to whatever now stands at that index, silently wherever
    /// the two ports share a type. The counts this branch actually produced
    /// on Deconstruct are the case measured here.
    /// </summary>
    private static void ValidateParameterMismatch(Assembly plugin)
    {
        Type identity = RequireComponentType(plugin, "ParameterIdentity");
        MethodInfo mismatch = RequireStatic(identity, "Mismatch");

        object? moved = mismatch.Invoke(null, new object?[] { 2, 20, 1, 13 });
        if (moved is not string text)
        {
            throw new InvalidOperationException(
                "A definition saved against 2 inputs and 20 outputs, opened "
                + "against 1 and 13, must be warned that its wires moved; nothing "
                + "came back.");
        }
        if (!text.Contains("20", StringComparison.Ordinal) ||
            !text.Contains("13", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The warning must name what was archived and what is registered, "
                + $"so the author knows which surface moved; got '{text}'.");
        }

        object? unchanged = mismatch.Invoke(null, new object?[] { 4, 9, 4, 9 });
        if (unchanged is not null)
        {
            throw new InvalidOperationException(
                "A file saved against the CURRENT surface must stay silent, or "
                + "every reopened definition carries a warning that means nothing; "
                + $"got '{unchanged}'.");
        }

        // Export's own move, and the reason it holds Live: a definition
        // saved before this branch carries seven inputs and two outputs
        // against the nine and six registered now, so every wire in it
        // lands on a different port, three of them silently, and one of
        // those three is the Live toggle.
        object? exportMoved = mismatch.Invoke(null, new object?[] { 7, 2, 9, 6 });
        if (exportMoved is not string exportText ||
            !exportText.Contains("7 inputs and 2 outputs", StringComparison.Ordinal) ||
            !exportText.Contains("9 and 6", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A saved Export, 7 inputs and 2 outputs against the 9 and 6 it "
                + "registers now, must be warned and both counts named; got "
                + $"'{exportMoved}'.");
        }
        object? exportUnchanged = mismatch.Invoke(null, new object?[] { 9, 6, 9, 6 });
        if (exportUnchanged is not null)
        {
            throw new InvalidOperationException(
                "An Export saved against the current nine and six is told "
                + $"nothing; got '{exportUnchanged}'.");
        }
    }

    /// <summary>
    /// <c>ColumnFinderComponent</c>'s load path and column aiming, measured
    /// against vectors worked out by hand.
    ///
    /// This path had never had a number checked, and when it finally was, it
    /// was reading the load off <c>equilibrium.Reactions</c>, which exist only
    /// at SUPPORTS: every interior notch read zero, so each bar was solved as a
    /// beam with no load on it. The load now comes from the solve's own member
    /// forces, and the direction that falls out of it aims the column.
    ///
    /// Three bars, each three notches long, running along Y at x = 0, one metre
    /// up. Only the middle notch is loaded, and only its infill cables differ:
    ///
    ///   SYMMETRIC   cables to (-1, y, 0) and (1, y, 0), 100 N each. The
    ///               horizontal halves cancel and the pull is straight down, so
    ///               the column must come out PLUMB. Leaning it would cost
    ///               axial force and hand its foot a sideways push for nothing,
    ///               which is the whole reason a lean has to be earned.
    ///
    ///   ONE-SIDED   one cable to (1, y, 0), 100 N, so the pull runs down and
    ///               toward +x at 45 degrees. The column supplies the opposite,
    ///               so it aims up and toward -x at 45 degrees and its FOOT
    ///               lands on the +x side: it leans against the pull. This is
    ///               Gaudi's rule, and the sign is the half of it that is easy
    ///               to get backwards.
    ///
    ///   SHALLOW     one cable to (1, y, 0.9), so the pull is nearly
    ///               horizontal and would want a 84-degree lean. Held at the
    ///               60-degree cap instead, because past that a column pushes
    ///               sideways more than it holds up and the sliding joint
    ///               cannot reach the angle.
    ///
    /// The bar runs along Y throughout, so its tangent is Y and the projection
    /// that sends along-bar pull to the anchors takes nothing away here. That
    /// is deliberate: it keeps these three cases about the aiming.
    /// </summary>
    private static void ValidateColumnAim(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo loads = finder.GetMethod("BarLoads", BindingFlags.Public | BindingFlags.Static)!;
        MethodInfo transverse = finder.GetMethod("BarTransverse", BindingFlags.Public | BindingFlags.Static)!;
        // The aim rule itself now lives in MouldGeometry, shared: Column
        // Finder PLACES by it, and Animate only MEASURES its trunks against
        // it, so testing it once tests both. Animate re-aims nothing: a trunk
        // points where its foot and its notch put it, and the aim is read to
        // report how far that is from the force path at this frame.
        MethodInfo armAim = finder.GetMethod(
            "AimFrom", BindingFlags.Public | BindingFlags.Static)!;

        Type point3d = loads.GetParameters()[1].ParameterType.GetElementType()
            ?? throw new InvalidOperationException(
                "BarLoads' node parameter is not an array.");
        Type incidentArray = loads.GetParameters()[2].ParameterType;
        Type incidentList = incidentArray.GetElementType()
            ?? throw new InvalidOperationException(
                "BarLoads' incident parameter is not an array.");

        CheckOneAim(
            loads, transverse, armAim, point3d, incidentArray, incidentList,
            farX: 1.0, farZ: 0.0, twoSided: true,
            expectedX: 0.0, expectedZ: 1.0, label: "symmetric bay");
        CheckOneAim(
            loads, transverse, armAim, point3d, incidentArray, incidentList,
            farX: 1.0, farZ: 0.0, twoSided: false,
            expectedX: -Math.Sqrt(0.5), expectedZ: Math.Sqrt(0.5),
            label: "one-sided bay");

        // Capped: the direction is held at sixty degrees from vertical, so the
        // horizontal part is sin(60) and the vertical cos(60), leaning toward
        // -x as before.
        CheckOneAim(
            loads, transverse, armAim, point3d, incidentArray, incidentList,
            farX: 1.0, farZ: 0.9, twoSided: false,
            expectedX: -Math.Sin(Math.PI / 3.0),
            expectedZ: Math.Cos(Math.PI / 3.0),
            label: "capped shallow pull");
    }

    /// <summary>
    /// <c>ColumnPlacement</c>, the engine that replaced the beam search:
    /// every rule of spec section 3, driven on hand-built nets. A net here is
    /// an arch of notches in the XZ plane, anchored at both ends, with a
    /// vertical pull on every notch; that is enough to measure grouping,
    /// feet, fork, rejection and Auto, and it is the case Param's three
    /// screenshots were of.
    /// </summary>
    private static void ValidateColumnPlacement(Assembly plugin)
    {
        Type engine = plugin.GetType(
            "Ananke.COMPAS.Native.Components.ColumnPlacement", throwOnError: true)!;
        MethodInfo group = RequirePublicStatic(engine, "Group");
        MethodInfo place = RequirePublicStatic(engine, "Place");
        MethodInfo segment = RequirePublicStatic(engine, "SegmentDistance");
        Type point3d = place.GetParameters()[0].ParameterType.GetElementType()!;
        Type vector3d = place.GetParameters()[3].ParameterType.GetElementType()!.GetElementType()!;
        double forkFraction = (double)engine.GetField("ForkFraction")!.GetValue(null)!;
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        double maxLean = (double)geometry.GetField("MaxLeanDegrees")!.GetValue(null)!;

        // ---- Grouping.
        (int[][] Groups, int[] Mains) Grouped(int count, int branching)
        {
            object result = group.Invoke(null, new object?[] { count, branching })!;
            Type type = result.GetType();
            return (
                (int[][])type.GetField("Item1")!.GetValue(result)!,
                (int[])type.GetField("Item2")!.GetValue(result)!);
        }
        string Show(int[][] groups) => string.Join(" ", groups.Select(g => "[" + string.Join(",", g) + "]"));

        (int[][] nine, int[] nineMains) = Grouped(9, 2);
        string nineText = Show(nine);
        if (nineText != "[0,1] [2,3] [4] [5,6] [7,8]")
            throw new InvalidOperationException($"Nine notches at Branching 2 must be a centre single and four mirrored pairs; got {nineText}.");
        if (!nineMains.SequenceEqual(new[] { 1, 3, 4, 5, 7 }))
            throw new InvalidOperationException($"Mains must be the innermost notch of each group, mirrored; got [{string.Join(",", nineMains)}].");
        (int[][] eight, _) = Grouped(8, 3);
        string eightText = Show(eight);
        if (eightText != "[0] [1,2,3] [4,5,6] [7]")
            throw new InvalidOperationException($"Eight notches at Branching 3 must be two triples with a single at each anchor end; got {eightText}.");
        (int[][] five, _) = Grouped(5, 1);
        if (five.Length != 5 || five.Any(g => g.Length != 1))
            throw new InvalidOperationException($"Five notches at Branching 1 are five singles; got {Show(five)}.");
        (int[][] none, _) = Grouped(0, 2);
        if (none.Length != 0)
            throw new InvalidOperationException("No notches group into nothing.");

        // ---- A hand-built arch.
        // count notches from x = 0 to x = width, z = rise * 4 * s * (1 - s),
        // anchored at both ends, every notch pulled straight down by `load`.
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        object V(double x, double y, double z) => Activator.CreateInstance(vector3d, x, y, z)!;

        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Arch(int count, double width, double rise, double load)
        {
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            for (int i = 0; i < count; i++)
            {
                double s = (double)i / (count - 1);
                nodes.SetValue(P(width * s, 0.0, rise * 4.0 * s * (1.0 - s)), i);
                acrossBar.SetValue(V(0.0, 0.0, -load), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }

        object Run((Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net, int[][] loops, double median, int branching, int ground)
        {
            return place.Invoke(null, new object?[]
            {
                net.Nodes, net.Bars, net.Anchors, net.Across, loops, 0.0, median, branching, ground,
            })!;
        }
        T Get<T>(object o, string name)
        {
            Type type = o.GetType();
            object value = type.GetField(name)?.GetValue(o) ?? type.GetProperty(name)?.GetValue(o)
                ?? throw new InvalidOperationException($"{type.Name} has no {name}.");
            return (T)value;
        }
        double X(object p) => (double)point3d.GetProperty("X")!.GetValue(p)!;
        double Y(object p) => (double)point3d.GetProperty("Y")!.GetValue(p)!;
        double Z(object p) => (double)point3d.GetProperty("Z")!.GetValue(p)!;

        // A parabolic arch whose across pulls are mirrored in SHAPE, carrying
        // the two asymmetries a solved net always has. `bend` is the mirrored
        // part (positive leans the pulls outward from the midpoint), `skew` a
        // common along-chord tilt on every notch, `flank` a scale on the left
        // half alone. Neither asymmetry survives the mirror rule of spec 3.4,
        // and both move the feet today.
        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) SkewArch(
            int count, double width, double rise, double bend, double skew, double flank)
        {
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            double middle = (count - 1) / 2.0;
            for (int i = 0; i < count; i++)
            {
                double s = (double)i / (count - 1);
                nodes.SetValue(P(width * s, 0.0, rise * 4.0 * s * (1.0 - s)), i);
                double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                double scale = i < middle ? flank : 1.0;
                acrossBar.SetValue(V(scale * ((side * bend) + skew), 0.0, -scale), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }

        (int Lower, int Upper)[] MembersOf(object level) =>
            ((IEnumerable)Get<object>(level, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!,
                    (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();

        // Which node each tree stands on: the lower end of the first member
        // of that tree that leaves a foot.
        int[] FootOfTree(object level, int treeCount)
        {
            (int Lower, int Upper)[] members = MembersOf(level);
            var feet = ((IEnumerable)Get<object>(level, "Feet")).Cast<int>().ToHashSet();
            int[] memberTree = ((IEnumerable)Get<object>(level, "MemberTree")).Cast<int>().ToArray();
            int[] byTree = Enumerable.Repeat(-1, treeCount).ToArray();
            for (int m = 0; m < members.Length; m++)
            {
                int t = memberTree[m];
                if (byTree[t] < 0 && feet.Contains(members[m].Lower))
                    byTree[t] = members[m].Lower;
            }
            return byTree;
        }

        // ---- Mirrored feet (spec 6). Eleven notches, span ten, rise 2.5:
        // the across pulls mirrored in shape and leaning outward, the LEFT
        // flank scaled by 1.1, and every notch skewed one degree along the
        // chord. Spec 3.4 mirrors the resultants about the span's midpoint
        // before a single foot is placed, so the scale and the skew both go:
        // the along-chord parts of a pair are made equal and opposite, its
        // across and down parts equal, and the centre tree stands plumb.
        {
            const double skew = 0.0174550649282176;   // tan(1 degree)
            var arch = SkewArch(11, 10.0, 2.5, bend: 0.25, skew: skew, flank: 1.1);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int m = trees.Length;
            if (m != 9)
                throw new InvalidOperationException($"Eleven notches anchored at both ends hold nine trees at Branching 1; got {m}.");
            int[] footNode = FootOfTree(built, m);
            const double midpoint = 5.0;
            for (int i = 0; i < m / 2; i++)
            {
                double left = X(nodes[footNode[i]]);
                double right = X(nodes[footNode[m - 1 - i]]);
                if (Math.Abs((left + right) - (2.0 * midpoint)) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Trees {i} and {m - 1 - i} are a mirrored pair and their feet straddle the span's midpoint: "
                        + $"{left:0.#########} and {right:0.#########} sum to {left + right:0.#########}, not {2.0 * midpoint:0.#}. "
                        + "The feet are following each tree's RAW resultant, which the along-chord skew tilts the same way on both flanks.");
                }
            }
            double centre = X(nodes[footNode[m / 2]]);
            if (Math.Abs(centre - midpoint) > 1.0e-9)
                throw new InvalidOperationException($"The centre tree stands outside the pairing and its foot is ON the midpoint; it is at {centre:0.#########}.");
            int[] memberTree = ((IEnumerable)Get<object>(built, "MemberTree")).Cast<int>().ToArray();
            (int Lower, int Upper)[] members = MembersOf(built);
            for (int k = 0; k < members.Length; k++)
            {
                if (memberTree[k] != m / 2)
                    continue;
                object a = nodes[members[k].Lower];
                object b = nodes[members[k].Upper];
                double lean = AngleDeg(
                    X(b) - X(a), Y(b) - Y(a), Z(b) - Z(a), 0.0, 0.0, 1.0);
                if (lean > 1.0e-9)
                    throw new InvalidOperationException($"The centre tree's along-chord pull is mirrored away, so its member stands vertical; it leans {lean:0.######} degrees.");
            }
            double moved = Get<double>(placed, "AsymmetryRemoved");
            if (moved <= 0.0)
                throw new InvalidOperationException($"Symmetrise reports the largest angle it moved an aim through, and on an arch this lopsided that is more than nothing; it reported {moved:0.######}.");
        }

        // ---- One family (spec 6). The same arch three times, offset in Y by
        // 0, 1 and 2, the second's pulls scaled by 1.05, the third traced
        // BACKWARDS. A family is every span with the same free-notch count
        // (Branching is one slider, so the tree count and layout follow);
        // each span is read in the frame of the family's first span, a span
        // whose chord points the other way being read reversed, and each
        // takes the family's mean. Every principal line of a family therefore
        // carries the same columns in its own frame.
        {
            const double skew = 0.0174550649282176;
            const int count = 11;
            Array nodes = Array.CreateInstance(point3d, 3 * count);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 3);
            var bars = new int[3][];
            var anchors = new List<int>();
            double middle = (count - 1) / 2.0;
            for (int b = 0; b < 3; b++)
            {
                Array acrossBar = Array.CreateInstance(vector3d, count);
                var bar = new int[count];
                for (int i = 0; i < count; i++)
                {
                    double s = (double)i / (count - 1);
                    int node = (b * count) + i;
                    nodes.SetValue(P(10.0 * s, b, 2.5 * 4.0 * s * (1.0 - s)), node);
                    double side = i < middle ? -1.0 : (i > middle ? 1.0 : 0.0);
                    double flank = i < middle ? 1.1 : 1.0;
                    double scale = flank * (b == 1 ? 1.05 : 1.0);
                    // Bar 2 is traced from its far end: bar position k holds
                    // the node at count-1-k, and the pull at that POSITION is
                    // the pull that node carries.
                    int position = b == 2 ? count - 1 - i : i;
                    bar[position] = node;
                    acrossBar.SetValue(V(scale * ((side * 0.25) + skew), 0.0, -scale), position);
                }
                bars[b] = bar;
                across.SetValue(acrossBar, b);
                anchors.Add(b * count);
                anchors.Add((b * count) + count - 1);
            }
            var family = (nodes, bars, anchors.ToArray(), across, Array.Empty<(int, int)>());
            object placed = Run(family, Array.Empty<int[]>(), 1.0, 1, 0);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 3)
                throw new InvalidOperationException($"Three bars anchored at both ends give three spans; got {spans.Length}.");
            int[] footNode = FootOfTree(built, trees.Length);
            var offsets = new List<(double Along, double Across)>[spans.Length];
            for (int s = 0; s < spans.Length; s++)
            {
                object span = spans[s];
                int[] bar = bars[Get<int>(span, "Bar")];
                object first = nodes.GetValue(bar[Get<int>(span, "First")])!;
                object last = nodes.GetValue(bar[Get<int>(span, "Last")])!;
                double cx = X(last) - X(first);
                double cy = Y(last) - Y(first);
                double length = Math.Sqrt((cx * cx) + (cy * cy));
                cx /= length;
                cy /= length;
                double midX = 0.5 * (X(first) + X(last));
                double midY = 0.5 * (Y(first) + Y(last));
                offsets[s] = new List<(double Along, double Across)>();
                for (int t = 0; t < trees.Length; t++)
                {
                    if (Get<int>(trees[t], "Span") != s)
                        continue;
                    object foot = levelNodes[footNode[t]];
                    double dx = X(foot) - midX;
                    double dy = Y(foot) - midY;
                    offsets[s].Add(((dx * cx) + (dy * cy), (dx * -cy) + (dy * cx)));
                }
            }
            for (int s = 1; s < spans.Length; s++)
            {
                if (offsets[s].Count != offsets[0].Count)
                    throw new InvalidOperationException($"Every span of a family holds the same trees; span {s} holds {offsets[s].Count} against {offsets[0].Count}.");
                for (int i = 0; i < offsets[0].Count; i++)
                {
                    if (Math.Abs(offsets[s][i].Along - offsets[0][i].Along) > 1.0e-9 ||
                        Math.Abs(offsets[s][i].Across - offsets[0][i].Across) > 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"Foot {i} of span {s}, read in its OWN frame, stands where foot {i} of the family's first span stands: "
                            + $"({offsets[s][i].Along:0.#########}, {offsets[s][i].Across:0.#########}) against ({offsets[0][i].Along:0.#########}, {offsets[0][i].Across:0.#########}). "
                            + "A span traced backwards is being read in the world's frame, not the family's.");
                    }
                }
            }
        }

        // ---- Fork on the segment, collinear. Rise five over eight: when
        // this arch is reused below at Ground 1 its outer trunks lean 54
        // degrees, inside the 60-degree cap, and alignment is judged at the
        // FOOT, where mirrored trunks sum to a vertical push. Judging each
        // trunk alone against its plumb aim refused this arch, and every
        // ordinary arch with it; the rise needed to pass that way was
        // fifteen, which is not an arch anyone builds.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 2, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var members = ((IEnumerable)Get<object>(built, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!, (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToHashSet();
            if (members.Any(m => Z(nodes[m.Item1]) > Z(nodes[m.Item2]) + 1.0e-9))
                throw new InvalidOperationException("Every member must leave the engine lower end first.");
            int forks = 0;
            foreach ((int lower, int upper) in members)
            {
                if (!feet.Contains(lower))
                    continue;
                // A trunk. Its upper end is a fork when something leaves it.
                var above = members.Where(m => m.Item1 == upper).ToArray();
                if (above.Length == 0)
                    continue;
                forks++;
                object foot = nodes[lower];
                object fork = nodes[upper];
                // The main branch is the one collinear with the trunk.
                double bestAngle = double.MaxValue;
                object? main = null;
                foreach ((int _, int notch) in above)
                {
                    double angle = AngleDeg(
                        X(fork) - X(foot), Y(fork) - Y(foot), Z(fork) - Z(foot),
                        X(nodes[notch]) - X(fork), Y(nodes[notch]) - Y(fork), Z(nodes[notch]) - Z(fork));
                    if (angle < bestAngle)
                    {
                        bestAngle = angle;
                        main = nodes[notch];
                    }
                }
                if (bestAngle > 0.5)
                    throw new InvalidOperationException($"Trunk and main branch must be collinear within 0.5 degrees; a fork kinks by {bestAngle:0.###}.");
                double expectedZ = Z(foot) + ((Z(main!) - Z(foot)) * forkFraction);
                if (Math.Abs(Z(fork) - expectedZ) > 1.0e-9)
                    throw new InvalidOperationException($"The fork must sit at {forkFraction:0.##} of the main notch height; it sits at z {Z(fork):0.###} against {expectedZ:0.###}.");
            }
            if (forks < 2)
                throw new InvalidOperationException($"Nine notches at Branching 2 must build forked trees; {forks} forks found.");
        }

        // ---- The same arch at Branching 3, where a tree holds a notch BELOW
        // 65% of its main notch's height. Group(7,3) gives {1,2,3} with main
        // 3 at z 4.6875, so the spec's fork height is z 3.047 while bar
        // position 1 sits at z 2.1875, under it. Two things must hold and
        // neither did: every member leaves the engine lower end first, and a
        // node that is only ever a lower end is a FOOT, so it stands on the
        // ground. The branch used to be emitted (fork, notch) with the notch
        // below, which made columns.lean read 90 degrees on the canvas, and
        // once the block sorted it by Z that held head became a foot in
        // mid-air for Deconstruct, Monitor and Animate alike.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 3, 0);
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var members = ((IEnumerable)Get<object>(built, "Members")).Cast<object>()
                .Select(m => ((int)m.GetType().GetField("Item1")!.GetValue(m)!, (int)m.GetType().GetField("Item2")!.GetValue(m)!))
                .ToArray();
            if (members.Any(m => Z(nodes[m.Item1]) > Z(nodes[m.Item2]) + 1.0e-9))
                throw new InvalidOperationException("At Branching 3 a branch running down from the fork must still leave the engine lower end first.");
            var isLower = new bool[nodes.Length];
            var isUpper = new bool[nodes.Length];
            foreach ((int lower, int upper) in members)
            {
                isLower[lower] = true;
                isUpper[upper] = true;
            }
            for (int i = 0; i < nodes.Length; i++)
            {
                if (isLower[i] && !isUpper[i] && Z(nodes[i]) > 1.0e-9)
                    throw new InvalidOperationException($"A node that is only ever a lower end is read as a FOOT by the block; this one stands at z {Z(nodes[i]):0.###}, a column head turned into a foot in mid-air. The fork must sit below every notch it serves.");
            }
        }

        // ---- The wide arch refuses one central foot.
        {
            var wide = Arch(13, 12.0, 2.0, 1.0);
            object placed = Run(wide, Array.Empty<int[]>(), 1.0, 1, 1);
            int asked = Get<int>(placed, "GroundAsked");
            int got = Get<int>(placed, "GroundPlaced");
            if (asked != 1 || got != 0)
                throw new InvalidOperationException($"A shallow arch twelve wide asked for one foot must fall back to standalone; asked {asked}, placed {got}.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            object first = tried[0];
            if (Get<int>(first, "Ground") != 1 || Get<bool>(first, "Feasible") || Get<string>(first, "Rule") != "lean")
                throw new InvalidOperationException("Level 1 must be recorded as refused on lean.");
            if (Get<double>(first, "Value") <= maxLean)
                throw new InvalidOperationException("The refusing lean must exceed the cap.");
        }

        // ---- The centred foot, odd and even counts.
        foreach (int count in new[] { 9, 8 })
        {
            var arch = Arch(count, 8.0, 5.0, 1.0);
            object placed = Run(arch, Array.Empty<int[]>(), 1.0, 1, 1);
            if (Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"A rise-five arch eight wide holds one central foot: its outer trunks lean 54 degrees and the mirrored pairs sum to a vertical push at the foot; {count} notches fell back.");
            object built = Get<object>(placed, "Built");
            var nodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 1)
                throw new InvalidOperationException($"Ground 1 on one bar is one foot; {feet.Length} built with {count} notches.");
            double off = Math.Abs(X(nodes[feet[0]]) - 4.0);
            if (off > 0.08)
                throw new InvalidOperationException($"The one foot must stand on the span's plan centre within a hundredth of the span; it is {off:0.####} off with {count} notches. This is Param's off-centre foot, refused.");
        }

        // ---- A held ring: mid-bar anchors cut the bar and are never heads.
        // Anchors at 0, 3, 5 and 8 on nine notches leave three spans: 1..2,
        // the single notch 4 between two anchors, and 6..7.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            var held = (arch.Nodes, arch.Bars, new[] { 0, 3, 5, 8 }, arch.Across, arch.Edges);
            object placed = Run(held, Array.Empty<int[]>(), 1.0, 1, 0);
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 3)
                throw new InvalidOperationException($"Anchors at 0, 3, 5 and 8 cut a nine-notch bar into three spans; got {spans.Length}.");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var headNodes = trees.SelectMany(t => ((int[])Get<object>(t, "Nodes"))).ToArray();
            if (headNodes.Any(h => h == 0 || h == 3 || h == 5 || h == 8))
                throw new InvalidOperationException("An anchor is never a head.");
            if (headNodes.Length != 5)
                throw new InvalidOperationException($"Five free notches must all be held; {headNodes.Length} heads built.");
        }

        // ---- A free rim: two bars ending on an anchor-free loop.
        {
            // Bar 0 along +x from an anchor at x=-4 to a rim notch at x=-1;
            // bar 1 along +y from an anchor at y=-4 to a rim notch at y=-1.
            // The hole's rim is the loop {2, 5, 6}; node 6 is a spare rim node.
            Array nodes = Array.CreateInstance(point3d, 7);
            nodes.SetValue(P(-4.0, 0.0, 0.0), 0);
            nodes.SetValue(P(-2.5, 0.0, 2.0), 1);
            nodes.SetValue(P(-1.0, 0.0, 3.0), 2);
            nodes.SetValue(P(0.0, -4.0, 0.0), 3);
            nodes.SetValue(P(0.0, -2.5, 2.0), 4);
            nodes.SetValue(P(0.0, -1.0, 3.0), 5);
            nodes.SetValue(P(1.0, 1.0, 3.0), 6);
            Array acrossA = Array.CreateInstance(vector3d, 3);
            Array acrossB = Array.CreateInstance(vector3d, 3);
            for (int i = 0; i < 3; i++)
            {
                acrossA.SetValue(V(0.0, 0.0, -1.0), i);
                acrossB.SetValue(V(0.0, 0.0, -1.0), i);
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(acrossA, 0);
            across.SetValue(acrossB, 1);
            var net = (nodes, new[] { new[] { 0, 1, 2 }, new[] { 3, 4, 5 } }, new[] { 0, 3 }, across, new[] { (0, 1), (1, 2), (3, 4), (4, 5), (2, 6), (5, 6), (2, 5) });
            object placed = Run(net, new[] { new[] { 2, 5, 6 } }, 1.5, 1, 0);
            object? ring = Get<object?>(placed, "RingTree");
            if (ring is null)
                throw new InvalidOperationException("Two bars ending on an anchor-free rim must get a ring tree.");
            object foot = Get<object>(ring, "FixedFoot");
            if (Math.Abs(X(foot)) > 0.04 || Math.Abs(Y(foot)) > 0.04)
                throw new InvalidOperationException($"The ring foot is the plan intersection of the end tangents, the origin here within a hundredth of the span; it is at ({X(foot):0.###}, {Y(foot):0.###}).");
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var allHeads = trees.SelectMany(t => (int[])Get<object>(t, "Nodes")).ToArray();
            if (allHeads.Count(h => h == 2) != 1 || allHeads.Count(h => h == 5) != 1)
                throw new InvalidOperationException("Each rim notch is held exactly once, by the ring tree.");
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Any(s => Get<string>(s, "LastKind") != "rim" && Get<string>(s, "FirstKind") != "rim"))
                throw new InvalidOperationException("Every span on these bars ends at the rim notch.");
        }

        // ---- A crossing: the shared node is held once, by the lower bar.
        {
            Array nodes = Array.CreateInstance(point3d, 9);
            // Bar 0 along x through the crossing at index 2; bar 1 along y
            // through the same node.
            nodes.SetValue(P(-4.0, 0.0, 0.0), 0);
            nodes.SetValue(P(-2.0, 0.0, 2.0), 1);
            nodes.SetValue(P(0.0, 0.0, 3.0), 2);
            nodes.SetValue(P(2.0, 0.0, 2.0), 3);
            nodes.SetValue(P(4.0, 0.0, 0.0), 4);
            nodes.SetValue(P(0.0, -4.0, 0.0), 5);
            nodes.SetValue(P(0.0, -2.0, 2.0), 6);
            nodes.SetValue(P(0.0, 2.0, 2.0), 7);
            nodes.SetValue(P(0.0, 4.0, 0.0), 8);
            Array acrossA = Array.CreateInstance(vector3d, 5);
            Array acrossB = Array.CreateInstance(vector3d, 5);
            for (int i = 0; i < 5; i++)
            {
                acrossA.SetValue(V(0.0, 0.0, -1.0), i);
                acrossB.SetValue(V(0.0, 0.0, -1.0), i);
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(acrossA, 0);
            across.SetValue(acrossB, 1);
            var net = (nodes, new[] { new[] { 0, 1, 2, 3, 4 }, new[] { 5, 6, 2, 7, 8 } }, new[] { 0, 4, 5, 8 }, across,
                new[] { (0, 1), (1, 2), (2, 3), (3, 4), (5, 6), (6, 2), (2, 7), (7, 8) });
            object placed = Run(net, Array.Empty<int[]>(), 2.0, 1, 1);
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var heads = trees.SelectMany(t => (int[])Get<object>(t, "Nodes")).ToArray();
            if (heads.Count(h => h == 2) != 1)
                throw new InvalidOperationException($"The crossing node is held exactly once; it is held {heads.Count(h => h == 2)} times.");
            object owner = trees.First(t => ((int[])Get<object>(t, "Nodes")).Contains(2));
            if (Get<int>(owner, "Bar") != 0)
                throw new InvalidOperationException("The crossing belongs to the lower-indexed bar.");
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (spans.Length != 2)
                throw new InvalidOperationException($"A crossing does not cut a span: two bars give two spans, got {spans.Length}.");
            object built = Get<object>(placed, "Built");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"Ground 1 on this cross is feasible (rise three over a half-width of four leans the outer trunks 53 degrees, and the mirrored pairs sum vertical at the foot) and must be placed; placed {Get<int>(placed, "GroundPlaced")}.");
            if (feet.Length != 1)
                throw new InvalidOperationException($"Ground 1 on a cross merges the two midpoint feet into one; {feet.Length} built.");
        }

        // ---- The segment distance, the primitive under the member rule.
        {
            double D(double[] a, double[] b, double[] c, double[] d) =>
                (double)segment.Invoke(null, new[] { P(a[0], a[1], a[2]), P(b[0], b[1], b[2]), P(c[0], c[1], c[2]), P(d[0], d[1], d[2]) })!;
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 0.0, 0.5, 0.0 }, new[] { 1.0, 0.5, 0.0 }) - 0.5) > 1.0e-9)
                throw new InvalidOperationException("Parallel unit segments half a unit apart are half a unit apart.");
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 0.5, -1.0, 0.2 }, new[] { 0.5, 1.0, 0.2 }) - 0.2) > 1.0e-9)
                throw new InvalidOperationException("A segment crossing over another at height 0.2 is 0.2 away.");
            if (Math.Abs(D(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 }, new[] { 3.0, 0.0, 0.0 }, new[] { 4.0, 0.0, 0.0 }) - 2.0) > 1.0e-9)
                throw new InvalidOperationException("Collinear segments two apart are two apart.");
        }

        // ---- The collision RULE, spec 6, on CountCollisions itself. The
        // segment distance above is only its primitive; nothing used to drive
        // the rule, so neither the member test nor the net test had ever been
        // measured and a level could be refused on "collision" untested.
        {
            Type levelType = engine.GetNestedType("Level", BindingFlags.Public | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException("ColumnPlacement has no Level.");
            MethodInfo countCollisions = RequirePublicStatic(engine, "CountCollisions");

            object BuildLevel(double[][] points, (int, int)[] pairs)
            {
                object level = Activator.CreateInstance(levelType, nonPublic: true)!;
                object nodeList = levelType.GetField("Nodes")!.GetValue(level)!;
                MethodInfo addNode = nodeList.GetType().GetMethod("Add")!;
                foreach (double[] point in points)
                    addNode.Invoke(nodeList, new[] { P(point[0], point[1], point[2]) });
                object memberList = levelType.GetField("Members")!.GetValue(level)!;
                Type pair = memberList.GetType().GetGenericArguments()[0];
                MethodInfo addMember = memberList.GetType().GetMethod("Add")!;
                foreach ((int lower, int upper) in pairs)
                    addMember.Invoke(memberList, new[] { Activator.CreateInstance(pair, lower, upper) });
                return level;
            }

            int Collisions(object level, double[][] netVertices, double clearance)
            {
                Array netNodes = Array.CreateInstance(point3d, netVertices.Length);
                for (int i = 0; i < netVertices.Length; i++)
                    netNodes.SetValue(P(netVertices[i][0], netVertices[i][1], netVertices[i][2]), i);
                return (int)countCollisions.Invoke(null, new object?[]
                {
                    level, netNodes, new HashSet<int>(), clearance,
                })!;
            }

            const double clearance = 0.1;
            var empty = Array.Empty<double[]>();
            object half = BuildLevel(
                new[]
                {
                    new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 },
                    new[] { 0.0, 0.05, 0.0 }, new[] { 1.0, 0.05, 0.0 },
                },
                new[] { (0, 1), (2, 3) });
            if (Collisions(half, empty, clearance) != 1)
                throw new InvalidOperationException("Two parallel members that share no end, at half the clearance, collide.");
            object twice = BuildLevel(
                new[]
                {
                    new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 0.0, 0.0 },
                    new[] { 0.0, 0.2, 0.0 }, new[] { 1.0, 0.2, 0.0 },
                },
                new[] { (0, 1), (2, 3) });
            if (Collisions(twice, empty, clearance) != 0)
                throw new InvalidOperationException("The same two members at twice the clearance do not collide.");

            // The net test: a member whose interior rises above the net
            // vertex nearest it in plan is through the net. The same member
            // under a net that passes above it is not.
            object flat = BuildLevel(
                new[] { new[] { 0.0, 0.0, 1.0 }, new[] { 2.0, 0.0, 1.0 } },
                new[] { (0, 1) });
            if (Collisions(flat, new[] { new[] { 1.0, 0.0, 0.0 } }, clearance) != 1)
                throw new InvalidOperationException("A member whose midpoint rises above the nearest net vertex collides with the net.");
            if (Collisions(flat, new[] { new[] { 1.0, 0.0, 5.0 } }, clearance) != 0)
                throw new InvalidOperationException("A member under the net does not collide with it.");
        }

        // ---- Auto picks the shorter load path where both are feasible.
        {
            // Spec 6's case, which the old fixture did not build: Ground 1
            // and Ground 0 BOTH feasible and Ground 1 the shorter load path,
            // so Auto places 1.
            //
            // A steep narrow arch of three free notches whose transverse
            // pulls lean OUTWARD. Ground 0 stands each tree on its own
            // AimFrom foot, which throws the outer feet past the anchors and
            // lengthens their members; Ground 1 puts one foot on the span
            // centre, and the three trunks arriving there sum to a vertical
            // push against a vertical wanted, so alignment passes. Levels 2,
            // 3 and 4 hand every tree its own plumb foot again, where a
            // single tilted aim is 35 degrees off its own plumb trunk, past
            // the 30-degree cap, so they are refused and cannot take the
            // tie-to-the-higher-level rule off 1.
            const double tilt = 0.7;
            Array archNodes = Array.CreateInstance(point3d, 5);
            Array archAcross = Array.CreateInstance(vector3d, 5);
            var archEdges = new List<(int, int)>();
            for (int i = 0; i < 5; i++)
            {
                double s = i / 4.0;
                archNodes.SetValue(P(3.0 * s, 0.0, 3.0 * 4.0 * s * (1.0 - s)), i);
                double lean = i < 2 ? -tilt : (i > 2 ? tilt : 0.0);
                archAcross.SetValue(V(lean, 0.0, -1.0), i);
                if (i > 0)
                    archEdges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(archAcross, 0);
            var outward = (archNodes, new[] { new[] { 0, 1, 2, 3, 4 } }, new[] { 0, 4 }, across, archEdges.ToArray());

            object placed = Run(outward, Array.Empty<int[]>(), 0.75, 1, -1);
            if (Get<int>(placed, "GroundAsked") != -1)
                throw new InvalidOperationException("Auto records GroundAsked as -1.");
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            object AtLevel(int level) =>
                tried.FirstOrDefault(t => Get<int>(t, "Ground") == level)
                ?? throw new InvalidOperationException($"Auto must evaluate every level; {level} is missing.");
            object one = AtLevel(1);
            object zero = AtLevel(0);
            if (!Get<bool>(one, "Feasible"))
                throw new InvalidOperationException($"Spec 6 wants Ground 1 feasible here; it was refused on {Get<string>(one, "Rule")} at {Get<double>(one, "Value"):0.###}.");
            if (!Get<bool>(zero, "Feasible"))
                throw new InvalidOperationException($"Spec 6 wants Ground 0 feasible here; it was refused on {Get<string>(zero, "Rule")} at {Get<double>(zero, "Value"):0.###}.");
            if (Get<double>(one, "LoadPath") >= Get<double>(zero, "LoadPath"))
                throw new InvalidOperationException($"Ground 1 must carry the SHORTER load path here; it scores {Get<double>(one, "LoadPath"):0.###} against Ground 0 at {Get<double>(zero, "LoadPath"):0.###}.");
            if (Get<int>(placed, "GroundPlaced") != 1)
                throw new InvalidOperationException($"Auto must place Ground 1, the feasible level with the least load path; it placed {Get<int>(placed, "GroundPlaced")}.");
            foreach (int level in new[] { 2, 3, 4 })
            {
                object refused = AtLevel(level);
                if (Get<bool>(refused, "Feasible") || Get<string>(refused, "Rule") != "alignment")
                    throw new InvalidOperationException($"Level {level} gives every tree its own plumb foot under a tilted aim and must be refused on alignment; it came back {(Get<bool>(refused, "Feasible") ? "feasible" : Get<string>(refused, "Rule"))}.");
            }
        }
    }

    private static double AngleDeg(double ax, double ay, double az, double bx, double by, double bz)
    {
        double la = Math.Sqrt((ax * ax) + (ay * ay) + (az * az));
        double lb = Math.Sqrt((bx * bx) + (by * by) + (bz * bz));
        if (la <= 1.0e-12 || lb <= 1.0e-12)
            return 0.0;
        double c = ((ax * bx) + (ay * by) + (az * bz)) / (la * lb);
        return Math.Acos(Math.Min(Math.Max(c, -1.0), 1.0)) * 180.0 / Math.PI;
    }

    private static object Step(string name, Func<object?> call)
    {
        try
        {
            return call()
                ?? throw new InvalidOperationException($"{name} returned null.");
        }
        catch (TargetInvocationException error)
        {
            throw new InvalidOperationException(
                $"{name} threw: {DescribeException(error.InnerException ?? error)}",
                error);
        }
    }

    /// <summary>
    /// <c>MouldGeometry.ConnectedGroups</c> and
    /// <c>MouldGeometry.MemberRunIndex</c>: the two rules the tree outputs of
    /// Mould Animate and Deconstruct branch by.
    ///
    /// Param's complaint was that anchors and principal lines arrived as flat
    /// lists that were "so difficult to organise after". The flat list is not
    /// merely unhelpful, it is lossy: the anchors of a vault are two strips
    /// down opposite sides, and merging them into one list sorted by node index
    /// destroys both which strip a node was on and the order along it. Node
    /// index order is not geometric, so node 7 can sit at the far end of the
    /// far side from node 6.
    ///
    /// So the two things worth measuring are exactly the two things a flat list
    /// threw away. First, that two strips come back as TWO groups and not one.
    /// Second, that each group is WALKED rather than sorted, which is tested on
    /// a strip whose node indices deliberately disagree with its geometry:
    /// index order gives 0,1,2,3,4 and the connectivity gives 0,3,1,4,2, so a
    /// sort cannot pass by accident.
    ///
    /// The member rule has one case that a naive test would miss. A cable can
    /// join two notches of the SAME bar without being part of that bar, by
    /// cutting a corner across the net. Membership is therefore consecutiveness
    /// along the run, not "both ends are on it", and the corner-cutting member
    /// has to land in the infill branch where it belongs.
    /// </summary>
    private static void ValidateOutputGrouping(Assembly plugin)
    {
        Type mouldGeometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry",
            throwOnError: true)!;
        MethodInfo connected = RequirePublicStatic(
            mouldGeometry, "ConnectedGroups");
        MethodInfo runIndex = RequirePublicStatic(
            mouldGeometry, "MemberRunIndex");
        MethodInfo buildAdjacency = RequirePublicStatic(
            mouldGeometry, "BuildAdjacency");

        Type edgeArrayType = buildAdjacency.GetParameters()[1].ParameterType;
        Type edgeType = edgeArrayType.GetElementType()!;

        Array Edges(params (int A, int B)[] pairs)
        {
            Array array = Array.CreateInstance(edgeType, pairs.Length);
            for (int i = 0; i < pairs.Length; i++)
            {
                array.SetValue(
                    Activator.CreateInstance(
                        edgeType, pairs[i].A, pairs[i].B),
                    i);
            }
            return array;
        }

        int[][] Groups(int count, int[] ids, params (int A, int B)[] pairs)
        {
            object neighbours = buildAdjacency.Invoke(
                null, new object?[] { count, Edges(pairs) })!;
            object result = connected.Invoke(
                null, new object?[] { ids, neighbours })!;
            return ((IEnumerable)result)
                .Cast<IEnumerable<int>>()
                .Select(group => group.ToArray())
                .ToArray();
        }

        // TWO STRIPS, the case that made this necessary. Two rows of five,
        // joined along each row and never across, asked for together.
        int[][] sides = Groups(
            10,
            Enumerable.Range(0, 10).ToArray(),
            (0, 1), (1, 2), (2, 3), (3, 4),
            (5, 6), (6, 7), (7, 8), (8, 9));
        if (sides.Length != 2)
        {
            throw new InvalidOperationException(
                "Two anchor strips down opposite sides are TWO groups; "
                + $"{sides.Length} came back. One group means the strips were "
                + "merged, which is the flat list this replaces.");
        }
        if (!sides[0].SequenceEqual(new[] { 0, 1, 2, 3, 4 }) ||
            !sides[1].SequenceEqual(new[] { 5, 6, 7, 8, 9 }))
        {
            throw new InvalidOperationException(
                "The two strips came back as "
                + $"[{string.Join(",", sides[0])}] and "
                + $"[{string.Join(",", sides[1])}]; expected 0..4 and 5..9, "
                + "each whole and in order.");
        }

        // WALKED, NOT SORTED. The chain 0-3-1-4-2 is deliberately laid out so
        // that node index order and connectivity order disagree, so a sort
        // cannot pass this by luck.
        int[][] tangled = Groups(
            5,
            new[] { 0, 1, 2, 3, 4 },
            (0, 3), (3, 1), (1, 4), (4, 2));
        if (tangled.Length != 1)
        {
            throw new InvalidOperationException(
                $"One connected chain is one group; {tangled.Length} came "
                + "back.");
        }
        if (!tangled[0].SequenceEqual(new[] { 0, 3, 1, 4, 2 }))
        {
            throw new InvalidOperationException(
                "A strip must come back WALKED, in the order its members "
                + "connect: expected 0,3,1,4,2 and got "
                + $"{string.Join(",", tangled[0])}. Getting 0,1,2,3,4 means it "
                + "was sorted by node index, which is not a geometric order "
                + "and is the thing the flat list already did.");
        }

        // THE SAME EDGE TWICE, which is the ordinary case rather than a freak
        // one: GroupingAdjacency unions the plan's edges onto the solved ones,
        // so every edge present in both graphs arrives twice. Counting list
        // entries rather than distinct neighbours made BOTH ends of an open
        // strip count two, so no end was recognised and the walk fell back to
        // the lowest index. The chain here is 2-0-3-1-4, whose lowest index
        // sits in the MIDDLE, so a walk that starts there dead-ends after one
        // step and the rest is appended by index.
        int[][] doubled = Groups(
            5,
            new[] { 0, 1, 2, 3, 4 },
            (2, 0), (0, 3), (3, 1), (1, 4),
            (2, 0), (0, 3), (3, 1), (1, 4));
        if (doubled.Length != 1 ||
            !doubled[0].SequenceEqual(new[] { 2, 0, 3, 1, 4 }))
        {
            throw new InvalidOperationException(
                "A strip whose edges are supplied twice must still walk end to "
                + "end: expected one group of 2,0,3,1,4 and got "
                + $"{doubled.Length} group(s), the first ["
                + string.Join(
                    ",",
                    doubled.Length > 0 ? doubled[0] : Array.Empty<int>())
                + "]. Getting 0,2,... means the duplicate entries hid the ends "
                + "of the strip from the walk.");
        }

        // A CLOSED LOOP has no end to start from, and must still come back
        // whole and walked round rather than split.
        int[][] loop = Groups(
            4,
            new[] { 0, 1, 2, 3 },
            (0, 1), (1, 2), (2, 3), (3, 0));
        if (loop.Length != 1 || loop[0].Length != 4)
        {
            throw new InvalidOperationException(
                $"A closed boundary loop is one group of four; got "
                + $"{loop.Length} group(s) of "
                + $"{string.Join("/", loop.Select(g => g.Length))}.");
        }
        if (!loop[0].SequenceEqual(new[] { 0, 1, 2, 3 }) &&
            !loop[0].SequenceEqual(new[] { 0, 3, 2, 1 }))
        {
            throw new InvalidOperationException(
                "A loop must come back walked round, either way about: got "
                + $"{string.Join(",", loop[0])}.");
        }

        // THE WRONG-GRAPH REGRESSION, which showed as 42 branches of one node
        // each.
        //
        // A TNA analysis topology carries no edge between two supports: such
        // an edge joins two fixed nodes, contributes no unknown, and the
        // network never needs it. Six anchors joined only to the interior and
        // never to each other IS that graph. Grouping over it can only give
        // singletons, and asserting it here says the walk is not at fault, so
        // nobody goes hunting for the bug inside it.
        int[][] byNetOnly = Groups(
            10,
            new[] { 0, 1, 2, 6, 7, 8 },
            // every anchor to an interior node, and no anchor to an anchor
            (0, 3), (1, 4), (2, 5), (6, 3), (7, 4), (8, 5));
        if (byNetOnly.Length != 6)
        {
            throw new InvalidOperationException(
                "Anchors joined only to the interior must come back as six "
                + $"singletons; got {byNetOnly.Length} group(s). This case "
                + "documents WHY the solved net is the wrong graph to group "
                + "by, so it has to keep reproducing.");
        }

        // The same anchors over the UNION with the plan as drawn, where each
        // side IS continuous. Two sides, three nodes each, walked in order.
        int[][] byUnion = Groups(
            10,
            new[] { 0, 1, 2, 6, 7, 8 },
            (0, 3), (1, 4), (2, 5), (6, 3), (7, 4), (8, 5),
            (0, 1), (1, 2),      // side A, joined in the plan
            (6, 7), (7, 8));     // side B, joined in the plan
        if (byUnion.Length != 2)
        {
            throw new InvalidOperationException(
                "Adding the plan's own side edges must give TWO strips; got "
                + $"{byUnion.Length}. That union is the fix: group over the "
                + "plan together with the solved net, not the net alone.");
        }
        if (!byUnion[0].SequenceEqual(new[] { 0, 1, 2 }) ||
            !byUnion[1].SequenceEqual(new[] { 6, 7, 8 }))
        {
            throw new InvalidOperationException(
                "The two sides came back as "
                + $"[{string.Join(",", byUnion[0])}] and "
                + $"[{string.Join(",", byUnion[1])}]; expected 0,1,2 and "
                + "6,7,8, each whole and walked in order.");
        }

        // Coverage note: this measures the GROUPING, which is where the
        // observable behaviour is. MouldGeometry.GroupingAdjacency, which
        // unions the two edge sets and guards on the pattern carrying the same
        // vertex count, is exercised only through the components; a fixture
        // for it needs a whole nested ResultDto.

        // MEMBER OWNERSHIP. Two bars, and four members put to them.
        var runs = new List<IReadOnlyList<int>>
        {
            new List<int> { 0, 1, 2, 3 },
            new List<int> { 10, 11, 12 },
        };
        Array members = Edges(
            (0, 1),    // bar 0
            (2, 1),    // bar 0, given backwards
            (10, 11),  // bar 1
            (0, 2),    // BOTH ends on bar 0, but not consecutive: infill
            (5, 6));   // nowhere near a bar: infill
        var owner = (int[])runIndex.Invoke(
            null, new object?[] { members, runs })!;
        var expected = new[] { 0, 0, 1, -1, -1 };
        if (!owner.SequenceEqual(expected))
        {
            throw new InvalidOperationException(
                $"Members belong to [{string.Join(",", expected)}]; got "
                + $"[{string.Join(",", owner)}]. Index 1 is the same member "
                + "given end for end and must still be bar 0. Index 3 joins "
                + "two notches of bar 0 by cutting the corner between them, "
                + "which makes it INFILL: membership is consecutiveness along "
                + "the run, not both ends lying on it.");
        }
    }

    /// <summary>
    /// What EI is still for, and the lean rule, both measured.
    ///
    /// Nothing chooses where a column stands by stiffness any more: every
    /// notch is held, so there is no arrangement for EI to pick between and
    /// no way for it to tune a placement while claiming not to. EI is asked
    /// for on Monitor and nowhere else, and it has one job left, which has
    /// to be exact: DEFLECTION SCALES AS ONE OVER EI. The beam knows the
    /// SHAPE of the sag between the notches a column holds, and that exact
    /// reciprocal is what turns the shape into millimetres, which is the
    /// unit a build tolerance is written in.
    ///
    /// The other half is LeanFromVertical, the rule the trunks are held to.
    /// A Ground level that would lean a trunk past sixty degrees is refused
    /// and the next lower one tried, so the measurement that decides it is
    /// checked against angles computed by hand.
    /// </summary>
    private static void ValidateStiffnessSeparation(Assembly plugin)
    {
        Type solver = plugin.GetType(
            "Ananke.COMPAS.Native.Components.BeamSolver", throwOnError: true)!;
        MethodInfo response = RequirePublicStatic(solver, "Response");

        const int stations = 31;
        var arc = new double[stations];
        var load = new double[stations];
        for (int i = 0; i < stations; i++)
        {
            double x = (double)i / (stations - 1);
            arc[i] = x;
            // Deliberately NOT uniform. A flat load is the one case where a
            // dependence on stiffness could hide behind symmetry.
            load[i] = 1.0 + (0.4 * Math.Sin(6.0 * x));
        }

        // Deflection is exactly reciprocal in EI.
        var supports = new[] { 0, stations / 2, stations - 1 };
        double[] Deflect(double EI)
        {
            object result = response.Invoke(
                null, new object?[] { arc, load, supports, EI })!;
            return (double[])result.GetType()
                .GetField("Item1")!.GetValue(result)!;
        }

        double[] one = Deflect(1.0);
        double[] four = Deflect(4.0);
        for (int i = 0; i < one.Length; i++)
        {
            double expected = one[i] / 4.0;
            if (Math.Abs(four[i] - expected) > 1.0e-9 * (1.0 + Math.Abs(expected)))
            {
                throw new InvalidOperationException(
                    $"Deflection must scale as one over EI: node {i} gave "
                    + $"{four[i]:G6} at EI 4 against {expected:G6} expected "
                    + $"from {one[i]:G6} at EI 1. Without that exact "
                    + "reciprocal, one EI cannot convert the placement's "
                    + "bending shape into millimetres.");
            }
        }

        // The lean rule the trunks are held to.
        Type geometry = plugin.GetType(
            "Ananke.COMPAS.Native.Components.MouldGeometry", throwOnError: true)!;
        MethodInfo lean = RequirePublicStatic(geometry, "LeanFromVertical");
        Type point3d = lean.GetParameters()[0].ParameterType;
        double Lean(double dx, double rise)
        {
            object foot = Activator.CreateInstance(point3d, 0.0, 0.0, 0.0)!;
            object top = Activator.CreateInstance(point3d, dx, 0.0, rise)!;
            return (double)lean.Invoke(null, new[] { foot, top })!;
        }

        if (Math.Abs(Lean(0.0, 1.0)) > 1.0e-9)
            throw new InvalidOperationException("A plumb member leans 0 degrees.");
        if (Math.Abs(Lean(1.0, 1.0) - 45.0) > 1.0e-9)
            throw new InvalidOperationException("One across, one up, is 45 degrees.");
        if (Math.Abs(Lean(Math.Sqrt(3.0), 1.0) - 60.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Root three across, one up, is exactly 60 degrees, which is "
                + "the limit itself and so the value that decides whether a "
                + "Ground level is refused.");
        }
    }

    private static MethodInfo RequirePublicStatic(Type owner, string name) =>
        owner.GetMethod(
            name,
            BindingFlags.Public | BindingFlags.Static)
        ?? throw new InvalidOperationException(
            $"{owner.Name}.{name} was not found.");

    private static MethodInfo RequireStatic(Type owner, string name) =>
        owner.GetMethod(
            name,
            BindingFlags.NonPublic | BindingFlags.Static)
        ?? throw new InvalidOperationException(
            $"{owner.Name}.{name} was not found.");

    private static void CheckOneAim(
        MethodInfo loads,
        MethodInfo transverse,
        MethodInfo armAim,
        Type point3d,
        Type incidentArray,
        Type incidentList,
        double farX,
        double farZ,
        bool twoSided,
        double expectedX,
        double expectedZ,
        string label)
    {
        // 0,1,2 are the bar along Y at x = 0, z = 1. 3 and 4 are the far ends
        // of the middle notch's infill cables.
        var coordinates = new List<(double X, double Y, double Z)>
        {
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 1.0),
            (0.0, 2.0, 1.0),
            (farX, 1.0, farZ),
            (-farX, 1.0, farZ),
        };
        Array nodes = Array.CreateInstance(point3d, coordinates.Count);
        for (int index = 0; index < coordinates.Count; index++)
        {
            (double x, double y, double z) = coordinates[index];
            nodes.SetValue(Activator.CreateInstance(point3d, x, y, z), index);
        }

        // Positive is tension, so each cable pulls node 1 toward its far end.
        var cables = new List<(int Node, int Other)> { (1, 3) };
        if (twoSided)
            cables.Add((1, 4));

        Array incident = Array.CreateInstance(
            incidentList, coordinates.Count);
        MethodInfo add = incidentList.GetMethod("Add")
            ?? throw new InvalidOperationException("List.Add was not found.");
        for (int index = 0; index < coordinates.Count; index++)
            incident.SetValue(Activator.CreateInstance(incidentList), index);
        foreach ((int node, int other) in cables)
        {
            add.Invoke(
                incident.GetValue(node),
                new object[] { (other, 100.0) });
            add.Invoke(
                incident.GetValue(other),
                new object[] { (node, 100.0) });
        }
        // The bar's own edges, which BarLoads must leave out.
        add.Invoke(incident.GetValue(0), new object[] { (1, 50.0) });
        add.Invoke(incident.GetValue(1), new object[] { (0, 50.0) });
        add.Invoke(incident.GetValue(1), new object[] { (2, 50.0) });
        add.Invoke(incident.GetValue(2), new object[] { (1, 50.0) });

        var bar = new List<int> { 0, 1, 2 };
        object pull = Step("BarLoads", () => loads.Invoke(
            null, new object?[] { bar, nodes, incident }));
        object across = Step("BarTransverse", () => transverse.Invoke(
            null, new object?[] { bar, nodes, pull }));

        object loaded = ((Array)across).GetValue(1)
            ?? throw new InvalidOperationException(
                "BarTransverse returned nothing for the loaded notch.");
        object direction = Step("AimFrom", () => armAim.Invoke(
            null, new object?[] { loaded }));
        Type vector3d = direction.GetType();
        double aimX = (double)vector3d.GetProperty("X")!.GetValue(direction)!;
        double aimY = (double)vector3d.GetProperty("Y")!.GetValue(direction)!;
        double aimZ = (double)vector3d.GetProperty("Z")!.GetValue(direction)!;

        const double tolerance = 1.0e-9;
        if (Math.Abs(aimX - expectedX) > tolerance ||
            Math.Abs(aimY) > tolerance ||
            Math.Abs(aimZ - expectedZ) > tolerance)
        {
            throw new InvalidOperationException(
                $"The column for a {label} must aim ("
                + $"{expectedX:G6}, 0, {expectedZ:G6}); it aims "
                + $"({aimX:G6}, {aimY:G6}, {aimZ:G6}). A wrong sign on X means "
                + "the column leans WITH the pull instead of against it.");
        }
    }

    /// <summary>
    /// <c>PrincipalRunFinder.FromCurves</c>: one bar, however many times it
    /// was traced.
    ///
    /// The same physical line arrives twice more easily than it looks. From the
    /// anchors, a line traced from one strip reaches the other, so the strip
    /// opposite traces it backwards. From drawn curves, two curves laid near
    /// the same run of nodes both snap to it. The duplicate is INVISIBLE in the
    /// viewport, because the second bar draws exactly on top of the first, and
    /// it is ruinous downstream: each bar is given its own full set of columns,
    /// each mirrored about its own slightly different midpoint, so the columns
    /// land on one line at two offset spacings and read as hopelessly
    /// lopsided.
    ///
    /// This is measured because the fix was written once for the ANCHOR path
    /// and shipped, and it fixed nothing at all for a definition whose lines
    /// come from curves. A rule that has two callers needs a check that covers
    /// both, so this drives the curve path and the shared rule under it.
    ///
    /// Five nodes in a row with a curve down them, twice, is one bar. A second
    /// curve down a genuinely different row is a second bar.
    /// </summary>
    private static void ValidateRunDeduplication(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        MethodInfo dedupe = finder.GetMethod(
            "Deduplicate", BindingFlags.NonPublic | BindingFlags.Static)!;

        int Kept(params int[][] runs)
        {
            var input = new List<List<int>>();
            foreach (int[] run in runs)
                input.Add(new List<int>(run));
            object result = dedupe.Invoke(null, new object?[] { input })!;
            return ((IEnumerable)result).Cast<object>().Count();
        }

        // The same five nodes, traced twice, ending one node apart. One bar.
        int doubled = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 4, 3, 2, 1, 0 });
        if (doubled != 1)
        {
            throw new InvalidOperationException(
                "One line traced from both ends is one bar; "
                + $"{doubled} came back.");
        }

        // The realistic case: the two traces disagree at their ends, which is
        // exactly why matching endpoints could not catch this.
        int ragged = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 5, 3, 2, 1, 0 });
        if (ragged != 1)
        {
            throw new InvalidOperationException(
                "Two traces of one line that finish on DIFFERENT nodes are "
                + $"still one bar; {ragged} came back. Matching their ends is "
                + "what failed before, so this is the case that matters.");
        }

        // A genuinely separate line must survive.
        int separate = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 10, 11, 12, 13, 14 });
        if (separate != 2)
        {
            throw new InvalidOperationException(
                "Two lines sharing no nodes are two bars; "
                + $"{separate} came back. Deduplication must not swallow a "
                + "real second line.");
        }

        // Crossing at one node is not the same line.
        int crossing = Kept(
            new[] { 0, 1, 2, 3, 4 },
            new[] { 20, 21, 2, 22, 23 });
        if (crossing != 2)
        {
            throw new InvalidOperationException(
                "Two lines that merely CROSS share one node and are still two "
                + $"bars; {crossing} came back.");
        }
    }

    /// <summary>
    /// The anchor derivation is deleted, and stays deleted. A principal line
    /// is a decision the author draws into Pattern. When Supports derived
    /// lines whenever Pattern carried none, a definition that forgot its
    /// curves quietly got bars it never asked for, which is a second author
    /// of one fact. This pins the deletion so it cannot creep back under
    /// another refactor.
    /// </summary>
    private static void ValidateDerivationRemoved(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static | BindingFlags.Instance;
        if (finder.GetMethods(Any).Any(m => m.Name == "DeriveFromAnchors"))
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.DeriveFromAnchors still exists. Principal "
                + "lines are input only; nothing derives them from anchors.");
        }
        if (finder.GetMethod("FromCurves", Any) is null)
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.FromCurves is missing; it is the one way in.");
        }
        if (finder.GetMethod("Deduplicate", Any) is null)
        {
            throw new InvalidOperationException(
                "PrincipalRunFinder.Deduplicate is missing; it is the safety net "
                + "for two curves snapping to one run.");
        }
    }

    /// <summary>
    /// <c>PrincipalRunFinder.Outcome</c>: what Pattern says about the curves
    /// it was handed, as one pure function of three counts, so the error path
    /// is measured rather than trusted. The error case matters most: curves
    /// wired and none placed used to fall through silently to no runs, and the
    /// first sign was Columns with nothing to stand under.
    /// </summary>
    private static void ValidatePrincipalOutcome(Assembly plugin)
    {
        Type finder = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PrincipalRunFinder",
            throwOnError: true)!;
        MethodInfo outcome = finder.GetMethod(
            "Outcome", BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "PrincipalRunFinder.Outcome(int, int, int) is missing.");

        (string Severity, string Message) Run(int supplied, int unmatched, int kept)
        {
            object result = outcome.Invoke(
                null, new object?[] { supplied, unmatched, kept })!;
            Type type = result.GetType();
            string severity = (string)type.GetProperty("Severity")!
                .GetValue(result)!;
            string message = (string)type.GetProperty("Message")!
                .GetValue(result)!;
            return (severity, message);
        }

        void Expect(
            (int, int, int) counts, string severity, string contains)
        {
            (int supplied, int unmatched, int kept) = counts;
            (string got, string message) = Run(supplied, unmatched, kept);
            if (got != severity)
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) should be "
                    + $"'{severity}'; it was '{got}' with message '{message}'.");
            }
            if (contains.Length > 0 &&
                !message.Contains(contains, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) message should "
                    + $"contain '{contains}'; it was '{message}'.");
            }
            if (contains.Length == 0 && message.Length != 0)
            {
                throw new InvalidOperationException(
                    $"Outcome({supplied}, {unmatched}, {kept}) should carry no "
                    + $"message; it was '{message}'.");
            }
        }

        Expect((0, 0, 0), "none", "");
        Expect((2, 0, 2), "none", "");
        Expect((3, 1, 2), "warning", "1 of 3");
        Expect((3, 0, 2), "remark", "merged");
        Expect((2, 2, 0), "error", "No Pattern");
        Expect((2, 0, 0), "error", "No Pattern");
    }

    /// <summary>
    /// <c>ParameterIdentity.Restore</c> after a document read: a mapping the
    /// plugin REGISTERED wins over the archive, a mapping it did not register
    /// belongs to the author.
    ///
    /// Pattern's Principal Lines port shipped without its Flatten and gained
    /// it later. Grasshopper resets every mapping from the archive on load,
    /// so without this rule every definition saved before the flatten
    /// reopened with P unflattened and one Pattern per branch of curves. The
    /// first fix re-asserted EVERY port's registered mapping, which would
    /// have wiped any graft or flatten the author set by hand, on every port
    /// of every component, on every reopen. Both halves are measured here by
    /// playing the archive's part: leave the ports as a load would, call
    /// Restore, read them back.
    /// </summary>
    private static void ValidateRegisteredMappingWins(Assembly plugin)
    {
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static;
        Type identity = plugin.GetType(
            "Ananke.COMPAS.Native.Components.ParameterIdentity",
            throwOnError: true)!;
        MethodInfo capture = identity.GetMethod("Capture", Any)
            ?? throw new InvalidOperationException(
                "ParameterIdentity.Capture is missing.");
        MethodInfo restore = identity.GetMethod("Restore", Any)
            ?? throw new InvalidOperationException(
                "ParameterIdentity.Restore is missing.");

        Type patternType = plugin.GetType(
            "Ananke.COMPAS.Native.Components.PatternComponent",
            throwOnError: true)!;
        object pattern = Activator.CreateInstance(patternType)
            ?? throw new InvalidOperationException(
                "PatternComponent could not be constructed.");
        try
        {
            object parameters = patternType.GetProperty("Params")!
                .GetValue(pattern)!;
            object inputs = parameters.GetType().GetProperty("Input")!
                .GetValue(parameters)!;
            var list = (IList)inputs;
            object principal = list[4]!;
            object mode = list[1]!;
            PropertyInfo principalMapping =
                principal.GetType().GetProperty("DataMapping")!;
            PropertyInfo modeMapping =
                mode.GetType().GetProperty("DataMapping")!;
            Type mappingType = principalMapping.PropertyType;
            object none = Enum.Parse(mappingType, "None");
            object flatten = Enum.Parse(mappingType, "Flatten");
            object graft = Enum.Parse(mappingType, "Graft");

            if (!Equals(principalMapping.GetValue(principal), flatten))
            {
                throw new InvalidOperationException(
                    "Pattern's Principal Lines port must register Flatten; "
                    + $"it registers {principalMapping.GetValue(principal)}.");
            }
            if (!Equals(modeMapping.GetValue(mode), none))
            {
                throw new InvalidOperationException(
                    "Pattern's Mode port must register no mapping for this "
                    + "check to mean anything; it registers "
                    + $"{modeMapping.GetValue(mode)}.");
            }

            // Capture runs before the archive is read, on the registered
            // identity, exactly as the Read override does.
            object snapshots = capture.Invoke(null, new[] { inputs })!;

            // The archive's part: an old definition saved P before it
            // flattened, and the author grafted Mode by hand.
            principalMapping.SetValue(principal, none);
            modeMapping.SetValue(mode, graft);

            restore.Invoke(null, new object?[] { inputs, snapshots });

            if (!Equals(principalMapping.GetValue(principal), flatten))
            {
                throw new InvalidOperationException(
                    "The registered Flatten on Principal Lines did not win over "
                    + "the archived None; definitions saved before the flatten "
                    + "reopen unflattened.");
            }
            if (!Equals(modeMapping.GetValue(mode), graft))
            {
                throw new InvalidOperationException(
                    "The author's graft on an unmapped port was wiped by "
                    + "Restore; a registered None must not be re-asserted.");
            }
        }
        finally
        {
            if (pattern is IDisposable disposable)
                disposable.Dispose();
        }
    }

    /// <summary>
    /// Pattern is the only component that previews principal runs. Every
    /// other component used to hold a <c>List&lt;Line&gt;</c> of red bars and
    /// paint it over its own preview, so two components on one canvas showed
    /// each bar twice: the "dual lining" that read as a doubled principal
    /// line. The rule is mechanical: an instance field of type List of Line
    /// whose name contains "Principal" exists on PatternComponent and on no
    /// other component, and the helper that read runs off a Result for the
    /// others, <c>TnaWorkflowPreview.ResultPrincipalLines</c>, is gone.
    /// </summary>
    private static void ValidatePrincipalPreviewOwner(
        Assembly plugin,
        Type[] componentTypes)
    {
        const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Static | BindingFlags.Instance;
        Type preview = plugin.GetType(
            "Ananke.COMPAS.Native.Components.TnaWorkflowPreview",
            throwOnError: true)!;
        if (preview.GetMethods(Any).Any(m => m.Name == "ResultPrincipalLines"))
        {
            throw new InvalidOperationException(
                "TnaWorkflowPreview.ResultPrincipalLines still exists. Pattern is "
                + "the only component that previews principal runs, and it reads "
                + "a topology, not a Result.");
        }

        const BindingFlags Fields = BindingFlags.Public | BindingFlags.NonPublic
            | BindingFlags.Instance | BindingFlags.DeclaredOnly;
        var owners = new List<string>();
        foreach (Type componentType in componentTypes)
        {
            for (Type? at = componentType; at is not null; at = at.BaseType)
            {
                foreach (FieldInfo field in at.GetFields(Fields))
                {
                    if (!field.Name.Contains(
                            "Principal", StringComparison.OrdinalIgnoreCase))
                        continue;
                    Type type = field.FieldType;
                    bool listOfLine = type.IsGenericType
                        && type.GetGenericTypeDefinition() == typeof(List<>)
                        && type.GetGenericArguments()[0].Name == "Line";
                    if (listOfLine)
                        owners.Add(componentType.FullName ?? componentType.Name);
                }
            }
        }

        const string Pattern = "Ananke.COMPAS.Native.Components.PatternComponent";
        if (!owners.Contains(Pattern))
        {
            throw new InvalidOperationException(
                "PatternComponent holds no principal-line preview field; it is "
                + "the one component that must.");
        }
        string[] others = owners.Where(o => o != Pattern).Distinct().ToArray();
        if (others.Length > 0)
        {
            throw new InvalidOperationException(
                "Only Pattern previews principal runs; these still hold a "
                + $"principal preview field: {string.Join(", ", others)}.");
        }
    }

    private static Type RequireComponentType(Assembly plugin, string typeName)
    {
        const string ComponentsNamespace = "Ananke.COMPAS.Native.Components";
        return plugin.GetType($"{ComponentsNamespace}.{typeName}", throwOnError: true)
            ?? throw new InvalidOperationException(
                $"Type '{ComponentsNamespace}.{typeName}' was not found.");
    }

    /// <summary>
    /// Finding 1 of the 2026-08-20 plugin sweep: a negative Courses value
    /// becomes a "c-1p0"-style key deep in the studio's
    /// tessellation.from_document import (which pins course &gt;= 0 and
    /// refuses it), so ExportComponent now catches it itself, naming
    /// every offending index and value. <c>SolveInstance</c> needs a live
    /// <c>IGH_DataAccess</c>/Grasshopper document this harness never
    /// launches (it never calls SolveInstance on anything, only
    /// constructors and static contract methods), so the standalone
    /// guard behind that check -- <c>HasNegativeCourse</c> -- is as far
    /// as this repo's reflection-based pattern reaches; the component
    /// wiring around it (AddRuntimeMessage, "no file written") is not
    /// exercised here.
    /// </summary>
    private static void ValidateExportCoursesValidation(Assembly plugin)
    {
        Type exportType = RequireComponentType(plugin, "ExportComponent");
        MethodInfo method = exportType.GetMethod(
            "HasNegativeCourse",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ExportComponent.HasNegativeCourse was not found.");

        object?[] negativeArgs = { new List<int> { 0, -1, 2, -3 }, null };
        var flagged = (bool)method.Invoke(null, negativeArgs)!;
        var detail = (string)negativeArgs[1]!;
        if (!flagged)
        {
            throw new InvalidOperationException(
                "HasNegativeCourse did not flag a Courses list containing " +
                "negative values.");
        }
        if (!detail.Contains("index 1 = -1", StringComparison.Ordinal) ||
            !detail.Contains("index 3 = -3", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "HasNegativeCourse did not name every offending index " +
                $"and value; received '{detail}'.");
        }

        object?[] validArgs = { new List<int> { 0, 1, 2 }, null };
        var flaggedValid = (bool)method.Invoke(null, validArgs)!;
        if (flaggedValid)
        {
            throw new InvalidOperationException(
                "HasNegativeCourse flagged a Courses list with no " +
                "negative values.");
        }
    }

    /// <summary>
    /// Finding 2 of the 2026-08-20 plugin sweep: BuildTessellationJson now
    /// serialises through the shared ContractJson.Options rather than
    /// default JsonSerializer options. Every field in this payload is
    /// non-null and every key is already a camelCase literal, so no
    /// option ContractJson.Options sets actually changes a byte for this
    /// shape (confirmed separately, outside this harness, by comparing
    /// the built .gha's output before and after the change); what this
    /// asserts is that the exact schema the studio's
    /// tessellation.from_document expects -- key/course/outline per
    /// cell, the bench.tessellation/1 envelope -- still comes out
    /// byte-for-byte as written.
    /// </summary>
    private static void ValidateExportTessellationJsonOptions(Assembly plugin)
    {
        Type exportType = RequireComponentType(plugin, "ExportComponent");
        Type cellType = RequireComponentType(plugin, "TessellationCell");
        MethodInfo method = exportType.GetMethod(
            "BuildTessellationJson",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ExportComponent.BuildTessellationJson was not found.");

        var outline = new List<double[]>
        {
            new[] { 0.0, 0.0 },
            new[] { 1.0, 0.0 },
            new[] { 0.0, 1.0 }
        };
        object cell = Activator.CreateInstance(cellType, 0, outline)
            ?? throw new InvalidOperationException(
                $"Could not construct {cellType.FullName}.");
        Type cellListType = typeof(List<>).MakeGenericType(cellType);
        object cellList = Activator.CreateInstance(cellListType)
            ?? throw new InvalidOperationException(
                $"Could not construct {cellListType.FullName}.");
        MethodInfo addMethod = cellListType.GetMethod("Add")
            ?? throw new InvalidOperationException(
                $"{cellListType.FullName} does not expose Add.");
        addMethod.Invoke(cellList, new[] { cell });

        var json = method.Invoke(null, new object[] { cellList, 1.0 }) as string
            ?? throw new InvalidOperationException(
                "BuildTessellationJson returned an unexpected type.");
        const string expected =
            "{\"schema\":\"bench.tessellation/1\",\"units\":\"m\"," +
            "\"domain\":\"plan\",\"pattern\":\"authored\",\"cells\":[" +
            "{\"key\":\"c0p0\",\"course\":0," +
            "\"outline\":[[0,0],[1,0],[0,1]]}]}";
        if (!string.Equals(json, expected, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "BuildTessellationJson output changed shape; expected " +
                $"'{expected}', received '{json}'.");
        }

        // A millimetre document. The sidecar declares metres and the
        // studio reads metres only, refusing any other declaration
        // outright, so the corners have to BE metres by the time they
        // are written. Before this factor existed the component wrote
        // document coordinates under a metre label, which the studio
        // accepts without complaint and reads a thousand times too
        // large: the one shape of unit error that never raises.
        var millimetres =
            method.Invoke(null, new object[] { cellList, 0.001 }) as string
            ?? throw new InvalidOperationException(
                "BuildTessellationJson returned an unexpected type.");
        const string expectedMillimetres =
            "{\"schema\":\"bench.tessellation/1\",\"units\":\"m\"," +
            "\"domain\":\"plan\",\"pattern\":\"authored\",\"cells\":[" +
            "{\"key\":\"c0p0\",\"course\":0," +
            "\"outline\":[[0,0],[0.001,0],[0,0.001]]}]}";
        if (!string.Equals(millimetres, expectedMillimetres, StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "BuildTessellationJson did not convert document units to " +
                $"metres; expected '{expectedMillimetres}', received " +
                $"'{millimetres}'.");
        }
    }

    private static void ValidateExportPlan(Assembly plugin)
    {
        Type plan = plugin.GetType("Ananke.COMPAS.Native.Components.ExportPlan", throwOnError: true)!;
        MethodInfo kinds = RequirePublicStatic(plan, "Kinds");
        string Show(bool cells, bool columns) =>
            string.Join(",", (string[])kinds.Invoke(null, new object?[] { cells, columns })!);
        if (Show(false, false) != "contract,compas") throw new InvalidOperationException($"No cells, no columns: contract,compas; got {Show(false, false)}.");
        if (Show(true, false) != "contract,compas,tessellation") throw new InvalidOperationException($"Cells add tessellation; got {Show(true, false)}.");
        if (Show(false, true) != "contract,compas,columns") throw new InvalidOperationException($"Columns add columns; got {Show(false, true)}.");
        if (Show(true, true) != "contract,compas,tessellation,columns") throw new InvalidOperationException($"All four in order; got {Show(true, true)}.");

        // The study name rule. A Name is one path segment because it is
        // both a file name stem inside the folder the author chose and
        // one segment of the studio's route: a separator or a dot-dot in
        // it writes the set somewhere the author never named, quietly and
        // successfully, and reaches a route nobody asked for.
        MethodInfo segment = RequirePublicStatic(plan, "NameIsOneSegment");
        bool OneSegment(string name) => (bool)segment.Invoke(null, new object?[] { name })!;
        if (!OneSegment("study-1"))
            throw new InvalidOperationException("An ordinary study name is one segment.");
        foreach (string refused in new[] { "..", ".", @"a\b", "a/b", "a:b", "a?b", "", "   " })
        {
            if (OneSegment(refused))
            {
                throw new InvalidOperationException(
                    $"'{refused}' is not one path segment and must be refused: "
                    + "a Name carrying a separator, a colon, a dot-dot or a "
                    + "character no file name may hold escapes the folder the "
                    + "author chose.");
            }
        }
    }

    private static void ValidateColumnsMesh(Assembly plugin)
    {
        Type mesh = plugin.GetType("Ananke.COMPAS.Native.Components.ColumnsMesh", throwOnError: true)!;
        MethodInfo build = RequirePublicStatic(mesh, "Build");
        Type memberList = build.GetParameters()[0].ParameterType;   // IReadOnlyList<(Point3d, Point3d, double)>
        Type tuple = memberList.GetGenericArguments()[0];
        Type point3d = tuple.GetGenericArguments()[0];
        object P(double x, double y, double z) => Activator.CreateInstance(point3d, x, y, z)!;
        object Member(double x0, double y0, double z0, double x1, double y1, double z1, double f) =>
            Activator.CreateInstance(tuple, P(x0, y0, z0), P(x1, y1, z1), f)!;
        object ListOf(params object[] members)
        {
            var list = (System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(tuple))!;
            foreach (object m in members) list.Add(m);
            return list;
        }
        (double[][] V, int[][] F) Run(object members, double radius)
        {
            object result = build.Invoke(null, new object?[] { members, radius, 6 })!;
            Type t = result.GetType();
            return ((double[][])t.GetField("Item1")!.GetValue(result)!, (int[][])t.GetField("Item2")!.GetValue(result)!);
        }

        (double[][] v, int[][] f) = Run(ListOf(Member(0, 0, 0, 0, 0, 2, 5.0)), 0.1);
        if (v.Length != 12) throw new InvalidOperationException($"A six-sided prism has 12 vertices; got {v.Length}.");
        if (f.Count(x => x.Length == 4) != 6 || f.Count(x => x.Length == 3) != 8)
            throw new InvalidOperationException($"Six side quads and eight cap triangles; got {f.Count(x => x.Length == 4)} quads and {f.Count(x => x.Length == 3)} triangles.");
        foreach (double[] p in v)
        {
            double r = Math.Sqrt((p[0] * p[0]) + (p[1] * p[1]));
            if (Math.Abs(r - 0.1) > 1.0e-9) throw new InvalidOperationException($"Every vertex sits at the radius; one is at {r:0.######}.");
            if (Math.Abs(p[2]) > 1.0e-9 && Math.Abs(p[2] - 2.0) > 1.0e-9) throw new InvalidOperationException($"Cap vertices sit at the member's ends; one is at z {p[2]:0.######}.");
        }
        foreach (int[] face in f)
            foreach (int i in face)
                if (i < 0 || i >= v.Length) throw new InvalidOperationException("A face indexes outside the vertices.");
        (double[][] none, int[][] noneF) = Run(ListOf(Member(1, 1, 1, 1, 1, 1, 1.0)), 0.1);
        if (none.Length != 0 || noneF.Length != 0) throw new InvalidOperationException("A zero-length member draws nothing.");
        (double[][] two, int[][] twoF) = Run(ListOf(Member(0, 0, 0, 0, 0, 2, 1.0), Member(1, 0, 0, 3, 0, 0, 1.0)), 0.1);
        if (two.Length != 24) throw new InvalidOperationException($"Two members give 24 vertices; got {two.Length}.");
        if (twoF.SelectMany(x => x).Any(i => i < 0 || i >= 24)) throw new InvalidOperationException("Two members' faces index within 24 vertices.");

        // A DIAGONAL member. Every case above lies on an axis, so all of
        // them would pass against a prism whose cap circle was drawn in
        // world XY and only stretched along the member: the circle has to
        // be perpendicular to the MEMBER, and this is where that shows.
        (double[][] diagonal, int[][] _) = Run(ListOf(Member(0, 0, 0, 1, 1, 1, 1.0)), 0.1);
        if (diagonal.Length != 12)
            throw new InvalidOperationException($"A diagonal member is a prism too; got {diagonal.Length} vertices.");
        double unit = 1.0 / Math.Sqrt(3.0);
        for (int i = 0; i < diagonal.Length; i++)
        {
            double end = i < 6 ? 0.0 : 1.0;
            double ox = diagonal[i][0] - end;
            double oy = diagonal[i][1] - end;
            double oz = diagonal[i][2] - end;
            double along = (ox * unit) + (oy * unit) + (oz * unit);
            double across = Math.Sqrt((ox * ox) + (oy * oy) + (oz * oz));
            if (Math.Abs(along) > 1.0e-9)
                throw new InvalidOperationException(
                    $"Cap vertex {i} is {along:0.#########} off its cap plane: the "
                    + "circle must be perpendicular to the member, not to world Z.");
            if (Math.Abs(across - 0.1) > 1.0e-9)
                throw new InvalidOperationException(
                    $"Cap vertex {i} sits at {across:0.#########} from the axis point, not at the radius asked.");
        }

        // The document beside the mesh. The radius it declares is the one
        // the mesh was built at, floored once for both, and a member too
        // short to be drawn is absent from the members list as well as
        // from the prisms, so the nth of one is the nth of the other.
        MethodInfo json = RequirePublicStatic(mesh, "Json");
        string Document(object members, double radius) =>
            (string)json.Invoke(null, new object?[] { members, radius, "kN", 1.0 })!;
        JsonNode skipped = JsonNode.Parse(
            Document(ListOf(Member(1, 1, 1, 1, 1, 1, 1.0)), 0.1))!;
        if (skipped["vertices"]!.AsArray().Count != 0 ||
            skipped["members"]!.AsArray().Count != 0)
        {
            throw new InvalidOperationException(
                "A member too short to draw is skipped in BOTH lists; the "
                + "document listed one of them.");
        }
        JsonNode clamped = JsonNode.Parse(
            Document(ListOf(Member(0, 0, 0, 0, 0, 2, 1.0)), 0.0))!;
        if (Math.Abs(clamped["radius"]!.GetValue<double>() - 1.0e-9) > 1.0e-18)
        {
            throw new InvalidOperationException(
                "The radius in the document is the one the mesh was built at: "
                + "a zero radius is floored once, for both, not floored inside "
                + $"the mesh and declared raw beside it (got {clamped["radius"]!.GetValue<double>()}).");
        }
    }

    private static void ValidateLiveUploader(Assembly plugin)
    {
        Type uploader = plugin.GetType("Ananke.COMPAS.Native.Components.LiveUploader", throwOnError: true)!;
        MethodInfo delay = RequirePublicStatic(uploader, "RetryDelay");
        MethodInfo route = RequirePublicStatic(uploader, "RouteFor");
        MethodInfo outcome = RequirePublicStatic(uploader, "Outcome");
        MethodInfo key = RequirePublicStatic(uploader, "SetKey");
        int? Delay(int attempt) => (int?)delay.Invoke(null, new object?[] { attempt });
        if (Delay(0) != 2000 || Delay(1) != 4000 || Delay(2) != 8000 || Delay(3) is not null)
            throw new InvalidOperationException("The retry schedule is 2000, 4000, 8000 then null.");
        string Route(string kind, string name, string studio) => (string)route.Invoke(null, new object?[] { kind, name, studio })!;
        if (Route("contract", "arch", "http://127.0.0.1:8600") != "http://127.0.0.1:8600/api/uploads/exports/arch/contract")
            throw new InvalidOperationException($"Contract route wrong: {Route("contract", "arch", "http://127.0.0.1:8600")}.");
        if (Route("tessellation", "arch", "http://127.0.0.1:8600/") != "http://127.0.0.1:8600/api/uploads/exports/arch/tessellation")
            throw new InvalidOperationException("A trailing slash on Studio is tolerated.");
        if (Route("columns", "arch", "http://127.0.0.1:8600") != "http://127.0.0.1:8600/api/uploads/columns/arch-columns.json")
            throw new InvalidOperationException($"Columns route wrong: {Route("columns", "arch", "http://127.0.0.1:8600")}.");
        // The study name is free text off the canvas and lands in a URL
        // path segment. Interpolated raw, a space breaks the URI and a #
        // cuts the rest of the route off as a fragment, so the PUT goes
        // somewhere nobody asked for and the author sees only a 404.
        if (Route("contract", "my study#1", "http://127.0.0.1:8600") !=
            "http://127.0.0.1:8600/api/uploads/exports/my%20study%231/contract")
        {
            throw new InvalidOperationException(
                "A Name with a space and a # must be escaped into the route; got "
                + Route("contract", "my study#1", "http://127.0.0.1:8600") + ".");
        }
        if (Route("columns", "my study#1", "http://127.0.0.1:8600") !=
            "http://127.0.0.1:8600/api/uploads/columns/my%20study%231-columns.json")
        {
            throw new InvalidOperationException(
                "The columns route escapes the Name too; got "
                + Route("columns", "my study#1", "http://127.0.0.1:8600") + ".");
        }
        string Verdict(int status, int attempt) => (string)outcome.Invoke(null, new object?[] { status, attempt })!;
        if (Verdict(200, 0) != "stored" || Verdict(204, 5) != "stored") throw new InvalidOperationException("2xx is stored.");
        if (Verdict(409, 0) != "retry" || Verdict(409, 2) != "retry") throw new InvalidOperationException("409 retries while the schedule has entries.");
        if (Verdict(409, 3) != "deferred") throw new InvalidOperationException("409 after the schedule is deferred.");
        if (Verdict(400, 0) != "refused" || Verdict(500, 0) != "refused") throw new InvalidOperationException("Anything else is refused.");
        // What a deferred kind says it is waiting behind. The studio's
        // 409 body names the run it is busy with, and that run id is what
        // the author looks for in the studio; pasting the document raw
        // makes them read JSON off a component chin.
        MethodInfo deferred = RequirePublicStatic(uploader, "DeferredDetail");
        string Detail(string body) => (string)deferred.Invoke(null, new object?[] { body })!;
        if (Detail("{\"run\": \"r-42\"}") != "(run r-42)")
            throw new InvalidOperationException($"A 409 body naming a run reads as the run; got {Detail("{\"run\": \"r-42\"}")}.");
        if (Detail("study is busy") != "study is busy")
            throw new InvalidOperationException("A body that is not that JSON falls back to the body itself.");
        if (Detail("{\"detail\": \"busy\"}") != "{\"detail\": \"busy\"}")
            throw new InvalidOperationException("JSON carrying no run falls back to the body itself.");
        // The set key. It decides whether a re-solve sends again, and the
        // component expires itself on every outcome, so a key that cannot
        // repeat is an unbounded loop of worker calls and PUTs rather than
        // a cosmetic defect. What it must read: the Name, the Studio and
        // every kind by name and by content. What it must NOT read: the
        // compas document's own bytes, because the worker's json_dumps
        // stamps a fresh uuid4 into every serialisation of the same Result
        // (compas/data/data.py), so those bytes differ on every solve of
        // an unchanged definition.
        string Key(string name, string studio, List<(string, string)> set) =>
            (string)key.Invoke(null, new object?[] { name, studio, set })!;
        const string Studio = "http://127.0.0.1:8600";
        var a = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"guid\":\"aaa\"}") };
        var b = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"guid\":\"aaa\"}") };
        if (Key("arch", Studio, a) != Key("arch", Studio, b))
            throw new InvalidOperationException("Equal sets key the same.");
        // The loop guard itself: same Result, second solve, a fresh guid
        // inside the compas document and nothing else changed.
        var freshGuid = new List<(string, string)> { ("contract", "{\"a\":1}"), ("compas", "{\"guid\":\"bbb\"}") };
        if (Key("arch", Studio, a) != Key("arch", Studio, freshGuid))
        {
            throw new InvalidOperationException(
                "Two sets differing ONLY in the compas kind's JSON must key the SAME: "
                + "the worker mints a fresh uuid per serialisation, so a key that read "
                + "those bytes could never repeat and the expire-on-outcome loop would "
                + "never terminate.");
        }
        // What the key does read, one part at a time.
        var changedContract = new List<(string, string)> { ("contract", "{\"a\":2}"), ("compas", "{\"guid\":\"aaa\"}") };
        if (Key("arch", Studio, a) == Key("arch", Studio, changedContract))
            throw new InvalidOperationException("A set differing in the contract kind's JSON keys differently.");
        var withoutCompas = new List<(string, string)> { ("contract", "{\"a\":1}") };
        if (Key("arch", Studio, a) == Key("arch", Studio, withoutCompas))
        {
            throw new InvalidOperationException(
                "A set carrying a compas kind and the same set without one must key "
                + "differently: the compas kind's PRESENCE counts even though its bytes "
                + "do not, so a set recovered after a worker failure is sent.");
        }
        if (Key("arch", Studio, a) == Key("arch-b", Studio, a))
            throw new InvalidOperationException("The same set under a different Name keys differently.");
        if (Key("arch", Studio, a) == Key("arch", "http://127.0.0.1:8601", a))
            throw new InvalidOperationException("The same set going to a different Studio keys differently.");
        var d = new List<(string, string)> { ("contract", "{\"a\":1}") };
        var e = new List<(string, string)> { ("compas", "{\"a\":1}") };
        if (Key("arch", Studio, d) == Key("arch", Studio, e))
            throw new InvalidOperationException("A set differing only in Kind keys differently.");
    }

    /// <summary>
    /// Export's Path resolution, which decides where a whole set of files
    /// lands. Reflection only: the method is pure (it reads
    /// <c>Directory.Exists</c> but creates nothing and writes nothing), so
    /// this asserts against paths that do not exist on this machine.
    /// </summary>
    private static void ValidateExportWriteFolder(Assembly plugin)
    {
        Type export = RequireComponentType(plugin, "ExportComponent");
        MethodInfo resolve = export.GetMethod(
            "TryResolveWriteFolder",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ExportComponent.TryResolveWriteFolder was not found.");
        (bool Ok, string Folder, string Refusal) Resolve(string path)
        {
            object?[] args = { path, null, null };
            bool ok = (bool)resolve.Invoke(null, args)!;
            return (ok, (string)args[1]!, (string)args[2]!);
        }

        // A folder the author means to create: read as a file path, the
        // whole set landed one level up, silently, beside it.
        (bool ok, string folder, string refusal) = Resolve(@"C:\ananke-smoke-nowhere\my-study");
        if (!ok || folder != @"C:\ananke-smoke-nowhere\my-study")
            throw new InvalidOperationException(
                $"An extensionless Path is the folder, whether or not it exists yet; got ok={ok}, folder '{folder}'.");
        (ok, folder, refusal) = Resolve(@"C:\ananke-smoke-nowhere\my-study\");
        if (!ok || folder.TrimEnd('\\') != @"C:\ananke-smoke-nowhere\my-study")
            throw new InvalidOperationException(
                $"A trailing separator is a folder; got ok={ok}, folder '{folder}'.");
        (ok, folder, refusal) = Resolve(@"C:\ananke-smoke-nowhere\study.json");
        if (!ok || folder != @"C:\ananke-smoke-nowhere")
            throw new InvalidOperationException(
                $"A Path with an extension uses its own directory; got ok={ok}, folder '{folder}'.");
        (ok, folder, refusal) = Resolve("  C:\\ananke-smoke-nowhere\\my-study  ");
        if (!ok || folder != @"C:\ananke-smoke-nowhere\my-study")
            throw new InvalidOperationException("The Path is trimmed before it is read.");
        // A bare name has no folder in it at all, so the set would land in
        // the process working directory, which under Rhino is not
        // somewhere an author can find.
        (ok, folder, refusal) = Resolve("my-study");
        if (ok || refusal.Length == 0 || !refusal.Contains("my-study", StringComparison.Ordinal))
            throw new InvalidOperationException(
                $"A bare relative name is refused, naming the path; got ok={ok}, refusal '{refusal}'.");
        (ok, folder, refusal) = Resolve("study.json");
        if (ok || refusal.Length == 0)
            throw new InvalidOperationException(
                $"A bare file name is refused; got ok={ok}, refusal '{refusal}'.");

        // A relative Path with directories of its own is not a bare name,
        // but it is still not rooted: today it resolves against the
        // process working directory the same way a bare name would, which
        // under Rhino is nobody's intent. Refused, naming the path, the
        // same as a bare name.
        (ok, folder, refusal) = Resolve(@"sub\study");
        if (ok || refusal.Length == 0 ||
            !refusal.Contains(@"sub\study", StringComparison.Ordinal))
            throw new InvalidOperationException(
                $"A non-rooted relative Path is refused, naming the path; got ok={ok}, refusal '{refusal}'.");
        // A relative Path with an extension already fell out refused
        // before this rule existed, but for an unrelated reason (the
        // pre-rule depth check happened to reject it once its own
        // directory name was peeled off). The refusal text below is
        // specific to the rootedness rule, so this assertion still fails
        // against the pre-rule code even though its ok/false verdict
        // alone would not have.
        (ok, folder, refusal) = Resolve(@"sub\study.json");
        if (ok || refusal.Length == 0 ||
            !refusal.Contains("rooted", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(
                $"A non-rooted relative Path with an extension is refused for being unrooted; got ok={ok}, refusal '{refusal}'.");

        // The rooted equivalent of each relative Path above is accepted,
        // with the same folder the existing rooted rules already give:
        // an extensionless Path is the folder itself, a Path with an
        // extension uses its own directory. Built from a temp folder path
        // so the check needs nothing on disk; Directory.Exists on a path
        // that does not exist is simply false, which these rules already
        // tolerate.
        string rootedCheckRoot = Path.Combine(
            Path.GetTempPath(), "ananke-smoke-rooted-check");
        string rootedNoExt = Path.Combine(rootedCheckRoot, "sub", "study");
        (ok, folder, refusal) = Resolve(rootedNoExt);
        if (!ok || folder != rootedNoExt)
            throw new InvalidOperationException(
                $"A rooted extensionless Path is still the folder itself; got ok={ok}, folder '{folder}'.");
        string rootedWithExt = Path.Combine(
            rootedCheckRoot, "sub", "study.json");
        (ok, folder, refusal) = Resolve(rootedWithExt);
        if (!ok || folder != Path.Combine(rootedCheckRoot, "sub"))
            throw new InvalidOperationException(
                $"A rooted Path with an extension still uses its own directory; got ok={ok}, folder '{folder}'.");
    }

    /// <summary>
    /// The cross-repo fixture check: <c>ImportPiecesComponent.ParseDocument</c>
    /// driven with a bench.pieces/1 document generated by the UI repo's own
    /// pieces-export test suite (<c>assets/fixture-pieces.json</c>,
    /// provenance recorded in <c>assets/README.md</c>). Asserts piece
    /// count, order preservation (keys stay in the document's own drop
    /// order), and vertex/face array shapes, then doctors an in-memory
    /// copy's schema and units to confirm ParseDocument refuses each,
    /// naming what it found -- the binding spec's "component Error naming
    /// what was found," as far as this harness's reflection-only reach
    /// (no live Rhino document, no SolveInstance) can exercise it.
    ///
    /// Addendum, 2026-08-20: also asserts BaseMesh's shape against the
    /// committed fixture (regenerated with base_mesh present via the UI
    /// route's real code), and separately proves ParseDocument tolerates
    /// a document with NO base_mesh key at all -- doctored by removing
    /// the property wholesale from an in-memory JSON copy, not merely
    /// nulling it, so old documents (written before this addendum) are
    /// proven to stay loadable.
    ///
    /// Addendum follow-up, 2026-08-20: the fixture was regenerated again
    /// (size 0.6, not 0.9) so it cuts 2 courses instead of 1 -- a
    /// single-course fixture could assert order preservation but never
    /// the addendum's actual point, that M/K/S PARTITION by course. This
    /// method now groups the parsed PieceRecords by Course (the same
    /// field SolveInstance keys GH_Path on) and asserts the exact
    /// per-course counts and in-branch document order against the
    /// fixture's own known shape, measuring the partitioning contract
    /// instead of merely inspecting the component's source for it.
    /// </summary>
    private static void ValidateImportPiecesParsing(Assembly plugin)
    {
        string fixturePath = Path.Combine(
            AppContext.BaseDirectory,
            "assets",
            "fixture-pieces.json");
        if (!File.Exists(fixturePath))
        {
            throw new FileNotFoundException(
                "Committed fixture not found (expected it copied to the " +
                "build output by the harness's assets/ convention): " +
                fixturePath,
                fixturePath);
        }
        string json = File.ReadAllText(fixturePath);

        Type importType = RequireComponentType(plugin, "ImportPiecesComponent");
        MethodInfo parseMethod = importType.GetMethod(
            "ParseDocument",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ImportPiecesComponent.ParseDocument was not found.");

        object document = parseMethod.Invoke(null, new object[] { json })
            ?? throw new InvalidOperationException(
                "ParseDocument returned null for the committed fixture.");
        Type documentType = document.GetType();

        // The fixture's own document order (piece keys, verbatim), across
        // BOTH of its courses: 10 course-0 pieces, then 4 course-1 pieces,
        // not the sorted/alphabetical order the keys would fall into on
        // their own, and not grouped by course in the document itself
        // (that grouping is exactly what GH_Path(piece.Course) partitions
        // out downstream -- asserted separately below). Addendum
        // follow-up, 2026-08-20: regenerated at size 0.6 (was 0.9) so the
        // fixture actually cuts 2 courses; a single-course fixture could
        // never prove the tree PARTITIONS.
        var expectedKeys = new[]
        {
            "c0p5", "c0p6", "c0p7", "c0p8", "c0p9",
            "c0p0", "c0p1", "c0p2", "c0p3", "c0p4",
            "c1p2", "c1p3", "c1p0", "c1p1",
        };

        object? pieceCountValue =
            documentType.GetProperty("PieceCount")?.GetValue(document);
        if (pieceCountValue is not int pieceCount ||
            pieceCount != expectedKeys.Length)
        {
            throw new InvalidOperationException(
                $"PiecesDocument.PieceCount must be {expectedKeys.Length}; " +
                $"received '{pieceCountValue}'.");
        }

        IList pieces = documentType.GetProperty("Pieces")?.GetValue(document)
            as IList
            ?? throw new InvalidOperationException(
                "PiecesDocument.Pieces could not be inspected.");
        if (pieces.Count != expectedKeys.Length)
        {
            throw new InvalidOperationException(
                $"Expected {expectedKeys.Length} pieces, found " +
                $"{pieces.Count}.");
        }

        for (int index = 0; index < expectedKeys.Length; index++)
        {
            object piece = pieces[index]
                ?? throw new InvalidOperationException(
                    $"Piece {index} is null.");
            Type pieceType = piece.GetType();
            string key =
                pieceType.GetProperty("Key")?.GetValue(piece) as string
                ?? string.Empty;
            if (!string.Equals(
                    key,
                    expectedKeys[index],
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"Piece {index} key must be '{expectedKeys[index]}' " +
                    $"(the document's own drop order); received '{key}'.");
            }

            IList vertices =
                pieceType.GetProperty("Vertices")?.GetValue(piece) as IList
                ?? throw new InvalidOperationException(
                    $"Piece '{key}' Vertices could not be inspected.");
            if (vertices.Count == 0)
            {
                throw new InvalidOperationException(
                    $"Piece '{key}' has no vertices.");
            }
            foreach (object? vertex in vertices)
            {
                if (vertex is not double[] xyz || xyz.Length != 3)
                {
                    throw new InvalidOperationException(
                        $"Piece '{key}' has a vertex that is not an " +
                        "[x, y, z] triple.");
                }
            }

            IList faces =
                pieceType.GetProperty("Faces")?.GetValue(piece) as IList
                ?? throw new InvalidOperationException(
                    $"Piece '{key}' Faces could not be inspected.");
            if (faces.Count == 0)
            {
                throw new InvalidOperationException(
                    $"Piece '{key}' has no faces.");
            }
            foreach (object? face in faces)
            {
                if (face is not int[] corners || corners.Length < 3)
                {
                    throw new InvalidOperationException(
                        $"Piece '{key}' has a face with fewer than 3 " +
                        "corners.");
                }
            }
        }

        // Addendum follow-up, 2026-08-20: the partitioning contract,
        // MEASURED rather than merely inspected by reading the
        // component's source. Groups the parsed PieceRecords by their
        // own Course value -- the exact field ImportPiecesComponent's
        // SolveInstance keys GH_Path(piece.Course) on -- in document
        // order, then asserts the result against the committed fixture's
        // own known shape: 2 distinct course branches, exact per-course
        // counts, and document order preserved WITHIN each branch. This
        // is what GH_Path(course) partitioning produces without needing
        // to run inside Grasshopper: Append-in-order grouped by key is
        // the same operation either way.
        var courseOrder = new List<int>();
        var courseGroups = new Dictionary<int, List<string>>();
        foreach (object piece in pieces)
        {
            Type pieceType = piece.GetType();
            object? courseValue =
                pieceType.GetProperty("Course")?.GetValue(piece);
            if (courseValue is not int pieceCourse)
            {
                throw new InvalidOperationException(
                    "PieceRecord.Course could not be inspected.");
            }
            string pieceKey =
                pieceType.GetProperty("Key")?.GetValue(piece) as string
                ?? string.Empty;

            if (!courseGroups.TryGetValue(pieceCourse, out List<string>? keys))
            {
                keys = new List<string>();
                courseGroups[pieceCourse] = keys;
                courseOrder.Add(pieceCourse);
            }
            keys.Add(pieceKey);
        }

        if (courseGroups.Count < 2)
        {
            throw new InvalidOperationException(
                "The fixture must carry >= 2 distinct course values to " +
                $"prove tree partitioning; found {courseGroups.Count}.");
        }

        var expectedCourseGroups = new (int Course, string[] Keys)[]
        {
            (0, new[]
            {
                "c0p5", "c0p6", "c0p7", "c0p8", "c0p9",
                "c0p0", "c0p1", "c0p2", "c0p3", "c0p4",
            }),
            (1, new[] { "c1p2", "c1p3", "c1p0", "c1p1" }),
        };

        if (courseOrder.Count != expectedCourseGroups.Length)
        {
            throw new InvalidOperationException(
                $"Expected {expectedCourseGroups.Length} distinct course " +
                $"branches (the GH_Path partitioning this fixture must " +
                $"prove); found {courseOrder.Count}.");
        }

        foreach ((int course, string[] expectedCourseKeys) in expectedCourseGroups)
        {
            if (!courseGroups.TryGetValue(course, out List<string>? actualKeys))
            {
                throw new InvalidOperationException(
                    $"Course {course} branch is missing from the parsed " +
                    "pieces.");
            }
            if (actualKeys.Count != expectedCourseKeys.Length)
            {
                throw new InvalidOperationException(
                    $"Course {course} branch (GH_Path({course})) must " +
                    $"carry {expectedCourseKeys.Length} piece(s); found " +
                    $"{actualKeys.Count}.");
            }
            for (int index = 0; index < expectedCourseKeys.Length; index++)
            {
                if (!string.Equals(
                        actualKeys[index],
                        expectedCourseKeys[index],
                        StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"Course {course} branch item {index} must be " +
                        $"'{expectedCourseKeys[index]}' (document order " +
                        "preserved within the branch); received " +
                        $"'{actualKeys[index]}'.");
                }
            }
        }

        // Addendum, 2026-08-20: base_mesh shape, against the committed
        // fixture (regenerated to carry one).
        object? baseMeshValue =
            documentType.GetProperty("BaseMesh")?.GetValue(document);
        if (baseMeshValue is null)
        {
            throw new InvalidOperationException(
                "PiecesDocument.BaseMesh must be present for the " +
                "committed fixture (regenerated with base_mesh); found " +
                "null.");
        }
        Type baseMeshType = baseMeshValue.GetType();
        IList baseMeshVertices =
            baseMeshType.GetProperty("Vertices")?.GetValue(baseMeshValue)
                as IList
            ?? throw new InvalidOperationException(
                "BaseMesh.Vertices could not be inspected.");
        IList baseMeshFaces =
            baseMeshType.GetProperty("Faces")?.GetValue(baseMeshValue)
                as IList
            ?? throw new InvalidOperationException(
                "BaseMesh.Faces could not be inspected.");
        if (baseMeshVertices.Count == 0 || baseMeshFaces.Count == 0)
        {
            throw new InvalidOperationException(
                "BaseMesh must carry at least one vertex and one face " +
                "for the committed fixture.");
        }
        foreach (object? vertex in baseMeshVertices)
        {
            if (vertex is not double[] xyz || xyz.Length != 3)
            {
                throw new InvalidOperationException(
                    "BaseMesh has a vertex that is not an [x, y, z] " +
                    "triple.");
            }
        }
        foreach (object? face in baseMeshFaces)
        {
            if (face is not int[] corners || corners.Length < 3)
            {
                throw new InvalidOperationException(
                    "BaseMesh has a face with fewer than 3 corners.");
            }
        }

        // Addendum, 2026-08-20: absence tolerance. Strip base_mesh from
        // an in-memory copy of the fixture's own JSON (property removed
        // entirely, not nulled) and confirm ParseDocument still succeeds
        // with BaseMesh coming back null -- an export written before
        // this addendum must stay loadable.
        string jsonWithoutBaseMesh = RemoveJsonProperty(json, "base_mesh");
        object documentWithoutBaseMesh =
            parseMethod.Invoke(null, new object[] { jsonWithoutBaseMesh })
            ?? throw new InvalidOperationException(
                "ParseDocument returned null for a fixture doctored to " +
                "omit base_mesh.");
        object? baseMeshWhenAbsent = documentType
            .GetProperty("BaseMesh")
            ?.GetValue(documentWithoutBaseMesh);
        if (baseMeshWhenAbsent is not null)
        {
            throw new InvalidOperationException(
                "PiecesDocument.BaseMesh must be null when the document " +
                "has no base_mesh key; ParseDocument must tolerate " +
                "absence, not fabricate a value.");
        }

        RequireParseRefusal(
            parseMethod,
            json.Replace(
                "\"schema\": \"bench.pieces/1\"",
                "\"schema\": \"bench.pieces/2\""),
            "schema",
            "bench.pieces/2",
            "a doctored bad-schema copy");
        RequireParseRefusal(
            parseMethod,
            json.Replace(
                "\"units\": \"m\"",
                "\"units\": \"mm\""),
            "units",
            "mm",
            "a doctored bad-units copy");
    }

    /// <summary>
    /// Removes one top-level property from a JSON document, returning the
    /// re-serialized text -- used to prove ParseDocument tolerates a
    /// document with a key entirely ABSENT, not merely present-and-null,
    /// which a simple string replace of the property's value could not
    /// distinguish.
    /// </summary>
    private static string RemoveJsonProperty(string json, string propertyName)
    {
        JsonNode node = JsonNode.Parse(json)
            ?? throw new InvalidOperationException(
                "JSON did not parse to a node.");
        JsonObject root = node.AsObject();
        root.Remove(propertyName);
        return root.ToJsonString();
    }

    /// <summary>
    /// Invokes <c>ParseDocument</c> with a doctored copy and requires it
    /// to throw naming both the offending field and the value that was
    /// actually found (not merely "invalid").
    /// </summary>
    private static void RequireParseRefusal(
        MethodInfo parseMethod,
        string doctoredJson,
        string expectedField,
        string expectedFoundValue,
        string label)
    {
        try
        {
            parseMethod.Invoke(null, new object[] { doctoredJson });
        }
        catch (TargetInvocationException invocation)
            when (invocation.InnerException is not null)
        {
            string message = invocation.InnerException.Message;
            if (!message.Contains(
                    expectedField,
                    StringComparison.OrdinalIgnoreCase) ||
                !message.Contains(expectedFoundValue, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{label} was refused, but the message did not name " +
                    $"'{expectedField}'/'{expectedFoundValue}': '{message}'.");
            }
            return;
        }
        throw new InvalidOperationException(
            $"{label} was not refused by ParseDocument.");
    }

    // A minimal, internally consistent triangle fixture (3 vertices, 3
    // edges, 1 face) shared by every JSON template below. Building genuine
    // JSON and deserializing it through the plugin's own ContractJson codec
    // exercises the exact path Grasshopper document persistence uses,
    // rather than merely poking properties by reflection.
    private const string TopologyJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.topology"",
  ""networkKind"": ""faced"",
  ""vertices"": [
    {""x"": 0.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 1.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 0.0, ""y"": 1.0, ""z"": 0.0}
  ],
  ""edges"": [
    {""u"": 0, ""v"": 1},
    {""u"": 1, ""v"": 2},
    {""u"": 2, ""v"": 0}
  ],
  ""faces"": [[0, 1, 2]],
  ""lengthUnit"": ""m"",
  ""topologyHash"": ""__HASH__""
}";

    private const string SupportSetJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.support_set"",
  ""topologyHash"": ""__HASH__"",
  ""mode"": ""explicit"",
  ""nodeIds"": [0]
}";

    private const string TnaPatternJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.tna_pattern"",
  ""patternMode"": ""mesh"",
  ""topology"": __TOPOLOGY__,
  ""supports"": __SUPPORTS__
}";

    private const string LoadCaseJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.load_case"",
  ""topologyHash"": ""__HASH__"",
  ""name"": ""spine-smoke"",
  ""distribution"": ""point"",
  ""nodeIds"": [0],
  ""vectors"": [{""x"": 0.0, ""y"": 0.0, ""z"": -1.0}]
}";

    private const string AnchoredPatternJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""AnchoredPattern"",
  ""pattern"": __PATTERN__,
  ""anchorNodeIds"": __ANCHORS__
}";

    private const string ProblemJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""Problem"",
  ""anchored"": __ANCHORED__,
  ""load"": __LOAD__
}";

    private const string TnaPreparedPatternJson = @"
{
  ""patternKind"": ""faced"",
  ""vertices"": [
    {""x"": 0.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 1.0, ""y"": 0.0, ""z"": 0.0},
    {""x"": 0.0, ""y"": 1.0, ""z"": 0.0}
  ],
  ""edges"": [
    {""u"": 0, ""v"": 1},
    {""u"": 1, ""v"": 2},
    {""u"": 2, ""v"": 0}
  ],
  ""faces"": [[0, 1, 2]],
  ""edgeForceDensities"": [1.0, 1.0, 1.0]
}";

    private const string TnaDiagramGraphJson = @"
{
  ""vertices"": [
    {""id"": 0, ""point"": {""x"": 0.0, ""y"": 0.0, ""z"": 0.0}},
    {""id"": 1, ""point"": {""x"": 1.0, ""y"": 0.0, ""z"": 0.0}},
    {""id"": 2, ""point"": {""x"": 0.0, ""y"": 1.0, ""z"": 0.0}}
  ],
  ""edges"": [
    {""id"": 0, ""u"": 0, ""v"": 1},
    {""id"": 1, ""u"": 1, ""v"": 2},
    {""id"": 2, ""u"": 2, ""v"": 0}
  ]
}";

    private const string TnaPreparedMappingsJson = @"
{
  ""patternVertexToTopologyVertex"": [0, 1, 2],
  ""backendSourceToTopologyVertex"": [
    {""topologyVertexId"": 0},
    {""topologyVertexId"": 1},
    {""topologyVertexId"": 2}
  ],
  ""sourceEdgeToPatternEdge"": [
    {""sourceEdgeId"": 0, ""patternEdgeId"": 0, ""u"": 0, ""v"": 1},
    {""sourceEdgeId"": 1, ""patternEdgeId"": 1, ""u"": 1, ""v"": 2},
    {""sourceEdgeId"": 2, ""patternEdgeId"": 2, ""u"": 2, ""v"": 0}
  ],
  ""supportNodeIds"": [0],
  ""fixedPlanNodeIds"": [],
  ""formEdgeToForceEdge"": [
    {""formEdgeId"": 0, ""targetEdgeId"": 0},
    {""formEdgeId"": 1, ""targetEdgeId"": 1},
    {""formEdgeId"": 2, ""targetEdgeId"": 2}
  ]
}";

    private const string TnaPreparedJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""ananke.tna_prepared"",
  ""source"": __PATTERN__,
  ""workerTopologyHash"": ""__HASH__"",
  ""supportSet"": __SUPPORTS__,
  ""pattern"": __PREPARED_PATTERN__,
  ""formGraph"": __FORM_GRAPH__,
  ""forceGraph"": __FORCE_GRAPH__,
  ""mappings"": __MAPPINGS__
}";

    private const string RelaxedJsonTemplate = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""Relaxed"",
  ""prepared"": __PREPARED__,
  ""problem"": __PROBLEM__
}";

    private const string RelaxedEmptyJson = @"
{
  ""schemaVersion"": ""0.2"",
  ""kind"": ""Relaxed""
}";

    /// <summary>
    /// Constructs the three spine contracts (<c>AnchoredPatternDto</c>,
    /// <c>ProblemDto</c>, <c>RelaxedDto</c>) via JSON round-tripped through
    /// the plugin's own <c>ContractJson</c> codec, exercising one valid and
    /// one invalid case per type, then confirms a <c>ProblemDto</c> attaches
    /// to <c>ResultDto.Problem</c> without breaking a valid TNA result.
    /// </summary>
    private static void ValidateSpineContracts(Assembly plugin)
    {
        Type topologyType = RequireContractType(plugin, "TopologyDto");
        Type anchoredType = RequireContractType(plugin, "AnchoredPatternDto");
        Type problemType = RequireContractType(plugin, "ProblemDto");
        Type preparedType = RequireContractType(plugin, "TnaPreparedDto");
        Type relaxedType = RequireContractType(plugin, "RelaxedDto");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");

        string zeroHash = new string('0', 64);
        object draftTopology = DeserializeContract(
            plugin,
            topologyType,
            TopologyJsonTemplate.Replace("__HASH__", zeroHash));
        string topologyHash = ComputeTopologyHash(plugin, draftTopology);
        string topologyJson = TopologyJsonTemplate.Replace("__HASH__", topologyHash);
        string supportSetJson =
            SupportSetJsonTemplate.Replace("__HASH__", topologyHash);
        string patternJson = TnaPatternJsonTemplate
            .Replace("__TOPOLOGY__", topologyJson)
            .Replace("__SUPPORTS__", supportSetJson);

        // AnchoredPatternDto: valid (one anchor) and invalid (no anchors).
        string validAnchoredJson = AnchoredPatternJsonTemplate
            .Replace("__PATTERN__", patternJson)
            .Replace("__ANCHORS__", "[0]");
        object validAnchored =
            DeserializeContract(plugin, anchoredType, validAnchoredJson);
        RequireNoValidationErrors(validAnchored, "Valid AnchoredPatternDto");

        object invalidAnchored = DeserializeContract(
            plugin,
            anchoredType,
            AnchoredPatternJsonTemplate
                .Replace("__PATTERN__", patternJson)
                .Replace("__ANCHORS__", "[]"));
        RequireValidationErrors(
            invalidAnchored,
            "Invalid AnchoredPatternDto without anchor node IDs");

        // ProblemDto: valid (matching topology hash) and invalid
        // (load.topologyHash does not match the anchored pattern).
        string validLoadJson = LoadCaseJsonTemplate.Replace("__HASH__", topologyHash);
        string validProblemJson = ProblemJsonTemplate
            .Replace("__ANCHORED__", validAnchoredJson)
            .Replace("__LOAD__", validLoadJson);
        object validProblem =
            DeserializeContract(plugin, problemType, validProblemJson);
        RequireNoValidationErrors(validProblem, "Valid ProblemDto");

        object invalidProblem = DeserializeContract(
            plugin,
            problemType,
            ProblemJsonTemplate
                .Replace("__ANCHORED__", validAnchoredJson)
                .Replace(
                    "__LOAD__",
                    LoadCaseJsonTemplate.Replace("__HASH__", zeroHash)));
        RequireValidationErrors(
            invalidProblem,
            "Invalid ProblemDto with a load from a different source topology");

        // RelaxedDto: valid (both members present and valid) and invalid
        // (both members missing).
        string preparedJson = TnaPreparedJsonTemplate
            .Replace("__PATTERN__", patternJson)
            .Replace("__HASH__", topologyHash)
            .Replace("__SUPPORTS__", supportSetJson)
            .Replace("__PREPARED_PATTERN__", TnaPreparedPatternJson)
            .Replace("__FORM_GRAPH__", TnaDiagramGraphJson)
            .Replace("__FORCE_GRAPH__", TnaDiagramGraphJson)
            .Replace("__MAPPINGS__", TnaPreparedMappingsJson);
        object prepared = DeserializeContract(plugin, preparedType, preparedJson);
        RequireNoValidationErrors(
            prepared,
            "Valid TnaPreparedDto (spine smoke fixture)");

        object validRelaxed = DeserializeContract(
            plugin,
            relaxedType,
            RelaxedJsonTemplate
                .Replace("__PREPARED__", preparedJson)
                .Replace("__PROBLEM__", validProblemJson));
        RequireNoValidationErrors(validRelaxed, "Valid RelaxedDto");

        object invalidRelaxed =
            DeserializeContract(plugin, relaxedType, RelaxedEmptyJson);
        RequireValidationErrors(
            invalidRelaxed,
            "Invalid RelaxedDto missing both prepared and problem");

        // ResultDto.Problem: optional provenance attach (Task 4 step 4)
        // must not disturb an otherwise-valid TNA result.
        object resultWithProblem = CreateResultDto(
            resultType,
            solver: "tna",
            equilibrium: CreateInstance(equilibriumType),
            formGraph: CreateInstance(graphType),
            forceGraph: CreateInstance(graphType));
        SetContractProperty(resultWithProblem, resultType, "Problem", validProblem);
        RequireNoValidationErrors(
            resultWithProblem,
            "Valid TNA ResultDto with an attached Problem");
    }

    private static object DeserializeContract(
        Assembly plugin,
        Type contractType,
        string json)
    {
        Type contractJsonType = RequireContractType(plugin, "ContractJson");
        MethodInfo generic = contractJsonType.GetMethod(
            "Deserialize",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "ContractJson.Deserialize was not found.");
        MethodInfo bound = generic.MakeGenericMethod(contractType);
        return bound.Invoke(null, new object[] { json })
            ?? throw new InvalidOperationException(
                $"Deserializing {contractType.FullName} returned null.");
    }

    private static string ComputeTopologyHash(Assembly plugin, object topology)
    {
        Type fingerprintType = RequireContractType(plugin, "TopologyFingerprint");
        MethodInfo computeMethod = fingerprintType.GetMethod(
            "Compute",
            BindingFlags.Public | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "TopologyFingerprint.Compute was not found.");
        return computeMethod.Invoke(null, new object[] { topology }) as string
            ?? throw new InvalidOperationException(
                "TopologyFingerprint.Compute returned an unexpected type.");
    }

    private static string DescribeException(Exception exception)
    {
        Exception current = exception;
        var chain = new List<string>();
        while (true)
        {
            chain.Add($"{current.GetType().Name}: {current.Message}");
            if (current.InnerException is null)
                break;
            current = current.InnerException;
        }
        return string.Join(" -> ", chain);
    }

    private static string ResolveRhinoRoot(string? requestedRoot)
    {
        var candidates = new[]
        {
            requestedRoot,
            Environment.GetEnvironmentVariable("RHINO8_ROOT"),
            Path.Combine(
                Environment.GetFolderPath(
                    Environment.SpecialFolder.ProgramFiles),
                "Rhino 8")
        };

        foreach (string? candidate in candidates)
        {
            if (string.IsNullOrWhiteSpace(candidate))
                continue;
            string fullPath = Path.GetFullPath(candidate);
            if (Directory.Exists(fullPath))
                return fullPath;
        }

        throw new UsageException(
            "Rhino 8 was not found. Pass --rhino-root or set RHINO8_ROOT.");
    }

    private static string RequireFile(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException(
                $"Required Rhino/Grasshopper dependency was not found: {path}",
                path);
        return Path.GetFullPath(path);
    }

    private sealed record Options(string PluginPath, string? RhinoRoot)
    {
        public static Options Parse(IReadOnlyList<string> args)
        {
            if (args.Count == 0)
                throw new UsageException("A built .gha path is required.");

            string? pluginPath = null;
            string? rhinoRoot = null;
            for (int index = 0; index < args.Count; index++)
            {
                string argument = args[index];
                if (string.Equals(
                    argument,
                    "--rhino-root",
                    StringComparison.OrdinalIgnoreCase))
                {
                    if (++index >= args.Count)
                        throw new UsageException(
                            "--rhino-root requires a directory.");
                    rhinoRoot = args[index];
                    continue;
                }

                if (argument.StartsWith("-", StringComparison.Ordinal))
                    throw new UsageException(
                        $"Unknown option: {argument}");
                if (pluginPath is not null)
                    throw new UsageException(
                        "Only one plugin path may be supplied.");
                pluginPath = argument;
            }

            if (string.IsNullOrWhiteSpace(pluginPath))
                throw new UsageException("A built .gha path is required.");
            return new Options(pluginPath, rhinoRoot);
        }
    }

    private sealed class UsageException : Exception
    {
        public UsageException(string message)
            : base(message)
        {
        }
    }
}
