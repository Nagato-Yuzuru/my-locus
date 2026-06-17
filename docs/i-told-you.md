# "I told you ☝️🤓" 手册

这个栏目记录我对新闻 / 商业决策 / 技术方向的**公开判断**,发布即盖密码学时间戳(防"事后诸葛亮"),事后照实自评——错的也记。本文是给自己看的操作手册:**每种文件的元信息、不可变性边界、完整工作流、命令、看板、验证方法**。

文章本身的通用 frontmatter(title/date/draft/tags 等)见 [`frontmatter.md`](./frontmatter.md);本文只讲这个栏目特有的东西。

---

## 1. 一条 take 的文件结构

```
content/i-told-you/<slug>/
├── index.md           # EN 源文：frontmatter（含 claim）+ 正文 + {{< claim >}} 占位。作者写。
├── index.zh-cn.md     # 中文版：独立 frontmatter（含自己的 claim）+ 正文。作者本地写/译。
├── claim.en.txt       # 从 index.md 的 claim 字段抽出的【冻结文本】= 被盖章的字节。★ CI 生成，勿手改。
├── claim.zh-cn.txt    # 从 index.zh-cn.md 的 claim 抽出。★ CI 生成。
├── proof.en.tsr       # claim.en.txt 的 RFC 3161 时间戳令牌。★ CI 生成。
└── proof.zh-cn.tsr    # claim.zh-cn.txt 的令牌。★ CI 生成。
```

**关键观念:中英不是严格镜像,而是各自独立的判断**(只是常常恰好一致)。所以每个语言**各有一份 claim、各自盖章**。`claim.<lang>.txt` / `proof.<lang>.tsr` 都由 CI 产出,不要手动改动或提交。

新建:`just told-you-new <slug>`,走 `archetypes/i-told-you.md`。

---

## 2. Frontmatter 字段(本栏目特有)

| 字段 | 类型 | 可变? | 消费者 | 说明 |
|---|---|---|---|---|
| `claim` | string(YAML 块标量 `\|`) | **❌ 冻结** | `timestamp_take.py`(抽取盖章)、`claim` shortcode(展示) | **★ 被盖章的承诺**。一句方向性判断。首次发布时 CI 抽取+盖章后**不可再改**——要修正/更新想法请**开新一集**。每语言各一份、各自盖章。 |
| `verdict` | enum | ✅ 可变 | 看板、verdict pill | `pending` / `correct` / `wrong` / `partial`。事后自评。用 `just verdict` 改;**不碰证明**。 |
| `stance` | string | ✅ | (速览/未来可展示) | 一句话方向性结论的速记。非盖章对象。 |
| `series` | list[string] | ✅ | Blowfish series | 系列名(=同一件事的"下一集")。自由格式,无白名单。 |
| `series_order` | int | ✅ | Blowfish series | 第几集 + 决定系列框里的 "Part N" 标签与排序。**不写则编号空白**。 |
| `featured` | bool | ✅ | 看板 spotlight | `true` 时进 `/i-told-you/` 顶部"★ Featured"展示框。 |
| `tags` | list[string] | ✅ | CI 校验 | 必须 ⊂ `data/tags.yaml`(同 posts)。本栏目常用 `commentary` / `business`。 |

> 已删除的旧字段:`claim_lang`(已改为"每语言独立盖章",不再需要"哪个是权威")。

`title` / `date` / `description` / `draft` 等通用字段语义同 posts。

### claim 写法示例

```yaml
claim: |
  我认为这笔收购是战略错误：整合成本远超分发收益，
  而且监管会把它拖过真正有意义的窗口期。
```

---

## 3. 不可变性 / 信任模型(最重要)

