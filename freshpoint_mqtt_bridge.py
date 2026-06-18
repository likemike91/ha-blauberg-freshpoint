#!/usr/bin/env python3
import argparse
import json
import re
import socket
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import paho.mqtt.client as mqtt


START = b"\xfd\xfd"
TYPE = 0x02
PORT = 4000

PARAM_POWER = 0x0001
PARAM_SPEED_MODE = 0x0002
PARAM_MANUAL_SPEED = 0x0044
PARAM_HUMIDITY = 0x0025
PARAM_SUPPLY_RPM = 0x004A
PARAM_EXTRACT_RPM = 0x004B
PARAM_FILTER_STATUS = 0x0088
PARAM_DIRECTION = 0x00B7
PARAM_RECOVERY_EFFICIENCY = 0x0129

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
}

READ_PARAMS = [
    PARAM_POWER,
    PARAM_SPEED_MODE,
    PARAM_MANUAL_SPEED,
    PARAM_HUMIDITY,
    PARAM_SUPPLY_RPM,
    PARAM_EXTRACT_RPM,
    PARAM_FILTER_STATUS,
    PARAM_DIRECTION,
    PARAM_RECOVERY_EFFICIENCY,
]


def slug(value):
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return value.strip("_")


def checksum(payload):
    return sum(payload) & 0xFFFF


def read_param_stream(params):
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
        size = PARAM_SIZES.get(param, 1)
        raw = int(value).to_bytes(size, "little", signed=False)
        if size != 1:
            out.extend([0xFE, size])
        out.append(param & 0xFF)
        out.extend(raw)
    return bytes(out)


def packet(controller_id, password, func, data):
    controller_id = controller_id.encode("ascii")
    password = password.encode("ascii")
    body = bytearray([TYPE, len(controller_id)])
    body.extend(controller_id)
    body.append(len(password))
    body.extend(password)
    body.append(func)
    body.extend(data)
    return START + bytes(body) + struct.pack("<H", checksum(body))


def parse_response(data):
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
        values[param] = int.from_bytes(raw, "little") if raw is not None else None

    return controller_id, values


@dataclass
class Freshpoint:
    name: str
    ip: str
    controller_id: str
    password: str
    key: str


class FreshpointClient:
    def __init__(self, timeout=2.0):
        self.timeout = timeout

    def _send(self, unit, func, data):
        msg = packet(unit.controller_id, unit.password, func, data)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        sock.sendto(msg, (unit.ip, PORT))
        response, _ = sock.recvfrom(4096)
        _, values = parse_response(response)
        return values

    def read_state(self, unit):
        values = self._send(unit, 0x01, read_param_stream(READ_PARAMS))
        return {
            "power": values.get(PARAM_POWER),
            "speed_mode": values.get(PARAM_SPEED_MODE),
            "percentage": values.get(PARAM_MANUAL_SPEED),
            "humidity": values.get(PARAM_HUMIDITY),
            "supply_rpm": values.get(PARAM_SUPPLY_RPM),
            "extract_rpm": values.get(PARAM_EXTRACT_RPM),
            "filter_status": values.get(PARAM_FILTER_STATUS),
            "direction": values.get(PARAM_DIRECTION),
            "recovery_efficiency": values.get(PARAM_RECOVERY_EFFICIENCY),
        }

    def write(self, unit, writes):
        return self._send(unit, 0x03, write_param_stream(writes))

    def set_power(self, unit, enabled):
        return self.write(unit, [(PARAM_POWER, 1 if enabled else 0)])

    def set_percentage(self, unit, percentage):
        percentage = max(10, min(100, int(percentage)))
        return self.write(unit, [(PARAM_SPEED_MODE, 255), (PARAM_MANUAL_SPEED, percentage)])


