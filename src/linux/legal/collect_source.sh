#!/bin/sh
# collect_source.sh -- fetch the complete corresponding source of the GPL programs in
# src/linux/prebuilt/ (the Linux kernel and BusyBox), with every patch that was applied to
# them and the configuration, exactly as they were built.  Needs the network; no compiling.
#
#     sh src/linux/legal/collect_source.sh [folder]      # about 10 minutes, ~500 MB
#
# What it does: clone Buildroot at the tag that built the images, clone
# linux-on-litex-vexriscv at the commit whose kernel patches and configuration were used,
# point Buildroot at this repository's src/linux as its external tree (the same three
# ingredients 3.03 uses), and run Buildroot's own `make legal-info`.  The result,
# <folder>/out/legal-info/, holds sources/<package>/ (the upstream archive, the patches in
# the order applied, and `series`), licenses/, buildroot.config and manifest.csv.
set -e
BUILDROOT_TAG=2026.02.3                 # src/linux/prebuilt/README.md says which build
LOLV_COMMIT=05fc5e4
ADDA=$(cd "$(dirname "$0")/../../.." && pwd)
D=${1:-$PWD/legal-info-src}
mkdir -p "$D"
cd "$D"
[ -d buildroot ] || git clone --branch $BUILDROOT_TAG --depth 1 https://gitlab.com/buildroot.org/buildroot.git
[ -d linux-on-litex-vexriscv ] || git clone https://github.com/litex-hub/linux-on-litex-vexriscv.git
(cd linux-on-litex-vexriscv && git checkout -q $LOLV_COMMIT)
cd buildroot
make O="$D/out" BR2_EXTERNAL="$D/linux-on-litex-vexriscv/buildroot:$ADDA/src/linux" icepi_adda_defconfig
make O="$D/out" legal-info
echo
echo "Source, patches and licences: $D/out/legal-info/"
ls "$D/out/legal-info/sources"
