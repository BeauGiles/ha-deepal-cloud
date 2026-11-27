"""Sensors for Deepal vehicles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL, PERCENTAGE, UnitOfLength, UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import sda_unmapped_attributes
from .const import vehicle_uses_sda
from .coordinator import DeepalDataUpdateCoordinator
from .entity import DeepalEntity
from .gating import async_add_supported


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


def _temp_value(data: dict[str, Any], path: tuple[str | int, ...]) -> float | None:
    value = _path_value(data, path)
    return (value / 10) if isinstance(value, int | float) else None


def _millis_to_datetime(value: Any) -> datetime | None:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(millis / 1000, UTC)


def _charge_schedule(data: dict[str, Any]) -> dict[str, Any]:
    plans = _path_value(data, ("charge", "chargePlanList"))
    if not isinstance(plans, list) or not plans:
        return {}
    first_plan = plans[0]
    return first_plan if isinstance(first_plan, dict) else {}


def _format_hours_minutes(minutes: Any) -> str | None:
    """Format remaining charge minutes as H:MM, or None when there is no estimate.

    The duration-style sensor shows seconds in the frontend; this text form is
    meant for dashboards. 8191 is the app's "no estimate" value. Idea and format
    follow Sunek0/ha-deepal-alternative (MIT).
    """
    if not isinstance(minutes, int | float) or minutes < 0 or minutes == 8191:
        return None
    total = int(minutes)
    return f"{total // 60}:{total % 60:02d}"


def _format_hhmm(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).zfill(4)
    if len(raw) != 4 or not raw.isdigit():
        return str(value)
    return f"{raw[:2]}:{raw[2:]}"


@dataclass(frozen=True, kw_only=True)
class DeepalSensorDescription(SensorEntityDescription):
    path: tuple[str | int, ...]
    divide_by: float | None = None
    timestamp_ms: bool = False
    options: list[str] | None = None
    value_map: dict[int, str] | None = None


SENSOR_NAMES = {
    "soc": "State of charge",
    "drv_mileage": "Estimated range",
    "total_mileage": "Odometer",
    "speed": "Speed",
    "last_updated_at": "Vehicle data timestamp",
    "inside_temp": "Inside temperature",
    "outside_temp": "Outside temperature",
    "ac_status": "Cabin climate mode",
    "inside_humidity": "Cabin humidity",
    "inside_pm25": "Cabin PM2.5",
    "inside_air_quality_level": "Cabin air quality index",
    "charge_status": "Charging status",
    "charge_current": "Reported charging current",
    "ac_charge_current": "AC charging current",
    "dc_charge_current": "DC charging current",
    "remain_charge_time": "Remaining charge time",
    "remain_charge_time_hhmm": "Remaining charge time (H:MM)",
    "max_soc_percent": "Max charge limit",
    "charge_plan_start_time": "Charging schedule start time",
    "charge_plan_end_time": "Charging schedule end time",
    "tire_front_left_pressure": "Front left tyre pressure",
    "tire_front_right_pressure": "Front right tyre pressure",
    "tire_rear_left_pressure": "Rear left tyre pressure",
    "tire_rear_right_pressure": "Rear right tyre pressure",
    "tire_lowest_pressure": "Lowest tyre pressure",
    "fuel_level": "Fuel level",
    "fuel_volume": "Fuel volume",
    "fuel_range": "Fuel range",
    "driver_seat_heater_level": "Driver seat heater level",
    "front_passenger_seat_heater_level": "Front passenger seat heater level",
    "rear_left_seat_heater_level": "Rear left seat heater level",
    "rear_right_seat_heater_level": "Rear right seat heater level",
    "steering_wheel_heater": "Steering wheel heater",
    "vehicle_status": "Vehicle status",
    "power_status": "Power status",
    "gear_signal": "Gear signal",
    "epb_sts": "Electronic parking brake status",
    "img_url": "Vehicle image URL",
    "refresh_failure_count": "Refresh failure count",
    "ota_status": "OTA status",
}


SENSORS: tuple[DeepalSensorDescription, ...] = (
    DeepalSensorDescription(
        key="soc",
        translation_key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        path=("vehicleStatus", "soc"),
    ),
    DeepalSensorDescription(
        key="drv_mileage",
        translation_key="drv_mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("vehicleStatus", "drvMileage"),
    ),
    DeepalSensorDescription(
        key="total_mileage",
        translation_key="total_mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        path=("vehicleStatus", "totalMileage"),
    ),
    DeepalSensorDescription(
        key="speed",
        translation_key="speed",
        native_unit_of_measurement="km/h",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        path=("vehicleStatus", "speed"),
    ),
    DeepalSensorDescription(
        key="last_updated_at",
        translation_key="last_updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        path=("lastUpdatedAt",),
        timestamp_ms=True,
    ),
    DeepalSensorDescription(
        key="inside_temp",
        translation_key="inside_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("hvac", "insideTemp"),
        divide_by=10,
    ),
    DeepalSensorDescription(
        key="outside_temp",
        translation_key="outside_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("hvac", "outsideTemp"),
        divide_by=10,
    ),
    DeepalSensorDescription(
        key="ac_status",
        translation_key="ac_status",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:air-conditioner",
        path=(),
        options=["off", "heat_cool"],
    ),
    DeepalSensorDescription(
        key="inside_humidity",
        translation_key="inside_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        path=("hvac", "insideHumidity"),
    ),
    DeepalSensorDescription(
        key="inside_pm25",
        translation_key="inside_pm25",
        native_unit_of_measurement="ug/m3",
        icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT,
        path=("hvac", "insidePm25"),
    ),
    DeepalSensorDescription(
        key="inside_air_quality_level",
        translation_key="inside_air_quality_level",
        # Promoted out of Diagnostic: the Polestar C3 fork's equivalent ("Cabin
        # air quality index") is a primary Sensors-card entity, not Diagnostic.
        path=("hvac", "insideAirQualityLevel"),
    ),
    DeepalSensorDescription(
        key="charge_status",
        translation_key="charge_status",
        # Promoted out of Diagnostic: the Polestar C3 fork's equivalent
        # ("Charging status") is a primary Sensors-card entity, not Diagnostic,
        # and this tells more than the plain Charging on/off binary sensor.
        path=("charge", "chargeStatus"),
        value_map={0: "Charge Complete", 1: "Not Charging", 6: "Charging"},
    ),
    DeepalSensorDescription(
        key="charge_current",
        translation_key="charge_current",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        path=("charge", "chargeCurrent"),
    ),
    DeepalSensorDescription(
        key="ac_charge_current",
        translation_key="ac_charge_current",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        path=("charge", "acChargeCurrent"),
    ),
    DeepalSensorDescription(
        key="dc_charge_current",
        translation_key="dc_charge_current",
        native_unit_of_measurement="A",
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        path=("charge", "dcChargeCurrent"),
    ),
    DeepalSensorDescription(
        key="remain_charge_time",
        translation_key="remain_charge_time",
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
        path=("charge", "remainChargeTime"),
    ),
    DeepalSensorDescription(
        key="remain_charge_time_hhmm",
        translation_key="remain_charge_time_hhmm",
        icon="mdi:timer-outline",
        path=("charge", "remainChargeTime"),
    ),
    DeepalSensorDescription(
        key="max_soc_percent",
        translation_key="max_soc_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        # Diagnostic: a read-only mirror of the Charge Limit number control,
        # same treatment as a config-echo value. The Polestar C3 fork doesn't
        # even duplicate its equivalent (Target SoC) as a separate sensor.
        entity_category=EntityCategory.DIAGNOSTIC,
        path=("charge", "maxSocPercent"),
    ),
    DeepalSensorDescription(
        key="charge_plan_start_time",
        translation_key="charge_plan_start_time",
        # Diagnostic: a read-only mirror of the Charging Schedule Start time
        # entity, same reasoning as max_soc_percent above.
        entity_category=EntityCategory.DIAGNOSTIC,
        path=(),
    ),
    DeepalSensorDescription(
        key="charge_plan_end_time",
        translation_key="charge_plan_end_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        path=(),
    ),
    DeepalSensorDescription(
        key="tire_front_left_pressure",
        translation_key="tire_front_left_pressure",
        native_unit_of_measurement="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("tire", "leftFront", "pressure"),
    ),
    DeepalSensorDescription(
        key="tire_front_right_pressure",
        translation_key="tire_front_right_pressure",
        native_unit_of_measurement="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("tire", "rightFront", "pressure"),
    ),
    DeepalSensorDescription(
        key="tire_rear_left_pressure",
        translation_key="tire_rear_left_pressure",
        native_unit_of_measurement="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("tire", "leftBack", "pressure"),
    ),
    DeepalSensorDescription(
        key="tire_rear_right_pressure",
        translation_key="tire_rear_right_pressure",
        native_unit_of_measurement="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("tire", "rightBack", "pressure"),
    ),
    # The lowest of the four, so a dashboard or automation doesn't need four
    # separate thresholds - the same thing a min_max + threshold helper pair
    # would do, built in. Created only once at least one wheel reports a
    # pressure (see _sensor_supported below); hidden on cars with none.
    DeepalSensorDescription(
        key="tire_lowest_pressure",
        translation_key="tire_lowest_pressure",
        native_unit_of_measurement="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        path=(),
    ),
    # S05 PHEV only (Sunek0/ha-deepal-alternative, MIT, for the raw field
    # names, hardware-validated against a real S05 PHEV). Absent on a BEV, so
    # hidden there, on S07 and on E07.
    DeepalSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("fuel", "levelPercent"),
    ),
    DeepalSensorDescription(
        key="fuel_volume",
        translation_key="fuel_volume",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("fuel", "volumeL"),
    ),
    DeepalSensorDescription(
        key="fuel_range",
        translation_key="fuel_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        path=("fuel", "remainingRangeKm"),
    ),
    DeepalSensorDescription(
        key="driver_seat_heater_level",
        translation_key="driver_seat_heater_level",
        path=("seat", "driver", "heatStatus"),
    ),
    DeepalSensorDescription(
        key="front_passenger_seat_heater_level",
        translation_key="front_passenger_seat_heater_level",
        path=("seat", "passenger", "heatStatus"),
    ),
    DeepalSensorDescription(
        key="rear_left_seat_heater_level",
        translation_key="rear_left_seat_heater_level",
        path=("seat", "leftBack", "heatStatus"),
    ),
    DeepalSensorDescription(
        key="rear_right_seat_heater_level",
        translation_key="rear_right_seat_heater_level",
        path=("seat", "rightBack", "heatStatus"),
    ),
    DeepalSensorDescription(
        key="steering_wheel_heater",
        translation_key="steering_wheel_heater",
        path=(),
    ),
    DeepalSensorDescription(
        key="vehicle_status",
        translation_key="vehicle_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        path=("vehicleStatus", "status"),
    ),
    DeepalSensorDescription(
        key="power_status",
        translation_key="power_status",
        # Promoted out of Diagnostic: the Polestar C3 fork's closest equivalent
        # ("In use") is a primary Sensors-card entity, not Diagnostic.
        path=("vehicleStatus", "powerStatus"),
        value_map={0: "Idle", 2: "Drive"},
    ),
    DeepalSensorDescription(
        key="gear_signal",
        translation_key="gear_signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        path=("vehicleStatus", "gearSignal"),
    ),
    DeepalSensorDescription(
        key="epb_sts",
        translation_key="epb_sts",
        entity_category=EntityCategory.DIAGNOSTIC,
        path=("vehicleStatus", "epbSts"),
    ),
    DeepalSensorDescription(
        key="refresh_failure_count",
        translation_key="refresh_failure_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        path=(),
    ),
    DeepalSensorDescription(
        key="img_url",
        translation_key="img_url",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        path=(),
    ),
    DeepalSensorDescription(
        key="ota_status",
        translation_key="ota_status",
        icon="mdi:update",
        entity_category=EntityCategory.DIAGNOSTIC,
        path=(),
    ),
)


# Sensors that are always created: they do not come from the vehicle's condition.
ALWAYS_SENSORS = frozenset({"refresh_failure_count", "img_url"})


def _condition(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("condition") or {}


_TIRE_PATHS: tuple[tuple[str, ...], ...] = (
    ("tire", "leftFront", "pressure"),
    ("tire", "rightFront", "pressure"),
    ("tire", "leftBack", "pressure"),
    ("tire", "rightBack", "pressure"),
)


def _tire_pressures(condition: dict[str, Any]) -> list[float]:
    values = (_path_value(condition, path) for path in _TIRE_PATHS)
    return [value for value in values if isinstance(value, int | float)]


def _sensor_supported(description: DeepalSensorDescription):
    """Return a predicate telling whether the vehicle reports this sensor's data."""
    key = description.key
    if key in ALWAYS_SENSORS:
        return lambda data: True
    if key == "ota_status":
        return lambda data: bool(data.get("ota"))
    if key in ("charge_plan_start_time", "charge_plan_end_time"):
        field = "startTime" if key == "charge_plan_start_time" else "endTime"
        return lambda data: _charge_schedule(_condition(data)).get(field) is not None
    if key == "ac_status":
        return lambda data: _path_value(_condition(data), ("hvac", "acStatus")) is not None
    if key == "steering_wheel_heater":
        return lambda data: _path_value(_condition(data), ("vehicleStatus", "steeringWheelHeater")) is not None
    if key == "tire_lowest_pressure":
        return lambda data: bool(_tire_pressures(_condition(data)))
    path = description.path
    return lambda data: _path_value(_condition(data), path) is not None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DeepalDataUpdateCoordinator = entry.runtime_data
    async_add_entities([DeepalRawConditionSensor(coordinator)])
    if vehicle_uses_sda((coordinator.data or {}).get("vehicle") or {}):
        async_add_entities([DeepalSdaDataSensor(coordinator)])
    await async_add_supported(
        hass,
        entry,
        coordinator,
        async_add_entities,
        [(DeepalSensor(coordinator, description), _sensor_supported(description)) for description in SENSORS],
        "sensor",
    )


