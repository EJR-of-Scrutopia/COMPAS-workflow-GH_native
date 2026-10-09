"""Which spools of a machine share a motor (spec 2026-10-09 section 3.3, test 7
of section 8)."""

import pytest

from tree_forest_compas import pairing as pg


def _count(n, largest):
    # set partitions of n items into blocks of at most `largest`:
    # P(n) = sum over k < largest of C(n - 1, k) P(n - 1 - k), P(0) = 1
    from math import comb
    p = [1]
    for m in range(1, n + 1):
        p.append(sum(comb(m - 1, k) * p[m - 1 - k] for k in range(min(largest, m))))
    return p[n]


def test_every_split_of_seven_spools_is_tried_once():
    spools = list("abcdefg")
    for largest, expected in ((1, 1), (2, 232), (3, 652), (7, 877)):
        found = list(pg.splits(spools, largest))
        assert len(found) == expected == _count(7, largest)
        assert len(set(found)) == len(found)
        for groups in found:
            assert sorted(w for g in groups for w in g) == spools
            assert all(1 <= len(g) <= largest for g in groups)
    with pytest.raises(pg.PairingError, match="at least one wire"):
        list(pg.splits(spools, 0))


def test_the_best_split_pairs_the_wires_that_need_the_same_reels():
    needs = {"a": [0.0, 1.0], "b": [5.0, 6.0], "c": [0.0, 1.0], "d": [5.0, 6.0]}
    groups, cost = pg.best_split(["a", "b", "c", "d"], needs, 2)
    assert sorted(sorted(g) for g in groups) == [["a", "c"], ["b", "d"]]
    assert cost == pytest.approx(0.0)
    # one motor a wire would cost nothing too: the split uses the fewest
    # motors that carry the wires two a motor, and searches only the pairing
    assert len(groups) == 2
    # checked against every split listed by hand
    by_hand = {
        (("a", "b"), ("c", "d")): 4 * 12.5 * 2 / 2,
        (("a", "c"), ("b", "d")): 0.0,
        (("a", "d"), ("b", "c")): 4 * 12.5 * 2 / 2,
    }
    for split, expected in by_hand.items():
        assert pg.split_cost(split, needs) == pytest.approx(expected)


def test_a_shared_motor_reels_the_mean_of_its_wires_needs():
    needs = {"a": 1.0, "b": 3.0, "c": 2.0}
    assert pg.common_reels(needs, (("a", "b"), ("c",))) == {"a": 2.0, "b": 2.0, "c": 2.0}
