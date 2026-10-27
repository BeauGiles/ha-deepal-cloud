# Changelog

All notable changes to this fork are documented here. Dates are in `YYYY-MM-DD`.

## [Unreleased]

### Added

- **Spanish, Portuguese, Italian and Dutch translations** for the setup and options screens and the repair dialog. Entity names stay in English on purpose, so entity IDs and the documented dashboard cards are the same in every language. These are first drafts and have not been checked by native speakers; corrections are welcome. Home Assistant uses them when your language is set to one of these, and falls back to English otherwise.

### Fixed

- **S05 charging (untested on a real S05; from Sunek0's v1.6.0 findings).** A new
  **charge stopped** state (`ChrgSts=5`, seen with the wallbox disabled and the
  cable still plugged in) now shows as Not Charging instead of unknown. A plugged
  cable is no longer reported as unplugged: a raw connection value of `1` means the
  AC gun is connected (only `0` means not connected), and while the car is idle
  (states 0 and 5) the raw connection fields decide, because they stay set with the
  cable in. Negative charge currents (DC charging can read about -60.5 A) are shown
  as positive amps, and the 2538 A glitch is still dropped whichever sign it has.
- **S05 outside temperature** is now read from MQTT (`outsideTemperature` or
  `externalTemperature`), so the sensor is no longer empty.
- The English options and remote-command descriptions no longer say S05 support is read-only, and the "Deepal remote commands need reauthentication" repair dialog shows its title instead of a raw translation key.

## [0.4.0] - 2026-10-25

Adds **Deepal E07 support (telemetry)**, **opt-in remote controls for MQTT
vehicles (S05)**, new **S07 seat and steering-wheel controls**, a **diagnostics
download**, and many mapping and reliability fixes. **Read the upgrade notes
first: some changes break automations.**

### Upgrade notes

- **Windows and Boot are now buttons, not covers (breaking).** A cover's up arrow
  means "open", which for windows means lowering them, and a stray tap is easy.
  There are now four explicit buttons: **Lower Windows**, **Raise Windows**,
  **Open Boot** and **Close Boot**, sending the same commands as before. The old
  `cover` entities are removed automatically, so any automation, script or card
  using `cover.*windows` or `cover.*boot` must switch to `button.press`. Their
  open/closed state is still available from the existing binary sensors. There is
  no confirmation prompt at integration level; use a dashboard card's tap-action
  confirmation if you want one.
- **Fewer entities on new installs.** Sensors and binary sensors are now only
  created for data the vehicle actually reports, and added later if the data first
  appears. Existing installs keep every entity already in their registry; delete
  ones you do not want (they will not return unless the car starts reporting them).
- **Left-hand-drive cars: driver and passenger seat values swap.** Front doors,
  windows and seats are now placed using the vehicle's `RHD`/`LHD` setting.
  Right-hand-drive cars (including the AU S07) are unchanged.
- **MQTT (S05) setups can now enable remote commands.** They stay off until you
  enable them with the control PIN; lock and the window/boot buttons only appear
  once commands are enabled.

### Known limitations

- **S05 remains untested.** The MQTT telemetry changes, the wake and the
  lock/window/boot commands have not been tried on a real S05 by anyone. The
  command protocol comes from kobizz's fork, where it was validated on an
  Israel-market S05. If you own an S05, please report how it behaves.
- **The Lower/Raise Windows and Open/Close Boot buttons, and the command queue,
  have not yet been tested on a real car.** The same commands worked as covers
  on the S07 before, and the queue is covered by unit tests, but nobody has used
  the new buttons end to end.
- **E07 is telemetry only**, and its charging-state mapping is inferred from one
  car's report.

### Added

- **Deepal E07 support (telemetry only).** E07s report `protocolType: SDA-MQTT`
  and read their condition from the regional SDA REST endpoint
  (`getCarConditionByCarId`), not the S05 MQTT path. Battery, range, odometer,
  charging, doors, locks, windows, climate, seats and lamps are mapped. Confirmed
  on a live AU E07; remote commands are **not** available. Tyre pressures,
  outside temperature and humidity are not mapped yet.
- **Opt-in remote controls for MQTT vehicles (S05):** door lock/unlock, windows
  and boot. Commands wake the vehicle, are published exactly once (never
  auto-retried), wait for the broker's response, and are followed by a fresh read.
  Validated by upstream only on an Israel-market S05; untested in this fork.
- **S07 seat and steering-wheel controls:** Driver and Front Passenger Seat
  Heating and Ventilation levels (0-3) and a Steering Wheel Heating switch. Not
  created for MQTT or SDA vehicles. These send real commands.
- **Diagnostics download** (device page): protocol detection, mapped telemetry,
  raw SDA/MQTT signals, signals no entity reads yet (`unmapped_signals`), MQTT
  topic structure and refresh state. VIN, plate, location and tokens are redacted.
- **Throttled wake for MQTT vehicles:** pressing *Refresh Vehicle Data* on an MQTT
  vehicle whose last report is over 2 minutes old wakes it and waits up to 60 s
  for fresh data, at most once per 5 minutes. The periodic poll never wakes the
  car. Not used for E07 (REST).
- **Any Window** binary sensor (on if any window is open), alongside Any Door.
- **Remaining Charge Time (H:MM)** sensor for dashboards.
- **Vehicle image fallback:** the picture is fetched in the background, and if it
  is missing, slow or not an image the Deepal logo is shown instead.
- **Spain, Italy and the Netherlands** login regions (default European cluster;
  not verified by this fork).
- Deepal icon and logo in `custom_components/deepal/brand/`.
- A unit-test suite (`tests/`, `pytest`, no Home Assistant needed) and a CI
  workflow that runs it.
- With "Enable redacted API logging" on, MQTT telemetry logs each decoded message
  (redacted) and the topic structure, to help support new models.

### Changed

- Commands now **queue** instead of failing with "already in progress": they run
  one at a time in order (up to 4 running or waiting, then a clear error). The
  periodic background refresh still skips while a command runs.
- Commands **stop waiting once the cloud reports success.** They used to hold
  everything for up to 30 s until the vehicle data matched. After a short grace
  period the integration asks the car for fresh data once and stops waiting,
  logging a warning if the data still shows the old state.
- **Fewer cloud calls for MQTT vehicles:** the CA connection configuration is
  reused for 11 minutes and the MQTT auth token for 1 minute, instead of both
  being fetched on every MQTT session (every poll). The cache is dropped as soon
  as an MQTT exchange fails.
- MQTT code is named generically (`mqtt_*` rather than `s05_*`): it is chosen by
  the vehicle's `protocolType`, not its model.
- Setup and reauthentication no longer force remote commands off for MQTT vehicles.

### Fixed

- **E07 charging state:** Charge Status, Charging and Charging Cable were wrong
  while charging, because the E07's charge status enum differs from the S07's.
  They are now translated using the reported currents, and "Reported Charge
  Current" is positive while charging. The mapping is inferred from one car's
  report.
- **Any Door** counted a door value the car did not report as "open"; unreported
  values are now unknown, as in the new Any Window sensor.
- **Remaining Charge Time** showed 8191 ("no estimate") on the S07 and on MQTT/SDA
  cars; it now shows unknown.
- **Rejected CA bootstrap (`invalided token`):** if the legacy `getConnConf` /
  `getAuthTokenByUserId` routes are rejected, the app's alternate routes
  (`appGetCarConfFunc`, and the `app-apigw/vot-auth` token route) are tried once
  (the alternate configuration is only used if it carries the connection info).
  A message saying the session token is invalid or expired refreshes the session
  once per hour (and saves the new tokens), then falls back to the REST
  condition. It never starts a re-login flow, which could trigger login rate
  limits. Routes from Sunek0/ha-deepal-alternative (MIT); untested on an
  affected account.
- **HTTP 429 rate limits:** the integration now stops calling the API for the
  gateway's `Retry-After` (seconds or an HTTP date; at least 1 minute, at most
  1 hour) instead of retrying every poll. A rate limit during a token refresh no
  longer turns into a re-login prompt.