- **密码学上不可改的只有一样:`claim`(逐语言)。** 流程:`claim` 字段 →(yq 抽取)→ `claim.<lang>.txt` →(SHA-256 + freeTSA)→ `proof.<lang>.tsr`。
- `proof.<lang>.tsr` 证明:**这段 claim 文字在 T 时刻已存在、且此后未改**(改一字节 `openssl ts -verify` 即失败)。
- **被证明的时刻 T = TSA 盖章时刻**(在 CI 流程里 ≈ 合并/发布时),不是 `date` 字段。
- **其它全部可变**:`verdict`、`stance`、正文、`title`、译文…… 改这些都不影响证明。这正是"事后能打分却不破坏证明"的根基。
- **改已发布的 claim → CI 红**(verify 不过)。要更新观点:**开新一集**(同 `series`,新 `series_order`),老 claim 永远冻结。
- 自评(verdict)是"软证据":靠的是 **claim 公开+盖章 × 现实结果公开**,任何人都能核对你标得诚不诚实;改动留痕在 git 历史。要让"评价"也成硬证据,就把复盘写成**新一集**(它自带时间戳)。

---

## 4. 工作流 SOP(发布 → 回顾)

1. **建** `just told-you-new <slug>`。
2. **写**(`index.md`):
   - `claim:` 填那句要被锁定的判断;
   - `stance` / `series`(+`series_order`)/ `tags` / `verdict: "pending"` / `featured`;
   - 正文里放 `{{< claim >}}`(框出现在此处)+ "Why I think so" 分析;
   - 完成后 `draft: false`。
3. **译**:本地(LLM 整篇译)生成 `index.zh-cn.md`,**它有自己的 `claim`**(独立、会单独盖章)。
4. **发**:开 PR(不能直推 main)。`autofix.ci` 在 PR 上跑 `just timestamp`:逐语言抽取 claim → `claim.<lang>.txt` → 盖 `proof.<lang>.tsr` → 推回 PR。**在 PR diff 里亲眼检查证明**,再合并。
5. **合并** → `deploy.yml` 严格校验 + 部署。上线即带证明。
6. **回顾**(reality 揭晓后):
   - 轻量:`just verdict <slug> correct|wrong|partial`(看板/徽章自动更新);
   - 严谨:开**新一集**写复盘(自带时间戳)。

---

## 5. 命令参考(Justfile)

| 命令 | 作用 |
|---|---|
| `just told-you-new <slug>` | 从 archetype 脚手架一条 take |
| `just timestamp [bundle]` | 逐语言抽取 claim + 缺则盖章(幂等)。不带参数=全部。**通常 CI 跑,本地一般不用** |
| `just verdict <slug> <state>` | 改 verdict(yq 结构化改 frontmatter,中英两个文件一起);`state` ∈ pending/correct/wrong/partial |
| `just verify-told-you` | 逐语言校验:claim 未变 + proof 验证通过(strict) |
| `just test` | 跑 `tests/`(pytest) |
| `just typecheck` | `deno check` 校验 `assets/js/*.ts` |
| `just check` | validate tags + tags-sync + verify-told-you + typecheck + build |

---

## 6. 看板 `/i-told-you/`(由 `layouts/i-told-you/list.html` 驱动)

| 部件 | 数据来源 |
|---|---|
| 胜率环(conic-gradient,中心镂空) | `correct / (correct + wrong)`;0 已揭晓时显示"—" |
| ✓/✗ 计数(细线 SVG 图标) | verdict 计数 |
| 筛选 chip(correct/wrong/partial/pending/All) | 点击同时筛网格+列表(原生 JS,`assets/js/i-told-you.ts`) |
| 每条一格的网格 | 每条 take 一格,按日期排,按 verdict 上色 |
| 列表 + 分页 | 每页 10 条;`data-perpage` 可调 |
| ★ Featured 展示框 | `featured: true` 的 take(纯服务端) |

样式:`assets/css/i-told-you.css`(纯 CSS + 自定义属性,跟随深/浅主题)。交互 JS 写成 TS、Hugo `js.Build` 转译、压缩+指纹+SRI,只在本 section 加载(见 `layouts/partials/extend-head-uncached.html`)。

