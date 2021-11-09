from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from collections import defaultdict
from dataclasses import dataclass, fields

import paho.mqtt.client

logger = logging.getLogger("teslabuddy")
LOCATION_DT = 0.05


@dataclass(frozen=True)
class Config:
    mqtt_host: str
    mqtt_username: str | None
    mqtt_password: str | None


@dataclass(frozen=True)
class CarInfo:
    car_id: int
    name: str
    model: str
    sw_version: str


@dataclass(frozen=True)
class SensorInfo:
    name: str
    device_class: str | None = None
    icon: str | None = None
    inverted: bool = False
    state_class: str | None = None
    unit_of_measurement: str | None = None


class LocationState:
    last_seen: float = 0
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None

    def update(self, topic: str, payload: str) -> dict | None:
        if time.time() > self.last_seen + LOCATION_DT:
            self.reset()
        self.last_seen = time.time()

        if topic == "latitude":
            self.latitude = float(payload)
        elif topic == "longitude":
            self.longitude = float(payload)
        elif topic == "elevation":
            self.elevation = float(payload)
        else:
            raise RuntimeError(f"Bad topic: {topic}")

        if self.latitude is None or self.longitude is None or self.elevation is None:
            return None

        msg = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.elevation,
            "gps_accuracy": 1.0,
        }
        self.reset()
        return msg

    def topic(self, car: CarInfo) -> str:
        return f"teslamatetracker/{car.car_id}/tracker"

    def reset(self) -> None:
        self.last_seen = 0
        self.latitude = None
        self.longitude = None


CAR_FIELDS = {"display_name", "model", "version"}
LOCATION_FIELDS = {"latitude", "longitude", "elevation"}

BINARY_SENSORS = {
    "charge_port_door_open": SensorInfo(
        "Vehicle Charge Port Door",
        device_class="opening",
        icon="mdi:ev-plug-tesla",
    ),
    "doors_open": SensorInfo("Vehicle Doors", device_class="door", icon="mdi:car-door"),
    "frunk_open": SensorInfo(
        "Vehicle Frunk", device_class="opening", icon="mdi:car-side"
    ),
    "healthy": SensorInfo(
        "Vehicle Healthy", device_class="connectivity", icon="mdi:heart-pulse"
    ),
    "is_climate_on": SensorInfo("Vehicle Climate On", icon="mdi:fan"),
    "is_preconditioning": SensorInfo("Vehicle Preconditioning", icon="mdi:fan"),
    "is_user_present": SensorInfo("Vehicle User Present", icon="mdi:human-greeting"),
    "locked": SensorInfo("Vehicle Locked", device_class="lock", inverted=True),
    "plugged_in": SensorInfo(
        "Vehicle Plugged In", device_class="plug", icon="mdi:ev-station"
    ),
    "sentry_mode": SensorInfo(
        "Vehicle Sentry Mode", device_class="running", icon="mdi:shield-car"
    ),
    "trunk_open": SensorInfo(
        "Vehicle Trunk", device_class="opening", icon="mdi:car-side"
    ),
    "update_available": SensorInfo("Vehicle Update Available", icon="mdi:package-down"),
    "windows_open": SensorInfo(
        "Vehicle Windows", device_class="window", icon="mdi:car-door"
    ),
}

