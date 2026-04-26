#Requires -Version 5
<#
.SYNOPSIS
  Build AND push both ART images to Docker Hub. Combines build.ps1 + push.ps1.

.EXAMPLE
  .\scripts\azure\release.ps1                # tag = latest
  .\scripts\azure\release.ps1 -Tag v1
  .\scripts\azure\release.ps1 -Tag v2 -User hoso30 -NextPublicApiUrl /api/v1
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

& "$PSScriptRoot\build.ps1" `
  -Tag $Tag -User $User `
  -NextPublicAppName $NextPublicAppName `
  -NextPublicApiUrl $NextPublicApiUrl `
  -NextPublicMinioUrl $NextPublicMinioUrl `
  -InternalApiUrl $InternalApiUrl
if ($LASTEXITCODE -ne 0) { throw "build step failed" }

& "$PSScriptRoot\push.ps1" -Tag $Tag -User $User
if ($LASTEXITCODE -ne 0) { throw "push step failed" }

Write-Host ""
Write-Host "Release complete: $User/art-backend:$Tag, $User/art-frontend:$Tag" -ForegroundColor Green
