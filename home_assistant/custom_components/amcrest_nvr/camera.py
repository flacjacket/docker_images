"""Support for Amcrest IP cameras."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Callable, List, Optional

from amcrest import AmcrestError
from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components.camera import SUPPORT_ON_OFF, SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream,
    async_aiohttp_proxy_web,
    async_get_clientsession,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CAMERA_WEB_SESSION_TIMEOUT,
    CAMERAS,
    COMM_TIMEOUT,
    DATA_AMCREST,
    DEVICES,
    SERVICE_UPDATE,
    SNAPSHOT_TIMEOUT,
)
from .helpers import log_update_error, service_signal

if TYPE_CHECKING:
    from . import AmcrestDevice

_LOGGER = logging.getLogger("amcrest_nvr")

SCAN_INTERVAL = timedelta(seconds=15)

STREAM_SOURCE_LIST = ["snapshot", "mjpeg", "rtsp"]

_SRV_EN_REC = "enable_recording"
_SRV_DS_REC = "disable_recording"
_SRV_EN_AUD = "enable_audio"
_SRV_DS_AUD = "disable_audio"
_SRV_EN_MOT_REC = "enable_motion_recording"
_SRV_DS_MOT_REC = "disable_motion_recording"
_SRV_GOTO = "goto_preset"
_SRV_CBW = "set_color_bw"
_SRV_TOUR_ON = "start_tour"
_SRV_TOUR_OFF = "stop_tour"

_SRV_PTZ_CTRL = "ptz_control"
_ATTR_PTZ_TT = "travel_time"
_ATTR_PTZ_MOV = "movement"
_MOV = [
    "zoom_out",
    "zoom_in",
    "right",
    "left",
    "up",
    "down",
    "right_down",
    "right_up",
    "left_down",
    "left_up",
]
_ZOOM_ACTIONS = ["ZoomWide", "ZoomTele"]
_MOVE_1_ACTIONS = ["Right", "Left", "Up", "Down"]
_MOVE_2_ACTIONS = ["RightDown", "RightUp", "LeftDown", "LeftUp"]
_ACTION = _ZOOM_ACTIONS + _MOVE_1_ACTIONS + _MOVE_2_ACTIONS

_DEFAULT_TT = 0.2

_ATTR_PRESET = "preset"
_ATTR_COLOR_BW = "color_bw"

_CBW_COLOR = "color"
_CBW_AUTO = "auto"
_CBW_BW = "bw"
_CBW = [_CBW_COLOR, _CBW_AUTO, _CBW_BW]

_SRV_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids})
_SRV_GOTO_SCHEMA = _SRV_SCHEMA.extend(
    {vol.Required(_ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=1))}
)
_SRV_CBW_SCHEMA = _SRV_SCHEMA.extend({vol.Required(_ATTR_COLOR_BW): vol.In(_CBW)})
_SRV_PTZ_SCHEMA = _SRV_SCHEMA.extend(
    {
        vol.Required(_ATTR_PTZ_MOV): vol.In(_MOV),
        vol.Optional(_ATTR_PTZ_TT, default=_DEFAULT_TT): cv.small_float,
    }
)

CAMERA_SERVICES = {
    _SRV_EN_REC: (_SRV_SCHEMA, "async_enable_recording", ()),
    _SRV_DS_REC: (_SRV_SCHEMA, "async_disable_recording", ()),
    _SRV_EN_AUD: (_SRV_SCHEMA, "async_enable_audio", ()),
    _SRV_DS_AUD: (_SRV_SCHEMA, "async_disable_audio", ()),
    _SRV_EN_MOT_REC: (_SRV_SCHEMA, "async_enable_motion_recording", ()),
    _SRV_DS_MOT_REC: (_SRV_SCHEMA, "async_disable_motion_recording", ()),
    _SRV_GOTO: (_SRV_GOTO_SCHEMA, "async_goto_preset", (_ATTR_PRESET,)),
    _SRV_CBW: (_SRV_CBW_SCHEMA, "async_set_color_bw", (_ATTR_COLOR_BW,)),
    _SRV_TOUR_ON: (_SRV_SCHEMA, "async_start_tour", ()),
    _SRV_TOUR_OFF: (_SRV_SCHEMA, "async_stop_tour", ()),
    _SRV_PTZ_CTRL: (
        _SRV_PTZ_SCHEMA,
        "async_ptz_control",
        (_ATTR_PTZ_MOV, _ATTR_PTZ_TT),
    ),
}

_BOOL_TO_STATE = {True: STATE_ON, False: STATE_OFF}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an Amcrest IP Camera."""
    if discovery_info is None:
        return

    camera_name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][camera_name]
    async_add_entities([AmcrestCam(camera_name, device, hass.data[DATA_FFMPEG])], True)


