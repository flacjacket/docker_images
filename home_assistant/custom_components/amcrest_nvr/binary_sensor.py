"""Support for Amcrest IP camera binary sensors."""
from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Callable, List, Optional

from amcrest import AmcrestError
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SOUND,
    BinarySensorEntity,
)
from homeassistant.const import CONF_BINARY_SENSORS, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import Throttle

from .const import (
    BINARY_SENSOR_SCAN_INTERVAL_SECS,
    DATA_AMCREST,
    DEVICES,
    SENSOR_DEVICE_CLASS,
    SENSOR_EVENT_CODE,
    SENSOR_NAME,
    SERVICE_EVENT,
    SERVICE_UPDATE,
)
from .helpers import log_update_error, service_signal

if TYPE_CHECKING:
    from . import AmcrestDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=BINARY_SENSOR_SCAN_INTERVAL_SECS)
_ONLINE_SCAN_INTERVAL = timedelta(seconds=60 - BINARY_SENSOR_SCAN_INTERVAL_SECS)

BINARY_SENSOR_AUDIO_DETECTED = "audio_detected"
BINARY_SENSOR_AUDIO_DETECTED_POLLED = "audio_detected_polled"
BINARY_SENSOR_MOTION_DETECTED = "motion_detected"
BINARY_SENSOR_MOTION_DETECTED_POLLED = "motion_detected_polled"
BINARY_SENSOR_ONLINE = "online"
BINARY_SENSOR_CROSSLINE_DETECTED = "crossline_detected"
BINARY_SENSOR_CROSSLINE_DETECTED_POLLED = "crossline_detected_polled"
BINARY_POLLED_SENSORS = [
    BINARY_SENSOR_AUDIO_DETECTED_POLLED,
    BINARY_SENSOR_MOTION_DETECTED_POLLED,
    BINARY_SENSOR_ONLINE,
]
_AUDIO_DETECTED_PARAMS = {
    SENSOR_NAME: "Audio Detected",
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_SOUND,
    SENSOR_EVENT_CODE: "AudioMutation",
}
_MOTION_DETECTED_PARAMS = {
    SENSOR_NAME: "Motion Detected",
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_MOTION,
    SENSOR_EVENT_CODE: "VideoMotion",
}
_CROSSLINE_DETECTED_PARAMS = {
    SENSOR_NAME: "CrossLine Detected",
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_MOTION,
    SENSOR_EVENT_CODE: "CrossLineDetection",
}
_ONLINE_PARAMS = {
    SENSOR_NAME: "Online",
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
    SENSOR_EVENT_CODE: None,
}
CAMERA_BINARY_SENSORS = {
    BINARY_SENSOR_AUDIO_DETECTED: _AUDIO_DETECTED_PARAMS,
    BINARY_SENSOR_AUDIO_DETECTED_POLLED: _AUDIO_DETECTED_PARAMS,
    BINARY_SENSOR_MOTION_DETECTED: _MOTION_DETECTED_PARAMS,
    BINARY_SENSOR_MOTION_DETECTED_POLLED: _MOTION_DETECTED_PARAMS,
    BINARY_SENSOR_CROSSLINE_DETECTED: _CROSSLINE_DETECTED_PARAMS,
    BINARY_SENSOR_CROSSLINE_DETECTED_POLLED: _CROSSLINE_DETECTED_PARAMS,
}
DEVICE_BINARY_SENSORS = {
    BINARY_SENSOR_ONLINE: _ONLINE_PARAMS,
}
BINARY_SENSORS = CAMERA_BINARY_SENSORS | DEVICE_BINARY_SENSORS
_EXCLUSIVE_OPTIONS = [
    {BINARY_SENSOR_AUDIO_DETECTED, BINARY_SENSOR_AUDIO_DETECTED_POLLED},
    {BINARY_SENSOR_MOTION_DETECTED, BINARY_SENSOR_MOTION_DETECTED_POLLED},
    {BINARY_SENSOR_CROSSLINE_DETECTED, BINARY_SENSOR_CROSSLINE_DETECTED_POLLED},
]

_UPDATE_MSG = "Updating %s binary sensor"


