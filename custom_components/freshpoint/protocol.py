"""UDP protocol client for Blauberg Freshpoint units."""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from typing import Iterable

from .const import (
    DEFAULT_DEVICE_ID,
    DEFAULT_PORT,
    PARAM_CO2,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_TYPE,
    PARAM_DIRECTION,
    PARAM_EXTRACT_INLET_TEMPERATURE,
    PARAM_EXTRACT_OUTLET_TEMPERATURE,
    PARAM_EXTRACT_RPM,
    PARAM_FAULT_WARNING,
    PARAM_FILTER_COUNTDOWN,
    PARAM_FILTER_RESET,
    PARAM_FILTER_STATUS,
    PARAM_FROST_PROTECTION,
    PARAM_HEATER_CONTROL,
    PARAM_HEATER_STATUS,
    PARAM_HUMIDITY,
    PARAM_MANUAL_SPEED,
    PARAM_MOTOR_RUNTIME,
    PARAM_OUTDOOR_TEMPERATURE,
    PARAM_POWER,
    PARAM_RECOVERY_EFFICIENCY,
    PARAM_SPEED_MODE,
    PARAM_SUPPLY_TEMPERATURE,
    PARAM_SUPPLY_RPM,
    PARAM_TIMER_MODE,
    PARAM_VOC,
)

START = b"\xfd\xfd"
PROTOCOL_TYPE = 0x02
FUNC_READ = 0x01
FUNC_WRITE_WITH_RESPONSE = 0x03
FUNC_RESPONSE = 0x06

PARAM_SIZES = {
    PARAM_POWER: 1,
    PARAM_SPEED_MODE: 1,
    PARAM_TIMER_MODE: 1,
    PARAM_MANUAL_SPEED: 1,
    PARAM_OUTDOOR_TEMPERATURE: 2,
    PARAM_SUPPLY_TEMPERATURE: 2,
    PARAM_EXTRACT_INLET_TEMPERATURE: 2,
    PARAM_EXTRACT_OUTLET_TEMPERATURE: 2,
    PARAM_HUMIDITY: 1,
    PARAM_CO2: 2,
    PARAM_SUPPLY_RPM: 2,
    PARAM_EXTRACT_RPM: 2,
    PARAM_FILTER_COUNTDOWN: 4,
    PARAM_FILTER_RESET: 1,
    PARAM_HEATER_CONTROL: 1,
    PARAM_MOTOR_RUNTIME: 4,
    PARAM_HEATER_STATUS: 1,
    PARAM_FAULT_WARNING: 1,
    PARAM_FILTER_STATUS: 1,
    PARAM_DIRECTION: 1,
    PARAM_RECOVERY_EFFICIENCY: 1,
    PARAM_DEVICE_ID: 16,
    PARAM_DEVICE_TYPE: 2,
    PARAM_FROST_PROTECTION: 1,
    PARAM_VOC: 2,
}

DEVICE_TYPE_NAMES = {
    17: "Freshpoint 160",
    20: "Freshpoint Eco 160",
    22: "Freshpoint 200",
    24: "Freshpoint Eco 200",
}


@dataclass(frozen=True)
class FreshpointDiscoveryResult:
    """Freshpoint device found on the local network."""

    host: str
    controller_id: str
    device_type: int | None

    @property
    def name(self) -> str:
        """Return a user-friendly discovered device name."""
        model = DEVICE_TYPE_NAMES.get(self.device_type, "Freshpoint")
        return f"{model} {self.host}"


class FreshpointError(Exception):
    """Base exception for Freshpoint protocol errors."""


class FreshpointTimeoutError(FreshpointError):
    """Raised when a Freshpoint device does not respond."""


@dataclass(frozen=True)
class FreshpointState:
    """Current state read from a Freshpoint unit."""

    power: int | None = None
    speed_mode: int | None = None
    timer_mode: int | None = None
    percentage: int | None = None
    outdoor_temperature: float | None = None
    supply_temperature: float | None = None
    extract_inlet_temperature: float | None = None
    extract_outlet_temperature: float | None = None
    humidity: int | None = None
    co2: int | None = None
    supply_rpm: int | None = None
    extract_rpm: int | None = None
    filter_countdown_hours: float | None = None
    heater_control: int | None = None
    motor_runtime_hours: float | None = None
    heater_status: int | None = None
    fault_warning: int | None = None
    filter_status: int | None = None
    direction: int | None = None
    recovery_efficiency: int | None = None
    frost_protection: int | None = None
    voc: int | None = None
    device_type: int | None = None


def _checksum(payload: bytes | bytearray) -> int:
    return sum(payload) & 0xFFFF


def _decode_temperature(value: int | bytes | None) -> float | None:
    """Decode a signed, tenths-of-a-degree Freshpoint temperature."""
    if not isinstance(value, int):
        return None
    signed_value = value - 0x10000 if value >= 0x8000 else value
    if signed_value in (-32768, 32767):
        return None
    return signed_value / 10


