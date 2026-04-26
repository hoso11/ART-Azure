#Requires -Version 5
<#
.SYNOPSIS
  Push the two custom ART images to Docker Hub.

.DESCRIPTION
  You must be logged into Docker Hub as <User> before running this
  (docker login). Docker Hub repo is assumed public — no credentials
  are supplied to Azure at pull time.

.EXAMPLE
  .\scripts\azure\push.ps1
  .\scripts\azure\push.ps1 -Tag v1
#>

param(
  [string]$Tag  = "latest",
  [string]$User = "hoso30"
)

$ErrorActionPreference = "Stop"

$backend  = "$User/art-backend:$Tag"
$frontend = "$User/art-frontend:$Tag"

Write-Host ""
Write-Host "== Push $backend ==" -ForegroundColor Cyan
docker push $backend
if ($LASTEXITCODE -ne 0) { throw "backend push failed" }

Write-Host ""
Write-Host "== Push $frontend ==" -ForegroundColor Cyan
docker push $frontend
if ($LASTEXITCODE -ne 0) { throw "frontend push failed" }

Write-Host ""
Write-Host "Pushed to Docker Hub:" -ForegroundColor Green
Write-Host "  https://hub.docker.com/r/$User/art-backend/tags"
Write-Host "  https://hub.docker.com/r/$User/art-frontend/tags"
