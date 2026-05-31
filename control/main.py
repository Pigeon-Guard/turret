#!/usr/bin/env python3
"""Pigeon Guard Turret Control - Main entry point."""
import signal
import sys
import threading
import time

from config.config import Config
from control.hardware import build_pin_factory, ServoAdapter, TriggerAdapter
from control.mqtt_handler import MQTTHandler, create_mqtt_client
from control.servo_controller import ServoController
from control.state_manager import StateManager


class TurretApplication:
    """Main application class for turret control."""

    def __init__(self):
        self.shutdown_event = threading.Event()

        # Initialize hardware
        pin_factory, simulated_io, active_backend = build_pin_factory(Config.SERVO_BACKEND)
        self.active_backend = active_backend
        self.simulated_io = simulated_io

        self.pan_servo = ServoAdapter(
            Config.PAN_PIN, Config.PAN_MIN, Config.PAN_MAX,
            pin_factory=pin_factory, simulate=simulated_io
        )
        self.tilt_servo = ServoAdapter(
            Config.TILT_PIN, Config.TILT_MIN, Config.TILT_MAX,
            pin_factory=pin_factory, simulate=simulated_io
        )
        self.trigger = TriggerAdapter(
            Config.TRIGGER_PIN, Config.TRIGGER_ACTIVE_HIGH,
            pin_factory=pin_factory, simulate=simulated_io
        )

        # Initialize state and controllers
        self.state_manager = StateManager(active_backend, simulated_io)
        self.mqtt_handler = MQTTHandler(self.state_manager, self.pulse_trigger)
        self.servo_controller = ServoController(
            self.state_manager, self.pan_servo, self.tilt_servo, self.shutdown_event
        )

        # Initialize MQTT client
        self.client = create_mqtt_client(self.mqtt_handler)

    def pulse_trigger(self, client, source):
        """Execute trigger pulse in background thread."""
        def worker():
            self.trigger.on()
            time.sleep(Config.TRIGGER_PULSE_MS / 1000.0)
            self.trigger.off()
            self.state_manager.increment_trigger_count()
            self.state_manager.publish_state(client)

        threading.Thread(target=worker, daemon=True).start()

    def install_signal_handlers(self):
        """Install signal handlers for graceful shutdown."""
        def handler(signum, frame):
            self.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def cleanup(self):
        """Cleanup resources and shutdown."""
        self.shutdown_event.set()

        try:
            if self.client is not None:
                self.client.loop_stop()
                self.client.disconnect()
        except Exception:
            pass

        try:
            self.trigger.off()
            self.pan_servo.detach()
            self.tilt_servo.detach()
            self.trigger.close()
            self.pan_servo.close()
            self.tilt_servo.close()
        except Exception:
            pass

    def print_setup_notes(self):
        """Print startup information."""
        notes = f"""
Pi Zero controller started.
Backend: {self.active_backend} (simulated_io={self.simulated_io})
MQTT: {Config.MQTT_HOST}:{Config.MQTT_PORT}
Topics:
  {Config.topic('mode/set')}
  {Config.topic('manual/joystick')}
  {Config.topic('servo/set')}
  {Config.topic('trigger/fire')}
  {Config.topic('state')}
Servo pins: pan={Config.PAN_PIN}, tilt={Config.TILT_PIN}, trigger={Config.TRIGGER_PIN}
""".strip()
        print(notes)

    def run(self):
        """Run the application."""
        self.install_signal_handlers()

        # Connect to MQTT and start event loop
        self.client.connect(Config.MQTT_HOST, Config.MQTT_PORT, keepalive=30)
        self.client.loop_start()

        # Start servo control loop in background
        threading.Thread(
            target=self.servo_controller.run,
            args=(self.client,),
            daemon=True
        ).start()

        self.print_setup_notes()

        # Main loop
        while not self.shutdown_event.is_set():
            time.sleep(1)


def main():
    """Application entry point."""
    app = TurretApplication()
    app.run()


if __name__ == "__main__":
    main()
