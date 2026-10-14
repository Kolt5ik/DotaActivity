import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app


class UpdateAndLanguageTests(unittest.TestCase):
    def release(self, tag="v0.0.7", *, prerelease=False, asset=True):
        assets = []
        if asset:
            assets.append({
                "name": f"DotaActivity-{tag}-Windows-x64.exe",
                "browser_download_url": f"https://github.com/Kolt5ik/DotaActivity/releases/download/{tag}/DotaActivity-{tag}-Windows-x64.exe",
            })
        return {"tag_name": tag, "draft": False, "prerelease": prerelease, "assets": assets, "body": "Fixes"}

    def test_finds_new_windows_release_asset(self):
        update = app.parse_release_update(self.release())
        self.assertIsNotNone(update)
        self.assertEqual(update["version"], "0.0.7")
        self.assertTrue(update["url"].endswith("DotaActivity-v0.0.7-Windows-x64.exe"))

    def test_ignores_current_or_older_versions(self):
        self.assertIsNone(app.parse_release_update(self.release("v0.0.6")))
        self.assertIsNone(app.parse_release_update(self.release("v0.0.4")))

    def test_ignores_prereleases_and_missing_windows_asset(self):
        self.assertIsNone(app.parse_release_update(self.release(prerelease=True)))
        self.assertIsNone(app.parse_release_update(self.release(asset=False)))

    def test_rejects_untrusted_download_hosts(self):
        release = self.release()
        release["assets"][0]["browser_download_url"] = "https://example.com/DotaActivity.exe"
        self.assertIsNone(app.parse_release_update(release))

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
            ):
                app.apply_staged_update(4321, installed, ["--background"])
            wait.assert_called_once_with(4321)
            self.assertEqual(installed.read_bytes(), b"new version")
            launch.assert_called_once_with(
                [str(installed), "--background"], cwd=str(root), close_fds=True,
            )

    def test_english_translation_covers_runtime_status(self):
        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.language = "en"
        self.assertEqual(instance.tr("game_closed"), "Dota is not running")
        self.assertEqual(instance.ui_text("Выбирает героя"), "Picking a hero")

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
