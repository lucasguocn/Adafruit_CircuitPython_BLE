# SPDX-FileCopyrightText: 2019 Dan Halbert for Adafruit Industries
# SPDX-FileCopyrightText: 2019 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
====================================================


"""

from . import Service
from ..uuid import VendorUUID
from ..characteristics.stream import StreamOut, StreamIn

# from typing import Final

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_BLE.git"


# <constants>
NICLA_BLE_SENSOR_CFG_PKT_SIZE = 9
NICLA_BLE_SENSOR_DATA_PKT_SIZE = 12         #sizeof(SensorDataPacket.data) + 2
NICLA_BLE_SENSOR_DATA_LONG_PKT_SIZE = 23    #sizeof(SensorLongDataPacket.data) + 2
NICLA_BLE_SENSOR_BUFFER_PKT_CNT = 200
NICLA_BLE_SENSOR_BUFFER_LONG_PKT_CNT = 10

SCALE_DEFAULT_ACCEL = (16.0/65536)
SCALE_DEFAULT_GYRO = (4000.0/65536)

SENSOR_ID_ACC_RAW = 1
SENSOR_ID_GYR_RAW = 10
SENSOR_ID_ACC = 4
SENSOR_ID_GYR = 13
SENSOR_ID_BARO = 129
SENSOR_ID_TEMP = 128
SENSOR_ID_HUMID = 130
SENSOR_ID_BSEC = 115
SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR = 116
SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER = 117
SENSOR_ID_BSEC_DEPRECATED = 171


SENSOR_ID_NICLA_SYSTEM = 201

nicla_sensors_desc_tab = {
        #frame_size complies with BHI260AP datasheet
        SENSOR_ID_ACC_RAW         : {"name":"accelerometer raw",           "frame_size":7,          "scale":SCALE_DEFAULT_ACCEL},
        SENSOR_ID_GYR_RAW         : {"name":"gyroscope raw",               "frame_size":7,          "scale":SCALE_DEFAULT_GYRO},
        SENSOR_ID_ACC             : {"name":"accelerometer corrected",     "frame_size":7,          "scale":SCALE_DEFAULT_ACCEL},
        SENSOR_ID_GYR             : {"name":"gyroscope corrected",         "frame_size":7,          "scale":SCALE_DEFAULT_GYRO},
        SENSOR_ID_BARO            : {"name":"barometric pressure",         "frame_size":4,          "scale":1},
        SENSOR_ID_TEMP            : {"name":"temperature",                 "frame_size":3,          "scale": 0.01}, 
        SENSOR_ID_HUMID           : {"name":"relative humidity",           "frame_size":2,          "scale":1},
        SENSOR_ID_BSEC            : {"name":"BSEC",                        "frame_size":19,         "scale":1},
        SENSOR_ID_BSEC_DEPRECATED : {"name":"BSEC (deprecated)",           "frame_size":10,         "scale":1},
        SENSOR_ID_BSEC2_GAS_SCANNING_DATA_COLLECTOR            : {"name":"BSEC2 gas scanning raw data", "frame_size":22, "scale":1},
        SENSOR_ID_BSEC2_GAS_SCANNING_CLASSIFIER : {"name":"BSEC2 gas scanning result",   "frame_size":6,  "scale":1},
        SENSOR_ID_NICLA_SYSTEM    : {"name":"nicla system",                 "frame_size":11,          "scale": 1},
        }

# </sonstants>

class NiclaService(Service):
    """
    :param int timeout:  the timeout in seconds to wait
      for the first character and between subsequent characters.
    :param int buffer_size: buffer up to this many bytes.
      If more bytes are received, older bytes will be discarded.

    See ``examples/ble_uart_echo_test.py`` for a usage example.
    """

    # pylint: disable=no-member
    uuid = VendorUUID("34C2E3BB-34AA-11EB-ADC1-0242AC120002")
    _server_tx = StreamOut(
        uuid=VendorUUID("34C2E3BC-34AA-11EB-ADC1-0242AC120002"),
        timeout=1.0,
        buffer_size= NICLA_BLE_SENSOR_DATA_PKT_SIZE * NICLA_BLE_SENSOR_BUFFER_PKT_CNT,
    )

    _server_tx_long = StreamOut(
        uuid=VendorUUID("34C2E3BE-34AA-11EB-ADC1-0242AC120002"),
        timeout=0.01,   #too small value could corrupt data
        buffer_size= NICLA_BLE_SENSOR_DATA_LONG_PKT_SIZE * NICLA_BLE_SENSOR_BUFFER_LONG_PKT_CNT,
    )

    _server_rx = StreamIn(
        uuid=VendorUUID("34C2E3BD-34AA-11EB-ADC1-0242AC120002"),
        timeout=1.0,
        buffer_size=64,
    )

    def __init__(self, service=None):
        super().__init__(service=service)
        self.connectable = True
        if not service:
            self._rx = self._server_rx
            self._tx = self._server_tx
            self._tx_long = None
        else:
            # If we're a client then swap the characteristics we use.
            self._rx = self._server_tx
            self._rx_long = self._server_tx_long
            self._tx = self._server_rx


    def read(self, nbytes=None, long = False):
        """
        Read characters. If ``nbytes`` is specified then read at most that many bytes.
        Otherwise, read everything that arrives until the connection times out.
        Providing the number of bytes expected is highly recommended because it will be faster.

        :return: Data read
        :rtype: bytes or None
        """
        if long:
            return self._rx_long.read(nbytes)
        else:
            return self._rx.read(nbytes)

    def readinto(self, buf, nbytes=None, long = False):
        """
        Read bytes into the ``buf``. If ``nbytes`` is specified then read at most
        that many bytes. Otherwise, read at most ``len(buf)`` bytes.

        :return: number of bytes read and stored into ``buf``
        :rtype: int or None (on a non-blocking error)
        """
        if long:
            return self._rx.readinto(buf, nbytes)
        else:
            return self._rx_long.readinto(buf, nbytes)


    @property
    def in_waiting(self):
        """The number of bytes in the input buffer, available to be read."""
        return self._rx.in_waiting

    def reset_input_buffer(self):
        """Discard any unread characters in the input buffer."""
        self._rx.reset_input_buffer()

    def write(self, buf):
        """Write a buffer of bytes."""
        self._tx.write(buf)

