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

import signal
import time
import readchar


time_1st_event = datetime.datetime.now()
pkt_cnt_got = 0

def handler(signum, frame):
    #msg = "Ctrl-c was pressed. Do you really want to exit? y/n "
    t_now = datetime.datetime.now()
    print("cnt received: ", pkt_cnt_got, end=" ", flush=True)
    print("start time: ", time_1st_event, end = " ")
    print("end time: ", t_now)
    res = input("do you want to continue(y/n)")
    if res == 'y':
        print("")
        exit(1)
    else:
        print("", end="\r", flush=True)
        print(" " * len(msg), end="", flush=True) # clear the printed line
        print("    ", end="\r", flush=True)


signal.signal(signal.SIGINT, handler)


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
        #latency is milli-seconds, if the rate for a sensor is higher than 25hz, recommends to have a latency larger than 40ms
        SENSOR_ID_ACC                   : {"sample_rate":000.0,     "latency":90,    "evtCnt":0},
        SENSOR_ID_GYR                   : {"sample_rate":000.0,     "latency":90,    "evtCnt":0},
        SENSOR_ID_ACC_RAW               : {"sample_rate":000.0,     "latency":90,    "evtCnt":0},
        SENSOR_ID_GYR_RAW               : {"sample_rate":000.0,     "latency":90,    "evtCnt":0},
        SENSOR_ID_BARO                  : {"sample_rate":0.0,       "latency":0,    "evtCnt":0},
        SENSOR_ID_TEMP                  : {"sample_rate":0.0,       "latency":0,    "evtCnt":0},
        SENSOR_ID_HUMID                 : {"sample_rate":0.0,       "latency":0,    "evtCnt":0},
        SENSOR_ID_BSEC                  : {"sample_rate":0.0,       "latency":0,    "evtCnt":0},
        SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR : {"sample_rate":1.0,       "latency":0,    "evtCnt":0},
        SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER     : {"sample_rate":0.0,       "latency":0,    "evtCnt":0},
        }

max_sample_rate = 0.0

DEBUG = False
#DEBUG = True

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
        latency = int(sensorList[sensor]["latency"])
        st.pack_into(sensorConfigPkt, 0, sensor, sample_rate, latency)

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

    if (batchReadSize >= NICLA_BLE_SENSOR_DATA_PKT_SIZE):
        if DEBUG:
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
    global pkt_cnt_got
    global time_1st_event
    sensorId = sensorFrame[0]
    name = nicla_sensors_desc_tab[sensorId]["name"]
    scale = nicla_sensors_desc_tab[sensorId]["scale"]
    t_now = datetime.datetime.now()
    #if (sensorId == SENSOR_ID_ACC) or (sensorId == SENSOR_ID_GYR):
    if (sensorId in [SENSOR_ID_ACC, SENSOR_ID_GYR, SENSOR_ID_ACC_RAW, SENSOR_ID_GYR_RAW]):
        buf = sensorFrame[1: 7+1]
        (sz, x, y, z) = struct.unpack("<Bhhh", buf)
        (X, Y, Z) = tuple(i * scale for i in (x,y,z))
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        if (pkt_cnt == 1):
            print("time for 1st event:", t_now)
            time_1st_event = t_now
        pkt_cnt_got = pkt_cnt
        print(name, ",", pkt_cnt, ",",  X, "," , Y, ",", Z, ", dbg:", sensorFrame[NICLA_BLE_SENSOR_DATA_PKT_SIZE-1])
    elif (sensorId == SENSOR_ID_BARO):
        buf = sensorFrame[1: 4+1+1] #baro sensor is 3bytes long, need an extra byte for a padding 0
        buf[4] = 0
        (sz, baro) = struct.unpack("<BI", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",", pkt_cnt, ",",  baro * scale, ",", " dbg:", sensorFrame[NICLA_BLE_SENSOR_DATA_PKT_SIZE-1])
    elif (sensorId == SENSOR_ID_TEMP):
        buf = sensorFrame[1: 3+1]   #ds says 3 as frame size
        (sz, temp) = struct.unpack("<Bh", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",", pkt_cnt, ",",  temp * scale, ",", t_now)
    elif (sensorId == SENSOR_ID_HUMID):
        buf = sensorFrame[1: 2+1]
        (sz, humid) = struct.unpack("<BB", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",", pkt_cnt, ",",  humid * scale, ",", t_now)
    elif (sensorId == SENSOR_ID_BSEC):
        buf = sensorFrame[1: 19+1]
        (sz, iaq,iaq_s,bvoc_eq,eco2_and_status,comp_t,comp_h,comp_g) = struct.unpack("<BHHHIhHf", buf)
        bvoc_eq = bvoc_eq * 0.01
        comp_t = comp_t / 256
        comp_h = comp_h / 500
        eco2 = eco2_and_status & 0xffffff
        status = eco2_and_status >> 24
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",", pkt_cnt, ",",  iaq, ",", iaq_s, ",", bvoc_eq * 0.01, ",", eco2, ",", status, ",", t_now)
        print("\t"+name + " temperature", ",#", pkt_cnt, ",", comp_t, ",", t_now)
        print("\t"+name + " humidity", ",#", pkt_cnt, ",", comp_h, ",", t_now)
    elif (sensorId == SENSOR_ID_BSEC_DEPRECATED):
        buf = sensorFrame[1: 10+1]
        (sz, temp_comp, humid_comp) = struct.unpack("<Bff", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",", pkt_cnt, ",",  temp_comp, ",", humid_comp, t_now, ",", sz)
    elif (sensorId == SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR):
        buf = sensorFrame[1: 22+1]
        (sz, ts_dev, raw_temp, raw_pressure, raw_humid, raw_gas, gas_index) = struct.unpack("<BQhfHfB", buf)
        raw_temp *= 1.0 / 256
        raw_humid *= 0.01
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",", pkt_cnt, ",",  ts_dev, ",", raw_temp, ",", raw_pressure, ",", raw_humid, ",", raw_gas, ",", gas_index, ",", t_now, ",", sz)
    elif (sensorId == SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER):
        buf = sensorFrame[1: 6+1]
        (sz, likelihood_0, likelihood_1, likelihood_2, likelihood_3, accuracy) = struct.unpack("<BBBBBB", buf)
        pkt_cnt = sensorList[sensorId]["evtCnt"] = (sensorList[sensorId]["evtCnt"] + 1)
        print(name, ",", pkt_cnt, ",",
                str(likelihood_0)+"%", ",", str(likelihood_1)+'%', ",",
                str(likelihood_2)+'%', ",", str(likelihood_3)+'%', ",", accuracy, ",", t_now, ",", sz)
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
                print("unmatched frame size", sensorFrame[1], " vs ",
                        nicla_sensors_desc_tab[sensorId]["frame_size"],  "suspicious data, abandon the rest")
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



