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
