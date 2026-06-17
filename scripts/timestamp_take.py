# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
为 "I told you" take 逐语言抽取 claim 并做 RFC 3161 时间戳。

每个语言版本相互独立、各自盖章(两种语言不是严格镜像)。对每个
`index.<lang>.md`:从 frontmatter 的 `claim` 字段结构化抽取(yq) →
冻结成 `claim.<lang>.txt` → 申请 `proof.<lang>.tsr`。

抽取与盖章在 CI(autofix.yml)里完成;本地只管写。

子命令:
  stamp [bundle]      抽取每语言 claim → 冻结 → 缺 proof 则盖章(幂等)。
  verify [--lenient]  逐语言校验:(a) claim 字段未变 (b) proof 对 claim 验证通过。
                      默认 strict(要求每语言都有 proof);--lenient 允许缺失。

外部依赖:yq、openssl(均由 mise 提供)。
"""

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

SECTION_DIR = Path("content/i-told-you")
TSA_URL = "https://freetsa.org/tsr"
CA_FILE = Path("static/tsa/freetsa-cacert.pem")
TSA_CERT = Path("static/tsa/freetsa-tsa.crt")
DEFAULT_LANG = "en"


class TakeError(Exception):
    """A single language-claim failed extraction, stamping, or verification."""


def lang_of(index_file: Path) -> str:
    """index.md -> 'en'; index.zh-cn.md -> 'zh-cn'."""
    middle = index_file.name[len("index") : -len(".md")]
    return middle.lstrip(".") or DEFAULT_LANG


def extract_claim(index_file: Path) -> str:
    """用 yq 从 frontmatter 结构化抽取 `claim`(无正则);返回去掉首尾空白的文本。"""
    result = subprocess.run(
        ["yq", "--front-matter=extract", ".claim", str(index_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TakeError(f"{index_file}: yq failed: {result.stderr.strip()}")
    claim = result.stdout.strip()
    if not claim or claim == "null":
        raise TakeError(f"{index_file}: missing `claim` front-matter field")
    return claim


def frozen_bytes(claim: str) -> bytes:
    return (claim + "\n").encode("utf-8")


def verify_crypto(claim_file: Path, proof: Path) -> None:
    result = subprocess.run(
        ["openssl", "ts", "-verify", "-data", str(claim_file), "-in", str(proof),
         "-CAfile", str(CA_FILE), "-untrusted", str(TSA_CERT)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TakeError(f"{proof.name}: RFC 3161 verify failed: {result.stderr.strip()}")


def reply_time(proof: Path) -> str:
    out = subprocess.run(
        ["openssl", "ts", "-reply", "-in", str(proof), "-text"],
        check=True, capture_output=True, text=True,
    ).stdout
    for line in out.splitlines():
        if "Time stamp:" in line:
            return line.split("Time stamp:", 1)[1].strip()
    return "unknown"


def request_token(claim_file: Path, proof: Path) -> None:
    tsq = claim_file.with_suffix(".tsq")
    subprocess.run(
        ["openssl", "ts", "-query", "-data", str(claim_file), "-sha256", "-cert", "-out", str(tsq)],
        check=True, capture_output=True,
    )
    request = tsq.read_bytes()
    http = urllib.request.Request(
        TSA_URL, data=request, headers={"Content-Type": "application/timestamp-query"}
    )
    with urllib.request.urlopen(http, timeout=30) as response:  # noqa: S310 - fixed TSA URL
        proof.write_bytes(response.read())
    tsq.unlink()


def index_files(bundle: Path | None) -> list[Path]:
    root = bundle if bundle is not None else SECTION_DIR
    pattern = "index*.md" if bundle is not None else "*/index*.md"
    return sorted(root.glob(pattern))


def cmd_stamp(bundle: str | None) -> None:
    files = index_files(Path(bundle) if bundle else None)
    if not files:
        print("no takes found")
        return
    for index_file in files:
        lang = lang_of(index_file)
        claim_file = index_file.parent / f"claim.{lang}.txt"
        proof = index_file.parent / f"proof.{lang}.tsr"
        if proof.exists():
            print(f"· {index_file.parent.name} [{lang}]: already stamped")
            continue
        claim_file.write_bytes(frozen_bytes(extract_claim(index_file)))  # freeze at first stamp
        request_token(claim_file, proof)
        verify_crypto(claim_file, proof)
        print(f"✓ {index_file.parent.name} [{lang}]: stamped at {reply_time(proof)}")


def cmd_verify(strict: bool) -> None:
    files = index_files(None)
    failures: list[str] = []
    for index_file in files:
        lang = lang_of(index_file)
        name = f"{index_file.parent.name} [{lang}]"
        claim_file = index_file.parent / f"claim.{lang}.txt"
        proof = index_file.parent / f"proof.{lang}.tsr"
        try:
            current = frozen_bytes(extract_claim(index_file))
            if not proof.exists() or not claim_file.exists():
                if strict:
                    failures.append(f"{name}: not stamped (missing claim/proof)")
                continue
            if claim_file.read_bytes() != current:  # freeze guard: field changed since stamping
                failures.append(f"{name}: claim field changed since it was stamped")
                continue
            verify_crypto(claim_file, proof)
        except TakeError as e:
            failures.append(str(e))
    if failures:
        print("VERIFY FAILED:")
        for failure in failures:
            print(f"  ✗ {failure}")
        raise SystemExit(1)
    print(f"✓ verify passed ({len(files)} language-claims)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stamp = sub.add_parser("stamp", help="extract + timestamp each language's claim")
    p_stamp.add_argument("bundle", nargs="?", default=None, help="one bundle, or omit for all")
    p_stamp.set_defaults(run=lambda a: cmd_stamp(a.bundle))

    p_verify = sub.add_parser("verify", help="verify every language-claim")
    p_verify.add_argument("--lenient", dest="strict", action="store_false", help="allow missing proofs (PR mode)")
    p_verify.set_defaults(run=lambda a: cmd_verify(a.strict), strict=True)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
