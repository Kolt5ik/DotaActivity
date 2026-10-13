from __future__ import annotations

import csv
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "Dota Activity"
APP_VERSION = "0.0.6"
DISCORD_GAME_NAME = "Dota"
GSI_PORT = 38174
DISCORD_APPLICATION_ID = "1559228191195922513"
STEAM_ASSET_ROOT = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react"
# A square image is required here: Discord crops large Rich Presence art to a square.
DOTA_LOGO_URL = "https://raw.githubusercontent.com/Kolt5ik/DotaActivity/feature/discord-presence-polish/assets/dota-logo-square.png"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "DotaActivity"
SETTINGS_PATH = APP_DIR / "settings.json"
APP_ICON_PNG = Path("assets") / "logo_dota.png"
GSI_FILENAME = "gamestate_integration_dotapresence.cfg"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "DotaActivity"
GITHUB_RELEASE_API = "https://api.github.com/repos/Kolt5ik/DotaActivity/releases/latest"
GITHUB_RELEASE_PREFIX = "https://github.com/Kolt5ik/DotaActivity/releases/download/"
MAX_UPDATE_BYTES = 250 * 1024 * 1024

TEXT = {
    "ru": {
        "window_title": "Dota Activity", "brand_subtitle": "Проект Kolt5ik · статус Dota в Discord",
        "presence_header": "СЕЙЧАС В DISCORD", "game_closed": "Dota не запущена",
        "game_closed_details": "Активность появится при запуске игры", "gsi_title": "DOTA 2",
        "autostart": "Автозапуск Windows", "tray": "Свернуть в трей",
        "tray_open": "Открыть Dota Activity", "exit": "Выход",
        "language": "Язык", "check_updates": "Проверить обновления",
        "footnote": "Оставь приложение и Discord запущенными во время игры.",
        "waiting": "Ожидаю запуска Dota 2", "game_started": "Dota 2 запущена · подключаюсь к Discord",
        "rpc_connected": "Подключено к Discord", "rpc_wait": "Открой настольный Discord · повторное подключение…",
        "rpc_published": "Статус Dota 2 опубликован в Discord", "rpc_lost": "Потеряна связь с Discord · переподключаюсь…",
        "server_ready": "Локальное подключение готово · ожидаю Discord", "server_error": "Не удалось открыть локальный порт для Dota 2",
        "steam_search": "Ищу Dota 2 в библиотеках Steam…", "dota_found": "Dota 2 найдена · GSI настроен автоматически ({library})",
        "gsi_error": "Не удалось настроить Dota 2: {error}", "autostart_enabled": "Автозапуск Windows включён",
        "autostart_disabled": "Автозапуск Windows выключен", "autostart_error_title": "Автозапуск Windows",
        "autostart_error": "Не удалось изменить автозапуск.\n\n{error}", "tray_error_title": "Системный трей",
        "tray_error": "Не удалось свернуть приложение в трей.\n\n{error}",
        "update_checking": "Проверяю обновления…", "update_current": "Установлена последняя версия ({version})",
        "update_downloading": "Скачиваю обновление…", "update_available": "Доступна версия {version}",
        "update_unavailable": "Не удалось проверить обновления. Проверь подключение к интернету.",
        "update_error_title": "Проверка обновлений", "update_found_title": "Доступно обновление",
        "update_prompt": "Доступна Dota Activity {version}. Скачать обновление?\n\n{notes}",
        "update_none_title": "Обновлений нет", "update_none": "У тебя установлена последняя версия ({version}).",
        "update_download_title": "Загрузка обновления", "update_download_error": "Не удалось скачать обновление:\n\n{error}",
        "update_downloaded_title": "Обновление скачано",
        "update_downloaded": "Файл сохранён сюда:\n{path}\n\nЗакрой Dota Activity и запусти скачанный файл.",
        "update_invalid": "GitHub вернул некорректные данные о последнем релизе.",
        "activity_default": "В главном меню", "activity_details": "Готовится к игре",
    },
    "en": {
        "window_title": "Dota Activity", "brand_subtitle": "Kolt5ik project · Dota status for Discord",
        "presence_header": "CURRENT DISCORD STATUS", "game_closed": "Dota is not running",
        "game_closed_details": "Activity will appear when the game starts", "gsi_title": "DOTA 2",
        "autostart": "Start with Windows", "tray": "Minimize to tray",
        "tray_open": "Open Dota Activity", "exit": "Exit",
        "language": "Language", "check_updates": "Check for updates",
        "footnote": "Keep the app and Discord running while you play.",
        "waiting": "Waiting for Dota 2", "game_started": "Dota 2 is running · connecting to Discord",
        "rpc_connected": "Connected to Discord", "rpc_wait": "Open the Discord desktop app · reconnecting…",
        "rpc_published": "Dota 2 status posted to Discord", "rpc_lost": "Discord connection lost · reconnecting…",
        "server_ready": "Local connection ready · waiting for Discord", "server_error": "Could not open the local Dota 2 port",
        "steam_search": "Looking for Dota 2 in Steam libraries…", "dota_found": "Dota 2 found · GSI configured automatically ({library})",
        "gsi_error": "Could not configure Dota 2: {error}", "autostart_enabled": "Windows startup enabled",
        "autostart_disabled": "Windows startup disabled", "autostart_error_title": "Windows startup",
        "autostart_error": "Could not change the startup setting.\n\n{error}", "tray_error_title": "System tray",
        "tray_error": "Could not minimize the app to the tray.\n\n{error}",
        "update_checking": "Checking for updates…", "update_current": "You have the latest version ({version})",
        "update_downloading": "Downloading update…", "update_available": "Version {version} is available",
        "update_unavailable": "Could not check for updates. Check your internet connection.",
        "update_error_title": "Update check", "update_found_title": "Update available",
        "update_prompt": "Dota Activity {version} is available. Download it?\n\n{notes}",
        "update_none_title": "No updates", "update_none": "You have the latest version ({version}).",
        "update_download_title": "Downloading update", "update_download_error": "Could not download the update:\n\n{error}",
        "update_downloaded_title": "Update downloaded",
        "update_downloaded": "The file was saved here:\n{path}\n\nClose Dota Activity and run the downloaded file.",
        "update_invalid": "GitHub returned invalid information about the latest release.",
        "activity_default": "Main menu", "activity_details": "Getting ready to play",
    },
}


