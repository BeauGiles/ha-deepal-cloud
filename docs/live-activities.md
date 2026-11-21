# iOS Live Activities for your car

An automation that puts your car's charging status on the iOS Lock Screen,
using nothing but the entities this integration already creates and the
official Home Assistant Companion app. No extra integration, card or
dashboard package is needed, only the free Companion app and a notify
target.

## What you get

A Live Activity while plugged in, showing state of charge and a countdown
to the charge limit. It updates silently every 5 minutes and on every
state-of-charge change, and becomes an audible alert once the car reports
**Charge Complete** or stops charging while still plugged in. It clears
itself 30 minutes after finishing, or as soon as you unplug.

This reads the car's own sensors, so it works the same for an S07, S05 or
E07, as long as the entities below exist for your vehicle.

## Requirements

- The Home Assistant Companion app installed on the phone(s) you want the
  Live Activity on, with notifications enabled. Live Activities themselves
  need iOS 16.1 or newer; the `chronometer` countdown used below needs the
  Companion app's usual minimum supported iOS version.
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
                silent: false
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
                silent: false
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
              silent: true
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
              silent: true
mode: restart
```

## Notes

- **`live_update: true`** is what turns a notification into a Live Activity
  update on the Lock Screen rather than a banner; `silent: true` on the
  refreshes stops every 5-minute tick from alerting you, while the start,
  finish and pause notifications stay audible.
- **The 2-minute debounce** on the `Not Charging` and `Charge Complete`
  triggers exists because the cloud can report a brief wrong status while the
  car and charger renegotiate. Without it you can get a false "Paused" alert
  seconds before the car goes back to actually charging.
- **`tag`** is what Home Assistant uses to update an existing Live Activity in
  place instead of starting a new one, and to clear it later with
  `clear_notification`. Keep each automation's tag unique if you add more Live
  Activities for other things.
- This was built and is running on a real S07.

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
