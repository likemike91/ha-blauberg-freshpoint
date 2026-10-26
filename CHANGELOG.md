# Changelog

## 0.3.1

- Disable the live device clock by default for new entities, avoiding continuous clock Activity/history updates; existing installations can disable it manually.
- Add device-level set_datetime and set_current_datetime actions independent of enabled entities.
- Keep the current-time button on the shared coordinator method without changing its entity identity.
- Add HACS-facing release notes and a tag-triggered GitHub Release workflow.

## 0.3.0

- Added fan speed-mode selection, humidity/CO2/VOC automatic controls and thresholds.
- Added night/turbo duration, timer countdown, filter interval, weekly-schedule enable and cloud permission.
- Added display brightness, content, sound, backlight, standby clock and off-interval controls.
- Added alarm codes/count, firmware, RTC battery, air-quality status and network diagnostics.
- Kept technical diagnostics disabled by default and fetch stable diagnostics hourly when enabled.
- Split state reads to respect the documented UDP packet limit.
- New write controls validate ranges and device acknowledgements; hardware write testing is pending.

## 0.2.3

- Added an editable local device date/time entity for RTC parameters 111 and 112.
- Poll only parameters required by enabled entities, including on startup.
- Categorized diagnostic sensors and disabled technical detail sensors by default.

## 0.2.2

- Added a per-device button to set the clock and calendar from Home Assistant local time.
- Clarified protocol capabilities that are not yet exposed.

## 0.2.0

- Added outdoor, supply, extract inlet, and extract outlet temperature sensors.
- Added an operating mode select for ventilation, heat recovery, supply only, and extraction only.
- Added heater and night/turbo timer controls.
- Added filter reset, filter countdown, motor runtime, heater/frost/problem status, and optional
  CO2/VOC sensors.

## 0.1.0

- Initial HACS-ready custom integration.
- Added local UDP discovery for Freshpoint units.
- Added fan entity with on/off and percentage control.
- Added sensors for humidity, fan RPM, filter status, direction, recovery efficiency, and device type.
