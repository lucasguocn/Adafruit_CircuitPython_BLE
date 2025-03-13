
# SPDX-FileCopyrightText: 2020 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
Demonstration of a Bluefruit BLE Central for Circuit Playground Bluefruit. Connects to the first BLE
Nicla peripheral it finds. Sends Bluefruit ColorPackets, read from three accelerometer axis, to the
peripheral.
"""


from adafruit_ble.services.nicla import *
from NiclaBLESensorClient import NiclaBLESensorClient
from NiclaApp_BaroScale import NiclaApp_BaroScale


baroScale = NiclaApp_BaroScale(dbg = False)
baroScale.connectToDevice(macAddrFilter = "44:4d")
mqttcfg = {
        "hostname":"localhost",
        "port":1883,
        "user":None,
        "password":None,
        "clientid":"test_app.py"
        }
baroScale.setupMQTT(mqttcfg)

baroScale.startDataStreamingLoop(pressureSensorSR = 10.0)

