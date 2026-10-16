"""Sensors are only created for data the vehicle actually reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.deepal.api import add_seat_roles
from custom_components.deepal.binary_sensor import BINARY_SENSORS, _binary_supported
from custom_components.deepal.gating import partition
from custom_components.deepal.sensor import SENSORS, _sensor_supported

FIXTURES = Path(__file__).parent / "fixtures"

# What an AU S07 (RHD, REST) never reports: these stay hidden.
S07_NEVER_REPORTED = {
    ("sensor", "speed"),
    ("sensor", "outside_temp"),
    ("sensor", "inside_pm25"),
    ("sensor", "inside_air_quality_level"),
    ("sensor", "charge_current"),
    ("sensor", "charge_plan_start_time"),
    ("sensor", "charge_plan_end_time"),
    ("sensor", "rear_left_seat_heater_level"),
    ("sensor", "rear_right_seat_heater_level"),
    ("sensor", "gear_signal"),
    ("sensor", "epb_sts"),
    ("binary", "engine_sts"),
}


def _hidden(data):
    hidden = {("sensor", d.key) for d in SENSORS if not _sensor_supported(d)(data)}
    hidden |= {("binary", d.key) for d in BINARY_SENSORS if not _binary_supported(d)(data)}
    return hidden


@pytest.fixture
def s07_data():
    fixture = json.loads((FIXTURES / "s07_au.json").read_text())
    condition = add_seat_roles(fixture["condition"], fixture["vehicle"]["driveSeatPosition"])
    return {"condition": condition, "vehicle": fixture["vehicle"], "ota": {"state": "INSTALLED"}}


def test_s07_hides_exactly_the_unreported_entities(s07_data):
    assert _hidden(s07_data) == S07_NEVER_REPORTED


def test_values_that_are_unknown_but_reported_stay_visible(s07_data):
    # Remaining charge time is the "no estimate" value (8191) in the raw data: the
    # key is present, so the entity exists and shows unknown until charging.
    hidden = _hidden(s07_data)
    assert ("sensor", "remain_charge_time") not in hidden
    assert ("sensor", "remain_charge_time_hhmm") not in hidden


def test_front_seat_entities_follow_the_drive_side_aliases(s07_data):
    hidden = _hidden(s07_data)
    assert ("sensor", "driver_seat_heater_level") not in hidden
    assert ("binary", "driver_seat_heater_on") not in hidden


def test_empty_first_report_creates_only_always_on_entities():
    # A sleeping car can return empty blocks; nothing should be created yet.
    empty = {"condition": {"vehicleStatus": {}, "hvac": {}, "charge": {}}, "ota": None, "vehicle": {}}
    visible = {d.key for d in SENSORS if _sensor_supported(d)(empty)}
    visible |= {d.key for d in BINARY_SENSORS if _binary_supported(d)(empty)}
    assert visible == {"refresh_failure_count", "img_url"}


def test_any_door_open_needs_door_data():
    # Its value is False even without door data, so the data itself is checked.
    description = next(d for d in BINARY_SENSORS if d.key == "any_door_open")
    assert not _binary_supported(description)({"condition": {}})
    assert _binary_supported(description)({"condition": {"door": {"doors": [0, 0, 0, 0]}}})


def test_ota_sensor_needs_ota_data(s07_data):
    description = next(d for d in SENSORS if d.key == "ota_status")
    assert _sensor_supported(description)(s07_data)
    assert not _sensor_supported(description)({**s07_data, "ota": None})


class _Entity:
    def __init__(self, unique_id):
        self.unique_id = unique_id


class TestPartition:
    def candidates(self):
        return [(_Entity("a"), lambda d: d.get("a")), (_Entity("b"), lambda d: d.get("b")), (_Entity("c"), lambda d: d.get("c"))]

    def ids(self, entities):
        return [getattr(item, "unique_id", None) or item[0].unique_id for item in entities]

    def test_supported_and_registered_entities_are_added(self):
        add, pending = partition(self.candidates(), existing={"c"}, seen=set(), data={"a": 1})
        assert self.ids(add) == ["a", "c"]
        assert self.ids(pending) == ["b"]

    def test_pending_entity_is_added_when_data_appears_later(self):
        _, pending = partition(self.candidates(), existing=set(), seen=set(), data={})
        add, still_pending = partition(pending, existing=set(), seen=set(), data={"b": 1})
        assert self.ids(add) == ["b"]
        assert self.ids(still_pending) == ["a", "c"]

    def test_previously_seen_entity_is_kept_when_value_is_missing(self):
        add, pending = partition(self.candidates(), existing=set(), seen={"b"}, data={})
        assert self.ids(add) == ["b"]
        assert self.ids(pending) == ["a", "c"]

    def test_nothing_new_adds_nothing(self):
        add, _ = partition([], existing=set(), seen=set(), data={})
        assert add == []
