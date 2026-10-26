"""Isolated coordinator tests; these do not replace Home Assistant runtime tests."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from .test_protocol import protocol
from custom_components.freshpoint.polling import ENTITY_READS


def load_coordinator():
    """Provide only the HA boundaries needed for selective-polling tests."""
    names = (
        "homeassistant", "homeassistant.config_entries", "homeassistant.const",
        "homeassistant.core", "homeassistant.helpers", "homeassistant.helpers.entity_registry",
        "homeassistant.helpers.device_registry", "homeassistant.helpers.update_coordinator",
        "homeassistant.util", "homeassistant.util.dt",
    )
    modules = {name: types.ModuleType(name) for name in names}
    modules["homeassistant.config_entries"].ConfigEntry = object
    modules["homeassistant.const"].CONF_HOST = "host"
    modules["homeassistant.const"].CONF_PASSWORD = "password"
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.helpers.entity_registry"].async_get = lambda hass: hass.registry
    modules["homeassistant.helpers.device_registry"].async_get = lambda hass: hass.devices

    class Coordinator:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

    modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = Coordinator
    modules["homeassistant.helpers.update_coordinator"].UpdateFailed = RuntimeError
    path = Path(__file__).parents[1] / "custom_components/freshpoint/coordinator.py"
    spec = importlib.util.spec_from_file_location("custom_components.freshpoint._test_coordinator", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = load_coordinator()
        self.entries = {
            f"{platform}.unit_{key}": types.SimpleNamespace(disabled_by="user")
            for platform, key, _, _ in ENTITY_READS
        }
        registry = types.SimpleNamespace(
            async_get_entity_id=lambda platform, domain, uid: f"{platform}.{uid}",
            async_get=lambda entity_id: self.entries[entity_id],
        )
        self.coordinator = object.__new__(self.module.FreshpointCoordinator)
        self.coordinator.device = {"controller_id": "unit"}
        self.coordinator.hass = types.SimpleNamespace(registry=registry)
        self.coordinator._diagnostic_cache = {}
        self.coordinator._diagnostic_updated = {}
        self.calls = []

        def read_state(params):
            self.calls.append(list(params))
            return protocol.FreshpointState(values={param: param for param in params})

        self.coordinator.client = types.SimpleNamespace(read_state=read_state)

        async def call(action, *args):
            return action(*args)

        self.coordinator._async_call_with_rediscovery = call

    def enable(self, platform, key):
        self.entries[f"{platform}.unit_{key}"].disabled_by = None

    async def test_all_disabled_skips_network(self):
        state = await self.coordinator._async_update_data()
        self.assertEqual(self.calls, [])
        self.assertEqual(state.values, {})

    async def test_hourly_diagnostic_cache_and_disable(self):
        self.enable("sensor", "wifi_channel")
        with patch.object(self.module, "monotonic", return_value=100):
            first = await self.coordinator._async_update_data()
        with patch.object(self.module, "monotonic", return_value=120):
            second = await self.coordinator._async_update_data()
        self.assertEqual(self.calls, [[154]])
        self.assertEqual(first.values, second.values)
        with patch.object(self.module, "monotonic", return_value=3700):
            await self.coordinator._async_update_data()
        self.assertEqual(self.calls, [[154], [154]])
        self.entries["sensor.unit_wifi_channel"].disabled_by = "user"
        state = await self.coordinator._async_update_data()
        self.assertEqual(state.values, {})
        self.assertEqual(len(self.calls), 2)

    async def test_fast_fields_continue_while_diagnostics_cached(self):
        self.enable("sensor", "wifi_channel")
        self.enable("sensor", "humidity")
        with patch.object(self.module, "monotonic", return_value=100):
            await self.coordinator._async_update_data()
            second = await self.coordinator._async_update_data()
        self.assertEqual(self.calls, [[37, 154], [37]])
        self.assertEqual(second.values, {37: 37, 154: 154})

    async def test_newly_enabled_setting_is_read_next_update(self):
        await self.coordinator._async_update_data()
        self.enable("number", "co2_threshold")
        await self.coordinator._async_update_data()
        self.assertEqual(self.calls, [[26]])

    async def test_shared_flags_polled_only_once(self):
        self.enable("binary_sensor", "humidity_threshold_exceeded")
        self.enable("binary_sensor", "co2_threshold_exceeded")
        await self.coordinator._async_update_data()
        self.assertEqual(self.calls, [[132]])


    async def test_rediscovery_remains_keyword_only(self):
        self.coordinator._rediscovery_lock = asyncio.Lock()
        self.coordinator.config_entry = types.SimpleNamespace(options={}, data={})
        self.coordinator.device["password"] = "1111"
        self.coordinator.client.host = "192.0.2.1"

        async def execute(action):
            return action()

        self.coordinator.hass.async_add_executor_job = execute
        def discover(**kwargs):
            self.assertEqual(kwargs["password"], "1111")
            return [protocol.FreshpointDiscoveryResult("192.0.2.1", "unit", 17)]
        with patch.object(self.module, "discover_freshpoints", discover):
            self.assertTrue(await self.coordinator._async_rediscover_host())
