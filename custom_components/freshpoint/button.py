"""Button entities for Blauberg Freshpoint."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshpointCoordinator

FILTER_RESET_DESCRIPTION = ButtonEntityDescription(
    key="filter_reset",
    translation_key="filter_reset",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freshpoint buttons."""
    coordinators: list[FreshpointCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FreshpointFilterResetButton(coordinator)
        for coordinator in coordinators
        if coordinator.data.filter_status is not None
    )


class FreshpointFilterResetButton(
    CoordinatorEntity[FreshpointCoordinator], ButtonEntity
):
    """Reset the Freshpoint filter replacement countdown."""

    _attr_has_entity_name = True
    entity_description = FILTER_RESET_DESCRIPTION

    def __init__(self, coordinator: FreshpointCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device['controller_id']}_filter_reset"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    async def async_press(self) -> None:
        """Reset the filter countdown."""
        await self.coordinator.async_reset_filter()
