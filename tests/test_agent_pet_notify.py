import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_pet_notify as notify_module


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_defaults_include_collapsible_session_panel(self):
        settings = notify_module.Settings(str(self.home))
        self.assertTrue(settings.get("show_sessions"))
        self.assertFalse(settings.get("mute_all"))

    def test_settings_round_trip(self):
        settings = notify_module.Settings(str(self.home))
        settings.set("show_sessions", False)
        settings.set("x", 321)
        loaded = notify_module.Settings(str(self.home))
        self.assertFalse(loaded.get("show_sessions"))
        self.assertEqual(loaded.get("x"), 321)
        stored = json.loads((self.home / ".pi-pet" / "pet.json").read_text(encoding="utf-8"))
        self.assertFalse(stored["show_sessions"])

    def test_done_alert_respects_mute(self):
        settings = notify_module.Settings(str(self.home))
        with mock.patch.object(notify_module, "notify") as send:
            settings.alert("done", "Agent Pet", "done")
            send.assert_called_once()
            settings.set("mute_done", True)
            settings.alert("done", "Agent Pet", "done")
            send.assert_called_once()

    def test_needs_you_uses_toast(self):
        settings = notify_module.Settings(str(self.home))
        with mock.patch.object(notify_module, "notify") as send:
            settings.alert("needs-you", "Agent Pet", "input")
            self.assertTrue(send.call_args.kwargs["toast"])
            self.assertEqual(send.call_args.kwargs["sound"], "Exclamation")


if __name__ == "__main__":
    unittest.main()
