#!/usr/bin/env python3
import argparse
import socket
import struct
import sys


START = b"\xfd\xfd"
TYPE = 0x02
DEFAULT_ID = b"DEFAULT_DEVICEID"


PARAMS = {
    0x0001: ("power", 1),
    0x0002: ("speed_mode", 1),
    0x0007: ("timer", 1),
    0x001F: ("outdoor_air_temp_c_x10", 2),
    0x0021: ("exhaust_air_temp_in_c_x10", 2),
    0x0025: ("room_humidity", 1),
    0x004A: ("supply_fan_rpm", 2),
    0x004B: ("extract_fan_rpm", 2),
    0x0044: ("manual_speed_percent", 1),
    0x007C: ("device_id", 16),
    0x0083: ("fault_warning_indicator", 1),
    0x0086: ("firmware", 6),
    0x0088: ("filter_status", 1),
    0x00A3: ("current_ip", 4),
    0x00B7: ("fan_rotation_direction", 1),
    0x00B9: ("device_type", 2),
    0x0129: ("recovery_efficiency", 1),
}


def checksum(payload):
    return sum(payload) & 0xFFFF


def low_param_stream(params):
    out = bytearray()
    page = 0
    for param in params:
        param_page = (param >> 8) & 0xFF
        if param_page != page:
            out.extend([0xFF, param_page])
            page = param_page
        out.append(param & 0xFF)
    return bytes(out)


def write_param_stream(writes):
    out = bytearray()
    page = 0
    for param, value in writes:
        param_page = (param >> 8) & 0xFF
        if param_page != page:
            out.extend([0xFF, param_page])
            page = param_page

        size = PARAMS.get(param, (None, 1))[1]
        raw = int(value).to_bytes(size, "little", signed=False)
        if size != 1:
            out.extend([0xFE, size])
        out.append(param & 0xFF)
        out.extend(raw)
    return bytes(out)


def packet(controller_id, password, func, data):
    controller_id = controller_id.encode("ascii")
    password = password.encode("ascii")
    body = bytearray()
    body.append(TYPE)
    body.append(len(controller_id))
    body.extend(controller_id)
    body.append(len(password))
    body.extend(password)
    body.append(func)
    body.extend(data)
    return START + bytes(body) + struct.pack("<H", checksum(body))


def parse_values(data):
    if len(data) < 8 or data[:2] != START:
        raise ValueError("not a Freshpoint packet")
    got = struct.unpack("<H", data[-2:])[0]
    want = checksum(data[2:-2])
    if got != want:
        raise ValueError(f"bad checksum: got 0x{got:04x}, expected 0x{want:04x}")

    pos = 2
    proto = data[pos]
    pos += 1
    if proto != TYPE:
        raise ValueError(f"unexpected protocol type 0x{proto:02x}")

    id_len = data[pos]
    pos += 1
    controller_id = data[pos : pos + id_len].decode("ascii", "replace")
    pos += id_len
    pwd_len = data[pos]
    pos += 1 + pwd_len
    func = data[pos]
    pos += 1
    if func != 0x06:
        raise ValueError(f"unexpected response function 0x{func:02x}")

    values = {}
    page = 0
    while pos < len(data) - 2:
        b = data[pos]
        pos += 1
        size = 1
        if b == 0xFF:
            page = data[pos]
            pos += 1
            continue
        if b == 0xFD:
            unsupported = (page << 8) | data[pos]
            pos += 1
            values[unsupported] = None
            continue
        if b == 0xFE:
            size = data[pos]
            pos += 1
            b = data[pos]
            pos += 1
        param = (page << 8) | b
        raw = data[pos : pos + size]
        pos += size
        values[param] = raw

    return controller_id, values


