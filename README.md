# gpsd-i2c

A simple way to read raw NMEA 0183 data from a GPS module that has I²C output capability and make it available in a virtual serial port for [GPSD](https://gpsd.gitlab.io/gpsd/) to read.


### Why?

> Why make GPSD read from a virtual serial port being fed by another process when I can just have GPSD read from the module's _real_ serial port?  How is this added complexity useful?

Fair question.  To put it bluntly: if you're not sure how this would be useful, then you probably won't need it.  

This something I slapped together as a test while working through a particular problem, and not only did it work, but it actually works a lot better than expected.  Like... it works _surprisingly well_.  I figured this might be useful to more people than just me, so I decided to share it.


### Purpose

This utility enables you to use other tools to read or configure your GPS module in read-write mode, directly on the device's serial port, while simultaneously allowing GPSD to run in read-only mode.  This makes it easier to configure or troubleshoot without having to constantly stop and restart GPSD.

For example, this would be perfect for enabling the use of [u-center](https://www.u-blox.com/en/product/u-center) for u-blox modules -- just need a simple TCP-to-serial redirect, and you can remotely monitor or configure your u-blox module while GPSD is running.


### How this works

This utility uses a Python script to continuously read a data stream from a particular I²C device, parse the data to ensure it's a NMEA 0183 sentence (including verifying the checksum), then dump it to `stdout`.

Socat is actually responsible for running the Python script, and it captures the `stdout` and redirects it to a virtual serial port device that it creates.  Any tool or program (such as GPSD) that can read from a serial device can then read from this virtual serial device.

However, the communication is one-way -- this utility does not facilitate sending data from the virtual serial device back to the I²C device, making the GPS device essentially read-only.

This utility includes a systemd service file to automatically run at boot-up, which is designed to make the existing gpsd.service depend on it; the GPSD service is supposed to start after this one, which is necessary because the virtual serial port that GPSD will be expecting to read from won't exist until this service starts.


## Setup

### Requirements

You'll need these to make this utility work:

1. Python 3
2. [smbus2](https://pypi.org/project/smbus2/) Python module
3. [socat](http://www.dest-unreach.org/socat/)

If you're using any current version of Debian or Ubuntu, or any distribution based on either of those, this will be easy:
```bash
sudo apt install python3 python3-smbus2 socat
```

Also, your GPS module needs to be configured to output NMEA on its I²C interface (or DDC on u-blox, maybe others).  I would assume that if your GPS module has an I²C port, that it would be outputting data to it by default, but you might consult the documentation for your module to be certain.

> [!IMPORTANT] 
> The Python script in this utility only looks for and handles valid NMEA 0183 sentences -- anything else, such as UBX or RTMC or other protocols will be silently ignored.


### Prepare

Before you can use this utility, we need to check on a few things.  The steps below use commands provided by `i2c-tools` (which can be installed in Debian/Ubuntu with `apt install i2c-tools`).


#### 1. What's the address of your GPS module?

This should be listed in the documentation for your module.  If your module is connected to the I²C bus, you can use `i2cdetect -y 0` to scan for all devices to confirm:

```text
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --
40: -- -- 42 -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- UU -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```
In this example, address `42` is my u-blox GPS module; `52` is a real-time clock; and `3c` is an OLED display.  

If you get nothing, your host might have more than one I²C bus.  You can see all of them with `i2cdetect -l`, and re-running `i2cdetect -y X` where `X` is the numeric bus ID should find it.  If not, you've got other problems that are beyond the scope of this guide.


#### 2. Determine maximum I²C speed

For this utility to be optimal, you'll want your I²C bus speed to be as fast as your GPS module is capable of running (maybe, see below).  For instance, my u-blox MAX-M8Q supports "Fast" mode, which is 400 Kbps -- much faster than the most common UART speeds.  Consult your GPS module's documentation to find out what I²C speeds are supported.

If your GPS module supports "Fast-plus" (1 Mbps) or "High-speed" (3.4 Mbps) modes, then you might try those if your bus supports them.  However, higher speeds aren't always guaranteed to work -- many factors, such as wire length, circuitry design quality, and electrical interference from external sources can effect reliability at higher speeds.  Try the fastest mode available, and drop down if you have problems.

If your GPS module or I²C bus doesn't support faster than "Standard" mode (100 Kbps), it'll still be faster than the common 9600 baud, and comparably fast with 115200 baud.


#### 3. Set I²C speed

Once you've determined the maximum speed for your I²C bus, you'll need to configure your host to use it.  The python script in this utility cannot do that for you.

For Raspberry Pi, it's as simple as adding a line to the `/boot/config.txt` file, as shown in [this gist](https://gist.github.com/ribasco/c22ab6b791e681800df47dd0a46c7c3a).

For other Linux distributions, it might not be this simple -- for instance, in Armbian I had to [write my own device tree overlay](https://gist.github.com/MaffooClock/1ce31eb33500bdfc646bb30a43ce943b) to set the clock frequency of my I²C bus.


### Install

1. Clone this repository:
   ```bash
   cd /opt
   git clone https://github.com/MaffooClock/gpsd-i2c.git
   ```
   
2. Test the service (use the I²C bus and address of your GPS module):
   ```bash
   I2C_BUS=0 I2C_ADDRESS=0x42 python3 /opt/gpsd-i2c/gpsd-i2c.py
   ```
   If everything is correct, you should immediately see a bunch of NMEA sentences in the console.  Just <kbd>Ctrl</kbd>+<kbd>C</kbd> to stop, and then continue with the remaining steps below.
   
   If not, you'll need to resolve whatever errors you see before proceeding.
   
3. Setup the systemd service (use the I²C bus and address of your GPS module):
   ```bash
   cd /opt/gpsd-i2c
   cp gpsd-i2c.service /etc/systemd/system/
   mkdir /etc/systemd/system/gpsd-i2c.service.d/
   printf "[Service]\nEnvironment=I2C_BUS=0 I2C_ADDRESS=0x42\n" > \
     /etc/systemd/system/gpsd-i2c.service.d/override.conf
   ```

4. Start the service automatically on boot:
   ```bash
   systemctl enable --now gpsd-i2c.service
   ```

Of course, you don't have to install this into `/opt` -- anywhere you prefer is fine, just be sure to update the `WorkingDirectory=` line in the [gpsd-i2c.service](gpsd-i2c.service) file.

If the service starts, then you should see a new virtual serial port in `/dev/gpsd0`.  You can change the name of this device, if necessary, by editing the [gpsd-i2c.service](gpsd-i2c.service) file.

> [!TIP]
> Don't forget to execute `systemctl daemon-reload` after editing the service file.

You can monitor the status with:
```bash
journalctl -fu gpsd-i2c.service
```


### Reconfigure GPSD

Now that socat is running our Python script and redirecting its output to `/dev/gpsd0` (or whatever device you may have changed it to), we can configure GPSD to read from it.  We'll also want to add the `--readonly` flag to the command so that GPSD doesn't attempt to write anything to the device (it wouldn't work anyway).

First, stop GPSD if it is running (assumes systemd):
```bash
systemctl stop gpsd
```

**For Debian/Ubuntu users:** If you installed GPSD with `apt`, you might be able to do this one of two ways:

1. Run:
   ```bash
   dpkg-reconfigure gpsd
   ```
   ...to be prompted for configuration options.  Just specify `/dev/gpsd0` when prompted for the device, and append `--readonly` when prompted for additional options.

2. Alternatively, you should have a file at `/etc/default/gpsd` that looks something like this:
   ```bash
   START_DAEMON="true"
   #GPSD_OPTIONS="-n"
   GPSD_OPTIONS="-n --readonly"
   #DEVICES="/dev/ttyAMA0"
   DEVICES="/dev/gpsd0"
   USBAUTO="false"
   GPSD_SOCKET="/var/run/gpsd.sock"
   ```

**For other systems**, these configuration options might be found in:
- `/etc/sysconfig`
- `/lib/systemd/system/gpsd.service`
- `/etc/systemd/system/gpsd.service`

Once you've re-configured GPSD, you can attempt to restart it:
```bash
systemctl start gpsd
```

Then check the logs to see that it's actually running:
```bash
journalctl -fu gpsd
```

And as a final test, execute either `gpsmon` or `cgps -s` to view live data from GPSD.


## Credit

The Python script in this utility was something I found on [ozzmaker.com](https://ozzmaker.com/accessing-gps-via-i2c-on-a-berrygps-imu/) by [richardp](https://ozzmaker.com/author/richard/).  I applied some tweaks to bring it up-to-date and make it work seamlessly with socat as a systemd service.
