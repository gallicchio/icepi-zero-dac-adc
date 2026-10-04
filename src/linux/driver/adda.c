// SPDX-License-Identifier: GPL-2.0
/*
 * adda.c -- a Linux driver for the Icepi Zero ADC/DAC peripherals (Chapter 3).
 *
 * The kernel finds the hardware through the device tree node that
 * make_linux.py adds (compatible = "hmc,icepi-adda"), and this driver gives
 * each peripheral a directory of ordinary files:
 *
 *   /sys/bus/platform/devices/<address>.adda/
 *       funcgen/frequency    Hz.  Write "1000000"; read back the exact value.
 *       funcgen/amplitude    0..255
 *       funcgen/waveform     sine, square, triangle or sawtooth
 *       capture/decimation   keep 1 sample in 2^decimation (0..15)
 *       capture/trigger      "off", or a level 0..255 to wait for
 *       capture/sample_rate  samples per second (read only)
 *       capture/data         reading it takes a capture: 16384 bytes
 *       lockin/n_log2        average 2^n_log2 samples (8..24)
 *       lockin/result        reading it measures at funcgen/frequency:
 *                            "<x> <y>", the averages of (adc-128)*cos and
 *                            (adc-128)*(-sin), in ADC codes squared
 */
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/math64.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/sysfs.h>
#include <linux/unaligned.h>

/* Register offsets within each peripheral: build/<board>/csr.csv */
#define FUNCGEN_TW		0x00
#define FUNCGEN_AMPLITUDE	0x04
#define FUNCGEN_WAVEFORM	0x08
#define CAPTURE_CONTROL		0x00
#define CAPTURE_CONFIG		0x04
#define CAPTURE_STATUS		0x08
#define LOCKIN_CONTROL		0x00
#define LOCKIN_N_LOG2		0x04
#define LOCKIN_STATUS		0x08
#define LOCKIN_X		0x0c	/* 64 bits, as two 32-bit words, high word first */
#define LOCKIN_Y		0x14
#define STATUS_DONE		BIT(1)

#define N_SAMPLES		16384

struct adda {
	void __iomem *funcgen, *capture, *lockin, *buffer;
	u32 clk;			/* the SoC's clock, Hz */
	int decimation;
	int trigger;			/* -1 = off */
	struct mutex lock;		/* one capture or measurement at a time */
	u8 samples[N_SAMPLES];		/* the most recent capture */
};

/* ---- function generator -------------------------------------------------- */

static ssize_t frequency_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);
	u64 f = (u64)readl(a->funcgen + FUNCGEN_TW) * a->clk;	/* Hz * 2^32 */
	u64 mhz = ((f & 0xffffffff) * 1000) >> 32;		/* the fraction, in mHz */

	return sysfs_emit(buf, "%llu.%03llu\n", f >> 32, mhz);
}

static ssize_t frequency_store(struct device *dev, struct device_attribute *attr,
			       const char *buf, size_t count)
{
	struct adda *a = dev_get_drvdata(dev);
	u64 hz;
	int ret = kstrtou64(buf, 0, &hz);

	if (ret)
		return ret;
	if (hz >= a->clk / 2)
		return -EINVAL;
	writel(div_u64(hz << 32, a->clk), a->funcgen + FUNCGEN_TW);	/* f = tw * clk / 2^32 */
	return count;
}
static DEVICE_ATTR_RW(frequency);

static ssize_t amplitude_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);

	return sysfs_emit(buf, "%u\n", readl(a->funcgen + FUNCGEN_AMPLITUDE));
}

static ssize_t amplitude_store(struct device *dev, struct device_attribute *attr,
			       const char *buf, size_t count)
{
	struct adda *a = dev_get_drvdata(dev);
	u8 v;
	int ret = kstrtou8(buf, 0, &v);

	if (ret)
		return ret;
	writel(v, a->funcgen + FUNCGEN_AMPLITUDE);
	return count;
}
static DEVICE_ATTR_RW(amplitude);

static const char * const waveforms[] = { "sine", "square", "triangle", "sawtooth" };

static ssize_t waveform_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);

	return sysfs_emit(buf, "%s\n", waveforms[readl(a->funcgen + FUNCGEN_WAVEFORM) & 3]);
}

