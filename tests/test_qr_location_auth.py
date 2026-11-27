"""QR location-permission authorisation and the GPS device tracker.

Ported from danperks/ha-deepal (MIT). The tracker is only ever populated for
an S05 (literal MQTT): locationGeo is mapped from MQTT telemetry in api.py's
_mqtt_condition_from_params, and nothing maps it for the S07 REST condition
or the E07 SDA condition.
"""

from __future__ import annotations

import asyncio
import types

import pytest

from custom_components.deepal import coordinator as coordinator_module
from custom_components.deepal import device_tracker
from custom_components.deepal.api import (
    DeepalApiError,
    DeepalAuthError,
    DeepalClient,
    _mqtt_condition_from_params,
    extract_qr_code,
)
from custom_components.deepal.coordinator import DeepalDataUpdateCoordinator
from custom_components.deepal.device_tracker import DeepalLocationTracker

_SAMPLE_QR = "00000000-0000-4000-8000-000000000001"
_SCAN_URL = (
    "https://ca-m.iov.changanauto.com.de/intl-app-gw/intl-app-user/api/qr-code/tmp-auth/scan"
    f"?qrCode={_SAMPLE_QR}"
)

# --- api.py: extract_qr_code ------------------------------------------------


class TestExtractQrCode:
    def test_query_url(self):
        assert extract_qr_code(f"  {_SCAN_URL}  ") == _SAMPLE_QR

    def test_fragment_url(self):
        url = f"https://ca-m.iov.changanauto.com.de/#/tmp-auth?qrCode={_SAMPLE_QR}"
        assert extract_qr_code(url) == _SAMPLE_QR

    def test_query_wins_over_fragment(self):
        url = "https://example.test/scan?qrCode=from-query#/path?qrCode=from-fragment"
        assert extract_qr_code(url) == "from-query"

    def test_bare_qr_code_parameter(self):
        assert extract_qr_code(f"qrCode={_SAMPLE_QR}&unused=1") == _SAMPLE_QR

    def test_bare_token(self):
        assert extract_qr_code(f"\n{_SAMPLE_QR}\t") == _SAMPLE_QR

    @pytest.mark.parametrize(
        "value",
        ["", "   ", "not a token", "https://example.test/scan", "https://example.test/scan?qrCode="],
    )
    def test_rejects_blank_internal_whitespace_and_url_without_code(self, value):
        with pytest.raises(ValueError):
            extract_qr_code(value)


# --- api.py: authorize_qr_code ---------------------------------------------


def make_client(*, posts):
    """A DeepalClient whose _post is a fake that records calls and replays posts."""
    client = object.__new__(DeepalClient)
    client.calls = []
    remaining = list(posts)

    async def fake_post(path, payload=None, **kwargs):
        client.calls.append({"path": path, "payload": payload, "kwargs": kwargs})
        if not remaining:
            raise DeepalApiError("no more responses queued")
        result = remaining.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    client._post = fake_post
    return client


class TestAuthorizeQrCode:
    def test_scans_then_confirms_without_retry(self):
        client = make_client(posts=["scan-data", "confirm-data"])
        result = asyncio.run(client.authorize_qr_code(_SCAN_URL))
        assert result == {"qr_code": _SAMPLE_QR, "scan": "scan-data", "confirm": "confirm-data"}
        assert len(client.calls) == 2
        assert client.calls[0]["path"].endswith("/tmp-auth/scan")
        assert client.calls[1]["path"].endswith("/tmp-auth/confirm")
        assert client.calls[0]["payload"] == {"qrCode": _SAMPLE_QR}
        assert client.calls[0]["kwargs"]["retry"] is False
        assert client.calls[1]["kwargs"]["retry"] is False

    def test_bare_token_also_works(self):
        client = make_client(posts=["scan-data", "confirm-data"])
        result = asyncio.run(client.authorize_qr_code(_SAMPLE_QR))
        assert result["qr_code"] == _SAMPLE_QR

    def test_invalid_qr_does_not_post(self):
        client = make_client(posts=[])
        with pytest.raises(DeepalApiError):
            asyncio.run(client.authorize_qr_code("   "))
        assert client.calls == []

    def test_scan_failure_does_not_confirm(self):
        client = make_client(posts=[DeepalApiError("rejected")])
        with pytest.raises(DeepalApiError):
            asyncio.run(client.authorize_qr_code(_SAMPLE_QR))
        assert len(client.calls) == 1
        assert client.calls[0]["path"].endswith("/tmp-auth/scan")


# --- api.py: _post's retry parameter ----------------------------------------


class TestPostRetryParameter:
    def test_retry_false_only_attempts_once(self):
        client = object.__new__(DeepalClient)
        client.enable_api_logging = False
        client.base_url = "https://example.test"
        client.gateway_prefix = "/intl-app-gw"
        client._session = types.SimpleNamespace()
        client._headers = lambda **_: {}
        attempts = []

        class _Boom:
            async def __aenter__(self):
                attempts.append(1)
                raise TimeoutError("slow")

            async def __aexit__(self, *exc):
                return False

        def fake_request(method, url, **kwargs):
            return _Boom()

        client._session.request = fake_request

        async def fake_sleep(_delay):
            return None

        import custom_components.deepal.api as api_module

        orig_sleep = api_module.asyncio.sleep
        api_module.asyncio.sleep = fake_sleep
        try:
            with pytest.raises(DeepalApiError, match="after 1 attempt"):
                asyncio.run(client._post("/x", {}, retry=False))
        finally:
            api_module.asyncio.sleep = orig_sleep
        assert len(attempts) == 1


