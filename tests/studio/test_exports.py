from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

from fastapi.testclient import TestClient

import app as studio_app
import exports


@pytest.fixture()
def client(monkeypatch):
    # Setting the folder rebinds a module global, as for the other six; put
    # it back afterwards so no later test reads this one's temporary folder.
    monkeypatch.setattr(studio_app, "CABLENET_EXPORTS_DIR",
                        studio_app.CABLENET_EXPORTS_DIR, raising=False)
    return TestClient(studio_app.create_app(runner=lambda request: {}))


def test_the_export_folder_is_set_validated_and_remembered(client, tmp_path, monkeypatch):
    stored = {}
    monkeypatch.setattr(studio_app, "remember_setting",
                        lambda key, value: stored.__setitem__(key, value))
    monkeypatch.setattr(studio_app, "read_settings", lambda: dict(stored))

    chosen = tmp_path / "exports"
    chosen.mkdir()
    body = client.post("/api/cablenet/exports/folder",
                       json={"path": str(chosen)}).json()
    assert body["path"] == str(chosen)
    assert stored["cablenet_exports_folder"] == str(chosen)
    assert client.get("/api/cablenet/exports/folder").json()["path"] == str(chosen)


def test_a_folder_that_is_not_there_is_refused_by_name(client, tmp_path):
    missing = tmp_path / "nope"
    response = client.post("/api/cablenet/exports/folder",
                           json={"path": str(missing)})
    assert response.status_code == 400
    assert str(missing) in response.json()["detail"]


def test_an_empty_path_is_refused(client):
    assert client.post("/api/cablenet/exports/folder", json={"path": "  "}).status_code == 400


