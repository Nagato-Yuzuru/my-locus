# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic-ai[anthropic]", "markdown-it-py", "mdformat", "pyyaml"]
# ///
"""
将 Hugo markdown 文章通过 LLM 翻译为目标语言。

- PydanticAI：支持多模型提供商（通过 TRANSLATE_MODEL 切换，默认 anthropic:claude-opus-4-7）
- markdown-it-py：正确解析块级结构，取代纯正则；Hugo shortcode 非标准语法仍用定向 regex
- mdformat：规范化翻译后的 Markdown 格式

用法：
  TARGET_LANG=zh-cn ANTHROPIC_API_KEY=sk-... uv run scripts/translate_posts.py
  TARGET_LANG=en    FORCE_RETRANSLATE=true   uv run scripts/translate_posts.py
  TRANSLATE_MODEL=openai:gpt-4o              uv run scripts/translate_posts.py
"""

import glob
import json
import os
import re
import sys

import mdformat
import yaml
from markdown_it import MarkdownIt
from pydantic_ai import Agent

CONTENT_DIR = "content/posts"
TARGET_LANG = os.environ.get("TARGET_LANG", "zh-cn")
FORCE_RETRANSLATE = os.environ.get("FORCE_RETRANSLATE", "false").lower() == "true"
TRANSLATE_MODEL = os.environ.get("TRANSLATE_MODEL", "anthropic:claude-opus-4-7")

LANG_NAMES = {
    "zh-cn": "简体中文 (Simplified Chinese)",
    "en": "English",
    "ja": "日本語 (Japanese)",
}

# 结构化输出模式下格式由协议保证，保留语义规则即可
SYSTEM_PROMPT = """\
你是专业的技术文档翻译员，目标语言：{target_lang_name}。

接收一个字符串数组（Markdown 文本片段），返回等长的翻译结果数组。

严格规则：
1. 输出数组长度必须与输入完全一致，不能合并或拆分元素。
2. 保留所有 Markdown 语法符号（##、**、-、[text](url) 等）。
3. 不翻译 URL（链接文字可以翻译，href 不翻译）。
"""

# ──────────────────────────────────────────────
# PydanticAI Agent（模块级单例，TARGET_LANG 固定于进程启动时）
# ──────────────────────────────────────────────

_target_lang_name = LANG_NAMES.get(TARGET_LANG, TARGET_LANG)

_agent = Agent(
    TRANSLATE_MODEL,
    output_type=list[str],
    system_prompt=SYSTEM_PROMPT.format(target_lang_name=_target_lang_name),
)


# ──────────────────────────────────────────────
# Frontmatter 解析与重建
# ──────────────────────────────────────────────

