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
            ["Ananke.COMPAS.Native.Components.NetworkComponent"] =
                new[] { 0 },
            ["Ananke.COMPAS.Native.Components.SupportSetComponent"] =
                new[] { 1, 2 },
            ["Ananke.COMPAS.Native.Components.LoadCaseComponent"] =
                new[] { 1, 2, 3 },
            ["Ananke.COMPAS.Native.Components.EquilibriumProblemComponent"] =
                new[] { 2 },
            ["Ananke.COMPAS.Native.Components.FDSettingsComponent"] =
                new[] { 0 }
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
        if (parameterTypes.Length != 10)
        {
            failures.Add(
                $"Expected 10 public persistent contract parameters, found " +
                $"{parameterTypes.Length}.");
        }
        Console.WriteLine($"Parameters discovered: {parameterTypes.Length}");
        Console.WriteLine(
            $"Parameters passed: " +
            $"{parameterTypes.Length - (failures.Count - componentFailureCount)}");

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
