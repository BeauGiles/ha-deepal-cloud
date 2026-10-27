"""S05 (MQTT) parameter mapping into the shared condition."""

from __future__ import annotations

import pytest

from custom_components.deepal.api import _iso_to_millis
from custom_components.deepal.api import _mqtt_condition_from_params as mqtt


@pytest.mark.parametrize(
    ("side", "doors", "windows", "driver_seat"),
    [
        ("RHD", [0, 1], [0, 50], "rightFront"),
        ("LHD", [1, 0], [50, 0], "leftFront"),
        # Unknown side keeps the arrangement used before drive-side support.
        (None, [1, 0], [50, 0], "rightFront"),
    ],
)
def test_drive_side_placement(side, doors, windows, driver_seat):
    condition = mqtt(
        {
            "driverDoor": 1,
            "passengerDoor": 0,
            "diverWindow": 50,
            "passengerWindow": 0,
            "driverSeatHeatStatus": 3,
        },
        side,
    )
    assert condition["door"]["doors"][:2] == doors
    assert condition["window"]["windows"][:2] == windows
    assert condition["seat"][driver_seat]["heatStatus"] == 3


class TestAliases:
    def test_misspelled_dc_gun_key_is_read(self):
        # The real payload spells it "dcDharge...".
        assert mqtt({"dcDhargeGunConnectionState": 3})["charge"]["dcChargeGunConnectStatus"] == 3

    def test_correctly_spelled_dc_gun_key_still_read(self):
        assert mqtt({"dcChargeGunConnectionState": 3})["charge"]["dcChargeGunConnectStatus"] == 3

    def test_misspelled_key_wins_when_both_present(self):
        params = {"dcDhargeGunConnectionState": 3, "dcChargeGunConnectionState": 0}
        assert mqtt(params)["charge"]["dcChargeGunConnectStatus"] == 3

    @pytest.mark.parametrize("key", ["hood", "hoodStatus"])
    def test_hood_keys(self, key):
        assert mqtt({key: 1})["door"]["hood"] == 1


class TestReportTimestamp:
    def test_last_updated_time_is_preferred(self):
        params = {"lastUpdatedTime": 1_700_000_000_000, "latestDate": "2020-01-01T00:00:00Z"}
        assert mqtt(params)["lastUpdatedAt"] == 1_700_000_000_000

    def test_falls_back_to_now_without_a_timestamp(self):
        assert mqtt({})["lastUpdatedAt"] > 1_700_000_000_000

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2026-10-13T04:02:00Z", 1_791_864_120_000),
            (1_791_864_120_000, 1_791_864_120_000),  # epoch ms
            (1_791_864_120, 1_791_864_120_000),  # epoch s
            ("1791864120", 1_791_864_120_000),
            (None, None),
            ("", None),
            ("not a date", None),
            (True, None),
        ],
    )
    def test_iso_to_millis(self, value, expected):
        assert _iso_to_millis(value) == expected


def test_charge_time_sentinel_is_unknown():
    assert mqtt({"chargDeltMins": 8191})["charge"]["remainChargeTime"] is None
    assert mqtt({"chargDeltMins": 95})["charge"]["remainChargeTime"] == 95
