# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""
从 data/tags.yaml 幂等地生成 content/tags/<id>/ 下的多语言 _index 文件。

- 已存在的文件不覆盖（保留人工添加的描述等内容）
- 使用 --force 强制覆盖

用法：
  uv run scripts/sync_tags.py
  uv run scripts/sync_tags.py --force
"""

import argparse
import sys
from pathlib import Path

import yaml

TAGS_FILE = Path("data/tags.yaml")
TAGS_DIR = Path("content/tags")

LANG_CONFIG = {
    "en": {"filename": "_index.md", "date_field": "date"},
    "zh-cn": {"filename": "_index.zh-cn.md", "date_field": "date"},
}

PLACEHOLDER_DATE = "2020-01-01T00:00:00+00:00"


def load_tags(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    tags = data.get("tags", [])
    missing_id = [t for t in tags if not isinstance(t, dict) or "id" not in t]
    if missing_id:
        print(f"ERROR: entries missing 'id' field: {missing_id}")
        sys.exit(1)
    return tags


def index_content(title: str) -> str:
    fm = {
        "title": title,
        "date": PLACEHOLDER_DATE,
    }
    return "---\n" + yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False) + "---\n"


def sync_tag(tag: dict, force: bool) -> list[str]:
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


def list_tags(tags: list[dict]) -> None:
    for t in tags:
        print(f"  {t['id']:<20}  en={t.get('en', '?'):<22}  zh-cn={t.get('zh-cn', '?')}")


def main():
    parser = argparse.ArgumentParser(description="Sync tag content pages from data/tags.yaml")
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
            print(f"  WRITE  {path}")
        total_written += len(written)

    skipped = sum(
        sum(1 for cfg in LANG_CONFIG.values() if (TAGS_DIR / tag["id"] / cfg["filename"]).exists())
        for tag in tags
    ) - total_written

    print(f"\n完成。写入 {total_written} 个文件，跳过 {skipped} 个已存在文件。")
    if args.force and total_written == 0:
        print("（所有文件均已为最新）")


if __name__ == "__main__":
    main()
