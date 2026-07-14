param(
  [string]$Title   = 'Claude Code',
  [string]$Message = '',
  [string]$Sound   = 'None',        # 'Asterisk' | 'Exclamation' | 'None'
  [string]$State   = '',            # 'idle'|'working'|'done'|'needs-you' ; '' = don't touch state
  [string]$Action  = '',            # 'end' = remove this session's state file
  [switch]$Toast                    # show a Windows toast only when present
)

$dir = Join-Path $env:USERPROFILE '.claude\pet-sessions'

# Resolve a stable per-session key from the hook's stdin JSON (session_id).
# Guard on IsInputRedirected so a manual/interactive run never blocks on ReadToEnd.
function Get-SessionKey {
  $sid = $null
  try {
    if ([Console]::IsInputRedirected) {
      $raw = [Console]::In.ReadToEnd()
      if ($raw) { $sid = ($raw | ConvertFrom-Json).session_id }
    }
  } catch {}
  if ([string]::IsNullOrWhiteSpace($sid)) { return 'default' }
  return ($sid -replace '[^A-Za-z0-9_.-]', '_')     # sanitize for a filename
}

# 1) Per-session pet state (best-effort)
if ($State -ne '' -or $Action -eq 'end') {
  try {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $key  = Get-SessionKey
    $file = Join-Path $dir ($key + '.txt')
    if ($Action -eq 'end') {
      # only delete when we truly identified the session; never nuke the shared bucket
      if ($key -ne 'default') { Remove-Item $file -Force -ErrorAction SilentlyContinue }
    } else {
      $ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
      [System.IO.File]::WriteAllText($file, "$State|$ts", (New-Object System.Text.UTF8Encoding($false)))
    }
  } catch {}
}

# 2) Sound (best-effort)
if ($Sound -ne 'None') {
  try {
    if ($Sound -eq 'Exclamation') { [System.Media.SystemSounds]::Exclamation.Play() }
    else                          { [System.Media.SystemSounds]::Asterisk.Play() }
  } catch {}
}

# 3) Visual toast via the built-in tray API (no external modules). Best-effort.
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
