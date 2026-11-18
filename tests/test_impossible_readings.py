"""One impossible reading must become "unknown", never abort the refresh."""

from __future__ import annotations

import pytest

from custom_components.deepal.api import (
    _as_float,
    _as_int,
    _humidity_percent,
    _mqtt_condition_from_params,
    _percent_or_none,
)
from custom_components.deepal.api import _sda_condition_from_params as sda


class TestNumbers:
    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "nan", "NaN", "Infinity", "-inf"])
    def test_non_finite_floats_are_unknown(self, value):
        assert _as_float(value) is None

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "nan", "Infinity", "-Infinity"])
    def test_non_finite_ints_are_unknown_and_do_not_raise(self, value):
        assert _as_int(value) is None

    @pytest.mark.parametrize(("value", "as_float", "as_int"), [(5, 5.0, 5), ("0", 0.0, 0), ("12.7", 12.7, 12), (-3.9, -3.9, -3)])
    def test_ordinary_values_are_unchanged(self, value, as_float, as_int):
        assert _as_float(value) == as_float
        assert _as_int(value) == as_int

    @pytest.mark.parametrize("value", [None, "", "x", [], {}])
    def test_rubbish_is_unknown(self, value):
        assert _as_float(value) is None
        assert _as_int(value) is None


class TestPercent:
    @pytest.mark.parametrize(("value", "expected"), [(0, 0), (55, 55), (100, 100), (101, None), (255, None), (-1, None), (None, None)])
    def test_range(self, value, expected):
        assert _percent_or_none(value) == expected


class TestSoc:
    def test_sda_invalid_marker_falls_back_to_the_other_signal(self):
        assert sda({"VIUSocDisp": 255, "BcuSocDisp": 61.4})["vehicleStatus"]["soc"] == 61

    def test_sda_both_invalid_is_unknown(self):
        assert sda({"VIUSocDisp": 255, "BcuSocDisp": 255})["vehicleStatus"]["soc"] is None

    def test_sda_valid_value_is_unchanged(self):
        assert sda({"VIUSocDisp": 61, "BcuSocDisp": 50.2})["vehicleStatus"]["soc"] == 61

    def test_sda_charge_target_marker_is_unknown(self):
        assert sda({"TboxSocChrgTarSet": 255})["charge"]["maxSocPercent"] is None
        assert sda({"TboxSocChrgTarSet": 80})["charge"]["maxSocPercent"] == 80

    def test_mqtt_soc_marker_is_unknown(self):
        assert _mqtt_condition_from_params({"soc": 255}, None)["vehicleStatus"]["soc"] is None
        assert _mqtt_condition_from_params({"soc": 72}, None)["vehicleStatus"]["soc"] == 72

    def test_infinite_values_do_not_abort_a_whole_report(self):
        condition = sda({"VIUSocDisp": float("inf"), "BcuSocDisp": "nan", "CdcTotMilg": float("inf"), "VcuResiMilg": 300})
        assert condition["vehicleStatus"]["soc"] is None
        assert condition["vehicleStatus"]["totalMileage"] is None
        assert condition["vehicleStatus"]["drvMileage"] == 300


class TestHumidityPlaceholder:
    def test_zero_is_no_reading(self):
        assert _humidity_percent(0) is None
        assert _humidity_percent("0") is None

    def test_real_values_still_work(self):
        assert _humidity_percent(45) == 45.0
        assert _humidity_percent(453) == 45.3
        assert _humidity_percent(1) == 1.0