def check_binary_sensors(value: List[str]) -> List[str]:
    """Validate binary sensor configurations."""
    for exclusive_options in _EXCLUSIVE_OPTIONS:
        if len(set(value) & exclusive_options) > 1:
            raise vol.Invalid(
                f"must contain at most one of {', '.join(exclusive_options)}."
            )
    return value


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a binary sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    async_add_entities(
        [
            AmcrestBinarySensor(name, device, sensor_type)
            for sensor_type in discovery_info[CONF_BINARY_SENSORS]
        ],
        True,
    )


class AmcrestBinarySensor(BinarySensorEntity):
    """Binary sensor for Amcrest camera."""

    def __init__(self, name: str, device: AmcrestDevice, sensor_type: str) -> None:
        """Initialize entity."""
        self._name = f"{name} {BINARY_SENSORS[sensor_type][SENSOR_NAME]}"
        self._device_class = BINARY_SENSORS[sensor_type][SENSOR_DEVICE_CLASS]
        self._event_code = BINARY_SENSORS[sensor_type][SENSOR_EVENT_CODE]
        self._signal_name = name
        self._api = device.api
        self._channel = device.channel
        self._sensor_type = sensor_type
        self._state: Optional[bool] = None
        self._unique_id: Optional[str] = None
        self._unsub_dispatcher: List[Callable[[], None]] = []

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return self._sensor_type in BINARY_POLLED_SENSORS

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def is_on(self):
        """Return if entity is on."""
        return self._state

    @property
    def device_class(self):
        """Return device class."""
        return self._device_class

    @property
    def available(self):
        """Return True if entity is available."""
        return self._sensor_type == BINARY_SENSOR_ONLINE or self._api.available

    def update(self):
        """Update entity."""
        if self._sensor_type == BINARY_SENSOR_ONLINE:
            self._update_online()
        else:
            self._update_others()

    @Throttle(_ONLINE_SCAN_INTERVAL)
    def _update_online(self):
        if not (self._api.available or self.is_on):
            return
        _LOGGER.debug(_UPDATE_MSG, self._name)
        self._update_unique_id()
        if self._api.available:
            # Send a command to the camera to test if we can still communicate with it.
            # Override of Http.command() in __init__.py will set self._api.available
            # accordingly.
            with suppress(AmcrestError):
                self._api.current_time
        self._state = self._api.available

    def _update_others(self):
        if not self.available:
            return
        _LOGGER.debug(_UPDATE_MSG, self._name)

        self._update_unique_id()
        try:
            self._state = self._channel in self._api.event_channels_happened(
                self._event_code
            )
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "binary sensor", error)

    async def async_on_demand_update(self):
        """Update state."""
        if self._sensor_type == BINARY_SENSOR_ONLINE:
            _LOGGER.debug(_UPDATE_MSG, self._name)
            self._state = self._api.available
            self.async_write_ha_state()
        else:
            self.async_schedule_update_ha_state(True)

    @callback
    def async_event_received(self, state: bool):
        """Update state from received event."""
        _LOGGER.debug(_UPDATE_MSG, self._name)
        self._state = state
        self._update_unique_id()
        self.async_write_ha_state()

    def _update_unique_id(self):
        if self._unique_id is None:
            self._unique_id = (
                f"{self._api.serial_number}-{self._channel}-{self._sensor_type}"
            )

    async def async_added_to_hass(self):
        """Subscribe to signals."""
        assert self.hass is not None

        self._unsub_dispatcher.append(
            async_dispatcher_connect(
                self.hass,
                service_signal(SERVICE_UPDATE, self._signal_name),
                self.async_on_demand_update,
            )
        )
        if self._event_code and self._sensor_type not in BINARY_POLLED_SENSORS:
            self._unsub_dispatcher.append(
                async_dispatcher_connect(
                    self.hass,
                    service_signal(SERVICE_EVENT, self._signal_name, self._event_code),
                    self.async_event_received,
                )
            )

    async def async_will_remove_from_hass(self):
        """Disconnect from update signal."""
        for unsub_dispatcher in self._unsub_dispatcher:
            unsub_dispatcher()
