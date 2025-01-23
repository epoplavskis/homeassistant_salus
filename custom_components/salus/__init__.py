"""Support for Salus iT600."""
import logging
import time
from asyncio import sleep

from homeassistant import config_entries, core
from homeassistant.helpers import device_registry as dr

from homeassistant.const import (
    CONF_HOST,
    CONF_TOKEN
)

from pyit600.exceptions import IT600AuthenticationError, IT600ConnectionError
from pyit600.gateway import IT600Gateway

from .config_flow import CONF_FLOW_TYPE, CONF_USER
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = ["climate", "binary_sensor", "switch", "cover", "sensor"]


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the Salus iT600 component."""
    return True


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up components from a config entry."""
    hass.data[DOMAIN] = {}
    if entry.data[CONF_FLOW_TYPE] == CONF_USER:
        if not await async_setup_gateway_entry(hass, entry):
            return False

    return True


async def async_setup_gateway_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry) -> bool:
    """Set up the Gateway component from a config entry."""
    host = entry.data[CONF_HOST]
    euid = entry.data[CONF_TOKEN]

    # Connect to gateway
    gateway = IT600Gateway(host=host, euid=euid)
    try:
        for remaining_attempts in reversed(range(3)):
            try:
                await gateway.connect()
                await gateway.poll_status()
            except Exception as e:
                if remaining_attempts == 0:
                    raise e
                else:
                    await sleep(3)
    except IT600ConnectionError as ce:
        _LOGGER.error("Connection error: check if you have specified gateway's HOST correctly.")
        return False
    except IT600AuthenticationError as ae:
        _LOGGER.error("Authentication error: check if you have specified gateway's EUID correctly.")
        return False

    hass.data[DOMAIN][entry.entry_id] = gateway

    gateway_info = gateway.get_gateway_device()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, gateway_info.unique_id)},
        identifiers={(DOMAIN, gateway_info.unique_id)},
        manufacturer=gateway_info.manufacturer,
        name=gateway_info.name,
        model=gateway_info.model,
        sw_version=gateway_info.sw_version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, GATEWAY_PLATFORMS)

    return True

async def async_unload_entry(hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, GATEWAY_PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