- **Malformed MQTT packets** (truncated topic or packet id, bad text, a payload
  that is not a JSON object) are skipped instead of aborting the exchange.
- Command results with code `"00000"` (the REST success code) count as success.
- **REST cabin humidity** uses the tenths-of-a-percent rule already applied to
  MQTT (a raw 453 is 45.3%, not 453%).
- **"Power is not off" (result code 1032):** the car refuses some remote
  commands (seen with turning the air conditioner off, and with windows) while it
  is powered on. The error now says so and what to do (switch the car off or wait
  for it to power down), keeping the car's own message.
- **S05 accounts the CA gateway rejects** (danperks/ha-deepal issue #11: login
  works but `getConnConf` answers `APIGW_-1_7_01_004 invalided token`): the
  gateway accepts a different token as the user token depending on the account.
  The CA calls now try the cacToken first (as before) and, on an `APIGW_`
  rejection, the access-token half once, remembering whichever works. If MQTT
  telemetry still fails, the integration falls back to the REST condition (it may
  be partial) and retries MQTT with a growing delay (1, 2, 4, 8, then every
  10 minutes) instead of sending a rejected request every minute. Authentication
  errors are not hidden. Idea from danperks/ha-deepal; untested on an affected
  account.
- **S05 charging state, plug and current** (values observed on a live S05 and
  documented by Sunek0/ha-deepal-alternative): the S05's `ChrgSts` is a 0-4 enum
  (0 not charging, 1 AC plugged, 2 DC plugged, 3 AC charging, 4 DC charging), not
  the S07 codes our entities expect, so charging showed as "Unknown" and a plugged
  cable as "Not Charging". It is now translated; the AC/DC plug entities follow
  that state, so a stale connection field cannot keep a gun "plugged"; and the
  charge current is taken from the charger in use. A raw glitch the car publishes
  after a DC session (2538 A while parked) is no longer shown as amps. Untested
  on a live S05.
