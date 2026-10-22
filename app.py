from __future__ import annotations

import csv
import ctypes
import hashlib
import hmac
import http.client
import json
import math
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
APP_VERSION = "0.0.12"
DISCORD_GAME_NAME = "Dota"
GSI_PORT = 38174
DISCORD_APPLICATION_ID = "1559228191195922513"
STEAM_ASSET_ROOT = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react"
# Use the commit that introduced this file so PR builds can load the image
# before the PR is merged. The commit URL stays valid after the branch is removed.
DOTA_LOGO_URL = "https://raw.githubusercontent.com/Kolt5ik/DotaActivity/65b8bfb/assets/dota-presence-centered.png"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "DotaActivity"
SETTINGS_PATH = APP_DIR / "settings.json"
APP_ICON_PNG = Path("assets") / "logo_dota.png"
GSI_FILENAME = "gamestate_integration_dotapresence.cfg"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "DotaActivity"
LANGUAGE_SETTINGS_VERSION = 1
GITHUB_RELEASE_API = "https://api.github.com/repos/Kolt5ik/DotaActivity/releases/latest"
GITHUB_RELEASE_PREFIX = "https://github.com/Kolt5ik/DotaActivity/releases/download/"
MAX_UPDATE_BYTES = 250 * 1024 * 1024
_INSTANCE_MUTEX_HANDLE = None
INSTANCE_MUTEX_NAME = r"Local\DotaActivity.Singleton"
_NO_GSI_EVENT = object()

TEXT = {
    "ru": {
        "window_title": "Dota Activity", "brand_subtitle": "Проект Kolt5ik · статус Dota в Discord",
        "presence_header": "СЕЙЧАС В DISCORD", "game_closed": "Dota не запущена",
        "game_closed_details": "Активность появится при запуске игры", "gsi_title": "DOTA 2",
        "tray": "Свернуть в трей",
        "autostart_on": "Автозапуск Windows · Вкл.", "autostart_off": "Автозапуск Windows · Выкл.",
        "tray_open": "Открыть Dota Activity", "exit": "Выход",
        "language": "Язык", "check_updates": "Проверить обновления", "gsi_repair": "Восстановить GSI",
        "footnote": "Оставь приложение и Discord запущенными во время игры.",
        "waiting": "Ожидаю запуска Dota 2", "game_started": "Dota 2 запущена · подключаюсь к Discord",
        "app_id_missing": "Не задан Discord Application ID проекта",
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
        "update_installing": "Обновление готово. Приложение перезапустится и заменит старую версию.",
        "update_install_error": "Не удалось установить обновление автоматически:\n\n{error}\n\nФайл обновления сохранён здесь:\n{path}",
        "update_invalid": "GitHub вернул некорректные данные о последнем релизе.",
        "activity_default": "В главном меню", "activity_details": "Готовится к игре",
        "already_running_title": "Dota Activity уже запущена",
        "already_running": "Уже работает другая копия Dota Activity.",
    },
    "en": {
        "window_title": "Dota Activity", "brand_subtitle": "Kolt5ik project · Dota status for Discord",
        "presence_header": "CURRENT DISCORD STATUS", "game_closed": "Dota is not running",
        "game_closed_details": "Activity will appear when the game starts", "gsi_title": "DOTA 2",
        "tray": "Minimize to tray",
        "autostart_on": "Start with Windows · On", "autostart_off": "Start with Windows · Off",
        "tray_open": "Open Dota Activity", "exit": "Exit",
        "language": "Language", "check_updates": "Check for updates", "gsi_repair": "Repair GSI",
        "footnote": "Keep the app and Discord running while you play.",
        "waiting": "Waiting for Dota 2", "game_started": "Dota 2 is running · connecting to Discord",
        "app_id_missing": "The project Discord Application ID is not configured",
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
        "update_installing": "The update is ready. The app will restart and replace the current version.",
        "update_install_error": "Could not install the update automatically:\n\n{error}\n\nThe update file is saved here:\n{path}",
        "update_invalid": "GitHub returned invalid information about the latest release.",
        "activity_default": "Main menu", "activity_details": "Getting ready to play",
        "already_running_title": "Dota Activity is already running",
        "already_running": "Another copy of Dota Activity is already running.",
    },
}


def parse_release_update(release: dict, current_version: str = APP_VERSION) -> dict | None:
    """Validate GitHub's latest release and return a newer Windows asset, if present."""
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name", "")
    if not isinstance(tag, str):
        return None
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
        expected_url = f"{GITHUB_RELEASE_PREFIX}{tag}/{asset_name}"
        digest = asset.get("digest")
        if (url == expected_url and isinstance(digest, str)
                and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest)):
            return {"version": match.group(0).removeprefix("v"), "url": url,
                    "name": asset_name, "sha256": digest.split(":", 1)[1].lower(),
                    "notes": str(release.get("body") or "").strip()}
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


def sha256_matches(actual: str, expected: str) -> bool:
    return bool(
        isinstance(actual, str) and isinstance(expected, str)
        and re.fullmatch(r"[0-9a-fA-F]{64}", actual)
        and re.fullmatch(r"[0-9a-fA-F]{64}", expected)
        and hmac.compare_digest(actual.lower(), expected.lower())
    )


def update_download_directory(frozen: bool, home: Path | None = None) -> Path:
    """Use a private staging folder for packaged installs and Downloads in source mode."""
    if frozen:
        return APP_DIR / "updates"
    return (home or Path.home()) / "Downloads"


def cleanup_update_files(directory: Path) -> None:
    """Remove abandoned staged installers and partial downloads."""
    for pattern in ("DotaActivity-*-Windows-x64.exe", "*.part"):
        for path in directory.glob(pattern):
            try:
                path.unlink()
            except OSError:
                pass


