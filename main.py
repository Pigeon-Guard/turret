#!/usr/bin/env python3
import json
import math
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional

if os.getenv("GPIOZERO_PIN_FACTORY") is None and sys.platform != "linux":
    os.environ["GPIOZERO_PIN_FACTORY"] = "mock"

import paho.mqtt.client as mqtt
from gpiozero import AngularServo, DigitalOutputDevice


MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "pguard")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "pguard-turret")
OWNER_TIMEOUT_SEC = float(os.getenv("OWNER_TIMEOUT_SEC", "2.0"))
STEP_INTERVAL_SEC = float(os.getenv("STEP_INTERVAL_SEC", "0.05"))
STEP_DEG = float(os.getenv("STEP_DEG", "2.0"))
PAN_PIN = int(os.getenv("PAN_PIN", "12"))
TILT_PIN = int(os.getenv("TILT_PIN", "13"))
TRIGGER_PIN = int(os.getenv("TRIGGER_PIN", "18"))
TRIGGER_ACTIVE_HIGH = os.getenv("TRIGGER_ACTIVE_HIGH", "1") == "1"
TRIGGER_PULSE_MS = int(os.getenv("TRIGGER_PULSE_MS", "180"))
PAN_MIN = float(os.getenv("PAN_MIN", "-85"))
PAN_MAX = float(os.getenv("PAN_MAX", "85"))
TILT_MIN = float(os.getenv("TILT_MIN", "-60"))
TILT_MAX = float(os.getenv("TILT_MAX", "60"))
SERVO_BACKEND = os.getenv("SERVO_BACKEND", "auto").lower()
STATE_LOGGING = os.getenv("STATE_LOGGING", "1") == "1"


@dataclass
class SharedState:
    mode: str = "manual"
    owner: str = "none"
    owner_since: float = 0.0
    owner_last_seen: float = 0.0
    pan_target: float = 0.0
    tilt_target: float = 0.0
    pan_angle: float = 0.0
    tilt_angle: float = 0.0
    trigger_count: int = 0


class TriggerAdapter:
    def __init__(self, pin: int, active_high: bool, pin_factory=None, simulate: bool = False):
        self.simulate = simulate
        self.pin = pin
        self.device = None if simulate else DigitalOutputDevice(pin, active_high=active_high, initial_value=False, pin_factory=pin_factory)
        self.value = False

    def on(self):
        self.value = True
        if self.device:
            self.device.on()

    def off(self):
        self.value = False
        if self.device:
            self.device.off()

    def close(self):
        if self.device:
            self.device.close()


class ServoAdapter:
    def __init__(self, pin: int, min_angle: float, max_angle: float, pin_factory=None, simulate: bool = False):
        self.simulate = simulate
        self.pin = pin
        self.angle = 0.0
        self.device = None if simulate else AngularServo(pin, min_angle=min_angle, max_angle=max_angle, initial_angle=0, pin_factory=pin_factory)

    def set_angle(self, angle: float):
        self.angle = angle
        if self.device:
            self.device.angle = angle

    def detach(self):
        if self.device:
            self.device.detach()

    def close(self):
        if self.device:
            self.device.close()


state = SharedState()
lock = threading.Lock()
shutdown_event = threading.Event()


def build_pin_factory():
    backend = SERVO_BACKEND
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
    try:
        from gpiozero.pins.pigpio import PiGPIOFactory
        return PiGPIOFactory(), False, "pigpio-auto"
    except Exception:
        return None, True, "simulate-fallback"


PIN_FACTORY, SIMULATED_IO, ACTIVE_BACKEND = build_pin_factory()
pan_servo = ServoAdapter(PAN_PIN, PAN_MIN, PAN_MAX, pin_factory=PIN_FACTORY, simulate=SIMULATED_IO)
tilt_servo = ServoAdapter(TILT_PIN, TILT_MIN, TILT_MAX, pin_factory=PIN_FACTORY, simulate=SIMULATED_IO)
trigger = TriggerAdapter(TRIGGER_PIN, TRIGGER_ACTIVE_HIGH, pin_factory=PIN_FACTORY, simulate=SIMULATED_IO)


def clamp(value, low, high):
    return max(low, min(high, value))


def topic(name):
    return f"{MQTT_TOPIC}/{name}"


def get_local_ip():
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def current_state_payload():
    with lock:
        payload = {
            **asdict(state),
            "pan_angle": round(state.pan_angle, 2),
            "tilt_angle": round(state.tilt_angle, 2),
            "pan_target": round(state.pan_target, 2),
            "tilt_target": round(state.tilt_target, 2),
            "backend": ACTIVE_BACKEND,
            "simulated_io": SIMULATED_IO,
            "ts": time.time(),
        }
    return payload


def publish_state(client: Optional[mqtt.Client]):
    payload = current_state_payload()
    if client is not None:
        client.publish(topic("state"), json.dumps(payload), qos=0, retain=True)
    if STATE_LOGGING:
        print(json.dumps(payload, sort_keys=True))


def claim_owner(requested_owner):
    now = time.time()
    with lock:
        if state.owner != requested_owner:
            state.owner = requested_owner
            state.owner_since = now
        state.owner_last_seen = now


