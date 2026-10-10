"""The formwork sequence on a net small enough to follow by hand (spec
2026-10-09 sections 3 and 4; tests 7 and 9 to 12 of section 8)."""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from tree_forest_compas import formwork_sequence as fs  # noqa: E402
from tree_forest_compas import net_engine as ne  # noqa: E402


def _toy(wires_per_motor=1, stiffness=(50.0, 20.0, 10.0, 5.0)):
    # the studio's tiny study in millimetres: a 3 x 3 net of 1 m bays, its
    # corners held by wires running out to their machines, one tree whose
    # head rises 400 mm under the centre. Designed, the edge midpoints hang
    # 250 mm in and 50 mm up, so the skin, one row going on a quarter at a
    # time, one edge midpoint after another, loads nodes in the air. The
    # wires are soft and each has its own stiffness, so the same pull asks a
    # different reel of each
    design = np.array([[i * 1000.0, j * 1000.0, 0.0] for j in range(3) for i in range(3)])
    design[4, 2] = 400.0
    for node, inward in ((1, (0.0, 250.0)), (3, (250.0, 0.0)), (5, (-250.0, 0.0)),
                         (7, (0.0, -250.0))):
        design[node] += [*inward, 50.0]
    edges = np.array([(j * 3 + i, j * 3 + i + 1) for j in range(3) for i in range(2)]
                     + [(j * 3 + i, (j + 1) * 3 + i) for j in range(2) for i in range(3)])
    flat = design.copy()
    flat[:, 2] = 0.0
    out = {0: (-1.0, -1.0), 2: (1.0, -1.0), 6: (-1.0, 1.0), 8: (1.0, 1.0)}
    rim = {node: fs.RimWire(design[node].copy(), np.array([*out[node], 0.0]) / np.sqrt(2.0), k)
           for node, k in zip((0, 2, 6, 8), stiffness)}

    def trees(z):
        return np.array([[1000.0, 1000.0, 0.0], [1000.0, 1000.0, z]])

    frames = [fs.Frame(30.0, "raise", flat, trees(0.0)),
              fs.Frame(60.0, "finish", design, trees(400.0)),
              fs.Frame(100.0, "hold", design, trees(400.0))]
    weight = np.zeros((9, 3))
    weight[:, 2] = -0.5
    quarters = []
    for quarter in range(1, 5):
        skin = np.zeros((9, 3))
        skin[[1, 3, 5, 7][:quarter], 2] = -20.0
        quarters.append(skin)
    return fs.Model(design=design, edges=edges, ea=1.0e5, weight=weight, prestress=50.0,
                    rim=rim, heads=[(4, 1)], tree_members=np.array([[0, 1]]), tree_feet=[0],
                    frames=frames, rows=[fs.Row("S1", quarters)], machines=[[0, 2, 6, 8]],
                    wires_per_motor=wires_per_motor, wall=3.2)


def _held_by_wire_and_foundation(model, capture):
    # every rim node on its wire's line; out of its anchor the wire alone holds
    # it along that line, on its anchor the foundation pushes back the rest
    for i, node in enumerate(sorted(model.rim)):
        wire = model.rim[node]
        assert capture.x[node] == pytest.approx(wire.anchor - capture.let_out[i] * wire.into,
                                                abs=1.0e-6)
        along = float(-capture.anchor_force[i] @ wire.into)
        if capture.let_out[i] > 0.0:
            assert along == pytest.approx(capture.wire_tension[i], abs=0.02)
        else:
            assert capture.wire_tension[i] - along >= -ne.LEFTOVER_N


def test_the_cut_puts_each_member_at_its_fitted_tension_never_below_the_prestress():
    model = _toy()
    rest_lengths, force = fs.cut(model)
    assert np.all(force >= model.prestress)
    held = np.ones(9, dtype=bool)                         # the net held exactly at the design
    rest = ne.bring_to_rest(model.design, held, ne.ropes(model.edges, rest_lengths, model.ea),
                            model.weight)
    assert rest.tension == pytest.approx(force, abs=0.1)


