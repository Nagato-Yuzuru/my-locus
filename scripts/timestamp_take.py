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
