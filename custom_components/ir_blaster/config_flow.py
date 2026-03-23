"""Config flow for IR Blaster integration."""

from __future__ import annotations

import asyncio
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
import json

from .const import (
    DOMAIN,
    CONF_TOPIC,
    CONF_DEVICE_NAME,
    CONF_SAVED_CODES,
    DEFAULT_TOPIC,
    TOPIC_SEND,
    TOPIC_RESULT,
    PKT_STUDY_ON,
    PKT_STUDY_OFF,
    DP_IR_CODE_7,
    DP_IR_CODE_2,
    LEARN_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_NAME, default="IR Blaster"): str,
        vol.Required(CONF_TOPIC, default=DEFAULT_TOPIC): str,
    }
)


class IRBlasterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IR Blaster."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_TOPIC])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_DEVICE_NAME],
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return IRBlasterOptionsFlow(config_entry)


class IRBlasterOptionsFlow(config_entries.OptionsFlow):
    """Options flow — manage saved IR codes."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._saved_codes: dict = dict(
            config_entry.options.get(CONF_SAVED_CODES, {})
        )
        self._pending_name: str | None = None
        self._learned_code: str | None = None

    # ------------------------------------------------------------------ #
    # Step 1: Main menu                                                    #
    # ------------------------------------------------------------------ #
    async def async_step_init(self, user_input=None):
        """Show menu: Add Code / Remove Code / Done."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_name()
            if action == "remove":
                return await self.async_step_remove()
            # Done
            return self.async_create_entry(
                title="",
                data={CONF_SAVED_CODES: self._saved_codes},
            )

        code_list = ", ".join(self._saved_codes.keys()) if self._saved_codes else "None"
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="done"): vol.In(
                        {"add": "Add new code", "remove": "Remove a code", "done": "Save and exit"}
                    )
                }
            ),
            description_placeholders={"saved_codes": code_list},
        )

    # ------------------------------------------------------------------ #
    # Step 2a: Enter the name for the new code                            #
    # ------------------------------------------------------------------ #
    async def async_step_add_name(self, user_input=None):
        errors = {}
        if user_input is not None:
            name = user_input.get("code_name", "").strip()
            if not name:
                errors["code_name"] = "name_required"
            elif name in self._saved_codes:
                errors["code_name"] = "name_exists"
            else:
                self._pending_name = name
                return await self.async_step_learn()

        return self.async_show_form(
            step_id="add_name",
            data_schema=vol.Schema({vol.Required("code_name"): str}),
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Step 2b: Put device in study mode and wait for a capture            #
    # ------------------------------------------------------------------ #
    async def async_step_learn(self, user_input=None):
        """Send study-on, wait up to 30s for TuyaReceived, send study-off."""
        if user_input is not None:
            # User hit submit after learning — shouldn't normally happen
            # but handle gracefully
            return await self.async_step_init()

        topic = self.config_entry.data[CONF_TOPIC]
        hass = self.hass

        # Send study on
        await mqtt.async_publish(hass, TOPIC_SEND.format(topic=topic), PKT_STUDY_ON)
        _LOGGER.debug("Learn mode: study ON sent for '%s'", self._pending_name)

        captured_code: list[str] = []
        learned_event = asyncio.Event()

        @callback
        def message_received(msg):
            try:
                data = json.loads(msg.payload)
                tuya = data.get("TuyaReceived", {})
                code = tuya.get(DP_IR_CODE_7) or tuya.get(DP_IR_CODE_2)
                if code:
                    if code.startswith("0x"):
                        code = code[2:]
                    if set(code) == {"8"}:
                        return  # noise, ignore
                    captured_code.append(code)
                    learned_event.set()
            except (json.JSONDecodeError, AttributeError):
                pass

        result_topic = TOPIC_RESULT.format(topic=topic)
        unsubscribe = await mqtt.async_subscribe(hass, result_topic, message_received, 0)

        try:
            await asyncio.wait_for(learned_event.wait(), timeout=LEARN_TIMEOUT)
            code = captured_code[0]
            self._saved_codes[self._pending_name] = code
            _LOGGER.debug("Learned code for '%s': %s", self._pending_name, code)
            result = "success"
        except asyncio.TimeoutError:
            _LOGGER.warning("Learn timeout for '%s'", self._pending_name)
            result = "timeout"
        finally:
            unsubscribe()
            await mqtt.async_publish(hass, TOPIC_SEND.format(topic=topic), PKT_STUDY_OFF)
            _LOGGER.debug("Learn mode: study OFF sent")

        self._learned_code = captured_code[0] if captured_code else None
        return await self.async_step_learn_result(result)

    # ------------------------------------------------------------------ #
    # Step 2c: Show result of learning                                     #
    # ------------------------------------------------------------------ #
    async def async_step_learn_result(self, result: str, user_input=None):
        if user_input is not None:
            return await self.async_step_init()

        if result == "success":
            description = f"✅ Code saved as **{self._pending_name}**.\n\n`{self._learned_code}`"
        else:
            description = f"⏱ No code captured within {LEARN_TIMEOUT}s. Try again."

        return self.async_show_form(
            step_id="learn_result",
            data_schema=vol.Schema({}),
            description_placeholders={"result": description},
        )

    # ------------------------------------------------------------------ #
    # Step 3: Remove a code                                               #
    # ------------------------------------------------------------------ #
    async def async_step_remove(self, user_input=None):
        errors = {}
        if not self._saved_codes:
            return self.async_abort(reason="no_codes")

        if user_input is not None:
            name = user_input.get("code_name")
            if name and name in self._saved_codes:
                del self._saved_codes[name]
            return await self.async_step_init()

        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema(
                {
                    vol.Required("code_name"): vol.In(list(self._saved_codes.keys()))
                }
            ),
            errors=errors,
        )
