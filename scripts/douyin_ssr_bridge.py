#!/usr/bin/env python3
"""
Douyin SSR bridge for <VAULT> vault (采集前台, 不碰 wiki 入库).

灵感来自 lyxdream/obsidian-content-capture-backend 的分享页 SSR 解析:
  移动端 UA 打开 iesdouyin share 页 → 读 window._ROUTER_DATA / RENDER_DATA
  → 无水印 play 链或图文 desc+配图。

设计边界:
  - 只产出 raw 侧证据 (默认 raw/video/), 再交给 llmwiki-ingest
  - 不改 extract_transcript.py; 视频 ASR 优先调用该脚本本地文件模式
  - 不写 Obsidian 插件式 Douyin/ 夹, 不嵌视频进 vault 附件目录
  - 不打印/不把签名 CDN URL 写入 raw Markdown 正文

用法示例:
  # 仅解析元数据 (最快, 验证 SSR 是否仍活)
  python tools/douyin_ssr_bridge.py "https://v.douyin.com/xxx/" --meta-only

  # 解析 + 下载临时 MP4 + 调用 extract_transcript 转写 → raw/video
  python tools/douyin_ssr_bridge.py "分享文案或链接" --output raw/video --model medium

  # 图文 note: 只写 desc 与元数据, 不跑 Whisper
  python tools/douyin_ssr_bridge.py "https://www.douyin.com/note/ID" --output raw/video

  # 仅下载到临时目录, 你自己再转写
  python tools/douyin_ssr_bridge.py "链接" --download-only --tmp-dir _tmp_douyin
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote

try:
    import requests
except ImportError:
    print("需要 requests: pip install requests", file=sys.stderr)
    sys.exit(1)

SHARE_PAGE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
ROUTER_DATA_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(\{.+)", re.DOTALL)
RENDER_DATA_RE = re.compile(
    r'<script id="RENDER_DATA" type="application/json">([^<]+)</script>'
)
IMAGE_AWEME_TYPES = {2, 68}
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DouyinContentMeta:
    aweme_id: str
    title: str
    author: str
    source_url: str
    content_type: Literal["video", "image"] = "video"
    aweme_type: int | None = None
    download_url: str = ""
    cover_url: str | None = None
    image_urls: list[str] = field(default_factory=list)
    page_url: str = ""


class DouyinResolveError(Exception):
    pass


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": SHARE_PAGE_UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return s


def expand_share_url(share_text: str) -> str:
    text = share_text.strip()
    match = re.search(
        r"https?://(?:v\.douyin\.com|www\.douyin\.com|www\.iesdouyin\.com|"
        r"m\.douyin\.com|iesdouyin\.com)[^\s\]]*",
        text,
    )
    if not match:
        raise DouyinResolveError("未在输入中找到抖音链接")
    return match.group(0).rstrip("/.,;)")


def normalize_to_share_page(url: str) -> str:
    note = re.search(r"https?://(?:www\.)?douyin\.com/note/(\d+)", url)
    if note:
        return f"https://www.iesdouyin.com/share/note/{note.group(1)}/"
    video = re.search(r"https?://(?:www\.)?douyin\.com/video/(\d+)", url)
    if video:
        return f"https://www.iesdouyin.com/share/video/{video.group(1)}/"
    return url


def resolve_share_page(session: requests.Session, share_url: str) -> tuple[str, str]:
    resp = session.get(share_url, allow_redirects=True, timeout=30)
    resp.raise_for_status()
    return str(resp.url), resp.text


def extract_aweme_id(page_url: str, html: str | None = None) -> str:
    patterns = [
        r"/video/(\d+)",
        r"/note/(\d+)",
        r"/share/video/(\d+)",
        r"/share/note/(\d+)",
        r"modal_id=(\d+)",
        r"item_ids=(\d+)",
        r'"aweme_id"\s*:\s*"?(\d+)"?',
        r'"itemId"\s*:\s*"?(\d+)"?',
    ]
    for pat in patterns:
        m = re.search(pat, page_url)
        if m:
            return m.group(1)
    if html:
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                return m.group(1)
    raise DouyinResolveError(f"无法从分享页解析作品 ID: {page_url}")


def _parse_router_data(html: str) -> dict[str, Any] | None:
    m = ROUTER_DATA_RE.search(html)
    if not m:
        return None
    raw = m.group(1).split("</script>")[0].rstrip().rstrip(";")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_render_data(html: str) -> dict[str, Any] | None:
    m = RENDER_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(unquote(m.group(1)))
    except json.JSONDecodeError:
        return None


def _find_item_list(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, dict):
        if "item_list" in obj and isinstance(obj["item_list"], list) and obj["item_list"]:
            first = obj["item_list"][0]
            if isinstance(first, dict) and (
                "aweme_id" in first or "video" in first or "images" in first
            ):
                return obj["item_list"]
        for v in obj.values():
            found = _find_item_list(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_item_list(item)
            if found:
                return found
    return []


def _pick_url_from_image_node(img: dict[str, Any]) -> str | None:
    for key in ("url_list", "download_url_list"):
        lst = img.get(key) or []
        if lst:
            return str(lst[-1])
    return None


def _extract_image_urls(item: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(u: str | None) -> None:
        if u and u not in seen:
            seen.add(u)
            urls.append(u)

    for img in item.get("images") or []:
        if isinstance(img, dict):
            add(_pick_url_from_image_node(img))
    post = item.get("image_post_info") or {}
    if isinstance(post, dict):
        for img in post.get("images") or []:
            if isinstance(img, dict):
                add(_pick_url_from_image_node(img))
    return urls


def _has_playable_video(item: dict[str, Any]) -> bool:
    video = item.get("video") or {}
    if not isinstance(video, dict):
        return False
    play_addr = video.get("play_addr") or video.get("playAddr") or {}
    if not isinstance(play_addr, dict):
        return False
    return bool(play_addr.get("uri") or play_addr.get("url_list"))


def is_image_note(item: dict[str, Any]) -> bool:
    if item.get("aweme_type") in IMAGE_AWEME_TYPES:
        return True
    return bool(_extract_image_urls(item)) and not _has_playable_video(item)


def _build_no_watermark_url(play_addr: dict[str, Any]) -> str:
    uri = play_addr.get("uri") or ""
    url_list = play_addr.get("url_list") or []
    if uri:
        return (
            f"https://aweme.snssdk.com/aweme/v1/play/"
            f"?video_id={uri}&ratio=720p&line=0"
        )
    if url_list:
        return str(url_list[0]).replace("playwm", "play")
    raise DouyinResolveError("分享页内嵌数据中未找到视频播放地址")


def _meta_from_aweme_item(
    item: dict[str, Any], source_url: str, page_url: str
) -> DouyinContentMeta:
    aweme_id = str(item.get("aweme_id") or item.get("awemeId") or "")
    desc = (item.get("desc") or item.get("caption") or "").strip() or f"douyin_{aweme_id}"
    aweme_type = item.get("aweme_type")
    author = ""
    author_info = item.get("author") or {}
    if isinstance(author_info, dict):
        author = author_info.get("nickname") or author_info.get("unique_id") or ""

    if is_image_note(item):
        image_urls = _extract_image_urls(item)
        if not image_urls:
            raise DouyinResolveError("识别为图文，但未找到图片地址")
        return DouyinContentMeta(
            aweme_id=aweme_id,
            title=desc,
            author=author,
            source_url=source_url,
            content_type="image",
            aweme_type=aweme_type,
            cover_url=image_urls[0],
            image_urls=image_urls,
            page_url=page_url,
        )

    video = item.get("video") or {}
    play_addr = video.get("play_addr") or video.get("playAddr") or {}
    if not isinstance(play_addr, dict):
        raise DouyinResolveError("视频节点缺少 play_addr")
    download_url = _build_no_watermark_url(play_addr)

    for br in video.get("bit_rate") or []:
        if not isinstance(br, dict):
            continue
        br_play = br.get("play_addr") or {}
        if isinstance(br_play, dict) and br_play.get("url_list"):
            u = str(br_play["url_list"][0])
            if "playwm" not in u and ("douyinvod" in u or "bytecdn" in u):
                download_url = u
                break

    cover = None
    for key in ("cover", "origin_cover", "dynamic_cover"):
        cover_info = video.get(key) or {}
        if isinstance(cover_info, dict):
            covers = cover_info.get("url_list") or []
            if covers:
                cover = str(covers[0])
                break

    return DouyinContentMeta(
        aweme_id=aweme_id,
        title=desc,
        author=author,
        source_url=source_url,
        content_type="video",
        aweme_type=aweme_type,
        download_url=download_url,
        cover_url=cover,
        page_url=page_url,
    )


def parse_share_page_html(html: str, page_url: str, original_share: str) -> DouyinContentMeta:
    for parser in (_parse_router_data, _parse_render_data):
        payload = parser(html)
        if not payload:
            continue
        items = _find_item_list(payload)
        if not items:
            continue
        meta = _meta_from_aweme_item(items[0], original_share, page_url)
        if not meta.aweme_id:
            meta.aweme_id = extract_aweme_id(page_url, html)
        return meta
    raise DouyinResolveError(
        "分享页未找到内嵌公开数据（_ROUTER_DATA / RENDER_DATA）。链接失效或平台改版。"
    )


def resolve_douyin_share(share_text: str) -> DouyinContentMeta:
    session = _session()
    share_url = expand_share_url(share_text)
    fetch_url = normalize_to_share_page(share_url)
    page_url, html = resolve_share_page(session, fetch_url)
    # 短链会跳到 iesdouyin；若仍是 v.douyin，再取 final URL 归一
    if "iesdouyin.com" not in page_url and "douyin.com" in page_url:
        page_url2, html2 = resolve_share_page(session, normalize_to_share_page(page_url))
        page_url, html = page_url2, html2
    return parse_share_page_html(html, page_url, share_url)


def slugify_title(title: str, max_len: int = 40) -> str:
    t = re.sub(r"\s+", "-", title.strip())
    t = re.sub(r'[\\/:*?"<>|#]', "", t)
    t = re.sub(r"-+", "-", t).strip("-")
    if len(t) > max_len:
        t = t[:max_len].rstrip("-")
    return t or "douyin"


def canonical_url(meta: DouyinContentMeta) -> str:
    if meta.content_type == "image":
        return f"https://www.douyin.com/note/{meta.aweme_id}"
    return f"https://www.douyin.com/video/{meta.aweme_id}"


def download_media(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = _session()
    with session.get(url, stream=True, timeout=120, allow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
    if dest.stat().st_size < 1024:
        raise RuntimeError(f"下载文件过小 ({dest.stat().st_size} bytes)，可能被风控")
    return dest


def write_raw_markdown(
    *,
    output_dir: Path,
    meta: DouyinContentMeta,
    transcript: str,
    transcript_method: str,
    extraction_status: str,
    backend: str,
    title_override: str | None,
    collector_notes: list[str],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    title = (title_override or meta.title or f"douyin-{meta.aweme_id}").strip()
    today = date.today().isoformat()
    fname = f"{today}_{slugify_title(title)}.md"
    path = output_dir / fname
    if path.exists():
        path = output_dir / f"{today}_{slugify_title(title)}-{meta.aweme_id[-6:]}.md"

    body_transcript = transcript.strip() if transcript.strip() else (
        "> Transcript unavailable. Reason: no caption / ASR not run"
    )
    notes = "\n".join(f"  - {n}" for n in collector_notes) or "  - (none)"

    content = f"""---
