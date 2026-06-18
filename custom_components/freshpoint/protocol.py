"""UDP protocol client for Blauberg Freshpoint units."""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from typing import Iterable

from .const import (
    DEFAULT_PORT,
    PARAM_DEVICE_ID,
    PARAM_DEVICE_TYPE,
    PARAM_DIRECTION,
    PARAM_EXTRACT_RPM,
    PARAM_FILTER_STATUS,
    PARAM_HUMIDITY,
    PARAM_MANUAL_SPEED,
    PARAM_POWER,
    PARAM_RECOVERY_EFFICIENCY,
    PARAM_SPEED_MODE,
    PARAM_SUPPLY_RPM,
)

START = b"\xfd\xfd"
PROTOCOL_TYPE = 0x02
FUNC_READ = 0x01
FUNC_WRITE_WITH_RESPONSE = 0x03
FUNC_RESPONSE = 0x06

PARAM_SIZES = {
    PARAM_POWER: 1,
    PARAM_SPEED_MODE: 1,
    PARAM_MANUAL_SPEED: 1,
    PARAM_HUMIDITY: 1,
    PARAM_SUPPLY_RPM: 2,
    PARAM_EXTRACT_RPM: 2,
    PARAM_FILTER_STATUS: 1,
    PARAM_DIRECTION: 1,
    PARAM_RECOVERY_EFFICIENCY: 1,
    PARAM_DEVICE_ID: 16,
    PARAM_DEVICE_TYPE: 2,
}


@dataclass(frozen=True)
class FreshpointDiscoveryResult:
    """Freshpoint device found on the local network."""

    host: str
    controller_id: str
    device_type: int | None


class FreshpointError(Exception):
    """Base exception for Freshpoint protocol errors."""


class FreshpointTimeoutError(FreshpointError):
    """Raised when a Freshpoint device does not respond."""


@dataclass(frozen=True)
class FreshpointState:
    """Current state read from a Freshpoint unit."""

    power: int | None = None
    speed_mode: int | None = None
    percentage: int | None = None
    humidity: int | None = None
    supply_rpm: int | None = None
    extract_rpm: int | None = None
    filter_status: int | None = None
    direction: int | None = None
    recovery_efficiency: int | None = None
    device_type: int | None = None


def _checksum(payload: bytes | bytearray) -> int:
    return sum(payload) & 0xFFFF


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

    def _send(self, function: int, data: bytes) -> dict[int, int | None]:
        request = _packet(self.controller_id, self.password, function, data)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(request, (self.host, self.port))
            try:
                response, _ = sock.recvfrom(4096)
            except TimeoutError as exc:
                raise FreshpointTimeoutError("Freshpoint did not respond") from exc
        return _parse_response(response)

    def read(self, params: Iterable[int]) -> dict[int, int | None]:
        """Read raw parameter values."""
        return self._send(FUNC_READ, _read_param_stream(params))

    def read_state(self, params: Iterable[int]) -> FreshpointState:
        """Read and map the current device state."""
        values = self.read(params)
        return FreshpointState(
            power=values.get(PARAM_POWER),
            speed_mode=values.get(PARAM_SPEED_MODE),
            percentage=values.get(PARAM_MANUAL_SPEED),
            humidity=values.get(PARAM_HUMIDITY),
            supply_rpm=values.get(PARAM_SUPPLY_RPM),
            extract_rpm=values.get(PARAM_EXTRACT_RPM),
            filter_status=values.get(PARAM_FILTER_STATUS),
            direction=values.get(PARAM_DIRECTION),
            recovery_efficiency=values.get(PARAM_RECOVERY_EFFICIENCY),
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
