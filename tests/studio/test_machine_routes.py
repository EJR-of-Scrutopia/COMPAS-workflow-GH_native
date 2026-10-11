"""The five choices through the studio's routes (spec 2026-10-09 mechanism
choices, section 7.4): what the catalogue offers. Choices judged on a study and
Recommend went with the old Cable net (spec 2026-10-11 one Cable net tab,
section 9); the tab chooses whole mechanisms (test_mechanisms.py)."""

import pytest

pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402

def test_the_catalogue_offers_the_five_choices(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    choices = client.get("/api/catalogue").json()["choices"]
    assert [m["key"] for m in choices["motors"]][:2] == ["23HS45-4204D-E1000",
                                                         "34HS31-6004D-E1000"]
    assert [o["ratio"] for o in choices["ratios"]["23HS45-4204D-E1000"]] == [None, 5, 10, 20, 50]
    assert "Pfaff-DSRB-90-4" in choices["pulleys"]["rope-4mm"]
    assert "Pfaff-DSRB-185-8" not in choices["pulleys"]["rope-4mm"]
    assert choices["wires_per_motor"] == [1, 2, 3, 4, 5, 6, 7]


def test_the_lightest_chain_is_worked_out_once_per_wire_and_angle(monkeypatch):
    """Recommend derives 15 thousand machines; each wire's anchor chain is
    worked out once for a catalogue and an angle, not once a machine."""

    import catalogue
    import machine

    parts = catalogue.load_parts()
    calls = []
    real = catalogue.chain_limit

    def counted(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(catalogue, "chain_limit", counted)
    first = machine.lightest_chain(parts, "rope-4mm", 10.0)
    worked = len(calls)
    assert worked > 0
    assert machine.lightest_chain(parts, "rope-4mm", 10.0) == first
    assert len(calls) == worked                       # nothing worked out again
    machine.lightest_chain(parts, "rope-5mm", 10.0)
    assert len(calls) == 2 * worked                   # another wire is its own
    # another catalogue, as a reload gives, is worked out afresh
    machine.lightest_chain(catalogue.load_parts(), "rope-4mm", 10.0)
    assert len(calls) == 3 * worked