title: "{title.replace('"', "'")}"
source_platform: douyin
source_type: {"image_note" if meta.content_type == "image" else "short_video"}
url: "{meta.source_url}"
canonical_url: "{canonical_url(meta)}"
video_id: "{meta.aweme_id}"
author: "{meta.author}"
published: "unknown"
captured: "{today}"
duration: "unknown"
transcript_method: "{transcript_method}"
extraction_status: "{extraction_status}"
tags:
  - douyin
---

# {title}

## Source Metadata

- Platform: Douyin
- Author: {meta.author or "unknown"}
- URL: {meta.source_url}
- Canonical URL: {canonical_url(meta)}
- Video ID: {meta.aweme_id}
- Content type: {meta.content_type}
- Captured: {today}
- Extraction backend: {backend}
- Transcript method: {transcript_method}
- Extraction status: {extraction_status}

## Description

{meta.title}

## Transcript

{body_transcript}

## Visual Notes

- content_type={meta.content_type}; image_count={len(meta.image_urls)}
- 未在正文中保存签名媒体 URL。

## Collector Notes

- What worked:
{notes}
- What failed:
  - （无则留空）
- Fields requiring verification:
  - published / duration / hashtags
"""
    path.write_text(content, encoding="utf-8")
    return path


def run_extract_transcript(
    media_path: Path, *, output: Path, title: str, model: str
) -> Path:
    script = REPO_ROOT / "extract_transcript.py"
    if not script.exists():
        raise FileNotFoundError(f"找不到 {script}（AGENTS 约定只用、不改）")
    cmd = [
        sys.executable,
        str(script),
        str(media_path),
        "--output",
        str(output),
        "--title",
        title,
        "--model",
        model,
    ]
    print("调用 extract_transcript.py:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))
    # extract_transcript 命名: YYYY-MM-DD_title.md
    candidates = sorted(output.glob(f"{date.today().isoformat()}_*.md"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        candidates = sorted(output.glob("*.md"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise RuntimeError("extract_transcript 已运行但未找到输出 md")
    return candidates[-1]


def print_meta_summary(meta: DouyinContentMeta) -> None:
    safe = {
        "aweme_id": meta.aweme_id,
        "title": meta.title[:120],
        "author": meta.author,
        "content_type": meta.content_type,
        "source_url": meta.source_url,
        "canonical_url": canonical_url(meta),
        "has_download_url": bool(meta.download_url),
        "image_count": len(meta.image_urls),
        "page_url_host": re.sub(r"^https?://", "", meta.page_url).split("/")[0]
        if meta.page_url
        else "",
    }
    print(json.dumps(safe, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Douyin SSR → raw/video bridge")
    parser.add_argument("input", help="抖音链接或整段分享文案")
    parser.add_argument("--output", default="raw/video", help="raw Markdown 输出目录")
    parser.add_argument("--title", default=None, help="覆盖标题/文件名")
    parser.add_argument("--model", default="medium", help="Whisper 模型，转交给 extract_transcript")
    parser.add_argument("--meta-only", action="store_true", help="只解析元数据，不下载不转写")
    parser.add_argument("--download-only", action="store_true", help="解析并下载到临时目录")
    parser.add_argument(
        "--tmp-dir",
        default=None,
        help="临时媒体目录；默认系统临时目录下 douyin_ssr_*",
    )
    parser.add_argument(
        "--keep-media",
        action="store_true",
        help="转写后保留临时 MP4（默认删除）",
    )
    parser.add_argument(
        "--no-asr",
        action="store_true",
        help="下载后不调用 extract_transcript，只写 metadata-only/partial raw",
    )
    args = parser.parse_args()

    try:
        meta = resolve_douyin_share(args.input)
    except DouyinResolveError as e:
        print(f"RESOLVE_FAILED: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"NETWORK_FAILED: {e}", file=sys.stderr)
        return 1

    print_meta_summary(meta)
    backend = "iesdouyin-ssr (_ROUTER_DATA/RENDER_DATA)"

    if args.meta_only:
        out = write_raw_markdown(
            output_dir=Path(args.output),
            meta=meta,
            transcript="",
            transcript_method="unavailable",
            extraction_status="metadata-only",
            backend=backend,
            title_override=args.title,
            collector_notes=["SSR 分享页解析成功", "meta-only 模式未下载/转写"],
        )
        print(f"raw written: {out}")
        return 0

    # 图文：desc 即文案
    if meta.content_type == "image":
        out = write_raw_markdown(
            output_dir=Path(args.output),
            meta=meta,
            transcript=meta.title,
            transcript_method="platform_desc",
            extraction_status="complete",
            backend=backend,
            title_override=args.title,
            collector_notes=[
                "SSR 解析图文 note",
                f"配图 {len(meta.image_urls)} 张（未下载进 vault，避免附件膨胀）",
            ],
        )
        print(f"raw written: {out}")
        return 0

    if not meta.download_url:
        print("无 download_url，无法下载视频", file=sys.stderr)
        return 1

    tmp_root = Path(args.tmp_dir) if args.tmp_dir else Path(tempfile.mkdtemp(prefix="douyin_ssr_"))
    tmp_root.mkdir(parents=True, exist_ok=True)
    media_path = tmp_root / f"{meta.aweme_id}.mp4"
    print(f"下载到临时文件: {media_path} (不打印 CDN URL)")
    try:
        download_media(meta.download_url, media_path)
    except Exception as e:
        out = write_raw_markdown(
            output_dir=Path(args.output),
            meta=meta,
            transcript="",
            transcript_method="unavailable",
            extraction_status="audio-download-failed",
            backend=backend,
            title_override=args.title,
            collector_notes=["SSR 解析成功", f"下载失败: {type(e).__name__}: {e}"],
        )
        print(f"raw written (failed download): {out}", file=sys.stderr)
        return 1

    if args.download_only:
        print(f"download-only ok: {media_path}")
        return 0

    if args.no_asr:
        out = write_raw_markdown(
            output_dir=Path(args.output),
            meta=meta,
            transcript="",
            transcript_method="unavailable",
            extraction_status="partial",
            backend=backend,
            title_override=args.title,
            collector_notes=[
                "SSR 解析 + 临时下载成功",
                f"媒体路径: {media_path}",
                "未跑 ASR（--no-asr）",
            ],
        )
        print(f"raw written: {out}")
        return 0

    title = args.title or meta.title
    try:
        md = run_extract_transcript(
            media_path, output=Path(args.output), title=title, model=args.model
        )
        print(f"transcript raw: {md}")
        # 在 extract 产出上补一条 collector 说明更干净；此处只打印提示
        print(
            "提示: extract_transcript 已写 raw。"
            "若 frontmatter 缺 video_id，可手动补或再用本脚本 --meta-only 对照。"
        )
    except Exception as e:
        out = write_raw_markdown(
            output_dir=Path(args.output),
            meta=meta,
            transcript="",
            transcript_method="unavailable",
            extraction_status="asr-failed",
            backend=backend,
            title_override=args.title,
            collector_notes=[
                "SSR 解析 + 下载成功",
                f"ASR/extract_transcript 失败: {type(e).__name__}: {e}",
                f"临时媒体: {media_path}",
            ],
        )
        print(f"raw written (asr failed): {out}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_media and media_path.exists() and not args.download_only:
            try:
                media_path.unlink()
            except OSError:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
