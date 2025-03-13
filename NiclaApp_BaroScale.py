# SPDX-FileCopyrightText: 2020 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
Demonstration of a Bluefruit BLE Central for Circuit Playground Bluefruit. Connects to the first BLE
Nicla peripheral it finds. Sends Bluefruit ColorPackets, read from three accelerometer axis, to the
peripheral.
"""


from adafruit_ble.services.nicla import *
from NiclaBLESensorClient import NiclaBLESensorClient
from SensorMQTTClient import SensorMQTTClient
import struct
import json

class NiclaApp_BaroScale:
    def __init__(self, printData:bool = True, dbg:bool = True):
        self.dbg = dbg
        self.printData = printData
        self.calib_status = False
        self.calib_offset = 0
    def connectToDevice(self, macAddrFilter:str=""):
        self.nicla_client = NiclaBLESensorClient(macAddrFilter=macAddrFilter, printData = False, dbg = self.dbg)
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
                SENSOR_ID_BARO                              : {"sample_rate":10.0,                  "latency":0,     "cb":self.__cb_sensor_data_ready_baro_app},
                SENSOR_ID_TEMP                              : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_HUMID                             : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_BSEC                              : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER     : {"sample_rate":0.0,                   "latency":0,     "cb":None},
                SENSOR_ID_NICLA_SYSTEM                      : {"sample_rate":0.0,                   "latency":0,     "cb":None},
            }
            success = self.nicla_client.configSensors(sensorsCfg)
            if self.printData:
                print(f"Sensor Name, Timestamp, Barometer Value (Pa), Calibration Offset (g), Calibration Status")
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

        if self.printData:
            print(f"Barometer,{timestamp}, {baro}, {self.calib_offset}, {self.calib_status}")
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



    def __handler_calib_start(self, args:list = None)->int:
        return 0

    # Custom message callback function 
    def __cb_mqtt_app_baro_scale(self, topic, payload):
        print(f"App received message on [{topic}]: [{payload}]")
        #example valid message:
        #topic:[nicla/44:4D/cmd]: 
        #payload:[{"_payload":{"payload":{"command":"calibrate_start","arg1":503},,"socketid":"IEI2qi-67j9Ex3-dAAAD"}}]

        cmd_handlers = {
                "calibrate_start"   :{'cb':__handler_calib_start,   'num_args' : 1},
                "calibrate_stop"    :{'cb':__handler_calib_stop,    'num_args' : 0},
                "tare"              :{'cb':__handler_tare,          'num_args' : 0},
                }
        try:
            # Attempt to parse the JSON message
            data = json.loads(payload)

            # Safely extract the values
            command = data["_payload"]["payload"].get("command", None)
            arg1 = data["_payload"]["payload"].get("arg1", None)

            if self.dbg:
                print("command:", command)
                print("arg1:", arg1)

            if command in cmd_handlers:
                num_args = cmd_handlers[command].get('num_args', 0)

        except json.JSONDecodeError:
            print("Error: Received an invalid JSON message")
        except KeyError as e:
            print(f"Error: Missing key in JSON message - {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    def setupMQTT(self, mqttCfg:dict)->bool:
        # Test MQTT Client with localhost
        self.mqtt_client = SensorMQTTClient(
            hostname=mqttCfg["hostname"],
            port=mqttCfg["port"],
            user=mqttCfg["user"],
            password=mqttCfg["password"],
            clientid=mqttCfg["clientid"],
            dbg = self.dbg
        )

        # Start the client
        self.mqtt_client.start()

        # Subscribe user 1 to the topic "nicla/cmd" with their callback
        topic_lower = "nicla/" + self.nicla_mac_addr_s.lower() + "/cmd"
        topic_upper = "nicla/" + self.nicla_mac_addr_s.upper() + "/cmd"
        self.mqtt_client.subscribe(topic_lower, self.__cb_mqtt_app_baro_scale)
        self.mqtt_client.subscribe(topic_upper, self.__cb_mqtt_app_baro_scale)


