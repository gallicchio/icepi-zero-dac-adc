# The source behind the prebuilt Linux

`src/linux/prebuilt/` holds binaries of GPL-licensed programs: the Linux kernel
(6.12) and BusyBox (1.37.0), inside `Image`, `rootfs.cpio.gz` and
`sdcard.img.xz`. The GPL (version 2, section 3) says that whoever passes those
binaries on must also make their *complete corresponding source* available:
the upstream source, every patch that was applied, and the configuration.

Here that source is three public things, pinned to exact versions:

| ingredient | where | version |
| --- | --- | --- |
| the kernel and BusyBox archives | kernel.org, busybox.net (Buildroot downloads them) | `linux-6.12.tar.xz`, `busybox-1.37.0.tar.bz2` |
| the patches | Buildroot's `package/busybox/*.patch` (14), and linux-on-litex-vexriscv's `buildroot/patches/linux/*.patch` (30: LiteX's drivers) | Buildroot 2026.02.3, linux-on-litex-vexriscv `05fc5e4` |
| the configuration | this repository's `src/linux/` (the defconfig, the kernel fragment, the BusyBox fragment, the root-file-system overlay) | this repository |

`collect_source.sh` fetches all of it and lays it out the way Buildroot's
`make legal-info` does, in about ten minutes: an archive, a `series` file and
the patches for each package, their licence texts, and `manifest.csv`.
`src/linux/prebuilt/legal-info-manifest.csv` is that manifest, from the build
that made the images.

**Is a script that fetches the source enough?** It is what most educational
and hobby projects do, and it gives anyone everything needed to rebuild the
images bit for bit, which is the spirit of the licence. Read strictly, GPLv2
asks that the source *accompany* the binaries, or that you promise in writing
to supply it for three years; pointing at kernel.org is a convenience, not a
guarantee that the archive will still be there. The simple way to be on the
right side of both readings costs nothing: attach the `legal-info/sources/`
folder that `collect_source.sh` produces (about 250 MB, mostly the kernel
archive) to a GitHub Release of this repository, and name that Release here:

> Source archive: (not yet published)

Since 3.03 tells every reader how to rebuild the images from these same
ingredients, the tutorial itself is also the written offer.