def update_helper_command(update_path: Path, target_path: Path, process_id: int,
                          launch_args: list[str] | None = None) -> list[str]:
    """Build the detached helper command that installs an update after this process exits."""
    return [str(update_path), "--apply-update", str(process_id), str(target_path), *(launch_args or [])]


def _is_windows() -> bool:
    return os.name == "nt"


def _wait_for_process_exit(process_id: int) -> None:
    """Wait for a Windows process handle, allowing an already-exited process."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    synchronize = 0x00100000
    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel32.WaitForSingleObject.restype = ctypes.c_ulong
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(synchronize, False, int(process_id))
    if not handle:
        error = ctypes.get_last_error()
        if error in (0, 87, 1168):  # No such process: it has already exited.
            return
        raise OSError(error, "Could not wait for the running Dota Activity process")
    try:
        result = kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
        if result != 0:
            raise OSError(ctypes.get_last_error(), "Waiting for Dota Activity to close failed")
    finally:
        kernel32.CloseHandle(handle)


def apply_staged_update(process_id: int, target: Path, launch_args: list[str] | None = None) -> None:
    """Install the staged executable and restore the previous app if launch fails."""
    if not _is_windows() or not getattr(sys, "frozen", False):
        raise RuntimeError("Automatic replacement is available only in the packaged Windows app")
    source = Path(sys.executable).resolve()
    target = Path(target).resolve()
    if source == target:
        raise ValueError("The staged update and installed app paths are the same")
    _wait_for_process_exit(int(process_id))
    replacement = target.with_name(f".{target.name}.{os.getpid()}.new")
    backup = target.with_name(f".{target.name}.{os.getpid()}.bak")
    ready_file = target.with_name(f".{target.name}.{os.getpid()}.ready")
    process = None
    try:
        import shutil
        shutil.copy2(source, replacement)
        os.replace(target, backup)
        try:
            os.replace(replacement, target)
            ready_file.unlink(missing_ok=True)
            process = subprocess.Popen(
                [str(target), *(launch_args or []), "--update-ready-file", str(ready_file)],
                cwd=str(target.parent), close_fds=True,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if ready_file.is_file():
                    break
                if process.poll() is not None:
                    raise RuntimeError("The updated app exited before reporting readiness")
                time.sleep(0.2)
            else:
                raise RuntimeError("The updated app did not become ready within 30 seconds")
        except Exception:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except Exception:
                        pass
            try:
                target.unlink(missing_ok=True)
                os.replace(backup, target)
            except OSError as rollback_error:
                raise RuntimeError(
                    f"Update failed and automatic rollback failed. The previous executable is at: {backup}"
                ) from rollback_error
            try:
                subprocess.Popen([str(target), *(launch_args or [])], cwd=str(target.parent), close_fds=True)
            except OSError:
                pass
            raise
        backup.unlink(missing_ok=True)
        ready_file.unlink(missing_ok=True)
        # Remove abandoned installers left by earlier failed or superseded updates.
        updates_dir = source.parent
        for stale in updates_dir.glob("DotaActivity-*-Windows-x64.exe"):
            if stale.resolve() != source:
                try:
                    stale.unlink()
                except OSError:
                    pass
        for partial in updates_dir.glob("*.part"):
            try:
                partial.unlink()
            except OSError:
                pass
    finally:
        try:
            replacement.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            ready_file.unlink(missing_ok=True)
        except OSError:
            pass


def acquire_single_instance() -> bool:
    """Hold a Windows mutex for this process; return False when another copy owns it."""
    global _INSTANCE_MUTEX_HANDLE
    if not _is_windows() or _INSTANCE_MUTEX_HANDLE is not None:
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.CreateMutexW(None, True, INSTANCE_MUTEX_NAME)
    if not handle:
        error = ctypes.get_last_error()
        raise OSError(error, "Could not create the Dota Activity single-instance mutex")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return False
    _INSTANCE_MUTEX_HANDLE = handle
    return True


def show_update_helper_error(error: Exception) -> None:
    """Display an error from the detached updater without starting the main window."""
    if _is_windows():
        ctypes.windll.user32.MessageBoxW(None, str(error), "Dota Activity update", 0x10)


def initial_language(settings: dict) -> str:
    """Default old installs to English once, then honor saved user choices."""
    if settings.get("language_settings_version") != LANGUAGE_SETTINGS_VERSION:
        settings["language_settings_version"] = LANGUAGE_SETTINGS_VERSION
        settings["language"] = "en"
        return "en"
    value = settings.get("language", "en")
    return value if value in TEXT else "en"


def tray_menu_labels(language: str) -> tuple[str, str]:
    """Return localized open and exit labels for the system tray menu."""
    labels = TEXT.get(language, TEXT["en"])
    return labels["tray_open"], labels["exit"]


UI_STATUS_EN = {
    "Dota не запущена": "Dota is not running", "Выбирает героя": "Picking a hero",
    "Подготовка к матчу": "Preparing for a match", "В игре": "In game",
    "Смотрит матч": "Spectating", "Наблюдает за матчем": "Watching a match",
    "Наблюдает за матчем · матч завершён": "Watching a match · match complete",
    "После матча": "Post-game", "Рейтинг · All Pick": "Ranked · All Pick",
    "Рейтинг": "Ranked", "Против ботов": "Vs. bots", "Тренировка": "Practice",
    "Обычная игра · All Pick": "Normal game · All Pick", "Обычная игра": "Normal game",
    "Турнир": "Tournament", "Обучение": "Tutorial", "Главное меню": "Main menu",
    "В главном меню": "In the main menu",
    "Активность появится при запуске игры": "Activity will appear when the game starts",
    "Готовится к игре": "Getting ready to play", "Матч скоро начнётся": "Match starting soon",
    "Победа": "Victory", "Поражение": "Defeat", "Матч завершён": "Match complete",
    "Ожидаю запуска Dota 2": "Waiting for Dota 2", "Локальное подключение готово · ожидаю Discord": "Local connection ready · waiting for Discord",
    "Не удалось открыть локальный порт для Dota 2": "Could not open the local Dota 2 port",
    "Dota 2 запущена · подключаюсь к Discord": "Dota 2 is running · connecting to Discord",
    "Подключено к Discord": "Connected to Discord", "Открой настольный Discord · повторное подключение…": "Open the Discord desktop app · reconnecting…",
    "Статус Dota 2 опубликован в Discord": "Dota 2 status posted to Discord",
    "Потеряна связь с Discord · переподключаюсь…": "Discord connection lost · reconnecting…",
    "Ищу Dota 2 в библиотеках Steam…": "Looking for Dota 2 in Steam libraries…",
    "Тренировка": "Practice", "Турнир": "Tournament", "Обучение": "Tutorial",
    "Против ботов": "Vs. bots", "Обычная игра · All Pick": "Normal game · All Pick",
    "Single Draft": "Single Draft", "Random Draft": "Random Draft",
    "Captains Mode": "Captains Mode", "All Random": "All Random",
    "Ability Draft": "Ability Draft", "Turbo": "Turbo",
}


def localized_presence_text(value: str, language: str) -> str:
    """Translate a Discord presence field using the app's selected language."""
    if language != "en":
        return value
    translated = UI_STATUS_EN.get(value)
    if translated is not None:
        return translated
    parts = value.split(" · ")
    translated_parts = [UI_STATUS_EN.get(part, part) for part in parts]
    if translated_parts != parts:
        return " · ".join(translated_parts)
    for russian, english in (("Победа", "Victory"), ("Поражение", "Defeat"), ("Матч завершён", "Match complete")):
        prefix = russian + " · "
        if value.startswith(prefix):
            return english + value[len(russian):]
    return value


