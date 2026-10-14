"""Support for (temperature, not thermostat) sensors."""
from datetime import timedelta
import logging
import async_timeout

import voluptuous as vol
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_TOKEN,
    UnitOfTemperature,
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
    """Set up Salus sensors from a config entry."""

    gateway = hass.data[DOMAIN][config_entry.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        async with async_timeout.timeout(10):
            await gateway.poll_status()
            return gateway.get_sensor_devices()

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

    async_add_entities(SalusSensor(coordinator, idx, gateway) for idx
                       in coordinator.data)

    async def async_update_climate_data():
        """Fetch climate device data (used here only to expose the SQ610
        floor sensor reading as its own sensor.* entity)."""
        async with async_timeout.timeout(10):
            await gateway.poll_status()
            return gateway.get_climate_devices()

    climate_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="salus_floor_temperature",
        update_method=async_update_climate_data,
        update_interval=timedelta(seconds=30),
    )

    await climate_coordinator.async_refresh()

    # Only thermostats that already report a floor sensor reading get an
    # entity. If the S1/S2 floor sensor is wired up later, reload the
    # integration to pick it up.
    async_add_entities(
        SalusFloorTemperatureSensor(climate_coordinator, idx, gateway)
        for idx in climate_coordinator.data
        if climate_coordinator.data.get(idx).current_floor_temperature is not None
    )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    pass


class SalusSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, coordinator, idx, gateway):
        """Initialize the sensor."""
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
        """Return the name of the sensor."""
        return self._coordinator.data.get(self._idx).name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._coordinator.data.get(self._idx).state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._coordinator.data.get(self._idx).unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._coordinator.data.get(self._idx).device_class


class SalusFloorTemperatureSensor(SensorEntity):
    """Floor temperature reading from the S1/S2 sensor input of a SQ610
    thermostat (configured as "floor sensor" in the installer menu).
    Sourced from the climate device's current_floor_temperature, not from
    gateway.get_sensor_devices()."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, idx, gateway):
        """Initialize the sensor. idx is the parent thermostat's unique_id."""
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
    def available(self):
        """Return if entity is available."""
        device = self._coordinator.data.get(self._idx)
        return device is not None and device.available

    @property
    def device_info(self):
        """Return the device info. Same identifiers as the climate entity,
        so this sensor is attached to the same thermostat device."""
        device = self._coordinator.data.get(self._idx)
        return {
            "name": device.name,
            "identifiers": {("salus", device.unique_id)},
            "manufacturer": device.manufacturer,
            "model": device.model,
            "sw_version": device.sw_version,
        }

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._idx}_floor"

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._coordinator.data.get(self._idx).name} Floor temperature"

    @property
    def native_value(self):
        """Return the floor temperature reported by the thermostat."""
        return self._coordinator.data.get(self._idx).current_floor_temperature
