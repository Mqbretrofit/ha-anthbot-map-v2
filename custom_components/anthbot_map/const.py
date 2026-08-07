"""Constants for the Anthbot Genie integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "anthbot_map"

CONF_API_HOST = "api_host"
CONF_BEARER_TOKEN = "bearer_token"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_AREA_CODE = "area_code"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_NAME = "Anthbot Genie"
DEFAULT_API_HOST = "api.anthbot.com"
DEFAULT_AREA_CODE = "36"

# Known category_id values (as reported by /api/v1.8.2/device/bindList).
# The app uses these as human-readable model names; mapping them keeps the
# device card in HA clean instead of showing cryptic codes.
MODEL_NAME_BY_CATEGORY: dict[str, str] = {
    "Genie 600": "Anthbot Genie 600",
    "Genie 1000": "Anthbot Genie 1000",
    "Genie 3000": "Anthbot Genie 3000",
    "Genie 5000": "Anthbot Genie 5000",
}

# Mapping of numeric error codes (err_code) to human-readable descriptions.
# Sourced from the Anthbot mobile app i18n table (error_226_des..error_260_des
# and friends) plus a few well-known ones; 0 means "no error".
ERROR_CODE_DESCRIPTIONS: dict[int, str] = {
    0: "No error",
    1: "Battery low",
    2: "Battery critically low",
    3: "Battery over-temperature",
    4: "Battery under-temperature",
    5: "Battery overvoltage",
    10: "Left wheel stuck",
    11: "Right wheel stuck",
    12: "Left wheel motor overload",
    13: "Right wheel motor overload",
    14: "Left wheel motor overheat",
    15: "Right wheel motor overheat",
    20: "Blade motor stuck",
    21: "Blade motor overload",
    22: "Blade motor overheat",
    30: "Device lifted",
    31: "Device tilted over limit",
    32: "Device rollover",
    33: "Device stuck",
    40: "Bumper sensor triggered",
    41: "Collision sensor jammed",
    42: "ToF sensor fault",
    43: "Structured-light sensor fault",
    50: "GPS not ready",
    51: "RTK not ready",
    52: "IMU bias error",
    53: "IMU data error",
    60: "Boundary wire break",
    61: "Boundary wire too long",
    62: "Charging pile communication error",
    63: "Charging pile overcurrent protection",
    64: "Charging pile wire error",
    65: "Recharge failure",
    66: "Docking station return failure",
    70: "WiFi config error",
    71: "WiFi connection error",
    80: "Firmware download error",
    81: "Firmware upgrade error",
    100: "Out of bounds",
    101: "Unreachable mowing area",
    102: "Started from forbidden zone",
    103: "Started from virtual wall",
    226: "Functional safety error",
    227: "Ground app error",
    228: "Ground base error",
    229: "React error",
    230: "Battery communication error",
    231: "Drive motor stall",
    232: "Drive motor overtemperature",
    233: "Cutting motor stall protection",
    234: "Mowing motor undervoltage",
    235: "Mowing motor stuck",
    236: "Lift up detected",
    237: "Lift motor fault",
}

# Robot maintenance component labels (shadow `robot_maintenance` has these
# three wear counters expressed as remaining percentage).
MAINTENANCE_LABELS: dict[str, str] = {
    "ccp_pecent": "Cutting components life",
    "cl_pecent": "Cutting line life",
    "rc_pecent": "Recharge dock brushes life",
}

# RTK state enum (from `rtk_state` int).
RTK_STATE_OPTIONS: dict[int, str] = {
    0: "not_ready",
    1: "single",
    2: "differential",
    3: "fixed",
    4: "float",
    5: "dead_reckoning",
}

# RTK base state enum (from `ctl_rtk_base.rtk_base_state` int).
RTK_BASE_STATE_OPTIONS: dict[int, str] = {
    0: "offline",
    1: "initializing",
    2: "searching",
    3: "online",
    4: "error",
}

DEFAULT_SCAN_INTERVAL = 10
DEFAULT_SCAN_INTERVAL_DELTA = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Service names and attributes.
SERVICE_START_FULL_MOW = "start_full_mow"
SERVICE_START_OUTER_EDGE_MOW = "start_outer_edge_mow"
SERVICE_START_DOCK_EDGE_MOW = "start_dock_edge_mow"
SERVICE_CONNECT_CLOUD = "connect_cloud"
SERVICE_STOP_MOW = "stop_mow"
SERVICE_SET_MOW_HEIGHT = "set_mow_height"
SERVICE_RETURN_TO_DOCK = "return_to_dock"
SERVICE_SET_VOICE_VOLUME = "set_voice_volume"
SERVICE_SET_CUSTOM_MOWING_DIRECTION = "set_custom_mowing_direction"
SERVICE_SET_RAIN_CONTINUE_TIME = "set_rain_continue_time"
SERVICE_SET_RAIN_PERCEPTION = "set_rain_perception"
SERVICE_START_ZONE_MOW = "start_zone_mow"
SERVICE_START_AUTO_ZONE_MOW = "start_auto_zone_mow"

ATTR_SERIAL_NUMBER = "serial_number"
ATTR_MOW_HEIGHT = "mow_height"
ATTR_VOICE_VOLUME = "voice_volume"
ATTR_MOW_DIRECTION = "mow_direction"
ATTR_ENABLE_CUSTOM_DIRECTION = "enable_custom_direction"
ATTR_RAIN_CONTINUE_TIME = "rain_continue_time"
ATTR_ENABLE_RAIN_PERCEPTION = "enable_rain_perception"
ATTR_ZONES = "zones"
ATTR_AUTO_ZONES = "auto_zones"

# Defaults embedded in Anthbot mobile app auth flow.
DEFAULT_IOT_REGION = "us-east-1"
DEFAULT_IOT_ENDPOINT = "a2bhy9nr7jkgaj-ats.iot.us-east-1.amazonaws.com"
IOT_ENDPOINT_TEMPLATE = "a2bhy9nr7jkgaj-ats.iot.{region}.amazonaws.com"
CN_NORTHWEST_IOT_ENDPOINT = "a2iw0czxjowiip-ats.iot.cn-northwest-1.amazonaws.com.cn"

# Country list for login (areaCode in Anthbot API).
COUNTRY_AREA_CODES: tuple[tuple[str, str], ...] = (
    ("Australia (+61)", "61"),
    ("Austria (+43)", "43"),
    ("Belgium (+32)", "32"),
    ("Brazil (+55)", "55"),
    ("United States / Canada (+1)", "1"),
    ("China (+86)", "86"),
    ("Czech Republic (+420)", "420"),
    ("Denmark (+45)", "45"),
    ("Finland (+358)", "358"),
    ("France (+33)", "33"),
    ("Germany (+49)", "49"),
    ("Greece (+30)", "30"),
    ("Hungary (+36)", "36"),
    ("India (+91)", "91"),
    ("Ireland (+353)", "353"),
    ("Italy (+39)", "39"),
    ("Japan (+81)", "81"),
    ("Luxembourg (+352)", "352"),
    ("Mexico (+52)", "52"),
    ("Netherlands (+31)", "31"),
    ("New Zealand (+64)", "64"),
    ("Norway (+47)", "47"),
    ("Poland (+48)", "48"),
    ("Portugal (+351)", "351"),
    ("Romania (+40)", "40"),
    ("Singapore (+65)", "65"),
    ("Slovakia (+421)", "421"),
    ("South Africa (+27)", "27"),
    ("South Korea (+82)", "82"),
    ("Spain (+34)", "34"),
    ("Sweden (+46)", "46"),
    ("Switzerland (+41)", "41"),
    ("Turkey (+90)", "90"),
    ("Ukraine (+380)", "380"),
    ("United Arab Emirates (+971)", "971"),
    ("United Kingdom (+44)", "44"),
)
