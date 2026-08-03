"""Naming the mesh defect that stops a pattern becoming a COMPAS mesh.

``Mesh.is_valid`` returns a bare boolean, so the registrar used to reject a
pattern without saying what was wrong or where. Measured against COMPAS 2.15.1,
``is_valid`` is False for exactly two conditions: a directed halfedge claimed by
more than one face (a duplicated or same-wound face), and an edge shared by more
than two faces (a non-manifold edge). Both are reportable with locations, which
is the difference between a fixable message and a dead end.
"""

import unittest

from tree_forest_compas import TNATopologyError
from tree_forest_compas import register_tna_pattern
from tree_forest_compas.tna import describe_mesh_defects


GRID = [
    (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0),
    (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (2.0, 1.0, 0.0),
    (0.0, 2.0, 0.0), (1.0, 2.0, 0.0), (2.0, 2.0, 0.0),
]
FACES = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]


class DescribeMeshDefectsTests(unittest.TestCase):
    def test_a_clean_quad_grid_has_no_defects(self):
        self.assertEqual(describe_mesh_defects(GRID, FACES), ())

    def test_a_duplicated_face_is_reported(self):
        defects = describe_mesh_defects(GRID, FACES + [[0, 1, 4, 3]])

        self.assertTrue(defects)
        joined = " ".join(defects)
        self.assertIn("face", joined.lower())
        # The duplicate is face index 4, and its location must be quoted so the
        # offending region can be found in the CAD model.
        self.assertIn("4", joined)

    def test_a_non_manifold_edge_is_reported(self):
        vertices = list(GRID) + [(0.0, -1.0, 0.0)]
        defects = describe_mesh_defects(vertices, FACES + [[1, 9, 4]])

        self.assertTrue(defects)
        self.assertIn("edge", " ".join(defects).lower())

    def test_consistent_winding_is_not_reported_as_a_defect(self):
        """Reversed winding is a real problem but not the one is_valid rejects.

        Reporting it here would send the user hunting for the wrong thing.
        """
        flipped = [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 8, 5, 7]]
        self.assertEqual(describe_mesh_defects(GRID, flipped), ())

    def test_defect_text_carries_coordinates(self):
        defects = describe_mesh_defects(GRID, FACES + [[0, 1, 4, 3]])
        joined = " ".join(defects)

        # A coordinate triple has to appear so the defect is locatable.
        self.assertIn("(", joined)
        self.assertIn(")", joined)


class RegistrationErrorTests(unittest.TestCase):
    def test_duplicate_face_error_names_the_defect(self):
        with self.assertRaises(TNATopologyError) as raised:
            register_tna_pattern(
                vertices=GRID,
                faces=FACES + [[0, 1, 4, 3]],
            )

        message = str(raised.exception)
        self.assertIn("face", message.lower())
        # The old message said only that the mesh was not valid.
        self.assertNotEqual(
            message.strip(),
            "The merged vertices/faces do not form a valid oriented COMPAS mesh.",
        )

    def test_non_manifold_edge_error_names_the_defect(self):
        vertices = list(GRID) + [(0.0, -1.0, 0.0)]
        with self.assertRaises(TNATopologyError) as raised:
            register_tna_pattern(vertices=vertices, faces=FACES + [[1, 9, 4]])

        self.assertIn("edge", str(raised.exception).lower())

    def test_a_clean_pattern_still_registers(self):
        problem = register_tna_pattern(vertices=GRID, faces=FACES)
        self.assertEqual(problem.form.number_of_faces(), 4)


if __name__ == "__main__":
    unittest.main()
