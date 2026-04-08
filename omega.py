#!/usr/bin/env python3
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import pyttsx3
import requests
import speech_recognition as sr
from rapidfuzz import fuzz

try:
    from openai import OpenAI
except Exception:  # Optional dependency for Phase 5
    OpenAI = None


WAKE_WORD = "omega"


@dataclass
class Action:
    name: str
    params: Dict[str, Any]


class OmegaAssistant:
    def __init__(self, wake_word: str = WAKE_WORD, use_gpt: bool = False):
        self.wake_word = wake_word.lower()
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.use_gpt = use_gpt
        self.openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

    def speak(self, text: str) -> None:
        print(f"Omega: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self, timeout: int = 5, phrase_time_limit: int = 8) -> str:
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
            print("Listening...")
            audio = self.recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )

        try:
            text = self.recognizer.recognize_google(audio).lower().strip()
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            self.speak("Speech service is unavailable right now.")
            return ""

    def has_wake_word(self, text: str) -> bool:
        return self.wake_word in text

    def normalize(self, text: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def fuzzy_contains(self, text: str, target: str, threshold: int = 76) -> bool:
        if target in text:
            return True
        words = text.split()
        target_words = target.split()
        if len(words) < len(target_words):
            return fuzz.ratio(text, target) >= threshold

        for i in range(len(words) - len(target_words) + 1):
            chunk = " ".join(words[i : i + len(target_words)])
            if fuzz.ratio(chunk, target) >= threshold:
                return True
        return False

    def parse_with_rules(self, text: str) -> Action:
        normalized = self.normalize(text)

        if any(word in normalized for word in ["stop", "exit", "quit", "goodbye"]):
            return Action("stop", {})

        if self.fuzzy_contains(normalized, "open chrome") or self.fuzzy_contains(normalized, "open browser"):
            return Action("open_app", {"app": "chrome"})

        if self.fuzzy_contains(normalized, "open spotify"):
            return Action("open_app", {"app": "spotify"})

        if any(phrase in normalized for phrase in ["what time", "tell time", "current time", "time now"]):
            return Action("get_time", {})

        if any(phrase in normalized for phrase in ["search", "google", "look up"]):
            query = normalized
            for prefix in ["search", "google", "look up", "search for"]:
                query = query.replace(prefix, "").strip()
            if not query:
                return Action("ask", {"question": "What should I search for?"})
            return Action("search_web", {"query": query})

        if any(phrase in normalized for phrase in ["temperature", "weather", "forecast"]):
            city_match = re.search(r"(?:in|for)\s+([a-zA-Z\s]+)$", text, flags=re.IGNORECASE)
            city = city_match.group(1).strip() if city_match else ""
            if city:
                return Action("get_weather", {"city": city})
            return Action("ask", {"question": "Which city should I check weather for?"})

        if any(phrase in normalized for phrase in ["volume up", "increase volume", "louder"]):
            return Action("volume", {"direction": "up"})

        if any(phrase in normalized for phrase in ["volume down", "decrease volume", "softer"]):
            return Action("volume", {"direction": "down"})

        if any(phrase in normalized for phrase in ["mute", "unmute"]):
            return Action("toggle_mute", {})

        if any(phrase in normalized for phrase in ["play music", "resume music", "play pause", "pause music"]):
            return Action("toggle_media", {})

        if any(phrase in normalized for phrase in ["close app", "close application", "kill app"]):
            app_name = normalized.replace("close app", "").replace("close application", "").replace("kill app", "").strip()
            if app_name:
                return Action("close_app", {"app": app_name})
            return Action("ask", {"question": "Which app should I close?"})

        return Action("unknown", {"raw_text": text})

    def parse_with_gpt(self, text: str) -> Optional[Action]:
        if not self.use_gpt or not self.openai_api_key or OpenAI is None:
            return None

        prompt = (
            "You are Omega, a local AI assistant running on a user's computer.\n\n"
            "Your job:\n"
            "- Convert natural language commands into structured actions.\n\n"
            "Rules:\n"
            "- Be concise\n"
            "- Output JSON only\n"
            "- Identify intent and parameters\n\n"
            "Supported actions:\n"
            "- open_app (chrome, spotify, vscode)\n"
            "- search_web (query)\n"
            "- get_weather (city)\n"
            "- play_music\n"
            "- stop_music\n"
            "- get_time\n"
            "- stop\n"
        )

        try:
            client = OpenAI(api_key=self.openai_api_key)
            response = client.responses.create(
                model="gpt-5.1-mini",
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0,
            )
            content = response.output_text.strip()
            parsed = json.loads(content)
            action = parsed.get("action")
            if not action:
                return None

            if action == "open_app":
                return Action("open_app", {"app": parsed.get("app", "")})
            if action == "search_web":
                return Action("search_web", {"query": parsed.get("query", "")})
            if action == "get_weather":
                return Action("get_weather", {"city": parsed.get("city", "")})
            if action in ["play_music", "stop_music"]:
                return Action("toggle_media", {})
            if action == "get_time":
                return Action("get_time", {})
            if action == "stop":
                return Action("stop", {})
        except Exception as exc:
            print(f"GPT parse failed: {exc}")

        return None

    def parse_command(self, text: str) -> Action:
        gpt_action = self.parse_with_gpt(text)
        if gpt_action:
            return gpt_action
        return self.parse_with_rules(text)

    def open_app(self, app: str) -> None:
        app = app.lower()
        if app in ["chrome", "browser"]:
            chrome_paths = [
                shutil.which("google-chrome"),
                shutil.which("google-chrome-stable"),
                shutil.which("chromium"),
                shutil.which("chromium-browser"),
            ]
            chrome = next((path for path in chrome_paths if path), None)
            if chrome:
                subprocess.Popen([chrome])
            else:
                webbrowser.open("https://www.google.com")
            self.speak("Opening Chrome")
            return

        if app == "spotify":
            spotify = shutil.which("spotify")
            if spotify:
                subprocess.Popen([spotify])
                self.speak("Opening Spotify")
            else:
                webbrowser.open("https://open.spotify.com")
                self.speak("Spotify app was not found, opening web player")
            return

        if app == "vscode":
            code = shutil.which("code")
            if code:
                subprocess.Popen([code])
                self.speak("Opening VS Code")
            else:
                self.speak("VS Code command is not available")
            return

        self.speak(f"I don't support opening {app} yet")

    def close_app(self, app: str) -> None:
        app = app.strip().lower()
        if not app:
            self.speak("Please tell me which app to close")
            return

        if platform.system().lower() == "linux":
            subprocess.run(["pkill", "-f", app], check=False)
            self.speak(f"Tried to close {app}")
        elif platform.system().lower() == "darwin":
            subprocess.run(["pkill", "-f", app], check=False)
            self.speak(f"Tried to close {app}")
        else:
            subprocess.run(["taskkill", "/IM", f"{app}.exe", "/F"], check=False)
            self.speak(f"Tried to close {app}")

    def search_web(self, query: str) -> None:
        query = query.strip()
        if not query:
            self.speak("Please tell me what to search")
            return
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        webbrowser.open(url)
        self.speak(f"Searching for {query}")

    def get_weather(self, city: str) -> None:
        if not self.openweather_api_key:
            self.speak("OpenWeather API key is missing")
            return

        city = city.strip()
        if not city:
            self.speak("Please tell me the city name")
            return

        params = {
            "q": city,
            "appid": self.openweather_api_key,
            "units": "metric",
        }
        try:
            response = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params=params,
                timeout=12,
            )
            data = response.json()
            if response.status_code != 200:
                self.speak(f"Weather lookup failed for {city}")
                return

            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            desc = data["weather"][0]["description"]
            self.speak(
                f"In {city}, temperature is {temp:.1f} degrees Celsius, feels like {feels_like:.1f}, with {desc}"
            )
        except Exception:
            self.speak("Failed to fetch weather right now")

    def volume_control(self, direction: str) -> None:
        # Try Linux-native controls first, then keyboard simulation fallback.
        if platform.system().lower() == "linux":
            pactl = shutil.which("pactl")
            if pactl:
                step = "+5%" if direction == "up" else "-5%"
                subprocess.run([pactl, "set-sink-volume", "@DEFAULT_SINK@", step], check=False)
                self.speak(f"Volume {direction}")
                return

            amixer = shutil.which("amixer")
            if amixer:
                step = "5%+" if direction == "up" else "5%-"
                subprocess.run([amixer, "-D", "pulse", "sset", "Master", step], check=False)
                self.speak(f"Volume {direction}")
                return

        try:
            import keyboard

            keyboard.send("volume up" if direction == "up" else "volume down")
            self.speak(f"Volume {direction}")
        except Exception:
            self.speak("Volume control is not available on this machine")

    def toggle_mute(self) -> None:
        if platform.system().lower() == "linux" and shutil.which("pactl"):
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=False)
            self.speak("Toggled mute")
            return

        try:
            import keyboard

            keyboard.send("volume mute")
            self.speak("Toggled mute")
        except Exception:
            self.speak("Mute control is not available")

    def toggle_media(self) -> None:
        playerctl = shutil.which("playerctl")
        if playerctl:
            subprocess.run([playerctl, "play-pause"], check=False)
            self.speak("Toggled playback")
            return

        try:
            import pyautogui

            pyautogui.press("playpause")
            self.speak("Toggled playback")
        except Exception:
            self.speak("Media controls are not available")

    def execute(self, action: Action) -> bool:
        if action.name == "open_app":
            self.open_app(action.params.get("app", ""))
            return True

        if action.name == "get_time":
            now = datetime.now().strftime("%H:%M")
            self.speak(f"The time is {now}")
            return True

        if action.name == "search_web":
            self.search_web(action.params.get("query", ""))
            return True

        if action.name == "get_weather":
            city = action.params.get("city", "")
            if not city:
                self.speak("Please tell me the city")
                city = self.listen()
            self.get_weather(city)
            return True

        if action.name == "volume":
            self.volume_control(action.params.get("direction", "up"))
            return True

        if action.name == "toggle_mute":
            self.toggle_mute()
            return True

        if action.name == "toggle_media":
            self.toggle_media()
            return True

        if action.name == "close_app":
            self.close_app(action.params.get("app", ""))
            return True

        if action.name == "ask":
            self.speak(action.params.get("question", "Please repeat"))
            follow_up = self.listen()
            next_action = self.parse_command(follow_up)
            return self.execute(next_action)

        if action.name == "stop":
            self.speak("Goodbye")
            return False

        self.speak("Sorry, I didn't understand that")
        return True

    def run(self) -> None:
        self.speak("Omega online")
        while True:
            heard = self.listen()
            if not heard:
                continue

            if not self.has_wake_word(heard):
                continue

            self.speak("Yes, how can I help?")
            command = self.listen()
            if not command:
                self.speak("I didn't catch that")
                continue

            action = self.parse_command(command)
            should_continue = self.execute(action)
            if not should_continue:
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Omega local voice assistant")
    parser.add_argument(
        "--use-gpt",
        action="store_true",
        help="Enable GPT-based intent parsing (requires OPENAI_API_KEY and openai package)",
    )
    args = parser.parse_args()

    assistant = OmegaAssistant(use_gpt=args.use_gpt)
    assistant.run()


if __name__ == "__main__":
    main()
