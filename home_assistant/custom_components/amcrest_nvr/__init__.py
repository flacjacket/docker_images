"""Support for Amcrest IP cameras."""
from dataclasses import dataclass
from datetime import timedelta
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from amcrest import AmcrestError
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.camera import DOMAIN as CAMERA
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_AUTHENTICATION,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_USERNAME,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.service import async_extract_entity_ids

from .amcrest_checker import AmcrestChecker
from .binary_sensor import (
    BINARY_POLLED_SENSORS,
    CAMERA_BINARY_SENSORS,
    DEVICE_BINARY_SENSORS,
    check_binary_sensors,
)
from .camera import CAMERA_SERVICES, STREAM_SOURCE_LIST
from .const import (
    CAMERAS,
    DATA_AMCREST,
    DEVICES,
    DOMAIN,
    SENSOR_EVENT_CODE,
    SERVICE_EVENT,
)
from .helpers import service_signal
from .sensor import SENSORS

_LOGGER = logging.getLogger(__name__)

CONF_CAMERAS = "cameras"
CONF_CHANNEL = "channel"
CONF_RESOLUTION = "resolution"
CONF_STREAM_SOURCE = "stream_source"
CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"
CONF_CONTROL_LIGHT = "control_light"

DEFAULT_NAME = "Amcrest Camera"
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = "high"
DEFAULT_ARGUMENTS = "-pred 1"

NOTIFICATION_ID = "amcrest_notification"
NOTIFICATION_TITLE = "Amcrest Camera Setup"

RESOLUTION_LIST = {"high": 0, "low": 1}

SCAN_INTERVAL = timedelta(seconds=10)

AUTHENTICATION_LIST = {"basic": "basic"}


def _has_unique_names(devices):
    nvr_names = [nvr_device[CONF_NAME] for nvr_device in devices]
    camera_names = [
        camera_device[CONF_NAME]
        for nvr_device in devices
        for camera_device in nvr_device[CONF_CAMERAS]
    ]
    vol.Schema(vol.Unique())(nvr_names + camera_names)
    return devices


CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_CHANNEL): cv.positive_int,
        vol.Optional(CONF_RESOLUTION, default=DEFAULT_RESOLUTION): vol.All(
            vol.In(RESOLUTION_LIST)
        ),
        vol.Optional(CONF_STREAM_SOURCE, default=STREAM_SOURCE_LIST[0]): vol.All(
            vol.In(STREAM_SOURCE_LIST)
        ),
        vol.Optional(CONF_FFMPEG_ARGUMENTS, default=DEFAULT_ARGUMENTS): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list,
            [vol.In(CAMERA_BINARY_SENSORS)],
            vol.Unique(),
            check_binary_sensors,
        ),
        vol.Optional(CONF_CONTROL_LIGHT, default=True): cv.boolean,
    }
)

AMCREST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CAMERAS): vol.All(cv.ensure_list, [CAMERA_SCHEMA]),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.All(
            vol.In(AUTHENTICATION_LIST)
        ),
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list,
            [vol.In(DEVICE_BINARY_SENSORS)],
            vol.Unique(),
            check_binary_sensors,
        ),
        vol.Optional(CONF_SENSORS): vol.All(
            cv.ensure_list, [vol.In(SENSORS)], vol.Unique()
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [AMCREST_SCHEMA], _has_unique_names)},
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class AmcrestDevice:
    """Representation of a base Amcrest discovery device."""

    device_name: str
    api: AmcrestChecker
    channel: int
    authentication: Optional[aiohttp.BasicAuth]
    ffmpeg_arguments: List[str]
    stream_source: str
    resolution: int
    control_light: bool


def _start_event_monitor(
    hass: HomeAssistant,
    device_name: str,
    camera_events: Dict[int, Tuple[str, List[str]]],
    api: AmcrestChecker,
) -> None:
    thread = threading.Thread(
        target=_monitor_events,
        name=f"Amcrest {device_name}",
        args=(hass, device_name, camera_events, api),
        daemon=True,
    )
    thread.start()


def _monitor_events(
    hass: HomeAssistant,
    device_name: str,
    camera_events: Dict[int, Tuple[str, List[str]]],
    api: AmcrestChecker,
) -> None:
    unique_event_codes = {
        event for _, events in camera_events.values() for event in events
    }
    event_codes = list(unique_event_codes)
    while True:
        api.available_flag.wait()
        try:
            for code, payload in api.event_actions(event_codes, retries=5):
                channel = payload["channel"]
                if channel not in camera_events:
                    continue
                camera_name, events = camera_events[channel]
                if code not in events:
                    continue
                signal = service_signal(SERVICE_EVENT, camera_name, code)
                _LOGGER.debug("Sending signal: '%s': %s", signal, payload)
                status = payload["action"].lower() == "start"
                dispatcher_send(hass, signal, status)
        except AmcrestError as error:
            _LOGGER.warning(
                "Error while processing events from %s device: %r", device_name, error
            )


