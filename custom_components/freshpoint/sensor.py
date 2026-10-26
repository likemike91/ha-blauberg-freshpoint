"""Sensor entities for Blauberg Freshpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EntityCategory,
    PERCENTAGE,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshpointCoordinator
from .protocol import FreshpointState, decode_timer_seconds, decode_alarms, decode_firmware
from .polling import ENTITY_READS


@dataclass(frozen=True, kw_only=True)
class FreshpointSensorDescription(SensorEntityDescription):
    """Describes a Freshpoint sensor."""

    value_fn: Callable[[FreshpointState], int | float | str | None]


SENSORS: tuple[FreshpointSensorDescription, ...] = (
    FreshpointSensorDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.outdoor_temperature,
    ),
    FreshpointSensorDescription(
        key="supply_temperature",
        translation_key="supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.supply_temperature,
    ),
    FreshpointSensorDescription(
        key="extract_inlet_temperature",
        translation_key="extract_inlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.extract_inlet_temperature,
    ),
    FreshpointSensorDescription(
        key="extract_outlet_temperature",
        translation_key="extract_outlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.extract_outlet_temperature,
    ),
    FreshpointSensorDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.humidity,
    ),
    FreshpointSensorDescription(
        key="co2",
        translation_key="co2",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.co2,
    ),
    FreshpointSensorDescription(
        key="voc",
        translation_key="voc",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.voc,
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
        key="filter_countdown",
        translation_key="filter_countdown",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.filter_countdown_hours,
    ),
    FreshpointSensorDescription(
        key="motor_runtime",
        translation_key="motor_runtime",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda state: state.motor_runtime_hours,
    ),
    FreshpointSensorDescription(
        key="fault_warning",
        translation_key="fault_warning",
        device_class=SensorDeviceClass.ENUM,
        options=["normal", "alarm", "warning", "unknown"],
        value_fn=lambda state: {
            0: "normal",
            1: "alarm",
            2: "warning",
        }.get(state.fault_warning, "unknown"),
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


SENSORS += (
    FreshpointSensorDescription(
        key="wifi_channel", translation_key="wifi_channel",
        value_fn=lambda state: state.values.get(154),
    ),
    FreshpointSensorDescription(
        key="current_ip", translation_key="current_ip",
        value_fn=lambda state: (
            ".".join(str(part) for part in value.to_bytes(4, "little"))
            if isinstance((value := state.values.get(163)), int) and 0 <= value < 1 << 32
            else None
        ),
    ),
    FreshpointSensorDescription(
        key="timer_remaining", translation_key="timer_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda state: decode_timer_seconds(state.values.get(11)),
    ),
    FreshpointSensorDescription(
        key="rtc_battery", translation_key="rtc_battery",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        value_fn=lambda state: state.values.get(36),
    ),
    FreshpointSensorDescription(
        key="alarm_details", translation_key="alarm_details",
        value_fn=lambda state: (
            len(alarms) if (alarms := decode_alarms(state.values.get(127))) is not None else None
        ),
    ),
    FreshpointSensorDescription(
        key="firmware", translation_key="firmware",
        value_fn=lambda state: (
            firmware[0] if (firmware := decode_firmware(state.values.get(134))) else None
        ),
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
        defaults = {suffix: default for platform, suffix, _, default in ENTITY_READS if platform == "sensor"}
        self._attr_entity_registry_enabled_default = defaults[description.key]
        if description.key in {
            "supply_rpm", "extract_rpm", "filter_status", "filter_countdown",
            "motor_runtime", "fault_warning", "direction", "recovery_efficiency", "device_type",
            "rtc_battery", "alarm_details", "firmware", "wifi_channel", "current_ip",
        }:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"{device['controller_id']}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Expose documented alarm codes and firmware build date."""
        if self.entity_description.key == "alarm_details":
            alarms = decode_alarms(self.coordinator.data.values.get(127))
            return {"alarms": alarms} if alarms is not None else None
        if self.entity_description.key == "firmware":
            firmware = decode_firmware(self.coordinator.data.values.get(134))
            return {"build_date": firmware[1]} if firmware else None
        return None
