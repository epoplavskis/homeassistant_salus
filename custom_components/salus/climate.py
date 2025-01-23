"""Support for climate devices (thermostats)."""
from datetime import timedelta
import logging
import async_timeout

import voluptuous as vol
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
    FAN_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_TOKEN
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Salus thermostats from a config entry."""

    gateway = hass.data[DOMAIN][config_entry.entry_id]

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    pass


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
        # definetly needs a better approach
        # return self._coordinator.data.get(self._idx).supported_features

        supported_features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.FAN_MODE
        return supported_features

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
        return self._coordinator.data.get(self._idx).current_humidity

    @property
    def hvac_mode(self):
        """Return the current operation. head, cool idle."""
        return self._coordinator.data.get(self._idx).hvac_mode

    @property
    def hvac_modes(self):
        """Return the operation modes list."""
        return self._coordinator.data.get(self._idx).hvac_modes

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

    @property
    def fan_mode(self):
        return self._coordinator.data.get(self._idx).fan_mode

    @property
    def fan_modes(self):
        return self._coordinator.data.get(self._idx).fan_modes

    @property
    def locked(self):
        return self._coordinator.data.get(self._idx).locked

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._gateway.set_climate_device_temperature(self._idx, temperature)
        await self._coordinator.async_request_refresh()

    # TODO: Not listed in methods here https://developers.home-assistant.io/docs/core/entity/climate/#methods
    # async def async_set_locked(self, locked):
    #     """Set locked (true, false)."""
    #     await self._gateway.set_climate_device_locked(self._idx, locked)
    #     await self._coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode):
        """Set fan speed (auto, low, medium, high, off)."""
        _LOGGER.info('set_fan_mode: ' + str(fan_mode))
        if fan_mode == FAN_OFF:
            mode = "Off"
        elif fan_mode == FAN_LOW:
            mode = "Low"
        elif fan_mode == FAN_MEDIUM:
            mode = "Medium"
        elif fan_mode == FAN_HIGH:
            mode = "High"
        else:
            mode = "Auto"
        await self._gateway.set_climate_device_fan_mode(self._idx, mode)
        await self._coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode (auto, heat, cool)."""
        if hvac_mode == HVACMode.HEAT:
            mode = "heat"
        elif hvac_mode == HVACMode.COOL:
            mode = "cool"
        else:
            mode = "auto"
        await self._gateway.set_climate_device_mode(self._idx, mode)
        await self._coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode (Off, Permanent Hold, Eco, Temporary Hold, Follow Schedule)"""
        await self._gateway.set_climate_device_preset(self._idx, preset_mode)
        await self._coordinator.async_request_refresh()