static ssize_t waveform_store(struct device *dev, struct device_attribute *attr,
			      const char *buf, size_t count)
{
	struct adda *a = dev_get_drvdata(dev);
	int i = sysfs_match_string(waveforms, buf);

	if (i < 0)
		return i;
	writel(i, a->funcgen + FUNCGEN_WAVEFORM);
	return count;
}
static DEVICE_ATTR_RW(waveform);

static struct attribute *funcgen_attrs[] = {
	&dev_attr_frequency.attr, &dev_attr_amplitude.attr, &dev_attr_waveform.attr, NULL,
};
static const struct attribute_group funcgen_group = {
	.name = "funcgen", .attrs = funcgen_attrs,
};

/* ---- ADC capture ------------------------------------------------------------ */

static ssize_t decimation_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);

	return sysfs_emit(buf, "%d\n", a->decimation);
}

static ssize_t decimation_store(struct device *dev, struct device_attribute *attr,
				const char *buf, size_t count)
{
	struct adda *a = dev_get_drvdata(dev);
	int v;
	int ret = kstrtoint(buf, 0, &v);

	if (ret)
		return ret;
	if (v < 0 || v > 15)
		return -EINVAL;
	a->decimation = v;
	return count;
}
static DEVICE_ATTR_RW(decimation);

static ssize_t trigger_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);

	if (a->trigger < 0)
		return sysfs_emit(buf, "off\n");
	return sysfs_emit(buf, "%d\n", a->trigger);
}

static ssize_t trigger_store(struct device *dev, struct device_attribute *attr,
			     const char *buf, size_t count)
{
	struct adda *a = dev_get_drvdata(dev);
	int v;

	if (sysfs_streq(buf, "off")) {
		a->trigger = -1;
		return count;
	}
	if (kstrtoint(buf, 0, &v) || v < 0 || v > 255)
		return -EINVAL;
	a->trigger = v;
	return count;
}
static DEVICE_ATTR_RW(trigger);

static ssize_t sample_rate_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);

	return sysfs_emit(buf, "%u\n", (a->clk / 2) >> a->decimation);
}
static DEVICE_ATTR_RO(sample_rate);

/* Record 16384 samples into a->samples.  Called with a->lock held. */
static int adda_capture(struct adda *a)
{
	u32 config = a->decimation, status;
	int i, ret;

	if (a->trigger >= 0)
		config |= BIT(8) | (a->trigger << 16);	/* trig_enable, trig_level */
	writel(config, a->capture + CAPTURE_CONFIG);
	writel(1, a->capture + CAPTURE_CONTROL);	/* start */

	/* up to 21 s at decimation 15; the calling process sleeps meanwhile */
	ret = readl_poll_timeout(a->capture + CAPTURE_STATUS, status,
				 status & STATUS_DONE, 1000, 30 * USEC_PER_SEC);
	if (ret)
		return ret;

	/* the buffer holds four samples per 32-bit word, first in the low byte */
	for (i = 0; i < N_SAMPLES / 4; i++)
		put_unaligned_le32(readl(a->buffer + 4 * i), &a->samples[4 * i]);
	return 0;
}

static ssize_t data_read(struct file *file, struct kobject *kobj, struct bin_attribute *attr,
			 char *buf, loff_t off, size_t count)
{
	struct adda *a = dev_get_drvdata(kobj_to_dev(kobj));	/* the device, even in a group */
	int ret = 0;

	/* "cat data" reads in several pieces: capture only for the first one */
	mutex_lock(&a->lock);
	if (off == 0)
		ret = adda_capture(a);
	if (!ret)
		memcpy(buf, a->samples + off, count);
	mutex_unlock(&a->lock);
	return ret ? ret : count;
}
static BIN_ATTR_RO(data, N_SAMPLES);

static struct attribute *capture_attrs[] = {
	&dev_attr_decimation.attr, &dev_attr_trigger.attr, &dev_attr_sample_rate.attr, NULL,
};
static struct bin_attribute *capture_bin_attrs[] = { &bin_attr_data, NULL };
static const struct attribute_group capture_group = {
	.name = "capture", .attrs = capture_attrs, .bin_attrs = capture_bin_attrs,
};

/* ---- lock-in ----------------------------------------------------------------- */

static ssize_t n_log2_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);

	return sysfs_emit(buf, "%u\n", readl(a->lockin + LOCKIN_N_LOG2));
}

