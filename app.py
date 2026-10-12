from __future__ import annotations

import json
import os
import queue
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import ttk

APP_NAME = "Dota Activity"
DISCORD_GAME_NAME = "Dota"
GSI_PORT = 38174
DISCORD_APPLICATION_ID = "1559228191195922513"
STEAM_ASSET_ROOT = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react"
DOTA_LOGO_URL = f"{STEAM_ASSET_ROOT}/global/dota2_logo_horiz.png"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "DotaActivity"
SETTINGS_PATH = APP_DIR / "settings.json"
GSI_FILENAME = "gamestate_integration_dotapresence.cfg"
GSI_STATES = {
    "Главное меню": ("В главном меню", "Готовится к игре"),
    "Поиск матча": ("Ищет матч", "Подбор игры в Dota 2"),
    "Матч найден": ("Выбирает героя", "Подготовка к матчу"),
    "В игре": ("Играет в Dota 2", "Матч в процессе"),
    "После матча": ("Завершил матч", "Смотрит результаты"),
    "Наблюдение": ("Смотрит матч", "Наблюдает за игрой"),
    "Приватное лобби": ("В приватном лобби", "Играет с друзьями"),
}
GAME_MODES = {
    1: "All Pick", 2: "Captains Mode", 3: "Random Draft", 4: "Single Draft",
    5: "All Random", 7: "Diretide", 8: "Reverse Captains Mode", 9: "Greeviling",
    10: "Тренировка", 11: "Mid Only", 12: "Least Played", 13: "Limited Heroes",
    14: "Compendium Matchmaking", 15: "Custom", 16: "Captains Draft",
    18: "Ability Draft", 19: "Event", 20: "All Random Deathmatch",
    21: "1v1 Mid", 22: "All Pick", 23: "Turbo", 24: "Mutation",
}
LOBBY_TYPES = {1: "Тренировка", 2: "Турнир", 3: "Обучение", 4: "Против ботов", 7: "Рейтинг"}


def prettify_hero(raw: str) -> str:
    name = raw.removeprefix("npc_dota_hero_").replace("_", " ").strip()
    return name.title() if name else "Dota 2"


def hero_asset(raw: str) -> str:
    hero = raw.removeprefix("npc_dota_hero_") if raw else ""
    return {"windrunner": "windranger", "abyssal_underlord": "underlord"}.get(hero, hero)


