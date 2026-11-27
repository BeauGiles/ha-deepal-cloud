"""S05 BEV charge-schedule: the REST overlay and the gated switch/time entities.

The PHEV is deliberately excluded for now - its plan behaves differently
(Sunek0/ha-deepal-alternative's reverse engineering), which this does not
implement.
"""

from __future__ import annotations

import asyncio
import types

from custom_components.deepal import switch
from custom_components.deepal import time as time_module
from custom_components.deepal.api import DeepalApiError
from custom_components.deepal.coordinator import DeepalDataUpdateCoordinator

# --- coordinator.s05_charge_schedule_supported -----------------------------


class TestS05ChargeScheduleSupported:
    def _coordinator(self, monkeypatch, *, mqtt_supported, commands_enabled, model_code):
        coordinator = object.__new__(DeepalDataUpdateCoordinator)
        coordinator.client = type(
            "Client", (), {"commands_enabled": commands_enabled, "last_mqtt_model_code": model_code}
        )()
        monkeypatch.setattr(
            type(coordinator), "mqtt_commands_supported", property(lambda self: mqtt_supported), raising=False
        )
        return coordinator

    def test_false_when_commands_not_supported(self, monkeypatch):
        coordinator = self._coordinator(monkeypatch, mqtt_supported=False, commands_enabled=True, model_code=None)
        assert coordinator.s05_charge_schedule_supported is False

    def test_false_when_commands_not_enabled(self, monkeypatch):
        coordinator = self._coordinator(monkeypatch, mqtt_supported=True, commands_enabled=False, model_code=None)
        assert coordinator.s05_charge_schedule_supported is False

    def test_true_for_a_bev_model_code(self, monkeypatch):
        coordinator = self._coordinator(
            monkeypatch, mqtt_supported=True, commands_enabled=True, model_code="SC6464AAKBEV"
        )
        assert coordinator.s05_charge_schedule_supported is True

    def test_false_for_a_phev_model_code(self, monkeypatch):
        coordinator = self._coordinator(
            monkeypatch, mqtt_supported=True, commands_enabled=True, model_code="SC6460AAAA7HEV"
        )
        assert coordinator.s05_charge_schedule_supported is False

    def test_true_when_the_model_code_is_not_known_yet(self, monkeypatch):
        coordinator = self._coordinator(monkeypatch, mqtt_supported=True, commands_enabled=True, model_code=None)
        assert coordinator.s05_charge_schedule_supported is True


# --- coordinator._async_overlay_charge_plan --------------------------------


class _FakeClient:
    def __init__(self, *, plans=None, error=None):
        self._plans = plans
        self._error = error
        self.condition_calls = 0

    async def condition(self, vehicle_id):
        self.condition_calls += 1
        if self._error is not None:
            raise self._error
        return {"charge": {"chargePlanList": self._plans}}


def overlay(client, condition):
    coordinator = object.__new__(DeepalDataUpdateCoordinator)
    coordinator.client = client
    coordinator.vehicle_id = "1"
    asyncio.run(coordinator._async_overlay_charge_plan(condition))
    return condition


class TestOverlayChargePlan:
    def test_merges_the_rest_plan_list_into_mqtt_telemetry(self):
        client = _FakeClient(plans=[{"planId": "1", "startTime": "0000", "endTime": "0600"}])
        condition = {"charge": {"chargeStatus": 6}}  # MQTT's own fresher field
        result = overlay(client, condition)
        assert result["charge"]["chargePlanList"] == [{"planId": "1", "startTime": "0000", "endTime": "0600"}]
        assert result["charge"]["chargeStatus"] == 6  # not clobbered

    def test_creates_the_charge_dict_if_missing(self):
        client = _FakeClient(plans=[])
        condition = {}
        result = overlay(client, condition)
        assert result["charge"]["chargePlanList"] == []

    def test_a_failed_overlay_fetch_leaves_the_condition_unchanged(self):
        client = _FakeClient(error=DeepalApiError("boom"))
        condition = {"charge": {"chargeStatus": 6}}
        result = overlay(client, condition)
        assert result == {"charge": {"chargeStatus": 6}}
        assert client.condition_calls == 1

    def test_a_none_plan_list_does_not_overwrite_an_existing_one(self):
        # The REST condition's own shape always has the key, but guard against
        # a surprising None rather than silently hiding an existing plan.
        client = _FakeClient(plans=None)
        condition = {"charge": {"chargePlanList": [{"planId": "1"}]}}
        result = overlay(client, condition)
        assert result["charge"]["chargePlanList"] == [{"planId": "1"}]


# --- switch.py / time.py gating --------------------------------------------


class _SwitchFakeCoordinator:
    vehicle_id = "123"

    def __init__(
        self,
        *,
        mqtt=False,
        charge_schedule_supported=False,
        mqtt_commands_supported=False,
        commands_enabled=False,
    ):
        self.vehicle_uses_mqtt = mqtt
        self.s05_charge_schedule_supported = charge_schedule_supported
        self.mqtt_commands_supported = mqtt_commands_supported
        self.client = types.SimpleNamespace(commands_enabled=commands_enabled)
        self.data = {"condition": {}}


def _added(module, coordinator):
    entities = []
    entry = type("Entry", (), {"runtime_data": coordinator})()
    asyncio.run(module.async_setup_entry(None, entry, entities.extend))
    return {entity._attr_name for entity in entities if getattr(entity, "_attr_name", None)}


class TestSwitchSetup:
    def test_s07_gets_both_switches(self):
        names = _added(switch, _SwitchFakeCoordinator(mqtt=False))
        assert {"Charging schedule", "Steering wheel heating"} <= names

    def test_s05_bev_with_commands_gets_both_switches(self):
        # Steering wheel heat only needs commands enabled (any S05); charge
        # schedule additionally needs s05_charge_schedule_supported (BEV only).
        names = _added(
            switch,
            _SwitchFakeCoordinator(
                mqtt=True, charge_schedule_supported=True, mqtt_commands_supported=True, commands_enabled=True
            ),
        )
        assert {"Charging schedule", "Steering wheel heating"} <= names

    def test_s05_phev_with_commands_gets_steering_but_not_charge_schedule(self):
        names = _added(
            switch,
            _SwitchFakeCoordinator(
                mqtt=True, charge_schedule_supported=False, mqtt_commands_supported=True, commands_enabled=True
            ),
        )
        assert "Steering wheel heating" in names
        assert "Charging schedule" not in names

    def test_s05_without_support_gets_neither(self):
        names = _added(switch, _SwitchFakeCoordinator(mqtt=True, charge_schedule_supported=False))
        assert not {"Charging schedule", "Steering wheel heating"} & names


class TestTimeSetup:
    def test_s07_gets_the_time_entities(self):
        names = _added(time_module, _SwitchFakeCoordinator(mqtt=False))
        assert {"Charging schedule start", "Charging schedule end"} <= names

    def test_s05_bev_with_commands_gets_the_time_entities(self):
        names = _added(time_module, _SwitchFakeCoordinator(mqtt=True, charge_schedule_supported=True))
        assert {"Charging schedule start", "Charging schedule end"} <= names

    def test_s05_without_support_gets_none(self):
        names = _added(time_module, _SwitchFakeCoordinator(mqtt=True, charge_schedule_supported=False))
        assert not {"Charging schedule start", "Charging schedule end"} & names
