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
sensorList = {
        SENSOR_ID_ACC                   : {"sample_rate":200.0, "evtCnt":0},
        SENSOR_ID_GYR                   : {"sample_rate":200.0, "evtCnt":0},
        SENSOR_ID_BARO                  : {"sample_rate":0.0,   "evtCnt":0},
        SENSOR_ID_TEMP                  : {"sample_rate":0.0,   "evtCnt":0},
        SENSOR_ID_HUMID                 : {"sample_rate":0.0,   "evtCnt":0},
        SENSOR_ID_BSEC                  : {"sample_rate":0.0,   "evtCnt":0},
        SENSOR_ID_BSEC_DEPRECATED       : {"sample_rate":0.0,   "evtCnt":0},
        }

max_sample_rate = 0.0

#DEBUG = True
DEBUG = False

process_composite_sensors = True
#process_composite_sensors = False

sensorDataPktCnt = 0
sensorConfigured = False
def configSensors(connection):
    global sensorConfigured
    global max_sample_rate
    global sensorDataPktCnt

    sensorDataPktCnt = 0    #reset

    st = struct.Struct("=BfI")
    sensorConfigPkt = bytearray(NICLA_BLE_SENSOR_CFG_PKT_SIZE)
    for sensor in sensorList:
        sample_rate = sensorList[sensor]["sample_rate"]
        st.pack_into(sensorConfigPkt, 0, sensor, sample_rate, 0)

        if (max_sample_rate < sample_rate):
            max_sample_rate = sample_rate

        if DEBUG:
            print("config pkt for sensor:", sensor)
            for b in sensorConfigPkt: print(hex(b))

        connection[NiclaService].write(sensorConfigPkt)
        print("sensor config packet sent for sensor:", sensor)

    connection[NiclaService].reset_input_buffer()
    sensorConfigured = True


def poll_regular_sensors(connection):
    t_now = datetime.datetime.now()

    avail = nicla_connection[NiclaService].in_waiting
    batchReadSize = (avail // NICLA_BLE_SENSOR_DATA_PKT_SIZE) * NICLA_BLE_SENSOR_DATA_PKT_SIZE

    if (batchReadSize >= NICLA_BLE_SENSOR_DATA_LONG_PKT_SIZE):
        print("batch_size:", batchReadSize, " avail: ", avail, " time:", t_now)
        batch = nicla_connection[NiclaService].read(batchReadSize, long = False)
    else:
        batch = None

    return batch

def poll_composite_sensors(connection):
        batchReadSize = int(NICLA_BLE_SENSOR_DATA_LONG_PKT_SIZE * 1)
        batch = nicla_connection[NiclaService].read(batchReadSize, long = True)

        return batch



def process_sensor_packet(sensorFrame, pkt_size, pkt_cnt):
    sensorId = sensorFrame[0]
    name = nicla_sensors_desc_tab[sensorId]["name"]
    scale = nicla_sensors_desc_tab[sensorId]["scale"]
    t_now = datetime.datetime.now()
    if (sensorId == SENSOR_ID_ACC) or (sensorId == SENSOR_ID_GYR):
        buf = sensorFrame[1: 2 + 6]
        (sz, x, y, z) = struct.unpack("<Bhhh", buf)
        (X, Y, Z) = tuple(i * scale for i in (x,y,z))
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",#", pkt_cnt, ",",  X, "," , Y, ",", Z, " dbg:", sensorFrame[11])
    elif (sensorId == SENSOR_ID_BARO):
        buf = sensorFrame[1: 2 + 3 + 1]
        buf[4] = 0
        (sz, baro) = struct.unpack("<BI", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",#", pkt_cnt, ",",  baro * scale, ",", t_now)
    elif (sensorId == SENSOR_ID_TEMP):
        buf = sensorFrame[1: 2 + 2]
        (sz, temp) = struct.unpack("<Bh", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",#", pkt_cnt, ",",  temp * scale, ",", t_now)
    elif (sensorId == SENSOR_ID_HUMID):
        buf = sensorFrame[1: 2 + 1]
        (sz, humid) = struct.unpack("<BB", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",#", pkt_cnt, ",",  humid * scale, ",", t_now)
    elif (sensorId == SENSOR_ID_BSEC):
        buf = sensorFrame[1: 2 + 18]
        (sz, iaq,iaq_s,bvoc_eq,eco2_and_status,comp_t,comp_h,comp_g) = struct.unpack("<BHHHIhHf", buf)
        bvoc_eq = bvoc_eq * 0.01
        comp_t = comp_t / 256
        comp_h = comp_h / 500
        eco2 = eco2_and_status & 0xffffff
        status = eco2_and_status >> 24
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",#", pkt_cnt, ",",  iaq, ",", iaq_s, ",", bvoc_eq * 0.01, ",", eco2, ",", status, ",", t_now)
        print(name + " temperature", ",#", pkt_cnt, ",", comp_t, ",", t_now)
        print(name + " humidity", ",#", pkt_cnt, ",", comp_h, ",", t_now)
    elif (sensorId == SENSOR_ID_BSEC_DEPRECATED):
        buf = sensorFrame[1: 2 + 8]
        (sz, temp_comp, humid_comp) = struct.unpack("<Bff", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",#", pkt_cnt, ",",  temp_comp, ",", humid_comp, t_now, ",", sz)
    else:
        print("undefined parsing scheme for sensor:", sensorId)
    return

