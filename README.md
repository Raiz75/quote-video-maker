# Quote Video Maker

Generates 1080×1920 vertical quote videos with typewriter animation, Ken Burns zoom, and background music — for TikTok, YouTube Shorts, and Instagram Reels.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

1. Run `python quote-video-maker.py` (or double-click `run_quote-video-maker.vbs`)
2. Click **COPY MASTER PROMPT** and paste it into an LLM (ChatGPT, Claude, etc.)
3. The LLM returns a JSON array of quotes — paste it into the text area
4. Click **GENERATE VIDEOS** — videos are saved to `output/`
5. Click **CANCEL** mid-batch to stop after the current quote

## Configuration

Edit `config.json` to adjust:
- **video**: resolution, fps, duration, typing speed
- **fonts**: quote/author size, line spacing
- **visual**: zoom range, padding, dark overlay opacity

## Project Structure

```
├── quote-video-maker.py    GUI app
├── render_quote.py         Video rendering engine
├── config.json             Settings
├── prompts/
│   └── master_prompt.txt   LLM prompt for quote generation
├── bg-image/               Background images (16:9 portrait)
├── bg-music/               Background music tracks
├── output/                 Generated videos
├── yt-files/               YouTube thumbnails, logos
└── requirements.txt        Dependencies
```
