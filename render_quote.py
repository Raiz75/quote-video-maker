import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import AudioFileClip, ImageSequenceClip

# ── Config ───────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 24,
        "duration": 5,
        "typing_duration": 2.0,
    },
    "fonts": {
        "quote_size": 68,
        "author_size": 42,
        "line_spacing": 1.45,
        "author_gap": 40,
    },
    "visual": {
        "shadow_offset": 3,
        "dark_overlay_opacity": 110,
        "zoom_start": 1.0,
        "zoom_end": 1.10,
        "pad_left": 60,
        "right_button_margin": 200,
    },
}

def _load_config():
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            user_config = json.load(f)
    except Exception:
        user_config = {}
    config = {}
    for section, defaults in DEFAULT_CONFIG.items():
        config[section] = {**defaults, **(user_config.get(section) or {})}
    return config

CONFIG = _load_config()

VIDEO_WIDTH   = CONFIG["video"]["width"]
VIDEO_HEIGHT  = CONFIG["video"]["height"]
VIDEO_FPS     = CONFIG["video"]["fps"]
VIDEO_DURATION = CONFIG["video"]["duration"]
TYPING_DURATION = CONFIG["video"]["typing_duration"]
HOLD_DURATION = VIDEO_DURATION - TYPING_DURATION

QUOTE_FONT_SIZE  = CONFIG["fonts"]["quote_size"]
AUTHOR_FONT_SIZE = CONFIG["fonts"]["author_size"]
LINE_SPACING     = CONFIG["fonts"]["line_spacing"]
AUTHOR_GAP       = CONFIG["fonts"]["author_gap"]

SHADOW_OFFSET = CONFIG["visual"]["shadow_offset"]
ZOOM_START    = CONFIG["visual"]["zoom_start"]
ZOOM_END      = CONFIG["visual"]["zoom_end"]
PAD_LEFT      = CONFIG["visual"]["pad_left"]
RIGHT_BUTTON_MARGIN = CONFIG["visual"]["right_button_margin"]
DARK_OVERLAY_OPACITY = CONFIG["visual"]["dark_overlay_opacity"]
PAD_RIGHT = RIGHT_BUTTON_MARGIN + 40

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

def _get_font(size, bold=True):
    paths = FONT_PATHS_BOLD if bold else FONT_PATHS_REGULAR
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def _wrap_text(text, font, max_width, draw):
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

def _precompute_text_structure(quote_text):
    full_wrapped_lines = []
    words_with_positions = []

    quote_lines = quote_text.split('\n') if '\n' in quote_text else [quote_text]
    font_quote = _get_font(QUOTE_FONT_SIZE, bold=True)
    max_w = VIDEO_WIDTH - PAD_LEFT - PAD_RIGHT
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)

    for line in quote_lines:
        wrapped = _wrap_text(line, font_quote, max_w, draw)
        full_wrapped_lines.extend(wrapped)

    for line_idx, line in enumerate(full_wrapped_lines):
        for word in line.split():
            words_with_positions.append((word, line_idx))

    return full_wrapped_lines, words_with_positions

def _apply_zoom(bg_img, progress):
    """
    Apply Ken Burns zoom to background image.
    progress: 0.0 to 1.0 over video duration.
    Returns zoomed PIL Image.
    """
    scale = ZOOM_START + (ZOOM_END - ZOOM_START) * progress
    new_w = int(VIDEO_WIDTH * scale)
    new_h = int(VIDEO_HEIGHT * scale)
    zoomed = bg_img.resize((new_w, new_h), Image.LANCZOS)
    
    # Crop to original dimensions (center crop)
    left = (new_w - VIDEO_WIDTH) // 2
    top = (new_h - VIDEO_HEIGHT) // 2
    return zoomed.crop((left, top, left + VIDEO_WIDTH, top + VIDEO_HEIGHT))

def _load_bg(bg_path):
    img = Image.open(bg_path).convert("RGB")
    img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS)
    dark = Image.new("RGBA", img.size, (0, 0, 0, DARK_OVERLAY_OPACITY))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, dark)
    return img.convert("RGB")

