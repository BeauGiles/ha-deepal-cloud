"""S05 charging: ChrgSts is a 0-4 enum, not the S07's codes (6 = charging)."""

from __future__ import annotations

import pytest

from custom_components.deepal.api import (
    _charge_state,
    _humidity_percent,
    _mqtt_charge_currents,
    _mqtt_charge_status,
    _mqtt_condition_from_params as mqtt,
    _mqtt_gun_flags,
)


class TestChargeState:
    @pytest.mark.parametrize("value", [0, 1, 2, 3, 4, 5, "3", 3.0])
    def test_known_states(self, value):
        assert _charge_state(value) == int(float(value))

    @pytest.mark.parametrize("value", [6, 7, -1, None, "x", ""])
    def test_anything_else_is_unknown(self, value):
        # An unrecognised value must not be translated into a state.
        assert _charge_state(value) is None

    @pytest.mark.parametrize(
        ("state", "expected"),
        [(0, 1), (1, 1), (2, 1), (3, 6), (4, 6), (5, 1), (None, None)],
    )
    def test_shared_status_codes(self, state, expected):
        # 6 = charging, 1 = not charging (what the entities understand).
        assert _mqtt_charge_status(state) == expected


class TestGunFlags:
    @pytest.mark.parametrize(
        ("state", "ac", "dc"),
        [(1, True, False), (2, False, True), (3, True, False), (4, False, True)],
    )
    def test_charging_states_identify_the_gun(self, state, ac, dc):
        # Authoritative even when the raw fields disagree.
        assert _mqtt_gun_flags(state, 0, 0) == (ac, dc)

    @pytest.mark.parametrize("state", [0, 5])
    def test_idle_states_defer_to_the_raw_fields(self, state):
        # Not charging / charge stopped do not say which gun: a connected cable
        # keeps its raw field set (1 on a live S05), so it must not read unplugged.
        assert _mqtt_gun_flags(state, 1, 0) == (True, False)
        assert _mqtt_gun_flags(state, 0, 3) == (False, True)
        assert _mqtt_gun_flags(state, 0, 0) == (False, False)
        assert _mqtt_gun_flags(state, None, None) == (None, None)

    def test_raw_fields_are_used_when_the_state_is_unknown(self):
        assert _mqtt_gun_flags(None, 3, 0) == (True, False)
        assert _mqtt_gun_flags(None, 1, 1) == (True, True)  # only 0 means not connected
        assert _mqtt_gun_flags(None, 0, 0) == (False, False)
        assert _mqtt_gun_flags(None, None, None) == (None, None)


class TestCurrents:
    def test_dc_charging_uses_the_dc_field_even_when_ac_reads_zero(self):
        # The old mapping picked AC first, so a present AC 0 hid the real DC current.
        assert _mqtt_charge_currents(0, 60, 4) == (0.0, 60.0, 60.0)

    def test_ac_charging_uses_the_ac_field(self):
        assert _mqtt_charge_currents(16, 0, 3) == (16.0, 0.0, 16.0)

    @pytest.mark.parametrize("state", [0, 1, 2, 5])
    def test_plugged_or_unplugged_without_charging_is_zero(self, state):
        assert _mqtt_charge_currents(5, 30, state) == (0.0, 0.0, 0.0)

    def test_parked_dc_glitch_is_dropped(self):
        # After a DC session the car kept 2538 A in BattDCChrgInCurr while parked.
        ac, dc, active = _mqtt_charge_currents(0, 2538, 0)
        assert (ac, dc, active) == (0.0, 0.0, 0.0)

    def test_glitch_while_charging_is_unknown_not_a_number(self):
        assert _mqtt_charge_currents(0, 2538, 4) == (0.0, None, None)

    def test_boundary_values(self):
        assert _mqtt_charge_currents(None, 600, 4)[1] == 600.0
        assert _mqtt_charge_currents(None, 601, 4)[1] is None
        assert _mqtt_charge_currents(None, -601, 4)[1] is None

    def test_negative_readings_are_exposed_as_positive_magnitudes(self):
        # The car uses the battery sign convention: DC charging can read -60.5 A.
        assert _mqtt_charge_currents(0, -60.5, 4) == (0.0, 60.5, 60.5)
        assert _mqtt_charge_currents(-16, 0, 3) == (16.0, 0.0, 16.0)

    def test_the_glitch_is_dropped_with_either_sign(self):
        assert _mqtt_charge_currents(0, -2538, 4) == (0.0, None, None)

    def test_unknown_state_keeps_the_non_zero_reading(self):
        assert _mqtt_charge_currents(0, 12.5, None) == (0.0, 12.5, 12.5)
        assert _mqtt_charge_currents(8, 0, None) == (8.0, 0.0, 8.0)

    def test_nothing_reported_is_unknown(self):
        assert _mqtt_charge_currents(None, None, 3) == (None, None, None)


