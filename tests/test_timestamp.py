import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import timestamp_take as tt  # noqa: E402

CLAIM_BLOCK = "{{< claim >}}\n%s\n{{< /claim >}}\n"


def _frontmatter() -> str:
    return "---\ntitle: x\nclaim_lang: en\n---\n"


def _make_take(tmp_path, claim="My call.") -> Path:
    b = tmp_path / "take"
    b.mkdir()
    (b / "index.md").write_text(_frontmatter() + (CLAIM_BLOCK % claim), encoding="utf-8")
    return b


def test_extract_claim_returns_inner_text():
    md = "pre\n" + (CLAIM_BLOCK % "Hello world.") + "post"
    assert tt.extract_claim(md) == "Hello world."


def test_extract_claim_none_when_absent():
    assert tt.extract_claim("nothing here") is None


import pytest  # noqa: E402


def test_freeze_then_guard_passes(tmp_path):
    b = _make_take(tmp_path)
    tt.freeze_claim(b, force=False)
    assert (b / "claim.txt").read_text(encoding="utf-8") == "My call.\n"
    tt.freeze_guard(b)  # must not raise


def test_freeze_guard_detects_visible_edit(tmp_path):
    b = _make_take(tmp_path)
    tt.freeze_claim(b, force=False)
    (b / "index.md").write_text(_frontmatter() + (CLAIM_BLOCK % "DIFFERENT"), encoding="utf-8")
    with pytest.raises(SystemExit):
        tt.freeze_guard(b)


def test_refreeze_changed_claim_refused(tmp_path):
    b = _make_take(tmp_path)
    tt.freeze_claim(b, force=False)
    (b / "index.md").write_text(_frontmatter() + (CLAIM_BLOCK % "CHANGED"), encoding="utf-8")
    with pytest.raises(SystemExit):
        tt.freeze_claim(b, force=False)


import subprocess as _sp  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
CA = "static/tsa/freetsa-cacert.pem"
TSA = "static/tsa/freetsa-tsa.crt"


def _verify(data: Path) -> int:
    return _sp.run(
        ["openssl", "ts", "-verify", "-data", str(data),
         "-in", str(FIX / "proof.tsr"), "-CAfile", CA, "-untrusted", TSA],
        capture_output=True,
    ).returncode


def test_pristine_fixture_verifies():
    assert _verify(FIX / "claim.txt") == 0


def test_tampered_claim_fails_verification(tmp_path):
    bad = tmp_path / "claim.txt"
    bad.write_bytes((FIX / "claim.txt").read_bytes() + b"tampered")
    assert _verify(bad) != 0


import argparse as _ap  # noqa: E402


def test_verify_strict_fails_when_proof_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "SECTION_DIR", tmp_path)
    b = _make_take(tmp_path)
    tt.freeze_claim(b, force=False)  # claim.txt but NO proof.tsr
    with pytest.raises(SystemExit):
        tt.cmd_verify(_ap.Namespace(strict=True))


def test_verify_lenient_passes_when_proof_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "SECTION_DIR", tmp_path)
    b = _make_take(tmp_path)
    tt.freeze_claim(b, force=False)
    tt.cmd_verify(_ap.Namespace(strict=False))  # must not raise


import set_verdict as sv  # noqa: E402


def test_set_verdict_replaces_only_that_line(tmp_path):
    md = tmp_path / "index.md"
    md.write_text(
        '---\ntitle: x\nstance: "I said verdict: stays in prose"\nverdict: "pending"\n---\nbody verdict: untouched\n',
        encoding="utf-8",
    )
    sv.set_verdict(md, "correct")
    text = md.read_text(encoding="utf-8")
    assert 'verdict: "correct"' in text
    assert "stays in prose" in text           # frontmatter prose untouched
    assert "body verdict: untouched" in text  # body untouched
