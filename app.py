import json
import logging
import threading
import time
import random
from datetime import datetime
import paho.mqtt.client as mqtt

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("TurnstileMQTT")


class TurnstileMQTTClient:
    def __init__(self):
        # ---- Device identifiers (edit for your controller) ----
        self.serial = "1J9112"       # Serial in doc heartbeat example
        self.device_id = "1J9112"    # “ID” field in doc
        self.client_id = "12345"     # Any unique client-id

        # ---- MQTT broker ----
        self.broker = "192.168.0.116"     # or cloud host
        self.port = 1883                  # 8883 if TLS
        self.username = "user"
        self.password = "pass"
        self.keepalive = 60

        # ---- Topics from documentation ----
        self.heartbeat_topic = f"/sys/{self.serial}/{self.device_id}/thing/event/property/post"
        self.event_topic = f"/sys/{self.serial}/{self.device_id}/thing/event/post"
        self.cmd_topic = f"/sys/{self.serial}/{self.device_id}/thing/service/property/set"  # commands from server
        self.ack_topic = self.cmd_topic  # replies go to same topic

        self.client = None
        self.connected = False

    # ============================================================
    # MQTT Callbacks
    # ============================================================
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("Connected to MQTT broker")
            self.connected = True
            client.subscribe(self.cmd_topic, qos=1)
            log.info("Subscribed to command topic: %s", self.cmd_topic)
            self._start_heartbeat()
        else:
            log.error("Connect failed, rc=%s", rc)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            log.info("Got message on %s: %s", msg.topic, payload)
            method = payload.get("method")
            if method == "OpenDoor":
                self._handle_open(payload)
            elif method == "CloseDoor":
                self._handle_close(payload)
            elif method == "LockDoor":
                self._handle_lock(payload)
            else:
                log.warning("Unknown command: %s", method)
        except Exception as e:
            log.exception("Error handling msg: %s", e)

    def on_disconnect(self, *_):
        self.connected = False
        log.warning("Disconnected, will auto-reconnect if loop_start() running")

    # ============================================================
    # Connect / Disconnect
    # ============================================================
    def connect(self):
        self.client = mqtt.Client(client_id=self.client_id, clean_session=True)
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.client.connect(self.broker, self.port, self.keepalive)
        self.client.loop_start()

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    # ============================================================
    # Heartbeat
    # ============================================================
    def _start_heartbeat(self):
        def loop():
            while True:
                if self.connected:
                    self.send_heartbeat()
                time.sleep(30)
        threading.Thread(target=loop, daemon=True).start()

    def send_heartbeat(self):
        payload = {
            "id": random.randint(1, 9999),
            "version": "1.0",
            "taskNo": 10,
            "method": "Status",
            "data": {
                "Serial": self.serial,
                "ID": self.device_id,
                "DoorStatus": [0, 0],
                "Input": 0,
                "Now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Firmware": "0.2.128",
                "BuildTime": "Feb 13 2025 14:43:49",
                "PCBCode": "DD1B",
                "Model": "G-ZJ1000TCP",
                "TimeStamp": int(time.time()),
                "CardsInPacket": 16,
                "SystemOption": 57,
                "DoorRelay": [0, 0],
                "AlarmRelay": [0, 0],
                "Button": [0, 0],
                "Sensor": [0, 0],
                "AlarmIn": 0,
                "FireIn": 0,
                "TamperIn": 0,
                "ResetIn": 0
            }
        }
        self.client.publish(self.heartbeat_topic, json.dumps(payload), qos=1)

    # ============================================================
    # Events (card swipe)
    # ============================================================
    def send_card_event(self, card_no, door=1):
        evt = {
            "id": random.randint(100, 9999),
            "version": "1.0",
            "taskNo": 10,
            "method": "CardEvent",
            "data": {
                "Serial": self.serial,
                "Time": datetime.now().strftime("%Y%m%d%H%M%S"),
                "DataType": 0,
                "Card": str(card_no),
                "EventType": 1,
                "Door": door,
                "Reader": 0,
                "Exist": 1,
                "Pass": 1,
                "APBInOut": 0,
                "APBOn": 0,
                "Count": 0,
                "Index": 1
            }
        }
        self.client.publish(self.event_topic, json.dumps(evt), qos=1)

    # ============================================================
    # Command ACK helpers
    # ============================================================
    def _ack(self, req, method):
        resp = {
            "id": req.get("id", 0),
            "code": 0,
            "taskNo": req.get("taskNo", 10),
            "method": method,
            "message": "",
            "Serial": self.serial,
            "version": req.get("version", "1.0"),
            "data": {}
        }
        self.client.publish(self.ack_topic, json.dumps(resp), qos=1)

    # ============================================================
    # Command Handlers
    # ============================================================
    def _handle_open(self, payload):
        door = payload.get("data", {}).get("Door", 0)
        log.info(">>> Open door %s", door)
        # TODO: call hardware SDK
        self._ack(payload, "OpenDoor")

    def _handle_close(self, payload):
        door = payload.get("data", {}).get("Door", 0)
        log.info(">>> Close door %s", door)
        self._ack(payload, "CloseDoor")

    def _handle_lock(self, payload):
        door = payload.get("data", {}).get("Door", 0)
        state = payload.get("data", {}).get("Lock", 1)
        log.info(">>> Lock door %s (state=%s)", door, state)
        self._ack(payload, "LockDoor")


# =============================================================
# MAIN
# =============================================================
if __name__ == "__main__":
    client = TurnstileMQTTClient()
    try:
        client.connect()
        log.info("Turnstile MQTT client running... Ctrl+C to exit")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping client")
    finally:
        client.disconnect()
