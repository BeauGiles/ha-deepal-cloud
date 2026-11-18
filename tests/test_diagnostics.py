"""The diagnostics download is posted publicly in issues: it must not leak secrets."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from custom_components.deepal import diagnostics

SECRETS = {
    "access": "ACCESSTOKEN-abc123",
    "refresh": "REFRESHTOKEN-def456",
    "cac": "CACTOKEN-ghi789",
    "rc": "RCTOKEN-jkl012",
    "pin": "482915",
    "pem": "-----BEGIN PRIVATE KEY-----MIIEvQIBADANBgkq",
    "device": "DEVICEID-mno345",
    "user": "USERID-pqr678",
    "ca_user": "CAUSERID-stu901",
    "cac_user": "CACUSERID-vwx234",
    "vehicle": "VEHICLEID-yza567",
    "car_id": "CARID-bcd890",
    "vin": "LDP0000VINSECRET1",
    "plate": "ABC123PLATE",
    "img": "https://img.example/PRIVATEIMAGE.png",
    "email": "owner@example.com",
}


def _redact_data(data, to_redact):
    """Same behaviour as Home Assistant's async_redact_data."""
    if isinstance(data, list):
        return [_redact_data(item, to_redact) for item in data]
    if not isinstance(data, dict):
        return data
    return {
        key: "**REDACTED**" if key in to_redact else _redact_data(value, to_redact)
        for key, value in data.items()
    }


def _entry():
    coordinator = SimpleNamespace(
        client=SimpleNamespace(
            commands_enabled=True,
            country="AU",
            base_url="https://m.iov.changanauto.sg",
            sda_base_url="https://prod-m.sda.changanauto.sg",
            gateway_prefix="/appgw",
            # As produced by DeepalClient._mqtt_topic_summary (device ids already hidden).
            last_mqtt_model_code="SC6464AAKBEV",
            last_mqtt_topics=[{"msgType": "properties", "pub": ["$vdp/[redacted]/properties/get/req"], "sub": []}],
        ),
        data={
            "vehicle": {
                "protocolType": "SDA-MQTT",
                "carId": SECRETS["car_id"],
                "vin": SECRETS["vin"],
                "plateNumber": SECRETS["plate"],
                "imgUrl": SECRETS["img"],
            },
            "condition": {
                "vehicleStatus": {"soc": 61},
                "rawSda": {
                    "BcuSoc": 61,
                    "vin": SECRETS["vin"],
                    "plateNumber": SECRETS["plate"],
                    "Lat": "-33.86",
                    "Lng": "151.20",
                    "SomeUnknownSignal": 7,
                },
            },
            "ota": None,
        },
        last_update_success=True,
        refresh_failure_count=0,
        last_refresh_failure=None,
        update_interval="0:01:00",
        mqtt_fallback_active=False,
        _mqtt_failures=0,
        _mqtt_last_error=None,
    )
    return SimpleNamespace(
        runtime_data=coordinator,
        data={
            "access_token": SECRETS["access"],
            "refresh_token": SECRETS["refresh"],
            "cac_token": SECRETS["cac"],
            "rc_token": SECRETS["rc"],
            "control_pin": SECRETS["pin"],
            "private_key_pem": SECRETS["pem"],
            "device_id": SECRETS["device"],
            "user_id": SECRETS["user"],
            "ca_user_id": SECRETS["ca_user"],
            "cac_user_id": SECRETS["cac_user"],
            "vehicle_id": SECRETS["vehicle"],
            "email": SECRETS["email"],
            "country": "AU",
        },
        options={"control_pin": SECRETS["pin"], "enable_commands": True},
    )


@pytest.fixture
def report(monkeypatch):
    async def get_integration(hass, domain):
        return SimpleNamespace(version="0.4.0")

    monkeypatch.setattr(diagnostics, "async_redact_data", _redact_data)
    monkeypatch.setattr(diagnostics, "async_get_integration", get_integration)
    return asyncio.run(diagnostics.async_get_config_entry_diagnostics(None, _entry()))


def test_no_secret_value_appears_anywhere(report):
    text = json.dumps(report, default=str)
    leaked = {name: value for name, value in SECRETS.items() if value in text}
    assert not leaked, f"leaked into diagnostics: {sorted(leaked)}"


def test_coordinates_in_raw_signals_are_redacted(report):
    raw = report["raw_sda"]
    assert raw.get("Lat") != "-33.86"
    assert raw.get("Lng") != "151.20"


def test_still_useful_for_debugging(report):
    assert report["integration_version"] == "0.4.0"
    assert report["detection"]["protocol_type"] == "SDA-MQTT"
    assert report["detection"]["country"] == "AU"
    assert report["detection"]["mqtt_model_code"] == "SC6464AAKBEV"  # a model code, not an identifier
    assert report["raw_sda"]["BcuSoc"] == 61  # harmless signals are kept
    assert "SomeUnknownSignal" in report["unmapped_signals"]


def _rest_entry(client_extra):
    entry = _entry()
    coordinator = entry.runtime_data
    coordinator.vehicle_id = SECRETS["vehicle"]
    coordinator.data["vehicle"] = {"protocolType": "REST", "carId": SECRETS["car_id"], "vin": SECRETS["vin"]}
    coordinator.data["condition"] = {"vehicleStatus": {"soc": 61}}
    for name, value in client_extra.items():
        setattr(coordinator.client, name, value)
    return entry


def _run(monkeypatch, entry):
    async def get_integration(hass, domain):
        return SimpleNamespace(version="0.4.0")

    monkeypatch.setattr(diagnostics, "async_redact_data", _redact_data)
    monkeypatch.setattr(diagnostics, "async_get_integration", get_integration)
    return asyncio.run(diagnostics.async_get_config_entry_diagnostics(None, entry))


def test_probes_report_data_and_failures_without_leaking(monkeypatch):
    async def function_config(vehicle_id, v2=False):
        if v2:
            raise RuntimeError("Deepal API error: APP_X_1 not found")
        return {"functions": ["seat_heat"], "vin": SECRETS["vin"]}

    async def condition_v2(vehicle_id):
        return {"vehicleStatus": {"soc": 61}, "vehicleId": SECRETS["vehicle"]}

    entry = _rest_entry({"probe_function_config": function_config, "probe_condition_v2": condition_v2})
    report = _run(monkeypatch, entry)
    probes = report["endpoint_probes"]
    assert probes["function_config"]["ok"] is True
    assert probes["function_config"]["data"]["functions"] == ["seat_heat"]
    assert probes["function_config_v2"]["ok"] is False
    assert "RuntimeError" in probes["function_config_v2"]["error"]
    assert probes["condition_v2"]["ok"] is True
    text = json.dumps(report, default=str)
    assert SECRETS["vin"] not in text
    assert SECRETS["vehicle"] not in text


def test_probes_skipped_for_non_rest_vehicles(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("must not be called")

    report = _run(monkeypatch, _sda_entry(boom))
    assert "skipped" in report["endpoint_probes"]


def _sda_entry(fn):
    entry = _entry()
    entry.runtime_data.vehicle_id = SECRETS["vehicle"]
    entry.runtime_data.client.probe_function_config = fn
    entry.runtime_data.client.probe_condition_v2 = fn
    return entry
