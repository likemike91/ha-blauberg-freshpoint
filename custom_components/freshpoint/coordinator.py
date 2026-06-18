"""Coordinator for Blauberg Freshpoint devices."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    READ_PARAMS,
)
from .protocol import FreshpointClient, FreshpointError, FreshpointState

_LOGGER = logging.getLogger(__name__)


class FreshpointCoordinator(DataUpdateCoordinator[FreshpointState]):
    """Coordinates polling and command calls for one Freshpoint unit."""

    def __init__(self, hass: HomeAssistant, device: dict) -> None:
        self.device = device
        self.client = FreshpointClient(
            device[CONF_HOST],
            device["controller_id"],
            device[CONF_PASSWORD],
            port=device.get("port", DEFAULT_PORT),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device['controller_id']}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )

    async def _async_update_data(self) -> FreshpointState:
        try:
            return await self.hass.async_add_executor_job(self.client.read_state, READ_PARAMS)
        except (FreshpointError, OSError) as exc:
            raise UpdateFailed(str(exc)) from exc

    async def async_set_power(self, enabled: bool) -> None:
        """Set power and refresh state."""
        await self.hass.async_add_executor_job(self.client.set_power, enabled)
        await self.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set speed percentage and refresh state."""
        await self.hass.async_add_executor_job(self.client.set_percentage, percentage)
        await self.async_request_refresh()
