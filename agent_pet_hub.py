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
