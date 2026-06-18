import logging
import sys
from pathlib import Path

import pytest
import validate_tags as vt


# --- helpers ---------------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _tags_file(tmp_path: Path, *ids: str) -> Path:
    """A data/tags.yaml registry defining `ids`, each with extra en/zh-cn labels."""
    entries = "".join(
        f"  - id: {tag}\n    en: {tag.title()}\n    zh-cn: {tag}\n" for tag in ids
    )
    return _write(tmp_path / "tags.yaml", f"tags:\n{entries}")


def _post(path: Path, frontmatter: str | None, body: str = "\nbody\n") -> Path:
    """Write a markdown post.

    `frontmatter` is the YAML between the `---` fences; pass None for a file with
    no front matter at all.
    """
    text = body if frontmatter is None else f"---\n{frontmatter}\n---{body}"
    return _write(path, text)


# --- load_allowed_tags -----------------------------------------------------


def test_load_allowed_tags_returns_the_set_of_ids(tmp_path):
    path = _tags_file(tmp_path, "python", "go", "rust")
    assert vt.load_allowed_tags(path) == {"python", "go", "rust"}


def test_load_allowed_tags_ignores_label_columns(tmp_path):
    # en/zh-cn live in the registry but must not leak into the allowed set.
    path = _write(
        tmp_path / "tags.yaml",
        "tags:\n  - id: web-dev\n    en: Web Dev\n    zh-cn: 网页开发\n",
    )
    assert vt.load_allowed_tags(path) == {"web-dev"}


def test_load_allowed_tags_empty_registry_is_empty_set(tmp_path):
    path = _write(tmp_path / "tags.yaml", "tags: []\n")
    assert vt.load_allowed_tags(path) == set()


def test_load_allowed_tags_entry_without_id_exits(tmp_path):
    path = _write(tmp_path / "tags.yaml", "tags:\n  - en: Python\n    zh-cn: Python\n")
    with pytest.raises(SystemExit) as exc:
        vt.load_allowed_tags(path)
    assert exc.value.code == 1


def test_load_allowed_tags_missing_tags_key_exits(tmp_path):
    path = _write(tmp_path / "tags.yaml", "other: 1\n")
    with pytest.raises(SystemExit) as exc:
        vt.load_allowed_tags(path)
    assert exc.value.code == 1


# --- post_tags -------------------------------------------------------------


def test_post_tags_no_frontmatter_returns_empty(tmp_path):
    post = _post(tmp_path / "index.md", None, body="plain body, no fences\n")
    assert vt.post_tags(post) == []


def test_post_tags_reads_block_list(tmp_path):
    post = _post(tmp_path / "index.md", "title: hi\ntags:\n  - python\n  - go")
    assert vt.post_tags(post) == ["python", "go"]


def test_post_tags_reads_inline_list(tmp_path):
    post = _post(tmp_path / "index.md", 'tags: ["python", "web-dev"]')
    assert vt.post_tags(post) == ["python", "web-dev"]


def test_post_tags_frontmatter_without_tags_key_returns_empty(tmp_path):
    post = _post(tmp_path / "index.md", "title: hi\ndraft: false")
    assert vt.post_tags(post) == []


def test_post_tags_non_list_tags_raises(tmp_path):
    post = _post(tmp_path / "index.md", "tags: python")
    with pytest.raises(vt.FrontmatterError, match="must be a list"):
        vt.post_tags(post)


def test_post_tags_malformed_yaml_raises(tmp_path):
    # Unterminated flow sequence -> yaml.safe_load raises -> FrontmatterError.
    post = _post(tmp_path / "index.md", "tags: [python, go")
    with pytest.raises(vt.FrontmatterError, match="malformed front matter"):
        vt.post_tags(post)


# --- check_files -----------------------------------------------------------


def test_check_files_clean_when_all_tags_known(tmp_path):
    a = _post(tmp_path / "a.md", "tags:\n  - python")
    b = _post(tmp_path / "b.md", "tags:\n  - go")
    assert vt.check_files([a, b], {"python", "go"}) == []


