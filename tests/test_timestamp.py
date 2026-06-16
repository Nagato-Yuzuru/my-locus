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