- **S05 cabin humidity** could read 453%: the car sends a percentage or tenths of
  a percent, so values above 100 are divided by ten and anything outside 0-100 is
  unknown.
- **Cabin Climate temperature range** is now 18-32 C (it was 16-30), and targets
  sent to the car are clamped to that range: the gateway rejects anything outside
  it with `COMMON_1_1_01_005`, which made turning the AC on fail when the car's own
  setting was out of range.
- **S05 (MQTT) payload keys:** the DC gun state is read from the payload's
  misspelled `dcDhargeGunConnectionState` as well as the correct spelling, `hood`
  is accepted as well as `hoodStatus`, and the report timestamp also looks at
  `lastUpdatedTime` and accepts epoch seconds/milliseconds. Untested on a live S05.
- MQTT command responses with result code `"000000"` count as success.
- The MQTT telemetry read no longer loads the SSL trust store on the event loop
  (Home Assistant's blocking-call warning).
- API logging also redacts licence plate and location (`Lat`/`Lng`, `location`,
  `gps`, `address`); raw signal dumps in diagnostics only redact exactly-sensitive
  names so ordinary signals are not hidden.
- Removed an unused `bluetooth` matcher and `bluetooth_adapters` dependency from
  the manifest.

### Credits

- [danperks/ha-deepal](https://github.com/danperks/ha-deepal): the base
  integration; seat/steering control requests and the ES/IT/NL regions.
- [kobizz/ha-deepal](https://github.com/kobizz/ha-deepal): the S05 MQTT command
  protocol (lock, windows, boot), validated on an Israel-market S05.
- [Sunek0/ha-deepal-alternative](https://github.com/Sunek0/ha-deepal-alternative)
  (MIT): the E07 SDA REST request shape and signal mapping, S05 payload key names,
  and the ideas behind diagnostics, the wake, the image fallback and the H:MM
  sensor. See [NOTICE.md](NOTICE.md).
- [DylanTusler/ha-deepal](https://github.com/DylanTusler/ha-deepal): Australia
  region support.
- @timalpipo: testing and detailed reports on a live AU E07.

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
