"""Button platform for IR Blaster.

Two button types:
  - SendLastCapturedButton: fires whatever the sensor last captured (test/debug)
  - IRCodeButton: one per saved named code, fires that specific code
"""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_TOPIC,
    CONF_SAVED_CODES,
    TOPIC_SEND,
    PKT_SEND_IR,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    topic = entry.data[CONF_TOPIC]

    entities: list[ButtonEntity] = []

    # Always add the "Send Last Captured" test button
    entities.append(SendLastCapturedButton(hass, entry, topic))

    # Add one button per saved code (from options)
    saved_codes: dict = entry.options.get(CONF_SAVED_CODES, {})
    for name, code in saved_codes.items():
        entities.append(IRCodeButton(hass, entry, topic, name, code))

    async_add_entities(entities)


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


class SendLastCapturedButton(IRBaseButton):
    """Button that resends whatever the sensor last captured."""

    def __init__(self, hass, entry, topic):
        super().__init__(hass, entry, topic)
        self._attr_name = "Send Last Captured"
        self._attr_unique_id = f"{DOMAIN}_{topic}_send_last_captured"
        self._attr_icon = "mdi:remote"

    async def async_press(self) -> None:
        sensor_entity_id = f"sensor.{self._entry.data.get('device_name', 'IR Blaster').lower().replace(' ', '_')}_last_captured_code"
        code = self._hass.states.get(sensor_entity_id)
        if code is None or code.state in ("unknown", "unavailable", ""):
            _LOGGER.warning("Send Last Captured: no code available in sensor %s", sensor_entity_id)
            return
        raw = code.state
        if raw.startswith("0x"):
            raw = raw[2:]
        payload = f"{PKT_SEND_IR}{raw}"
        await mqtt.async_publish(
            self._hass,
            TOPIC_SEND.format(topic=self._topic),
            payload,
        )
        _LOGGER.debug("Send Last Captured fired: %s", payload)


class IRCodeButton(IRBaseButton):
    """Button that sends a specific saved IR code."""

    def __init__(self, hass, entry, topic, name: str, code: str):
        super().__init__(hass, entry, topic)
        self._code_name = name
        self._code = code
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{topic}_code_{name.lower().replace(' ', '_')}"
        self._attr_icon = "mdi:remote"

    async def async_press(self) -> None:
        code = self._code
        if code.startswith("0x"):
            code = code[2:]
        payload = f"{PKT_SEND_IR}{code}"
        await mqtt.async_publish(
            self._hass,
            TOPIC_SEND.format(topic=self._topic),
            payload,
        )
        _LOGGER.debug("IR code button '%s' fired: %s", self._code_name, payload)
