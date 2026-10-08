"""A cantilever, checked against PL^3 / 3EI.

Every other result in this package is trusted because this one is right.
The ULS factor of 1.35 is part of the expected answer: LoadCombination.ULS
multiplies a DL case by 1.35, so the closed form must too.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ananke_fea.compat import analyse, apply_patches, require_backend

LENGTH = 4.0
MODULUS = 30e9
WIDTH = DEPTH = 0.3
TIP_LOAD = 1000.0
ULS_FACTOR = 1.35

SECOND_MOMENT = WIDTH * DEPTH**3 / 12.0
CLOSED_FORM = ULS_FACTOR * TIP_LOAD * LENGTH**3 / (3.0 * MODULUS * SECOND_MOMENT)


@pytest.fixture(scope="module")
def solved():
    require_backend()
    apply_patches()

    from compas_fea2.model import BeamElement, ElasticIsotropic, FixedBC
    from compas_fea2.model import Model, Node, Part, RectangularSection
    from compas_fea2.problem import LoadCombination, Problem, StaticStep
    from compas_fea2.results import DisplacementFieldResults, ReactionFieldResults

    model = Model(name="cantilever")
    part = Part(name="beam")
    nodes = []
    for index in range(9):
        node = Node(xyz=[index * (LENGTH / 8.0), 0.0, 0.0])
        part.add_node(node)
        nodes.append(node)

    material = ElasticIsotropic(E=MODULUS, v=0.2, density=2400)
    section = RectangularSection(w=WIDTH, h=DEPTH, material=material)
    for start, end in zip(nodes[:-1], nodes[1:]):
        part.add_element(
            BeamElement(nodes=[start, end], section=section, frame=[0, 0, 1])
        )

    model.add_part(part)
    model.add_bcs(FixedBC(), nodes=[nodes[0]])

    problem = Problem(name="tip_load")
    step = StaticStep()
    step.add_uniform_node_load(nodes=[nodes[-1]], z=-TIP_LOAD, load_case="DL")
    step.combination = LoadCombination.ULS()
    step.add_output(DisplacementFieldResults)
    step.add_output(ReactionFieldResults)
    problem.add_step(step)
    model.add_problem(problem)

    directory = Path(tempfile.mkdtemp(prefix="ananke_cantilever_")) / "run"
    analyse(problem, directory)
    return step, nodes


def test_tip_deflection_matches_closed_form(solved):
    step, _ = solved
    results = list(step.displacement_field.results)
    peak = max(results, key=lambda result: result.magnitude)
    assert peak.magnitude == pytest.approx(CLOSED_FORM, rel=0.01)


def test_one_result_per_node_not_two(solved):
    """analyse_and_extract would give 18 here. Our analyse() must give 9."""

    step, nodes = solved
    assert len(list(step.displacement_field.results)) == len(nodes)


def test_reactions_sum_to_the_factored_load(solved):
    step, _ = solved
    total = sum(result.vector[2] for result in step.reaction_field.results)
    assert total == pytest.approx(ULS_FACTOR * TIP_LOAD, rel=1e-6)
