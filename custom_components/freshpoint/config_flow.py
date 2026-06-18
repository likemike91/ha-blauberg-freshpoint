"""Config flow for Blauberg Freshpoint."""

from __future__ import annotations

from functools import partial
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CONTROLLER_ID,
    CONF_DEVICES,
    DEFAULT_DISCOVERY_BROADCAST,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DOMAIN,
    PARAM_DEVICE_TYPE,
)
from .protocol import FreshpointClient, FreshpointError, FreshpointDiscoveryResult, discover_freshpoints

CONF_BROADCAST_ADDRESS = "broadcast_address"
CONF_SELECTED_DEVICES = "selected_devices"


class FreshpointConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Blauberg Freshpoint."""

    VERSION = 1

    def __init__(self) -> None:
        self._password = DEFAULT_PASSWORD
        self._discovered: dict[str, FreshpointDiscoveryResult] = {}

    async def async_step_user(self, user_input=None):
        """Discover Freshpoint units on the local network."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            broadcast_address = user_input[CONF_BROADCAST_ADDRESS]
            try:
                discovered = await self.hass.async_add_executor_job(
                    partial(
                        discover_freshpoints,
                        broadcast_address=broadcast_address,
                        password=self._password,
                    )
                )
            except OSError:
                errors["base"] = "cannot_discover"
            else:
                configured_ids = {
                    device[CONF_CONTROLLER_ID]
                    for entry in self._async_current_entries()
                    for device in entry.data.get(CONF_DEVICES, [])
                }
                self._discovered = {
                    device.controller_id: device
                    for device in discovered
                    if device.controller_id not in configured_ids
                }
                if not self._discovered:
                    errors["base"] = "no_devices_found"
                else:
                    return await self.async_step_select()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROADCAST_ADDRESS, default=DEFAULT_DISCOVERY_BROADCAST): str,
                    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select(self, user_input=None):
        """Select which discovered Freshpoint units to add."""
        errors: dict[str, str] = {}
        options = {
            controller_id: f"{device.host} ({controller_id})"
            for controller_id, device in self._discovered.items()
        }

        if user_input is not None:
            selected_ids = user_input[CONF_SELECTED_DEVICES]
            if not selected_ids:
                errors["base"] = "no_devices_selected"
            else:
                devices = [
                    {
                        CONF_NAME: f"{DEFAULT_NAME} {index}",
                        CONF_HOST: self._discovered[controller_id].host,
                        CONF_CONTROLLER_ID: controller_id,
                        CONF_PASSWORD: self._password,
                        "device_type": self._discovered[controller_id].device_type,
                    }
                    for index, controller_id in enumerate(selected_ids, start=1)
                ]
                unique_id = "-".join(sorted(selected_ids))
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_NAME: DEFAULT_NAME, CONF_DEVICES: devices},
                )

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SELECTED_DEVICES,
                        default=list(options),
                    ): cv.multi_select(options),
                }
            ),
            errors=errors,
        )

    async def async_step_manual(self, user_input=None):
        """Handle manual setup when broadcast discovery is unavailable."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            controller_id = user_input[CONF_CONTROLLER_ID]
            password = user_input[CONF_PASSWORD]

            try:
                client = FreshpointClient(host, controller_id, password)
                values = await self.hass.async_add_executor_job(client.read, [PARAM_DEVICE_TYPE])
            except (FreshpointError, OSError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(controller_id)
                self._abort_if_unique_id_configured()
                title = user_input[CONF_NAME]
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_NAME: title,
                        CONF_DEVICES: [
                            {
                                CONF_NAME: title,
                                CONF_HOST: host,
                                CONF_CONTROLLER_ID: controller_id,
                                CONF_PASSWORD: password,
                                "device_type": values.get(PARAM_DEVICE_TYPE),
                            }
                        ],
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_CONTROLLER_ID): str,
                    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return FreshpointOptionsFlow(config_entry)


class FreshpointOptionsFlow(config_entries.OptionsFlow):
    """Handle Freshpoint options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