def localized_presence(data: dict, language: str) -> dict:
    """Return the presence payload with visible text translated for Discord."""
    result = dict(data)
    for key in ("status", "details", "state", "large_text", "small_text"):
        value = result.get(key)
        if isinstance(value, str):
            result[key] = localized_presence_text(value, language)
    return result


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
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
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


def migrate_windows_autostart() -> bool:
    """Point an existing startup entry at this executable after a manual upgrade."""
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            WINDOWS_RUN_KEY,
            0,
            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
        ) as key:
            try:
                current, _kind = winreg.QueryValueEx(key, AUTOSTART_NAME)
            except FileNotFoundError:
                return False
            expected = windows_autostart_command()
            if current == expected:
                return False
            winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, expected)
            return True
    except FileNotFoundError:
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
    mode = map_data.get("game_mode")
    mode_text = str(mode or "").strip().lower()
    try:
        mode_id = int(mode)
    except (TypeError, ValueError):
        mode_id = None

    # GSI can report the lobby as ranked while the actual game mode is Turbo.
    # The game mode is the more specific field and must take precedence here.
    if mode_id == 23 or "turbo" in mode_text:
        return "Turbo"
    if mode_id == 10 or any(word in mode_text for word in ("tutorial", "training", "трен")):
        return "Тренировка"

    lobby = map_data.get("lobby_type")
    lobby_text = str(lobby or "").strip().lower()
    if any(word in lobby_text for word in ("bot", "coop", "co-op")):
        return "Против ботов"
    if any(word in lobby_text for word in ("practice", "training", "трен")):
        return "Тренировка"
    if lobby_text in {"ranked", "rank", "7"}:
        return "Рейтинг"
    try:
        lobby_id = int(lobby)
    except (TypeError, ValueError):
        lobby_id = None
    if lobby_id in LOBBY_TYPES:
        return LOBBY_TYPES[lobby_id]

    if any(word in mode_text for word in ("bot", "coop", "co-op")):
        return "Против ботов"
    if mode_text in {"ranked", "rank"}:
        return "Рейтинг · All Pick"
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


def is_spectating(payload: dict) -> bool:
    """Detect Dota's spectator payload, where player data contains both teams."""
    player = payload.get("player")
    if not isinstance(player, dict):
        return False
    if str(player.get("activity", "")).lower() in {"spectating", "watching"}:
        return True
    return any(isinstance(player.get(team), dict) for team in ("team2", "team3"))


