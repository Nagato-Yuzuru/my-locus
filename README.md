# my-locus

Source for [blog.yuzuru.me](https://blog.yuzuru.me). Hugo + Blowfish, auto-deployed to GitHub Pages on push to `main`.

This README is a personal ops cheatsheet, not a tutorial.

## Bootstrap

```bash
mise install                          # installs go / hugo-extended / just / uv
export ANTHROPIC_API_KEY=sk-...       # only needed for local translation
```

## Commands

| Command | Purpose |
|---|---|
| `just new <slug>` | Scaffold `content/posts/<slug>/index.md` (leaf bundle, draft) |
| `just serve` | Local preview, drafts on, live reload |
| `just validate` | Check all post tags against `data/tags.yaml` allowlist |
| `just build` | Production build (same step CI runs) |
| `just check` | `validate` + `build`; run before committing |
| `just translate [lang]` | Translate to target language (default `zh-cn`); skips existing |
| `just retranslate [lang]` | Force-overwrite translations |
| `just clean` | Remove `public/` and `resources/_gen/` |

## Daily flow

1. `just new my-slug` → write
2. `just serve` to iterate
3. `just check` before committing
4. `just translate zh-cn` for the Chinese version
5. `git commit && git push` → CI builds and OIDC-deploys

## Notes to self

- **Tag allowlist**: every tag must be listed in `data/tags.yaml`; CI rejects unknown tags
- **Full frontmatter reference**: see [`docs/frontmatter.md`](docs/frontmatter.md)
- **Theme**: Blowfish is pulled as a Hugo Module (`go.mod` + `config/_default/module.toml`), not a submodule
- **Toolchain versions** live in `mise.toml`; CI reads the same file via `jdx/mise-action@v2`
- **No CI secrets**: deployment uses OIDC; translation runs only locally

## Layout

```
content/posts/<slug>/index.md         # source (EN)
content/posts/<slug>/index.zh-cn.md   # translation
config/_default/*.toml                # split Hugo config
data/tags.yaml                        # tag allowlist
scripts/validate_tags.py              # PEP 723 script, uv run
scripts/translate_posts.py            # same, PydanticAI + Anthropic
.github/workflows/deploy.yml          # CI: mise + hugo + Pages
archetypes/default.md                 # new-post template
```
