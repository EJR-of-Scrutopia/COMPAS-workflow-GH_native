#nullable enable

using System;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// Base for components which draw renderer-owned viewport geometry.
///
/// Grasshopper's Preview command updates <see cref="IGH_PreviewObject.Hidden"/>.
/// Custom drawing code must honour that flag explicitly; otherwise it can
/// remain visible after the user disables preview on the component.
/// </summary>
public abstract class NativePreviewComponentBase : NativeComponentBase
{
    protected NativePreviewComponentBase(
        string name,
        string nickname,
        string description,
        string subcategory,
        string iconName)
        : base(name, nickname, description, subcategory, iconName)
    {
    }

    public sealed override void DrawViewportWires(IGH_PreviewArgs args)
    {
        ArgumentNullException.ThrowIfNull(args);
        if (Hidden)
            return;

        base.DrawViewportWires(args);
        DrawVisibleViewportWires(args);
    }

    /// <summary>
    /// Draw custom wires after the native preview-visibility guard has passed.
    /// </summary>
    protected abstract void DrawVisibleViewportWires(IGH_PreviewArgs args);
}
