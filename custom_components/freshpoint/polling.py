"""Parameter dependencies and defaults for each entity."""

from . import const as c
from .settings import SETTINGS

# Platform, unique-ID suffix, required read parameters, enabled by default.
ENTITY_READS = (
    ("fan", "fan", (c.PARAM_POWER, c.PARAM_MANUAL_SPEED, c.PARAM_SPEED_MODE), True),
    ("select", "operating_mode", (c.PARAM_DIRECTION,), True),
    ("select", "timer_mode", (c.PARAM_TIMER_MODE,), True),
    ("switch", "heater", (c.PARAM_HEATER_CONTROL,), True),
    ("datetime", "device_clock", (c.PARAM_RTC_TIME, c.PARAM_RTC_CALENDAR), False),
    ("sensor", "outdoor_temperature", (c.PARAM_OUTDOOR_TEMPERATURE,), True),
    ("sensor", "supply_temperature", (c.PARAM_SUPPLY_TEMPERATURE,), True),
    ("sensor", "extract_inlet_temperature", (c.PARAM_EXTRACT_INLET_TEMPERATURE,), True),
    ("sensor", "extract_outlet_temperature", (c.PARAM_EXTRACT_OUTLET_TEMPERATURE,), True),
    ("sensor", "humidity", (c.PARAM_HUMIDITY,), True),
    ("sensor", "co2", (c.PARAM_CO2,), True),
    ("sensor", "voc", (c.PARAM_VOC,), True),
    ("sensor", "supply_rpm", (c.PARAM_SUPPLY_RPM,), False),
    ("sensor", "extract_rpm", (c.PARAM_EXTRACT_RPM,), False),
    ("sensor", "filter_status", (c.PARAM_FILTER_STATUS,), False),
    ("sensor", "filter_countdown", (c.PARAM_FILTER_COUNTDOWN,), True),
    ("sensor", "motor_runtime", (c.PARAM_MOTOR_RUNTIME,), False),
    ("sensor", "fault_warning", (c.PARAM_FAULT_WARNING,), True),
    ("sensor", "direction", (c.PARAM_DIRECTION,), False),
    ("sensor", "recovery_efficiency", (c.PARAM_RECOVERY_EFFICIENCY,), False),
    ("sensor", "device_type", (c.PARAM_DEVICE_TYPE,), False),
    ("binary_sensor", "filter", (c.PARAM_FILTER_STATUS,), True),
    ("binary_sensor", "heater_active", (c.PARAM_HEATER_STATUS,), True),
    ("binary_sensor", "frost_protection", (c.PARAM_FROST_PROTECTION,), True),
    ("binary_sensor", "problem", (c.PARAM_FAULT_WARNING,), True),
)

ENTITY_READS += tuple(
    (setting.platform, setting.key, (setting.param,), setting.enabled_default)
    for setting in SETTINGS
)
ENTITY_READS += (
    ("sensor", "timer_remaining", (11,), True),
    ("sensor", "rtc_battery", (36,), False),
    ("sensor", "alarm_details", (127,), True),
    ("sensor", "firmware", (134,), False),
    ("sensor", "wifi_channel", (154,), False),
    ("sensor", "current_ip", (163,), False),
    ("binary_sensor", "humidity_threshold_exceeded", (132,), False),
    ("binary_sensor", "co2_threshold_exceeded", (132,), False),
    ("binary_sensor", "voc_threshold_exceeded", (132,), False),
)


def enabled_read_params(controller_id, lookup):
    """Resolve registry preferences, including before entities are first added."""
    params = set()
    for platform, suffix, dependencies, default in ENTITY_READS:
        entry = lookup(platform, f"{controller_id}_{suffix}")
        enabled = entry.disabled_by is None if entry is not None else default
        if enabled:
            params.update(dependencies)
    return sorted(params)
