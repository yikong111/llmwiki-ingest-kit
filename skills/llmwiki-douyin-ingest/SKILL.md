---
name: llmwiki-douyin-ingest
description: Prepare Douyin videos, share links, local short-video files, and transcripts for the <VAULT> Obsidian LLMwiki. Use when the user asks to 抓取抖音, 解析抖音视频, 转写抖音, 把抖音/短视频整理进 wiki, or convert Douyin to Markdown. Front-stage only: write raw/video Markdown, then hand off to llmwiki-ingest. Do not use in the any unrelated repo.
---

# LLMwiki Douyin Ingest

This skill is a Douyin front-stage collector for the <VAULT> vault. `llmwiki-ingest` owns durable wiki pages. This skill only turns public Douyin videos or local short videos into clean `raw/video/` Markdown.

## Fit With this vault

Write prepared Markdown into **`raw/video/`** (matches `AGENTS.md` + `extract_transcript.py`). Then hand off to `llmwiki-ingest`. Do not write `wiki/` here.

After creating the raw Markdown artifact, hand off to **`llmwiki-ingest`** (this vault). Do not invent a parallel wiki schema. `llmwiki-ingest` owns `wiki/sources`, `wiki/concepts`, `wiki/entities`, `wiki/index.md`, and `wiki/log.md`. This vault does not use `wiki/topics`.

## Core Workflow

When the user gives a Douyin URL, copied share text, a `v.douyin.com` short link, or a local MP4/MOV file:

1. Identify whether the input is a public URL, copied share text, or local media file.
2. Resolve short links and capture the canonical URL when possible.
3. Extract metadata: title/description, author, publish time, hashtags, music/audio title, duration, stats if visible, video ID, and original URL.
4. Obtain spoken content:
   - Prefer platform captions or subtitle text if available.
   - Otherwise extract audio and transcribe with local ASR such as Whisper.
   - If media extraction fails, preserve metadata and visible text and clearly mark transcript as unavailable.
5. Create a single clean Markdown source artifact.
6. Ask or proceed to hand the artifact to `llmwiki-ingest`, depending on the user request.

## Extraction Backends

Choose the least invasive path that works.

### URL and Media

Prefer (updated 2026-08-10 — 借鉴 content-capture SSR，不接 Obsidian 插件写库):

1. **Vault SSR bridge first for Douyin links**: `python tools/douyin_ssr_bridge.py "<链接或分享文案>" --output raw/video`.
   - 读 `iesdouyin.com/share/...` 页内 `_ROUTER_DATA` / `RENDER_DATA`（免 cookie 的公开 SSR 路径）。
   - 视频：临时下载 → 调用仓库 **未修改** 的 `extract_transcript.py` 本地文件模式 → `raw/video/`。
   - 图文 note：`desc` 作文案写入 raw，**不**把视频/配图堆进 vault 附件夹。
   - 验证用：`--meta-only`；只下不转：`--download-only`。
2. Optional full local backend (lyxdream `obsidian-content-capture-backend`) **as a download/ASR engine only**:
   - 可 CLI/`POST /api/video/extract` 拿 `transcript.txt` + `meta.json`。
   - **禁止**默认启用配套 Obsidian 插件往 `Douyin/` 写笔记；拿到文案后仍写成 vault 规范 `raw/video/*.md`，再 hand-off `llmwiki-ingest`。
3. `yt-dlp` for non-Douyin platforms, or Douyin when it currently works.
4. Playwright with a user-provided minimal Douyin cookie file when SSR/yt-dlp fail at media. Inject only Douyin-domain cookies; never print signed media URLs into durable notes.
5. Locally installed `tools/Douyin_TikTok_Download_API` / `tools/douyin_backend_probe.py` when user-maintained.
6. User-provided local video file → `extract_transcript.py` 本地文件模式（历史主路径，风控时常兜底）。
7. Manual paste of description/transcript as a fallback.

Treat Douyin-specific parsers as brittle. Douyin may require fresh cookies, anti-bot parameters, or browser context. Do not promise full automation.

### Trial checklist (本机验证 SSR / 桥接)

