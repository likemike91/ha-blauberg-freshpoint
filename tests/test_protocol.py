"""Unit tests for the Freshpoint UDP protocol mapping."""

from __future__ import annotations

from datetime import datetime
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

    for module_name in ("const", "settings", "protocol", "polling"):
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


class ClockTests(unittest.TestCase):
    """Check the documented RTC wire format and acknowledgement handling."""

    def test_clock_and_calendar_wire_bytes(self) -> None:
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        streams = []

        def send(function, data):
            self.assertEqual(function, protocol.FUNC_WRITE_WITH_RESPONSE)
            streams.append(data)
            return protocol._parse_response(
                protocol._packet("0" * 16, "1111", protocol.FUNC_RESPONSE, data)
            )

        client._send = send
        client.set_datetime(datetime(2026, 10, 25, 23, 59, 58))
        self.assertEqual(streams, [bytes.fromhex("fe036f3a3b17fe047019070a1a")])

    def test_leap_day(self) -> None:
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        writes = []

        def write(values):
            writes.extend(values)
            return dict(values)

        client.write = write
        client.set_datetime(datetime(2028, 2, 29))
        self.assertEqual(writes[1][1].to_bytes(4, "little"), bytes((29, 2, 2, 28)))

    def test_rejects_unsupported_year_before_write(self) -> None:
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        for year in (1999, 2100):
            with self.assertRaises(ValueError):
                client.set_datetime(datetime(year, 1, 1))

    def test_reports_unsupported_clock(self) -> None:
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        client.write = lambda values: {const.PARAM_RTC_TIME: None}
        with self.assertRaises(protocol.FreshpointError):
            client.set_datetime(datetime(2026, 10, 26))


class PollingTests(unittest.TestCase):
    """Verify registry-driven dependencies without Home Assistant imports."""

    def setUp(self):
        self.polling = sys.modules["custom_components.freshpoint.polling"]
        self.entries = {}
        for platform, suffix, _, _ in self.polling.ENTITY_READS:
            self.entries[(platform, f"device_{suffix}")] = types.SimpleNamespace(disabled_by="user")

    def params(self):
        return self.polling.enabled_read_params("device", lambda platform, uid: self.entries.get((platform, uid)))

    def enable(self, platform, suffix):
        self.entries[(platform, f"device_{suffix}")].disabled_by = None

    def test_all_disabled_produces_no_reads(self):
        self.assertEqual(self.params(), [])

    def test_clock_only_reads_both_rtc_fields(self):
        self.enable("datetime", "device_clock")
        self.assertEqual(self.params(), [111, 112])

    def test_shared_parameter_survives_one_entity_disabled(self):
        self.enable("sensor", "filter_status")
        self.enable("binary_sensor", "filter")
        self.assertEqual(self.params(), [const.PARAM_FILTER_STATUS])
        self.entries[("sensor", "device_filter_status")].disabled_by = "user"
        self.assertEqual(self.params(), [const.PARAM_FILTER_STATUS])
        self.entries[("binary_sensor", "device_filter")].disabled_by = "user"
        self.assertEqual(self.params(), [])

    def test_enable_then_disable_takes_effect_next_poll(self):
        self.enable("sensor", "supply_rpm")
        self.assertEqual(self.params(), [const.PARAM_SUPPLY_RPM])
        self.entries[("sensor", "device_supply_rpm")].disabled_by = "integration"
        self.assertEqual(self.params(), [])

    def test_startup_uses_defaults_for_new_entities(self):
        self.entries.clear()
        self.assertNotIn(const.PARAM_MOTOR_RUNTIME, self.params())
        self.assertNotIn(const.PARAM_SUPPLY_RPM, self.params())
        self.assertIn(const.PARAM_HUMIDITY, self.params())
        self.assertNotIn(const.PARAM_RTC_CALENDAR, self.params())
        self.assertNotIn(const.PARAM_RTC_TIME, self.params())

    def test_device_preferences_are_independent(self):
        self.enable("sensor", "humidity")
        self.assertEqual(self.params(), [const.PARAM_HUMIDITY])
        other = self.polling.enabled_read_params("other", lambda platform, uid: self.entries.get((platform, uid)))
        self.assertIn(const.PARAM_CO2, other)


