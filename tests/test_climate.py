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