class CannotSnapshot(Exception):
    """Conditions are not valid for taking a snapshot."""


class AmcrestCommandFailed(Exception):
    """Amcrest camera command did not work."""


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, camera_name: str, device: AmcrestDevice, ffmpeg) -> None:
        """Initialize an Amcrest camera."""
        super().__init__()
        self._name = camera_name
        self._device_name = device.device_name
        self._channel = device.channel
        self._api = device.api
        self._ffmpeg = ffmpeg
        self._ffmpeg_arguments = device.ffmpeg_arguments
        self._stream_source = device.stream_source
        self._resolution = device.resolution
        self._token = self._auth = device.authentication
        self._snapshot_lock = asyncio.Lock()
        self._control_light = device.control_light
        self._is_recording: Optional[bool] = False
        self._motion_detection_enabled: Optional[bool] = None
        self._brand: Optional[str] = None
        self._model: Optional[str] = None
        self._audio_enabled: Optional[bool] = None
        self._motion_recording_enabled: Optional[bool] = None
        self._color_bw: Optional[str] = None
        self._rtsp_url: Optional[str] = None
        self._unique_id: Optional[str] = None
        self._unsub_dispatcher: List[Callable[[], None]] = []
        self._update_succeeded = False

    def _check_snapshot_ok(self) -> bool:
        available = self.available
        if not available or not self.is_on:
            _LOGGER.warning(
                "Attempt to take snapshot when %s camera is %s",
                self.name,
                "offline" if not available else "off",
            )
            return False
        return True

    async def _async_get_image(self):
        assert self.hass is not None
        try:
            # Send the request to snap a picture and return raw jpg data
            # Snapshot command needs a much longer read timeout than other commands.
            return await self.hass.async_add_executor_job(
                partial(
                    self._api.snapshot,
                    timeout=(COMM_TIMEOUT, SNAPSHOT_TIMEOUT),
                    stream=False,
                    channel=self._channel + 1,
                )
            )
        except AmcrestError as error:
            log_update_error(_LOGGER, "get image from", self.name, "camera", error)
            return None

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        assert self.hass is not None
        _LOGGER.debug("Take snapshot from %s", self._name)
        # Amcrest cameras only support one snapshot command at a time.
        # Hence need to wait if a previous snapshot has not yet finished.
        async with self._snapshot_lock:
            # Also need to check that camera is online and turned on before each wait
            # and before initiating shapshot.
            if not self._check_snapshot_ok():
                return None
            # Run snapshot command in separate Task that can't be cancelled so
            # 1) it's not possible to send another snapshot command while camera is
            #    still working on a previous one, and
            # 2) someone will be around to catch any exceptions.
            snapshot_task = self.hass.async_create_task(self._async_get_image())
            return await asyncio.shield(snapshot_task)

    async def handle_async_mjpeg_stream(self, request):
        """Return an MJPEG stream."""
        assert self.hass is not None
        # The snapshot implementation is handled by the parent class
        if self._stream_source == "snapshot":
            _LOGGER.debug("Handling snapshot request")
            return await super().handle_async_mjpeg_stream(request)

        if not self.available:
            _LOGGER.warning(
                "Attempt to stream %s when %s camera is offline",
                self._stream_source,
                self.name,
            )
            return None

        if self._stream_source == "mjpeg":
            # stream an MJPEG image stream directly from the camera
            _LOGGER.debug("Using mjpeg streaming")
            websession = async_get_clientsession(self.hass)
            streaming_url = self._api.mjpeg_url(
                typeno=self._resolution, channel=self._channel + 1
            )
            stream_coro = websession.get(
                streaming_url, auth=self._token, timeout=CAMERA_WEB_SESSION_TIMEOUT
            )

            return await async_aiohttp_proxy_web(self.hass, request, stream_coro)

        # streaming via ffmpeg
        _LOGGER.debug("Using rtsp streaming")
        streaming_url = "-rtsp_transport tcp -i {}".format(self._rtsp_url)
        _LOGGER.debug("Using ffmpeg binary %s", self._ffmpeg.binary)
        stream = CameraMjpeg(self._ffmpeg.binary)
        await stream.open_camera(streaming_url, extra_cmd=self._ffmpeg_arguments)
        _LOGGER.debug(
            "Camera opened with url %s and arguments %s",
            streaming_url,
            self._ffmpeg_arguments,
        )

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    # Entity property overrides

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unique_id(self):
        """Return unique id of this camera"""
        return self._unique_id

    @property
    def extra_state_attributes(self):
        """Return the Amcrest-specific camera state attributes."""
        attr = {}
        if self._audio_enabled is not None:
            attr["audio"] = _BOOL_TO_STATE.get(self._audio_enabled)
        if self._motion_recording_enabled is not None:
            attr["motion_recording"] = _BOOL_TO_STATE.get(
                self._motion_recording_enabled
            )
        if self._color_bw is not None:
            attr[_ATTR_COLOR_BW] = self._color_bw
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.available

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_ON_OFF | SUPPORT_STREAM

    # Camera property overrides

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._is_recording

    @property
    def brand(self):
        """Return the camera brand."""
        return self._brand

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        if self._motion_detection_enabled is not None:
            return _BOOL_TO_STATE[self._motion_detection_enabled]

    @property
    def model(self):
        """Return the camera model."""
        return self._model

    async def stream_source(self):
        """Return the source of the stream."""
        return self._rtsp_url

    @property
    def is_on(self):
        """Return true if on."""
        return self.is_streaming

    # Other Entity method overrides

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Subscribe to signals and add camera to list."""
        assert self.hass is not None
        self._unsub_dispatcher.extend(
            async_dispatcher_connect(
                self.hass,
                service_signal(service, self.entity_id),
                getattr(self, callback_name),
            )
            for service, (_, callback_name, _) in CAMERA_SERVICES.items()
        )
        self._unsub_dispatcher.append(
            async_dispatcher_connect(
                self.hass,
                service_signal(SERVICE_UPDATE, self.name),
                self.async_on_demand_update,
            )
        )
        self.hass.data[DATA_AMCREST][CAMERAS].append(self.entity_id)

    async def async_will_remove_from_hass(self):
        """Remove camera from list and disconnect from signals."""
        assert self.hass is not None
        self.hass.data[DATA_AMCREST][CAMERAS].remove(self.entity_id)
        for unsub_dispatcher in self._unsub_dispatcher:
            unsub_dispatcher()

    def update(self):
        """Update entity status."""
        if not self.available:
            return

        try:
            if not self._update_succeeded:
                if self._unique_id is None:
                    self._unique_id = (
                        f"{self._api.serial_number}-{self._channel}-camera"
                    )
                if self._brand is None:
                    resp = self._api.vendor_information
                    if resp.startswith("vendor="):
                        self._brand = resp.split("=")[-1]
                    else:
                        self._brand = "unknown"
                if self._model is None:
                    self._model = self._api.device_type.strip()
                self._rtsp_url = self._api.rtsp_url(
                    channel=self._channel + 1, typeno=self._resolution
                )
                self._update_succeeded = True
            self.is_streaming = self._get_video()
            self._is_recording = self._get_recording()
            self._motion_detection_enabled = self._get_motion_detection()
            self._audio_enabled = self._get_audio()
            self._motion_recording_enabled = self._get_motion_recording()
            self._color_bw = self._get_color_mode()
        except AmcrestError as error:
            log_update_error(_LOGGER, "get", self.name, "camera attributes", error)

    # Other Camera method overrides

    def turn_off(self):
        """Turn off camera."""
        self._enable_video(False)

    def turn_on(self):
        """Turn on camera."""
        self._enable_video(True)

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        self._enable_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self._enable_motion_detection(False)

    # Additional Amcrest Camera service methods

    async def async_enable_recording(self):
        """Call the job and enable recording."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._enable_recording, True)

    async def async_disable_recording(self):
        """Call the job and disable recording."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._enable_recording, False)

    async def async_enable_audio(self):
        """Call the job and enable audio."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._enable_audio, True)

    async def async_disable_audio(self):
        """Call the job and disable audio."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._enable_audio, False)

    async def async_enable_motion_recording(self):
        """Call the job and enable motion recording."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._enable_motion_recording, True)

    async def async_disable_motion_recording(self):
        """Call the job and disable motion recording."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._enable_motion_recording, False)

    async def async_goto_preset(self, preset):
        """Call the job and move camera to preset position."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._goto_preset, preset)

    async def async_set_color_bw(self, color_bw):
        """Call the job and set camera color mode."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._set_color_bw, color_bw)

    async def async_start_tour(self):
        """Call the job and start camera tour."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._start_tour, True)

    async def async_stop_tour(self):
        """Call the job and stop camera tour."""
        assert self.hass is not None
        await self.hass.async_add_executor_job(self._start_tour, False)

    async def async_ptz_control(self, movement, travel_time):
        """Move or zoom camera in specified direction."""
        assert self.hass is not None
        code = _ACTION[_MOV.index(movement)]

        kwargs = {"arg1": 0, "arg2": 0, "arg3": 0}
        if code in _MOVE_1_ACTIONS:
            kwargs["arg2"] = 1
        elif code in _MOVE_2_ACTIONS:
            kwargs["arg1"] = kwargs["arg2"] = 1

        try:
            await self.hass.async_add_executor_job(
                partial(
                    self._api.ptz_control_command,
                    action="start",
                    code=code,
                    channel=self._channel,
                    **kwargs,
                )
            )
            await asyncio.sleep(travel_time)
            await self.hass.async_add_executor_job(
                partial(
                    self._api.ptz_control_command,
                    action="stop",
                    code=code,
                    channel=self._channel,
                    **kwargs,
                )
            )
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "move", self.name, f"camera PTZ {movement}", error
            )

    # Methods to send commands to Amcrest camera and handle errors

    def _change_setting(self, value, description, attr=None):
        func = description.replace(" ", "_")
        description = f"camera {description} to {value}"
        action = "set"
        tries = 3
        while True:
            try:
                getattr(self, f"_set_{func}")(value)
                new_value = getattr(self, f"_get_{func}")()
                if new_value != value:
                    raise AmcrestCommandFailed
            except (AmcrestError, AmcrestCommandFailed) as error:
                if tries == 1:
                    log_update_error(_LOGGER, action, self.name, description, error)
                    return
                log_update_error(
                    _LOGGER, action, self.name, description, error, logging.DEBUG
                )
            else:
                if attr:
                    setattr(self, attr, new_value)
                    self.schedule_update_ha_state()
                return
            tries -= 1

    def _get_video(self):
        return self._api.is_video_enabled(channel=self._channel)

    def _set_video(self, enable):
        self._api.set_video_enabled(enable, channel=self._channel)

    def _enable_video(self, enable):
        """Enable or disable camera video stream."""
        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # recording on if video stream is being turned off.
        if self.is_recording and not enable:
            self._enable_recording(False)
        self._change_setting(enable, "video", "is_streaming")
        if self._control_light:
            self._change_light()

    def _get_recording(self):
        return self._api.get_record_mode(channel=self._channel) == "Manual"

    def _set_recording(self, enable):
        rec_modes = {"Automatic": 0, "Manual": 1}
        rec_mode = rec_modes["Manual" if enable else "Automatic"]
        self._api.set_record_mode(rec_mode, channel=self._channel)

    def _enable_recording(self, enable):
        """Turn recording on or off."""
        # Given the way the camera's state is determined by
        # is_streaming and is_recording, we can't leave
        # video stream off if recording is being turned on.
        if not self.is_streaming and enable:
            self._enable_video(True)
        self._change_setting(enable, "recording", "_is_recording")

    def _get_motion_detection(self):
        return self._api.is_motion_detector_on(channel=self._channel)

    def _set_motion_detection(self, enable):
        self._api.set_motion_detection(enable, channel=self._channel)

    def _enable_motion_detection(self, enable):
        """Enable or disable motion detection."""
        self._change_setting(enable, "motion detection", "_motion_detection_enabled")

    def _get_audio(self):
        return self._api.is_audio_enabled(channel=self._channel)

    def _set_audio(self, enable):
        self._api.set_audio_enabled(enable, channel=self._channel)

    def _enable_audio(self, enable):
        """Enable or disable audio stream."""
        self._change_setting(enable, "audio", "_audio_enabled")
        if self._control_light:
            self._change_light()

    def _get_indicator_light(self):
        return (
            "true"
            in self._api.command(
                "configManager.cgi?action=getConfig&name=LightGlobal"
            ).content.decode()
        )

    def _set_indicator_light(self, enable):
        self._api.command(
            f"configManager.cgi?action=setConfig&LightGlobal[0].Enable={str(enable).lower()}"
        )

    def _change_light(self):
        """Enable or disable indicator light."""
        self._change_setting(
            self._audio_enabled or self.is_streaming, "indicator light"
        )

    def _get_motion_recording(self) -> bool:
        return self._api.is_record_on_motion_detection(channel=self._channel)

    def _set_motion_recording(self, enable: bool) -> None:
        self._api.set_motion_recording(enable, channel=self._channel)

    def _enable_motion_recording(self, enable):
        """Enable or disable motion recording."""
        self._change_setting(enable, "motion recording", "_motion_recording_enabled")

    def _goto_preset(self, preset):
        """Move camera position and zoom to preset."""
        try:
            self._api.go_to_preset(
                action="start", preset_point_number=preset, channel=self._channel
            )
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "move", self.name, f"camera to preset {preset}", error
            )

    def _get_color_mode(self):
        return _CBW[self._api.get_day_night_color(channel=self._channel)]

    def _set_color_mode(self, cbw):
        self._api.set_day_night_color(_CBW.index(cbw), channel=self._channel)

    def _set_color_bw(self, cbw):
        """Set camera color mode."""
        self._change_setting(cbw, "color mode", "_color_bw")

    def _start_tour(self, start):
        """Start camera tour."""
        try:
            self._api.tour(start=start, channel=self._channel)
        except AmcrestError as error:
            log_update_error(
                _LOGGER, "start" if start else "stop", self.name, "camera tour", error
            )