def presence_from_gsi(payload: dict) -> dict | None:
    """Convert a Dota GSI payload to a Discord presence description."""
    map_data = payload.get("map") or {}
    player = payload.get("player") or {}
    hero = payload.get("hero") or {}
    state = str(map_data.get("game_state", ""))
    game_time = map_data.get("game_time")
    hero_value = hero.get("name", "")
    hero_raw_name = hero_value if isinstance(hero_value, str) else ""
    hero_name = prettify_hero(hero_raw_name)
    mode = game_context(map_data, state)

    # Explicit lobby transitions clear an old match presence. Unknown/partial
    # GSI packets do not clear it, since Valve sends incremental payloads.
    if state in {"DOTA_GAMERULES_STATE_INIT", "DOTA_GAMERULES_STATE_WAIT_FOR_PLAYERS_TO_LOAD"}:
        return {"_clear": True}

    if state == "DOTA_GAMERULES_STATE_HERO_SELECTION":
        return {"status": "Выбирает героя", "details": "Выбирает героя", "state": mode, "large_image": DOTA_LOGO_URL, "large_text": "Dota 2"}

    if state == "DOTA_GAMERULES_STATE_PRE_GAME":
        return {"status": "Подготовка к матчу", "details": "Матч скоро начнётся", "state": mode, "large_image": DOTA_LOGO_URL, "large_text": "Dota 2"}

    if state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS":
        if is_spectating(payload):
            start = int(time.time() - game_time) if isinstance(game_time, (int, float)) and game_time > 0 else None
            return {
                "status": "Смотрит матч", "details": "Наблюдает за матчем", "state": mode,
                "large_image": DOTA_LOGO_URL, "large_text": "Dota 2", "start": start,
            }
        stat_keys = ("kills", "deaths", "assists")
        stats_available = all(key in player and player[key] is not None for key in stat_keys)
        if stats_available:
            kills, deaths, assists = (player.get(key, 0) for key in stat_keys)
            details = f"{hero_name} · {kills}/{deaths}/{assists}" if hero_name else f"{kills}/{deaths}/{assists}"
        else:
            details = hero_name or "В игре"
        start = int(time.time() - game_time) if isinstance(game_time, (int, float)) and game_time > 0 else None
        return {
            "status": "В игре", "details": details, "state": mode,
            "large_image": hero_image_url(hero_raw_name), "large_text": hero_name,
            "small_image": DOTA_LOGO_URL, "small_text": "Dota 2", "start": start,
        }

    if state == "DOTA_GAMERULES_STATE_POST_GAME":
        if is_spectating(payload):
            return {
                "status": "Смотрит матч", "details": "Наблюдает за матчем · матч завершён",
                "state": mode, "large_image": DOTA_LOGO_URL, "large_text": "Dota 2",
            }
        win_team = map_data.get("win_team")
        team = player.get("team_name")
        team_aliases = {
            "radiant": "radiant", "good": "radiant", "team2": "radiant",
            "dire": "dire", "bad": "dire", "team3": "dire",
        }
        winner = team_aliases.get(str(win_team or "").strip().casefold())
        player_team = team_aliases.get(str(team or "").strip().casefold())
        if winner and player_team:
            outcome = "Победа" if winner == player_team else "Поражение"
        else:
            outcome = "Матч завершён"
        return {
            "status": "После матча", "details": outcome,
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


class GSIHTTPServer(ThreadingHTTPServer):
    """Bound local GSI request concurrency and prevent slow clients lingering."""
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, *args, **kwargs):
        self._request_slots = threading.BoundedSemaphore(8)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(2.0)
        return sock, address


class GSIHandler(BaseHTTPRequestHandler):
    events: queue.Queue = queue.Queue(maxsize=32)
    token = ""

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                self.send_error(400)
                return
            body = self.rfile.read(length)
            if len(body) != length:
                self.send_error(400)
                return
            payload = json.loads(body, parse_constant=reject_json_constant)
            if not isinstance(payload, dict):
                self.send_error(400)
                return
            auth = payload.get("auth")
            if not isinstance(auth, dict):
                self.send_error(400)
                return
            if any(
                key in payload and payload[key] is not None and not isinstance(payload[key], dict)
                for key in ("map", "player", "hero")
            ):
                self.send_error(400)
                return
            if auth.get("token") != self.token:
                self.send_error(403)
                return
            if not json_values_are_safe(payload):
                self.send_error(400)
                return
            presence = presence_from_gsi(payload)
            if presence is not None:
                self.enqueue_latest(presence)
            self.send_response(204)
            self.end_headers()
        except (ValueError, json.JSONDecodeError, RecursionError, OverflowError, TimeoutError):
            self.send_error(400)

    @classmethod
    def enqueue_latest(cls, presence):
        try:
            cls.events.put_nowait(presence)
        except queue.Full:
            try:
                cls.events.get_nowait()
            except queue.Empty:
                pass
            try:
                cls.events.put_nowait(presence)
            except queue.Full:
                pass

    def log_message(self, *_args):
        pass


def json_values_are_safe(value, *, max_depth: int = 64) -> bool:
    """Reject pathological nesting and non-finite numeric values in a GSI body."""
    pending = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > max_depth:
            return False
        if isinstance(current, float) and not math.isfinite(current):
            return False
        if isinstance(current, dict):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
    return True


def reject_json_constant(value: str):
    raise ValueError(f"Non-finite JSON number: {value}")


