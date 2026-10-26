"""Clock actions with native fan/group targets and legacy device selection."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized, UnknownUser
from homeassistant.helpers import config_validation as cv, entity_registry as er, service
from homeassistant.util import dt as dt_util

from .const import CONF_CONTROLLER_ID, DOMAIN
from .coordinator import FreshpointCoordinator
from .protocol import FreshpointError

SERVICE_SET_DATETIME = "set_datetime"
SERVICE_SET_CURRENT_DATETIME = "set_current_datetime"

SET_CURRENT_DATETIME_SCHEMA = cv.make_entity_service_schema({})
SET_DATETIME_SCHEMA = cv.make_entity_service_schema({vol.Required("datetime"): cv.datetime})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register once during integration setup; keep actions during entry reloads."""

    async def resolve_devices(call: ServiceCall) -> list[FreshpointCoordinator]:
        """Validate all devices before sending a command to any of them."""
        coordinators = []
        device_ids = list(call.data.get("device_id", []))
        # HA resolves fan groups, nested groups, areas and labels using the same
        # target machinery as built-in actions. Never depend on enabled RTC entities.
        entity_ids = await service.async_extract_entity_ids(call, expand_group=True)
        registry = er.async_get(hass)
        user = None
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
        for entity_id in sorted(entity_ids):
            entity = registry.async_get(entity_id)
            if not entity_id.startswith("fan.") or entity is None or entity.platform != DOMAIN:
                continue
            if user is not None and not user.permissions.check_entity(entity_id, POLICY_CONTROL):
                raise Unauthorized(context=call.context, entity_id=entity_id)
            if entity.device_id:
                device_ids.append(entity.device_id)
        for device_id in dict.fromkeys(device_ids):
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
        if not coordinators:
            raise ServiceValidationError("Select at least one loaded Freshpoint fan, group or device")
        return coordinators

    async def handle_clock_action(call: ServiceCall) -> None:
        coordinators = await resolve_devices(call)
        value = None
        if call.service == SERVICE_SET_DATETIME:
            value = dt_util.as_local(call.data["datetime"])
            if not 2000 <= value.year <= 2099:
                raise ServiceValidationError("Freshpoint supports years 2000-2099")
        failures = []
        for coordinator in coordinators:
            try:
                if value is None:
                    await coordinator.async_set_current_datetime()
                else:
                    await coordinator.async_set_datetime(value)
            except (FreshpointError, OSError, ValueError) as exc:
                failures.append(f"{coordinator.device[CONF_CONTROLLER_ID]}: {exc}")
        if failures:
            raise HomeAssistantError("Could not set all Freshpoint clocks: " + "; ".join(failures))

    hass.services.async_register(
        DOMAIN, SERVICE_SET_DATETIME, handle_clock_action, schema=SET_DATETIME_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_CURRENT_DATETIME, handle_clock_action,
        schema=SET_CURRENT_DATETIME_SCHEMA,
    )
