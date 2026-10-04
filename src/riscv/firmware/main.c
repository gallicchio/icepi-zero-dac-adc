// main.c -- a small command shell for the ADC/DAC peripherals (2.03-2.05, and
// 7.04's loadable filter).
//
// Runs on the VexRiscv CPU inside the FPGA.  Talk to it with
//     litex_term --kernel=firmware.bin /dev/ttyUSB0
// and type "help".
//
// Every peripheral register has a C function made for it by LiteX, in
// build/icepi_zero/software/include/generated/csr.h: funcgen_tw_write(),
// capture_status_read(), lockin_x_read() and so on.  Each one is a single
// load or store to a fixed address.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include <irq.h>
#include <system.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>

#define F_SYS              CONFIG_CLOCK_FREQUENCY   /* 50 MHz */
#define ADC_CODES_PER_VOLT 25.35f                   /* measured: see 0.00 */
#define N_SAMPLES          16384

/*---- function generator (2.03) ---------------------------------------------*/

static const char *wave_names[] = {"sine", "square", "triangle", "sawtooth"};

static void funcgen_set(uint32_t hz, int amplitude, int wave)
{
	uint32_t tw = ((uint64_t)hz << 32) / F_SYS;     /* f = tw * F_SYS / 2^32 */
	/* ####################################################################
	 * ##  KEY LINE: one store to the tuning-word register, and the DDS in
	 * ##  funcgen_core.sv starts making the new frequency.
	 * #################################################################### */
	funcgen_tw_write(tw);
	funcgen_amplitude_write(amplitude);
	funcgen_waveform_write(wave);
}

static void print_frequency(void)
{
	uint64_t f = (uint64_t)funcgen_tw_read() * F_SYS;      /* Hz * 2^32 */
	uint32_t hz = f >> 32;
	uint32_t mhz = ((f & 0xffffffff) * 1000) >> 32;         /* the fraction, in mHz */
	printf("%lu.%03lu Hz", (unsigned long)hz, (unsigned long)mhz);
}

static void fg_cmd(char *args[], int n)
{
	if (n >= 2) {
		int amplitude = (n >= 3) ? atoi(args[2]) : 255;
		int wave = 0;
		if (n >= 4)
			for (int i = 0; i < 4; i++)
				if (strncmp(args[3], wave_names[i], 3) == 0)
					wave = i;
		funcgen_set(strtoul(args[1], NULL, 0), amplitude, wave);
	}
	printf("funcgen: ");
	print_frequency();
	printf(", amplitude %d/255, %s\n", (int)funcgen_amplitude_read(),
	       wave_names[funcgen_waveform_read() & 3]);
}

/*---- ADC capture (2.04) ------------------------------------------------------*/

/* The capture buffer is ordinary memory as far as the CPU is concerned. */
static volatile uint8_t *const samples = (volatile uint8_t *)CAPTURE_BUF_BASE;

static int capture(int decimation, int trig_level)
{
	uint32_t config = decimation & 0xf;
	if (trig_level >= 0)                                  /* trig_enable + level */
		config |= (1 << 8) | ((trig_level & 0xff) << 16);
	capture_config_write(config);
	/* ####################################################################
	 * ##  KEY LINE: start a capture.  The hardware records 16384 samples by
	 * ##  itself; the CPU just waits for the `done` bit below.
	 * #################################################################### */
	capture_control_write(1);                             /* start */
	for (int ms = 0; ms < 25000; ms++) {                  /* 16384 samples: 0.7 ms .. 21 s at decimation 15 */
		if (capture_status_read() & 2)                /* done */
			return 0;
		busy_wait(1);
	}
	return -1;
}

