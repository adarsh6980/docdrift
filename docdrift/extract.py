import re, textwrap
from dataclasses import dataclass

FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.S | re.M)
# reStructuredText: ".. code-block:: python" or ".. code:: python", indented body, ends at dedent
RST = re.compile(r"^\.\. code(?:-block)?::\s*(\w+)[^\S\n]*\n[ \t]*\n((?:^[ \t]+.*(?:\n|$)|^[ \t]*\n)+)", re.M)
REPL = re.compile(r"^(>>>|\.\.\.) ?")

@dataclass(frozen=True)
class Snippet:
    file: str
    index: int
    lang: str
    code: str
    line: int

def _normalize(code: str) -> str:
    """Make a doc snippet runnable: dedent; convert doctest-style >>> blocks to plain code."""
    code = textwrap.dedent(code)
    lines = code.splitlines()
    if any(REPL.match(l) for l in lines):
        kept = []
        for l in lines:
            m = REPL.match(l)
            if m:
                kept.append(l[m.end():])
            # else: expected-output line inside a doctest block - drop
        code = "\n".join(kept)
    return code.strip("\n") + "\n"

def extract_snippets(path: str, text: str, langs=("python", "py")):
    """Markdown fenced blocks and RST code blocks. Snippets ordered by position in the file."""
    found = []
    for m in FENCE.finditer(text):
        if m.group(1).lower() in langs:
            found.append((m.start(), text.count("\n", 0, m.start()) + 2, m.group(1).lower(), m.group(2)))
    for m in RST.finditer(text):
        if m.group(1).lower() in langs:
            found.append((m.start(), text.count("\n", 0, m.start()) + 3, m.group(1).lower(), m.group(2)))
    found.sort()
    return [Snippet(path, i, lang, _normalize(code), line) for i, (_, line, lang, code) in enumerate(found)]
