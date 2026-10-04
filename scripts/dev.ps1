<#
.SYNOPSIS
  Windows equivalent of the Makefile.   .\scripts\dev.ps1 <target>
  Targets: install dev db migrate backend frontend test test-backend test-frontend lint format typecheck build docker docker-down clean
#>
param([Parameter(Position = 0)][string]$Target = "help")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Be = Join-Path $Root "backend"
$Fe = Join-Path $Root "mock-assessment"

function In($dir, [scriptblock]$block) {
    Push-Location $dir
    try { & $block; if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "command failed ($LASTEXITCODE)" } }
    finally { Pop-Location }
}

switch ($Target) {
    "install"       { In $Be { uv sync }; In $Fe { npm ci } }
    "db"            { In $Root { docker compose up -d db } }
    "migrate"       { In $Be { uv run alembic upgrade head } }
    "backend"       { In $Be { uv run uvicorn app.main:app --reload --port 8000 } }
    "frontend"      { In $Fe { npm run dev } }
    "dev" {
        In $Root { docker compose up -d db }
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Be'; uv run uvicorn app.main:app --reload --port 8000"
        In $Fe { npm run dev }
    }
    "test"          { In $Be { uv run pytest -q }; In $Fe { npm test } }
    "test-backend"  { In $Be { uv run pytest -q } }
    "test-frontend" { In $Fe { npm test } }
    "lint"          { In $Be { uv run ruff check . }; In $Fe { npm run lint }; In $Fe { npx prettier --check src } }
    "format"        { In $Be { uv run ruff check --fix . }; In $Fe { npm run format } }
    "typecheck"     { In $Be { uv run mypy app }; In $Fe { npx tsc -b } }
    "build"         { In $Fe { npm run build } }
    "docker"        { In $Root { docker compose up -d --build } }
    "docker-down"   { In $Root { docker compose down } }
    "clean" {
        foreach ($p in "$Fe\dist", "$Be\.pytest_cache", "$Be\.mypy_cache", "$Be\.ruff_cache") {
            if (Test-Path $p) { Remove-Item -Recurse -Force $p }
        }
        Get-ChildItem $Fe -Filter *.tsbuildinfo | Remove-Item -Force
        Get-ChildItem $Be -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
    }
    default { Get-Help $PSCommandPath; exit 1 }
}
