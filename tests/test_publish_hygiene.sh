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
