# Alarm Panel Auto Arming

Automatically manage Alarm Control Panel integration

* Switch between `armed_home` and `armed_away` based on time of day
* Automatically re-arm when nobody at home
* Automatically switch off `armed_away` mode when at least one person returns
* Use usual bed-time as alternative to sunrise/sunset
* Allow manual override via remote buttons
* Optional delay on selecting away mode via remote button
* Support for mobile push actionable notifications

## Configure

Switch on module, and add configuration, using appdaemon `apps.yaml`

### Example

``` yaml
alarm_arming:
  module: alarm_arming
  class: AlarmArming
  alarm_panel: alarm_control_panel.home_alarm_control
  # Everything after this is optional

  # Usual bedtime, auto-disarm and night mode at start and day mode or disarm at end
  sleep_start: "21:30:00"
  sleep_end: "06:30:00"
  # When away button pressed, how long to wait until armed, e.g. to lock up and leave
  arm_away_delay: "00:02:00"
  # Should the alarm be disarmed if house occupied and sleep period ended?
  auto_disarm: False
  # For far north/south countries sunrise can be middle of night, so allow override
  sunrise_cutoff: "07:00:00"
  reset_button_device: binary_sensor.zone_control_middle
  away_button_device: binary_sensor.zone_control_up
  vacation_button_device: 
  disarm_button_device: binary_sensor.zone_control_down
  log_level: INFO
  occupants:
    - person.john_doe
    - person.mariam_khan
    - person.junior_doe
  notify:
    common:
      service: apple_devices
      data:
        group: alarm_arming
        actions:
          - action: "ALARM_PANEL_DISARM"
            title: "Disarm Alarm Panel"
            icon: "sfsymbols:bell.slash"
          - action: "ALARM_PANEL_RESET"
            title: "Arm Alarm Panel for at Home"
            icon: "sfsymbols:bell"
          - action: "ALARM_PANEL_AWAY"
            title: "Arm Alarm Panel for Going Away"
            icon: "sfsymbols:airplane"
    quiet:
      data:
        push:
          interruption-level: passive
    normal:
      data:
        push:
          interruption-level: active


```
