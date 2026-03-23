"""Text platform for IR Blaster — send raw hex codes via MQTT."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_TOPIC, TOPIC_SEND, PKT_SEND_IR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    topic = entry.data[CONF_TOPIC]
    async_add_entities([IRSendCodeText(hass, entry, topic)])


class IRSendCodeText(TextEntity):
    """Text entity — write a hex code to send it via MQTT."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:remote"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 500
    _attr_should_poll = False

    def __init__(self, hass, entry, topic):
        self._hass = hass
        self._entry = entry
        self._topic = topic
        self._attr_name = "Send Code"
        self._attr_unique_id = f"{DOMAIN}_{topic}_send_code"
        self._attr_native_value = ""

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._topic)},
            "name": self._entry.data.get("device_name", "IR Blaster"),
            "manufacturer": "Tuya",
            "model": "IRREMOTEWFBK",
        }

    async def async_set_value(self, value: str) -> None:
        """Send the hex code via MQTT."""
        if not value:
            return
        # Strip 0x prefix if present
        if value.startswith("0x"):
            value = value[2:]
        self._attr_native_value = value
        self.async_write_ha_state()
        payload = f"{PKT_SEND_IR}{value}"
        await mqtt.async_publish(
            self._hass,
            TOPIC_SEND.format(topic=self._topic),
            payload,
        )
        _LOGGER.debug("IR code sent: %s", payload)
