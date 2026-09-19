"""Download a user-authorized WeChat Channels share through a local parser API.

The parser is intentionally external to this plugin.  It must run on the same
machine and expose a loopback HTTP endpoint; this module never reads cookies,
browser profiles, or WeChat data.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


URL_RE = re.compile(r"https?://[^\s<>\"'，。；：！？]+", re.IGNORECASE)
SHARE_HOSTS = {"channels.weixin.qq.com", "weixin.qq.com"}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def extract_share_url(text: str) -> str:
    """Extract the first WeChat Channels HTTPS URL from a share message."""
    for candidate in URL_RE.findall(text):
        parsed = urlparse(candidate)
        if parsed.scheme != "https":
            continue
        if parsed.hostname and (parsed.hostname in SHARE_HOSTS or parsed.hostname.endswith(".weixin.qq.com")):
            return candidate
    raise ValueError("未找到微信视频号 HTTPS 分享链接")


def validate_parser_url(parser_url: str) -> str:
    """Permit local helper APIs only, so share data is not sent to a third party."""
    parsed = urlparse(parser_url)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        raise ValueError("解析器必须是本机回环 HTTP 地址，例如 http://127.0.0.1:2026/api/...")
    if parsed.username or parsed.password:
        raise ValueError("解析器地址不能包含凭据")
    return parser_url


def _walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def find_media_urls(payload: Any) -> list[str]:
    """Find unique Tencent video URLs and intentionally ignore image/page URLs."""
    found: list[str] = []
    for value in _walk_strings(payload):
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (host == "video.qq.com" or host.endswith(".video.qq.com")):
            continue
        if value not in found:
            found.append(value)
    return found


def request_parse(parser_url: str, share_url: str, url_param: str = "url", timeout: int = 30) -> Any:
    """Call a local share-link parser and return its JSON response."""
    parser_url = validate_parser_url(parser_url)
    parsed = urlparse(parser_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[url_param] = share_url
    request_url = urlunparse(parsed._replace(query=urlencode(query)))
    request = Request(request_url, headers={"Accept": "application/json", "User-Agent": "LLMwiki-Media-Ingest/0.2"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def download_media(media_url: str, output: Path, max_mb: int = 500, timeout: int = 60) -> Path:
    """Download one parser-provided media URL with a strict size limit."""
    output.parent.mkdir(parents=True, exist_ok=True)
    cap = max_mb * 1024 * 1024
    request = Request(media_url, headers={"User-Agent": "LLMwiki-Media-Ingest/0.2"})
    total = 0
    with urlopen(request, timeout=timeout) as response, output.open("wb") as handle:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > cap:
            raise ValueError(f"视频超过 {max_mb}MB 限额")
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            total += len(chunk)
            if total > cap:
                output.unlink(missing_ok=True)
                raise ValueError(f"视频超过 {max_mb}MB 限额")
            handle.write(chunk)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Download an authorized WeChat Channels share through a local parser.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--share-text")
    source.add_argument("--share-url")
    parser.add_argument("--parser-url", required=True, help="Loopback URL of the local share-link parser")
    parser.add_argument("--url-param", default="url", help="Parser query parameter used for the shared URL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-mb", type=int, default=500)
    args = parser.parse_args()

    share_url = args.share_url or extract_share_url(args.share_text)
    if args.share_url:
        share_url = extract_share_url(args.share_url)
    payload = request_parse(args.parser_url, share_url, args.url_param)
    media_urls = find_media_urls(payload)
    if not media_urls:
        raise SystemExit("本地解析器未返回可下载的视频地址；请确认分享链接有效且解析器已启动。")
    output = download_media(media_urls[0], Path(args.output), args.max_mb)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
