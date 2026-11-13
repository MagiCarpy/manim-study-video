"""Compact index of the studio helpers: `study api [cslib|base|style|tts|all] [--grep WORD]`.

Generated from the source with `ast`, so nothing is imported (no manim, no TTS stack) and the
index cannot drift from the code. Default section: cslib. Lists public classes, functions,
methods (signature + first docstring line), style constants and tts.PRONOUNCE keys.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parent
SECTIONS = {
    "cslib": ["cslib.py"],
    "base": ["base.py"],
    "style": ["style.py"],
    "tts": ["tts.py"],
}
DOC_CHARS = 64  # first docstring line, truncated: enough to pick a helper, not to read it


def _doc(node) -> str:
    lines = (ast.get_docstring(node) or "").strip().splitlines()
    text = lines[0].strip() if lines else ""
    return text if len(text) <= DOC_CHARS else text[: DOC_CHARS - 3].rstrip() + "..."


def _sig(fn: ast.FunctionDef, is_method: bool) -> str:
    """Parameters with defaults; annotations dropped to keep the index short."""
    a = fn.args
    positional = a.posonlyargs + a.args
    defaults = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
    pairs = list(zip(positional, defaults))
    if is_method and pairs:
        pairs = pairs[1:]  # self / cls
    parts = [p.arg if d is None else f"{p.arg}={ast.unparse(d)}" for p, d in pairs]
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    elif a.kwonlyargs:
        parts.append("*")
    for p, d in zip(a.kwonlyargs, a.kw_defaults):
        parts.append(p.arg if d is None else f"{p.arg}={ast.unparse(d)}")
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return ", ".join(parts)


def _fn_line(fn: ast.FunctionDef, is_method: bool, prefix: str = "") -> str:
    doc = _doc(fn)
    head = f"{prefix}{fn.name}({_sig(fn, is_method)})"
    return f"{head}: {doc}" if doc else head


def _class_block(node: ast.ClassDef) -> list[str]:
    bases = ", ".join(ast.unparse(b) for b in node.bases)
    head = f"class {node.name}({bases})" if bases else f"class {node.name}"
    doc = _doc(node)
    lines = [f"{head}: {doc}" if doc else head]
    for member in node.body:
        if not isinstance(member, ast.FunctionDef):
            continue
        if member.name == "__init__":
            lines.append(f"  {node.name}({_sig(member, True)})")
        elif not member.name.startswith("_"):
            lines.append("  " + _fn_line(member, True, prefix="."))
    return lines


def _module_block(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            lines.extend(_class_block(node))
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            lines.append(_fn_line(node, False, prefix="def "))
    return lines


def _constant_lines(path: Path) -> list[str]:
    """Top-level UPPER_CASE assignments; ManimColor("#hex") shown as the bare hex."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines = []
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper()):
            continue
        value = node.value
        if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "ManimColor" and value.args:
            value = value.args[0]
        lines.append(f"{node.targets[0].id} = {ast.unparse(value)}")
    return lines


def _pronounce_lines(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "PRONOUNCE" for t in node.targets):
            pairs = [f"{ast.literal_eval(k)}->{ast.literal_eval(v)}" for k, v in zip(node.value.keys, node.value.values)]
            return [f"PRONOUNCE ({len(pairs)}): " + ", ".join(pairs)]
    return ["PRONOUNCE: (not found)"]


def _section(name: str, grep: str | None) -> list[str]:
    """Lines for one section; with --grep, class blocks keep their header and matching members."""
    files = [STUDIO / f for f in SECTIONS[name]]
    out = []
    for path in files:
        header = f"# studio/{path.name}"
        if name == "style":
            body = _constant_lines(path)
            body += _module_block(path)
        elif name == "tts":
            body = _module_block(path) + _pronounce_lines(path)
        else:
            body = _module_block(path)
        if grep:
            body = _filter(body, grep)
        if body:
            out.append(header)
            out.extend(body)
    return out


def _filter(lines: list[str], word: str) -> list[str]:
    """Keep matching lines; a class header is kept when any of its members match."""
    word = word.lower()
    kept, header, header_hit, members = [], None, False, []
    for line in lines:
        if line.startswith("class "):
            if header is not None and (header_hit or members):
                kept.append(header)
                kept.extend(members)
            header, header_hit, members = line, word in line.lower(), []
        elif line.startswith("  "):
            if word in line.lower():
                members.append(line)
        else:
            if header is not None and (header_hit or members):
                kept.append(header)
                kept.extend(members)
            header, header_hit, members = None, False, []
            if word in line.lower():
                kept.append(line)
    if header is not None and (header_hit or members):
        kept.append(header)
        kept.extend(members)
    return kept


def main(argv: list[str]) -> int:
    grep = None
    names = []
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--grep":
            if not args:
                print("study api: --grep needs a word", file=sys.stderr)
                return 2
            grep = args.pop(0)
        elif arg in SECTIONS or arg == "all":
            names.append(arg)
        else:
            print(f"usage: study api [{'|'.join(SECTIONS)}|all] [--grep WORD]  (got {arg!r})", file=sys.stderr)
            return 2
    selected = list(SECTIONS) if "all" in names else (names or ["cslib"])
    out = []
    for name in selected:
        out.extend(_section(name, grep))
    if not out:
        print(f"study api: nothing matches {grep!r}" if grep else "study api: empty index", file=sys.stderr)
        return 1
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
