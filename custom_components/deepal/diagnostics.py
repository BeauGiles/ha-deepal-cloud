"""Diagnostics download for the Changan Deepal Cloud integration.

Meant to make telemetry problems debuggable from Home Assistant alone: it
contains the vehicle's protocol detection, the mapped telemetry, the raw signals
the car reported and the ones no entity consumes yet. Credentials, the VIN,
licence plate and location-like values are redacted. The idea follows
Sunek0/ha-deepal-alternative (MIT).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .api import _redact_for_log, _redact_signals, unmapped_signal_keys
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CAC_TOKEN,
    CONF_CAC_USER_ID,
    CONF_CA_USER_ID,
    CONF_CONTROL_PIN,
    CONF_DEVICE_ID,
    CONF_PRIVATE_KEY,
    CONF_RC_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    CONF_VEHICLE_ID,
    DOMAIN,
    vehicle_supports_mqtt_commands,
    vehicle_uses_mqtt,
    vehicle_uses_sda,
)

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_CAC_TOKEN,
    CONF_CAC_USER_ID,
    CONF_CA_USER_ID,
    CONF_CONTROL_PIN,
    CONF_DEVICE_ID,
    CONF_PRIVATE_KEY,
    CONF_RC_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    CONF_VEHICLE_ID,
    "carId",
    "vin",
    "plateNumber",
    "imgUrl",
    "authId",
}

# Large raw blobs are reported separately, not duplicated in the mapped view.
_RAW_KEYS = ("rawMqtt", "rawSda")


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    client = coordinator.client
    data = coordinator.data or {}
    vehicle = data.get("vehicle") or {}
    condition = data.get("condition") or {}
    integration = await async_get_integration(hass, DOMAIN)

    raw_sda = condition.get("rawSda")
    raw_mqtt = condition.get("rawMqtt")
    if vehicle_uses_sda(vehicle):
        source = "sda-rest"
    elif vehicle_uses_mqtt(vehicle):
        source = "mqtt"
    else:
        source = "rest"

    report: dict[str, Any] = {
        "integration_version": str(integration.version),
        "vehicle": vehicle,
        "detection": {
            "protocol_type": vehicle.get("protocolType"),
            "condition_source": source,
            "uses_mqtt": vehicle_uses_mqtt(vehicle),
            "uses_sda": vehicle_uses_sda(vehicle),
            "mqtt_commands_supported": vehicle_supports_mqtt_commands(vehicle),
            "commands_enabled": client.commands_enabled,
            "country": client.country,
            "base_url": client.base_url,
            "sda_base_url": client.sda_base_url,
            "gateway_prefix": client.gateway_prefix,
        },
        "refresh": {
            "last_update_success": coordinator.last_update_success,
            "failure_count": coordinator.refresh_failure_count,
            "last_failure": coordinator.last_refresh_failure,
            "update_interval": str(coordinator.update_interval),
        },
        "config_entry_data": dict(entry.data),
        "config_entry_options": dict(entry.options),
        "mapped_telemetry": {k: v for k, v in condition.items() if k not in _RAW_KEYS},
        "raw_sda": _redact_signals(raw_sda),
        "raw_mqtt": _redact_signals(raw_mqtt),
        # Named without "key": the generic log redaction hides keys containing it.
        "unmapped_signals": (
            unmapped_signal_keys(raw_sda, sda=True)
            if isinstance(raw_sda, dict)
            else unmapped_signal_keys(raw_mqtt, sda=False)
            if isinstance(raw_mqtt, dict)
            else None
        ),
        "mqtt_topics": client.last_mqtt_topics,
        "ota": data.get("ota"),
    }
    # Key-based log redaction for everything except the raw signal dumps (which
    # get exact-key redaction only, above), then the explicit config keys.
    raw = {name: report.pop(name) for name in ("raw_sda", "raw_mqtt")}
    redacted = async_redact_data(_redact_for_log(report), TO_REDACT)
    redacted.update(raw)
    return redacted