def test_browse_returns_a_path_without_setting_it(client, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(studio_app, "ask_for_folder", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(studio_app, "remember_setting",
                        lambda key, value: seen.append(key))
    assert client.post("/api/cablenet/exports/folder/browse").json()["path"] == str(tmp_path)
    assert seen == []        # browsing must not remember; the caller posts it back


def _demand(**kwargs):
    base = {
        "study": "Test Vault", "prestress": 300.0, "ea_newtons": 450000.0,
        "acceptance": 2.18, "acceptance_source": "plywood rib 2000 x 400",
        "sizing_stage": "S7", "density": 1800.0, "thickness": 0.02,
        "net": {"net_edge_count": 2253, "fixed": list(range(36)),
                "ea_provenance": "rope-4mm, assumed"},
        "wires": [{"name": "w1", "net_vertex": 658, "frame_point": [0, 0, 6000]}],
        "stages": [
            {"stage": 1, "name": "S1", "kind": "raise",
             "placed_weight_newtons": 0.0, "skin_load_sum_newtons": 0.0,
             "wire_rest_lengths": [2000.0], "wire_reel_commands": [0.0],
             "wire_tensions": [400.0], "deviation": 0.5, "reachable": True,
             "residual_after": 0.5},
            {"stage": 2, "name": "S7", "kind": "tile",
             "placed_weight_newtons": 12000.0, "skin_load_sum_newtons": 12000.0,
             "wire_rest_lengths": [1990.0], "wire_reel_commands": [-10.0],
             "wire_tensions": [900.0], "deviation": 1.4, "reachable": True,
             "residual_after": 1.4},
        ],
    }
    base.update(kwargs)
    return base


def _configuration(**kwargs):
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rope="rope-4mm", rail="MGN15H-300", sheave=None, reeve_factor=1,
                chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    base.update(kwargs)
    return base


def _row(parts, configuration, **kwargs):
    import catalogue
    ceiling, binding = catalogue.ceiling_for(parts, configuration, 10.0)
    base = {
        "configuration": configuration, "ceiling": ceiling, "binding": binding,
        "passes": True, "passes_note": None, "margin": ceiling / 900.0,
        "price": catalogue.price_of(parts, configuration),
        "rope_speed_mm_s": catalogue.rope_speed(parts, configuration),
        "refused": None,
    }
    base.update(kwargs)
    return base


def test_the_model_carries_every_ceiling_term_with_the_part_that_sets_it():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")

    names = [term["name"] for term in model["terms"]]
    assert "rope tension" in names and "motor torque" in names
    binding = [term for term in model["terms"] if term["binds"]]
    assert len(binding) == 1
    assert binding[0]["part_id"] == "turnbuckle-hook-hook-M10"
    assert round(binding[0]["newtons"]) == 1471
    assert model["verdict"]["tension"]["binding"] == binding[0]["part_id"]


def test_the_verdict_has_two_separate_halves():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    assert set(model["verdict"]) == {"tension", "shape", "holds"}
    assert model["verdict"]["shape"]["worst_residual_mm"] == 1.4
    assert model["verdict"]["shape"]["acceptance_mm"] == 2.18
    assert model["verdict"]["shape"]["within"] is True
    assert model["verdict"]["holds"] is True


def test_parts_can_carry_it_while_the_net_misses_the_shape():
    # the case the panel got wrong before the first spec's final review
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    demand = _demand()
    demand["stages"][1]["residual_after"] = 7.4
    demand["stages"][1]["deviation"] = 7.4
    model = exports.export_model(parts, demand, _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    assert model["verdict"]["tension"]["passes"] is True
    assert model["verdict"]["shape"]["within"] is False
    assert model["verdict"]["shape"]["worst_stage"] == "S7"
    assert model["verdict"]["holds"] is False


def test_an_unreachable_stage_fails_the_shape_half():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    demand = _demand()
    demand["stages"][1]["reachable"] = False
    model = exports.export_model(parts, demand, _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    assert model["verdict"]["shape"]["within"] is False
    assert model["verdict"]["holds"] is False


def test_every_chosen_part_arrives_with_its_provenance():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    model = exports.export_model(parts, _demand(), _row(parts, configuration),
                                 configuration, 10.0, "2026-10-07")
    for part in model["parts"]:
        assert set(part) >= {"kind", "id", "model", "supplier", "part_number",
                             "unit_price", "vat", "price_seen", "confidence"}
    ids = {part["id"] for part in model["parts"]}
    assert "34HS46" in ids and "turnbuckle-hook-hook-M10" in ids


def test_a_refused_configuration_cannot_be_modelled():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration(motor="boatlift-1hp", drive="none")
    with pytest.raises(exports.ExportError, match="cannot be built"):
        exports.export_model(parts, _demand(),
                             {"refused": "family C", "configuration": configuration},
                             configuration, 10.0, "2026-10-07")


def _model(**overrides):
    """The one fixture every export test builds on."""
    import catalogue
    parts = catalogue.load_parts()
    configuration = overrides.pop("configuration", None) or _configuration()
    demand = overrides.pop("demand", None) or _demand()
    angle = overrides.pop("angle_degrees", 10.0)
    row = overrides.pop("row", None) or _row(parts, configuration)
    return exports.export_model(parts, demand, row, configuration, angle,
                                overrides.pop("generated_at", "2026-10-07"))


def test_exactly_one_term_binds_whatever_the_configuration():
    reeved = _configuration(sheave="WZ-11-K", reeve_factor=2)
    for configuration in (
        _configuration(),
        _configuration(chain=["eye-M12"]),
        _configuration(motor="23HS45", drive="CL57Y", gearbox="direct"),
        reeved,
    ):
        model = _model(configuration=configuration)
        assert sum(1 for term in model["terms"] if term["binds"]) == 1, configuration


def test_every_assumption_names_what_it_is():
    model = _model()
    whats = [item["what"] for item in model["assumptions"]]
    assert all(whats) and len(set(whats)) == len(whats)
    assert {"rope EA", "gearbox efficiency", "flat torque derate",
            "anchor angle"} <= set(whats)
    assert any("assumed" in w or "EA" in w for w in whats)
    assert model["not_checked"]


def test_the_workbook_has_the_five_sheets_in_order(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    model = _model()
    written = exports.write_spreadsheet(model, tmp_path, "Test Vault-cablenet")
    assert len(written) == 1 and written[0].suffix == ".xlsx"
    book = openpyxl.load_workbook(written[0])
    assert book.sheetnames == ["Read this", "Chosen", "Parts", "Stages", "Ladder"]


def test_an_unpriced_line_marks_the_total_a_floor(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    model = _model()                       # the drum carries no price
    written = exports.write_spreadsheet(model, tmp_path, "x")
    book = openpyxl.load_workbook(written[0])
    text = " ".join(str(c.value) for row in book["Parts"].iter_rows()
                    for c in row if c.value is not None)
    assert "floor" in text.lower()
    assert "drum-72" in text


def test_without_openpyxl_it_writes_csvs_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_openpyxl", None)
    written = exports.write_spreadsheet(_model(), tmp_path, "x")
    assert len(written) == 5
    assert all(path.suffix == ".csv" for path in written)
    assert exports.last_spreadsheet_note() and "openpyxl" in exports.last_spreadsheet_note()


def test_the_chosen_sheet_shows_both_halves_of_the_verdict(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    model = _model()
    model["verdict"]["shape"]["within"] = False
    written = exports.write_spreadsheet(model, tmp_path, "x")
    book = openpyxl.load_workbook(written[0])
    text = " ".join(str(c.value) for row in book["Chosen"].iter_rows()
                    for c in row if c.value is not None).lower()
    assert "tension" in text and "shape" in text


def test_the_csv_path_says_what_the_workbook_would(tmp_path, monkeypatch):
    # the rows are built once; the CSV is the same content, and it runs today
    import csv
    monkeypatch.setattr(exports, "_openpyxl", None)
    written = exports.write_spreadsheet(_model(), tmp_path, "x")
    assert [p.name for p in written] == [
        "x-" + name.lower().replace(" ", "-") + ".csv" for name in exports.SHEETS]
    def text(name):
        path = next(p for p in written if p.name.endswith(name + ".csv"))
        with open(path, newline="", encoding="utf-8") as handle:
            return " ".join(c for row in csv.reader(handle) for c in row)
    parts = text("parts")
    assert "floor" in parts.lower() and "drum-72" in parts
    chosen = text("chosen").lower()
    assert "tension" in chosen and "shape" in chosen


def test_the_note_is_reset_on_every_call(tmp_path, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(exports, "_openpyxl", None)
        exports.write_spreadsheet(_model(), tmp_path, "x")
        assert exports.last_spreadsheet_note()
    if exports._openpyxl is None:
        pytest.skip("needs openpyxl for the successful run")
    exports.write_spreadsheet(_model(), tmp_path, "x")
    assert exports.last_spreadsheet_note() is None


def _scored(parts, configuration, **kwargs):
    import catalogue
    ceiling, binding = catalogue.ceiling_for(parts, configuration, 10.0)
    row = {"configuration": configuration, "ceiling": ceiling, "binding": binding,
           "price": catalogue.price_of(parts, configuration), "refused": None}
    row.update(kwargs)
    return row


def _laddered(*variants):
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    rows = [_scored(parts, configuration)]
    for change in variants:
        if isinstance(change, str):
            rows.append({"configuration": dict(configuration, motor="boatlift-1hp"),
                         "refused": change})
        else:
            rows.append(_scored(parts, dict(configuration, **change)))
    return exports.export_model(parts, _demand(), _row(parts, configuration),
                                configuration, 10.0, "2026-10-07", ladder_rows=rows)


def test_a_rung_lists_only_the_keys_that_differ():
    model = _laddered({"chain": ["eye-M12"]})
    rung = [r for r in model["ladder"] if not r["is_chosen"]][0]
    assert list(rung["changes"]) == ["chain"]
    assert rung["ceiling_newtons"] > 0 and rung["binding"]


def test_the_chosen_rung_is_marked_with_no_changes():
    model = _laddered({"chain": ["eye-M12"]})
    chosen = [r for r in model["ladder"] if r["is_chosen"]]
    assert len(chosen) == 1 and chosen[0]["changes"] == {}


def test_a_refused_rung_survives_with_its_text():
    model = _laddered("family C")
    rung = model["ladder"][1]
    assert rung["refused"] == "family C"
    assert rung["ceiling_newtons"] is None and rung["binding"] is None


def test_no_ladder_rows_gives_an_empty_list():
    assert _model()["ladder"] == []


def test_the_ladder_sheet_renders_the_real_rungs():
    rows = exports._sheet_rows(_laddered({"chain": ["eye-M12"]}, "family C"))["Ladder"]
    assert len(rows) == 4 and rows[1][0] == "Chosen"
    assert "chain" in rows[2][1] and rows[3][4].startswith("Not buildable")


def test_the_diagram_marks_the_same_part_the_verdict_names(tmp_path):
    model = _model()
    svg = exports.write_diagram(model, tmp_path, "x").read_text(encoding="utf-8")
    assert svg.startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert model["verdict"]["tension"]["binding"] in svg
    # the binding element is marked, and exactly one is
    assert svg.count('class="binds"') == 1


def test_the_diagram_prints_the_terms_it_was_given_and_computes_nothing():
    model = _model()
    for term in model["terms"]:
        term["newtons"] = 4242.0          # nonsense, but it is what was given
    svg = exports.diagram_svg(model)
    assert svg.count("4242") >= len(model["terms"])


def test_a_single_fall_draws_no_moving_block(tmp_path):
    model = _model()
    assert "moving block" not in exports.diagram_svg(model).lower()
    reeved = _model(configuration=_configuration(reeve_factor=2, sheave="WZ-11-K"))
    assert "moving block" in exports.diagram_svg(reeved).lower()


def test_the_diagram_escapes_what_it_is_given():
    model = _model()
    model["study"] = 'Vault & <script>"'
    svg = exports.diagram_svg(model)
    assert "<script>" not in svg and "&amp;" in svg


def test_escaping_does_not_double_escape():
    assert exports._esc('&<>"') == "&amp;&lt;&gt;&quot;"


def test_the_marked_element_moves_with_the_terms_not_with_a_recomputation():
    reeved = _model(configuration=_configuration(reeve_factor=2, sheave="WZ-11-K"))
    svg = exports.diagram_svg(reeved)
    assert svg.count('class="binds"') == 1
    marked = svg.split('class="binds"')[1].split("</g>")[0]
    assert "WZ-11-K" in marked


def test_the_diagram_names_the_net_band():
    svg = exports.diagram_svg(_model())
    assert "36 anchors" in svg and "658" in svg and "S7" in svg


def test_every_box_is_at_least_as_wide_as_its_longest_line():
    model = _model(configuration=_configuration(reeve_factor=2, sheave="WZ-11-K"))
    model["terms"][0]["part_id"] = "a-very-long-catalogue-identifier-for-a-part"
    by_name = {t["name"]: t for t in model["terms"]}
    for name, title in exports._PATH:
        if name not in by_name:
            continue
        lines = exports._box_lines(name, title, by_name[name], model["configuration"])
        longest = max(exports._estimated_width(t, s) for t, s, _ in lines)
        assert exports._box_width(lines) >= longest
    svg = exports.diagram_svg(model)
    import re
    width = int(re.search(r'<svg[^>]* width="(\d+)"', svg).group(1))
    assert 'viewBox="0 0 {} '.format(width) in svg


def test_the_net_band_counts_agree_with_their_nouns():
    one = exports.diagram_svg(_model())
    assert "1 wire," in one and "1 wires" not in one
    demand = _demand()
    demand["wires"].append({"name": "w2", "net_vertex": 9, "frame_point": [0, 0, 0]})
    demand["net"]["fixed"] = [1]
    two = exports.diagram_svg(_model(demand=demand))
    assert "2 wires" in two and "1 anchor," in two


def _section(text, heading_word):
    """The body of the `## ` section whose heading contains the word.

    Found by heading text, never by position, so adding a section cannot make
    an assertion silently read the wrong one.
    """
    blocks = text.split("\n## ")
    matches = [b for b in blocks[1:] if b.splitlines()[0].lower().find(heading_word) >= 0]
    assert len(matches) == 1, (heading_word, [b.splitlines()[0] for b in blocks])
    return matches[0]


def test_the_data_sheet_leads_with_the_failure_when_it_fails():
    model = _model()
    model["verdict"]["shape"]["within"] = False
    model["verdict"]["shape"]["worst_residual_mm"] = 7.4
    model["verdict"]["holds"] = False
    section = _section(exports.datasheet_markdown(model), "whether it holds")
    body = section.split("\n", 1)[1].strip()
    first_sentence = body.split(". ")[0]
    assert "not" in first_sentence.lower() or "fails" in first_sentence.lower()
    assert "does not keep its shape" in first_sentence
    assert "do not carry" not in first_sentence
    assert "7.4" in section


def test_the_data_sheet_names_the_tension_half_when_only_it_fails():
    model = _model()
    model["verdict"]["tension"]["passes"] = False
    model["verdict"]["holds"] = False
    section = _section(exports.datasheet_markdown(model), "whether it holds")
    first_sentence = section.split("\n", 1)[1].strip().split(". ")[0]
    assert "do not carry the tension" in first_sentence
    assert "does not keep" not in first_sentence


def test_the_data_sheet_states_a_pass_first_when_both_halves_hold():
    model = _model()
    assert model["verdict"]["holds"]
    section = _section(exports.datasheet_markdown(model), "whether it holds")
    first_sentence = section.split("\n", 1)[1].strip().split(". ")[0]
    assert "holds" in first_sentence.lower() and "not" not in first_sentence.lower()


def test_the_assumptions_are_a_section_and_not_a_footnote():
    text = exports.datasheet_markdown(_model())
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert any("assumption" in h.lower() for h in headings)
    assert any("not checked" in h.lower() for h in headings)
    assert "450000" in text or "450,000" in text      # the rope EA is named


def test_the_sheet_has_the_seven_sections_in_the_specified_order():
    text = exports.datasheet_markdown(_model())
    headings = [l[3:].lower() for l in text.splitlines() if l.startswith("## ")]
    words = ["replaces", "demands", "chosen", "holds", "load path",
             "assumptions", "not checked"]
    assert len(headings) == 7
    for heading, word in zip(headings, words):
        assert word in heading


def test_every_assumed_figure_reaches_the_sheet():
    model = _model()
    section = _section(exports.datasheet_markdown(model), "assumptions")
    for assumption in model["assumptions"]:
        assert assumption["what"] in section


def test_every_unchecked_item_reaches_the_sheet():
    model = _model()
    section = _section(exports.datasheet_markdown(model), "not checked")
    for line in model["not_checked"]:
        assert line in section


def test_the_acceptance_source_is_quoted_verbatim():
    model = _model()
    section = _section(exports.datasheet_markdown(model), "replaces")
    assert model["verdict"]["shape"]["acceptance_source"] in section


def test_the_data_sheet_has_no_em_dash_and_no_latex():
    text = exports.datasheet_markdown(_model())
    assert "\u2014" not in text and "$" not in text and "\frac" not in text


def test_the_load_path_lists_every_term_and_marks_the_binding_one():
    model = _model()
    section = _section(exports.datasheet_markdown(model), "load path")
    for term in model["terms"]:
        assert term["name"] in section
    assert section.count("binds") + section.count("binding") >= 1


def test_the_data_sheet_is_written_beside_the_others(tmp_path):
    path = exports.write_datasheet(_model(), tmp_path, "vault-cablenet")
    assert path.name == "vault-cablenet.md"
    assert path.read_text(encoding="utf-8").startswith("# ")
