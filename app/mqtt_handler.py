"""MQTT message handling and client management."""
import json
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt

from app.config import Config
from app.state_manager import StateManager


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value between low and high."""
    return max(low, min(high, value))


class MQTTHandler:
    """Handles MQTT messages and turret control commands."""

    def __init__(self, state_manager: StateManager, trigger_callback):
        self.state_manager = state_manager
        self.trigger_callback = trigger_callback

    def handle_manual_command(self, client: mqtt.Client, payload: dict):
        """Handle manual joystick control command."""
        owner = payload.get("owner", "manual-ui")
        self.state_manager.claim_owner(owner)

        with self.state_manager.lock:
            if self.state_manager.state.mode != "manual" or self.state_manager.state.owner != owner:
                return

            dx = float(payload.get("dx", 0.0))
            dy = float(payload.get("dy", 0.0))
            self.state_manager.state.pan_target = clamp(
                self.state_manager.state.pan_target + dx * Config.STEP_DEG,
                Config.PAN_MIN,
                Config.PAN_MAX
            )
            self.state_manager.state.tilt_target = clamp(
                self.state_manager.state.tilt_target - dy * Config.STEP_DEG,
                Config.TILT_MIN,
                Config.TILT_MAX
            )

        self.state_manager.publish_state(client)

    def handle_set_angles(self, client: mqtt.Client, payload: dict):
        """Handle direct servo angle control command."""
        owner = payload.get("owner", "pi5")
        requested_mode = payload.get("mode", "auto")
        if requested_mode not in {"auto", "manual"}:
            requested_mode = "auto"

        self.state_manager.claim_owner(owner)

        with self.state_manager.lock:
            if self.state_manager.state.mode != requested_mode or self.state_manager.state.owner != owner:
                return

            if "pan" in payload:
                self.state_manager.state.pan_target = clamp(
                    float(payload["pan"]),
                    Config.PAN_MIN,
                    Config.PAN_MAX
                )
            if "tilt" in payload:
                self.state_manager.state.tilt_target = clamp(
                    float(payload["tilt"]),
                    Config.TILT_MIN,
                    Config.TILT_MAX
                )

        self.state_manager.publish_state(client)

    def on_connect(self, client: mqtt.Client, userdata, flags, rc, properties=None):
        """Handle MQTT connection."""
        client.subscribe(Config.topic("mode/set"))
        client.subscribe(Config.topic("manual/joystick"))
        client.subscribe(Config.topic("servo/set"))
        client.subscribe(Config.topic("trigger/fire"))
        client.subscribe(Config.topic("heartbeat"))
        self.state_manager.publish_state(client)

    def on_message(self, client: mqtt.Client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload.decode("utf-8")) if msg.payload else {}
        except json.JSONDecodeError:
            return

        if msg.topic == Config.topic("mode/set"):
            mode = payload.get("mode")
            owner = payload.get("owner", "unknown")
            if mode in {"auto", "manual"}:
                self.state_manager.set_mode(mode, owner)
                self.state_manager.publish_state(client)
            return

        if msg.topic == Config.topic("heartbeat"):
            owner = payload.get("owner", "unknown")
            self.state_manager.claim_owner(owner)
            self.state_manager.publish_state(client)
            return

        if msg.topic == Config.topic("manual/joystick"):
            self.handle_manual_command(client, payload)
            return

        if msg.topic == Config.topic("servo/set"):
            self.handle_set_angles(client, payload)
            return

        if msg.topic == Config.topic("trigger/fire"):
            owner = payload.get("owner", "unknown")
            with self.state_manager.lock:
                allowed = (
                    self.state_manager.state.owner == owner
                    and self.state_manager.state.mode == payload.get("mode", self.state_manager.state.mode)
                )
            if allowed:
                self.trigger_callback(client, owner)


def create_mqtt_client(mqtt_handler: MQTTHandler) -> mqtt.Client:
    """Create and configure MQTT client."""
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=Config.MQTT_CLIENT_ID,
        clean_session=True
    )

    if Config.MQTT_USERNAME:
        client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)

    client.on_connect = mqtt_handler.on_connect
    client.on_message = mqtt_handler.on_message
    client.will_set(
        Config.topic("state"),
        json.dumps({"status": "offline", "ts": time.time()}),
        retain=True
    )

    return client
