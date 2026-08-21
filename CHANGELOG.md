# Changelog

All notable changes to this fork are documented here. Dates are in `YYYY-MM-DD`.

## [0.3.0] - 2026-08-21

Rebased on [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (via
[DylanTusler's fork](https://github.com/DylanTusler/ha-deepal)) in place of the
earlier standalone version of this integration, to pick up account-based login
(no more manually capturing tokens with a proxy tool), full remote vehicle
control (locks, windows, boot, climate, charge limit/schedule, lights, horn),
and Deepal S05 support alongside the existing S07 telemetry. Credit to
danperks and DylanTusler for that base. Everything below was added, changed,
or fixed on top of it.

### Added

- Vehicle image entity (`image.py`) showing the car's photo — the upstream fork
  only exposed the image URL as a diagnostic sensor string, with no picture
  rendered.
- VIN reported as the device's serial number in Home Assistant.
- OTA firmware update status sensor, with `stage`/`process`/`state`/`task_id`
  attributes and human-readable states ("Up to date", "Downloading N%",
  "Installing N%").
- Icons added throughout: `mdi:car-parking-lights` (Flash Lights),
  `mdi:bullhorn` (Honk Horn), `mdi:car-back` (Boot), `mdi:air-conditioner`
  (Cabin Climate Mode), `mdi:air-filter` (Cabin PM2.5), plus every icon carried
  over from the original repo (door locks, individual doors, windows, AC/DC
  charge guns).
- Enum mappings for "Power Status" (`Idle`/`Drive`) and "Charge Status"
  (`Charge Complete`/`Not Charging`/`Charging`) — previously shown as raw
  numbers.

### Changed

- Entity keys renamed to mirror the real Deepal API fields (verified against a
  live captured condition payload), while display names stay in plain English
  — e.g. the boot sensor's key is `trunk` (matching `door.trunk`) but displays
  as "Boot"; `total_mileage` displays as "Odometer".
- Renamed entities to AU/UK terminology throughout: Odometer (was "Total
  Mileage"), Tyre (was "Tire"), Boot (was "Trunk"), Charging Cable (was
  "Charge Cable Connected").
- Consistent Title Case applied to every entity name.
- Every spatial entity (doors, windows, tyre pressures, seat heaters) now
  consistently orders **Front/Rear, then Left/Right** — in both keys and
  display names (e.g. "Front Left Door", `tire_front_left_pressure`).
- Dropped redundant words that just repeated the entity's own state, e.g.
  "Boot Open" → "Boot", "High Beam On" → "High Beam", "Defrost On" → "Defrost
  Status".
- Light-status sensors (high beam, low beam, position lamp, turn signals) and
  AC/DC charge current sensors moved into the Diagnostic category.
- "Vehicle Image URL" and "Raw Condition Data" (diagnostic entities) now
  disabled by default.

### Fixed

- Charge-gun connection status (both the AC "Charging Cable" and DC gun) was
  checking the wrong threshold and reporting connected/disconnected
  incorrectly.
- The "Charging" binary sensor was inverted — "Not Charging" was being
  reported as actively charging.
- The "Charge Schedule Enabled" binary sensor disagreed with the actual
  schedule switch's own on/off logic (it used an OR of two fields where the
  real switch requires both).
- The four seat heater level sensors were reading a field (`level`) that
  doesn't exist anywhere in the real API payload and always returned
  `Unknown`. Fixed to read the correct field (`heatStatus`).
- `strings.json` and `translations/en.json` were out of sync with each other
  and with the actual entity keys in code (missing entries, no `entity`
  section in `en.json` at all) — a pre-existing gap in the upstream fork, not
  introduced here. Both files are now fully consistent with the code and with
  each other.

### Known limitations / deferred

- Setting a maximum AC/DC charge current (amps) isn't implemented. The app
  supports it, so the cloud API almost certainly does too, but it hasn't been
  reverse-engineered yet — would need a fresh capture of that specific action.
- The OTA sensor doesn't expose an explicit firmware version number, only
  install state/progress — the API response hasn't been observed to include
  one.
- "Vehicle Status" (`vehicleStatus.status`) still shows a raw numeric value —
  no mapping exists to decode it yet.

### Upgrade notes

- **Entity IDs will change.** Because entity keys were renamed throughout,
  upgrading from a previous version of this integration (or migrating from
  the upstream fork) will create new entities rather than renaming existing
  ones in place. You'll need to update any dashboards or automations that
  reference the old entity IDs, and remove the old (orphaned) entities from
  the entity registry.
- `unique_id` format is `{vehicle_id}_{key}` (no `deepal_` prefix).
- The DC Charge Gun and Defrost sensors are `binary_sensor` entities (not
  plain `sensor`, as in the pre-fork version of this integration) — this is
  intentional, both are genuinely boolean concepts and both have corrected
  logic as of this release.
- The old "Remote Temp Setting" sensor doesn't exist as a standalone entity
  anymore — the target cabin temperature now lives as part of the interactive
  Cabin Climate entity, since it can actually be controlled.
