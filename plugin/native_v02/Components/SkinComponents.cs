#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components
{
    /// <summary>
    /// Skin: the cells the surface is built from, one closed polyline per
    /// face of the thrust mesh, banded into courses by height. The
    /// ready-made Cells and Courses inputs for Export, which flattens them
    /// itself. Moved here from Deconstruct, which is geometry only; the
    /// mechanism is unchanged.
    /// </summary>
    public sealed class SkinComponent : NativeComponentBase
    {
        public SkinComponent()
            : base(
                "Skin",
                "Skin",
                "One closed polyline per face of the thrust mesh, banded into "
                    + "courses by Course Height: the Cells and Courses for "
                    + "Export, which flattens them itself.",
                ComponentCategories.Visualise,
                "skin")
        {
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "A solved TNA Result. FD carries no faces and gives nothing.",
                GH_ParamAccess.item);
            parameters.AddNumberParameter(
                "Course Height",
                "CH",
                "Band height in metres for the Face Courses output: faces are "
                    + "banded by centroid height from the lowest face upward, "
                    + "bottom row 0. Minimum 1 mm.",
                GH_ParamAccess.item,
                0.35);
            parameters[1].Optional = true;
        }

        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddCurveParameter(
                "Face Polylines",
                "FP",
                "One closed polyline per Thrust Mesh face, as a TREE branched "
                    + "by COURSE (path = course, 0-up from the bottom): the "
                    + "ready-made Cells input for Export. Wire it straight in; "
                    + "Export's Cells port flattens the tree itself. Empty for "
                    + "FD.",
                GH_ParamAccess.tree);
            parameters.AddIntegerParameter(
                "Face Courses",
                "FC",
                "The course per face, branched and ordered exactly as Face "
                    + "Polylines, so the pairing survives: the ready-made "
                    + "Courses input for Export. Wire it straight in; Export's "
                    + "Courses port flattens the tree itself, and the course "
                    + "index is repeated per item, so the flatten keeps the "
                    + "pairing. Empty for FD.",
                GH_ParamAccess.tree);
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                return;
            }
            double courseHeight = 0.35;
            data.GetData(1, ref courseHeight);
            // Negated comparison, not "<= 0": NaN fails every comparison, so
            // "NaN <= 0" would sail past a positivity guard and floor every
            // face to course 0; a tiny positive would overflow the int cast
            // in FaceCourses. 1 mm is the sane floor for a physical course.
            if (!(courseHeight > 0.001))
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "Course Height must be at least 1 mm; using 0.35 m.");
                courseHeight = 0.35;
            }

            try
            {
                IReadOnlyList<string> errors = result.Validate();
                if (errors.Count > 0)
                    throw new InvalidOperationException(string.Join(" ", errors));

                // The one TNA test every reader of a Result shares. Writing
                // the four clauses again here would be a second place to
                // drift from it.
                bool isTna = ResultTables.IsTna(result);
                Mesh mesh = isTna ? DeconstructComponent.ThrustMesh(result) : new Mesh();
                if (mesh.Faces.Count == 0)
                {
                    // The parenthesis is only true of the FD path. A TNA
                    // Result whose form graph carries no faces reaches this
                    // branch too, and telling its author it is an FD Result
                    // would send them looking for the wrong fault.
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Remark,
                        isTna
                            ? "No faces on this Result, so there are no cells."
                            : "No faces on this Result (FD carries none), so "
                                + "there are no cells.");
                }

                IReadOnlyList<PolylineCurve> facePolylines = FacePolylines(mesh);
                IReadOnlyList<int> faceCourses = FaceCourses(mesh, courseHeight);
                var faceByCourse = new List<List<Curve>>();
                var courseByCourse = new List<List<int>>();
                int courseCount = faceCourses.Count == 0 ? 0 : faceCourses.Max() + 1;
                for (int c = 0; c < courseCount; c++)
                {
                    faceByCourse.Add(new List<Curve>());
                    courseByCourse.Add(new List<int>());
                }
                for (int i = 0; i < facePolylines.Count; i++)
                {
                    int course = i < faceCourses.Count ? faceCourses[i] : 0;
                    if (course < 0 || course >= courseCount)
                        continue;
                    faceByCourse[course].Add(facePolylines[i]);
                    courseByCourse[course].Add(course);
                }
                data.SetDataTree(0, OutputTree.Curves(faceByCourse));
                data.SetDataTree(1, OutputTree.Integers(courseByCourse));
                Message = $"{facePolylines.Count} cells, {courseCount} courses";
            }
            catch (Exception error)
            {
                Message = "Invalid";
                ReportException("Skin failed", error);
            }
        }

        /// <summary>
        /// One mesh face's corner points, in winding order: three for a
        /// triangle, four for a quad. <see cref="FacePolylines"/> and
        /// <see cref="FaceCourses"/> both read a face's corners this
        /// way, so the corner/count logic is written once, not twice.
        /// </summary>
        private static IReadOnlyList<Point3d> FaceCorners(
            Mesh mesh,
            MeshFace face)
        {
            var points = new List<Point3d>(4)
            {
                mesh.Vertices[face.A],
                mesh.Vertices[face.B],
                mesh.Vertices[face.C]
            };
            if (face.IsQuad)
                points.Add(mesh.Vertices[face.D]);
            return points;
        }

        /// <summary>
        /// One closed polyline per mesh face, in face order: Export takes
        /// these as authored Cells verbatim (it drops z and dedupes the
        /// closing repeat itself). Internal because EXPORT calls it too,
        /// for the tessellation it builds when nobody wired one: the same
        /// code, so wiring Skin in later changes the courses and nothing
        /// else.
        /// </summary>
        internal static IReadOnlyList<PolylineCurve> FacePolylines(Mesh mesh)
        {
            var polylines = new List<PolylineCurve>(mesh.Faces.Count);
            for (int i = 0; i < mesh.Faces.Count; i++)
            {
                IReadOnlyList<Point3d> corners =
                    FaceCorners(mesh, mesh.Faces[i]);
                var points = new List<Point3d>(corners.Count + 1);
                points.AddRange(corners);
                points.Add(points[0]);
                polylines.Add(new PolylineCurve(points));
            }
            return polylines;
        }

        /// <summary>
        /// The course per face, aligned with <see cref="FacePolylines"/>:
        /// centroid heights banded from the lowest face upward, so the
        /// bottom row is 0 and nothing is ever sorted -- sorting is
        /// exactly what would break the one-to-one pairing the Export
        /// component's Cells/Courses inputs rely on.
        /// </summary>
        private static IReadOnlyList<int> FaceCourses(
            Mesh mesh,
            double courseHeight)
        {
            var centroids = new double[mesh.Faces.Count];
            double lowest = double.PositiveInfinity;
            for (int i = 0; i < mesh.Faces.Count; i++)
            {
                IReadOnlyList<Point3d> corners =
                    FaceCorners(mesh, mesh.Faces[i]);
                double z = 0.0;
                foreach (Point3d corner in corners)
                    z += corner.Z;
                centroids[i] = z / corners.Count;
                if (centroids[i] < lowest)
                    lowest = centroids[i];
            }
            var courses = new int[mesh.Faces.Count];
            for (int i = 0; i < mesh.Faces.Count; i++)
            {
                courses[i] = (int)Math.Floor(
                    (centroids[i] - lowest) / courseHeight);
            }
            return courses;
        }
    }
}
