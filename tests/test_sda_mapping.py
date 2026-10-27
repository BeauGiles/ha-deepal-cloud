"""E07 (SDA) signal mapping into the shared condition."""

from __future__ import annotations

import pytest

from custom_components.deepal.api import _sda_charge_status
from custom_components.deepal.api import _sda_condition_from_params as sda


def test_basic_signals_and_conventions():
    condition = sda(
        {
            "BcuSocDisp": "78.4",
            "VcuResiMilg": 310,
            "CdcTotMilg": "12034.5",
            "DrvrDoorSts": 2,
            "PassDoorSts": 1,
            "DrvrDoorLockLogicSts": 2,
            "PassDoorLockLogicSts": 1,
            "ITMSAcIntT": 22.5,
            "DrvrWinPos": 0,
        },
        "RHD",
    )
    assert condition["vehicleStatus"]["soc"] == 78
    assert condition["vehicleStatus"]["totalMileage"] == 12034.5
    # status 2 = closed (0); anything else = open (1). RHD: passenger is front-left.
    assert condition["door"]["doors"][:2] == [1, 0]
    # lock value 2 = locked (0 in the shared convention); 1 = unlocked.
    assert condition["door"]["driverLock"] == 0
    assert condition["door"]["passengerLock"] == 1
    assert condition["hvac"]["insideTemp"] == 225.0  # tenths of a degree


def test_viu_soc_preferred_over_bcu():
    assert sda({"VIUSocDisp": 61, "BcuSocDisp": 50.2})["vehicleStatus"]["soc"] == 61


def test_charge_time_sentinel_is_unknown():
    assert sda({"BcuChrgTiDisp": 8191})["charge"]["remainChargeTime"] is None
    assert sda({"BcuChrgTiDisp": 218})["charge"]["remainChargeTime"] == 218


@pytest.mark.parametrize(
    ("side", "doors", "windows", "seats"),
    [
        # (driver door, passenger door) land in (front-left, front-right)
        ("RHD", [0, 1], [0, 40], ("rightFront", "leftFront")),
        ("LHD", [1, 0], [40, 0], ("leftFront", "rightFront")),
        (None, [1, 0], [40, 0], ("leftFront", "rightFront")),
    ],
)
def test_drive_side_placement(side, doors, windows, seats):
    condition = sda(
        {
            "DrvrDoorSts": 1,
            "PassDoorSts": 2,
            "DrvrWinPos": 40,
            "PassWinPos": 0,
            "DrHeatGear": 2,
            "PsgHeatGear": 1,
        },
        side,
    )
    assert condition["door"]["doors"][:2] == doors
    assert condition["window"]["windows"][:2] == windows
    driver_seat, passenger_seat = seats
    assert condition["seat"][driver_seat]["heatStatus"] == 2
    assert condition["seat"][passenger_seat]["heatStatus"] == 1


class TestChargeStatus:
    """The E07's BcuChrgSts enum differs from the S07's (1 = not charging, 6 = charging)."""

    def test_reported_charging_session(self):
        # Live AU E07 charging at 7 kW: raw status 1, AC 29.5 A, battery -10 A.
        assert _sda_charge_status(1, 29.5, 10.2, -10.0) == 6

    def test_idle_is_not_charging(self):
        assert _sda_charge_status(0, 0.0, 0.0, 0.0) == 1

    def test_plugged_but_no_current_is_complete(self):
        assert _sda_charge_status(1, 0.0, 0.0, 0.2) == 0

    def test_no_current_signals_falls_back_to_status(self):
        assert _sda_charge_status(1, None, None, None) == 6

    def test_missing_status_is_unknown(self):
        assert _sda_charge_status(None, 29.5, None, None) is None

    def test_condition_while_charging(self):
        condition = sda(
            {
                "BcuChrgSts": 1,
                "ObcChrgInpAcIL1": 29.5,
                "ObcChrgDcI": 10.2,
                "BcuBattI": -10.0,
                "BcuChrgTiDisp": 218,
                "AcChrgCnctrSts": 0,
            }
        )
        charge = condition["charge"]
        assert charge["chargeStatus"] == 6
        assert charge["chargeConStatus"] == 3  # entities treat 3 as "plugged in"
        assert charge["chargeCurrent"] == 10.0  # positive while charging
        assert charge["remainChargeTime"] == 218

    def test_condition_idle_and_unplugged(self):
        charge = sda({"BcuChrgSts": 0, "BcuBattI": 0, "AcChrgCnctrSts": 0})["charge"]
        assert charge["chargeStatus"] == 1
        assert charge["chargeConStatus"] == 0
        assert charge["chargeCurrent"] == 0.0

    def test_discharging_reports_no_charge_current(self):
        assert sda({"BcuChrgSts": 0, "BcuBattI": 80.0})["charge"]["chargeCurrent"] == 0.0
