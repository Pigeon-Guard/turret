"""Hardware adapters for servo motors and trigger mechanism."""
import os
import sys
from typing import Optional, Tuple

# Set up mock GPIO if not on Linux
if os.getenv("GPIOZERO_PIN_FACTORY") is None and sys.platform != "linux":
    os.environ["GPIOZERO_PIN_FACTORY"] = "mock"

from gpiozero import AngularServo, DigitalOutputDevice


class TriggerAdapter:
    """Adapter for trigger control with optional simulation mode."""

    def __init__(self, pin: int, active_high: bool, pin_factory=None, simulate: bool = False):
        self.simulate = simulate
        self.pin = pin
        self.device = None if simulate else DigitalOutputDevice(
            pin, active_high=active_high, initial_value=False, pin_factory=pin_factory
        )
        self.value = False

    def on(self):
        """Activate trigger."""
        self.value = True
        if self.device:
            self.device.on()

    def off(self):
        """Deactivate trigger."""
        self.value = False
        if self.device:
            self.device.off()

    def close(self):
        """Close and cleanup device."""
        if self.device:
            self.device.close()


class ServoAdapter:
    """Adapter for servo motor control with optional simulation mode."""

    def __init__(
        self, pin: int, min_angle: float, max_angle: float, pin_factory=None, simulate: bool = False
    ):
        self.simulate = simulate
        self.pin = pin
        self.angle = 0.0
        self.device = None if simulate else AngularServo(
            pin, min_angle=min_angle, max_angle=max_angle, initial_angle=0, pin_factory=pin_factory
        )

    def set_angle(self, angle: float):
        """Set servo to specified angle."""
        self.angle = angle
        if self.device:
            self.device.angle = angle

    def detach(self):
        """Detach servo motor."""
        if self.device:
            self.device.detach()

    def close(self):
        """Close and cleanup device."""
        if self.device:
            self.device.close()


def build_pin_factory(backend: str) -> Tuple[Optional[object], bool, str]:
    """
    Build GPIO pin factory based on backend configuration.

    Args:
        backend: Backend type (mock, pigpio, simulate, auto)

    Returns:
        Tuple of (pin_factory, simulate_flag, active_backend_name)
    """
    if backend == "mock":
        from gpiozero.pins.mock import MockFactory
        return MockFactory(), True, "mock"

    if backend == "pigpio":
        from gpiozero.pins.pigpio import PiGPIOFactory
        return PiGPIOFactory(), False, "pigpio"

    if backend == "simulate":
        return None, True, "simulate"

    if os.getenv("GPIOZERO_PIN_FACTORY") == "mock":
        return None, True, "mock-env"

    # Auto mode: try pigpio, fallback to simulation
    try:
        from gpiozero.pins.pigpio import PiGPIOFactory
        return PiGPIOFactory(), False, "pigpio-auto"
    except Exception:
        return None, True, "simulate-fallback"
