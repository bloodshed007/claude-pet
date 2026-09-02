import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AppContractTests(unittest.TestCase):
    def test_entrypoint_is_generic_and_wired_to_all_modules(self):
        text = (ROOT / "agent-pet.pyw").read_text(encoding="utf-8")
        for module in (
            "agent_pet_state", "agent_pet_notify", "agent_pet_render",
            "agent_pet_layered", "agent_pet_hub",
        ):
            self.assertIn(module, text)
        self.assertIn('root.title("Agent Pet")', text)
        self.assertNotIn("pi_pet_", text)

    def test_latest_show_sessions_control_is_present(self):
        text = (ROOT / "agent-pet.pyw").read_text(encoding="utf-8")
        self.assertIn('("show_sessions", "Show sessions")', text)
        self.assertIn('_sess if _set.get("show_sessions") else []', text)

    def test_no_fixed_distro_hub_or_interpreter(self):
        text = (ROOT / "agent-pet.pyw").read_text(encoding="utf-8")
        self.assertNotIn('"Ubuntu"', text)
        self.assertNotIn('/home/', text)
        self.assertNotIn('C:\\Users\\', text)
        self.assertIn("build_focus_command(window)", text)


if __name__ == "__main__":
    unittest.main()
