# Changelog

All notable changes to this fork are documented here. Dates are in `YYYY-MM-DD`.

## [Unreleased]

### Added

- **Opt-in remote controls for MQTT-backed vehicles** (door lock/unlock,
  windows, boot). Vehicles whose `protocolType` is `MQTT` (the Deepal S05, and
  potentially other models such as the E07) were previously read-only. They
  can now be given a control PIN and have remote commands enabled, like the
  S07. Commands wake the vehicle, are published exactly once (never
  auto-retried), wait for the correlated broker response, and are followed by
  a fresh telemetry read.
  - The MQTT command protocol, request envelope, response/error decoding and
    the lock/window/boot command mappings are ported from
    [kobizz/ha-deepal](https://github.com/kobizz/ha-deepal) (commits
    `9de00eb`, `a6ea281`, `f87fa64`, `f82c608`, `b5e6608`). **Credit and thanks
    to kobizz** for reverse engineering and validating this against an
    Israel-market S05.
  - The command mappings (service codes and enum values) have only been
    validated on an S05. Other MQTT models may use different ones; treat
    controls on them as untested.
  - Climate, charging, lights and horn remain unavailable on MQTT vehicles.
- With "Enable redacted API logging" on, MQTT telemetry now logs each decoded
  message (redacted) and which service codes were accepted or ignored, to help
  support new MQTT models.

### Fixed (since beta11, unreleased)

- S05 (MQTT): the DC gun state is read from the payload's misspelled
  `dcDhargeGunConnectionState` key as well as the correct spelling, so the DC
  Charge Gun entity is no longer always unknown; `hood` is accepted as well as
  `hoodStatus`; the report timestamp now also looks at `lastUpdatedTime` and
  accepts epoch seconds/milliseconds as well as ISO strings (a missing timestamp
  fell back to "now", which would also stop the S05 wake from ever triggering).
  Keys from Sunek0/ha-deepal-alternative's S05 mapper (MIT). Untested on a live
  S05.

### Added (since beta11, unreleased)

- A unit-test suite (`tests/`, run with `pytest`, no Home Assistant needed) for
  the S05/E07 mappings, drive-side placement, E07 charging translation,
  sensor gating, redaction, command results and manifest checks, plus a CI
  workflow to run it.

### Fixed (beta11)

- **E07 charging state** (reported by @timalpipo on a live AU E07 charging at
  7 kW): Charge Status showed "Not Charging", Charging and Charging Cable were
  off. The E07's `BcuChrgSts` uses a different enum from the S07's, so it is now
  translated into the shared codes, using the reported currents to confirm a
  session; the cable counts as connected while charging. "Reported Charge
  Current" is now positive while charging (the battery current is negative into
  the pack). The enum is inferred from one car's report; diagnostics from a
  charging E07 would confirm it.
- Removed the unused `bluetooth` matcher and `bluetooth_adapters` dependency
  from the manifest (merged in from main, where it had no use).

### Added (beta10, from danperks/ha-deepal)

