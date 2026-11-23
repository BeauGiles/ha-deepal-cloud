"""The S05 live MQTT session: client.mqtt_live_condition_stream and the
coordinator's reconnect loop around it.
"""

from __future__ import annotations

import asyncio
import types

import pytest

from custom_components.deepal import coordinator as coordinator_module
from custom_components.deepal.api import DeepalApiError, DeepalClient, _mqtt_publish_packet
from custom_components.deepal.coordinator import DeepalDataUpdateCoordinator

# --- a fake broker-side TCP stream ------------------------------------------


class FakeReader:
    def __init__(self, packets: list[bytes]):
        self._buffer = b"".join(packets)
        self._pos = 0

    async def readexactly(self, n: int) -> bytes:
        if self._pos + n > len(self._buffer):
            # No more scripted bytes: block "forever" so the caller's own
            # asyncio.wait_for(..., timeout=...) is what ends the read, the
            # same way a real idle broker connection would behave.
            await asyncio.sleep(1_000_000)
        data = self._buffer[self._pos : self._pos + n]
        self._pos += n
        return data


class FakeWriter:
    def __init__(self):
        self.written: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        pass


def _packet(first: int, body: bytes) -> bytes:
    from custom_components.deepal.api import _mqtt_remaining_length

    return bytes([first]) + _mqtt_remaining_length(len(body)) + body


def _publish(topic: str, payload: dict) -> bytes:
    # _mqtt_publish_packet already builds a complete, valid QoS0 PUBLISH
    # packet (first byte 0x30), so it can be used directly as a scripted
    # broker->client frame too.
    return _mqtt_publish_packet(topic, payload)


CONNACK_OK = _packet(0x20, b"\x00\x00")
SUBACK = _packet(0x90, b"\x00\x01\x00")

SECRET_KEY = "0123456789abcdef"
LOGIN_DID = "device-did"
DEVICE_DID = "device-did"


def secret_payload(req_id="r1"):
    return {"r": req_id, "b": {"mc": "SC6464AAKBEV"}, "rs": [{"params": {"secretKey": SECRET_KEY}}]}


def condition_payload(req_id, params):
    # The real "sers"/"rs" fields are AES-encrypted, which needs the real
    # `cryptography` package - stubbed out everywhere else in this suite, so
    # not available here either. make_client() patches
    # _mqtt_condition_params_from_payload to read this field directly
    # instead of decrypting anything, bypassing that layer for these tests.
    return {"r": req_id, "_test_params": params}


MQTT_CONFIG = {
    "mqttConnectionInfos": [
        {
            "clusterInfos": [{"brokerUrl": "ssl://broker.example", "brokerPort": 8883}],
            "topicInfos": [
                {"msgType": "loginout", "pubTopics": [f"$vdp/{LOGIN_DID}/loginout/req"], "subTopics": []},
                {
                    "msgType": "properties",
                    "pubTopics": [f"$vdp/{DEVICE_DID}/properties/get/req"],
                    "subTopics": [f"$vdp/{DEVICE_DID}/properties/get/res"],
                },
            ],
        }
    ]
}


def make_client():
    client = object.__new__(DeepalClient)
    client.user_id = "u1"
    client.drive_side = None
    client.enable_api_logging = False
    client.last_mqtt_topics = None
    client.last_mqtt_model_code = None
    client._invalidate_mqtt_caches = lambda: None
    # Bypasses the real AES decryption/encryption (see condition_payload's
    # comment) - the request payload's exact content is not under test here.
    client._mqtt_condition_params_from_payload = lambda payload, secret_key: payload.get("_test_params", {})
    client._mqtt_condition_request_payload = lambda device_did, login_did, secret_key, req_id: {"did": device_did}
    return client


def patch_connection(monkeypatch, reader, writer):
    async def fake_open_connection(host, port, ssl=None, server_hostname=None):
        return reader, writer

    async def fake_to_thread(fn, *a):
        return fn(*a)

    import custom_components.deepal.api as api_module

    monkeypatch.setattr(api_module.asyncio, "open_connection", fake_open_connection)
    monkeypatch.setattr(api_module.asyncio, "to_thread", fake_to_thread)


class TestReadConditionStream:
    def test_pushes_and_ends_cleanly_on_timeout(self, monkeypatch):
        client = make_client()
        reader = FakeReader(
            [
                CONNACK_OK,
                SUBACK,
                _publish("$vdp/device-did/properties/get/res", secret_payload()),
                _publish(
                    "$vdp/device-did/properties/get/res",
                    condition_payload("r2", {"soc": 77, "remainedPowerMile": 350}),
                ),
            ]
        )
        writer = FakeWriter()
        patch_connection(monkeypatch, reader, writer)

        pushed = []
        asyncio.run(client._mqtt_read_condition_stream(MQTT_CONFIG, "token", pushed.append, 0.05))

        assert len(pushed) == 1
        assert pushed[0]["vehicleStatus"]["soc"] == 77
        assert writer.closed

    def test_a_second_report_pushes_again_with_accumulated_fields(self, monkeypatch):
        client = make_client()
        reader = FakeReader(
            [
                CONNACK_OK,
                SUBACK,
                _publish("$vdp/device-did/properties/get/res", secret_payload()),
                _publish(
                    "$vdp/device-did/properties/get/res",
                    condition_payload("r2", {"soc": 77}),
                ),
                _publish(
                    "$vdp/device-did/properties/get/res",
                    condition_payload("r3", {"totalOdometer": 1234}),
                ),
            ]
        )
        writer = FakeWriter()
        patch_connection(monkeypatch, reader, writer)

        pushed = []
        asyncio.run(client._mqtt_read_condition_stream(MQTT_CONFIG, "token", pushed.append, 0.05))

        assert len(pushed) == 2
        # The second push still carries the first report's field: deltas
        # accumulate across the connection, not just the latest message.
        assert pushed[0]["vehicleStatus"]["soc"] == 77
        assert pushed[1]["vehicleStatus"]["soc"] == 77
        assert pushed[1]["vehicleStatus"]["totalMileage"] == 1234

    def test_rejects_missing_topics(self, monkeypatch):
        client = make_client()
        patch_connection(monkeypatch, FakeReader([]), FakeWriter())
        with pytest.raises(DeepalApiError):
            asyncio.run(client._mqtt_read_condition_stream({}, "token", lambda c: None, 1))


