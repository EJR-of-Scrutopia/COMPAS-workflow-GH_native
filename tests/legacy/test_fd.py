import math
import unittest

import numpy as np

from tree_forest_compas.fd import FDInputError
from tree_forest_compas.fd import joint_force_polygons
from tree_forest_compas.fd import solve_fd_network


def _catenary_lines(divisions=10, length=100.0):
    return [
        [
            [length * index / divisions, 0.0, 0.0],
            [length * (index + 1) / divisions, 0.0, 0.0],
        ]
        for index in range(divisions)
    ]


class FDWorkflowTests(unittest.TestCase):
    def test_catenary_is_registered_and_solved_as_one_network(self):
        lines = _catenary_lines()
        loads = np.zeros((11, 3))
        loads[1:-1, 2] = -10.0

        session = solve_fd_network(
            lines,
            fixed=[0, 10],
            forcedensities=10.0,
            loads=loads,
        )

        self.assertEqual(len(session.source_edges), 10)
        self.assertEqual(len(session.equilibrium_vertices), 11)
        self.assertEqual(len(session.components), 1)
        self.assertAlmostEqual(max(session.member_forces), 109.6585609973)
        free = np.asarray(session.residuals)[1:-1]
        self.assertLess(np.linalg.norm(free, axis=1).max(), 1e-10)

    def test_local_degree_two_loaded_nodes_make_closed_triangles(self):
        lines = _catenary_lines()
        loads = np.zeros((11, 3))
        loads[1:-1, 2] = -10.0
        session = solve_fd_network(
            lines, fixed=[0, 10], forcedensities=10.0, loads=loads
        )

        polygon = joint_force_polygons(session, nodes=[5])[0]

        self.assertEqual(len(polygon.member_vectors), 2)
        self.assertEqual(len(polygon.points), 5)
        self.assertLess(polygon.closure_error, 1e-10)

    def test_support_polygon_includes_the_reaction(self):
        lines = _catenary_lines()
        loads = np.zeros((11, 3))
        loads[1:-1, 2] = -10.0
        session = solve_fd_network(
            lines, fixed=[0, 10], forcedensities=10.0, loads=loads
        )

        polygon = joint_force_polygons(session, nodes=[0])[0]

        self.assertTrue(any(abs(value) > 0.0 for value in polygon.reaction_vector))
        self.assertLess(polygon.closure_error, 1e-10)

    def test_source_segment_force_alignment_survives_reversed_lines(self):
        lines = list(reversed(_catenary_lines()))
        loads = np.zeros((11, 3))
        loads[1:-1, 2] = -10.0
        session = solve_fd_network(
            lines, fixed=[0, 10], forcedensities=10.0, loads=loads
        )

        self.assertEqual(len(session.member_forces), len(lines))
        self.assertTrue(all(math.isfinite(value) for value in session.member_forces))

    def test_every_connected_component_requires_a_support(self):
        lines = [
            [[0, 0, 0], [1, 0, 0]],
            [[10, 0, 0], [11, 0, 0]],
        ]

        with self.assertRaisesRegex(FDInputError, "Every connected component"):
            solve_fd_network(lines, fixed=[0], forcedensities=1.0)

    def test_zero_force_density_is_rejected(self):
        with self.assertRaisesRegex(FDInputError, "non-zero"):
            solve_fd_network(
                _catenary_lines(2), fixed=[0, 2], forcedensities=0.0
            )


if __name__ == "__main__":
    unittest.main()
