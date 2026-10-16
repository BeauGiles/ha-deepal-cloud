"""Shared helpers: seat roles, redaction, command results and payloads."""

from __future__ import annotations

import pytest

from custom_components.deepal.api import (
    DeepalClient,
    _charge_minutes,
    _front_pair,
    _mqtt_command_result_error,
    _redact_for_log,
    _redact_signals,
    add_seat_roles,
    unmapped_signal_keys,
)
from custom_components.deepal.sensor import _format_hours_minutes

SEATS = {"seat": {"leftFront": {"heatStatus": 1}, "rightFront": {"heatStatus": 3}}}


class TestSeatRoles:
    def test_rhd_driver_is_front_right(self):
        seat = add_seat_roles(SEATS, "RHD")["seat"]
        assert (seat["driver"]["heatStatus"], seat["passenger"]["heatStatus"]) == (3, 1)

    def test_lhd_driver_is_front_left(self):
        seat = add_seat_roles(SEATS, "LHD")["seat"]
        assert (seat["driver"]["heatStatus"], seat["passenger"]["heatStatus"]) == (1, 3)

    def test_unknown_side_defaults_to_rhd(self):
        assert add_seat_roles(SEATS, None)["seat"]["driver"]["heatStatus"] == 3

    def test_condition_without_seats_is_untouched(self):
        assert add_seat_roles({"x": 1}, "RHD") == {"x": 1}

    def test_input_is_not_mutated(self):
        add_seat_roles(SEATS, "RHD")
        assert "driver" not in SEATS["seat"]


@pytest.mark.parametrize(
    ("side", "legacy_left", "expected"),
    [
        ("RHD", True, ("P", "D")),
        ("LHD", False, ("D", "P")),
        ("rhd", True, ("P", "D")),
        (None, True, ("D", "P")),
        (None, False, ("P", "D")),
    ],
)
def test_front_pair(side, legacy_left, expected):
    assert _front_pair("D", "P", side, legacy_driver_left=legacy_left) == expected


@pytest.mark.parametrize(("value", "expected"), [(8191, None), (8191.0, None), (0, 0), (95, 95), (None, None)])
def test_charge_minutes(value, expected):
    assert _charge_minutes(value) == expected


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(218, "3:38"), (5, "0:05"), (60, "1:00"), (0, "0:00"), (8191, None), (None, None), (-1, None)],
)
def test_hours_minutes_format(minutes, expected):
    assert _format_hours_minutes(minutes) == expected


class TestRedaction:
    def test_secrets_and_identifiers_are_redacted(self):
        redacted = _redact_for_log(
            {"vin": "X", "plateNumber": "ABC", "Lat": 1, "Lng": 2, "location": {"a": 1}, "access_token": "t", "soc": 80}
        )
        assert redacted["soc"] == 80
        assert all(redacted[key] == "[redacted]" for key in ("vin", "plateNumber", "Lat", "Lng", "location", "access_token"))

    def test_latest_date_is_not_mistaken_for_latitude(self):
        assert _redact_for_log({"latestDate": "2026"})["latestDate"] == "2026"

    def test_substring_rules_would_hide_unrelated_signals(self):
        # Names that merely contain "key"/"pin" are legitimate signals...
        assert _redact_for_log({"RemoteKeyBatt": 3})["RemoteKeyBatt"] == "[redacted]"
        # ...so raw signal dumps only redact exact sensitive names.
        raw = _redact_signals({"RemoteKeyBatt": 3, "MappingPinSts": 1, "Lat": 1, "vin": "X"})
        assert raw == {"RemoteKeyBatt": 3, "MappingPinSts": 1, "Lat": "[redacted]", "vin": "[redacted]"}

    def test_unmapped_signal_list_key_is_visible(self):
        # "key" in a name would redact it; the diagnostics field must avoid that.
        assert _redact_for_log({"unmapped_signals": ["A"]})["unmapped_signals"] == ["A"]


class TestMqttCommandResult:
    @staticmethod
    def error(item):
        return _mqtt_command_result_error({"rs": [item]}, "secret", "req")

    @pytest.mark.parametrize("code", ["000000", "0", 0, 200, "OK", "SUCCESS"])
    def test_success_codes(self, code):
        assert self.error({"code": code}) is None

    def test_known_vehicle_error_is_explained(self):
        assert "door status" in self.error({"code": "VVCC_-1_-1_02_023"})

    def test_explicit_failure_flag(self):
        assert self.error({"success": False, "msg": "nope"}) == "nope"


class TestSeatPayload:
    def test_driver_on(self):
        assert DeepalClient._seat_payload("seats_heat", driver=True, level=2) == {
            "command": "seats_heat",
            "masterSwitch": 1,
            "masterLevel": 2,
        }

    def test_passenger_off_sends_no_level(self):
        # The endpoint rejects a zero level and explicit nulls.
        assert DeepalClient._seat_payload("seats_wind", driver=False, level=0) == {
            "command": "seats_wind",
            "copilotSwitch": 0,
        }


def test_unmapped_signal_keys_only_lists_unread_signals():
    unmapped = unmapped_signal_keys({"BcuSocDisp": 1, "DrvrDoorSts": 2, "SomethingNew": 3}, sda=True)
    assert unmapped == ["SomethingNew"]
