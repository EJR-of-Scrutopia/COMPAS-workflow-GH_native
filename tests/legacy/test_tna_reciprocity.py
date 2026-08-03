"""Reciprocity reporting for the legacy TNA solver core.

A form edge and its dual force edge are unoriented lines, so the reciprocal
condition is satisfied when they are parallel *or* antiparallel. ``compas_tna``
stores an oriented direction difference in the ``_a`` edge attribute, and its
own source notes that this "does not account for flipped edges". Reporting that
raw number made a perfectly reciprocal solve read as a 180-degree error.
"""

import unittest

from tree_forest_compas import register_tna_pattern
from tree_forest_compas import solve_tna_problem
from tree_forest_compas.tna import _unoriented_angle


def square_grid(n):
    """Return keyed vertices and quad faces for an ``n`` x ``n`` plan grid."""
    keys = []
    vertices = []
    index = {}
    for row in range(n + 1):
        for column in range(n + 1):
            key = "n{}_{}".format(row, column)
            index[row, column] = key
            keys.append(key)
            vertices.append((float(column), float(row), 0.0))
    faces = [
        [
            index[row, column],
            index[row, column + 1],
            index[row + 1, column + 1],
            index[row + 1, column],
        ]
        for row in range(n)
        for column in range(n)
    ]
    return dict(zip(keys, vertices)), faces, index


class UnorientedAngleTests(unittest.TestCase):
    def test_parallel_and_antiparallel_are_both_zero_error(self):
        self.assertEqual(_unoriented_angle(0.0), 0.0)
        self.assertEqual(_unoriented_angle(180.0), 0.0)
        self.assertEqual(_unoriented_angle(-180.0), 0.0)

    def test_flipped_edge_reports_its_small_true_deviation(self):
        # The reciprocity error of a 177.9-degree difference is 2.1 degrees.
        self.assertAlmostEqual(_unoriented_angle(177.9), 2.1, places=9)
        self.assertAlmostEqual(_unoriented_angle(-2.1), 2.1, places=9)

    def test_perpendicular_is_the_worst_possible_error(self):
        self.assertEqual(_unoriented_angle(90.0), 90.0)

    def test_result_never_exceeds_ninety_degrees(self):
        for value in (0.0, 45.0, 90.0, 135.0, 180.0, 200.0, 359.0, -270.0):
            self.assertLessEqual(_unoriented_angle(value), 90.0)
            self.assertGreaterEqual(_unoriented_angle(value), 0.0)


class ReciprocityDiagnosticTests(unittest.TestCase):
    def test_converged_boundary_supported_pattern_reports_zero_error(self):
        vertices, faces, _ = square_grid(4)
        problem = register_tna_pattern(vertices=vertices, faces=faces)
        session = solve_tna_problem(
            problem,
            support_mode="boundary",
            pz=-1.0,
            vertical_mode="zmax",
            zmax=1.5,
        )

        self.assertAlmostEqual(
            session.diagnostics["max_reciprocal_angle_deviation"],
            0.0,
            places=9,
        )

    def test_flipped_edges_are_not_reported_as_a_180_degree_error(self):
        """The regression: a corner-supported solve reported 180 degrees.

        The raw ``compas_tna`` attribute still reaches 180 here because some
        dual edges are antiparallel. The reported reciprocity error must be the
        genuine 27-degree non-convergence, not the flipped-edge artefact.
        """
        vertices, faces, index = square_grid(4)
        problem = register_tna_pattern(vertices=vertices, faces=faces)
        corners = [
            index[0, 0],
            index[0, 4],
            index[4, 0],
            index[4, 4],
        ]
        session = solve_tna_problem(
            problem,
            support_mode="keys",
            support_keys=corners,
            pz=-1.0,
            vertical_mode="zmax",
            zmax=2.0,
            horizontal_kmax=100,
        )

        raw = session.diagnostics["max_raw_form_force_angle"]
        reported = session.diagnostics["max_reciprocal_angle_deviation"]

        self.assertAlmostEqual(raw, 180.0, places=6)
        self.assertLessEqual(reported, 90.0)
        self.assertAlmostEqual(reported, 27.2503, places=3)

    def test_more_horizontal_iterations_converge_the_reciprocal(self):
        """The same pattern reaches a parallel reciprocal with more iterations.

        This documents that ``horizontal_kmax`` is a real convergence control,
        while leaving the shipped default unchanged.
        """
        vertices, faces, index = square_grid(4)
        corners = [
            index[0, 0],
            index[0, 4],
            index[4, 0],
            index[4, 4],
        ]

        def reciprocity(kmax):
            problem = register_tna_pattern(vertices=vertices, faces=faces)
            session = solve_tna_problem(
                problem,
                support_mode="keys",
                support_keys=corners,
                pz=-1.0,
                vertical_mode="zmax",
                zmax=2.0,
                horizontal_kmax=kmax,
            )
            return session.diagnostics["max_reciprocal_angle_deviation"]

        self.assertGreater(reciprocity(100), 1.0)
        self.assertAlmostEqual(reciprocity(500), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
