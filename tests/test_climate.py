"""The gateway rejects air-conditioning targets outside 18-32 C."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.deepal import climate
from custom_components.deepal.api import DeepalClient, clamp_ac_temperature
from custom_components.deepal.const import AC_MAX_TEMP_C, AC_MIN_TEMP_C


def test_range_matches_the_gateway():
    assert (AC_MIN_TEMP_C, AC_MAX_TEMP_C) == (18.0, 32.0)


def test_thermostat_uses_the_same_range():
    assert climate.DeepalClimate._attr_min_temp == AC_MIN_TEMP_C
    assert climate.DeepalClimate._attr_max_temp == AC_MAX_TEMP_C


@pytest.mark.parametrize(
    ("requested", "sent"),
    [(21.0, 21.0), (18.0, 18.0), (32.0, 32.0), (16.0, 18.0), (0.0, 18.0), (35.0, 32.0), (30.5, 30.5)],
)
def test_clamp(requested, sent):
    assert clamp_ac_temperature(requested) == sent


@pytest.mark.parametrize(("requested", "payload_value"), [(21.0, 210), (16.0, 180), (35.0, 320), (24.5, 245)])
def test_command_sends_a_clamped_target_in_tenths(requested, payload_value):
    client = object.__new__(DeepalClient)
    sent = {}

    async def fake_signed_command(**kwargs):
        sent.update(kwargs)
        return "cmd"

    client._signed_command = fake_signed_command
    asyncio.run(client.control_air_conditioner(vehicle_id="1", enabled=True, target_temp_c=requested))
    assert sent["payload"]["targetTemp"] == payload_value


class _FakeCar:
    """Stands in for DeepalClimate: just the two helpers the mixins read."""

    def _current_temperature_c(self):
        return 19.5

    def _target_temperature_c(self):
        return 22.0


class TestTemperatureProperties:
    """Home Assistant 2026.11 wants native_*; older versions only know the plain names."""

    def test_native_variant_uses_native_names_only(self):
        car = type("Car", (climate._NativeTemperatures, _FakeCar), {})()
        assert car.native_temperature_unit == climate.UnitOfTemperature.CELSIUS
        assert car.native_current_temperature == 19.5
        assert car.native_target_temperature == 22.0
        for plain in ("temperature_unit", "current_temperature", "target_temperature"):
            assert not hasattr(climate._NativeTemperatures, plain)

    def test_legacy_variant_uses_plain_names_only(self):
        car = type("Car", (climate._LegacyTemperatures, _FakeCar), {})()
        assert car.temperature_unit == climate.UnitOfTemperature.CELSIUS
        assert car.current_temperature == 19.5
        assert car.target_temperature == 22.0
        for native in ("native_temperature_unit", "native_current_temperature", "native_target_temperature"):
            assert not hasattr(climate._LegacyTemperatures, native)

    def test_entity_uses_one_of_the_two_sets(self):
        assert issubclass(climate.DeepalClimate, (climate._NativeTemperatures, climate._LegacyTemperatures))
