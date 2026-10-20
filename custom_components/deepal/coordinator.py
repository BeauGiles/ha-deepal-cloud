"""Data coordinator for Deepal vehicles."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DeepalApiError, DeepalAuthError, DeepalClient, add_seat_roles
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACTIVE_REFRESH_INTERVAL,
    CONF_REFRESH_TOKEN,
    DEFAULT_ACTIVE_REFRESH_INTERVAL,
    COMMAND_INQUIRY_WAIT,
    COMMAND_SUCCESS_GRACE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_QUEUED_COMMANDS,
    MQTT_BACKOFF_BASE,
    MQTT_BACKOFF_MAX,
    WAKE_COOLDOWN,
    WAKE_POLL_INTERVAL,
    WAKE_REPORT_TIMEOUT,
    WAKE_STALE_AFTER,
    vehicle_supports_mqtt_commands,
    vehicle_uses_mqtt,
    vehicle_uses_sda,
)

_LOGGER = logging.getLogger(__name__)

# Result code the car returns when it refuses a remote command because it is
# powered on (seen with the air conditioner and the windows; also reported by
# Sunek0/ha-deepal-alternative).
POWER_NOT_OFF_RESULT_CODE = 1032
POWER_NOT_OFF_HINT = (
    " The car is powered on, so it refused this remote command. Switch the car off "
    "(or wait for it to power down) and try again."
)


def command_failure_message(result_code: Any, error_message: Any) -> str:
    """Build the error shown when the car reports a failed command."""
    message = f"Deepal command failed with result code {result_code}: {error_message}"
    if result_code == POWER_NOT_OFF_RESULT_CODE:
        message += POWER_NOT_OFF_HINT
    return message


class DeepalDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch vehicle list and condition data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DeepalClient, vehicle_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )
        self.entry = entry
        self.client = client
        self.vehicle_id = vehicle_id
        self.refresh_failure_count = 0
        self.last_refresh_failure: str | None = None
        self._command_lock = asyncio.Lock()
        self._queued_commands = 0  # running + waiting
        self._next_active_refresh_at = 0.0
        self._last_wake_at: float | None = None
        self._mqtt_failures = 0
        self._mqtt_next_attempt = 0.0
        self._mqtt_last_error: DeepalApiError | None = None
        self.mqtt_fallback_active = False
        self._wake_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            vehicles, condition = await self._async_fetch()
        except DeepalAuthError as err:
            try:
                tokens = await self.client.refresh_tokens()
                new_data = dict(self.entry.data)
                new_data[CONF_ACCESS_TOKEN] = tokens.access_token
                if tokens.refresh_token:
                    new_data[CONF_REFRESH_TOKEN] = tokens.refresh_token
                self.hass.config_entries.async_update_entry(self.entry, data=new_data)
                vehicles, condition = await self._async_fetch()
            except (DeepalApiError, DeepalAuthError) as refresh_err:
                self._record_refresh_failure(refresh_err)
                raise ConfigEntryAuthFailed(f"Authentication failed: {refresh_err}") from refresh_err
        except DeepalApiError as err:
            self._record_refresh_failure(err)
            raise UpdateFailed(str(err)) from err

        self.last_refresh_failure = None
        vehicle = self._vehicle_from_list(vehicles)
        ota = None
        if not vehicle_uses_mqtt(vehicle or {}):
            try:
                ota = await self.client.ota_status(self.vehicle_id)
            except DeepalApiError as err:
                # OTA status is a nice-to-have; a failure here shouldn't fail the
                # whole update (ported from the original repo's same approach).
                _LOGGER.debug("Deepal: failed to fetch OTA status: %s", err)
                ota = None
        condition = add_seat_roles(condition, (vehicle or {}).get("driveSeatPosition"))
        position = getattr(self.client, "last_position", None)
        return {
            "vehicles": vehicles,
            "vehicle": vehicle or {},
            "condition": condition,
            "ota": ota,
            "position": {"latitude": position[0], "longitude": position[1]} if position else None,
        }

    async def _async_fetch(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch vehicle metadata and condition."""
        vehicles = await self.client.vehicles()
        vehicle = self._vehicle_from_list(vehicles) or {}
        self.client.drive_side = vehicle.get("driveSeatPosition")
        if vehicle_uses_sda(vehicle):
            condition = await self.client.sda_condition(self.vehicle_id)
        elif vehicle_uses_mqtt(vehicle):
            condition = await self._async_mqtt_condition_with_fallback()
        else:
            await self._async_maybe_active_condition_refresh()
            condition = await self.client.condition(self.vehicle_id)
        return vehicles, condition

    async def _async_mqtt_condition_with_fallback(self) -> dict[str, Any]:
        """Read MQTT telemetry; if it fails, use the REST condition and back off.

        An account whose token the CA gateway rejects would otherwise get nothing
        and a rejected request every poll. Authentication errors are not swallowed.
        """
        now = time.monotonic()
        if now >= self._mqtt_next_attempt:
            try:
                condition = await self.client.mqtt_condition(self.vehicle_id)
            except DeepalAuthError:
                raise
            except DeepalApiError as err:
                self._mqtt_failures += 1
                self._mqtt_last_error = err
                delay = min(MQTT_BACKOFF_MAX, MQTT_BACKOFF_BASE * 2 ** (self._mqtt_failures - 1))
                self._mqtt_next_attempt = now + delay
                if self._mqtt_failures == 1:
                    _LOGGER.warning(
                        "MQTT telemetry unavailable (%s); using the REST condition and retrying MQTT in %s s",
                        err,
                        delay,
                    )
            else:
                if self.mqtt_fallback_active:
                    _LOGGER.info("MQTT telemetry is working again")
                self._mqtt_failures = 0
                self._mqtt_next_attempt = 0.0
                self._mqtt_last_error = None
                self.mqtt_fallback_active = False
                return condition

        rest = await self._async_usable_rest_condition()
        if rest is not None:
            self.mqtt_fallback_active = True
            return rest
        raise self._mqtt_last_error or DeepalApiError("MQTT telemetry is unavailable")

    async def _async_usable_rest_condition(self) -> dict[str, Any] | None:
        """Return the REST condition if it carries data (it may be partial), else None."""
        try:
            condition = await self.client.condition(self.vehicle_id)
        except DeepalAuthError:
            raise
        except DeepalApiError as err:
            _LOGGER.debug("REST condition fallback failed: %s", err)
            return None
        status = condition.get("vehicleStatus") if isinstance(condition, dict) else None
        if isinstance(status, dict) and any(value is not None for value in status.values()):
            return condition
        return None

    def _vehicle_from_list(self, vehicles: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Return the configured vehicle metadata from a vehicle list response."""
        return next((item for item in vehicles if str(item.get("carId")) == self.vehicle_id), None)

    @property
    def vehicle_uses_mqtt(self) -> bool:
        """Return whether the configured vehicle uses MQTT telemetry."""
        return vehicle_uses_mqtt((self.data or {}).get("vehicle") or {})

    @property
    def mqtt_commands_supported(self) -> bool:
        """Return whether MQTT remote commands are available for this vehicle."""
        return vehicle_supports_mqtt_commands((self.data or {}).get("vehicle") or {})

    def _should_wake(self, report_ts: int | None) -> bool:
        """Return whether a manual refresh should wake the car.

        Throttled: never within the cooldown of the last wake, and only when the
        last report is older than the stale threshold. A report with no real
        timestamp never triggers a wake.
        """
        if self._last_wake_at is not None and time.monotonic() - self._last_wake_at < WAKE_COOLDOWN:
            return False
        if report_ts is None:
            return False
        return time.time() - report_ts / 1000 > WAKE_STALE_AFTER

    async def async_refresh_vehicle(self) -> None:
        """Refresh vehicle data, waking an MQTT car first when its report is stale.

        Only for MQTT telemetry vehicles (S05). SDA (E07) telemetry is REST and
        needs no wake. The periodic poll never wakes the car; only this explicit
        refresh does, and at most once per cooldown.
        """
        if (
            not self.vehicle_uses_mqtt
            or self.mqtt_fallback_active
            or vehicle_uses_sda((self.data or {}).get("vehicle") or {})
        ):
            await self.async_request_refresh()
            return

        previous = ((self.data or {}).get("condition") or {}).get("lastUpdatedAt")
        if not self._should_wake(previous):
            await self.async_request_refresh()
            return

        async with self._wake_lock:
            if not self._should_wake(previous):
                await self.async_request_refresh()
                return
            try:
                await self.client.mqtt_wake(self.vehicle_id)
            except (DeepalApiError, DeepalAuthError) as err:
                _LOGGER.warning("Deepal wake request failed: %s", err)
                await self.async_request_refresh()
                return
            # Record the wake as soon as it is accepted, whether or not a
            # report arrives, so a silent car is not woken repeatedly.
            self._last_wake_at = time.monotonic()

            loop = asyncio.get_running_loop()
            deadline = loop.time() + WAKE_REPORT_TIMEOUT
            while loop.time() < deadline:
                await asyncio.sleep(WAKE_POLL_INTERVAL)
                try:
                    condition = await self.client.mqtt_condition(self.vehicle_id)
                except (DeepalApiError, DeepalAuthError) as err:
                    _LOGGER.debug("Deepal wake poll failed: %s", err)
                    continue
                report_ts = condition.get("lastUpdatedAt")
                if previous is None or (report_ts is not None and report_ts > previous):
                    self._async_set_condition(condition)
                    return
            await self.async_request_refresh()
            raise HomeAssistantError(
                "The vehicle did not report fresh data after the wake request; "
                "it may be offline or asleep"
            )

    async def _async_maybe_active_condition_refresh(self) -> None:
        """Periodically ask the car/cloud for fresh condition data."""
        if not self.client.commands_enabled:
            return

        loop = asyncio.get_running_loop()
        now = loop.time()
        if now < self._next_active_refresh_at:
            return

        interval = self.entry.options.get(CONF_ACTIVE_REFRESH_INTERVAL, DEFAULT_ACTIVE_REFRESH_INTERVAL)
        self._next_active_refresh_at = now + interval
        try:
            await self.async_execute_command(
                lambda: self.client.control_condition_inquiry(vehicle_id=self.vehicle_id),
                raise_if_busy=False,
                timeout=30,
            )
        except (DeepalApiError, DeepalAuthError, HomeAssistantError) as err:
            _LOGGER.warning("Deepal active condition refresh failed: %s", err)

    async def async_execute_command(
        self,
        send_command: Callable[[], Awaitable[str]],
        *,
        is_done: Callable[[], bool] | None = None,
        raise_if_busy: bool = True,
        timeout: float = 30,
        interval: float = 2,
    ) -> None:
        """Run one command. Commands queue and run one at a time.

        A background caller (``raise_if_busy=False``, the periodic condition
        refresh) skips instead of waiting when a command is running. User
        commands wait their turn; the queue is capped so a stuck car cannot pile
        up physical commands.
        """
        if not raise_if_busy and self._command_lock.locked():
            return
        if self._queued_commands >= MAX_QUEUED_COMMANDS:
            raise HomeAssistantError(
                "Too many Deepal commands are waiting for the vehicle; try again in a moment"
            )
        self._queued_commands += 1
        try:
            async with self._command_lock:
                await self._async_run_command(send_command, is_done=is_done, timeout=timeout, interval=interval)
        finally:
            self._queued_commands -= 1

    async def _async_run_command(
        self,
        send_command: Callable[[], Awaitable[str]],
        *,
        is_done: Callable[[], bool] | None,
        timeout: float,
        interval: float,
    ) -> None:
        """Send one command and wait for its result and the resulting vehicle data."""
        previous_last_updated = self._condition_last_updated()
        command_id = await send_command()
        if self.vehicle_uses_mqtt:
            # MQTT commands are acknowledged by the broker response, so
            # there is no HTTP command result to poll; just re-read state.
            try:
                await self.async_request_refresh()
            except (DeepalApiError, UpdateFailed) as err:
                _LOGGER.warning(
                    "MQTT command %s was acknowledged but the follow-up state refresh failed: %s",
                    command_id,
                    err,
                )
            return
        await self.async_poll_command_update(
            command_id,
            previous_last_updated=previous_last_updated,
            is_done=is_done,
            timeout=timeout,
            interval=interval,
        )

    async def async_poll_command_update(
        self,
        command_id: str,
        *,
        previous_last_updated: str | None,
        is_done: Callable[[], bool] | None = None,
        timeout: float = 30,
        interval: float = 2,
    ) -> None:
        """Poll command result and condition until the cloud reports fresh data."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        condition_changed = False
        success_at: float | None = None

        while True:
            result = await self.client.control_result(vehicle_id=self.vehicle_id, command_id=command_id)
            condition = await self.client.condition(self.vehicle_id)
            self._async_set_condition(condition)

            last_updated = self._condition_last_updated(condition)
            condition_changed = bool(last_updated) and last_updated != previous_last_updated
            state_done = is_done() if is_done is not None else True
            if condition_changed and state_done:
                return

            result_code = result.get("resultCode")
            if result_code not in (None, -100, 0, 1015):
                raise HomeAssistantError(command_failure_message(result_code, result.get("errorMsg")))

            if result_code == 0 and success_at is None:
                success_at = loop.time()
            if success_at is not None and loop.time() - success_at >= COMMAND_SUCCESS_GRACE:
                await self._async_settle_after_success(command_id, is_done)
                return

            if loop.time() >= deadline:
                if not condition_changed:
                    _LOGGER.warning(
                        "Deepal command %s timed out before lastUpdatedAt changed from %s",
                        command_id,
                        previous_last_updated,
                    )
                return

            await asyncio.sleep(interval)

    async def _async_settle_after_success(
        self, command_id: str, is_done: Callable[[], bool] | None
    ) -> None:
        """The cloud reported success but the vehicle data has not caught up.

        Ask the car for fresh data once and read it. If the data still shows the
        old state, say so (a stale cloud snapshot or a command the car ignored
        both look like this) and stop waiting, so the next command is not held up.
        """
        try:
            await self.client.control_condition_inquiry(vehicle_id=self.vehicle_id)
            await asyncio.sleep(COMMAND_INQUIRY_WAIT)
            self._async_set_condition(await self.client.condition(self.vehicle_id))
        except (DeepalApiError, DeepalAuthError, HomeAssistantError) as err:
            _LOGGER.debug("Deepal condition inquiry after command %s failed: %s", command_id, err)
        if is_done is not None and not is_done():
            _LOGGER.warning(
                "Deepal command %s was accepted (result: success) but the vehicle data still shows the "
                "previous state; the change may not have been applied or the cloud data is stale",
                command_id,
            )

    def _async_set_condition(self, condition: dict[str, Any]) -> None:
        """Update coordinator data with a freshly fetched condition payload."""
        data = dict(self.data or {})
        side = (data.get("vehicle") or {}).get("driveSeatPosition")
        data["condition"] = add_seat_roles(condition, side)
        self.async_set_updated_data(data)

    def _condition_last_updated(self, condition: dict[str, Any] | None = None) -> str | None:
        """Return the condition last-updated marker as a stable string."""
        if condition is None:
            condition = (self.data or {}).get("condition") or {}
        value = condition.get("lastUpdatedAt")
        if value is None:
            value = (condition.get("vehicleStatus") or {}).get("lastUpdatedAt")
        return str(value) if value is not None else None

    def _record_refresh_failure(self, err: Exception) -> None:
        """Track and log failed API refreshes for rate-limit observation."""
        self.refresh_failure_count += 1
        self.last_refresh_failure = str(err)
        _LOGGER.warning(
            "Deepal refresh failed for vehicle %s; failure_count=%s; error=%s",
            self.vehicle_id,
            self.refresh_failure_count,
            err,
        )
