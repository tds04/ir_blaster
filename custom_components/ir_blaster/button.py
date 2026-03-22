"""Button platform for IR Blaster."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.button import ButtonEntity
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
    async_add_entities([
        IRStudyOnButton(hass, entry, topic),
        IRStudyOffButton(hass, entry, topic),
    ])


class IRBaseButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass, entry, topic):
        self._hass = hass
        self._entry = entry
        self._topic = topic

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._topic)},
            "name": self._entry.data.get("device_name", "IR Blaster"),
            "manufacturer": "Tuya",
            "model": "IRREMOTEWFBK",
        }


class IRStudyOnButton(IRBaseButton):
    def __init__(self, hass, entry, topic):
        super().__init__(hass, entry, topic)
        self._attr_name = "Study On"
        self._attr_unique_id = f"{DOMAIN}_{topic}_study_on"
        self._attr_icon = "mdi:remote"

    async def async_press(self):
        await mqtt.async_publish(
            self._hass,
            TOPIC_SEND.format(topic=self._topic),
            PKT_STUDY_ON,
        )


class IRStudyOffButton(IRBaseButton):
    def __init__(self, hass, entry, topic):
        super().__init__(hass, entry, topic)
        self._attr_name = "Study Off"
        self._attr_unique_id = f"{DOMAIN}_{topic}_study_off"
        self._attr_icon = "mdi:remote-off"

    async def async_press(self):
        await mqtt.async_publish(
            self._hass,
            TOPIC_SEND.format(topic=self._topic),
            PKT_STUDY_OFF,
        )
