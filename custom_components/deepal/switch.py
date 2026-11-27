"""Switch entities for Deepal vehicles."""

from __future__ import annotations

from datetime import time as dt_time
from typing import Any

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import DeepalApiError, DeepalCommandAuthError, DeepalCommandNotReady
from .coordinator import DeepalDataUpdateCoordinator
from .entity import DeepalEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DeepalDataUpdateCoordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    # Charge schedule: S07 always; S05 BEV only, with commands enabled, and
    # only once the REST overlay has given it a plan list to read (see
    # coordinator.s05_charge_schedule_supported and _async_overlay_charge_plan).
    if not coordinator.vehicle_uses_mqtt or coordinator.s05_charge_schedule_supported:
        entities.append(DeepalChargeScheduleSwitch(coordinator))
        _async_register_set_charge_window()
    # Steering wheel heating: S07 always; S05 (literal MQTT, not the E07's
    # SDA-MQTT) once commands are enabled, via a different (MQTT) command -
    # ported from danperks/ha-deepal (MIT), "limited live use" there, not
    # verified here.
    if not coordinator.vehicle_uses_mqtt or (
        coordinator.mqtt_commands_supported and coordinator.client.commands_enabled
    ):
        entities.append(DeepalSteeringWheelHeatSwitch(coordinator))
    async_add_entities(entities)


def _async_register_set_charge_window() -> None:
    """Register ``deepal.set_charge_window`` on the charge schedule switch."""
    try:
        platform = entity_platform.async_get_current_platform()
        platform.async_register_entity_service(
            "set_charge_window",
            {
                vol.Required("start_time"): cv.time,
                vol.Required("end_time"): cv.time,
            },
            "async_set_charge_window",
        )
    except (RuntimeError, AttributeError):
        # Unit tests call async_setup_entry with no entity platform active.
        # Real Home Assistant raises RuntimeError for that; this repo's test
        # stub instead returns a stub object with no matching method, which
        # surfaces as an AttributeError.
        return


def _charge_plan(condition: dict[str, Any]) -> dict[str, Any]:
    plans = ((condition.get("charge") or {}).get("chargePlanList") or [])
    return plans[0] if plans and isinstance(plans[0], dict) else {}


class DeepalChargeScheduleSwitch(DeepalEntity, SwitchEntity):
    """Enable or disable the charging schedule."""

    _attr_translation_key = "charge_schedule_control"
    _attr_name = "Charging schedule"
    # Config: the Polestar C3 fork's equivalent ("Charging schedule") is a
    # Configuration-card entity, not a plain Sensors/Controls one.
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "charge_schedule_control")

    @property
    def is_on(self) -> bool | None:
        plan = _charge_plan(self.condition)
        if not plan:
            return None
        return plan.get("startSwitch") == 1 and plan.get("endSwitch") == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_update_schedule(enabled=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_update_schedule(enabled=False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Moved here from the now-removed "Charging schedule enabled" binary
        # sensor, which duplicated this switch's own on/off state.
        plan = _charge_plan(self.condition)
        return {
            "plan_id": plan.get("planId"),
            "start_time": plan.get("startTime"),
            "end_time": plan.get("endTime"),
            "start_switch": plan.get("startSwitch"),
            "end_switch": plan.get("endSwitch"),
            "is_valid": plan.get("isValid"),
            "weeks": plan.get("weeks"),
            "time_zone": plan.get("timeZone"),
            "time_format": plan.get("timeFormat"),
            "plan_type": plan.get("planType"),
            "send_time": plan.get("sendTime"),
        }

    async def _async_update_schedule(self, *, enabled: bool) -> None:
        plan = _charge_plan(self.condition)
        if not plan:
            raise HomeAssistantError("Deepal charge schedule plan is not available")
        try:
            await self.async_execute_command(
                lambda: self.coordinator.client.control_charge_schedule(
                    vehicle_id=self.coordinator.vehicle_id,
                    plan_id=str(plan["planId"]),
                    start_time=str(plan.get("startTime") or "0000"),
                    end_time=str(plan.get("endTime") or "0000"),
                    enabled=enabled,
                    plan_type=int(plan.get("planType") or 1),
                    time_format=int(plan.get("timeFormat") or 1),
                    time_zone=str(plan.get("timeZone") or "GMT+08:00"),
                )
            )
        except KeyError as err:
            raise HomeAssistantError("Deepal charge schedule plan id is not available") from err
        except DeepalCommandAuthError as err:
            self.raise_command_reauth_required(err)
        except (DeepalApiError, DeepalCommandNotReady) as err:
            raise HomeAssistantError(f"Deepal charge schedule command failed: {err}") from err

    async def async_set_charge_window(self, start_time: dt_time, end_time: dt_time) -> None:
        """Set the schedule start and end in one command, keeping each switch's state."""
        plan = _charge_plan(self.condition)
        if not plan:
            raise HomeAssistantError("Deepal charge schedule plan is not available")
        try:
            await self.async_execute_command(
                lambda: self.coordinator.client.control_charge_schedule(
                    vehicle_id=self.coordinator.vehicle_id,
                    plan_id=str(plan["planId"]),
                    start_time=f"{start_time.hour:02d}{start_time.minute:02d}",
                    end_time=f"{end_time.hour:02d}{end_time.minute:02d}",
                    start_enabled=plan.get("startSwitch") == 1,
                    end_enabled=plan.get("endSwitch") == 1,
                    plan_type=int(plan.get("planType") or 1),
                    time_format=int(plan.get("timeFormat") or 1),
                    time_zone=str(plan.get("timeZone") or "GMT+08:00"),
                )
            )
        except KeyError as err:
            raise HomeAssistantError("Deepal charge schedule plan id is not available") from err
        except DeepalCommandAuthError as err:
            self.raise_command_reauth_required(err)
        except (DeepalApiError, DeepalCommandNotReady) as err:
            raise HomeAssistantError(f"Deepal charge schedule command failed: {err}") from err


class DeepalSteeringWheelHeatSwitch(DeepalEntity, SwitchEntity):
    """Turn the steering wheel heating on or off (request shape from danperks/ha-deepal)."""

    _attr_translation_key = "steering_wheel_heating_control"
    _attr_name = "Steering wheel heating"
    _attr_icon = "mdi:steering"

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "steering_wheel_heating_control")

    @property
    def is_on(self) -> bool | None:
        value = (self.condition.get("vehicleStatus") or {}).get("steeringWheelHeater")
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_control(open_value=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_control(open_value=False)

    async def _async_control(self, *, open_value: bool) -> None:
        client = self.coordinator.client
        control = (
            client.mqtt_control_steering_wheel_heat
            if self.coordinator.vehicle_uses_mqtt
            else client.control_steering_wheel_heat
        )
        try:
            await self.async_execute_command(
                lambda: control(
                    vehicle_id=self.coordinator.vehicle_id,
                    open_value=open_value,
                ),
                is_done=lambda: self.is_on is open_value,
            )
        except DeepalCommandAuthError as err:
            self.raise_command_reauth_required(err)
        except (DeepalApiError, DeepalCommandNotReady) as err:
            raise HomeAssistantError(f"Deepal steering wheel heating command failed: {err}") from err
