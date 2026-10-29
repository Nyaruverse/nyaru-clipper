"""切片封面合成：弹幕峰值时刻截帧 + 黄字红边大字报。

- 截帧用 ffmpeg（media.tool_path），叠字用 Pillow；
- 任何失败（无视频/无字体/无封面文字）都返回 False，绝不影响评分与切片流程；
- 输出 JPEG 写入任务目录，文件名 cover-NN.jpg，由 apply_covers 负责缓存与失效。
"""
from __future__ import annotations

import json
from pathlib import Path

from app.arctime import media

# 大字报配色：黄色填充 + 红色描边
FILL = (255, 222, 26)
STROKE = (199, 22, 16)
# B 站投稿封面固定 16:10（1146×717）
COVER_WIDTH, COVER_HEIGHT = 1146, 717
COVER_VERSION = "16x10"
# 单行/两行字号占画面高度的比例
SIZE_ONE_LINE = .16
SIZE_TWO_LINES = .125
TOP_MARGIN = .055
MAX_TEXT_WIDTH = .92

_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)
_font_path: str | None = None


def _find_font() -> str | None:
    global _font_path
    if _font_path is not None:
        return _font_path or None
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            _font_path = candidate
            return candidate
    _font_path = ""
    return None


def _wrap(text: str) -> list[str]:
    """6 字以内一行；更长则两行，优先在标点处断开。"""
    text = " ".join(text.split())
    if len(text) <= 6:
        return [text]
    mid = (len(text) + 1) // 2
    for offset in range(3):
        for pos in (mid + offset, mid - offset):
            if 0 < pos < len(text) and text[pos - 1] in "，。！？、：；… ":
                return [text[:pos].strip(), text[pos:].strip()]
    return [text[:mid], text[mid:]]


def _load_font(size: int):
    from PIL import ImageFont
    path = _find_font()
    if not path:
        return None
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return None


def render(video: Path, at: float, text: str, out: Path) -> bool:
    """在 at 秒截帧并把 text 以大字报样式叠到顶部，保存为 JPEG。失败返回 False。"""
    from PIL import Image, ImageDraw

    text = text.strip()
    if not text or not video.is_file():
        return False
    frame = out.with_suffix(".frame.jpg")
    try:
        media.run_managed([media.tool_path("ffmpeg"), "-ss", f"{max(0.0, at):.3f}", "-i", str(video),
                           "-frames:v", "1", "-q:v", "2", "-y", str(frame)], timeout=60)
        if not frame.is_file() or frame.stat().st_size == 0:
            return False
        image = Image.open(frame).convert("RGB")
        # 中心裁切成 16:10 再缩放到 B 站投稿封面尺寸，避免比例不符被拉伸
        ratio = COVER_WIDTH / COVER_HEIGHT
        frame_w, frame_h = image.size
        if frame_w / frame_h > ratio:
            crop_w = int(round(frame_h * ratio))
            left = (frame_w - crop_w) // 2
            image = image.crop((left, 0, left + crop_w, frame_h))
        else:
            crop_h = int(round(frame_w / ratio))
            top = (frame_h - crop_h) // 2
            image = image.crop((0, top, frame_w, top + crop_h))
        image = image.resize((COVER_WIDTH, COVER_HEIGHT), Image.LANCZOS)
        width, height = image.size
        lines = _wrap(text)
        draw = ImageDraw.Draw(image)
        size = int(height * (SIZE_ONE_LINE if len(lines) == 1 else SIZE_TWO_LINES))
        font = _load_font(size)
        if font is None:
            return False
        # 超出画面宽度时按最宽行等比缩小
        widths = [draw.textbbox((0, 0), line, font=font, stroke_width=0)[2] for line in lines]
        widest = max(widths) if widths else 0
        if widest > width * MAX_TEXT_WIDTH:
            size = max(12, int(size * width * MAX_TEXT_WIDTH / widest))
            font = _load_font(size)
            if font is None:
                return False
        stroke = max(3, size // 11)
        y = int(height * TOP_MARGIN)
        for line in lines:
            box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
            x = (width - (box[2] - box[0])) // 2
            draw.text((x, y), line, font=font, fill=FILL, stroke_width=stroke, stroke_fill=STROKE)
            y += box[3] - box[1] + int(size * .25)
        image.save(out, "JPEG", quality=90)
        return True
    except Exception:
        return False
    finally:
        try:
            frame.unlink(missing_ok=True)
        except OSError:
            pass


def apply_covers(directory: Path, segments: list[dict]) -> bool:
    """为有封面文字的切片合成封面；内容与时刻未变时跳过。

    依赖 segment 上的 cover_text；截帧时刻优先弹幕峰值 dm_peak_time，
    无弹幕（如本地上传的视频）时退化为切片中点。缺少封面文字的切片不生成。
    返回是否有变化。
    """
    try:
        job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
        video_name = job.get("video")
    except (OSError, json.JSONDecodeError, AttributeError):
        return False
    if not video_name:
        return False
    video = directory / video_name
    if video.is_symlink() or not video.is_file():
        return False
    changed = False
    for index, segment in enumerate(segments):
        text = str(segment.get("cover_text") or "").strip()
        peak = segment.get("dm_peak_time")
        if peak is None:
            # 无弹幕时用切片中点截帧，保证本地上传的视频也能生成封面
            try:
                peak = (float(segment.get("start") or 0) + float(segment.get("end") or 0)) / 2
            except (TypeError, ValueError):
                peak = None
        if not text or peak is None:
            continue
        name = f"cover-{index + 1:02d}.jpg"
        source = f"{COVER_VERSION}|{text}|{peak}"
        if segment.get("cover") == name and segment.get("cover_source") == source \
                and (directory / name).is_file():
            continue
        if render(video, float(peak), text, directory / name):
            segment["cover"] = name
            segment["cover_source"] = source
            changed = True
    # 重新生成内容切片后段数/顺序会变，删除不再被任何段引用的旧编号封面，
    # 避免孤儿文件被同名复用或打包进投稿 zip
    referenced = {str(segment.get("cover") or "") for segment in segments}
    for stale in directory.glob("cover-*.jpg"):
        if stale.name not in referenced:
            try:
                stale.unlink()
            except OSError:
                pass
    return changed
