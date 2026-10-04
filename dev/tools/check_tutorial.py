"""Check the tutorial's integrity: run this after any edit, by a person or a program.

    python3 dev/tools/check_tutorial.py        # prints problems; exit 1 if there are errors

Errors (must fix):
  - sync_md.py --check fails: a page's printed code differs from the file in src/,
    a navigation line is out of date, or a page is missing from README.md's contents
  - a link to a file that doesn't exist, or to a heading (#anchor) that doesn't exist
  - an image that doesn't exist
  - a section named in the text (like 1.08 or 5.03) that isn't a link
  - a "The whole file" box without a <!-- file: --> code block in it
  - <details> boxes that don't balance, or a <summary> without a blank line after it
    (GitHub then shows the Markdown inside as plain text)
  - Unicode superscripts and subscripts (write <sup>2</sup>)
Warnings (worth a look):
  - a command runs a file (python3 x.py, make load-x) before the page prints that file
  - a page whose first thing after its title isn't a picture
  - something that looks like an old letter-style section name (1i's, 5d)
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
os.chdir(ROOT)
PAGES = sorted(glob.glob("tutorial/*.md"))
OTHERS = ["README.md", "dev/README.md", "adapter_board/README.md", "src/linux/prebuilt/README.md"]
errors, warnings = [], []


def slug(h):
    a = re.sub(r"<[^>]+>", "", h).strip().lower()
    a = re.sub(r"[`*]", "", a)
    return re.sub(r"[^\w\- ]", "", a).replace(" ", "-")


def anchors(path):
    s = re.sub(r"```.*?```", "", open(path).read(), flags=re.S)
    out, seen = set(), {}
    for h in re.findall(r"^#{1,6} (.+)$", s, re.M):
        a = slug(h)
        n = seen.get(a, 0)
        seen[a] = n + 1
        out.add(a if n == 0 else f"{a}-{n}")
    return out


def prose_lines(text):
    """(line number, line) outside fenced code blocks."""
    in_code = False
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            yield i, line


# ---- 1. sync_md ------------------------------------------------------------------------------
r = subprocess.run([sys.executable, os.path.join(HERE, "sync_md.py"), "--check"], capture_output=True, text=True)
if r.returncode:
    errors.append("sync_md.py --check: " + r.stdout.strip().replace("\n", "; "))

SECTION = {b[0] + "." + b[2:4] for b in map(os.path.basename, PAGES) if re.match(r"\d_\d\d_", b)}
# a number followed by one of these is a measurement, not a section ("3.04 s", "1.00 V")
UNIT = r"[mµun]?s|[mk]?V|[kMG]?Hz|dB\w*|[cmk]?m|[mk]?W|m?A|bits?|codes?|rad\w*|cycles?|[kM]S/s|ppm|ppb|volts?|seconds?|[kMG]B|times|turns|samples?|per|x"
for f in PAGES + OTHERS:
    text = open(f).read()
    base = os.path.dirname(f)
    # ---- 2, 3. links, anchors and images ---------------------------------------------------
    for i, line in prose_lines(text):
        for m in re.finditer(r"(!?)\[[^\]]*\]\(([^)\s]+)\)", line):
            target = m.group(2)
            if re.match(r"[a-z]+:", target):
                continue
            path, _, anchor = target.partition("#")
            full = os.path.normpath(os.path.join(base, path)) if path else f
            if not os.path.exists(full):
                errors.append(f"{f}:{i}: missing {'image' if m.group(1) else 'file'} {target}")
            elif anchor and full.endswith(".md") and anchor not in anchors(full):
                errors.append(f"{f}:{i}: no heading #{anchor} in {full}")
        for m in re.finditer(r'<img src="([^"]+)"', line):
            if not os.path.exists(os.path.normpath(os.path.join(base, m.group(1)))):
                errors.append(f"{f}:{i}: missing image {m.group(1)}")
    if f not in PAGES:
        continue
    # ---- 4. section names that aren't links ------------------------------------------------
    for i, line in prose_lines(text):
        if line.startswith("<!--") or line.startswith("# "):
            continue
        bare = re.sub(r"\[[^\]]*\]\([^)]*\)|`[^`]*`|<[^>]+>|https?://\S+", "", line)
        for m in re.finditer(r"(?<![\w.,/#§−–-])(\d\.\d\d)(?!\d|\.\d|[–-]\d| ?(?:" + UNIT + r")\b| ?[%°Ω×])", bare):
            if re.search(r"(?:Linux|kernel|version|Buildroot|MicroPython|LiteX|Python|GCC|v)\s?\(?$", bare[:m.start()]) \
                    or re.search(r"(?:Linux|kernel)[^\n]{0,40}\($", bare[:m.start()]):
                continue                                   # a version number: "Linux 6.12"
            if m.group(1) in SECTION:
                errors.append(f"{f}:{i}: section {m.group(1)} named but not linked")
        for m in re.finditer(r"(?<![\w./#-])[0-6][a-k](?='s\b|\)|,| and\b| or\b)", bare):
            warnings.append(f"{f}:{i}: old letter-style section name? '{m.group(0)}': {line.strip()[:80]}")
    # ---- 5. "The whole file" boxes, and details --------------------------------------------
    for m in re.finditer(r"<summary>The whole file: <code>([^<]+)</code></summary>(.*?)</details>", text, re.S):
        if "<!-- file:" not in m.group(2):
            errors.append(f"{f}: 'The whole file: {m.group(1)}' has no <!-- file: --> block")
    if text.count("<details>") != text.count("</details>"):
        errors.append(f"{f}: <details> and </details> don't balance")
    for m in re.finditer(r"</summary>\n(?!\n)", text):
        errors.append(f"{f}:{text[:m.start()].count(chr(10)) + 1}: no blank line after </summary>")
    # ---- 6. superscripts --------------------------------------------------------------------
    for i, line in prose_lines(text):
        if re.search(r"[⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉]", line) and not line.startswith("!["):
            errors.append(f"{f}:{i}: Unicode super/subscript (use <sup>/<sub>)")
    # ---- 7. run before print ----------------------------------------------------------------
    printed = {}
    for m in re.finditer(r"<!-- file: (\S+) -->", text):
        printed.setdefault(os.path.basename(m.group(1)), m.start())
    for m in re.finditer(r"```(?:console|bash)\n(.*?)```", text, re.S):
        for name in re.findall(r"python3 ([\w]+\.py)|make (?:load-)?([\w]+)(?:\.bit)?", m.group(1)):
            fname = name[0] or (name[1] + ".sv")
            if fname in printed and printed[fname] > m.start():
                warnings.append(f"{f}: runs {fname} before printing it")
    # ---- 8. a picture first ------------------------------------------------------------------
    after = text.split("\n# ", 1)[-1].split("\n", 1)[-1].lstrip("\n")
    if not (after.startswith("![") or after.startswith("<img") or after.startswith("<p") or after.startswith("<a")):
        warnings.append(f"{f}: doesn't open with a picture")

for e in errors:
    print("ERROR  ", e)
for w in sorted(set(warnings)):
    print("warning", w)
print(f"{len(errors)} errors, {len(set(warnings))} warnings, in {len(PAGES)} pages")
sys.exit(1 if errors else 0)
