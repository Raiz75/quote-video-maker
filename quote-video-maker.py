import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import random
import re
import os
from pathlib import Path
from datetime import datetime
from render_quote import render_quote_video

BASE_DIR   = Path(__file__).parent
BG_IMAGE_DIR = BASE_DIR / "bg-image"
BG_MUSIC_DIR = BASE_DIR / "bg-music"
OUTPUT_DIR   = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MUSIC_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".aac"}

STATE_FILE = BASE_DIR / "state.json"

def _load_batch_number() -> int:
    """Read next_batch from state.json. Returns 1 if file doesn't exist."""
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return int(data.get("next_batch", 1))
    except Exception:
        return 1

def _save_batch_number(n: int):
    """Persist next_batch to state.json."""
    STATE_FILE.write_text(json.dumps({"next_batch": n}, indent=2), encoding="utf-8")

MASTER_PROMPT = """You are a viral quote generator for social media (YouTube Shorts, TikTok, Reels).

BEFORE GENERATING, ask the user:

"What theme would you like? Choose a number:

1. Self-Love — gentle, affirming, nurturing
2. Healing — calm, reassuring, hopeful
3. Overthinking — anxious, reflective, relatable
4. Loneliness — quiet, emotional, isolating
5. Moving On — freeing, forward-looking, empowering
6. Late Night Thoughts — raw, vulnerable, intimate
7. Unspoken Feelings — subtle, deep, emotionally restrained
8. Trust Issues — guarded, cautious, honest
9. Fake People — exposing, direct, slightly harsh
10. Glow Up — confident, transformative, empowering
11. Silent Battles — heavy, personal, unseen struggle
12. Regret — reflective, emotional, bittersweet
13. Letting Go — peaceful, accepting, mature
14. Heartbreak Recovery — healing, soft, rebuilding
15. Inner Peace — calm, grounded, mindful
16. Reality Check — blunt, eye-opening, honest
17. Maturity — wise, grounded, self-aware
18. Detachment — emotionally distant, controlled, powerful
19. Energy Protection — protective, self-prioritizing, firm
20. No Contact — disciplined, restrained, self-respecting
21. Motivation When Tired — supportive, pushing, understanding
22. Lost in Life — confused, searching, introspective
23. Purpose — meaningful, inspiring, direction-focused
24. Time & Life — reflective, philosophical, aware
25. Karma — poetic justice, subtle, confident
26. Revenge Glow — quiet success, proving through action
27. Minimalist — short, clean, impactful
28. Dark Truth — uncomfortable, real, brutally honest
29. Hope — uplifting, light, reassuring
30. Second Chances — forgiving, reflective, growth-focused"

Wait for the user's number. Then generate exactly 21 quotes based on that theme.

---

TASK:
Generate 21 short, emotional, highly relatable quotes. Each quote is its OWN independent piece of content — never read together as a list.

ATTRIBUTION RULES:
- At least 7 of 21 must be ORIGINAL (author = null).
- Remaining may use REAL, verifiably attributed quotes with correct author names.
- Do NOT invent fake authors. When in doubt, make it original.

CORE REQUIREMENTS:
- Feel PERSONAL — speak directly to one person using "you," "your," "I."
- Feel RELATABLE — the reader feels seen instantly.
- Feel SHAREABLE — the reader wants to send it to someone specific.
- 1–2 sentences maximum per quote.
- Emotionally impactful and scroll-stopping.
- No clichés unless reworded into a specific human behavior.

CONTENT RULES (each quote is its own post):

1. CURIOSITY GAP: First 5 words must be intriguing and incomplete. No closed, declarative openers.

2. ONE EMOTION ONLY: Pick one dominant emotion per quote.
   Allowed: anger, sadness, relief, hope, exhaustion, acceptance, defiance, grief, longing, peace, regret, nostalgia, fear, calm.

3. SENTENCE COUNT: At least 14 of 21 must be ONE sentence only. Use commas, em-dashes, or semicolons for internal structure.

4. EMOTIONAL DISTINCTNESS: No two quotes may express the same emotional truth.

5. WEIGHTED ENDING: Last 3–4 words must land with weight or an unexpected emotional turn.

6. NO TOXIC POSITIVITY: Name the feeling. Do not try to fix it.
   Banned: "you can do it," "keep going," "everything happens for a reason" — unless heavily rewritten.

7. LIKING THRESHOLD: Would 70%+ of people in this emotional state say "yes, exactly" within 2 seconds? If no → rewrite.

8. CONCRETE DETAIL: Every quote must contain one concrete emotional anchor — an action, time, habit, silence, phone, mirror, bed, window, text message, sound, or room. No abstract-only statements.

9. PERSONAL TEST: If replacing "you" with "people" still works → rewrite it. Must feel addressed to one person.

STYLE MIX (across all 21):
- Direct address ("You...") — ~8 quotes
- First-person confession ("I...") — ~6 quotes
- Universal truth (no pronoun, implied "you") — ~7 quotes

HOOK PATTERNS — use for at least 10 of 21:
- "The moment you realize..."
- "Nobody talks about how..."
- "You don't miss..."
- "The quietest kind of..."
- "One day you'll wake up and..."
- "The version of you that..."
- "You know it's bad when..."
- "What nobody tells you about..."
- "The part that hurts most isn't..."
- "You stopped [verb]ing and that's when..."

CLICHÉ REPLACEMENTS — replace clichés with specific human behaviors:
- "It is what it is" → "You stopped explaining."
- "Let go of what no longer serves you" → "You can love the memory and still lock the door."
- "Actions speak louder than words" → "Their silence was louder than any lie."
- "Healing takes time" → "You're not late. You're just tired."
- "Everything will be okay" → "You closed the tab and stared at the ceiling."
- "You deserve better" → "You kept the thread unread for three days."

NEVER INCLUDE:
- Brand names or platform names
- Political figures or partisan language
- Content romanticizing self-harm or substance abuse
- Anything that would be flagged or removed on TikTok, Reels, or Shorts

OUTPUT FORMAT (STRICT):
Return ONLY valid JSON. No explanations. No preamble. No markdown fences. No extra text.

{
  "quotes": [
    {
      "text": "Quote here",
      "author": null
    },
    {
      "text": "Quote here",
      "author": "Author Name"
    }
  ]
}"""


