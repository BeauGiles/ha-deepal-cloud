"""Experimental opt-in vehicle location."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.deepal import coordinator as coordinator_module
from custom_components.deepal import device_tracker
from custom_components.deepal.api import DeepalClient
from custom_components.deepal.coordinator import DeepalDataUpdateCoordinator
from custom_components.deepal.location import find_location, location_paths

SYDNEY = (-33.8688, 151.2093)


class TestFindLocation:
    @pytest.mark.parametrize(
        "payload",
        [
            {"lat": -33.8688, "lng": 151.2093},
            {"Lat": -33.8688, "Lng": 151.2093},
            {"latitude": -33.8688, "longitude": 151.2093},
            {"LAT": "-33.8688", "LON": "151.2093"},  # numeric strings, other spellings
            {"location": {"lat": -33.8688, "lng": 151.2093}},
            {"data": {"gps": [{"latitude": -33.8688, "longitude": 151.2093}]}},
        ],
    )
    def test_found_in_common_shapes(self, payload):
        assert find_location(payload) == SYDNEY

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            None,
            "text",
            {"lat": -33.8688},  # no longitude
            {"lng": 151.2093},  # no latitude
            {"lat": 0, "lng": 0},  # "no fix"
            {"lat": 91, "lng": 10},  # out of range
            {"lat": 10, "lng": 181},
            {"lat": True, "lng": True},
            {"lat": "abc", "lng": "def"},
            {"a": {"lat": 10}, "b": {"lng": 20}},  # a pair must come from the same object
            {"latestDate": "2026-10-20", "lngth": 5},  # similar-looking keys are not coordinates
        ],
    )
    def test_not_found(self, payload):
        assert find_location(payload) is None

    def test_the_shallowest_pair_wins(self):
        payload = {"x": {"y": {"lat": 1, "lng": 2}}, "lat": -33.8688, "lng": 151.2093}
        assert find_location(payload) == SYDNEY

    def test_the_first_source_with_a_position_is_used(self):
        assert find_location({}, {"lat": 5, "lng": 6}, {"lat": 7, "lng": 8}) == (5.0, 6.0)

    def test_search_depth_is_limited(self):
        deep = {"lat": 1, "lng": 2}
        for _ in range(10):
            deep = {"n": deep}
        assert find_location(deep) is None


class TestLocationPaths:
    def test_reports_where_never_what(self):
        payload = {"location": {"lat": -33.8688, "lng": 151.2093}, "tires": [{"Lat": 1.5, "Lng": 2.5}]}
        paths = location_paths(payload)
        assert paths == ["location", "tires[0]"]
        text = str(paths)
        assert "33.8688" not in text and "151.2093" not in text

    def test_top_level(self):
        assert location_paths({"lat": 1, "lng": 2}) == ["(top level)"]


# ---------------------------------------------------------------- client


def make_client(*, fetch, responses):
    client = object.__new__(DeepalClient)
    client.fetch_location = fetch
    client.last_position = None
    client._location_state = None
    client.payloads = []
    pending = list(responses)

    async def fake_post(path, payload=None, **_):
        client.payloads.append(payload)
        return pending.pop(0) if len(pending) > 1 else pending[0]

    client._post = fake_post
    return client


def run(client):
    return asyncio.run(client.condition("1"))


class TestClient:
    def test_location_is_not_requested_by_default(self):
        client = make_client(fetch=False, responses=[{"lat": 1, "lng": 2}])
        run(client)
        assert "location" not in client.payloads[0]["vechileCriteria"]
        assert client.last_position is None  # not even looked at when off

    def test_location_is_requested_when_enabled(self):
        client = make_client(fetch=True, responses=[{}])
        run(client)
        assert client.payloads[0]["vechileCriteria"]["location"] == "1"
        assert client.payloads[0]["vechileCriteria"]["door"] == "1"  # the normal request is intact

    def test_position_is_kept_when_a_later_response_has_none(self):
        client = make_client(fetch=True, responses=[{"location": {"lat": -33.8688, "lng": 151.2093}}, {"vehicleStatus": {}}])
        run(client)
        assert client.last_position == SYDNEY
        run(client)
        assert client.last_position == SYDNEY  # last known fix survives a sleeping car

    def test_a_newer_fix_replaces_the_old_one(self):
        client = make_client(fetch=True, responses=[{"lat": 1, "lng": 2}, {"lat": 3, "lng": 4}])
        run(client)
        run(client)
        assert client.last_position == (3.0, 4.0)

    def test_the_condition_is_returned_unchanged(self):
        response = {"vehicleStatus": {"soc": 50}, "location": {"lat": 1, "lng": 2}}
        assert run(make_client(fetch=True, responses=[response])) == response

    def test_logs_once_per_change_and_never_coordinates(self, caplog):
        responses = [{}, {}, {"location": {"lat": -33.8688, "lng": 151.2093}}, {"location": {"lat": -33.9, "lng": 151.3}}, {}]
        client = make_client(fetch=True, responses=responses)
        with caplog.at_level("INFO"):
            for _ in responses:
                run(client)
        # Sequence: none, none, fix, newer fix, none -> logs on each change only:
        # missing (once, not every poll), found (once), missing again.
        assert caplog.text.count("carried no position") == 2
        assert caplog.text.count("a position was found at") == 1
        assert "33.8688" not in caplog.text and "151.2093" not in caplog.text
        assert "33.9" not in caplog.text


# ---------------------------------------------------------------- coordinator / entity


def make_coordinator(position):
    coordinator = object.__new__(DeepalDataUpdateCoordinator)
    vehicle = {"carId": "1", "protocolType": "TLV"}

    class Client:
        last_position = position

        async def vehicles(self):
            return [vehicle]

        async def condition(self, vehicle_id):
            return {"vehicleStatus": {"soc": 50}}

        async def ota_status(self, vehicle_id):
            return {}

        async def _unused(self):  # pragma: no cover
            return None

    coordinator.client = Client()
    coordinator.vehicle_id = "1"
    coordinator.last_refresh_failure = None
    coordinator._mqtt_failures = 0
    coordinator._mqtt_next_attempt = 0.0
    coordinator._mqtt_last_error = None
    coordinator.mqtt_fallback_active = False
    coordinator._next_active_refresh_at = 0.0
    coordinator._async_maybe_active_condition_refresh = lambda: asyncio.sleep(0)
    return coordinator


class TestCoordinatorData:
    def test_position_is_published_when_known(self):
        data = asyncio.run(make_coordinator(SYDNEY)._async_update_data())
        assert data["position"] == {"latitude": SYDNEY[0], "longitude": SYDNEY[1]}

    def test_no_position_is_none(self):
        data = asyncio.run(make_coordinator(None)._async_update_data())
        assert data["position"] is None


class TestTracker:
    def make(self, data):
        coordinator = type("C", (), {"vehicle_id": "1", "data": data})()
        tracker = device_tracker.DeepalLocationTracker(coordinator)
        tracker.coordinator = coordinator
        return tracker

    def test_reports_the_position(self):
        tracker = self.make({"position": {"latitude": -33.8688, "longitude": 151.2093}})
        assert (tracker.latitude, tracker.longitude) == SYDNEY
        assert tracker._attr_unique_id == "1_location"
        assert tracker._attr_name == "Location"

    def test_unknown_without_a_position(self):
        tracker = self.make({"position": None})
        assert (tracker.latitude, tracker.longitude) == (None, None)

    def test_only_created_when_a_position_exists(self):
        captured = {}

        async def fake_add(hass, entry, coordinator, add, candidates, platform):
            captured["candidates"] = candidates
            captured["platform"] = platform

        original = device_tracker.async_add_supported
        device_tracker.async_add_supported = fake_add
        try:
            entry = type("Entry", (), {"runtime_data": type("C", (), {"vehicle_id": "1", "data": {}})()})()
            asyncio.run(device_tracker.async_setup_entry(None, entry, lambda e: None))
        finally:
            device_tracker.async_add_supported = original
        (_entity, supported), = captured["candidates"]
        assert captured["platform"] == "device_tracker"
        assert supported({"position": {"latitude": 1.0, "longitude": 2.0}})
        assert not supported({"position": None})
        assert not supported({})
