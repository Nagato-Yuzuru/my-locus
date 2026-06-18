# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "msgspec>=0.21.1",
#     "pyyaml>=6.0.3",
# ]
# ///
"""
Idempotently generate the multilingual _index files under content/tags/<id>/
from data/tags.yaml.

- Existing files are left untouched (preserves hand-written descriptions, etc.).
- Use --force to overwrite.

Usage:
  uv run scripts/sync_tags.py
  uv run scripts/sync_tags.py --force
"""

import argparse
import logging
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

import yaml
from msgspec import ValidationError, convert

BlogTag = TypedDict("BlogTag", {"id": str, "en": str, "zh-cn": str})

logger = logging.getLogger("sync_tags")

TAGS_FILE = Path("data/tags.yaml")
TAGS_DIR = Path("content/tags")

LANG_CONFIG = {
    "en": {"filename": "_index.md", "date_field": "date"},
    "zh-cn": {"filename": "_index.zh-cn.md", "date_field": "date"},
}

PLACEHOLDER_DATE = "2020-01-01T00:00:00+00:00"


def load_tags(path: Path) -> list[BlogTag]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    try:
        return convert(data.get("tags", []), list[BlogTag])
    except ValidationError as e:
        logger.error("Invalid tag entry in %s: %s", path, e)
        raise SystemExit(1) from e


def index_content(title: str) -> str:
    fm = {
        "title": title,
        "date": PLACEHOLDER_DATE,
    }
    return (
        "---\n"
        + yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
        + "---\n"
    )


def sync_tag(tag: BlogTag, force: bool) -> list[str]:
    tag_id = tag["id"]
    tag_dir = TAGS_DIR / tag_id
    tag_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for lang, cfg in LANG_CONFIG.items():
        label = tag.get(lang)
        if not label:
            continue
        target = tag_dir / cfg["filename"]
        if target.exists() and not force:
            continue
        target.write_text(index_content(label), encoding="utf-8")
        written.append(str(target))
    return written


def list_tags(tags: Iterable[BlogTag]) -> None:
    print(
        "\n".join(
            f"  {t['id']:<20}  en={t.get('en', '?'):<22}  zh-cn={t.get('zh-cn', '?')}"
            for t in tags
        ),
        file=sys.stdout,
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    parser = argparse.ArgumentParser(
        description="Sync tag content pages from data/tags.yaml",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--list", action="store_true", help="Print all tags and exit")
    args = parser.parse_args()

    tags = load_tags(TAGS_FILE)

    if args.list:
        list_tags(tags)
        return

    total_written = 0

    for tag in tags:
        written = sync_tag(tag, force=args.force)
        for path in written:
            logger.info("  WRITE  %s", path)
        total_written += len(written)

    skipped = (
        sum(
            sum(
                1
                for cfg in LANG_CONFIG.values()
                if (TAGS_DIR / tag["id"] / cfg["filename"]).exists()
            )
            for tag in tags
        )
        - total_written
    )

    logger.info(
        "\nDone. Wrote %s file(s), skipped %s existing.",
        total_written,
        skipped,
    )
    if args.force and total_written == 0:
        logger.info("(everything already up to date)")


if __name__ == "__main__":
    main()
