"""Documented settings shared by entity platforms, polling and validation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Setting:
    """One bounded writable protocol field."""

    key: str
    platform: str
    param: int
    size: int = 1
    minimum: int = 0
    maximum: int = 1
    options: tuple[tuple[int, str], ...] = ()
    unit: str | None = None
    encoding: str = "integer"
    enabled_default: bool = True
    config: bool = True

    def encode(self, value: int | float) -> int:
        """Reject invalid values before creating a UDP request."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Invalid value for {self.key}")
        if not self.minimum <= value <= self.maximum or int(value) != value:
            raise ValueError(f"Invalid value for {self.key}: {value}")
        number = int(value)
        if self.options and number not in dict(self.options):
            raise ValueError(f"Invalid option for {self.key}: {number}")
        if self.key == "filter_interval" and number not in (0, *range(70, 366)):
            raise ValueError("Filter interval must be 0 or 70-365 days")
        if self.encoding == "minutes":
            return (number // 60 << 8) | (number % 60)
        return number

    def decode(self, raw: int | bytes | None) -> int | None:
        """Decode a field without assigning meaning to invalid responses."""
        if not isinstance(raw, int):
            return None
        value = raw
        if self.encoding == "minutes":
            minute, hour = raw & 255, raw >> 8
            if minute > 59 or hour > 23:
                return None
            value = hour * 60 + minute
        try:
            self.encode(value)
        except ValueError:
            return None
        return value


SETTINGS = (
    Setting("speed_mode", "select", 2, maximum=255,
            options=tuple((i, f"speed_{i}") for i in range(1, 6)) + ((255, "manual"),), config=False),
    Setting("humidity_auto", "switch", 15),
    Setting("co2_auto", "switch", 17),
    Setting("humidity_threshold", "number", 25, minimum=40, maximum=80, unit="%"),
    Setting("co2_threshold", "number", 26, size=2, minimum=400, maximum=2000, unit="ppm"),
    Setting("filter_interval", "number", 99, size=2, maximum=365, unit="d"),
    Setting("weekly_schedule", "switch", 114),
    Setting("cloud", "switch", 133),
    # Timer fields have minute/hour bytes. Restrict the UI to valid wall-clock fields.
    Setting("night_duration", "number", 770, size=2, maximum=1439, unit="min", encoding="minutes"),
    Setting("turbo_duration", "number", 771, size=2, maximum=1439, unit="min", encoding="minutes"),
    Setting("voc_auto", "switch", 789),
    Setting("voc_threshold", "number", 799, size=2, minimum=50, maximum=250),
    Setting("display_brightness", "number", 1024, minimum=1, maximum=100, unit="%"),
    # English Freshpoint manual, page 11: zero-based codes; Polish edition differs.
    Setting("sound", "switch", 1025),
    Setting("backlight_mode", "select", 1026, options=((0, "auto"), (1, "manual"))),
    Setting("display_temperature", "select", 1027, maximum=2,
            options=((0, "alternating"), (1, "supply"), (2, "extract"))),
    Setting("display_air_quality", "select", 1028, maximum=2,
            options=((0, "alternating"), (1, "co2"), (2, "voc"))),
    Setting("display_content", "select", 1029, maximum=2,
            options=((0, "alternating"), (1, "time"), (2, "temperature_humidity"))),
    Setting("standby_clock", "switch", 1030),
    Setting("display_mode", "select", 1031, maximum=2,
            options=((0, "off"), (1, "on"), (2, "scheduled_off"))),
    Setting("display_off_start", "time", 1032, size=2, maximum=1439, encoding="minutes"),
    Setting("display_off_end", "time", 1033, size=2, maximum=1439, encoding="minutes"),
)

SETTINGS_BY_KEY = {setting.key: setting for setting in SETTINGS}
