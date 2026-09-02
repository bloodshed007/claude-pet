import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_pet_state import Session
import agent_pet_render as render_module


def session(name="alpha", hint=""):
    return Session(
        key=name, state="needs-you" if hint else "working", raw_state="working",
        ts=1, name=name, agent="claude", window="hub:" + name,
        hint=hint, display=name,
    )


class RenderTests(unittest.TestCase):
    def setUp(self):
        render_module.set_scale(1.0)

    def test_robot_only_frame_is_rgba(self):
        image, rows, drag = render_module.render("idle", "idle", [], 0)
        self.assertEqual(image.mode, "RGBA")
        self.assertEqual(rows, [])
        self.assertEqual(len(drag), 4)

    def test_session_panel_adds_clickable_row(self):
        robot, _, _ = render_module.render("idle", "idle", [], 0)
        image, rows, _ = render_module.render("working", "alpha working", [session()], 1)
        self.assertGreater(image.width, robot.width)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1].window, "hub:alpha")

    def test_hint_row_renders(self):
        image, rows, _ = render_module.render("needs-you", "alpha needs you", [session(hint="Ship it?")], 2)
        self.assertGreater(image.height, 0)
        self.assertEqual(rows[0][1].hint, "Ship it?")


if __name__ == "__main__":
    unittest.main()
