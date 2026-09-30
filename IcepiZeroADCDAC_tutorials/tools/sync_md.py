"""Keep the code in IcepiZeroADCDAC_tutorials.md identical to the tested files.

A code block preceded by the line  <!-- file: path -->  (path relative to the
IcepiZeroADCDAC_tutorials/ directory) has its contents replaced by that file.

    python3 tools/sync_md.py           # rewrite the blocks in place
    python3 tools/sync_md.py --check   # exit 1 if any block is out of date
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, ".."))
MD = os.path.normpath(os.path.join(SRC, "..", "IcepiZeroADCDAC_tutorials.md"))

pat = re.compile(r"(<!-- file: (\S+) -->\n```[^\n]*\n)(.*?)(^```$)", re.S | re.M)
text = open(MD).read()
stale = []


def repl(m):
    body = open(os.path.join(SRC, m.group(2))).read()
    if not body.endswith("\n"):
        body += "\n"
    if body != m.group(3):
        stale.append(m.group(2))
    return m.group(1) + body + m.group(4)


new = pat.sub(repl, text)
if "--check" in sys.argv:
    print("out of date:" if stale else "all code blocks match their files", *stale)
    sys.exit(1 if stale else 0)
open(MD, "w").write(new)
print("updated:", *stale) if stale else print("nothing to update")
