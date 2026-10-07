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


def test_the_model_names_the_units_of_density_and_thickness():
    demand = _model()["demand"]
    assert demand["density_kg_m3"] == 1800.0
    assert demand["thickness_m"] == 0.02


def test_the_sheet_names_the_units_of_density_and_thickness():
    section = _section(exports.datasheet_markdown(_model()), "demands")
    assert "1,800 kg/m3" in section and "0.020 m" in section
    assert "own units" not in section


def test_no_assumption_has_a_confidence_word_for_a_value():
    model = _model()
    for assumption in model["assumptions"]:
        assert assumption["value"] != "assumed", assumption
    text = exports.datasheet_markdown(model)
    assert "Value: assumed" not in text


def test_the_rope_ea_and_the_gearbox_efficiency_each_appear_once():
    whats = [a["what"] for a in _model()["assumptions"]]
    assert whats.count("rope EA") == 1
    assert whats.count("gearbox efficiency") == 1
    assert not any(w.endswith("ea confidence") or w.endswith("efficiency confidence")
                   for w in whats)


def test_the_load_path_uses_one_decimal_convention():
    import re
    section = _section(exports.datasheet_markdown(_model()), "load path")
    figures = re.findall(r"allows ([\d,.]+) N", section)
    assert figures and all(re.fullmatch(r"\d+\.\d", f) for f in figures)


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------

def _plant_demand(monkeypatch, tmp_path, name="My Vault", demand=None):
    import json
    import bundle
    import geometry

    monkeypatch.setattr(bundle, "STUDIES_DIR", tmp_path / "studies")
    path = bundle.cablenet_path(geometry.slugify(name), "tile", "herringbone",
                                1.0, 0.02, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(demand or _demand()), encoding="utf-8")


def _into(monkeypatch, folder):
    folder.mkdir(exist_ok=True)
    monkeypatch.setattr(studio_app, "read_settings",
                        lambda: {"cablenet_exports_folder": str(folder)})


def _spy_on_export_model(monkeypatch):
    seen = {}
    real = exports.export_model

    def spy(*args, **kwargs):
        seen["row"] = args[2]
        seen["ladder"] = kwargs.get("ladder_rows")
        return real(*args, **kwargs)

    monkeypatch.setattr(exports, "export_model", spy)
    return seen


def test_one_run_produces_three_documents_that_name_the_same_binding_part(tmp_path):
    # LITERAL: the ceiling is rendered once by the shared formatter and must
    # appear byte for byte in the diagram, the data sheet and the spreadsheet.
    model = _model()
    paths = (exports.write_spreadsheet(model, tmp_path, "x")
             + [exports.write_diagram(model, tmp_path, "x"),
                exports.write_datasheet(model, tmp_path, "x")])
    binding = model["verdict"]["tension"]["binding"]
    shown = exports._newtons(model["verdict"]["tension"]["ceiling_newtons"])
    assert shown == "1471.0"
    svg = [p for p in paths if p.suffix == ".svg"][0].read_text(encoding="utf-8")
    md = [p for p in paths if p.suffix == ".md"][0].read_text(encoding="utf-8")
    assert binding in svg and binding in md
    assert shown + " N" in svg and shown + " N" in md
    if exports._openpyxl is not None:
        import openpyxl
        book = openpyxl.load_workbook(next(p for p in paths if p.suffix == ".xlsx"))
        cells = [c for row in book["Chosen"].iter_rows() for c in row
                 if c.value is not None]
        ceiling = next(c for c in cells if c.value == float(shown))
        assert ceiling.number_format == "0.0"
        assert binding in [c.value for c in cells]


def test_the_csv_fallback_prints_the_same_ceiling_text(tmp_path, monkeypatch):
    monkeypatch.setattr(exports, "_openpyxl", None)
    model = _model()
    paths = exports.write_spreadsheet(model, tmp_path, "x")
    shown = exports._newtons(model["verdict"]["tension"]["ceiling_newtons"])
    chosen = next(p for p in paths if p.name.endswith("-chosen.csv"))
    text = chosen.read_text(encoding="utf-8-sig")
    assert shown in text
    assert model["verdict"]["tension"]["binding"] in text