def set_mode(new_mode, requested_by=None):
    now = time.time()
    with lock:
        state.mode = new_mode
        if requested_by:
            state.owner = requested_by
            state.owner_since = now
            state.owner_last_seen = now


def handle_manual_command(client, payload):
    owner = payload.get("owner", "manual-ui")
    claim_owner(owner)
    with lock:
        if state.mode != "manual" or state.owner != owner:
            return
        dx = float(payload.get("dx", 0.0))
        dy = float(payload.get("dy", 0.0))
        state.pan_target = clamp(state.pan_target + dx * STEP_DEG, PAN_MIN, PAN_MAX)
        state.tilt_target = clamp(state.tilt_target - dy * STEP_DEG, TILT_MIN, TILT_MAX)
    publish_state(client)


def handle_set_angles(client, payload):
    owner = payload.get("owner", "pi5")
    requested_mode = payload.get("mode", "auto")
    if requested_mode not in {"auto", "manual"}:
        requested_mode = "auto"
    claim_owner(owner)
    with lock:
        if state.mode != requested_mode or state.owner != owner:
            return
        if "pan" in payload:
            state.pan_target = clamp(float(payload["pan"]), PAN_MIN, PAN_MAX)
        if "tilt" in payload:
            state.tilt_target = clamp(float(payload["tilt"]), TILT_MIN, TILT_MAX)
    publish_state(client)


def pulse_trigger(client, source):
    def worker():
        trigger.on()
        time.sleep(TRIGGER_PULSE_MS / 1000.0)
        trigger.off()
        with lock:
            state.trigger_count += 1
        publish_state(client)
    threading.Thread(target=worker, daemon=True).start()


def on_connect(client, userdata, flags, rc, properties=None):
    client.subscribe(topic("mode/set"))
    client.subscribe(topic("manual/joystick"))
    client.subscribe(topic("servo/set"))
    client.subscribe(topic("trigger/fire"))
    client.subscribe(topic("heartbeat"))
    publish_state(client)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8")) if msg.payload else {}
    except json.JSONDecodeError:
        return

    if msg.topic == topic("mode/set"):
        mode = payload.get("mode")
        owner = payload.get("owner", "unknown")
        if mode in {"auto", "manual"}:
            set_mode(mode, owner)
            publish_state(client)
        return

    if msg.topic == topic("heartbeat"):
        owner = payload.get("owner", "unknown")
        claim_owner(owner)
        publish_state(client)
        return

    if msg.topic == topic("manual/joystick"):
        handle_manual_command(client, payload)
        return

    if msg.topic == topic("servo/set"):
        handle_set_angles(client, payload)
        return

    if msg.topic == topic("trigger/fire"):
        owner = payload.get("owner", "unknown")
        with lock:
            allowed = state.owner == owner and state.mode == payload.get("mode", state.mode)
        if allowed:
            pulse_trigger(client, owner)


def servo_loop(client):
    while not shutdown_event.is_set():
        stale = False
        with lock:
            if state.owner != "none" and time.time() - state.owner_last_seen > OWNER_TIMEOUT_SEC:
                stale = True
                state.owner = "none"
                state.mode = "manual"
            pan_diff = state.pan_target - state.pan_angle
            tilt_diff = state.tilt_target - state.tilt_angle
            if abs(pan_diff) > 0.2:
                state.pan_angle = clamp(state.pan_angle + math.copysign(min(abs(pan_diff), STEP_DEG), pan_diff), PAN_MIN, PAN_MAX)
                pan_servo.set_angle(state.pan_angle)
            if abs(tilt_diff) > 0.2:
                state.tilt_angle = clamp(state.tilt_angle + math.copysign(min(abs(tilt_diff), STEP_DEG), tilt_diff), TILT_MIN, TILT_MAX)
                tilt_servo.set_angle(state.tilt_angle)
        if stale or STATE_LOGGING:
            publish_state(client)
        time.sleep(STEP_INTERVAL_SEC)


def cleanup(client=None):
    shutdown_event.set()
    try:
        if client is not None:
            client.loop_stop()
            client.disconnect()
    except Exception:
        pass
    try:
        trigger.off()
        pan_servo.detach()
        tilt_servo.detach()
        trigger.close()
        pan_servo.close()
        tilt_servo.close()
    except Exception:
        pass


def install_signal_handlers(client):
    def handler(signum, frame):
        cleanup(client)
        sys.exit(0)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def print_setup_notes():
    notes = f"""
Pi Zero controller started.
Backend: {ACTIVE_BACKEND} (simulated_io={SIMULATED_IO})
MQTT: {MQTT_HOST}:{MQTT_PORT}
Topics:
  {topic('mode/set')}
  {topic('manual/joystick')}
  {topic('servo/set')}
  {topic('trigger/fire')}
  {topic('state')}
Servo pins: pan={PAN_PIN}, tilt={TILT_PIN}, trigger={TRIGGER_PIN}
""".strip()
    print(notes)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID, clean_session=True)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set(topic("state"), json.dumps({"status": "offline", "ts": time.time()}), retain=True)
    install_signal_handlers(client)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    threading.Thread(target=servo_loop, args=(client,), daemon=True).start()
    print_setup_notes()
    while not shutdown_event.is_set():
        time.sleep(1)


if __name__ == "__main__":
    main()