t_prev = datetime.datetime.now()

def process_sensor_data_batch(batch, pkt_size):
    global t_prev
    global sensorDataPktCnt

    t_now = datetime.datetime.now()
    lenSensorDataBatch = len(batch)
    pktCntInBatch = int(lenSensorDataBatch / pkt_size)

    if DEBUG:
        print("    bytes read:", lenSensorDataBatch, pktCntInBatch, "#",  "@", t_now, "del=", (t_now - t_prev))

    t_prev = t_now

    if DEBUG:
        for b in batch: print(hex(b))

    for i in range(pktCntInBatch):
        sensorFrame = batch[i * pkt_size : ((i + 1) * pkt_size + 1)]

        sensorId = sensorFrame[0]
        if (sensorId in nicla_sensors_desc_tab):
            if (sensorFrame[1] != nicla_sensors_desc_tab[sensorId]["frame_size"]):
                print("unmatched frame size, suspicious data, abandon the rest")
                break
        else:
            print("unknown or unrequested sensor:", sensorId, "skip packet")
            continue

        process_sensor_packet(sensorFrame, pkt_size, sensorDataPktCnt)
        sensorDataPktCnt += 1

    if DEBUG:
        print("sensor data pkt cnt received so far:", sensorDataPktCnt)




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

    while nicla_connection and nicla_connection.connected:
        try:
            if not sensorConfigured:
                configSensors(nicla_connection)

            sensorDataBatch = poll_regular_sensors(nicla_connection)
            if (sensorDataBatch is not None):
                process_sensor_data_batch(sensorDataBatch, NICLA_BLE_SENSOR_DATA_PKT_SIZE)

            if process_composite_sensors:
                longSensorDataBatch = poll_composite_sensors(nicla_connection)
                if (longSensorDataBatch is not None):
                    process_sensor_data_batch(longSensorDataBatch, NICLA_BLE_SENSOR_DATA_LONG_PKT_SIZE)
            else:
                longSensorDataBatch = None

            if (sensorDataBatch is None) and (longSensorDataBatch is None):
                if DEBUG:
                    print("read none")
                #time.sleep(1)
                continue


            if DEBUG:
                print("max_sample_rate:", max_sample_rate)
            if (max_sample_rate < 5.0):
                sys.stdout.flush()

        except OSError:
            try:
                nicla_connection.disconnect()
                print("disconnected")
            except:  # pylint: disable=bare-except
                pass

            nicla_connection = None