def test_the_sequence_captures_every_frame_and_every_quarter():
    model = _toy()
    result = fs.simulate(model)
    captures = result.captures
    assert [c.phase for c in captures] == ["raise", "finish", "hold"] + ["tiling"] * 4
    assert [c.time for c in captures[:3]] == [30.0, 60.0, 100.0]
    assert [(c.row, c.quarter) for c in captures[3:]] == [("S1", q) for q in (1, 2, 3, 4)]
    for c in captures:
        assert c.solver in ("newton", "relaxation") and c.leftover < ne.LEFTOVER_N
        assert np.all(c.x[:, 2] >= -1.0e-9)                 # nothing under the ground
        assert np.all(c.wire_tension >= 0.0) and np.all(c.let_out >= 0.0)
        assert np.all(np.isfinite(c.deviation))
    hold = captures[2]
    assert hold.x[4] == pytest.approx([1000.0, 1000.0, 400.0])   # in its head's notch
    assert hold.head_push[0, 2] > 0.0
    assert result.groups is None
    # one wire a motor: each drum reels what holds its node on its anchor
    assert np.all(hold.let_out == 0.0)
    _held_by_wire_and_foundation(model, hold)


def test_every_head_holds_its_node_through_the_whole_sequence():
    # the owner's ruling of 10 October 2026: the column heads are tied to their
    # nodes from the layout on, so each head node is where its head is in every
    # capture, raise, finish, hold and tiling alike
    model = _toy()
    result = fs.simulate(model)
    for c in result.captures:
        assert c.x[4] == pytest.approx(c.tree_x[1], abs=1.0e-6)
        assert np.linalg.norm(c.head_push[0]) > 0.0


def test_the_sequence_ties_every_head_to_its_node_from_the_layout_on(monkeypatch):
    # in the toy every rope pulls its one head down, so a head that could only
    # push would hold it anyway: what is asked of the sequence is that every
    # settle it makes has the heads tied
    seen = []
    real = ne.settle

    def spy(*args, **kwargs):
        seen.append(args[4].tied)
        return real(*args, **kwargs)

    monkeypatch.setattr(ne, "settle", spy)
    fs.simulate(_toy())
    assert seen and all(tied == frozenset({4}) for tied in seen)


def test_the_holds_are_jacked_to_the_design_after_the_raise_and_held_there():
    # spec 2026-10-10 formwork holds, section 3 (his ruling: a hold is a
    # gripped rod): once the net is up, each hold takes its node to its design
    # point and grips it there from then on, like a column head, pushing or
    # pulling as the net asks
    model = _toy()._replace(holds=(1, 3, 5, 7))
    result = fs.simulate(model)
    captures = result.captures
    assert [c.phase for c in captures] == ["raise", "finish", "hold", "holds"] + ["tiling"] * 4
    jacked = captures[3]
    assert jacked.time == 100.0 and jacked.row is None
    for c in captures:
        assert c.hold_push.shape == (4, 3)
    for c in captures[:3]:
        assert np.all(c.hold_push == 0.0)                  # none before the jacking
    # from the jacking on every held node is at its design point (in the toy
    # the net would carry the edge midpoints 10 mm above theirs, so their
    # holds pull), and its hold carries what the net puts on it
    for c in captures[3:]:
        for node in (1, 3, 5, 7):
            assert c.x[node] == pytest.approx(model.design[node], abs=1.0e-6)
        assert np.all(np.linalg.norm(c.hold_push, axis=1) > 0.0)
    assert np.any(jacked.hold_push[:, 2] < 0.0)
    # and a run with no holds is the sequence as it was
    plain = fs.simulate(_toy())
    assert [c.phase for c in plain.captures] == ["raise", "finish", "hold"] + ["tiling"] * 4
    assert all(c.hold_push.shape == (0, 3) for c in plain.captures)


def test_the_progress_counts_the_capture_after_the_jacking():
    # found on the real study: "capture 101 of 100"
    told = []
    fs.simulate(_toy()._replace(holds=(1, 3, 5, 7)), lambda done, total, what: told.append((done, total)))
    assert told[-1] == (8, 8) and {total for _, total in told} == {8}


def test_the_holds_grip_their_nodes_from_the_jacking_on_and_never_let_go(monkeypatch):
    # found on the real study: push-only props were pulled off their nodes,
    # held the net sideways and let it slide out of their cradles at every
    # spacing. His ruling: a hold grips its node like a column head, from the
    # jacking on, and never lets go
    seen = []
    real = ne.settle

    def spy(*args, **kwargs):
        seen.append(({1, 3, 5, 7} <= args[4].tied, {1, 3, 5, 7} <= args[4].engaged))
        return real(*args, **kwargs)

    monkeypatch.setattr(ne, "settle", spy)
    fs.simulate(_toy()._replace(holds=(1, 3, 5, 7)))
    gripped = [i for i, (tied, _) in enumerate(seen) if tied]
    assert gripped, "the jacks grip their nodes"
    assert all(tied and engaged for tied, engaged in seen[gripped[0]:])


