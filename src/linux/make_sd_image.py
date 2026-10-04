#!/usr/bin/env python3
"""Make an SD-card image file on the laptop: the same card that install-sd.sh
makes on the board (3.04), ready for any card-writing program.

    python3 make_sd_image.py IMAGES_SD ROOTFS_EXT2 sdcard.img [--root-mib 512] [--xz]

IMAGES_SD    the boot files for a card: Image, opensbi.bin, rv32.dtb (made by
             make_linux.py --rootfs=mmcblk0p2) and boot.json
ROOTFS_EXT2  Buildroot's images/rootfs.ext2: the root file system, owned by root
             as it should be, which a plain copy of the files couldn't be

The image is the partition table, then partition 1 (64 MiB, FAT32, the boot
files) and partition 2 (ext2, the root file system, grown to --root-mib).
Needs `pip install pyfatfs`, and e2fsprogs (e2fsck, resize2fs): Buildroot's own,
which it builds next to images/, or the laptop's.  Linux only.
"""
import argparse
import os
import shutil
import subprocess
import tempfile

from pyfatfs.PyFat import PyFat
from pyfatfs.PyFatFS import PyFatFS

import make_mbr

MIB = 1024 * 1024

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("images_sd")
ap.add_argument("rootfs_ext2")
ap.add_argument("out")
ap.add_argument("--root-mib", type=int, default=512, help="size of partition 2 (default 512)")
ap.add_argument("--xz", action="store_true", help="also write OUT.xz")
args = ap.parse_args()

with tempfile.TemporaryDirectory() as tmp:
    # partition 1: a FAT32 file system holding the four boot files
    fat = os.path.join(tmp, "boot.img")
    if shutil.which("mkfs.vfat"):                    # dosfstools, if it's there
        subprocess.run(["mkfs.vfat", "-F", "32", "-n", "BOOT", "-C", fat, str(64 * 1024)],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        open(fat, "wb").truncate(64 * MIB)
        PyFat().mkfs(fat, PyFat.FAT_TYPE_FAT32, size=64 * MIB, label="BOOT")
    fs = PyFatFS(fat)
    for f in ["Image", "opensbi.bin", "rv32.dtb", "boot.json"]:
        fs.writebytes("/" + f, open(os.path.join(args.images_sd, f), "rb").read())
    fs.close()

    # partition 2: Buildroot's ext2 image, grown to fill the partition
    ext = os.path.join(tmp, "root.img")
    shutil.copy(args.rootfs_ext2, ext)
    # Buildroot's own e2fsprogs, which made the image, if they're next to it: an
    # older e2fsck or resize2fs may not know all of the file system's features
    host = os.path.join(os.path.dirname(os.path.abspath(args.rootfs_ext2)), "..", "host", "sbin")
    tool = lambda t: os.path.join(host, t) if os.path.exists(os.path.join(host, t)) else t
    subprocess.run([tool("e2fsck"), "-fy", ext], check=False, stdout=subprocess.DEVNULL)
    subprocess.run([tool("resize2fs"), ext, "%dM" % args.root_mib], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([tool("e2label"), ext, "root"], check=True)

    # the card: partition table, gap, partition 1, partition 2
    with open(args.out, "wb") as out:
        out.write(make_mbr.make_mbr(args.root_mib * MIB // make_mbr.SECTOR))
        out.seek(make_mbr.FIRST * make_mbr.SECTOR)
        out.write(open(fat, "rb").read())
        out.write(open(ext, "rb").read())
size = os.path.getsize(args.out)
print(f"{args.out}: {size / MIB:.0f} MiB")
if args.xz:
    subprocess.run(["xz", "-9", "-k", "-f", "-T0", args.out], check=True)
    print(f"{args.out}.xz: {os.path.getsize(args.out + '.xz') / MIB:.1f} MiB")
