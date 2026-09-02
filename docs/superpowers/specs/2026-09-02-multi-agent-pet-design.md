# Multi-Agent Pet Branch Design

> **Last updated:** 2026-09-02
> **Initiated by:** bloodshed007
> **Model:** gpt-5.6-sol

---

**Status:** Approved by the repository owner on 2026-09-02

## Context

The repository's `main` branch is a Claude Code-only Windows desktop companion. A separately evolved desktop pet now tracks Claude Code, Codex, and Pi sessions through AgentHub's shared state-file protocol and includes a session panel, click-to-focus behavior, per-session alerts, high-DPI layered rendering, persisted controls, and the latest panel visibility setting.

The `feat/multi-agent-pet` branch will become a clean, reusable multi-agent successor without changing public `main`. It will be built from the fresh remote clone rather than the dirty archived checkout.

## Goals

- Preserve the current multi-agent pet behavior and latest session-panel setting.
- Support Claude Code, Codex, and Pi session state from AgentHub.
- Remove personal usernames, fixed interpreter paths, fixed WSL distributions, and fixed hub paths.
- Provide an idempotent Windows installer and ownership-safe uninstaller.
- Preserve compatibility with AgentHub's existing state location and six-field protocol.
- Push only the feature branch for review; do not merge it into `main`.

## Non-goals

- Modify AgentHub's tmux CLI or lifecycle hook installers.
- Duplicate Claude, Codex, or Pi event writers in this repository.
- Change the public `main` branch.
- Publish a release or tag from this branch.
- Support native Linux or macOS desktop rendering in this iteration.
- Migrate or delete existing pet settings and session-state files.

## Selected approach

The feature branch replaces the Claude-only runtime with a clearly named multi-agent desktop application. It uses the proven modular runtime as its behavioral baseline, then removes machine-specific assumptions and adds installation coverage. Keeping the work on a branch preserves the original application and gives the successor an isolated review surface.

A raw source snapshot was rejected because it contains workstation-specific paths and historical planning files. Applying only the latest UI tweak to the Claude-only app was rejected because it would omit the multi-agent behavior that the branch is intended to preserve.

## Repository structure

```text
claude-pet/
├── agent-pet.pyw
├── agent_pet_state.py
├── agent_pet_render.py
├── agent_pet_layered.py
├── agent_pet_notify.py
├── agent_pet_hub.py
├── install.py
├── uninstall.py
├── tests/
│   ├── test_agent_pet_state.py
│   ├── test_hub_command.py
│   ├── test_install.py
│   └── test_publish_hygiene.sh
├── docs/
│   └── superpowers/
│       └── specs/
├── README.md
├── LICENSE
└── .gitignore
```

The branch removes the obsolete Claude-only PowerShell notifier and its hook-writing installer behavior. AgentHub remains the sole owner of lifecycle writers and agent hook configuration.

## Components

### Desktop entry point

`agent-pet.pyw` owns the tkinter window, render loop, mouse interactions, visibility rules, menus, per-session transition handling, and click-to-focus orchestration. It depends on the focused state, render, layered-window, notification, and hub-command modules rather than duplicating their internals.

### State model

`agent_pet_state.py` owns the six-field state protocol, backward-compatible three-field parsing, stale-file filtering, done-to-idle relaxation, display-name de-duplication, aggregate priority, age formatting, and per-session transition tracking.

The shared state directory remains:

```text
%USERPROFILE%\.pi-pet\sessions
```

The settings file remains `%USERPROFILE%\.pi-pet\pet.json` so current preferences and window position continue to work.

### Rendering and Windows integration

`agent_pet_render.py` owns Pillow-based frame construction and hit rectangles. `agent_pet_layered.py` owns per-pixel-alpha Windows presentation and foreground-window helpers. `agent_pet_notify.py` owns sounds, toasts, and persisted settings, including `show_sessions`.

### AgentHub focus bridge

Click-to-focus calls AgentHub inside WSL without embedding a username or Linux path.

Configuration:

- `AGENT_PET_WSL_DISTRO`: optional WSL distribution; omitted means the Windows default distribution.
- `AGENT_PET_HUB_COMMAND`: optional command name or absolute WSL path; default `hub`.

