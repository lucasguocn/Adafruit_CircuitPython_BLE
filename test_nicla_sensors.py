# SPDX-FileCopyrightText: 2020 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
Demonstration of a Bluefruit BLE Central for Circuit Playground Bluefruit. Connects to the first BLE
Nicla peripheral it finds. Sends Bluefruit ColorPackets, read from three accelerometer axis, to the
peripheral.
"""

import time
import datetime
import struct

import busio
import digitalio

import sys

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nicla import *



ble = BLERadio()

nicla_connection = None
# See if any existing connections are providing NiclaService.
if ble.connected:
    for connection in ble.connections:
        if NiclaService in connection:
            nicla_connection = connection
        break


# set sample_rate 0 to turn off a sensor
configSensors = {
        SENSOR_ID_ACC       : {"sample_rate":0.0},
        SENSOR_ID_TEMP      : {"sample_rate":1.0},
        SENSOR_ID_HUMID     : {"sample_rate":1.0},
        }

max_sample_rate = 0.0

#DEBUG = True
DEBUG = False


sensorDataBuf = bytearray(100 * NICLA_BLE_SENSOR_DATA_PKT_SIZE)
t_prev = datetime.datetime.now()
while True:
    if not nicla_connection:
        print("Scanning...")
        for adv in ble.start_scan(ProvideServicesAdvertisement, timeout=5):
            if NiclaService in adv.services:
                print("found a Nicla Sense ME device")
                nicla_connection = ble.connect(adv)
                break
        # Stop scanning whether or not we are connected.
        ble.stop_scan()

    sensorConfigured = False
    sensorDataPktCnt = 0
    while nicla_connection and nicla_connection.connected:
        try:
            if not sensorConfigured:
                st = struct.Struct("=BfI")
                sensorConfigPkt = bytearray(NICLA_BLE_SENSOR_CFG_PKT_SIZE)
                for sensor in configSensors:
                    sample_rate = configSensors[sensor]["sample_rate"]
                    st.pack_into(sensorConfigPkt, 0, sensor, sample_rate, 0)

                    if (max_sample_rate < sample_rate):
                        max_sample_rate = sample_rate

                    if DEBUG:
                        for b in sensorConfigPkt: print(hex(b))

                    nicla_connection[NiclaService].write(sensorConfigPkt)
                    print("sensor config packet sent for sensor:", sensor);

                sensorConfigured = True

            batchReadSize = int(NICLA_BLE_SENSOR_DATA_PKT_SIZE * 1)
            sensorDataBatch = nicla_connection[NiclaService].read(batchReadSize)
            if (sensorDataBatch is None):
                time.sleep(1)
                continue

            t_now = datetime.datetime.now()
            lenSensorDataBatch = len(sensorDataBatch)
            pktCntInBatch = int(lenSensorDataBatch / NICLA_BLE_SENSOR_DATA_PKT_SIZE)

            if DEBUG:
                print("    bytes read:", lenSensorDataBatch, pktCntInBatch, "#",  "@", t_now, "del=", (t_now - t_prev))

            t_prev = t_now

            if DEBUG:
                for b in sensorDataBatch: print(hex(b))

            for i in range(pktCntInBatch):
                sensorFrame = sensorDataBatch[i * NICLA_BLE_SENSOR_DATA_PKT_SIZE : ((i + 1) * NICLA_BLE_SENSOR_DATA_PKT_SIZE + 1)]

                sensorId = sensorFrame[0]
                if (sensorId in nicla_sensors_desc_tab):
                    if (sensorFrame[1] != nicla_sensors_desc_tab[sensorId]["frame_size"]):
                        print("unmatched frame size, suspicious data, abandon the rest");
                        break
                else:
                    print("unknown or unrequested sensor:", sensorId, "abandon the rest");
                    break;

                name = nicla_sensors_desc_tab[sensorId]["name"]
                scale = nicla_sensors_desc_tab[sensorId]["scale"]
                t_now = datetime.datetime.now()
                if (sensorId == SENSOR_ID_ACC):
                    buf = sensorFrame[0: 2 + 6]
                    (id, sz, x, y, z) = struct.unpack("=BBhhh", buf)
                    (X, Y, Z) = tuple(i * scale for i in (x,y,z))
                    print(name, ",#", sensorDataPktCnt, ",",  X, "," , Y, ",", Z)
                elif (sensorId == SENSOR_ID_TEMP):
                    buf = sensorFrame[0: 2 + 2]
                    (id, sz, temp) = struct.unpack("=BBh", buf)
                    print(name, ",#", sensorDataPktCnt, ",",  temp * scale, ",", t_now)
                elif (sensorId == SENSOR_ID_HUMID):
                    buf = sensorFrame[0: 2 + 1]
                    (id, sz, humid) = struct.unpack("=BBB", buf)
                    print(name, ",#", sensorDataPktCnt, ",",  humid * scale, ",", t_now)
                sensorDataPktCnt += 1

            if DEBUG:
                print("sensor data pkt cnt received so far:", sensorDataPktCnt);


            if (max_sample_rate < 5.0):
                sys.stdout.flush()

        except OSError:
            try:
                nicla_connection.disconnect()
                print("disconnected");
            except:  # pylint: disable=bare-except
                pass

            nicla_connection = None

        time.sleep(0.2)
