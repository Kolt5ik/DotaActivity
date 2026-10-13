import unittest

import app


class GameContextTests(unittest.TestCase):
    def test_turbo_takes_precedence_over_ranked_lobby(self):
        self.assertEqual(app.game_context({"game_mode": 23, "lobby_type": 7}), "Turbo")

    def test_turbo_string_from_gsi_is_recognized(self):
        self.assertEqual(app.game_context({"game_mode": "DOTA_GAMEMODE_TURBO", "lobby_type": 7}), "Turbo")

    def test_ranked_all_pick_is_not_reported_as_normal(self):
        self.assertEqual(app.game_context({"game_mode": 1, "lobby_type": 7, "matchid": 123}), "Рейтинг")

    def test_plain_all_pick_keeps_normal_label(self):
        self.assertEqual(app.game_context({"game_mode": 1, "lobby_type": 0, "matchid": 123}), "Обычная игра · All Pick")

    def test_old_settings_migrate_default_language_to_english(self):
        settings = {"language": "ru"}
        self.assertEqual(app.initial_language(settings), "en")
        self.assertEqual(app.initial_language(settings), "en")

    def test_saved_language_is_preserved_after_migration(self):
        settings = {"language_settings_version": app.LANGUAGE_SETTINGS_VERSION, "language": "ru"}
        self.assertEqual(app.initial_language(settings), "ru")

    def test_presence_uses_centered_default_red_dota_logo(self):
        self.assertTrue(app.DOTA_LOGO_URL.endswith("/assets/dota-presence-centered.png"))


if __name__ == "__main__":
    unittest.main()
