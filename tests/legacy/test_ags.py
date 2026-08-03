import math
import unittest

from tree_forest_compas.ags import AGSRegistrationError
from tree_forest_compas.ags import solve_planar_graphic_statics


def _single_panel_system():
    return [
        [[3.0, 3.0, 0.0], [3.6695631068, 5.0086893204, 0.0]],
        [[6.0, -2.0, 0.0], [6.0, 0.0, 0.0]],
        [[0.0, -2.0, 0.0], [0.0, 0.0, 0.0]],
        [[0.0, 0.0, 0.0], [-2.0, 0.0, 0.0]],
        [[0.0, 0.0, 0.0], [3.0, 3.0, 0.0]],
        [[3.0, 3.0, 0.0], [6.0, 0.0, 0.0]],
        [[6.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
    ]


class AGSWorkflowTests(unittest.TestCase):
    def test_whole_planar_system_builds_reciprocal_diagrams(self):
        result = solve_planar_graphic_statics(
            _single_panel_system(),
            reference_source_edge=0,
            reference_force=-3.0,
        )

        self.assertEqual(result.form.number_of_vertices(), 7)
        self.assertEqual(result.form.number_of_edges(), 7)
        self.assertEqual(result.force.number_of_edges(), 7)
        self.assertEqual(len(result.source_edge_to_form_edge), 7)
        self.assertEqual(len(result.source_edge_to_force_edge), 7)
        self.assertEqual(len(result.member_forces), 7)
        self.assertAlmostEqual(result.source_forces[0], -3.0)
        self.assertLess(max(abs(value) for value in result.angle_deviations), 1e-8)
        self.assertEqual(result.nullity, 1)
        self.assertEqual(result.mechanisms, 0)
        self.assertIn("COMPAS AGS solve complete", result.report)

    def test_force_solution_is_scaled_by_reference_force(self):
        a = solve_planar_graphic_statics(
            _single_panel_system(),
            reference_source_edge=0,
            reference_force=-3.0,
        )
        b = solve_planar_graphic_statics(
            _single_panel_system(),
            reference_source_edge=0,
            reference_force=-6.0,
        )

        for first, second in zip(a.source_forces, b.source_forces):
            self.assertAlmostEqual(second, 2.0 * first)

    def test_rejects_non_coplanar_linework(self):
        lines = _single_panel_system()
        lines[0][1][2] = 1.0

        with self.assertRaisesRegex(AGSRegistrationError, "two-dimensional"):
            solve_planar_graphic_statics(lines)

    def test_rejects_zero_reference_force(self):
        with self.assertRaisesRegex(AGSRegistrationError, "non-zero"):
            solve_planar_graphic_statics(
                _single_panel_system(),
                reference_force=0.0,
            )

    def test_all_member_forces_are_finite(self):
        result = solve_planar_graphic_statics(
            _single_panel_system(),
            reference_force=-3.0,
        )

        self.assertTrue(all(math.isfinite(value) for value in result.member_forces))

    def test_independent_lists_and_external_roles_are_explicit(self):
        result = solve_planar_graphic_statics(
            _single_panel_system(),
            independent_source_edges=[0],
            independent_forces=[-3.0],
            load_source_edges=[0],
            reaction_source_edges=[1, 2],
        )

        self.assertEqual(result.independent_source_edges, (0,))
        self.assertEqual(result.independent_forces, (-3.0,))
        self.assertEqual(result.source_roles[0], "load")
        self.assertEqual(result.source_roles[1], "reaction")
        self.assertEqual(result.source_roles[2], "reaction")
        self.assertEqual(len(result.external_force_edges), 4)

    def test_wrong_number_of_independent_forces_is_rejected(self):
        with self.assertRaisesRegex(
            AGSRegistrationError, "independent force state"
        ):
            solve_planar_graphic_statics(
                _single_panel_system(),
                independent_source_edges=[0, 1],
                independent_forces=[-3.0, -2.0],
            )


if __name__ == "__main__":
    unittest.main()
