# LLMwiki Ingest Kit

把**视频 / 文章 / PDF / 播客**丢进去，自动转写、建页、挂双链，长进你自己的 Obsidian 库。

这套东西的重点不是"能摄入"，是**摄入之后不让库烂掉**——里面带了三道质量门，
是我在自己 1000 多页的库上踩出来的。

---

## 它解决什么问题

自动摄入很容易，一天能往库里灌几百页。难的是半年以后：

我自己那个库体检时的真实数字 —— 1045 页里 **373 页没有任何入链（35%）**，
另有 **213 页是同一个来源存了两遍**（同一个 URL 进了两个文件夹）。
清完之后剩 832 页，孤儿率降到 19%。

所以这套 kit 的一半是采集，另一半是**拦截**。

---

## 安装（一个包，装一次）

**下载** → [最新 Release](https://github.com/yikong111/llmwiki-ingest-kit/releases/latest) 里的 `llmwiki-ingest-kit.zip`

解压后是一个完整插件，整个目录放进你的插件目录即可：

- **Claude Code**：放进 `~/.claude/plugins/`（识别 `.claude-plugin/plugin.json`）
- **Codex**：放进你的插件目录（识别 `.codex-plugin/plugin.json`）
- **只想要 skill 也行**：把 `skills/` 下的四个目录直接丢进 agent 的 skills 目录

然后两步：

1. 在你的库根目录放一个 `AGENTS.md`，写清库结构（concepts / entities / sources / summaries / syntheses）。
2. 对 agent 说：**「把这个链接整合进库」+ 链接**。路由会自己判断走哪条线。

长视频想单独转写：`python scripts/extract_transcript.py <文件或链接>`

## 组成

```
.claude-plugin/plugin.json   # Claude Code 插件清单
.codex-plugin/plugin.json    # Codex 插件清单
skills/
  llmwiki-ingest/                    # 主流程：建页、双链、索引、日志、三道质量门
  llmwiki-ingest-router/             # 来源路由：判断该走哪条线
  llmwiki-douyin-ingest/             # 抖音/短视频前置采集
  llmwiki-wechat-channels-ingest/    # 微信视频号
scripts/
  extract_transcript.py       # 本地转写
  douyin_ssr_bridge.py        # 抖音页面数据桥接
  wechat_channels_adapter.py  # 视频号适配
tests/
```

## 三道质量门（这套东西真正的价值）

- **门一 · 低价值直接跳过**：「原帖已被作者删除」「转发」「抽奖答题」「纯行情播报」「正文只剩一个链接」→ 不建页，只在日志记一行「已跳过 + 原因」。
- **门二 · 判重按来源身份**：按 URL / 视频 ID / 帖子 ID / 文件 SHA-256 查重，命中就**升级旧页**。禁止靠加 ID 后缀、加序号绕开判重——我那 213 页重复就是这么来的。
- **门三 · 一页至少一条入链**：建页前先想清楚它从哪一页被链进来。连不上任何已有页就**不建**，原料留在 `raw/` 即可。这是 35% 孤儿页的直接对策。

另外两条配套约束：

- **合成配额**：每 5 次摄入至少产出 1 页跨源合成，否则在日志里记「合成欠账 +1」。不然库会变成剪报堆。
- **季度淘汰**：零入链且 90 天未更新的摘要页 → 移到 `archive/`。库要能减。

## 设计上的几个固执己见

- `raw/` **只读**。原始转写稿进去之后一个字都不改，溯源时它是唯一的底。
- 摄入的是**「某人怎么读这本书」**，不是「这本书就是这么说的」。书评层必须在页顶标明来源。
- 讲者发散出去的部分（宇宙、能量、玄学……）**明确分层**，不当作已确认知识沉淀。
- 每次摄入都往 `log.md` 追加一条：来源、动了哪些页、有什么疑点。

## 边界与免责

- 只处理**你有权保存的公开内容**。付费内容、私密内容、有 DRM 保护的，工具会停下不处理。
- 不读取、不导出、不打包任何 cookie / 登录态 / 会话数据。仓库的 `.gitignore` 已经把这些路径全挡掉了。
- 使用者自行遵守各平台服务条款与当地法律。本项目按现状提供，不承担使用后果。

## 关于 issue

欢迎提。作者会看，但响应时间不保证。

MIT License。
