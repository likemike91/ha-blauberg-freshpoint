"""Switch entities for Blauberg Freshpoint."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
    """Set up Freshpoint switches."""
    coordinators: list[FreshpointCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FreshpointHeaterSwitch(coordinator)
        for coordinator in coordinators
        if coordinator.data.heater_control is not None
    )


class FreshpointHeaterSwitch(CoordinatorEntity[FreshpointCoordinator], SwitchEntity):
    """Control whether the Freshpoint heater may operate."""

    _attr_has_entity_name = True
    _attr_translation_key = "heater"

    def __init__(self, coordinator: FreshpointCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device['controller_id']}_heater"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def is_on(self) -> bool | None:
        """Return whether heater control is enabled."""
        if self.coordinator.data.heater_control is None:
            return None
        return self.coordinator.data.heater_control == 1

    async def async_turn_on(self, **kwargs) -> None:
        """Enable heater control."""
        await self.coordinator.async_set_heater(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable heater control."""
        await self.coordinator.async_set_heater(False)
