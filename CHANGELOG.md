# Changelog

All notable changes to this fork are documented here. Dates are in `YYYY-MM-DD`.

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