**2026-08-10 本机已通过主链**（Python 3.12.10 + ffmpeg 9.0 + CUDA Whisper small）：

- `tools/douyin_ssr_bridge.py "https://v.douyin.com/6So0S8xiElI/" --meta-only` → `aweme_id` + `has_download_url: true`
- 同链 `--download-only` → 约 20.8 MB MP4
- `extract_transcript.py` 本地文件模式 + `--model small` → 约 11 分钟视频 GPU 转写成功（~61s）
- 细节见 `notes/10-Action/抖音SSR桥接试跑.md`

未测：图文 note 链、故意失败降级、正式 `llmwiki-ingest` 入库。

新环境或回归时按序：

1. **解释器**: `python --version` 为真实 3.10+（非 Store 空壳）；`import requests` 成功。
2. **ffmpeg/ffprobe**: 在 PATH 中。
3. **仅解析**: `python tools/douyin_ssr_bridge.py "<短链>" --meta-only`
4. **图文**（若有 note 链）: 不加 `--meta-only` → `platform_desc`
5. **视频全链**: `python tools/douyin_ssr_bridge.py "<短链>" --output raw/video --model medium`
6. **失败降级**: 本地 MP4 / metadata-only / `asr-failed`
7. **入库**: `llmwiki-ingest`；禁止并行写插件 `Douyin/` 夹

**Windows CUDA 备忘**：若报 `cublas64_12.dll is not found`，把 `nvidia/cublas|cuda_runtime|cudnn` 的 DLL 复制进 `site-packages/ctranslate2/`（与 `extract_transcript.py` 头注释一致）。

On Windows, `yt-dlp --cookies-from-browser chrome` can fail even with user approval if Chrome cookies are protected by DPAPI in a way the agent process cannot decrypt. If that happens, stop trying browser-profile extraction and ask for a manually exported Netscape-format cookie file limited to Douyin domains, or a local video file.

If `yt-dlp --cookies <file>` still returns "Fresh cookies" after accepting the cookie file, this may be a Douyin extractor limitation rather than a bad cookie file. In that case, use the Playwright fallback with the same cookies: visit the canonical video page, capture visible metadata and media responses, then download only the selected media response needed for transcription.

### Verified Playwright Media Fallback (2026-07-10)

Use this path for a public Douyin link when `yt-dlp` reports `Fresh cookies` but the project already contains a user-authorized Netscape-format `cookies.txt` limited to Douyin domains:

1. Launch Chrome through the locally installed Python Playwright with only those Douyin cookies. Try headless first; if the title is a verification-interstitial page, reopen visibly so the user can complete the platform's one-time verification. Do not solve or bypass CAPTCHA programmatically.
2. Open the canonical video page and collect its visible metadata and media responses. Do not print or store signed media URLs in durable artifacts.
3. Inspect `Content-Range`. Douyin commonly delivers video/audio as multiple HTTP `206` byte ranges. **Never save the first response body as a complete MP4.** Read the total size from `Content-Range`, then request the complete `bytes=0-(total-1)` range through the same verified browser context.
4. Verify the resulting media with `ffprobe` before ASR. For transcript-only ingest, use the complete audio stream; then call the repository's unmodified `extract_transcript.py` to produce the readable raw transcript and hand it to `llmwiki-ingest`.

This keeps the normal route one-click: link → authenticated browser capture → complete audio → transcript → LLMwiki. The only manual interruption is a platform-issued verification page when it actually appears.

### Transcription

Prefer:

1. Existing caption/subtitle text.
2. Local Whisper or another local ASR tool.
3. API ASR only if the user has configured credentials and approves use.
4. Metadata-only artifact if no transcript can be obtained.

For Chinese videos, transcribe in Chinese by default. Preserve exact wording for trading rules, product claims, formulas, named methods, quotes, and user-relevant phrases.

## Safety

