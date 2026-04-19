# Frontmatter 字段参考

本文档列出本博客所有可用的 frontmatter 字段及其语义，覆盖 **Hugo 原生**、**Blowfish 主题**、**本项目自定义** 三类。

字段语法：YAML（`---` 包裹）。默认值来源于 `config/_default/params.toml` 的 `[article]` 块，frontmatter 同名字段会覆盖之。

---

## 文件位置约定

```
content/posts/<slug>/
├── index.md          # 源文（EN，默认内容语言）
├── index.zh-cn.md    # 翻译（由 scripts/translate_posts.py 生成）
├── feature.jpg       # 可选：自动成为头图/OG image/列表缩略图
└── <其他资源>        # 图片、附件等 Page Resources，随文章走
```

新建用 `just new <slug>`，走 `archetypes/default.md` 模板，会预填 `title` / `date` / `lastmod` / `draft:true` / `translate:true` / 空 `tags:[]` / 空 `description:""`。

---

## 1. Hugo 原生字段

### 1.1 必填 / 强烈建议

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | string | 文章标题。archetype 会按目录 slug 自动生成（hyphen → 空格、Title Case） |
| `date` | datetime | 发布时间，用于排序、列表分组（`groupByYear = true`） |
| `description` | string | meta description + 首页/列表卡片预览文字；**翻译脚本会单独翻译此字段** |
| `tags` | list\[string\] | 分类维度。**必须全部在 `data/tags.yaml` 白名单内**，否则 CI 挡下 |

### 1.2 发布控制

| 字段 | 类型 | 说明 |
|---|---|---|
| `draft` | bool | `true` 不进生产构建；`just serve` 会带 `-D` 显示草稿 |
| `publishDate` | datetime | 未来日期在 `buildFuture = false` 下不公开 |
| `expiryDate` | datetime | 到期后下架 |
| `lastmod` | datetime | 最后修改时间。`enableGitInfo = true` 默认从 git 取；frontmatter 覆盖 git |

### 1.3 内容/URL

| 字段 | 类型 | 说明 |
|---|---|---|
| `summary` | string | 覆盖自动摘要（否则截 `summaryLength = 30` 个词） |
| `slug` | string | 覆盖最后一段 URL（默认取目录名） |
| `aliases` | list\[string\] | 旧路径重定向，保留链接不断 |
| `weight` | int | 手动排序权重（小 → 前，0 表示用 date） |
| `keywords` | list\[string\] | SEO；也可用于相关文章索引（见 §4） |

### 1.4 示例

```yaml
---
title: "Understanding Tokio's Runtime"
date: 2026-04-19T10:00:00+08:00
lastmod: 2026-04-20T14:30:00+08:00
draft: false
description: "A deep dive into how Tokio schedules tasks across threads."
tags: [rust, systems, deep-dive]
keywords: [tokio, async, green-thread, work-stealing]
slug: tokio-runtime
---
```

---

## 2. Blowfish 主题字段

这些都是**每篇覆盖**项 —— 不写就用 `params.toml [article]` 里的默认值。当前默认全部为 `true`，相关限制 3 条。

### 2.1 显示开关

| 字段 | 默认 | 作用 |
|---|---|---|
| `showDate` | true | 显示发布日期 |
| `showDateUpdated` | true | 显示 "Updated" 时间（走 `lastmod`） |
| `showAuthor` | true | 显示作者卡片 |
| `showReadingTime` | true | 估算阅读时长 |
| `showWordCount` | true | 字数；CJK 启用（`hasCJKLanguage = true`）按字符算 |
| `showTableOfContents` | true | 右侧 TOC |
| `showTaxonomies` | true | 文末显示 tags |
| `showRelatedContent` | true | 显示"相关文章"块（§4） |
| `relatedContentLimit` | 3 | 相关文章条数 |
| `showEdit` | true | "Edit this page" 链接到 GitHub |
| `sharingLinks` | `[x-twitter, bluesky, reddit, email]` | 分享按钮；设 `false` 关掉整块 |
| `showBreadcrumbs` | （默认 false） | 面包屑，扁平结构下意义不大 |
| `showHeadingAnchors` | true | 标题锚点 |
| `showPagination` | true | 同 section 上/下一篇 |
| `showComments` | false | 评论（未接入） |

### 2.2 布局 / 头图

| 字段 | 取值 | 说明 |
|---|---|---|
| `heroStyle` | `"basic"` / `"big"` / `"background"` / `"thumbAndBackground"` | 头图排版风格 |
| `layoutBackgroundBlur` | bool | 配合 `background` 系列样式的高斯模糊 |
| `layoutBackgroundHeaderSpace` | bool | 头部与导航之间留空 |

