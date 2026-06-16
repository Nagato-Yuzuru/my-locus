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
