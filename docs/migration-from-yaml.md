# Existing notifications to re-add

Snapshot of the YAML package removed from `homeassistant-config` on 2026-11-03 (last version: commit `1f02a9b4` and earlier; `packages/notification_lights.yaml`, blueprint `vrykolas/notification.yaml`). Recreate these in the UI. Old model: 8 eighths, importance `critical`/`normal`, rooms from a `rooms` attribute.

New-model suggestion: scope, footprint, priority (unique, lower on top), quiet-hours flag. "Source" is what to enter.

| # | Name | Colour (RGB) | Old placement | New footprint | Scope | Show in quiet hours | Source |
|---|---|---|---|---|---|---|---|
| 1 | Fire | 255,0,0 | whole, critical | whole | house | yes | `binary_sensor.smoke_detectors` on **or** `binary_sensor.kitchen_carbon_monoxide_detector_carbon_monoxide` on |
| 2 | Leak | 0,0,255 | whole, critical | whole | house | yes | any of the 8 leak sensors on (below) |
| 3 | Washing | 0,255,255 | eighth 1 | eighth 1 | house | no | `sensor.washing_machine_machine_state` = `stop` |
| 4 | Drying | 255,120,0 | eighth 2 | eighth 2 | house | no | `sensor.tumble_dryer_machine_state` = `stop` |
| 5 | Fridge | 255,255,255 | eighth 3 | eighth 3 | house | no | `binary_sensor.refrigerator_cooler_door` or `binary_sensor.refrigerator_freezer_door` on, **delay 5 min** |
| 6 | Vacuum | 160,0,255 | eighth 4 | eighth 4 | house | no | `sensor.q5_pro_vacuum_error` or `sensor.q5_pro_dock_error` not in none/ok/unknown/unavailable (template) |
| 7 | Rain | 0,0,255 | eighth 5, per room | eighth 5 | house | no | raining AND an opening open AND someone home (template below), **delay 1 min** |
| 8 | Air | 0,255,0 | eighth 6, per room | eighth 6 | **room**, one per room | no | CO2 > 1200 and room occupied, or mould > 70 while home, **delay 10 min** (template below) |
| 9 | Bins | 255,200,0 | eighth 7 | eighth 7 | house | no | template below |
| 10 | Octoplus | 255,0,255 | eighth 8 | eighth 8 | house | no | `calendar.octopus_energy_a_7d82c42b_octoplus_power_down` on |

Old priority was the row number (1 = on top). Fire and Leak get the top priorities so their whole footprint covers everything else.

## Leak sensors (all `binary_sensor.`, state on)
`bathroom_bath_leak_detector_water_leak`, `bathroom_sink_leak_detector_water_leak`, `kitchen_sink_leak_detector_water_leak`, `kitchen_boiler_leak_detector_water_leak`, `kitchen_dishwasher_leak_detector_water_leak`, `kitchen_washing_machine_leak_detector_water_leak`, `kitchen_tumble_dryer_leak_detector_water_leak`, `kitchen_washer_dryer_drain_leak_detector_water_leak`

## Templates

Rain (new model, house scope; the per-room part is dropped for now):
```
{% set openings = ['binary_sensor.computer_room_main_window_contact',
  'binary_sensor.bedroom_main_window_contact', 'binary_sensor.office_main_window_contact',
  'binary_sensor.living_room_main_window_contact', 'binary_sensor.kitchen_main_window_contact',
  'binary_sensor.bathroom_main_window_contact', 'binary_sensor.patio_door_contact'] %}
{{ states('weather.met_office_rubery') in ['rainy','pouring','lightning-rainy','hail','snowy-rainy']
   and openings | select('is_state','on') | list | count > 0
   and states('zone.home') | int(0) > 0 }}
```

Air, one notification per room (replace ROOM, CO2 and MOLD). Old per-room sensors:
- CO2 (> 1200, room occupied via `binary_sensor.<room>_occupancy_delayed`): bedroom `sensor.bedroom_epl_co2`, computer_room `sensor.computer_room_epl_co2`, dining_room `sensor.dining_room_epl_co2`, kitchen `sensor.kitchen_kitchen_epl_co2`, living_room `sensor.living_room_living_room_epp_co2`, office `sensor.office_epl_co2`.
- Mould (> 70, only while `zone.home` > 0): bedroom `sensor.bedroom_bedroom_environment_sensor_bedroom_mold_indicator`, electronics_room `sensor.electronics_room_mould_indicator`, landing `sensor.landing_landing_temperature_landing_mold_indicator`, living_room `sensor.living_room_living_room_environment_sensor_living_room_mold_indicator`, office `sensor.office_mould_indicator`, toilet `sensor.toilet_toilet_temperature_toilet_mold_indicator`.
```
{{ (states('CO2') | float(0) > 1200 and is_state('binary_sensor.ROOM_occupancy_delayed','on'))
   or (states('MOLD') | float(0) > 70 and states('zone.home') | int(0) > 0) }}
```
(Drop whichever half the room has no sensor for.)

Bins:
```
{{ (states('sensor.garbage_days_2') | int(-1) == 1 or states('sensor.recycling_days_2') | int(-1) == 1)
   and now() >= today_at('18:30') }}
```

## Notification lights (rings)
| Light | Area | Segments | Offset | Quiet at bedtime |
|---|---|---|---|---|
| `light.bedroom_light_bulb_rgb` | bedroom | 26 | 0 | yes |
| `light.dining_room_light_bulb_rgb` | dining_room + kitchen | 26 | 0 (a guess, never calibrated) | no |

Quiet hours entity: `input_boolean.house_bedtime`.

## Gaps to decide when re-adding
- The old dining ring also answered for `kitchen` (open-plan). A light can list several rooms, so add it with rooms dining_room and kitchen.
- Accent LEDs (living room EPP, office tag reader) are no longer supported.
- The old `switch.clear_notifications` becomes the clear-all service/button.
- Untested on hardware: whole-ring (fire/leak) path.
- The live dashboard `dashboard-notifications` (storage mode, not in git) must be removed by hand in HA once the package is gone.
