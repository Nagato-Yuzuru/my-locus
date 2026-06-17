# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "msgspec>=0.21.1",
#     "pyyaml>=6.0.3",
# ]
# ///
"""
Validate that every tag used in a post is defined in data/tags.yaml.

Modes:
  uv run scripts/validate_tags.py              # CI: strict, any issue exits 1
  uv run scripts/validate_tags.py --pre-commit  # local: staged=error, others=warning
"""

import argparse
import logging
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

import msgspec
import yaml

logger = logging.getLogger("validate_tags")

TAGS_FILE = "data/tags.yaml"
CONTENT_DIR = "content"

# validate_tags only consumes tag ids; extra keys (en/zh-cn) are ignored.
class TagEntry(TypedDict):
    id: str


class TagRegistry(msgspec.Struct):
    tags: list[TagEntry]


class FrontmatterError(Exception):
    """A post's YAML front matter is present but could not be parsed."""


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def load_allowed_tags(path: Path) -> set[str]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        registry = msgspec.convert(raw, TagRegistry)
    except msgspec.ValidationError as e:
        logger.error("Invalid tag registry %s: %s", path, e)
        raise SystemExit(1) from e
    return {entry["id"] for entry in registry.tags}


def post_tags(path: Path) -> list[str]:
    """Return the `tags` list from a post's front matter.

    Returns [] when the file has no front matter. Raises FrontmatterError when
    the front matter is present but malformed, or when `tags` is not a list.
    """
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return []
    try:
        fm = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise FrontmatterError(f"malformed front matter: {e}") from e
    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        raise FrontmatterError(f"`tags` must be a list, got {type(tags).__name__}")
    return tags


def get_staged_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.splitlines())


def check_files(
    md_files: Iterable[Path], allowed: set[str]
) -> list[tuple[str, list[str]]]:
    """Return [(path, [problem, ...]), ...] for every file with problems."""
    problems: list[tuple[str, list[str]]] = []
    for path in sorted(md_files):
        try:
            tags = post_tags(path)
        except FrontmatterError as e:
            problems.append((str(path), [str(e)]))
            continue
        unknown = [f"unknown tag: '{t}'" for t in tags if t not in allowed]
        if unknown:
            problems.append((str(path), unknown))
    return problems


def report(header: str, problems: list[tuple[str, list[str]]], level: int) -> None:
    logger.log(level, header)
    logger.log(level, "=" * 60)
    for path, lines in problems:
        logger.log(level, "  %s", path)
        for line in lines:
            logger.log(level, "    %s", line)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="Pre-commit mode: staged=error, others=warning",
    )
    args = parser.parse_args()

    allowed = load_allowed_tags(Path(TAGS_FILE))
    md_files = sorted(Path(CONTENT_DIR).rglob("*.md"))
    problems = check_files(md_files, allowed)

    if not problems:
        logger.info("✓ Tag check passed (%s files)", len(md_files))
        return

    fix_hint = f"Fix: define unknown tags in {TAGS_FILE} before using them."

    if not args.pre_commit:
        report("TAG VALIDATION FAILED", problems, logging.ERROR)
        logger.error(fix_hint)
        sys.exit(1)

    staged = get_staged_files()
    errors = [p for p in problems if p[0] in staged]
    warnings = [p for p in problems if p[0] not in staged]

    if warnings:
        report(
            "⚠ Tag warnings (files not in this commit; non-blocking)",
            warnings,
            logging.WARNING,
        )
    if errors:
        report("✗ Tag check failed (files in this commit)", errors, logging.ERROR)
        logger.error(fix_hint)
        sys.exit(1)


if __name__ == "__main__":
    main()
