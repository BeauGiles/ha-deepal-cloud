"""CA bootstrap reuse and alternate routes, malformed MQTT packets, rate limits (Sunek0 review)."""

from __future__ import annotations

import asyncio
import struct
import types
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.deepal import coordinator as coordinator_module
from custom_components.deepal.api import (
    DeepalApiError,
    DeepalAuthError,
    DeepalClient,
    DeepalRateLimitError,
    DeepalSessionInvalidated,
    _exception_for_http_error,
    _mqtt_command_result_error,
    _mqtt_try_parse_publish,
    _session_invalid_message,
    parse_retry_after,
)
from custom_components.deepal.coordinator import DeepalDataUpdateCoordinator

HomeAssistantError = coordinator_module.HomeAssistantError
UpdateFailed = coordinator_module.UpdateFailed

CONFIG = {"mqttConnectionInfos": [{"clusterInfos": []}]}
REJECTED = DeepalApiError("Deepal API error for /x: APIGW_-1_7_01_004 invalided token")

# ---------------------------------------------------------------- Retry-After / HTTP errors


class TestParseRetryAfter:
    NOW = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)

    @pytest.mark.parametrize(("value", "expected"), [("120", 120.0), ("1.5", 1.5), (" 30 ", 30.0), (45, 45.0)])
    def test_delta_seconds(self, value, expected):
        assert parse_retry_after(value) == expected

    def test_http_date_in_the_future(self):
        future = (self.NOW + timedelta(seconds=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        assert parse_retry_after(future, now=self.NOW) == 90.0

    def test_http_date_in_the_past_is_ignored(self):
        past = (self.NOW - timedelta(seconds=90)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        assert parse_retry_after(past, now=self.NOW) is None

    @pytest.mark.parametrize("value", [None, "", "  ", "soon", "-5", "0", "nan", "inf", "Wed, 99 Foo 2026"])
    def test_unusable_values(self, value):
        assert parse_retry_after(value) is None


class TestHttpErrors:
    def test_429_is_a_rate_limit_with_the_gateways_wait(self):
        err = _exception_for_http_error(429, {"Retry-After": "75"}, "/x")
        assert isinstance(err, DeepalRateLimitError)
        assert err.retry_after == 75.0

    def test_429_without_a_header(self):
        err = _exception_for_http_error(429, {}, "/x")
        assert isinstance(err, DeepalRateLimitError) and err.retry_after is None
        assert isinstance(_exception_for_http_error(429, None, "/x"), DeepalRateLimitError)

    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_statuses(self, status):
        assert isinstance(_exception_for_http_error(status, {}, "/x"), DeepalAuthError)

    def test_other_statuses_are_plain_errors(self):
        err = _exception_for_http_error(500, {}, "/x")
        assert type(err) is DeepalApiError and "500" in str(err)


class TestSessionInvalidMessage:
    @pytest.mark.parametrize(
        "message",
        ["invalided token", "Invalid token", "token expired", "The login Token has expired", "token is invalid"],
    )
    def test_recognised(self, message):
        assert _session_invalid_message(message)

    @pytest.mark.parametrize("message", [None, "", "operation failed", "invalid captcha", "rcToken is invalid", "token ok"])
    def test_not_recognised(self, message):
        assert not _session_invalid_message(message)

    def test_it_is_not_an_authentication_error(self):
        # An account the CA gateway always rejects must not be pushed into a re-login loop.
        assert issubclass(DeepalSessionInvalidated, DeepalApiError)
        assert not issubclass(DeepalSessionInvalidated, DeepalAuthError)


# ---------------------------------------------------------------- CA bootstrap reuse


def make_client(*, responses):
    """responses: {path-substring: [result or exception, ...]} consumed in order."""
    client = object.__new__(DeepalClient)
    client.device_id = "dev"
    client.user_id = "user"
    client._mqtt_config_cache = {}
    client._mqtt_token_cache = None
    client.calls = []

    async def fake_post_ca(path, payload=None):
        client.calls.append(path.rsplit("/", 1)[-1])
        for fragment, outcomes in responses.items():
            if fragment in path:
                outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise AssertionError(f"unexpected call {path}")

    client._post_ca = fake_post_ca
    return client


@pytest.fixture
def clock(monkeypatch):
    state = {"t": 1000.0}
    from custom_components.deepal import api

    monkeypatch.setattr(api, "time", types.SimpleNamespace(monotonic=lambda: state["t"], time=lambda: state["t"]))
    return state


class TestCache:
    def test_config_is_reused_within_the_ttl_and_refetched_after(self, clock):
        client = make_client(responses={"getConnConf": [CONFIG]})
        for _ in range(3):
            assert asyncio.run(client._mqtt_config("1")) == CONFIG
        assert client.calls == ["getConnConf"]
        clock["t"] += 661  # past MQTT_CONFIG_TTL
        asyncio.run(client._mqtt_config("1"))
        assert client.calls == ["getConnConf", "getConnConf"]

    def test_config_is_cached_per_vehicle(self, clock):
        client = make_client(responses={"getConnConf": [CONFIG]})
        asyncio.run(client._mqtt_config("1"))
        asyncio.run(client._mqtt_config("2"))
        assert client.calls == ["getConnConf", "getConnConf"]

    def test_token_is_reused_for_a_minute(self, clock):
        client = make_client(responses={"getAuthTokenByUserId": [{"authToken": "T1"}, {"authToken": "T2"}]})
        assert asyncio.run(client._mqtt_token()) == "T1"
        clock["t"] += 59
        assert asyncio.run(client._mqtt_token()) == "T1"
        clock["t"] += 2
        assert asyncio.run(client._mqtt_token()) == "T2"

    def test_force_bypasses_the_cache(self, clock):
        client = make_client(responses={"getConnConf": [CONFIG]})
        asyncio.run(client._mqtt_config("1"))
        asyncio.run(client._mqtt_config("1", force=True))
        assert client.calls == ["getConnConf", "getConnConf"]

    def test_a_failed_read_drops_the_cached_bootstrap(self, clock):
        client = make_client(responses={"getConnConf": [CONFIG], "getAuthTokenByUserId": [{"authToken": "T"}]})

        async def failing_read(config, token):
            raise DeepalApiError("broker rejected connection")

        client._mqtt_read_condition = failing_read
        with pytest.raises(DeepalApiError):
            asyncio.run(client.mqtt_condition("1"))
        assert client._mqtt_config_cache == {} and client._mqtt_token_cache is None

    def test_a_successful_read_keeps_the_cache(self, clock):
        client = make_client(responses={"getConnConf": [CONFIG], "getAuthTokenByUserId": [{"authToken": "T"}]})

        async def read(config, token):
            return {"soc": 1}

        client._mqtt_read_condition = read
        asyncio.run(client.mqtt_condition("1"))
        asyncio.run(client.mqtt_condition("1"))
        assert client.calls == ["getConnConf", "getAuthTokenByUserId"]


class TestAlternateRoutes:
    def test_config_falls_back_to_the_alternate_route(self, clock):
        client = make_client(responses={"getConnConf": [REJECTED], "appGetCarConfFunc": [CONFIG]})
        assert asyncio.run(client._mqtt_config("1")) == CONFIG
        assert client.calls == ["getConnConf", "appGetCarConfFunc"]

    def test_an_alternate_without_connection_info_is_not_used(self, clock):
        # appGetCarConfFunc may return only the function tree.
        client = make_client(responses={"getConnConf": [REJECTED], "appGetCarConfFunc": [{"carConfigJson": "{}"}]})
        with pytest.raises(DeepalApiError, match="APIGW_"):
            asyncio.run(client._mqtt_config("1"))

    def test_a_failing_alternate_raises_the_original_error(self, clock):
        client = make_client(responses={"getConnConf": [REJECTED], "appGetCarConfFunc": [DeepalApiError("alt down")]})
        with pytest.raises(DeepalApiError, match="APIGW_"):
            asyncio.run(client._mqtt_config("1"))

    def test_token_falls_back_to_the_app_route(self, clock):
        client = make_client(responses={"getAuthTokenByUserId": [REJECTED, {"authToken": "ALT"}]})
        assert asyncio.run(client._mqtt_token()) == "ALT"
        assert client.calls == ["getAuthTokenByUserId", "getAuthTokenByUserId"]

    def test_an_alternate_token_response_without_a_token_raises_the_original(self, clock):
        client = make_client(responses={"getAuthTokenByUserId": [REJECTED, {}]})
        with pytest.raises(DeepalApiError, match="APIGW_"):
            asyncio.run(client._mqtt_token())

    @pytest.mark.parametrize("error", [DeepalRateLimitError("slow down"), DeepalAuthError("auth failed")])
    def test_rate_limits_and_auth_errors_skip_the_alternates(self, clock, error):
        client = make_client(responses={"getConnConf": [error], "appGetCarConfFunc": [CONFIG]})
        with pytest.raises(type(error)):
            asyncio.run(client._mqtt_config("1"))
        assert client.calls == ["getConnConf"]


# ---------------------------------------------------------------- malformed MQTT packets


def publish(topic=b"$vdp/x/y", payload=b'{"a": 1}', qos=0, packet_id=7, truncate_topic=False):
    first = 0x30 | (qos << 1)
    body = struct.pack("!H", len(topic) + (50 if truncate_topic else 0)) + topic
    if qos:
        body += struct.pack("!H", packet_id)
    return first, body + payload


class TestMalformedPackets:
    def test_a_good_packet_parses(self):
        assert _mqtt_try_parse_publish(*publish()) == ("$vdp/x/y", {"a": 1}, None)

    def test_qos1_packet_id_is_returned(self):
        assert _mqtt_try_parse_publish(*publish(qos=1, packet_id=42))[2] == 42

    @pytest.mark.parametrize(
        "packet",
        [
            (0x30, b""),  # nothing at all
            (0x30, b"\x00"),  # truncated topic length
            (0x30, b"\x00\x09abc"),  # topic shorter than declared: payload is then garbage
            (0x32, struct.pack("!H", 1) + b"t" + b"\x00"),  # QoS 1 with a truncated packet id
            (0x30, struct.pack("!H", 1) + b"t" + b"not json"),
            (0x30, struct.pack("!H", 1) + b"t" + b"\xff\xfe"),  # not valid UTF-8
            (0x30, struct.pack("!H", 1) + b"t" + b"[1, 2]"),  # JSON, but not an object
            (0x30, struct.pack("!H", 1) + b"t" + b"42"),
        ],
    )
    def test_malformed_packets_are_skipped_not_raised(self, packet):
        assert _mqtt_try_parse_publish(*packet) is None


# ---------------------------------------------------------------- success codes


class TestSuccessCodes:
    @staticmethod
    def error(code):
        return _mqtt_command_result_error({"rs": [{"code": code}]}, "secret", "req")

    @pytest.mark.parametrize("code", ["00000", "000000", "0", 0, 200, "OK"])
    def test_success(self, code):
        assert self.error(code) is None

    def test_failure_still_reported(self):
        assert self.error("VVCC_-1_-1_02_023")


# ---------------------------------------------------------------- REST humidity


class TestRestHumidity:
    @staticmethod
    def condition(value):
        client = object.__new__(DeepalClient)
        client.fetch_location = False
        client.last_position = None
        client._location_state = None

        async def fake_post(path, payload=None, **_):
            return {"hvac": {"insideHumidity": value, "insideTemp": 240}}

        client._post = fake_post
        return asyncio.run(client.condition("1"))["hvac"]

    @pytest.mark.parametrize(("raw", "expected"), [(41.0, 41.0), (453, 45.3), (100, 100.0), (1500, None), (-3, None), (None, None)])
    def test_percentage_or_tenths(self, raw, expected):
        assert self.condition(raw)["insideHumidity"] == expected

    def test_other_values_untouched(self):
        assert self.condition(41.0)["insideTemp"] == 240


# ---------------------------------------------------------------- coordinator


def make_coordinator(client):
    coordinator = object.__new__(DeepalDataUpdateCoordinator)
    coordinator.client = client
    coordinator.vehicle_id = "1"
    coordinator.entry = types.SimpleNamespace(data={})
    coordinator.refresh_failure_count = 0
    coordinator.last_refresh_failure = None
    coordinator._mqtt_failures = 0
    coordinator._mqtt_next_attempt = 0.0
    coordinator._mqtt_last_error = None
    coordinator.mqtt_fallback_active = False
    coordinator._rate_limited_until = 0.0
    coordinator._last_session_refresh = None
    coordinator._record_refresh_failure = lambda err: None
    return coordinator


@pytest.fixture
def cclock(monkeypatch):
    state = {"t": 5000.0}
    monkeypatch.setattr(coordinator_module, "time", types.SimpleNamespace(monotonic=lambda: state["t"], time=lambda: state["t"]))
    return state


class TestRateLimitBackoff:
    def make(self, error):
        class Client:
            calls = 0

            async def vehicles(self_inner):
                Client.calls += 1
                raise error

        coordinator = make_coordinator(Client())
        coordinator._client_cls = Client
        return coordinator

    def test_a_429_stops_further_calls_until_the_wait_is_over(self, cclock):
        coordinator = self.make(DeepalRateLimitError("429", retry_after=300))
        with pytest.raises(UpdateFailed):
            asyncio.run(coordinator._async_update_data())
        assert coordinator._client_cls.calls == 1
        assert coordinator._rate_limited_until == 5000.0 + 300

        cclock["t"] += 100  # still inside the wait: no API call at all
        with pytest.raises(UpdateFailed, match="rate limited"):
            asyncio.run(coordinator._async_update_data())
        assert coordinator._client_cls.calls == 1

        cclock["t"] += 201  # wait over: the API is called again
        with pytest.raises(UpdateFailed):
            asyncio.run(coordinator._async_update_data())
        assert coordinator._client_cls.calls == 2

    @pytest.mark.parametrize(("retry_after", "expected"), [(None, 60), (5, 60), (300, 300), (999999, 3600)])
    def test_the_wait_is_bounded(self, cclock, retry_after, expected):
        coordinator = self.make(DeepalRateLimitError("429", retry_after=retry_after))
        with pytest.raises(UpdateFailed):
            asyncio.run(coordinator._async_update_data())
        assert coordinator._rate_limited_until == 5000.0 + expected

    def test_a_rate_limit_while_refreshing_the_session_never_starts_a_re_login(self, cclock):
        class Client:
            async def vehicles(self):
                raise DeepalAuthError("token expired")

            async def refresh_tokens(self):
                raise DeepalRateLimitError("429", retry_after=120)

        coordinator = make_coordinator(Client())
        with pytest.raises(UpdateFailed):  # not ConfigEntryAuthFailed
            asyncio.run(coordinator._async_update_data())
        assert coordinator._rate_limited_until == 5000.0 + 120

    def test_a_rate_limit_is_not_swallowed_by_the_mqtt_fallback(self, cclock):
        class Client:
            rest_calls = 0

            async def mqtt_condition(self, vehicle_id):
                raise DeepalRateLimitError("429", retry_after=60)

            async def condition(self, vehicle_id):
                Client.rest_calls += 1
                return {"vehicleStatus": {"soc": 1}}

        coordinator = make_coordinator(Client())
        with pytest.raises(DeepalRateLimitError):
            asyncio.run(coordinator._async_mqtt_condition_with_fallback())
        assert Client.rest_calls == 0  # no extra calls while the gateway is throttling


class TestSessionRefreshOnInvalid:
    def make(self, *, mqtt, refresh_error=None):
        class Client:
            def __init__(self_inner):
                self_inner.mqtt_calls = 0
                self_inner.refreshes = 0

            async def mqtt_condition(self_inner, vehicle_id):
                self_inner.mqtt_calls += 1
                outcome = mqtt.pop(0) if len(mqtt) > 1 else mqtt[0]
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

            async def refresh_tokens(self_inner):
                self_inner.refreshes += 1
                if refresh_error:
                    raise refresh_error
                return types.SimpleNamespace(access_token="NEW", refresh_token="NEWR")

            async def condition(self_inner, vehicle_id):
                return {}

        client = Client()
        coordinator = make_coordinator(client)
        persisted = []
        coordinator.hass = types.SimpleNamespace(
            config_entries=types.SimpleNamespace(async_update_entry=lambda entry, data: persisted.append(data))
        )
        coordinator.persisted = persisted
        return coordinator, client

    def test_refreshes_the_session_once_then_retries_and_succeeds(self, cclock):
        coordinator, client = self.make(mqtt=[DeepalSessionInvalidated("invalided token"), {"vehicleStatus": {"soc": 9}}])
        assert asyncio.run(coordinator._async_mqtt_condition_with_fallback())["vehicleStatus"]["soc"] == 9
        assert client.refreshes == 1 and client.mqtt_calls == 2
        assert coordinator.persisted and coordinator.persisted[0]["access_token"] == "NEW"  # saved, not just in memory

    def test_does_not_refresh_again_within_the_interval(self, cclock):
        coordinator, client = self.make(mqtt=[DeepalSessionInvalidated("invalided token")])
        for _ in range(3):
            try:
                asyncio.run(coordinator._async_mqtt_condition_with_fallback())
            except DeepalApiError:
                pass
            cclock["t"] += 700  # past the MQTT back-off, still inside the hour
        assert client.refreshes == 1

    def test_a_failed_refresh_falls_back_and_never_raises_an_auth_error(self, cclock):
        coordinator, client = self.make(
            mqtt=[DeepalSessionInvalidated("invalided token")],
            refresh_error=DeepalAuthError("refresh token expired"),
        )
        with pytest.raises(DeepalSessionInvalidated):  # the original error, not an auth failure
            asyncio.run(coordinator._async_mqtt_condition_with_fallback())
        assert coordinator._mqtt_failures == 1