def game_context(map_data: dict) -> str:
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
    mode = game_context(map_data)

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
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("460x340")
        self.root.minsize(420, 300)
        self.root.configure(bg="#101116")
        self.rpc = None
        self.tray_icon = None
        self.server: ThreadingHTTPServer | None = None
        self.events: queue.Queue = queue.Queue()
        GSIHandler.events = self.events
        self.settings = self.load_settings()
        self.gsi_token = self.settings.get("gsi_token") or secrets.token_urlsafe(24)
        self.status_var = tk.StringVar(value="Запуск…")
        self.state_var = tk.StringVar(value="В главном меню")
        self.details_var = tk.StringVar(value="Готовится к игре")
        self.manual_var = tk.StringVar(value="Главное меню")
        self.gsi_var = tk.StringVar(value="Ищу установленную Dota 2…")
        self.last_presence: dict | None = None
        self.dota_cfg_dir: Path | None = None
        self.last_rpc_attempt = 0.0
        self.build_ui()
        GSIHandler.token = self.gsi_token
        self.ensure_gsi()
        self.start_server()
        self.root.after(200, self.try_connect)
        self.root.after(500, self.poll_events)
        self.root.after(5000, self.maintenance)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

    @staticmethod
    def load_settings() -> dict:
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return settings if isinstance(settings, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_settings(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps({"gsi_token": self.gsi_token}, indent=2), encoding="utf-8")

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101116")
        style.configure("TLabel", background="#101116", foreground="#e9e9ef", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 20), foreground="#f4c95d")
        style.configure("Muted.TLabel", foreground="#9a9baa", font=("Segoe UI", 9))
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="DOTA ACTIVITY", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Статус Dota 2 для Discord", style="Muted.TLabel").pack(anchor="w", pady=(0, 16))
        card = tk.Frame(main, bg="#202230", padx=16, pady=14)
        card.pack(fill="x", pady=(0, 12))
        tk.Label(card, text="АКТИВНОСТЬ В DISCORD", bg="#202230", fg="#9a9baa", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=self.state_var, bg="#202230", fg="#f3f3f7", font=("Segoe UI Semibold", 15)).pack(anchor="w", pady=(6, 0))
        tk.Label(card, textvariable=self.details_var, bg="#202230", fg="#c6c7d2", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))
        tk.Label(card, textvariable=self.status_var, bg="#202230", fg="#f4c95d", font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))
        ttk.Label(main, textvariable=self.gsi_var, style="Muted.TLabel", wraplength=400).pack(anchor="w", pady=(4, 0))
        manual = ttk.Frame(main)
        manual.pack(fill="x", pady=(12, 0))
        ttk.Label(manual, text="Состояние вручную (если Dota его не передала)").pack(side="left", fill="x", expand=True)
        ttk.Combobox(manual, textvariable=self.manual_var, values=list(GSI_STATES), state="readonly", width=18).pack(side="left", padx=(8, 0))
        ttk.Button(manual, text="Показать", command=self.apply_manual).pack(side="left", padx=(6, 0))
        ttk.Label(main, text="Оставь приложение и Discord запущенными во время игры.", style="Muted.TLabel", wraplength=400).pack(anchor="w", pady=(8, 0))
        ttk.Button(main, text="Свернуть в трей", command=self.hide_to_tray).pack(anchor="e", pady=(10, 0))

    def ensure_gsi(self):
        cfg_dir = find_dota_cfg_dir()
        if cfg_dir is None:
            self.dota_cfg_dir = None
            self.gsi_var.set("Ищу Dota 2 в библиотеках Steam…")
            return
        try:
            target = install_gsi_config(cfg_dir, self.gsi_token)
            self.dota_cfg_dir = cfg_dir
            self.gsi_var.set(f"Dota 2 найдена · GSI настроен автоматически ({target.parent.parent.parent.name})")
            self.save_settings()
        except OSError as exc:
            self.dota_cfg_dir = None
            self.gsi_var.set(f"Не удалось настроить Dota 2: {exc}")

    def start_server(self):
        GSIHandler.token = self.gsi_token
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", GSI_PORT), GSIHandler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            self.status_var.set("Локальное подключение готово · ожидаю Discord")
        except OSError:
            self.status_var.set("Не удалось открыть локальный порт для Dota 2")

    def try_connect(self):
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
            self.status_var.set("Подключено к Discord")
            self.send_presence({"status": "Главное меню", "details": "Готовится к игре", "image": "dota2"})
        except Exception:
            self.rpc = None
            self.status_var.set("Открой настольный Discord · повторное подключение…")

    def send_presence(self, data: dict):
        self.last_presence = data
        self.state_var.set(data.get("status", "Dota 2"))
        self.details_var.set(data.get("details", ""))
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
            self.status_var.set("Статус Dota 2 опубликован в Discord")
        except Exception:
            self.status_var.set("Потеряна связь с Discord · переподключаюсь…")
            try:
                self.rpc.close()
            except Exception:
                pass
            self.rpc = None
            self.last_rpc_attempt = 0

    def apply_manual(self):
        label = self.manual_var.get()
        details, state = GSI_STATES.get(label, GSI_STATES["Главное меню"])
        self.send_presence({"status": label, "details": details, "state": state, "image": "dota2"})

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
        if self.rpc is None:
            self.try_connect()
        self.root.after(5000, self.maintenance)

    def _create_tray_icon(self):
        import pystray
        from PIL import Image, ImageDraw

        image = Image.new("RGBA", (64, 64), (16, 17, 22, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((7, 7, 57, 57), fill=(232, 64, 54, 255))
        draw.polygon(((32, 14), (45, 48), (32, 42), (19, 48)), fill=(255, 255, 255, 255))
        menu = pystray.Menu(
            pystray.MenuItem("Открыть Dota Activity", lambda _icon, _item: self.root.after(0, self.show_window)),
            pystray.MenuItem("Выход", lambda _icon, _item: self.root.after(0, self.exit_app)),
        )
        self.tray_icon = pystray.Icon("DotaActivity", image, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, name="DotaActivityTray", daemon=True).start()

    def hide_to_tray(self):
        if self.tray_icon is None:
            try:
                self._create_tray_icon()
            except Exception as exc:
                from tkinter import messagebox
                messagebox.showerror("Системный трей", f"Не удалось свернуть приложение в трей.\n\n{exc}")
                return
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

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
            if self.rpc:
                rpc, self.rpc = self.rpc, None
                try:
                    rpc.clear()
                except Exception:
                    pass
                try:
                    rpc.close()
                except Exception:
                    pass
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
    DotaActivityApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
