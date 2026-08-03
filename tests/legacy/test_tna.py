import unittest
from types import SimpleNamespace

import compas
import compas_tna

from tree_forest_compas import TNAInputError
from tree_forest_compas import TNAProblem
from tree_forest_compas import TNASession
from tree_forest_compas import TNATopologyError
from tree_forest_compas import register_tna_pattern
from tree_forest_compas import solve_tna_pattern
from tree_forest_compas import solve_tna_problem


def grid_vertices_faces(n=5):
    vertices = [[float(x), float(y), 0.0] for x in range(n) for y in range(n)]

    def key(x, y):
        return x * n + y

    faces = []
    for x in range(n - 1):
        for y in range(n - 1):
            faces.append(
                [
                    key(x, y),
                    key(x + 1, y),
                    key(x + 1, y + 1),
                    key(x, y + 1),
                ]
            )
    return vertices, faces


def grid_lines(n=3, jitter=0.0):
    pairs = []
    for x in range(n):
        for y in range(n - 1):
            pairs.append(((x, y), (x, y + 1)))
    for y in range(n):
        for x in range(n - 1):
            pairs.append(((x, y), (x + 1, y)))

    lines = []
    for index, (start, end) in enumerate(pairs):
        delta = (index % 5) * jitter
        lines.append(
            [
                [start[0] + delta, start[1] - delta, 0.0],
                [end[0] - delta, end[1] + delta, 0.0],
            ]
        )
    return lines


class RegisterTnaPatternTests(unittest.TestCase):
    def test_register_vertices_faces_keeps_stable_source_mappings(self):
        vertices, faces = grid_vertices_faces(n=3)
        keys = ["node-{}".format(index) for index in range(len(vertices))]

        problem = register_tna_pattern(
            vertices=vertices,
            faces=faces,
            vertex_keys=keys,
            tolerance=1e-6,
            metadata={"case": "face-grid"},
        )

        self.assertIsInstance(problem, TNAProblem)
        self.assertEqual(problem.source_kind, "vertices_faces")
        self.assertEqual(problem.form.number_of_vertices(), 9)
        self.assertEqual(problem.form.number_of_faces(), 4)
        self.assertEqual(problem.source_to_form["node-4"], 4)
        self.assertEqual(problem.form_to_sources[4], ("node-4",))
        self.assertEqual(len(problem.source_edges), 12)
        self.assertEqual(problem.metadata["case"], "face-grid")

    def test_register_lines_merges_noisy_endpoints_with_tolerance(self):
        lines = grid_lines(n=3, jitter=1e-7)

        problem = register_tna_pattern(lines=lines, tolerance=1e-5)

        self.assertEqual(problem.source_kind, "lines")
        self.assertEqual(problem.form.number_of_vertices(), 9)
        self.assertEqual(problem.form.number_of_faces(), 4)
        self.assertEqual(problem.diagnostics["input_endpoint_count"], 24)
        self.assertEqual(problem.diagnostics["merged_endpoint_count"], 15)
        self.assertEqual(len(problem.endpoint_to_source), 24)
        self.assertEqual(len(problem.source_edge_to_form), len(lines))

    def test_register_lines_uses_decimal_precision(self):
        lines = grid_lines(n=3, jitter=1e-4)

        problem = register_tna_pattern(
            lines=lines,
            tolerance=0.0,
            precision=3,
        )

        self.assertEqual(problem.form.number_of_vertices(), 9)
        self.assertEqual(problem.form.number_of_faces(), 4)
        self.assertEqual(problem.diagnostics["precision"], 3)

    def test_rejects_faces_missing(self):
        vertices, _ = grid_vertices_faces(n=3)
        with self.assertRaisesRegex(TNATopologyError, "face"):
            register_tna_pattern(vertices=vertices, faces=[])

    def test_rejects_line_tree_with_compas_fd_guidance(self):
        tree = [
            [[0, 0, 0], [1, 0, 0]],
            [[1, 0, 0], [2, 0, 0]],
            [[1, 0, 0], [1, 1, 0]],
        ]
        with self.assertRaisesRegex(TNATopologyError, "compas_fd"):
            register_tna_pattern(lines=tree)

    def test_rejects_mixed_sources(self):
        vertices, faces = grid_vertices_faces(n=3)
        with self.assertRaises(TNAInputError):
            register_tna_pattern(
                vertices=vertices,
                faces=faces,
                lines=grid_lines(),
            )


