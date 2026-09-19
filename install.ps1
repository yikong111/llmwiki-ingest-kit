# LLMwiki Ingest Kit 一键安装（Windows PowerShell）
# 用法： powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = 'Stop'

$url = 'https://github.com/yikong111/llmwiki-ingest-kit/releases/latest/download/llmwiki-ingest-kit.zip'
$tmp = Join-Path $env:TEMP ("llmwiki-kit-" + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$zip = Join-Path $tmp 'kit.zip'

Write-Host '→ 下载 llmwiki-ingest-kit ...'
Invoke-WebRequest -Uri $url -OutFile $zip

Write-Host '→ 解压 ...'
Expand-Archive -Path $zip -DestinationPath $tmp -Force
$src = Join-Path $tmp 'llmwiki-ingest-kit'
if (-not (Test-Path $src)) { throw '解压结果异常，中止' }

$installed = $false

# Claude Code 插件目录
$claude = Join-Path $env:USERPROFILE '.claude'
if (Test-Path $claude) {
    $dst = Join-Path $claude 'plugins\llmwiki-ingest-kit'
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
    Copy-Item $src $dst -Recurse -Force
    Write-Host "✓ 已装到 $dst"
    $installed = $true
}

# Codex 插件目录
$codex = Join-Path $env:USERPROFILE '.codex'
if (Test-Path $codex) {
    $dst = Join-Path $codex 'plugins\llmwiki-ingest-kit'
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
    Copy-Item $src $dst -Recurse -Force
    Write-Host "✓ 已装到 $dst"
    $installed = $true
}

# 通用 agent skills 目录
$skills = Join-Path $env:USERPROFILE '.agents\skills'
if (Test-Path $skills) {
    Get-ChildItem (Join-Path $src 'skills') -Directory | ForEach-Object {
        $d = Join-Path $skills $_.Name
        if (Test-Path $d) { Remove-Item $d -Recurse -Force }
        Copy-Item $_.FullName $d -Recurse -Force
    }
    Write-Host "✓ 四个 skill 已装到 $skills"
    $installed = $true
}

if (-not $installed) {
    Write-Host '没找到 .claude / .codex / .agents\skills 目录。'
    Write-Host "包已解压在：$src"
    Write-Host '把整个目录复制进你的插件目录，或把 skills 下四个目录复制进 agent 的 skills 目录。'
    exit 2
}

Write-Host ''
Write-Host '还差一步：在你的 Obsidian 库根目录放一个 AGENTS.md，写清库结构'
Write-Host '（concepts / entities / sources / summaries / syntheses / raw / index.md / log.md）。'
Write-Host '没有它，摄入流程不知道该把页面建到哪。详见 INSTALL.md。'
Write-Host ''
Write-Host '然后对你的 agent 说：「把这个链接整合进库」+ 链接。'
