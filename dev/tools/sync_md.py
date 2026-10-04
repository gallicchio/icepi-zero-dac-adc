"""Keep the tutorial's pages consistent with the tested files, and with each other.

1. A code block preceded by the line  <!-- file: path -->  (path relative to the
   repository's top folder) has its contents replaced by that file, so the code
   on the page is always exactly the code that was tested.
2. A line  <!-- nav -->  gets a line of links after it: to the previous page, the
   contents, and the next page, in file-name order.  Each link goes to the page's
   title (#1b-a-counter-on-the-leds), so that GitHub scrolls past its file list.
   (The links go on their own line: Markdown doesn't look for links on a line
   that starts with an HTML comment.)
3. In README.md, each contents line  - [title](tutorial/file.md#anchor)  is
   rewritten from that page's title, and every page must have one.
4. A line  <!-- author -->  (the last line of every page) gets the author's
   name and email after it.

    python3 dev/tools/sync_md.py           # rewrite the pages in place
    python3 dev/tools/sync_md.py --check   # exit 1 if anything is out of date

dev/tools/check_tutorial.py checks everything else (links, anchors, images, ...).
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
TUT = os.path.join(ROOT, "tutorial")
README = os.path.join(ROOT, "README.md")

code = re.compile(r"(<!-- file: (\S+) -->\n```[^\n]*\n)(.*?)(^```$)", re.S | re.M)
pages = sorted(glob.glob(os.path.join(TUT, "*.md")))
titles = {}
for p in pages:
    m = re.search(r"^# (.+)$", open(p).read(), re.M)
    titles[p] = m.group(1) if m else os.path.basename(p)


def slug(title):
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    a = re.sub(r"<[^>]+>", "", title).strip().lower()
    return re.sub(r"[^\w\- ]", "", a).replace(" ", "-")


def href(p):
    return f"{os.path.basename(p)}#{slug(titles[p])}"


SEP = " &emsp;&emsp;&emsp; "
AUTHOR = "<!-- author -->\n<sub>Jason Gallicchio, jason@hmc.edu, Harvey Mudd College</sub>"


def nav(p):
    i = pages.index(p)
    prev = f"[← {titles[pages[i - 1]]}]({href(pages[i - 1])})" if i > 0 else "[← Front page](../README.md)"
    nxt = f"[{titles[pages[i + 1]]} →]({href(pages[i + 1])})" if i + 1 < len(pages) else ""
    return "<!-- nav -->\n" + SEP.join(x for x in [prev, "**[Contents](../README.md#contents)**", nxt] if x)


def contents(text):
    """README.md: rewrite each contents line from its page's title."""
    def repl(m):
        p = os.path.join(TUT, m.group(1))
        if p not in titles:
            return m.group(0)
        return f"- [{titles[p]}](tutorial/{href(p)})"
    return re.sub(r"^- \[[^\]]*\]\(tutorial/([^)#]+\.md)(?:#[^)]*)?\)$", repl, text, flags=re.M)


stale = []
for p in pages + [README]:
    text = open(p).read()

    def repl(m):
        body = open(os.path.join(ROOT, m.group(2))).read()
        if not body.endswith("\n"):
            body += "\n"
        return m.group(1) + body + m.group(4)

    new = code.sub(repl, text)
    if p in pages:
        new = re.sub(r"^<!-- nav -->.*$(?:\n\[(?:←|Contents).*$)?", lambda m: nav(p), new, flags=re.M)
        new = re.sub(r"^<!-- author -->.*$(?:\n<sub>.*</sub>$)?", AUTHOR, new, flags=re.M)
    else:
        new = contents(new)
    if new != text:
        stale.append(os.path.relpath(p, ROOT))
        if "--check" not in sys.argv:
            open(p, "w").write(new)

listed = set(re.findall(r"^- \[[^\]]*\]\(tutorial/([^)#]+\.md)", open(README).read(), re.M))
missing = [os.path.basename(p) for p in pages if os.path.basename(p) not in listed]
if missing:
    print("not in README.md's contents:", *missing)

if "--check" in sys.argv:
    print("out of date:" if stale else "every page is up to date", *stale)
    sys.exit(1 if stale or missing else 0)
print("updated:", *stale) if stale else print("nothing to update")
