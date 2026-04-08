# Omega AI (Phase-Wise Voice Assistant)

This project implements your Omega build plan in the same phase order, from a basic wake-word assistant to optional GPT-based intent parsing.

## Stack

- Python
- SpeechRecognition
- pyttsx3
- rapidfuzz (flexible command matching)
- requests (OpenWeather + Google search URL handling)
- keyboard, pyautogui (system/media control)
- openai (optional Phase 5)

## Project Files

- `omega.py`: Main assistant
- `requirements.txt`: Python dependencies
- `.env.example`: API key template

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. (Linux) Install audio/system helper packages if needed:

```bash
sudo apt update
sudo apt install -y portaudio19-dev espeak-ng python3-tk python3-dev
```

4. (Optional for Phase 3 + 5) add env vars:

```bash
cp .env.example .env
export OPENWEATHER_API_KEY="your_key"
export OPENAI_API_KEY="your_key"
```

## Run

Without GPT parser:

```bash
python omega.py
```

Without microphone (text mode):

```bash
python omega.py --text-mode
```

With GPT parser (Phase 5):

```bash
python omega.py --use-gpt
```

With GPT + text mode:

```bash
python omega.py --use-gpt --text-mode
```

Note:
- If no microphone is detected, Omega automatically falls back to text mode.

## Phase Coverage

### Phase 1 - Basic Assistant

Goal: Voice -> command -> action

Implemented:
- Wake word: `Omega`
- Commands:
	- open chrome
	- open spotify
	- tell time

### Phase 2 - Smart Commands

Goal: Understand flexible commands such as:
- `Omega, can you open chrome?`

Implemented:
- Fuzzy matching via `rapidfuzz`
- Rule-based intent extraction for natural phrasing

### Phase 3 - Real-world Tasks

Implemented:
- Weather via OpenWeather API
- Search via Google

Flow:
- Detect weather intent
- Extract city (or ask follow-up)
- Call API
- Speak result

### Phase 4 - System Control

Implemented:
- Volume up/down
- Mute toggle
- Open apps
- Close apps
- Play/pause media

Primary Linux methods:
- `pactl` or `amixer` for volume
- `playerctl` for media

Fallback methods:
- `keyboard` and `pyautogui`

### Phase 5 - AI Brain (Optional)

Implemented:
- GPT-based intent parsing when `--use-gpt` is enabled
- Falls back to local parser if GPT is unavailable or fails

## Brain Prompt Used

The script includes your structured brain prompt concept for GPT parsing:

- concise behavior
- JSON-only output
- intent + parameters
- action schema for app open, search, weather, media, and time

## Example Commands

- `Omega open chrome`
- `Omega can you open spotify`
- `Omega what time is it`
- `Omega search latest AI news`
- `Omega what's temperature in Delhi`
- `Omega volume up`
- `Omega pause music`
- `Omega close app spotify`
- `Omega stop`