"""Config flow for IR Blaster integration."""

from __future__ import annotations

import asyncio
import json
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback

from .const import (
    CONF_DEVICE_NAME,
    CONF_SAVED_CODES,
    CONF_TOPIC,
    DEFAULT_TOPIC,
    DOMAIN,
    DP_IR_CODE_2,
    DP_IR_CODE_7,
    LEARN_TIMEOUT,
    PKT_STUDY_OFF,
    PKT_STUDY_ON,
    TOPIC_RESULT,
    TOPIC_SEND,
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
        # Background learn task state
        self._learn_task: asyncio.Task | None = None
        self._captured_code: str | None = None
        self._learn_result: str | None = None  # "success" | "timeout"
        self._unsubscribe = None

    # ------------------------------------------------------------------ #
    # Step 1: Main menu                                                    #
    # ------------------------------------------------------------------ #
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_name()
            if action == "remove":
                return await self.async_step_remove()
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
                        {
                            "add": "Add new code",
                            "remove": "Remove a code",
                            "done": "Save and exit",
                        }
                    )
                }
            ),
            description_placeholders={"saved_codes": code_list},
        )

    # ------------------------------------------------------------------ #
    # Step 2a: Name the new code                                          #
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
                self._captured_code = None
                self._learn_result = None
                return await self.async_step_learn_start()

        return self.async_show_form(
            step_id="add_name",
            data_schema=vol.Schema({vol.Required("code_name"): str}),
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    # Step 2b: Start learning — send study-on, kick off background task  #
    # ------------------------------------------------------------------ #
    async def async_step_learn_start(self, user_input=None):
        """Send study-on and launch background capture task, show waiting form."""
        topic = self.config_entry.data[CONF_TOPIC]

        # Send study on
        await mqtt.async_publish(
            self.hass, TOPIC_SEND.format(topic=topic), PKT_STUDY_ON
        )
        _LOGGER.debug("Learn: study ON for '%s'", self._pending_name)

        # Subscribe to MQTT and start timeout task
        self._captured_code = None
        self._learn_result = None
        captured: list[str] = []
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
                        return
                    captured.append(code)
                    learned_event.set()
            except (json.JSONDecodeError, AttributeError):
                pass

        result_topic = TOPIC_RESULT.format(topic=topic)
        self._unsubscribe = await mqtt.async_subscribe(
            self.hass, result_topic, message_received, 0
        )

        async def _wait_for_code():
            try:
                await asyncio.wait_for(learned_event.wait(), timeout=LEARN_TIMEOUT)
                self._captured_code = captured[0]
                self._learn_result = "success"
                _LOGGER.debug("Learned '%s': %s", self._pending_name, self._captured_code)
            except asyncio.TimeoutError:
                self._learn_result = "timeout"
                _LOGGER.warning("Learn timeout for '%s'", self._pending_name)
            finally:
                if self._unsubscribe:
                    self._unsubscribe()
                    self._unsubscribe = None
                await mqtt.async_publish(
                    self.hass, TOPIC_SEND.format(topic=topic), PKT_STUDY_OFF
                )
                _LOGGER.debug("Learn: study OFF")

        self._learn_task = self.hass.async_create_task(_wait_for_code())

        return self.async_show_form(
            step_id="learn_wait",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._pending_name,
                "timeout": str(LEARN_TIMEOUT),
            },
        )

    # ------------------------------------------------------------------ #
    # Step 2c: User pressed Continue — check if code was captured         #
    # ------------------------------------------------------------------ #
    async def async_step_learn_wait(self, user_input=None):
        """Called when user submits the waiting form."""
        if user_input is not None:
            # Cancel task if still running
            if self._learn_task and not self._learn_task.done():
                self._learn_task.cancel()
                if self._unsubscribe:
                    self._unsubscribe()
                    self._unsubscribe = None
                topic = self.config_entry.data[CONF_TOPIC]
                await mqtt.async_publish(
                    self.hass, TOPIC_SEND.format(topic=topic), PKT_STUDY_OFF
                )

            if self._learn_result == "success" and self._captured_code:
                self._saved_codes[self._pending_name] = self._captured_code
                return self.async_show_form(
                    step_id="learn_result",
                    data_schema=vol.Schema({}),
                    description_placeholders={
                        "result": f"✅ Saved as '{self._pending_name}'",
                        "code": self._captured_code,
                    },
                )
            else:
                return self.async_show_form(
                    step_id="learn_result",
                    data_schema=vol.Schema({}),
                    description_placeholders={
                        "result": f"⏱ No code captured within {LEARN_TIMEOUT}s. Try again.",
                        "code": "",
                    },
                )

        # Shouldn't reach here but show form again if needed
        return self.async_show_form(
            step_id="learn_wait",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._pending_name,
                "timeout": str(LEARN_TIMEOUT),
            },
        )

    # ------------------------------------------------------------------ #
    # Step 2d: Show result, then back to menu                             #
    # ------------------------------------------------------------------ #
    async def async_step_learn_result(self, user_input=None):
        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="learn_result",
            data_schema=vol.Schema({}),
            description_placeholders={
                "result": self._learn_result or "",
                "code": self._captured_code or "",
            },
        )

    # ------------------------------------------------------------------ #
    # Step 3: Remove a code                                               #
    # ------------------------------------------------------------------ #
    async def async_step_remove(self, user_input=None):
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
                {vol.Required("code_name"): vol.In(list(self._saved_codes.keys()))}
            ),
        )
