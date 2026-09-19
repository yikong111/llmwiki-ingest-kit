# llmwiki-douyin-ingest

This is a Codex/agent skill draft for preparing Douyin videos for the main [`sdyckjq-lab/llm-wiki-skill`](https://github.com/sdyckjq-lab/llm-wiki-skill) workflow.

It is intentionally a front-stage collector:

1. Resolve Douyin/share/local-video inputs.
2. Extract metadata.
3. Transcribe audio when possible.
4. Create one clean Markdown source artifact.
5. Hand the artifact to `llm-wiki` for digestion into sources, topics, entities, backlinks, cache, log, index, and graph.

Generated Markdown files should use readable title/topic-based filenames, for example:

```text
raw/articles/2026-07-07-如何把-codex-改造成自进化系统-大力ai.md
```

Keep numeric video IDs in frontmatter. Use them in filenames only as a short conflict suffix.

## Recommended Stack

- Install `llm-wiki-skill` as the main knowledge-base skill.
- Enable its optional adapters for normal article/web/YouTube/Wechat/Zhihu sources.
- Use this skill only for the missing Douyin/short-video path.

## Install Main llm-wiki

On Windows, prefer the repository's PowerShell installer because it handles UTF-8 console setup:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 --platform codex --with-optional-adapters
```

The upstream README also documents:

```bash
bash install.sh --platform codex --with-optional-adapters
```

## Install This Skill

Copy this folder to an active skill directory, for example:

```powershell
Copy-Item -Recurse -Force `
  "<你的输出目录>/llmwiki-douyin-ingest" `
  "<你的 agents 目录>/skills/llmwiki-douyin-ingest"
```

Restart the agent session after installing so the skill metadata is loaded.

## Suggested Backends

- **Preferred for Douyin links**: vault `tools/douyin_ssr_bridge.py` (iesdouyin share-page SSR → temp download → `extract_transcript.py` local mode → `raw/video/`). See trial checklist in `SKILL.md`.
- Optional: lyxdream `obsidian-content-capture-backend` as download/ASR only — **do not** use the Obsidian plugin as the write path into this vault.
- `yt-dlp` for public metadata/audio extraction when it works (mainly non-Douyin).
- Playwright cookie-injected page probing when SSR/yt-dlp cannot pass Douyin's media challenge.
- `tools/Douyin_TikTok_Download_API` / `tools/douyin_backend_probe.py` when maintained locally.
- User local MP4 → `extract_transcript.py` (historical fallback).
- Whisper or another ASR tool for Chinese transcription when captions are unavailable.

Douyin extraction is brittle because platform anti-bot behavior changes frequently. This skill degrades gracefully: preserve metadata when full media extraction fails, label failure modes clearly, and keep source evidence traceable.

## Cookie Note

In a real test, `yt-dlp` may resolve the Douyin video ID but stop with:

```text
Fresh cookies (not necessarily logged in) are needed
```

Do not automatically read browser cookies. Use browser-profile cookies only after explicit user approval, or ask the user for a local exported video file / manually exported minimal cookie file.

On Windows/Codex, even after Chrome is closed, `yt-dlp --cookies-from-browser chrome` may fail with:

```text
Failed to decrypt with DPAPI
```

That means the agent process cannot decrypt Chrome's protected cookie store. In that case, prefer a manually exported Netscape-format `cookies.txt` limited to Douyin domains, or a user-provided local video file.

## Tested Extraction Path

In a real Codex Windows test on 2026-07-07:

1. `yt-dlp` resolved a Douyin short link to a canonical video ID.
2. `yt-dlp --cookies <douyin-cookies.txt>` still failed with "Fresh cookies" because the current extractor could not pass Douyin's web detail verification.
3. Playwright with the same manually exported Douyin cookies loaded the canonical page successfully.
4. The browser page exposed playable Douyin media responses.
5. The media response was downloaded, audio was extracted with ffmpeg, and a Chinese timestamped transcript was produced with `faster_whisper`.

This is the preferred fallback when `yt-dlp` accepts cookies but still fails at Douyin's detail API.
