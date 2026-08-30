"""Low-level text scanning shared by the CDK parser.

Everything here is deliberately dumb about TypeScript syntax except for the
one thing that actually matters for regex-based extraction: not letting a
brace inside a string, template literal, or comment throw off bracket
balancing.
"""
import html
import re

_QUOTES = ("'", '"', "`")


def dom_id(prefix, key):
    return prefix + "__" + re.sub(r"[^A-Za-z0-9_]", "_", key)


def find_matching(text, open_idx, open_ch="{", close_ch="}"):
    """Return the index of the char matching text[open_idx], skipping over
    string/template literals and comments so a stray brace inside a Docker
    CMD string, a `// {note}` comment, or a JSON literal in an env var
    doesn't desynchronize the count."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            nl = text.find("\n", i)
            i = nl if nl != -1 else n
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = end + 2 if end != -1 else n
            continue
        if ch in _QUOTES:
            quote = ch
            i += 1
            while i < n and text[i] != quote:
                i += 2 if text[i] == "\\" else 1
            i += 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_options(text, after_idx):
    i = after_idx
    while i < len(text) and text[i] not in "{;":
        i += 1
    if i >= len(text) or text[i] != "{":
        return None
    end = find_matching(text, i, "{", "}")
    return text[i + 1:end] if end != -1 else None


def extract_block(text, keyname):
    """Return inner text of `keyname: {...}` within text, or None."""
    m = re.search(re.escape(keyname) + r"\s*:\s*\{", text)
    if not m:
        return None
    end = find_matching(text, m.end() - 1, "{", "}")
    return text[m.end():end] if end != -1 else None


def parse_env_pairs(text):
    block = extract_block(text, "environment")
    if not block:
        return []
    pairs = []
    for m in re.finditer(r"(\w+)\s*:\s*([^,{}]+(?:\{[^{}]*\}[^,{}]*)?)", block):
        pairs.append((m.group(1), m.group(2).strip().rstrip(",")))
    return pairs


def esc(s):
    return html.escape(str(s)) if s is not None else ""
