from __future__ import annotations

from ananke_equilibrium.cli.main import main


def test_health_prints_worker_and_packages(capsys):
    exit_code = main(["health"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ananke-equilibrium-worker" in captured.out
    assert "compas" in captured.out


def test_unknown_command_exits_nonzero(capsys):
    exit_code = main(["definitely-not-a-command"])
    assert exit_code == 2
