import unittest

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

    def test_english_translation_covers_runtime_status(self):
        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.language = "en"
        self.assertEqual(instance.tr("game_closed"), "Dota is not running")
        self.assertEqual(instance.ui_text("Выбирает героя"), "Picking a hero")


if __name__ == "__main__":
    unittest.main()
