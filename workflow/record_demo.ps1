# Requires: npm install --no-save playwright ; ffmpeg on PATH.
# Records the local demo UI without production credentials.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python -and $python.Source -notlike '*WindowsApps*') {
  & $python.Source "$PSScriptRoot/daily_deals.py" --run --mode demo | Set-Content "$PSScriptRoot/latest-demo.json"
} elseif (Get-Command wsl -ErrorAction SilentlyContinue) {
  $linuxRoot = "/mnt/c/Users/abhis/OneDrive/Documents/aitx_sat_2026"
  & wsl -d Ubuntu-24.04 -- bash -lc "cd '$linuxRoot' && python3 workflow/daily_deals.py --run --mode demo" | Set-Content "$PSScriptRoot/latest-demo.json"
} else {
  throw "Python 3 is required (or install WSL with Python 3)."
}
Push-Location $root
try {
  $page = ([uri](Join-Path $PSScriptRoot 'demo.html')).AbsoluteUri
  $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
  if (-not $ffmpeg) {
    $ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  }
  if (-not $ffmpeg) { throw 'FFmpeg was not found after installation.' }
  npx playwright screenshot --device="Desktop Chrome" $page workflow/demo.png
  $ffmpegPath = if ($ffmpeg.Source) { $ffmpeg.Source } else { $ffmpeg.FullName }
  & $ffmpegPath -y -loop 1 -i workflow/demo.png -t 12 -r 30 -vf "format=yuv420p" frontend/media/daily-deals-workflow-demo.mp4
} finally { Pop-Location }
