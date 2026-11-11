param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'AtelierStudio'), [switch]$NoShortcuts)
$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $packageRoot 'runtime\pythonw.exe'))) {
    throw 'Bu kurucu yalnizca Windows hazir paketinin icinde calisir.'
}
$resolvedDestination = [IO.Path]::GetFullPath($Destination)
$driveRoot = [IO.Path]::GetPathRoot($resolvedDestination)
if ($resolvedDestination.TrimEnd('\') -eq $driveRoot.TrimEnd('\')) { throw 'Surucu kokune kurulum yapilamaz.' }
New-Item -ItemType Directory -Path $resolvedDestination -Force | Out-Null
foreach ($folder in @('app','runtime')) {
    Copy-Item -LiteralPath (Join-Path $packageRoot $folder) -Destination $resolvedDestination -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $packageRoot 'uninstall.ps1') -Destination $resolvedDestination -Force
if (Test-Path -LiteralPath (Join-Path $packageRoot 'manifest.json')) {
    Copy-Item -LiteralPath (Join-Path $packageRoot 'manifest.json') -Destination $resolvedDestination -Force
}
if (-not $NoShortcuts) {
$shell = New-Object -ComObject WScript.Shell
$startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Atelier Python Studio.lnk'
$desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Atelier Python Studio.lnk'
foreach ($linkPath in @($startMenu,$desktop)) {
    $link = $shell.CreateShortcut($linkPath)
    $link.TargetPath = Join-Path $resolvedDestination 'runtime\pythonw.exe'
    $link.Arguments = '"' + (Join-Path $resolvedDestination 'app\main.py') + '"'
    $link.WorkingDirectory = Join-Path $resolvedDestination 'app\examples'
    $link.Description = 'Atelier Python Studio'
    $link.Save()
}
}
Write-Host "Atelier kuruldu: $resolvedDestination"
Write-Host 'Masaustundeki Atelier Python Studio kisayolundan acabilirsiniz.'