`agent_pet_hub.py` builds the focus command as a testable unit. The Windows process invokes `wsl.exe`, then `bash -lc` with the hub command and tmux window passed as positional arguments rather than interpolated shell text. A missing WSL installation, hub command, or tmux window is logged when diagnostics are enabled and never crashes the pet UI.

## User-visible behavior

- The aggregate robot reflects `needs-you > working > done > idle`.
- The session panel shows agent glyph, display name, state, age, and an optional hint.
- Duplicate display names receive stable suffixes.
- Clickable rows focus their AgentHub tmux window and foreground the terminal.
- The robot focuses the first blocked session when the aggregate state is `needs-you`.
- Drag position and mute/visibility settings persist.
- `Show sessions` collapses or restores the side panel without disabling the robot.
- Per-session `needs-you` alerts fire on state edges.
- Done chimes require the configured minimum working duration.
- Auto-hide never hides active `working` or `needs-you` states.

## Installation

The supported Windows flow is:

```powershell
py install.py
```

The installer:

1. Requires Windows and verifies tkinter and Pillow imports.
2. Locates `pythonw.exe` beside the selected interpreter, with a documented fallback.
3. Copies the six runtime files into `%USERPROFILE%\.agent-pet\`.
4. Creates or updates one Startup shortcut using Windows' built-in `WScript.Shell` COM interface.
5. Launches the installed entry point.
6. Is idempotent and does not modify AgentHub, Claude Code, Codex, or Pi configuration.

If Pillow is absent, installation stops with the exact command needed to install it. Existing destination files are replaced only after source validation. Installation never deletes state or settings.

Agent lifecycle setup remains a separate prerequisite performed from the private AgentHub repository with its optional pet integration mode.

## Uninstallation

The supported Windows flow is:

```powershell
py uninstall.py
```

The uninstaller removes only:

- The six files installed under `%USERPROFILE%\.agent-pet\`.
- The Agent Pet Startup shortcut when it points to the installed entry point.
- The empty application directory when possible.

It preserves `%USERPROFILE%\.pi-pet\pet.json`, all session-state files, AgentHub commands, and every agent hook/configuration entry.

## Error handling and safety

- Runtime state-file errors and notification failures remain best-effort and do not stop the UI.
- Installer validation occurs before destination mutation.
- Installer and uninstaller report filesystem or shortcut errors with actionable paths.
- Uninstaller checks shortcut ownership before removal.
- Focus command construction uses positional arguments to avoid shell injection.
- Public-branch hygiene rejects personal paths, company terms, credentials, generated state, caches, and local settings.
- The dirty archived checkout is never used as a branch source or overwritten.

## Testing

Automated tests cover:

- State parsing, backward compatibility, priority, TTL, name de-duplication, clickability, age formatting, and transition edges.
- Hub command construction with default and explicit WSL distributions, custom commands, spaces, and hostile window text.
- Installer file lists, prerequisite failures, idempotent copy behavior, shortcut command construction, and launch command selection using temporary homes and mocked process boundaries.
- Uninstaller ownership checks and preservation of state/settings.
- Repository hygiene and absence of workstation-specific paths.
- Python syntax/import checks for non-GUI modules.

Current-machine acceptance uses the required Windows Python interpreter. State and rendering checks run without replacing the live pet. A second-instance smoke test uses `PI_PET_HOME` and the alternate lock port only after automated tests pass.

## Branch and publication flow

1. Start from remote `main` commit `c77177c` in a fresh WSL clone.
2. Implement on `feat/multi-agent-pet` with test-first commits.
3. Run specification and quality reviews.
4. Scan the complete branch and commit history for local or sensitive material.
5. Push `feat/multi-agent-pet` to the public repository.
6. Leave `main` unchanged and create no tag or pull request unless explicitly requested later.

## Success criteria

- The feature branch contains the complete current multi-agent desktop behavior, including `Show sessions`.
- No source or documentation contains a personal username, fixed local interpreter, fixed WSL distribution, fixed hub path, company path, credential, or generated state.
- A second Windows + WSL system can install the desktop app without editing source.
- The app reads the existing AgentHub state protocol and focuses hub windows through generic discovery.
- Install and uninstall are idempotent and ownership-safe.
- Tests and hygiene checks pass before push.
- Remote `main` remains at its pre-branch commit while `feat/multi-agent-pet` is available for review.
