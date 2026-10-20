"""Command queueing and completion (seat "off" succeeded in the cloud but the data never changed)."""

from __future__ import annotations

import asyncio
import time

import pytest

from custom_components.deepal import coordinator as coordinator_module
from custom_components.deepal.coordinator import DeepalDataUpdateCoordinator

HomeAssistantError = coordinator_module.HomeAssistantError


class FakeClient:
    """Records calls; control_result codes and condition snapshots are scripted."""

    def __init__(self, results=(0,), conditions=None):
        self.results = list(results)
        self.conditions = list(conditions or [{"lastUpdatedAt": "1"}])
        self.inquiries = 0

    async def control_result(self, *, vehicle_id, command_id):
        code = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        return {"resultCode": code, "errorMsg": "msg"}

    async def condition(self, vehicle_id):
        return self.conditions.pop(0) if len(self.conditions) > 1 else self.conditions[0]

    async def control_condition_inquiry(self, *, vehicle_id):
        self.inquiries += 1
        return "inquiry"


def make(client=None):
    coordinator = object.__new__(DeepalDataUpdateCoordinator)
    coordinator._command_lock = asyncio.Lock()
    coordinator._queued_commands = 0
    coordinator.client = client or FakeClient()
    coordinator.vehicle_id = "123"
    coordinator.data = {"condition": {"lastUpdatedAt": "0"}, "vehicle": {}}

    def set_condition(condition):
        coordinator.data = {**coordinator.data, "condition": condition}

    coordinator._async_set_condition = set_condition
    return coordinator


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(coordinator_module, "COMMAND_SUCCESS_GRACE", 0.05)
    monkeypatch.setattr(coordinator_module, "COMMAND_INQUIRY_WAIT", 0.01)


async def send_ok():
    return "cmd-1"


class TestQueue:
    def test_commands_run_one_at_a_time_in_order(self):
        coordinator = make(FakeClient(conditions=[{"lastUpdatedAt": "9"}]))
        events = []

        def command(name):
            async def send():
                events.append(f"start {name}")
                await asyncio.sleep(0.02)
                events.append(f"end {name}")
                return name

            return send

        async def run():
            await asyncio.gather(
                *(
                    coordinator.async_execute_command(command(name), is_done=lambda: True, interval=0.01)
                    for name in ("a", "b", "c")
                )
            )

        asyncio.run(run())
        assert events == ["start a", "end a", "start b", "end b", "start c", "end c"]

    def test_queue_is_capped(self, monkeypatch):
        monkeypatch.setattr(coordinator_module, "MAX_QUEUED_COMMANDS", 2)
        coordinator = make()

        async def slow():
            await asyncio.sleep(0.05)
            return "cmd"

        async def run():
            first = asyncio.create_task(coordinator.async_execute_command(slow, interval=0.01))
            second = asyncio.create_task(coordinator.async_execute_command(slow, interval=0.01))
            await asyncio.sleep(0.01)
            with pytest.raises(HomeAssistantError, match="Too many"):
                await coordinator.async_execute_command(slow, interval=0.01)
            await asyncio.gather(first, second)

        asyncio.run(run())

    def test_counter_is_released_after_a_failure(self):
        # The snapshot stays unchanged, so the failure result is what ends the wait.
        coordinator = make(FakeClient(results=(5,), conditions=[{"lastUpdatedAt": "0"}]))

        async def run():
            with pytest.raises(HomeAssistantError, match="result code 5"):
                await coordinator.async_execute_command(send_ok, is_done=lambda: False, interval=0.01)

        asyncio.run(run())
        assert coordinator._queued_commands == 0
        assert not coordinator._command_lock.locked()

    def test_background_refresh_skips_while_a_command_runs(self):
        coordinator = make()
        ran = []

        async def background():
            ran.append("ran")
            return "cmd"

        async def run():
            async with coordinator._command_lock:
                await coordinator.async_execute_command(background, raise_if_busy=False)

        asyncio.run(run())
        assert ran == []


class TestCompletion:
    def test_confirmed_state_returns_immediately_without_an_inquiry(self):
        client = FakeClient(results=(0,), conditions=[{"lastUpdatedAt": "9"}])
        coordinator = make(client)
        started = time.monotonic()
        asyncio.run(coordinator.async_execute_command(send_ok, is_done=lambda: True, timeout=5, interval=0.01))
        assert time.monotonic() - started < 0.5
        assert client.inquiries == 0

    def test_success_without_the_data_changing_stops_waiting_after_the_grace(self, caplog):
        # The real case: control-result says success, but the seat block never changes.
        client = FakeClient(results=(0,), conditions=[{"lastUpdatedAt": "0"}])
        coordinator = make(client)
        started = time.monotonic()
        with caplog.at_level("WARNING"):
            asyncio.run(
                coordinator.async_execute_command(send_ok, is_done=lambda: False, timeout=30, interval=0.01)
            )
        assert time.monotonic() - started < 1  # not the full 30 s
        assert client.inquiries == 1  # one nudge for fresh data
        assert "accepted (result: success)" in caplog.text

    def test_pending_results_keep_polling_until_success(self):
        # The vehicle data only catches up on the third poll.
        client = FakeClient(
            results=(-100, -100, 0),
            conditions=[{"lastUpdatedAt": "0"}, {"lastUpdatedAt": "0"}, {"lastUpdatedAt": "9"}],
        )
        coordinator = make(client)
        asyncio.run(
            coordinator.async_execute_command(
                send_ok,
                is_done=lambda: coordinator.data["condition"]["lastUpdatedAt"] == "9",
                timeout=5,
                interval=0.01,
            )
        )
        assert client.results == [0]  # both pending answers were consumed
        assert client.inquiries == 0

    def test_a_failure_code_raises(self):
        coordinator = make(FakeClient(results=(7,), conditions=[{"lastUpdatedAt": "0"}]))
        with pytest.raises(HomeAssistantError, match="result code 7"):
            asyncio.run(coordinator.async_execute_command(send_ok, is_done=lambda: False, interval=0.01))

    def test_a_failed_inquiry_does_not_break_the_command(self):
        client = FakeClient(results=(0,), conditions=[{"lastUpdatedAt": "0"}])

        async def broken(**_):
            raise coordinator_module.DeepalApiError("nope")

        client.control_condition_inquiry = broken
        coordinator = make(client)
        asyncio.run(coordinator.async_execute_command(send_ok, is_done=lambda: False, timeout=30, interval=0.01))


class TestPowerNotOff:
    """Result code 1032: the car is powered on and refuses the remote command."""

    def test_message_explains_what_to_do(self):
        message = coordinator_module.command_failure_message(1032, "Operation failed. Power is not off.")
        assert "result code 1032" in message
        assert "Power is not off." in message  # the car's own text is kept
        assert "powered on" in message
        assert "Switch the car off" in message

    def test_other_codes_get_no_hint(self):
        message = coordinator_module.command_failure_message(7, "boom")
        assert message == "Deepal command failed with result code 7: boom"

    def test_the_command_raises_the_explained_error(self):
        class PowerOnClient(FakeClient):
            async def control_result(self, *, vehicle_id, command_id):
                return {"resultCode": 1032, "errorMsg": "Operation failed. Power is not off."}

        coordinator = make(PowerOnClient(conditions=[{"lastUpdatedAt": "0"}]))
        with pytest.raises(HomeAssistantError, match="Switch the car off"):
            asyncio.run(coordinator.async_execute_command(send_ok, is_done=lambda: False, interval=0.01))
