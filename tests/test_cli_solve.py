from __future__ import annotations

import json
import shutil
from pathlib import Path

from ananke_equilibrium.cli.main import main
from ananke_equilibrium.cli.study import build_request
from ananke_equilibrium.cli.study import load_study
from ananke_equilibrium.worker import dispatch


EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "example-arch"


def copy_example(tmp_path):
    target = tmp_path / "example-arch"
    # Exclude results/: a previous run in the real studies directory leaves one
    # behind, and copying it would let the "no result written on failure" test
    # pass on a copied file rather than on the behaviour it means to check.
    shutil.copytree(EXAMPLE, target, ignore=shutil.ignore_patterns("results"))
    assert not (target / "results").exists()
    return target / "problem.json"


def test_solve_writes_a_result_file(tmp_path):
    problem = copy_example(tmp_path)
    exit_code = main(["solve", str(problem)])
    assert exit_code == 0
    result_path = problem.parent / "results" / "result.json"
    assert result_path.is_file()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["vertices"]


def test_solve_matches_a_direct_dispatch_call(tmp_path):
    problem = copy_example(tmp_path)
    main(["solve", str(problem)])
    written = json.loads(
        (problem.parent / "results" / "result.json").read_text(encoding="utf-8")
    )
    direct = dispatch(build_request(load_study(problem)))
    assert written == direct["result"]


def test_solve_reports_a_contract_failure_and_exits_one(tmp_path, capsys):
    problem = copy_example(tmp_path)
    document = json.loads(problem.read_text(encoding="utf-8"))
    document["payload"]["supports"]["node_ids"] = [99]
    problem.write_text(json.dumps(document), encoding="utf-8")
    exit_code = main(["solve", str(problem)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.strip()
    assert not (problem.parent / "results" / "result.json").exists()


def test_archive_writes_a_second_timestamped_copy(tmp_path):
    problem = copy_example(tmp_path)
    main(["solve", str(problem), "--archive"])
    results = sorted((problem.parent / "results").glob("*.json"))
    assert len(results) == 2
    assert (problem.parent / "results" / "result.json") in results
