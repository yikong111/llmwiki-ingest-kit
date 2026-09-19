"""
抖音/多平台视频文案提取工具
流程:(下载或本地文件) → 语音识别转文字 → 输出markdown

支持两种输入模式,脚本按参数是否以 http(s):// 开头自动区分:
  1. 链接模式:B站/YouTube 等 yt-dlp 支持良好的平台,直接传链接自动下载
  2. 本地文件模式:传入一个已存在的本地视频/音频文件路径,跳过下载直接转写
     抖音因平台签名风控无法直接下载,统一走本地文件模式(先把视频存到电脑)

依赖(首次使用需安装,见下方"安装说明"):
  pip install yt-dlp faster-whisper --break-system-packages
  另需安装 ffmpeg 并加入系统 PATH
  GPU 加速(本机 RTX 4060 已启用,2026-07-05):转写默认跑在 CUDA 显卡上(device="cuda", float16)
    1) pip install nvidia-cudnn-cu12 nvidia-cublas-cu12 nvidia-cuda-runtime-cu12
    2) Windows 下 ctranslate2 只在自己所在目录找依赖 DLL(PATH/add_dll_directory 都不生效),
       须把 cublas64_12.dll、cublasLt64_12.dll、cudart64_12.dll、cudnn*64_9.dll 复制到
       site-packages/ctranslate2/ 目录下。若日后升级/重装 ctranslate2,需重新复制这些 DLL。
  无 GPU 的机器把上面 transcribe() 里的 device 改回 "cpu"、compute_type 改回 "int8" 即可

用法:
  python extract_transcript.py "https://www.bilibili.com/video/xxxx" --output raw/video
  python extract_transcript.py "D:/视频/抖音某条.mp4" --model medium --output raw/video \
         --title "有了AI为何还需要Obsidian"

参数说明:
  --model   Whisper 模型大小: tiny/base/small/medium/large-v3
            越大越准但越慢。中文推荐至少 small,追求准确率用 medium
  --output  输出目录,默认当前目录
  --lang    语言代码,默认 zh(中文),留空则自动检测
  --title   手动指定标题,决定输出文件名与页内标题。本地文件模式强烈建议指定,
            否则会拿下载文件名(如"xxx的抖音")当标题,需事后 rename
  --cookies cookies.txt 文件路径。仅链接模式对个别有风控的平台可能用得到;
            抖音签名风控 cookies 无效,请改用本地文件模式
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path
from datetime import date


def check_dependencies():
    """检查必需工具是否已安装"""
    missing = []
    try:
        import yt_dlp  # noqa
    except ImportError:
        missing.append("yt-dlp (pip install yt-dlp --break-system-packages)")
    try:
        import faster_whisper  # noqa
    except ImportError:
        missing.append("faster-whisper (pip install faster-whisper --break-system-packages)")

    # 检查 ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("ffmpeg (需要安装并加入系统 PATH, 见 https://ffmpeg.org/download.html)")

    if missing:
        print("缺少以下依赖,请先安装:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)


def download_video(url: str, tmp_dir: Path, cookies: str | None = None) -> tuple[Path, dict]:
    """下载视频,返回音频文件路径和元信息(标题、作者等)"""
    import yt_dlp

    tmp_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(tmp_dir / "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": False,
        "noplaylist": True,
    }

    # 抖音等平台有风控,需要 cookies 才能下载。传入手动导出的 cookies.txt。
    if cookies:
        ydl_opts["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id", "unknown")
        audio_path = tmp_dir / f"{video_id}.mp3"

    meta = {
        "title": info.get("title", "未知标题"),
        "uploader": info.get("uploader", "未知作者"),
        "webpage_url": info.get("webpage_url", url),
        "duration": info.get("duration"),
    }
    return audio_path, meta


def probe_duration(path: Path) -> int | None:
    """用 ffprobe 读取本地媒体时长(秒),读不到则返回 None(不影响主流程)"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return int(float(out.stdout.strip()))
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def local_file_meta(path: Path) -> dict:
    """本地文件模式:用文件名等信息构造与 download_video 一致的 meta"""
    return {
        "title": path.stem,
        "uploader": "本地文件",
        "webpage_url": str(path.resolve()),
        "duration": probe_duration(path),
    }


