"""A Grasshopper authored tessellation is a first class generator.

Every rule the schema states is enforced here, and every rejection names
the offending cell, because an author fixing a pattern in Grasshopper
needs to know which polygon to look at.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def studio():
    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import tessellation
    return tessellation


def document(cells=None, **overrides):
    base = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": cells if cells is not None else [
            {"key": "a", "course": 0,
             "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
            {"key": "b", "course": 1,
             "outline": [[0, 1], [1, 1], [1, 2], [0, 2]]},
        ],
        "provenance": {"source": "Grasshopper", "author": "test"},
    }
    base.update(overrides)
    return base


def flat(x, y):
    return 0.0


def test_a_valid_document_is_accepted():
    t = studio()
    tess = t.from_document(document(), flat)
    assert tess["source"] == "imported"
    assert tess["pattern"] == "authored"
    assert len(tess["cells"]) == 2
    assert tess["provenance"]["author"] == "test"
    assert "coverage_holes" in tess["report"]
    assert "broken_boundary" in tess["report"]


def test_an_authored_cut_has_no_target_size_of_its_own():
    # Task 8 fix round 1, C1: an authored cut ignores size entirely, so
    # target_size must be None (not applicable), the same convention
    # z_offset_max already uses, rather than 0.0 (measured and found to be
    # zero). 0.0 is a real number bundle.py used to echo straight into the
    # top level "size" field the client trusts, which then failed the API's
    # own 0.3 to 3.0 validation on the very next reload.
    t = studio()
    tess = t.from_document(document(), flat)
    assert tess["target_size"] is None


def test_a_duplicate_key_is_rejected_by_name():
    t = studio()
    cells = [
        {"key": "same", "course": 0, "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
        {"key": "same", "course": 1, "outline": [[0, 1], [1, 1], [1, 2], [0, 2]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "same" in str(error.value)


def test_overlapping_cells_are_rejected_by_name():
    t = studio()
    cells = [
        {"key": "low", "course": 0, "outline": [[0, 0], [2, 0], [2, 2], [0, 2]]},
        {"key": "over", "course": 1, "outline": [[1, 1], [3, 1], [3, 3], [1, 3]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    message = str(error.value)
    assert "low" in message and "over" in message


def test_an_unknown_schema_is_rejected_rather_than_guessed():
    t = studio()
    with pytest.raises(ValueError) as error:
        t.from_document(document(schema="bench.tessellation/2"), flat)
    assert "bench.tessellation/2" in str(error.value)


def test_an_unknown_units_value_is_rejected_rather_than_guessed():
    t = studio()
    with pytest.raises(ValueError) as error:
        t.from_document(document(units="mm"), flat)
    assert "mm" in str(error.value)


def test_an_unknown_domain_is_rejected_rather_than_guessed():
    t = studio()
    with pytest.raises(ValueError) as error:
        t.from_document(document(domain="elevation"), flat)
    assert "elevation" in str(error.value)


def test_a_self_intersecting_outline_is_rejected_by_name():
    t = studio()
    cells = [{"key": "bowtie", "course": 0,
              "outline": [[0, 0], [1, 1], [1, 0], [0, 1]]}]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "bowtie" in str(error.value)


def test_an_authored_fold_is_refused_where_a_generated_one_is_only_named():
    """The two routes disagree about a fold on purpose.

    build_tessellation reports folded cells rather than raising, because a
    generated fold is the studio's own doing on a plan whose rim it has to
    follow, and the rest of that report degrades the same way. An author
    can fix theirs in Grasshopper, so from_document still refuses by name,
    and the check that refuses runs before build_tessellation ever sees the
    cell: the same outline never reaches the folded list by this route.
    """

    t = studio()
    outline = [[0.0, 0.0], [4.0, 0.0], [1.0, 3.0], [3.0, 3.0]]
    cells = [{"key": "bowtie", "course": 0, "outline": outline}]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "bowtie" in str(error.value)
    assert "crosses itself" in str(error.value)

    generated = t.build_tessellation(
        [{"key": "bowtie", "course": 0, "outline": outline, "holes": []}],
        "test", "generated", 1.0, 1,
    )
    assert generated["report"]["folded"] == ["bowtie"]


def test_a_supplied_z_is_measured_against_the_surface_not_used():
    t = studio()
    cells = [
        {"key": "a", "course": 0,
         "outline": [[0, 0, 0.5], [1, 0, 0.5], [1, 1, 0.5], [0, 1, 0.5]]},
    ]
    tess = t.from_document(document(cells), flat)
    assert tess["z_offset_max"] == pytest.approx(0.5)
    # The geometry is the plan only: z never reaches the point table.
    assert all(len(p) == 2 for p in tess["points"])


def test_z_offset_max_is_none_when_surface_never_answers():
    t = studio()
    def no_surface(x, y):
        return None
    cells = [
        {"key": "a", "course": 0,
         "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
    ]
    tess = t.from_document(document(cells), no_surface)
    assert tess["z_offset_max"] is None


def test_a_missing_course_is_filled_in_and_disclosed():
    t = studio()
    cells = [{"key": "a", "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    tess = t.from_document(document(cells), flat)
    assert tess["cells"][0]["course"] == 0
    assert tess["courses_inferred"] is True


def test_the_contract_wins_over_the_sidecar(tmp_path):
    t = studio()
    sidecar = tmp_path / "x-tessellation.json"
    sidecar.write_text(json.dumps(document(pattern="sidecar")), encoding="utf-8")
    found = t.read_tessellation({"tessellation": document(pattern="contract")}, sidecar)
    assert found["pattern"] == "contract"
    found = t.read_tessellation({}, sidecar)
    assert found["pattern"] == "sidecar"
    assert t.read_tessellation({}, tmp_path / "missing.json") is None


def test_a_concave_l_shaped_cell_and_its_exact_complement_are_accepted():
    t = studio()
    cells = [
        {"key": "L", "course": 0,
         "outline": [[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]]},
        {"key": "notch", "course": 0,
         "outline": [[1, 1], [3, 1], [3, 3], [1, 3]]},
    ]
    tess = t.from_document(document(cells), flat)
    assert len(tess["cells"]) == 2


def test_a_ring_that_touches_itself_at_a_vertex_is_rejected_by_name():
    t = studio()
    cells = [{"key": "pinch", "course": 0,
              "outline": [[0, 0], [2, 0], [1, 1], [2, 2], [0, 2], [1, 1]]}]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "pinch" in str(error.value)


def test_a_vertex_lying_on_a_non_adjacent_edge_is_rejected_by_name():
    t = studio()
    cells = [{"key": "bad", "course": 0,
              "outline": [[0, 0], [2, 3], [4, 0], [4, 3], [0, 3]]}]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    assert "bad" in str(error.value)


def test_identical_outlines_in_same_order_are_rejected_by_name():
    t = studio()
    cells = [
        {"key": "square1", "course": 0,
         "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
        {"key": "square2", "course": 0,
         "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    message = str(error.value)
    assert "square1" in message and "square2" in message


def test_identical_outlines_in_different_order_are_rejected_by_name():
    t = studio()
    cells = [
        {"key": "square1", "course": 0,
         "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]},
        {"key": "square2", "course": 0,
         "outline": [[1, 0], [1, 1], [0, 1], [0, 0]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    message = str(error.value)
    assert "square1" in message and "square2" in message
    assert "identical outlines" in message


def test_cells_with_same_corners_in_different_order_are_rejected_by_name():
    t = studio()
    cells = [
        {"key": "a", "course": 0,
         "outline": [[0, 0], [4, 0], [0, 4], [1, 1]]},
        {"key": "b", "course": 0,
         "outline": [[0, 0], [4, 0], [1, 1], [0, 4]]},
    ]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    message = str(error.value)
    assert "a" in message and "b" in message
    assert "connect the same corners in different orders" in message


def test_a_wrong_container_type_is_a_named_rejection_not_a_crash():
    """The schema validates values by name, which reads the container.

    A wrong container type therefore escaped from_document as a bare
    AttributeError or TypeError, and app.get_bundle catches only
    ValueError, so the route answered 500 with no detail body at all: not
    the cell key, not even which file. Every case here used to be one of
    those. The assertion is both that it is a ValueError (so the route can
    make it a 400) and that the message names the cell, which is the whole
    point of the 400 contract.
    """
    t = studio()
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    cases = [
        ("cells is not a list", document(), {"cells": "abc"}, "cells"),
        ("a cell is a bare string", document(["oops"]), None, "cell 0"),
        ("outline is not a list",
         document([{"key": "a", "course": 0, "outline": 7}]), None, "'a'"),
        ("holes is not a list",
         document([{"key": "a", "course": 0, "outline": square, "holes": 5}]),
         None, "'a'"),
        ("a hole is not a list",
         document([{"key": "a", "course": 0, "outline": square, "holes": [7]}]),
         None, "'a'"),
        ("a point is an object, not a pair",
         document([{"key": "a", "course": 0,
                    "outline": [{"x": 0}, {"x": 1}, {"x": 2}]}]), None, "'a'"),
    ]
    for label, doc, override, expected in cases:
        if override is not None:
            doc = dict(doc, **override)
        with pytest.raises(ValueError) as error:
            t.from_document(doc, flat)
        assert expected in str(error.value), "{}: {}".format(label, error.value)


def test_a_document_that_is_not_an_object_is_rejected_not_crashed():
    """A sidecar holding a JSON list reached from_document unguarded.

    read_tessellation type-checks the CONTRACT route (isinstance dict) but
    hands the sidecar's json.loads result straight through, so a sidecar
    authored as a bare list raised AttributeError on document.get.
    """
    t = studio()
    with pytest.raises(ValueError) as error:
        t.from_document(["not", "a", "document"], flat)
    assert "JSON object" in str(error.value)


def test_a_negative_course_is_rejected_by_cell_key():
    """A negatively coursed cell was drawn but placed by no stage.

    It welds, it becomes a piece, and it never appears in any stage, so
    its weight leaves the formwork curve. analysis_binding reports zero
    orphans (its faces ARE covered by a cell), so the one disclosure
    mechanism cannot see it. Rejected at the authoring boundary, by name.
    """
    t = studio()
    cells = [{"key": "sunk", "course": -3,
              "outline": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    with pytest.raises(ValueError) as error:
        t.from_document(document(cells), flat)
    message = str(error.value)
    assert "sunk" in message and "-3" in message


def test_a_malformed_sidecar_names_the_file_it_could_not_read(tmp_path):
    """json.JSONDecodeError subclasses ValueError, so this already 400'd.

    But "Expecting value: line 1 column 1" names neither the file nor the
    fact a sidecar was involved, and the author is staring at a contract
    that is perfectly valid.
    """
    t = studio()
    sidecar = tmp_path / "Trial-tessellation.json"
    sidecar.write_text("{not json at all", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        t.read_tessellation({}, sidecar)
    assert "Trial-tessellation.json" in str(error.value)
