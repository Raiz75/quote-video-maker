import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    ImageSequenceClip,
    concatenate_videoclips,
)

# ── Constants ────────────────────────────────────────────────────────────────
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS    = 24
VIDEO_DURATION = 5  # seconds

QUOTE_FONT_SIZE  = 68
AUTHOR_FONT_SIZE = 42
LINE_SPACING = 1.45
AUTHOR_GAP   = 40
SHADOW_OFFSET = 3

# Typewriter timing
TYPING_DURATION = 2.0  # seconds to type all words
HOLD_DURATION = VIDEO_DURATION - TYPING_DURATION  # ~3 seconds

# Ken Burns zoom
ZOOM_START = 1.0
ZOOM_END = 1.10  # 10% zoom over full duration

# Safe zone for platform buttons (right side)
RIGHT_BUTTON_MARGIN = 200
PAD_LEFT  = 60
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

def _split_into_words_per_line(lines):
    """Convert list of text lines into list of word lists per line."""
    return [[word for word in line.split()] for line in lines]

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
    dark = Image.new("RGBA", img.size, (0, 0, 0, 110))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, dark)
    return img.convert("RGB")

def _build_quote_frame_with_reveal(bg_img, quote_lines, author_text, reveal_word_count):
    """
    Render a single frame showing only first N words of the quote.
    quote_lines: list of strings, each line fully typed but we'll reveal by word count.
    """
    frame = bg_img.copy().convert("RGBA")
    draw = ImageDraw.Draw(frame)
    
    font_quote = _get_font(QUOTE_FONT_SIZE, bold=True)
    font_author = _get_font(AUTHOR_FONT_SIZE, bold=False)
    
    max_w = VIDEO_WIDTH - PAD_LEFT - PAD_RIGHT
    safe_center_x = PAD_LEFT + max_w // 2
    
    # Wrap quote lines fully (word wrap based on max width)
    full_wrapped_lines = []
    for line in quote_lines:
        wrapped = _wrap_text(line, font_quote, max_w, draw)
        full_wrapped_lines.extend(wrapped)
    
    # Flatten all words across lines with position tracking
    words_with_positions = []  # (word, line_index)
    for line_idx, line in enumerate(full_wrapped_lines):
        for word in line.split():
            words_with_positions.append((word, line_idx))
    
    # Truncate to reveal count
    visible_words = words_with_positions[:reveal_word_count]
    if not visible_words:
        return np.array(frame.convert("RGB"))
    
    # Reconstruct visible lines
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
    
    # Calculate vertical positions
    line_h = int(QUOTE_FONT_SIZE * LINE_SPACING)
    total_q_h = line_h * len(full_wrapped_lines)  # Use full height for centering
    
    a_h = 0
    if author_text:
        a_bbox = draw.textbbox((0, 0), author_text, font=font_author)
        a_h = a_bbox[3] - a_bbox[1]
    
    block_h = total_q_h + (AUTHOR_GAP + a_h if author_text else 0)
    y = (VIDEO_HEIGHT - block_h) // 2
    
    # Draw visible quote lines
    for line in visible_lines:
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        lw = bbox[2] - bbox[0]
        x = safe_center_x - lw // 2
        draw.text((x + SHADOW_OFFSET, y + SHADOW_OFFSET), line,
                  font=font_quote, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font_quote, fill=(255, 255, 255, 255))
        y += line_h
    
    # Draw author (only if all quote words are visible)
    if author_text and reveal_word_count >= len(words_with_positions):
        y = (VIDEO_HEIGHT - block_h) // 2 + total_q_h + AUTHOR_GAP
        a_bbox = draw.textbbox((0, 0), author_text, font=font_author)
        aw = a_bbox[2] - a_bbox[0]
        ax = safe_center_x - aw // 2
        draw.text((ax + SHADOW_OFFSET, y + SHADOW_OFFSET), author_text,
                  font=font_author, fill=(0, 0, 0, 160))
        draw.text((ax, y), author_text, font=font_author, fill=(210, 210, 210, 255))
    
    return np.array(frame.convert("RGB"))

