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


def _sda_entry(client_extra):
    entry = _entry()
    entry.runtime_data.vehicle_id = SECRETS["vehicle"]
    for name, value in client_extra.items():
        setattr(entry.runtime_data.client, name, value)
    return entry


def test_s07_probes_not_run_for_e07(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("S07 probes must not run for an E07")

    async def probe_sda(vehicle_id, path):
        return {}

    report = _run(monkeypatch, _sda_entry({"probe_function_config": boom, "probe_condition_v2": boom, "probe_sda": probe_sda}))
    assert set(report["endpoint_probes"]) == {
        "function_list",
        "last_event",
        "mqtt_server_config",
        "ota_task",
        "ota_progress",
        "ota_history",
    }


def test_e07_probes_report_function_list_but_only_shape_of_sensitive_ones(monkeypatch):
    async def probe_sda(vehicle_id, path):
        if path.endswith("get-function"):
            return {"functions": ["window", "trunk"], "vin": SECRETS["vin"]}
        if path.endswith("get-mqtt-server-config"):
            return {"host": "broker.example.com", "password": "BROKERPASSWORD123", "port": 8883}
        raise RuntimeError("404 not found")

    report = _run(monkeypatch, _sda_entry({"probe_sda": probe_sda}))
    probes = report["endpoint_probes"]
    assert probes["function_list"]["data"]["functions"] == ["window", "trunk"]
    assert probes["mqtt_server_config"]["shape_only"] is True
    shape = probes["mqtt_server_config"]["data"]
    assert shape["host"] == "str" and shape["port"] == "int"  # types only, never values
    assert "password" in shape
    assert probes["last_event"]["ok"] is False
    text = json.dumps(report, default=str)
    for secret in ("BROKERPASSWORD123", "broker.example.com", SECRETS["vin"]):
        assert secret not in text


def test_shape_of_hides_values():
    from custom_components.deepal.api import shape_of

    assert shape_of({"a": [{"b": 1}, {"b": 2}], "c": None, "d": []}) == {"a": [{"b": "int"}], "c": "NoneType", "d": []}


def test_e07_ota_probes_report_values_trim_history_and_strip_url_queries(monkeypatch):
    calls = []

    async def probe_sda(vehicle_id, path):
        calls.append(path)
        if path.endswith("ota/get-task"):
            return {"upgradeStatus": 2, "version": "1.2.3", "vin": SECRETS["vin"], "pkg": "https://cdn.example.com/p.zip?sign=SIGNEDSECRET#frag"}
        if path.endswith("ota/get-progress"):
            return {"progress": 40}
        if path.endswith("ota/get-upgrade-history"):
            return {"records": [{"version": f"v{n}"} for n in range(12)]}
        return {}

    report = _run(monkeypatch, _sda_entry({"probe_sda": probe_sda}))
    probes = report["endpoint_probes"]
    assert probes["ota_task"]["data"]["upgradeStatus"] == 2  # real values, so enums can be learned
    assert probes["ota_task"]["data"]["pkg"] == "https://cdn.example.com/p.zip"
    assert probes["ota_progress"]["data"] == {"progress": 40}
    records = probes["ota_history"]["data"]["records"]
    assert len(records) == 6 and records[-1] == "... 7 more not shown"
    assert any(path.endswith("ota/get-task") for path in calls)
    text = json.dumps(report, default=str)
    assert "SIGNEDSECRET" not in text and SECRETS["vin"] not in text


def test_trim_lists_and_strip_url_queries():
    from custom_components.deepal.api import strip_url_queries, trim_lists

    assert trim_lists([1, 2, 3], limit=5) == [1, 2, 3]
    assert trim_lists({"a": [1, 2, 3, 4]}, limit=2) == {"a": [1, 2, "... 2 more not shown"]}
    assert strip_url_queries({"u": ["http://x/y?a=1", "not a url?x=1", 5]}) == {"u": ["http://x/y", "not a url?x=1", 5]}
