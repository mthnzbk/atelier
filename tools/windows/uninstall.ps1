$ErrorActionPreference = 'Stop'
$installRoot = [IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
if (-not (Test-Path -LiteralPath (Join-Path $installRoot 'app\main.py')) -or
    -not (Test-Path -LiteralPath (Join-Path $installRoot 'runtime\python.exe'))) { throw 'Atelier kurulum klasoru dogrulanamadi.' }
$answer = Read-Host 'Kurulum klasorundeki uygulama dosyalari kaldirilsin mi? Ayarlar ve bu klasorun disindaki projeler korunur. (E/H)'
if ($answer -ne 'E') { exit }
foreach ($name in @('app','runtime')) {
    $target = [IO.Path]::GetFullPath((Join-Path $installRoot $name))
    if (-not $target.StartsWith($installRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Gecersiz hedef.' }
    Remove-Item -LiteralPath $target -Recurse -Force
}
foreach ($folder in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
    $shortcut = Join-Path $folder 'Atelier Python Studio.lnk'
    if (Test-Path -LiteralPath $shortcut) { Remove-Item -LiteralPath $shortcut -Force }
}
Write-Host 'Uygulama kaldirildi. Kullanici ayarlari, kurtarma kayitlari ve projeler korunuyor.'
