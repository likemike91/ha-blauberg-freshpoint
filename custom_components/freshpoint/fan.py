"""Fan entity for Blauberg Freshpoint."""

from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshpointCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Freshpoint fan entity."""
    coordinators: list[FreshpointCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(FreshpointFan(coordinator) for coordinator in coordinators)


class FreshpointFan(CoordinatorEntity[FreshpointCoordinator], FanEntity):
    """Representation of a Freshpoint fan."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_has_entity_name = True
    _attr_translation_key = "fan"
    _attr_speed_count = 91

    def __init__(self, coordinator: FreshpointCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device['controller_id']}_fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        if self.coordinator.data.power is None:
            return None
        return self.coordinator.data.power == 1

    @property
    def percentage(self) -> int | None:
        """Return current percentage."""
        return self.coordinator.data.percentage

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn the fan on."""
        await self.coordinator.async_set_power(True)
        if percentage is not None:
            await self.coordinator.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        await self.coordinator.async_set_power(False)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan percentage."""
        if percentage <= 0:
            await self.async_turn_off()
            return
        await self.coordinator.async_set_power(True)
        await self.coordinator.async_set_percentage(percentage)