static void cap_cmd(char *args[], int n)
{
	int d = (n >= 2) ? atoi(args[1]) : 0;
	int level = (n >= 3) ? atoi(args[2]) : -1;
	if (capture(d, level) < 0) {
		printf("capture: timed out (no trigger?)\n");
		return;
	}
	int lo = 255, hi = 0, sum = 0;
	for (int i = 0; i < N_SAMPLES; i++) {
		int s = samples[i];                          /* a load from the buffer */
		lo = s < lo ? s : lo;
		hi = s > hi ? s : hi;
		sum += s;
	}
	printf("capture: %d samples at %lu S/s, codes %d..%d, mean %d\n", N_SAMPLES,
	       (unsigned long)(F_SYS / 2 >> d), lo, hi, sum / N_SAMPLES);
}

static void dump_cmd(void)
{
	/* 16384 samples as hex, 64 per line: 34 kB of text, ~3 s at 115200 baud */
	for (int i = 0; i < N_SAMPLES; i++) {
		printf("%02x", samples[i]);
		if (i % 64 == 63)
			printf("\n");
	}
}

/*---- lock-in (2.05) ----------------------------------------------------------*/

/* One measurement at the function generator's frequency.  Returns the
   amplitude (volts at the ADC) and phase (degrees) of what came back. */
static int lockin_measure(int n_log2, float *volts, float *degrees)
{
	lockin_n_log2_write(n_log2);
	lockin_control_write(1);                              /* start */
	for (int ms = 0; ms < 2000; ms++) {
		if (lockin_status_read() & 2) {               /* done */
			/* The sums are 64-bit; divide by 2^n_log2 in integers first
			   (keeping 8 fraction bits), since this CPU's C library can't
			   convert a 64-bit integer straight to float. */
			int32_t x256 = (int64_t)lockin_x_read() >> (n_log2 - 8);
			int32_t y256 = (int64_t)lockin_y_read() >> (n_log2 - 8);
			float x = x256 / 256.0f;                      /* < adc * cos > */
			float y = y256 / 256.0f;                      /* < adc * -sin > */
			/* ####################################################################
			 * ##  KEY LINES: amplitude and phase from X and Y, in floating point --
			 * ##  the part of the lock-in that's easier in C than in logic.
			 * #################################################################### */
			*volts   = 2.0f * sqrtf(x * x + y * y) / 127.0f / ADC_CODES_PER_VOLT;
			*degrees = atan2f(y, x) * 180.0f / (float)M_PI;
			return 0;
		}
		busy_wait(1);
	}
	return -1;
}

/* print x/1000 with three decimals: printf here has no %f */
static void print_milli(int x)
{
	printf("%s%d.%03d", x < 0 ? "-" : "", abs(x) / 1000, abs(x) % 1000);
}

static void li_cmd(char *args[], int n)
{
	if (n >= 2)
		funcgen_set(strtoul(args[1], NULL, 0), 255, 0);
	int n_log2 = (n >= 3) ? atoi(args[2]) : 20;          /* 8..24 */
	float v, deg;
	if (lockin_measure(n_log2, &v, &deg) < 0) {
		printf("lockin: timed out\n");
		return;
	}
	print_frequency();
	printf("  ");
	print_milli(v * 1e6f);                                /* microvolts -> "mV" */
	printf(" mV  ");
	print_milli(deg * 1000);
	printf(" deg\n");
}

static void sweep_cmd(char *args[], int n)
{
	if (n < 4) {
		printf("usage: sweep <start Hz> <stop Hz> <points> [n_log2]\n");
		return;
	}
	float f0 = strtoul(args[1], NULL, 0), f1 = strtoul(args[2], NULL, 0);
	int points = atoi(args[3]);
	int n_log2 = (n >= 5) ? atoi(args[4]) : 20;
	printf("# f_Hz amplitude_mV phase_deg\n");
	for (int i = 0; i < points; i++) {
		float f = f0 * powf(f1 / f0, points > 1 ? (float)i / (points - 1) : 0);  /* log spacing */
		float v, deg;
		funcgen_set((uint32_t)f, 255, 0);
		if (lockin_measure(n_log2, &v, &deg) < 0)
			break;
		printf("%lu ", (unsigned long)f);
		print_milli(v * 1e6f);
		printf(" ");
		print_milli(deg * 1000);
		printf("\n");
	}
}

