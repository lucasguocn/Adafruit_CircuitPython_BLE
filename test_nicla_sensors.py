# SPDX-FileCopyrightText: 2020 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
Demonstration of a Bluefruit BLE Central for Circuit Playground Bluefruit. Connects to the first BLE
Nicla peripheral it finds. Sends Bluefruit ColorPackets, read from three accelerometer axis, to the
peripheral.
"""


from adafruit_ble.services.nicla import *
from NiclaBLESensorClient import NiclaBLESensorClient


nicla_client = NiclaBLESensorClient()
nicla_client.try_connect_until_success()
sensorsCfg = {
    #latency is milli-seconds, if the rate for a sensor is higher than 25hz, recommends to have a latency larger than 40ms
    SENSOR_ID_ACC                               : {"sample_rate":000.0,                 "latency":90,    "cb":None},
    SENSOR_ID_GYR                               : {"sample_rate":000.0,                 "latency":90,    "cb":None},
    SENSOR_ID_ACC_RAW                           : {"sample_rate":000.0,                 "latency":90,    "cb":None},
    SENSOR_ID_GYR_RAW                           : {"sample_rate":000.0,                 "latency":90,    "cb":None},
    SENSOR_ID_BARO                              : {"sample_rate":0.0,                   "latency":0,     "cb":None},
    SENSOR_ID_TEMP                              : {"sample_rate":0.0,                   "latency":0,     "cb":None},
    SENSOR_ID_HUMID                             : {"sample_rate":0.0,                   "latency":0,     "cb":None},
    SENSOR_ID_BSEC                              : {"sample_rate":0.0,                   "latency":0,     "cb":None},
    SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR : {"sample_rate":0.0,                   "latency":0,     "cb":None},
    SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER     : {"sample_rate":0.0,                   "latency":0,     "cb":None},
    SENSOR_ID_NICLA_SYSTEM                      : {"sample_rate":0.0,                   "latency":0,     "cb":None},
}
nicla_client.configSensors(sensorsCfg)
nicla_client.loopPolling()

