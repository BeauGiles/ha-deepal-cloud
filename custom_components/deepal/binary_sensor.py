"""Binary sensors for Deepal vehicles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import DeepalDataUpdateCoordinator
from .entity import DeepalEntity


def _path_value(data: dict[str, Any], path: tuple[str | int, ...]) -> Any:
    value: Any = data
    for key in path:
        if isinstance(key, int):
            if not isinstance(value, list) or len(value) <= key:
                return None
            value = value[key]
            continue
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _door(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("door") or {}


def _charge(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("charge") or {}


def _charge_gun_connected(data: dict[str, Any]) -> bool | None:
    # chargeConStatus == 3 is the confirmed "connected" value (reverse-engineered
    # against a Deepal S07 AU-market account). Dylan's original (charge_connection
    # not in (0, 1)) over-fires on other status codes that aren't actually connected.
    charge_connection = _charge(data).get("chargeConStatus")
    if charge_connection is None:
        return None
    return charge_connection == 3


def _charge_schedule(data: dict[str, Any]) -> dict[str, Any]:
    plans = _path_value(data, ("charge", "chargePlanList"))
    if not isinstance(plans, list) or not plans:
        return {}
    first_plan = plans[0]
    return first_plan if isinstance(first_plan, dict) else {}


def _charge_schedule_enabled(data: dict[str, Any]) -> bool | None:
    plan = _charge_schedule(data)
    if not plan:
        return None
    # Matches switch.py's DeepalChargeScheduleSwitch.is_on exactly - both start and
    # end switches must be == 1. The previous OR-based check (truthy on either
    # switch) disagreed with the actual switch entity's own on/off state.
    return plan.get("startSwitch") == 1 and plan.get("endSwitch") == 1


@dataclass(frozen=True, kw_only=True)
class DeepalBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_NAMES = {
    "any_door_open": "Any Door",
    "front_left_door_open": "Front Left Door",
    "front_right_door_open": "Front Right Door",
    "rear_left_door_open": "Rear Left Door",
    "rear_right_door_open": "Rear Right Door",
    "trunk": "Boot",
    "driver_lock": "Driver Door Locked",
    "passenger_lock": "Passenger Door Locked",
    "front_left_window_open": "Front Left Window",
    "front_right_window_open": "Front Right Window",
    "rear_left_window_open": "Rear Left Window",
    "rear_right_window_open": "Rear Right Window",
    "charge_con_status": "Charging Cable",
    "dc_charge_gun_connect_status": "DC Charge Gun",
    "charge_status": "Charging",
    "charge_schedule_enabled": "Charge Schedule Enabled",
    "defrost_status": "Defrost Status",
    "connect_status": "Vehicle Connected",
    "engine_sts": "Engine On",
    "high_beam": "High Beam",
    "low_beam": "Low Beam",
    "position_lamp": "Position Lamp",
    "left_turn": "Left Turn Signal",
    "right_turn": "Right Turn Signal",
    "driver_seat_heater_on": "Driver Seat Heater On",
    "front_passenger_seat_heater_on": "Front Passenger Seat Heater On",
    "driver_seat_ventilation_on": "Driver Seat Ventilation On",
    "front_passenger_seat_ventilation_on": "Front Passenger Seat Ventilation On",
}


BINARY_SENSORS: tuple[DeepalBinarySensorDescription, ...] = (
    DeepalBinarySensorDescription(
        key="any_door_open",
        translation_key="any_door_open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: any(value != 0 for value in (_door(data).get("doors") or [])),
    ),
    DeepalBinarySensorDescription(
        key="front_left_door_open",
        translation_key="front_left_door_open",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: _path_value(data, ("door", "doors", 0)) != 0 if _path_value(data, ("door", "doors", 0)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="front_right_door_open",
        translation_key="front_right_door_open",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: _path_value(data, ("door", "doors", 1)) != 0 if _path_value(data, ("door", "doors", 1)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="rear_left_door_open",
        translation_key="rear_left_door_open",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: _path_value(data, ("door", "doors", 2)) != 0 if _path_value(data, ("door", "doors", 2)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="rear_right_door_open",
        translation_key="rear_right_door_open",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: _path_value(data, ("door", "doors", 3)) != 0 if _path_value(data, ("door", "doors", 3)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-back",
        value_fn=lambda data: (_door(data).get("trunk") != 0) if _door(data).get("trunk") is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="driver_lock",
        translation_key="driver_lock",
        icon="mdi:car-door-lock",
        value_fn=lambda data: (_door(data).get("driverLock") == 0) if _door(data).get("driverLock") is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="passenger_lock",
        translation_key="passenger_lock",
        icon="mdi:car-door-lock",
        value_fn=lambda data: (_door(data).get("passengerLock") == 0) if _door(data).get("passengerLock") is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="front_left_window_open",
        translation_key="front_left_window_open",
        icon="mdi:car-windshield",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda data: _path_value(data, ("window", "windows", 0)) != 0 if _path_value(data, ("window", "windows", 0)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="front_right_window_open",
        translation_key="front_right_window_open",
        icon="mdi:car-windshield",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda data: _path_value(data, ("window", "windows", 1)) != 0 if _path_value(data, ("window", "windows", 1)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="rear_left_window_open",
        translation_key="rear_left_window_open",
        icon="mdi:car-windshield",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda data: _path_value(data, ("window", "windows", 2)) != 0 if _path_value(data, ("window", "windows", 2)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="rear_right_window_open",
        translation_key="rear_right_window_open",
        icon="mdi:car-windshield",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda data: _path_value(data, ("window", "windows", 3)) != 0 if _path_value(data, ("window", "windows", 3)) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="charge_con_status",
        translation_key="charge_con_status",
        icon="mdi:ev-plug-type2",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=_charge_gun_connected,
    ),
    DeepalBinarySensorDescription(
        key="dc_charge_gun_connect_status",
        translation_key="dc_charge_gun_connect_status",
        icon="mdi:ev-plug-ccs2",
        device_class=BinarySensorDeviceClass.PLUG,
        # == 3 is "connected", matching the AC chargeConStatus convention above.
        # Dylan's original checked == 0, which is inverted.
        value_fn=lambda data: (_charge(data).get("dcChargeGunConnectStatus") == 3) if _charge(data).get("dcChargeGunConnectStatus") is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="charge_status",
        translation_key="charge_status",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        # chargeStatus == 6 is "Charging" (0 = Charge Complete, 1 = Not Charging).
        # Dylan's original (!= 0) treated "Not Charging" (1) as charging too.
        value_fn=lambda data: (_charge(data).get("chargeStatus") == 6) if _charge(data).get("chargeStatus") is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="charge_schedule_enabled",
        translation_key="charge_schedule_enabled",
        value_fn=_charge_schedule_enabled,
    ),
    DeepalBinarySensorDescription(
        key="defrost_status",
        translation_key="defrost_status",
        value_fn=lambda data: _path_value(data, ("hvac", "defrostStatus")) != 0 if _path_value(data, ("hvac", "defrostStatus")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="connect_status",
        translation_key="connect_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _path_value(data, ("vehicleStatus", "connectStatus")) == 1 if _path_value(data, ("vehicleStatus", "connectStatus")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="engine_sts",
        translation_key="engine_sts",
        value_fn=lambda data: _path_value(data, ("vehicleStatus", "engineSts")) != 0 if _path_value(data, ("vehicleStatus", "engineSts")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="high_beam",
        translation_key="high_beam",
        device_class=BinarySensorDeviceClass.LIGHT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _path_value(data, ("lamp", "highBeam")) != 0 if _path_value(data, ("lamp", "highBeam")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="low_beam",
        translation_key="low_beam",
        device_class=BinarySensorDeviceClass.LIGHT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _path_value(data, ("lamp", "lowBeam")) != 0 if _path_value(data, ("lamp", "lowBeam")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="position_lamp",
        translation_key="position_lamp",
        device_class=BinarySensorDeviceClass.LIGHT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _path_value(data, ("lamp", "positionLamp")) != 0 if _path_value(data, ("lamp", "positionLamp")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="left_turn",
        translation_key="left_turn",
        device_class=BinarySensorDeviceClass.LIGHT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _path_value(data, ("lamp", "leftTurn")) != 0 if _path_value(data, ("lamp", "leftTurn")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="right_turn",
        translation_key="right_turn",
        device_class=BinarySensorDeviceClass.LIGHT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _path_value(data, ("lamp", "rightTurn")) != 0 if _path_value(data, ("lamp", "rightTurn")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="driver_seat_heater_on",
        translation_key="driver_seat_heater_on",
        value_fn=lambda data: _path_value(data, ("seat", "rightFront", "heatStatus")) != 0 if _path_value(data, ("seat", "rightFront", "heatStatus")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="front_passenger_seat_heater_on",
        translation_key="front_passenger_seat_heater_on",
        value_fn=lambda data: _path_value(data, ("seat", "leftFront", "heatStatus")) != 0 if _path_value(data, ("seat", "leftFront", "heatStatus")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="driver_seat_ventilation_on",
        translation_key="driver_seat_ventilation_on",
        value_fn=lambda data: _path_value(data, ("seat", "rightFront", "ventStatus")) != 0 if _path_value(data, ("seat", "rightFront", "ventStatus")) is not None else None,
    ),
    DeepalBinarySensorDescription(
        key="front_passenger_seat_ventilation_on",
        translation_key="front_passenger_seat_ventilation_on",
        value_fn=lambda data: _path_value(data, ("seat", "leftFront", "ventStatus")) != 0 if _path_value(data, ("seat", "leftFront", "ventStatus")) is not None else None,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DeepalDataUpdateCoordinator = entry.runtime_data
    async_add_entities(DeepalBinarySensor(coordinator, description) for description in BINARY_SENSORS)


class DeepalBinarySensor(DeepalEntity, BinarySensorEntity):
    """Deepal binary sensor."""

    entity_description: DeepalBinarySensorDescription

    def __init__(self, coordinator: DeepalDataUpdateCoordinator, description: DeepalBinarySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = BINARY_SENSOR_NAMES.get(description.key)

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.condition)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "charge_schedule_enabled":
            return None
        plan = _charge_schedule(self.condition)
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
