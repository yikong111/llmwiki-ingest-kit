---
name: llmwiki-ingest-router
description: "Route online articles, PDFs, Markdown, HTML, YouTube/Bilibili/podcast links, Douyin links, WeChat Channels share text, local video, audio, and transcripts into the correct LLMwiki ingestion workflow. Use whenever the user says 整合进 LLMwiki, 入库, 整理进 Obsidian, archive this article/video, or gives a 微信视频号/抖音/视频链接."
---

# LLMwiki Ingest Router

Use this as the source-routing layer; final knowledge-base integration remains the repository LLMwiki workflow.

## Required Routing

- 微信视频号分享文本或 `channels.weixin.qq.com` 链接：使用 `llmwiki-wechat-channels-ingest`。分享链接是首选输入，不要求用户先准备 MP4。
- 抖音链接、抖音分享文本、短视频本地文件：使用 `llmwiki-douyin-ingest`，再交给主 LLMwiki ingest。
- 文章、PDF、网页、已准备的转录稿、YouTube、Bilibili、播客：使用主 LLMwiki ingest。

## Safety

- 保留原始分享链接和采集日期，但不打印签名媒体 URL、Cookie 或会话数据。
- 只处理用户有权保存的公开内容；不能处理私密内容、付费内容或 DRM 时，明确停止。
- 微信视频号下载使用本机桌面微信下载器；不读取微信 Cookie，也不把链接提交给第三方下载网页。

## Report

- Source type:
- Chosen skill:
- Why:
- Expected artifact:
- Whether final LLMwiki integration was requested:
