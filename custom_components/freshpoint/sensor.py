"""Sensor entities for Blauberg Freshpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshpointCoordinator
from .protocol import FreshpointState


@dataclass(frozen=True, kw_only=True)
class FreshpointSensorDescription(SensorEntityDescription):
    """Describes a Freshpoint sensor."""

    value_fn: Callable[[FreshpointState], int | None]


SENSORS: tuple[FreshpointSensorDescription, ...] = (
    FreshpointSensorDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.humidity,
    ),
    FreshpointSensorDescription(
        key="supply_rpm",
        translation_key="supply_rpm",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.supply_rpm,
    ),
    FreshpointSensorDescription(
        key="extract_rpm",
        translation_key="extract_rpm",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.extract_rpm,
    ),
    FreshpointSensorDescription(
        key="filter_status",
        translation_key="filter_status",
        value_fn=lambda state: state.filter_status,
    ),
    FreshpointSensorDescription(
        key="direction",
        translation_key="direction",
        value_fn=lambda state: state.direction,
    ),
    FreshpointSensorDescription(
        key="recovery_efficiency",
        translation_key="recovery_efficiency",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.recovery_efficiency,
    ),
    FreshpointSensorDescription(
        key="device_type",
        translation_key="device_type",
        value_fn=lambda state: state.device_type,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freshpoint sensors."""
    coordinators: list[FreshpointCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FreshpointSensor(coordinator, description)
        for coordinator in coordinators
        for description in SENSORS
    )


class FreshpointSensor(CoordinatorEntity[FreshpointCoordinator], SensorEntity):
    """Freshpoint diagnostic/state sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FreshpointCoordinator,
        description: FreshpointSensorDescription,
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
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
