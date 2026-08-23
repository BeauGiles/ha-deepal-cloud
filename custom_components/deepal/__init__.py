"""Changan Deepal Cloud integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DeepalClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_VERSION,
    CONF_CAC_TOKEN,
    CONF_CAC_USER_ID,
    CONF_CA_USER_ID,
    CONF_COUNTRY,
    CONF_CONTROL_PIN,
    CONF_DEVICE_ID,
    CONF_ENABLE_API_LOGGING,
    CONF_ENABLE_COMMANDS,
    CONF_LANGUAGE,
    CONF_PRIVATE_KEY,
    CONF_RC_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    CONF_VEHICLE_ID,
    DEFAULT_APP_VERSION,
    DEFAULT_COUNTRY,
    DEFAULT_LANGUAGE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import DeepalDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Deepal from a config entry."""
    session = async_get_clientsession(hass)
    data = entry.data | entry.options
    client = DeepalClient(
        session,
        access_token=data[CONF_ACCESS_TOKEN],
        refresh_token=data.get(CONF_REFRESH_TOKEN),
        country=data.get(CONF_COUNTRY, DEFAULT_COUNTRY),
        language=data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
        app_version=data.get(CONF_APP_VERSION, DEFAULT_APP_VERSION),
        device_id=data[CONF_DEVICE_ID],
        private_key_pem=data.get(CONF_PRIVATE_KEY),
        enable_commands=data.get(CONF_ENABLE_COMMANDS, False),
        enable_api_logging=data.get(CONF_ENABLE_API_LOGGING, False),
        rc_token=data.get(CONF_RC_TOKEN),
        control_pin=data.get(CONF_CONTROL_PIN),
        cac_token=data.get(CONF_CAC_TOKEN),
        user_id=data.get(CONF_USER_ID) or data.get(CONF_CA_USER_ID) or data.get(CONF_CAC_USER_ID),
    )
    coordinator = DeepalDataUpdateCoordinator(hass, entry, client, str(data[CONF_VEHICLE_ID]))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload only when the user's actual *options* (set via the options flow)
    # change - not on every entry.data save. Refreshing the access token also
    # persists the new token via async_update_entry(data=...), which fires
    # this same "update listener" mechanism; reloading on every one of those
    # would tear down and recreate every entity each time the token expires
    # (commonly hourly), causing brief periodic "Unavailable" flickers across
    # every entity even though nothing actually failed.
    known_options = dict(entry.options)

    async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Reload the integration only on a genuine options-flow change."""
        if dict(entry.options) == known_options:
            return
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