def parse_release_update(release: dict, current_version: str = APP_VERSION) -> dict | None:
    """Validate GitHub's latest release and return a newer Windows asset, if present."""
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name", "")
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    current = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", current_version)
    if not match or not current:
        return None
    version = tuple(map(int, match.groups()))
    if version <= tuple(map(int, current.groups())):
        return None
    asset_name = f"DotaActivity-v{match.group(0).removeprefix('v')}-Windows-x64.exe"
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") != asset_name:
            continue
        url = asset.get("browser_download_url", "")
        if isinstance(url, str) and url.startswith(GITHUB_RELEASE_PREFIX):
            return {"version": match.group(0).removeprefix("v"), "url": url,
                    "name": asset_name, "notes": str(release.get("body") or "").strip()}
    return None


def compare_versions(first: str, second: str) -> int:
    """Compare two three-part versions; return -1, 0, or 1."""
    def parts(value: str) -> tuple[int, int, int]:
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
        if not match:
            raise ValueError("Expected a version in MAJOR.MINOR.PATCH format")
        return tuple(map(int, match.groups()))
    a, b = parts(first), parts(second)
    return (a > b) - (a < b)


UI_STATUS_EN = {
    "Dota не запущена": "Dota is not running", "Выбирает героя": "Picking a hero",
    "Подготовка к матчу": "Preparing for a match", "В игре": "In game",
    "После матча": "Post-game", "Рейтинг · All Pick": "Ranked · All Pick",
    "Рейтинг": "Ranked", "Против ботов": "Vs. bots", "Тренировка": "Practice",
    "Обычная игра · All Pick": "Normal game · All Pick", "Обычная игра": "Normal game",
    "Турнир": "Tournament", "Обучение": "Tutorial", "Главное меню": "Main menu",
    "Активность появится при запуске игры": "Activity will appear when the game starts",
    "Готовится к игре": "Getting ready to play", "Матч скоро начнётся": "Match starting soon",
    "Победа": "Victory", "Матч завершён": "Match complete",
    "Ожидаю запуска Dota 2": "Waiting for Dota 2", "Локальное подключение готово · ожидаю Discord": "Local connection ready · waiting for Discord",
    "Не удалось открыть локальный порт для Dota 2": "Could not open the local Dota 2 port",
    "Dota 2 запущена · подключаюсь к Discord": "Dota 2 is running · connecting to Discord",
    "Подключено к Discord": "Connected to Discord", "Открой настольный Discord · повторное подключение…": "Open the Discord desktop app · reconnecting…",
    "Статус Dota 2 опубликован в Discord": "Dota 2 status posted to Discord",
    "Потеряна связь с Discord · переподключаюсь…": "Discord connection lost · reconnecting…",
    "Ищу Dota 2 в библиотеках Steam…": "Looking for Dota 2 in Steam libraries…",
}


