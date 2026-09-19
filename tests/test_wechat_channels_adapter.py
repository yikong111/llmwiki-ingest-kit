import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "wechat_channels_adapter.py"
SPEC = importlib.util.spec_from_file_location("wechat_channels_adapter", SCRIPT)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class WeChatChannelsAdapterTests(unittest.TestCase):
    def test_extracts_wechat_channels_url_from_share_text(self):
        text = "朋友发来：视频号内容 https://channels.weixin.qq.com/abc?x=1"
        self.assertEqual(
            adapter.extract_share_url(text),
            "https://channels.weixin.qq.com/abc?x=1",
        )

    def test_rejects_non_wechat_share_url(self):
        with self.assertRaises(ValueError):
            adapter.extract_share_url("https://example.com/video")

    def test_accepts_only_loopback_parser_url(self):
        self.assertEqual(
            adapter.validate_parser_url("http://127.0.0.1:2026/api/channels/parse_sph"),
            "http://127.0.0.1:2026/api/channels/parse_sph",
        )
        with self.assertRaises(ValueError):
            adapter.validate_parser_url("https://parser.example.com/parse")

    def test_finds_tencent_video_urls_but_not_thumbnails(self):
        payload = {
            "page": "https://channels.weixin.qq.com/abc",
            "thumbnail": "https://wx.qlogo.cn/avatar.jpg",
            "media": {
                "url": "https://finder.video.qq.com/123/stream.mp4?token=secret",
            },
            "fallback": "https://finder.video.qq.com/123/stream.mp4?token=secret",
        }
        self.assertEqual(
            adapter.find_media_urls(payload),
            ["https://finder.video.qq.com/123/stream.mp4?token=secret"],
        )


if __name__ == "__main__":
    unittest.main()
