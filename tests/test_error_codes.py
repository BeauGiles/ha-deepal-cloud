"""The app-derived result code table and its use as a last-resort fallback."""

from __future__ import annotations

import re

import pytest

from custom_components.deepal.api import _mqtt_command_result_error
from custom_components.deepal.error_codes import (
    CLOUD_ERROR_MESSAGES,
    RKE_RESULT_MESSAGES,
    describe_vehicle_code,
)

SUCCESS_OR_PROGRESS = ("2000", "2001", "2002", "3005", "300f", "3010", "3013")


class TestTables:
    def test_rke_keys_are_lowercase_four_hex_digits(self):
        assert RKE_RESULT_MESSAGES
        assert all(re.fullmatch(r"[0-9a-f]{4}", key) for key in RKE_RESULT_MESSAGES)

    def test_cloud_keys_are_zero_padded_three_digits(self):
        assert CLOUD_ERROR_MESSAGES
        assert all(re.fullmatch(r"\d{3}", key) for key in CLOUD_ERROR_MESSAGES)

    def test_no_empty_or_generic_text(self):
        for table in (RKE_RESULT_MESSAGES, CLOUD_ERROR_MESSAGES):
            for text in table.values():
                assert text.strip()
                assert text.strip().rstrip(".") != "Operation failed"

    def test_success_codes_are_not_described_as_failures(self):
        for code in SUCCESS_OR_PROGRESS:
            assert code not in RKE_RESULT_MESSAGES
        assert "084" not in CLOUD_ERROR_MESSAGES

    def test_account_and_login_errors_are_left_out(self):
        # error_msg_022..038 in the app are registration/login messages.
        for number in range(22, 39):
            assert f"{number:03d}" not in CLOUD_ERROR_MESSAGES


class TestDescribe:
    @pytest.mark.parametrize(
        ("code", "fragment"),
        [
            ("3006", "Previous Command"),
            (3006, "Previous Command"),
            ("401E", "trailer mode"),
            ("401e", "trailer mode"),
            ("039", "Controller is not responding"),
            ("045", "start the vehicle manually"),
        ],
    )
    def test_known_codes(self, code, fragment):
        assert fragment in describe_vehicle_code(code)

    @pytest.mark.parametrize("code", [None, "", " ", "0", 39, "39", "VVCC_-1_-1_02_023", "9999", "ffff"])
    def test_unknown_or_ambiguous_codes(self, code):
        assert describe_vehicle_code(code) is None


class TestFallbackInCommandResult:
    @staticmethod
    def error(item):
        return _mqtt_command_result_error({"rs": [item]}, "secret", "req")

    def test_code_without_message_is_explained(self):
        result = self.error({"resultCode": "3006"})
        assert "Previous Command" in result
        assert "(3006)" in result

    def test_vehicle_own_message_is_never_replaced(self):
        assert self.error({"resultCode": "3006", "msg": "custom text"}) == "custom text"

    def test_existing_vehicle_code_still_wins(self):
        assert "door status" in self.error({"code": "VVCC_-1_-1_02_023"})

    def test_unknown_code_keeps_old_wording(self):
        assert self.error({"resultCode": "9999"}) == "result code 9999"

    def test_success_codes_still_succeed(self):
        for code in ("0", "000000", 200, "OK"):
            assert self.error({"code": code}) is None
