---
name: llmwiki-ingest
description: Ingest a source into the your Obsidian vault (<VAULT>) wiki/. Use when the user is in that vault and says ingest, 摄入, 入库 raw, or update the <VAULT> second brain from a file/URL. Do not use in the any unrelated repo, and do not treat generic 整合/沉淀 as ingest.
---

# LLMwiki Ingest

Follow the repository `AGENTS.md` first. This skill is a focused workflow for the Tianyuan second-brain vault.

## Core Rules

- Use Chinese for wiki pages. Preserve English technical terms when useful.
- Treat `raw/` as read-only. Never modify, move, rename, or delete files under `raw/`.
- Maintain `wiki/` pages, `wiki/index.md`, and `wiki/log.md`.
- Use Obsidian double links: `[[页面名]]`.
- Do not merge, delete, or rename important pages without explicit user approval.
- For <你自己的核心心法页> and trading-rule content, preserve the user's original wording when precision matters.

## Routing

If the source is a Douyin link, share text, or short-video file, run `llmwiki-douyin-ingest` first and ingest the resulting `raw/video/` Markdown. Do not transcribe inside this skill.

If the source is a local book under `raw/books/` and the user has not confirmed 炼化/保存, run `llmwiki-book-refinery` first. This skill writes wiki pages only after that handoff is confirmed.

Before writing, decide the content type:

- Knowledge source: place or read original material from `raw/`, then create or update `wiki/sources/`.
- Concept/theory/method: update or create `wiki/concepts/`.
- Person, organization, software, project, book: update or create `wiki/entities/`.
- Cross-source topic: update or create `wiki/summaries/`.
- User-requested analysis or durable answer: update or create `wiki/syntheses/`.
- Task to execute: use `notes/10-Action/` only when the user explicitly wants task tracking.
- Immature thought: use `notes/20-Card/闪念卡/` only when the user explicitly wants a card.

## 摄入质量门（2026-09-19 加，依据当天全库体检）

体检结果：全库 1045 页，**373 页（35%）没有任何入链**；来源摘要 747 页里存在明显低价值条目
（「原帖已被作者删除」「转发」「答题抢红包」「【异动】…跌幅」等）；并存在同一来源被摄入两次、
第二次靠加 ID 后缀新建的情况（例：`2018-06-13_原帖已被作者删除` 与 `..._108796592`）。
以下三道门用来止血。

### 门一 · 低价值来源直接跳过，不建页

标题或正文命中以下任一，**不建 wiki 页**，只在 log 里记一行「已跳过 + 原因」：

- 「原帖已被作者删除」「转发」且无正文
- 抽奖 / 答题 / 抢红包 / 活动推广
- 纯行情播报（「【异动】…涨跌幅…现价…」）
- 正文只剩一个链接、没有可提取观点
- 全文短于约 200 字且无独有事实

### 门二 · 判重按来源身份，不按文件名

建页前先按**来源唯一身份**查重：URL、视频 ID（如抖音 aweme_id）、帖子 ID、文件 SHA-256。

- 命中 → **升级原页**（补充新增内容 + 更新 `updated`），**禁止新建**。
- **禁止用加 ID 后缀、加序号、加日期的方式绕开判重**——现有的 `_108796592` 这类就是这么来的。
- 确实是不同内容但同名 → 页名加**语义区分**（不是加数字），并在两页之间互相链接。

### 门三 · 一页至少一条入链，否则不建

新建任何页之前，先想清楚它**从哪一页被链进来**。

- 连不上任何已有页 → 说明它和这个库没关系，**不建**，原始材料留在 `raw/` 即可。
- 只能连上「索引」不算数，必须是内容页。
- 这条是 35% 孤儿页的直接对策。

### 合成配额 · 别只搬运不产出

`syntheses` 目前 4 页、`summaries` 2 页，合计占全库 0.6%——库在快速变成剪报堆。

