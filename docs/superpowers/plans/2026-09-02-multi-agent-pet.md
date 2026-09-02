# Multi-Agent Pet Branch Implementation Plan

> **Last updated:** 2026-09-02
> **Initiated by:** bloodshed007
> **Model:** gpt-5.6-sol

---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a clean `feat/multi-agent-pet` branch that turns the Claude-only Windows pet into a reusable Claude/Codex/Pi desktop companion backed by AgentHub.

**Architecture:** Port the proven modular multi-agent runtime under generic `agent_pet_*` names, isolate WSL focus command construction, and replace Claude-hook installation with an ownership-safe Windows desktop-app installer. Preserve the existing `.pi-pet` state/settings protocol while keeping remote `main` unchanged.

**Tech Stack:** Python 3.8+ standard library, tkinter, Pillow, Windows ctypes/PowerShell, WSL, unittest, Bash, GitHub

**Design:** `docs/superpowers/specs/2026-09-02-multi-agent-pet-design.md`

---

## File map

| File | Responsibility |
|---|---|
| `agent-pet.pyw` | Window, render loop, interactions, menus, visibility, transition orchestration |
| `agent_pet_state.py` | State protocol, sessions, aggregate priority, transition tracker |
| `agent_pet_render.py` | Pillow frame rendering, session panel, hit rectangles |
| `agent_pet_layered.py` | Windows layered-window blit and foreground-window helpers |
| `agent_pet_notify.py` | Alerts and persisted settings, including `show_sessions` |
| `agent_pet_hub.py` | Injection-safe AgentHub focus command construction |
| `install.py` | Dependency validation, runtime copy, Startup shortcut, launch |
| `uninstall.py` | Owned shortcut/app removal while preserving state and settings |
| `tests/test_agent_pet_state.py` | State-model and transition tests |
| `tests/test_agent_pet_notify.py` | Settings persistence and alert-routing tests |
| `tests/test_agent_pet_render.py` | Headless Pillow rendering and panel-layout tests |
| `tests/test_hub_command.py` | WSL command construction and hostile-input tests |
| `tests/test_install.py` | Install/uninstall pure-function and isolated-copy tests |
| `tests/test_app_contract.py` | Entrypoint wiring and latest UI-setting contract |
| `tests/test_publish_hygiene.sh` | Public-branch path, secret, stale-file, and docs guard |

## Preconditions

Work only in the fresh WSL clone on `feat/multi-agent-pet`. Set a local, untracked source pointer to the approved current pet implementation:

```bash
: "${AGENT_PET_SOURCE_DIR:?Set AGENT_PET_SOURCE_DIR in the current shell to the approved pet source directory}"
: "${AGENT_PET_TEST_PYTHON:?Set AGENT_PET_TEST_PYTHON to the approved Windows Python executable}"
test -x "$AGENT_PET_TEST_PYTHON"
python3() { "$AGENT_PET_TEST_PYTHON" "$@"; }
export -f python3
test "$(git branch --show-current)" = feat/multi-agent-pet
test -z "$(git status --porcelain)"
test -f "$AGENT_PET_SOURCE_DIR/pi-pet.pyw"
test -f "$AGENT_PET_SOURCE_DIR/pi_pet_state.py"
python3 -c 'import PIL, tkinter'
```

The value of `AGENT_PET_SOURCE_DIR` must never be written into a tracked file.

## Task 1: Port the multi-agent state model test-first

**Files:**
- Create: `agent_pet_state.py`
- Create: `tests/test_agent_pet_state.py`

- [ ] **Step 1: Import and rename the state tests before production code**

```bash
mkdir -p tests
cp "$AGENT_PET_SOURCE_DIR/test_pi_pet_state.py" tests/test_agent_pet_state.py
sed -i 's/from pi_pet_state/from agent_pet_state/' tests/test_agent_pet_state.py
sed -i 's/test_pi_pet_state/test_agent_pet_state/g; s/pi_pet_state/agent_pet_state/g' tests/test_agent_pet_state.py
```

Replace the module docstring with:

```python
"""Unit tests for the platform-independent Agent Pet state model."""
```

