"""Every translation must have exactly the keys of en.json and no leftovers."""
import json
import re
from pathlib import Path

import pytest

TRANSLATIONS = Path(__file__).resolve().parents[1] / "custom_components" / "deepal" / "translations"
LANGUAGES = sorted(p.stem for p in TRANSLATIONS.glob("*.json") if p.stem != "en")


def load(name):
    return json.loads((TRANSLATIONS / f"{name}.json").read_text(encoding="utf-8"))


def flatten(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from flatten(value, f"{prefix}{key}.")
    else:
        yield prefix.rstrip("."), node


def test_expected_languages_present():
    assert {"es", "pt", "it", "nl"} <= set(LANGUAGES)


@pytest.mark.parametrize("language", LANGUAGES)
def test_same_keys_as_english(language):
    english = dict(flatten(load("en")))
    translated = dict(flatten(load(language)))
    assert set(translated) == set(english)


@pytest.mark.parametrize("language", LANGUAGES)
def test_placeholders_and_references_preserved(language):
    english = dict(flatten(load("en")))
    for key, text in flatten(load(language)):
        assert isinstance(text, str) and text.strip(), key
        assert "[%key" not in text, key
        assert sorted(re.findall(r"\{[^}]*\}", text)) == sorted(
            re.findall(r"\{[^}]*\}", english[key])
        ), key


def test_english_has_no_unresolved_references():
    for key, text in flatten(load("en")):
        assert "[%key" not in text, key