- **每 5 次 ingest，至少产出 1 页 `syntheses/` 或 `summaries/`**（跨源、带自己的判断）。
- 没产出就在 `wiki/log.md` 当次记录里写一行 `合成欠账 +1`，下次优先还。

### 季度淘汰 · 库要能减

每季度跑一次：**零入链 且 90 天未更新** 的来源摘要页 → 移到 `archive/`（不删原始材料）。
减下来的页数记进 log。库只增不减，就会变成今天这样 71% 是摘要。

## Ingest Steps

1. Read the relevant source completely. For long PDFs or books, first map structure, then ingest in manageable sections.
2. Create or update exactly one source page in `wiki/sources/` for each source file.
3. Extract important concepts and entities. Prefer updating existing pages after checking `wiki/index.md` and relevant folders.
4. Keep a single ingest focused. New plus updated pages should usually stay around 5-15 pages.
5. Add backlinks among source, concepts, entities, summaries, and syntheses.
6. Update `wiki/index.md`.
7. Append an entry to `wiki/log.md` using the repository log format.
8. Report what was ingested, which pages changed, and any notable links or contradictions.

## Required Frontmatter

Every wiki page must include frontmatter matching the repository convention:

- source: `title`, `type: source`, `source_date`, `source_type`, optional `url`, `tags`, `summary`
- concept: `title`, `type: concept`, `created`, `updated`, `tags`, `sources`, `summary`
- entity: `title`, `type: entity`, `entity_type`, `created`, `updated`, `tags`, `sources`, `summary`
- synthesis: `title`, `type: synthesis`, `created`, `tags`, `sources`, `summary`

Keep `summary` within about 50 Chinese characters.

## PDF Handling

- Do not dump a whole PDF as a flat Markdown translation.
- Preserve the source PDF in `raw/` when the user provides it there.
- The wiki output should be structured knowledge: key claims, methods, definitions, limitations, user-relevant takeaways, and links.
- If the PDF is too long, first produce a chapter/section map, then ingest by section.

## 书籍炼化 handoff 与 source 页质量

收到 `llmwiki-book-refinery` 的 B/C 保存 handoff 时，仍先执行本 Skill 的确认与 source_hash/锚点复核；本 Skill 是唯一写入 `wiki/`、`wiki/index.md` 和 `wiki/log.md` 的流程。

- handoff 内的临时决策包服务安全和路由，不是用户报告正文。正式书籍 source 页必须以**用户可读书籍精华报告**为主体，系统评级、hash 和处理状态置于最后的“系统信息”。
- 书籍 source 页默认依次含：一句话结论、真正给我的东西、核心精华、可直接实践的方法、值得亲自阅读的原文、关键原文、常见认识纠正、证据边界、最小实践方案、阅读路线、知识库关系、个人理解记录、系统信息。
- C 级不拆 concept，但不代表报告可以变浅：仍必须有 5—10 条可用精华、原书存在的练习步骤及其时长/频率（未明确则如实标记）、至少 10 条独立短引文、3—8 个精读入口、证据边界和最小实践方案。
- 每条关键原文和精读入口必须有章节、可重新解析的 locator、简短说明和绑定 source_hash 的 `tianyuan-book://` 深链接。链接无可靠精确阅读器时，明确写“打开原书＋搜索唯一短引文”，不得承诺精确跳句。
- 不得补造原书未提供的训练参数、疗效或证据；不得把作者主张、谨慎推导与 AI 延伸混写。疾病、减重、社恐、延缓衰老或成功等广泛结论必须保留证据边界，不能替代正规诊疗。

## Safety

- Ask before writing outside `wiki/`, `notes/10-Action`, `notes/20-Card`, or `notes/30-Time`.
- Never modify PARA notes under `notes/0-Inbox`, `notes/1-Projects`, `notes/2-Areas`, `notes/3-Resources`, or `notes/4-Archives` unless the user explicitly requests it.
- When uncertain whether a page already exists or should be merged, ask the user instead of guessing.
