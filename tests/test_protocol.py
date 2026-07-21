"""Unit tests for the Freshpoint UDP protocol mapping."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


def _load_protocol_modules():
    """Load protocol code without importing Home Assistant integration setup."""
    root = Path(__file__).parents[1] / "custom_components" / "freshpoint"
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = []
    freshpoint = types.ModuleType("custom_components.freshpoint")
    freshpoint.__path__ = [str(root)]
    sys.modules.setdefault("custom_components", custom_components)
    sys.modules.setdefault("custom_components.freshpoint", freshpoint)

    for module_name in ("const", "protocol"):
        qualified_name = f"custom_components.freshpoint.{module_name}"
        spec = importlib.util.spec_from_file_location(
            qualified_name, root / f"{module_name}.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified_name] = module
        spec.loader.exec_module(module)

    return (
        sys.modules["custom_components.freshpoint.const"],
        sys.modules["custom_components.freshpoint.protocol"],
    )


const, protocol = _load_protocol_modules()


class TemperatureTests(unittest.TestCase):
    """Test signed temperature decoding and state mapping."""

    def test_decode_temperature(self) -> None:
        self.assertEqual(protocol._decode_temperature(235), 23.5)
        self.assertEqual(protocol._decode_temperature(0xFF9C), -10.0)
        self.assertIsNone(protocol._decode_temperature(0x8000))
        self.assertIsNone(protocol._decode_temperature(0x7FFF))
        self.assertIsNone(protocol._decode_temperature(None))

    def test_read_state_maps_all_temperature_sensors(self) -> None:
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        client.read = lambda _params: {
            const.PARAM_OUTDOOR_TEMPERATURE: 0xFFFB,
            const.PARAM_SUPPLY_TEMPERATURE: 201,
            const.PARAM_EXTRACT_INLET_TEMPERATURE: 223,
            const.PARAM_EXTRACT_OUTLET_TEMPERATURE: 175,
        }

        state = client.read_state(const.READ_PARAMS)

        self.assertEqual(state.outdoor_temperature, -0.5)
        self.assertEqual(state.supply_temperature, 20.1)
        self.assertEqual(state.extract_inlet_temperature, 22.3)
        self.assertEqual(state.extract_outlet_temperature, 17.5)


class DurationTests(unittest.TestCase):
    """Test packed Freshpoint duration values."""

    def test_decode_duration(self) -> None:
        packed = 30 | (6 << 8) | (12 << 16)
        self.assertEqual(protocol._decode_packed_duration_hours(packed), 294.5)
        self.assertIsNone(protocol._decode_packed_duration_hours(60))
        self.assertIsNone(protocol._decode_packed_duration_hours(None))


class DirectionTests(unittest.TestCase):
    """Test airflow direction writes."""

    def test_set_direction_writes_protocol_parameter(self) -> None:
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        writes = []
        client.write = lambda values: writes.extend(values)

        client.set_direction(3)

        self.assertEqual(writes, [(const.PARAM_DIRECTION, 3)])

    def test_set_direction_rejects_unknown_value(self) -> None:
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        with self.assertRaises(ValueError):
            client.set_direction(4)


class AdditionalControlTests(unittest.TestCase):
    """Test timer, heater, and filter protocol writes."""

    def setUp(self) -> None:
        self.client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        self.writes = []
        self.client.write = lambda values: self.writes.extend(values)

    def test_set_timer_mode(self) -> None:
        self.client.set_timer_mode(2)
        self.assertEqual(self.writes, [(const.PARAM_TIMER_MODE, 2)])

    def test_set_heater(self) -> None:
        self.client.set_heater(True)
        self.assertEqual(self.writes, [(const.PARAM_HEATER_CONTROL, 1)])

    def test_reset_filter(self) -> None:
        self.client.reset_filter()
        self.assertEqual(self.writes, [(const.PARAM_FILTER_RESET, 1)])


if __name__ == "__main__":
    unittest.main()