def test_every_force_is_written_by_the_one_formatter():
    # no renderer may format newtons its own way: 1500 N and 1471.4 N read alike
    assert exports._newtons(1500) == "1500.0"
    assert exports._newtons(1471.4) == "1471.4"
    assert exports._newtons(None) == "not recorded"
    model = _model()
    svg = exports.diagram_svg(model)
    md = exports.datasheet_markdown(model)
    import re
    for text in (svg, md):
        assert not re.search(r"\b\d{4,} N\b", text)       # always a decimal
    # no force is grouped, whatever follows it: the only grouped figure the
    # sheet may carry is the density, which is not a force
    assert _grouped_figures(md + svg) == [], _grouped_figures(md + svg)


GROUPED = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?(?: \S+)?"


def _grouped_figures(text):
    import re
    return [g for g in re.findall(GROUPED, text) if not g.endswith(" kg/m3")]


def test_the_forbidding_tests_really_fail_on_a_grouped_force():
    # the guard must bite: feed it the shapes the old regexes let through
    import re
    for bad in ("Value: 450,000", "Value: 450,000.0", "allows 1,471.0 N",
                "taken as 450,000 N"):
        assert _grouped_figures(bad), bad
    assert _grouped_figures("a density of 1,800 kg/m3") == []
    assert not re.fullmatch(r"\d+\.\d", "1,471.0")


def test_a_force_assumption_prints_ungrouped_with_one_decimal_and_a_unit():
    text = exports.datasheet_markdown(_model())
    assert "**rope EA.** Value: 450000.0 N." in text
    assert "**uniform prestress.** Value: 300.0 N." in text
    assert "450,000" not in text