def _generate_typewriter_frames(bg_img, quote_text, author_text):
    """
    Generate list of frames for typewriter animation.
    Returns list of (frame_array, duration_seconds) for each step.
    """
    # Split quote into lines for structure
    quote_lines = quote_text.split('\n') if '\n' in quote_text else [quote_text]
    
    # Count total words
    words = quote_text.split()
    total_words = len(words)
    
    if total_words == 0:
        return []
    
    # Each step reveals 1 word
    frames = []
    
    for reveal_count in range(1, total_words + 1):
        # Calculate frame duration: each word gets equal time within TYPING_DURATION
        frame_duration = TYPING_DURATION / total_words
        frame = _build_quote_frame_with_reveal(bg_img, quote_lines, author_text, reveal_count)
        frames.append((frame, frame_duration))
    
    # Add hold frames (same as final frame)
    hold_frame = _build_quote_frame_with_reveal(bg_img, quote_lines, author_text, total_words)
    frames.append((hold_frame, HOLD_DURATION))
    
    return frames

def render_quote_video(quote_text, author_text, bg_image_path, bg_music_path, output_path):
    """
    Render 5-second portrait video with word-level typewriter animation
    and Ken Burns zoom on background.
    """
    bg_img = _load_bg(bg_image_path)
    
    # Generate all frames with typewriter progression
    typewriter_frames = _generate_typewriter_frames(bg_img, quote_text, author_text)
    
    if not typewriter_frames:
        raise ValueError("No frames generated — quote text may be empty")
    
    # Write frames to temporary directory
    temp_dir = tempfile.mkdtemp()
    frame_paths = []
    
    for idx, (frame_array, duration) in enumerate(typewriter_frames):
        # Apply Ken Burns zoom per frame based on cumulative time
        # For simplicity, we'll handle zoom in MoviePy via a resize effect
        # But PIL zoom per frame is expensive; better to composite after
        frame_img = Image.fromarray(frame_array)
        frame_path = os.path.join(temp_dir, f"frame_{idx:04d}.png")
        frame_img.save(frame_path)
        frame_paths.append(frame_path)
    
    # Create clips with correct durations
    clips = []
    for idx, (frame_path, (_, duration)) in enumerate(zip(frame_paths, typewriter_frames)):
        clip = ImageClip(frame_path).set_duration(duration)
        # Apply Ken Burns zoom using MoviePy's resize effect
        # Progress = start + (end - start) * (time_in_clip / total_time)
        # We'll apply to each clip with its midpoint time
        clips.append(clip)
    
    # Concatenate all clips
    video_clip = concatenate_videoclips(clips, method="compose")
    
    # Apply Ken Burns zoom as a single effect across entire video
    def ken_burns_effect(get_frame, t):
        """Apply zoom based on global time t (0 to VIDEO_DURATION)."""
        frame = get_frame(t)
        progress = t / VIDEO_DURATION
        scale = ZOOM_START + (ZOOM_END - ZOOM_START) * progress
        
        h, w = frame.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)
        
        # Resize using MoviePy's built-in (approximate)
        from moviepy.video.fx.resize import resize
        resized = resize(lambda t: frame, newsize=(new_w, new_h))
        # This is complex; simpler: pre-render zoomed frames
        return frame
        
    # Alternative: pre-render zoomed frames (more reliable)
    # Regenerate frames with zoom applied per frame
    zoomed_frames = []
    total_frames = sum(int(dur * VIDEO_FPS) for _, dur in typewriter_frames)
    time_per_frame = 1.0 / VIDEO_FPS
    current_time = 0
    
    for frame_array, duration in typewriter_frames:
        frame_duration_frames = int(duration * VIDEO_FPS)
        for frame_idx in range(frame_duration_frames):
            t = current_time + frame_idx * time_per_frame
            progress = min(t / VIDEO_DURATION, 1.0)
            
            # Apply zoom to background for this specific frame
            zoomed_bg = _apply_zoom(bg_img, progress)
            # Re-render quote on zoomed background with same reveal count
            # This is expensive but accurate
            quote_lines = quote_text.split('\n') if '\n' in quote_text else [quote_text]
            words = quote_text.split()
            reveal_count = min(len(words), int((t / TYPING_DURATION) * len(words)) + 1)
            if reveal_count > len(words):
                reveal_count = len(words)
            elif t > TYPING_DURATION:
                reveal_count = len(words)
            
            frame = _build_quote_frame_with_reveal(zoomed_bg, quote_lines, author_text, reveal_count)
            zoomed_frames.append(frame)
        current_time += duration
    
    # Use zoomed frames directly
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
    
    # Cleanup
    audio.close()
    final_clip.close()
    for f in frame_paths:
        try:
            os.remove(f)
        except:
            pass
    try:
        os.rmdir(temp_dir)
    except:
        pass