def test_every_capture_names_the_nodes_the_ground_holds():
    # laid out, every node but the rim's and the head's rests on the ground
    # (spec 2026-10-10 formwork tab, section 4); raised, the tree lifts the
    # centre and the edge midpoints with it, so fewer rest there, and the ground
    # only ever holds a node at its own height
    result = fs.simulate(_toy())
    first, hold = result.captures[0], result.captures[2]
    assert first.ground == (1, 3, 5, 7)
    assert len(hold.ground) < len(first.ground)
    for c in result.captures:
        assert list(c.ground) == sorted(c.ground)
        assert all(abs(float(c.x[i, 2])) < 1.0e-6 for i in c.ground)


def test_the_net_is_laid_out_where_the_first_frame_has_it_as_near_as_it_allows():
    # the animation has node 1 300 mm up and 650 mm further out than its ropes
    # reach: the people laying the net out put it on the ground, and held there
    # it would carry tens of kilonewtons, so they let it slide in until no rope
    # is stretched (spec 4.1)
    model = _toy()
    flat = model.frames[0].net.copy()
    flat[1] = [1000.0, -400.0, 300.0]
    model = model._replace(frames=[model.frames[0]._replace(net=flat)] + model.frames[1:])
    first = fs.simulate(model).captures[0]
    assert first.tension.max() < 1.0
    assert 172.0 < first.x[1, 1] < 254.0 and first.x[1, 2] == pytest.approx(0.0)
    assert first.deviation[1] > 500.0         # how far the frame's layout was from one a net can take


def test_the_head_lifts_the_net_off_the_ground_and_its_tree_carries_the_push():
    result = fs.simulate(_toy())
    start, hold = result.captures[0], result.captures[2]
    assert start.x[4, 2] == pytest.approx(0.0)
    assert hold.x[4, 2] == pytest.approx(400.0)
    assert hold.tree_axial[0] == pytest.approx(-hold.head_push[0, 2])


def test_through_the_tiling_the_reels_hold_and_the_skin_lets_the_rim_out():
    model = _toy()
    result = fs.simulate(model)
    hold, tiling = result.captures[2], result.captures[3:]
    for c in tiling:
        assert np.array_equal(c.reel, hold.reel)              # the drums hold
        _held_by_wire_and_foundation(model, c)
    assert tiling[-1].let_out.max() > 0.0                     # the skin has stretched the wires


def test_shared_motors_reel_the_mean_of_their_wires_needs_and_let_the_long_wire_out():
    alone = fs.simulate(_toy())
    model = _toy(wires_per_motor=2)
    result = fs.simulate(model)
    # the corners pull alike, so each wire needs its pull over its stiffness:
    # the stiff pair and the soft pair share
    assert sorted(sorted(group) for group in result.groups[0]) == [[0, 2], [6, 8]]
    at = {node: i for i, node in enumerate(sorted(model.rim))}
    for c, own in zip(result.captures, alone.captures):
        assert (c.phase, c.time, c.row, c.quarter) == (own.phase, own.time, own.row, own.quarter)
        for group in result.groups[0]:
            reels = [c.reel[at[node]] for node in group]
            assert max(reels) == min(reels)                    # one drum, one reel
            if c.phase != "tiling":
                assert reels[0] == pytest.approx(np.mean([own.reel[at[node]] for node in group]))
        _held_by_wire_and_foundation(model, c)
    raised = [c for c in result.captures if c.phase != "tiling"]
    assert max(c.let_out.max() for c in raised) > 0.0         # a wire left long let its node out


def test_shared_motors_refuse_a_rim_wire_on_no_machine():
    with pytest.raises(ne.EngineError, match=r"rim nodes \[8\] are on no machine"):
        fs.simulate(_toy(wires_per_motor=2)._replace(machines=[[0, 2, 6]]))


def test_the_thinnest_wall_holds_every_capture():
    result = fs.simulate(_toy())
    assert result.thinnest_wall == min(fs.tr.STANDARD_WALLS)     # a toy tree carries little
    assert result.wall == 3.2


def test_a_model_with_no_frames_is_refused():
    with pytest.raises(ne.EngineError, match="no frames"):
        fs.simulate(_toy()._replace(frames=[]))
