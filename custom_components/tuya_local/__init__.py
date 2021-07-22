"""
Platform for Tuya WiFi-connected devices.

Based on nikrolls/homeassistant-goldair-climate for Goldair branded devices.
Based on sean6541/tuya-homeassistant for service call logic, and TarxBoy's
investigation into Goldair's tuyapi statuses
https://github.com/codetheweb/tuyapi/issues/31.
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CLIMATE,
    CONF_DEVICE_ID,
    CONF_FAN,
    CONF_HUMIDIFIER,
    CONF_LIGHT,
    CONF_LOCAL_KEY,
    CONF_LOCK,
    CONF_SWITCH,
    CONF_TYPE,
    DOMAIN,
)
from .device import setup_device, delete_device
from .helpers.device_config import get_config

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, entry: ConfigEntry):
    """Migrate to latest config format."""

    CONF_TYPE_AUTO = "auto"
    CONF_DISPLAY_LIGHT = "display_light"
    CONF_CHILD_LOCK = "child_lock"

    if entry.version == 1:
        # Removal of Auto detection.
        config = {**entry.data, **entry.options, "name": entry.title}
        opts = {**entry.options}
        if config[CONF_TYPE] == CONF_TYPE_AUTO:
            device = setup_device(hass, config)
            config[CONF_TYPE] = await device.async_inferred_type()
            if config[CONF_TYPE] is None:
                return False

        entry.data = {
            CONF_DEVICE_ID: config[CONF_DEVICE_ID],
            CONF_LOCAL_KEY: config[CONF_LOCAL_KEY],
            CONF_HOST: config[CONF_HOST],
        }
        if CONF_CHILD_LOCK in config:
            opts.pop(CONF_CHILD_LOCK, False)
            opts[CONF_LOCK] = config[CONF_CHILD_LOCK]
        if CONF_DISPLAY_LIGHT in config:
            opts.pop(CONF_DISPLAY_LIGHT, False)
            opts[CONF_LIGHT] = config[CONF_DISPLAY_LIGHT]

        entry.options = {**opts}
        entry.version = 2

    if entry.version == 2:
        # CONF_TYPE is not configurable, move it from options to the main config.
        config = {**entry.data, **entry.options, "name": entry.title}
        opts = {**entry.options}
        # Ensure type has been migrated.  Some users are reporting errors which
        # suggest it was removed completely.  But that is probably due to
        # overwriting options without CONF_TYPE.
        if config.get(CONF_TYPE, CONF_TYPE_AUTO) == CONF_TYPE_AUTO:
            device = setup_device(hass, config)
            config[CONF_TYPE] = await device.async_inferred_type()
            if config[CONF_TYPE] is None:
                return False
        entry.data = {
            CONF_DEVICE_ID: config[CONF_DEVICE_ID],
            CONF_LOCAL_KEY: config[CONF_LOCAL_KEY],
            CONF_HOST: config[CONF_HOST],
            CONF_TYPE: config[CONF_TYPE],
        }
        opts.pop(CONF_TYPE, None)
        entry.options = {**opts}
        entry.version = 3

    if entry.version == 3:
        # Migrate to filename based config_type, to avoid needing to
        # parse config files to find the right one.
        config = {**entry.data, **entry.options, "name": entry.title}
        config_type = get_config(config[CONF_TYPE]).config_type

        # Special case for kogan_switch.  Consider also v2.
        if config_type == "smartplugv1":
            device = setup_device(hass, config)
            config_type = await device.async_inferred_type()
            if config_type != "smartplugv2":
                config_type = "smartplugv1"

        entry.data = {
            CONF_DEVICE_ID: config[CONF_DEVICE_ID],
            CONF_LOCAL_KEY: config[CONF_LOCAL_KEY],
            CONF_HOST: config[CONF_HOST],
            CONF_TYPE: config_type,
        }
        entry.version = 4

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug(f"Setting up entry for device: {entry.data[CONF_DEVICE_ID]}")
    config = {**entry.data, **entry.options, "name": entry.title}
    setup_device(hass, config)

    if config.get(CONF_CLIMATE, False) is True:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "climate")
        )
    if config.get(CONF_LIGHT, False) is True:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "light")
        )
    if config.get(CONF_LOCK, False) is True:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "lock")
        )
    if config.get(CONF_SWITCH, False) is True:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "switch")
        )
    if config.get(CONF_HUMIDIFIER, False) is True:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "humidifier")
        )
    if config.get(CONF_FAN, False) is True:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "fan")
        )
    entry.add_update_listener(async_update_entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug(f"Unloading entry for device: {entry.data[CONF_DEVICE_ID]}")
    config = entry.data
    data = hass.data[DOMAIN][config[CONF_DEVICE_ID]]

    if CONF_CLIMATE in data:
        await hass.config_entries.async_forward_entry_unload(entry, "climate")
    if CONF_LIGHT in data:
        await hass.config_entries.async_forward_entry_unload(entry, "light")
    if CONF_LOCK in data:
        await hass.config_entries.async_forward_entry_unload(entry, "lock")
    if CONF_SWITCH in data:
        await hass.config_entries.async_forward_entry_unload(entry, "switch")
    if CONF_HUMIDIFIER in data:
        await hass.config_entries.async_forward_entry_unload(entry, "humidifier")
    if CONF_FAN in data:
        await hass.config_entries.async_forward_entry_unload(entry, "fan")

    delete_device(hass, config)
    del hass.data[DOMAIN][config[CONF_DEVICE_ID]]

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug(f"Updating entry for device: {entry.data[CONF_DEVICE_ID]}")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