- **Seat and steering-wheel controls for REST vehicles (S07):** Driver and
  Front Passenger Seat Heating / Ventilation levels (0-3 sliders) and a
  Steering Wheel Heating switch. Request shapes from
  [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (commit
  `00a3902`); the seat entities read the drive-side-aware `seat.driver` /
  `seat.passenger` data. Not created for MQTT/SDA vehicles. Untested on a live
  car; these send real commands.
- Spain, Italy and the Netherlands login regions (default European cluster,
  also from danperks `6018bd6`; not verified by this fork).

### Fixed (beta10)

- MQTT command responses with result code `"000000"` are treated as success
  (it is the broker's success code), so an accepted command is no longer
  reported as failed.
- The MQTT telemetry read no longer loads the system trust store on the event
  loop (Home Assistant's "blocking call" warning).

### Changed (beta9)

- **Sensors and binary sensors are only created for data the vehicle reports.**
  An entity is added once its value has been seen, and added later if the data
  first appears later (for example after a car wakes from an empty first
  report). On an AU S07 this hides 12 entities that never have a value (speed,
  gear, parking brake, engine on, outside temperature, PM2.5, air quality,
  reported charge current, charge-plan start/end, rear seat heater levels).
  The same applies automatically to S05 and E07 gaps.
- Existing installs are not changed: entities already in the entity registry are
  always kept, and a seen-set is stored so an entity is not hidden again after a
  restart. Unwanted existing entities can be deleted from the entity list; they
  will not come back unless the car starts reporting them.

### Fixed (beta8)

- **Drive side (`driveSeatPosition`)**: S05 (MQTT) and E07 (SDA) report the
  front doors, windows and seats by role (driver/passenger), but the entities
  are positional. They are now placed using the vehicle's `RHD`/`LHD` setting,
  so on a right-hand-drive E07 the driver's door and window are Front Right.
  Before, the E07 front doors/windows and seats were swapped on RHD cars.
- The Driver / Front Passenger seat heater and ventilation entities now follow
  the drive side too (driver is front-right on RHD, front-left on LHD).
  **Behaviour change for LHD cars (e.g. LHD S05/S07):** driver and passenger
  seat values swap compared with earlier versions. RHD cars (including the AU
  S07) are unchanged. If the drive side is not reported, the previous
  arrangement is kept.

### Fixed (beta7)

- Diagnostics: the unmapped-signals list was always shown as `[redacted]`
  because its key name contained "key"; it is now `unmapped_signals`. Raw
  SDA/MQTT signal dumps only redact exactly-sensitive names (VIN, plate,
  location, ids), so signals whose names merely contain `key`/`pin`/`token` are
  no longer hidden. `authId` is redacted.

### Changed (beta6)

- Added the Deepal icon and logo in `custom_components/deepal/brand/`.
- The vehicle image fallback is now the Deepal logo instead of a generic car
  drawing.

### Fixed (beta5)

- Vehicle image: the API picture is now fetched in the background with a 20 s
  timeout (requests wait at most 7 s before showing the fallback), retried
  after 60 s, and a failure is logged once at warning level with the reason.
  beta4's 5 s limit made slow CDN responses fall back to the generic picture
  on an S07.
- The Remaining Charge Time (minutes) sensor now shows unknown instead of 8191
  on all vehicles; the S07's REST data uses the same "no estimate" value.

### Added (from Sunek0/ha-deepal-alternative, MIT; ideas and values credited, code written for this fork)

- **Diagnostics download** (device page → Download diagnostics): protocol
  detection, mapped telemetry, the raw SDA/MQTT signals, which signals no
  entity consumes yet (`unmapped_signal_keys`), the MQTT topic structure and
  refresh state. Tokens, VIN, licence plate and location are redacted.
- **Vehicle image fallback**: the API picture is fetched with a 5 s timeout
  (inside Home Assistant's 10 s image-proxy limit); if it is missing, slow or
  not a real image, a bundled generic vehicle picture is shown instead, and a
  failed fetch is not retried for 10 minutes.
- **Throttled MQTT wake (S05)**: pressing *Refresh Vehicle Data* on an MQTT
  vehicle whose last report is older than 2 minutes wakes it (the same
  `TxWakeup` request used before MQTT commands) and waits up to 60 s for a
  fresh report. Wakes are at most once per 5 minutes and the periodic poll
  never wakes the car, to avoid draining the 12 V battery. Needs no control
  PIN. Not used for E07/SDA (REST) vehicles.
- **Remaining Charge Time (H:MM)** sensor for dashboards. "No estimate" (8191)
  is now reported as unknown for MQTT and SDA vehicles instead of 8191.

### Fixed

- SDA (E07) requests send the same composite login token as the other
  requests (minus `Bearer `), as the official app does.
- API logging now redacts licence plate and location (`Lat`/`Lng`, `location`,
  `gps`, `address`) as well as the other identifiers.
- **Deepal E07 (`SDA-MQTT`) telemetry now reads the SDA REST condition**
  (`getCarConditionByCarId` on the regional SDA gateway) instead of the S05
  MQTT path, which that platform does not serve. The flat SDA signals are
  mapped into the standard condition (battery, range, charging, doors,
  locks, windows, climate, seats, lamps). The request shape, SDA host names
  and signal mapping come from
  [Sunek0/ha-deepal-alternative](https://github.com/Sunek0/ha-deepal-alternative)
  (MIT); thanks to Sunek0. Untested on a live AU account.
- Regions now carry their own SDA host for E07 telemetry (the ASEAN host is
  unconfirmed for AU). The CA host used by S05 MQTT is unchanged.
- Vehicles reporting `protocolType: "SDA-MQTT"` (the Deepal E07) were treated
  as HTTP vehicles and showed almost every sensor as unknown, because MQTT
  detection required an exact `MQTT` match. Any protocol type containing
  `MQTT` now uses MQTT telemetry. Remote commands stay limited to the exact
  `MQTT` type (S05); `SDA-MQTT` vehicles are telemetry-only until their
  command protocol is confirmed. Reported by @timalpipo.
- With API logging enabled, the MQTT topic structure (device IDs hidden) is
  logged, and is always logged when required topics are missing.

### Changed

- Lock, window and boot entities on MQTT vehicles are only created once
  remote commands are enabled with a control PIN, so existing S05 setups gain
  no new entities on upgrade.
- MQTT code paths are named generically (`mqtt_*` instead of `s05_*`) since
  they are selected by the vehicle's `protocolType`, not by model.
- The setup and reauth flows no longer force remote commands off for MQTT
  vehicles.

## [0.3.6] - 2026-09-10

### Fixed

- The Charge Limit slider allowed setting as low as 50% in steps of 10. On
  the S07, the vehicle itself enforces a 60% minimum, and the official app
  lets you set any 1% increment, not just multiples of 10. Corrected the
  slider to a 60-100% range with a 1% step to match.

## [0.3.5] - 2026-09-10

### Fixed

- **Every fresh setup of this integration failed outright** with
  `ModuleNotFoundError: Platform deepal.image not found`. `const.py` has
  declared `Platform.IMAGE` since the rebase onto danperks/ha-deepal, but
  the actual `custom_components/deepal/image.py` implementing it was never
  committed — it has never existed in this repo's history. Home Assistant
  hard-fails the entire config entry when any declared platform module is
  missing, so every new install (and, on some Home Assistant core versions,
  every reload of an existing one) broke immediately on setup. Reported by
  a user unable to complete setup even after removing and re-adding the
  integration.
- Added the missing `image.py`, rendering the vehicle photo Deepal already
  supplies via the `vehicle.imgUrl` field (the same field the existing
  `img_url` diagnostic sensor already uses). Works around the fact that
  Deepal's CDN doesn't reliably send an `image/*` Content-Type header — which
  Home Assistant's built-in `ImageEntity.image_url` fetch path requires — by
  fetching the bytes directly and sniffing the image format from its magic
  bytes instead.

## [0.3.4] - 2026-09-06

Fixes from a live debugging session against a real AU-market S07 account,
where every remote command (lock, charge limit, flash, honk, charge
schedule) failed outright. Root-caused by diffing live captures of the
current official app's traffic against what this integration sent for the
same calls.

### Fixed

- **The actual root cause**: `control_charge_limit`, `control_charge_schedule`,
  and `control_flashing_honking` were the only signed commands missing
  `sign_omit_keys={"command", "rcToken"}` - every other signed command already
  excludes these two fields from the signature correctly. Without that
  exclusion, the signature was computed over fields the real app's signature
  never includes for these endpoints, so the server rejected the request
  before reaching any business logic. This reproduced identically regardless
  of account, region, or how recently the login/command-signing key had been
  refreshed.
- Bumped `DEFAULT_APP_VERSION` from `V1.11.0` to `V1.12.0` and added the
  `X-Tsp-User-Token`/`X-VCS-User-Token` headers (both set to the existing
  `cacToken`) on every authenticated request - both confirmed present on the
  real app's current traffic and previously missing from this integration's
  requests entirely.
- `check_control_code` (the control-PIN exchange) now calls
  `security-code/get-status` first, matching the real app's flow, which
  always calls it immediately before submitting the code.
- A cached `rcToken` was reused indefinitely once obtained, with no way to
  notice it had gone stale (the official app itself re-prompts for the
  control PIN roughly weekly). Commands that reuse a cached token and get
  rejected now clear it, re-exchange a fresh one, and retry once before
  giving up.
- `control_doors` accepted a `command` parameter from `lock.py` (`"lock"` vs
  `"unlock"`) but silently discarded it, always hardcoding `"command":
  "lock"` regardless of which action was requested. Live captures of both a
  real lock and a real unlock confirmed the payload needs no `command` field
  at all; removed it along with the now-unused parameter.
- The options ("Configure") dialog crashed with a 500 error on newer Home
  Assistant core versions, which turned `OptionsFlow.config_entry` into a
  framework-managed property - a custom `__init__` assigning it directly
  (the long-standing recommended pattern) now raises instead of being
  redundant. Fixed by dropping the custom `__init__` entirely.

### Added

- A "Reauthenticate now" checkbox in the options flow, and a working fix
  flow for the existing (but previously non-functional, for lack of a
  `repairs.py`) "Deepal remote commands need reauthentication" repair issue.
  Both force a fresh login - and therefore a freshly generated and
  registered command-signing keypair - without needing to delete and re-add
  the integration.

## [0.3.3] - 2026-08-23

### Fixed

- The periodic "Unavailable" flicker across every entity (roughly hourly, a
  couple of seconds each time) **was not actually fixed by 0.3.2.** Root
  cause turned out to be unrelated to network requests entirely: refreshing
  the access token calls `hass.config_entries.async_update_entry(entry,
  data=new_data)` to persist the new token, which fires the integration's
  standard config-entry "update listener" - and that listener unconditionally
  called `async_reload()` on **every** entry update, not just genuine changes
  made through the options flow. Since access tokens typically expire roughly
  hourly, this meant the entire integration - every entity - was being torn
  down and recreated from scratch each time the token refreshed, which is
  exactly what a brief "Unavailable" flicker looks like.
- Fixed by only reloading when the user's actual *options* (set via the
  options flow) have changed, comparing `entry.options` before and after
  rather than reloading on any `entry.data`/`entry.options` write. Token
  refreshes only ever touch `entry.data`, so they no longer trigger a reload;
  genuine option changes (scan interval, active refresh interval, remote
  command settings, etc.) still correctly reload as before.
- The 0.3.2 retry logic (still present in `api.py`) wasn't wrong, it just
  wasn't the actual cause of this particular symptom - transient network
  retries and unwanted config-entry reloads are two different failure modes
  that happen to look similar in the entity history graph. Keeping both
  fixes, since the retry logic is still worth having for genuine transient
  network blips.

## [0.3.2] - 2026-08-22

### Fixed

- Entities periodically going "Unavailable" for a poll cycle or two (roughly
  hourly, in scattered short blips). Root cause: every API call went through a
  single request path with no retry at all — a single transient network
  hiccup (timeout, connection reset, brief cloud-gateway blip) would
  immediately fail the whole coordinator update and mark every entity
  unavailable until the next poll succeeded.
- Added a retry mechanism to the shared request path (`api.py`'s `_post()`,
  which token refresh also routes through): up to 3 attempts per request, with
  a non-blocking 2-second wait between attempts. Only retries transient,
  network-level failures (timeouts, connection resets) — HTTP-level errors
  (401/403/4xx/5xx) are not retried, since those aren't transient and
  retrying them would only delay correct auth/error handling.
- Adapted from the retry logic originally added to the pre-rebase version of
  this integration
  ([commit 13cc8d7](https://github.com/BeauGiles/ha-deepal/commit/13cc8d7cf3e61c6685b9b6b423c298904d36c66c)),
  reworked for this codebase's single shared request method and for async
  (`asyncio.sleep` instead of a blocking `time.sleep`, which would otherwise
  freeze the whole Home Assistant event loop).

### Known limitations / deferred

- This fix covers the standard S07 cloud request path. The separate S05 MQTT
  condition-fetch path doesn't go through the same request method and wasn't
  covered by this change — if S05 users see similar "Unavailable" blips, that
  path would need the same treatment separately.

## [0.3.1] - 2026-08-21

### Added

- Login region support for New Zealand, Singapore, Malaysia, Thailand, Vietnam,
  Hong Kong, Macau, Indonesia, Philippines, and Mongolia, added alongside
  Australia to `REGION_GATEWAYS`.

### Known limitations / deferred

- **Only Australia is confirmed working.** The other nine countries added in
  this release assume they're homed on the same Singapore cluster/gateway
  (`m.iov.changanauto.sg`, `/appgw`) as Australia, on the basis that the
  original (pre-rebase) `BeauGiles/ha-deepal` integration worked for all of
  them against a single shared endpoint. That integration used a different,
  simpler auth model (manually captured bearer tokens) that didn't
  distinguish between regional clusters the way this one does, so the
  assumption hasn't been independently verified per-country here. If login
  fails for one of these regions, it likely means that account is actually
  homed on a different cluster — flag it with the failing country and, if
  possible, a packet capture of the login request/response.

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