SENSORS = {
    "battery_level": SensorInfo(
        "Vehicle Battery", device_class="battery", unit_of_measurement="%"
    ),
    "charge_energy_added": SensorInfo(
        "Vehice Charge Energy Added",
        device_class="energy",
        unit_of_measurement="kWh",
        state_class="total_increasing",
    ),
    "charge_limit_soc": SensorInfo(
        "Vehicle Charge Limit SOC",
        unit_of_measurement="%",
        icon="mdi:battery-charging-100",
    ),
    "charger_actual_current": SensorInfo(
        "Vehicle Actual Current",
        device_class="current",
        unit_of_measurement="A",
        state_class="measurement",
    ),
    "charger_phases": SensorInfo("Vehicle Charger Phases", icon="mdi:sine-wave"),
    "charger_power": SensorInfo(
        "Vehicle Charger Power",
        device_class="power",
        unit_of_measurement="kW",
        state_class="measurement",
    ),
    "charger_voltage": SensorInfo(
        "Vehicle Voltage", device_class="voltage", unit_of_measurement="V"
    ),
    "elevation": SensorInfo(
        "Vehice Elevation", unit_of_measurement="m", icon="mdi:image-filter-hdr"
    ),
    "est_battery_range_km": SensorInfo(
        "Vehicle Range - Estimated", unit_of_measurement="km", icon="mdi:gauge"
    ),
    "exterior_color": SensorInfo("Vehicle Exterior Color", icon="mdi:palette"),
    "heading": SensorInfo(
        "Vehice Heading", unit_of_measurement="°", icon="mdi:compass"
    ),
    "ideal_battery_range_km": SensorInfo(
        "Vehicle Range - Ideal", unit_of_measurement="km", icon="mdi:gauge"
    ),
    "inside_temp": SensorInfo(
        "Vehicle Temperature Inside",
        device_class="temperature",
        unit_of_measurement="°C",
        state_class="measurement",
    ),
    "odometer": SensorInfo(
        "Vehicle Odometer",
        unit_of_measurement="km",
        icon="mdi:counter",
        state_class="total",
    ),
    "outside_temp": SensorInfo(
        "Vehicle Temperature Outside",
        device_class="temperature",
        unit_of_measurement="°C",
        state_class="measurement",
    ),
    "power": SensorInfo(
        "Vehicle Power",
        device_class="power",
        unit_of_measurement="W",
        state_class="measurement",
    ),
    "rated_battery_range_km": SensorInfo(
        "Vehicle Range - Rated", unit_of_measurement="km", icon="mdi:gauge"
    ),
    "shift_state": SensorInfo("Vehicle Shift State", icon="mdi:car-shift-pattern"),
    "speed": SensorInfo(
        "Vehicle Speed",
        unit_of_measurement="km/h",
        icon="mdi:speedometer",
        state_class="measurement",
    ),
    "state": SensorInfo("Vehicle State", icon="mdi:car-connected"),
    "time_to_full_charge": SensorInfo(
        "Vehicle Time To Full Charge", unit_of_measurement="h", icon="mdi:clock-outline"
    ),
    "trim_badging": SensorInfo("Vehicle Trim Badging", icon="mdi:shield-star-outline"),
    "update_version": SensorInfo("Vehicle Update Version", icon="mdi:alphabetical"),
    "usable_battery_level": SensorInfo(
        "Vehicle Battery - Usable", unit_of_measurement="%", icon="mdi:battery-80"
    ),
    "version": SensorInfo("Vehicle Version", icon="mdi:alphabetical"),
    "wheel_type": SensorInfo("Vehicle Wheel Type", icon="mdi:tire"),
}


def build_device_info(car: CarInfo) -> dict:
    return {
        "identifiers": ["teslamate", str(car.car_id)],
        "manufacturer": "Tesla",
        "model": f"Model {car.model}",
        "name": car.name,
        "sw_version": car.sw_version,
    }


def build_availability(car: CarInfo) -> list[dict]:
    return [
        {
            "payload_available": "true",
            "payload_not_available": "false",
            "topic": f"teslamate/cars/{car.car_id}/healthy",
        }
    ]


def build_unique_id(car: CarInfo, sensor: str) -> str:
    return f"teslamate_{car.car_id}_{sensor}"


def build_discovery_topic(car: CarInfo, sensor: str, component: str) -> str:
    return f"homeassistant/{component}/{build_unique_id(car, sensor)}/config"


