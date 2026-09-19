#!/usr/bin/env bash
# LLMwiki Ingest Kit 一键安装（macOS / Linux / Git Bash）
# 用法： bash install.sh   或   curl -sL <raw-url>/install.sh | bash
set -euo pipefail

URL="https://github.com/yikong111/llmwiki-ingest-kit/releases/latest/download/llmwiki-ingest-kit.zip"
TMP="$(mktemp -d)"
ZIP="$TMP/kit.zip"

echo "→ 下载 llmwiki-ingest-kit ..."
curl -fsSL "$URL" -o "$ZIP"

echo "→ 解压 ..."
unzip -qo "$ZIP" -d "$TMP"
SRC="$TMP/llmwiki-ingest-kit"
[ -d "$SRC" ] || { echo "解压结果异常，中止"; exit 1; }

installed=0

# Claude Code 插件目录
if [ -d "$HOME/.claude" ]; then
  mkdir -p "$HOME/.claude/plugins"
  rm -rf "$HOME/.claude/plugins/llmwiki-ingest-kit"
  cp -R "$SRC" "$HOME/.claude/plugins/llmwiki-ingest-kit"
  echo "✓ 已装到 ~/.claude/plugins/llmwiki-ingest-kit"
  installed=1
fi

# Codex 插件目录
if [ -d "$HOME/.codex" ]; then
  mkdir -p "$HOME/.codex/plugins"
  rm -rf "$HOME/.codex/plugins/llmwiki-ingest-kit"
  cp -R "$SRC" "$HOME/.codex/plugins/llmwiki-ingest-kit"
  echo "✓ 已装到 ~/.codex/plugins/llmwiki-ingest-kit"
  installed=1
fi

# 通用 agent skills 目录
if [ -d "$HOME/.agents/skills" ]; then
  for s in "$SRC"/skills/*/; do
    n="$(basename "$s")"
    rm -rf "$HOME/.agents/skills/$n"
    cp -R "$s" "$HOME/.agents/skills/$n"
  done
  echo "✓ 四个 skill 已装到 ~/.agents/skills/"
  installed=1
fi

if [ "$installed" -eq 0 ]; then
  echo "没找到 ~/.claude、~/.codex 或 ~/.agents/skills。"
  echo "包已解压在：$SRC"
  echo "把整个目录复制进你的插件目录，或把 skills/ 下四个目录复制进 agent 的 skills 目录。"
  exit 2
fi

cat <<'TIP'

还差一步：在你的 Obsidian 库根目录放一个 AGENTS.md，写清库结构
（concepts / entities / sources / summaries / syntheses / raw / index.md / log.md）。
没有它，摄入流程不知道该把页面建到哪。详见 INSTALL.md。

然后对你的 agent 说：「把这个链接整合进库」+ 链接。
TIP
