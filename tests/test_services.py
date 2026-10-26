"""Test device actions with real schemas and isolated Home Assistant boundaries."""

from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import voluptuous as vol
import yaml

from .test_protocol import protocol

ROOT = Path(__file__).parents[1]
LOCAL_TZ = ZoneInfo("Europe/Vienna")


class ValidationError(Exception):
    """Stand-in for Home Assistant's ServiceValidationError."""


def local_time(value):
    return value.replace(tzinfo=LOCAL_TZ) if value.tzinfo is None else value.astimezone(LOCAL_TZ)


def load_services(resolve):
    names = (
        "homeassistant", "homeassistant.core", "homeassistant.exceptions",
        "homeassistant.helpers", "homeassistant.helpers.service",
        "homeassistant.helpers.config_validation", "homeassistant.util",
        "homeassistant.util.dt", "custom_components.freshpoint.coordinator",
    )
    modules = {name: types.ModuleType(name) for name in names}
    modules["homeassistant.core"].HomeAssistant = object
    modules["homeassistant.core"].ServiceCall = object
    modules["homeassistant.core"].callback = lambda function: function
    modules["homeassistant.exceptions"].HomeAssistantError = RuntimeError
    modules["homeassistant.exceptions"].ServiceValidationError = ValidationError
    modules["homeassistant.helpers.service"].async_get_device_and_config_entry = resolve
    cv = modules["homeassistant.helpers.config_validation"]
    cv.ensure_list = lambda value: value if isinstance(value, list) else [value]
    cv.string = str

    def parse_datetime(value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError) as exc:
            raise vol.Invalid("Invalid datetime") from exc

    cv.datetime = parse_datetime
    modules["homeassistant.util.dt"].as_local = local_time
    modules["custom_components.freshpoint.coordinator"].FreshpointCoordinator = object
    spec = importlib.util.spec_from_file_location(
        "custom_components.freshpoint._test_services",
        ROOT / "custom_components/freshpoint/services.py",
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.coordinators = [
            types.SimpleNamespace(
                device={"controller_id": controller},
                async_set_datetime=AsyncMock(),
                async_set_current_datetime=AsyncMock(),
            )
            for controller in ("first", "second", "third")
        ]
        self.devices = {
            "device1": ("first", "entry1"),
            "device2": ("second", "entry1"),
            "device3": ("third", "entry2"),
        }

        def resolve(hass, domain, device_id):
            self.assertEqual(domain, "freshpoint")
            if device_id not in self.devices:
                raise ValidationError("Unknown or unloaded device")
            controller, entry_id = self.devices[device_id]
            return (
                types.SimpleNamespace(identifiers={(domain, controller)}),
                types.SimpleNamespace(entry_id=entry_id),
            )

        self.module = load_services(resolve)
        self.actions = {}

        def register(domain, name, handler, schema):
            self.assertEqual(domain, "freshpoint")
            self.actions[name] = (handler, schema)

        self.hass = types.SimpleNamespace(
            data={"freshpoint": {"entry1": self.coordinators[:2], "entry2": self.coordinators[2:]}},
            services=types.SimpleNamespace(async_register=register),
        )
        self.module.async_setup_services(self.hass)

    async def call(self, action, data):
        handler, schema = self.actions[action]
        await handler(types.SimpleNamespace(service=action, data=schema(data)))

    async def test_current_clock_routes_selected_devices_only(self):
        await self.call("set_current_datetime", {"device_id": ["device1", "device3"]})
        self.coordinators[0].async_set_current_datetime.assert_awaited_once_with()
        self.coordinators[1].async_set_current_datetime.assert_not_awaited()
        self.coordinators[2].async_set_current_datetime.assert_awaited_once_with()

    async def test_explicit_clock_uses_ha_local_timezone(self):
        await self.call("set_datetime", {"device_id": "device2", "datetime": "2026-10-26 12:30:00"})
        self.coordinators[1].async_set_datetime.assert_awaited_once_with(datetime(2026, 10, 26, 12, 30, tzinfo=LOCAL_TZ))
        self.coordinators[0].async_set_datetime.assert_not_awaited()

    async def test_offset_converts_to_local_time(self):
        await self.call("set_datetime", {"device_id": "device1", "datetime": "2026-07-01T10:30:00+00:00"})
        self.coordinators[0].async_set_datetime.assert_awaited_once_with(datetime(2026, 7, 1, 12, 30, tzinfo=LOCAL_TZ))

    async def test_local_year_checked_after_timezone_conversion(self):
        with self.assertRaises(ValidationError):
            await self.call("set_datetime", {"device_id": "device1", "datetime": "2099-12-31T23:30:00+00:00"})
        self.coordinators[0].async_set_datetime.assert_not_awaited()

    async def test_invalid_target_prevents_all_writes(self):
        with self.assertRaises(ValidationError):
            await self.call("set_current_datetime", {"device_id": ["device1", "unknown"]})
        self.coordinators[0].async_set_current_datetime.assert_not_awaited()

    async def test_unloaded_runtime_has_clear_error(self):
        self.hass.data.clear()
        with self.assertRaises(ValidationError):
            await self.call("set_current_datetime", {"device_id": "device1"})

    async def test_duplicate_devices_written_once(self):
        await self.call("set_current_datetime", {"device_id": ["device1", "device1"]})
        self.coordinators[0].async_set_current_datetime.assert_awaited_once_with()

    async def test_invalid_input_never_reaches_device(self):
        for data in (
            {}, {"device_id": []}, {"device_id": "device1"},
            {"device_id": "device1", "datetime": "nonsense"},
            {"device_id": "device1", "datetime": "2026-02-30 12:00:00"},
        ):
            with self.subTest(data=data), self.assertRaises(vol.Invalid):
                await self.call("set_datetime", data)
        self.coordinators[0].async_set_datetime.assert_not_awaited()

    async def test_device_failure_propagates(self):
        self.coordinators[0].async_set_current_datetime.side_effect = protocol.FreshpointError("no acknowledgement")
        with self.assertRaisesRegex(RuntimeError, "Could not set"):
            await self.call("set_current_datetime", {"device_id": "device1"})

    async def test_actions_exist_without_loaded_entries(self):
        self.hass.data.clear()
        self.assertEqual(set(self.actions), {"set_datetime", "set_current_datetime"})
        with self.assertRaises(ValidationError):
            await self.call("set_current_datetime", {"device_id": "device1"})

    def test_editor_metadata_matches_registered_actions(self):
        descriptions = yaml.safe_load((ROOT / "custom_components/freshpoint/services.yaml").read_text())
        strings = json.loads((ROOT / "custom_components/freshpoint/strings.json").read_text())
        self.assertEqual(set(descriptions), set(self.actions))
        self.assertEqual(set(strings["services"]), set(self.actions))
        for action, description in descriptions.items():
            selector = description["fields"]["device_id"]["selector"]["device"]
            self.assertEqual(selector, {"integration": "freshpoint", "multiple": True})
            self.assertTrue(description["fields"]["device_id"]["required"])
        self.assertTrue(descriptions["set_datetime"]["fields"]["datetime"]["required"])
