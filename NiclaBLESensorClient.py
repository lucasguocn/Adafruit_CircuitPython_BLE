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


class NiclaBLESensorClient:
    def __init__(self, macAddrFilter:str = "", printData:bool = True, dbg:bool = False):
        self.ble = BLERadio()
        self.dbg = dbg
        self.printData = printData
        self.macAddrFilter = macAddrFilter

        self.time_1st_event = datetime.datetime.now()
        self.pkt_cnt_got = 0
        self.max_sample_rate = 0.0

        self.nicla_connection = None
        self.nicla_mac_addr = None
        self.process_composite_sensors = True
        self.sensorDataPktCnt = 0
        self.sensorsConfigured = False

        self.t_prev = datetime.datetime.now()

# set sample_rate 0 to turn off a sensor
        self.sensorStateList = {}
            #latency is milli-seconds, if the rate for a sensor is higher than 25hz, recommends to have a latency larger than 40ms
            #example entry:
            # SENSOR_ID_ACC                   : {"sample_rate":000.0,     "latency":90,    "evtCnt":0, "cb":None},


        signal.signal(signal.SIGINT, self.__handler)
        # See if any existing connections are providing NiclaService.
        if self.ble.connected:
            for connection in self.ble.connections:
                if NiclaService in connection:
                    self.nicla_connection = connection
                break


    def __handler(self, signum, frame):
        #msg = "Ctrl-c was pressed. Do you really want to exit? y/n "
        t_now = datetime.datetime.now()
        print("cnt received: ", self.pkt_cnt_got, end=" ", flush=True)
        print("start time: ", self.time_1st_event, end = " ")
        print("end time: ", t_now)
        res = input("do you want to continue(y/n)")
        if res == 'y':
            print("")
            exit(1)
        else:
            print("", end="\r", flush=True)
            print(" " * len(msg), end="", flush=True) # clear the printed line
            print("    ", end="\r", flush=True)



    def __configSensors(self, sensorsCfg:dict) -> bool:
        connection = self.nicla_connection
        if connection is None or not connection.connected:
            if self.dbg:
                print(f"no active connection yet: {connection}")
            return False

        self.sensorDataPktCnt = 0    #reset

        st = struct.Struct("=BfI")
        sensorConfigPkt = bytearray(NICLA_BLE_SENSOR_CFG_PKT_SIZE)
        for sensor, cfg in sensorsCfg.items():
            self.sensorStateList[sensor] = {}
            self.sensorStateList[sensor]["sample_rate"] = cfg.get("sample_rate", 0)
            self.sensorStateList[sensor]["latency"] = cfg.get("latency", 0)
            self.sensorStateList[sensor]["cb"] = cfg.get("cb", None)
            self.sensorStateList[sensor]["evtCnt"] = 0

            sample_rate = self.sensorStateList[sensor]["sample_rate"]
            latency = int(self.sensorStateList[sensor]["latency"])
            st.pack_into(sensorConfigPkt, 0, sensor, sample_rate, latency)

            if (self.max_sample_rate < sample_rate):
                self.max_sample_rate = sample_rate

            if self.dbg:
                print(f"config sample_rate:{sample_rate} for sensor: {sensor}")
                print("config pkt for sensor:", sensor)
                for b in sensorConfigPkt: print(hex(b))

            connection[NiclaService].write(sensorConfigPkt)
            print("sensor config packet sent for sensor:", sensor)

        connection[NiclaService].reset_input_buffer()
        self.sensorsConfigured = True
        return True


    def __poll_regular_sensors(self):
        t_now = datetime.datetime.now()

        avail = self.nicla_connection[NiclaService].in_waiting
        batchReadSize = (avail // NICLA_BLE_SENSOR_DATA_PKT_SIZE) * NICLA_BLE_SENSOR_DATA_PKT_SIZE

        if (batchReadSize >= NICLA_BLE_SENSOR_DATA_PKT_SIZE):
            if self.dbg:
                print("batch_size:", batchReadSize, " avail: ", avail, " time:", t_now)
            batch = self.nicla_connection[NiclaService].read(batchReadSize, long = False)
        else:
            batch = None

        return batch

    def __poll_composite_sensors(self):
            batchReadSize = int(NICLA_BLE_SENSOR_DATA_LONG_PKT_SIZE * 1)
            batch = self.nicla_connection[NiclaService].read(batchReadSize, long = True)

            return batch



    def __process_sensor_packet(self, sensorFrame, pkt_size):
        sensorId = sensorFrame[0]


        name = nicla_sensors_desc_tab[sensorId]["name"]
        scale = nicla_sensors_desc_tab[sensorId]["scale"]
        t_now = datetime.datetime.now()

        if sensorId in self.sensorStateList:
            cb = self.sensorStateList[sensorId]["cb"]
            if cb is not None:
                cb(t_now, sensorFrame, pkt_size)
        #if (sensorId == SENSOR_ID_ACC) or (sensorId == SENSOR_ID_GYR):
        if (sensorId in [SENSOR_ID_ACC, SENSOR_ID_GYR, SENSOR_ID_ACC_RAW, SENSOR_ID_GYR_RAW]):
            buf = sensorFrame[1: 7+1]
            (sz, x, y, z) = struct.unpack("<Bhhh", buf)
            (X, Y, Z) = tuple(i * scale for i in (x,y,z))
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if (pkt_cnt == 1) and self.printData:
                print("time for 1st event:", t_now)
                self.time_1st_event = t_now
            self.pkt_cnt_got = pkt_cnt
            if self.printData:
                print(name, ",", pkt_cnt, ",",  X, "," , Y, ",", Z, ", dbg:", sensorFrame[NICLA_BLE_SENSOR_DATA_PKT_SIZE-1])
        elif (sensorId == SENSOR_ID_BARO):
            buf = sensorFrame[1: 4+1+1] #baro sensor is 3bytes long, need an extra byte for a padding 0
            buf[4] = 0
            (sz, baro) = struct.unpack("<BI", buf)
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print(name, ",", pkt_cnt, ",",  baro * scale, ",", " dbg:", sensorFrame[NICLA_BLE_SENSOR_DATA_PKT_SIZE-1])
        elif (sensorId == SENSOR_ID_TEMP):
            buf = sensorFrame[1: 3+1]   #ds says 3 as frame size
            (sz, temp) = struct.unpack("<Bh", buf)
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print(name, ",", pkt_cnt, ",",  temp * scale, ",", t_now)
        elif (sensorId == SENSOR_ID_NICLA_SYSTEM):
            buf = sensorFrame[1: 11+1]   #ds says 3 as frame size
            (sz, temp, dummy,fault_h, fault_l, bat_stat, pmic_h, pmic_l, f_55, faa) = struct.unpack("<BhBBBBBBBB", buf)
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print("fault_h:", fault_h, "fault_l:", fault_l, "bat_stat:", bat_stat, "pmic_h:", pmic_h, "pmic_l:", pmic_l, f_55, faa)
        elif (sensorId == SENSOR_ID_HUMID):
            buf = sensorFrame[1: 2+1]
            (sz, humid) = struct.unpack("<BB", buf)
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print(name, ",", pkt_cnt, ",",  humid * scale, ",", t_now)
        elif (sensorId == SENSOR_ID_BSEC):
            buf = sensorFrame[1: 19+1]
            (sz, iaq,iaq_s,bvoc_eq,eco2_and_status,comp_t,comp_h,comp_g) = struct.unpack("<BHHHIhHf", buf)
            bvoc_eq = bvoc_eq * 0.01
            comp_t = comp_t / 256
            comp_h = comp_h / 500
            eco2 = eco2_and_status & 0xffffff
            status = eco2_and_status >> 24
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print(name, ",", pkt_cnt, ",",  iaq, ",", iaq_s, ",", bvoc_eq * 0.01, ",", eco2, ",", status, ",", t_now)
                print("\t"+name + " temperature", ",#", pkt_cnt, ",", comp_t, ",", t_now)
                print("\t"+name + " humidity", ",#", pkt_cnt, ",", comp_h, ",", t_now)
        elif (sensorId == SENSOR_ID_BSEC_DEPRECATED):
            buf = sensorFrame[1: 10+1]
            (sz, temp_comp, humid_comp) = struct.unpack("<Bff", buf)
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print(name, ",", pkt_cnt, ",",  temp_comp, ",", humid_comp, t_now, ",", sz)
        elif (sensorId == SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR):
            buf = sensorFrame[1: 22+1]
            (sz, ts_dev, raw_temp, raw_pressure, raw_humid, raw_gas, gas_index) = struct.unpack("<BQhfHfB", buf)
            raw_temp *= 1.0 / 256
            raw_humid *= 0.002
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print(name, ",", pkt_cnt, ",",  ts_dev, ",",
                      format(raw_temp, '.2f'), ",", format(raw_pressure, '.6f'), ",",
                      format(raw_humid, '.2f'), ",", format(raw_gas, '.6f'),
                      ",", gas_index, ",", t_now, ",", sz)
        elif (sensorId == SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER):
            buf = sensorFrame[1: 6+1]
            (sz, likelihood_0, likelihood_1, likelihood_2, likelihood_3, accuracy) = struct.unpack("<BBBBBB", buf)
            pkt_cnt = self.sensorStateList[sensorId]["evtCnt"] = (self.sensorStateList[sensorId]["evtCnt"] + 1)
            if self.printData:
                print(name, ",", pkt_cnt, ",",
                      str(likelihood_0)+"%", ",", str(likelihood_1)+'%', ",",
                      str(likelihood_2)+'%', ",", str(likelihood_3)+'%', ",", accuracy, ",", t_now, ",", sz)
        else:
            if self.printData:
                print("undefined parsing scheme for sensor:", sensorId)
        return


    def __process_sensor_data_batch(self, batch, pkt_size):

        t_now = datetime.datetime.now()
        lenSensorDataBatch = len(batch)
        pktCntInBatch = int(lenSensorDataBatch / pkt_size)

        if self.dbg:
            print("    bytes read:", lenSensorDataBatch, pktCntInBatch, "#",  "@", t_now, "del=", (t_now - self.t_prev))

        self.t_prev = t_now

        if self.dbg:
            for b in batch: print(hex(b))

        for i in range(pktCntInBatch):
            sensorFrame = batch[i * pkt_size : ((i + 1) * pkt_size + 1)]

            sensorId = sensorFrame[0]
            if (sensorId in nicla_sensors_desc_tab):
                if (sensorFrame[1] != nicla_sensors_desc_tab[sensorId]["frame_size"]):
                    if self.printData:
                        print("unmatched frame size", sensorFrame[1], " vs ",
                                nicla_sensors_desc_tab[sensorId]["frame_size"],  "suspicious data, abandon the rest")
                    break
            else:
                if self.printData:
                    print("unknown or unrequested sensor:", sensorId, "skip packet")
                continue

            self.__process_sensor_packet(sensorFrame, pkt_size)
            self.sensorDataPktCnt += 1

        if self.dbg:
            print("sensor data pkt cnt received so far:", self.sensorDataPktCnt)

    def try_connect(self, timeout = 5) -> bool:
        if not self.nicla_connection:
            print("Scanning...")
            for adv in self.ble.start_scan(ProvideServicesAdvertisement, timeout=5):
                if NiclaService in adv.services:
                    print(f"found a Nicla Sense ME device: <{adv.address}>")
                    if self.macAddrFilter is not None:
                        if self.macAddrFilter.lower() not in adv.address.string.lower():
                            if self.dbg:
                                print(f"mac address does not match filter:'{self.macAddrFilter}'")
                            continue

                    self.nicla_connection = self.ble.connect(adv)
                    self.nicla_mac_addr = adv.address.string
                    break
            # Stop scanning whether or not we are connected.
            self.ble.stop_scan()
        else:
            print("Nicla connection exists, connected:", self.nicla_connection.connected)


        if self.nicla_connection and self.nicla_connection.connected:
            return True
        else:
            return False


    def try_connect_until_success(self, timeout_sec = -1) -> bool:
        time_start = time.time()
        while True:
            success = self.try_connect(self)
            if (success):
                return True
            else:
                if (timeout_sec > 0):
                    time_now = time.time()
                    if (time_now - time_start) >= timeout_sec:
                        return False

    def configSensors(self, sensorsCfg)->bool:
        success = False
        try:
            success = self.__configSensors(sensorsCfg)
        except OSError:
            try:
                self.nicla_connection.disconnect()
                print("disconnected")
            except:  # pylint: disable=bare-except
                pass

            self.nicla_connection = None
            success = False
        return success



    def loopPolling(self, sleep_time_no_data:float=0.0):
        while True:
            if self.nicla_connection and self.nicla_connection.connected:
                try:
                    sensorDataBatch = self.__poll_regular_sensors()
                    if (sensorDataBatch is not None):
                        self.__process_sensor_data_batch(sensorDataBatch, NICLA_BLE_SENSOR_DATA_PKT_SIZE)

                    if self.process_composite_sensors:
                        longSensorDataBatch = self.__poll_composite_sensors()
                        if (longSensorDataBatch is not None):
                            self.__process_sensor_data_batch(longSensorDataBatch, NICLA_BLE_SENSOR_DATA_LONG_PKT_SIZE)
                    else:
                        longSensorDataBatch = None

                    if (sensorDataBatch is None) and (longSensorDataBatch is None):
                        if self.dbg:
                            print("read none")
                        if (sleep_time_no_data > 0):
                            time.sleep(sleep_time_no_data)
                        continue

                    if self.dbg:
                        print("self.max_sample_rate:", self.max_sample_rate)
                    if (self.max_sample_rate < 5.0):
                        sys.stdout.flush()

                except OSError:
                    try:
                        self.nicla_connection.disconnect()
                        print("disconnected")
                    except:  # pylint: disable=bare-except
                        pass

                    self.nicla_connection = None


if __name__ == "__main__":
    nicla_client = NiclaBLESensorClient()
    success = nicla_client.try_connect_until_success(timeout_sec = 60)
    if success:
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
        success = nicla_client.configSensors(sensorsCfg)
        if success:
            nicla_client.loopPolling()
        else:
            print("failed with sensor configSensors")
    else:
            print("failed with sensor connection")


