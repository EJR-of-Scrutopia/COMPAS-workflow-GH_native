"""Keep the FEA tests out of any environment that cannot run them.

The discriminator is the OpenSees backend, not compas_fea2 itself. The main
environment may legitimately carry compas_fea2 0.2.1 through the pyproject
"fea" extra, which the worker uses for capability reporting, but that build
has no backend, no shims, and none of the pinned-commit API this suite is
written against. compas_fea2_opensees is not on PyPI at all, so its
presence identifies the dedicated .venv-fea and nothing else.
"""

collect_ignore_glob = []

try:
    import compas_fea2_opensees  # noqa: F401
except ImportError:
    collect_ignore_glob = ["*.py"]