def test_the_route_writes_all_three_and_they_agree(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    folder = tmp_path / "out"
    _into(monkeypatch, folder)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    written = [Path(p) for p in response.json()["paths"]]
    assert {p.suffix for p in written} >= {".svg", ".md"}
    assert all(p.is_file() and p.parent == folder for p in written)
    svg = next(p for p in written if p.suffix == ".svg").read_text(encoding="utf-8")
    md = next(p for p in written if p.suffix == ".md").read_text(encoding="utf-8")
    assert "turnbuckle-hook-hook-M10" in svg and "turnbuckle-hook-hook-M10" in md
    assert "1471.0 N" in svg and "1471.0 N" in md


def test_the_route_scores_the_panels_ladder(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    ladder = seen["ladder"]
    assert len(ladder) == 5
    assert ladder[0]["configuration"] == _configuration()
    assert ladder[1]["configuration"]["chain"] == ["eye-M12", "turnbuckle-eye-eye-M10"]
    assert ladder[2]["configuration"]["rope"] == "rope-5mm"
    assert ladder[3]["configuration"]["chain"] == ["eye-M16", "turnbuckle-eye-eye-M10"]
    assert ladder[3]["configuration"]["rope"] == "rope-6mm"
    assert ladder[4]["configuration"]["chain"] == ["eye-M20", "turnbuckle-eye-eye-M12"]
    assert ladder[4]["configuration"]["rope"] == "rope-8mm"
    assert all(rung["refused"] is None and rung["ceiling"] > 0 for rung in ladder)


def test_a_rung_the_catalogue_refuses_is_passed_through_with_its_text(
        client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    # no eye-and-eye turnbuckle exists at M20, so the first rung is refused
    configuration = _configuration(chain=["eye-M20", "turnbuckle-hook-eye-M20"])
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": configuration})
    assert response.status_code == 200, response.text
    assert len(seen["ladder"]) == 5
    assert seen["ladder"][1]["refused"]


def test_the_rope_wound_is_the_worst_wires_summed_reel_commands(
        client, monkeypatch, tmp_path):
    stages = _demand()["stages"]
    stages[0]["wire_reel_commands"] = [5.0, -3.0]
    stages[1]["wire_reel_commands"] = [-10.0, -20.0]
    _plant_demand(monkeypatch, tmp_path, demand=_demand(stages=stages))
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    client.post("/api/studies/My Vault/cablenet/exports",
                json={"configuration": _configuration()})
    assert seen["row"]["rope_path"]["rope_wound_mm"] == 23.0


def test_a_body_rope_wound_wins_over_the_demand(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    client.post("/api/studies/My Vault/cablenet/exports",
                json={"configuration": _configuration(), "rope_wound_mm": 123.0})
    assert seen["row"]["rope_path"]["rope_wound_mm"] == 123.0


def test_a_failing_configuration_is_still_exported(client, monkeypatch, tmp_path):
    stages = _demand()["stages"]
    stages[1]["wire_tensions"] = [90000.0]       # far over any ceiling
    _plant_demand(monkeypatch, tmp_path, demand=_demand(stages=stages))
    _into(monkeypatch, tmp_path / "out")
    seen = _spy_on_export_model(monkeypatch)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 200, response.text
    assert seen["row"]["passes"] is False


def test_a_refused_configuration_is_a_400_not_a_500(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    response = client.post(
        "/api/studies/My Vault/cablenet/exports",
        json={"configuration": _configuration(motor="no-such-motor")})
    assert response.status_code == 400
    assert "cannot be built" in response.json()["detail"]


def test_a_study_with_no_demand_document_cannot_export(client):
    response = client.post("/api/studies/nothing-here/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code == 404
    assert "cable net phase" in response.json()["detail"]


def test_an_unwritable_folder_is_reported_and_not_swallowed(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    gone = tmp_path / "gone"
    monkeypatch.setattr(studio_app, "read_settings",
                        lambda: {"cablenet_exports_folder": str(gone)})
    # the folder is missing, so the export must say so rather than silently
    # landing somewhere else, which is what deliver_output would do
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code != 200
    assert str(gone) in response.json()["detail"]
    assert not gone.exists()


def test_an_os_error_while_writing_names_the_folder_and_the_reason(
        client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    folder = tmp_path / "out"
    _into(monkeypatch, folder)

    def refuse(*args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(exports, "write_diagram", refuse)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration()})
    assert response.status_code != 200
    detail = response.json()["detail"]
    assert str(folder) in detail and "Access is denied" in detail


def test_each_kind_can_be_downloaded_after_a_run(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    client.post("/api/studies/My Vault/cablenet/exports",
                json={"configuration": _configuration()})
    for kind, suffix in (("spreadsheet", ".xlsx"), ("diagram", ".svg"),
                         ("datasheet", ".md")):
        response = client.get("/api/studies/My Vault/cablenet/exports/" + kind)
        assert response.status_code == 200, kind
        assert suffix in response.headers["content-disposition"]
    assert client.get("/api/studies/My Vault/cablenet/exports/other").status_code == 400


def test_a_csv_fallback_is_served_as_one_zip(client, monkeypatch, tmp_path):
    import io
    import zipfile
    monkeypatch.setattr(exports, "_openpyxl", None)
    _plant_demand(monkeypatch, tmp_path)
    _into(monkeypatch, tmp_path / "out")
    posted = client.post("/api/studies/My Vault/cablenet/exports",
                         json={"configuration": _configuration()}).json()
    assert posted["note"]
    response = client.get("/api/studies/My Vault/cablenet/exports/spreadsheet")
    assert response.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert len(names) == len(exports.SHEETS) and all(n.endswith(".csv") for n in names)


def test_downloading_before_any_run_is_a_404(client, monkeypatch, tmp_path):
    _into(monkeypatch, tmp_path / "out")
    response = client.get("/api/studies/My Vault/cablenet/exports/diagram")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# The shape verdict has three states. Nothing to judge is NOT a pass.
# ---------------------------------------------------------------------------

def _degenerate_demands():
    no_stages = _demand(stages=[])
    no_residual = _demand()
    for stage in no_residual["stages"]:
        stage.pop("residual_after")
    no_line = _demand(acceptance=None)
    no_line["stages"][1]["residual_after"] = 99.0
    return {"no stages": no_stages, "no residual": no_residual,
            "no acceptance": no_line}


@pytest.mark.parametrize("which", ["no stages", "no residual", "no acceptance"])
def test_a_demand_with_nothing_to_judge_is_not_established(which):
    model = _model(demand=_degenerate_demands()[which])
    shape = model["verdict"]["shape"]
    assert shape["within"] is None
    assert shape["why_unknown"]
    assert model["verdict"]["holds"] is not True
    assert model["verdict"]["holds"] is None


def test_the_three_reasons_are_told_apart():
    reasons = {k: _model(demand=d)["verdict"]["shape"]["why_unknown"]
               for k, d in _degenerate_demands().items()}
    assert len(set(reasons.values())) == 3


def test_a_failing_tension_half_is_false_even_when_the_shape_is_unknown():
    import catalogue
    parts = catalogue.load_parts()
    configuration = _configuration()
    row = _row(parts, configuration, passes=False)
    model = _model(demand=_demand(stages=[]), row=row)
    assert model["verdict"]["holds"] is False


def test_genuine_verdicts_are_not_turned_into_unknowns():
    passing = _model()["verdict"]
    assert passing["shape"]["within"] is True and passing["holds"] is True
    assert passing["shape"]["why_unknown"] is None
    demand = _demand()
    demand["stages"][1]["residual_after"] = 7.4
    failing = _model(demand=demand)["verdict"]
    assert failing["shape"]["within"] is False and failing["holds"] is False


def test_an_unreachable_stage_is_a_failure_and_not_an_unknown():
    demand = _demand(stages=[{"stage": 1, "name": "S1", "reachable": False}])
    verdict = _model(demand=demand)["verdict"]
    assert verdict["shape"]["within"] is False
    assert verdict["holds"] is False
    nulled = _demand(acceptance=None)
    nulled["stages"][1]["reachable"] = False
    assert _model(demand=nulled)["verdict"]["shape"]["within"] is False


def _unknown_model():
    return _model(demand=_demand(stages=[]))


def test_the_data_sheet_says_not_established_and_never_that_it_holds():
    text = exports.datasheet_markdown(_unknown_model())
    section = _section(text, "whether it holds")
    first = section.split("\n", 1)[1].strip().split(". ")[0].lower()
    assert "not been established" in first
    assert "this configuration holds" not in section.lower()
    assert "does not hold" not in section.lower()
    assert "stays within the acceptance line. That has not been established" in section
    assert "no residual was measured" in section


def test_the_chosen_sheet_says_not_established_and_never_yes_for_the_shape(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    written = exports.write_spreadsheet(_unknown_model(), tmp_path, "x")
    rows = [[c.value for c in row] for row in
            openpyxl.load_workbook(written[0])["Chosen"].iter_rows()]
    by_label = {r[0]: r for r in rows if r and r[0]}
    shape_row = by_label["Shape: within the acceptance line"]
    both_row = by_label["Both halves hold"]
    assert shape_row[1] == "not established"
    assert "no residual was measured" in str(shape_row[2])
    assert both_row[1] == "not established"


def test_the_diagram_says_not_established_and_never_that_it_holds():
    svg = exports.diagram_svg(_unknown_model())
    assert "not established" in svg
    assert "Verdict: holds" not in svg and "does not hold" not in svg
    passing = exports.diagram_svg(_model())
    assert "Verdict: holds" in passing and "not established" not in passing
    demand = _demand()
    demand["stages"][1]["residual_after"] = 7.4
    failing = exports.diagram_svg(_model(demand=demand))
    assert "does not hold" in failing and "not established" not in failing


def test_the_panel_and_the_documents_agree_on_what_is_unknown():
    import re
    js = (Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
          / "cablenet.js").read_text(encoding="utf-8")
    for demand in _degenerate_demands().values():
        why = _model(demand=demand)["verdict"]["shape"]["why_unknown"]
        assert why in js          # the panel carries the documents' wording
    assert re.search(r"acceptance === null", js)


# ---------------------------------------------------------------------------
# Review fixes: one truth test for `reachable`, one rounding for lengths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["absent", "null"])
def test_a_stage_with_no_reachable_is_told_the_same_way_everywhere(
        tmp_path, monkeypatch, missing):
    demand = _demand()
    if missing == "absent":
        demand["stages"][1].pop("reachable")
    else:
        demand["stages"][1]["reachable"] = None
    model = _model(demand=demand)
    # not False, so not an unreachable stage; and never read as reached
    assert model["verdict"]["shape"]["unreachable_stages"] == []
    text = exports.datasheet_markdown(model)
    assert "Stage 2 (S7, tile): residual 1.40 mm, reachability not recorded." in text
    assert "Stage 1 (S1, raise): residual 0.50 mm, reached." in text
    assert "not reachable" not in text
    rows = exports._sheet_rows(model)["Stages"]
    reach = {r[1]: r[5] for r in rows if len(r) == 7 and r[1] in ("S1", "S7")}
    assert reach == {"S1": "yes", "S7": "not recorded"}
    assert "Shape: unreachable stages" not in str(exports._sheet_rows(model)["Chosen"])


def test_a_stage_that_is_false_is_unreachable_in_every_document():
    demand = _demand()
    demand["stages"][1]["reachable"] = False
    model = _model(demand=demand)
    assert model["verdict"]["shape"]["unreachable_stages"] == ["S7"]
    assert "residual 1.40 mm, not reachable." in exports.datasheet_markdown(model)
    rows = exports._sheet_rows(model)["Stages"]
    assert {r[1]: r[5] for r in rows if len(r) == 7}["S7"] == "no"
    assert "does not hold" in exports.diagram_svg(model)


def test_the_panel_tests_reachable_against_false_only():
    js = (Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
          / "cablenet.js").read_text(encoding="utf-8")
    assert "stage.reachable === false" in js
    assert "stage.reachable ===" not in js.replace("stage.reachable === false", "")


def test_workbook_lengths_use_the_data_sheets_rounding(tmp_path, monkeypatch):
    demand = _demand()
    demand["stages"][1]["residual_after"] = 1.4000000000000001
    demand["stages"][1]["deviation"] = 0.30000000000000004
    monkeypatch.setattr(exports, "_openpyxl", None)
    model = _model(demand=demand)
    paths = exports.write_spreadsheet(model, tmp_path, "x")
    stages = next(p for p in paths if p.name.endswith("-stages.csv")).read_text(
        encoding="utf-8-sig")
    assert "1.40" in stages and "0.30" in stages
    assert "1.4000000000000001" not in stages and "0.30000000000000004" not in stages
    assert exports._millimetres(1.4000000000000001) == "1.40"


# ---------------------------------------------------------------------------
# A chosen rope can contradict the analysis the demand was solved for
# ---------------------------------------------------------------------------

def _all_documents(model, tmp_path):
    """The three documents as text, the workbook through its CSV fallback."""

    import re
    texts = {"datasheet": exports.datasheet_markdown(model),
             "diagram": exports.diagram_svg(model)}
    rows = exports._sheet_rows(model)
    texts["workbook"] = "\n".join(
        str(c) for sheet in rows.values() for row in sheet for c in row)
    return texts


def test_a_different_rope_is_stated_in_all_three_documents(tmp_path):
    # solved at 450000 N for rope-4mm, exported with rope-8mm (EA 1800000 N)
    model = _model(configuration=_configuration(rope="rope-8mm"))
    mismatch = model["rope_mismatch"]
    assert mismatch["analysed_rope"] == "rope-4mm"
    assert mismatch["chosen_rope"] == "rope-8mm"
    for name, text in _all_documents(model, tmp_path).items():
        flat = " ".join(text.split())
        assert "the chosen rope is not the rope that was analysed" in flat, name
        assert "rope-4mm" in flat and "rope-8mm" in flat, name
        assert "The tension ceiling is for the chosen rope" in flat, name
        assert ("The prestress floor, the residuals and the cut lengths are "
                "for the analysed rope and do not describe the chosen one"
                in flat), name
    # the ceiling really is the chosen rope's, and the export is not refused
    assert model["verdict"]["tension"]["ceiling_newtons"] > 0


def test_the_data_sheet_states_the_mismatch_before_the_first_section():
    text = exports.datasheet_markdown(
        _model(configuration=_configuration(rope="rope-8mm")))
    assert text.index("not the rope that was analysed") < text.index("## ")


def test_the_two_ea_figures_are_each_labelled_when_the_rope_differs():
    text = exports.datasheet_markdown(
        _model(configuration=_configuration(rope="rope-8mm")))
    assert "(EA 450000.0 N)" in text and "(EA 1800000.0 N)" in text


def test_nothing_extra_is_said_when_the_rope_is_the_one_analysed(tmp_path):
    import re
    model = _model()
    assert model["rope_mismatch"] is None
    for name, text in _all_documents(model, tmp_path).items():
        assert "not the rope that was analysed" not in text, name
        assert "Warning" not in text, name
    md = exports.datasheet_markdown(model)
    # ONE rope EA figure, wherever it is printed
    figures = set(re.findall(r"\b(?:450000|1800000)\.0\b", md))
    assert figures == {"450000.0"}


def test_a_demand_with_no_ea_cannot_contradict_a_rope():
    demand = _demand()
    demand["ea_newtons"] = None
    assert _model(demand=demand)["rope_mismatch"] is None


def test_an_unnamed_analysed_rope_is_found_by_its_stiffness():
    demand = _demand()
    demand["net"]["ea_provenance"] = "assumed"
    model = _model(demand=demand, configuration=_configuration(rope="rope-8mm"))
    assert model["rope_mismatch"]["analysed_rope"] == "rope-4mm"


def test_the_route_exports_a_different_rope_and_says_so(client, monkeypatch, tmp_path):
    _plant_demand(monkeypatch, tmp_path)
    folder = tmp_path / "out"
    _into(monkeypatch, folder)
    response = client.post("/api/studies/My Vault/cablenet/exports",
                           json={"configuration": _configuration(rope="rope-8mm")})
    assert response.status_code == 200, response.text
    md = next(Path(p) for p in response.json()["paths"]
              if p.endswith(".md")).read_text(encoding="utf-8")
    assert "not the rope that was analysed" in md
