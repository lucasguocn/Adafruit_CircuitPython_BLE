import paho.mqtt.client as mqtt
import json
import random
import time

class SensorMQTTClient:
    def __init__(self, hostname, port=1883, user=None, password=None, clientid=None, dbg = False):
        """
        Initialize the MQTT client.
        
        :param hostname: MQTT broker address.
        :param port: MQTT broker port (default 1883).
        :param user: Optional username for authentication.
        :param password: Optional password for authentication.
        :param clientid: Optional client ID (if None, a random one is assigned).
        """
        self.hostname = hostname
        self.port = port
        self.client = mqtt.Client(client_id=clientid)  # Create an MQTT client
        self.dbg = dbg
        
        # Set authentication if provided
        if user and password:
            self.client.username_pw_set(user, password)

        # Dictionary to store users and their subscribed topics with callbacks
        self.subscribers = {}

        # Set callback functions
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        """Handles connection to the MQTT broker."""
        if rc == 0:
            if self.dbg:
                print(f"Connected to MQTT Broker at {self.hostname}:{self.port}")
        else:
            if self.dbg:
                print(f"Failed to connect, return code {rc}")

    def on_message(self, client, userdata, msg):
        """Handles incoming messages and triggers the appropriate callbacks."""
        try:
            payload = msg.payload.decode()
            if self.dbg:
                print(f"Received message on topic:[{msg.topic}]: payload:[{payload}]")
            
            # Notify all users subscribed to this topic
            if msg.topic in self.subscribers:
                for callback in self.subscribers[msg.topic]:
                    callback(msg.topic, payload)
        except Exception as e:
            print(f"Error processing message: {e}")

    def on_disconnect(self, client, userdata, rc):
        """Handles unexpected disconnection."""
        if self.dbg:
            print("Disconnected from MQTT Broker. Reconnecting...")
        client.reconnect()

    def publish(self, topic, message):
        """Publishes a message to a specified topic."""
        self.client.publish(topic, json.dumps(message))
        #self.client.publish(topic, (message))
        if self.dbg:
            print(f"Published to {topic}: {message}")

    def subscribe(self, topic, callback):
        """Subscribe a user to a topic with their corresponding callback."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []

        # Add the callback to the topic's list of subscribers
        self.subscribers[topic].append(callback)
        self.client.subscribe(topic)
        if self.dbg:
            print(f"Subscribed to topic: {topic}")

    def start(self):
        """Connects to the MQTT broker and starts the loop."""
        if self.dbg:
            print("Starting MQTT client...")
        self.client.connect(self.hostname, self.port, 60)
        self.client.loop_start()  # Start the background loop

    def stop(self):
        """Stops the MQTT client."""
        if self.dbg:
            print("Stopping MQTT client...")
        self.client.loop_stop()
        self.client.disconnect()


# Test code to run when the script is executed directly
if __name__ == "__main__":
    # Custom message callback function for user 1
    def user1_callback(topic, payload):
        print(f"User 1 received message on {topic}: {payload}")


    # Test MQTT Client with localhost
    mqtt_client = SensorMQTTClient(
        hostname="localhost",
        port=1883,
        user=None,  # No authentication
        password=None,  # No password
        clientid="TestClient1"
    )

    # Start the client
    mqtt_client.start()

    # Subscribe user 1 to the topic "nicla/cmd" with their callback
    mqtt_client.subscribe("nicla/cmd", user1_callback)


    # Publish random pressure data at 10Hz for 10 seconds to "nicla/data/pressure"
    for _ in range(100):  # 10Hz for 10s -> 100 iterations
        pressure_data = {
            "pressure": round(random.uniform(950, 1050), 2)  # Random pressure between 950 and 1050 hPa
        }
        mqtt_client.publish("nicla/data/pressure", pressure_data)
        time.sleep(0.1)  # Wait for 100ms (10Hz)


    # Stop the client
    mqtt_client.stop()