class TestHumidity:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(61, 61.0), (0, 0.0), (100, 100.0), (453, 45.3), (1000, 100.0), (None, None), ("x", None), (-5, None), (1500, None)],
    )
    def test_percent_or_tenths(self, value, expected):
        assert _humidity_percent(value) == expected


class TestWholeReport:
    def test_ac_charging_report(self):
        charge = mqtt({"ChrgSts": 3, "BattACChrgInCurr": 15.5, "BattDCChrgInCurr": 2538, "acChargeGunConnectionState": 1})["charge"]
        assert charge["chargeStatus"] == 6  # shows as Charging
        assert charge["chargeConStatus"] == 3  # AC cable plugged in
        assert charge["dcChargeGunConnectStatus"] == 0
        assert charge["chargeCurrent"] == 15.5
        assert charge["dcChargeCurrent"] == 0.0  # not the 2538 glitch

    def test_ac_plugged_but_not_charging(self):
        charge = mqtt({"ChrgSts": 1})["charge"]
        assert charge["chargeStatus"] == 1  # "Not Charging", not "Unknown (1)"
        assert charge["chargeConStatus"] == 3

    def test_dc_charging_report(self):
        charge = mqtt({"ChrgSts": 4, "BattACChrgInCurr": 0, "BattDCChrgInCurr": 120.0})["charge"]
        assert charge["chargeStatus"] == 6
        assert charge["chargeConStatus"] == 0  # the AC cable is not the one in use
        assert charge["dcChargeGunConnectStatus"] == 3
        assert charge["chargeCurrent"] == 120.0

    def test_unplugged_after_a_dc_session(self):
        charge = mqtt({"ChrgSts": 0, "BattACChrgInCurr": 0, "BattDCChrgInCurr": 2538, "acChargeGunConnectionState": 0, "dcDhargeGunConnectionState": 0})["charge"]
        assert charge["chargeStatus"] == 1
        assert charge["chargeConStatus"] == 0
        assert charge["dcChargeGunConnectStatus"] == 0
        assert charge["dcChargeCurrent"] == 0.0  # the 2538 glitch is dropped
        assert charge["chargeCurrent"] == 0.0

    def test_cable_connected_but_not_charging(self):
        # Wallbox disabled with the cable still plugged in: ChrgSts 0 and 5 both
        # keep acChargeGunConnectionState=1 on a live S05.
        for state in (0, 5):
            charge = mqtt({"ChrgSts": state, "BattACChrgInCurr": 0, "acChargeGunConnectionState": 1})["charge"]
            assert charge["chargeStatus"] == 1
            assert charge["chargeConStatus"] == 3
            assert charge["chargeCurrent"] == 0.0

    def test_charge_stopped_has_no_current(self):
        charge = mqtt({"ChrgSts": 5, "BattACChrgInCurr": 0, "BattDCChrgInCurr": 0})["charge"]
        assert charge["chargeStatus"] == 1  # shows as Not Charging, not unknown

    def test_dc_charging_with_a_negative_current(self):
        charge = mqtt({"ChrgSts": 4, "BattACChrgInCurr": 0, "BattDCChrgInCurr": -60.5})["charge"]
        assert charge["dcChargeCurrent"] == 60.5
        assert charge["chargeCurrent"] == 60.5

    def test_humidity_in_a_report(self):
        assert mqtt({"innerHumidity": 453})["hvac"]["insideHumidity"] == 45.3


class TestOutsideTemperature:
    def test_reported_in_celsius_and_stored_as_tenths(self):
        assert mqtt({"outsideTemperature": 21.5})["hvac"]["outsideTemp"] == 215.0

    def test_alternative_key(self):
        assert mqtt({"externalTemperature": 18})["hvac"]["outsideTemp"] == 180.0

    def test_not_reported_is_unknown(self):
        assert mqtt({})["hvac"]["outsideTemp"] is None
