#!/usr/bin/env python3
"""Open the port, wait briefly, send a command line, capture the response."""
import sys
import time
import serial

port = sys.argv[1]
baud = int(sys.argv[2])
cmd = sys.argv[3]
wait_before = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
capture_seconds = float(sys.argv[5]) if len(sys.argv) > 5 else 8.0

ser = serial.Serial(port, baud, timeout=0.2)
ser.dtr = True
ser.rts = True

time.sleep(wait_before)
# drain anything already buffered (e.g. help banner) and print it
pre = ser.read(65536)
sys.stdout.buffer.write(pre)

ser.write((cmd + "\r\n").encode())

deadline = time.time() + capture_seconds
while time.time() < deadline:
    chunk = ser.read(4096)
    if chunk:
        sys.stdout.buffer.write(chunk)
        sys.stdout.flush()

ser.close()