/*---- the loadable filter (7.04) -----------------------------------------------*/

/* The sixteen b and four a registers were made in order, so b_k lives at b0's
   address + 4k: index them, instead of calling twenty csr.h functions by name. */
static void filter_b_write(int k, int v) { csr_write_simple((uint16_t)v, CSR_FILTER_B0_ADDR + 4 * k); }
static int  filter_b_read(int k)         { return (int16_t)csr_read_simple(CSR_FILTER_B0_ADDR + 4 * k); }
static void filter_a_write(int k, int v) { csr_write_simple((uint16_t)v, CSR_FILTER_A1_ADDR + 4 * (k - 1)); }
static int  filter_a_read(int k)         { return (int16_t)csr_read_simple(CSR_FILTER_A1_ADDR + 4 * (k - 1)); }

/* A whole filter: nb feed-forward and na feedback taps, the rest zero. */
static void filter_load(const int16_t *b, int nb, const int16_t *a, int na)
{
	for (int k = 0; k < 16; k++)
		filter_b_write(k, k < nb ? b[k] : 0);
	for (int k = 1; k <= 4; k++)
		filter_a_write(k, k <= na ? a[k - 1] : 0);
}

/* 7.01's SET 1, the 15-tap windowed sinc with a 2 MHz cutoff, now in Q2.13:
     python3 -c "import numpy as np, scipy.signal as s
     print(np.round(8192 * s.firwin(15, 2e6, fs=25e6)).astype(int))"       */
static const int16_t lowpass_b[15] = {-12, 8, 87, 289, 625, 1020, 1344, 1470,
                                      1344, 1020, 625, 289, 87, 8, -12};
static const int16_t edge_b[3] = {-8192, 16384, -8192};     /* 7.01's SET 2: [-1 2 -1] */

static const char *src_names[] = {"ADC", "impulse", "step", "noise", "tone", "?", "?", "?"};

static void filter_show(void)
{
	printf("filter: b =");
	for (int k = 0; k < 16; k++)
		printf(" %d", filter_b_read(k));
	printf("\n        a =");
	for (int k = 1; k <= 4; k++)
		printf(" %d", filter_a_read(k));
	printf("   (x 8192)\n");
	uint64_t f = (uint64_t)filter_tone_read() * (F_SYS / 2);     /* Hz x 2^32: the ADC's rate */
	int status = filter_status_read();
	printf("        src %s, out %s, tone %lu Hz; the DAC plays %s%s%s\n",
	       src_names[filter_src_read() & 7],
	       filter_out_read() ? "the input" : "the output",
	       (unsigned long)((f + (1ull << 31)) >> 32),               /* rounded */
	       filter_dac_source_read() ? "the filter" : "the function generator ('filter on' to switch)",
	       (status & 1) ? ", running" : "", (status & 2) ? ", clipped" : "");
}

