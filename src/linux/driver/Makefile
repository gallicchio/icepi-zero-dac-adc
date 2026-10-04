# Build adda.ko against the kernel Buildroot built (3.03):
#     make
# The module must be built by the same compiler, from the same kernel source
# and configuration, as the kernel it will be loaded into.
obj-m := adda.o

# Buildroot's output folder (3.03): this repository's tools/buildroot-icepi
BR    ?= $(abspath $(CURDIR)/../../../tools/buildroot-icepi)
KDIR  ?= $(BR)/build/linux-6.12
# the same compiler Buildroot built the kernel with (riscv32-buildroot-linux-musl-gcc)
CROSS ?= $(patsubst %gcc,%,$(firstword $(wildcard $(BR)/host/bin/riscv32-buildroot-linux-*-gcc)))

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=riscv CROSS_COMPILE=$(CROSS) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) ARCH=riscv CROSS_COMPILE=$(CROSS) clean