class Bridge:
    def __init__(self, config):
        self.config = config
        self.client = FreshpointClient()
        self.topic_prefix = config["mqtt"].get("topic_prefix", "freshpoint").rstrip("/")
        self.discovery_prefix = config["mqtt"].get("discovery_prefix", "homeassistant").rstrip("/")
        self.poll_interval = config.get("poll_interval_seconds", 20)
        self.units = [
            Freshpoint(
                name=item["name"],
                ip=item["ip"],
                controller_id=item["id"],
                password=item.get("password", "1111"),
                key=item.get("key") or slug(item["name"]),
            )
            for item in config["freshpoints"]
        ]
        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config["mqtt"].get("client_id", "freshpoint-mqtt-bridge"))
        username = config["mqtt"].get("username")
        password = config["mqtt"].get("password")
        if username:
            self.mqtt.username_pw_set(username, password)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.stop_event = threading.Event()

    def base_topic(self, unit):
        return f"{self.topic_prefix}/{unit.key}"

    def availability_topic(self, unit):
        return f"{self.base_topic(unit)}/availability"

    def state_topic(self, unit):
        return f"{self.base_topic(unit)}/state"

    def command_topic(self, unit):
        return f"{self.base_topic(unit)}/set"

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"MQTT connected: {reason_code}")
        for unit in self.units:
            client.subscribe(f"{self.command_topic(unit)}/#")
            self.publish_discovery(unit)

    def on_message(self, client, userdata, message):
        topic = message.topic
        payload = message.payload.decode("utf-8").strip()
        for unit in self.units:
            prefix = self.command_topic(unit)
            if not topic.startswith(prefix + "/"):
                continue
            command = topic[len(prefix) + 1 :]
            try:
                if command == "power":
                    self.client.set_power(unit, payload.upper() in {"ON", "1", "TRUE"})
                elif command == "percentage":
                    self.client.set_percentage(unit, int(payload))
                else:
                    print(f"Unsupported command topic: {topic}")
                    return
                self.publish_unit_state(unit)
            except Exception as exc:
                print(f"{unit.name}: command failed for {topic}: {exc}")
            return

    def publish_discovery(self, unit):
        device = {
            "identifiers": [f"blauberg_freshpoint_{unit.controller_id}"],
            "manufacturer": "Blauberg",
            "model": "Freshpoint 160",
            "name": unit.name,
        }
        unique = f"freshpoint_{unit.key}"
        fan_config = {
            "name": unit.name,
            "unique_id": f"{unique}_fan",
            "availability_topic": self.availability_topic(unit),
            "state_topic": self.state_topic(unit),
            "state_value_template": "{{ value_json.power }}",
            "command_topic": f"{self.command_topic(unit)}/power",
            "payload_on": "ON",
            "payload_off": "OFF",
            "percentage_state_topic": self.state_topic(unit),
            "percentage_value_template": "{{ value_json.percentage }}",
            "percentage_command_topic": f"{self.command_topic(unit)}/percentage",
            "speed_range_min": 10,
            "speed_range_max": 100,
            "device": device,
        }
        self.mqtt.publish(
            f"{self.discovery_prefix}/fan/{unique}/config",
            json.dumps(fan_config),
            retain=True,
        )
        sensors = {
            "humidity": ("humidity", "%", None),
            "supply_rpm": ("supply fan rpm", "rpm", None),
            "extract_rpm": ("extract fan rpm", "rpm", None),
            "filter_status": ("filter status", None, None),
            "direction": ("direction", None, None),
            "recovery_efficiency": ("recovery efficiency", "%", None),
        }
        for key, (label, unit_of_measurement, device_class) in sensors.items():
            cfg = {
                "name": f"{unit.name} {label}",
                "unique_id": f"{unique}_{key}",
                "availability_topic": self.availability_topic(unit),
                "state_topic": self.state_topic(unit),
                "value_template": f"{{{{ value_json.{key} }}}}",
                "device": device,
            }
            if unit_of_measurement:
                cfg["unit_of_measurement"] = unit_of_measurement
            if device_class:
                cfg["device_class"] = device_class
            self.mqtt.publish(
                f"{self.discovery_prefix}/sensor/{unique}_{key}/config",
                json.dumps(cfg),
                retain=True,
            )

    def publish_unit_state(self, unit):
        try:
            state = self.client.read_state(unit)
            payload = {
                "power": "ON" if state.get("power") == 1 else "OFF",
                "speed_mode": state.get("speed_mode"),
                "percentage": state.get("percentage"),
                "humidity": state.get("humidity"),
                "supply_rpm": state.get("supply_rpm"),
                "extract_rpm": state.get("extract_rpm"),
                "filter_status": state.get("filter_status"),
                "direction": state.get("direction"),
                "recovery_efficiency": state.get("recovery_efficiency"),
            }
            self.mqtt.publish(self.state_topic(unit), json.dumps(payload), retain=True)
            self.mqtt.publish(self.availability_topic(unit), "online", retain=True)
            print(f"{unit.name}: {payload}")
        except Exception as exc:
            self.mqtt.publish(self.availability_topic(unit), "offline", retain=True)
            print(f"{unit.name}: poll failed: {exc}")

    def run(self):
        mqtt_config = self.config["mqtt"]
        self.mqtt.connect(mqtt_config["host"], int(mqtt_config.get("port", 1883)), keepalive=60)
        self.mqtt.loop_start()
        try:
            while not self.stop_event.is_set():
                for unit in self.units:
                    self.publish_unit_state(unit)
                self.stop_event.wait(self.poll_interval)
        finally:
            self.mqtt.loop_stop()
            self.mqtt.disconnect()


def main():
    parser = argparse.ArgumentParser(description="MQTT bridge for Blauberg Freshpoint 160 units.")
    parser.add_argument("--config", default="freshpoint_mqtt_config.json")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text())
    Bridge(config).run()


if __name__ == "__main__":
    main()
