# AGENTS.md

Guidance for future coding agents working on this repository.

## Project

This repository contains a Home Assistant custom integration for Blauberg Freshpoint ventilation units using the documented local UDP Smart House protocol on port `4000`.

The publishable integration lives in:

```text
custom_components/freshpoint
```

The root-level scripts are development helpers:

- `freshpoint_probe.py` for discovery and direct protocol testing
- `freshpoint_mqtt_bridge.py` for the earlier MQTT bridge prototype

Do not make Home Assistant runtime code depend on those helper scripts.

## Development Rules

- Keep the integration cloud-free and local-first.
- Avoid third-party Python requirements in `manifest.json` unless absolutely necessary.
- Keep all Home Assistant runtime code inside `custom_components/freshpoint`.
- Use Home Assistant config entries and entity platforms rather than YAML-only setup.
- Keep one config flow capable of discovering multiple Freshpoint units.
- Treat UDP calls as blocking I/O and run them through Home Assistant executor jobs.
- Preserve compatibility with multiple Freshpoint devices in one config entry.

## Protocol Notes

- UDP port: `4000`
- Packet prefix: `0xFD 0xFD`
- Protocol type: `0x02`
- Default password: `1111`
- Discovery uses controller ID `DEFAULT_DEVICEID`
- Discovery reads:
  - `0x007C` device/controller ID
  - `0x00B9` device type
- Freshpoint 160 reports device type `17`
- Setting percentage writes:
  - `0x0002 = 255` manual speed mode
  - `0x0044 = percentage`

## Validation

Before handing off changes, run:

```bash
python3 -m py_compile custom_components/freshpoint/*.py freshpoint_probe.py freshpoint_mqtt_bridge.py
python3 -m json.tool hacs.json >/dev/null
python3 -m json.tool custom_components/freshpoint/manifest.json >/dev/null
python3 -m json.tool custom_components/freshpoint/strings.json >/dev/null
```

If Home Assistant test tooling is added later, prefer validating with `hassfest` and a real Home Assistant instance.

## Release Checklist

- Update `version` in `custom_components/freshpoint/manifest.json`.
- Replace placeholder GitHub URLs in `manifest.json`.
- Confirm `README.md` installation instructions match the published repository URL.
- Test setup flow in Home Assistant:
  - discovery using `255.255.255.255`
  - discovery using a subnet broadcast address such as `192.168.1.255`
  - selecting multiple devices
  - fan on/off
  - percentage control
  - sensor polling
- Tag releases with semantic versions, for example `v0.1.0`.
