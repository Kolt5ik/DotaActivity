import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app


class UpdateAndLanguageTests(unittest.TestCase):
    @staticmethod
    def next_release_tag():
        major, minor, patch = map(int, app.APP_VERSION.split("."))
        return f"v{major}.{minor}.{patch + 1}"

    def release(self, tag=None, *, prerelease=False, asset=True):
        tag = tag or self.next_release_tag()
        assets = []
        if asset:
            assets.append({
                "name": f"DotaActivity-{tag}-Windows-x64.exe",
                "browser_download_url": f"https://github.com/Kolt5ik/DotaActivity/releases/download/{tag}/DotaActivity-{tag}-Windows-x64.exe",
                "digest": "sha256:" + ("a" * 64),
            })
        return {"tag_name": tag, "draft": False, "prerelease": prerelease, "assets": assets, "body": "Fixes"}

    def test_finds_new_windows_release_asset(self):
        update = app.parse_release_update(self.release())
        self.assertIsNotNone(update)
        version = self.next_release_tag().removeprefix("v")
        self.assertEqual(update["version"], version)
        self.assertTrue(update["url"].endswith(f"DotaActivity-v{version}-Windows-x64.exe"))

    def test_ignores_current_or_older_versions(self):
        self.assertIsNone(app.parse_release_update(self.release("v0.0.11")))
        self.assertIsNone(app.parse_release_update(self.release("v0.0.10")))
        self.assertIsNone(app.parse_release_update(self.release("v0.0.4")))

    def test_ignores_prereleases_and_missing_windows_asset(self):
        self.assertIsNone(app.parse_release_update(self.release(prerelease=True)))
        self.assertIsNone(app.parse_release_update(self.release(asset=False)))

    def test_rejects_untrusted_download_hosts(self):
        release = self.release()
        release["assets"][0]["browser_download_url"] = "https://example.com/DotaActivity.exe"
        self.assertIsNone(app.parse_release_update(release))

    def test_rejects_asset_url_for_a_different_version(self):
        release = self.release()
        release["assets"][0]["browser_download_url"] = release["assets"][0]["browser_download_url"].replace(self.next_release_tag(), f"v{app.APP_VERSION}")
        self.assertIsNone(app.parse_release_update(release))

    def test_requires_github_sha256_digest(self):
        release = self.release()
        release["assets"][0].pop("digest")
        self.assertIsNone(app.parse_release_update(release))
        release = self.release()
        release["assets"][0]["digest"] = "sha1:" + ("a" * 40)
        self.assertIsNone(app.parse_release_update(release))

    def test_sha256_verification_rejects_mismatch_and_bad_input(self):
        digest = "a" * 64
        self.assertTrue(app.sha256_matches(digest, digest.upper()))
        self.assertFalse(app.sha256_matches(digest, "b" * 64))
        self.assertFalse(app.sha256_matches(digest, "not-a-digest"))

    def test_version_comparison(self):
        self.assertEqual(app.compare_versions("v0.0.10", "0.0.9"), 1)
        self.assertEqual(app.compare_versions("0.0.6", "v0.0.6"), 0)
        self.assertEqual(app.compare_versions("0.0.5", "0.0.6"), -1)

    def test_packaged_update_uses_private_staging_directory(self):
        app_dir = Path("C:/Users/example/AppData/Roaming/DotaActivity")
        with patch.object(app, "APP_DIR", app_dir):
            self.assertEqual(app.update_download_directory(True), app_dir / "updates")

    def test_source_update_stays_in_downloads(self):
        home = Path("C:/Users/example")
        self.assertEqual(app.update_download_directory(False, home), home / "Downloads")

    def test_update_helper_receives_process_and_target_paths(self):
        command = app.update_helper_command(
            Path("C:/Users/example/AppData/updates/new.exe"),
            Path("C:/Users/example/DotaActivity.exe"),
            1234,
            ["--background"],
        )
        self.assertEqual(Path(command[0]), Path("C:/Users/example/AppData/updates/new.exe"))
        self.assertEqual(command[1:3], ["--apply-update", "1234"])
        self.assertEqual(Path(command[3]), Path("C:/Users/example/DotaActivity.exe"))
        self.assertEqual(command[4:], ["--background"])

    def test_update_helper_waits_then_replaces_and_relaunches(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / "staged.exe"
            installed = root / "DotaActivity.exe"
            staged.write_bytes(b"new version")
            installed.write_bytes(b"old version")
            with (
                patch.object(app, "_is_windows", return_value=True),
                patch.object(app.sys, "frozen", True, create=True),
                patch.object(app.sys, "executable", str(staged)),
                patch.object(app, "_wait_for_process_exit") as wait,
                patch.object(app.subprocess, "Popen") as launch,
                patch.object(app.time, "sleep"),
            ):
                launch.return_value.poll.return_value = None
                def report_ready(command, **_kwargs):
                    marker = Path(command[command.index("--update-ready-file") + 1])
                    marker.write_text("ready", encoding="ascii")
                    return launch.return_value
                launch.side_effect = report_ready
                app.apply_staged_update(4321, installed, ["--background"])
            wait.assert_called_once_with(4321)
            self.assertEqual(installed.read_bytes(), b"new version")
            launch.assert_called_once()
            command = launch.call_args.args[0]
            options = launch.call_args.kwargs
            self.assertEqual(Path(command[0]).resolve(), installed.resolve())
            self.assertEqual(command[1:3], ["--background", "--update-ready-file"])
            self.assertFalse(Path(command[3]).exists())
            self.assertEqual(Path(options["cwd"]).resolve(), root.resolve())
            self.assertTrue(options["close_fds"])
            self.assertFalse(list(root.glob("*.bak")))

    def test_update_helper_restores_previous_executable_when_relaunch_fails(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / "staged.exe"
            installed = root / "DotaActivity.exe"
            staged.write_bytes(b"new version")
            installed.write_bytes(b"old version")
            with (
                patch.object(app, "_is_windows", return_value=True),
                patch.object(app.sys, "frozen", True, create=True),
                patch.object(app.sys, "executable", str(staged)),
                patch.object(app, "_wait_for_process_exit"),
                patch.object(app.subprocess, "Popen", side_effect=OSError("launch failed")),
                patch.object(app.time, "sleep"),
            ):
                with self.assertRaisesRegex(OSError, "launch failed"):
                    app.apply_staged_update(4321, installed)
            self.assertEqual(installed.read_bytes(), b"old version")
            self.assertEqual(staged.read_bytes(), b"new version")
            self.assertFalse(list(root.glob("*.bak")))

    def test_update_helper_restores_previous_executable_if_new_app_exits(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / "staged.exe"
            installed = root / "DotaActivity.exe"
            staged.write_bytes(b"new version")
            installed.write_bytes(b"old version")
            exited_process = type("ExitedProcess", (), {"poll": lambda _self: 1})()
            with (
                patch.object(app, "_is_windows", return_value=True),
                patch.object(app.sys, "frozen", True, create=True),
                patch.object(app.sys, "executable", str(staged)),
                patch.object(app, "_wait_for_process_exit"),
                patch.object(app.subprocess, "Popen", return_value=exited_process),
                patch.object(app.time, "sleep"),
            ):
                with self.assertRaisesRegex(RuntimeError, "exited before reporting readiness"):
                    app.apply_staged_update(4321, installed)
            self.assertEqual(installed.read_bytes(), b"old version")
            self.assertFalse(list(root.glob("*.bak")))

    def test_unranked_lobby_is_not_classified_as_ranked(self):
        self.assertNotIn("Рейтинг", app.game_context({"lobby_type": "unranked"}))

    def test_menu_transition_clears_old_match_presence(self):
        result = app.presence_from_gsi({"map": {"game_state": "DOTA_GAMERULES_STATE_INIT"}})
        self.assertEqual(result, {"_clear": True})

    def test_status_key_is_reformatted_when_language_changes(self):
        class Var:
            def __init__(self, value=None): self.value = value
            def get(self): return self.value
            def set(self, value): self.value = value
        class Root:
            def title(self, _value): pass

        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.language = "ru"
        instance.language_var = Var("English")
        instance.status_var = Var("Проверяю обновления…")
        instance.status_message = ("update_checking", {})
        instance.gsi_message = ("steam_search", {})
        instance.gsi_var = Var()
        instance.state_var = Var()
        instance.details_var = Var()
        instance.dota_running = False
        instance.last_presence = None
        instance.tray_icon = None
        instance._localized_widgets = []
        instance.root = Root()
        with (patch.object(instance, "refresh_settings_controls"),
              patch.object(instance, "save_settings")):
            instance.change_language()
        self.assertEqual(instance.status_var.value, "Checking for updates…")
        self.assertEqual(instance.gsi_var.value, "Looking for Dota 2 in Steam libraries…")

    def test_json_guard_rejects_non_finite_and_deep_values(self):
        self.assertFalse(app.json_values_are_safe({"x": float("inf")}))
        value = None
        for _ in range(66):
            value = [value]
        self.assertFalse(app.json_values_are_safe(value))

    def test_gsi_queue_keeps_only_the_latest_bounded_events(self):
        events = app.GSIHandler.events
        old = app.GSIHandler.events
        try:
            app.GSIHandler.events = __import__("queue").Queue(maxsize=2)
            app.GSIHandler.enqueue_latest({"n": 1})
            app.GSIHandler.enqueue_latest({"n": 2})
            app.GSIHandler.enqueue_latest({"n": 3})
            self.assertEqual(app.GSIHandler.events.get_nowait(), {"n": 2})
            self.assertEqual(app.GSIHandler.events.get_nowait(), {"n": 3})
        finally:
            app.GSIHandler.events = old

    def test_english_translation_covers_runtime_status(self):
        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.language = "en"
        self.assertEqual(instance.tr("game_closed"), "Dota is not running")
        self.assertEqual(instance.ui_text("Выбирает героя"), "Picking a hero")

    def test_english_rich_presence_translates_status_and_game_mode(self):
        presence = app.localized_presence({
            "status": "В игре", "details": "Победа · Tinker · 3/1/8",
            "state": "Тренировка", "large_text": "Tinker",
        }, "en")
        self.assertEqual(presence["status"], "In game")
        self.assertEqual(presence["details"], "Victory · Tinker · 3/1/8")
        self.assertEqual(presence["state"], "Practice")

    def test_repeated_identical_presence_is_not_sent_to_discord_twice(self):
        class Var:
            def set(self, _value): pass
        class Rpc:
            def __init__(self): self.calls = []
            def update(self, **kwargs): self.calls.append(kwargs)

        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.dota_running = True
        instance.language = "en"
        instance.rpc = Rpc()
        instance.last_rpc_payload = None
        instance.state_var = Var()
        instance.details_var = Var()
        instance.status_var = Var()
        presence = {
            "status": "В игре", "details": "Axe · 1/0/2", "state": "Тренировка",
            "large_image": "axe", "large_text": "Axe",
        }
        instance.send_presence(presence)
        instance.send_presence(presence)
        self.assertEqual(len(instance.rpc.calls), 1)

    def test_automatic_update_check_does_not_open_a_prompt(self):
        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.language = "en"
        instance.settings = {}
        instance.status_var = type("Status", (), {"set": lambda self, value: setattr(self, "value", value)})()
        instance.latest_available_version = None
        with patch.object(app.messagebox, "askyesno") as prompt:
            version = self.next_release_tag().removeprefix("v")
            instance.finish_update_check({"version": version, "notes": "Fixes"}, None, False, False)
        prompt.assert_not_called()
        self.assertEqual(instance.status_var.value, f"Version {self.next_release_tag().removeprefix('v')} is available")

    def test_manual_update_check_still_offers_the_update(self):
        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.language = "en"
        instance.settings = {}
        instance.status_var = type("Status", (), {"set": lambda self, value: setattr(self, "value", value)})()
        instance.latest_available_version = None
        with (patch.object(app.messagebox, "askyesno", return_value=False) as prompt,
              patch.object(instance, "save_settings")):
            instance.finish_update_check({"version": self.next_release_tag().removeprefix("v"), "notes": "Fixes"}, None, False, True)
        prompt.assert_called_once()

    def test_update_install_status_is_localized(self):
        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.language = "en"
        self.assertIn("restart", instance.tr("update_installing"))
        instance.language = "ru"
        self.assertIn("перезапустится", instance.tr("update_installing"))

    def test_tray_menu_labels_follow_selected_language(self):
        self.assertEqual(app.tray_menu_labels("en"), ("Open Dota Activity", "Exit"))
        self.assertEqual(app.tray_menu_labels("ru"), ("Открыть Dota Activity", "Выход"))


if __name__ == "__main__":
    unittest.main()