static ssize_t n_log2_store(struct device *dev, struct device_attribute *attr,
			    const char *buf, size_t count)
{
	struct adda *a = dev_get_drvdata(dev);
	int v;

	if (kstrtoint(buf, 0, &v) || v < 8 || v > 24)
		return -EINVAL;
	writel(v, a->lockin + LOCKIN_N_LOG2);
	return count;
}
static DEVICE_ATTR_RW(n_log2);

static s64 read_s64(void __iomem *reg)
{
	return (s64)(((u64)readl(reg) << 32) | readl(reg + 4));
}

/* print sum / 2^n with three decimals, without floating point */
static int emit_mean(char *buf, int at, s64 sum, int n)
{
	s64 milli = (sum * 1000) >> n;			/* rounds toward -infinity */
	u64 mag = milli < 0 ? -milli : milli;
	u32 frac;
	u64 whole = div_u64_rem(mag, 1000, &frac);	/* a 32-bit CPU: no plain 64-bit "/" */

	return sysfs_emit_at(buf, at, "%s%llu.%03u", milli < 0 ? "-" : "", whole, frac);
}

static ssize_t result_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct adda *a = dev_get_drvdata(dev);
	int n = readl(a->lockin + LOCKIN_N_LOG2);
	u32 status;
	s64 x, y;
	int ret, len;

	mutex_lock(&a->lock);
	writel(1, a->lockin + LOCKIN_CONTROL);		/* start */
	ret = readl_poll_timeout(a->lockin + LOCKIN_STATUS, status,
				 status & STATUS_DONE, 1000, 2 * USEC_PER_SEC);
	x = read_s64(a->lockin + LOCKIN_X);
	y = read_s64(a->lockin + LOCKIN_Y);
	mutex_unlock(&a->lock);
	if (ret)
		return ret;

	len = emit_mean(buf, 0, x, n);
	len += sysfs_emit_at(buf, len, " ");
	len += emit_mean(buf, len, y, n);
	len += sysfs_emit_at(buf, len, "\n");
	return len;
}
static DEVICE_ATTR_RO(result);

static struct attribute *lockin_attrs[] = {
	&dev_attr_n_log2.attr, &dev_attr_result.attr, NULL,
};
static const struct attribute_group lockin_group = {
	.name = "lockin", .attrs = lockin_attrs,
};

/* ---- finding the hardware ------------------------------------------------------ */

static const struct attribute_group *adda_groups[] = {
	&funcgen_group, &capture_group, &lockin_group, NULL,
};

static int adda_probe(struct platform_device *pdev)
{
	struct adda *a = devm_kzalloc(&pdev->dev, sizeof(*a), GFP_KERNEL);

	if (!a)
		return -ENOMEM;
	/* each reg = <address size> in the device tree, by its reg-names entry */
	a->funcgen = devm_platform_ioremap_resource_byname(pdev, "funcgen");
	a->capture = devm_platform_ioremap_resource_byname(pdev, "capture");
	a->lockin  = devm_platform_ioremap_resource_byname(pdev, "lockin");
	a->buffer  = devm_platform_ioremap_resource_byname(pdev, "buffer");
	if (IS_ERR(a->funcgen) || IS_ERR(a->capture) || IS_ERR(a->lockin) || IS_ERR(a->buffer))
		return -ENODEV;
	if (of_property_read_u32(pdev->dev.of_node, "clock-frequency", &a->clk))
		a->clk = 50000000;
	a->trigger = -1;
	mutex_init(&a->lock);
	platform_set_drvdata(pdev, a);
	dev_info(&pdev->dev, "ADC/DAC peripherals ready, clock %u Hz\n", a->clk);
	return 0;
}

static const struct of_device_id adda_of_match[] = {
	{ .compatible = "hmc,icepi-adda" },
	{ }
};
MODULE_DEVICE_TABLE(of, adda_of_match);

static struct platform_driver adda_driver = {
	.probe = adda_probe,
	.driver = {
		.name		= "adda",
		.of_match_table	= adda_of_match,
		.dev_groups	= adda_groups,	/* the sysfs files above */
	},
};
module_platform_driver(adda_driver);

MODULE_DESCRIPTION("Icepi Zero AD9280/AD9708 function generator, capture and lock-in");
MODULE_LICENSE("GPL");
