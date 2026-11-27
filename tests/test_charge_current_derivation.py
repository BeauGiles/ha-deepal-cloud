"""Reported charging current falls back to the AC/DC breakdown.

Some cars never send the plain chargeCurrent field at all - confirmed absent
from a real S07's diagnostics download, while acChargeCurrent and
dcChargeCurrent were both present (0.0 and 0.6 A respectively). The inactive
mode's field is 0 while not in use, so the larger of the two is the one
actually charging.
"""

from __future__ import annotations

from custom_components.deepal.sensor import SENSORS, DeepalSensor, _derived_charge_current, _sensor_supported


def _description():
    return next(d for d in SENSORS if d.key == "charge_current")


def _entity(condition):
    entity = DeepalSensor.__new__(DeepalSensor)
    entity.entity_description = _description()
    entity.coordinator = type("C", (), {"data": {"condition": condition}})()
    return entity


class TestDerivedChargeCurrent:
    def test_uses_the_plain_field_when_present(self):
        condition = {"charge": {"chargeCurrent": 7.0, "acChargeCurrent": 0.0, "dcChargeCurrent": 0.0}}
        assert _entity(condition).native_value == 7.0

    def test_falls_back_to_dc_when_only_dc_is_active(self):
        condition = {"charge": {"acChargeCurrent": 0.0, "dcChargeCurrent": 0.6}}
        assert _entity(condition).native_value == 0.6

    def test_falls_back_to_ac_when_only_ac_is_active(self):
        condition = {"charge": {"acChargeCurrent": 6.0, "dcChargeCurrent": 0.0}}
        assert _entity(condition).native_value == 6.0

    def test_none_when_neither_ac_nor_dc_is_present(self):
        assert _derived_charge_current({"charge": {}}) is None
        assert _entity({"charge": {}}).native_value is None

    def test_both_zero_still_reports_zero_not_none(self):
        condition = {"charge": {"acChargeCurrent": 0.0, "dcChargeCurrent": 0.0}}
        assert _entity(condition).native_value == 0.0


class TestChargeCurrentSupported:
    def test_hidden_without_chargecurrent_or_ac_dc(self):
        supported = _sensor_supported(_description())
        assert not supported({"condition": {"charge": {}}})

    def test_visible_with_only_ac_dc_breakdown(self):
        supported = _sensor_supported(_description())
        assert supported({"condition": {"charge": {"acChargeCurrent": 0.0, "dcChargeCurrent": 0.6}}})

    def test_visible_with_the_plain_field(self):
        supported = _sensor_supported(_description())
        assert supported({"condition": {"charge": {"chargeCurrent": 1.0}}})