def test_check_files_reports_each_unknown_tag(tmp_path):
    post = _post(tmp_path / "a.md", "tags:\n  - python\n  - mystery\n  - ghost")
    problems = vt.check_files([post], {"python"})
    assert problems == [
        (str(post), ["unknown tag: 'mystery'", "unknown tag: 'ghost'"])
    ]


def test_check_files_reports_frontmatter_error(tmp_path):
    post = _post(tmp_path / "a.md", "tags: python")  # not a list
    problems = vt.check_files([post], {"python"})
    assert len(problems) == 1
    path, lines = problems[0]
    assert path == str(post)
    assert "must be a list" in lines[0]


def test_check_files_skips_posts_without_tags(tmp_path):
    post = _post(tmp_path / "a.md", None, body="no frontmatter\n")
    assert vt.check_files([post], set()) == []


def test_check_files_output_is_sorted_by_path(tmp_path):
    # Pass out of order; problems must come back sorted by path.
    z = _post(tmp_path / "z.md", "tags:\n  - bad")
    a = _post(tmp_path / "a.md", "tags:\n  - bad")
    problems = vt.check_files([z, a], set())
    assert [path for path, _ in problems] == [str(a), str(z)]


# --- get_staged_files ------------------------------------------------------


def test_get_staged_files_splits_git_output_into_a_set(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["git", "diff", "--cached"]
        return type("R", (), {"stdout": "content/a.md\ncontent/b.md\n"})()

    monkeypatch.setattr(vt.subprocess, "run", fake_run)
    assert vt.get_staged_files() == {"content/a.md", "content/b.md"}


def test_get_staged_files_empty_output_is_empty_set(monkeypatch):
    monkeypatch.setattr(
        vt.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": ""})()
    )
    assert vt.get_staged_files() == set()


# --- main (strict vs --pre-commit) -----------------------------------------


def _project(tmp_path, monkeypatch, frontmatter: str, *allowed_ids: str) -> Path:
    """Point main() at a throwaway project; return the single post's path."""
    tags = _tags_file(tmp_path, *allowed_ids)
    content = tmp_path / "content"
    post = _post(content / "post" / "index.md", frontmatter)
    monkeypatch.setattr(vt, "TAGS_FILE", str(tags))
    monkeypatch.setattr(vt, "CONTENT_DIR", str(content))
    return post


def test_main_strict_passes_for_known_tags(tmp_path, monkeypatch, caplog):
    _project(tmp_path, monkeypatch, "tags:\n  - python", "python")
    monkeypatch.setattr(sys, "argv", ["validate_tags.py"])
    with caplog.at_level(logging.INFO, logger="validate_tags"):
        vt.main()  # must not raise
    assert "Tag check passed" in caplog.text


def test_main_strict_exits_on_unknown_tag(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, "tags:\n  - mystery", "python")
    monkeypatch.setattr(sys, "argv", ["validate_tags.py"])
    with pytest.raises(SystemExit) as exc:
        vt.main()
    assert exc.value.code == 1


def test_main_precommit_warns_but_passes_for_unstaged_post(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, "tags:\n  - mystery", "python")
    monkeypatch.setattr(vt, "get_staged_files", set)
    monkeypatch.setattr(sys, "argv", ["validate_tags.py", "--pre-commit"])
    vt.main()  # problem is in an unstaged file -> warning only, no exit


def test_main_precommit_exits_when_staged_post_has_unknown_tag(tmp_path, monkeypatch):
    post = _project(tmp_path, monkeypatch, "tags:\n  - mystery", "python")
    monkeypatch.setattr(vt, "get_staged_files", lambda: {str(post)})
    monkeypatch.setattr(sys, "argv", ["validate_tags.py", "--pre-commit"])
    with pytest.raises(SystemExit) as exc:
        vt.main()
    assert exc.value.code == 1