# --- api.py: locationGeo mapping in _mqtt_condition_from_params ------------


class TestMqttLocationMapping:
    def test_maps_location_fields_and_aliases(self):
        mapped = _mqtt_condition_from_params(
            {
                "lat": "51.5007",
                "carLocationLatitude": "99",
                "lng": "0.0",
                "alti": "15.0",
                "heading": "0.0",
                "satNum": "8",
                "gpsTime": "2026-01-01 12:00:00",
                "locationSwitch": 1,
            }
        )
        assert mapped["locationGeo"] == {
            "lat": "51.5007",
            "lng": "0.0",
            "alti": "15.0",
            "heading": "0.0",
            "satNum": "8",
            "gpsTime": "2026-01-01 12:00:00",
            "locationSwitch": 1,
        }

    def test_car_location_aliases_when_lat_lng_absent(self):
        mapped = _mqtt_condition_from_params(
            {
                "carLocationLatitude": "51.5",
                "carLocationLongitude": "-0.12",
                "gpsTime": "2026-11-25 12:00:00",
                "locationSwitch": "1",
            }
        )
        assert mapped["locationGeo"]["lat"] == "51.5"
        assert mapped["locationGeo"]["lng"] == "-0.12"

    def test_location_switch_alone_is_mapped(self):
        mapped = _mqtt_condition_from_params({"locationSwitch": 0, "soc": "80"})
        assert mapped["locationGeo"]["locationSwitch"] == 0
        assert mapped["locationGeo"]["lat"] is None

    def test_unrelated_params_omit_location(self):
        mapped = _mqtt_condition_from_params({"soc": "80", "totalOdometer": "10"})
        assert "locationGeo" not in mapped


# --- device_tracker.py ------------------------------------------------------

_LIVE = {
    "lng": "0.0",
    "lat": "51.5007",
    "alti": "15.0",
    "gpsTime": "2026-01-01 12:00:00",
    "satNum": "8",
    "heading": "0.0",
    "locationSwitch": 1,
}
_OFF = {
    "lat": "0.0",
    "lng": "0.0",
    "alti": "0.0",
    "heading": "0.0",
    "satNum": "0",
    "gpsTime": "2000-01-01 00:00:00",
    "locationSwitch": 0,
}


class _FakeCoordinator:
    vehicle_id = "veh-1"

    def __init__(self, condition):
        self.data = {"condition": condition, "vehicle": {"carName": "Deepal"}}


def _tracker(location_geo):
    condition = {} if location_geo is None else {"locationGeo": location_geo}
    coordinator = _FakeCoordinator(condition)
    tracker = DeepalLocationTracker(coordinator)
    tracker.coordinator = coordinator
    return tracker


class TestLocationTracker:
    def test_entity_metadata(self):
        tracker = _tracker(_LIVE)
        assert tracker._attr_translation_key == "location"
        assert tracker._attr_icon == "mdi:car"
        assert tracker._attr_unique_id == "veh-1_location"

    def test_real_latitude_with_zero_longitude_passes_through(self):
        tracker = _tracker(_LIVE)
        assert tracker.latitude == float("51.5007")
        assert tracker.longitude == 0.0
        assert tracker.extra_state_attributes == {
            "altitude": 15.0,
            "heading": 0.0,
            "satellites": 8,
            "gps_time": "2026-01-01 12:00:00",
            "location_switch": True,
        }

    def test_zero_latitude_with_real_longitude_passes_through(self):
        tracker = _tracker({**_LIVE, "lat": "0.0", "lng": "1.2"})
        assert (tracker.latitude, tracker.longitude) == (0.0, 1.2)

    @pytest.mark.parametrize(
        ("name", "location_geo"),
        [
            ("missing", None),
            ("not a dict", "48.8,2.3"),
            ("switch off", {**_LIVE, "locationSwitch": 0}),
            ("switch off string", {**_LIVE, "locationSwitch": "0"}),
            ("sentinel time", {**_LIVE, "gpsTime": "2000-01-01 00:00:00"}),
            ("blank time", {**_LIVE, "gpsTime": "  "}),
            ("missing time", {k: v for k, v in _LIVE.items() if k != "gpsTime"}),
            ("both zero", {**_LIVE, "lat": "0.0", "lng": "0.0"}),
            ("both zero numbers", {**_LIVE, "lat": 0, "lng": 0.0}),
            ("unparsed lat", {**_LIVE, "lat": "nope"}),
            ("non finite", {**_LIVE, "lng": "nan"}),
            ("cloud off payload", _OFF),
        ],
    )
    def test_unavailable_when_uninitialised_or_off(self, name, location_geo):
        tracker = _tracker(location_geo)
        assert (tracker.latitude, tracker.longitude) == (None, None)

    def test_off_payload_still_exposes_switch(self):
        attrs = _tracker(_OFF).extra_state_attributes
        assert attrs["altitude"] == 0.0
        assert attrs["satellites"] == 0
        assert attrs["gps_time"] == "2000-01-01 00:00:00"
        assert attrs["location_switch"] is False


