import asyncio
import logging

import voluptuous as vol

from time import time

from homeassistant.const import (ATTR_ENTITY_ID)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'cover_control'

INTERVAL_NEW_POSITION_CONSIDERS_MOVING = 2

ATTR_SET_POSITION = 'position'

CONF_NAME = 'name'
CONF_COVER = 'cover'
CONF_COVER_POSITION = 'cover_position'
CONF_OPEN = 'open_at'
CONF_CLOSED = 'closed_at'
CONF_OPEN_EVENT = 'open'
CONF_CLOSE_EVENT = 'close'

EVENT_TYPE = 'type'
EVENT_ENTITY = 'entity'
EVENT_DATA = 'data'


SERVICE_OPEN = 'open'
SERVICE_CLOSE = 'close'

PERCENTAGE_VALIDATION = vol.All(
    vol.Coerce(int), vol.Range(min=0, max=100), msg="invalid percentage, must be int between 0 and 100"
)

EVENT_SCHEMA = vol.Schema({
    vol.Optional(EVENT_TYPE, default='deconz_event'): cv.string,
    vol.Optional(EVENT_ENTITY): cv.string,
    vol.Required(EVENT_DATA): cv.string,
})

COVER_CONTROL_CONFIG_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_COVER): cv.entity_id,
    vol.Required(CONF_COVER_POSITION): cv.entity_id,
    vol.Required(CONF_OPEN): PERCENTAGE_VALIDATION,
    vol.Required(CONF_CLOSED): PERCENTAGE_VALIDATION,
    vol.Required(CONF_OPEN_EVENT): EVENT_SCHEMA,
    vol.Required(CONF_CLOSE_EVENT): EVENT_SCHEMA,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [COVER_CONTROL_CONFIG_SCHEMA])
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    entities = []
    
    for conf in config[DOMAIN]:
        entities.append(CoverControlEntity(conf, hass))

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    await component.async_add_entities(entities)

    component.async_register_entity_service(SERVICE_OPEN, {}, 'open_cover')
    component.async_register_entity_service(SERVICE_CLOSE, {}, 'close_cover')

    return True

class CoverControlEntity(Entity):

    def __init__(self, config, hass):
        self._name = config[CONF_NAME] if config.get(CONF_NAME) else config[CONF_COVER].split('.')[1]
        self._cover = config[CONF_COVER]
        self._cover_position = config[CONF_COVER_POSITION]
        self._open_at = config[CONF_OPEN]
        self._closed_at = config[CONF_CLOSED]
        self._position = 0
        self._last_time_moving = 0
        self._is_opening = False
        
        open_event = config[CONF_OPEN_EVENT]
        close_event = config[CONF_CLOSE_EVENT]

        self._listeners = [
            (open_event, self.open_cover),
            (close_event, self.close_cover)
        ]

        self._set_up_listeners(hass, open_event, close_event)


    def _set_up_listeners(self, hass, open_event, close_event):
        unique_event_types = set([open_event[EVENT_TYPE], close_event[EVENT_TYPE]])

        for event_type in unique_event_types:
            hass.bus.async_listen(event_type, self._handle_event)

        async_track_state_change_event(hass, [self._cover_position], self._state_changed)


    def _handle_event(self, call):
        triggering_entity = call.data.get('id')
        event_data = call.data.get('event')

        for (event, callback) in self._listeners:
            if event.get(EVENT_DATA) == str(event_data):
                if (not event.get(EVENT_ENTITY)) or event.get(EVENT_ENTITY) == triggering_entity: # No specific entity or matching
                    async_call_later(self.hass, 0, callback)

    def _state_changed(self, call):
        new_state = call.data.get('new_state')
        if new_state:
            try:
                new_position = float(new_state.state)
                self._is_opening = new_position > self._position
                self._position = new_position
                self._last_time_moving = time()
                async_call_later(self.hass, 0, self.async_update_ha_state)
            except ValueError:
                pass

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._get_state()

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        return {
            CONF_OPEN: str(self._open_at),
            CONF_CLOSED: str(self._closed_at),
            'current_position': str(self._calculate_position()),
            'original_position': str(self._position),
        }

    @property
    def icon(self):
        return 'mdi:blinds-open' if self.state == 'open' else 'mdi:blinds'

    def _calculate_position(self):
        return 100 * (self._position-self._closed_at) / (self._open_at-self._closed_at)

    def _get_state(self):
            return 'open' if (self._position > self._open_at-2 and self._position < self._open_at+2) else 'closed'

    def _is_moving(self):
        return self._last_time_moving + INTERVAL_NEW_POSITION_CONSIDERS_MOVING > time()

    async def open_cover(self, *_):
        if self._is_moving() and self._is_opening:
            await self._stop_covers()
        else:
            await self._set_position(self._open_at)

    async def close_cover(self, *_):
        if self._is_moving() and not self._is_opening:
            await self._stop_covers()
        else:
            await self._set_position(self._closed_at)

    async def _set_position(self, position):
        await self.hass.services.async_call("cover", "set_cover_position", {ATTR_ENTITY_ID: self._cover, ATTR_SET_POSITION: position})

    async def _stop_covers(self):
        await self.hass.services.async_call("cover", "stop_cover", {ATTR_ENTITY_ID: self._cover})
