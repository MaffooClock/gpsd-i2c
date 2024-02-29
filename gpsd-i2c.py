#!/usr/bin/env python3

import os
def parse_int(val, default):
    try:
        result = int(val)
    except (TypeError, ValueError):
        try:
            result = int(val,16)
        except (TypeError, ValueError):
            result = default
    except Exception:
        result = default
    return result

# Default to device 0-0042; can be overriden via environment
I2C_BUS = parse_int(os.environ.get("I2C_BUS", None), 0)
I2C_ADDRESS = parse_int(os.environ.get("I2C_ADDRESS", None), 0x42)

##### Don't edit anything below this line #####

import time
import smbus2
import signal
import sys

BUS = None


def handle_ctrl_c( signal, frame ):
    sys.exit( 130 )

# This will capture exit when using [Ctrl]+[C] for a graceful exit
signal.signal( signal.SIGINT, handle_ctrl_c )

def connectBus():
    global BUS
    BUS = smbus2.SMBus( I2C_BUS )

def parseResponse( gpsLine ):
  if( gpsLine.count( 36 ) == 1 ):                         # Check #1 -- make sure '$' doesn't appear twice
    if len( gpsLine ) < 84:                               # Check #2 -- 83 is maximun NMEA sentenace length
        CharError = 0;

        for c in gpsLine:                                 # Check #3 -- make sure that only readable ASCII characters and Carriage Return are seen
            if ( c < 32 or c > 122 ) and  c != 13:
                CharError += 1

        if ( CharError == 0 ):                            # Only proceed if there are no errors
            gpsChars = ''.join( chr( c ) for c in gpsLine )

            if ( gpsChars.find( 'txbuf' ) == -1 ):        # Check #4 -- skip txbuff allocation error
                gpsStr, chkSum = gpsChars.split( '*', 2 ) # Check #5 -- only split twice to avoid unpack error
                gpsComponents = gpsStr.split( ',' )
                chkVal = 0

                for ch in gpsStr[1:]:                     # Remove the $ and do a manual checksum on the rest of the NMEA sentence
                     chkVal ^= ord( ch )

                if ( chkVal == int( chkSum, 16 ) ):       # Compare the calculated checksum with the one in the NMEA sentence
                     print( gpsChars )

def readGPS():
    c = None
    response = []

    try:
        while True:
            c = BUS.read_byte( I2C_ADDRESS )
            if c == 255:
                return False

            elif c == 10:
                break

            else:
                response.append( c )

        parseResponse( response )

    except IOError:
        connectBus()

    except Exception as e:
        print( e )

connectBus()

while True:
    readGPS()
