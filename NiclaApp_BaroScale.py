# SPDX-FileCopyrightText: 2020 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
Demonstration of a Bluefruit BLE Central for Circuit Playground Bluefruit. Connects to the first BLE
Nicla peripheral it finds. Sends Bluefruit ColorPackets, read from three accelerometer axis, to the
peripheral.
"""


from adafruit_ble.services.nicla import *
from NiclaBLESensorClient import NiclaBLESensorClient
import struct
from SensorMQTTClient import SensorMQTTClient

class NiclaApp_BaroScale:
    def __init__(self, dbg:bool = True):
        self.dbg = dbg
    def connectToDevice(self, macAddrFilter:str=""):
        self.nicla_client = NiclaBLESensorClient(macAddrFilter=macAddrFilter, printData = False)
        success = self.nicla_client.try_connect_until_success(timeout_sec = 10)
        if success:
            self.nicla_mac_addr_s = self.nicla_client.nicla_mac_addr[-5:]
            if self.dbg:
                print(f"Nicla Sense ME device: {self.nicla_client.nicla_mac_addr} connected, short name: {self.nicla_mac_addr_s}")
        else:
            print("failed with connection")
        return success

    def startDataStreamingLoop(self, pressureSensorSR:float = 10.0):
        #this function might loop endlessly,
        #so make sure other configurations are finished before calling this one
        if self.nicla_mac_addr_s:
            sensorsCfg = {
                #latency is milli-seconds, if the rate for a sensor is higher than 25hz, recommends to have a latency larger than 40ms
                SENSOR_ID_ACC                               : {"sample_rate":000.0,                 "latency":90,    "cb":None},
                SENSOR_ID_GYR                               : {"sample_rate":000.0,                 "latency":90,    "cb":None},
                SENSOR_ID_ACC_RAW                           : {"sample_rate":000.0,                 "latency":90,    "cb":None},
                SENSOR_ID_GYR_RAW                           : {"sample_rate":000.0,                 "latency":90,    "cb":None},
                SENSOR_ID_BARO                              : {"sample_rate":pressureSensorSR,                  "latency":0,     "cb":self.__cb_sensor_data_ready_baro_app},
                SENSOR_ID_TEMP                              : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_HUMID                             : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_BSEC                              : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER     : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_NICLA_SYSTEM                      : {"sample_rate":0.0,                   "latency":0,     "cb":None},
            }
            success = self.nicla_client.configSensors(sensorsCfg)
            if success:
                self.nicla_client.loopPolling()
            else:
                print("failed with sensor configuration")
        else:
            print("no active connection")

    def __cb_sensor_data_ready_baro_app(self, timestamp, sensorFrame, pkt_size):
        buf = sensorFrame[1: 4+1+1] #baro sensor is 3bytes long, need an extra byte for a padding 0
        buf[4] = 0
        (sz, baro) = struct.unpack("<BI", buf)
        scale = nicla_sensors_desc_tab[SENSOR_ID_BARO]["scale"]
        baro = baro * scale

        if self.dbg:
            print(f"new_event,baro,{timestamp}, {baro}")
        if self.mqtt_client is not None:
            pressure_data = {
                    "value":baro,
                    "timestamp": str(timestamp)
            }
            topic = "nicla/" + self.nicla_mac_addr_s + "/data/pressure"
            self.mqtt_client.publish(topic, pressure_data)
            #msg_pres_data = '{"value":' + str(baro) + ',' + '"timestamp":' + str(timestamp) + '}'
            #msg_pres_data = '{"value":' + str(baro) + ',' + '"timestamp":' + str(timestamp) + '}'
            #self.mqtt_client.publish(topic, msg_pres_data)



    # Custom message callback function for user 1
    def __cb_mqtt_app_baro_scale(self, topic, payload):
        print(f"User 1 received message on {topic}: {payload}")

    def setupMQTT(self, mqttCfg:dict)->bool:
        # Test MQTT Client with localhost
        self.mqtt_client = SensorMQTTClient(
            hostname=mqttCfg["hostname"],
            port=mqttCfg["port"],
            user=mqttCfg["user"],
            password=mqttCfg["password"],
            clientid=mqttCfg["clientid"]
        )

        # Start the client
        self.mqtt_client.start()

        # Subscribe user 1 to the topic "nicla/cmd" with their callback
        self.mqtt_client.subscribe("nicla/+/cmd", self.__cb_mqtt_app_baro_scale)


