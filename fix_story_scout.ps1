$path = "C:\Deep research\roblox_trend_radar_pro\roblox_trend_radar_x\radar\story_scout.py"

if (-not (Test-Path $path)) {
    Write-Error "File not found: $path"
    exit 1
}

Copy-Item $path "$path.bak" -Force

$content = Get-Content $path -Raw

$old = '    candidates = [StoryCandidate(**row) for row in _load_rows()]'

$new = @'
    candidates = []
    for row in _load_rows():
        row.setdefault("api_language", "")
        row.setdefault("english_confidence", 0)
        row.setdefault("detected_game", "")
        candidates.append(StoryCandidate(**row))
'@

if (-not $content.Contains($old)) {
    Write-Error "Target line was not found. No changes were made."
    exit 1
}

$content = $content.Replace($old, $new)
Set-Content -Path $path -Value $content -Encoding UTF8

Write-Host "Patched successfully:" $path
Write-Host "Backup created:" "$path.bak"