def split_frontmatter(content: str) -> tuple[str | None, str]:
    """分离 frontmatter 和 body，返回 (fm_raw, body)。"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, content


def translate_fm_fields(fm: dict) -> dict:
    """翻译 frontmatter 中的 title、description、series，其余字段原样返回。"""
    to_translate = {}
    if fm.get("title"):
        to_translate["title"] = fm["title"]
    if fm.get("description"):
        to_translate["description"] = fm["description"]
    # series is a list; translate each element as a display name
    series_list = fm.get("series") or []
    if series_list:
        for i, s in enumerate(series_list):
            to_translate[f"series_{i}"] = s
    if not to_translate:
        return fm

    keys = list(to_translate.keys())
    values = [str(to_translate[k]) for k in keys]
    translated_values = _call_translate_api(values)

    result = dict(fm)
    translated_map = dict(zip(keys, translated_values))

    for k, v in translated_map.items():
        if not k.startswith("series_"):
            result[k] = v

    # Reassemble series list from series_0, series_1, ...
    if series_list:
        result["series"] = [
            translated_map.get(f"series_{i}", series_list[i])
            for i in range(len(series_list))
        ]

    return result


def rebuild_frontmatter(fm: dict) -> str:
    return "---\n" + yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False) + "---\n"


# ──────────────────────────────────────────────
# Body 结构化分段
# ──────────────────────────────────────────────

_md = MarkdownIt()

# Hugo shortcode 和内联元素：非标准 Markdown，markdown-it-py 无法识别，保留定向 regex
_SHORTCODE_RE = re.compile(r"\{\{<[\s\S]*?>>\}\}|\{\{%[\s\S]*?%\}\}")
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

_OPAQUE_PLACEHOLDER = "\x00OPAQUE_{idx}\x00"
_OPAQUE_RE = re.compile(r"\x00OPAQUE_(\d+)\x00")


def _extract_opaques(body: str) -> tuple[str, list[str]]:
    """
    提取 body 中不可翻译区域并替换为占位符。

    Phase 1: markdown-it-py 识别块级 opaque（围栏代码块、缩进代码、HTML 块）
    Phase 2: 定向 regex 处理 Hugo shortcode、HTML 注释、内联代码
    """
    opaques: list[str] = []

    # Phase 1: 块级解析
    tokens = _md.parse(body)
    lines = body.splitlines(keepends=True)

    opaque_ranges: list[tuple[int, int]] = []
    for token in tokens:
        if token.map and token.type in ("fence", "code_block", "html_block"):
            opaque_ranges.append((token.map[0], token.map[1]))
    opaque_ranges.sort()

    parts: list[str] = []
    prev = 0
    for start, end in opaque_ranges:
        if prev < start:
            parts.append("".join(lines[prev:start]))
        block = "".join(lines[start:end])
        idx = len(opaques)
        opaques.append(block)
        # 保留末尾换行以维持段落结构
        parts.append(_OPAQUE_PLACEHOLDER.format(idx=idx) + "\n")
        prev = end
    if prev < len(lines):
        parts.append("".join(lines[prev:]))

    processed = "".join(parts)

    # Phase 2: 定向 regex
    def replacer(m: re.Match) -> str:
        idx = len(opaques)
        opaques.append(m.group(0))
        return _OPAQUE_PLACEHOLDER.format(idx=idx)

    processed = _SHORTCODE_RE.sub(replacer, processed)
    processed = _HTML_COMMENT_RE.sub(replacer, processed)
    processed = _INLINE_CODE_RE.sub(replacer, processed)

    return processed, opaques


def _split_into_segments(body: str) -> list[str]:
    """按空行分段，保留空行分隔符。"""
    parts = re.split(r"(\n{2,})", body)
    return [p for p in parts if p]


def _restore_opaques(segments: list[str], opaques: list[str]) -> list[str]:
    def restore(m: re.Match) -> str:
        return opaques[int(m.group(1))]
    return [_OPAQUE_RE.sub(restore, seg) for seg in segments]


# ──────────────────────────────────────────────
# LLM 翻译调用（PydanticAI 结构化输出）
# ──────────────────────────────────────────────

def _call_translate_api(texts: list[str]) -> list[str]:
    """通过 PydanticAI Agent 批量翻译，返回等长翻译结果数组。"""
    if not texts:
        return []

    user_content = json.dumps(texts, ensure_ascii=False)
    try:
        result = _agent.run_sync(user_content)
        translated = result.output
        if isinstance(translated, list) and len(translated) == len(texts):
            return translated
        print(f"  WARNING：输出长度不匹配（{len(translated)} != {len(texts)}），保留原文")
    except Exception as e:
        print(f"  WARNING：API 调用失败，保留原文。错误：{e}")
    return texts


def translate_body(body: str) -> str:
    """结构化翻译 body：opaque 区域原样保留，其余批量翻译，mdformat 规范化输出。"""
    processed, opaques = _extract_opaques(body)
    segments = _split_into_segments(processed)

    translatable_indices = []
    translatable_texts = []
    for i, seg in enumerate(segments):
        stripped = seg.strip()
        if stripped and not _OPAQUE_RE.fullmatch(stripped):
            translatable_indices.append(i)
            translatable_texts.append(stripped)

    if translatable_texts:
        translated_texts = _call_translate_api(translatable_texts)
        for idx, translated in zip(translatable_indices, translated_texts):
            orig = segments[idx]
            leading = orig[: len(orig) - len(orig.lstrip("\n"))]
            trailing = orig[len(orig.rstrip("\n")):]
            segments[idx] = leading + translated + trailing

    restored = _restore_opaques(segments, opaques)
    result = "".join(restored)

    # mdformat 规范化（对标准 Markdown 语法规范化；Hugo shortcode 作为不透明内联，通常原样保留）
    try:
        result = mdformat.text(result)
    except Exception as e:
        print(f"  WARNING: mdformat 规范化失败，使用原始输出：{e}")

    return result


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def translate_file(source_path: str, target_path: str) -> bool:
    with open(source_path, encoding="utf-8") as f:
        content = f.read()

    fm_raw, body = split_frontmatter(content)

    if fm_raw is None:
        print(f"  SKIP（无 frontmatter）：{source_path}")
        return False

    fm = yaml.safe_load(fm_raw) or {}
    if not fm.get("translate", True):
        print(f"  SKIP（translate: false）：{source_path}")
        return False

    print(f"  翻译中：{source_path} → {target_path}")

    translated_fm = translate_fm_fields(fm)
    new_frontmatter = rebuild_frontmatter(translated_fm)
    translated_body = translate_body(body)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(new_frontmatter + translated_body)

    return True


def main():
    # 早期 API key 检查（PydanticAI 运行时也会校验，这里提供更友好的报错）
    model_prefix = TRANSLATE_MODEL.split(":")[0]
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google-gla": "GEMINI_API_KEY",
        "google-vertex": "GOOGLE_CLOUD_PROJECT",
    }
    required_key = key_map.get(model_prefix)
    if required_key and not os.environ.get(required_key):
        print(f"错误：使用 {model_prefix} 模型需要设置 {required_key} 环境变量。")
        sys.exit(1)

    if TARGET_LANG == "en":
        source_filename = "index.zh-cn.md"
        target_filename = "index.md"
    else:
        source_filename = "index.md"
        target_filename = f"index.{TARGET_LANG}.md"

    post_dirs = sorted(glob.glob(f"{CONTENT_DIR}/*/"))
    translated_count = 0

    for post_dir in post_dirs:
        source_path = os.path.join(post_dir, source_filename)
        target_path = os.path.join(post_dir, target_filename)

        if not os.path.exists(source_path):
            continue

        if os.path.exists(target_path) and not FORCE_RETRANSLATE:
            print(f"  EXISTS（跳过）：{target_path}")
            continue

        if translate_file(source_path, target_path):
            translated_count += 1

    print(f"\n完成。共翻译 {translated_count} 篇文章。")


if __name__ == "__main__":
    main()