def transcribe(audio_path: Path, model_size: str, lang: str | None) -> str:
    """用本地 Whisper 模型转写音频为文字"""
    from faster_whisper import WhisperModel

    print(f"加载 Whisper 模型: {model_size} (首次运行会自动下载模型文件)")
    # GPU 加速:RTX 4060 + CUDA 12.x,用 float16 精度跑在显卡上,比 CPU int8 快一个数量级
    # 依赖 cuDNN 9.x(pip install nvidia-cudnn-cu12 nvidia-cublas-cu12)
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    segments, info = model.transcribe(
        str(audio_path),
        language=lang if lang else None,
        vad_filter=True,  # 过滤静音段,提升效率和准确率
    )

    print(f"检测到语言: {info.language} (置信度 {info.language_probability:.2f})")

    lines = []
    for seg in segments:
        lines.append(seg.text.strip())
        print(f"  [{seg.start:.1f}s] {seg.text.strip()}")

    return "".join(lines)


def sanitize_filename(title: str, max_len: int = 30) -> str:
    """把标题转成安全的文件名片段"""
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    title = re.sub(r"\s+", "-", title.strip())
    return title[:max_len] if title else "untitled"


def save_markdown(text: str, meta: dict, output_dir: Path, source_url: str) -> Path:
    """保存为符合第二大脑 raw/video 规范的 markdown 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    slug = sanitize_filename(meta["title"])
    filename = f"{today}_{slug}.md"
    filepath = output_dir / filename

    content = f"""# {meta['title']}

- 来源:抖音(或其他视频平台)
- 作者:{meta['uploader']}
- 原始链接:{source_url}
- 观看/摄入日期:{today}
- 时长:{meta.get('duration', '未知')} 秒

## 文字稿(自动转写,未人工校对)

{text}

## 我的想法(待补充)

"""
    filepath.write_text(content, encoding="utf-8")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="视频文案提取工具")
    parser.add_argument("url", help="视频链接(抖音/B站/YouTube等 yt-dlp 支持的平台)")
    parser.add_argument("--model", default="medium",
                         choices=["tiny", "base", "small", "medium", "large-v3"],
                         help="Whisper 模型大小,默认 medium(GPU 加速下 medium 速度也很快,无需为速度降级)")
    parser.add_argument("--output", default=".", help="输出目录,默认当前目录")
    parser.add_argument("--lang", default="zh", help="语言代码,默认 zh,留空自动检测")
    parser.add_argument("--keep-audio", action="store_true", help="保留下载的音频文件(默认转写后删除)")
    parser.add_argument("--cookies", default=None,
                         help="cookies.txt 文件路径。抖音等有风控的平台需要,用浏览器扩展导出 douyin.com 的 cookies")
    parser.add_argument("--title", default=None,
                         help="手动指定标题(决定输出文件名与页内标题)。本地文件模式下强烈建议指定,"
                              "否则会拿下载文件名(如'xxx的抖音')当标题")
    args = parser.parse_args()

    check_dependencies()

    tmp_dir = Path("./_tmp_audio")
    output_dir = Path(args.output)

    # 按参数是否以 http(s):// 开头区分:链接模式走 yt-dlp 下载,否则当作本地文件
    is_url = bool(re.match(r"^https?://", args.url, re.I))
    if is_url:
        print(f"链接模式,正在下载: {args.url}")
        audio_path, meta = download_video(args.url, tmp_dir, args.cookies)
        print(f"下载完成: {meta['title']} (作者: {meta['uploader']})")
    else:
        src = Path(args.url)
        if not src.exists():
            print(f"错误:本地文件不存在: {src}")
            print("(参数不是 http(s):// 链接时按本地文件处理,请检查路径)")
            sys.exit(1)
        audio_path = src
        meta = local_file_meta(src)
        # faster-whisper 用 av 解码,视频/音频文件都能直接转写,无需先抽音轨
        print(f"本地文件模式: {src}")

    # 手动标题优先,决定输出文件名与页内标题
    if args.title:
        meta["title"] = args.title

    print("开始转写(第一次用某个模型会先下载模型文件,请耐心等待)...")
    text = transcribe(audio_path, args.model, args.lang if args.lang else None)

    filepath = save_markdown(text, meta, output_dir, args.url)
    print(f"\n完成!已保存到: {filepath}")

    # 只清理下载产生的临时音频;本地文件模式绝不删用户的原始文件
    if not args.keep_audio and is_url:
        audio_path.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except OSError:
            pass  # 目录非空(可能有其他临时文件),不强制删除


if __name__ == "__main__":
    main()
