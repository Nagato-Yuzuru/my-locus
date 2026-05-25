# Hugo Blog — common commands
# Toolchain: see mise.toml

set shell := ["bash", "-euo", "pipefail", "-c"]

# Default: list available commands
default:
    @just --list

# First-time setup: install prek hooks
setup:
    prek install

# Local development server (with drafts, live reload)
serve:
    hugo server -D --disableFastRender

# Production build
build:
    hugo --minify

# Create new post (usage: just new my-post-slug)
new slug:
    hugo new posts/{{ slug }}/index.md

# Validate all post tags are defined in data/tags.yaml
validate:
    uv run scripts/validate_tags.py

# List all available tags (id + labels)
tags:
    uv run scripts/sync_tags.py --list

# Generate content/tags/<id>/ pages from data/tags.yaml (idempotent)
tags-sync:
    uv run scripts/sync_tags.py

# Force-regenerate all tag pages (overwrites existing)
tags-sync-force:
    uv run scripts/sync_tags.py --force

# Translate posts to target language (default: zh-cn)
# Usage: just translate zh-cn | just translate en
translate lang="zh-cn":
    TARGET_LANG={{ lang }} uv run scripts/translate_posts.py

# Force retranslate (overwrite existing translations)
# Usage: just retranslate zh-cn
retranslate lang="zh-cn":
    TARGET_LANG={{ lang }} FORCE_RETRANSLATE=true uv run scripts/translate_posts.py

# Clean build artifacts
clean:
    rm -rf public/ resources/_gen/

# Full check: validate tags + sync tag pages + production build
check: validate tags-sync build
    @echo "✓ All checks passed"
