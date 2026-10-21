import unittest
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

import app


class RuntimeControlTests(unittest.TestCase):
    def test_single_instance_mutex_rejects_an_existing_copy(self):
        kernel32 = SimpleNamespace(
            CreateMutexW=Mock(return_value=123),
            CloseHandle=Mock(),
        )
        with (
            patch.object(app, "_is_windows", return_value=True),
            patch.object(app, "_INSTANCE_MUTEX_HANDLE", None),
            patch.object(app.ctypes, "WinDLL", return_value=kernel32, create=True),
            patch.object(app.ctypes, "get_last_error", return_value=183, create=True),
        ):
            self.assertFalse(app.acquire_single_instance())
        kernel32.CloseHandle.assert_called_once_with(123)

    def test_background_duplicate_exits_without_opening_a_window(self):
        with (
            patch.object(app, "acquire_single_instance", return_value=False),
            patch.object(app.sys, "argv", ["DotaActivity.exe", "--background"]),
            patch.object(app.tk, "Tk") as create_window,
        ):
            app.main()
        create_window.assert_not_called()

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

    def test_autostart_button_toggles_windows_setting(self):
        class Value:
            def __init__(self, value=None): self.value = value
            def get(self): return self.value
            def set(self, value): self.value = value

        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.autostart_var = Value(False)
        instance.language = "en"
        instance.status_var = Value()
        with patch.object(app, "set_windows_autostart") as set_autostart:
            instance.toggle_autostart()

        set_autostart.assert_called_once_with(True)
        self.assertTrue(instance.autostart_var.get())
        self.assertEqual(instance.status_var.get(), app.TEXT["en"]["autostart_enabled"])

    def test_autostart_button_rolls_back_when_windows_rejects_change(self):
        class Value:
            def __init__(self, value=None): self.value = value
            def get(self): return self.value
            def set(self, value): self.value = value

        instance = app.DotaActivityApp.__new__(app.DotaActivityApp)
        instance.autostart_var = Value(False)
        instance.language = "en"
        with (
            patch.object(app, "set_windows_autostart", side_effect=OSError("access denied")),
            patch.object(app.messagebox, "showerror") as show_error,
        ):
            instance.toggle_autostart()

        self.assertFalse(instance.autostart_var.get())
        show_error.assert_called_once()

    def test_existing_autostart_entry_is_migrated_to_current_executable(self):
        class FakeKey:
            def __enter__(self): return self
            def __exit__(self, *_args): pass

        key = FakeKey()
        existing = r'"C:\Old\DotaActivity.exe" --background'
        updated = []
        winreg = SimpleNamespace(
            HKEY_CURRENT_USER=1, KEY_QUERY_VALUE=2, KEY_SET_VALUE=4, REG_SZ=1,
            OpenKey=lambda *_args: key,
            QueryValueEx=lambda *_args: (existing, 1),
            SetValueEx=lambda _key, name, _reserved, kind, value: updated.append((name, kind, value)),
        )
        with patch.dict(sys.modules, {"winreg": winreg}), patch.object(
            app, "windows_autostart_command", return_value=r'"C:\New\DotaActivity.exe" --background'
        ):
            migrated = app.migrate_windows_autostart()

        self.assertTrue(migrated)
        self.assertEqual(updated, [(app.AUTOSTART_NAME, winreg.REG_SZ, r'"C:\New\DotaActivity.exe" --background')])

    def test_autostart_migration_leaves_disabled_startup_disabled(self):
        class FakeKey:
            def __enter__(self): return self
            def __exit__(self, *_args): pass

        winreg = SimpleNamespace(
            HKEY_CURRENT_USER=1, KEY_QUERY_VALUE=2, KEY_SET_VALUE=4, REG_SZ=1,
            OpenKey=lambda *_args: FakeKey(),
            QueryValueEx=lambda *_args: (_ for _ in ()).throw(FileNotFoundError()),
            SetValueEx=lambda *_args: self.fail("Must not enable startup during migration"),
        )
        with patch.dict(sys.modules, {"winreg": winreg}):
            self.assertFalse(app.migrate_windows_autostart())


if __name__ == "__main__":
    unittest.main()
