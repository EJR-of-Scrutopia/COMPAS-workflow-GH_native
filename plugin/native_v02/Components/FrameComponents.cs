#nullable enable

using System;
using System.Collections.Generic;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Frame: the geometry of the state a Result stands at.
    ///
    /// One component reads the net, whatever moment it is at. A Result
    /// straight from a solver or from Columns carries no frame, so this is
    /// the finished vault; a Result from Animate carries one, so this is
    /// that frame of the build. Nothing here decides anything: the whole
    /// reading is <see cref="FrameGeometry.Build"/>, which is the same call
    /// Animate's viewport draws from, so the two cannot drift.
    ///
    /// This is why Animate has one port. Making a frame and reading one are
    /// different jobs, and eight geometry ports on the component that makes
    /// them meant the geometry could only be had by animating, and could
    /// never be had of the finished vault at all.
    ///
    /// No custom preview, and the geometry outputs start HIDDEN, the way
    /// every other reader of a Result starts them (Deconstruct, Monitor,
    /// Skin, Columns). Animate owns the drawing of the machine and this
    /// component owns the data; left visible, Grasshopper's default red drew
    /// the same mesh, the same cables and the same columns a second time
    /// over Animate's own shaded preview, which is the very doubling having
    /// no custom preview here was meant to avoid. Each output can still be
    /// switched on from its own context menu. Phase is text and previews
    /// nothing either way.
    /// </summary>
    public sealed class FrameComponent : NativeComponentBase
    {
        public FrameComponent()
            : base(
                "Frame",
                "FR",
                "The geometry of the frame a Result stands at: the net, its "
                    + "notched bars, its anchors, its boundary and its "
                    + "columns. A Result from a solver or from Columns gives "
                    + "the finished vault; a Result from Animate gives that "
                    + "frame of the build.",
                ComponentCategories.Read,
                "frame")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("5d8e2f61-7a4c-4b93-a0e6-c3f19b7d2a58");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "A solved Result. With a Mould frame on it, from Animate, "
                    + "the geometry comes back at that frame; without one it "
                    + "comes back at the solved shape.",
                GH_ParamAccess.item);
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "The formwork surface at this frame, rebuilt from the "
                    + "Result's own faces. Empty for an FD result, which "
                    + "carries no faces to rebuild from.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Cables",
                "C",
                "Every net member at this frame, infill and bar alike, as a "
                    + "TREE: one branch per principal line carrying that "
                    + "bar's own members in order along it, and a LAST branch "
                    + "holding the infill, everything not on a bar. Branch "
                    + "{i} is bar {i}, the same bar as branch {i} of "
                    + "Principal Lines and Principal Nodes.",
                GH_ParamAccess.tree);
            parameters.AddCurveParameter(
                "Principal Lines",
                "PL",
                "The notched bars at this frame, bending as they rise, as a "
                    + "TREE with one branch per bar. One curve per branch.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Principal Nodes",
                "PN",
                "Every notch: one crossing cable, and a pair of stepper "
                    + "motors pulling it, one each side. A TREE with one "
                    + "branch per bar, the notches IN ORDER ALONG THAT BAR, "
                    + "so branch {i} runs the length of Principal Lines "
                    + "branch {i}. A node where two bars cross appears in "
                    + "both branches, because it is a notch on both.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Anchor Nodes",
                "AN",
                "The Result's supports: the side anchors that stay on the "
                    + "ground and take the perimeter cables' prestress. A "
                    + "TREE with one branch per CONNECTED STRIP, walked end "
                    + "to end, so opposite sides of the vault come back as "
                    + "separate branches instead of one merged list.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Perimeter Nodes",
                "PRN",
                "Nodes on the naked boundary of the net, as a TREE with one "
                    + "branch per boundary LOOP, walked round. A net with a "
                    + "hole in it has a branch for the outside and one for "
                    + "the hole.",
                GH_ParamAccess.tree);
            parameters.AddCurveParameter(
                "Perimeter Lines",
                "PRL",
                "The boundary of the net at this frame as polylines, a TREE "
                    + "with one branch per boundary group, the same group as "
                    + "branch {i} of Perimeter Nodes: closed when the group "
                    + "is a loop, open when it is a strip. Empty, with "
                    + "animate.perimeter_estimated on the Result to say why, "
                    + "when the boundary could only be estimated from node "
                    + "degree.",
                GH_ParamAccess.tree);
            parameters.AddLineParameter(
                "Columns",
                "CO",
                "The columns at this frame: every tree on its built foot, as "
                    + "a TREE with one branch per COLUMN TREE, that is per "
                    + "foot, each branch holding that tree's trunk and arms "
                    + "together. A member whose ends have met at this frame "
                    + "is not drawn, so a branch can come back short. Empty "
                    + "unless the Result carries columns from Columns "
                    + "upstream.",
                GH_ParamAccess.tree);
            parameters.AddTextParameter(
                "Phase",
                "PH",
                "The word for the moment this geometry is at: reel, raise, "
                    + "finish or hold from an Animate Result, and final from "
                    + "a Result with no frame on it, which stands at its own "
                    + "solved shape.",
                GH_ParamAccess.item);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                // Said in the chin as well as by the empty ports, the way
                // Export says it: without this the component sits under the
                // previous solve's phase word, so a Frame with nothing wired
                // reads "hold" as though a frame were still standing on it.
                Message = "No Result";
                return;
            }

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                FrameGeometry.Set set = FrameGeometry.Build(result);
                data.SetData(0, set.Mesh);
                data.SetDataTree(1, OutputTree.Lines(set.Cables));
                data.SetDataTree(2, OutputTree.Curves(set.PrincipalLines));
                data.SetDataTree(3, OutputTree.Points(set.PrincipalNodes));
                data.SetDataTree(4, OutputTree.Points(set.AnchorGroups));
                data.SetDataTree(5, OutputTree.Points(set.PerimeterNodes));
                data.SetDataTree(6, OutputTree.Curves(set.PerimeterLines));
                data.SetDataTree(7, OutputTree.Lines(set.ColumnBranches));
                data.SetData(8, set.Phase);
                Message = set.Phase;
            }
            catch (Exception error)
            {
                Message = "Invalid";
                ReportException("Frame failed", error);
            }
        }
    }
}
