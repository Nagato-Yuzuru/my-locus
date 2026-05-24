# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml"]
# ///
"""
校验所有文章的 tag 必须在 data/tags.yaml 中定义。

模式：
  uv run scripts/validate_tags.py              # CI：全量严格，任何问题都 exit 1
  uv run scripts/validate_tags.py --pre-commit  # 本地：staged 文件问题 exit 1，其余 warning
"""

import argparse
import glob
import re
import subprocess
import sys

import yaml

TAGS_FILE = "data/tags.yaml"
CONTENT_DIR = "content"


def load_allowed_tags(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    entries = data.get("tags", [])
    ids = set()
    for entry in entries:
        if isinstance(entry, str):
            ids.add(entry)
        elif isinstance(entry, dict) and "id" in entry:
            ids.add(entry["id"])
    return ids


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


def get_staged_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def check_files(md_files: list[str], allowed: set[str]) -> list[tuple[str, list[str]]]:
    violations = []
    for filepath in sorted(md_files):
        fm = extract_frontmatter(filepath)
        post_tags = fm.get("tags", [])
        if not isinstance(post_tags, list):
            continue
        unknown = [t for t in post_tags if t not in allowed]
        if unknown:
            violations.append((filepath, unknown))
    return violations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-commit", action="store_true", help="Pre-commit mode: staged=error, others=warning")
    args = parser.parse_args()

    allowed = load_allowed_tags(TAGS_FILE)
    md_files = glob.glob(f"{CONTENT_DIR}/**/*.md", recursive=True)
    violations = check_files(md_files, allowed)

    if not violations:
        print(f"✓ Tag 校验通过（{len(md_files)} 个文件）")
        sys.exit(0)

    if not args.pre_commit:
        # CI 模式：全量严格
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

    # Pre-commit 模式：staged=error，其余=warning
    staged = get_staged_files()
    errors = [(f, tags) for f, tags in violations if f in staged]
    warnings = [(f, tags) for f, tags in violations if f not in staged]

    if warnings:
        print("⚠ Tag 警告（非本次提交的文件，不阻断）")
        print("-" * 60)
        for filepath, bad_tags in warnings:
            print(f"  {filepath}")
            for tag in bad_tags:
                print(f"    未知 TAG：'{tag}'")
        print()

    if errors:
        print("✗ Tag 校验失败（本次提交的文件）")
        print("=" * 60)
        for filepath, bad_tags in errors:
            print(f"  {filepath}")
            for tag in bad_tags:
                print(f"    未知 TAG：'{tag}'")
        print()
        print(f"修复方法：先在 {TAGS_FILE} 中添加新 tag，再在文章中使用。")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