def _scan_assets(folder, exts):
    """Return sorted list of files in folder matching extensions."""
    try:
        return sorted([f for f in folder.iterdir() if f.suffix.lower() in exts])
    except Exception:
        return []


def _parse_quotes(raw_json: str):
    """
    Parse the JSON blob, clean it, and return list of
    {"text": str, "author": str|None} dicts.
    Strips keys/values of extra whitespace.
    """
    data = json.loads(raw_json.strip())
    quotes = data.get("quotes", [])
    result = []
    for q in quotes:
        text = (q.get("text") or "").strip()
        author = (q.get("author") or "").strip() or None
        if text:
            result.append({"text": text, "author": author})
    return result


def _format_author(author):
    """Return '— Author' or '' if None."""
    return f"— {author}" if author else ""


def _safe_filename(text, max_len=50):
    """Sanitize quote text into a safe filename segment."""
    cleaned = re.sub(r'[<>:"/\\|?*\n]', '', text)
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned[:max_len]


class QuoteVideoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quote Video Maker")
        self.root.geometry("700x720")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)

        self.status_var  = tk.StringVar(value="Ready.")
        self.progress_var = tk.DoubleVar(value=0)
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TProgressbar",
                        troughcolor="#16213e", background="#e94560", thickness=8)

        # Title
        tk.Label(self.root, text="QUOTE VIDEO MAKER",
                 font=("Consolas", 16, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=(18, 2))
        tk.Label(self.root, text="TikTok / YT Shorts  •  1080×1920  •  10s",
                 font=("Consolas", 9), bg="#1a1a2e", fg="#666").pack(pady=(0, 8))

        # ── Copy Master Prompt button ────────────────────────────────────────
        self.copy_btn = tk.Button(
            self.root, text="📋  COPY MASTER PROMPT",
            command=self._copy_master_prompt,
            bg="#0f3460", fg="#a8d8ea",
            font=("Consolas", 9, "bold"),
            relief="flat", cursor="hand2",
            padx=14, pady=5
        )
        self.copy_btn.pack(pady=(0, 12))

        # ── JSON input area ──────────────────────────────────────────────────
        json_frame = tk.LabelFrame(self.root, text=" Quotes JSON ",
                                   font=("Consolas", 9),
                                   bg="#16213e", fg="#aaa",
                                   bd=1, relief="flat", padx=10, pady=8)
        json_frame.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        json_scroll = tk.Scrollbar(json_frame)
        json_scroll.pack(side="right", fill="y")

        self.json_text = tk.Text(
            json_frame, height=14,
            bg="#0d0d1a", fg="#a8d8a8",
            font=("Consolas", 9),
            insertbackground="#e94560",
            bd=0, highlightthickness=0,
            yscrollcommand=json_scroll.set
        )
        self.json_text.pack(fill="both", expand=True)
        json_scroll.config(command=self.json_text.yview)

        # Hint
        hint_row = tk.Frame(self.root, bg="#1a1a2e")
        hint_row.pack(fill="x", padx=20, pady=(0, 6))
        tk.Label(hint_row,
                 text='Paste the full {"quotes":[...]} JSON above. Author nulls are handled automatically.',
                 font=("Consolas", 8), bg="#1a1a2e", fg="#555",
                 wraplength=660, anchor="w", justify="left").pack(side="left")

        # ── Asset status row ─────────────────────────────────────────────────
        asset_frame = tk.LabelFrame(self.root, text=" Asset Status ",
                                    font=("Consolas", 9),
                                    bg="#16213e", fg="#aaa",
                                    bd=1, relief="flat", padx=10, pady=6)
        asset_frame.pack(fill="x", padx=20, pady=(0, 8))

        self.img_count_var   = tk.StringVar()
        self.music_count_var = tk.StringVar()
        self._refresh_asset_counts()

        tk.Label(asset_frame, textvariable=self.img_count_var,
                 font=("Consolas", 9), bg="#16213e", fg="#7fcc7f").pack(anchor="w")
        tk.Label(asset_frame, textvariable=self.music_count_var,
                 font=("Consolas", 9), bg="#16213e", fg="#7fcc7f").pack(anchor="w")

        # ── Progress + status ────────────────────────────────────────────────
        prog_frame = tk.Frame(self.root, bg="#1a1a2e")
        prog_frame.pack(fill="x", padx=20, pady=(0, 4))
        ttk.Progressbar(prog_frame, variable=self.progress_var,
                        maximum=100, style="TProgressbar").pack(fill="x")

        tk.Label(self.root, textvariable=self.status_var,
                 font=("Consolas", 9), bg="#1a1a2e", fg="#888").pack(pady=(2, 4))

        # ── Log ──────────────────────────────────────────────────────────────
        log_frame = tk.LabelFrame(self.root, text=" Log ",
                                  font=("Consolas", 9),
                                  bg="#16213e", fg="#aaa",
                                  bd=1, relief="flat", padx=10, pady=6)
        log_frame.pack(fill="x", padx=20, pady=(0, 8))

        log_scroll = tk.Scrollbar(log_frame)
        log_scroll.pack(side="right", fill="y")

        self.log_box = tk.Text(log_frame, height=5,
                               bg="#0d0d1a", fg="#7fcc7f",
                               font=("Consolas", 8),
                               bd=0, highlightthickness=0,
                               state="disabled",
                               yscrollcommand=log_scroll.set)
        self.log_box.pack(fill="both", expand=True)
        log_scroll.config(command=self.log_box.yview)

        # ── Generate button ──────────────────────────────────────────────────
        self.gen_btn = tk.Button(
            self.root, text="  GENERATE VIDEOS  ",
            command=self.start_generation,
            bg="#e94560", fg="white",
            font=("Consolas", 12, "bold"),
            relief="flat", cursor="hand2",
            padx=20, pady=10
        )
        self.gen_btn.pack(pady=(0, 16))

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _copy_master_prompt(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(MASTER_PROMPT)
        self.root.update()
        # Flash button text to confirm
        self.copy_btn.config(text="✓  COPIED!", bg="#1a472a", fg="#7fcc7f")
        self.root.after(2000, lambda: self.copy_btn.config(
            text="📋  COPY MASTER PROMPT", bg="#0f3460", fg="#a8d8ea"))

    def _refresh_asset_counts(self):
        imgs   = _scan_assets(BG_IMAGE_DIR, IMAGE_EXTS)
        musics = _scan_assets(BG_MUSIC_DIR, MUSIC_EXTS)
        self.img_count_var.set(
            f"  Background images : {len(imgs)} found  ({BG_IMAGE_DIR.name}/)")
        self.music_count_var.set(
            f"  Background music  : {len(musics)} found  ({BG_MUSIC_DIR.name}/)")

    def log(self, msg):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # ── Generation pipeline ──────────────────────────────────────────────────
    def start_generation(self):
        raw = self.json_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("Empty Input", "Please paste your quotes JSON.")
            return

        # Parse & validate
        try:
            quotes = _parse_quotes(raw)
        except Exception as e:
            messagebox.showerror("JSON Error", f"Could not parse JSON:\n{e}")
            return

        if not quotes:
            messagebox.showwarning("No Quotes", "No valid quotes found in JSON.")
            return

        # Check assets
        imgs   = _scan_assets(BG_IMAGE_DIR, IMAGE_EXTS)
        musics = _scan_assets(BG_MUSIC_DIR, MUSIC_EXTS)
        if not imgs:
            messagebox.showerror("No Images",
                f"No background images found in:\n{BG_IMAGE_DIR}")
            return
        if not musics:
            messagebox.showerror("No Music",
                f"No background music found in:\n{BG_MUSIC_DIR}")
            return

        self.gen_btn.config(state="disabled")
        self.progress_var.set(0)
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(quotes, imgs, musics),
            daemon=True
        )
        thread.start()

    def _run_pipeline(self, quotes, imgs, musics):
        total     = len(quotes)
        processed = 0
        skipped   = 0

        batch_offset = _load_batch_number()          # first batch number for this run
        batches_in_run = (len(quotes) + 2) // 3      # how many groups of 3 this run produces
        _save_batch_number(batch_offset + batches_in_run)  # persist next run's starting batch

        for i, q in enumerate(quotes):
            text   = q["text"]
            author = _format_author(q["author"])

            self.status_var.set(f"[{i+1}/{total}] Rendering…")
            self.log(f"\n [{i+1}/{total}] {text[:60]}{'…' if len(text)>60 else ''}")
            if author:
                self.log(f"          {author}")

            # Random picks
            bg_img   = random.choice(imgs)
            bg_music = random.choice(musics)
            self.log(f"  img: {bg_img.name}  |  music: {bg_music.name}")

            # Build filename: timestamp + batch + slot
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            batch    = batch_offset + (i // 3)
            slot     = (i % 3) + 1
            out_path = OUTPUT_DIR / f"{ts}_b{batch:04d}_s{slot}.mp4"

            try:
                render_quote_video(
                    quote_text    = text,
                    author_text   = author,
                    bg_image_path = str(bg_img),
                    bg_music_path = str(bg_music),
                    output_path   = str(out_path),
                )
                self.log(f"  ✓ Saved: {out_path.name}")
                processed += 1
            except Exception as e:
                self.log(f"  ✗ ERROR: {e}")
                skipped += 1

            self.progress_var.set(((i + 1) / total) * 100)

        self.status_var.set(
            f"Done! {processed} video(s) exported, {skipped} failed.")
        self.log(f"\nAll done. Processed: {processed} | Failed: {skipped}")
        self.log(f"Output folder: {OUTPUT_DIR}")
        self.root.after(0, lambda: self.gen_btn.config(state="normal"))


if __name__ == "__main__":
    root = tk.Tk()
    app  = QuoteVideoApp(root)
    root.mainloop()
