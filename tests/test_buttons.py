"""Window and boot controls are explicit buttons, not covers."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.deepal import button, cover
from custom_components.deepal.api import DeepalApiError, DeepalCommandNotReady


class FakeClient:
    commands_enabled = True

    def __init__(self):
        self.calls = []

    async def control_windows(self, **kwargs):
        self.calls.append(("rest_windows", kwargs))
        return "cmd"

    async def mqtt_control_windows(self, **kwargs):
        self.calls.append(("mqtt_windows", kwargs))
        return "cmd"

    async def control_trunk(self, **kwargs):
        self.calls.append(("rest_trunk", kwargs))
        return "cmd"

    async def mqtt_control_trunk(self, **kwargs):
        self.calls.append(("mqtt_trunk", kwargs))
        return "cmd"


class FakeCoordinator:
    vehicle_id = "123"

    def __init__(self, *, mqtt=False, supported=True, condition=None):
        self.client = FakeClient()
        self.vehicle_uses_mqtt = mqtt
        self.mqtt_commands_supported = supported
        self.data = {"condition": condition or {}}


def make(cls, coordinator, **kwargs):
    entity = cls(coordinator, **kwargs)
    entity.coordinator = coordinator
    return entity


def press(entity):
    """Press the button; return (send_command, is_done) given to the command runner."""
    captured = {}

    async def fake_execute(send_command, *, is_done=None, **_):
        captured["send"] = send_command
        captured["is_done"] = is_done
        await send_command()

    entity.async_execute_command = fake_execute
    asyncio.run(entity.async_press())
    return captured


class TestNamesAndKeys:
    @pytest.mark.parametrize(
        ("cls", "kwargs", "name", "key"),
        [
            (button.DeepalWindowsButton, {"lower": True}, "Lower Windows", "windows_lower"),
            (button.DeepalWindowsButton, {"lower": False}, "Raise Windows", "windows_raise"),
            (button.DeepalBootButton, {"open_boot": True}, "Open Boot", "boot_open"),
            (button.DeepalBootButton, {"open_boot": False}, "Close Boot", "boot_close"),
        ],
    )
    def test_each_button_says_exactly_what_it_does(self, cls, kwargs, name, key):
        entity = make(cls, FakeCoordinator(), **kwargs)
        assert entity._attr_name == name
        assert entity._attr_translation_key == key
        assert entity._attr_unique_id == f"123_{key}"


class TestWindows:
    def test_lower_sends_open_and_waits_for_open_state(self):
        coordinator = FakeCoordinator(condition={"window": {"windows": [0, 0, 0, 0]}})
        captured = press(make(button.DeepalWindowsButton, coordinator, lower=True))
        assert coordinator.client.calls == [("rest_windows", {"vehicle_id": "123", "open_value": True})]
        assert captured["is_done"]() is False  # still closed
        coordinator.data["condition"]["window"]["windows"] = [30, 30, 0, 0]
        assert captured["is_done"]() is True

    def test_raise_sends_close_and_waits_for_closed_state(self):
        coordinator = FakeCoordinator(condition={"window": {"windows": [30, 0, 0, 0]}})
        captured = press(make(button.DeepalWindowsButton, coordinator, lower=False))
        assert coordinator.client.calls == [("rest_windows", {"vehicle_id": "123", "open_value": False})]
        assert captured["is_done"]() is False
        coordinator.data["condition"]["window"]["windows"] = [0, 0, 0, 0]
        assert captured["is_done"]() is True

    def test_mqtt_vehicle_uses_the_mqtt_command(self):
        coordinator = FakeCoordinator(mqtt=True, condition={"window": {"windows": [0, 0, 0, 0]}})
        press(make(button.DeepalWindowsButton, coordinator, lower=True))
        assert coordinator.client.calls[0][0] == "mqtt_windows"


class TestBoot:
    def test_open_and_close_commands(self):
        coordinator = FakeCoordinator(condition={"door": {"trunk": 0}})
        captured = press(make(button.DeepalBootButton, coordinator, open_boot=True))
        assert coordinator.client.calls == [("rest_trunk", {"vehicle_id": "123", "open_value": True})]
        assert captured["is_done"]() is False
        coordinator.data["condition"]["door"]["trunk"] = 1
        assert captured["is_done"]() is True

    def test_mqtt_vehicle_uses_the_mqtt_command(self):
        coordinator = FakeCoordinator(mqtt=True, condition={"door": {"trunk": 0}})
        press(make(button.DeepalBootButton, coordinator, open_boot=False))
        assert coordinator.client.calls[0][0] == "mqtt_trunk"

    def test_unknown_state_never_reports_done(self):
        entity = make(button.DeepalBootButton, FakeCoordinator(condition={}), open_boot=True)
        assert entity._is_closed() is None


class TestErrors:
    @pytest.mark.parametrize(
        ("error", "text"),
        [(DeepalApiError("boom"), "windows command failed: boom"), (DeepalCommandNotReady("not ready"), "not ready")],
    )
    def test_failures_become_home_assistant_errors(self, error, text):
        entity = make(button.DeepalWindowsButton, FakeCoordinator(), lower=True)

        async def failing(*_args, **_kwargs):
            raise error

        entity.async_execute_command = failing
        with pytest.raises(Exception) as raised:
            asyncio.run(entity.async_press())
        assert text in str(raised.value)


class TestSetup:
    @staticmethod
    def added(coordinator):
        entities = []
        entry = type("Entry", (), {"runtime_data": coordinator})()
        asyncio.run(button.async_setup_entry(None, entry, entities.extend))
        return {entity._attr_name for entity in entities if getattr(entity, "_attr_name", None)}

    def test_rest_vehicle_gets_window_and_boot_buttons(self):
        names = self.added(FakeCoordinator())
        assert {"Lower Windows", "Raise Windows", "Open Boot", "Close Boot"} <= names

    def test_mqtt_vehicle_without_commands_gets_none(self):
        coordinator = FakeCoordinator(mqtt=True, supported=True)
        coordinator.client.commands_enabled = False
        names = self.added(coordinator)
        assert not {"Lower Windows", "Open Boot"} & names

    def test_mqtt_vehicle_with_commands_gets_them(self):
        names = self.added(FakeCoordinator(mqtt=True, supported=True))
        assert {"Lower Windows", "Raise Windows", "Open Boot", "Close Boot"} <= names

    def test_unsupported_mqtt_variant_gets_none(self):
        # e.g. SDA-MQTT (E07): telemetry only, no remote commands.
        names = self.added(FakeCoordinator(mqtt=True, supported=False))
        assert not {"Lower Windows", "Open Boot"} & names


class TestRetiredCovers:
    def test_old_cover_entities_are_removed_from_the_registry(self, monkeypatch):
        removed = []

        class Registry:
            known = {
                ("cover", "deepal", "123_windows_cover"): "cover.garage_windows",
                ("cover", "deepal", "123_boot_cover"): "cover.garage_boot",
            }

            def async_get_entity_id(self, domain, platform, unique_id):
                return self.known.get((domain, platform, unique_id))

            def async_remove(self, entity_id):
                removed.append(entity_id)

        monkeypatch.setattr(cover, "er", type("ER", (), {"async_get": staticmethod(lambda hass: Registry())}))
        entry = type("Entry", (), {"runtime_data": FakeCoordinator()})()
        added = []
        asyncio.run(cover.async_setup_entry(None, entry, added.extend))
        assert sorted(removed) == ["cover.garage_boot", "cover.garage_windows"]
        assert added == []  # the cover platform creates nothing

    def test_missing_registry_entries_are_ignored(self, monkeypatch):
        class Registry:
            def async_get_entity_id(self, *_):
                return None

            def async_remove(self, entity_id):
                raise AssertionError("nothing to remove")

        monkeypatch.setattr(cover, "er", type("ER", (), {"async_get": staticmethod(lambda hass: Registry())}))
        entry = type("Entry", (), {"runtime_data": FakeCoordinator()})()
        asyncio.run(cover.async_setup_entry(None, entry, [].extend))
