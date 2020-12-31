"""Support for climate devices (thermostats)."""
from datetime import timedelta
import logging
import async_timeout

import voluptuous as vol
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_TOKEN
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pyit600.exceptions import IT600AuthenticationError, IT600ConnectionError
from pyit600.gateway import IT600Gateway

OPERATION_LIST = [HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_AUTO]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Salus thermostats from a config entry."""
    await async_setup_platform(hass, config_entry.data, async_add_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""

    gateway = IT600Gateway(host=config[CONF_HOST], euid=config[CONF_TOKEN])
    try:
        await gateway.connect()
    except IT600ConnectionError as ce:
        _LOGGER.error("Connection error: check if you have specified gateway's HOST correctly.")
        return False
    except IT600AuthenticationError as ae:
        _LOGGER.error("Authentication error: check if you have specified gateway's TOKEN correctly.")
        return False

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        async with async_timeout.timeout(10):
            await gateway.poll_status()
            return gateway.get_climate_devices()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    async_add_entities(SalusThermostat(coordinator, idx, gateway) for idx
                       in coordinator.data)


class SalusThermostat(ClimateEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, idx, gateway):
        """Initialize the thermostat."""
        self._coordinator = coordinator
        self._idx = idx
        self._gateway = gateway

    async def async_update(self):
        """Update the entity.
        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._coordinator.data.get(self._idx).supported_features

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.data.get(self._idx).available

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self._coordinator.data.get(self._idx).name,
            "identifiers": {("salus", self._coordinator.data.get(self._idx).unique_id)},
            "manufacturer": self._coordinator.data.get(self._idx).manufacturer,
            "model": self._coordinator.data.get(self._idx).model,
            "sw_version": self._coordinator.data.get(self._idx).sw_version
        }

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._coordinator.data.get(self._idx).unique_id

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def name(self):
        """Return the name of the Radio Thermostat."""
        return self._coordinator.data.get(self._idx).name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._coordinator.data.get(self._idx).temperature_unit

    @property
    def precision(self):
        """Return the precision of the system."""
        return self._coordinator.data.get(self._idx).precision

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._coordinator.data.get(self._idx).current_temperature

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._coordinator.data.get(self._idx).humidity

    @property
    def hvac_mode(self):
        """Return the current operation. head, cool idle."""
        return self._coordinator.data.get(self._idx).hvac_mode
        if self._coordinator.data.get(self._idx).preset_mode == "Off":
            return HVAC_MODE_OFF
        elif self._coordinator.data.get(self._idx).preset_mode == "Permanent Hold":
            return HVAC_MODE_HEAT
        elif self._coordinator.data.get(self._idx).preset_mode == "Follow Schedule":
            return HVAC_MODE_AUTO
        else:
            return None

    @property
    def hvac_modes(self):
        """Return the operation modes list."""
        return OPERATION_LIST

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        return self._coordinator.data.get(self._idx).hvac_action

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._coordinator.data.get(self._idx).target_temperature

    @property
    def max_temp(self):
        return self._coordinator.data.get(self._idx).max_temp

    @property
    def min_temp(self):
        return self._coordinator.data.get(self._idx).min_temp

    @property
    def preset_mode(self):
        return self._coordinator.data.get(self._idx).preset_mode

    @property
    def preset_modes(self):
        return self._coordinator.data.get(self._idx).preset_modes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._gateway.set_climate_device_temperature(self._idx, temperature)
        await self._coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode (auto, heat, off)."""
        if hvac_mode == HVAC_MODE_OFF:
            preset = "Off"
        elif hvac_mode == HVAC_MODE_HEAT:
            preset = "Permanent Hold"
        else:
            preset = "Follow Schedule"
        await self.async_set_preset_mode(preset)

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode (Off, Permanent Hold, Follow Schedule)"""
        await self._gateway.set_climate_device_preset(self._idx, preset_mode)
        await self._coordinator.async_request_refresh()
