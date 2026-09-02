import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install
import uninstall


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_runtime_file_contract(self):
        self.assertEqual(install.APP_FILES, (
            "agent-pet.pyw", "agent_pet_state.py", "agent_pet_render.py",
            "agent_pet_layered.py", "agent_pet_notify.py", "agent_pet_hub.py",
        ))

    def test_install_files_is_idempotent(self):
        source = self.root / "source"
        destination = self.root / "home" / ".agent-pet"
        source.mkdir()
        for name in install.APP_FILES:
            (source / name).write_text(name, encoding="utf-8")
        install.install_files(source, destination)
        install.install_files(source, destination)
        self.assertEqual(sorted(path.name for path in destination.iterdir()), sorted(install.APP_FILES))

    def test_missing_runtime_fails_before_destination_is_created(self):
        source = self.root / "source"
        destination = self.root / "home" / ".agent-pet"
        source.mkdir()
        with self.assertRaises(FileNotFoundError):
            install.install_files(source, destination)
        self.assertFalse(destination.exists())

    def test_missing_pillow_has_actionable_error(self):
        real_import = __import__

        def import_without_pillow(name, *args, **kwargs):
            if name == "PIL":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_pillow):
            with self.assertRaisesRegex(RuntimeError, "py -m pip install Pillow"):
                install.validate_dependencies()

    def test_shortcut_command_uses_installed_entrypoint(self):
        command = install.shortcut_create_command(
            Path("C:/Users/example/Startup/Agent Pet.lnk"),
            Path("C:/Python/pythonw.exe"),
            Path("C:/Users/example/.agent-pet/agent-pet.pyw"),
        )
        script = command[-1]
        self.assertIn("WScript.Shell", script)
        self.assertIn("agent-pet.pyw", script)
        self.assertIn("pythonw.exe", script)

    def test_uninstall_preserves_state_and_settings(self):
        home = self.root / "home"
        app = home / ".agent-pet"
        app.mkdir(parents=True)
        for name in install.APP_FILES:
            (app / name).write_text(name, encoding="utf-8")
        settings = home / ".pi-pet" / "pet.json"
        settings.parent.mkdir()
        settings.write_text("{}", encoding="utf-8")
        uninstall.remove_app_files(app)
        self.assertTrue(settings.exists())
        self.assertFalse(any((app / name).exists() for name in install.APP_FILES))

    def test_shortcut_ownership_requires_matching_target(self):
        expected = Path("C:/Users/example/.agent-pet/agent-pet.pyw")
        self.assertTrue(uninstall.shortcut_is_owned(str(expected), expected))
        self.assertFalse(uninstall.shortcut_is_owned("C:/Other/app.pyw", expected))


if __name__ == "__main__":
    unittest.main()
