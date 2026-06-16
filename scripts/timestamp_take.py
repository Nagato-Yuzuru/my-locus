# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""
为 "I told you" take 生成 / 校验 RFC 3161 时间戳。

子命令：
  stamp [bundle] [--force]   冻结 claim.txt 并向 TSA 申请 proof.tsr；
                             不带 bundle = 给所有未盖章的 take 盖章（幂等）。
  verify [--lenient]         校验所有 take：(a) 密码学 (b) 冻结守卫。
                             默认 strict（要求每个 take 都有 proof）；
                             --lenient 允许缺失 proof（PR 上 autofix 会补）。

用法：
  uv run scripts/timestamp_take.py stamp content/i-told-you/my-take
  uv run scripts/timestamp_take.py stamp
  uv run scripts/timestamp_take.py verify
  uv run scripts/timestamp_take.py verify --lenient
"""

import argparse
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

SECTION_DIR = Path("content/i-told-you")
TSA_URL = "https://freetsa.org/tsr"
CA_FILE = Path("static/tsa/freetsa-cacert.pem")
TSA_CERT = Path("static/tsa/freetsa-tsa.crt")

CLAIM_RE = re.compile(r"\{\{<\s*claim\s*>\}\}(.*?)\{\{<\s*/claim\s*>\}\}", re.DOTALL)


def extract_claim(md_text: str) -> str | None:
    """返回 {{< claim >}}…{{< /claim >}} 之间的文本（去首尾空白）；无则 None。"""
    m = CLAIM_RE.search(md_text)
    if not m:
        return None
    return m.group(1).strip()


def read_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def claim_source(bundle: Path) -> Path:
    """由 claim_lang 决定被盖章的 index 文件（en ⇒ index.md, 其它 ⇒ index.<lang>.md）。"""
    candidates = sorted(bundle.glob("index*.md"))
    if not candidates:
        raise FileNotFoundError(f"no index*.md in {bundle}")
    lang = read_frontmatter(candidates[0]).get("claim_lang", "en")
    fname = "index.md" if lang == "en" else f"index.{lang}.md"
    src = bundle / fname
    if not src.exists():
        raise FileNotFoundError(f"claim_lang={lang} but {src} missing")
    return src


def _frozen_bytes(claim_text: str) -> bytes:
    return (claim_text + "\n").encode("utf-8")


def freeze_claim(bundle: Path, force: bool) -> Path:
    src = claim_source(bundle)
    claim = extract_claim(src.read_text(encoding="utf-8"))
    if claim is None:
        raise SystemExit(f"{src}: no {{{{< claim >}}}} block")
    claim_file = bundle / "claim.txt"
    new_bytes = _frozen_bytes(claim)
    if claim_file.exists() and claim_file.read_bytes() != new_bytes and not force:
        raise SystemExit(
            f"REFUSING to re-freeze {claim_file}: the claim changed after it was frozen.\n"
            f"A published claim is immutable — add a new episode (same series) instead.\n"
            f"Use --force ONLY if this take was never published."
        )
    claim_file.write_bytes(new_bytes)
    return claim_file


def freeze_guard(bundle: Path) -> None:
    """校验 (b)：页面展示的 claim 仍与冻结的 claim.txt 字节一致。"""
    src = claim_source(bundle)
    live = extract_claim(src.read_text(encoding="utf-8"))
    if live is None:
        raise SystemExit(f"{src}: lost its {{{{< claim >}}}} block")
    if _frozen_bytes(live) != (bundle / "claim.txt").read_bytes():
        raise SystemExit(f"FREEZE GUARD: {src} claim differs from frozen claim.txt")
