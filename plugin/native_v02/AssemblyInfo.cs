using System;
using System.Collections.Concurrent;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Threading;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native;

internal static class PluginResources
{
    private static readonly Assembly Assembly = typeof(PluginResources).Assembly;
    private static readonly ConcurrentDictionary<string, Lazy<Bitmap?>> Icons =
        new(StringComparer.OrdinalIgnoreCase);

    public static Bitmap? Icon(string name)
    {
        if (string.IsNullOrWhiteSpace(name))
            return null;

        return Icons.GetOrAdd(
            name,
            static key => new Lazy<Bitmap?>(
                () => LoadIcon(key),
                LazyThreadSafetyMode.ExecutionAndPublication)).Value;
    }

    private static Bitmap? LoadIcon(string name)
    {
        string resourceName = $"Ananke.COMPAS.Native.Icons.{name}.png";
        using Stream? stream = Assembly.GetManifestResourceStream(resourceName);
        if (stream is null)
            return null;

        using var source = new Bitmap(stream);
        return new Bitmap(source);
    }
}

public sealed class AnankeNativeAssemblyInfo : GH_AssemblyInfo
{
    public override string Name => "Ananke COMPAS";

    public override Bitmap? Icon => PluginResources.Icon("network");

    public override string Description =>
        "Native Grasshopper components with an isolated COMPAS Python worker.";

    public override Guid Id =>
        new("d4c49da9-26d9-4c0d-89c0-958fa3ec5834");

    public override string AuthorName => "Edward / Ananke Eidos Studio";

    public override string AuthorContact => "edrowbo@googlemail.com";

    public override string Version => "0.2.0";
}
