# Moving from danperks/ha-deepal

This page lists how entities differ between [danperks/ha-deepal](https://github.com/danperks/ha-deepal) and this fork, so you can fix dashboards, automations and scripts after switching. For the install steps see [Coming from danperks/ha-deepal?](../README.md#coming-from-danperksha-deepal) in the README.

## How this was compared

The lists were built by comparing the entity keys in the code and the English entity names in each repository's `strings.json` (danperks, `main` at 8 Oct 2026) and `translations/en.json` (this fork, `main` at 21 Nov 2026). This fork was rebased in August 2026 on [DylanTusler's fork](https://github.com/DylanTusler/ha-deepal), which was danperks' code plus Australia support. danperks has changed since then (it added Australia itself on 8 Oct 2026), so a difference below could come from this fork or from danperks changing after the rebase. The tables list names and keys only. I have not tested what Home Assistant does with the registry entries when you switch.

## Why the names changed

- **Australian/UK wording:** Boot, Odometer, Tyre.
- **Keys that match the Deepal API fields**, for example `connectStatus` is `connect_status` and `drvMileage` is `drv_mileage`.
- **Front/Rear before Left/Right** for doors, windows, tyres and seats.
- **Shorter names:** words like "on" and "open" were dropped where the entity type already says it, and every name is in Title Case.

## What this means for entity IDs

Entity IDs are normally made from the device name plus the entity name, and the entity's key is used to identify it in the registry. So:

- **Different key (32 entities, first two tables):** Home Assistant sees a new entity. Updating in place leaves the old one behind as unavailable. Deleting the integration first and setting it up again gives the new names, so IDs may change.
- **Same key, different wording (13 entities, third table):** the ID is likely to change because the name changed.
- **Same key, only capitalisation (18 entities):** the ID should be the same.

Check the actual IDs on your own system. These are expectations from how Home Assistant names entities, not something I have confirmed on a live install.

## Binary sensors with a new key
| danperks key | danperks name | fork key | fork name |
|---|---|---|---|
| `charge_cable_connected` | Charge cable connected | `charge_con_status` | Charging Cable |
| `charging` | Charging | `charge_status` | Charging |
| `connected` | Vehicle connected | `connect_status` | Vehicle Connected |
| `dc_charge_gun_connected` | DC charge gun connected | `dc_charge_gun_connect_status` | DC Charge Gun |
| `defrost_on` | Defrost on | `defrost_status` | Defrost Status |
| `driver_door_locked` | Driver door locked | `driver_lock` | Driver Door Locked |
| `engine_on` | Engine on | `engine_sts` | Engine On |
| `high_beam_on` | High beam on | `high_beam` | High Beam |
| `left_turn_signal_on` | Left turn signal on | `left_turn` | Left Turn Signal |
| `low_beam_on` | Low beam on | `low_beam` | Low Beam |
| `passenger_door_locked` | Passenger door locked | `passenger_lock` | Passenger Door Locked |
| `position_lamp_on` | Position lamp on | `position_lamp` | Position Lamp |
| `right_turn_signal_on` | Right turn signal on | `right_turn` | Right Turn Signal |
| `trunk_open` | Trunk open | `trunk` | Boot |

Note: **Charging** appears with the same name on both sides, but its key changed from `charging` to `charge_status`, so it is still a new entity.

## Sensors with a new key
| danperks key | danperks name | fork key | fork name |
|---|---|---|---|
| `cabin_climate_mode` | Cabin climate mode | `ac_status` | Cabin Climate Mode |
| `cabin_humidity` | Cabin humidity | `inside_humidity` | Cabin Humidity |
| `charge_limit` | Charge limit | `max_soc_percent` | Max Charge Limit |
| `charge_schedule_end_time` | Charge schedule end time | `charge_plan_end_time` | Charge Schedule End Time |
| `charge_schedule_start_time` | Charge schedule start time | `charge_plan_start_time` | Charge Schedule Start Time |
| `epb_status` | Electronic parking brake status | `epb_sts` | Electronic Parking Brake Status |
| `inside_temperature` | Inside temperature | `inside_temp` | Inside Temperature |
| `last_updated` | Vehicle data timestamp | `last_updated_at` | Vehicle Data Timestamp |
| `left_rear_seat_heater_level` | Left rear seat heater level | `rear_left_seat_heater_level` | Rear Left Seat Heater Level |
| `outside_temperature` | Outside temperature | `outside_temp` | Outside Temperature |
| `range` | Estimated range | `drv_mileage` | Estimated Range |
| `remaining_charge_time` | Remaining charge time | `remain_charge_time` | Remaining Charge Time |
| `right_rear_seat_heater_level` | Right rear seat heater level | `rear_right_seat_heater_level` | Rear Right Seat Heater Level |
| `tire_left_front_pressure` | Left front tire pressure | `tire_front_left_pressure` | Front Left Tyre Pressure |
| `tire_left_rear_pressure` | Left rear tire pressure | `tire_rear_left_pressure` | Rear Left Tyre Pressure |
| `tire_right_front_pressure` | Right front tire pressure | `tire_front_right_pressure` | Front Right Tyre Pressure |
| `tire_right_rear_pressure` | Right rear tire pressure | `tire_rear_right_pressure` | Rear Right Tyre Pressure |
| `vehicle_image_url` | (none) | `img_url` | Vehicle Image URL |

## Same key, different wording
| platform | key | danperks name | fork name |
|---|---|---|---|
| binary sensor | `any_door_open` | Any door open | Any Door |
| binary sensor | `front_left_door_open` | Front left door open | Front Left Door |
| binary sensor | `front_right_door_open` | Front right door open | Front Right Door |
| binary sensor | `rear_left_door_open` | Rear left door open | Rear Left Door |
| binary sensor | `rear_right_door_open` | Rear right door open | Rear Right Door |
| binary sensor | `front_left_window_open` | Front left window open | Front Left Window |
| binary sensor | `front_right_window_open` | Front right window open | Front Right Window |
| binary sensor | `rear_left_window_open` | Rear left window open | Rear Left Window |
| binary sensor | `rear_right_window_open` | Rear right window open | Rear Right Window |
| sensor | `soc` | Battery | State of Charge |
| sensor | `total_mileage` | Total mileage | Odometer |
| sensor | `ac_charge_current` | AC input current | AC Charge Current |
| sensor | `dc_charge_current` | Battery current | DC Charge Current |

## Windows and boot controls

danperks has `cover` entities named Windows and Boot. This fork replaced them in 0.4.0 with buttons: Lower Windows, Raise Windows, Open Boot and Close Boot. A cover's up arrow means "open", which for windows is the wrong way round. Automations that call cover services on these need updating.

## Entities only in this fork

- OTA Status (`ota_status`)
- Remaining Charge Time (H:MM) (`remain_charge_time_hhmm`)
- Any Window (`any_window_open`)

## Entities unchanged apart from capitalisation

Buttons, numbers, switches, time entities and the climate entity keep their keys. Names went from sentence case to Title Case (for example "Refresh vehicle data" to "Refresh Vehicle Data"), which does not change the ID.
