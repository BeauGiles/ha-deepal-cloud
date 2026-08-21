# Changan Deepal Cloud for Home Assistant

<p align="center">
  <img src="icon.png" alt="Deepal logo" width="160">
</p>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Custom Home Assistant integration for the Changan Deepal cloud API.

This integration was built against a UK-market Deepal S07 and a Portugal-market Deepal S05. S07 support includes telemetry and remote controls when enabled. S05 support is currently **read-only** via the app's MQTT telemetry path.

## About This Fork

This repo is rebased on [danperks/ha-deepal](https://github.com/danperks/ha-deepal) (via [DylanTusler's fork](https://github.com/DylanTusler/ha-deepal)), which brought account-based login, full remote vehicle control, and Deepal S05 support — a big step up from the [earlier version of this integration](https://github.com/BeauGiles/ha-deepal), which was read-only and required manually capturing tokens with a proxy tool.
Credit to danperks and DylanTusler for that work.

On top of that base, this fork:

- Fixes incorrect logic for charge-gun connection status, the "Charging" binary sensor, and "Charge Schedule Enabled" (all three were reading the wrong values)
- Restores features from the original version of this integration that the upstream fork didn't carry over: the vehicle image entity, VIN as the device serial number, and the OTA firmware status sensor
- Renames entities to AU/UK conventions throughout (Odometer, Tyre, Boot) with keys aligned to the real Deepal API fields
- Adds icons and consistent Title Case naming across every entity

Full details are in [CHANGELOG.md](CHANGELOG.md).

**Note:** because entity keys changed from the upstream fork, upgrading will create new entities rather than renaming existing ones in place — you'll want to re-add any dashboard cards or automations that reference the old entity IDs, and remove the old (orphaned) entities from the entity registry.

## Important Warnings

- Use this integration at your own risk.
- This is an unofficial integration and is not endorsed by Changan or Deepal.
- Remote commands can affect the vehicle. Make sure it is safe before using controls such as locks, windows, boot, climate, lights, or horn.
- This integration cannot be used to drive the car. It does not implement the BLE/digital key path required for drive authorization.
- Logging in through this integration can log you out of the official Deepal app or other devices. Likewise, logging back into the official app may invalidate the Home Assistant session.

## Supported Vehicle

- Deepal S07: telemetry and optional remote controls.
- Deepal S05: read-only telemetry.
- Login regions: United Kingdom, Israel, Portugal, Australia

## Current Features

- Email-code and phone/SMS login flows through Home Assistant.
- Native Home Assistant reauthentication/repair flow when the cloud session is invalidated.
- Vehicle telemetry sensors and binary sensors, with entity keys matching the real Deepal API fields and friendly display names.
- Vehicle image entity showing the car's photo, plus VIN as the device serial number.
- OTA firmware update status sensor.
- Manual refresh button.
- Cabin climate entity. S05 is state-only in this version.
- S07 charge limit and charging schedule controls.
- S07 door lock control.
- S07 window and boot cover controls.
- S07 flash lights and horn buttons.

S05 controls are still being reverse engineered and are intentionally not exposed in this read-only release.

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

[![Open your Home Assistant instance and start setting up Changan Deepal Cloud.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=deepal)

You can also configure it manually from **Settings -> Devices & services -> Add integration**, then search for **Changan Deepal Cloud**.

During setup, choose the same login method you use in the official Deepal app. If phone/SMS login says the account is not registered, try email-code login instead. S07 users can choose whether to enable remote commands; remote commands require the same control PIN used by the official Deepal app. S05 entries are created read-only.

## Notes

- The integration polls cached cloud status every minute. S07 can also ask for refreshed vehicle data every 5 minutes when remote commands are enabled. S05 reads refreshed MQTT telemetry without exposing vehicle controls.
- After a command is accepted, the integration briefly polls for command result and refreshed vehicle state so Home Assistant updates faster than the normal polling interval.
- If the account is used elsewhere, Home Assistant may need reauthentication.

## Development Status

This is early reverse-engineering work. Expect breaking changes, incomplete model support, and occasional cloud API/session issues.