class TestMqttLiveConditionStream:
    def test_requires_user_id(self):
        client = object.__new__(DeepalClient)
        client.user_id = None
        with pytest.raises(DeepalApiError):
            asyncio.run(client.mqtt_live_condition_stream("v1", lambda c: None))

    def test_invalidates_caches_on_failure(self, monkeypatch):
        client = object.__new__(DeepalClient)
        client.user_id = "u1"
        invalidated = []
        client._invalidate_mqtt_caches = lambda: invalidated.append(True)

        async def failing_config(vehicle_id):
            raise DeepalApiError("boom")

        client._mqtt_config = failing_config
        with pytest.raises(DeepalApiError):
            asyncio.run(client.mqtt_live_condition_stream("v1", lambda c: None))
        assert invalidated == [True]


# --- coordinator._async_live_mqtt_loop reconnect/backoff -------------------


def make_coordinator(monkeypatch, *, cycles):
    """cycles: a list of outcomes, each either None (a clean cycle) or an
    Exception instance (a failed cycle). The loop is stopped after the list
    is exhausted by raising asyncio.CancelledError from the next call.
    """
    coordinator = object.__new__(DeepalDataUpdateCoordinator)
    coordinator.vehicle_id = "v1"
    remaining = list(cycles)
    delays: list[float] = []

    async def fake_stream(vehicle_id, on_condition, duration=None):
        if not remaining:
            raise asyncio.CancelledError
        outcome = remaining.pop(0)
        if outcome is not None:
            raise outcome

    async def fake_sleep(delay):
        delays.append(delay)

    coordinator.client = types.SimpleNamespace(mqtt_live_condition_stream=fake_stream)
    monkeypatch.setattr(coordinator_module.asyncio, "sleep", fake_sleep)
    return coordinator, delays


class TestLiveMqttLoop:
    def test_a_clean_cycle_reconnects_quickly(self, monkeypatch):
        coordinator, delays = make_coordinator(monkeypatch, cycles=[None])
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(coordinator._async_live_mqtt_loop())
        assert delays == [coordinator_module.MQTT_LIVE_RECONNECT_DELAY]

    def test_failures_back_off_and_reset_after_a_clean_cycle(self, monkeypatch):
        coordinator, delays = make_coordinator(
            monkeypatch,
            cycles=[DeepalApiError("a"), DeepalApiError("b"), None, DeepalApiError("c")],
        )
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(coordinator._async_live_mqtt_loop())
        base = coordinator_module.MQTT_LIVE_ERROR_BACKOFF_BASE
        assert delays == [
            base,  # 1st failure
            base * 2,  # 2nd failure (doubled)
            coordinator_module.MQTT_LIVE_RECONNECT_DELAY,  # clean cycle resets the count
            base,  # failure count starts over
        ]


class TestStartStopLiveMqttSession:
    def test_stop_without_start_is_a_no_op(self):
        coordinator = object.__new__(DeepalDataUpdateCoordinator)
        coordinator._live_mqtt_task = None
        asyncio.run(coordinator.stop_live_mqtt_session())

    def test_start_is_idempotent_while_running(self, monkeypatch):
        coordinator = object.__new__(DeepalDataUpdateCoordinator)
        coordinator._live_mqtt_task = None
        created = []

        class FakeEntry:
            entry_id = "e1"

            def async_create_background_task(self, hass, coro, name):
                coro.close()  # never actually run it in this test
                created.append(name)
                return types.SimpleNamespace(done=lambda: False)

        coordinator.entry = FakeEntry()
        coordinator.hass = None
        coordinator.start_live_mqtt_session()
        coordinator.start_live_mqtt_session()
        assert len(created) == 1


class TestOnLiveCondition:
    def test_merges_condition_without_disturbing_other_data(self):
        coordinator = object.__new__(DeepalDataUpdateCoordinator)
        coordinator.data = {"vehicles": ["v"], "vehicle": {"carId": "1"}, "ota": None, "condition": {"old": True}}
        captured = {}
        coordinator.async_set_updated_data = lambda data: captured.update(data)

        coordinator._on_live_condition({"soc": 50})

        assert captured["vehicles"] == ["v"]
        assert captured["vehicle"] == {"carId": "1"}
        assert captured["ota"] is None
        assert captured["condition"] == {"soc": 50}
