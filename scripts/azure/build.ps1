#Requires -Version 5
<#
.SYNOPSIS
  Build the two custom ART images for Azure deployment.

.DESCRIPTION
  Builds:
    <User>/art-backend:<Tag>   (from backend/Dockerfile.azure)
    <User>/art-frontend:<Tag>  (from frontend/Dockerfile.azure)

  The frontend image bakes NEXT_PUBLIC_* values at build time.
  Upstream sidecar images (postgres, redis, minio) are NOT built — Azure
  pulls them directly from Docker Hub.

.EXAMPLE
  .\scripts\azure\build.ps1
  .\scripts\azure\build.ps1 -Tag v1
  .\scripts\azure\build.ps1 -Tag v2 -User hoso30 -NextPublicApiUrl "/api/v1"
#>

param(
  [string]$Tag                 = "latest",
  [string]$User                = "hoso30",
  [string]$NextPublicAppName   = "ART Manufacturing",
  [string]$NextPublicApiUrl    = "/api/v1",
  [string]$NextPublicMinioUrl  = "",
  [string]$InternalApiUrl      = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

$backend  = "$User/art-backend:$Tag"
$frontend = "$User/art-frontend:$Tag"

Write-Host ""
Write-Host "== Build $backend ==" -ForegroundColor Cyan
docker build -f backend/Dockerfile.azure -t $backend ./backend
if ($LASTEXITCODE -ne 0) { throw "backend build failed" }

Write-Host ""
Write-Host "== Build $frontend ==" -ForegroundColor Cyan
docker build -f frontend/Dockerfile.azure `
  --build-arg NEXT_PUBLIC_APP_NAME=$NextPublicAppName `
  --build-arg NEXT_PUBLIC_API_URL=$NextPublicApiUrl `
  --build-arg NEXT_PUBLIC_MINIO_URL=$NextPublicMinioUrl `
  --build-arg INTERNAL_API_URL=$InternalApiUrl `
  -t $frontend ./frontend
if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }

Write-Host ""
Write-Host "Built:" -ForegroundColor Green
Write-Host "  $backend"
Write-Host "  $frontend"
