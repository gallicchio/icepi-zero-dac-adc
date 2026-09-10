#!/usr/bin/env python3
"""Minimal, non-interactive reimplementation of litex_term's SFL serial-boot
upload, since litex_term itself requires a real TTY on stdin (termios) and
fails outright ('Inappropriate ioctl for device') when driven from a
non-interactive/scripted context -- same class of problem this whole
investigation already hit with picocom. Protocol lifted directly from
litex/litex/tools/litex_term.py (sfl_* constants, SFLFrame, crc16, the
magic-handshake detection in reader()/detect_magic()/answer_magic()).

Usage: serial_boot.py <port> <baud> <kernel.bin> <address_hex> [timeout_s]
"""
import sys
import time
import serial

sfl_magic_req = b"sL5DdSMmkekro\n"
sfl_magic_ack = b"z6IHG7cYDID6o\n"

sfl_cmd_load = b"\x01"
sfl_cmd_jump = b"\x02"

sfl_ack_success  = b"K"
sfl_ack_crcerror = b"C"

SAFE_DATA_LENGTH = 64  # matches litex_term --safe

crc16_table = None


def _build_crc16_table():
    table = []
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
        table.append(crc)
    return table


def crc16(data):
    global crc16_table
    if crc16_table is None:
        crc16_table = _build_crc16_table()
    crc = 0
    for d in data:
        crc = crc16_table[((crc >> 8) ^ d) & 0xFF] ^ ((crc << 8) & 0xFFFF)
    return crc & 0xFFFF


def encode_frame(cmd, payload):
    packet = bytes([len(payload)])
    packet += crc16(cmd + payload).to_bytes(2, "big")
    packet += cmd
    packet += payload
    return packet


def wait_for_magic(ser, timeout):
    window = bytes(len(sfl_magic_req))
    deadline = time.time() + timeout
    seen = bytearray()
    while time.time() < deadline:
        c = ser.read(1)
        if not c:
            continue
        seen += c
        sys.stdout.buffer.write(c)
        sys.stdout.flush()
        window = window[1:] + c
        if window == sfl_magic_req:
            return True
    return False


def send_frame_and_wait_ack(ser, cmd, payload, retries=16, timeout=2.0):
    frame = encode_frame(cmd, payload)
    for _ in range(retries):
        ser.write(frame)
        ser.timeout = timeout
        reply = ser.read(1)
        if reply == sfl_ack_success:
            return True
        if reply == sfl_ack_crcerror:
            continue
        return False
    return False


def upload(ser, filename, address):
    with open(filename, "rb") as f:
        data = f.read()
    total = len(data)
    sent = 0
    while sent < total:
        chunk = data[sent:sent + SAFE_DATA_LENGTH]
        payload = (address + sent).to_bytes(4, "big") + chunk
        if not send_frame_and_wait_ack(ser, sfl_cmd_load, payload):
            print(f"\nupload failed at offset {sent}/{total}")
            return False
        sent += len(chunk)
        print(f"\ruploading: {sent}/{total} bytes", end="")
    print()
    return True


def jump(ser, address):
    payload = address.to_bytes(4, "big")
    return send_frame_and_wait_ack(ser, sfl_cmd_jump, payload)


def main():
    port     = sys.argv[1]
    baud     = int(sys.argv[2])
    kernel   = sys.argv[3]
    address  = int(sys.argv[4], 16)
    handshake_timeout = float(sys.argv[5]) if len(sys.argv) > 5 else 20.0

    ser = serial.Serial(port, baud, timeout=0.2)
    ser.dtr = True
    ser.rts = True

    print(f"[serial_boot] waiting up to {handshake_timeout}s for boot handshake...")
    if not wait_for_magic(ser, handshake_timeout):
        print("\n[serial_boot] timed out waiting for serial-boot magic handshake")
        ser.close()
        sys.exit(1)

    print("\n[serial_boot] got magic handshake, replying and uploading")
    ser.write(sfl_magic_ack)

    if not upload(ser, kernel, address):
        ser.close()
        sys.exit(1)

    print(f"[serial_boot] jumping to {address:#010x}")
    if not jump(ser, address):
        print("[serial_boot] jump command was not acked")
        ser.close()
        sys.exit(1)

    print("[serial_boot] done")
    ser.close()


if __name__ == "__main__":
    main()
