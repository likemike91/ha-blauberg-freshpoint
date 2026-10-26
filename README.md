# Blauberg Freshpoint for Home Assistant

Home Assistant custom integration for local control of Blauberg Freshpoint ventilation units.

## Features

- Local control, no cloud dependency
- Automatic network discovery during setup
- Fan on/off control
- Fan percentage control
- Operating mode control: ventilation, heat recovery, supply only, and extraction only
- Night and turbo timer control
- Heater control and active-state feedback
- Outdoor, supply, extract inlet, and extract outlet temperature sensors
- Humidity sensor
- Optional CO2 and VOC/air-quality sensors on models that report them
- Supply and extract fan RPM sensors
- Filter status, remaining-time sensor, and filter-timer reset button
- Editable device date and time (years 2000-2099)
- Set current time button (copies Home Assistant local time and date to each unit)
- Motor runtime sensor
- Alarm/warning and frost-protection status
- Rotation direction sensor
- Recovery efficiency sensor
- Support for multiple Freshpoint units

Temperature support follows the device protocol: values are reported in 0.1 degrees Celsius.
If a model does not have a documented temperature sensor, that entity reports no value.

## Controls and Defaults

| Controls | Category | Enabled by default |
| --- | --- | --- |
| Fan power, manual percentage, speed modes 1-5/manual, airflow mode, night/turbo mode | Normal | Yes |
| Humidity/CO2/VOC automatic control and thresholds | Configuration | Yes |
| Night/turbo duration, filter replacement interval | Configuration | Yes |
| Weekly schedule enable, cloud permission | Configuration | Yes |
| Display brightness, sound, backlight, displayed values, standby clock, off interval | Configuration | Yes |
| Editable live device date/time | Configuration | No |
| Set-current-time button | Configuration | Yes |
| Room climate and timer countdown | Normal | Yes |
| Filter countdown/change, fault status, alarm codes/count and frost protection | Diagnostic | Yes |
| RPM, runtime, efficiency, raw direction/filter status and device type | Diagnostic | No |
| RTC battery voltage, firmware/build date, current IP and Wi-Fi channel | Diagnostic | No |
| Device-reported humidity/CO2/VOC threshold flags | Diagnostic | No |

Defaults apply to new entities; existing registry preferences are preserved. Disabled
entities do not cause parameter reads, including at startup. Shared parameters are read
while any enabled entity needs them. If all read-dependent entities are disabled, no
state-read UDP request is sent. Discovery and explicit commands are separate from polling.
Optional entities are registered even without a value, so they can be enabled later;
unsupported fields remain unknown. Stable diagnostics (RTC voltage, firmware, current IP
and Wi-Fi channel) are fetched at most once per hour while enabled; other enabled fields
use the normal 20-second polling interval. Network rediscovery invalidates that cache.

The **Device date and time** configuration entity displays and writes RTC parameters 111
and 112 in Home Assistant's timezone. Years 2000-2099 are supported. The device stores
no timezone/DST flag, so repeated wall times cannot be distinguished. The **Set current
time** button copies Home Assistant's current local clock and calendar. Neither control
synchronizes automatically; press again after a DST change or use a Home Assistant
automation. Changing the clock can affect an existing device schedule.

### Clock actions and history

The live **Device date and time** entity is disabled by default for new devices. When
disabled, RTC parameters 111/112 are not polled and no continuous clock changes are
published to Activity/Recorder. Existing entity preferences are preserved: if upgrading
from 0.3.0, disable **Device date and time** in each device's entity settings to stop its
updates. Existing history is not deleted. Enabling it again resumes live readings and
regular Activity/Recorder entries; the integration does not modify global history filters.

The clock can be set without enabling the live entity or the button:

| Action | Required fields | Behavior |
| --- | --- | --- |
| `freshpoint.set_current_datetime` | `device_id`: one device registry ID or a list | Copies Home Assistant's current local date and time |
| `freshpoint.set_datetime` | `device_id`, `datetime` | Writes a supplied date and time, including the weekday |

Use the action picker in an automation or **Developer tools → Actions**. Select one or
more devices in **Freshpoint devices**; for `set_datetime`, supply **Date and time** as
well (for example `2026-10-26 12:30:00`). Values without a timezone use Home Assistant's
configured timezone; offset-aware values are converted to that timezone. Supported
calendar years are 2000-2099 after conversion. There is no implicit default device, and
all selected devices must be loaded Freshpoint devices. Both actions write the time and
calendar together. The existing button calls the same internal method as
`set_current_datetime`; its unique ID remains unchanged.

Numeric controls use explicit validated writes, not toggle commands. Filter interval
accepts 0 or 70-365 days (values 1-69 are rejected); changing the interval may affect the
current countdown. Timer durations use minutes, conservatively limited to 0-1439
(23:59); larger durations have not been verified. Display off times have minute precision.
Display brightness is the manual brightness setpoint; select manual backlight mode to use
it. New controls check write acknowledgements before refreshing enabled entity values.

Enabling the device's automatic control or weekly program can change airflow immediately.
The percentage entity reports the manual setpoint only in manual speed mode; preset mode
is shown by the separate speed-mode select. The timer and device automatics can override
manual behavior. Cloud permission changes do not require a cloud connection from this
integration.

Alarm details expose a count plus an `alarms` attribute containing numeric codes and
alarm/warning severity. Code descriptions are not guessed. Firmware exposes a build-date
attribute. Air-quality flags are device-reported; when the corresponding automatic
control is off they may remain normal even when the measured value exceeds the threshold.

## Verification and Remaining Capabilities

Read support for the newly exposed fields was verified on a Freshpoint 160 (firmware
0.12). Hardware write testing and Home Assistant runtime testing of the new controls are
still pending. In particular, verify display behavior and filter/timer side effects before
using these controls in automations.

The English manufacturer manual uses zero-based display codes for parameters 1025, 1026
and 1031. These agree with the observed device reads; the Polish edition differs. The
CO2 threshold is encoded with two bytes, as documented in the Polish edition and observed
on hardware; the English table incorrectly lists one byte for its 400-2000 ppm range.

Weekly schedule editing (119), speed-profile tuning (58-63), schedule-stage diagnostics
(774) and alarm reset (128) remain deferred until their behavior and UI are verified.
Wi-Fi reconfiguration, reading passwords and destructive factory/profile resets are
intentionally excluded. Passwords are used only for local device authentication.

Protocol references:
[English Freshpoint manufacturer manual](https://manuals.plus/m/bc5e11d73fd4b238edb650179ccd01f392bc33b5c9bd595439141b22028a2d5e.pdf),
[Polish Freshpoint manufacturer manual](https://blauberg24.pl/userdata/public/assets/FRESHPOINT_Podlaczenie_do_systemu-_Inteligentny-_dom.pdf).

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

## Releases

Each release has notes in `release_notes/<version>.md`. After merging and validating a
release, push the matching semantic-version tag (for example `v0.3.1`). The release
workflow checks that the tag matches `manifest.json` and publishes those notes as the
GitHub Release body for HACS. A changelog file alone does not publish HACS release notes.
Creating this branch does not publish a release or tag.

For local tests, install `requirements_test.txt` into a development environment and run
`python3 -m unittest discover` in addition to the compilation/JSON checks.
