using System;
using System.IO;
using System.Reflection;
using Ananke.COMPAS.Native.Backend;

namespace Ananke.COMPAS.Native.Components;

internal static class WorkerRuntime
{
    private static readonly object Gate = new();
    private static WorkerHost? _host;

    static WorkerRuntime()
    {
        AppDomain.CurrentDomain.ProcessExit += (_, _) => Dispose();
    }

    public static WorkerHost Host
    {
        get
        {
            lock (Gate)
            {
                _host ??= WorkerHost.FromInstalledConfiguration(
                    pluginDirectory: PluginDirectory());
                return _host;
            }
        }
    }

    public static void Dispose()
    {
        WorkerHost? host;
        lock (Gate)
        {
            host = _host;
            _host = null;
        }

        if (host is null)
            return;
        try
        {
            host.Dispose();
        }
        catch
        {
            // Rhino is exiting; there is no UI available for a shutdown error.
        }
    }

    private static string PluginDirectory()
    {
        string location = Assembly.GetExecutingAssembly().Location;
        return Path.GetDirectoryName(location) ?? AppContext.BaseDirectory;
    }
}