class DotaActivityApp:
    def __init__(self, root: tk.Tk, start_hidden: bool = False, readiness_file: Path | None = None):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("480x390")
        self.root.minsize(420, 350)
        self.root.configure(bg="#111116")
        self._window_icon = tk.PhotoImage(file=str(resource_path(APP_ICON_PNG)))
        self.root.iconphoto(True, self._window_icon)
        self.rpc = None
        self.last_rpc_payload = None
        self.tray_icon = None
        self.server: ThreadingHTTPServer | None = None
        self.events: queue.Queue = queue.Queue(maxsize=32)
        GSIHandler.events = self.events
        self.settings = self.load_settings()
        self.gsi_token = self.settings.get("gsi_token") or secrets.token_urlsafe(24)
        if not isinstance(self.gsi_token, str) or len(self.gsi_token) > 256:
            self.gsi_token = secrets.token_urlsafe(24)
        # Switch existing installations to English once; after that, preserve
        # the user's explicit language choice across launches.
        self.language = initial_language(self.settings)
        self._localized_widgets: list[tuple[tk.Widget, str]] = []
        self.status_var = tk.StringVar(value=self.tr("waiting"))
        self.status_message = ("waiting", {})
        self.state_var = tk.StringVar(value=self.tr("game_closed"))
        self.details_var = tk.StringVar(value=self.tr("game_closed_details"))
        self.gsi_var = tk.StringVar(value=self.tr("steam_search"))
        self.gsi_message = ("steam_search", {})
        self.language_var = tk.StringVar(value="Русский" if self.language == "ru" else "English")
        self.last_presence: dict | None = None
        self.last_gsi_update: float | None = None
        self.dota_running = False
        self.process_check_running = False
        self.autostart_var = tk.BooleanVar(value=windows_autostart_enabled())
        if getattr(sys, "frozen", False) and self.autostart_var.get():
            try:
                migrate_windows_autostart()
            except (ImportError, OSError):
                # Keep startup non-blocking; the user can still repair the entry
                # through the checkbox if the registry is temporarily unavailable.
                pass
        self.update_check_running = False
        self.update_download_running = False
        self.latest_available_version: str | None = None
        self.dota_cfg_dir: Path | None = None
        self.last_rpc_attempt = 0.0
        self.build_ui()
        GSIHandler.token = self.gsi_token
        self.ensure_gsi()
        self.start_server()
        self.state_var.set(self.tr("game_closed"))
        self.details_var.set(self.tr("game_closed_details"))
        self.set_status("waiting")
        self.root.after(500, self.poll_events)
        self.root.after(250, self.maintenance)
        self.root.after(1800, lambda: self.check_for_updates(manual=False))
        if getattr(sys, "frozen", False):
            self.root.after(10000, self.cleanup_old_updates)
        if readiness_file is not None:
            self.root.after(1000, lambda: self._mark_ready(readiness_file))
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        if start_hidden:
            self.root.withdraw()
            self.root.after(200, self.hide_to_tray)

    @staticmethod
    def load_settings() -> dict:
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(settings, dict):
                return {}
            if settings.get("language") not in (None, "en", "ru"):
                settings.pop("language", None)
            if not isinstance(settings.get("gsi_token"), str):
                settings.pop("gsi_token", None)
            if not isinstance(settings.get("dismissed_update_version"), str):
                settings.pop("dismissed_update_version", None)
            return settings
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
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
        self.refresh_settings_controls()
        if not self.dota_running:
            self.state_var.set(self.tr("game_closed"))
            self.details_var.set(self.tr("game_closed_details"))
        elif self.last_presence:
            self.state_var.set(self.ui_text(self.last_presence.get("status", "Dota")))
            self.details_var.set(self.ui_text(self.last_presence.get("details", "")))
        if getattr(self, "status_message", None):
            key, values = self.status_message
            self.status_var.set(self.tr(key, **values))
        else:
            self.status_var.set(self.ui_text(self.status_var.get()))
        gsi_key, gsi_values = self.gsi_message
        self.gsi_var.set(self.tr(gsi_key, **gsi_values))
        self.refresh_tray_menu()
        self.save_settings()
        if self.dota_running and self.last_presence:
            self.send_presence(self.last_presence)

    def refresh_tray_menu(self):
        if self.tray_icon is None:
            return
        self.tray_icon.menu = self.build_tray_menu()
        self.tray_icon.update_menu()

    def build_tray_menu(self):
        import pystray

        open_label, exit_label = tray_menu_labels(self.language)
        return pystray.Menu(
            pystray.MenuItem(open_label, lambda _icon, _item: self.root.after(0, self.show_window)),
            pystray.MenuItem(exit_label, lambda _icon, _item: self.root.after(0, self.exit_app)),
        )

    def save_settings(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        settings = json.dumps({
            "gsi_token": self.gsi_token,
            "language": self.language,
            "language_settings_version": LANGUAGE_SETTINGS_VERSION,
            "dismissed_update_version": self.settings.get("dismissed_update_version"),
        }, indent=2).encode("utf-8")
        temporary = SETTINGS_PATH.with_suffix(".json.tmp")
        try:
            temporary.write_bytes(settings)
            os.replace(temporary, SETTINGS_PATH)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def set_status(self, key: str, **values):
        self.status_message = (key, values)
        self.status_var.set(self.tr(key, **values))

    def set_gsi_status(self, key: str, **values):
        self.gsi_message = (key, values)
        self.gsi_var.set(self.tr(key, **values))

    @staticmethod
    def _mark_ready(path: Path):
        try:
            path.write_text("ready", encoding="ascii")
        except OSError:
            pass

    def cleanup_old_updates(self):
        if not self.update_download_running:
            cleanup_update_files(APP_DIR / "updates")

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#111116")
        style.configure("TLabel", background="#111116", foreground="#e9e9ef", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 17), foreground="#a78bfa")
        style.configure("Muted.TLabel", foreground="#9a9baa", font=("Segoe UI", 9))
        style.configure(
            "Action.TButton", font=("Segoe UI Semibold", 9), padding=(10, 6),
            background="#282336", foreground="#f3f3f7", relief="flat", borderwidth=0,
            bordercolor="#282336", lightcolor="#282336", darkcolor="#282336",
            focuscolor="#282336", focusthickness=0,
        )
        style.map(
            "Action.TButton", background=[("active", "#3a3152")],
            bordercolor=[("active", "#3a3152")], lightcolor=[("active", "#3a3152")],
            darkcolor=[("active", "#3a3152")],
        )
        style.configure(
            "Action.TMenubutton", font=("Segoe UI Semibold", 9), padding=(10, 6),
            background="#282336", foreground="#f3f3f7", arrowcolor="#a78bfa",
            relief="flat", borderwidth=0, bordercolor="#282336", lightcolor="#282336",
            darkcolor="#282336", focuscolor="#282336", focusthickness=0,
        )
        style.map(
            "Action.TMenubutton", background=[("active", "#3a3152")],
            bordercolor=[("active", "#3a3152")], lightcolor=[("active", "#3a3152")],
            darkcolor=[("active", "#3a3152")],
        )
        style.configure(
            "Selected.TButton", font=("Segoe UI Semibold", 9), padding=(10, 6),
            background="#3a3152", foreground="#f3f3f7", relief="flat", borderwidth=0,
            bordercolor="#3a3152", lightcolor="#3a3152", darkcolor="#3a3152",
            focuscolor="#3a3152", focusthickness=0,
        )
        style.map(
            "Selected.TButton", background=[("active", "#4a3b67")],
            bordercolor=[("active", "#4a3b67")], lightcolor=[("active", "#4a3b67")],
            darkcolor=[("active", "#4a3b67")],
        )
        style.configure("TCheckbutton", background="#111116", foreground="#b7b9c6", font=("Segoe UI", 9))
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 10))
        brand = ttk.Frame(header)
        brand.pack(fill="x")
        self._brand_image = self._window_icon.subsample(32, 32)
        tk.Label(brand, image=self._brand_image, bg="#111116", borderwidth=0).pack(side="left", padx=(0, 9))
        title_group = ttk.Frame(brand)
        title_group.pack(side="left", anchor="w")
        ttk.Label(title_group, text="DOTA ACTIVITY", style="Title.TLabel").pack(anchor="w")
        self.localized(ttk.Label(title_group, style="Muted.TLabel"), "brand_subtitle").pack(anchor="w", pady=(1, 0))

        card = tk.Frame(main, bg="#201d2b", padx=13, pady=11, highlightthickness=1, highlightbackground="#39314d")
        card.pack(fill="x", pady=(0, 9))
        self.localized(tk.Label(card, bg="#201d2b", fg="#a78bfa", font=("Segoe UI", 8, "bold")), "presence_header").pack(anchor="w")
        tk.Label(card, textvariable=self.state_var, bg="#201d2b", fg="#f3f3f7", font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(3, 0))
        tk.Label(card, textvariable=self.details_var, bg="#201d2b", fg="#c6c7d2", font=("Segoe UI", 9)).pack(anchor="w", pady=(1, 0))
        status_label = tk.Label(card, textvariable=self.status_var, bg="#201d2b", fg="#a78bfa", font=("Segoe UI", 8), wraplength=400, justify="left")
        status_label.pack(anchor="w", pady=(5, 0))

        gsi_panel = tk.Frame(main, bg="#191820", padx=10, pady=8, highlightthickness=1, highlightbackground="#2b2935")
        gsi_panel.pack(fill="x", pady=(0, 9))
        self.localized(tk.Label(gsi_panel, bg="#191820", fg="#a78bfa", font=("Segoe UI Semibold", 8)), "gsi_title").pack(anchor="w")
        gsi_controls = ttk.Frame(gsi_panel)
        gsi_controls.pack(fill="x", pady=(2, 0))
        gsi_label = tk.Label(gsi_controls, textvariable=self.gsi_var, bg="#191820", fg="#b7b9c6", font=("Segoe UI", 8), wraplength=400, justify="left")
        gsi_label.pack(side="left", anchor="w", fill="x", expand=True)
        self.localized(ttk.Button(gsi_controls, style="Action.TButton", command=self.repair_gsi), "gsi_repair").pack(side="right", padx=(8, 0))

        actions = ttk.Frame(main)
        actions.pack(fill="x")
        left_controls = ttk.Frame(actions)
        left_controls.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right_controls = ttk.Frame(actions)
        right_controls.pack(side="right", fill="x", expand=True)

        self.autostart_button = ttk.Button(
            left_controls, style="Action.TButton", command=self.toggle_autostart,
        )
        self.autostart_button.pack(fill="x", pady=(0, 6))
        self.language_menu_button = ttk.Menubutton(left_controls, style="Action.TMenubutton")
        self.language_menu_button.pack(fill="x")
        self.language_menu = tk.Menu(
            self.language_menu_button, tearoff=False, bg="#201d2b", fg="#f3f3f7",
            activebackground="#3a3152", activeforeground="#ffffff", bd=0,
        )
        self.language_menu.add_command(label="Русский", command=lambda: self.select_language("ru"))
        self.language_menu.add_command(label="English", command=lambda: self.select_language("en"))
        self.language_menu_button.configure(menu=self.language_menu)

        self.localized(ttk.Button(right_controls, style="Action.TButton", command=self.hide_to_tray), "tray").pack(fill="x", pady=(0, 6))
        self.update_button = self.localized(ttk.Button(
            right_controls, style="Action.TButton", command=lambda: self.check_for_updates(manual=True),
        ), "check_updates")
        self.update_button.pack(fill="x")
        self.refresh_settings_controls()

        def resize_wrapped_labels(event):
            wrap = max(220, event.width - 48)
            status_label.configure(wraplength=wrap)
            gsi_label.configure(wraplength=wrap)

        main.bind("<Configure>", resize_wrapped_labels)

    def check_for_updates(self, manual: bool = False):
        if self.update_check_running:
            return
        self.update_check_running = True
        self.set_status("update_checking")
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
                if not isinstance(tag, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
                    raise ValueError("Invalid release version")
                if compare_versions(tag, APP_VERSION) <= 0:
                    current_release = True
                else:
                    update = parse_release_update(release)
                    if update is None:
                        raise ValueError("The release does not contain the expected Windows executable")
            except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError) as exc:
                error = exc
            try:
                self.root.after(0, lambda: self.finish_update_check(update, error, current_release, manual))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=worker, name="DotaActivityUpdateCheck", daemon=True).start()

    def finish_update_check(self, update: dict | None, error: Exception | None, current: bool, manual: bool):
        self.update_check_running = False
        if getattr(self, "update_button", None):
            self.update_button.configure(state="normal")
        if error:
            self.set_status("update_unavailable")
            if manual:
                messagebox.showerror(self.tr("update_error_title"), self.tr("update_unavailable"))
            return
        if current or update is None:
            self.set_status("update_current", version=APP_VERSION)
            if manual:
                messagebox.showinfo(self.tr("update_none_title"), self.tr("update_none", version=APP_VERSION))
            return

        self.latest_available_version = update["version"]
        if not manual:
            self.set_status("update_available", version=update["version"])
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
            self.set_status("update_available", version=update["version"])

    def download_update(self, update: dict):
        self.update_download_running = True
        self.set_status("update_downloading")
        if getattr(self, "update_button", None):
            self.update_button.configure(state="disabled")

        def worker():
            path = None
            error = None
            temporary = None
            digest = hashlib.sha256()
            try:
                download_dir = update_download_directory(bool(getattr(sys, "frozen", False)))
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
                        digest.update(block)
                if total == 0:
                    raise ValueError("Downloaded file is empty")
                if not sha256_matches(digest.hexdigest(), update["sha256"]):
                    raise ValueError("The downloaded file failed its SHA-256 integrity check")
                os.replace(temporary, path)
            except (OSError, ValueError, KeyError, urllib.error.URLError, http.client.HTTPException) as exc:
                error = exc
                if temporary:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
            try:
                self.root.after(0, lambda: self.finish_update_download(path, error))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=worker, name="DotaActivityUpdateDownload", daemon=True).start()

    def finish_update_download(self, path: Path | None, error: Exception | None):
        self.update_download_running = False
        if getattr(self, "update_button", None):
            self.update_button.configure(state="normal")
        if error or path is None:
            messagebox.showerror(self.tr("update_download_title"), self.tr("update_download_error", error=error))
            return
        if getattr(sys, "frozen", False):
            messagebox.showinfo(self.tr("update_downloaded_title"), self.tr("update_installing"))
            launch_args = ["--background"] if "--background" in sys.argv[1:] else []
            command = update_helper_command(path, Path(sys.executable), os.getpid(), launch_args)
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            try:
                subprocess.Popen(command, cwd=str(path.parent), close_fds=True, creationflags=creationflags)
            except OSError as exc:
                messagebox.showerror(
                    self.tr("update_download_title"),
                    self.tr("update_install_error", error=exc, path=path),
                )
                return
            self.exit_app()
            return
        messagebox.showinfo(self.tr("update_downloaded_title"), self.tr("update_downloaded", path=path))

    def ensure_gsi(self):
        cfg_dir = find_dota_cfg_dir()
        if cfg_dir is None:
            self.dota_cfg_dir = None
            self.set_gsi_status("steam_search")
            return
        try:
            target = install_gsi_config(cfg_dir, self.gsi_token)
            self.dota_cfg_dir = cfg_dir
            self.set_gsi_status("dota_found", library=target.parent.parent.parent.name)
            self.save_settings()
        except OSError as exc:
            self.dota_cfg_dir = None
            self.set_gsi_status("gsi_error", error=exc)

    def start_server(self):
        GSIHandler.token = self.gsi_token
        try:
            self.server = GSIHTTPServer(("127.0.0.1", GSI_PORT), GSIHandler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            if self.dota_running:
                self.set_status("game_started")
            else:
                self.set_status("server_ready")
        except OSError:
            self.server = None
            self.set_status("server_error")

    def repair_gsi(self):
        self.ensure_gsi()
        if self.server is None:
            self.start_server()

    def toggle_autostart(self):
        enabled = not bool(self.autostart_var.get())
        self.autostart_var.set(enabled)
        try:
            set_windows_autostart(enabled)
        except (OSError, ImportError) as exc:
            self.autostart_var.set(not enabled)
            self.refresh_settings_controls()
            messagebox.showerror(self.tr("autostart_error_title"), self.tr("autostart_error", error=exc))
            return
        self.refresh_settings_controls()
        self.set_status("autostart_enabled" if enabled else "autostart_disabled")

    def refresh_settings_controls(self):
        autostart_button = getattr(self, "autostart_button", None)
        if autostart_button is not None:
            enabled = bool(self.autostart_var.get())
            autostart_button.configure(
                text=self.tr("autostart_on" if enabled else "autostart_off"),
                style="Selected.TButton" if enabled else "Action.TButton",
            )
        language_button = getattr(self, "language_menu_button", None)
        if language_button is not None:
            language = self.language_var.get()
            language_button.configure(text=f'{self.tr("language")} · {language}')

    def select_language(self, language: str):
        self.language_var.set("English" if language == "en" else "Русский")
        self.change_language()

    def try_connect(self):
        if not self.dota_running:
            return
        if self.rpc or time.monotonic() - self.last_rpc_attempt < 5:
            return
        self.last_rpc_attempt = time.monotonic()
        app_id = os.environ.get("DOTA_ACTIVITY_DISCORD_APP_ID", DISCORD_APPLICATION_ID).strip()
        if not app_id.isdigit():
            self.set_status("app_id_missing")
            return
        try:
            from pypresence import Presence
            rpc = Presence(app_id)
            rpc.connect()
            self.rpc = rpc
            self.last_rpc_payload = None
            self.set_status("rpc_connected")
            current = self.last_presence or {
                "status": "В главном меню", "details": "Готовится к игре", "state": "Dota 2",
                "large_image": DOTA_LOGO_URL, "large_text": "Dota 2",
            }
            self.send_presence(current)
        except Exception:
            self.rpc = None
            self.set_status("rpc_wait")

    def send_presence(self, data: dict):
        if not self.dota_running:
            return
        if data.get("_clear"):
            self.last_presence = None
            self.last_rpc_payload = None
            if self.rpc:
                try:
                    self.rpc.clear()
                except Exception:
                    pass
            self.state_var.set(self.tr("activity_default"))
            self.details_var.set(self.tr("activity_details"))
            return
        self.last_presence = data
        self.state_var.set(self.ui_text(data.get("status", "Dota 2")))
        self.details_var.set(self.ui_text(data.get("details", "")))
        if not self.rpc:
            return
        try:
            # Use public Dota image URLs; no custom Discord asset upload is needed.
            discord_data = localized_presence(data, self.language)
            kwargs = {
                "name": DISCORD_GAME_NAME,
                "details": discord_data.get("details", "Playing Dota 2"),
                "state": discord_data.get("state", "Dota 2"),
                "large_image": discord_data.get("large_image", DOTA_LOGO_URL),
                "large_text": discord_data.get("large_text", "Dota 2"),
            }
            if discord_data.get("small_image"):
                kwargs["small_image"] = discord_data["small_image"]
                kwargs["small_text"] = discord_data.get("small_text", "Dota 2")
            if discord_data.get("start"):
                kwargs["start"] = discord_data["start"]
            if kwargs == self.last_rpc_payload:
                return
            self.rpc.update(**kwargs)
            self.last_rpc_payload = kwargs
            self.set_status("rpc_published")
        except Exception:
            self.set_status("rpc_lost")
            try:
                self.rpc.close()
            except Exception:
                pass
            self.rpc = None
            self.last_rpc_attempt = 0

    def poll_events(self):
        latest = _NO_GSI_EVENT
        while True:
            try:
                latest = self.events.get_nowait()
            except queue.Empty:
                break
        if latest is not _NO_GSI_EVENT:
            if latest is not None and not latest.get("_clear"):
                self.last_gsi_update = time.monotonic()
            elif latest is None or latest.get("_clear"):
                self.last_gsi_update = None
            self.send_presence(latest if latest is not None else {"_clear": True})
        self.root.after(500, self.poll_events)

    def maintenance(self):
        if hasattr(self, "server") and self.server is None and not getattr(self, "_exiting", False):
            self.start_server()
        if self.dota_cfg_dir is None:
            self.ensure_gsi()
        if not self.process_check_running and not getattr(self, "_exiting", False):
            self.process_check_running = True
            threading.Thread(target=self._check_dota_process, name="DotaActivityProcessCheck", daemon=True).start()
        if (self.dota_running and self.last_presence and self.last_gsi_update is not None
                and time.monotonic() - self.last_gsi_update > 90):
            self.last_gsi_update = None
            self.send_presence({"_clear": True})
        if self.dota_running and self.rpc is None:
            self.try_connect()
        self.root.after(2500, self.maintenance)

    def _check_dota_process(self):
        running = is_dota_running()
        try:
            self.root.after(0, lambda: self._apply_dota_process_state(running))
        except (RuntimeError, tk.TclError):
            self.process_check_running = False

    def _apply_dota_process_state(self, running: bool):
        self.process_check_running = False
        if getattr(self, "_exiting", False) or running == self.dota_running:
            return
        if running != self.dota_running:
            self.dota_running = running
            if running:
                self.last_rpc_attempt = 0.0
                self.state_var.set(self.tr("activity_default"))
                self.details_var.set(self.tr("activity_details"))
                self.set_status("game_started")
            else:
                self.disconnect_rpc()
                self.last_presence = None
                self.last_gsi_update = None
                self.state_var.set(self.tr("game_closed"))
                self.details_var.set(self.tr("game_closed_details"))
                self.set_status("waiting")
        if running and self.rpc is None:
            self.try_connect()

    def _create_tray_icon(self):
        import pystray
        from PIL import Image

        with Image.open(resource_path(APP_ICON_PNG)) as source:
            image = source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        self.tray_icon = pystray.Icon("DotaActivity", image, APP_NAME, self.build_tray_menu())
        threading.Thread(target=self.tray_icon.run, name="DotaActivityTray", daemon=True).start()

    def hide_to_tray(self):
        if self.tray_icon is None:
            try:
                self._create_tray_icon()
            except Exception as exc:
                self.root.deiconify()
                self.root.lift()
                messagebox.showerror(self.tr("tray_error_title"), self.tr("tray_error", error=exc))
                return
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def disconnect_rpc(self):
        rpc, self.rpc = self.rpc, None
        self.last_rpc_payload = None
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
    start_hidden = "--background" in sys.argv[1:]
    readiness_file = None
    if "--update-ready-file" in sys.argv[1:]:
        index = sys.argv.index("--update-ready-file")
        if index + 1 < len(sys.argv):
            readiness_file = Path(sys.argv[index + 1])
    if not acquire_single_instance():
        if not start_hidden:
            language = initial_language(DotaActivityApp.load_settings())
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                TEXT[language]["already_running_title"],
                TEXT[language]["already_running"],
            )
            root.destroy()
        return
    root = tk.Tk()
    DotaActivityApp(root, start_hidden=start_hidden, readiness_file=readiness_file)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--apply-update":
        try:
            if len(sys.argv) < 4:
                raise ValueError("Missing process ID or install path")
            apply_staged_update(int(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
        except Exception as exc:
            show_update_helper_error(exc)
    else:
        main()