class SolveTnaProblemTests(unittest.TestCase):
    def test_zmax_solves_whole_pattern_and_returns_equilibrium_results(self):
        vertices, faces = grid_vertices_faces(n=5)
        problem = register_tna_pattern(vertices=vertices, faces=faces)
        boundary = set()
        for cycle in problem.form.vertices_on_boundaries():
            boundary.update(cycle)
        loads = {
            key: (0.0 if problem.source_to_form[key] in boundary else -1.0)
            for key in problem.source_vertex_order
        }

        session = solve_tna_problem(
            problem,
            support_mode="boundary",
            pz=loads,
            vertical_mode="zmax",
            zmax=2.0,
            density=0.0,
        )

        self.assertIsInstance(session, TNASession)
        self.assertGreater(session.force.number_of_edges(), 0)
        self.assertAlmostEqual(session.diagnostics["zmax_solved"], 2.0, places=6)
        self.assertLess(session.diagnostics["max_free_residual"], 1e-8)
        self.assertLess(session.diagnostics["global_force_error_norm"], 1e-8)
        self.assertEqual(
            session.diagnostics["compression_edge_count"],
            len(session.edge_forces),
        )
        self.assertTrue(all(value < 0.0 for value in session.edge_forces.values()))
        self.assertTrue(all(value < 0.0 for value in session.edge_q.values()))
        self.assertTrue(session.support_reactions)
        self.assertEqual(
            session.effective_form_loads[12],
            (0.0, 0.0, -1.0),
        )
        self.assertAlmostEqual(
            sum(vector[2] for vector in session.support_reactions_by_form.values()),
            -session.diagnostics["active_total_pz"],
            places=7,
        )
        self.assertEqual(
            session.diagnostics["load_sign_convention"],
            "signed analysis XYZ; negative pz acts along negative analysis Z",
        )
        self.assertTrue(any(value is None for value in session.source_to_form.values()))
        self.assertTrue(
            any(value is None for value in session.source_edge_to_form.values())
        )
        self.assertEqual(
            {
                tuple(sorted(edge))
                for edge in session.source_edge_to_form.values()
                if edge is not None
            },
            set(session.edge_q),
        )
        self.assertEqual(
            len(session.diagnostics["removed_source_edge_ids"]),
            sum(
                edge is None
                for edge in session.source_edge_to_form.values()
            ),
        )

    def test_support_keys_and_source_keyed_loads(self):
        vertices, faces = grid_vertices_faces(n=5)
        keys = ["node-{}".format(index) for index in range(len(vertices))]
        problem = register_tna_pattern(
            vertices=vertices,
            faces=faces,
            vertex_keys=keys,
        )

        session = solve_tna_problem(
            problem,
            support_mode="keys",
            support_keys=["node-0", "node-4", "node-20", "node-24"],
            pz={"node-12": -1.0},
            vertical_mode="zmax",
            zmax=2.0,
        )

        self.assertEqual(
            set(session.support_keys),
            {"node-0", "node-4", "node-20", "node-24"},
        )
        self.assertEqual(session.source_nodal_pz["node-12"], -1.0)
        self.assertAlmostEqual(session.diagnostics["active_total_pz"], -1.0)
        self.assertLess(session.diagnostics["global_force_error_norm"], 1e-7)

    def test_selected_support_identity_survives_vertex_welding(self):
        vertices, faces = grid_vertices_faces(n=3)
        vertices.append(vertices[0])
        keys = ["node-{}".format(index) for index in range(9)] + ["corner-alias"]
        problem = register_tna_pattern(
            vertices=vertices,
            faces=faces,
            vertex_keys=keys,
            tolerance=1e-6,
        )

        session = solve_tna_problem(
            problem,
            support_mode="keys",
            support_keys=["corner-alias", "node-2", "node-6", "node-8"],
            pz={"node-4": -1.0},
            vertical_mode="q",
            q_scale=-1.0,
        )

        self.assertIn("corner-alias", session.support_keys)
        self.assertNotIn("node-0", session.support_keys)
        self.assertIn("corner-alias", session.support_reactions)
        self.assertEqual(
            session.support_reactions["corner-alias"],
            session.support_reactions_by_form[
                session.source_to_form["corner-alias"]
            ],
        )

    def test_scalar_load_is_counted_once_per_registered_vertex_after_welding(self):
        vertices, faces = grid_vertices_faces(n=3)
        vertices.append(vertices[0])
        problem = register_tna_pattern(
            vertices=vertices,
            faces=faces,
            tolerance=1e-6,
        )

        session = solve_tna_problem(
            problem,
            pz=-1.0,
            vertical_mode="q",
            q_scale=-1.0,
        )

        self.assertEqual(problem.form.number_of_vertices(), 9)
        self.assertAlmostEqual(session.diagnostics["requested_total_pz"], -9.0)
        self.assertAlmostEqual(sum(session.source_nodal_pz.values()), -9.0)

    def test_reactions_use_analysis_xyz_sign_and_balance_negative_z_load(self):
        vertices, faces = grid_vertices_faces(n=3)
        session = solve_tna_pattern(
            vertices=vertices,
            faces=faces,
            pz={4: -2.0},
            vertical_mode="q",
            q_scale=-1.0,
            density=0.0,
        )

        self.assertEqual(session.effective_form_loads[4], (0.0, 0.0, -2.0))
        self.assertAlmostEqual(
            sum(vector[2] for vector in session.support_reactions_by_form.values()),
            2.0,
            places=8,
        )
        self.assertLess(session.diagnostics["global_force_error_norm"], 1e-8)
        for form_key, reaction in session.support_reactions_by_form.items():
            stored_residual = session.form.vertex_attributes(
                form_key, ["_rx", "_ry", "_rz"]
            )
            self.assertEqual(
                reaction,
                tuple(float(value) for value in stored_residual),
            )

    def test_nonzero_density_is_rejected_until_selfweight_sign_is_safe(self):
        vertices, faces = grid_vertices_faces(n=3)
        problem = register_tna_pattern(vertices=vertices, faces=faces)

        with self.assertRaisesRegex(
            TNAInputError,
            "explicit signed nodal pz",
        ):
            solve_tna_problem(
                problem,
                pz={4: -1.0},
                vertical_mode="q",
                q_scale=-1.0,
                density=1.0,
            )

    def test_q_mode_reports_effective_scaled_q(self):
        problem = register_tna_pattern(
            lines=grid_lines(n=3, jitter=1e-7),
            tolerance=1e-5,
        )
        center = problem.endpoint_to_source[(3, 0)]
        # Locate the canonical vertex nearest the plan centre rather than relying
        # on line order in downstream callers.
        center = min(
            problem.source_vertices,
            key=lambda key: (
                (problem.source_vertices[key][0] - 1.0) ** 2
                + (problem.source_vertices[key][1] - 1.0) ** 2
            ),
        )

        session = solve_tna_problem(
            problem,
            pz={center: -1.0},
            vertical_mode="q",
            q_scale=-2.0,
            density=0.0,
        )

        self.assertEqual(session.diagnostics["vertical_mode"], "q")
        self.assertEqual(session.diagnostics["vertical_scale"], -2.0)
        self.assertTrue(all(value < 0.0 for value in session.edge_q.values()))
        for edge, effective_q in session.edge_q.items():
            u, v = edge
            raw_q = session.form.edge_attribute((u, v), "q")
            if raw_q is None:
                raw_q = session.form.edge_attribute((v, u), "q")
            self.assertAlmostEqual(effective_q, -2.0 * float(raw_q))
        self.assertLess(session.diagnostics["global_force_error_norm"], 1e-8)

    def test_convenience_wrapper_records_official_versions(self):
        vertices, faces = grid_vertices_faces(n=3)
        loads = [0.0] * len(vertices)
        loads[4] = -1.0

        session = solve_tna_pattern(
            vertices=vertices,
            faces=faces,
            pz=loads,
            vertical_mode="q",
            q_scale=-1.0,
        )

        self.assertEqual(session.metadata["versions"]["compas"], compas.__version__)
        self.assertEqual(
            session.metadata["versions"]["compas_tna"],
            compas_tna.__version__,
        )
        self.assertEqual(session.metadata["versions"]["compas"], "2.15.1")
        self.assertEqual(session.metadata["versions"]["compas_tna"], "0.7.0")

    def test_registered_problem_is_not_mutated_by_solve(self):
        vertices, faces = grid_vertices_faces(n=3)
        problem = register_tna_pattern(vertices=vertices, faces=faces)
        original_vertices = list(problem.form.vertices())
        original_faces = list(problem.form.faces())

        solve_tna_problem(
            problem,
            pz={4: -1.0},
            vertical_mode="q",
            q_scale=-1.0,
        )

        self.assertEqual(list(problem.form.vertices()), original_vertices)
        self.assertEqual(list(problem.form.faces()), original_faces)
        self.assertFalse(any(problem.form.vertices_attribute("is_support")))

    def test_equivalent_problem_contract_survives_component_module_refresh(self):
        vertices, faces = grid_vertices_faces(n=3)
        problem = register_tna_pattern(vertices=vertices, faces=faces)
        stale_component_problem = SimpleNamespace(**problem.__dict__)

        session = solve_tna_problem(
            stale_component_problem,
            pz={4: -1.0},
            vertical_mode="q",
            q_scale=-1.0,
        )

        self.assertIsInstance(session, TNASession)
        self.assertLess(session.diagnostics["global_force_error_norm"], 1e-8)


if __name__ == "__main__":
    unittest.main()