class ClockDecodeTests(unittest.TestCase):
    def test_decode_observed_device_values(self):
        value = protocol.decode_rtc_datetime(
            int.from_bytes(bytes.fromhex("10 36 07"), "little"),
            int.from_bytes(bytes.fromhex("1a 01 0a 1a"), "little"),
        )
        self.assertEqual(value, datetime(2026, 10, 26, 7, 54, 16))

    def test_reject_invalid_or_missing_fields(self):
        calendar = int.from_bytes(bytes((26, 1, 10, 26)), "little")
        for clock in (None, -1, 1 << 24, 60, 24 << 16):
            self.assertIsNone(protocol.decode_rtc_datetime(clock, calendar))
        self.assertIsNone(protocol.decode_rtc_datetime(0, 0))
        self.assertIsNone(protocol.decode_rtc_datetime(0, None))


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.settings = sys.modules["custom_components.freshpoint.settings"]
        self.client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")

    def test_setting_wire_examples(self):
        streams = []
        def send(function, data):
            self.assertEqual(function, protocol.FUNC_WRITE_WITH_RESPONSE)
            streams.append(data)
            return protocol._parse_response(protocol._packet("0" * 16, "1111", protocol.FUNC_RESPONSE, data))
        self.client._send = send
        self.client.set_setting("co2_threshold", 800)
        self.client.set_setting("night_duration", 480)
        self.client.set_setting("display_off_start", 23 * 60)
        self.client.set_setting("display_mode", 2)
        self.client.set_setting("sound", 0)
        self.client.set_setting("speed_mode", 5)
        self.assertEqual(streams, [
            bytes.fromhex("fe021a2003"), bytes.fromhex("ff03fe02020008"),
            bytes.fromhex("ff04fe02080017"), bytes.fromhex("ff040702"),
            bytes.fromhex("ff040100"), bytes.fromhex("0205"),
        ])

    def test_invalid_values_do_not_write(self):
        def unexpected(_writes):
            self.fail("Invalid values must not send a write")
        self.client.write = unexpected
        for key, value in (
            ("co2_threshold", 399), ("co2_threshold", 2001),
            ("humidity_threshold", 81), ("voc_threshold", 49),
            ("filter_interval", 1), ("filter_interval", 69),
            ("night_duration", 1440), ("display_brightness", 0),
            ("speed_mode", 6), ("speed_mode", 0), ("sound", 2),
            ("display_mode", 3), ("humidity_threshold", 50.5),
            ("voc_threshold", float("nan")),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.client.set_setting(key, value)

    def test_filter_interval_special_zero(self):
        self.client.write = lambda values: dict(values)
        for value in (0, 70, 365):
            self.client.set_setting("filter_interval", value)

    def test_device_rejection_is_not_reported_as_success(self):
        for response in ({}, {25: None}, {25: 60}):
            self.client.write = lambda values, response=response: response
            with self.assertRaises(protocol.FreshpointError):
                self.client.set_setting("humidity_threshold", 70)

    def test_invalid_read_values_remain_unknown(self):
        definitions = self.settings.SETTINGS_BY_KEY
        self.assertIsNone(definitions["night_duration"].decode(60))
        self.assertIsNone(definitions["night_duration"].decode(24 << 8))
        self.assertIsNone(definitions["sound"].decode(2))
        self.assertIsNone(definitions["speed_mode"].decode(6))
        self.assertEqual(definitions["night_duration"].decode(8 << 8), 480)


class DiagnosticTests(unittest.TestCase):
    def test_alarm_bytes_preserved_and_decoded(self):
        for raw in (b"", bytes((7, 1, 9, 2))):
            packet = protocol._packet("0" * 16, "1111", protocol.FUNC_RESPONSE, bytes((254, len(raw), 127)) + raw)
            self.assertEqual(protocol._parse_response(packet)[127], raw)
        self.assertEqual(protocol.decode_alarms(b""), [])
        self.assertEqual(protocol.decode_alarms(bytes((7, 1, 9, 2))), [
            {"code": 7, "type": "alarm"}, {"code": 9, "type": "warning"},
        ])
        self.assertIsNone(protocol.decode_alarms(b"x"))
        self.assertIsNone(protocol.decode_alarms(None))

    def test_firmware_and_air_quality(self):
        self.assertEqual(protocol.decode_firmware(bytes.fromhex("00 0c 01 09 e9 07")), ("0.12", "2025-09-01"))
        self.assertIsNone(protocol.decode_firmware(b""))
        self.assertIsNone(protocol.decode_firmware(bytes((0, 12, 31, 2, 233, 7))))
        raw = bytes((1, 0, 0, 0, 1))
        self.assertTrue(protocol.decode_air_quality_flag(raw, 0))
        self.assertFalse(protocol.decode_air_quality_flag(raw, 1))
        self.assertTrue(protocol.decode_air_quality_flag(raw, 4))
        self.assertIsNone(protocol.decode_air_quality_flag(b"", 0))

    def test_timer_decode(self):
        self.assertEqual(protocol.decode_timer_seconds(int.from_bytes(bytes((30, 5, 2)), "little")), 7530)
        self.assertIsNone(protocol.decode_timer_seconds(60))

    def test_truncated_response_rejected(self):
        for stream in (b"\xff", b"\xfe\x02", b"\xfe\x06\x86\x01", b"\xfd"):
            with self.assertRaises(protocol.FreshpointError):
                protocol._parse_response(protocol._packet("0" * 16, "1111", protocol.FUNC_RESPONSE, stream))

    def test_all_enabled_fields_split_into_bounded_reads(self):
        polling = sys.modules["custom_components.freshpoint.polling"]
        params = sorted({param for _, _, dependencies, _ in polling.ENTITY_READS for param in dependencies})
        batches = []
        client = protocol.FreshpointClient("192.0.2.1", "0" * 16, "1111")
        def send(function, data):
            self.assertEqual(function, protocol.FUNC_READ)
            page = 0
            pos = 0
            batch = []
            while pos < len(data):
                low = data[pos]
                pos += 1
                if low == 255:
                    page = data[pos]
                    pos += 1
                else:
                    batch.append(page << 8 | low)
            batches.append(batch)
            if 127 in batch:
                self.assertEqual(batch, [127])
                return {127: b""}
            response = protocol._write_param_stream((param, 0) for param in batch)
            packet = protocol._packet("0" * 16, "1111", protocol.FUNC_RESPONSE, response)
            self.assertLessEqual(len(packet), 256)
            return protocol._parse_response(packet)
        client._send = send
        state = client.read_state(params)
        self.assertEqual(set(state.values), set(params))
        self.assertEqual([param for batch in batches for param in batch], params)
        self.assertGreater(len(batches), 1)


if __name__ == "__main__":
    unittest.main()