### 2.3 特性图 / OG image（不是 frontmatter，是文件名约定）

同目录放文件，Blowfish 自动识别（优先级从高到低）：

| 命名模式 | 用途 |
|---|---|
| `feature*` | 文章头图 + OG image |
| `cover*` | 同上（备用名） |
| `thumbnail*` | 列表页缩略图（若未配置则 fallback 到 feature） |

支持扩展名：`jpg`、`jpeg`、`png`、`webp`、`gif`。

### 2.4 示例（覆盖默认）

```yaml
---
title: "短随笔：喝茶"
date: 2026-04-19
tags: [notes]
heroStyle: basic
showTableOfContents: false
showReadingTime: false
sharingLinks: false
---
```

---

## 3. 本项目自定义字段

| 字段 | 类型 | 默认 | 消费者 | 作用 |
|---|---|---|---|---|
| `translate` | bool | true | `scripts/translate_posts.py` | `false` 时跳过自动翻译（适合纯中文或纯英文、不打算双语的文章） |

> 扩展自定义字段时，记得在本文件登记；不要放语义不明的 `custom:` 对象。

---

## 4. 相关文章（自动推荐）

Blowfish 的 `related.html` partial 只有一行：

```go-template
{{ $related := .Site.RegularPages.Related . | first .Site.Params.article.relatedContentLimit }}
```

即**完全走 Hugo 原生**相似度算法。当前配置（`config/_default/hugo.toml`）：

```toml
[related]
threshold = 20             # 0–100，得分低于此值不展示
toLower   = false

[[related.indices]]
name = "tags"
weight = 100               # 主维度：tag 重合度

[[related.indices]]
name = "date"
weight = 10                # 次维度：时间接近度
```

### 行为要点

- **不跨语言**：EN 只推 EN，zh-cn 只推 zh-cn
- **草稿不参与**（`draft: true` 既不当候选也不被推）
- **空结果不渲染**：相关为空时整块 `<h2>Related</h2>` 不出现
- **按语言查询 pool**：`.Site.RegularPages` 是当前语言的页面集合

### 想精细控制：加 keywords 索引

`tags` 白名单有 24 个词，粒度偏粗。想让"同讲 tokio"的文章比"同是 rust"的文章更强关联：

1. 在 `hugo.toml` 的 `[related]` 下加：

   ```toml
   [[related.indices]]
   name = "keywords"
   weight = 80
   ```

2. 每篇 frontmatter 写 3–5 个 keywords（自由，不走白名单）

### 想手动指定相关文章

Hugo 无原生字段。做法：
1. frontmatter 加 `related: ["/posts/foo/", "/posts/bar/"]`
2. 在 `layouts/partials/related.html` 写一个 override，先读这个字段再 fallback 到自动算法

（当前未实现，需要时再说。）

---

## 5. 完整示例

```yaml
---
# —— 必填
title: "Understanding Tokio's Runtime"
date: 2026-04-19T10:00:00+08:00
description: "A deep dive into how Tokio schedules tasks across threads."
tags: [rust, systems, deep-dive]

# —— 发布控制
draft: false
lastmod: 2026-04-20T14:30:00+08:00

# —— SEO / 相关推荐
keywords: [tokio, async, green-thread, work-stealing]
slug: tokio-runtime

# —— 主题覆盖（用默认就不写）
heroStyle: big
showTableOfContents: true

# —— 本项目自定义
translate: true
---

正文开始……
```

---

## 6. 校验规则

| 规则 | 实施位置 | 违规结果 |
|---|---|---|
| `tags` 必须 ⊂ `data/tags.yaml` 的 `tags:` 列表 | `scripts/validate_tags.py`（CI + `just validate`） | CI 失败，列出违规文件 |
| `tags` 命名：小写、连字符分隔（`web-dev` 而非 `WebDev`） | 约定（未自动校验） | 人工 review |
| `translate` 缺省视为 `true` | `translate_posts.py` 读取时 `fm.get("translate", True)` | 无默认会翻 |
| frontmatter 解析失败 | `validate_tags.py` 静默跳过；Hugo 构建失败 | 构建报错 |

---

## 相关文件

- `archetypes/default.md` — 新建文章模板
- `config/_default/params.toml` — Blowfish article 字段默认值
- `config/_default/hugo.toml` — 相关文章算法配置
- `data/tags.yaml` — tag 白名单
- `scripts/validate_tags.py` — tag 校验
- `scripts/translate_posts.py` — 自动翻译
