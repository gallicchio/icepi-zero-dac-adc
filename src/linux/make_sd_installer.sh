#!/bin/sh
# make_sd_installer.sh -- build the two sets of boot images for the SD card of 3.04.
#
# Run from $ADDA/tools/linux-on-litex-vexriscv after the Buildroot build, with
# the gateware already built by make_linux.py --build:
#
#     sh $ADDA/src/linux/make_sd_installer.sh
#
#   images_sd/       what goes on the card's FAT partition: Image, opensbi.bin,
#                    and a device tree whose root file system is /dev/mmcblk0p2
#   images_install/  a one-time serial boot: the usual kernel and root file
#                    system, plus an "installer payload" -- images_sd's files,
#                    an MBR and install-sd.sh -- appended to the initramfs, so
#                    they appear under /boot/sd on the running system
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
BR=${BR:-$HERE/../../tools/buildroot-icepi/images}
MAKE_LINUX="python3 $HERE/make_linux.py --board=icepi_zero_adda --uart-baudrate=460800"

# ---- images_sd: the files the BIOS will load from the card -------------------
mkdir -p images_sd
cp $BR/Image images_sd/
cp $BR/fw_jump.bin images_sd/opensbi.bin
$MAKE_LINUX --rootfs=mmcblk0p2 --images-dir=images_sd > /dev/null

# ---- the payload: an uncompressed cpio archive with /boot/sd/* ----------------
P=$(mktemp -d)
mkdir -p $P/boot/sd $P/root
gzip -9 -c images_sd/Image > $P/boot/sd/Image.gz          # gunzipped onto the card
cp images_sd/opensbi.bin images_sd/rv32.dtb images_sd/boot.json $P/boot/sd/
python3 $HERE/make_mbr.py $P/boot/sd/mbr.bin
cp $HERE/install-sd.sh $P/root/
chmod +x $P/root/install-sd.sh
(cd $P && find boot root | cpio -o -H newc --quiet) > payload.cpio
rm -rf $P

# ---- images_install: rootfs.cpio.gz + zero padding to 4 bytes + payload -------
# The kernel unpacks concatenated archives one after another, skipping zero
# bytes between them; an uncompressed one must start on a 4-byte boundary.
mkdir -p images_install
cp $BR/Image images_install/
cp $BR/fw_jump.bin images_install/opensbi.bin
cp $BR/rootfs.cpio.gz images_install/rootfs.cpio.gz
SIZE=$(stat -c %s images_install/rootfs.cpio.gz)
head -c $(( (4 - SIZE % 4) % 4 )) /dev/zero >> images_install/rootfs.cpio.gz
cat payload.cpio >> images_install/rootfs.cpio.gz
rm payload.cpio
$MAKE_LINUX --images-dir=images_install > /dev/null      # sizes the initrd in the DTB

ls -l images_sd images_install