- [ ] **Step 2: Run the state tests and verify RED**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_agent_pet_state.py' -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_pet_state'`.

- [ ] **Step 3: Port the minimal state implementation**

```bash
cp "$AGENT_PET_SOURCE_DIR/pi_pet_state.py" agent_pet_state.py
```

Replace its opening docstring with:

```python
"""Read and reduce AgentHub's per-session state files.

Both the six-field v2 protocol and legacy three-field records are accepted.
This module has no tkinter or Windows dependencies.
"""
```

Do not change state names, priorities, TTL, done fade, minimum-work threshold, glyphs, or the six-field parser.

- [ ] **Step 4: Run the state tests and verify GREEN**

```bash
python3 -m unittest discover -s tests -p 'test_agent_pet_state.py' -v
```

Expected: 26 tests pass.

- [ ] **Step 5: Verify hygiene and commit**

```bash
python3 -m py_compile agent_pet_state.py tests/test_agent_pet_state.py
git diff --check
git add agent_pet_state.py tests/test_agent_pet_state.py
git commit -m "feat: add multi-agent pet state model"
```

## Task 2: Port settings and notification behavior test-first

**Files:**
- Create: `agent_pet_notify.py`
- Create: `tests/test_agent_pet_notify.py`

- [ ] **Step 1: Write failing settings and alert tests**

Create `tests/test_agent_pet_notify.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_agent_pet_notify.py' -v
```

Expected: FAIL because `agent_pet_notify.py` does not exist.

- [ ] **Step 3: Port the notification module**

```bash
cp "$AGENT_PET_SOURCE_DIR/pi_pet_notify.py" agent_pet_notify.py
```

Use this generic module docstring:

```python
"""Windows sounds/toasts and persisted Agent Pet settings."""
```

Retain the existing best-effort PowerShell boundary, mute settings, window coordinates, `always_show`, and `show_sessions`.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest discover -s tests -p 'test_agent_pet_notify.py' -v
python3 -m unittest discover -s tests -v
git diff --check
git add agent_pet_notify.py tests/test_agent_pet_notify.py
git commit -m "feat: add agent pet settings and alerts"
```

Expected: 30 tests pass.

## Task 3: Build an injection-safe AgentHub focus bridge

**Files:**
- Create: `agent_pet_hub.py`
- Create: `tests/test_hub_command.py`

- [ ] **Step 1: Write failing hub-command tests**

Create `tests/test_hub_command.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest discover -s tests -p 'test_hub_command.py' -v`

Expected: FAIL because `agent_pet_hub.py` does not exist.

- [ ] **Step 3: Implement command construction**

Create `agent_pet_hub.py`:

```python
"""Build the Windows-to-WSL command used to focus an AgentHub window."""

import os


def build_focus_command(window, distro=None, hub_command=None):
    distro = os.environ.get("AGENT_PET_WSL_DISTRO", "") if distro is None else distro
    hub_command = os.environ.get("AGENT_PET_HUB_COMMAND", "hub") if hub_command is None else hub_command
    command = ["wsl.exe"]
    if distro:
        command.extend(["-d", distro])
    command.extend([
        "--", "bash", "-lc", 'exec "$1" focus "$2"',
        "agent-pet", hub_command, window,
    ])
    return command
```

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest discover -s tests -p 'test_hub_command.py' -v
python3 -m unittest discover -s tests -v
git diff --check
git add agent_pet_hub.py tests/test_hub_command.py
git commit -m "feat: add portable agenthub focus command"
```

Expected: 34 tests pass.

## Task 4: Port rendering and Windows layered-window integration

**Files:**
- Create: `agent_pet_render.py`
- Create: `agent_pet_layered.py`
- Create: `tests/test_agent_pet_render.py`

- [ ] **Step 1: Write failing headless render tests**

Create `tests/test_agent_pet_render.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest discover -s tests -p 'test_agent_pet_render.py' -v`

Expected: FAIL because `agent_pet_render.py` does not exist.

- [ ] **Step 3: Port rendering and rename the state import**

```bash
cp "$AGENT_PET_SOURCE_DIR/pi_pet_render.py" agent_pet_render.py
sed -i 's/from pi_pet_state/from agent_pet_state/' agent_pet_render.py
```

Replace the module docstring with:

```python
"""Pillow rendering for the Agent Pet robot and session panel."""
```

- [ ] **Step 4: Run render tests and verify GREEN**

```bash
python3 -m unittest discover -s tests -p 'test_agent_pet_render.py' -v
```

Expected: 3 tests pass when Pillow is installed.

- [ ] **Step 5: Port the Windows layered-window boundary**

```bash
cp "$AGENT_PET_SOURCE_DIR/pi_pet_layered.py" agent_pet_layered.py
```

Replace its module docstring with:

```python
"""Windows per-pixel-alpha blitting and terminal foreground helpers."""
```

Do not change the ctypes structures, premultiplied BGRA conversion, DIB ownership, or foreground-window behavior.

- [ ] **Step 6: Run tests and commit**

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile agent_pet_render.py agent_pet_layered.py
git diff --check
git add agent_pet_render.py agent_pet_layered.py tests/test_agent_pet_render.py
git commit -m "feat: add agent pet rendering"
```

