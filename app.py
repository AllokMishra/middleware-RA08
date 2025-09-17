import json
import logging
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TurnstileMQTTClient:
    def __init__(self):
        self.client = None
        self.connected = False
        self.serial_no = "119112"  # From your configuration
        self.device_id = "1J9112"   # From your configuration
        
        # MQTT Configuration - You'll need to set these parameters
        self.broker_host = "your-mqtt-broker.com"  # e.g., "mqtt.eclipse.org"
        self.broker_port = 1883
        self.username = "username"
        self.password = "password"
        self.keepalive = 60
        
        # Topics
        self.status_topic = f"/sys/{self.serial_no}/{self.device_id}/thing/event/property/post"
        self.event_topic = f"/sys/{self.serial_no}/{self.device_id}/thing/event/post"
        self.command_topic = f"/sys/{self.serial_no}/{self.device_id}/thing/command/post"

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
            self.connected = True
            # Subscribe to command topic
            client.subscribe(self.command_topic)
            logger.info(f"Subscribed to command topic: {self.command_topic}")
            # Start heartbeat thread
            self.start_heartbeat()
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            logger.info(f"Received message on topic {msg.topic}: {payload}")
            
            data = json.loads(payload)
            method = data.get("method", "")
            
            # Handle different commands
            if method == "OpenDoor":
                self.handle_open_door(data)
            elif method == "CloseDoor":
                self.handle_close_door(data)
            elif method == "LockDoor":
                self.handle_lock_door(data)
            # Add more command handlers as needed
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT broker, return code: {rc}")
        self.connected = False

    def connect(self):
        """Connect to MQTT broker"""
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        try:
            self.client.connect(self.broker_host, self.broker_port, self.keepalive)
            self.client.loop_start()
            logger.info("MQTT client started")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    def start_heartbeat(self):
        """Start sending heartbeat messages"""
        def heartbeat_loop():
            while True:
                if self.connected:
                    self.send_heartbeat()
                time.sleep(30)  # Send heartbeat every 30 seconds
        
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        logger.info("Heartbeat thread started")

    def send_heartbeat(self):
        """Send status heartbeat"""
        heartbeat_data = {
            "id": random.randint(1, 1000),
            "version": "1.0",
            "method": "Status",
            "taskNo": 10,
            "data": {
                "Serial": self.serial_no,
                "ID": self.device_id,
                "DoorStatus": [0, 0],  # Example: [door1_status, door2_status]
                "Input": 0,
                "Now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Firmware": "0.2.128",
                "BuildTime": "Feb 13 2025 14:43:49",
                "PCBCode": "DD1B",
                "Model": "G-ZJ1000TCP",
                "TimeStamp": int(time.time()),
                "CardsinPacket": 16,
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
        
        try:
            result = self.client.publish(self.status_topic, json.dumps(heartbeat_data))
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info("Heartbeat sent successfully")
            else:
                logger.error(f"Failed to send heartbeat: {result.rc}")
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    def send_card_event(self, card_number, door=1, event_type=1):
        """Send card swipe event"""
        event_data = {
            "id": random.randint(1, 1000),
            "version": "1.0",
            "taskNo": 10,
            "method": "CardEvent",
            "data": {
                "Serial": self.serial_no,
                "Time": datetime.now().strftime("%Y%m%d%H%M%S"),
                "DataType": 0,
                "Card": str(card_number),
                "EventType": event_type,
                "Door": door,
                "Reader": 0,
                "Exist": 1,
                "Pass": 1,
                "APBInOut": 0,
                "APBOn": 0,
                "Count": 0,
                "Index": random.randint(1, 1000)
            }
        }
        
        try:
            result = self.client.publish(self.event_topic, json.dumps(event_data))
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Card event sent for card: {card_number}")
            else:
                logger.error(f"Failed to send card event: {result.rc}")
        except Exception as e:
            logger.error(f"Error sending card event: {e}")

    def handle_open_door(self, data):
        """Handle open door command"""
        door = data.get("data", {}).get("Door", 0)
        open_cmd = data.get("data", {}).get("Open", 1)
        
        logger.info(f"Received open door command: Door={door}, Open={open_cmd}")
        
        # Here you would implement the actual door opening logic
        # For now, we'll just log it and send a response
        
        response = {
            "id": data["id"],
            "code": "0",
            "taskNo": data["taskNo"],
            "method": "OpenDoor",
            "message": "",
            "Serial": self.serial_no,
            "version": data["version"],
            "data": {}
        }
        
        try:
            self.client.publish(self.command_topic, json.dumps(response))
            logger.info("Open door response sent")
        except Exception as e:
            logger.error(f"Error sending open door response: {e}")

    def handle_close_door(self, data):
        """Handle close door command"""
        door = data.get("data", {}).get("Door", 0)
        logger.info(f"Received close door command for door: {door}")
        
        # Implement door closing logic here
        
        response = {
            "id": data["id"],
            "code": "0",
            "taskNo": data["taskNo"],
            "method": "CloseDoor",
            "message": "",
            "Serial": self.serial_no,
            "version": data["version"],
            "data": {}
        }
        
        try:
            self.client.publish(self.command_topic, json.dumps(response))
            logger.info("Close door response sent")
        except Exception as e:
            logger.error(f"Error sending close door response: {e}")

    def handle_lock_door(self, data):
        """Handle lock door command"""
        door = data.get("data", {}).get("Door", 0)
        lock = data.get("data", {}).get("Lock", 1)
        
        logger.info(f"Received lock door command: Door={door}, Lock={lock}")
        
        # Implement door locking logic here
        
        response = {
            "id": data["id"],
            "code": "0",
            "taskNo": data["taskNo"],
            "method": "LockDoor",
            "message": "",
            "Serial": self.serial_no,
            "version": data["version"],
            "data": 0
        }
        
        try:
            self.client.publish(self.command_topic, json.dumps(response))
            logger.info("Lock door response sent")
        except Exception as e:
            logger.error(f"Error sending lock door response: {e}")

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")

# Usage example
if __name__ == "__main__":
    # Create requirements.txt with: paho-mqtt
    
    mqtt_client = TurnstileMQTTClient()
    
    try:
        mqtt_client.connect()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down MQTT client")
    finally:
        mqtt_client.disconnect()
