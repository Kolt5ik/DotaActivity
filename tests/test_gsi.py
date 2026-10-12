import unittest

from app import presence_from_gsi, prettify_hero


class GsiParsingTests(unittest.TestCase):
    def test_hero_name(self):
        self.assertEqual(prettify_hero("npc_dota_hero_axe"), "Axe")

    def test_in_game_presence(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", "game_time": 90, "game_mode": 22},
            "player": {"kills": 4, "deaths": 2, "assists": 7, "net_worth": 8400},
            "hero": {"name": "npc_dota_hero_axe"},
        })
        self.assertEqual(result["status"], "В игре")
        self.assertEqual(result["details"], "Axe · 4/2/7 · 8 400 NW")
        self.assertEqual(result["state"], "Ranked All Pick")

    def test_post_game_state(self):
        result = presence_from_gsi({
            "map": {"game_state": "DOTA_GAMERULES_STATE_POST_GAME", "win_team": "team2"},
            "player": {"team_name": "team2", "kills": 2, "deaths": 3, "assists": 8},
            "hero": {"name": "npc_dota_hero_juggernaut"},
        })
        self.assertIn("Победа", result["details"])


if __name__ == "__main__":
    unittest.main()
