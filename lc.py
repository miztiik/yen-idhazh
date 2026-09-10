import re
import sys
from pathlib import Path

LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


def slugs(path):
    out, fence = set(), False
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^#{1,6} (.+)$", line)
        if m:
            t = re.sub(r"[`*\[\]()]", "", m.group(1))
            t = re.sub(r"[^a-zA-Z0-9 _-]", "", t).strip().lower()
            out.add(re.sub(r"\s+", "-", t))
    return out


files = sorted(Path("docs").rglob("*.md"))
cache, bad = {}, 0
for f in files:
    for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
        for text, href in LINK.findall(line):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            part, _, anchor = href.partition("#")
            target = (f.parent / part) if part else f
            try:
                target = target.resolve().relative_to(Path.cwd().resolve())
            except ValueError:
                continue
            if not target.exists():
                print(f"MISSING {f.as_posix()}:{n} -> {href}")
                bad += 1
                continue
            if anchor and target.suffix == ".md":
                if target not in cache:
                    cache[target] = slugs(target)
                if anchor not in cache[target]:
                    print(f"DEAD    {f.as_posix()}:{n} -> {href}")
                    bad += 1
            if part and text.endswith(".md") and Path(text).name != Path(part).name:
                print(f"MISLABEL {f.as_posix()}:{n} -> text {text!r} opens {part!r}")
                bad += 1
print(f"checked {len(files)} md files; {bad} bad")
sys.exit(0)
