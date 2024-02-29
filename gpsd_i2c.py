#!/usr/bin/env python3
"""
A simple way to read raw NMEA 0183 data from a GPS module that has I²C output capability.
"""

import os
import signal
import sys
import smbus2

def parse_int(val, default):
    "Parse integer from string, first as decimal then as hex"
    try:
        result = int(val)
    except (TypeError, ValueError):
        try:
            result = int(val,16)
        except (TypeError, ValueError):
            result = default
    return result

# Default to device 0-0042; can be overriden via environment
I2C_BUS = parse_int(os.environ.get("I2C_BUS", None), 0)
I2C_ADDRESS = parse_int(os.environ.get("I2C_ADDRESS", None), 0x42)

def handle_ctrl_c(sig, frame):
    "Exit handler"
    # pylint: disable=unused-argument
    sys.exit(130)

# This will capture exit when using [Ctrl]+[C] for a graceful exit
signal.signal(signal.SIGINT, handle_ctrl_c)

def parse_response(gps_line):
    "Parse GPS line"
    # Check #1 -- make sure line starts with $ and $ doesn't appear twice
    if gps_line[0] != 36 or gps_line.count(36) != 1:
        return

    # Check #2 -- 83 is maximum NMEA sentence length
    if len(gps_line) > 83:
        return

    # Check #3 -- make sure that only readable ASCII characters
    # and carriage return are seen
    for char in gps_line:
        if (char < 32 or char > 122) and char != 13:
            return

    gps_chars = ''.join(chr(char) for char in gps_line)

    # Check #4 -- skip txbuff allocation error
    if 'txtbuf' in gps_chars:
        return

    # Check #5 -- only split twice to avoid unpack error
    gps_str, chk_sum = gps_chars.split('*', 2)

    # Remove the $ and do a manual checksum on the rest of the NMEA sentence
    chk_val = 0
    for char in gps_str[1:]:
        chk_val ^= ord(char)

    # Compare the calculated checksum with the one in the NMEA sentence
    if chk_val != int(chk_sum, 16):
        return

    # All checks passed
    print(gps_chars)

def read_gps(bus):
    "read bytes from I2C device"
    response = []
    try:
        while True:
            byte = bus.read_byte(I2C_ADDRESS)
            if byte == 255:
                return
            if byte == ord('\n'):
                break
            response.append(byte)
        parse_response(response)
    except IOError:
        bus = smbus2.SMBus(I2C_BUS)

BUS = smbus2.SMBus(I2C_BUS)
while True:
    read_gps(BUS)