def format_value(param, raw):
    if raw is None:
        return "unsupported"
    name, _ = PARAMS.get(param, (f"param_0x{param:04x}", len(raw)))
    if name in {"device_id"}:
        return raw.decode("ascii", "replace")
    if name == "current_ip":
        return ".".join(str(x) for x in raw)
    if name.endswith("_c_x10"):
        value = int.from_bytes(raw, "little", signed=True)
        return f"{value / 10:.1f}"
    if len(raw) <= 4:
        return str(int.from_bytes(raw, "little"))
    return raw.hex()


def request(host, params, controller_id, password, timeout, broadcast):
    msg = packet(controller_id, password, 0x01, low_param_stream(params))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(msg, (host, 4000))
    responses = []
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            break
        responses.append((addr, data))
        if not broadcast:
            break
    return responses


def write(host, writes, controller_id, password, timeout):
    msg = packet(controller_id, password, 0x03, write_param_stream(writes))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.sendto(msg, (host, 4000))
    try:
        data, addr = sock.recvfrom(4096)
    except socket.timeout:
        return []
    return [(addr, data)]


def parse_percent(value):
    value = value.strip()
    if value.endswith("%"):
        value = value[:-1]
    percent = int(value)
    if not 10 <= percent <= 100:
        raise argparse.ArgumentTypeError("speed percent must be between 10 and 100")
    return percent


def print_responses(responses):
    if not responses:
        print("No response.")
        return 1

    for addr, data in responses:
        print(f"Response from {addr[0]}:{addr[1]} ({len(data)} bytes)")
        try:
            controller_id, values = parse_values(data)
        except ValueError as exc:
            print(f"  Could not parse: {exc}")
            print(f"  Raw: {data.hex(' ')}")
            continue
        print(f"  controller_id: {controller_id}")
        for param, raw in values.items():
            name = PARAMS.get(param, (f"param_0x{param:04x}", None))[0]
            print(f"  {name} (0x{param:04x}): {format_value(param, raw)}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Control/probe Blauberg Freshpoint UDP smart-house protocol.")
    parser.add_argument("host", help="Freshpoint IP or broadcast address, e.g. 192.168.1.255")
    parser.add_argument("--id", default="DEFAULT_DEVICEID", help="16-char controller ID or DEFAULT_DEVICEID")
    parser.add_argument("--password", default="1111", help="device password, default: 1111")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--broadcast", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    read_parser = subparsers.add_parser("read", help="read one or more parameters")
    read_parser.add_argument(
        "--params",
        default="0x007c,0x00b9",
        help="comma-separated parameter numbers, default discovers ID and device type",
    )

    speed_parser = subparsers.add_parser("speed", help="set manual fan speed percent, e.g. speed 50%%")
    speed_parser.add_argument("percent", type=parse_percent)

    speed_mode_parser = subparsers.add_parser("speed-mode", help="set built-in speed mode 1..5")
    speed_mode_parser.add_argument("mode", type=int, choices=range(1, 6))

    subparsers.add_parser("on", help="turn unit on")
    subparsers.add_parser("off", help="turn unit off")

    args = parser.parse_args()
    if args.command is None:
        args.command = "read"

    try:
        if args.command == "read":
            params = [int(x.strip(), 0) for x in args.params.split(",") if x.strip()]
            responses = request(args.host, params, args.id, args.password, args.timeout, args.broadcast)
        elif args.command == "speed":
            responses = write(
                args.host,
                [(0x0002, 255), (0x0044, args.percent)],
                args.id,
                args.password,
                args.timeout,
            )
        elif args.command == "speed-mode":
            responses = write(args.host, [(0x0002, args.mode)], args.id, args.password, args.timeout)
        elif args.command == "on":
            responses = write(args.host, [(0x0001, 1)], args.id, args.password, args.timeout)
        elif args.command == "off":
            responses = write(args.host, [(0x0001, 0)], args.id, args.password, args.timeout)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except OSError as exc:
        print(f"send failed: {exc}", file=sys.stderr)
        return 2

    return print_responses(responses)


if __name__ == "__main__":
    raise SystemExit(main())
