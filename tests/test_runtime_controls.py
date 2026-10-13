import unittest
from pathlib import Path
from unittest.mock import patch

import app


class RuntimeControlTests(unittest.TestCase):
    def test_dota_process_is_detected_from_tasklist_csv(self):
        self.assertTrue(app.dota_is_listed('"dota2.exe","4120","Console","1","123,456 K"'))

    def test_other_process_does_not_count_as_dota(self):
        self.assertFalse(app.dota_is_listed('"discord.exe","4120","Console","1","123,456 K"'))

    def test_tasklist_header_without_process_is_not_a_match(self):
        self.assertFalse(app.dota_is_listed('INFO: No tasks are running which match the specified criteria.'))


    def test_presence_is_ignored_while_dota_is_closed(self):
        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.dota_running = False
        instance.rpc = None
        instance.last_presence = None
        instance.send_presence({"status": "В игре"})
        self.assertIsNone(instance.last_presence)

    def test_closing_dota_clears_and_closes_discord_rpc(self):
        class Var:
            def __init__(self): self.value = None
            def set(self, value): self.value = value

        class FakeRpc:
            def __init__(self): self.cleared = False; self.closed = False
            def clear(self): self.cleared = True
            def close(self): self.closed = True

        class FakeRoot:
            def after(self, _delay, _callback): pass

        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.dota_cfg_dir = Path("configured")
        instance.dota_running = True
        instance.rpc = FakeRpc()
        rpc = instance.rpc
        instance.last_presence = {"status": "В игре"}
        instance.state_var = Var()
        instance.details_var = Var()
        instance.status_var = Var()
        instance.root = FakeRoot()
        with patch.object(app, "is_dota_running", return_value=False):
            instance.maintenance()
        self.assertTrue(rpc.cleared)
        self.assertTrue(rpc.closed)
        self.assertIsNone(instance.rpc)
        self.assertIsNone(instance.last_presence)
        self.assertEqual(instance.state_var.value, "Dota не запущена")

    def test_frozen_autostart_command_starts_hidden(self):
        with patch.object(app.sys, "frozen", True, create=True), patch.object(app.sys, "executable", r"C:\Apps\Dota Activity.exe"):
            command = app.windows_autostart_command()
        self.assertIn("--background", command)
        self.assertIn("Dota Activity.exe", command)


if __name__ == "__main__":
    unittest.main()
