"""Bounded configuration numbers for Freshpoint."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FreshpointSettingEntity
from .settings import SETTINGS, Setting


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    """Register configurable thresholds and durations."""
    async_add_entities(
        FreshpointNumber(coordinator, setting)
        for coordinator in hass.data[DOMAIN][entry.entry_id]
        for setting in SETTINGS if setting.platform == "number"
    )


class FreshpointNumber(FreshpointSettingEntity, NumberEntity):
    """Expose only documented numeric ranges."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(self, coordinator, setting: Setting) -> None:
        super().__init__(coordinator, setting)
        self._attr_native_min_value = setting.minimum
        self._attr_native_max_value = setting.maximum
        self._attr_native_unit_of_measurement = setting.unit

    @property
    def native_value(self) -> int | None:
        return self.setting_value

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_setting(self.setting.key, value)
