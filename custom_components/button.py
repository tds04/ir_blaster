"""Button platform for IR Blaster.

Entities:
  - LearnButton: starts learning session (reads name from CodeNameText first)
  - SendLastButton: resends last captured code (test/debug)
  - IRCodeButton: one per saved named code
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components import mqtt
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_NAME,
    CONF_TOPIC,
    DEFAULT_CODE_NAME_PLACEHOLDER,
    DOMAIN,
    PKT_SEND_IR,
    STATE_ARMED,
    STATE_IDLE,
    STATE_RECEIVED,
    TOPIC_SEND,
)
from .learning import LearnedCode, LearningSession
from .storage import IRBlasterStorage

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    topic = entry.data[CONF_TOPIC]
    storage: IRBlasterStorage = hass.data[DOMAIN][entry.entry_id]["storage"]
    learning_session: LearningSession = hass.data[DOMAIN][entry.entry_id]["learning_session"]

    entities: list[ButtonEntity] = [
        LearnButton(hass, entry, topic, learning_session),
        SendLastButton(hass, entry, topic, learning_session),
    ]

    for code in storage.get_codes():
        entities.append(IRCodeButton(hass, entry, topic, code["id"], code["name"], code["hex"]))

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
            "name": self._entry.data.get(CONF_DEVICE_NAME, "IR Blaster"),
            "manufacturer": "Tuya",
            "model": "IRREMOTEWFBK",
        }


class LearnButton(IRBaseButton):
    """Press to learn a new IR code. Name must be set in Code Name text entity first."""

    def __init__(self, hass, entry, topic, learning_session: LearningSession):
        super().__init__(hass, entry, topic)
        self._learning_session = learning_session
        self._attr_name = "Learn"
        self._attr_unique_id = f"{DOMAIN}_{topic}_learn"
        self._attr_icon = "mdi:remote-tv"
        self._pending_name: str | None = None

    async def async_press(self) -> None:
        # If already armed, ignore
        if self._learning_session.state == STATE_ARMED:
            _LOGGER.info("Learning already in progress")
            return

        # Reset if in a non-idle state
        if self._learning_session.state != STATE_IDLE:
            await self._learning_session.async_clear_pending()

        # Get the code name from the text entity
        text_entity_id = f"text.{self._entry.data.get(CONF_DEVICE_NAME, 'IR Blaster').lower().replace(' ', '_')}_code_name"
        state = self._hass.states.get(text_entity_id)

        name = None
        if state and state.state not in ("", "unavailable", "unknown", DEFAULT_CODE_NAME_PLACEHOLDER):
            name = state.state.strip()

        if not name:
            await self._hass.services.async_call(
                "persistent_notification", "create", {
                    "notification_id": f"ir_blaster_no_name_{self._entry.entry_id}",
                    "title": "IR Blaster — Name Required",
                    "message": "Enter a name in the **Code Name** field before pressing Learn.",
                }
            )
            _LOGGER.warning("Learn pressed but no code name entered")
            return

        # Check for duplicate name
        storage: IRBlasterStorage = self._hass.data[DOMAIN][self._entry.entry_id]["storage"]
        if storage.name_exists(name):
            await self._hass.services.async_call(
                "persistent_notification", "create", {
                    "notification_id": f"ir_blaster_duplicate_{self._entry.entry_id}",
                    "title": "IR Blaster — Duplicate Name",
                    "message": f"A code named **{name}** already exists. Choose a different name.",
                }
            )
            return

        self._pending_name = name
        self._learning_session.register_callback(self._on_learning_state_change)
        success = await self._learning_session.async_start()
        if not success:
            self._learning_session.unregister_callback(self._on_learning_state_change)
            self._pending_name = None

    def _on_learning_state_change(self, state: str, code: LearnedCode | None) -> None:
        if state == STATE_RECEIVED and code and self._pending_name:
            self._hass.async_create_task(self._async_save(code))

    async def _async_save(self, code: LearnedCode) -> None:
        try:
            storage: IRBlasterStorage = self._hass.data[DOMAIN][self._entry.entry_id]["storage"]
            await storage.async_add_code(self._pending_name, code.hex_code)

            # Clear the Code Name text entity
            text_entity_id = f"text.{self._entry.data.get(CONF_DEVICE_NAME, 'IR Blaster').lower().replace(' ', '_')}_code_name"
            await self._hass.services.async_call(
                "text", "set_value", {
                    "entity_id": text_entity_id,
                    "value": DEFAULT_CODE_NAME_PLACEHOLDER,
                }
            )

            await self._learning_session.async_clear_pending()

            # Reload to create the new button entity
            await self._hass.config_entries.async_reload(self._entry.entry_id)
        except Exception as err:
            _LOGGER.error("Failed to save learned code: %s", err, exc_info=True)
        finally:
            self._learning_session.unregister_callback(self._on_learning_state_change)
            self._pending_name = None


class SendLastButton(IRBaseButton):
    """Resend the last captured code — useful for testing."""

    def __init__(self, hass, entry, topic, learning_session: LearningSession):
        super().__init__(hass, entry, topic)
        self._learning_session = learning_session
        self._attr_name = "Send Last Captured"
        self._attr_unique_id = f"{DOMAIN}_{topic}_send_last"
        self._attr_icon = "mdi:send"

    async def async_press(self) -> None:
        code = self._learning_session.pending_code
        if code is None:
            # Fall back to sensor state
            sensor_id = f"sensor.{self._entry.data.get(CONF_DEVICE_NAME, 'IR Blaster').lower().replace(' ', '_')}_last_captured_code"
            state = self._hass.states.get(sensor_id)
            if not state or state.state in ("unknown", "unavailable", ""):
                _LOGGER.warning("Send Last: no code available")
                return
            raw = state.state
        else:
            raw = code.hex_code

        if raw.startswith("0x"):
            raw = raw[2:]

        payload = f"{PKT_SEND_IR}{raw}"
        await mqtt.async_publish(self._hass, TOPIC_SEND.format(topic=self._topic), payload)
        _LOGGER.debug("Send Last fired: %s", payload)


class IRCodeButton(IRBaseButton):
    """One button per saved IR code."""

    def __init__(self, hass, entry, topic, code_id: str, name: str, hex_code: str):
        super().__init__(hass, entry, topic)
        self._code_id = code_id
        self._hex_code = hex_code
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{topic}_code_{code_id}"
        self._attr_icon = "mdi:remote"

    async def async_press(self) -> None:
        code = self._hex_code
        if code.startswith("0x"):
            code = code[2:]
        payload = f"{PKT_SEND_IR}{code}"
        await mqtt.async_publish(self._hass, TOPIC_SEND.format(topic=self._topic), payload)
        _LOGGER.debug("IR code '%s' fired", self._attr_name)
