"""Config flow for IR Blaster integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.mqtt import async_publish
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_TOPIC, CONF_DEVICE_NAME, DEFAULT_TOPIC

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_NAME, default="IR Blaster"): str,
        vol.Required(CONF_TOPIC, default=DEFAULT_TOPIC): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IR Blaster."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Check for duplicate topic
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
            description_placeholders={
                "mqtt_info": "Enter the Tasmota MQTT topic for your IR blaster device."
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return IRBlasterOptionsFlow(config_entry)


class IRBlasterOptionsFlow(config_entries.OptionsFlow):
    """Handle options for IR Blaster."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TOPIC,
                        default=self.config_entry.data.get(CONF_TOPIC, DEFAULT_TOPIC),
                    ): str,
                }
            ),
        )
