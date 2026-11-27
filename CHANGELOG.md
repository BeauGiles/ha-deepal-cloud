# Changelog

All notable changes to this fork are documented here. Dates are in `YYYY-MM-DD`.

## [Unreleased]

### Fixed

- **"Reported charging current" is now derived from AC/DC when the car never sends the combined field.** Confirmed from a real S07's diagnostics: `acChargeCurrent`/`dcChargeCurrent` are present but the plain `chargeCurrent` field is never sent at all. The sensor now falls back to whichever of the two is actually reporting a non-zero current, and is created for cars that only ever report the breakdown.
- **"Remaining charge time (H:MM)" now shows "Not applicable" instead of Unknown when the car has no current estimate** (the cloud's `8191` sentinel, seen whenever the car isn't charging). The plain-minutes sensor still shows Unknown for the same case - it has a device class and unit, so it can't carry free text, unlike the H:MM one.
- **The Location device tracker was never actually gated to S05 - only the repair issue was, in 0.4.4.** A real S07's raw REST condition response carries its own top-level `locationGeo` block (same root cause as the repair fix above), so checking the data alone isn't enough. The entity itself is now gated the same way the other S05-only platforms are.

### Changed

- **Removed the "Charging schedule enabled" binary sensor.** It duplicated the Charging schedule switch's own on/off state exactly, with no control of its own. Its extra attributes (plan ID, start/end switches, weeks, time zone, etc.) moved onto the switch entity, so no detail is lost - only the redundant entity itself is gone.

## [0.4.4] - 2026-11-27

Urgent bugfix release. Reported directly from a live 0.4.3 S07 install within hours of that release going out - see below.

### Fixed

- **"Deepal location permission is off" repair fired for every vehicle, not just the S05 it's meant for.** The S07's raw REST condition response carries its own top-level `locationGeo` block (not something this integration maps there itself), which the 0.4.3 location-permission check read without first confirming the vehicle actually uses MQTT. Now gated the same way the location device tracker already is, and clears any issue a non-S05 vehicle was mistakenly given.
- **Opening that repair for the first time crashed with a 500 error.** Home Assistant's repair-flow manager calls the flow's init step with its own data dict (not a form submission), and the flow forwarded it straight into the step that reads the submitted QR URL, raising `KeyError: 'qr_auth_url'` before the form ever showed. The existing command-reauth repair already avoided this; the location-permission one now does too.

## [0.4.3] - 2026-11-27

More experimental, opt-in S05 features, a new service, a login quality-of-life fix, and an entity-layout cleanup. **S05-specific features added since 0.4.2 are still untested on a real S05** - released as stable because the S07/E07 paths this fork was built against are unaffected (the only change there is the entity-category/naming cleanup below, which doesn't touch any entity's data or control logic). **If you have an S05 or S05 PHEV, please try these out and report back.** Home Assistant 2026.3.0 or newer is still required.

### Added

