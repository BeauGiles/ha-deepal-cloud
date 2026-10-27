"""The country table is the single source: hacs.json and the README must agree with it."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from custom_components.deepal.const import DEFAULT_COUNTRY, REGION_GATEWAYS
from custom_components.deepal.countries import COUNTRIES, REGION_APAC, REGION_EUROPE

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_table_is_well_formed():
    assert DEFAULT_COUNTRY in COUNTRIES
    for code, country in COUNTRIES.items():
        assert code == country.code and re.fullmatch(r"[A-Z]{2}", code)
        assert country.dial_code.isdigit()
        assert country.region in {REGION_EUROPE, REGION_APAC}
        assert country.label == f"{country.name} (+{country.dial_code})"


def test_only_apac_countries_get_the_regional_gateway():
    assert set(REGION_GATEWAYS) == {c for c, v in COUNTRIES.items() if v.region == REGION_APAC}


def test_hacs_json_lists_exactly_these_countries():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert set(hacs["country"]) == set(COUNTRIES)


@pytest.mark.parametrize("country", list(COUNTRIES.values()), ids=list(COUNTRIES))
def test_readme_mentions_every_country(country):
    assert country.name in README


def test_readme_confirmed_list_matches_the_verified_flags():
    line = next(text for text in README.splitlines() if text.startswith("* **Confirmed working:**"))
    for country in COUNTRIES.values():
        assert (country.name in line) == country.verified, country.name
