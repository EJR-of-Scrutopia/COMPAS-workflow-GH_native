"""Load a study file and turn it into a worker request envelope.

A study file is the protocol payload plus two authoring keys. Keeping the
``payload`` block byte-identical to what the Grasshopper components send means
a captured canvas solve is already a valid study.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping


PROTOCOL_VERSION = 1
STUDY_KEYS = ("$schema", "study", "command", "payload")


def factor_warnings(payload: Mapping[str, Any]) -> List[str]:
    """Warn about payload fields the worker decodes but never applies.

    ``LoadCase.factor`` is the live example. ``gh.loads.build_load_case``
    multiplies the vectors by the factor, but ``codec.decode_load_case``
    stores the raw vectors and the factor side by side, and no solver reads
    the factor afterwards. The Grasshopper Loads component sidesteps this by
    pre-multiplying and sending ``Factor = 1.0``. A hand-written study file
    has no such protection, and this bench exists to invite hand-writing, so
    it says so rather than quietly solving the wrong load.
    """

    load_case = payload.get("load_case")
    if not isinstance(load_case, Mapping):
        return []
    factor = load_case.get("factor")
    if factor is None:
        return []
    try:
        value = float(factor)
    except (TypeError, ValueError):
        return []
    if abs(value - 1.0) < 1e-12:
        return []
    return [
        "load_case.factor is {} but the worker does not apply it. The solve "
        "will use the vectors exactly as written. Multiply the vectors "
        "instead.".format(value)
    ]


class StudyError(ValueError):
    """Raised when a study file cannot be read or is malformed."""


def _resolve_ref(value: Any, root: Path) -> Any:
    """Replace a ``{"$ref": "sibling.json"}`` object with the file contents."""

    if not isinstance(value, Mapping) or "$ref" not in value:
        return value
    if len(value) != 1:
        raise StudyError(
            "A $ref object must contain only the $ref key."
        )
    reference = value["$ref"]
    if not isinstance(reference, str) or not reference:
        raise StudyError("A $ref must be a non-empty relative path.")
    target = (root / reference).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise StudyError(
            "$ref {!r} resolves outside the study directory.".format(reference)
        )
    if not target.is_file():
        raise StudyError("$ref target does not exist: {}".format(target))
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StudyError(
            "$ref target {} is not valid JSON: {}".format(target, error)
        )


def load_study(path: Path) -> Dict[str, Any]:
    """Read a study file, resolving payload-level ``$ref`` objects."""

    path = Path(path)
    if not path.is_file():
        raise StudyError("Study file does not exist: {}".format(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StudyError("{} is not valid JSON: {}".format(path, error))
    if not isinstance(document, Mapping):
        raise StudyError("A study file must contain a JSON object.")
    document = dict(document)
    unknown = sorted(set(document) - set(STUDY_KEYS))
    if unknown:
        raise StudyError(
            "Study file contains unsupported keys: {}.".format(", ".join(unknown))
        )
    command = document.get("command")
    if not isinstance(command, str) or not command:
        raise StudyError("A study file requires a non-empty command string.")
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        raise StudyError("A study file requires a payload object.")
    root = path.parent.resolve()
    document["payload"] = {
        key: _resolve_ref(value, root) for key, value in payload.items()
    }
    return document


def build_request(study: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the worker request envelope for one loaded study."""

    return {
        "v": PROTOCOL_VERSION,
        "type": "request",
        "id": str(study.get("study") or "study"),
        "command": study["command"],
        "payload": dict(study["payload"]),
    }


__all__ = [
    "PROTOCOL_VERSION",
    "factor_warnings",
    "STUDY_KEYS",
    "StudyError",
    "build_request",
    "load_study",
]