- **Lowest/Low tyre pressure sensor pair, built in.** A `Lowest tyre pressure` sensor and a `Low tyre pressure` binary sensor are now created for every vehicle that reports any tyre pressure (not just the S05-only per-wheel warning flags) - the same thing a `min_max` + `threshold` helper pair would otherwise need, by hand, per vehicle. The warning threshold defaults to 230 kPa and is configurable per vehicle under **Configure** (`Low tyre pressure warning threshold`).
- **S05 vehicle location device tracker and QR location authorisation (experimental, opt-in).** The head unit only shares GPS location once its Privacy → Location permission QR is authorised - through the integration's Configure dialog, a repair that's raised while sharing is off, or the new `deepal.authorize_qr` service. Once authorised, a Location device tracker exposes the car's coordinates plus altitude, heading, satellite count, GPS time and whether sharing is on; a live latitude is still reported even when longitude happens to be exactly 0. **S05 only** (literal `MQTT`, not the E07's `SDA-MQTT`) - nothing maps an equivalent GPS field for the S07's REST condition or the E07's SDA condition, so the tracker stays unavailable on those. Ported from [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (MIT). **Completely untested on a real S05** - there is still no S05 owner testing this fork.
- **`deepal.set_charge_window` service.** Sets the charging schedule's start and end times in one call, keeping the current start/end switches as they are - the existing switch and Time entities always set both switches together, so there was no way to change just the times without also forcing the schedule on. Target the Charge Schedule switch entity. `control_charge_schedule` in `api.py` now accepts `start_enabled`/`end_enabled` independently of `enabled` to support this. Ported from [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (MIT).
- **"Start over" checkbox on the email and SMS code steps.** If a code expires or never arrives, you can now tick "Start over" on the code-entry step to go straight back and request a new one, instead of cancelling the whole config flow and starting from scratch. The code field is optional when ticked. Ported from [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (MIT).

### Changed

- **Entity categories and naming brought in line with the Polestar C3 fork's own audit.** Comparing this fork's entity layout against recent category/naming cleanup in [BeauGiles/ha-polestar-c3](https://github.com/BeauGiles/ha-polestar-c3):
  - `Charging status` (was `Charge status`, Diagnostic) and `Power status` (Diagnostic) are promoted to primary Sensors-card entities, matching that fork's `Charging status` and `In use`.
  - `Cabin air quality index` (renamed from `Cabin Air Quality Level`) is likewise promoted out of Diagnostic.
  - The `Refresh vehicle data` button is no longer marked Diagnostic, matching that fork's plain Controls-card `Refresh` button.
  - The charging-schedule switch, start/end time entities, and their sensor mirrors move to **Configuration** (switch/time) or **Diagnostic** (the sensor mirrors), matching that fork's `Charging schedule` placement; `Max charge limit` moves to Diagnostic for the same reason (a config-echo value, which that fork doesn't even duplicate as a separate sensor).
  - Several entities are renamed for consistency: `Charge Schedule*` -> `Charging schedule*`, `*Charge Current` -> `*Charging current`, matching the gerund wording used throughout the Polestar C3 fork.
  - **Every entity name now follows Home Assistant's sentence-case convention** (e.g. `Front left door`, not `Front Left Door`) instead of Title Case, matching current Home Assistant style guidance and the Polestar C3 fork. Internal keys/translation keys/unique IDs are unchanged - only the displayed name moves.

### Documentation

- **Belgium login region moved out of "unverified".** [danperks/ha-deepal](https://github.com/danperks/ha-deepal) reports Belgium working on the same European cluster this integration uses, and notes that Netherlands-delivered vehicles are often registered under Belgium (`BE`) rather than the Netherlands - a Dutch-dealer account that gets "Account not registered" under the Netherlands can succeed under Belgium instead. Not yet confirmed through this integration itself, so it's called out on its own line rather than moved into "Confirmed working".

## [0.4.3-beta2] - 2026-11-27

**Beta.** One more experimental, opt-in S05 feature (cabin climate, seat heating/ventilation and steering-wheel heating over MQTT), plus a concurrency fix for the live MQTT session added in 0.4.3-beta1. Install it from HACS with **Redownload → Show beta versions**. **Still no S05 or S05 PHEV owner has tested any of the S05-specific work in this fork** - if you have one, please try it and report back. Home Assistant 2026.3.0 or newer is still required.

### Added

- **S05 remote cabin climate, seat heating/ventilation and steering-wheel heating (experimental, opt-in).** Ported from [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (MIT), who describe it as having had "limited live use" so far. The Cabin Climate entity, the four seat heating/ventilation Number entities and the Steering Wheel Heating switch, previously S07-only, now also appear for an S05 (literal `MQTT`, not the E07's `SDA-MQTT`) once remote commands are enabled - both the BEV and the PHEV, unlike the charge-schedule entities from 0.4.3-beta1. Each uses a different `Cnr_*` MQTT command per function (`Cnr_DrACTemp`/`Cnr_AllAcOff` for climate, `Cnr_DrSeatHeat`/`Cnr_PsgSeatHeat`/`Cnr_DrSeatVent`/`Cnr_PsgSeatVent` for seats, `Cnr_TxSteeringHeat` for the steering wheel) rather than the REST commands the S07 uses. **Completely untested on a real S05 here** - there is still no S05 owner testing this fork.

### Fixed

- **The periodic poll, a command, and the live MQTT session (0.4.3-beta1) no longer race for the same MQTT connection.** The broker only accepts one connection per client id, and all three used the same one independently: the normal poll on an S05 runs over MQTT every scan interval regardless of the live session, and any command (lock, windows, boot, or the new S05 BEV charge-schedule writes) does too. With the live session enabled, any of these could open a second connection while the live session's was still open, which a real broker would be expected to reject or disconnect one of. A new `DeepalClient._mqtt_exclusive_connection()` now serializes all three; the live session additionally watches for a pending request and ends its current cycle early (checked at least every `MQTT_LIVE_YIELD_CHECK_SECONDS`, 5s) instead of holding the connection for the rest of its ~4-minute budget. Found by reading how [danperks/ha-deepal](https://github.com/danperks/ha-deepal)'s own newer live-MQTT work handles this same problem, not from anything observed on a real car - still no real S05 to test this against.

## [0.4.3-beta1] - 2026-11-24

**Beta.** Four new, experimental, opt-in features for the **S05**, none of them tested on a real S05 yet, plus a general fix for the vehicle photo. Install it from HACS with **Redownload → Show beta versions**. **If you have an S05 or an S05 PHEV, please try these out and report back** - this is the first real S05-specific work since the fork started, and it needs real-car feedback to go further. Home Assistant 2026.3.0 or newer is still required.

### Added

- **Live MQTT telemetry session for the S05 (experimental, opt-in, off by default).** A new "Keep a live MQTT connection" option keeps one MQTT connection open and pushes every telemetry update the car sends between the normal polls, instead of waiting for the next one. Built on the same connect/login/subscribe sequence the existing one-shot MQTT read already uses, just kept open and reading for ~4 minutes per cycle (reconnecting immediately after) instead of returning after the first report; no new keepalive/PINGREQ handling was needed as a result. The regular poll keeps running on its own schedule underneath this either way, so a live-session outage or simply leaving the option off never makes data go stale beyond the usual poll interval. **Literal `MQTT` vehicles only (S05).** The E07 also matches `vehicle_uses_mqtt` internally (its `protocolType` is `SDA-MQTT`), but this is explicitly excluded from it, since it isn't known to work there yet. **Untested on a real S05.**
- **Charge schedule for the S05 BEV (experimental, opt-in).** The Charge Schedule switch and the Charge Schedule Start/End time entities, previously S07-only, now also appear for an S05 BEV once remote commands are enabled. The car's own `chargePlanList` is REST-only (not in the MQTT telemetry), so the coordinator now overlays a REST condition read onto the MQTT one whenever commands are enabled, best-effort: a failed overlay only hides these entities, it doesn't affect telemetry. Like the existing S07 switch/time entities, they need a schedule plan to already exist (set once from the official app) before Home Assistant can read or change it. **Deliberately excluded:** the S05 PHEV, whose schedule plan behaves differently (the app edits one fixed "plan 1" in place rather than replacing it) and isn't implemented here yet; also the E07, which has no remote commands at all. **Completely untested on a real S05** - there is currently no S05 owner testing this fork. Please report back if you try it.
- **Fuel sensors for the S05 PHEV** (Fuel Level, Fuel Volume, Fuel Range). `api.py` now maps the car's `remainingFuel`/`fuelLeftover`/`remainedOilMile` MQTT fields. Raw field names and the real captured values (27 L at 53% on a live S05 PHEV) come from Sunek0/ha-deepal-alternative (MIT). No tank-capacity sensor is added, matching their own finding that the car never reports one. These stay hidden on a BEV, S07 or E07, which have no fuel data at all. Read-only; charge-schedule and other PHEV-specific controls are a separate, later piece of work.
- **Tyre-pressure-warning sensors (S05 only).** `api.py` already parsed the car's per-wheel `lfPressureWarning`/`rfPressureWarning`/`lrPressureWarning`/`rrPressureWarning` flags from S05 MQTT telemetry, but nothing read them. Four new binary sensors (Front Left/Right and Rear Left/Right Tyre Pressure Warning) expose them. They stay hidden on S07 and E07 cars, whose condition data has no such field; those models only have the four raw pressure sensors.

### Fixed

- **The Vehicle Image now keeps showing the last real photo across a failed or slow refetch**, instead of dropping straight to the bundled Deepal logo. The cloud's image URL can change (it looked hash-obfuscated/session-scoped), and if the new URL's fetch failed or didn't finish quickly, the entity used to show the generic logo even though it already had a perfectly good photo. It now only falls back to the logo when there has never been a successful fetch at all (idea from Sunek0/ha-deepal-alternative, MIT).

## [0.4.2-beta1] - 2026-11-19

**Beta.** Mostly groundwork for the E07 (diagnostics probes and a sensor that lists signals nothing reads yet), plus a Home Assistant 2026.11 deprecation fix and some hardening. Install it from HACS with **Redownload → Show beta versions**. **E07 owners:** please press **Download diagnostics** on the Deepal integration page after updating (ideally while the car is charging, and again just after a drive) and attach the file to your issue. It is redacted, but please skim it first. Home Assistant 2026.3.0 or newer is still required.

### Fixed

- **One impossible reading no longer risks a whole refresh.** A value of `NaN` or `Infinity` in a report is now unknown (before, `Infinity` could raise an error while reading an integer), and a state of charge or charge target outside 0-100 (such as the `255` "invalid" marker) is unknown instead of 255 %. On the E07, an invalid `VIUSocDisp` now falls back to `BcuSocDisp`. Cabin humidity of exactly 0 is treated as "no reading" (Sunek0 saw this alternate with real values on a parked PHEV); a real cabin is never at 0 %. These are precautions based on another integration's observations, not something seen on an S07 or E07 here.
- **Home Assistant 2026.11 deprecation warning for the cabin climate entity.** Home Assistant now wants `native_temperature_unit`, `native_current_temperature` and `native_target_temperature` and will stop accepting the plain names in 2027.11. The climate entity uses the native names on Home Assistant 2026.11 or newer and keeps the plain names on older versions, so the minimum Home Assistant version is unchanged. No change to behaviour or entity IDs.

### Added

- **E07 firmware-upgrade probes in the diagnostics download.** For SDA-MQTT cars, `endpoint_probes` now also holds read-only GETs of the three firmware-upgrade endpoints the official app (v1.12.0) has: the current task (`ota/get-task`), its progress (`ota/get-progress`) and the upgrade history (`ota/get-upgrade-history`, first five entries only). Unlike the last-event and server-config probes, these show **values** so the status codes can be learned; web links in them are cut at the `?` so signed links do not leak. The E07 has no OTA status sensor today (it shows unknown). Method and query are a best guess, so a failure is reported as text and is itself useful. Nothing uses the results yet.
- **SDA Data sensor (E07).** A diagnostic sensor, disabled by default, whose state is the number of E07 signals the car reports that no entity reads yet, and whose attributes are those signals, one flat attribute per signal (for example `BcuBattTMax`), so they can be used in templates with `state_attr()`. VIN, plate, location and ids are redacted. Values are the car's raw numbers: units and scaling are not confirmed. The attributes are kept out of the recorder history. When a signal gets its own entity it drops out of this sensor.
- **E07 endpoint probes in the diagnostics download.** For SDA-MQTT cars, `endpoint_probes` now holds read-only GETs of three E07 endpoints the official app (v1.12.0) has: the function list (`app-func/get-function`), the last event (`car-event/last`) and the MQTT server config (`car-ctrl/get-mqtt-server-config`, the broker the app uses for E07 remote controls). The last event and server config report **structure only (field names and types, no values)** because they may hold credentials or location. Method and query are a best guess; nothing uses the results. This is groundwork for the E07 remote controls, which still need real responses and a captured command to build.
- **Endpoint probes in the diagnostics download (S07 / REST cars only).** The download now includes `endpoint_probes`: read-only calls to the app's `vehicle/function-config`, `function-config/v2` and `vehicle/condition` v2 endpoints, with each result or error. These exist in the official app (v1.12.0) but the request and response shapes are unconfirmed, so nothing in the integration uses them yet; they are only reported so real responses can be collected. Failures never break the download.
- **Model code in the diagnostics download** (`detection.mqtt_model_code`), read from the MQTT message envelope of S05-style cars. It tells an S05 EV (code ending `BEV`) from a PHEV (`HEV`) in bug reports. It is only recorded; nothing acts on it. Empty when the car sends none.
- **Plainer messages when a remote command fails.** When the vehicle rejects a command with only a numeric result code and no text, the error now says what the code means (for example "Previous Command is executing; please try again later (3006)"). The wording comes from the official app's own English strings (v1.12.0): about 40 vehicle result codes and 50 vehicle-related cloud error codes. The vehicle's own message always wins, the code is always shown, and unknown codes behave as before. **These meanings are not yet confirmed against live responses from a car**, so please report any code that looks wrong.

## [0.4.1] - 2026-10-27

Adds **Spanish, Portuguese, Italian and Dutch** setup screens, **eight more European countries**, **more and state-aware icons**, S05 charging fixes, and a test that keeps the diagnostics download free of secrets. **Requires Home Assistant 2026.3.0 or newer.**

### Upgrade notes

- **Requires Home Assistant 2026.3.0 or newer** (was 2025.1.0 in `hacs.json`, which was never tested). 2026.3 is when Home Assistant started reading an integration's own brand icons. If you are on an older version, HACS will stop offering updates until you upgrade Home Assistant.

### Added

- **Hint on the SMS code step** to cancel and use email login if no SMS arrives. A Spanish integration reports Deepal stopped delivering login SMS codes in September 2026 (European gateway; not confirmed for other regions). Phone login is kept.
- **Spanish, Portuguese, Italian and Dutch translations** for the setup and options screens and the repair dialog. Entity names stay in English on purpose, so entity IDs and the documented dashboard cards are the same in every language. These are first drafts and have not been checked by native speakers; corrections are welcome. Home Assistant uses them when your language is set to one of these, and falls back to English otherwise.

### Changed

- **Icons follow the state** for the lock sensors (locked/unlocked), the four window sensors (open/closed) and the turn signals (on/off), plus tyre icons for the tyre pressures and AC/DC icons for the charge currents. Icon choices borrowed from manuelem1984/dec_deepal's icon registry (MDI names only).
- The Lower/Raise Windows and Open/Close Boot buttons are now confirmed working on an S07 (the 0.4.0 notes listed them as untested).
- **Icons for more entities** via `icons.json` (charging, seat and steering heating, lamps, indicators, engine, defrost, schedule, gear and brake status and others), with on/off variants where a good icon exists. Entities that already set an icon in code are unchanged.
- **Eight more European countries** can be selected at login: Ireland, France, Germany, Greece, Belgium, Luxembourg, Switzerland and Austria. They use the default European cluster, as listed by other integrations, and are unverified; please report whether login works.
- The country picker, `hacs.json` and the README region lists are now alphabetical by country name, and the README groups the unverified countries by cluster.
- Internal: the country list, dial codes and regional gateways now come from one table (`countries.py`) instead of three places, and a test fails if `hacs.json` or the README disagree with it. No behaviour change.
- A test for the diagnostics download checks that tokens, PIN, keys, device/user/vehicle ids, VIN, plate, image URL, email and coordinates never appear in it. Issue templates now ask for the details needed to debug a report, and ruff runs in CI.

### Fixed

- **S05 charging (untested on a real S05; from Sunek0's v1.6.0 findings).** A new
  **charge stopped** state (`ChrgSts=5`, seen with the wallbox disabled and the
  cable still plugged in) now shows as Not Charging instead of unknown. State 5 now counts the cable as
  connected. A raw connection value of `1` is treated as unknown rather than
  plugged or unplugged, because forks disagree about it (one saw a live S05 report
  `1` with the cable in, another documents `1` as unplugged, and a PHEV can keep a
  stale `1`); `0` is not connected and `2` or more is connected. Negative charge currents (DC charging can read about -60.5 A) are shown
  as positive amps, and the 2538 A glitch is still dropped whichever sign it has.
- **S05 outside temperature** is now mapped if the car reports it over MQTT
  (`outsideTemperature` or `externalTemperature`). Spanish S05 testing suggests the
  S05 may not send it at all, in which case the sensor simply does not appear.
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
