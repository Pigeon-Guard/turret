"""Configuration management using environment variables."""
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # MQTT Configuration
    MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
    MQTT_TOPIC = os.getenv("MQTT_TOPIC", "pguard")
    MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "pguard-turret")

    # Timing Configuration
    OWNER_TIMEOUT_SEC = float(os.getenv("OWNER_TIMEOUT_SEC", "2.0"))
    STEP_INTERVAL_SEC = float(os.getenv("STEP_INTERVAL_SEC", "0.05"))
    STEP_DEG = float(os.getenv("STEP_DEG", "2.0"))

    # GPIO Pin Configuration
    PAN_PIN = int(os.getenv("PAN_PIN", "12"))
    TILT_PIN = int(os.getenv("TILT_PIN", "13"))
    TRIGGER_PIN = int(os.getenv("TRIGGER_PIN", "18"))
    TRIGGER_ACTIVE_HIGH = os.getenv("TRIGGER_ACTIVE_HIGH", "1") == "1"
    TRIGGER_PULSE_MS = int(os.getenv("TRIGGER_PULSE_MS", "180"))

    # Servo Limits
    PAN_MIN = float(os.getenv("PAN_MIN", "-85"))
    PAN_MAX = float(os.getenv("PAN_MAX", "85"))
    TILT_MIN = float(os.getenv("TILT_MIN", "-60"))
    TILT_MAX = float(os.getenv("TILT_MAX", "60"))

    # Backend Configuration
    SERVO_BACKEND = os.getenv("SERVO_BACKEND", "auto").lower()
    STATE_LOGGING = os.getenv("STATE_LOGGING", "1") == "1"

    @classmethod
    def topic(cls, name: str) -> str:
        """Generate MQTT topic path."""
        return f"{cls.MQTT_TOPIC}/{name}"
