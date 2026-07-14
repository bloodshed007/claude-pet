param(
  [string]$Title   = 'Claude Code',
  [string]$Message = '',
  [string]$Sound   = 'None',        # 'Asterisk' | 'Exclamation' | 'None'
  [string]$State   = '',            # 'idle'|'working'|'done'|'needs-you' ; '' = don't touch state
  [string]$Action  = '',            # 'end' = remove this session's state file
  [switch]$Toast                    # show a Windows toast only when present
)

$claude = Join-Path $env:USERPROFILE '.claude'
$dir = Join-Path $claude 'pet-sessions'

# --- read the hook's stdin JSON once (session_id + message).
# Guard on IsInputRedirected so a manual/interactive run never blocks on ReadToEnd.
$hook = $null
try {
  if ([Console]::IsInputRedirected) {
    $raw = [Console]::In.ReadToEnd()
    if ($raw) { $hook = $raw | ConvertFrom-Json }
  }
} catch {}
$msg = if ($hook) { "$($hook.message)" } else { '' }

# The Notification hook (State=needs-you) fires for BOTH real permission prompts
# AND the plain "waiting for your input" idle nudge (~60s after a turn). Ignore
# the idle nudge so it doesn't turn a finished session into a sticky 'needs you'.
# (Last message is saved to pet-lastnotif.txt so the match can be tuned.)
if ($State -eq 'needs-you') {
  try { [System.IO.File]::WriteAllText((Join-Path $claude 'pet-lastnotif.txt'), $msg, (New-Object System.Text.UTF8Encoding($false))) } catch {}
  if ($msg -imatch 'waiting for your input|waiting for input|is waiting for|idle') { return }
}

# --- stable per-session key from session_id, else a shared 'default' bucket ---
$sid = if ($hook -and -not [string]::IsNullOrWhiteSpace("$($hook.session_id)")) { "$($hook.session_id)" } else { 'default' }
$key = $sid -replace '[^A-Za-z0-9_.-]', '_'

# 1) per-session pet state (best-effort)
if ($State -ne '' -or $Action -eq 'end') {
  try {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $file = Join-Path $dir ($key + '.txt')
    if ($Action -eq 'end') {
      if ($key -ne 'default') { Remove-Item $file -Force -ErrorAction SilentlyContinue }
    } else {
      $ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
      [System.IO.File]::WriteAllText($file, "$State|$ts", (New-Object System.Text.UTF8Encoding($false)))
    }
  } catch {}
}

# 2) sound (best-effort)
if ($Sound -ne 'None') {
  try {
    if ($Sound -eq 'Exclamation') { [System.Media.SystemSounds]::Exclamation.Play() }
    else                          { [System.Media.SystemSounds]::Asterisk.Play() }
  } catch {}
}

# 3) visual toast via the built-in tray API (no external modules). Best-effort.
if ($Toast) {
  try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon    = [System.Drawing.SystemIcons]::Information
    $n.Visible = $true
    $tip = if ($Sound -eq 'Exclamation') { [System.Windows.Forms.ToolTipIcon]::Warning }
           else                          { [System.Windows.Forms.ToolTipIcon]::Info }
    $n.ShowBalloonTip(6000, $Title, $Message, $tip)
    Start-Sleep -Milliseconds 600
    $n.Dispose()
  } catch {}
}