def _render_text_layer(full_wrapped_lines, words_with_positions, reveal_count, author_text):
    text_layer = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    font_quote = _get_font(QUOTE_FONT_SIZE, bold=True)
    font_author = _get_font(AUTHOR_FONT_SIZE, bold=False)
    max_w = VIDEO_WIDTH - PAD_LEFT - PAD_RIGHT
    safe_center_x = PAD_LEFT + max_w // 2

    visible_words = words_with_positions[:reveal_count]
    if not visible_words:
        return np.array(text_layer)

    visible_lines = []
    current_line_words = []
    last_line_idx = visible_words[0][1]
    for word, line_idx in visible_words:
        if line_idx != last_line_idx:
            if current_line_words:
                visible_lines.append(' '.join(current_line_words))
            current_line_words = [word]
            last_line_idx = line_idx
        else:
            current_line_words.append(word)
    if current_line_words:
        visible_lines.append(' '.join(current_line_words))

    line_h = int(QUOTE_FONT_SIZE * LINE_SPACING)
    total_q_h = line_h * len(full_wrapped_lines)

    a_h = 0
    if author_text:
        a_bbox = draw.textbbox((0, 0), author_text, font=font_author)
        a_h = a_bbox[3] - a_bbox[1]
    block_h = total_q_h + (AUTHOR_GAP + a_h if author_text else 0)
    y = (VIDEO_HEIGHT - block_h) // 2

    for line in visible_lines:
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        lw = bbox[2] - bbox[0]
        x = safe_center_x - lw // 2
        draw.text((x + SHADOW_OFFSET, y + SHADOW_OFFSET), line,
                  font=font_quote, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font_quote, fill=(255, 255, 255, 255))
        y += line_h

    if author_text and reveal_count >= len(words_with_positions):
        y = (VIDEO_HEIGHT - block_h) // 2 + total_q_h + AUTHOR_GAP
        a_bbox = draw.textbbox((0, 0), author_text, font=font_author)
        aw = a_bbox[2] - a_bbox[0]
        ax = safe_center_x - aw // 2
        draw.text((ax + SHADOW_OFFSET, y + SHADOW_OFFSET), author_text,
                  font=font_author, fill=(0, 0, 0, 160))
        draw.text((ax, y), author_text, font=font_author,
                  fill=(210, 210, 210, 255))

    return np.array(text_layer)

def _composite_text_on_bg(bg_pil, text_layer_np):
    bg = bg_pil.convert("RGBA")
    text = Image.fromarray(text_layer_np)
    composited = Image.alpha_composite(bg, text)
    return np.array(composited.convert("RGB"))

def _get_typewriter_timing(total_words):
    timing = []
    for reveal_count in range(1, total_words + 1):
        timing.append((reveal_count, TYPING_DURATION / total_words))
    timing.append((total_words, HOLD_DURATION))
    return timing

def render_quote_video(quote_text, author_text, bg_image_path, bg_music_path, output_path):
    bg_img = _load_bg(bg_image_path)

    full_wrapped_lines, words_with_positions = _precompute_text_structure(quote_text)
    total_words = len(words_with_positions)
    if total_words == 0:
        raise ValueError("No words in quote text")

    text_layers = {}
    for rc in range(1, total_words + 1):
        text_layers[rc] = _render_text_layer(
            full_wrapped_lines, words_with_positions, rc, author_text)

    timing = _get_typewriter_timing(total_words)
    zoomed_frames = []
    time_per_frame = 1.0 / VIDEO_FPS
    current_time = 0.0

    for reveal_count, duration in timing:
        text_layer = text_layers[reveal_count]
        frame_duration_frames = int(duration * VIDEO_FPS)
        for frame_idx in range(frame_duration_frames):
            t = current_time + frame_idx * time_per_frame
            progress = min(t / VIDEO_DURATION, 1.0)
            zoomed_bg = _apply_zoom(bg_img, progress)
            frame = _composite_text_on_bg(zoomed_bg, text_layer)
            zoomed_frames.append(frame)
        current_time += duration

    final_clip = ImageSequenceClip(zoomed_frames, fps=VIDEO_FPS)
    
    # Audio handling (unchanged)
    audio = AudioFileClip(bg_music_path)
    if audio.duration < VIDEO_DURATION:
        from moviepy.audio.AudioClip import concatenate_audioclips
        loops = int(VIDEO_DURATION // audio.duration) + 1
        audio = concatenate_audioclips([audio] * loops)
    audio = audio.subclip(0, VIDEO_DURATION)
    
    final_clip = final_clip.set_audio(audio)
    
    out = Path(output_path)
    final_clip.write_videofile(
        str(out),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(out.parent / "_tmp_audio.m4a"),
        remove_temp=True,
        logger=None,
    )
    
    audio.close()
    final_clip.close()