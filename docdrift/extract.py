import re, textwrap
from dataclasses import dataclass

FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.S | re.M)
# reStructuredText: ".. code-block:: python" or ".. code:: python", indented body, ends at dedent
RST = re.compile(r"^\.\. code(?:-block)?::\s*(\w+)[^\S\n]*\n[ \t]*\n((?:^[ \t]+.*(?:\n|$)|^[ \t]*\n)+)", re.M)
REPL = re.compile(r"^(>>>|\.\.\.) ?")
BARE_REPL = re.compile(r"^([ \t]*)>>> ")

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

def _bare_doctests(text, spans):
    """Doctest blocks (>>> lines) in prose, outside any directive/fence span.

    Common in RST READMEs that show console sessions without a code-block
    directive. A block runs from the first >>> line through following
    .../output lines, ending at a blank line or dedent. Session execution
    keeps cross-block state, so split blocks still share earlier bindings.
    """
    blocks, pos = [], 0
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line_start = pos
        pos += len(lines[i])
        m = BARE_REPL.match(lines[i])
        if not m or any(a <= line_start < b for a, b in spans):
            i += 1
            continue
        indent = len(m.group(1).replace("\t", "    "))
        start = line_start
        body = [lines[i]]
        j = i + 1
        while j < len(lines):
            l = lines[j]
            if REPL.match(l.lstrip()) and l[:indent].strip() == "":
                body.append(l); j += 1
            elif l.strip() and (len(l) - len(l.lstrip())) >= indent and not l.lstrip().startswith(".. "):
                body.append(l); j += 1  # doctest output line
            else:
                break
        blocks.append((start, text.count("\n", 0, start) + 1, "doctest", "".join(body)))
        pos += sum(len(l) for l in body[1:])
        i = j
    return blocks


def extract_snippets(path: str, text: str, langs=("python", "py", "python3", "pycon", "pycon3")):
    """Markdown fenced blocks, RST code blocks, and bare doctest blocks.
    Snippets ordered by position in the file."""
    found, spans = [], []
    for m in FENCE.finditer(text):
        if m.group(1).lower() in langs:
            found.append((m.start(), text.count("\n", 0, m.start()) + 2, m.group(1).lower(), m.group(2)))
            spans.append((m.start(), m.end()))
    for m in RST.finditer(text):
        if m.group(1).lower() in langs:
            found.append((m.start(), text.count("\n", 0, m.start()) + 3, m.group(1).lower(), m.group(2)))
            spans.append((m.start(), m.end()))
    found.extend(_bare_doctests(text, spans))
    found.sort()
    return [Snippet(path, i, lang, _normalize(code), line) for i, (_, line, lang, code) in enumerate(found)]
