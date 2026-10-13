"""Test setup: lets the integration's modules be imported without Home Assistant.

The mapping, gating and helper logic under test is plain Python. Home Assistant,
aiohttp and cryptography are replaced with minimal stand-ins so the suite only
needs ``pytest``.
"""

from __future__ import annotations

import dataclasses
import importlib.machinery
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_DESCRIPTION_FIELDS = [
    "key",
    "translation_key",
    "native_unit_of_measurement",
    "device_class",
    "entity_category",
    "state_class",
    "icon",
    "entity_registry_enabled_default",
    "suggested_display_precision",
    "name",
    "options",
    "has_entity_name",
    "unit_of_measurement",
]
_STUBBED = ("homeassistant", "voluptuous", "aiohttp", "cryptography", "httpx")


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Stub


class _Stub(metaclass=_Meta):
    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls

    def __call__(self, *args, **kwargs):
        return _Stub()


def _description_class(name: str):
    namespace = {"__annotations__": {field: "object" for field in _DESCRIPTION_FIELDS}}
    namespace.update({field: None for field in _DESCRIPTION_FIELDS})
    return dataclasses.dataclass(frozen=True, kw_only=True)(type(name, (), namespace))


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name.endswith("EntityDescription"):
            value = _description_class(name)
        elif name == "callback":
            value = lambda function: function  # noqa: E731
        else:
            value = type(name, (_Stub,), {})
        setattr(self, name, value)
        return value


class _StubFinder:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in _STUBBED:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        module = _StubModule(spec.name)
        module.__path__ = []
        return module

    def exec_module(self, module):
        pass


sys.meta_path.insert(0, _StubFinder())
