from __future__ import annotations

import ast
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised by the Python 3.9 CI job
    import tomli as tomllib

from ananke_equilibrium import __version__


REPOSITORY = Path(__file__).resolve().parents[1]


def test_v01_manifest_matches_source_scripts_and_package_version():
    manifest_path = REPOSITORY / "plugin" / "components.toml"
    with manifest_path.open("rb") as stream:
        manifest = tomllib.load(stream)

    components = manifest["components"]
    keys = [component["key"] for component in components]
    assert len(components) == 10
    assert len(keys) == len(set(keys))
    assert manifest["plugin"]["version"] == __version__

    for component in components:
        source = REPOSITORY / component["source_script"]
        assert source.is_file(), component["key"]
        ast.parse(
            source.read_text(encoding="utf-8"),
            filename=str(source),
            feature_version=(3, 9),
        )