文章页的 `{{< claim >}}` 框:读 `.Params.claim` 渲染 + verdict pill + 该语言自己的 `proof.<lang>.tsr` 链接。

---

## 7. 怎么验证一条 claim(任何人都能做)

下载某条 take 的 `claim.<lang>.txt` 和 `proof.<lang>.tsr`,然后:

```bash
openssl ts -verify -data claim.en.txt -in proof.en.tsr \
  -CAfile freetsa-cacert.pem -untrusted freetsa-tsa.crt
# 期望输出：Verification: OK
```

CA 链在仓库 `static/tsa/`,线上 [`/tsa/freetsa-cacert.pem`](/tsa/freetsa-cacert.pem)、[`/tsa/freetsa-tsa.crt`](/tsa/freetsa-tsa.crt)。栏目落地页底部也有"如何验证"。

---

## 8. CI/CD

| Workflow | 触发 | 干什么 | 权限 |
|---|---|---|---|
| `.github/workflows/autofix.yml`(名为 `autofix.ci`) | `pull_request` | `just timestamp`(逐语言抽取+盖章)→ `autofix-ci/action` 把 `claim.<lang>.txt`/`proof.<lang>.tsr` 推回 PR 分支 | `contents: read`(由 autofix.ci App 回写,不用 token) |
| `.github/workflows/deploy.yml` | push/PR | 加了一步 `timestamp_take.py verify`:**main 严格**(每语言必须有 proof)、**PR 宽松**(autofix 待补);然后构建 + 部署(GitHub Pages, OIDC) | `contents: read` |

**纪律**:take 走 PR 发布;直推 main 的未盖章 take 会被 main 的严格校验拦下(CI 红)。

---

## 9. 工具链(本栏目用到、均 mise 固定)

| 工具 | 用途 |
|---|---|
| `yq` | 结构化读写 frontmatter(抽取 `claim`、`just verdict` 改字段)——**不用正则改 md** |
| `deno` | `deno check` 给浏览器 TS(`assets/js/`)做类型检查(esbuild 只转译不查类型) |
| `openssl` | RFC 3161 query / verify / reply |
| Hugo Pipes(`js.Build`/`minify`/`fingerprint`) | 打包 TS、压缩 CSS、出指纹 + SRI;**不引第三方打包器** |
| freeTSA.org | RFC 3161 时间戳机构(免费) |

---

## 10. 校验规则

| 规则 | 实施位置 | 违规结果 |
|---|---|---|
| 已发布的 `claim` 不得改动 | `verify-told-you`(CI) | 红:`claim field changed since it was stamped` |
| `proof.<lang>.tsr` 必须能验 `claim.<lang>.txt` | `verify-told-you` / `openssl ts -verify` | 红:`RFC 3161 verify failed` |
| main 上每条 take 每语言都要有 proof | `deploy.yml`(strict) | 红:`not stamped` |
| `tags` ⊂ `data/tags.yaml` | `validate_tags.py` | CI 失败 |
| `claim` 字段必须存在 | `timestamp_take.py`(yq 抽取) | `TakeError: missing claim front-matter field` |

---

## 相关文件

- `archetypes/i-told-you.md` — 新建 take 模板
- `layouts/shortcodes/claim.html` — claim 框(读 `.Params.claim`)
- `layouts/i-told-you/list.html` — 看板
- `layouts/partials/extend-head-uncached.html` — 按 section 加载 CSS/JS
- `assets/css/i-told-you.css` / `assets/js/i-told-you.ts` — 看板样式 + 交互
- `scripts/timestamp_take.py` — 抽取 + 盖章 + 校验
- `static/tsa/` — freeTSA CA 链
- `.github/workflows/autofix.yml` / `deploy.yml` — CI
- [`frontmatter.md`](./frontmatter.md) — 通用 frontmatter 字段
