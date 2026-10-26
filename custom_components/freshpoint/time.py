"""Local display-off interval controls for Freshpoint."""

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FreshpointSettingEntity
from .settings import SETTINGS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    """Register the two minute-resolution time fields."""
    async_add_entities(
        FreshpointTime(coordinator, setting)
        for coordinator in hass.data[DOMAIN][entry.entry_id]
        for setting in SETTINGS if setting.platform == "time"
    )


class FreshpointTime(FreshpointSettingEntity, TimeEntity):
    """Represent a local wall time without a date or timezone."""

    @property
    def native_value(self) -> time | None:
        value = self.setting_value
        return time(value // 60, value % 60) if value is not None else None

    async def async_set_value(self, value: time) -> None:
        if value.second or value.microsecond:
            raise ValueError("Freshpoint display times have minute resolution")
        await self.coordinator.async_set_setting(
            self.setting.key, value.hour * 60 + value.minute
        )
