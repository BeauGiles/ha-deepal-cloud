# Lock Screen charging status (iOS Live Activities / Android Live Updates)

An automation that puts your car's charging status on the Lock Screen, using
nothing but the entities this integration already creates and the official
Home Assistant Companion app. No extra integration, card or dashboard package
is needed, only the free Companion app and a notify target.

Home Assistant's `live_update: true` works the same way on both platforms
from one automation: on iOS it's a Live Activity, on Android 16+ it's a Live
Update. The automation below targets both; see [Platform
differences](#platform-differences) for the couple of fields that aren't
shared.

## What you get

A persistent update while plugged in, showing state of charge and a
countdown to the charge limit. It updates silently every 5 minutes and on
every state-of-charge change, and becomes an audible alert once the car
reports **Charge Complete** or stops charging while still plugged in. It
clears itself 30 minutes after finishing, or as soon as you unplug.

This reads the car's own sensors, so it works the same for an S07, S05 or
E07, as long as the entities below exist for your vehicle.

## Requirements

- The Home Assistant Companion app, with notifications enabled, on the
  phone(s) you want this on. iOS needs 17.2 or newer for Live Activities;
  Android needs 16 or newer for Live Updates. Either way, Home Assistant Core
  needs to be 2026.7.0 or newer.
- A notify target for your phone. The examples below call `notify.my_phone`;
  use your own `notify.mobile_app_<device>`, or a [notify
  group](https://www.home-assistant.io/integrations/group/#notify-groups) if
  more than one person should see it.
- Your vehicle's entities, with whatever prefix Home Assistant gave them
  (shown here as `<car>`, for example `sensor.<car>_charge_status`). Find
  yours under **Settings -> Devices & services -> Deepal -> Entities**.

## Entities this automation reads

| Role | Entity |
|---|---|
| Charge status | `sensor.<car>_charge_status` |
| Charging cable plugged in | `binary_sensor.<car>_charging_cable` |
| State of charge | `sensor.<car>_state_of_charge` |
| Remaining charge time | `sensor.<car>_remaining_charge_time` |
| Charge limit | `number.<car>_charge_limit` |

## The automation

Replace `<car>` with your entity prefix and `notify.my_phone` with your own
notify target, then paste this into **Settings -> Automations -> Add
automation -> Edit in YAML**.

```yaml
alias: Live Activity - Charging
description: >-
  Single owner of the charging live activity (tag car-charging). Refreshes on
  state-of-charge/ETA changes and every 5 min. Refreshes (including the
  start) are silent; only Charged (finished) and Paused (stopped) are
  audible, shown after 2 min stable because the car can flap between
  Charging / Charge Complete / Not Charging for a few seconds. Keeps Charged
  for 30 min, clears on unplug.
triggers:
  - trigger: state
    entity_id: sensor.<car>_charge_status
    to: Charging
    id: start
  - trigger: state
    entity_id: sensor.<car>_charge_status
    to: Not Charging
    for: "00:02:00"
    id: stopped
  - trigger: state
    entity_id: sensor.<car>_charge_status
    to: Charge Complete
    for: "00:02:00"
    id: finished
  - trigger: state
    entity_id: sensor.<car>_charge_status
    to: Charge Complete
    for: "00:30:00"
    id: expire
  - trigger: state
    entity_id: binary_sensor.<car>_charging_cable
    to: "off"
    id: unplugged
  - trigger: time_pattern
    minutes: /5
    id: update
  - trigger: state
    entity_id:
      - sensor.<car>_state_of_charge
      - sensor.<car>_remaining_charge_time
    id: soc
actions:
  - choose:
      - alias: Clear when unplugged or 30 min after charged
        conditions:
          - condition: trigger
            id: [unplugged, expire]
        sequence:
          - action: notify.my_phone
            data:
              message: clear_notification
              data:
                tag: car-charging
      - alias: Charged (finished or target reached, still plugged in)
        conditions:
          - condition: trigger
            id: finished
          - condition: state
            entity_id: sensor.<car>_charge_status
            state: Charge Complete
          - condition: state
            entity_id: binary_sensor.<car>_charging_cable
            state: "on"
        sequence:
          - variables:
              soc: "{{ states('sensor.<car>_state_of_charge') | float(0) | round(0) | int }}"
          - action: notify.my_phone
            data:
              title: Your car
              message: "Charged · {{ soc }}%"
              data:
                tag: car-charging
                live_update: true
                critical_text: "{{ soc }}%"
                progress: "{{ soc }}"
                progress_max: 100
                notification_icon: mdi:battery-check
                notification_icon_color: "#4CAF50"
                progress_bar_color: "#4CAF50"
                color: "#4CAF50"
                silent: false
                alert_once: false
      - alias: Paused (stopped but still plugged in)
        conditions:
          - condition: trigger
            id: stopped
          - condition: state
            entity_id: sensor.<car>_charge_status
            state: Not Charging
          - condition: state
            entity_id: binary_sensor.<car>_charging_cable
            state: "on"
        sequence:
          - variables:
              soc: "{{ states('sensor.<car>_state_of_charge') | float(0) | round(0) | int }}"
              target: "{{ states('number.<car>_charge_limit') | float(100) | round(0) | int }}"
          - action: notify.my_phone
            data:
              title: Your car
              message: "Paused · plugged in · target {{ target }}%"
              data:
                tag: car-charging
                live_update: true
                critical_text: "{{ soc }}%"
                progress: "{{ soc }}"
                progress_max: 100
                notification_icon: mdi:ev-plug-type2
                notification_icon_color: "#ECECE7"
                progress_bar_color: "#ECECE7"
                color: "#ECECE7"
                silent: false
                alert_once: false
  default:
    - alias: Let state-of-charge, ETA and status sensors settle together
      delay: "00:00:05"
    - variables:
        soc: "{{ states('sensor.<car>_state_of_charge') | float(0) | round(0) | int }}"
        mins: "{{ states('sensor.<car>_remaining_charge_time') | float(0) | round(0) | int }}"
        finish: "{{ ((now().timestamp() + mins * 60) | int) if mins > 0 else 0 }}"
        target: "{{ states('number.<car>_charge_limit') | float(100) | round(0) | int }}"
    - if:
        - condition: state
          entity_id: sensor.<car>_charge_status
          state: Charging
      then:
        - action: notify.my_phone
          data:
            title: Your car
            message: "Charging · target {{ target }}%"
            data:
              tag: car-charging
              live_update: true
              critical_text: "{{ soc }}%"
              progress: "{{ soc }}"
              progress_max: 100
              chronometer: "{{ mins > 0 }}"
              when: "{{ finish }}"
              when_relative: false
              notification_icon: mdi:ev-station
              notification_icon_color: "#4CAF50"
              color: "#4CAF50"
              silent: true
              alert_once: true
    - alias: Refresh Charged when state-of-charge/ETA arrives late
      if:
        - condition: state
          entity_id: sensor.<car>_charge_status
          state: Charge Complete
        - condition: state
          entity_id: binary_sensor.<car>_charging_cable
          state: "on"
        - condition: trigger
          id: soc
      then:
        - action: notify.my_phone
          data:
            title: Your car
            message: "Charged · {{ soc }}%"
            data:
              tag: car-charging
              live_update: true
              critical_text: "{{ soc }}%"
              progress: "{{ soc }}"
              progress_max: 100
              notification_icon: mdi:battery-check
              notification_icon_color: "#4CAF50"
              color: "#4CAF50"
              silent: true
              alert_once: true
mode: restart
```

## Notes

- **`live_update: true`** is what turns a notification into a Live Activity
  (iOS) or Live Update (Android) instead of a banner; `silent: true` /
  `alert_once: true` on the refreshes stop every 5-minute tick from alerting
  you, while the start, finish and pause notifications stay audible on both
  platforms.
- **The 2-minute debounce** on the `Not Charging` and `Charge Complete`
  triggers exists because the cloud can report a brief wrong status while the
  car and charger renegotiate. Without it you can get a false "Paused" alert
  seconds before the car goes back to actually charging.
- **`tag`** is what Home Assistant uses to update an existing Live Activity /
  Live Update in place instead of starting a new one, and to clear it later
  with `clear_notification`. Keep each automation's tag unique if you add
  more of these for other things.
- **`title`** is required on Android for a notification to become a Live
  Update at all; without it, Android posts a plain banner instead. This
  automation always sets one, so that isn't something you need to add.
- This was built and verified running on a real S07, on iOS. The Android
  side follows the Companion app's own documented behaviour below but hasn't
  been checked on a real Android phone.

## Platform differences

Most fields behave the same on both platforms (`live_update`, `tag`,
`title`, `message`, `progress`/`progress_max`, `chronometer`/`when`/
`when_relative`, `notification_icon` and `clear_notification`). Two pairs
don't, and the automation above sets both sides of each pair so it behaves
correctly either way:

- **Colour:** `notification_icon_color` and `progress_bar_color` are iOS
  only. Android's equivalent is the single key `color`. The automation sets
  all three to the same value, so iOS gets its icon/progress-bar colour and
  Android gets its badge colour from the same line.
- **Quiet refreshes:** `silent` is iOS only ("an update arrives without a
  sound... has no effect when starting the activity"). Android's equivalent
  is `alert_once` ("plays sound or vibration only once"), not `silent`
  itself — setting only `silent: true` has no effect on Android, so the
  5-minute refreshes could alert every time instead of staying quiet. The
  automation sets both keys together wherever it previously set `silent`
  alone.

Reference: the Companion app's own [Live Activities and Live
Updates](https://companion.home-assistant.io/docs/notifications/live-activities/)
page documents every field and which platform(s) it applies to.

## What about a climate / pre-conditioning Live Activity?

A simple version of this, triggered directly off `climate.<car>_cabin_climate`
turning on, does not work: that entity reflects the cabin climate running for
*any* reason, including the car's own climate once you start driving, not
just a climate session you started remotely. A naive automation fires the
Live Activity every time you get in and drive off, not only when you
pre-conditioned the car before getting in.

A correct version needs to track whether *you* (or a schedule) started the
session, separately from the entity simply being on, and needs to notice when
the car starts moving so it stops treating a drive as a pre-conditioning
session. [rmxs/deepal-S05-Companion's preconditioning
feature](https://github.com/rmxs/deepal-S05-Companion/blob/main/docs/PRECONDITIONING.md)
already does this: it only manages a session it started itself (by your
button press or by one of its own schedules), confirms the result against a
fresh read of the car rather than trusting the request alone, and explicitly
hands control back the moment the car is driven, rather than inferring
"preconditioning" from the climate state alone. It's worth reading as a
reference for how to do this correctly, even if you don't install it.

**It will not work with this fork, though.** Companion is built specifically
against [Sunek0/ha-deepal-alternative](https://github.com/Sunek0/ha-deepal-alternative)'s
own entity keys (for example its battery sensor's key is `battery_level`,
where this fork's is `soc`), and it looks for those keys when you try to add
your car. Installing it here won't find your vehicle at setup.
