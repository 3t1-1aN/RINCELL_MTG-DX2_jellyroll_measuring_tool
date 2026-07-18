param(
    [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Get-PythonCommand {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }
    throw "Python was not found. Install Python 3.11+ and ensure it is on PATH."
}

$Python = Get-PythonCommand

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$VenvPyInstaller = Join-Path $RepoRoot ".venv\Scripts\pyinstaller.exe"

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt -r requirements-build.txt
& $VenvPyInstaller --clean --noconfirm ".\packaging\RincellLauncher.spec"

$ReleaseRoot = Join-Path $RepoRoot "release"
$ReleaseName = "Rincell-Measurement-Tools-$Version"
$ReleaseDir = Join-Path $ReleaseRoot $ReleaseName
$ZipPath = Join-Path $ReleaseRoot "$ReleaseName.zip"

if (Test-Path $ReleaseDir) {
    Remove-Item $ReleaseDir -Recurse -Force
}
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null
Copy-Item ".\dist\Rincell Launcher" $ReleaseDir -Recurse
Copy-Item ".\.env.example" (Join-Path $ReleaseDir ".env.example") -Force
Copy-Item ".\README.md" (Join-Path $ReleaseDir "README.md") -Force

if (-not (Test-Path ".\credentials.json")) {
    throw "credentials.json is required in the repo root so it can be shipped beside the launcher."
}
Copy-Item ".\credentials.json" (Join-Path $ReleaseDir "credentials.json") -Force

$StartScript = @"
@echo off
cd /d "%~dp0"
"Rincell Launcher.exe"
"@
Set-Content -Path (Join-Path $ReleaseDir "Start Rincell.bat") -Value $StartScript -Encoding ASCII

Compress-Archive -Path $ReleaseDir -DestinationPath $ZipPath -Force

Write-Host "Built $ReleaseName"
Write-Host "Release folder: $ReleaseDir"
Write-Host "Release zip: $ZipPath"
Write-Host "ZIP_PATH=$ZipPath"
