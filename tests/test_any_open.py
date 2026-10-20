"""Any Door / Any Window: unknown values are unknown, not "open"."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.deepal.api import _mqtt_condition_from_params, _sda_condition_from_params
from custom_components.deepal.binary_sensor import BINARY_SENSORS, _any_open, _binary_supported

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "s07_au.json").read_text())


def description(key):
    return next(d for d in BINARY_SENSORS if d.key == key)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([0, 0, 0, 0], False),
        ([0, 30, 0, 0], True),
        ([1, 0, 0, 0], True),
        ([None, None, None, None], None),
        ([], None),
        ([None, 0, 0, 0], False),  # unknown entries are ignored
        ([None, 12, 0, 0], True),
    ],
)
def test_any_open(values, expected):
    assert _any_open(values) is expected


class TestAnyWindow:
    sensor = description("any_window_open")

    def test_closed(self):
        assert self.sensor.value_fn({"window": {"windows": [0, 0, 0, 0]}}) is False

    def test_one_window_open(self):
        assert self.sensor.value_fn({"window": {"windows": [0, 0, 25, 0]}}) is True

    def test_no_window_data_is_unknown(self):
        assert self.sensor.value_fn({}) is None
        assert self.sensor.value_fn({"window": {}}) is None

    def test_metadata(self):
        assert self.sensor.key == "any_window_open"
        assert self.sensor.translation_key == "any_window_open"

    def test_s07_fixture_reports_all_closed(self):
        assert self.sensor.value_fn(FIXTURE["condition"]) is False

    def test_created_only_when_windows_are_reported(self):
        supported = _binary_supported(self.sensor)
        assert supported({"condition": FIXTURE["condition"]})
        assert not supported({"condition": {"window": {}}})
        assert not supported({"condition": {}})


class TestAnyDoor:
    sensor = description("any_door_open")

    def test_open_and_closed(self):
        assert self.sensor.value_fn({"door": {"doors": [0, 0, 0, 0]}}) is False
        assert self.sensor.value_fn({"door": {"doors": [0, 1, 0, 0]}}) is True

    def test_missing_door_values_are_not_reported_as_open(self):
        # Before: None != 0 counted as open, so an S05 with unreported doors showed "open".
        assert self.sensor.value_fn({"door": {"doors": [None, None, None, None]}}) is None


class TestFromRealMappers:
    """The mappers leave unreported signals as None; those must not read as open."""

    def test_s05_without_any_window_or_door_signals(self):
        condition = _mqtt_condition_from_params({"soc": 50})
        assert description("any_window_open").value_fn(condition) is None
        assert description("any_door_open").value_fn(condition) is None

    def test_s05_with_one_window_open(self):
        condition = _mqtt_condition_from_params({"diverWindow": 0, "passengerWindow": 40}, "LHD")
        assert description("any_window_open").value_fn(condition) is True

    def test_e07_with_all_windows_closed(self):
        condition = _sda_condition_from_params(
            {"DrvrWinPos": 0, "PassWinPos": 0, "LeReWinPos": 0, "RiReWinPos": 0, "DrvrDoorSts": 2}
        )
        assert description("any_window_open").value_fn(condition) is False
        assert description("any_door_open").value_fn(condition) is False

    def test_e07_with_a_rear_window_open(self):
        condition = _sda_condition_from_params({"DrvrWinPos": 0, "PassWinPos": 0, "LeReWinPos": 15, "RiReWinPos": 0})
        assert description("any_window_open").value_fn(condition) is True