def setup(hass: HomeAssistant, config: Any) -> bool:
    """Set up the Amcrest IP Camera component."""
    hass.data.setdefault(DATA_AMCREST, {DEVICES: {}, CAMERAS: []})

    for device in config[DOMAIN]:
        device_name: str = device[CONF_NAME]
        username: str = device[CONF_USERNAME]
        password: str = device[CONF_PASSWORD]

        api = AmcrestChecker(
            hass, device_name, device[CONF_HOST], device[CONF_PORT], username, password
        )

        # currently aiohttp only works with basic authentication
        # only valid for mjpeg streaming
        if device[CONF_AUTHENTICATION] == HTTP_BASIC_AUTHENTICATION:
            authentication = aiohttp.BasicAuth(username, password)
        else:
            authentication = None

        camera_events = {}
        for camera_config in device[CONF_CAMERAS]:
            camera_name = camera_config[CONF_NAME]
            channel = camera_config[CONF_CHANNEL]
            ffmpeg_arguments = camera_config[CONF_FFMPEG_ARGUMENTS]
            resolution = RESOLUTION_LIST[camera_config[CONF_RESOLUTION]]
            camera_binary_sensors = camera_config.get(CONF_BINARY_SENSORS)
            stream_source = camera_config[CONF_STREAM_SOURCE]
            control_light = camera_config.get(CONF_CONTROL_LIGHT)

            hass.data[DATA_AMCREST][DEVICES][camera_name] = AmcrestDevice(
                device_name=device_name,
                api=api,
                channel=channel,
                authentication=authentication,
                ffmpeg_arguments=ffmpeg_arguments,
                stream_source=stream_source,
                resolution=resolution,
                control_light=control_light,
            )

            discovery.load_platform(
                hass,
                CAMERA,
                DOMAIN,
                {CONF_NAME: camera_name},
                config,
            )

            if camera_binary_sensors:
                discovery.load_platform(
                    hass,
                    BINARY_SENSOR,
                    DOMAIN,
                    {
                        CONF_NAME: camera_name,
                        CONF_BINARY_SENSORS: camera_binary_sensors,
                    },
                    config,
                )
                events = [
                    CAMERA_BINARY_SENSORS[sensor_type][SENSOR_EVENT_CODE]
                    for sensor_type in camera_binary_sensors
                    if sensor_type not in BINARY_POLLED_SENSORS
                ]
                camera_events[channel] = camera_name, events

        if camera_events:
            _start_event_monitor(hass, device_name, camera_events, api)

        hass.data[DATA_AMCREST][DEVICES][device_name] = AmcrestDevice(
            device_name=device_name,
            api=api,
            channel=0,
            authentication=authentication,
            ffmpeg_arguments=[],
            stream_source="",
            resolution=0,
            control_light=True,
        )

        device_binary_sensors = device.get(CONF_BINARY_SENSORS)
        if device_binary_sensors:
            discovery.load_platform(
                hass,
                BINARY_SENSOR,
                DOMAIN,
                {CONF_NAME: device_name, CONF_BINARY_SENSORS: device_binary_sensors},
                config,
            )

        sensors = device.get(CONF_SENSORS)
        if sensors:
            discovery.load_platform(
                hass,
                SENSOR,
                DOMAIN,
                {CONF_NAME: device_name, CONF_SENSORS: sensors},
                config,
            )

    if not hass.data[DATA_AMCREST][DEVICES]:
        return False

    def have_permission(user, entity_id) -> bool:
        return not user or user.permissions.check_entity(entity_id, POLICY_CONTROL)

    async def async_extract_from_service(call) -> List[str]:
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
        else:
            user = None

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL:
            # Return all entity_ids user has permission to control.
            return [
                entity_id
                for entity_id in hass.data[DATA_AMCREST][CAMERAS]
                if have_permission(user, entity_id)
            ]

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_NONE:
            return []

        call_ids = await async_extract_entity_ids(hass, call)
        entity_ids = []
        for entity_id in hass.data[DATA_AMCREST][CAMERAS]:
            if entity_id not in call_ids:
                continue
            if not have_permission(user, entity_id):
                raise Unauthorized(
                    context=call.context, entity_id=entity_id, permission=POLICY_CONTROL
                )
            entity_ids.append(entity_id)
        return entity_ids

    async def async_service_handler(call):
        args = []
        for arg in CAMERA_SERVICES[call.service][2]:
            args.append(call.data[arg])
        for entity_id in await async_extract_from_service(call):
            async_dispatcher_send(hass, service_signal(call.service, entity_id), *args)

    for service, params in CAMERA_SERVICES.items():
        hass.services.register(DOMAIN, service, async_service_handler, params[0])

    return True
