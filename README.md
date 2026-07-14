# claude-pet 🤖

A tiny always-on-top desktop companion for [Claude Code](https://claude.com/claude-code) on Windows. It watches Claude Code's hooks and shows a little **animated robot** whose expression, colour, and motion change in real time — blinking, bobbing, eyes darting while it works — plus a chime + toast when a task finishes or Claude needs your input.

Think of it as the *"your task is done"* nudge, with a pet.

```
        (o)   <- glowing antenna       vector-drawn on a transparent window:
     ┌────────┐                        a rounded terminal-head with a screen
     │  o  o  │ <- eyes                 face, antenna, and little feet. It
     │   >_   │ <- terminal prompt      blinks, bobs, and reacts live — no box.
     └─┐    ┌─┘
       ▘    ▝   <- feet

   idle          working          done            needs-you
   calm eyes,    eyes darting,    happy arc-eyes   wide eyes + a shake
   gentle bob    quicker bob      (fades → idle)   (wins over working)
   blue          cyan  x2, x3…    green            amber + alert sound
```

## What it does

| Claude Code event | Pet reaction | Sound + toast |
|---|---|---|
| you open a session | pet appears, `idle` | — |
| you submit a prompt | `working` | — |
| Claude finishes a turn | `done` → fades to `idle` | ✅ chime + *"Done — back to you"* |
| Claude needs input / permission | `needs-you` | 🔔 alert + *"Claude Code needs you"* |
| you close the session | state cleaned up | — |

**Multiple windows?** Each Claude Code session reports its own state; the pet shows the **highest-priority** one (`needs-you > working > done > idle`) with a **`×N` count** when several share it. So a blocked window is never hidden by a busy one, and one window finishing doesn't reset the pet while another is still working. Exactly **one** pet runs no matter how many windows you open (socket lock on port `49731`).

## Requirements

- **Windows 10 / 11** — uses PowerShell + built-in Windows notifications, no extra installs
- **Python 3.8+** with `tkinter` (bundled with the standard [python.org](https://www.python.org/) installer)
- **Claude Code**

## Install

```powershell
git clone https://github.com/bloodshed007/claude-pet
cd claude-pet
py install.py
```

The installer:
1. copies `claude-pet.pyw`, `claude_pet_state.py`, `claude-notify.ps1` into `%USERPROFILE%\.claude\`
2. wires the hooks into `%USERPROFILE%\.claude\settings.json` (**merging**, not clobbering, your existing settings — re-running just updates in place)
3. launches the pet right away

> **One more step:** open `/hooks` in Claude Code once (or restart it) so it reloads the new hooks. Until then the pet sits `idle` because nothing is writing state yet. After the reload it's fully automatic.

## How it works

```
Claude Code hooks ──► claude-notify.ps1 ──► ~/.claude/pet-sessions/<session_id>.txt
   (settings.json)      writes state,          │   "working|<unix_millis>"
                        plays sound, toast      ▼
                                          claude-pet.pyw  ◄── claude_pet_state.py
                                          polls ~3×/sec, aggregates, draws the bot
```

- Hooks receive Claude Code's `session_id` on **stdin**; the notify script keys each session's state file by it.
- The pet reads the whole folder, drops stale files (a crash backstop), and reduces everything to one `(state, count)`.
- All hooks run `async`, so they add **zero delay** to your turns.

## Customize

Everything lives in `%USERPROFILE%\.claude\`:

- **Too chatty?** The `Stop` hook fires at the end of *every* turn. To silence the audio but keep the pet, remove `-Sound Asterisk` (or drop `-Toast`) from the `Stop` command in `settings.json`.
- **Move / resize / recolour the pet:** edit `claude-pet.pyw` — `W, H`, the `geometry(...)` corner, and the `STATES` colour/face table are all near the top.
- **Always-on (even without Claude Code):** put a shortcut to `claude-pet.pyw` in `shell:startup`.
- **Right-click** the pet for **Hide** / **Quit**.

## Uninstall

```powershell
py uninstall.py
```

Removes the hooks from `settings.json` (leaving your other settings intact) and deletes the copied files. Then right-click the pet → **Quit**.

## Troubleshooting

- **Pet not reacting to a session?** Open `/hooks` once, or restart Claude Code, to reload the hooks.
- **No toast?** Check Windows notification settings / Focus Assist for the *Windows PowerShell* app.
- **Restarting the pet after editing it:** it's single-instance — right-click → **Quit** (or kill whatever process owns port `49731`), then relaunch.
- **Windows only** for now: the pet (tkinter) is cross-platform, but the hooks and notifications are PowerShell-based.

## License

MIT — see [LICENSE](LICENSE).
