"""Button entities for Deepal vehicles."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import DeepalApiError, DeepalCommandAuthError, DeepalCommandNotReady
from .coordinator import DeepalDataUpdateCoordinator
from .entity import DeepalEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DeepalDataUpdateCoordinator = entry.runtime_data
    entities: list[ButtonEntity] = [DeepalRefreshButton(coordinator)]
    if not coordinator.vehicle_uses_mqtt:
        entities.extend([DeepalFlashLightsButton(coordinator), DeepalHonkHornButton(coordinator)])
    # MQTT vehicles only get window/boot controls once commands are enabled.
    if not coordinator.vehicle_uses_mqtt or (
        coordinator.mqtt_commands_supported and coordinator.client.commands_enabled
    ):
        entities.extend(
            [
                DeepalWindowsButton(coordinator, lower=True),
                DeepalWindowsButton(coordinator, lower=False),
                DeepalBootButton(coordinator, open_boot=True),
                DeepalBootButton(coordinator, open_boot=False),
            ]
        )
    async_add_entities(entities)


class DeepalRefreshButton(DeepalEntity, ButtonEntity):
    """Manually refresh cached Deepal cloud vehicle data."""

    _attr_translation_key = "refresh"
    _attr_name = "Refresh Vehicle Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        client = self.coordinator.client
        if client.commands_enabled and not self.coordinator.vehicle_uses_mqtt:
            try:
                await self.async_execute_command(
                    lambda: client.control_condition_inquiry(vehicle_id=self.coordinator.vehicle_id),
                    timeout=30,
                )
            except DeepalCommandAuthError as err:
                self.raise_command_reauth_required(err)
            except DeepalApiError:
                await self.coordinator.async_request_refresh()
                return
            return
        await self.coordinator.async_refresh_vehicle()


class _DeepalFlashHonkButton(DeepalEntity, ButtonEntity):
    """Base entity for captured flash/honk actions."""

    _action_type: int

    async def async_press(self) -> None:
        try:
            await self.async_execute_command(
                lambda: self.coordinator.client.control_flashing_honking(
                    vehicle_id=self.coordinator.vehicle_id,
                    action_type=self._action_type,
                )
            )
        except DeepalCommandAuthError as err:
            self.raise_command_reauth_required(err)
        except DeepalCommandNotReady as err:
            raise HomeAssistantError(str(err)) from err
        except DeepalApiError as err:
            raise HomeAssistantError(f"Deepal command failed: {err}") from err


class DeepalFlashLightsButton(_DeepalFlashHonkButton):
    """Momentary button to flash the vehicle lights."""

    _attr_translation_key = "flash_lights"
    _attr_name = "Flash Lights"
    _attr_icon = "mdi:car-parking-lights"
    _action_type = 1

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "flash_lights")


class DeepalHonkHornButton(_DeepalFlashHonkButton):
    """Momentary button to sound the horn."""

    _attr_translation_key = "honk_horn"
    _attr_name = "Honk Horn"
    _attr_icon = "mdi:bullhorn"
    _action_type = 3

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "honk_horn")


class _DeepalOpenCloseButton(DeepalEntity, ButtonEntity):
    """A one-way open or close action.

    Window and boot controls are separate, explicitly named buttons rather than a
    cover: a cover's up arrow means "open", which for windows means lowering
    them, and a mis-tap on a cover is easy. Each button does exactly what its
    name says.
    """

    _open_value: bool
    _what: str

    def _is_closed(self) -> bool | None:
        raise NotImplementedError

    def _send(self):
        """Return the coroutine factory that sends the command."""
        raise NotImplementedError

    async def async_press(self) -> None:
        open_value = self._open_value
        try:
            await self.async_execute_command(
                self._send(),
                is_done=lambda: self._is_closed() is (not open_value),
            )
        except DeepalCommandAuthError as err:
            self.raise_command_reauth_required(err)
        except DeepalCommandNotReady as err:
            raise HomeAssistantError(str(err)) from err
        except DeepalApiError as err:
            raise HomeAssistantError(f"Deepal {self._what} command failed: {err}") from err


class DeepalWindowsButton(_DeepalOpenCloseButton):
    """Lower (open) or raise (close) all windows."""

    _what = "windows"

    def __init__(self, coordinator: DeepalDataUpdateCoordinator, *, lower: bool) -> None:
        key = "windows_lower" if lower else "windows_raise"
        super().__init__(coordinator, key)
        self._open_value = lower
        self._attr_translation_key = key
        self._attr_name = "Lower Windows" if lower else "Raise Windows"
        self._attr_icon = "mdi:window-open-variant" if lower else "mdi:window-closed-variant"

    def _is_closed(self) -> bool | None:
        windows = (self.condition.get("window") or {}).get("windows")
        if not isinstance(windows, list) or not windows:
            return None
        return all(value == 0 for value in windows)

    def _send(self):
        client = self.coordinator.client
        control = client.mqtt_control_windows if self.coordinator.vehicle_uses_mqtt else client.control_windows
        return lambda: control(vehicle_id=self.coordinator.vehicle_id, open_value=self._open_value)


class DeepalBootButton(_DeepalOpenCloseButton):
    """Open or close the boot."""

    _what = "boot"

    def __init__(self, coordinator: DeepalDataUpdateCoordinator, *, open_boot: bool) -> None:
        key = "boot_open" if open_boot else "boot_close"
        super().__init__(coordinator, key)
        self._open_value = open_boot
        self._attr_translation_key = key
        self._attr_name = "Open Boot" if open_boot else "Close Boot"
        self._attr_icon = "mdi:car-back"

    def _is_closed(self) -> bool | None:
        trunk = (self.condition.get("door") or {}).get("trunk")
        return (trunk == 0) if trunk is not None else None

    def _send(self):
        client = self.coordinator.client
        control = client.mqtt_control_trunk if self.coordinator.vehicle_uses_mqtt else client.control_trunk
        return lambda: control(vehicle_id=self.coordinator.vehicle_id, open_value=self._open_value)