def _decode_packed_duration_hours(value: int | bytes | None) -> float | None:
    """Decode minutes, hours and uint16 days packed into four bytes."""
    if not isinstance(value, int):
        return None
    minutes = value & 0xFF
    hours = (value >> 8) & 0xFF
    days = (value >> 16) & 0xFFFF
    if minutes > 59 or hours > 23:
        return None
    return days * 24 + hours + minutes / 60


def _read_param_stream(params: Iterable[int]) -> bytes:
    out = bytearray()
    page = 0
    for param in params:
        param_page = (param >> 8) & 0xFF
        if param_page != page:
            out.extend([0xFF, param_page])
            page = param_page
        out.append(param & 0xFF)
    return bytes(out)


def _write_param_stream(writes: Iterable[tuple[int, int]]) -> bytes:
    out = bytearray()
    page = 0
    for param, value in writes:
        param_page = (param >> 8) & 0xFF
        if param_page != page:
            out.extend([0xFF, param_page])
            page = param_page

        size = PARAM_SIZES.get(param, 1)
        raw = int(value).to_bytes(size, "little", signed=False)
        if size != 1:
            out.extend([0xFE, size])
        out.append(param & 0xFF)
        out.extend(raw)
    return bytes(out)


def _packet(controller_id: str, password: str, function: int, data: bytes) -> bytes:
    controller_id_bytes = controller_id.encode("ascii")
    password_bytes = password.encode("ascii")
    body = bytearray([PROTOCOL_TYPE, len(controller_id_bytes)])
    body.extend(controller_id_bytes)
    body.append(len(password_bytes))
    body.extend(password_bytes)
    body.append(function)
    body.extend(data)
    return START + bytes(body) + struct.pack("<H", _checksum(body))


def _parse_response(data: bytes) -> dict[int, int | bytes | None]:
    if len(data) < 8 or data[:2] != START:
        raise FreshpointError("response is not a Freshpoint packet")

    received_checksum = struct.unpack("<H", data[-2:])[0]
    expected_checksum = _checksum(data[2:-2])
    if received_checksum != expected_checksum:
        raise FreshpointError("response checksum mismatch")

    pos = 2
    protocol_type = data[pos]
    pos += 1
    if protocol_type != PROTOCOL_TYPE:
        raise FreshpointError(f"unexpected protocol type {protocol_type}")

    id_len = data[pos]
    pos += 1 + id_len

    password_len = data[pos]
    pos += 1 + password_len

    function = data[pos]
    pos += 1
    if function != FUNC_RESPONSE:
        raise FreshpointError(f"unexpected response function {function}")

    values: dict[int, int | bytes | None] = {}
    page = 0
    while pos < len(data) - 2:
        byte = data[pos]
        pos += 1
        size = 1
        if byte == 0xFF:
            page = data[pos]
            pos += 1
            continue
        if byte == 0xFD:
            unsupported_param = (page << 8) | data[pos]
            pos += 1
            values[unsupported_param] = None
            continue
        if byte == 0xFE:
            size = data[pos]
            pos += 1
            byte = data[pos]
            pos += 1

        param = (page << 8) | byte
        raw = data[pos : pos + size]
        pos += size
        if param == PARAM_DEVICE_ID:
            values[param] = raw
        else:
            values[param] = int.from_bytes(raw, "little")

    return values


def discover_freshpoints(
    *,
    broadcast_address: str,
    password: str,
    source_address: str | None = None,
    port: int = DEFAULT_PORT,
    timeout: float = 3.0,
) -> list[FreshpointDiscoveryResult]:
    """Discover Freshpoint devices with the documented DEFAULT_DEVICEID query."""
    request = _packet(
        "DEFAULT_DEVICEID",
        password,
        FUNC_READ,
        _read_param_stream([PARAM_DEVICE_ID, PARAM_DEVICE_TYPE]),
    )
    results: dict[str, FreshpointDiscoveryResult] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        if source_address:
            sock.bind((source_address, 0))
        sock.sendto(request, (broadcast_address, port))

        while True:
            try:
                response, address = sock.recvfrom(4096)
            except TimeoutError:
                break

            try:
                values = _parse_response(response)
            except FreshpointError:
                continue

            raw_device_id = values.get(PARAM_DEVICE_ID)
            if not isinstance(raw_device_id, bytes):
                continue
            controller_id = raw_device_id.decode("ascii", "replace")
            device_type = values.get(PARAM_DEVICE_TYPE)
            results[controller_id] = FreshpointDiscoveryResult(
                host=address[0],
                controller_id=controller_id,
                device_type=device_type if isinstance(device_type, int) else None,
            )

    return sorted(results.values(), key=lambda result: result.host)


