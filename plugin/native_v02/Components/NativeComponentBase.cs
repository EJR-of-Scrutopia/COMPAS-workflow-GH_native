using System;
using System.Drawing;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Components;

internal static class ComponentCategories
{
    public const string Category = "Ananke COMPAS";
    public const string Model = "01 Model";
    public const string FormFinding = "02 Form Finding";
    public const string Visualisation = "05 Visualisation";
    public const string Query = "90 Query";
}

public abstract class NativeComponentBase : GH_Component
{
    private readonly string _iconName;

    protected NativeComponentBase(
        string name,
        string nickname,
        string description,
        string subcategory,
        string iconName)
        : base(
            name,
            nickname,
            description,
            ComponentCategories.Category,
            subcategory)
    {
        _iconName = iconName;
    }

    protected override Bitmap? Icon => PluginResources.Icon(_iconName);

    public override GH_Exposure Exposure => GH_Exposure.primary;

    protected void ReportException(string operation, Exception error)
    {
        string message = error.GetBaseException().Message;
        AddRuntimeMessage(
            GH_RuntimeMessageLevel.Error,
            $"{operation}: {message}");
    }
}

public abstract class NativeTaskComponentBase<TResult> :
    GH_TaskCapableComponent<TResult>
{
    private readonly string _iconName;

    protected NativeTaskComponentBase(
        string name,
        string nickname,
        string description,
        string subcategory,
        string iconName)
        : base(
            name,
            nickname,
            description,
            ComponentCategories.Category,
            subcategory)
    {
        _iconName = iconName;
        UseTasks = true;
    }

    protected override Bitmap? Icon => PluginResources.Icon(_iconName);

    public override GH_Exposure Exposure => GH_Exposure.primary;

    protected void ReportException(string operation, Exception error)
    {
        string message = error.GetBaseException().Message;
        AddRuntimeMessage(
            GH_RuntimeMessageLevel.Error,
            $"{operation}: {message}");
    }
}