- Work only with public content or content the user has permission to archive.
- Do not bypass login, paywalls, private accounts, DRM, or platform access controls.
- Do not ask for or store passwords. If cookies are required, ask for the minimum required cookie material and treat it as secret.
- Do not use `--cookies-from-browser` or read browser profiles unless the user explicitly approves that exact action after being warned that cookies are session material.
- Do not redistribute video files. Prefer text transcript, metadata, source URL, and notes.
- Keep downloaded audio/video temporary unless the user explicitly asks to preserve it.
- Respect rate limits. For batches, process slowly and stop on challenges, repeated failures, or blocks.
- Always label partial extraction and uncertainty.

## Source Artifact Template

Create one Markdown file per Douyin source. Use a filename that is stable, readable, and based on the content title or topic. The file should be recognizable in a file browser without opening it. Keep the video ID in frontmatter; do not make the primary filename a bare ID or hash-like string.

```text
raw/video/YYYY-MM-DD_<short-readable-title>.md
```

Good examples:

```text
raw/video/2026-07-07_如何把-codex-改造成自进化系统.md
raw/video/2026-07-07_缠论买卖点复盘.md
```

If the title is missing, infer a short topic from the transcript or visible description. If two files would collide, append a short video ID suffix such as `-7628277572291267890`, but only as a disambiguator.

Use this structure:

```markdown
---
title: "原始标题或可读标题"
source_platform: douyin
source_type: short_video
url: "https://..."
canonical_url: "https://..."
video_id: "..."
author: "..."
published: "YYYY-MM-DD or unknown"
captured: "YYYY-MM-DD"
duration: "unknown"
transcript_method: "caption | whisper | api_asr | manual | unavailable"
extraction_status: "complete | partial | metadata-only | failed"
tags:
  - douyin
---

# 原始标题或可读标题

## Source Metadata

- Platform: Douyin
- Author:
- URL:
- Canonical URL:
- Video ID:
- Published:
- Captured:
- Duration:
- Music/Audio:
- Hashtags:
- Extraction backend:
- Transcript method:
- Extraction status:

## Description

保留原始标题、描述、话题标签、页面可见文字。不要把后续分析混入这里。

## Transcript

如果有时间戳，使用紧凑列表：

- `[00:00] ...`
- `[00:08] ...`

如果没有时间戳，按自然段整理。

如果没有转写，写：

> Transcript unavailable. Reason: ...

## Visual Notes

只记录对理解内容有帮助的画面信息。不要凭空补充。

## Collector Notes

- What worked:
- What failed:
- Fields requiring verification:
```

This artifact should be factual and source-like. Leave interpretation, linking, entity/concept creation, and synthesis to `llmwiki-ingest`.

## Hand-Off To llmwiki-ingest

After the artifact is written, use `llmwiki-ingest` on that `raw/video/` file.

Expected ingest behavior:

- Create/update `wiki/sources/`.
- Create/update `wiki/entities/` and `wiki/concepts/` (not `wiki/topics/`).
- Update `wiki/index.md` and `wiki/log.md`.

Do not duplicate those writes here.

## Batch Workflow

For multiple Douyin links:

1. Create a manifest in the working area or next to the artifacts with columns: input, canonical_url, video_id, title, author, status, artifact_path, transcript_method.
2. Deduplicate by canonical URL or video ID.
3. Write one artifact per video.
4. Digest artifacts through `llmwiki-ingest` in small groups. A good default is 3-8 videos per pass.
5. Ask `llmwiki-ingest` for a summary/synthesis page only after the source artifacts have been digested.

## Failure Statuses

Use clear status labels:

- `resolved-url-failed`
- `metadata-only`
- `audio-download-failed`
- `asr-failed`
- `login-or-cookie-required`
- `rate-limited-or-blocked`
- `private-or-unavailable`

When blocked, give the smallest useful next step: direct URL, copied share text, local exported video file, a manually exported minimal cookie file, or permission to use a configured ASR service. Browser-profile cookie extraction is a sensitive action and should be treated as opt-in, not automatic.

## Final Report

End with:

- Processed source: title, author, URL.
- Raw artifact created: path.
- Transcript method and extraction status.
- `llmwiki-ingest` hand-off status: completed, requested, or pending.
- Missing fields or caveats.

Keep the report concise and honest. The value is traceable source evidence that `llmwiki-ingest` can digest cleanly.
