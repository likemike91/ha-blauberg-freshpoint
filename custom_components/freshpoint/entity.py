"""Shared setup for writable Freshpoint setting entities."""

from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshpointCoordinator
from .settings import Setting


class FreshpointSettingEntity(CoordinatorEntity[FreshpointCoordinator]):
    """Keep registry identity and polling defaults aligned with the setting."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreshpointCoordinator, setting: Setting) -> None:
        super().__init__(coordinator)
        self.setting = setting
        self._attr_translation_key = setting.key
        self._attr_entity_registry_enabled_default = setting.enabled_default
        if setting.config:
            self._attr_entity_category = EntityCategory.CONFIG
        device = coordinator.device
        self._attr_unique_id = f"{device['controller_id']}_{setting.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device["controller_id"])},
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": device[CONF_NAME],
        }

    @property
    def setting_value(self) -> int | None:
        """Return the validated field from the latest selective poll."""
        return self.setting.decode(self.coordinator.data.values.get(self.setting.param))
