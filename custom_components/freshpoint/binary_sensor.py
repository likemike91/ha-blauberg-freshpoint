"""Binary sensor entities for Blauberg Freshpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshpointCoordinator
from .protocol import FreshpointState


@dataclass(frozen=True, kw_only=True)
class FreshpointBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Freshpoint binary sensor."""

    value_fn: Callable[[FreshpointState], bool | None]
    supported_fn: Callable[[FreshpointState], bool] = lambda _state: True


BINARY_SENSORS = (
    FreshpointBinarySensorDescription(
        key="filter",
        translation_key="filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: None
        if state.filter_status is None
        else state.filter_status == 1,
        supported_fn=lambda state: state.filter_status is not None,
    ),
    FreshpointBinarySensorDescription(
        key="heater_active",
        translation_key="heater_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda state: None
        if state.heater_status is None
        else state.heater_status == 1,
        supported_fn=lambda state: state.heater_status is not None,
    ),
    FreshpointBinarySensorDescription(
        key="frost_protection",
        translation_key="frost_protection",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda state: None
        if state.frost_protection is None
        else state.frost_protection == 1,
        supported_fn=lambda state: state.frost_protection is not None,
    ),
    FreshpointBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: None
        if state.fault_warning is None
        else state.fault_warning != 0,
        supported_fn=lambda state: state.fault_warning is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freshpoint binary sensors."""
    coordinators: list[FreshpointCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FreshpointBinarySensor(coordinator, description)
        for coordinator in coordinators
        for description in BINARY_SENSORS
        if description.supported_fn(coordinator.data)
    )


class FreshpointBinarySensor(
    CoordinatorEntity[FreshpointCoordinator], BinarySensorEntity
):
    """Freshpoint binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreshpointCoordinator,
        description: FreshpointBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self.entity_description = description
        self._attr_unique_id = f"{device['controller_id']}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)
