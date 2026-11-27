"""S05 MQTT climate, seat heat/vent and steering-wheel-heat commands.

Ported from danperks/ha-deepal (MIT); "limited live use" there, not verified
on a car here. These tests cover the gating (literal MQTT only, commands
enabled) and that each entity calls the MQTT command for an S05 and the
existing REST command for an S07, not that the command shape itself is
correct against a real car.
"""

from __future__ import annotations

import asyncio

import pytest

from custom_components.deepal import climate, number, switch
from custom_components.deepal.api import DeepalClient

# --- api.py: the four new command methods call _mqtt_command correctly -----


def make_recording_client():
    client = object.__new__(DeepalClient)
    client.calls = []

    async def fake_mqtt_command(vehicle_id, *, service_code, method, params, wake_only=False):
        client.calls.append((vehicle_id, service_code, method, params))
        return "cmd"

    client._mqtt_command = fake_mqtt_command
    return client


class TestNewMqttCommandMethods:
    def test_air_conditioner_on_sends_temperature_and_run_timer(self):
        client = make_recording_client()
        asyncio.run(client.mqtt_control_air_conditioner(vehicle_id="v1", enabled=True, target_temp_c=21.5))
        vehicle_id, service_code, method, params = client.calls[0]
        assert (vehicle_id, service_code, method) == ("v1", "AC", "Cnr_DrACTemp")
        assert params["ACTempSet"] == 21.5
        assert params["SetTime"] > 0

    def test_air_conditioner_off_sends_no_parameters(self):
        client = make_recording_client()
        asyncio.run(client.mqtt_control_air_conditioner(vehicle_id="v1", enabled=False, target_temp_c=21.5))
        assert client.calls[0] == ("v1", "AC", "Cnr_AllAcOff", {})

    @pytest.mark.parametrize(("driver", "expected_method"), [(True, "Cnr_DrSeatHeat"), (False, "Cnr_PsgSeatHeat")])
    def test_seat_heat_picks_driver_or_passenger_method(self, driver, expected_method):
        client = make_recording_client()
        asyncio.run(client.mqtt_control_seat_heat(vehicle_id="v1", driver=driver, level=2))
        vehicle_id, service_code, method, params = client.calls[0]
        assert (service_code, method) == ("Seat", expected_method)
        assert params["SeatHeat"] == 2

    @pytest.mark.parametrize(("driver", "expected_method"), [(True, "Cnr_DrSeatVent"), (False, "Cnr_PsgSeatVent")])
    def test_seat_vent_picks_driver_or_passenger_method(self, driver, expected_method):
        client = make_recording_client()
        asyncio.run(client.mqtt_control_seat_vent(vehicle_id="v1", driver=driver, level=1))
        vehicle_id, service_code, method, params = client.calls[0]
        assert (service_code, method) == ("Seat", expected_method)
        assert params["SeatVent"] == 1

    def test_steering_wheel_heat_on_and_off_use_different_values(self):
        client = make_recording_client()
        asyncio.run(client.mqtt_control_steering_wheel_heat(vehicle_id="v1", open_value=True))
        asyncio.run(client.mqtt_control_steering_wheel_heat(vehicle_id="v1", open_value=False))
        on_params = client.calls[0][3]
        off_params = client.calls[1][3]
        assert on_params["SteeringHeat"] != off_params["SteeringHeat"]


# --- shared fakes for the entity-level tests --------------------------------


class _FakeClient:
    def __init__(self, *, commands_enabled=True):
        self.commands_enabled = commands_enabled
        self.calls = []

    async def control_air_conditioner(self, **kwargs):
        self.calls.append(("rest_ac", kwargs))
        return "cmd"

    async def mqtt_control_air_conditioner(self, **kwargs):
        self.calls.append(("mqtt_ac", kwargs))
        return "cmd"

    async def control_seats_heat(self, **kwargs):
        self.calls.append(("rest_seat_heat", kwargs))
        return "cmd"

    async def mqtt_control_seat_heat(self, **kwargs):
        self.calls.append(("mqtt_seat_heat", kwargs))
        return "cmd"

    async def control_seats_wind(self, **kwargs):
        self.calls.append(("rest_seat_vent", kwargs))
        return "cmd"

    async def mqtt_control_seat_vent(self, **kwargs):
        self.calls.append(("mqtt_seat_vent", kwargs))
        return "cmd"

    async def control_steering_wheel_heat(self, **kwargs):
        self.calls.append(("rest_steering", kwargs))
        return "cmd"

    async def mqtt_control_steering_wheel_heat(self, **kwargs):
        self.calls.append(("mqtt_steering", kwargs))
        return "cmd"


class _FakeCoordinator:
    vehicle_id = "123"

    def __init__(self, *, mqtt=False, mqtt_commands_supported=False, commands_enabled=True, condition=None):
        self.vehicle_uses_mqtt = mqtt
        self.mqtt_commands_supported = mqtt_commands_supported
        self.client = _FakeClient(commands_enabled=commands_enabled)
        self.data = {"condition": condition or {}}


# --- climate.py --------------------------------------------------------


