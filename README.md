# Blauberg Freshpoint for Home Assistant

Custom Home Assistant integration for local control of Blauberg Freshpoint 160 ventilation units over the documented UDP Smart House protocol.

This integration was built against Freshpoint 160 devices that identify as device type `17` and listen on UDP port `4000`.

## Features

- Local polling, no cloud dependency
- Config flow setup from the Home Assistant UI
- Fan entity with on/off and percentage control
- Sensors for humidity, fan RPM, filter status, rotation direction, recovery efficiency, and device type
- Supports multiple Freshpoint units by adding each device separately

## Installation With HACS

Until this repository is added to the default HACS list, install it as a custom repository.

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the three-dot menu.
4. Choose **Custom repositories**.
5. Add your published repository URL.
6. Select category **Integration**.
7. Install **Blauberg Freshpoint**.
8. Restart Home Assistant.

Recommended repository name:

```text
ha-blauberg-freshpoint
```

## Manual Installation

Copy `custom_components/freshpoint` into your Home Assistant `custom_components` directory:

```text
config/custom_components/freshpoint
```

Restart Home Assistant.

## Setup

Add the integration from:

```text
Settings -> Devices & services -> Add integration -> Blauberg Freshpoint
```

During setup the integration broadcasts a discovery request and shows the Freshpoint units it finds. Select the units you want to add.

You need:

- device password, default `1111`

If discovery does not work on your network, use a subnet broadcast address such as `192.168.1.255` instead of `255.255.255.255`. You can also discover devices with the included helper script:

```bash
python3 freshpoint_probe.py 192.168.1.255 --broadcast
```

Use your own broadcast address, for example `192.168.178.255`.

## Known Freshpoint Parameters Used

| Parameter | Meaning |
| --- | --- |
| `0x0001` | Power |
| `0x0002` | Speed mode |
| `0x0044` | Manual speed percentage |
| `0x0025` | Room humidity |
| `0x004A` | Supply fan RPM |
| `0x004B` | Extract fan RPM |
| `0x0088` | Filter status |
| `0x00B7` | Fan rotation direction |
| `0x0129` | Recovery efficiency |
| `0x00B9` | Device type |

## Notes

Setting a percentage switches the device to manual speed mode by writing:

- `0x0002 = 255`
- `0x0044 = percentage`

The integration stores all selected devices in one Home Assistant config entry. Run setup again later to add newly discovered units.

## Development

The standalone scripts are included for protocol testing:

- `freshpoint_probe.py`
- `freshpoint_mqtt_bridge.py`

The Home Assistant integration itself does not require external Python packages.
