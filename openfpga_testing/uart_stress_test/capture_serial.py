#!/usr/bin/env python3
"""Capture bytes from the DAPLink CDC-ACM port and check them against the
expected uart_stress_test pattern. Never run this while openFPGALoader is
touching the same probe -- close this before/after any JTAG operation.

Usage: capture_serial.py <port> <baud> <seconds> <pattern:0|1> [expect_bytes]
"""
import sys
import time
import serial

def main():
    port = sys.argv[1]
    baud = int(sys.argv[2])
    seconds = float(sys.argv[3])
    pattern = int(sys.argv[4])
    expect_bytes = int(sys.argv[5]) if len(sys.argv) > 5 else None

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

    print(f"captured {len(data)} bytes")
    if b"<DAPLink:Overflow>" in data:
        idx = data.index(b"<DAPLink:Overflow>")
        print(f"OVERFLOW detected at byte offset {idx}")

    # Check for expected pattern, allowing a leading run of stray nulls
    # (documented as a self-clearing power-up artifact).
    start = 0
    while start < len(data) and data[start] == 0:
        start += 1
    if start:
        print(f"skipped {start} leading null byte(s)")

    payload = data[start:]
    if b"<DAPLink:Overflow>" in payload:
        cut = payload.index(b"<DAPLink:Overflow>")
        payload = payload[:cut]

    # Continuous mode is a free-running counter with no fixed phase relative
    # to when capture started, so check internal consistency (each byte is
    # the previous byte + 1, mod range) rather than absolute alignment.
    mismatches = 0
    if payload:
        if pattern == 0:
            expected = 0x55
        else:
            expected = payload[0]
        for i, b in enumerate(payload):
            if b != expected:
                mismatches += 1
                if mismatches <= 5:
                    print(f"mismatch at payload offset {i}: got {b:#04x} expected {expected:#04x}")
                expected = b  # resync so one bad byte doesn't cascade
            if pattern == 0:
                expected = 0x55
            else:
                expected = 0x20 + ((expected - 0x20 + 1) % (0x7E - 0x20 + 1))

    print(f"payload bytes checked: {len(payload)}, mismatches: {mismatches}")
    if expect_bytes is not None:
        print(f"expected {expect_bytes} bytes, got {len(payload)} clean payload bytes "
              f"({'OK' if len(payload) == expect_bytes else 'MISMATCH'})")

if __name__ == "__main__":
    main()
