"""The vehicle image keeps serving the last good picture across a failed or
slow refetch, instead of jumping straight to the bundled Deepal logo.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from custom_components.deepal import image


def _make_entity(*, source_url=None, image_bytes=None, image_bytes_url=None, failed_at=None, fetch_task=None):
    entity = object.__new__(image.DeepalVehicleImage)
    entity.coordinator = SimpleNamespace(data={"vehicle": {"imgUrl": source_url}})
    entity._last_url = source_url
    entity._image_bytes = image_bytes
    entity._image_bytes_url = image_bytes_url
    entity._fallback_bytes = b"fallback"
    entity._failed_at = failed_at
    entity._fetch_task = fetch_task
    entity._warned = False
    entity.hass = None
    entity.entity_id = None
    entity._attr_content_type = None
    entity._attr_image_last_updated = None
    return entity


async def _completed_coro(value):
    return value


async def _never_completes_coro():
    await asyncio.sleep(10)
    return b"too-late"


async def _with_fetch_task(entity, coro):
    """Attach a running task for ``coro`` to ``entity`` and call async_image()."""
    entity._fetch_task = asyncio.ensure_future(coro)
    return await entity.async_image()


class TestNoSourceUrl:
    def test_falls_back_when_nothing_cached(self):
        entity = _make_entity(source_url=None)
        assert asyncio.run(entity.async_image()) == b"fallback"

    def test_returns_cached_bytes_without_fallback(self):
        entity = _make_entity(source_url=None, image_bytes=b"old-photo")
        assert asyncio.run(entity.async_image()) == b"old-photo"


class TestAlreadyCurrent:
    def test_returns_cached_bytes_with_no_fetch_when_url_matches(self, monkeypatch):
        entity = _make_entity(source_url="http://car/a.jpg", image_bytes=b"a", image_bytes_url="http://car/a.jpg")

        def _boom():
            raise AssertionError("should not start a fetch when the current picture is already cached")

        monkeypatch.setattr(entity, "_async_start_fetch", _boom)
        assert asyncio.run(entity.async_image()) == b"a"


class TestRecentFailure:
    def test_serves_cached_bytes_during_the_backoff_window(self, monkeypatch):
        entity = _make_entity(
            source_url="http://car/b.jpg",
            image_bytes=b"stale-but-real",
            image_bytes_url="http://car/old.jpg",
            failed_at=time.monotonic(),
        )
        monkeypatch.setattr(entity, "_async_start_fetch", lambda: None)
        assert asyncio.run(entity.async_image()) == b"stale-but-real"

    def test_falls_back_during_the_backoff_window_with_nothing_cached(self, monkeypatch):
        entity = _make_entity(source_url="http://car/b.jpg", failed_at=time.monotonic())
        monkeypatch.setattr(entity, "_async_start_fetch", lambda: None)
        assert asyncio.run(entity.async_image()) == b"fallback"


class TestRefetchInFlight:
    def test_a_slow_or_stuck_fetch_serves_the_last_good_picture(self, monkeypatch):
        # The URL changed, so the cached bytes are stale for it, and the
        # background fetch for the new one never finishes in time.
        entity = _make_entity(source_url="http://car/new.jpg", image_bytes=b"old-photo", image_bytes_url="http://car/old.jpg")
        monkeypatch.setattr(entity, "_async_start_fetch", lambda: None)
        monkeypatch.setattr(image, "API_IMAGE_WAIT", 0.01)
        assert asyncio.run(_with_fetch_task(entity, _never_completes_coro())) == b"old-photo"

    def test_a_slow_fetch_with_nothing_cached_yet_falls_back(self, monkeypatch):
        entity = _make_entity(source_url="http://car/new.jpg")
        monkeypatch.setattr(entity, "_async_start_fetch", lambda: None)
        monkeypatch.setattr(image, "API_IMAGE_WAIT", 0.01)
        assert asyncio.run(_with_fetch_task(entity, _never_completes_coro())) == b"fallback"

    def test_a_fetch_that_completes_in_time_wins(self, monkeypatch):
        entity = _make_entity(source_url="http://car/new.jpg", image_bytes=b"old-photo", image_bytes_url="http://car/old.jpg")
        monkeypatch.setattr(entity, "_async_start_fetch", lambda: None)
        assert asyncio.run(_with_fetch_task(entity, _completed_coro(b"new-photo"))) == b"new-photo"


class TestCoordinatorUpdate:
    def test_url_change_does_not_clear_the_cached_picture(self, monkeypatch):
        entity = _make_entity(source_url="http://car/new.jpg", image_bytes=b"old-photo", image_bytes_url="http://car/old.jpg")
        entity._last_url = "http://car/old.jpg"
        started = []
        monkeypatch.setattr(entity, "_async_start_fetch", lambda: started.append(True))
        monkeypatch.setattr(image.DeepalEntity, "_handle_coordinator_update", lambda self: None, raising=False)
        entity._handle_coordinator_update()
        assert entity._image_bytes == b"old-photo"
        assert entity._image_bytes_url == "http://car/old.jpg"
        assert entity._last_url == "http://car/new.jpg"
        assert started == [True]

    def test_unchanged_url_does_not_start_a_new_fetch(self, monkeypatch):
        entity = _make_entity(source_url="http://car/same.jpg", image_bytes=b"photo", image_bytes_url="http://car/same.jpg")
        entity._last_url = "http://car/same.jpg"

        def _boom():
            raise AssertionError("should not refetch when the URL hasn't changed")

        monkeypatch.setattr(entity, "_async_start_fetch", _boom)
        monkeypatch.setattr(image.DeepalEntity, "_handle_coordinator_update", lambda self: None, raising=False)
        entity._handle_coordinator_update()


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def raise_for_status(self):
        pass

    async def read(self):
        return self._data


class _FakeGet:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc_info):
        return False


class _FakeSession:
    def __init__(self, data: bytes):
        self._data = data

    def get(self, url, timeout=None):
        return _FakeGet(_FakeResponse(self._data))


class TestFetchRecordsTheUrlItCameFrom:
    def test_success_records_the_fetched_url_alongside_the_bytes(self):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"rest"
        entity = _make_entity(source_url="http://car/photo.jpg")
        entity._session = _FakeSession(png_bytes)

        async def _write_ha_state():
            pass

        asyncio.run(entity._async_fetch_api_image())
        assert entity._image_bytes == png_bytes
        assert entity._image_bytes_url == "http://car/photo.jpg"

    def test_failure_leaves_the_previous_good_bytes_and_url_untouched(self):
        entity = _make_entity(
            source_url="http://car/photo.jpg", image_bytes=b"old-good-photo", image_bytes_url="http://car/old.jpg"
        )
        entity._session = _FakeSession(b"not an image at all")  # no known signature -> treated as a failure

        result = asyncio.run(entity._async_fetch_api_image())
        assert result is None
        assert entity._image_bytes == b"old-good-photo"
        assert entity._image_bytes_url == "http://car/old.jpg"
        assert entity._failed_at is not None