static void filter_cmd(char *args[], int n)
{
	const char *what = (n >= 2) ? args[1] : "show";
	int k = (n >= 3) ? atoi(args[2]) : 0;
	int v = (n >= 4) ? atoi(args[3]) : 0;
	if (!strcmp(what, "b") && n >= 4 && k >= 0 && k < 16)
		/* ####################################################################
		 * ##  KEY LINE: one store, and the multiplier in filter_core.sv uses
		 * ##  the new coefficient on the next sample, 40 ns later.
		 * #################################################################### */
		filter_b_write(k, v);
	else if (!strcmp(what, "a") && n >= 4 && k >= 1 && k <= 4)
		filter_a_write(k, v);
	else if (!strcmp(what, "src") && n >= 3)
		filter_src_write(k);
	else if (!strcmp(what, "out") && n >= 3)
		filter_out_write(k);
	else if (!strcmp(what, "tone") && n >= 3)
		filter_tone_write(((uint64_t)strtoul(args[2], NULL, 0) << 32) / (F_SYS / 2));
	else if (!strcmp(what, "on"))
		filter_dac_source_write(1);
	else if (!strcmp(what, "off"))
		filter_dac_source_write(0);
	else if (!strcmp(what, "lowpass"))
		filter_load(lowpass_b, 15, NULL, 0);
	else if (!strcmp(what, "edge"))
		filter_load(edge_b, 3, NULL, 0);
	else if (!strcmp(what, "rc") && n >= 3 && k >= 0 && k <= 13) {
		/* 7.02's one-pole, y += (x - y) / 2^K:  b0 = 2^-K,  a1 = -(1 - 2^-K) */
		int16_t b0 = 8192 >> k, a1 = -(8192 - (8192 >> k));
		filter_load(&b0, 1, &a1, 1);
	} else if (strcmp(what, "show")) {
		printf("usage: filter b <0-15> <v> | a <1-4> <v> | src <0-4> | out <0-1> | tone <Hz>\n"
		       "       filter on | off | lowpass | edge | rc <K> | show\n");
		return;
	}
	filter_show();
}

/*---- the shell ------------------------------------------------------------------*/

static void help(void)
{
	puts("fg <Hz> [amplitude 0-255] [sine|square|triangle|sawtooth]   function generator");
	puts("cap [decimation 0-15] [trigger level 0-255]                capture 16384 samples");
	puts("dump                                                       print the capture, in hex");
	puts("li [Hz] [n_log2]                                           one lock-in measurement");
	puts("sweep <start Hz> <stop Hz> <points> [n_log2]               lock-in frequency sweep");
	puts("filter [show]                                              the loadable filter's settings (7.04)");
	puts("filter b <0-15> <v> | a <1-4> <v>                          one coefficient, x 8192 (Q2.13)");
	puts("filter lowpass | edge | rc <K>                             presets: 2 MHz low-pass, [-1 2 -1], one-pole");
	puts("filter src <0-4> | out <0-1> | tone <Hz> | on | off        input (0 ADC 1 impulse 2 step 3 noise 4 tone), DAC");
}

static char *readline(void)
{
	static char line[80];
	static int len = 0;
	while (readchar_nonblock()) {
		char c = getchar();
		if (c == '\r' || c == '\n') {
			line[len] = 0;
			len = 0;
			putchar('\n');
			return line;
		} else if ((c == 0x7f || c == 0x08) && len > 0) {
			len--;
			fputs("\x08 \x08", stdout);
		} else if (c >= ' ' && len < (int)sizeof(line) - 1) {
			line[len++] = c;
			putchar(c);
		}
	}
	return NULL;
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();
	puts("\nADC/DAC peripherals on LiteX.  Type 'help'.");
	funcgen_set(1000000, 255, 0);
	printf("adda> ");
	while (1) {
		char *line = readline();
		if (line == NULL)
			continue;
		char *args[8];
		int n = 0;
		for (char *tok = strtok(line, " "); tok && n < 8; tok = strtok(NULL, " "))
			args[n++] = tok;
		if (n == 0)                         ;
		else if (!strcmp(args[0], "help"))  help();
		else if (!strcmp(args[0], "fg"))    fg_cmd(args, n);
		else if (!strcmp(args[0], "cap"))   cap_cmd(args, n);
		else if (!strcmp(args[0], "dump"))  dump_cmd();
		else if (!strcmp(args[0], "li"))    li_cmd(args, n);
		else if (!strcmp(args[0], "sweep")) sweep_cmd(args, n);
		else if (!strcmp(args[0], "filter")) filter_cmd(args, n);
		else                                printf("unknown command; try 'help'\n");
		printf("adda> ");
	}
}
