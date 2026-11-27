"""The deepal.set_charge_window service, and the api.py change it needed.

Ported from danperks/ha-deepal (MIT). Sets the schedule's start and end times
in one command without disturbing the existing start/end switch state, which
the plain on/off switch always sets together.
"""

from __future__ import annotations

import asyncio
from datetime import time as dt_time

import pytest

from custom_components.deepal import switch
from custom_components.deepal.api import DeepalApiError, DeepalClient

# --- api.py: control_charge_schedule's independent start/end switches ------


def make_recording_client():
    client = object.__new__(DeepalClient)
    client.calls = []

    async def fake_signed_command(*, path, vehicle_id, payload, **kwargs):
        client.calls.append(payload)
        return "cmd"

    client._signed_command = fake_signed_command
    return client


class TestControlChargeScheduleSwitches:
    def test_enabled_sets_both_switches(self):
        client = make_recording_client()
        asyncio.run(
            client.control_charge_schedule(
                vehicle_id="v1", plan_id="1", start_time="0030", end_time="0700", enabled=True
            )
        )
        payload = client.calls[0]
        assert payload["startSwitch"] == 1
        assert payload["endSwitch"] == 1

    def test_disabled_clears_both_switches(self):
        client = make_recording_client()
        asyncio.run(
            client.control_charge_schedule(
                vehicle_id="v1", plan_id="1", start_time="0030", end_time="0700", enabled=False
            )
        )
        payload = client.calls[0]
        assert payload["startSwitch"] == 0
        assert payload["endSwitch"] == 0

    def test_explicit_start_and_end_enabled_override_the_default(self):
        client = make_recording_client()
        asyncio.run(
            client.control_charge_schedule(
                vehicle_id="v1",
                plan_id="1",
                start_time="0030",
                end_time="0700",
                start_enabled=True,
                end_enabled=False,
            )
        )
        payload = client.calls[0]
        assert payload["startSwitch"] == 1
        assert payload["endSwitch"] == 0

    def test_neither_enabled_nor_switches_given_clears_both(self):
        # Matches the pre-existing default: nothing requested means off.
        client = make_recording_client()
        asyncio.run(client.control_charge_schedule(vehicle_id="v1", plan_id="1", start_time="0030", end_time="0700"))
        payload = client.calls[0]
        assert payload["startSwitch"] == 0
        assert payload["endSwitch"] == 0


# --- switch.py: DeepalChargeScheduleSwitch.async_set_charge_window ---------


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def control_charge_schedule(self, **kwargs):
        self.calls.append(kwargs)
        return "cmd"


class _FakeCoordinator:
    vehicle_id = "123"

    def __init__(self, *, plan=None):
        self.client = _FakeClient()
        self.data = {"condition": {"charge": {"chargePlanList": [plan] if plan else []}}}


def _entity(coordinator):
    entity = switch.DeepalChargeScheduleSwitch(coordinator)
    entity.coordinator = coordinator
    entity.async_execute_command = lambda send_command, **_: send_command()
    return entity


class TestSetChargeWindow:
    def test_sets_the_new_times_and_keeps_each_switch(self):
        plan = {"planId": "7", "startSwitch": 1, "endSwitch": 0, "planType": 2, "timeFormat": 1, "timeZone": "GMT+01:00"}
        coordinator = _FakeCoordinator(plan=plan)
        entity = _entity(coordinator)
        asyncio.run(entity.async_set_charge_window(dt_time(0, 30), dt_time(7, 0)))
        kwargs = coordinator.client.calls[0]
        assert kwargs["plan_id"] == "7"
        assert kwargs["start_time"] == "0030"
        assert kwargs["end_time"] == "0700"
        assert kwargs["start_enabled"] is True
        assert kwargs["end_enabled"] is False
        assert kwargs["plan_type"] == 2
        assert kwargs["time_zone"] == "GMT+01:00"

    def test_raises_when_there_is_no_plan(self):
        coordinator = _FakeCoordinator(plan=None)
        entity = _entity(coordinator)
        with pytest.raises(switch.HomeAssistantError):
            asyncio.run(entity.async_set_charge_window(dt_time(0, 30), dt_time(7, 0)))

    def test_raises_when_the_plan_has_no_id(self):
        coordinator = _FakeCoordinator(plan={"startSwitch": 1, "endSwitch": 1})
        entity = _entity(coordinator)
        with pytest.raises(switch.HomeAssistantError):
            asyncio.run(entity.async_set_charge_window(dt_time(0, 30), dt_time(7, 0)))

    def test_api_error_raises_a_clear_message(self):
        plan = {"planId": "7", "startSwitch": 1, "endSwitch": 1}
        coordinator = _FakeCoordinator(plan=plan)
        entity = _entity(coordinator)

        async def failing(**kwargs):
            raise DeepalApiError("boom")

        coordinator.client.control_charge_schedule = failing
        with pytest.raises(switch.HomeAssistantError):
            asyncio.run(entity.async_set_charge_window(dt_time(0, 30), dt_time(7, 0)))


# --- switch.py: registering the service only when a platform is active ----


class TestRegisterSetChargeWindow:
    def test_no_active_platform_does_not_raise(self):
        # Mirrors what async_setup_entry does during tests (and, per Home
        # Assistant's own contract, outside an active entity platform):
        # nothing to register against, so this is a no-op either way.
        switch._async_register_set_charge_window()
