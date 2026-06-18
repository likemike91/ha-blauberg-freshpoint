# Blauberg Freshpoint for Home Assistant

Home Assistant custom integration for local control of Blauberg Freshpoint ventilation units.

## Features

- Local control, no cloud dependency
- Automatic network discovery during setup
- Fan on/off control
- Fan percentage control
- Humidity sensor
- Supply and extract fan RPM sensors
- Filter status sensor
- Rotation direction sensor
- Recovery efficiency sensor
- Support for multiple Freshpoint units

## Installation With HACS

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the three-dot menu.
4. Choose **Custom repositories**.
5. Add this repository URL.
6. Select category **Integration**.
7. Install **Blauberg Freshpoint**.
8. Restart Home Assistant.

## Manual Installation

Copy the integration folder into your Home Assistant configuration directory:

```text
custom_components/freshpoint
```

Restart Home Assistant.

## Setup

1. Go to **Settings** -> **Devices & services**.
2. Select **Add integration**.
3. Search for **Blauberg Freshpoint**.
4. Enter the device password. The default password is `1111`.
5. Keep the default broadcast address unless discovery does not find your devices.
6. Select the discovered Freshpoint units you want to add.

If discovery does not find your devices, try your subnet broadcast address instead. For example:

```text
192.168.1.255
```

or:

```text
192.168.178.255
```

## Supported Devices

This integration has been tested with Freshpoint 160 units.

Other Blauberg Freshpoint models may work if they use the same local control protocol.

## Troubleshooting

If no devices are discovered:

- Confirm Home Assistant is on the same network as the Freshpoint units.
- Confirm the Freshpoint units are connected to Wi-Fi.
- Try your subnet broadcast address instead of `255.255.255.255`.
- Check that firewalls allow local UDP traffic to the Freshpoint units.
- Confirm the device password is correct.

If entities are unavailable:

- Confirm the Freshpoint IP addresses did not change.
- Assign static DHCP leases for the Freshpoint units in your router.
- Restart Home Assistant after changing network settings.
