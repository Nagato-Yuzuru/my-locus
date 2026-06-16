# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
设置某条 "I told you" take 的 verdict 字段（只改 frontmatter 里的 verdict 行）。

用法：
  uv run scripts/set_verdict.py <slug> <pending|correct|wrong|partial>
"""

import argparse
import re
from pathlib import Path

VALID = ("pending", "correct", "wrong", "partial")
SECTION = Path("content/i-told-you")


def set_verdict(md: Path, verdict: str) -> None:
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)(.*)$", text, re.DOTALL)
    if not m:
        raise SystemExit(f"{md}: no frontmatter")
    fm, n = re.subn(r'(?m)^verdict:\s*.*$', f'verdict: "{verdict}"', m.group(2), count=1)
    if n == 0:
        raise SystemExit(f"{md}: no 'verdict:' field in frontmatter")
    md.write_text(m.group(1) + fm + m.group(3) + m.group(4), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("slug")
    p.add_argument("verdict", choices=VALID)
    args = p.parse_args()
    files = sorted((SECTION / args.slug).glob("index*.md"))
    if not files:
        raise SystemExit(f"no take at {SECTION / args.slug}")
    for f in files:
        set_verdict(f, args.verdict)
    print(f"✓ {args.slug}: verdict = {args.verdict} ({len(files)} file(s))")


if __name__ == "__main__":
    main()
