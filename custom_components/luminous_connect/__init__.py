"""Luminous Connect X solar integration."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AuthError, LuminousApi, energy_flows

DOMAIN = "luminous_connect"
PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = LuminousApi(async_get_clientsession(hass), entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    async def update() -> dict:
        try:
            plants = {}
            for plant in await api.get_plants():
                stats = await api.get_stats(plant["id"])
                stats["flows"] = energy_flows(stats)
                plants[str(plant["id"])] = {"name": plant.get("plantName"), "stats": stats}
            return plants
        except AuthError as err:
            raise ConfigEntryAuthFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=DOMAIN,
        update_method=update,
        update_interval=timedelta(minutes=2),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
