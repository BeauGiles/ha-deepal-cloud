# Changan Deepal Cloud for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/BeauGiles/ha-deepal-cloud/main/icon.png" alt="Deepal logo" width="160">
</p>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Custom Home Assistant integration for the Changan Deepal cloud API.

It supports the **Deepal S07** (telemetry and remote controls), the **Deepal S05** (MQTT telemetry, with opt-in lock, window and boot controls) and the **Deepal E07** (telemetry only). See [Supported Vehicles](#supported-vehicles) for what has actually been tested on each.

> [!IMPORTANT]
> **Upgrading from 0.3.x?** Windows and Boot are now buttons instead of covers, and sensors are only created for data your car reports. See the [0.4.0 upgrade notes](CHANGELOG.md#040---2026-10-25) before updating.

## About This Fork

This repo is rebased on [danperks/ha-deepal](https://github.com/danperks/ha-deepal), which brought account-based login, full remote vehicle control, and Deepal S05 support — a big step up from the earlier version of this integration, which was read-only and required manually capturing tokens with a proxy tool.

On top of that base, this fork:

- Fixes incorrect logic for charge-gun connection status, the "Charging" binary sensor, and "Charge Schedule Enabled" (all three were reading the wrong values)
- Restores features from the original version of this integration that the upstream fork didn't carry over: the vehicle image entity, VIN as the device serial number, and the OTA firmware status sensor
- Renames entities to AU/UK conventions throughout (Odometer, Tyre, Boot) with keys aligned to the real Deepal API fields
- Adds icons and consistent Title Case naming across every entity
- Disables a couple of noisy diagnostic-only entities by default

Full details are in [CHANGELOG.md](CHANGELOG.md).

> [!NOTE]
> Because entity keys changed from the upstream fork, upgrading will create new entities rather than renaming existing ones in place — you'll want to re-add any dashboard cards or automations that reference the old entity IDs, and remove the old (orphaned) entities from the entity registry.

## Important Warnings

> [!WARNING]
> **Unofficial and unsupported.** This is a community project, not endorsed by, affiliated with, or supported by Changan or Deepal. It was built by reverse-engineering the official app's own cloud traffic, not from a published API, and either can change or block it at any time without notice.

- This integration cannot be used to drive the car. It does not implement the BLE/digital key path required for drive authorization.
- Logging in through this integration can log you out of the official Deepal app or other devices. Likewise, logging back into the official app may invalidate the Home Assistant session. Consider creating a separate Deepal user/account for Home Assistant and then 'sharing' car access from your main account in the Deepal app.

See the full [Disclaimer](#disclaimer) at the bottom of this page.

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

If login fails for a region, the account may be homed on a different cluster: please open an issue with the country and the diagnostics file.

## Current Features

**All vehicles**
- Email-code and phone/SMS login through Home Assistant, with native reauthentication/repair when the cloud session is invalidated.
- Telemetry sensors and binary sensors with friendly names, including **Any Door** and **Any Window** (on if any door or window is open). Entities are only created for data your car actually reports, and added later if it first appears later.
- **Download diagnostics** on the device page: protocol detection, mapped and raw signals, and which signals no entity reads yet. VIN, plate, location and tokens are redacted.
- Manual *Refresh Vehicle Data* button. On MQTT vehicles it wakes a car whose last report is stale, at most once per 5 minutes; the periodic poll never wakes the car.

Commands run one at a time in order (up to four queued). Open/closed buttons have no confirmation prompt at integration level; if you want one, set a confirmation on the dashboard card's tap action.

## Features

✅ supported · 🧪 experimental (inferred from one car's report) · ◐ only on cars that report it · ➖ not available

### Read

| Feature | S07 | S05 | E07 |
| --- | :---: | :---: | :---: |
| State of charge, range | ✅ | ✅ | ✅ |
| Charging status, current, remaining charge time | ✅ | ✅ | 🧪 |
| Charging cable / gun connected | ✅ | ✅ | 🧪 |
| Charge limit (read) | ✅ | ➖ | ➖ |
| Charging schedule (read) | ✅ | 🧪 (opt-in, untested on a real S05, BEV only) | ➖ |
| Doors, windows, boot, Any Door/Any Window | ✅ | ✅ | ✅ |
| Door lock status | ✅ | ✅ | ◐ |
| Cabin climate status | ✅ | ✅ | ✅ |
| Inside temperature, cabin humidity | ✅ | ◐ | ◐ |
| Cabin air quality / PM2.5 | ◐ | ◐ | ➖ |
| Outside temperature | ➖ | ✅ | ➖ |
| Tyre pressure | ✅ | ✅ | ➖ |
| Tyre pressure warning flag | ➖ | ✅ | ➖ |
| Lights (beams, position, turn signals) | ✅ | ✅ | ✅ |
| Seat heating / ventilation status | ✅ | ✅ | ◐ |
| Steering wheel heater status | ✅ | ➖ | ➖ |
| Odometer | ✅ | ✅ | ✅ |
| Vehicle image, VIN, OTA status | ✅ | ◐ | ◐ |

### Control

| Feature | S07 | S05 | E07 |
| --- | :---: | :---: | :---: |
| Lock / unlock | ✅ | 🧪 (opt-in, untested on a real S05) | ➖ |
| Windows, boot (open/close) | ✅ | 🧪 (opt-in, untested on a real S05) | ➖ |
| Flash lights, honk horn | ✅ | ➖ | ➖ |
| Cabin climate start/stop, target temperature | ✅ | ➖ | ➖ |
| Charge limit | ✅ | ➖ | ➖ |
| Charging schedule | ✅ | 🧪 (opt-in, untested on a real S05, BEV only) | ➖ |
| Seat heating/ventilation level, steering wheel heater | ✅ | ➖ | ➖ |
| Manual refresh (wakes a stale car) | ✅ | ✅ | ➖ (REST needs no wake) |

> [!CAUTION]
> Commands act on a real car. You are responsible for how you use them and for any automations you build on them.

### Entities by platform

| Platform | Examples |
| --- | --- |
| Sensor | State of Charge, Estimated Range, Odometer, Charge Status, Charge Current, Remaining Charge Time, Tyre Pressures, Inside/Outside Temperature, Cabin Humidity, Power Status, OTA Status, Vehicle Image URL |
| Binary sensor | Any Door, Any Window, individual doors/windows, Boot, Driver/Passenger Door Locked, Charging Cable, DC Charge Gun, Charging, Charge Schedule Enabled, Vehicle Connected, lights, Seat Heater/Ventilation On, Tyre Pressure Warning (S05) |
| Lock | Door lock (S07, opt-in S05) |
| Climate | Cabin climate (control on S07, read-only elsewhere) |
| Number | Charge Limit, Seat Heater/Ventilation Level (S07 only) |
| Switch | Charge Schedule Enabled, Steering Wheel Heater (S07 only) |
| Time | Charge Schedule Start/End (S07 only) |
| Button | Refresh Vehicle Data, Flash Lights, Honk Horn, Lower/Raise Windows, Open/Close Boot |
| Image | Vehicle Image (falls back to the Deepal logo when the picture is unavailable) |

VIN is used as the device serial number. An OTA status sensor is created where the car provides one. Remaining charge time is available both as minutes and as an `H:MM` sensor for dashboards.

## Known Limitations

- **E07:** No remote controls. The app sends them over a separate MQTT broker that is not implemented. Tyre pressures, outside temperature and humidity are not mapped yet, and the charging-state mapping is inferred from one car's report.
- **S05:** The MQTT telemetry changes (including the charging-state mapping), the wake and the lock/window/boot commands in this fork have not been tested on a real S05. The command protocol comes from [kobizz/ha-deepal](https://github.com/kobizz/ha-deepal), validated there on an Israel-market S05.
- **S05 charge schedule (BEV only, opt-in):** also untested on a real S05. Needs a plan already set in the official app before Home Assistant can read or change it, same limitation as the S07. Not implemented for the S05 PHEV, whose schedule plan behaves differently (reverse-engineered by [Sunek0/ha-deepal-alternative](https://github.com/Sunek0/ha-deepal-alternative), MIT).
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

### Coming from danperks/ha-deepal?

This fork is built on [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (see [About This Fork](#about-this-fork)). I started from it because it already had account login, instead of capturing cookies and tokens as my original integration did, and remote commands, instead of read-only data. I kept the same integration name (`deepal`) so anyone already on this fork keeps their setup and history when they upgrade. The catch is that the two cannot be installed side by side. On Home Assistant 2026.11 and newer the Marketplace refuses to install this repository over the original, with a message like "The deepal directory belongs to danperks/ha-deepal".

There are two ways round it.

> [!CAUTION]
> Take a backup first either way.

- **Start clean (the route the Marketplace itself asks for, recommended).** Delete the Deepal entry under **Settings -> Devices & services**, uninstall danperks/ha-deepal, install this repository, then set the integration up again. You will need to sign in again.
- **Replace the files by hand.** Download the source of the release you want, copy its `custom_components/deepal` folder over the one in your `config` folder (File editor, Samba or SSH) and restart. This keeps the existing entry. It is **not tested** on the 2026.11 Marketplace, which may still list the old repository as the owner.

The Marketplace warns that uninstalling removes the integration's devices and entities. Your recorded history should stay in the database. Once you set the integration up again, any entity that comes back with the same ID picks its history up again, and automations and dashboards that use it work again. Some entity IDs will differ from the original, so expect to fix a few. [This page](docs/migrating-from-danperks.md) lists every entity that was renamed. Per-entity settings such as renames, areas and labels are lost.

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
- A state change that both starts and ends between two polls (for example a quick unlock-and-lock) can be missed entirely. If something looks wrong only briefly, check whether it could have happened and reverted inside one polling interval before reporting it as a bug.
- After a command is accepted, the integration polls for the command result and refreshed vehicle state. It stops waiting once the cloud reports success, asking the car for fresh data once.
- If the account is used elsewhere, Home Assistant may need reauthentication.
- Developer notes on what the official app reveals about the E07 (SDA) interface: [docs/sda-app-findings.md](docs/sda-app-findings.md). Names only, unverified.
- Want your charging status on your Lock Screen (iOS Live Activities or Android Live Updates)? [docs/live-activities.md](docs/live-activities.md) has an automation that does it with just the official Home Assistant Companion app, no other integration needed.
- Looking for ideas for alerts (low tyre pressure, a door left open, lights left on, lost cloud connection...)? [docs/example-automations.md](docs/example-automations.md) has several, built on this integration's own entities.

## Credits

- [danperks/ha-deepal](https://github.com/danperks/ha-deepal) for the base integration, and for the seat and steering-wheel control requests and the Spain, Italy and Netherlands regions.
- [kobizz/ha-deepal](https://github.com/kobizz/ha-deepal) for the S05 MQTT command protocol.
- [Sunek0/ha-deepal-alternative](https://github.com/Sunek0/ha-deepal-alternative) (MIT) for the E07 SDA request shape and signal mapping, S05 payload key names, and the ideas behind diagnostics, the wake, the image fallback and the `H:MM` sensor. See [NOTICE.md](NOTICE.md).
- [DylanTusler/ha-deepal](https://github.com/DylanTusler/ha-deepal) for Australia region support.
- @timalpipo for testing on a live AU E07.

## Disclaimer

This is an independent project. It is not affiliated with, authorized by, endorsed by, or in any way officially connected with Changan Automobile Co., Ltd., Deepal, or any of their subsidiaries. Any trademarks mentioned are the property of their respective owners.

> [!WARNING]
> **Unofficial access.** It was built by reverse engineering how the Deepal app talks to Changan's servers. It does not use a published API. Changan or Deepal can change that at any time, with no warning and no migration path.

- **Terms of service.** Using it may breach the Deepal terms of service in some regions, and could lead to your account being limited or blocked. Consider using a secondary account that has been given access to your car, not your main one.
- **It controls a real car.** Commands such as lock, unlock, start climate and start charging act on your actual vehicle. You are responsible for how you use them, and for automations you build on them. Do not rely on this for anything safety critical.
- **Your credentials.** Sign-in tokens are stored in your Home Assistant configuration. Protect your Home Assistant backups and access accordingly.
- **No warranty and no support from Changan or Deepal.** Use it at your own risk. It is provided as is, as set out in the licence. The authors are not responsible for any consequences of using it, including vehicle malfunctions, warranty implications or account restrictions. **Please do not contact Changan, Deepal or your dealer for help with this integration**; open an issue here instead.

This is also early reverse-engineering work. Expect breaking changes, incomplete model support, and occasional cloud API/session issues. There is no official Home Assistant integration for Deepal at the time of writing; this project exists to fill that gap.
