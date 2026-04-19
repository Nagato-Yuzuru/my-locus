# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""
校验所有文章的 tag 必须在 data/tags.yaml 中定义。
发现未知 tag 时以 exit code 1 退出并输出违规列表。

本地运行：uv run scripts/validate_tags.py
"""

import glob
import re
import sys

import yaml

TAGS_FILE = "data/tags.yaml"
CONTENT_DIR = "content"


def load_allowed_tags(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    return set(data.get("tags", []))


def extract_frontmatter(filepath):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def main():
    allowed = load_allowed_tags(TAGS_FILE)
    md_files = glob.glob(f"{CONTENT_DIR}/**/*.md", recursive=True)
    violations = []

    for filepath in sorted(md_files):
        fm = extract_frontmatter(filepath)
        post_tags = fm.get("tags", [])
        if not isinstance(post_tags, list):
            continue
        unknown = [t for t in post_tags if t not in allowed]
        if unknown:
            violations.append((filepath, unknown))

    if violations:
        print("TAG VALIDATION FAILED")
        print("=" * 60)
        print(f"允许的 tag 定义在：{TAGS_FILE}")
        print()
        for filepath, bad_tags in violations:
            print(f"  {filepath}")
            for tag in bad_tags:
                print(f"    未知 TAG：'{tag}'")
        print()
        print(f"修复方法：先在 {TAGS_FILE} 中添加新 tag，再在文章中使用。")
        sys.exit(1)
    else:
        print(f"Tag 校验通过。检查了 {len(md_files)} 个文件。")
        sys.exit(0)


if __name__ == "__main__":
    main()
