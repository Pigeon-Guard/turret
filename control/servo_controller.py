"""Servo control loop for smooth motion."""
import math
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt

from config.config import Config
from control.hardware import ServoAdapter
from control.state_manager import StateManager


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value between low and high."""
    return max(low, min(high, value))


class ServoController:
    """Controls servo motors with smooth motion."""

    def __init__(
        self,
        state_manager: StateManager,
        pan_servo: ServoAdapter,
        tilt_servo: ServoAdapter,
        shutdown_event: threading.Event
    ):
        self.state_manager = state_manager
        self.pan_servo = pan_servo
        self.tilt_servo = tilt_servo
        self.shutdown_event = shutdown_event

    def run(self, client: Optional[mqtt.Client]):
        """Main servo control loop."""
        while not self.shutdown_event.is_set():
            stale = self.state_manager.check_owner_timeout()

            with self.state_manager.lock:
                pan_diff = self.state_manager.state.pan_target - self.state_manager.state.pan_angle
                tilt_diff = self.state_manager.state.tilt_target - self.state_manager.state.tilt_angle

                if abs(pan_diff) > 0.2:
                    self.state_manager.state.pan_angle = clamp(
                        self.state_manager.state.pan_angle + math.copysign(min(abs(pan_diff), Config.STEP_DEG), pan_diff),
                        Config.PAN_MIN,
                        Config.PAN_MAX
                    )
                    self.pan_servo.set_angle(self.state_manager.state.pan_angle)

                if abs(tilt_diff) > 0.2:
                    self.state_manager.state.tilt_angle = clamp(
                        self.state_manager.state.tilt_angle + math.copysign(min(abs(tilt_diff), Config.STEP_DEG), tilt_diff),
                        Config.TILT_MIN,
                        Config.TILT_MAX
                    )
                    self.tilt_servo.set_angle(self.state_manager.state.tilt_angle)

            if stale:
                self.state_manager.publish_state(client)

            time.sleep(Config.STEP_INTERVAL_SEC)
