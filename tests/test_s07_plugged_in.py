"""Real S07 (AU) capture: plugged in at 77%, 90% limit, no charge estimate."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.deepal.sensor import (
    SENSORS,
    _format_hours_minutes,
    _path_value,
    _temp_value,
)

CONDITION = json.loads((Path(__file__).parent / "fixtures" / "s07_au_plugged_in.json").read_text())["condition"]
BY_KEY = {description.key: description for description in SENSORS}


def test_no_estimate_is_unknown_not_8191_minutes():
    assert _path_value(CONDITION, BY_KEY["remain_charge_time"].path) == 8191.0
    assert _format_hours_minutes(8191.0) is None


def test_tyre_pressures_are_read_in_kpa():
    values = {
        key: _path_value(CONDITION, BY_KEY[key].path)
        for key in (
            "tire_front_left_pressure",
            "tire_front_right_pressure",
            "tire_rear_left_pressure",
            "tire_rear_right_pressure",
        )
    }
    assert values == {
        "tire_front_left_pressure": 262.0,
        "tire_front_right_pressure": 269.0,
        "tire_rear_left_pressure": 266.0,
        "tire_rear_right_pressure": 269.0,
    }


def test_cabin_climate():
    assert _temp_value(CONDITION, BY_KEY["inside_temp"].path) == 23.0
    assert _path_value(CONDITION, BY_KEY["inside_humidity"].path) == 43.0


def test_charge_limit_and_level():
    assert _path_value(CONDITION, BY_KEY["max_soc_percent"].path) == 90
