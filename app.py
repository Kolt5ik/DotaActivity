from __future__ import annotations

import json
import os
import queue
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

APP_NAME = "Dota Activity"
GSI_PORT = 38174
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "DotaActivity"
SETTINGS_PATH = APP_DIR / "settings.json"
STATUS_LABELS = {
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
    5: "All Random", 11: "Mid Only", 12: "Least Played", 13: "Limited Heroes",
    15: "Custom", 16: "Captains Draft", 18: "Ability Draft", 19: "Event",
    22: "Ranked All Pick", 23: "Turbo", 24: "Mutation",
}


def prettify_hero(raw: str) -> str:
    name = raw.removeprefix("npc_dota_hero_").replace("_", " ").strip()
    return name.title() if name else "Dota 2"


def hero_asset(raw: str) -> str:
    return raw.removeprefix("npc_dota_hero_") if raw else ""


def presence_from_gsi(payload: dict) -> dict | None:
    """Convert a Dota GSI payload to a Discord presence description."""
    map_data = payload.get("map") or {}
    player = payload.get("player") or {}
    hero = payload.get("hero") or {}
    state = str(map_data.get("game_state", ""))
    game_time = map_data.get("game_time")
    hero_name = prettify_hero(str(hero.get("name", "")))
    mode_id = map_data.get("game_mode")
    mode = GAME_MODES.get(mode_id, "Dota 2") if isinstance(mode_id, int) else "Dota 2"

    if state in {"DOTA_GAMERULES_STATE_HERO_SELECTION", "DOTA_GAMERULES_STATE_PRE_GAME"}:
        return {"status": "Матч найден", "details": f"Выбирает героя · {mode}", "image": "dota2"}

    if state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS":
        kills, deaths, assists = (player.get(k, 0) for k in ("kills", "deaths", "assists"))
        details = f"{hero_name} · {kills}/{deaths}/{assists}"
        net_worth = player.get("net_worth")
        if isinstance(net_worth, int):
            details += f" · {net_worth:,} NW".replace(",", " ")
        start = int(time.time() - game_time) if isinstance(game_time, (int, float)) and game_time > 0 else None
        return {"status": "В игре", "details": details, "state": mode, "image": "dota2", "hero_image": hero_asset(hero.get("name", "")), "start": start}

    if state == "DOTA_GAMERULES_STATE_POST_GAME":
        win_team = map_data.get("win_team")
        team = player.get("team_name")
        outcome = "Победа" if win_team and team and win_team == team else "Матч завершён"
        kda = f"{player.get('kills', 0)}/{player.get('deaths', 0)}/{player.get('assists', 0)}"
        return {"status": "После матча", "details": f"{outcome} · {hero_name} · {kda}", "image": "dota2", "hero_image": hero_asset(hero.get("name", ""))}

    return None


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


class DotaPresenceApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Dota Activity")
        self.root.geometry("520x470")
        self.root.minsize(480, 440)
        self.root.configure(bg="#101116")
        self.rpc = None
        self.server: ThreadingHTTPServer | None = None
        self.gsi_token = secrets.token_urlsafe(24)
        self.events: queue.Queue = GSIHandler.events
        self.last_presence: dict | None = None
        self.app_id_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Отключено")
        self.state_var = tk.StringVar(value="Главное меню")
        self.folder_var = tk.StringVar(value="Папка Dota 2 не выбрана")
        self.details_var = tk.StringVar(value="Готовится к игре")
        self.load_settings()
        self.build_ui()
        if self.gsi_token and self.folder_var.get() != "Папка Dota 2 не выбрана":
            self.start_server()
        self.root.after(500, self.poll_events)
        if self.app_id_var.get().strip():
            self.root.after(300, self.connect)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def load_settings(self):
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            self.app_id_var.set(settings.get("discord_app_id", ""))
            self.folder_var.set(settings.get("dota_cfg_dir", "Папка Dota 2 не выбрана"))
            self.gsi_token = settings.get("gsi_token", "")
        except (OSError, json.JSONDecodeError):
            pass

    def save_settings(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps({
            "discord_app_id": self.app_id_var.get().strip(),
            "dota_cfg_dir": self.folder_var.get() if self.folder_var.get() != "Папка Dota 2 не выбрана" else "",
            "gsi_token": self.gsi_token,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101116")
        style.configure("TLabel", background="#101116", foreground="#e9e9ef", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 20), foreground="#f4c95d")
        style.configure("Muted.TLabel", foreground="#9a9baa", font=("Segoe UI", 9))
        style.configure("TButton", background="#252735", foreground="#f1f1f5", padding=8, borderwidth=0)
        style.map("TButton", background=[("active", "#373b4e")])
        style.configure("TEntry", fieldbackground="#1d202b", foreground="#f1f1f5", borderwidth=0, padding=7)
        style.configure("TCombobox", fieldbackground="#1d202b", background="#252735", foreground="#f1f1f5", padding=6)

        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="DOTA PRESENCE", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Статус Dota 2 для Discord", style="Muted.TLabel").pack(anchor="w", pady=(0, 16))

        card = tk.Frame(main, bg="#202230", padx=16, pady=14)
        card.pack(fill="x", pady=(0, 14))
        tk.Label(card, text="ИГРАЕТ В DOTA 2", bg="#202230", fg="#9a9baa", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=self.state_var, bg="#202230", fg="#f3f3f7", font=("Segoe UI Semibold", 15)).pack(anchor="w", pady=(6, 0))
        tk.Label(card, textvariable=self.details_var, bg="#202230", fg="#c6c7d2", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))
        self.presence_status = tk.Label(card, textvariable=self.status_var, bg="#202230", fg="#f4c95d", font=("Segoe UI", 9))
        self.presence_status.pack(anchor="w", pady=(8, 0))

        row = ttk.Frame(main)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Discord Application ID").pack(anchor="w")
        entryrow = ttk.Frame(row)
        entryrow.pack(fill="x", pady=(4, 0))
        ttk.Entry(entryrow, textvariable=self.app_id_var).pack(side="left", fill="x", expand=True)
        ttk.Button(entryrow, text="Подключить", command=self.connect).pack(side="left", padx=(8, 0))

        row2 = ttk.Frame(main)
        row2.pack(fill="x", pady=(10, 0))
        ttk.Label(row2, text="Ручной статус").pack(anchor="w")
        chooser = ttk.Frame(row2)
        chooser.pack(fill="x", pady=(4, 0))
        ttk.Combobox(chooser, textvariable=self.state_var, values=list(STATUS_LABELS), state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(chooser, text="Показать", command=self.apply_manual).pack(side="left", padx=(8, 0))

        ttk.Separator(main).pack(fill="x", pady=14)
        ttk.Label(main, text="Dota 2 Game State Integration", font=("Segoe UI Semibold", 10)).pack(anchor="w")
        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(5, 0))
        ttk.Label(bottom, textvariable=self.folder_var, style="Muted.TLabel", wraplength=320).pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Установить GSI-конфиг", command=self.install_gsi).pack(side="right")
        ttk.Label(main, text="Автообновление: выбор героя · игра · после матча", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def connect(self):
        app_id = self.app_id_var.get().strip()
        if not app_id.isdigit():
            messagebox.showerror("Неверный ID", "Вставь числовой Discord Application ID.")
            return
        self.save_settings()
        self.disconnect_rpc()
        try:
            from pypresence import Presence
            self.rpc = Presence(app_id)
            self.rpc.connect()
            self.status_var.set("Подключено к Discord")
            self.send_presence({"status": "Главное меню", "details": "Готовится к игре", "image": "dota2"})
        except Exception as exc:
            self.rpc = None
            self.status_var.set("Не удалось подключиться к Discord")
            messagebox.showerror("Discord RPC", f"Убедись, что Discord запущен.\n\n{exc}")

    def disconnect_rpc(self):
        if self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass
            self.rpc = None

    def send_presence(self, data: dict):
        self.last_presence = data
        self.state_var.set(data.get("status", "Dota 2"))
        self.details_var.set(data.get("details", ""))
        if not self.rpc:
            return
        try:
            kwargs = {"details": data.get("details", "Playing Dota 2"), "state": data.get("state", "Dota 2"), "large_image": data.get("image", "dota2"), "large_text": "Dota 2"}
            if data.get("hero_image"):
                kwargs.update(small_image=data["hero_image"], small_text=data.get("status", ""))
            if data.get("start"):
                kwargs["start"] = data["start"]
            self.rpc.update(**kwargs)
            self.status_var.set("Статус опубликован в Discord")
        except Exception as exc:
            self.status_var.set(f"Ошибка Discord RPC: {exc}")

    def apply_manual(self):
        label = self.state_var.get()
        details, state = STATUS_LABELS.get(label, STATUS_LABELS["Главное меню"])
        self.send_presence({"status": label, "details": details, "state": state, "image": "dota2"})

    def install_gsi(self):
        selected = filedialog.askdirectory(title="Выбери папку game\\dota\\cfg в Dota 2")
        if not selected:
            return
        root_path = Path(selected)
        if root_path.name.lower() != "cfg" or root_path.parent.name.lower() != "dota":
            if not messagebox.askyesno("Проверь папку", "Лучше выбрать ...\\game\\dota\\cfg. Установить конфиг в выбранную папку?\n\n" + selected):
                return
        integration_dir = root_path / "gamestate_integration"
        integration_dir.mkdir(parents=True, exist_ok=True)
        self.gsi_token = secrets.token_urlsafe(24)
        config = f'''"Dota Activity"
{{
    "uri" "http://127.0.0.1:{GSI_PORT}/"
    "timeout" "5.0"
    "buffer" "0.1"
    "throttle" "0.5"
    "heartbeat" "30.0"
    "auth"
    {{
        "token" "{self.gsi_token}"
    }}
    "data"
    {{
        "provider" "1"
        "map" "1"
        "player" "1"
        "hero" "1"
    }}
}}
'''
        target = integration_dir / "gamestate_integration_dotapresence.cfg"
        target.write_text(config, encoding="utf-8")
        GSIHandler.token = self.gsi_token
        self.folder_var.set(str(root_path))
        self.save_settings()
        self.start_server()
        if self.server:
            messagebox.showinfo("GSI установлен", f"Создан файл:\n{target}\n\nПерезапусти Dota 2, чтобы начать получать события.")

    def start_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        GSIHandler.token = self.gsi_token
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", GSI_PORT), GSIHandler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            self.status_var.set("GSI включён · ожидаю события Dota 2")
        except OSError as exc:
            self.status_var.set("Не удалось запустить локальный GSI сервер")
            messagebox.showerror("Локальный сервер", f"Не удалось открыть порт {GSI_PORT}.\n{exc}")

    def poll_events(self):
        latest = None
        while True:
            try:
                latest = self.events.get_nowait()
            except queue.Empty:
                break
        if latest:
            self.send_presence(latest)
        self.root.after(1000, self.poll_events)

    def close(self):
        self.save_settings()
        self.disconnect_rpc()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.root.destroy()


def main():
    root = tk.Tk()
    DotaPresenceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