def dota_is_listed(tasklist_output: str) -> bool:
    """Return whether CSV tasklist output contains the Dota 2 process."""
    try:
        return any(
            row and row[0].strip().strip('"').casefold() == "dota2.exe"
            for row in csv.reader(tasklist_output.splitlines())
        )
    except csv.Error:
        return False


def is_dota_running() -> bool:
    """Check the Windows process list without opening a console window."""
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq dota2.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return False
    return result.returncode == 0 and dota_is_listed(result.stdout)


def windows_autostart_command() -> str:
    """Build a quoted per-user Windows startup command."""
    if getattr(sys, "frozen", False):
        args = [sys.executable, "--background"]
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        executable = pythonw if pythonw.exists() else Path(sys.executable)
        args = [str(executable), str(Path(__file__).resolve()), "--background"]
    return subprocess.list2cmdline(args)


def windows_autostart_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
            winreg.QueryValueEx(key, AUTOSTART_NAME)
        return True
    except (ImportError, OSError):
        return False


def set_windows_autostart(enabled: bool) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, windows_autostart_command())
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_NAME)
            except FileNotFoundError:
                pass

GAME_MODES = {
    1: "All Pick", 2: "Captains Mode", 3: "Random Draft", 4: "Single Draft",
    5: "All Random", 7: "Diretide", 8: "Reverse Captains Mode", 9: "Greeviling",
    10: "Тренировка", 11: "Mid Only", 12: "Least Played", 13: "Limited Heroes",
    14: "Compendium Matchmaking", 15: "Custom", 16: "Captains Draft",
    18: "Ability Draft", 19: "Event", 20: "All Random Deathmatch",
    21: "1v1 Mid", 22: "All Pick", 23: "Turbo", 24: "Mutation",
}


def resource_path(relative_path: str | Path) -> Path:
    """Return a bundled asset path for both source runs and PyInstaller builds."""
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_dir / relative_path
LOBBY_TYPES = {1: "Тренировка", 2: "Турнир", 3: "Обучение", 4: "Против ботов", 7: "Рейтинг"}


def prettify_hero(raw: str) -> str:
    name = raw.removeprefix("npc_dota_hero_").replace("_", " ").strip()
    official_names = {
        "rattletrap": "Clockwerk", "windrunner": "Windranger", "zuus": "Zeus",
        "nevermore": "Shadow Fiend", "skeleton king": "Wraith King",
        "furion": "Nature's Prophet", "queenofpain": "Queen of Pain",
        "wisp": "Io", "shredder": "Timbersaw", "life stealer": "Lifestealer",
        "abyssal underlord": "Underlord", "magnataur": "Magnus",
        "anti mage": "Anti-Mage", "obsidian destroyer": "Outworld Destroyer",
        "treant": "Treant Protector", "vengefulspirit": "Vengeful Spirit",
    }
    if name in official_names:
        return official_names[name]
    return name.title() if name else "Dota 2"


def hero_asset(raw: str) -> str:
    hero = raw.removeprefix("npc_dota_hero_") if raw else ""
    return {"windrunner": "windranger", "abyssal_underlord": "underlord"}.get(hero, hero)


def game_context(map_data: dict, game_state: str = "") -> str:
    """Describe ranked, bot, training, or the known game mode from GSI fields."""
    lobby = map_data.get("lobby_type")
    lobby_text = str(lobby or "").strip().lower()
    if any(word in lobby_text for word in ("bot", "coop", "co-op")):
        return "Против ботов"
    if any(word in lobby_text for word in ("practice", "training", "трен")):
        return "Тренировка"
    if "rank" in lobby_text:
        return "Рейтинг"
    try:
        lobby_id = int(lobby)
    except (TypeError, ValueError):
        lobby_id = None
    if lobby_id in LOBBY_TYPES:
        return LOBBY_TYPES[lobby_id]

    mode = map_data.get("game_mode")
    mode_text = str(mode or "").strip().lower()
    if any(word in mode_text for word in ("bot", "coop", "co-op")):
        return "Против ботов"
    if any(word in mode_text for word in ("tutorial", "training", "трен")):
        return "Тренировка"
    if "rank" in mode_text:
        return "Рейтинг · All Pick"
    try:
        mode_id = int(mode)
    except (TypeError, ValueError):
        mode_id = None
    if mode_id == 22:
        return "Рейтинг · All Pick"
    if mode_id == 23:
        return "Turbo"
    if mode_id == 10:
        return "Тренировка"
    if mode_id in (None, 0, 1):
        match_id = map_data.get("matchid")
        # Local demo/practice games have no server match ID. Normal online
        # matches do, even when their game mode is plain All Pick.
        if game_state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS" and str(match_id or "0") == "0":
            return "Тренировка"
    if mode_id == 1:
        return "Обычная игра · All Pick"
    return GAME_MODES.get(mode_id, "Обычная игра")


