"""Device clock actions independent of enabled entity platforms."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util import dt as dt_util

from .const import CONF_CONTROLLER_ID, DOMAIN
from .coordinator import FreshpointCoordinator
from .protocol import FreshpointError

SERVICE_SET_DATETIME = "set_datetime"
SERVICE_SET_CURRENT_DATETIME = "set_current_datetime"

DEVICE_SCHEMA = {
    vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
}
SET_CURRENT_DATETIME_SCHEMA = vol.Schema(DEVICE_SCHEMA)
SET_DATETIME_SCHEMA = vol.Schema({**DEVICE_SCHEMA, vol.Required("datetime"): cv.datetime})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register once during integration setup; keep actions during entry reloads."""

    def resolve_devices(call: ServiceCall) -> list[FreshpointCoordinator]:
        """Validate all devices before sending a command to any of them."""
        coordinators = []
        for device_id in dict.fromkeys(call.data["device_id"]):
            device, entry = service.async_get_device_and_config_entry(
                hass, DOMAIN, device_id
            )
            matches = [
                coordinator
                for coordinator in hass.data.get(DOMAIN, {}).get(entry.entry_id, [])
                if (DOMAIN, coordinator.device[CONF_CONTROLLER_ID]) in device.identifiers
            ]
            if len(matches) != 1:
                raise ServiceValidationError(
                    "The selected Freshpoint device is not loaded or cannot be resolved"
                )
            if matches[0] not in coordinators:
                coordinators.append(matches[0])
        return coordinators

    async def handle_clock_action(call: ServiceCall) -> None:
        coordinators = resolve_devices(call)
        value = None
        if call.service == SERVICE_SET_DATETIME:
            value = dt_util.as_local(call.data["datetime"])
            if not 2000 <= value.year <= 2099:
                raise ServiceValidationError("Freshpoint supports years 2000-2099")
        for coordinator in coordinators:
            try:
                if value is None:
                    await coordinator.async_set_current_datetime()
                else:
                    await coordinator.async_set_datetime(value)
            except (FreshpointError, OSError, ValueError) as exc:
                raise HomeAssistantError(f"Could not set the Freshpoint clock: {exc}") from exc

    hass.services.async_register(
        DOMAIN, SERVICE_SET_DATETIME, handle_clock_action, schema=SET_DATETIME_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_CURRENT_DATETIME, handle_clock_action,
        schema=SET_CURRENT_DATETIME_SCHEMA,
    )
