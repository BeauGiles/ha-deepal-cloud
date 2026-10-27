# Changan Deepal Cloud for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/BeauGiles/ha-deepal-cloud/main/icon.png" alt="Deepal logo" width="160">
</p>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Custom Home Assistant integration for the Changan Deepal cloud API.

It supports the **Deepal S07** (telemetry and remote controls), the **Deepal S05** (MQTT telemetry, with opt-in lock, window and boot controls) and the **Deepal E07** (telemetry only). See [Supported Vehicles](#supported-vehicles) for what has actually been tested on each.

## About This Fork

This repo is rebased on [danperks/ha-deepal](https://github.com/danperks/ha-deepal), which brought account-based login, full remote vehicle control, and Deepal S05 support — a big step up from the earlier version of this integration, which was read-only and required manually capturing tokens with a proxy tool.

On top of that base, this fork:

- Fixes incorrect logic for charge-gun connection status, the "Charging" binary sensor, and "Charge Schedule Enabled" (all three were reading the wrong values)
- Restores features from the original version of this integration that the upstream fork didn't carry over: the vehicle image entity, VIN as the device serial number, and the OTA firmware status sensor
- Renames entities to AU/UK conventions throughout (Odometer, Tyre, Boot) with keys aligned to the real Deepal API fields
- Adds icons and consistent Title Case naming across every entity
- Disables a couple of noisy diagnostic-only entities by default

Full details are in [CHANGELOG.md](CHANGELOG.md).

**Note:** because entity keys changed from the upstream fork, upgrading will create new entities rather than renaming existing ones in place — you'll want to re-add any dashboard cards or automations that reference the old entity IDs, and remove the old (orphaned) entities from the entity registry.

## Important Warnings

- Use this integration at your own risk.
- This is an unofficial integration and is not endorsed by Changan or Deepal.
- Remote commands can affect the vehicle. Make sure it is safe before using controls such as locks, windows, boot, climate, lights, or horn.
- This integration cannot be used to drive the car. It does not implement the BLE/digital key path required for drive authorization.
- Logging in through this integration can log you out of the official Deepal app or other devices. Likewise, logging back into the official app may invalidate the Home Assistant session. Consider creating a separate Deepal user/account for Home Assistant and then 'sharing' car access from your main account in the Deepal app.

## Supported Vehicles

| Vehicle | Telemetry | Remote controls | Tested |
| --- | --- | --- | --- |
| **Deepal S07** | REST cloud API | Lock, windows, boot, climate, charging, lights, horn, seat and steering-wheel heating | UK and AU S07 |
| **Deepal S05** | MQTT | Lock, windows and boot only; off until you enable commands with the control PIN | Telemetry by upstream authors (Portugal, Israel). The MQTT commands, wake and changes in this fork have **not** been tested on an S05 |
| **Deepal E07** | SDA REST endpoint (`protocolType: SDA-MQTT`) | **None** | Telemetry confirmed on an AU E07 |

The integration chooses its behaviour from the `protocolType` the cloud reports for your car, not from its model name, so other models may work if they report one of these types. They are untested.

## Supported Regions
* **Confirmed working:** Australia, Israel, Portugal, and the United Kingdom.
* **Spain:** the Spanish community integration [manuelem1984/dec_deepal](https://github.com/manuelem1984/dec_deepal) reports Spain working with an S05 on the same European cluster this integration uses. It has not been confirmed through this integration yet.
* **Added but unverified, European cluster:** Austria, Belgium, France, Germany, Greece, Ireland, Italy, Luxembourg, the Netherlands and Switzerland (default European cluster; other integrations list them, nobody has confirmed a login here).
* **Added but unverified, Singapore cluster:** Hong Kong, Indonesia, Macau, Malaysia, Mongolia, New Zealand, the Philippines, Singapore, Thailand and Vietnam (assumed to share Australia's Singapore cluster).


## Current Features

**All vehicles**
- Email-code and phone/SMS login through Home Assistant, with native reauthentication/repair when the cloud session is invalidated.
- Telemetry sensors and binary sensors with friendly names, including **Any Door** and **Any Window** (on if any door or window is open). Entities are only created for data your car actually reports, and added later if it first appears later.
- Vehicle image (falls back to the Deepal logo when the picture is unavailable), VIN as the device serial number, and an OTA status sensor where the car provides one.
- Remaining charge time as minutes and as an `H:MM` sensor for dashboards.
- **Download diagnostics** on the device page: protocol detection, mapped and raw signals, and which signals no entity reads yet. VIN, plate, location and tokens are redacted.
- Manual *Refresh Vehicle Data* button. On MQTT vehicles it wakes a car whose last report is stale, at most once per 5 minutes; the periodic poll never wakes the car.

**S07 controls**
- Door lock, charge limit and charging schedule, cabin climate, flash lights and horn.
- Seat heating and ventilation levels (driver and front passenger) and steering-wheel heating.
- Window and boot **buttons**: Lower Windows, Raise Windows, Open Boot, Close Boot. Their open/closed state is available as binary sensors.

**S05 controls (opt-in)**
- Door lock, plus the same window and boot buttons, once remote commands are enabled with the control PIN. Climate, charging, lights and horn are not available on MQTT vehicles.

**E07**
- Telemetry only: battery, range, charging, doors, locks, windows, climate, seats and lamps.

Commands run one at a time in order (up to four queued). Open/closed buttons have no confirmation prompt at integration level; if you want one, set a confirmation on the dashboard card's tap action.

## Known Limitations

- **E07:** No remote controls. The app sends them over a separate MQTT broker that is not implemented. Tyre pressures, outside temperature and humidity are not mapped yet, and the charging-state mapping is inferred from one car's report.
- **S05:** The MQTT telemetry changes (including the charging-state mapping), the wake and the lock/window/boot commands in this fork have not been tested on a real S05. The command protocol comes from [kobizz/ha-deepal](https://github.com/kobizz/ha-deepal), validated there on an Israel-market S05.
- **The Lower/Raise Windows and Open/Close Boot buttons** are confirmed working on an S07. They are untested on the S05, and the command queue (several commands in quick succession) is covered by unit tests but has not been checked on a real car.
- **Other regions and models** are unverified (see above).
- Only the data the cloud provides is available; some cars report only while awake.

## Requirements and languages

- **Home Assistant 2026.3.0 or newer.** That is the first version that reads the integration's own brand icons, and the newest releases are what this integration is developed against; older versions are not tested.
- The setup, options and repair screens are available in English, Spanish, Portuguese, Italian and Dutch (first drafts, not reviewed by native speakers; corrections welcome). Entity names stay in English so entity IDs and the dashboard examples are the same for everyone.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the three-dot menu and choose **Custom repositories**.
4. Add `https://github.com/BeauGiles/ha-deepal-cloud` as an **Integration** repository.
5. Install **Changan Deepal Cloud** from HACS.
6. Restart Home Assistant.

### Manual

1. Copy `custom_components/deepal` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration

Once installed in HACS or manually:

[![Open your Home Assistant instance and start setting up Changan Deepal Cloud.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=deepal)

You can also configure it manually from **Settings -> Devices & services -> Add integration**, then search for **Changan Deepal Cloud**.

During setup, choose the same login method you use in the official Deepal app. If phone/SMS login says the account is not registered, try email-code login instead. If no SMS code ever arrives (Spanish testers report Deepal stopped delivering them in September 2026), cancel and start again with email-code login. You can choose whether to enable remote commands; they require the same control PIN used by the official Deepal app.

## Troubleshooting

- **A sensor is missing:** entities are only created once your car reports the data. Download the diagnostics from the device page and check `unmapped_signals` for data no entity reads yet.
- **Logging:** under **Configure**, tick *Enable redacted API logging*, reproduce the problem, then find the `Deepal` lines in **Settings -> System -> Logs**. Tokens, PINs, keys, VIN, plate and location are filtered, but check before sharing.
- **`APIGW_-1_7_01_004 invalided token` on an S05:** the cloud rejected the token for the MQTT setup. The integration tries the other token it knows about, then falls back to the REST condition (which may show less data) and retries MQTT every few minutes. If it persists, download the diagnostics (they show `mqtt_last_error`) and open an issue.
- **"The Deepal API rate limited the request":** the cloud asked the integration to slow down. It stops calling the API for the time the gateway asks (at least a minute) and carries on by itself; no action is needed.
- **`APP_1_1_02_005 ... logged in on another device`:** the official app or another client signed in with the same account. Use a separate Deepal account for Home Assistant, shared from your main account, and avoid repeated login attempts, which can trigger a rate limit.
- **"Power is not off" (result code 1032):** the car is powered on and refuses the remote command. Check the Power Status entity; switch the car off, or wait for it to power down, and try again.
- **Commands fail while data still updates:** use *Reauthenticate now* under **Configure** to register a fresh command-signing key.
- **Reporting a new model or region:** please attach the diagnostics file (while the car is charging if it is a charging problem) to a GitHub issue.

## Notes

- The integration polls cached cloud status every minute. S07 can also ask for refreshed vehicle data every 5 minutes when remote commands are enabled. MQTT vehicles read refreshed MQTT telemetry and do a fresh read after an acknowledged command.
- After a command is accepted, the integration polls for the command result and refreshed vehicle state. It stops waiting once the cloud reports success, asking the car for fresh data once.
- If the account is used elsewhere, Home Assistant may need reauthentication.

## Credits

- [danperks/ha-deepal](https://github.com/danperks/ha-deepal) for the base integration, and for the seat and steering-wheel control requests and the Spain, Italy and Netherlands regions.
- [kobizz/ha-deepal](https://github.com/kobizz/ha-deepal) for the S05 MQTT command protocol.
- [Sunek0/ha-deepal-alternative](https://github.com/Sunek0/ha-deepal-alternative) (MIT) for the E07 SDA request shape and signal mapping, S05 payload key names, and the ideas behind diagnostics, the wake, the image fallback and the `H:MM` sensor. See [NOTICE.md](NOTICE.md).
- [DylanTusler/ha-deepal](https://github.com/DylanTusler/ha-deepal) for Australia region support.
- @timalpipo for testing on a live AU E07.

## Development Status

This is early reverse-engineering work. Expect breaking changes, incomplete model support, and occasional cloud API/session issues.
