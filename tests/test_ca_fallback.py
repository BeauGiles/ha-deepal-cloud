"""CA gateway token fallback and the REST fallback for MQTT telemetry (danperks issue #11)."""

from __future__ import annotations

import asyncio
import types

import pytest

from custom_components.deepal import coordinator as coordinator_module
from custom_components.deepal.api import DeepalApiError, DeepalAuthError, DeepalClient
from custom_components.deepal.coordinator import DeepalDataUpdateCoordinator

REJECTED = "Deepal API error for /user-apigw/vot-connect-conf-center/api/device/getConnConf: APIGW_-1_7_01_004 invalided token"


def make_client(*, access="Bearer ACCESS", cac="CAC", script=None):
    client = object.__new__(DeepalClient)
    client.tokens = types.SimpleNamespace(access_token=access)
    client.cac_token = cac
    client._ca_tsp_token = None
    client.calls = []
    results = list(script or [{"ok": True}])

    async def fake_post(path, payload=None, **kwargs):
        overrides = kwargs.get("header_overrides")
        client.calls.append(overrides["X-Tsp-User-Token"] if overrides else None)
        outcome = results.pop(0) if len(results) > 1 else results[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client._post = fake_post
    return client


def call(client):
    return asyncio.run(client._post_ca("/user-apigw/x", {}))


class TestTokenFallback:
    def test_the_cac_token_is_tried_first(self):
        client = make_client()
        assert call(client) == {"ok": True}
        assert client.calls == ["CAC"]
        assert client._ca_tsp_token == "CAC"

    def test_apigw_rejection_falls_back_to_the_access_token_and_remembers_it(self):
        client = make_client(script=[DeepalApiError(REJECTED), {"ok": True}])
        assert call(client) == {"ok": True}
        assert client.calls == ["CAC", "ACCESS"]  # "Bearer " is stripped from the access half
        assert client._ca_tsp_token == "ACCESS"
        client.calls.clear()
        call(client)
        assert client.calls == ["ACCESS"]  # the remembered token goes first, no second attempt

    def test_both_rejected_raises_after_trying_each_once(self):
        client = make_client(script=[DeepalApiError(REJECTED)])
        with pytest.raises(DeepalApiError, match="APIGW_"):
            call(client)
        assert client.calls == ["CAC", "ACCESS"]
        assert client._ca_tsp_token is None

    def test_other_errors_are_not_retried(self):
        client = make_client(script=[DeepalApiError("Deepal HTTP error 500 for /x")])
        with pytest.raises(DeepalApiError, match="500"):
            call(client)
        assert client.calls == ["CAC"]

    def test_authentication_errors_are_not_retried(self):
        client = make_client(script=[DeepalAuthError("Deepal auth failed: APP_1_1_02_005 logged in on another device")])
        with pytest.raises(DeepalAuthError):
            call(client)
        assert client.calls == ["CAC"]

    def test_without_a_cac_token_only_the_access_half_is_sent(self):
        client = make_client(cac=None)
        call(client)
        assert client.calls == ["ACCESS"]

    def test_composite_login_token_is_split(self):
        client = make_client(access="Bearer JWTA|JWTB", cac=None)
        call(client)
        assert client.calls == ["JWTA"]

    def test_no_tokens_means_a_plain_request(self):
        client = make_client(access="", cac=None)
        call(client)
        assert client.calls == [None]

    def test_a_remembered_token_that_is_no_longer_valid_is_ignored(self):
        client = make_client()
        client._ca_tsp_token = "OLD-TOKEN-BEFORE-REFRESH"
        call(client)
        assert client.calls == ["CAC"]


# ---------------------------------------------------------------- coordinator


class FakeClient:
    def __init__(self, *, mqtt=None, rest=None):
        self.mqtt = mqtt if mqtt is not None else [{"vehicleStatus": {"soc": 80}, "src": "mqtt"}]
        self.rest = rest if rest is not None else [{"vehicleStatus": {"soc": 55}, "src": "rest"}]
        self.mqtt_calls = 0
        self.rest_calls = 0

    @staticmethod
    def _next(items):
        item = items.pop(0) if len(items) > 1 else items[0]
        if isinstance(item, Exception):
            raise item
        return item

    async def mqtt_condition(self, vehicle_id):
        self.mqtt_calls += 1
        return self._next(self.mqtt)

    async def condition(self, vehicle_id):
        self.rest_calls += 1
        return self._next(self.rest)


@pytest.fixture
def clock(monkeypatch):
    state = {"t": 1000.0}
    monkeypatch.setattr(
        coordinator_module,
        "time",
        types.SimpleNamespace(monotonic=lambda: state["t"], time=lambda: state["t"]),
    )
    return state


def make(client):
    coordinator = object.__new__(DeepalDataUpdateCoordinator)
    coordinator.client = client
    coordinator.vehicle_id = "1"
    coordinator._mqtt_failures = 0
    coordinator._mqtt_next_attempt = 0.0
    coordinator._mqtt_last_error = None
    coordinator.mqtt_fallback_active = False
    coordinator._rate_limited_until = 0.0
    coordinator._last_session_refresh = None
    return coordinator


def fetch(coordinator):
    return asyncio.run(coordinator._async_mqtt_condition_with_fallback())


class TestRestFallback:
    def test_healthy_mqtt_is_used_and_nothing_falls_back(self, clock):
        client = FakeClient()
        coordinator = make(client)
        assert fetch(coordinator)["src"] == "mqtt"
        assert client.rest_calls == 0
        assert not coordinator.mqtt_fallback_active

    def test_mqtt_failure_uses_the_rest_condition_and_backs_off(self, clock, caplog):
        client = FakeClient(mqtt=[DeepalApiError(REJECTED)])
        coordinator = make(client)
        with caplog.at_level("WARNING"):
            assert fetch(coordinator)["src"] == "rest"
        assert coordinator.mqtt_fallback_active
        assert coordinator._mqtt_failures == 1
        assert "MQTT telemetry unavailable" in caplog.text

        clock["t"] += 30  # still inside the 60 s back-off: MQTT is not tried again
        assert fetch(coordinator)["src"] == "rest"
        assert client.mqtt_calls == 1
        assert client.rest_calls == 2

    def test_warning_is_logged_once_not_every_poll(self, clock, caplog):
        coordinator = make(FakeClient(mqtt=[DeepalApiError(REJECTED)]))
        with caplog.at_level("WARNING"):
            for _ in range(4):
                fetch(coordinator)
                clock["t"] += 1000
        assert caplog.text.count("MQTT telemetry unavailable") == 1

    def test_mqtt_is_retried_after_the_back_off_and_recovery_clears_the_fallback(self, clock, caplog):
        client = FakeClient(mqtt=[DeepalApiError(REJECTED), {"vehicleStatus": {"soc": 80}, "src": "mqtt"}])
        coordinator = make(client)
        fetch(coordinator)
        clock["t"] += 61
        with caplog.at_level("INFO"):
            assert fetch(coordinator)["src"] == "mqtt"
        assert client.mqtt_calls == 2
        assert not coordinator.mqtt_fallback_active
        assert coordinator._mqtt_failures == 0
        assert coordinator._mqtt_next_attempt == 0.0
        assert "working again" in caplog.text

    def test_back_off_doubles_and_is_capped(self, clock):
        coordinator = make(FakeClient(mqtt=[DeepalApiError(REJECTED)]))
        delays = []
        for _ in range(6):
            before = clock["t"]
            fetch(coordinator)
            delays.append(coordinator._mqtt_next_attempt - before)
            clock["t"] = coordinator._mqtt_next_attempt  # wait out the back-off
        assert delays == [60, 120, 240, 480, 600, 600]

    def test_authentication_errors_are_not_swallowed(self, clock):
        client = FakeClient(mqtt=[DeepalAuthError("Deepal auth failed: APP_1_1_02_005")])
        with pytest.raises(DeepalAuthError):
            fetch(make(client))
        assert client.rest_calls == 0

    def test_an_empty_rest_condition_is_not_used(self, clock):
        client = FakeClient(mqtt=[DeepalApiError(REJECTED)], rest=[{"vehicleStatus": {}, "door": {}}])
        coordinator = make(client)
        with pytest.raises(DeepalApiError, match="APIGW_"):
            fetch(coordinator)
        assert not coordinator.mqtt_fallback_active

    def test_a_failing_rest_condition_raises_the_original_mqtt_error(self, clock):
        client = FakeClient(mqtt=[DeepalApiError(REJECTED)], rest=[DeepalApiError("REST down")])
        with pytest.raises(DeepalApiError, match="APIGW_"):
            fetch(make(client))

    def test_rest_condition_counts_if_any_status_field_has_a_value(self, clock):
        client = FakeClient(mqtt=[DeepalApiError(REJECTED)], rest=[{"vehicleStatus": {"soc": None, "drvMileage": 120}}])
        assert fetch(make(client))["vehicleStatus"]["drvMileage"] == 120
