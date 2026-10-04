#!/usr/bin/env python3
"""Write a 512-byte MBR (DOS) partition table for the SD card:

    partition 1:  64 MiB, FAT32 (type 0x0c)  -- the LiteX BIOS boots from here
    partition 2:   4 GiB, Linux (type 0x83)  -- the root file system

    python3 make_mbr.py mbr.bin           # what install-sd.sh writes (3.04)
    python3 make_mbr.py mbr.bin 512       # partition 2 of 512 MiB (make_sd_image.py)

The table is the first sector of the card: 446 bytes of (unused) boot code,
four 16-byte partition entries, and the signature 0x55 0xAA.  Each entry is
status, a CHS start address (unused today), type, a CHS end address, and the
two numbers that matter: the first sector and the number of sectors.
"""
import struct
import sys

SECTOR = 512
FIRST = 2048                              # 1 MiB in: the usual alignment
BOOT_SECTORS = 64 * 1024 * 1024 // SECTOR
ROOT_SECTORS = 4 * 1024 * 1024 * 1024 // SECTOR


def entry(bootable, ptype, first, count):
    no_chs = b"\xfe\xff\xff"              # "use the LBA fields"
    return struct.pack("<B3sB3sII", 0x80 if bootable else 0, no_chs, ptype, no_chs, first, count)


def make_mbr(root_sectors=ROOT_SECTORS):
    mbr = bytearray(SECTOR)
    struct.pack_into("<I", mbr, 440, 0x1CE9A0DA)              # disk signature (any value)
    mbr[446:462] = entry(True, 0x0C, FIRST, BOOT_SECTORS)
    mbr[462:478] = entry(False, 0x83, FIRST + BOOT_SECTORS, root_sectors)
    mbr[510:512] = b"\x55\xaa"
    return bytes(mbr)


if __name__ == "__main__":
    root = int(sys.argv[2]) * 1024 * 1024 // SECTOR if len(sys.argv) > 2 else ROOT_SECTORS
    open(sys.argv[1] if len(sys.argv) > 1 else "mbr.bin", "wb").write(make_mbr(root))
