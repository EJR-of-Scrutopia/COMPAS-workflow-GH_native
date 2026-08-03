import unittest

import numpy as np

from tree_forest_compas.fd import solve_fd_network
from tree_forest_compas.graphic_statics import GraphicStaticsError
from tree_forest_compas.graphic_statics import stitch_fd_force_diagram


def _chain_lines(divisions=10, length=100.0):
    return [
        [
            [length * index / divisions, 0.0, 0.0],
            [length * (index + 1) / divisions, 0.0, 0.0],
        ]
        for index in range(divisions)
    ]


def _catenary_session(extra_node=None, extra_load=0.0):
    loads = np.zeros((11, 3))
    loads[1:-1, 2] = -10.0
    if extra_node is not None:
        loads[int(extra_node), 2] -= float(extra_load)
    return solve_fd_network(
        _chain_lines(),
        fixed=[0, 10],
        forcedensities=10.0,
        loads=loads,
    )


def _distance(a, b):
    return float(np.linalg.norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)))


class GlobalGraphicStaticsTests(unittest.TestCase):
    def test_catenary_becomes_one_pole_fan_and_triangle(self):
        session = _catenary_session()

        result = stitch_fd_force_diagram(
            session,
            plane_xaxis=(1.0, 0.0, 0.0),
            plane_yaxis=(0.0, 0.0, 1.0),
        )

        self.assertEqual(result.chain_path, tuple(range(11)))
        self.assertEqual(result.chain_edges, tuple(range(10)))
        self.assertIsNotNone(result.pole)
        self.assertEqual(len(result.load_line_points), 10)
        self.assertEqual(len(result.boundary_loops), 1)
        self.assertEqual(len(result.boundary_loops[0].simplified_points), 4)
        self.assertTrue(result.fits_outer_envelope)
        self.assertEqual(result.force_dimension, 2)
        self.assertLess(result.max_joint_closure_error, 1e-10)
        self.assertLess(result.max_glue_error, 1e-10)

        for edge_index, line in enumerate(result.member_lines):
            self.assertAlmostEqual(
                _distance(*line),
                abs(session.member_forces[edge_index]),
                places=9,
            )
            self.assertTrue(
                _distance(line[0], result.pole) < 1e-9
                or _distance(line[1], result.pole) < 1e-9
            )

    def test_automatic_plane_detects_xz_catenary(self):
        result = stitch_fd_force_diagram(_catenary_session())

        self.assertIsNotNone(result.pole)
        self.assertLess(result.form_planarity_error, 1e-12)
        self.assertLess(result.force_planarity_error, 1e-12)
        self.assertAlmostEqual(abs(result.plane_normal[1]), 1.0, places=9)

    def test_moving_point_load_preserves_fan_topology(self):
        diagrams = []
        for node in (1, 5, 9):
            result = stitch_fd_force_diagram(
                _catenary_session(extra_node=node, extra_load=30.0),
                plane_xaxis=(1.0, 0.0, 0.0),
                plane_yaxis=(0.0, 0.0, 1.0),
            )
            diagrams.append(result)
            self.assertEqual(result.chain_path, tuple(range(11)))
            self.assertIsNotNone(result.pole)
            self.assertEqual(len(result.boundary_loops[0].simplified_points), 4)
            self.assertTrue(result.fits_outer_envelope)

        middle_lengths = [
            max(_distance(side.start, side.end) for side in result.load_lines)
            for result in diagrams
        ]
        self.assertTrue(all(abs(value - 40.0) < 1e-9 for value in middle_lengths))

    def test_source_alignment_survives_reversed_shuffled_segments(self):
        lines = list(reversed(_chain_lines()))
        lines[3] = list(reversed(lines[3]))
        loads = np.zeros((11, 3))
        loads[1:-1, 2] = -10.0
        session = solve_fd_network(
            lines,
            fixed=[0, 10],
            forcedensities=10.0,
            loads=loads,
        )

        result = stitch_fd_force_diagram(
            session,
            plane_xaxis=(1.0, 0.0, 0.0),
            plane_yaxis=(0.0, 0.0, 1.0),
        )

        self.assertEqual(len(result.member_lines), len(lines))
        for edge_index, line in enumerate(result.member_lines):
            self.assertAlmostEqual(
                _distance(*line),
                abs(session.member_forces[edge_index]),
                places=9,
            )

    def test_degree_three_tree_cells_stitch_globally(self):
        lines = [
            [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[0.0, 1.0, 0.0], [-1.0, 2.0, 0.0]],
            [[0.0, 1.0, 0.0], [1.0, 2.0, 0.0]],
        ]
        loads = np.zeros((4, 3))
        loads[2] = [-1.0, 1.0, 0.0]
        loads[3] = [1.0, 1.0, 0.0]
        session = solve_fd_network(
            lines,
            fixed=[0],
            forcedensities=1.0,
            loads=loads,
        )

        result = stitch_fd_force_diagram(
            session,
            plane_xaxis=(1.0, 0.0, 0.0),
            plane_yaxis=(0.0, 1.0, 0.0),
        )

        self.assertFalse(result.chain_path)
        self.assertIsNone(result.pole)
        self.assertEqual(len(result.cells), 4)
        self.assertEqual(len(result.member_lines), 3)
        self.assertEqual(len(result.boundary_loops), 1)
        self.assertEqual(len(result.boundary_loops[0].simplified_points), 4)
        self.assertLess(result.max_joint_closure_error, 1e-10)
        self.assertLess(result.max_glue_error, 1e-10)

    def test_wrong_plane_is_rejected(self):
        with self.assertRaisesRegex(GraphicStaticsError, "not planar"):
            stitch_fd_force_diagram(
                _catenary_session(),
                plane_xaxis=(1.0, 0.0, 0.0),
                plane_yaxis=(0.0, 1.0, 0.0),
            )

    def test_compression_arch_uses_the_same_global_fan_contract(self):
        loads = np.zeros((11, 3))
        loads[1:-1, 2] = -10.0
        session = solve_fd_network(
            _chain_lines(),
            fixed=[0, 10],
            forcedensities=-10.0,
            loads=loads,
        )

        result = stitch_fd_force_diagram(session)

        self.assertTrue(all(value < 0.0 for value in session.member_forces))
        self.assertIsNotNone(result.pole)
        self.assertTrue(result.fits_outer_envelope)
        self.assertEqual(len(result.boundary_loops[0].simplified_points), 4)

    def test_parallel_load_bare_tree_reports_degenerate_axial_reciprocal(self):
        lines = [
            [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            [[0.0, 0.0, 1.0], [-1.0, 0.0, 2.0]],
            [[0.0, 0.0, 1.0], [1.0, 0.0, 2.0]],
        ]
        loads = np.zeros((4, 3))
        loads[2:, 2] = -1.0
        session = solve_fd_network(
            lines,
            fixed=[0],
            forcedensities=1.0,
            loads=loads,
        )

        result = stitch_fd_force_diagram(session)

        self.assertEqual(result.force_dimension, 1)
        self.assertIn("bare one-root tree", result.report)
        self.assertFalse(result.fits_outer_envelope)

    def test_cyclic_fd_graph_routes_to_ags(self):
        lines = [
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
            [[1.0, 0.0, 0.0], [0.5, 1.0, 0.0]],
            [[0.5, 1.0, 0.0], [0.0, 0.0, 0.0]],
        ]
        session = solve_fd_network(
            lines,
            fixed=[0, 1, 2],
            forcedensities=1.0,
        )

        with self.assertRaisesRegex(GraphicStaticsError, "AGSGraphicStatics"):
            stitch_fd_force_diagram(session)


if __name__ == "__main__":
    unittest.main()
