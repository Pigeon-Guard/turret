"""State management for turret control."""
import json
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt

from app.config import Config
from app.models import SharedState


class StateManager:
    """Manages shared state with thread-safe access."""

    def __init__(self, active_backend: str, simulated_io: bool):
        self.state = SharedState()
        self.lock = threading.Lock()
        self.active_backend = active_backend
        self.simulated_io = simulated_io

    def claim_owner(self, requested_owner: str):
        """Claim ownership of the turret."""
        now = time.time()
        with self.lock:
            if self.state.owner != requested_owner:
                self.state.owner = requested_owner
                self.state.owner_since = now
            self.state.owner_last_seen = now

    def set_mode(self, new_mode: str, requested_by: Optional[str] = None):
        """Set control mode and optionally claim ownership."""
        now = time.time()
        with self.lock:
            self.state.mode = new_mode
            if requested_by:
                self.state.owner = requested_by
                self.state.owner_since = now
                self.state.owner_last_seen = now

    def check_owner_timeout(self) -> bool:
        """Check if owner has timed out. Returns True if owner was reset."""
        with self.lock:
            if self.state.owner != "none" and time.time() - self.state.owner_last_seen > Config.OWNER_TIMEOUT_SEC:
                self.state.owner = "none"
                self.state.mode = "manual"
                return True
        return False

    def increment_trigger_count(self):
        """Increment trigger count."""
        with self.lock:
            self.state.trigger_count += 1

    def get_state_payload(self) -> dict:
        """Get current state as a dictionary payload."""
        with self.lock:
            payload = {
                **self.state.to_dict(),
                "pan_angle": round(self.state.pan_angle, 2),
                "tilt_angle": round(self.state.tilt_angle, 2),
                "pan_target": round(self.state.pan_target, 2),
                "tilt_target": round(self.state.tilt_target, 2),
                "backend": self.active_backend,
                "simulated_io": self.simulated_io,
                "ts": time.time(),
            }
        return payload

    def publish_state(self, client: Optional[mqtt.Client]):
        """Publish current state to MQTT."""
        payload = self.get_state_payload()
        if client is not None:
            client.publish(Config.topic("state"), json.dumps(payload), qos=0, retain=True)
        if Config.STATE_LOGGING:
            print(json.dumps(payload, sort_keys=True))
