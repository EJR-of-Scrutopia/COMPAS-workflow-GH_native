from __future__ import annotations

import pytest


np = pytest.importorskip("numpy")

from tree_forest_compas.fd import FDInputError
from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.structural import StructuralAnalysisCase


def test_fd_registration_welds_shared_endpoints():
    problem = register_fd_network(
        (
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        )
    )

    assert problem.source_vertices == (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
    )
    assert problem.source_edges == ((0, 1), (1, 2))
    assert problem.components == ((0, 1, 2),)


def test_fd_registration_rejects_collapsed_segment():
    with pytest.raises(FDInputError, match="collapses"):
        register_fd_network(
            (((0.0, 0.0, 0.0), (1.0e-9, 0.0, 0.0)),),
            tolerance=1.0e-6,
        )


def test_structural_case_type_is_available_without_optional_backends():
    assert StructuralAnalysisCase.__name__ == "StructuralAnalysisCase"
