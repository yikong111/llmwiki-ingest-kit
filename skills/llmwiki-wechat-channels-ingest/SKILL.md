---
name: llmwiki-wechat-channels-ingest
description: "Prepare a user-authorized WeChat Channels (微信视频号) share link or share text for LLMwiki. Use when the user sends 视频号链接, 微信视频号分享, 下载微信视频号, or asks to save a WeChat Channels video into Obsidian/LLMwiki without first exporting an MP4."
---

# 微信视频号分享链接摄入

目标是“分享链接 → 桌面微信下载器 → 转录 → LLMwiki”，而不是先要求用户提供 MP4。

## Preconditions

1. 确认内容是公开的，且用户有权为个人学习、归档而保存。
2. 本机必须已启动受信任的桌面微信视频号下载器（当前流程为 `wx_channel`），并且它只在本机运行。
3. 不读取、索取或导出微信 Cookie、浏览器资料、聊天记录或私密链接。

## Workflow

1. 接收微信分享文本或 HTTPS 分享链接，原样保存为来源元数据。
2. 通过桌面微信打开分享链接；下载器捕获到视频后，使用其注入的“更多 → 下载视频”菜单。
3. 默认选择最低可用清晰度。此工作流以音频转写为主，除非用户明确要求，否则不保留高码率版本。
4. 等待下载器完成下载与解密后，用仓库的 `extract_transcript.py` 生成 `raw/video/` 转录稿，再走正常的 LLMwiki Ingest：source 页、双链、`wiki/index.md` 和 `wiki/log.md`。
5. 文件名使用主题化标题；分享链接、作者、采集日期、下载规格和解析状态放进 frontmatter。

## Failure Handling

- 本地下载器未运行、微信未注入或没有捕获到视频：报告所需的本机状态；不伪造下载结果。
- 视频不公开、需要额外登录、受 DRM 或平台限制：停止，不尝试规避。
- 只有当链接链路确实失败且用户随后自愿提供文件时，才采用本地文件兼容路径。
