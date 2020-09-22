## Native cover control
If you want to set up cover control as (11) HomeAssistant entities, here is how to!

### Set up input_booleans for state
Input_booleans showing whether cover is opening/closing, with the possibility to listen to changes

~~~
- covers_closing:
  name: Covers are closing
  initial: off
  icon: mdi:blinds

- covers_opening:
  name: Covers are opening
  initial: off
  icon: mdi:blinds-open
~~~

### Listen to remote control
The following 2 automations are configured to listen to open/close events from deconz and toggle an input_boolean each to indicate whether covers are opening/closing

~~~
- alias: Open covers when pushing open button
  trigger:
    platform: event
    event_type: deconz_event    
    event_data:
      id: tradfri_open_close_remote
      event: 1002
  action:
    - service: input_boolean.toggle
      data:
        entity_id: input_boolean.covers_opening

- alias: Close covers when pushing close button
  trigger:
    platform: event
    event_type: deconz_event
    event_data:
      id: tradfri_open_close_remote
      event: 2002
  action:
    - service: input_boolean.toggle
      data:
        entity_id: input_boolean.covers_closing
~~~

### Cover position
State template to calculate whether the cover is open or closed based on the new min/max (not 0 and 100 percent)

~~~
- platform: template
  sensors:
    cover_position:
      friendly_name: "Cover state"
      value_template: >-
        {% if state_attr('cover.my_cover', 'current_position') > 85 %}
          open
        {% elif state_attr('cover.my_cover', 'current_position') < 32 %}
          closed
        {% else %}
          partially open
        {% endif %}
      icon_template: >-
        {% if state_attr('cover.my_cover', 'current_position') > 85 %}
          mdi:blinds-open
        {% else %}
          mdi:blinds
        {% endif %}
~~~

### Opening the cover
We now have a solid foundation to open the cover. `input_boolean.covers_opening`: true indicates that the covers should open, `input_boolean.covers_opening`: false indicates that the covers should stop (opening). When `state.cover_position` goes to `open`, it indicates that the input_boolean should be reset since the covers are already in an open state.

~~~
- alias: 'Open covers'
  trigger:
    - platform: state
      entity_id: input_boolean.covers_opening
      to: 'on'
  action:
    - service: cover.set_cover_position
      data:
        entity_id: cover.my_cover
        position: 90

- alias: 'Stop open covers'
  trigger:
    - platform: state
      entity_id: input_boolean.covers_opening
      to: 'off'
  action:
     - service: cover.stop_cover
       entity_id: cover.my_cover

- alias: 'Reset open covers boolean'
  trigger:
    - platform: state
      entity_id: sensor.cover_position
      to: 'open'
  action:
     - service: input_boolean.turn_off
       entity_id: input_boolean.covers_opening
~~~ 

### Closing the cover
In the same way we can open the cover, we can also close it

~~~
- alias: 'Close covers'
  trigger:
    - platform: state
      entity_id: input_boolean.covers_closing
      to: 'on'
  action:
    - service: cover.set_cover_position
      data:
        entity_id: cover.my_cover
        position: 30

- alias: 'Stop close covers'
  trigger:
    - platform: state
      entity_id: input_boolean.covers_closing
      to: 'off'
  action:
     - service: cover.stop_cover
       entity_id: cover.my_cover

- alias: 'Reset close covers boolean'
  trigger:
    - platform: state
      entity_id: sensor.cover_position
      to: 'close'
  action:
     - service: input_boolean.turn_off
       entity_id: input_boolean.covers_closing
~~~ 