class TestDeviceTrackerSetup:
    def test_adds_one_tracker(self):
        entities = []
        entry = types.SimpleNamespace(runtime_data=_FakeCoordinator({}))
        asyncio.run(device_tracker.async_setup_entry(None, entry, entities.extend))
        assert len(entities) == 1
        assert isinstance(entities[0], DeepalLocationTracker)


# --- coordinator.py: async_authorize_qr_code and the repair issue ----------


class _FakeIssueRegistry:
    def __init__(self):
        self.created = []
        self.deleted = []

    def async_create_issue(self, hass, domain, issue_id, **kwargs):
        self.created.append(issue_id)

    def async_delete_issue(self, hass, domain, issue_id):
        self.deleted.append(issue_id)

    IssueSeverity = types.SimpleNamespace(WARNING="warning", ERROR="error")


class _FakeQrClient:
    def __init__(self, *, results=None, error=None):
        self._results = list(results or [])
        self._error = error
        self.calls = []

    async def authorize_qr_code(self, qr_code_or_url):
        self.calls.append(qr_code_or_url)
        if self._error is not None:
            err, self._error = self._error, None
            raise err
        return self._results.pop(0) if self._results else {"qr_code": "x"}


def _coordinator(monkeypatch, *, client, fake_ir):
    coordinator = object.__new__(DeepalDataUpdateCoordinator)
    coordinator.client = client
    coordinator.entry = types.SimpleNamespace(entry_id="entry-1", data={})
    coordinator.hass = types.SimpleNamespace(
        config_entries=types.SimpleNamespace(async_update_entry=lambda *a, **k: None)
    )
    coordinator.async_request_refresh = lambda: _noop()
    monkeypatch.setattr(coordinator_module, "ir", fake_ir)
    return coordinator


async def _noop():
    return None


class TestAsyncAuthorizeQrCode:
    def test_success_deletes_the_issue_and_requests_a_refresh(self, monkeypatch):
        fake_ir = _FakeIssueRegistry()
        client = _FakeQrClient(results=[{"qr_code": "abc"}])
        coordinator = _coordinator(monkeypatch, client=client, fake_ir=fake_ir)
        result = asyncio.run(coordinator.async_authorize_qr_code(_SAMPLE_QR))
        assert result == {"qr_code": "abc"}
        assert fake_ir.deleted == ["entry-1_location_permission"]

    def test_auth_error_refreshes_tokens_once_then_retries(self, monkeypatch):
        fake_ir = _FakeIssueRegistry()
        client = _FakeQrClient(error=DeepalAuthError("expired"), results=[{"qr_code": "retried"}])

        async def fake_refresh():
            return None

        coordinator = _coordinator(monkeypatch, client=client, fake_ir=fake_ir)
        coordinator._async_refresh_and_persist_tokens = fake_refresh
        result = asyncio.run(coordinator.async_authorize_qr_code(_SAMPLE_QR))
        assert result == {"qr_code": "retried"}
        assert len(client.calls) == 2

    def test_api_error_after_refresh_raises_config_entry_auth_failed(self, monkeypatch):
        fake_ir = _FakeIssueRegistry()
        client = _FakeQrClient(error=DeepalAuthError("expired"))

        async def failing_refresh():
            raise DeepalApiError("refresh failed")

        coordinator = _coordinator(monkeypatch, client=client, fake_ir=fake_ir)
        coordinator._async_refresh_and_persist_tokens = failing_refresh
        with pytest.raises(coordinator_module.ConfigEntryAuthFailed):
            asyncio.run(coordinator.async_authorize_qr_code(_SAMPLE_QR))


class TestSyncLocationPermissionIssue:
    def test_switch_off_creates_the_issue(self, monkeypatch):
        fake_ir = _FakeIssueRegistry()
        coordinator = _coordinator(monkeypatch, client=None, fake_ir=fake_ir)
        coordinator._async_sync_location_permission_issue({"locationGeo": {"locationSwitch": 0}})
        assert fake_ir.created == ["entry-1_location_permission"]

    def test_switch_on_deletes_the_issue(self, monkeypatch):
        fake_ir = _FakeIssueRegistry()
        coordinator = _coordinator(monkeypatch, client=None, fake_ir=fake_ir)
        coordinator._async_sync_location_permission_issue({"locationGeo": {"locationSwitch": 1}})
        assert fake_ir.deleted == ["entry-1_location_permission"]

    def test_no_locationgeo_does_nothing(self, monkeypatch):
        fake_ir = _FakeIssueRegistry()
        coordinator = _coordinator(monkeypatch, client=None, fake_ir=fake_ir)
        coordinator._async_sync_location_permission_issue({})
        assert fake_ir.created == []
        assert fake_ir.deleted == []
