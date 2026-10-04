// main.c -- a first C program for the RISC-V CPU inside the FPGA: prime numbers.
//
// Nothing here needs the ADC or the DAC: it is the kind of job a processor is for.
// It counts the primes below 100,000 and times itself with the SoC's timer, then
// shows one prime after another on the LEDs, in binary, slowly enough to read.
//
//     make                                         -> primes.bin (needs ../build/stock)
//     litex_term --kernel=primes.bin /dev/ttyUSB0  then type "serialboot" at litex>

#include <stdio.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>      // leds_out_write(), timer0_...(): written by LiteX
#include <generated/soc.h>      // CONFIG_CLOCK_FREQUENCY

// ##########################################################################
// ##  KEY FUNCTION: trial division.  Every candidate costs a multiply (d*d)
// ##  and a remainder (n % d) per step: real arithmetic for the CPU.
// ##########################################################################
static int is_prime(unsigned int n)
{
	if (n < 2)
		return 0;
	if (n % 2 == 0)
		return n == 2;
	for (unsigned int d = 3; d * d <= n; d += 2)
		if (n % d == 0)
			return 0;
	return 1;
}

// The SoC's timer0 counts down at the 50 MHz system clock.  Start it at the
// top, and the number of clock ticks since then is how far it has come down.
static void timer_start(void)
{
	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(0xffffffff);
	timer0_en_write(1);
}

static unsigned int timer_ticks(void)
{
	timer0_update_value_write(1);       // copy the counter into timer0_value
	return 0xffffffff - timer0_value_read();
}

// LiteX numbers the LEDs from the left (bit 0 = leftmost), so reverse the
// five bits to make a binary number read the usual way, MSB on the left.
static void leds_show(unsigned int v)
{
	unsigned int r = 0;
	for (int i = 0; i < 5; i++)
		if (v & (1 << i))
			r |= 1 << (4 - i);
	// ######################################################################
	// ##  KEY LINE: one store instruction to the LED register's address.
	// ######################################################################
	leds_out_write(r);
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();
	printf("\nPrime numbers on a RISC-V CPU inside an FPGA.\n");

	// 1. How fast is this CPU?
	timer_start();
	unsigned int count = 0;
	for (unsigned int n = 2; n < 100000; n++)
		if (is_prime(n))
			count++;
	unsigned int ms = timer_ticks() / (CONFIG_CLOCK_FREQUENCY / 1000);
	printf("%u primes below 100000, found in %u ms.\n", count, ms);

	// 2. One prime every 0.2 s, on the LEDs.
	printf("Now one at a time, on the LEDs (the low 5 bits).  Press any key to pause.\n");
	for (unsigned int n = 2;; n++) {
		if (readchar_nonblock()) {       // a key was pressed: wait for another
			getchar();
			printf("paused; press any key to go on\n");
			getchar();
		}
		if (!is_prime(n))
			continue;
		leds_show(n);
		char bits[6];                   // the low 5 bits as text, like the LEDs
		for (int i = 0; i < 5; i++)
			bits[i] = (n >> (4 - i)) & 1 ? '1' : '0';
		bits[5] = 0;
		printf("%6u   LEDs %s\n", n, bits);
		busy_wait(200);                 // milliseconds
	}
	return 0;
}
