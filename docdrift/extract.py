import re
from dataclasses import dataclass

FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.S | re.M)

@dataclass(frozen=True)
class Snippet:
    file: str
    index: int
    lang: str
    code: str
    line: int

def extract_snippets(path: str, text: str, langs=("python", "py")):
    out = []
    for i, m in enumerate(FENCE.finditer(text)):
        lang = m.group(1).lower()
        if lang in langs:
            line = text.count("\n", 0, m.start()) + 2
            out.append(Snippet(path, i, lang, m.group(2), line))
    return out