def hero_image_url(raw: str) -> str:
    hero = hero_asset(raw)
    return f"{STEAM_ASSET_ROOT}/heroes/{hero}.png" if hero else DOTA_LOGO_URL


def presence_from_gsi(payload: dict) -> dict | None:
    """Convert a Dota GSI payload to a Discord presence description."""
    map_data = payload.get("map") or {}
    player = payload.get("player") or {}
    hero = payload.get("hero") or {}
    state = str(map_data.get("game_state", ""))
    game_time = map_data.get("game_time")
    hero_raw_name = str(hero.get("name", ""))
    hero_name = prettify_hero(hero_raw_name)
    mode = game_context(map_data, state)

    if state == "DOTA_GAMERULES_STATE_HERO_SELECTION":
        return {"status": "Выбирает героя", "details": "Выбирает героя", "state": mode, "large_image": DOTA_LOGO_URL, "large_text": "Dota 2"}

    if state == "DOTA_GAMERULES_STATE_PRE_GAME":
        return {"status": "Подготовка к матчу", "details": "Матч скоро начнётся", "state": mode, "large_image": DOTA_LOGO_URL, "large_text": "Dota 2"}

    if state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS":
        kills, deaths, assists = (player.get(k, 0) for k in ("kills", "deaths", "assists"))
        details = f"{hero_name} · {kills}/{deaths}/{assists}"
        net_worth = player.get("net_worth")
        if isinstance(net_worth, int):
            details += f" · {net_worth:,} NW".replace(",", " ")
        start = int(time.time() - game_time) if isinstance(game_time, (int, float)) and game_time > 0 else None
        return {
            "status": "В игре", "details": details, "state": mode,
            "large_image": hero_image_url(hero_raw_name), "large_text": hero_name, "start": start,
        }

    if state == "DOTA_GAMERULES_STATE_POST_GAME":
        win_team = map_data.get("win_team")
        team = player.get("team_name")
        outcome = "Победа" if win_team and team and win_team == team else "Матч завершён"
        kda = f"{player.get('kills', 0)}/{player.get('deaths', 0)}/{player.get('assists', 0)}"
        return {
            "status": "После матча", "details": f"{outcome} · {hero_name} · {kda}",
            "state": mode, "large_image": hero_image_url(hero_raw_name), "large_text": hero_name,
        }
    return None


