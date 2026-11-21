"""The per-wheel tyre-pressure-warning binary sensors (S05 MQTT only)."""

from __future__ import annotations

import pytest

from custom_components.deepal.binary_sensor import BINARY_SENSORS, _binary_supported

KEYS_BY_WHEEL = {
    "leftFront": "tire_front_left_warning",
    "rightFront": "tire_front_right_warning",
    "leftBack": "tire_rear_left_warning",
    "rightBack": "tire_rear_right_warning",
}


def _description(key):
    return next(d for d in BINARY_SENSORS if d.key == key)


@pytest.mark.parametrize(("wheel", "key"), KEYS_BY_WHEEL.items())
class TestValues:
    def test_on_when_warning_flag_is_set(self, wheel, key):
        description = _description(key)
        condition = {"tire": {wheel: {"warning": 1}}}
        assert description.value_fn(condition) is True

    def test_off_when_warning_flag_is_clear(self, wheel, key):
        description = _description(key)
        condition = {"tire": {wheel: {"warning": 0}}}
        assert description.value_fn(condition) is False

    def test_unknown_when_not_reported(self, wheel, key):
        description = _description(key)
        assert _description(key).value_fn({"tire": {}}) is None
        assert description.value_fn({}) is None


@pytest.mark.parametrize("key", KEYS_BY_WHEEL.values())
def test_hidden_without_warning_data_present_for_that_wheel(key):
    # An S07/E07 condition has pressure but no "warning" field at all, so the
    # entity must not be created for those cars.
    description = _description(key)
    s07_like = {"condition": {"tire": {"leftFront": {"status": 0, "pressure": 264.0}}}}
    assert not _binary_supported(description)(s07_like)


@pytest.mark.parametrize(("wheel", "key"), KEYS_BY_WHEEL.items())
def test_visible_once_the_car_reports_the_flag(wheel, key):
    description = _description(key)
    s05_like = {"condition": {"tire": {wheel: {"pressure": 230.0, "warning": 0}}}}
    assert _binary_supported(description)(s05_like)
