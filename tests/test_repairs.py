"""The location-permission repair flow.

Regression test for a real production crash: Home Assistant's repair-flow
manager calls async_step_init with a data dict of its own (the issue's init
context, not a form submission) - passing that straight into
async_step_authorize made it KeyError on the missing qr_auth_url field the
very first time the repair was opened.
"""

from __future__ import annotations

import asyncio
import types

from custom_components.deepal import repairs
from custom_components.deepal.api import DeepalApiError
from custom_components.deepal.const import CONF_QR_AUTH_URL


class _FakeCoordinator:
    def __init__(self, *, error=None):
        self._error = error
        self.calls = []

    async def async_authorize_qr_code(self, qr_code_or_url):
        self.calls.append(qr_code_or_url)
        if self._error is not None:
            raise self._error


def _flow(*, entry=None, issue_id="entry-1_location_permission"):
    # RepairsFlow's base (data_entry_flow.FlowHandler) is stubbed out under
    # this repo's test harness, so async_show_form/async_create_entry - real
    # HA framework methods, not ours to test - are stood in here with plain
    # dicts shaped the same way the real ones are.
    flow = repairs.DeepalLocationPermissionRepairFlow()
    flow.issue_id = issue_id
    flow.hass = types.SimpleNamespace(
        config_entries=types.SimpleNamespace(async_get_entry=lambda entry_id: entry)
    )
    flow.async_show_form = lambda *, step_id, data_schema=None, errors=None: {
        "type": "form",
        "step_id": step_id,
        "errors": errors,
    }
    flow.async_create_entry = lambda *, data=None: {"type": "create_entry", "data": data}
    return flow


class TestLocationPermissionRepairFlowInit:
    def test_init_with_the_flow_managers_own_data_dict_shows_the_form(self):
        # This {} is what crashed in production: not None, but not a form
        # submission either.
        flow = _flow()
        result = asyncio.run(flow.async_step_init({}))
        assert result["step_id"] == "authorize"
        assert result.get("errors") is None

    def test_init_with_none_also_shows_the_form(self):
        flow = _flow()
        result = asyncio.run(flow.async_step_init(None))
        assert result["step_id"] == "authorize"


class TestLocationPermissionRepairFlowAuthorize:
    def test_successful_submission_creates_the_entry(self):
        coordinator = _FakeCoordinator()
        entry = types.SimpleNamespace(runtime_data=coordinator)
        flow = _flow(entry=entry)
        result = asyncio.run(flow.async_step_authorize({CONF_QR_AUTH_URL: "https://example/qr?qrCode=abc"}))
        assert result["type"] == "create_entry"
        assert coordinator.calls == ["https://example/qr?qrCode=abc"]

    def test_failed_authorization_shows_the_form_with_an_error(self):
        coordinator = _FakeCoordinator(error=DeepalApiError("bad code"))
        entry = types.SimpleNamespace(runtime_data=coordinator)
        flow = _flow(entry=entry)
        result = asyncio.run(flow.async_step_authorize({CONF_QR_AUTH_URL: "bad"}))
        assert result["step_id"] == "authorize"
        assert result["errors"] == {"base": "qr_auth_failed"}

    def test_no_loaded_entry_shows_the_form_with_an_error(self):
        flow = _flow(entry=None)
        result = asyncio.run(flow.async_step_authorize({CONF_QR_AUTH_URL: "x"}))
        assert result["errors"] == {"base": "qr_auth_failed"}
