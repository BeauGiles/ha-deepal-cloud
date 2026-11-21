# Example automations

A handful of alerts people commonly want, built as plain Home Assistant
automations on this integration's own entities. No extra integration, card or
dashboard is needed.

Replace `<car>` with your entity prefix (**Settings -> Devices & services ->
Deepal -> Entities**) and `notify.my_phone` with your own notify target or a
[notify group](https://www.home-assistant.io/integrations/group/#notify-groups).
Not every entity below exists on every model; skip an automation if yours is
missing.

## A reliable "parked" condition

> [!TIP]
> The car does not switch itself off when you walk away, so `power_status`
> (values `Idle` or `Drive`) often stays **Drive** long after you've left.
> Waiting for `Idle` alone means some of these alerts never fire. The fix:
> treat the car as parked when `power_status` is `Idle`, **or** it's `Drive`
> but the odometer hasn't changed for a few minutes (it keeps changing while
> you actually drive).

```yaml
condition: or
conditions:
  - condition: state
    entity_id: sensor.<car>_power_status
    state: Idle
  - condition: template
    value_template: >-
      {{ states('sensor.<car>_power_status') == 'Drive' and
         (now() - states.sensor.<car>_total_mileage.last_changed).total_seconds() > 300 }}
```

Every automation below that should stay quiet while you're driving uses this
condition block. Adjust the 5 minutes to taste; much shorter and a stop at
traffic lights can trigger it.

## Lost cloud connection

```yaml
alias: Alert - car offline
triggers:
  - trigger: state
    entity_id: binary_sensor.<car>_connect_status
    to: "off"
    for: "00:15:00"
actions:
  - action: notify.my_phone
    data:
      title: Your car
      message: Home Assistant has not heard from the cloud in 15 minutes.
mode: single
```

A cloud hiccup of a few minutes is normal; the delay keeps this from firing on
every blip.

## Door, window or boot left open

```yaml
alias: Alert - car left open
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.<car>_any_door
      - binary_sensor.<car>_any_window
      - binary_sensor.<car>_trunk
    to: "on"
    for: "00:10:00"
conditions:
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.<car>_power_status
        state: Idle
      - condition: template
        value_template: >-
          {{ states('sensor.<car>_power_status') == 'Drive' and
             (now() - states.sensor.<car>_total_mileage.last_changed).total_seconds() > 300 }}
actions:
  - action: notify.my_phone
    data:
      title: Your car
      message: A door, window or the boot has been open for 10 minutes.
mode: single
```

## Lights left on

```yaml
alias: Alert - car lights left on
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.<car>_position_lamp
      - binary_sensor.<car>_low_beam
      - binary_sensor.<car>_high_beam
    to: "on"
    for: "00:05:00"
conditions:
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.<car>_power_status
        state: Idle
      - condition: template
        value_template: >-
          {{ states('sensor.<car>_power_status') == 'Drive' and
             (now() - states.sensor.<car>_total_mileage.last_changed).total_seconds() > 300 }}
actions:
  - action: notify.my_phone
    data:
      title: Your car
      message: The lights have been on for 5 minutes while parked.
mode: single
```

## Seat heater or ventilation left on

```yaml
alias: Alert - seat heater or ventilation left on
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.<car>_driver_seat_heater_on
      - binary_sensor.<car>_front_passenger_seat_heater_on
      - binary_sensor.<car>_driver_seat_ventilation_on
      - binary_sensor.<car>_front_passenger_seat_ventilation_on
    to: "on"
    for: "00:15:00"
conditions:
  - condition: state
    entity_id: sensor.<car>_power_status
    state: Idle
actions:
  - action: notify.my_phone
    data:
      title: Your car
      message: A seat heater or fan has been left on for 15 minutes.
mode: single
```

> [!NOTE]
> This one checks `power_status` alone, not the full parked condition above:
> seat heating only matters once the car is actually switched off, and the
> odometer side of the parked check would let it fire while briefly stopped.

## Tyre pressure warning

On an S05 reporting over MQTT, the car itself sends a per-wheel
pressure-warning flag, exposed as four binary sensors:
`binary_sensor.<car>_tire_front_left_warning`,
`..._tire_front_right_warning`, `..._tire_rear_left_warning` and
`..._tire_rear_right_warning`. If yours exist, use them directly instead of
picking your own threshold:

```yaml
alias: Alert - low tyre pressure
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.<car>_tire_front_left_warning
      - binary_sensor.<car>_tire_front_right_warning
      - binary_sensor.<car>_tire_rear_left_warning
      - binary_sensor.<car>_tire_rear_right_warning
    to: "on"
actions:
  - action: notify.my_phone
    data:
      title: Your car
      message: "{{ trigger.to_state.name }} warning from the car."
mode: queued
```

> [!NOTE]
> S07 and E07 cars have no such flag (as far as this integration can tell), so
> there's nothing to turn on for them yet. The workaround below, built on the
> four raw pressure sensors with no custom code, is actually running on a
> real S07:

1. A **min/max helper** (type: minimum) over the four
   `sensor.<car>_tire_*_pressure` entities, giving one "lowest tyre pressure"
   sensor.
2. A **threshold helper** on that sensor: below 230 kPa, with 10 kPa
   hysteresis, so it only clears once pressure is back above 240 kPa. This is
   the one real number in use, not a guess; your car's placard pressure will
   differ.
3. An automation on the threshold helper's resulting `binary_sensor`, firing
   after it's stayed on for a while (10 minutes in the running example) and
   naming the specific tyre or tyres currently below the limit.

Set up under **Settings -> Devices & services -> Helpers -> Add helper**, no
YAML needed for the first two. It gives you one on/off sensor instead of four
numeric ones to watch, and it names the actual low tyre from the automation's
own template rather than from the helper.

## Low battery

```yaml
alias: Alert - low battery
triggers:
  - trigger: numeric_state
    entity_id: sensor.<car>_state_of_charge
    below: 20
conditions:
  - condition: state
    entity_id: binary_sensor.<car>_charging_cable
    state: "off"
actions:
  - action: notify.my_phone
    data:
      title: Your car
      message: "Battery is at {{ states('sensor.<car>_state_of_charge') }}%."
mode: single
```

The condition keeps this quiet while you're already charging through that
level.

## Charging complete or interrupted

See [docs/live-activities.md](live-activities.md) for a Lock Screen Live
Activity that covers charging start, pause and completion with a running
countdown. These alerts are a plainer, banner-notification alternative if you
don't want a Live Activity:

```yaml
alias: Alert - charging finished or stopped early
triggers:
  - trigger: state
    entity_id: sensor.<car>_charge_status
    to: Charge Complete
    for: "00:02:00"
    id: finished
  - trigger: state
    entity_id: sensor.<car>_charge_status
    to: Not Charging
    for: "00:02:00"
    id: stopped
conditions:
  - condition: state
    entity_id: binary_sensor.<car>_charging_cable
    state: "on"
actions:
  - action: notify.my_phone
    data:
      title: Your car
      message: >-
        {{ 'Charging complete' if trigger.id == 'finished' else 'Charging stopped early' }}
        at {{ states('sensor.<car>_state_of_charge') }}%.
mode: single
```

The 2-minute delay matches the one in the Live Activity automation, for the
same reason: the cloud can briefly report the wrong status while the car and
charger renegotiate.
