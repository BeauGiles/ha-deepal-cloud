"""Repairs for the Changan Deepal Cloud integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant

_COMMAND_REAUTH_SUFFIX = "_command_reauth"


class DeepalCommandReauthRepairFlow(RepairsFlow):
    """Confirm, then start a real reauthentication to register a fresh command key."""

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> data_entry_flow.FlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> data_entry_flow.FlowResult:
        """Confirm the fix, then hand off to the integration's normal reauth flow."""
        if user_input is not None:
            entry_id = self.issue_id.removesuffix(_COMMAND_REAUTH_SUFFIX)
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is not None:
                # This schedules the same reauth flow the integration triggers
                # automatically on a bad refresh token - it logs in again,
                # which generates and submits a fresh command-signing keypair.
                entry.async_start_reauth(self.hass)
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for a Deepal repair issue."""
    return DeepalCommandReauthRepairFlow()
