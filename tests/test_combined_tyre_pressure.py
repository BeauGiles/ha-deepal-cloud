"""Combined Lowest/Low tyre pressure sensor and binary sensor.

Built-in equivalent of a min_max + threshold helper pair, available on every
vehicle that reports any tyre pressure (not just the per-wheel warning flags,
which are S05 MQTT only). The low-pressure threshold is configurable per
vehicle (Configure -> Low tyre pressure warning threshold), default 230 kPa.
"""

from __future__ import annotations

import types

from custom_components.deepal import binary_sensor, sensor
from custom_components.deepal.const import CONF_LOW_TYRE_PRESSURE_KPA, DEFAULT_LOW_TYRE_PRESSURE_KPA

_ALL_FOUR = {
    "tire": {
        "leftFront": {"pressure": 240.0},
        "rightFront": {"pressure": 245.0},
        "leftBack": {"pressure": 220.0},
        "rightBack": {"pressure": 250.0},
    }
}


# --- sensor.py: Lowest tyre pressure ----------------------------------------


def _sensor_description():
    return next(d for d in sensor.SENSORS if d.key == "tire_lowest_pressure")


class TestLowestTyrePressureSensor:
    def test_reports_the_minimum_of_the_four(self):
        description = _sensor_description()
        entity = sensor.DeepalSensor.__new__(sensor.DeepalSensor)
        entity.entity_description = description
        entity.coordinator = types.SimpleNamespace(data={"condition": _ALL_FOUR})
        assert entity.native_value == 220.0

    def test_ignores_wheels_that_did_not_report(self):
        description = _sensor_description()
        entity = sensor.DeepalSensor.__new__(sensor.DeepalSensor)
        entity.entity_description = description
        entity.coordinator = types.SimpleNamespace(
            data={"condition": {"tire": {"leftFront": {"pressure": 240.0}, "rightFront": {"pressure": 230.0}}}}
        )
        assert entity.native_value == 230.0

    def test_none_when_nothing_reported(self):
        description = _sensor_description()
        entity = sensor.DeepalSensor.__new__(sensor.DeepalSensor)
        entity.entity_description = description
        entity.coordinator = types.SimpleNamespace(data={"condition": {}})
        assert entity.native_value is None

    def test_hidden_without_any_tyre_pressure(self):
        supported = sensor._sensor_supported(_sensor_description())
        assert not supported({"condition": {}})

    def test_visible_once_any_wheel_reports_a_pressure(self):
        supported = sensor._sensor_supported(_sensor_description())
        assert supported({"condition": _ALL_FOUR})
        assert supported({"condition": {"tire": {"leftFront": {"pressure": 240.0}}}})


# --- binary_sensor.py: Low tyre pressure, with the configurable threshold --


def _binary_description():
    return next(d for d in binary_sensor.BINARY_SENSORS if d.key == "tire_low_pressure")


def _entity(condition, *, data=None, options=None):
    description = _binary_description()
    entity = binary_sensor.DeepalBinarySensor.__new__(binary_sensor.DeepalBinarySensor)
    entity.entity_description = description
    entity.coordinator = types.SimpleNamespace(
        data={"condition": condition},
        entry=types.SimpleNamespace(data=data or {}, options=options or {}),
    )
    return entity


class TestLowTyrePressureBinarySensor:
    def test_on_when_below_the_default_threshold(self):
        condition = {"tire": {"leftFront": {"pressure": DEFAULT_LOW_TYRE_PRESSURE_KPA - 1}}}
        assert _entity(condition).is_on is True

    def test_off_when_all_above_the_default_threshold(self):
        condition = {"tire": {"leftFront": {"pressure": DEFAULT_LOW_TYRE_PRESSURE_KPA + 1}}}
        assert _entity(condition).is_on is False

    def test_none_when_nothing_reported(self):
        assert _entity({}).is_on is None

    def test_uses_the_configured_threshold_from_options(self):
        condition = {"tire": {"leftFront": {"pressure": 235.0}}}
        # Below the default (230) it would be fine; a higher configured
        # threshold (240) should flag it as low instead.
        assert _entity(condition).is_on is False
        assert _entity(condition, options={CONF_LOW_TYRE_PRESSURE_KPA: 240}).is_on is True

    def test_options_threshold_overrides_data_threshold(self):
        condition = {"tire": {"leftFront": {"pressure": 235.0}}}
        entity = _entity(condition, data={CONF_LOW_TYRE_PRESSURE_KPA: 200}, options={CONF_LOW_TYRE_PRESSURE_KPA: 240})
        assert entity.is_on is True

    def test_hidden_without_any_tyre_pressure(self):
        supported = binary_sensor._binary_supported(_binary_description())
        assert not supported({"condition": {}})

    def test_visible_once_any_wheel_reports_a_pressure(self):
        supported = binary_sensor._binary_supported(_binary_description())
        assert supported({"condition": _ALL_FOUR})
