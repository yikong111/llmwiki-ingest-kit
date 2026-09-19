# 给 AI 看的安装说明

> 如果你是一个 AI agent，用户把这个仓库/链接丢给你并让你「装上」，请**直接照下面做**，不要再问用户怎么装。
> 装完按最后一节汇报。

## 先判断用户在用什么

| 环境 | 判断依据 | 走哪条 |
|---|---|---|
| Claude Code | 存在 `~/.claude/` 目录 | 方式 A（首选） |
| Codex | 存在 `~/.codex/` 目录 | 方式 B |
| 其他 agent | 都不存在，或用户指定了 skills 目录 | 方式 C |

三条都做也没问题，skill 重复挂载不冲突。

## 方式 A · Claude Code 插件市场（首选，最干净）

让用户在 Claude Code 里执行这两条斜杠命令（你不能代替用户执行斜杠命令，请把它们给用户）：

```
/plugin marketplace add yikong111/llmwiki-ingest-kit
/plugin install llmwiki-ingest-kit
```

装完重启会话，四个 skill 就会出现在 skill 列表里。

## 方式 B · 直接放进插件目录

```bash
# macOS / Linux
curl -sL https://github.com/yikong111/llmwiki-ingest-kit/releases/latest/download/llmwiki-ingest-kit.zip -o /tmp/kit.zip
unzip -o /tmp/kit.zip -d ~/.claude/plugins/        # Codex 用户换成自己的插件目录
```

```powershell
# Windows PowerShell
$u="https://github.com/yikong111/llmwiki-ingest-kit/releases/latest/download/llmwiki-ingest-kit.zip"
$z="$env:TEMP\kit.zip"
Invoke-WebRequest $u -OutFile $z
Expand-Archive $z -DestinationPath "$env:USERPROFILE\.claude\plugins" -Force
```

或者直接跑仓库里的安装脚本：`install.sh`（bash）/ `install.ps1`（PowerShell），它会自己找目录。

## 方式 C · 只要 skill

把解压后 `skills/` 下的四个目录复制进用户的 agent skills 目录即可：

```
llmwiki-ingest/                 主流程：建页、双链、索引、日志、三道质量门
llmwiki-ingest-router/          来源路由：判断走哪条线
llmwiki-douyin-ingest/          抖音 / 短视频前置采集
llmwiki-wechat-channels-ingest/ 微信视频号
```

## 装完还要做一件事（不做则用不起来）

在**用户自己的 Obsidian 库根目录**放一个 `AGENTS.md`，写清库结构。没有它，摄入流程不知道该把页面建到哪。最小可用版本：

```markdown
# 本库结构

- wiki/concepts/    概念、理论、方法
- wiki/entities/    人物、组织、软件、项目、书
- wiki/sources/     每个原始来源一页
- wiki/summaries/   跨来源的主题综述
- wiki/syntheses/   我自己的判断与合成
- raw/              原始材料，只读，永不修改
- wiki/index.md     索引
- wiki/log.md       每次摄入追加一条
```

如果用户的库已有结构，照实写即可，不要强行改成上面这套。

## 自检

```bash
python tests/test_wechat_channels_adapter.py    # 期望：OK，4 tests
```

## 汇报格式

装完请告诉用户：

1. 走的是哪条方式、装到了哪个目录
2. 四个 skill 是否都在位
3. `AGENTS.md` 是已存在、还是你新建的（新建了要把内容给用户看）
4. 下一步怎么用：对我说「把这个链接整合进库」+ 链接

## 边界（安装时也请转告用户）

- 只处理用户有权保存的公开内容；付费、私密、有 DRM 的内容工具会停下不处理。
- 不读取、不导出任何 cookie 与登录态。
- 使用者自行遵守各平台服务条款与当地法律。
