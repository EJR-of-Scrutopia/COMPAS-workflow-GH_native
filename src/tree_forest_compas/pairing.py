"""Which spools of a machine share a motor (spec 2026-10-09 section 3.3).

Every way of splitting a machine's spools onto the fewest motors that carry
them with at most N each, ceil(7 / N) for seven spools, is tried, and the split
kept is the one whose shared reels stray least from what each wire needs. A wire's need, frame by frame, is the
take-up that holds its rim node on its anchor; a motor reels the mean of its
wires' needs, so a split costs the summed squared distance of every need from
its motor's mean.
"""

from __future__ import annotations

import itertools


class PairingError(ValueError):
    """A split that cannot be made."""


def splits(items, largest):
    """Every way of splitting items into groups of at most `largest`, each once:
    a group is a tuple led by its first item in the given order."""

    if int(largest) < 1:
        raise PairingError("a motor carries at least one wire, not {}".format(largest))

    def walk(rest):
        if not rest:
            yield ()
            return
        first, others = rest[0], rest[1:]
        for size in range(0, min(int(largest) - 1, len(others)) + 1):
            for partners in itertools.combinations(others, size):
                remaining = [other for other in others if other not in partners]
                for tail in walk(remaining):
                    yield ((first,) + partners,) + tail

    yield from walk(list(items))


def split_cost(groups, needs):
    """The summed squared distance of every wire's need from its motor's mean,
    over every frame."""

    cost = 0.0
    for group in groups:
        for frame in range(len(needs[group[0]])):
            values = [needs[wire][frame] for wire in group]
            mean = sum(values) / len(values)
            cost += sum((value - mean) ** 2 for value in values)
    return cost


def best_split(wires, needs, largest):
    """The split of these wires onto the fewest motors that carry them with at
    most `largest` each, ceil(len(wires) / largest), that costs least, and its
    cost; the first found wins a tie. One motor a wire would always cost
    nothing, so the motor count is the choice, and only the pairing is
    searched."""

    wires = list(wires)
    motors = -(-len(wires) // int(largest))
    best, best_cost = None, None
    for groups in splits(wires, largest):
        if len(groups) != motors:
            continue
        cost = split_cost(groups, needs)
        if best is None or cost < best_cost - 1.0e-12:
            best, best_cost = groups, cost
    return best, best_cost


def common_reels(needs, groups):
    """Each wire's drum reel when its motor reels the mean of its wires' needs:
    one reel a motor, the same for each of its wires. The engine then lets a
    wire left long let its node out, and a wire left short pull its node onto
    the anchor, where the foundation pushes back."""

    reels = {}
    for group in groups:
        mean = sum(needs[wire] for wire in group) / len(group)
        for wire in group:
            reels[wire] = mean
    return reels
