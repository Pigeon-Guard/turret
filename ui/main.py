#!/usr/bin/env python3
"""Web UI server for Pigeon Guard Turret Control."""
import json
import socket
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
import paho.mqtt.client as mqtt

from config.config import Config

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
READER_JS_FILE = BASE_DIR / "reader.js"

app = Flask(__name__)
last_state = {
    "webrtc_url": Config.WEBRTC_URL,
    "mode": "manual",
    "owner": "none",
}


def get_local_ip():
    """Get local IP address for WebSocket configuration."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def on_connect(client, userdata, flags, rc, properties=None):
    """MQTT connection callback."""
    client.subscribe(Config.topic("state"))


def on_message(client, userdata, msg):
    """MQTT message callback."""
    global last_state
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        if isinstance(payload, dict):
            last_state.update(payload)
    except Exception:
        pass


# Initialize MQTT client
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, clean_session=True)
if Config.MQTT_USERNAME:
    mqtt_client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(Config.MQTT_HOST, Config.MQTT_PORT, keepalive=30)
mqtt_client.loop_start()


@app.route("/")
def index():
    """Serve the main UI HTML page."""
    return send_file(INDEX_FILE)


@app.route("/reader.js")
def reader_js():
    """Serve the MediaMTX WebRTC reader JavaScript."""
    return send_file(READER_JS_FILE, mimetype="application/javascript")


@app.route("/config.js")
def config_js():
    """Generate JavaScript configuration from environment."""
    request_host = request.host.split(':')[0]
    mqtt_host = Config.MQTT_HOST.replace("message", request_host)
    webrtc_url = Config.WEBRTC_URL.replace("video", request_host)

    config = {
        "mqttHost": mqtt_host or get_local_ip(),
        "mqttPort": Config.MQTT_WEBSOCKET_PORT,
        "mqttPath": Config.MQTT_WEBSOCKET_PATH,
        "mqttTopic": Config.MQTT_TOPIC,
        "uiOwner": Config.UI_OWNER,
        "webrtcUrl": last_state.get("webrtc_url", webrtc_url),
    }
    payload = f"window.APP_CONFIG = {json.dumps(config)};"
    return Response(payload, mimetype="application/javascript")


@app.route("/state")
def state():
    """Return current turret state."""
    return jsonify(last_state)


if __name__ == "__main__":
    app.run(host=Config.HTTP_HOST, port=Config.HTTP_PORT, debug=False)