class DeepalSensor(DeepalEntity, SensorEntity):
    """Deepal sensor."""

    entity_description: DeepalSensorDescription

    def __init__(self, coordinator: DeepalDataUpdateCoordinator, description: DeepalSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = SENSOR_NAMES.get(description.key)
        if description.options:
            self._attr_options = description.options

    @property
    def native_value(self) -> Any:
        if self.entity_description.key == "ac_status":
            return _cabin_climate_mode_state(self.condition)
        if self.entity_description.key == "remain_charge_time":
            minutes = _path_value(self.condition, self.entity_description.path)
            return None if minutes == 8191 else minutes
        if self.entity_description.key == "remain_charge_time_hhmm":
            return _format_hours_minutes(_path_value(self.condition, self.entity_description.path))
        if self.entity_description.key == "charge_plan_start_time":
            return _format_hhmm(_charge_schedule(self.condition).get("startTime"))
        if self.entity_description.key == "charge_plan_end_time":
            return _format_hhmm(_charge_schedule(self.condition).get("endTime"))
        if self.entity_description.key == "steering_wheel_heater":
            return _steering_wheel_heater_state(self.condition)
        if self.entity_description.key == "tire_lowest_pressure":
            pressures = _tire_pressures(self.condition)
            return min(pressures) if pressures else None
        if self.entity_description.key == "refresh_failure_count":
            return self.coordinator.refresh_failure_count
        if self.entity_description.key == "img_url":
            return ((self.coordinator.data or {}).get("vehicle") or {}).get("imgUrl")
        if self.entity_description.key == "ota_status":
            ota = (self.coordinator.data or {}).get("ota")
            if not ota:
                return None
            state = ota.get("state", "Unknown")
            process = ota.get("process", 0)
            if state == "INSTALLED":
                return "Up to date"
            if state == "DOWNLOADING":
                return f"Downloading {process}%"
            if state == "INSTALLING":
                return f"Installing {process}%"
            return state
        if self.entity_description.timestamp_ms:
            return _millis_to_datetime(_path_value(self.condition, self.entity_description.path))
        value = _path_value(self.condition, self.entity_description.path)
        if self.entity_description.value_map is not None and value is not None:
            return self.entity_description.value_map.get(value, f"Unknown ({value})")
        if self.entity_description.divide_by and isinstance(value, int | float):
            return value / self.entity_description.divide_by
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "refresh_failure_count":
            return {"last_failure": self.coordinator.last_refresh_failure}
        if self.entity_description.key == "img_url":
            vehicle = ((self.coordinator.data or {}).get("vehicle") or {})
            return {
                "series": vehicle.get("seriesName") or vehicle.get("seriesCode"),
                "model": vehicle.get("modelName") or vehicle.get("modelCode"),
            }
        if self.entity_description.key == "ota_status":
            ota = (self.coordinator.data or {}).get("ota")
            if not ota:
                return {}
            return {
                "stage": ota.get("stage"),
                "process": ota.get("process"),
                "state": ota.get("state"),
                "task_id": (ota.get("taskBase") or {}).get("taskId"),
            }
        if self.entity_description.key == "ac_status":
            hvac = self.condition.get("hvac") or {}
            return {
                "raw_ac_status": hvac.get("acStatus"),
                "target_temperature": _temp_value(self.condition, ("hvac", "remoteTemp")),
            }
        if self.entity_description.key in ("charge_plan_start_time", "charge_plan_end_time"):
            return _charge_schedule_attributes(self.condition)
        if self.entity_description.key == "steering_wheel_heater":
            vehicle_status = self.condition.get("vehicleStatus") or {}
            return {
                "raw_switch": vehicle_status.get("steeringWheelHeater"),
                "raw_level": vehicle_status.get("steeringWheelHeaterLevel"),
                "levels": {"0": "Off", "1": "Low", "2": "Medium", "3": "High"},
            }
        return None


class DeepalRawConditionSensor(DeepalEntity, SensorEntity):
    """Diagnostic sensor exposing the complete condition payload."""

    _attr_translation_key = "raw_condition"
    _attr_name = "Raw condition data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "raw_condition")

    @property
    def native_value(self) -> datetime | None:
        return _millis_to_datetime(self.condition.get("lastUpdatedAt"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"condition": self.condition}


class DeepalSdaDataSensor(DeepalEntity, SensorEntity):
    """E07 signals no entity reads yet, one flat attribute per signal.

    The state is how many such signals the car reported. The attributes change
    with every report and can be large, so they are kept out of the recorder
    (they show live but are not written to the database history).
    """

    _attr_translation_key = "sda_data"
    _attr_name = "SDA data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, coordinator: DeepalDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "sda_data")

    @property
    def _signals(self) -> dict[str, Any]:
        return sda_unmapped_attributes(self.condition.get("rawSda"))

    @property
    def native_value(self) -> int | None:
        if not isinstance(self.condition.get("rawSda"), dict):
            return None
        return len(self._signals)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._signals


def _steering_wheel_heater_state(data: dict[str, Any]) -> str | None:
    vehicle_status = data.get("vehicleStatus") or {}
    heater_on = vehicle_status.get("steeringWheelHeater")
    level = vehicle_status.get("steeringWheelHeaterLevel")
    if heater_on is None and level is None:
        return None
    if not heater_on or not level:
        return "Off"
    if level == 1:
        return "Low"
    if level == 2:
        return "Medium"
    if level == 3:
        return "High"
    return None


def _cabin_climate_mode_state(data: dict[str, Any]) -> str | None:
    ac_status = (data.get("hvac") or {}).get("acStatus")
    if ac_status is None:
        return None
    return "off" if ac_status == 0 else "heat_cool"


def _charge_schedule_attributes(data: dict[str, Any]) -> dict[str, Any]:
    plan = _charge_schedule(data)
    return {
        "plan_id": plan.get("planId"),
        "start_switch": plan.get("startSwitch"),
        "end_switch": plan.get("endSwitch"),
        "is_valid": plan.get("isValid"),
        "weeks": plan.get("weeks"),
        "time_zone": plan.get("timeZone"),
        "time_format": plan.get("timeFormat"),
        "plan_type": plan.get("planType"),
        "send_time": plan.get("sendTime"),
    }
