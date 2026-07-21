"""Select entities for Blauberg Freshpoint."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshpointCoordinator

DIRECTION_TO_OPTION = {
    0: "ventilation",
    1: "recovery",
    2: "supply",
    3: "extract",
}
OPTION_TO_DIRECTION = {option: value for value, option in DIRECTION_TO_OPTION.items()}
TIMER_TO_OPTION = {
    0: "off",
    1: "night",
    2: "turbo",
}
OPTION_TO_TIMER = {option: value for value, option in TIMER_TO_OPTION.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freshpoint select entities."""
    coordinators: list[FreshpointCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in coordinators:
        entities.append(FreshpointOperatingModeSelect(coordinator))
        if coordinator.data.timer_mode is not None:
            entities.append(FreshpointTimerModeSelect(coordinator))
    async_add_entities(entities)


class FreshpointOperatingModeSelect(
    CoordinatorEntity[FreshpointCoordinator], SelectEntity
):
    """Select the Freshpoint airflow operating mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "operating_mode"
    _attr_options = list(OPTION_TO_DIRECTION)

    def __init__(self, coordinator: FreshpointCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device['controller_id']}_operating_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def current_option(self) -> str | None:
        """Return the current airflow operating mode."""
        return DIRECTION_TO_OPTION.get(self.coordinator.data.direction)

    async def async_select_option(self, option: str) -> None:
        """Set the airflow operating mode."""
        try:
            direction = OPTION_TO_DIRECTION[option]
        except KeyError as exc:
            raise ValueError(f"unsupported Freshpoint operating mode {option}") from exc
        await self.coordinator.async_set_direction(direction)


class FreshpointTimerModeSelect(CoordinatorEntity[FreshpointCoordinator], SelectEntity):
    """Select the Freshpoint timer mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "timer_mode"
    _attr_options = list(OPTION_TO_TIMER)

    def __init__(self, coordinator: FreshpointCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device['controller_id']}_timer_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def current_option(self) -> str | None:
        """Return the current timer mode."""
        return TIMER_TO_OPTION.get(self.coordinator.data.timer_mode)

    async def async_select_option(self, option: str) -> None:
        """Set the timer mode."""
        try:
            timer_mode = OPTION_TO_TIMER[option]
        except KeyError as exc:
            raise ValueError(f"unsupported Freshpoint timer mode {option}") from exc
        await self.coordinator.async_set_timer_mode(timer_mode)
