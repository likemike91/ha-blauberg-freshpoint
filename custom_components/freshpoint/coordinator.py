"""Coordinator for Blauberg Freshpoint devices."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from functools import partial
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BROADCAST_ADDRESS,
    CONF_CONTROLLER_ID,
    CONF_DEVICES,
    CONF_SOURCE_ADDRESS,
    DEFAULT_PORT,
    DEFAULT_DISCOVERY_BROADCAST,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    READ_PARAMS,
)
from .protocol import (
    FreshpointClient,
    FreshpointError,
    FreshpointState,
    FreshpointTimeoutError,
    discover_freshpoints,
)

_LOGGER = logging.getLogger(__name__)


class FreshpointCoordinator(DataUpdateCoordinator[FreshpointState]):
    """Coordinates polling and command calls for one Freshpoint unit."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, device: dict) -> None:
        self.config_entry = config_entry
        self.device = device
        self._rediscovery_lock = asyncio.Lock()
        self.client = FreshpointClient(
            device[CONF_HOST],
            device[CONF_CONTROLLER_ID],
            device[CONF_PASSWORD],
            port=device.get("port", DEFAULT_PORT),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device[CONF_CONTROLLER_ID]}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )

    async def _async_update_data(self) -> FreshpointState:
        try:
            return await self._async_call_with_rediscovery(self.client.read_state, READ_PARAMS)
        except (FreshpointError, OSError) as exc:
            raise UpdateFailed(str(exc)) from exc

    async def _async_call_with_rediscovery(self, action, *args):
        """Run a blocking client call, rediscovering the device after a transport failure."""
        try:
            return await self.hass.async_add_executor_job(action, *args)
        except (FreshpointTimeoutError, OSError):
            if not await self._async_rediscover_host():
                raise
            return await self.hass.async_add_executor_job(action, *args)

    async def _async_rediscover_host(self) -> bool:
        """Find this controller ID again and update its cached host."""
        async with self._rediscovery_lock:
            broadcast_address = self.config_entry.options.get(
                CONF_BROADCAST_ADDRESS
            ) or self.config_entry.data.get(
                CONF_BROADCAST_ADDRESS, DEFAULT_DISCOVERY_BROADCAST
            )
            source_address = self.config_entry.options.get(
                CONF_SOURCE_ADDRESS
            ) or self.config_entry.data.get(CONF_SOURCE_ADDRESS, "")
            discovered = await self.hass.async_add_executor_job(
                partial(
                    discover_freshpoints,
                    broadcast_address=broadcast_address,
                    password=self.device[CONF_PASSWORD],
                    source_address=source_address or None,
                    port=self.device.get("port", DEFAULT_PORT),
                )
            )
            controller_id = self.device[CONF_CONTROLLER_ID]
            match = next(
                (device for device in discovered if device.controller_id == controller_id),
                None,
            )
            if match is None:
                return False

            if match.host != self.client.host:
                _LOGGER.info(
                    "Freshpoint device %s moved from %s to %s",
                    controller_id,
                    self.client.host,
                    match.host,
                )
                self._update_host(match.host)
            return True

    def _update_host(self, host: str) -> None:
        """Update the runtime client and persisted config entry host."""
        self.client.host = host
        self.device = {**self.device, CONF_HOST: host}
        devices = [
            self.device
            if device[CONF_CONTROLLER_ID] == self.device[CONF_CONTROLLER_ID]
            else device
            for device in self.config_entry.data[CONF_DEVICES]
        ]
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_DEVICES: devices},
        )

    async def async_set_power(self, enabled: bool) -> None:
        """Set power and refresh state."""
        await self._async_call_with_rediscovery(self.client.set_power, enabled)
        if self.data is not None:
            self.async_set_updated_data(replace(self.data, power=1 if enabled else 0))
        await self.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set speed percentage and refresh state."""
        bounded_percentage = max(10, min(100, percentage))
        await self._async_call_with_rediscovery(
            self.client.set_percentage,
            bounded_percentage,
        )
        if self.data is not None:
            self.async_set_updated_data(
                replace(self.data, power=1, speed_mode=255, percentage=bounded_percentage)
            )
        await self.async_request_refresh()
