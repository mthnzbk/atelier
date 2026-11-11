param([int]$ParentProcessId, [string]$InstallRoot, [string]$Payload, [switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
$targetRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$payloadRoot = [IO.Path]::GetFullPath($Payload).TrimEnd('\')
$log = Join-Path $targetRoot 'update.log'
function CheckedChild([string]$root, [string]$name) {
    $target = [IO.Path]::GetFullPath((Join-Path $root $name))
    if (-not $target.StartsWith($root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Gecersiz guncelleme hedefi.' }
    return $target
}
try {
    if (-not (Test-Path -LiteralPath (CheckedChild $targetRoot 'app\main.py')) -or
        -not (Test-Path -LiteralPath (CheckedChild $targetRoot 'runtime\python.exe')) -or
        -not (Test-Path -LiteralPath (CheckedChild $payloadRoot 'manifest.json'))) { throw 'Kurulum veya hazir paket dogrulanamadi.' }
    $deadline = (Get-Date).AddSeconds(120)
    while (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) { throw 'Editor kapanmadi; guncelleme uygulanmadi.' }
        Start-Sleep -Milliseconds 200
    }
    $backupName = '.atelier-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6)
    $backup = CheckedChild $targetRoot $backupName
    New-Item -ItemType Directory -Path $backup | Out-Null
    $moved = @()
    try {
        foreach ($name in @('app','runtime')) {
            $old = CheckedChild $targetRoot $name
            $saved = CheckedChild $backup $name
            Move-Item -LiteralPath $old -Destination $saved
            $moved += $name
            Copy-Item -LiteralPath (CheckedChild $payloadRoot $name) -Destination $targetRoot -Recurse
        }
        foreach ($name in @('manifest.json','install.ps1','uninstall.ps1','kur.cmd','Atelier.cmd','BASLANGIC.txt')) {
            $source = CheckedChild $payloadRoot $name
            if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $targetRoot -Force }
        }
    } catch {
        foreach ($name in $moved) {
            $new = CheckedChild $targetRoot $name
            if (Test-Path -LiteralPath $new) { Remove-Item -LiteralPath $new -Recurse -Force }
            Move-Item -LiteralPath (CheckedChild $backup $name) -Destination $new
        }
        throw
    }
    'Update completed. Previous application: ' + $backup | Set-Content -LiteralPath $log
    if (-not $NoLaunch) {
        Start-Process -FilePath (CheckedChild $targetRoot 'runtime\pythonw.exe') -ArgumentList @('"' + (CheckedChild $targetRoot 'app\main.py') + '"') -WorkingDirectory (CheckedChild $targetRoot 'app\examples') -WindowStyle Hidden
    }
} catch {
    $_ | Out-String | Set-Content -LiteralPath $log
}