class TeslaBuddy:
    def __init__(self, config: Config, *, remove_on_shutdown: bool) -> None:
        self.cars: dict[int, CarInfo] = {}
        self.partial_cars: dict[int, dict[str, str]] = defaultdict(dict)
        self.car_locations: dict[int, LocationState] = defaultdict(LocationState)

        self.remove_on_shutdown = remove_on_shutdown

        self.client = paho.mqtt.client.Client()
        if config.mqtt_username and config.mqtt_password:
            self.client.username_pw_set(
                username=config.mqtt_username, password=config.mqtt_password
            )
        self.client.on_connect = self.on_mqtt_connect
        self.client.on_message = self.on_mqtt_message
        self.client.connect(config.mqtt_host)

    def loop(self) -> None:
        logger.info("Starting loop")
        self.client.loop_forever()
        logger.info("Exiting")

    def stop(self, sig, frame) -> None:
        logger.info("Shutting down loop")

        if self.remove_on_shutdown:
            shutdown_messages: list[str] = []
            shutdown_messages.extend(
                build_discovery_topic(car, sensor, "binary_sensor")
                for car in self.cars.values()
                for sensor in BINARY_SENSORS
            )
            shutdown_messages.extend(
                build_discovery_topic(car, sensor, "sensor")
                for car in self.cars.values()
                for sensor in SENSORS
            )
            shutdown_messages.extend(
                build_discovery_topic(car, "tracker", "device_tracker")
                for car in self.cars.values()
            )
            for topic in shutdown_messages:
                self.client.publish(topic, "")

        self.client.disconnect()

    def on_mqtt_connect(self, client, userdata, flags, rc) -> None:
        self.client.subscribe(f"teslamate/cars/#")

    def on_mqtt_message(self, client, userdata, msg) -> None:
        payload: str = msg.payload.decode()
        topic: str = msg.topic
        parts = topic.split("/")

        logger.debug("Incomming MQTT Message: %s : %s", topic, payload)
        _, _, car_id_str, topic = topic.split("/")
        car_id = int(car_id_str)
        self.process_message(car_id, topic, payload)

    def process_message(self, car_id: int, topic: str, payload: str) -> None:
        if car_id in self.cars:
            self.process_car_message(self.cars[car_id], topic, payload)
        else:
            partial_car = self.partial_cars[car_id]
            partial_car[topic] = payload

            if set(partial_car) >= CAR_FIELDS:
                del self.partial_cars[car_id]
                car = self.cars[car_id] = CarInfo(
                    car_id=int(car_id),
                    name=partial_car["display_name"],
                    model=partial_car["model"],
                    sw_version=partial_car["version"],
                )
                self.setup_car(car)
                logger.debug("Creating car %d: %s", car_id, car)
                for topic, payload in partial_car.items():
                    self.process_car_message(car, topic, payload)

    def process_car_message(self, car: CarInfo, topic: str, payload: str) -> None:
        if topic in LOCATION_FIELDS:
            location = self.car_locations[car.car_id]
            msg = location.update(topic, payload)
            if msg:
                logger.debug("Pushing device location: %s %s", location.topic(car), msg)
                self.client.publish(location.topic(car), json.dumps(msg), retain=True)

    def setup_car(self, car: CarInfo) -> None:
        device_info = build_device_info(car)
        messages = {}

        for sensor, sensor_info in BINARY_SENSORS.items():
            message = {
                "device": device_info,
                "name": sensor_info.name,
                "payload_off": "false",
                "payload_on": "true",
                "state_topic": f"teslamate/cars/{car.car_id}/{sensor}",
                "unique_id": build_unique_id(car, sensor),
            }
            if sensor_info.inverted:
                message["payload_on"] = "false"
                message["payload_off"] = "true"
            if sensor_info.device_class:
                message["device_class"] = sensor_info.device_class
            if sensor_info.icon:
                message["icon"] = sensor_info.icon

            if sensor != "health":
                message["availability"] = build_availability(car)

            messages[build_discovery_topic(car, sensor, "binary_sensor")] = message

        for sensor, sensor_info in SENSORS.items():
            message = {
                "availability": build_availability(car),
                "device": device_info,
                "name": sensor_info.name,
                "state_topic": f"teslamate/cars/{car.car_id}/{sensor}",
                "unique_id": build_unique_id(car, sensor),
            }
            if sensor_info.device_class:
                message["device_class"] = sensor_info.device_class
            if sensor_info.icon:
                message["icon"] = sensor_info.icon
            if sensor_info.state_class:
                message["state_class"] = sensor_info.state_class
            if sensor_info.unit_of_measurement:
                message["unit_of_measurement"] = sensor_info.unit_of_measurement

            messages[build_discovery_topic(car, sensor, "sensor")] = message

        location = self.car_locations[car.car_id]
        messages[build_discovery_topic(car, "tracker", "device_tracker")] = {
            "availability": build_availability(car),
            "device": device_info,
            "icon": "mdi:car",
            "json_attributes_topic": location.topic(car),
            "name": "Vehicle",
            "source_type": "gps",
            "state_topic": location.topic(car) + "/state",
            "unique_id": build_unique_id(car, "tracker"),
        }

        for topic, payload in messages.items():
            self.client.publish(topic, json.dumps(payload), retain=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--remove-on-shutdown", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    with open(args.config_file) as f:
        config = Config(**json.load(f))

    buddy = TeslaBuddy(config, remove_on_shutdown=args.remove_on_shutdown)
    signal.signal(signal.SIGINT, buddy.stop)
    buddy.loop()
