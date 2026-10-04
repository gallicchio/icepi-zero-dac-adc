"""Link concepts to Wikipedia where they're first mentioned.

    python3 dev/tools/wiki_links.py          # edit the pages in place
    python3 dev/tools/wiki_links.py --dry    # just list what it would link

TERMS: on every page, the first mention in the prose (not in a heading, code, a link,
or a picture's description) becomes a link, unless the page already links there.
BASIC: the same, but only once in the whole tutorial: these are everywhere.
"""
import glob
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
W = "https://en.wikipedia.org/wiki/"
BASIC = {
    r"FPGAs?": "Field-programmable_gate_array",
    r"ADC": "Analog-to-digital_converter",
    r"DAC": "Digital-to-analog_converter",
    r"SystemVerilog": "SystemVerilog",
    r"RISC-V": "RISC-V",
    r"Linux kernel": "Linux_kernel",
}
TERMS = {
    r"lock-in amplifiers?": "Lock-in_amplifier",
    r"direct digital synthesis": "Direct_digital_synthesis",
    r"phase-locked loops?": "Phase-locked_loop",
    r"UART": "Universal_asynchronous_receiver-transmitter",
    r"Nyquist frequency": "Nyquist_frequency",
    r"aliasing": "Aliasing",
    r"sampling theorem": "Nyquist%E2%80%93Shannon_sampling_theorem",
    r"fast Fourier transform": "Fast_Fourier_transform",
    r"discrete Fourier transform": "Discrete_Fourier_transform",
    r"leakage": "Spectral_leakage",
    r"butterfly": "Butterfly_diagram",
    r"bit-reversed": "Bit-reversal_permutation",
    r"linear-feedback shift register": "Linear-feedback_shift_register",
    r"m-sequence": "Maximum_length_sequence",
    r"C/A code": "GPS_signals#Coarse/Acquisition_code",
    r"impulse response": "Impulse_response",
    r"cross-correlation": "Cross-correlation",
    r"Wiener–Khinchin theorem": "Wiener%E2%80%93Khinchin_theorem",
    r"phasor": "Phasor",
    r"Euler's formula": "Euler%27s_formula",
    r"Bode plot": "Bode_plot",
    r"network analyzer": "Network_analyzer_(electrical)",
    r"spectrum analyzer": "Spectrum_analyzer",
    r"metastability": "Metastability_(electronics)",
    r"state machine": "Finite-state_machine",
    r"zero-order hold": "Zero-order_hold",
    r"equivalent time": "Equivalent_time_sampling",
    r"system on chip": "System_on_a_chip",
    r"BIOS": "BIOS",
    r"memory-management unit": "Memory_management_unit",
    r"device tree": "Devicetree",
    r"BusyBox": "BusyBox",
    r"Buildroot": "Buildroot",
    r"initramfs": "Initial_ramdisk",
    r"sysfs": "Sysfs",
    r"master boot record|MBR": "Master_boot_record",
    r"quartz crystal": "Crystal_oscillator",
    r"Q factor|Q(?= of (?:about )?[0-9])": "Q_factor",
    r"time-domain reflectometry": "Time-domain_reflectometer",
    r"PI controller|PID controller": "PID_controller",
    r"Allan deviation": "Allan_variance",
    r"frequency-shift keying": "Frequency-shift_keying",
    r"bit error rate": "Bit_error_rate",
    r"signal-to-noise ratio": "Signal-to-noise_ratio",
    r"orthogonal frequency-division multiplexing": "Orthogonal_frequency-division_multiplexing",
    r"QAM-64|QAM": "Quadrature_amplitude_modulation",
    r"cyclic prefix": "Cyclic_prefix",
    r"Shannon's limit": "Shannon%E2%80%93Hartley_theorem",
    r"error-vector magnitude": "Error_vector_magnitude",
    r"time transfer": "Time_transfer",
    r"White Rabbit": "White_Rabbit_Project",
    r"Einstein's convention": "Einstein_synchronisation",
    r"pulse compression": "Pulse_compression",
    r"chirp": "Chirp",
    r"ISM band": "ISM_radio_band",
    r"near-field": "Near_and_far_field",
    r"Johnson noise": "Johnson%E2%80%93Nyquist_noise",
    r"SLIP": "Serial_Line_Internet_Protocol",
    r"amplitude modulation": "Amplitude_modulation",
    r"crystal radio": "Crystal_radio",
    r"WWV": "WWV_(radio_station)",
    r"Costas loop": "Costas_loop",
    r"QPSK": "Phase-shift_keying#Quadrature_phase-shift_keying_(QPSK)",
    r"[Dd]ither": "Dither",
    r"differential nonlinearity": "Differential_nonlinearity",
    r"Fourier series": "Fourier_series",
    r"sinc": "Sinc_function",
    r"transmission line": "Transmission_line",
    r"characteristic impedance": "Characteristic_impedance",
    r"photodiode": "Photodiode",
    r"GPS-disciplined": "GPS_disciplined_oscillator",
    r"NTP": "Network_Time_Protocol",
    r"standing waves?": "Standing_wave",
    r"Huygens": "Christiaan_Huygens",
    r"injection locking|Adler's equation": "Injection_locking",
    r"two's complement": "Two%27s_complement",
    r"hexadecimal": "Hexadecimal",
    r"Gray code": "Gray_code",
    r"Hann window": "Hann_function",
    r"low-noise amplifier": "Low-noise_amplifier",
    r"CIC filter": "Cascaded_integrator%E2%80%93comb_filter",
    r"FIR filter": "Finite_impulse_response",
    r"envelope detector": "Envelope_detector",
    r"superheterodyne": "Superheterodyne_receiver",
    r"Pound–Drever–Hall": "Pound%E2%80%93Drever%E2%80%93Hall_technique",
}
DONE_BASIC = set()


def link_page(path, dry):
    text = open(path).read()
    out, in_code, changed = [], False, []
    used = {W + p for p in list(BASIC.values()) + list(TERMS.values()) if f"]({W + p})" in text}
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code or line.startswith("#") or line.startswith("<!--") or line.startswith("[←") \
                or line.startswith("!") or line.startswith("<img") or line.startswith("<summary"):
            out.append(line)
            continue
        for terms, once in ((BASIC, True), (TERMS, False)):
            for pat, page in terms.items():
                url = W + page
                if once and url in used:
                    DONE_BASIC.add(pat)          # already linked here: the tutorial's first mention
                if url in used or (once and pat in DONE_BASIC):
                    continue
                # spans to leave alone: links, inline code, HTML tags, emphasis markers around code
                protected = [m.span() for m in re.finditer(r"!?\[[^\]]*\]\([^)]*\)|`[^`]*`|<[^>]+>|https?://\S+", line)]
                for m in re.finditer(r"(?<![\w/\[-])(" + pat + r")(?![\w-])", line):
                    if any(a <= m.start() < b for a, b in protected):
                        continue
                    line = line[:m.start()] + f"[{m.group(1)}]({url})" + line[m.end():]
                    used.add(url)
                    changed.append(m.group(1))
                    if once:
                        DONE_BASIC.add(pat)
                    break
        out.append(line)
    if changed and not dry:
        open(path, "w").write("\n".join(out))
    return changed


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    pages = sorted(glob.glob(os.path.join(ROOT, "tutorial", "*.md")))
    for p in pages + ["README"]:
        if p == "README":                   # the front page links its basics too
            DONE_BASIC.clear()
            p = os.path.join(ROOT, "README.md")
        c = link_page(p, dry)
        if c:
            print(os.path.relpath(p, ROOT) + ":", ", ".join(c))
