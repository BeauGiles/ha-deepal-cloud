"""Constants for the Changan Deepal Cloud integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import Platform

DOMAIN = "deepal"
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.COVER,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.TIME,
    Platform.IMAGE,
    Platform.DEVICE_TRACKER,
]



def vehicle_uses_mqtt(vehicle: dict[str, Any]) -> bool:
    """Return whether the cloud declares this vehicle as MQTT-backed.

    Matches variants such as the E07's "SDA-MQTT" as well as plain "MQTT".
    """
    return "MQTT" in str(vehicle.get("protocolType") or "").upper()


def vehicle_uses_sda(vehicle: dict[str, Any]) -> bool:
    """Return whether telemetry comes from the SDA REST condition (Deepal E07)."""
    return str(vehicle.get("protocolType") or "").upper() == "SDA-MQTT"


def vehicle_supports_mqtt_commands(vehicle: dict[str, Any]) -> bool:
    """Return whether MQTT remote commands are available for this vehicle.

    The command mappings are only validated on vehicles reporting exactly
    "MQTT" (the S05). Variants such as "SDA-MQTT" are telemetry-only until
    their command protocol has been confirmed.
    """
    return str(vehicle.get("protocolType") or "").upper() == "MQTT"


CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_VEHICLE_ID = "vehicle_id"
CONF_COUNTRY = "country"
CONF_LANGUAGE = "language"
CONF_APP_VERSION = "app_version"
CONF_DEVICE_ID = "device_id"
CONF_EMAIL = "email"
CONF_PRIVATE_KEY = "private_key_pem"
CONF_LOGIN_METHOD = "login_method"
CONF_ENABLE_COMMANDS = "enable_commands"
CONF_ENABLE_API_LOGGING = "enable_api_logging"
CONF_FETCH_LOCATION = "fetch_location"
CONF_ACTIVE_REFRESH_INTERVAL = "active_refresh_interval"
CONF_RC_TOKEN = "rc_token"
CONF_CONTROL_PIN = "control_pin"
CONF_CAC_TOKEN = "cac_token"
CONF_USER_ID = "user_id"
CONF_CA_USER_ID = "ca_user_id"
CONF_CAC_USER_ID = "cac_user_id"

DEFAULT_COUNTRY = "GB"
DEFAULT_LANGUAGE = "en_US"
DEFAULT_APP_VERSION = "V1.12.0"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_ACTIVE_REFRESH_INTERVAL = 300

# MQTT vehicle wake (manual refresh only; the periodic poll never wakes the
# car). Waking drains the 12 V battery, so it is throttled. Values follow
# Sunek0/ha-deepal-alternative (MIT).
# Command handling. Commands are queued (one runs at a time); a command whose
# cloud result says "success" stops waiting for the vehicle data after a short
# grace period, because the cloud snapshot can lag behind or omit the change.
MAX_QUEUED_COMMANDS = 4  # running + waiting
COMMAND_SUCCESS_GRACE = 8  # seconds to wait for the data after a success result
COMMAND_INQUIRY_WAIT = 6  # seconds to wait after the final condition inquiry

# The gateway rejects an air-conditioning target outside this range
# (COMMON_1_1_01_005); the app offers the same limits.
AC_MIN_TEMP_C = 18.0
AC_MAX_TEMP_C = 32.0

# When MQTT telemetry fails (for example the CA gateway rejects the token for an
# account), fall back to the REST condition and retry MQTT with a growing delay
# instead of hammering the gateway every poll.
MQTT_BACKOFF_BASE = 60  # seconds after the first failure; doubles each time
MQTT_BACKOFF_MAX = 600  # seconds

# The CA bootstrap is per vehicle and practically static, and the auth token is
# account level, so both are reused instead of fetched on every MQTT session.
MQTT_CONFIG_TTL = 660  # seconds (about two default poll cycles)
MQTT_TOKEN_TTL = 60  # seconds

# After an HTTP 429 the integration stops calling the API for the gateway's
# Retry-After (at least the minimum, at most the maximum) instead of retrying.
RATE_LIMIT_MIN_BACKOFF = 60  # seconds
RATE_LIMIT_MAX_BACKOFF = 3600  # seconds
# A session-invalid answer from the CA gateway refreshes the session at most this often.
SESSION_REFRESH_MIN_INTERVAL = 3600  # seconds

WAKE_STALE_AFTER = 120  # seconds since the last report before a refresh wakes the car
WAKE_COOLDOWN = 300  # minimum seconds between wakes
WAKE_REPORT_TIMEOUT = 60  # seconds to wait for a fresh report after a wake
WAKE_POLL_INTERVAL = 5  # seconds between report reads while waiting

BASE_URL = "https://m.iov.changanauto.com.de"
CA_BASE_URL = "https://ca-m.iov.changanauto.com.de"
SDA_BASE_URL = "https://sda-m.iov.changanauto.com.de"

# Default (European) cluster gateway prefix baked into the endpoint paths.
DEFAULT_GATEWAY = "/intl-app-gw"

# Region-specific gateways. Accounts are homed on regional clusters: the default
# European cluster serves GB/IL/PT, while Australia and the rest of APAC are
# homed on the Singapore cluster, which fronts the same services behind an
# "/appgw" gateway prefix instead of "/intl-app-gw". Authenticating an APAC-homed
# account against the European cluster returns CAC_1_1_01_024 "Account not
# registered", so these requests must be routed here instead.
#
# NOTE: only AU has been confirmed working. The remaining entries assume the
# original BeauGiles/ha-deepal integration's APAC countries all share the same
# Singapore cluster/gateway as AU, since that integration worked for them
# against a single shared endpoint. This is UNTESTED for anything other than
# AU — flag issues per-country if login fails.
# Hosts are the ASEAN ("release_ase") environment of the app. The SDA host is
# taken from the app's environment table as documented by
# Sunek0/ha-deepal-alternative (MIT); only the main host is confirmed for AU.
# The CA host is deliberately not overridden: MQTT (S05) behaviour in APAC is
# left exactly as it was.
_APAC_REGION = {
    "base_url": "https://m.iov.changanauto.sg",
    "sda_base_url": "https://prod-m.sda.changanauto.sg",
    "gateway": "/appgw",
}

REGION_GATEWAYS = {
    "AU": _APAC_REGION,
    "NZ": _APAC_REGION,
    "SG": _APAC_REGION,
    "MY": _APAC_REGION,
    "TH": _APAC_REGION,
    "VN": _APAC_REGION,
    "HK": _APAC_REGION,
    "MO": _APAC_REGION,
    "ID": _APAC_REGION,
    "PH": _APAC_REGION,
    "MN": _APAC_REGION,
}

# 2048-bit RSA public key used by the app to encrypt mobile/password/control PIN fields.
# Extracted from the live app's Dalvik heap and validated against send-auth-code:
# RSA/ECB/PKCS1Padding succeeds; OAEP variants fail.
REQUEST_ENCRYPTION_PUBLIC_KEY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkyhr43cBPTJ3jLiYsmbUwUp74cMJIOju5vqVzgtuK63Q99qV6iVT8wN5cXlyMtWI2mfOmhIao/fUN821im69MfOHsWXdqQEo5e9v654GPw+bju0pCphEPtD1I0VcyS34QkAu04urSun2U1q3Dr2OICLVWSnLa+01ioKxkaB0D209zXcls2eFQpvRAWm7xxVsoqzSwqp+neu5quOpn+eO/bW0TxcSQ8VZcDEUvadRTLSR0eOWgRuHIBiD2RGqPIPzKCm5A14q1qhxUZ8U0pmYe0Sx7eMy4RVe2iW7fnjc6pxTUMBkercSL26mevYouuCKqyie+LVQAtGa29RMl/lyiwIDAQAB"
)