Expected: 37 tests pass.

## Task 5: Integrate the generic desktop entry point and latest UI behavior

**Files:**
- Create: `agent-pet.pyw`
- Create: `tests/test_app_contract.py`

- [ ] **Step 1: Write a failing source contract**

Create `tests/test_app_contract.py`:

```python
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
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `python3 -m unittest discover -s tests -p 'test_app_contract.py' -v`

Expected: ERROR because `agent-pet.pyw` does not exist.

- [ ] **Step 3: Port and generically rename the desktop entry point**

```bash
cp "$AGENT_PET_SOURCE_DIR/pi-pet.pyw" agent-pet.pyw
sed -i 's/from pi_pet_state/from agent_pet_state/; s/from pi_pet_notify/from agent_pet_notify/; s/import pi_pet_render as R/import agent_pet_render as R/; s/from pi_pet_layered/from agent_pet_layered/; s/pi_pet_layered/agent_pet_layered/g' agent-pet.pyw
```

Replace the opening docstring with:

```python
"""Always-on-top Windows companion for AgentHub sessions.

Environment:
  PI_PET_HOME          alternate home for an isolated test instance
  PI_PET_LOG           enable traceback logging
  AGENT_PET_WSL_DISTRO optional WSL distribution for click-to-focus
  AGENT_PET_HUB_COMMAND optional AgentHub command or WSL path
"""
```

Add the hub import:

```python
from agent_pet_hub import build_focus_command
```

Remove the fixed `HUB` constant, change the title to:

```python
root.title("Agent Pet")
```

Replace `_jump_worker` with:

```python
def _jump_worker(window):
    try:
        subprocess.run(
            build_focus_command(window), timeout=15, creationflags=NO_WINDOW,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        log("hub focus %s" % window)
    try:
        focus_window(FRONT_TITLES)
    except Exception:
        log("focus_window")
```

Change alert titles from `pi-pet` to `Agent Pet`. Retain the `show_sessions` menu item and collapsed-panel render behavior exactly.

- [ ] **Step 4: Run contracts and all pure tests**

```bash
python3 -m unittest discover -s tests -p 'test_app_contract.py' -v
python3 -m unittest discover -s tests -v
python3 -m py_compile agent-pet.pyw
git diff --check
```

Expected: 40 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent-pet.pyw tests/test_app_contract.py
git commit -m "feat: add multi-agent desktop entry point"
```

## Task 6: Replace hook installation with desktop-app install and uninstall

**Files:**
- Replace: `install.py`
- Replace: `uninstall.py`
- Create: `tests/test_install.py`

- [ ] **Step 1: Write failing install/uninstall tests**

Create `tests/test_install.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

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
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest discover -s tests -p 'test_install.py' -v`

Expected: FAIL because the existing Claude-only installers do not expose these contracts.

- [ ] **Step 3: Implement the Windows desktop installer**

Replace `install.py` with:

```python
#!/usr/bin/env python3
"""Install Agent Pet as a Windows desktop application."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_FILES = (
    "agent-pet.pyw", "agent_pet_state.py", "agent_pet_render.py",
    "agent_pet_layered.py", "agent_pet_notify.py", "agent_pet_hub.py",
)
SHORTCUT_NAME = "Agent Pet.lnk"
NO_WINDOW = 0x08000000
HERE = Path(__file__).resolve().parent


def app_dir(home=None):
    return Path(home or Path.home()) / ".agent-pet"


def startup_dir(appdata=None):
    root = Path(appdata or os.environ["APPDATA"])
    return root / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def powershell_exe():
    root = os.environ.get("SystemRoot")
    if root:
        candidate = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if candidate.is_file():
            return str(candidate)
    return "powershell.exe"


def find_pythonw():
    candidate = Path(sys.executable).with_name("pythonw.exe")
    if candidate.is_file():
        return candidate
    for name in ("pythonw.exe", "pythonw", "pyw"):
        found = shutil.which(name)
        if found:
            return Path(found)
    print("WARNING: pythonw was not found; a console window may flash.")
    return Path(sys.executable)


def validate_dependencies():
    try:
        import tkinter  # noqa: F401
    except Exception as error:
        raise RuntimeError("tkinter is required; use the standard Windows Python installer") from error
    try:
        import PIL  # noqa: F401
    except Exception as error:
        raise RuntimeError("Pillow is required; run: py -m pip install Pillow") from error


def install_files(source, destination):
    source, destination = Path(source), Path(destination)
    missing = [name for name in APP_FILES if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError("missing runtime files: " + ", ".join(missing))
    destination.mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        shutil.copy2(source / name, destination / name)


def shortcut_create_command(shortcut, pythonw, entrypoint):
    shortcut, pythonw, entrypoint = map(Path, (shortcut, pythonw, entrypoint))
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(%s);"
        "$s.TargetPath=%s;$s.Arguments=%s;$s.WorkingDirectory=%s;$s.Save()"
    ) % (
        ps_quote(shortcut), ps_quote(pythonw),
        ps_quote('"%s"' % entrypoint), ps_quote(entrypoint.parent),
    )
    return [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script]


def main():
    if os.name != "nt":
        print("ERROR: Agent Pet desktop installation requires Windows.")
        return 1
    try:
        validate_dependencies()
        destination = app_dir()
        install_files(HERE, destination)
        pythonw = find_pythonw()
        entrypoint = destination / "agent-pet.pyw"
        shortcut = startup_dir() / SHORTCUT_NAME
        shortcut.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(shortcut_create_command(shortcut, pythonw, entrypoint), check=True,
                       creationflags=NO_WINDOW)
        subprocess.Popen([str(pythonw), str(entrypoint)], close_fds=True,
                         creationflags=NO_WINDOW)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print("ERROR:", error)
        return 1
    print("installed Agent Pet into", destination)
    print("created Startup shortcut", shortcut)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

The installer does not read or write Claude, Codex, Pi, or AgentHub configuration.

- [ ] **Step 4: Implement ownership-safe uninstall helpers**

Replace `uninstall.py` with:

```python
#!/usr/bin/env python3
"""Remove Agent Pet app files and its owned Startup shortcut."""

import os
import subprocess
from pathlib import Path

from install import APP_FILES, app_dir, powershell_exe, ps_quote, startup_dir


def remove_app_files(destination):
    destination = Path(destination)
    for name in APP_FILES:
        path = destination / name
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    try:
        destination.rmdir()
    except OSError:
        pass


def shortcut_target(shortcut):
    script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(%s);$s.TargetPath" % ps_quote(shortcut)
    result = subprocess.run(
        [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def shortcut_is_owned(actual_target, expected_target):
    return os.path.normcase(os.path.abspath(actual_target)) == os.path.normcase(os.path.abspath(expected_target))


def main():
    destination = app_dir()
    entrypoint = destination / "agent-pet.pyw"
    shortcut = startup_dir() / "Agent Pet.lnk"
    if shortcut.exists():
        try:
            if shortcut_is_owned(shortcut_target(shortcut), entrypoint):
                shortcut.unlink()
            else:
                print("kept non-Agent-Pet shortcut:", shortcut)
        except (OSError, subprocess.SubprocessError) as error:
            print("could not inspect shortcut (%s); kept it" % error)
    remove_app_files(destination)
    print("Agent Pet app files removed; AgentHub state and settings were kept.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run install tests and all tests**

```bash
python3 -m unittest discover -s tests -p 'test_install.py' -v
python3 -m unittest discover -s tests -v
python3 -m py_compile install.py uninstall.py
git diff --check
```

Expected: 45 tests pass.

- [ ] **Step 6: Commit**

```bash
git add install.py uninstall.py tests/test_install.py
git commit -m "feat: add agent pet desktop installation"
```

## Task 7: Replace Claude-only docs and enforce public-branch hygiene

**Files:**
- Replace: `README.md`
- Modify: `.gitignore`
- Create: `tests/test_publish_hygiene.sh`
- Delete: `claude-notify.ps1`
- Delete: `claude-pet.pyw`
- Delete: `claude_pet_state.py`

- [ ] **Step 1: Write the failing publish-hygiene test**

Create `tests/test_publish_hygiene.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cloud_root='One''Drive'
patterns="(/mnt/[a-z]/Users/[^/$<{ ]+|[A-Za-z]:\\\\Users\\\\[^\\\\%<{]+|${cloud_root} - [^/]+|gho_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|password[[:space:]]*=|token[[:space:]]*=)"
if grep -RInE "$patterns" --exclude-dir=.git --exclude='test_publish_hygiene.sh' .; then
    exit 1
fi
for stale in claude-notify.ps1 claude-pet.pyw claude_pet_state.py; do
    [[ ! -e "$stale" ]] || { printf 'stale Claude-only file: %s\n' "$stale" >&2; exit 1; }
done
for heading in '## What you see' '## Requirements' '## Install' '## AgentHub integration' \
    '## Configuration' '## Uninstall' '## Troubleshooting'; do
    grep -qF "$heading" README.md || { printf 'missing README heading: %s\n' "$heading" >&2; exit 1; }
done
printf 'publish hygiene: ok\n'
```

- [ ] **Step 2: Run hygiene and verify RED**

Run: `bash tests/test_publish_hygiene.sh`

Expected: FAIL because Claude-only files and documentation remain.

- [ ] **Step 3: Remove obsolete Claude-only runtime files**

```bash
git rm claude-notify.ps1 claude-pet.pyw claude_pet_state.py
```

Do not remove `LICENSE`.

- [ ] **Step 4: Replace README with the branch user contract**

Write `README.md` with:

```markdown
# Agent Pet — multi-agent branch

> **Last updated:** 2026-09-02
> **Initiated by:** bloodshed007
> **Model:** gpt-5.6-sol

---

A Windows desktop companion for Claude Code, Codex, and Pi sessions managed through AgentHub. This experimental successor lives on `feat/multi-agent-pet`; the repository's `main` branch remains the original Claude-only app.

## What you see

- Aggregate animated robot with `needs-you > working > done > idle` priority.
- Optional session panel with agent glyph, name, state, age, and blocked-session hint.
- Click-to-focus for AgentHub tmux windows.
- Per-session chime/toast edges, persisted mute controls, drag position, auto-hide, and **Show sessions**.

## Requirements

- Windows 10 or 11 with WSL2
- Python 3.8+ with tkinter
- Pillow (`py -m pip install Pillow`)
- AgentHub installed in WSL with optional pet integration enabled

## Install

```powershell
git clone --branch feat/multi-agent-pet https://github.com/bloodshed007/claude-pet.git
cd claude-pet
py install.py
```

The installer copies the desktop runtime to `%USERPROFILE%\.agent-pet`, creates the Agent Pet Startup shortcut, and launches it. It does not modify agent hooks.

## AgentHub integration

AgentHub owns Claude/Codex/Pi lifecycle writers. Install those separately from the private AgentHub repository using its optional pet mode. Agent Pet reads `%USERPROFILE%\.pi-pet\sessions`.

State records use:

```text
state|unix_millis|name|agent|window|hint
```

## Configuration

| Variable | Effect |
|---|---|
| `PI_PET_HOME` | Alternate home for an isolated test instance; uses the alternate lock port |
| `PI_PET_LOG` | Enables traceback logging |
| `AGENT_PET_WSL_DISTRO` | Optional WSL distribution for click-to-focus |
| `AGENT_PET_HUB_COMMAND` | Optional AgentHub command or absolute WSL path; default `hub` |

Right-click the robot for mute, always-show, panel visibility, hide, and quit controls. Settings remain in `%USERPROFILE%\.pi-pet\pet.json`.

## Uninstall

```powershell
py uninstall.py
```

Uninstall removes only app files and the owned Startup shortcut. AgentHub hooks, state files, and settings remain.

## Troubleshooting

- **No sessions:** verify AgentHub optional pet integration and `%USERPROFILE%\.pi-pet\sessions`.
- **Click does not focus:** set `AGENT_PET_WSL_DISTRO` or `AGENT_PET_HUB_COMMAND` when defaults do not resolve.
- **No window:** use the standard Windows Python build with tkinter and install Pillow.
- **Pet already running:** quit the existing pet before launching another normal instance.
- **Diagnostics:** set `PI_PET_LOG=1` and inspect `%USERPROFILE%\.pi-pet\pet.log`.

## License

MIT. See [LICENSE](LICENSE).
```

- [ ] **Step 5: Strengthen `.gitignore`**

Ensure `.gitignore` contains:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.env
.env.*
!.env.example
credentials.env
hosts.yml
.pi-pet/
.agent-pet/
```

- [ ] **Step 6: Run hygiene, tests, and commit**

```bash
chmod +x tests/test_publish_hygiene.sh
bash tests/test_publish_hygiene.sh
python3 -m unittest discover -s tests -v
python3 -m py_compile agent_pet_state.py agent_pet_notify.py agent_pet_hub.py \
    agent_pet_render.py agent_pet_layered.py agent-pet.pyw install.py uninstall.py
git diff --check
git add README.md .gitignore tests/test_publish_hygiene.sh
git commit -m "docs: document multi-agent pet branch"
```

Expected: 45 tests pass and hygiene prints `publish hygiene: ok`.

## Task 8: Windows acceptance, final review, and branch-only push

**Files:**
- Review all branch files; modify only defects found test-first.

- [ ] **Step 1: Run the complete WSL-safe suite**

```bash
set -euo pipefail
python3 -m unittest discover -s tests -v
bash tests/test_publish_hygiene.sh
python3 -m py_compile agent_pet_state.py agent_pet_notify.py agent_pet_hub.py \
    agent_pet_render.py agent-pet.pyw install.py uninstall.py
git diff --check
git status --short
```

Expected: 45 tests pass, hygiene and syntax pass, and status has no output.

- [ ] **Step 2: Run tests with the approved Windows interpreter**

Set `AGENT_PET_TEST_PYTHON` locally to the required Windows Python executable without writing it to the repository, then run:

```bash
test -x "$AGENT_PET_TEST_PYTHON"
"$AGENT_PET_TEST_PYTHON" -m unittest discover -s "$(wslpath -w "$PWD/tests")" -v
"$AGENT_PET_TEST_PYTHON" -m py_compile \
    "$(wslpath -w "$PWD/agent_pet_layered.py")" \
    "$(wslpath -w "$PWD/agent-pet.pyw")"
```

Expected: 45 tests pass and Windows-only modules compile.

- [ ] **Step 3: Run an isolated alternate-home smoke test**

Use a temporary Windows directory as `PI_PET_HOME`, launch `agent-pet.pyw` with the approved Windows `pythonw.exe`, verify TCP port 49733 becomes owned, then stop only that process. Do not replace or stop the live normal pet.

```powershell
$env:PI_PET_HOME = Join-Path $env:TEMP "agent-pet-smoke"
$pythonw = $env:AGENT_PET_TEST_PYTHONW
$entrypoint = $env:AGENT_PET_TEST_ENTRYPOINT
if (-not (Test-Path $pythonw) -or -not (Test-Path $entrypoint)) { exit 2 }
$p = Start-Process -PassThru -WindowStyle Hidden $pythonw $entrypoint
Start-Sleep -Seconds 2
if (-not (Get-NetTCPConnection -LocalPort 49733 -State Listen -ErrorAction SilentlyContinue)) { Stop-Process -Id $p.Id -Force; exit 1 }
Stop-Process -Id $p.Id -Force
```

Expected: the isolated process owns port 49733 and exits without affecting port 49732.

- [ ] **Step 4: Run specification and code-quality review**

Review every requirement in `docs/superpowers/specs/2026-09-02-multi-agent-pet-design.md` against the actual branch. Invoke the requesting-code-review workflow, fix Critical and Important findings test-first, and rerun both WSL and Windows verification.

- [ ] **Step 5: Scan the complete branch and history**

```bash
bash tests/test_publish_hygiene.sh
if git log -p origin/main..HEAD | grep -E '(/mnt/[a-z]/Users/[^/$<{ ]+|[A-Za-z]:\\Users\\[^\\%<{]+|gho_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)'; then
    printf 'branch history hygiene failed\n' >&2
    exit 1
fi
git ls-files | grep -E '(^|/)(hosts\.yml|credentials\.env|\.env|sessions/)' && exit 1 || true
```

Expected: no local path, credential pattern, credential file, or generated state is found.

- [ ] **Step 6: Push only the feature branch**

```bash
test "$(git branch --show-current)" = feat/multi-agent-pet
test "$(git rev-parse origin/main)" = c77177ce2be44f50f5773bcbf65de8e6576e9688
git push -u origin feat/multi-agent-pet
git ls-remote --heads origin refs/heads/main refs/heads/feat/multi-agent-pet
git status --short --branch
```

Expected: both remote branches exist, remote `main` retains `c77177c`, and the local feature branch tracks its remote with a clean worktree.

- [ ] **Step 7: Do not merge, tag, or create a pull request**

Report the public branch URL and verification evidence. Leave integration into `main` for a later explicit decision.
