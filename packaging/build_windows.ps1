param(
    [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt
& ".\.venv\Scripts\pyinstaller.exe" --clean --noconfirm ".\packaging\RincellLauncher.spec"

$ReleaseRoot = Join-Path $RepoRoot "release"
$ReleaseName = "Rincell-Measurement-Tools-$Version"
$ReleaseDir = Join-Path $ReleaseRoot $ReleaseName

if (Test-Path $ReleaseDir) {
    Remove-Item $ReleaseDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null
Copy-Item ".\dist\Rincell Launcher" $ReleaseDir -Recurse
Copy-Item ".\.env.example" (Join-Path $ReleaseDir ".env.example") -Force
Copy-Item ".\README.md" (Join-Path $ReleaseDir "README.md") -Force

$StartScript = @"
@echo off
cd /d "%~dp0"
"Rincell Launcher.exe"
"@
Set-Content -Path (Join-Path $ReleaseDir "Start Rincell.bat") -Value $StartScript -Encoding ASCII

Compress-Archive -Path $ReleaseDir -DestinationPath (Join-Path $ReleaseRoot "$ReleaseName.zip") -Force

Write-Host "Built $ReleaseName"
Write-Host "Release folder: $ReleaseDir"
Write-Host "Release zip: $(Join-Path $ReleaseRoot "$ReleaseName.zip")"
