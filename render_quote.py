import os
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
)

# ── Constants ────────────────────────────────────────────────────────────────
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS    = 24
VIDEO_DURATION = 10  # seconds (fixed)

QUOTE_FONT_SIZE  = 68
AUTHOR_FONT_SIZE = 42
MAX_CHARS_PER_LINE = 28   # narrow for portrait
LINE_SPACING = 1.45
AUTHOR_GAP   = 40         # px between last quote line and author line
SHADOW_OFFSET = 3

# TikTok / YT Shorts action buttons (like, comment, share, follow) occupy
# the right ~200px of the frame. Keep all text within the left safe zone.
RIGHT_BUTTON_MARGIN = 200   # px reserved on the right for platform UI
PAD_LEFT  = 60              # px padding from left edge
PAD_RIGHT = RIGHT_BUTTON_MARGIN + 40  # extra breathing room from button column

FONT_PATHS_BOLD = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_PATHS_REGULAR = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# ── Font helpers ─────────────────────────────────────────────────────────────
def _get_font(size, bold=True):
    paths = FONT_PATHS_BOLD if bold else FONT_PATHS_REGULAR
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap_text(text, font, max_width, draw):
    """Word-wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


# ── Background loader ────────────────────────────────────────────────────────
def _load_bg(bg_path):
    """Load + resize image to portrait 1080x1920 with darkening overlay."""
    img = Image.open(bg_path).convert("RGB")
    img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
    dark = Image.new("RGBA", img.size, (0, 0, 0, 110))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, dark)
    return img.convert("RGB")


# ── Frame builder ────────────────────────────────────────────────────────────
def _build_quote_frame(bg_img, quote_text, author_text):
    """
    Render a single RGB frame: background + centered quote + author line.
    author_text: already formatted string (e.g. "— Buddha") or "" if no author.
    """
    frame = bg_img.copy().convert("RGBA")
    draw  = ImageDraw.Draw(frame)

    font_quote  = _get_font(QUOTE_FONT_SIZE,  bold=True)
    font_author = _get_font(AUTHOR_FONT_SIZE, bold=False)

    max_w = VIDEO_WIDTH - PAD_LEFT - PAD_RIGHT  # safe zone width
    safe_center_x = PAD_LEFT + max_w // 2       # horizontal center within safe zone

    # Wrap quote
    q_lines = _wrap_text(quote_text, font_quote, max_w, draw)
    line_h  = int(QUOTE_FONT_SIZE * LINE_SPACING)
    total_q_h = line_h * len(q_lines)

    # Author height
    a_h = 0
    if author_text:
        a_bbox = draw.textbbox((0, 0), author_text, font=font_author)
        a_h = a_bbox[3] - a_bbox[1]

    # Total block height
    block_h = total_q_h + (AUTHOR_GAP + a_h if author_text else 0)

    # Vertically center block
    y = (VIDEO_HEIGHT - block_h) // 2

    # Draw quote lines — centered within the safe zone
    for line in q_lines:
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        lw = bbox[2] - bbox[0]
        x  = safe_center_x - lw // 2
        # shadow
        draw.text((x + SHADOW_OFFSET, y + SHADOW_OFFSET), line,
                  font=font_quote, fill=(0, 0, 0, 180))
        # text
        draw.text((x, y), line, font=font_quote, fill=(255, 255, 255, 255))
        y += line_h

    # Draw author — also centered within safe zone
    if author_text:
        y += AUTHOR_GAP
        a_bbox = draw.textbbox((0, 0), author_text, font=font_author)
        aw = a_bbox[2] - a_bbox[0]
        ax = safe_center_x - aw // 2
        draw.text((ax + SHADOW_OFFSET, y + SHADOW_OFFSET), author_text,
                  font=font_author, fill=(0, 0, 0, 160))
        draw.text((ax, y), author_text, font=font_author, fill=(210, 210, 210, 255))

    return np.array(frame.convert("RGB"))


# ── Main render function ─────────────────────────────────────────────────────
def render_quote_video(quote_text, author_text, bg_image_path, bg_music_path, output_path):
    """
    Render a 10-second portrait quote video.

    Parameters
    ----------
    quote_text     : str  — the quote body
    author_text    : str  — formatted author string (e.g. "— Buddha") or ""
    bg_image_path  : str  — path to background image (ibg1.png etc.)
    bg_music_path  : str  — path to background music (mbg1.mp3 etc.)
    output_path    : str  — destination .mp4 path
    """
    bg_img = _load_bg(bg_image_path)
    frame  = _build_quote_frame(bg_img, quote_text, author_text)

    # Static image clip for full 10 seconds
    video_clip = ImageClip(frame).set_duration(VIDEO_DURATION)

    # Audio: trim to 10s, loop if shorter
    audio = AudioFileClip(bg_music_path)
    if audio.duration < VIDEO_DURATION:
        from moviepy.audio.AudioClip import concatenate_audioclips
        loops = int(VIDEO_DURATION // audio.duration) + 1
        audio = concatenate_audioclips([audio] * loops)
    audio = audio.subclip(0, VIDEO_DURATION)

    video_clip = video_clip.set_audio(audio)

    out = Path(output_path)
    video_clip.write_videofile(
        str(out),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(out.parent / "_tmp_audio.m4a"),
        remove_temp=True,
        logger=None,
    )

    audio.close()
    video_clip.close()