def identify_freshpoint(
    *,
    host: str,
    password: str,
    port: int = DEFAULT_PORT,
    timeout: float = 2.0,
) -> FreshpointDiscoveryResult:
    """Identify a Freshpoint device by host when broadcast discovery is unavailable."""
    client = FreshpointClient(host, DEFAULT_DEVICE_ID, password, port=port, timeout=timeout)
    values = client.read([PARAM_DEVICE_ID, PARAM_DEVICE_TYPE])
    raw_device_id = values.get(PARAM_DEVICE_ID)
    if not isinstance(raw_device_id, bytes):
        raise FreshpointError("response did not include a controller ID")

    device_type = values.get(PARAM_DEVICE_TYPE)
    return FreshpointDiscoveryResult(
        host=host,
        controller_id=raw_device_id.decode("ascii", "replace"),
        device_type=device_type if isinstance(device_type, int) else None,
    )


class FreshpointClient:
    """Blocking UDP client for a Freshpoint unit."""

    def __init__(
        self,
        host: str,
        controller_id: str,
        password: str,
        *,
        port: int = DEFAULT_PORT,
        timeout: float = 2.0,
    ) -> None:
        self.host = host
        self.controller_id = controller_id
        self.password = password
        self.port = port
        self.timeout = timeout

    def _send(self, function: int, data: bytes) -> dict[int, int | bytes | None]:
        request = _packet(self.controller_id, self.password, function, data)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(request, (self.host, self.port))
            try:
                response, _ = sock.recvfrom(4096)
            except TimeoutError as exc:
                raise FreshpointTimeoutError("Freshpoint did not respond") from exc
        return _parse_response(response)

    def read(self, params: Iterable[int]) -> dict[int, int | bytes | None]:
        """Read raw parameter values."""
        return self._send(FUNC_READ, _read_param_stream(params))

    def read_state(self, params: Iterable[int]) -> FreshpointState:
        """Read and map the current device state."""
        values = self.read(params)
        return FreshpointState(
            power=values.get(PARAM_POWER),
            speed_mode=values.get(PARAM_SPEED_MODE),
            timer_mode=values.get(PARAM_TIMER_MODE),
            percentage=values.get(PARAM_MANUAL_SPEED),
            outdoor_temperature=_decode_temperature(
                values.get(PARAM_OUTDOOR_TEMPERATURE)
            ),
            supply_temperature=_decode_temperature(
                values.get(PARAM_SUPPLY_TEMPERATURE)
            ),
            extract_inlet_temperature=_decode_temperature(
                values.get(PARAM_EXTRACT_INLET_TEMPERATURE)
            ),
            extract_outlet_temperature=_decode_temperature(
                values.get(PARAM_EXTRACT_OUTLET_TEMPERATURE)
            ),
            humidity=values.get(PARAM_HUMIDITY),
            co2=values.get(PARAM_CO2),
            supply_rpm=values.get(PARAM_SUPPLY_RPM),
            extract_rpm=values.get(PARAM_EXTRACT_RPM),
            filter_countdown_hours=_decode_packed_duration_hours(
                values.get(PARAM_FILTER_COUNTDOWN)
            ),
            heater_control=values.get(PARAM_HEATER_CONTROL),
            motor_runtime_hours=_decode_packed_duration_hours(
                values.get(PARAM_MOTOR_RUNTIME)
            ),
            heater_status=values.get(PARAM_HEATER_STATUS),
            fault_warning=values.get(PARAM_FAULT_WARNING),
            filter_status=values.get(PARAM_FILTER_STATUS),
            direction=values.get(PARAM_DIRECTION),
            recovery_efficiency=values.get(PARAM_RECOVERY_EFFICIENCY),
            frost_protection=values.get(PARAM_FROST_PROTECTION),
            voc=values.get(PARAM_VOC),
            device_type=values.get(PARAM_DEVICE_TYPE),
        )

    def write(self, writes: Iterable[tuple[int, int]]) -> dict[int, int | None]:
        """Write raw parameter values."""
        return self._send(FUNC_WRITE_WITH_RESPONSE, _write_param_stream(writes))

    def set_power(self, enabled: bool) -> None:
        """Turn the unit on or off."""
        self.write([(PARAM_POWER, 1 if enabled else 0)])

    def set_percentage(self, percentage: int) -> None:
        """Set manual speed percentage."""
        bounded_percentage = max(10, min(100, percentage))
        self.write([(PARAM_SPEED_MODE, 255), (PARAM_MANUAL_SPEED, bounded_percentage)])

    def set_direction(self, direction: int) -> None:
        """Set ventilation direction/mode."""
        if direction not in range(4):
            raise ValueError(f"unsupported Freshpoint direction {direction}")
        self.write([(PARAM_DIRECTION, direction)])

    def set_timer_mode(self, timer_mode: int) -> None:
        """Set normal, night or turbo timer mode."""
        if timer_mode not in range(3):
            raise ValueError(f"unsupported Freshpoint timer mode {timer_mode}")
        self.write([(PARAM_TIMER_MODE, timer_mode)])

    def set_heater(self, enabled: bool) -> None:
        """Enable or disable heater control."""
        self.write([(PARAM_HEATER_CONTROL, 1 if enabled else 0)])

    def reset_filter(self) -> None:
        """Reset the filter replacement countdown."""
        self.write([(PARAM_FILTER_RESET, 1)])
