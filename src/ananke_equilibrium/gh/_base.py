"""Shared helpers for the thin Grasshopper-facing adapter layer.

This package is deliberately importable in ordinary CPython without Rhino,
Grasshopper, COMPAS, or the numerical backends installed.  Actual solver
imports happen only when a component function is executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from importlib import import_module
from inspect import Parameter
from inspect import signature
from math import isfinite
from typing import Any
from typing import Callable
from typing import Generic
from typing import Mapping
from typing import Optional
from typing import TypeVar


T = TypeVar("T")
_MISSING = object()


class AdapterError(RuntimeError):
    """Base error for component-boundary failures."""


class OptionalDependencyError(AdapterError, ImportError):
    """Raised when an optional numerical or host dependency is unavailable."""


@dataclass(frozen=True)
class ComponentStatus:
    """Small status object suitable for a single Grasshopper output.

    ``severity`` is one of ``"ok"``, ``"warning"`` or ``"error"``.  Keeping
    it as a string makes the object serialisable and avoids importing
    Grasshopper runtime-message enums.
    """

    severity: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.severity != "error"

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class ComponentResult(Generic[T]):
    """The two logical outputs shared by the v0.1 adapter components."""

    value: Optional[T]
    status: ComponentStatus

    @property
    def ok(self) -> bool:
        return self.status.ok

    def __iter__(self):
        """Allow ``Value, Status = result`` in a Grasshopper wrapper."""

        yield self.value
        yield self.status

    def unwrap(self) -> T:
        """Return the value or raise a friendly boundary error."""

        if self.value is None or not self.ok:
            raise AdapterError(self.status.message)
        return self.value


def success(value: T, message: str, **details: Any) -> ComponentResult[T]:
    return ComponentResult(
        value=value,
        status=ComponentStatus("ok", message, details),
    )


def warning(value: T, message: str, **details: Any) -> ComponentResult[T]:
    return ComponentResult(
        value=value,
        status=ComponentStatus("warning", message, details),
    )


def failure(message: str, **details: Any) -> ComponentResult[Any]:
    return ComponentResult(
        value=None,
        status=ComponentStatus("error", message, details),
    )


def friendly(component_name: str):
    """Convert expected component-boundary exceptions into a status output."""

    handled = (
        AdapterError,
        ImportError,
        AttributeError,
        TypeError,
        ValueError,
    )

    def decorate(function: Callable[..., T]):
        def wrapped(*args: Any, **kwargs: Any) -> ComponentResult[T]:
            try:
                result = function(*args, **kwargs)
            except handled as error:
                return failure(
                    "{}: {}".format(component_name, error),
                    exception=type(error).__name__,
                    component=component_name,
                )
            if isinstance(result, ComponentResult):
                return result
            return success(result, "{} complete.".format(component_name))

        wrapped.__name__ = function.__name__
        wrapped.__doc__ = function.__doc__
        wrapped.__module__ = function.__module__
        return wrapped

    return decorate


def unwrap_goo(value: Any) -> Any:
    """Unwrap common GH goo wrappers without importing Grasshopper."""

    return value.Value if hasattr(value, "Value") else value


def items(value: Any) -> list[Any]:
    """Normalise a Grasshopper item/list input into a regular Python list."""

    value = unwrap_goo(value)
    if value is None:
        return []
    if isinstance(value, (str, bytes, Mapping)):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def get_value(value: Any, name: str, default: Any = _MISSING) -> Any:
    """Read a named value from either a mapping or protocol-like object."""

    if isinstance(value, Mapping) and name in value:
        return value[name]
    if hasattr(value, name):
        return getattr(value, name)
    if default is _MISSING:
        raise AdapterError(
            "{} is missing required field {!r}.".format(type(value).__name__, name)
        )
    return default


def get_any(
    value: Any,
    names: tuple[str, ...],
    default: Any = _MISSING,
) -> Any:
    """Read the first available alias from a mapping or protocol-like object."""

    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    if default is _MISSING:
        raise AdapterError(
            "{} is missing required field {}.".format(
                type(value).__name__,
                "/".join(names),
            )
        )
    return default


def finite_float(value: Any, label: str, *, positive: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise AdapterError("{} must be numeric.".format(label)) from error
    if not isfinite(result):
        raise AdapterError("{} must be finite.".format(label))
    if positive and result <= 0.0:
        raise AdapterError("{} must be greater than zero.".format(label))
    return result


def point3(value: Any, label: str = "Point") -> tuple[float, float, float]:
    """Coerce Rhino-like or sequence-like points without importing Rhino."""

    value = unwrap_goo(value)
    if all(hasattr(value, axis) for axis in ("X", "Y", "Z")):
        coordinates = (value.X, value.Y, value.Z)
    else:
        try:
            coordinates = tuple(value)
        except TypeError as error:
            raise AdapterError("{} must be a point-like value.".format(label)) from error
    if len(coordinates) == 2:
        coordinates = coordinates + (0.0,)
    if len(coordinates) != 3:
        raise AdapterError("{} must contain two or three coordinates.".format(label))
    return tuple(
        finite_float(component, "{} coordinate".format(label))
        for component in coordinates
    )


def vector3(value: Any, label: str = "Vector") -> tuple[float, float, float]:
    return point3(value, label)


def import_backend(
    injected: Any,
    *,
    candidates: tuple[str, ...],
    purpose: str,
) -> Any:
    """Resolve an injected backend first, then lazily try module candidates."""

    if injected is not None:
        return injected
    errors = []
    for module_name in candidates:
        try:
            return import_module(module_name)
        except ImportError as error:
            errors.append("{} ({})".format(module_name, error))
    raise OptionalDependencyError(
        "{} requires a numerical backend. Install the plugin dependencies or "
        "inject a backend callable/module. Tried: {}.".format(
            purpose,
            ", ".join(errors),
        )
    )


def call_backend(backend: Any, method: str, /, *args: Any, **kwargs: Any) -> Any:
    """Call either an injected callable or a named method on a backend module."""

    function = backend if callable(backend) else getattr(backend, method, None)
    if not callable(function):
        raise AdapterError(
            "The injected backend must be callable or provide {}(...).".format(method)
        )
    return function(*args, **kwargs)


def contract_type(name: str) -> type:
    """Load a shared contract type only when an adapter is executed."""

    try:
        module = import_module("ananke_equilibrium.contracts")
    except ImportError as error:
        raise OptionalDependencyError(
            "The shared contract module is unavailable; reinstall the plugin."
        ) from error
    contract = getattr(module, name, None)
    if not isinstance(contract, type):
        raise OptionalDependencyError(
            "The installed contract module does not define {}.".format(name)
        )
    return contract


def make_contract(contract_name: str, **values: Any) -> Any:
    """Construct a contract while tolerating additive contract evolution.

    Adapters intentionally depend on field names rather than a concrete import
    at module import time.  Extra values are filtered against the constructor;
    missing required values still produce an explicit, friendly error.
    """

    cls = contract_type(contract_name)
    parameters = signature(cls).parameters
    accepts_kwargs = any(
        parameter.kind == Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    supplied = values if accepts_kwargs else {
        key: value for key, value in values.items() if key in parameters
    }
    required = [
        key
        for key, parameter in parameters.items()
        if parameter.kind
        not in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD)
        and parameter.default is Parameter.empty
        and key not in supplied
    ]
    if required:
        raise AdapterError(
            "{} contract requires fields not supplied by this adapter: {}.".format(
                contract_name,
                ", ".join(required),
            )
        )
    try:
        return cls(**supplied)
    except (TypeError, ValueError) as error:
        raise AdapterError(
            "Could not create {}: {}".format(contract_name, error)
        ) from error


def contract_name(value: Any) -> str:
    return type(value).__name__
