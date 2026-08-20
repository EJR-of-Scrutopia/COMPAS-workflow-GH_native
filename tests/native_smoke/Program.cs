using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;

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
                new[] { 0 },
            ["Ananke.COMPAS.Native.Components.SupportsComponent"] =
                new[] { 1 },
            ["Ananke.COMPAS.Native.Components.LoadsComponent"] =
                new[] { 2 },
            ["Ananke.COMPAS.Native.Components.FdSolveComponent"] =
                new[] { 1 }
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
                    // Course Height joined 2026-08-18 (the Face Courses
                    // banding knob); Face Polylines / Face Courses are the
                    // authored-tessellation feeds added the same day.
                    new[] { "Result", "Course Height" },
                    new[]
                    {
                        "Thrust Mesh",
                        "Member Lines",
                        "Form Lines",
                        "q",
                        "H",
                        "F",
                        "Force State",
                        "Member IDs",
                        "Node IDs",
                        "Support Points",
                        "Load Points",
                        "Load Vectors",
                        "Reaction Points",
                        "Reaction Vectors",
                        "Residuals",
                        "Diagnostics",
                        "Report",
                        "Face Polylines",
                        "Face Courses"
                    })
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
                    new[] { "G", "M", "R", "Tol" },
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
                    new[] { "PRB", "q", "Sag %" },
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
                    new[] { "M", "C", "K", "S", "D" })
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
                "drop-order preservation, and vertex/face array shapes " +
                "match the committed bench.pieces/1 fixture, and doctored " +
                "schema/units copies are refused naming what was found.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"ImportPiecesComponent.ParseDocument: " +
                $"{DescribeException(exception)}");
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

    private static Type RequireContractType(Assembly plugin, string typeName)
    {
        const string ContractsNamespace = "Ananke.COMPAS.Native.Contracts";
        return plugin.GetType($"{ContractsNamespace}.{typeName}", throwOnError: true)
            ?? throw new InvalidOperationException(
                $"Type '{ContractsNamespace}.{typeName}' was not found.");
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

        var json = method.Invoke(null, new[] { cellList }) as string
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

        // The fixture's own document order (piece keys, verbatim): course
        // 0, five pieces, not the sorted/alphabetical order the keys
        // would fall into on their own.
        var expectedKeys = new[] { "c0p3", "c0p4", "c0p0", "c0p1", "c0p2" };

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
