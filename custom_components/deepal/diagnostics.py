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

from .api import (
    SDA_PROBE_PATHS,
    SDA_SHAPE_ONLY_PROBES,
    SDA_TRIMMED_PROBES,
    _redact_for_log,
    _redact_signals,
    shape_of,
    strip_url_queries,
    trim_lists,
    unmapped_signal_keys,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CA_USER_ID,
    CONF_CAC_TOKEN,
    CONF_CAC_USER_ID,
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


async def _run_probes(client: Any, vehicle_id: str, *, source: str) -> dict[str, Any]:
    """Run the read-only endpoint probes. Never raises; failures are reported as text."""
    if source == "sda-rest":
        return await _run_sda_probes(client, vehicle_id)
    if source != "rest":
        return {"skipped": "only run for REST (S07) and SDA (E07) vehicles"}
    probes = {
        "function_config": lambda: client.probe_function_config(vehicle_id),
        "function_config_v2": lambda: client.probe_function_config(vehicle_id, v2=True),
        "condition_v2": lambda: client.probe_condition_v2(vehicle_id),
    }
    results: dict[str, Any] = {}
    for name, call in probes.items():
        try:
            results[name] = {"ok": True, "data": await call()}
        except Exception as err:  # noqa: BLE001 - diagnostics must never fail
            results[name] = {"ok": False, "error": f"{type(err).__name__}: {err}"}
    return results


async def _run_sda_probes(client: Any, vehicle_id: str) -> dict[str, Any]:
    """E07 probes. Some report structure only, as their values may be sensitive."""
    results: dict[str, Any] = {}
    for name, path in SDA_PROBE_PATHS.items():
        try:
            data = await client.probe_sda(vehicle_id, path)
            if name in SDA_SHAPE_ONLY_PROBES:
                data = shape_of(data)
            else:
                data = strip_url_queries(data)
                if name in SDA_TRIMMED_PROBES:
                    data = trim_lists(data)
            results[name] = {"ok": True, "shape_only": name in SDA_SHAPE_ONLY_PROBES, "data": data}
        except Exception as err:  # noqa: BLE001 - diagnostics must never fail
            results[name] = {"ok": False, "error": f"{type(err).__name__}: {err}"}
    return results


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
        source = "rest (mqtt fallback)" if coordinator.mqtt_fallback_active else "mqtt"
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
            # Model code from the MQTT message envelope (diagnostic only). Tells an
            # S05 EV (...BEV) from a PHEV (...HEV); None if the car sends none.
            "mqtt_model_code": getattr(client, "last_mqtt_model_code", None),
        },
        "refresh": {
            "last_update_success": coordinator.last_update_success,
            "failure_count": coordinator.refresh_failure_count,
            "last_failure": coordinator.last_refresh_failure,
            "update_interval": str(coordinator.update_interval),
            "mqtt_fallback_active": coordinator.mqtt_fallback_active,
            "mqtt_failures": coordinator._mqtt_failures,
            "mqtt_last_error": str(coordinator._mqtt_last_error) if coordinator._mqtt_last_error else None,
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
        # Read-only calls to endpoints the official app has but this integration
        # does not use yet. Reported only, to learn what real cars return.
        "endpoint_probes": (
            await _run_probes(client, coordinator.vehicle_id, source=source)
            if hasattr(client, "probe_function_config") or hasattr(client, "probe_sda")
            else None
        ),
    }
    # Key-based log redaction for everything except the raw signal dumps (which
    # get exact-key redaction only, above), then the explicit config keys.
    raw = {name: report.pop(name) for name in ("raw_sda", "raw_mqtt")}
    redacted = async_redact_data(_redact_for_log(report), TO_REDACT)
    redacted.update(raw)
    return redacted
