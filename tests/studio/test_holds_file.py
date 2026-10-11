"""The holds file for Grasshopper (spec 2026-10-10 prestress and holds, section
8): the nodes the chosen machine needs held, at the finished shape, in metres,
written beside the other exports. The page and the export route no longer
offer it (spec 2026-10-11 one Cable net tab, section 9); the writer stays,
unreached, until the file is rebuilt from the formwork run."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

# test_exports puts bench/studio on the path, so it comes first
from test_exports import _demand  # noqa: E402
import exports  # noqa: E402

NEEDS = {
    "stage": "S7", "tolerance_mm": 20.0, "ceiling_newtons": 1123.4,
    "steps": [{"count": 0, "added": [], "prestress_newtons": 300.0},
              {"count": 2, "added": [2, 1], "prestress_newtons": 150.0},
              {"count": 3, "added": [0], "prestress_newtons": 1.0}],
    "ladder": [{"prestress_newtons": 100.0, "worst_sag_mm": 25.0, "roof": 0.5}]}
# contract node n sits at engine vertex n + 10, in millimetres
NET = {"vertices": [[0.0, 0.0, 0.0]] * 10 + [[1000.0, 2000.0, 3000.0], [1500.0, -250.0, 4125.0],
                                              [-2000.0, 0.0, 500.0]],
       "node_of": {"0": 10, "1": 11, "2": 12}, "net_edge_count": 2253,
       "fixed": list(range(36)), "ea_provenance": "rope-4mm, assumed"}


def _held_demand():
    return _demand(needs=NEEDS, net=NET)


def test_the_holds_for_a_ceiling_are_the_fewest_steps_it_covers():
    # the same rule as the panel's holdsFor
    assert exports.holds_for(NEEDS, 1123.4) == {"step": 0, "nodes": [], "covered": True,
                                               "prestress_newtons": 300.0}
    assert exports.holds_for(NEEDS, 200.0) == {"step": 1, "nodes": [2, 1], "covered": True,
                                              "prestress_newtons": 150.0}
    assert exports.holds_for(NEEDS, 0.5) == {"step": 2, "nodes": [2, 1, 0], "covered": False,
                                            "prestress_newtons": 1.0}
    assert exports.holds_for(None, 200.0) is None and exports.holds_for(NEEDS, None) is None


def test_the_document_names_each_node_at_the_finished_shape_in_metres():
    document = exports.holds_document(_held_demand(), 200.0, 6660.0, "My Vault",
                                      {"material": "tile"})
    assert document["schema"] == "bench.holds/1" and document["study"] == "My Vault"
    assert document["cut"] == {"material": "tile"}
    assert document["tolerance_mm"] == 20.0 and document["ceiling_newtons"] == 200.0
    assert document["prestress_newtons"] == 150.0 and document["reason"] == "machine"
    assert document["nodes"] == [
        {"node": 2, "x": -2.0, "y": 0.0, "z": 0.5, "step": 1},
        {"node": 1, "x": 1.5, "y": -0.25, "z": 4.125, "step": 1}]
    every = exports.holds_document(_held_demand(), 200.0, 250.0, "My Vault", {})
    assert every["reason"] == "every machine"
    none = exports.holds_document(_held_demand(), 1123.4, 6660.0, "My Vault", {})
    assert none["nodes"] == [] and none["reason"] is None


def test_an_older_analysis_has_no_holds_to_write():
    with pytest.raises(exports.ExportError, match="prestress table"):
        exports.holds_document(_demand(), 200.0, 6660.0, "My Vault", {})
