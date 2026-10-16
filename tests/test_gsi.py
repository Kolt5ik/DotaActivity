import unittest
import tempfile
import io
import json
import queue
from pathlib import Path

from app import DOTA_LOGO_URL, DISCORD_APPLICATION_ID, GSIHandler, find_dota_cfg_dir, gsi_config_text, install_gsi_config, presence_from_gsi, prettify_hero, steam_roots_from_vdf


class GSIHandlerTestDouble:
    def __init__(self, body):
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)
        self.token = "test"
        self.events = queue.Queue()
        self.errors = []

    def send_error(self, code):
        self.errors.append(code)


class GsiParsingTests(unittest.TestCase):
    def test_gsi_handler_rejects_non_object_json(self):
        handler = GSIHandlerTestDouble(b"[]")
        GSIHandler.do_POST(handler)
        self.assertEqual(handler.errors, [400])

    def test_gsi_handler_rejects_malformed_nested_fields(self):
        handler = GSIHandlerTestDouble(json.dumps({"auth": {"token": "test"}, "map": []}).encode())
        GSIHandler.do_POST(handler)
        self.assertEqual(handler.errors, [400])

    def test_discord_application_id_is_embedded(self):
        self.assertTrue(DISCORD_APPLICATION_ID.isdigit())

    def test_hero_name(self):
        self.assertEqual(prettify_hero("npc_dota_hero_axe"), "Axe")
        self.assertEqual(prettify_hero("npc_dota_hero_rattletrap"), "Clockwerk")

    def test_ranked_presence_uses_hero_portrait(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", "game_time": 90, "game_mode": 22},
            "player": {"kills": 4, "deaths": 2, "assists": 7, "net_worth": 8400},
            "hero": {"name": "npc_dota_hero_axe"},
        })
        self.assertEqual(result["status"], "В игре")
        self.assertEqual(result["details"], "Axe · 4/2/7 · 8 400 NW")
        self.assertEqual(result["state"], "Рейтинг · All Pick")
        self.assertEqual(result["large_image"], "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/axe.png")

    def test_hero_selection_uses_dota_logo_until_match_starts(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_HERO_SELECTION", "game_mode": 22},
            "hero": {"name": "npc_dota_hero_invoker"},
        })
        self.assertEqual(result["status"], "Выбирает героя")
        self.assertEqual(result["details"], "Выбирает героя")
        self.assertEqual(result["large_image"], DOTA_LOGO_URL)
        self.assertEqual(result["state"], "Рейтинг · All Pick")

    def test_hero_selection_without_hero_keeps_generic_status(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_HERO_SELECTION"},
        })
        self.assertEqual(result["details"], "Выбирает героя")

    def test_training_and_bot_lobbies_are_distinguished(self):
        training = presence_from_gsi({"map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", "game_mode": 10}})
        bots = presence_from_gsi({"map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", "game_mode": 1, "lobby_type": 4}})
        self.assertEqual(training["state"], "Тренировка")
        self.assertEqual(bots["state"], "Против ботов")

    def test_local_practice_without_match_id_is_not_labeled_as_normal(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", "game_mode": 1, "matchid": 0},
            "hero": {"name": "npc_dota_hero_rattletrap"},
        })
        self.assertEqual(result["state"], "Тренировка")
        self.assertIn("Clockwerk", result["details"])

    def test_online_all_pick_with_match_id_stays_normal(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", "game_mode": 1, "matchid": 12345},
        })
        self.assertEqual(result["state"], "Обычная игра · All Pick")

    def test_post_game_state(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_POST_GAME", "win_team": "team2"},
            "player": {"team_name": "team2", "kills": 2, "deaths": 3, "assists": 8},
            "hero": {"name": "npc_dota_hero_juggernaut"},
        })
        self.assertIn("Победа", result["details"])

    def test_discovers_dota_in_a_secondary_steam_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            steam = Path(temporary) / "Steam"
            library = Path(temporary) / "Games"
            cfg = library / "steamapps" / "common" / "dota 2 beta" / "game" / "dota" / "cfg"
            cfg.mkdir(parents=True)
            vdf = f'"libraryfolders" {{ "1" {{ "path" "{str(library).replace(chr(92), chr(92)*2)}" }} }}'
            roots = steam_roots_from_vdf(steam, vdf)
            self.assertEqual(find_dota_cfg_dir(roots), cfg)

    def test_writes_gsi_config_and_reuses_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            cfg = Path(temporary) / "cfg"
            target = install_gsi_config(cfg, "test-token")
            self.assertTrue(target.is_file())
            self.assertIn('"token" "test-token"', target.read_text(encoding="utf-8"))
            before = target.stat().st_mtime_ns
            self.assertEqual(install_gsi_config(cfg, "test-token"), target)
            self.assertEqual(target.stat().st_mtime_ns, before)

    def test_gsi_configuration_uses_localhost(self):
        config = gsi_config_text("abc")
        self.assertIn('"uri" "http://127.0.0.1:38174/"', config)
        self.assertNotIn("0.0.0.0", config)
        self.assertIn('"draft" "1"', config)


if __name__ == "__main__":
    unittest.main()
