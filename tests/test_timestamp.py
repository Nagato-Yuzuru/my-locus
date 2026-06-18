from pathlib import Path

import pytest
import timestamp_take as tt


def _take(tmp_path: Path, suffix: str = "", claim: str = "My call.") -> Path:
    b = tmp_path / "take"
    b.mkdir(exist_ok=True)
    (b / f"index{suffix}.md").write_text(
        f'---\ntitle: x\nverdict: "pending"\nclaim: |\n  {claim}\n---\n\nbody\n',
        encoding="utf-8",
    )
    return b


def test_lang_of():
    assert tt.lang_of(Path("x/index.md")) == "en"
    assert tt.lang_of(Path("x/index.zh-cn.md")) == "zh-cn"


def test_frozen_bytes_appends_single_newline():
    assert tt.frozen_bytes("hi") == b"hi\n"


def test_extract_claim_reads_frontmatter_field(tmp_path):
    b = _take(tmp_path, "", "I think X will win.")
    assert tt.extract_claim(b / "index.md") == "I think X will win."


def test_extract_claim_missing_field_raises(tmp_path):
    b = tmp_path / "take"
    b.mkdir()
    (b / "index.md").write_text("---\ntitle: x\n---\nbody\n", encoding="utf-8")
    with pytest.raises(tt.TakeError):
        tt.extract_claim(b / "index.md")


# --- tamper detection against a committed RFC 3161 fixture (via verify_crypto) ---
FIX = Path(__file__).resolve().parent / "fixtures"


def test_pristine_fixture_verifies():
    tt.verify_crypto(FIX / "claim.txt", FIX / "proof.tsr")  # must not raise


def test_tampered_claim_fails_verification(tmp_path):
    bad = tmp_path / "claim.txt"
    bad.write_bytes((FIX / "claim.txt").read_bytes() + b"tampered")
    with pytest.raises(tt.TakeError):
        tt.verify_crypto(bad, FIX / "proof.tsr")


# --- verify modes (strict vs lenient) over a bundle with no proof yet ---
def test_verify_strict_fails_when_unstamped(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "SECTION_DIR", tmp_path)
    _take(tmp_path)
    with pytest.raises(SystemExit):
        tt.cmd_verify(strict=True)


def test_verify_lenient_passes_when_unstamped(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "SECTION_DIR", tmp_path)
    _take(tmp_path)
    tt.cmd_verify(strict=False)  # must not raise
