"""Editable local clock and calendar for Freshpoint."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import FreshpointCoordinator
from .protocol import decode_rtc_datetime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one editable clock per configured unit."""
    async_add_entities(
        FreshpointDateTime(coordinator)
        for coordinator in hass.data[DOMAIN][entry.entry_id]
    )


class FreshpointDateTime(CoordinatorEntity[FreshpointCoordinator], DateTimeEntity):
    """Represent both RTC parameters as one local date/time control."""

    _attr_has_entity_name = True
    _attr_translation_key = "device_clock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FreshpointCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device['controller_id']}_device_clock"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def native_value(self) -> datetime | None:
        """Interpret the device's wall clock in Home Assistant's timezone."""
        state = self.coordinator.data
        value = decode_rtc_datetime(state.rtc_time, state.rtc_calendar)
        return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE) if value else None

    async def async_set_value(self, value: datetime) -> None:
        """Set time and date together; supported years are 2000-2099."""
        await self.coordinator.async_set_datetime(value)