class TestClimateMqttRouting:
    def _entity(self, coordinator):
        entity = climate.DeepalClimate(coordinator)
        entity.coordinator = coordinator
        return entity

    @pytest.mark.parametrize(
        ("mqtt", "supported", "enabled", "expected"),
        [
            (False, False, True, True),  # S07: always supported
            (True, True, True, True),  # S05, commands supported+enabled
            (True, True, False, False),  # S05, supported but not enabled
            (True, False, True, False),  # S05, not a literal-MQTT-commands vehicle (e.g. E07)
        ],
    )
    def test_mqtt_commands_supported_property(self, mqtt, supported, enabled, expected):
        coordinator = _FakeCoordinator(mqtt=mqtt, mqtt_commands_supported=supported, commands_enabled=enabled)
        entity = self._entity(coordinator)
        assert entity._mqtt_commands_supported is expected

    def test_supported_features_disabled_only_for_unsupported_mqtt(self, monkeypatch):
        # The stubbed homeassistant.components.climate makes every
        # ClimateEntityFeature(...)/.TARGET_TEMPERATURE access a fresh,
        # non-comparable fake object, so swap in real, comparable values to
        # test supported_features' own branching rather than the stub.
        class _FakeFeature:
            TARGET_TEMPERATURE = "target_temperature"

            def __new__(cls, value):
                return "none" if value == 0 else value

        monkeypatch.setattr(climate, "ClimateEntityFeature", _FakeFeature)

        unsupported = self._entity(_FakeCoordinator(mqtt=True, mqtt_commands_supported=False))
        assert unsupported.supported_features == "none"

        supported = self._entity(_FakeCoordinator(mqtt=True, mqtt_commands_supported=True, commands_enabled=True))
        assert supported.supported_features == "target_temperature"

    def test_raise_if_read_only_only_blocks_unsupported_mqtt(self):
        unsupported = self._entity(_FakeCoordinator(mqtt=True, mqtt_commands_supported=False))
        with pytest.raises(climate.HomeAssistantError):
            unsupported._raise_if_read_only()

        supported = self._entity(_FakeCoordinator(mqtt=True, mqtt_commands_supported=True, commands_enabled=True))
        supported._raise_if_read_only()  # must not raise

        s07 = self._entity(_FakeCoordinator(mqtt=False))
        s07._raise_if_read_only()  # must not raise

    def test_async_send_routes_to_mqtt_command_for_an_s05(self):
        coordinator = _FakeCoordinator(mqtt=True, mqtt_commands_supported=True, commands_enabled=True)
        entity = self._entity(coordinator)
        entity.async_execute_command = lambda send_command: send_command()
        asyncio.run(entity._async_send(enabled=True, target_temperature=22.0))
        assert coordinator.client.calls[0][0] == "mqtt_ac"

    def test_async_send_routes_to_rest_command_for_an_s07(self):
        coordinator = _FakeCoordinator(mqtt=False)
        entity = self._entity(coordinator)
        entity.async_execute_command = lambda send_command: send_command()
        asyncio.run(entity._async_send(enabled=True, target_temperature=22.0))
        assert coordinator.client.calls[0][0] == "rest_ac"


# --- number.py: seat level ---------------------------------------------


class TestSeatLevelNumberMqttRouting:
    def _entity(self, coordinator, *, driver=True, function="heat"):
        entity = number.DeepalSeatLevelNumber(coordinator, driver=driver, function=function)
        entity.coordinator = coordinator
        return entity

    @pytest.mark.parametrize("function", ["heat", "vent"])
    def test_routes_to_mqtt_for_an_s05(self, function):
        coordinator = _FakeCoordinator(mqtt=True, mqtt_commands_supported=True, commands_enabled=True)
        entity = self._entity(coordinator, function=function)
        entity.async_execute_command = lambda send_command, **_: send_command()
        asyncio.run(entity.async_set_native_value(2))
        assert coordinator.client.calls[0][0] == f"mqtt_seat_{function}"

    @pytest.mark.parametrize("function", ["heat", "vent"])
    def test_routes_to_rest_for_an_s07(self, function):
        coordinator = _FakeCoordinator(mqtt=False)
        entity = self._entity(coordinator, function=function)
        entity.async_execute_command = lambda send_command, **_: send_command()
        asyncio.run(entity.async_set_native_value(2))
        assert coordinator.client.calls[0][0] == f"rest_seat_{function}"


class TestNumberSetupGating:
    @staticmethod
    def _added(coordinator):
        entities = []
        entry = type("Entry", (), {"runtime_data": coordinator})()
        asyncio.run(number.async_setup_entry(None, entry, entities.extend))
        return {entity._attr_name for entity in entities if getattr(entity, "_attr_name", None)}

    def test_s07_gets_charge_limit_and_seat_levels(self):
        names = self._added(_FakeCoordinator(mqtt=False))
        assert "Charge Limit" in names
        assert "Driver Seat Heating" in names

    def test_s05_with_commands_gets_seat_levels_but_not_charge_limit(self):
        names = self._added(_FakeCoordinator(mqtt=True, mqtt_commands_supported=True, commands_enabled=True))
        assert "Charge Limit" not in names
        assert "Driver Seat Heating" in names
        assert "Front Passenger Seat Ventilation" in names

    def test_s05_without_commands_gets_neither(self):
        names = self._added(_FakeCoordinator(mqtt=True, mqtt_commands_supported=False))
        assert names == set()


# --- switch.py: steering wheel heat control routing --------------------


class TestSteeringWheelHeatMqttRouting:
    def _entity(self, coordinator):
        entity = switch.DeepalSteeringWheelHeatSwitch(coordinator)
        entity.coordinator = coordinator
        return entity

    def test_routes_to_mqtt_for_an_s05(self):
        coordinator = _FakeCoordinator(mqtt=True, mqtt_commands_supported=True, commands_enabled=True)
        entity = self._entity(coordinator)
        entity.async_execute_command = lambda send_command, **_: send_command()
        asyncio.run(entity._async_control(open_value=True))
        assert coordinator.client.calls[0][0] == "mqtt_steering"

    def test_routes_to_rest_for_an_s07(self):
        coordinator = _FakeCoordinator(mqtt=False)
        entity = self._entity(coordinator)
        entity.async_execute_command = lambda send_command, **_: send_command()
        asyncio.run(entity._async_control(open_value=True))
        assert coordinator.client.calls[0][0] == "rest_steering"
