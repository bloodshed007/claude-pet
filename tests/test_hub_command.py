import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_pet_hub import build_focus_command


class HubCommandTests(unittest.TestCase):
    def test_default_distribution_and_command(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            command = build_focus_command("hub:alpha")
        self.assertEqual(command[:2], ["wsl.exe", "--"])
        self.assertEqual(command[-3:], ["agent-pet", "hub", "hub:alpha"])

    def test_explicit_distribution_and_custom_command(self):
        command = build_focus_command(
            "hub:alpha", distro="Ubuntu-24.04", hub_command="/opt/agent hub/bin/hub"
        )
        self.assertEqual(command[:4], ["wsl.exe", "-d", "Ubuntu-24.04", "--"])
        self.assertEqual(command[-2:], ["/opt/agent hub/bin/hub", "hub:alpha"])

    def test_environment_configuration(self):
        env = {"AGENT_PET_WSL_DISTRO": "Work", "AGENT_PET_HUB_COMMAND": "myhub"}
        with mock.patch.dict(os.environ, env, clear=True):
            command = build_focus_command("hub:beta")
        self.assertEqual(command[:4], ["wsl.exe", "-d", "Work", "--"])
        self.assertEqual(command[-2:], ["myhub", "hub:beta"])

    def test_window_text_is_positional_not_interpolated(self):
        window = 'hub:x; touch /tmp/not-allowed $(echo bad)'
        command = build_focus_command(window)
        self.assertNotIn(window, command[command.index("-lc") + 1])
        self.assertEqual(command[-1], window)


if __name__ == "__main__":
    unittest.main()
