#!/usr/bin/env python3
"""Dump raw captured bytes (as text, best-effort) from the DAPLink serial
port for a fixed window -- for inspecting LiteX BIOS boot banners rather
than the synthetic uart_stress_test pattern."""
import sys
import time
import serial

port = sys.argv[1]
baud = int(sys.argv[2])
seconds = float(sys.argv[3])

ser = serial.Serial(port, baud, timeout=0.2)
ser.dtr = True
ser.rts = True

data = bytearray()
deadline = time.time() + seconds
while time.time() < deadline:
    chunk = ser.read(4096)
    if chunk:
        data.extend(chunk)
ser.close()

sys.stderr.write(f"captured {len(data)} bytes\n")
sys.stdout.buffer.write(data)
