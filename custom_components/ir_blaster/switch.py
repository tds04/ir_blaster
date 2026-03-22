"""Switch platform for IR Blaster — study mode control."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_TOPIC, TOPIC_SEND, PKT_STUDY_ON, PKT_STUDY_OFF

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    topic = entry.data[CONF_TOPIC]
    async_add_entities([IRStudyModeSwitch(hass, entry, topic)])


class IRStudyModeSwitch(SwitchEntity):
    """Switch to toggle IR study mode."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:remote"
    _attr_should_poll = False

    def __init__(self, hass, entry, topic):
        self._hass = hass
        self._entry = entry
        self._topic = topic
        self._attr_name = "Study Mode"
        self._attr_unique_id = f"{DOMAIN}_{topic}_study_mode"
        self._attr_is_on = False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._topic)},
            "name": self._entry.data.get("device_name", "IR Blaster"),
            "manufacturer": "Tuya",
            "model": "IRREMOTEWFBK",
        }

    async def async_turn_on(self, **kwargs):
        await mqtt.async_publish(
            self._hass,
            TOPIC_SEND.format(topic=self._topic),
            PKT_STUDY_ON,
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await mqtt.async_publish(
            self._hass,
            TOPIC_SEND.format(topic=self._topic),
            PKT_STUDY_OFF,
        )
        self._attr_is_on = False
        self.async_write_ha_state()
