"""The countries the integration offers at login, and the cluster each is homed on.

One table instead of the same facts repeated in several places. To add a country,
add one line here (and its name to the README and its code to ``hacs.json``; a test
fails if they disagree).
"""

from __future__ import annotations

from dataclasses import dataclass

#: The default (European) cluster, which also serves Israel.
REGION_EUROPE = "eu"
#: The Singapore cluster behind the "/appgw" gateway prefix (Australia and APAC).
REGION_APAC = "apac"


@dataclass(frozen=True)
class Country:
    """One selectable country."""

    code: str
    name: str
    dial_code: str
    region: str
    #: True once someone has logged in from this country with this integration.
    verified: bool = False

    @property
    def label(self) -> str:
        return f"{self.name} (+{self.dial_code})"


_COUNTRIES = (
    Country("GB", "United Kingdom", "44", REGION_EUROPE, verified=True),
    Country("IL", "Israel", "972", REGION_EUROPE, verified=True),
    Country("PT", "Portugal", "351", REGION_EUROPE, verified=True),
    Country("ES", "Spain", "34", REGION_EUROPE),
    Country("IT", "Italy", "39", REGION_EUROPE),
    Country("NL", "Netherlands", "31", REGION_EUROPE),
    Country("AU", "Australia", "61", REGION_APAC, verified=True),
    Country("NZ", "New Zealand", "64", REGION_APAC),
    Country("SG", "Singapore", "65", REGION_APAC),
    Country("MY", "Malaysia", "60", REGION_APAC),
    Country("TH", "Thailand", "66", REGION_APAC),
    Country("VN", "Vietnam", "84", REGION_APAC),
    Country("HK", "Hong Kong", "852", REGION_APAC),
    Country("MO", "Macau", "853", REGION_APAC),
    Country("ID", "Indonesia", "62", REGION_APAC),
    Country("PH", "Philippines", "63", REGION_APAC),
    Country("MN", "Mongolia", "976", REGION_APAC),
)

COUNTRIES: dict[str, Country] = {country.code: country for country in _COUNTRIES}