def steam_roots_from_vdf(steam_root: Path, vdf_text: str = "") -> list[Path]:
    """Return the Steam root and extra library paths from libraryfolders.vdf."""
    roots = [steam_root]
    text = vdf_text
    if not text:
        try:
            text = (steam_root / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8")
        except OSError:
            return roots

    for raw_path in re.findall(r'"path"\s*"((?:\\\\|[^"])*)"', text):
        normalized = raw_path.replace("\\\\", "\\")
        path = Path(normalized)
        if path not in roots:
            roots.append(path)
    return roots


def steam_install_roots() -> list[Path]:
    """Read the current user's Steam location and its configured libraries."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
    except (ImportError, OSError):
        return []
    root = Path(str(steam_path).replace("/", "\\"))
    return steam_roots_from_vdf(root)


def find_dota_cfg_dir(steam_roots: list[Path] | None = None) -> Path | None:
    """Find Dota 2's game/dota/cfg folder in the installed Steam libraries."""
    roots = steam_roots if steam_roots is not None else steam_install_roots()
    for root in roots:
        candidate = root / "steamapps" / "common" / "dota 2 beta" / "game" / "dota" / "cfg"
        if candidate.is_dir():
            return candidate
    return None


def gsi_config_text(token: str) -> str:
    return f'''"{APP_NAME}"
{{
    "uri" "http://127.0.0.1:{GSI_PORT}/"
    "timeout" "5.0"
    "buffer" "0.1"
    "throttle" "0.5"
    "heartbeat" "30.0"
    "auth"
    {{
        "token" "{token}"
    }}
    "data"
    {{
        "provider" "1"
        "map" "1"
        "player" "1"
        "hero" "1"
        "draft" "1"
    }}
}}
'''


def install_gsi_config(cfg_dir: Path, token: str) -> Path:
    target_dir = cfg_dir / "gamestate_integration"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / GSI_FILENAME
    expected = gsi_config_text(token)
    try:
        current = target.read_text(encoding="utf-8")
    except OSError:
        current = ""
    if current != expected:
        target.write_text(expected, encoding="utf-8")
    return target


class GSIHandler(BaseHTTPRequestHandler):
    events: queue.Queue = queue.Queue()
    token = ""

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                self.send_error(400)
                return
            payload = json.loads(self.rfile.read(length))
            if payload.get("auth", {}).get("token") != self.token:
                self.send_error(403)
                return
            presence = presence_from_gsi(payload)
            if presence:
                self.events.put(presence)
            self.send_response(204)
            self.end_headers()
        except (ValueError, json.JSONDecodeError):
            self.send_error(400)

    def log_message(self, *_args):
        pass


class DotaActivityApp:
    def __init__(self, root: tk.Tk, start_hidden: bool = False):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("440x330")
        self.root.minsize(400, 310)
        self.root.configure(bg="#101116")
        self._window_icon = tk.PhotoImage(file=str(resource_path(APP_ICON_PNG)))
        self.root.iconphoto(True, self._window_icon)
        self.rpc = None
        self.tray_icon = None
        self.server: ThreadingHTTPServer | None = None
        self.events: queue.Queue = queue.Queue()
        GSIHandler.events = self.events
        self.settings = self.load_settings()
        self.gsi_token = self.settings.get("gsi_token") or secrets.token_urlsafe(24)
        self.language = self.settings.get("language", "ru")
        if self.language not in TEXT:
            self.language = "ru"
        self._localized_widgets: list[tuple[tk.Widget, str]] = []
        self.status_var = tk.StringVar(value=self.tr("waiting"))
        self.state_var = tk.StringVar(value=self.tr("game_closed"))
        self.details_var = tk.StringVar(value=self.tr("game_closed_details"))
        self.gsi_var = tk.StringVar(value=self.tr("steam_search"))
        self.language_var = tk.StringVar(value="Русский" if self.language == "ru" else "English")
        self.last_presence: dict | None = None
        self.dota_running = False
        self.autostart_var = tk.BooleanVar(value=windows_autostart_enabled())
        self.update_check_running = False
        self.latest_available_version: str | None = None
        self.dota_cfg_dir: Path | None = None
        self.last_rpc_attempt = 0.0
        self.build_ui()
        GSIHandler.token = self.gsi_token
        self.ensure_gsi()
        self.start_server()
        self.state_var.set(self.tr("game_closed"))
        self.details_var.set(self.tr("game_closed_details"))
        self.status_var.set(self.tr("waiting"))
        self.root.after(500, self.poll_events)
        self.root.after(250, self.maintenance)
        self.root.after(1800, lambda: self.check_for_updates(manual=False))
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        if start_hidden:
            self.root.withdraw()
            self.root.after(200, self.hide_to_tray)

    @staticmethod
    def load_settings() -> dict:
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return settings if isinstance(settings, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def tr(self, key: str, **values) -> str:
        language = getattr(self, "language", "ru")
        return TEXT[language][key].format(**values)

    def ui_text(self, value: str) -> str:
        if self.language == "en":
            if value.startswith("Dota 2 найдена · GSI настроен автоматически ("):
                library = value.removeprefix("Dota 2 найдена · GSI настроен автоматически (").removesuffix(")")
                return f"Dota 2 found · GSI configured automatically ({library})"
            if value.startswith("Не удалось настроить Dota 2: "):
                return value.replace("Не удалось настроить Dota 2: ", "Could not configure Dota 2: ", 1)
            return UI_STATUS_EN.get(value, value)
        reverse = {english: russian for russian, english in UI_STATUS_EN.items()}
        if value.startswith("Dota 2 found · GSI configured automatically ("):
            library = value.removeprefix("Dota 2 found · GSI configured automatically (").removesuffix(")")
            return f"Dota 2 найдена · GSI настроен автоматически ({library})"
        if value.startswith("Could not configure Dota 2: "):
            return value.replace("Could not configure Dota 2: ", "Не удалось настроить Dota 2: ", 1)
        return reverse.get(value, value)

    def localized(self, widget: tk.Widget, key: str):
        self._localized_widgets.append((widget, key))
        widget.configure(text=self.tr(key))
        return widget

    def change_language(self, _event=None):
        self.language = "en" if self.language_var.get() == "English" else "ru"
        for widget, key in self._localized_widgets:
            try:
                widget.configure(text=self.tr(key))
            except tk.TclError:
                pass
        self.root.title(self.tr("window_title") + f" v{APP_VERSION}")
        if not self.dota_running:
            self.state_var.set(self.tr("game_closed"))
            self.details_var.set(self.tr("game_closed_details"))
        elif self.last_presence:
            self.state_var.set(self.ui_text(self.last_presence.get("status", "Dota")))
            self.details_var.set(self.ui_text(self.last_presence.get("details", "")))
        self.status_var.set(self.ui_text(self.status_var.get()))
        self.gsi_var.set(self.ui_text(self.gsi_var.get()))
        self.save_settings()

    def save_settings(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps({
            "gsi_token": self.gsi_token,
            "language": self.language,
            "dismissed_update_version": self.settings.get("dismissed_update_version"),
        }, indent=2), encoding="utf-8")

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101116")
        style.configure("TLabel", background="#101116", foreground="#e9e9ef", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 17), foreground="#f4c95d")
        style.configure("Muted.TLabel", foreground="#9a9baa", font=("Segoe UI", 9))
        style.configure("Action.TButton", font=("Segoe UI Semibold", 9), padding=(10, 6))
        style.configure("TCheckbutton", background="#101116", foreground="#b7b9c6", font=("Segoe UI", 9))
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 10))
        brand = ttk.Frame(header)
        brand.pack(anchor="w")
        self._brand_image = self._window_icon.subsample(32, 32)
        tk.Label(brand, image=self._brand_image, bg="#101116", borderwidth=0).pack(side="left", padx=(0, 9))
        title_group = ttk.Frame(brand)
        title_group.pack(side="left", anchor="w")
        ttk.Label(title_group, text="DOTA ACTIVITY", style="Title.TLabel").pack(anchor="w")
        self.localized(ttk.Label(title_group, style="Muted.TLabel"), "brand_subtitle").pack(anchor="w", pady=(1, 0))

        card = tk.Frame(main, bg="#202230", padx=13, pady=11)
        card.pack(fill="x", pady=(0, 9))
        self.localized(tk.Label(card, bg="#202230", fg="#9a9baa", font=("Segoe UI", 8, "bold")), "presence_header").pack(anchor="w")
        tk.Label(card, textvariable=self.state_var, bg="#202230", fg="#f3f3f7", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(3, 0))
        tk.Label(card, textvariable=self.details_var, bg="#202230", fg="#c6c7d2", font=("Segoe UI", 9)).pack(anchor="w", pady=(1, 0))
        tk.Label(card, textvariable=self.status_var, bg="#202230", fg="#f4c95d", font=("Segoe UI", 8), wraplength=360, justify="left").pack(anchor="w", pady=(5, 0))

        gsi_panel = tk.Frame(main, bg="#181a21", padx=10, pady=8)
        gsi_panel.pack(fill="x", pady=(0, 9))
        self.localized(tk.Label(gsi_panel, bg="#181a21", fg="#f4c95d", font=("Segoe UI Semibold", 8)), "gsi_title").pack(anchor="w")
        tk.Label(gsi_panel, textvariable=self.gsi_var, bg="#181a21", fg="#b7b9c6", font=("Segoe UI", 8), wraplength=360, justify="left").pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(main)
        actions.pack(fill="x")
        self.localized(ttk.Checkbutton(
            actions, variable=self.autostart_var,
            command=self.toggle_autostart,
        ), "autostart").pack(side="left")
        self.localized(ttk.Button(actions, style="Action.TButton", command=self.hide_to_tray), "tray").pack(side="right")

        footer = ttk.Frame(main)
        footer.pack(fill="x", pady=(8, 0))
        language_row = ttk.Frame(footer)
        language_row.pack(side="left")
        self.localized(ttk.Label(language_row, style="Muted.TLabel"), "language").pack(side="left")
        language_box = ttk.Combobox(
            language_row, textvariable=self.language_var, values=("Русский", "English"),
            state="readonly", width=9,
        )
        language_box.pack(side="left", padx=(6, 0))
        language_box.bind("<<ComboboxSelected>>", self.change_language)
        self.update_button = self.localized(ttk.Button(
            footer, style="Action.TButton", command=lambda: self.check_for_updates(manual=True),
        ), "check_updates")
        self.update_button.pack(side="right")

        def resize_wrapped_labels(event):
            wrap = max(220, event.width - 48)
            for label in (status_label, gsi_label):
                label.configure(wraplength=wrap)

        status_label = card.winfo_children()[-1]
        gsi_label = gsi_panel.winfo_children()[-1]
        main.bind("<Configure>", resize_wrapped_labels)

    def check_for_updates(self, manual: bool = False):
        if self.update_check_running:
            return
        self.update_check_running = True
        self.status_var.set(self.tr("update_checking"))
        update_button = getattr(self, "update_button", None)
        if update_button:
            update_button.configure(state="disabled")

        def worker():
            update = None
            error = None
            current_release = False
            try:
                request = urllib.request.Request(
                    GITHUB_RELEASE_API,
                    headers={"Accept": "application/vnd.github+json", "User-Agent": "DotaActivity-Updater"},
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    release = json.loads(response.read(2_000_000))
                tag = release.get("tag_name", "") if isinstance(release, dict) else ""
                if not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
                    raise ValueError("Invalid release version")
                if compare_versions(tag, APP_VERSION) <= 0:
                    current_release = True
                else:
                    update = parse_release_update(release)
                    if update is None:
                        raise ValueError("The release does not contain the expected Windows executable")
            except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
                error = exc
            self.root.after(0, lambda: self.finish_update_check(update, error, current_release, manual))

        threading.Thread(target=worker, name="DotaActivityUpdateCheck", daemon=True).start()

    def finish_update_check(self, update: dict | None, error: Exception | None, current: bool, manual: bool):
        self.update_check_running = False
        if getattr(self, "update_button", None):
            self.update_button.configure(state="normal")
        if error:
            self.status_var.set(self.tr("update_unavailable"))
            if manual:
                messagebox.showerror(self.tr("update_error_title"), self.tr("update_unavailable"))
            return
        if current or update is None:
            self.status_var.set(self.tr("update_current", version=APP_VERSION))
            if manual:
                messagebox.showinfo(self.tr("update_none_title"), self.tr("update_none", version=APP_VERSION))
            return

        self.latest_available_version = update["version"]
        if not manual and self.settings.get("dismissed_update_version") == update["version"]:
            return
        notes = update.get("notes", "")[:800] or ("Нет описания релиза." if self.language == "ru" else "No release notes.")
        accepted = messagebox.askyesno(
            self.tr("update_found_title"),
            self.tr("update_prompt", version=update["version"], notes=notes),
        )
        if accepted:
            self.download_update(update)
        else:
            self.settings["dismissed_update_version"] = update["version"]
            self.save_settings()
            self.status_var.set(self.tr("update_available", version=update["version"]))

    def download_update(self, update: dict):
        self.status_var.set(self.tr("update_downloading"))
        if getattr(self, "update_button", None):
            self.update_button.configure(state="disabled")

        def worker():
            path = None
            error = None
            temporary = None
            try:
                download_dir = Path.home() / "Downloads"
                download_dir.mkdir(parents=True, exist_ok=True)
                path = download_dir / update["name"]
                temporary = path.with_suffix(path.suffix + ".part")
                request = urllib.request.Request(update["url"], headers={"User-Agent": "DotaActivity-Updater"})
                total = 0
                with urllib.request.urlopen(request, timeout=30) as response, temporary.open("wb") as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        total += len(block)
                        if total > MAX_UPDATE_BYTES:
                            raise ValueError("Update file exceeds the 250 MB limit")
                        output.write(block)
                if total == 0:
                    raise ValueError("Downloaded file is empty")
                os.replace(temporary, path)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                error = exc
                if temporary:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
            self.root.after(0, lambda: self.finish_update_download(path, error))

        threading.Thread(target=worker, name="DotaActivityUpdateDownload", daemon=True).start()

    def finish_update_download(self, path: Path | None, error: Exception | None):
        if getattr(self, "update_button", None):
            self.update_button.configure(state="normal")
        if error or path is None:
            messagebox.showerror(self.tr("update_download_title"), self.tr("update_download_error", error=error))
            return
        messagebox.showinfo(self.tr("update_downloaded_title"), self.tr("update_downloaded", path=path))

    def ensure_gsi(self):
        cfg_dir = find_dota_cfg_dir()
        if cfg_dir is None:
            self.dota_cfg_dir = None
            self.gsi_var.set(self.tr("steam_search"))
            return
        try:
            target = install_gsi_config(cfg_dir, self.gsi_token)
            self.dota_cfg_dir = cfg_dir
            self.gsi_var.set(self.tr("dota_found", library=target.parent.parent.parent.name))
            self.save_settings()
        except OSError as exc:
            self.dota_cfg_dir = None
            self.gsi_var.set(self.tr("gsi_error", error=exc))

    def start_server(self):
        GSIHandler.token = self.gsi_token
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", GSI_PORT), GSIHandler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            self.status_var.set(self.tr("server_ready"))
        except OSError:
            self.status_var.set(self.tr("server_error"))

    def toggle_autostart(self):
        enabled = bool(self.autostart_var.get())
        try:
            set_windows_autostart(enabled)
        except (OSError, ImportError) as exc:
            self.autostart_var.set(not enabled)
            messagebox.showerror(self.tr("autostart_error_title"), self.tr("autostart_error", error=exc))
            return
        self.status_var.set(self.tr("autostart_enabled" if enabled else "autostart_disabled"))

    def try_connect(self):
        if not self.dota_running:
            return
        if self.rpc or time.monotonic() - self.last_rpc_attempt < 5:
            return
        self.last_rpc_attempt = time.monotonic()
        app_id = os.environ.get("DOTA_ACTIVITY_DISCORD_APP_ID", DISCORD_APPLICATION_ID).strip()
        if not app_id.isdigit():
            self.status_var.set("Сборка ожидает Discord Application ID проекта")
            return
        try:
            from pypresence import Presence
            rpc = Presence(app_id)
            rpc.connect()
            self.rpc = rpc
            self.status_var.set(self.tr("rpc_connected"))
            self.send_presence({"status": "Главное меню", "details": "Готовится к игре", "image": "dota2"})
        except Exception:
            self.rpc = None
            self.status_var.set(self.tr("rpc_wait"))

    def send_presence(self, data: dict):
        if not self.dota_running:
            return
        self.last_presence = data
        self.state_var.set(self.ui_text(data.get("status", "Dota 2")))
        self.details_var.set(self.ui_text(data.get("details", "")))
        if not self.rpc:
            return
        try:
            # Use public Dota image URLs; no custom Discord asset upload is needed.
            kwargs = {
                "name": DISCORD_GAME_NAME,
                "details": data.get("details", "Playing Dota 2"),
                "state": data.get("state", "Dota 2"),
                "large_image": data.get("large_image", DOTA_LOGO_URL),
                "large_text": data.get("large_text", "Dota 2"),
            }
            if data.get("start"):
                kwargs["start"] = data["start"]
            self.rpc.update(**kwargs)
            self.status_var.set(self.tr("rpc_published"))
        except Exception:
            self.status_var.set(self.tr("rpc_lost"))
            try:
                self.rpc.close()
            except Exception:
                pass
            self.rpc = None
            self.last_rpc_attempt = 0

    def poll_events(self):
        latest = None
        while True:
            try:
                latest = self.events.get_nowait()
            except queue.Empty:
                break
        if latest:
            self.send_presence(latest)
        self.root.after(500, self.poll_events)

    def maintenance(self):
        if self.dota_cfg_dir is None:
            self.ensure_gsi()
        running = is_dota_running()
        if running != self.dota_running:
            self.dota_running = running
            if running:
                self.last_rpc_attempt = 0.0
                self.state_var.set(self.tr("activity_default"))
                self.details_var.set(self.tr("activity_details"))
                self.status_var.set(self.tr("game_started"))
            else:
                self.disconnect_rpc()
                self.last_presence = None
                self.state_var.set(self.tr("game_closed"))
                self.details_var.set(self.tr("game_closed_details"))
                self.status_var.set(self.tr("waiting"))
        if self.dota_running and self.rpc is None:
            self.try_connect()
        self.root.after(2500, self.maintenance)

    def _create_tray_icon(self):
        import pystray
        from PIL import Image

        with Image.open(resource_path(APP_ICON_PNG)) as source:
            image = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        menu = pystray.Menu(
            pystray.MenuItem(self.tr("tray_open"), lambda _icon, _item: self.root.after(0, self.show_window)),
            pystray.MenuItem(self.tr("exit"), lambda _icon, _item: self.root.after(0, self.exit_app)),
        )
        self.tray_icon = pystray.Icon("DotaActivity", image, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, name="DotaActivityTray", daemon=True).start()

    def hide_to_tray(self):
        if self.tray_icon is None:
            try:
                self._create_tray_icon()
            except Exception as exc:
                messagebox.showerror(self.tr("tray_error_title"), self.tr("tray_error", error=exc))
                return
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def disconnect_rpc(self):
        rpc, self.rpc = self.rpc, None
        if rpc is None:
            return
        try:
            rpc.clear()
        except Exception:
            pass
        try:
            rpc.close()
        except Exception:
            pass

    def exit_app(self):
        if getattr(self, "_exiting", False):
            return
        self._exiting = True
        try:
            try:
                self.save_settings()
            except OSError:
                pass
            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception:
                    pass
                self.tray_icon = None
            self.disconnect_rpc()
            if self.server:
                server, self.server = self.server, None
                try:
                    server.shutdown()
                except Exception:
                    pass
                try:
                    server.server_close()
                except Exception:
                    pass
        finally:
            try:
                self.root.quit()
            finally:
                try:
                    self.root.destroy()
                except tk.TclError:
                    pass


def main():
    root = tk.Tk()
    DotaActivityApp(root, start_hidden="--background" in sys.argv[1:])
    root.mainloop()


if __name__ == "__main__":
    main()
